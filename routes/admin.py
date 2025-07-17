from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, create_access_token, get_jwt_identity
from app import db, socketio
from models.admin import Admin
from models.order import Order
from models.user import User
from models.menu import MenuItem
from utils.sms_service import SMSService
from datetime import datetime, timedelta
from sqlalchemy import func, text
import csv
import io

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/login', methods=['POST'])
def admin_login():
    """Admin login with email and password"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Find admin
        admin = Admin.query.filter_by(email=email, is_active=True).first()
        
        if not admin or not admin.check_password(password):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Update last login
        admin.update_last_login(request.remote_addr)
        
        # Create JWT token
        access_token = create_access_token(
            identity=str(admin.id),
            additional_claims={'role': admin.role, 'type': 'admin'}
        )
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'admin': admin.to_dict(include_permissions=True)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Admin login error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/orders', methods=['GET'])
@jwt_required()
def get_all_orders():
    """Get all orders for admin dashboard"""
    try:
        # Verify admin access
        admin_id = get_jwt_identity()
        admin = Admin.query.get(int(admin_id))
        
        if not admin or not admin.has_permission('manage_orders'):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        status = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        search = request.args.get('search', '').strip()
        
        # Build query
        orders_query = Order.query
        
        if status:
            orders_query = orders_query.filter_by(status=status)
        
        if date_from:
            try:
                date_from_obj = datetime.fromisoformat(date_from)
                orders_query = orders_query.filter(Order.created_at >= date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.fromisoformat(date_to) + timedelta(days=1)
                orders_query = orders_query.filter(Order.created_at < date_to_obj)
            except ValueError:
                pass
        
        if search:
            orders_query = orders_query.filter(
                db.or_(
                    Order.order_number.contains(search),
                    Order.customer_name.contains(search),
                    Order.customer_phone.contains(search)
                )
            )
        
        # Paginate results
        orders_pagination = orders_query.order_by(Order.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        orders_data = [order.to_summary_dict() for order in orders_pagination.items]
        
        return jsonify({
            'orders': orders_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': orders_pagination.total,
                'pages': orders_pagination.pages,
                'has_next': orders_pagination.has_next,
                'has_prev': orders_pagination.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get all orders error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/orders/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details(order_id):
    """Get detailed order information"""
    try:
        admin_id = get_jwt_identity()
        admin = Admin.query.get(int(admin_id))
        
        if not admin or not admin.has_permission('manage_orders'):
            return jsonify({'error': 'Access denied'}), 403
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        return jsonify({'order': order.to_dict()}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get order details error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@jwt_required()
def update_order_status(order_id):
    """Update order status"""
    try:
        admin_id = get_jwt_identity()
        admin = Admin.query.get(int(admin_id))
        
        if not admin or not admin.has_permission('manage_orders'):
            return jsonify({'error': 'Access denied'}), 403
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        note = data.get('note', '')
        
        valid_statuses = [
            'pending', 'confirmed', 'preparing', 'ready_for_pickup',
            'out_for_delivery', 'delivered', 'cancelled', 'refunded'
        ]
        
        if new_status not in valid_statuses:
            return jsonify({'error': 'Invalid status'}), 400
        
        # Update order status
        order.update_status(new_status, note, f'admin_{admin.id}')
        
        # Send notification to customer
        try:
            sms_service = SMSService()
            sms_service.send_order_notification(
                order.customer_phone, 
                order.order_number, 
                new_status
            )
        except Exception as e:
            current_app.logger.error(f"SMS notification error: {str(e)}")
        
        # Emit real-time update
        socketio.emit('order_status_updated', {
            'order_id': order.id,
            'order_number': order.order_number,
            'status': new_status,
            'note': note
        })
        
        return jsonify({
            'message': 'Order status updated successfully',
            'order': order.to_summary_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update order status error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/dashboard/stats', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        admin_id = get_jwt_identity()
        admin = Admin.query.get(int(admin_id))
        
        if not admin or not admin.has_permission('view_analytics'):
            return jsonify({'error': 'Access denied'}), 403
        
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Today's stats
        today_orders = Order.query.filter(
            func.date(Order.created_at) == today
        ).count()
        
        today_revenue = db.session.query(func.sum(Order.total)).filter(
            func.date(Order.created_at) == today,
            Order.payment_status == 'completed'
        ).scalar() or 0
        
        # Pending orders
        pending_orders = Order.query.filter_by(status='pending').count()
        active_orders = Order.query.filter(
            Order.status.in_(['confirmed', 'preparing', 'ready_for_pickup', 'out_for_delivery'])
        ).count()
        
        # Weekly stats
        week_orders = Order.query.filter(
            Order.created_at >= week_ago
        ).count()
        
        week_revenue = db.session.query(func.sum(Order.total)).filter(
            Order.created_at >= week_ago,
            Order.payment_status == 'completed'
        ).scalar() or 0
        
        # Monthly stats
        month_orders = Order.query.filter(
            Order.created_at >= month_ago
        ).count()
        
        month_revenue = db.session.query(func.sum(Order.total)).filter(
            Order.created_at >= month_ago,
            Order.payment_status == 'completed'
        ).scalar() or 0
        
        # Popular items
        popular_items = MenuItem.query.filter_by(is_available=True).order_by(
            MenuItem.order_count.desc()
        ).limit(5).all()
        
        # Recent orders
        recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
        
        return jsonify({
            'stats': {
                'today': {
                    'orders': today_orders,
                    'revenue': round(today_revenue, 2)
                },
                'pending_orders': pending_orders,
                'active_orders': active_orders,
                'week': {
                    'orders': week_orders,
                    'revenue': round(week_revenue, 2)
                },
                'month': {
                    'orders': month_orders,
                    'revenue': round(month_revenue, 2)
                }
            },
            'popular_items': [item.to_dict() for item in popular_items],
            'recent_orders': [order.to_summary_dict() for order in recent_orders]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get dashboard stats error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/orders/export', methods=['GET'])
@jwt_required()
def export_orders():
    """Export orders to CSV"""
    try:
        admin_id = get_jwt_identity()
        admin = Admin.query.get(int(admin_id))
        
        if not admin or not admin.has_permission('view_analytics'):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get query parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        status = request.args.get('status')
        
        # Build query
        orders_query = Order.query
        
        if status:
            orders_query = orders_query.filter_by(status=status)
        
        if date_from:
            try:
                date_from_obj = datetime.fromisoformat(date_from)
                orders_query = orders_query.filter(Order.created_at >= date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.fromisoformat(date_to) + timedelta(days=1)
                orders_query = orders_query.filter(Order.created_at < date_to_obj)
            except ValueError:
                pass
        
        orders = orders_query.order_by(Order.created_at.desc()).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Order Number', 'Customer Name', 'Customer Phone', 'Status', 
            'Total Amount', 'Payment Method', 'Time Slot', 'Scheduled For',
            'Created At', 'Delivery Address', 'Items Count'
        ])
        
        # Write data
        for order in orders:
            writer.writerow([
                order.order_number,
                order.customer_name,
                order.customer_phone,
                order.status,
                order.total,
                order.payment_method,
                order.time_slot,
                order.scheduled_for.isoformat() if order.scheduled_for else '',
                order.created_at.isoformat() if order.created_at else '',
                order.delivery_address_full,
                order.item_count
            ])
        
        output.seek(0)
        csv_content = output.getvalue()
        output.close()
        
        return jsonify({
            'csv_data': csv_content,
            'filename': f'orders_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv',
            'total_orders': len(orders)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Export orders error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/menu/items', methods=['GET'])
@jwt_required()
def get_menu_items():
    """Get all menu items for admin"""
    try:
        admin_id = get_jwt_identity()
        admin = Admin.query.get(int(admin_id))
        
        if not admin or not admin.has_permission('manage_menu'):
            return jsonify({'error': 'Access denied'}), 403
        
        items = MenuItem.query.all()
        items_data = [item.to_dict() for item in items]
        
        return jsonify({'items': items_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get menu items error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/menu/items/<int:item_id>/availability', methods=['PUT'])
@jwt_required()
def toggle_item_availability(item_id):
    """Toggle menu item availability"""
    try:
        admin_id = get_jwt_identity()
        admin = Admin.query.get(int(admin_id))
        
        if not admin or not admin.has_permission('manage_menu'):
            return jsonify({'error': 'Access denied'}), 403
        
        item = MenuItem.query.get(item_id)
        if not item:
            return jsonify({'error': 'Menu item not found'}), 404
        
        data = request.get_json()
        is_available = data.get('is_available')
        
        if is_available is None:
            return jsonify({'error': 'is_available field is required'}), 400
        
        item.is_available = bool(is_available)
        item.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': f'Item {"enabled" if is_available else "disabled"} successfully',
            'item': item.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Toggle item availability error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500