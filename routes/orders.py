from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_socketio import emit
from app import db, socketio
from models.user import User
from models.order import Order
from models.menu import MenuItem
from utils.validators import validate_order_items, validate_delivery_address, validate_time_slot, validate_payment_method
from utils.sms_service import SMSService
from datetime import datetime, timedelta
import json

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/', methods=['POST'])
@jwt_required()
def place_order():
    """Place a new order"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['items', 'delivery_address', 'time_slot', 'scheduled_for', 'payment_method']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate items
        is_valid, message = validate_order_items(data['items'])
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Validate delivery address
        is_valid, message = validate_delivery_address(data['delivery_address'])
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Validate time slot
        if not validate_time_slot(data['time_slot']):
            return jsonify({'error': 'Invalid time slot'}), 400
        
        # Validate payment method
        if not validate_payment_method(data['payment_method']):
            return jsonify({'error': 'Invalid payment method'}), 400
        
        # Validate scheduled time
        try:
            scheduled_for = datetime.fromisoformat(data['scheduled_for'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid scheduled time format'}), 400
        
        # Check if scheduled time is in the future
        if scheduled_for <= datetime.utcnow():
            return jsonify({'error': 'Scheduled time must be in the future'}), 400
        
        # Calculate pricing
        subtotal = sum(item['price'] * item['quantity'] for item in data['items'])
        
        # Determine delivery charges based on zone
        delivery_address = data['delivery_address']
        delivery_zone = delivery_address.get('delivery_zone', 'other_areas')
        delivery_charges = 0 if delivery_zone == 'brigade_gateway' else 30
        
        # Calculate taxes (5% GST)
        taxes = round(subtotal * 0.05, 2)
        
        # Apply discounts if any
        discount = data.get('discount', 0)
        
        # Handle wallet usage
        wallet_used = min(data.get('wallet_amount', 0), user.wallet_balance)
        
        total = subtotal + delivery_charges + taxes - discount - wallet_used
        
        if total < 0:
            total = 0
        
        # Create order
        order = Order(
            customer_id=user.id,
            customer_name=user.name or f"User {user.phone[-4:]}",
            customer_phone=user.phone,
            customer_email=user.email,
            subtotal=subtotal,
            delivery_charges=delivery_charges,
            taxes=taxes,
            discount=discount,
            wallet_used=wallet_used,
            total=total,
            delivery_name=delivery_address['name'],
            delivery_phone=delivery_address['phone'],
            delivery_address_line1=delivery_address['address_line1'],
            delivery_address_line2=delivery_address.get('address_line2', ''),
            delivery_landmark=delivery_address.get('landmark', ''),
            delivery_city=delivery_address['city'],
            delivery_pincode=delivery_address['pincode'],
            delivery_latitude=delivery_address.get('latitude'),
            delivery_longitude=delivery_address.get('longitude'),
            delivery_zone=delivery_zone,
            time_slot=data['time_slot'],
            scheduled_for=scheduled_for,
            payment_method=data['payment_method'],
            special_instructions=data.get('special_instructions', ''),
            source='website'
        )
        
        # Set order items
        order.set_items(data['items'])
        
        # Calculate estimated delivery time
        order.calculate_estimated_delivery_time()
        
        # Calculate loyalty points
        order.calculate_loyalty_points()
        
        db.session.add(order)
        
        # Deduct wallet amount if used
        if wallet_used > 0:
            user.deduct_wallet_balance(
                wallet_used, 
                f"Used for order {order.order_number}",
                order.id
            )
        
        db.session.commit()
        
        # Update menu item order counts
        for item in data['items']:
            menu_item = MenuItem.query.filter_by(item_id=item['item_id']).first()
            if menu_item:
                menu_item.increment_order_count()
        
        db.session.commit()
        
        # Send notifications
        try:
            # SMS notification to customer
            sms_service = SMSService()
            sms_service.send_order_notification(user.phone, order.order_number, 'confirmed')
            
            # Real-time notification to admin
            socketio.emit('new_order', {
                'order': order.to_summary_dict()
            }, room='admin')
            
        except Exception as e:
            current_app.logger.error(f"Notification error: {str(e)}")
        
        return jsonify({
            'message': 'Order placed successfully',
            'order': order.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Place order error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@orders_bp.route('/', methods=['GET'])
@jwt_required()
def get_user_orders():
    """Get user's orders"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 10)), 50)
        status = request.args.get('status')
        
        # Build query
        orders_query = Order.query.filter_by(customer_id=user.id)
        
        if status:
            orders_query = orders_query.filter_by(status=status)
        
        # Paginate results
        orders_pagination = orders_query.order_by(Order.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        orders_data = [order.to_dict(include_items=False) for order in orders_pagination.items]
        
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
        current_app.logger.error(f"Get user orders error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@orders_bp.route('/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details(order_id):
    """Get specific order details"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        order = Order.query.filter_by(id=order_id, customer_id=user.id).first()
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        return jsonify({'order': order.to_dict()}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get order details error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@orders_bp.route('/<int:order_id>/cancel', methods=['PUT'])
@jwt_required()
def cancel_order(order_id):
    """Cancel an order"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        order = Order.query.filter_by(id=order_id, customer_id=user.id).first()
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        if not order.can_be_cancelled():
            return jsonify({'error': 'Order cannot be cancelled at this stage'}), 400
        
        data = request.get_json()
        cancellation_reason = data.get('reason', 'Cancelled by customer')
        
        # Update order status
        order.update_status('cancelled', cancellation_reason, f'customer_{user.id}')
        order.cancellation_reason = cancellation_reason
        
        # Process refund if payment was made
        if order.payment_status == 'completed':
            order.refund_amount = order.total
            order.refund_reason = cancellation_reason
            order.refund_processed_at = datetime.utcnow()
            # In real implementation, integrate with payment gateway for refund
        
        # Refund wallet amount if used
        if order.wallet_used > 0:
            user.wallet_balance += order.wallet_used
            # Record wallet transaction
            # (This would be handled by a WalletTransaction model)
        
        db.session.commit()
        
        # Send notifications
        try:
            sms_service = SMSService()
            sms_service.send_order_notification(user.phone, order.order_number, 'cancelled')
            
            # Notify admin
            socketio.emit('order_cancelled', {
                'order': order.to_summary_dict()
            }, room='admin')
            
        except Exception as e:
            current_app.logger.error(f"Cancel notification error: {str(e)}")
        
        return jsonify({
            'message': 'Order cancelled successfully',
            'order': order.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Cancel order error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@orders_bp.route('/<int:order_id>/track', methods=['GET'])
@jwt_required()
def track_order(order_id):
    """Get order tracking information"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        order = Order.query.filter_by(id=order_id, customer_id=user.id).first()
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        tracking_info = {
            'order_number': order.order_number,
            'status': order.status,
            'status_history': order.get_status_history(),
            'tracking_updates': order.get_tracking_updates(),
            'estimated_delivery_time': order.estimated_delivery_time,
            'scheduled_for': order.scheduled_for.isoformat() if order.scheduled_for else None,
            'delivery_partner': {
                'name': order.delivery_partner_name,
                'phone': order.delivery_partner_phone,
                'vehicle': order.delivery_partner_vehicle
            } if order.delivery_partner_name else None
        }
        
        return jsonify({'tracking': tracking_info}), 200
        
    except Exception as e:
        current_app.logger.error(f"Track order error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@orders_bp.route('/<int:order_id>/feedback', methods=['POST'])
@jwt_required()
def submit_feedback(order_id):
    """Submit feedback for completed order"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        order = Order.query.filter_by(id=order_id, customer_id=user.id).first()
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        if order.status != 'delivered':
            return jsonify({'error': 'Feedback can only be submitted for delivered orders'}), 400
        
        if order.rating:
            return jsonify({'error': 'Feedback already submitted for this order'}), 400
        
        data = request.get_json()
        
        # Validate rating
        rating = data.get('rating')
        if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400
        
        # Update order with feedback
        order.rating = rating
        order.feedback_comment = data.get('comment', '').strip()
        order.feedback_submitted_at = datetime.utcnow()
        
        # Update menu item ratings
        for item_data in order.get_items():
            menu_item = MenuItem.query.filter_by(item_id=item_data['item_id']).first()
            if menu_item:
                menu_item.update_rating(rating)
        
        # Add loyalty points for feedback
        user.add_loyalty_points(5, f"Feedback for order {order.order_number}")
        
        db.session.commit()
        
        return jsonify({
            'message': 'Feedback submitted successfully',
            'loyalty_points_earned': 5
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Submit feedback error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@orders_bp.route('/<int:order_id>/reorder', methods=['POST'])
@jwt_required()
def reorder(order_id):
    """Reorder items from a previous order"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        original_order = Order.query.filter_by(id=order_id, customer_id=user.id).first()
        
        if not original_order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Get original order items
        original_items = original_order.get_items()
        
        # Check item availability and get current prices
        updated_items = []
        unavailable_items = []
        
        for item in original_items:
            menu_item = MenuItem.query.filter_by(item_id=item['item_id'], is_available=True).first()
            if menu_item:
                updated_item = {
                    'item_id': item['item_id'],
                    'name': menu_item.name,
                    'price': menu_item.price,  # Use current price
                    'quantity': item['quantity'],
                    'category': menu_item.category,
                    'tags': menu_item.get_tags()
                }
                updated_items.append(updated_item)
            else:
                unavailable_items.append(item['name'])
        
        if not updated_items:
            return jsonify({'error': 'All items from the original order are currently unavailable'}), 400
        
        response_data = {
            'items': updated_items,
            'original_delivery_address': {
                'name': original_order.delivery_name,
                'phone': original_order.delivery_phone,
                'address_line1': original_order.delivery_address_line1,
                'address_line2': original_order.delivery_address_line2,
                'landmark': original_order.delivery_landmark,
                'city': original_order.delivery_city,
                'pincode': original_order.delivery_pincode,
                'delivery_zone': original_order.delivery_zone
            }
        }
        
        if unavailable_items:
            response_data['unavailable_items'] = unavailable_items
            response_data['message'] = f"Some items are no longer available: {', '.join(unavailable_items)}"
        
        return jsonify(response_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Reorder error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500