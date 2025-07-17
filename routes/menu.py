from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.menu import MenuItem, MenuManager
from models.user import User
from datetime import datetime

menu_bp = Blueprint('menu', __name__)

@menu_bp.route('/', methods=['GET'])
def get_menu():
    """Get menu items filtered by time slot"""
    try:
        time_slot = request.args.get('time_slot')
        category = request.args.get('category')
        popular_only = request.args.get('popular') == 'true'
        
        if time_slot:
            # Get menu for specific time slot
            menu = MenuManager.get_menu_by_time_slot(time_slot)
        else:
            # Get all available items
            items_query = MenuItem.query.filter_by(is_available=True)
            
            if category:
                items_query = items_query.filter_by(category=category)
            
            if popular_only:
                items_query = items_query.filter_by(is_popular=True)
            
            items = items_query.all()
            
            # Group by category
            menu = {}
            for item in items:
                if item.category not in menu:
                    menu[item.category] = []
                menu[item.category].append(item.to_dict())
        
        return jsonify({
            'menu': menu,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get menu error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@menu_bp.route('/item/<item_id>', methods=['GET'])
def get_menu_item(item_id):
    """Get specific menu item details"""
    try:
        item = MenuItem.query.filter_by(item_id=item_id, is_available=True).first()
        
        if not item:
            return jsonify({'error': 'Menu item not found'}), 404
        
        return jsonify({'item': item.to_dict()}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get menu item error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@menu_bp.route('/search', methods=['GET'])
def search_menu():
    """Search menu items"""
    try:
        query = request.args.get('q', '').strip()
        category = request.args.get('category')
        tags = request.args.get('tags', '').split(',') if request.args.get('tags') else None
        
        if not query and not category and not tags:
            return jsonify({'error': 'Search query, category, or tags required'}), 400
        
        items = MenuManager.search_items(query, category, tags)
        
        # Group results by category
        results = {}
        for item in items:
            if item.category not in results:
                results[item.category] = []
            results[item.category].append(item.to_dict())
        
        return jsonify({
            'results': results,
            'total_items': len(items)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Search menu error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@menu_bp.route('/popular', methods=['GET'])
def get_popular_items():
    """Get popular menu items"""
    try:
        limit = min(int(request.args.get('limit', 10)), 20)  # Max 20 items
        
        popular_items = MenuManager.get_popular_items(limit)
        items_data = [item.to_dict() for item in popular_items]
        
        return jsonify({
            'popular_items': items_data,
            'count': len(items_data)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get popular items error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@menu_bp.route('/recommendations', methods=['GET'])
@jwt_required()
def get_recommendations():
    """Get personalized recommendations for user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        recommendations = MenuManager.get_recommendations_for_user(user)
        items_data = [item.to_dict() for item in recommendations]
        
        return jsonify({
            'recommendations': items_data,
            'count': len(items_data)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get recommendations error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@menu_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get available menu categories"""
    try:
        categories = db.session.query(MenuItem.category).filter_by(is_available=True).distinct().all()
        category_list = [cat[0] for cat in categories]
        
        # Category display names
        category_info = {
            'breakfast': {
                'name': 'Breakfast',
                'description': 'Start your day with our healthy breakfast options',
                'icon': '🌅',
                'time_range': '8:00 AM - 11:00 AM'
            },
            'lunch_dinner': {
                'name': 'Lunch & Dinner',
                'description': 'Wholesome meals for lunch and dinner',
                'icon': '🍽️',
                'time_range': '12:00 PM - 3:00 PM, 7:00 PM - 10:00 PM'
            },
            'snacks': {
                'name': 'Snacks',
                'description': 'Quick bites and evening snacks',
                'icon': '🥪',
                'time_range': 'All day'
            },
            'salads': {
                'name': 'Salads',
                'description': 'Fresh and healthy salad options',
                'icon': '🥗',
                'time_range': 'All day'
            },
            'beverages': {
                'name': 'Beverages',
                'description': 'Refreshing drinks and traditional beverages',
                'icon': '🥤',
                'time_range': 'All day'
            }
        }
        
        categories_with_info = []
        for cat in category_list:
            if cat in category_info:
                info = category_info[cat].copy()
                info['slug'] = cat
                categories_with_info.append(info)
        
        return jsonify({'categories': categories_with_info}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get categories error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@menu_bp.route('/tags', methods=['GET'])
def get_tags():
    """Get available dietary tags"""
    try:
        # Get unique tags from all menu items
        items = MenuItem.query.filter_by(is_available=True).all()
        all_tags = set()
        
        for item in items:
            tags = item.get_tags()
            all_tags.update(tags)
        
        # Tag descriptions
        tag_info = {
            'vegetarian': {'name': 'Vegetarian', 'icon': '🥬', 'color': 'green'},
            'non_vegetarian': {'name': 'Non-Vegetarian', 'icon': '🍗', 'color': 'red'},
            'vegan': {'name': 'Vegan', 'icon': '🌱', 'color': 'green'},
            'jain': {'name': 'Jain', 'icon': '🙏', 'color': 'orange'},
            'healthy': {'name': 'Healthy Choice', 'icon': '💚', 'color': 'green'},
            'protein_rich': {'name': 'High Protein', 'icon': '💪', 'color': 'blue'},
            'spicy': {'name': 'Spicy', 'icon': '🌶️', 'color': 'red'},
            'mild': {'name': 'Mild', 'icon': '😊', 'color': 'blue'},
            'popular': {'name': 'Popular', 'icon': '⭐', 'color': 'yellow'},
            'south_indian': {'name': 'South Indian', 'icon': '🏠', 'color': 'purple'},
            'north_indian': {'name': 'North Indian', 'icon': '🏠', 'color': 'purple'},
            'traditional': {'name': 'Traditional', 'icon': '🏛️', 'color': 'brown'}
        }
        
        tags_with_info = []
        for tag in all_tags:
            if tag in tag_info:
                info = tag_info[tag].copy()
                info['slug'] = tag
                tags_with_info.append(info)
        
        return jsonify({'tags': tags_with_info}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get tags error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@menu_bp.route('/time-slots', methods=['GET'])
def get_time_slots():
    """Get available time slots"""
    try:
        time_slots = {
            'breakfast': {
                'name': 'Breakfast',
                'start_time': '08:00',
                'end_time': '11:00',
                'order_cutoff': '10:30',
                'description': 'Start your day right with our wholesome breakfast options'
            },
            'lunch': {
                'name': 'Lunch',
                'start_time': '12:00',
                'end_time': '15:00',
                'order_cutoff': '14:30',
                'description': 'Satisfying lunch meals for your midday hunger'
            },
            'dinner': {
                'name': 'Dinner',
                'start_time': '19:00',
                'end_time': '22:00',
                'order_cutoff': '21:30',
                'description': 'End your day with our delicious dinner options'
            }
        }
        
        return jsonify({'time_slots': time_slots}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get time slots error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@menu_bp.route('/reload', methods=['POST'])
def reload_menu():
    """Reload menu from YAML file (admin operation)"""
    try:
        # This endpoint can be used by admin to reload menu from YAML
        # In production, this should be protected with admin authentication
        
        success = MenuManager.load_menu_from_yaml()
        
        if success:
            return jsonify({'message': 'Menu reloaded successfully'}), 200
        else:
            return jsonify({'error': 'Failed to reload menu'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Reload menu error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500