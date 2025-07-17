from app import db
from datetime import datetime
import yaml
import os

class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(20), unique=True, nullable=False, index=True)  # e.g., 'bf001'
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'breakfast', 'lunch_dinner', 'snacks', 'salads', 'beverages'
    tags = db.Column(db.Text)  # JSON string of tags
    prep_time = db.Column(db.Integer, default=20)  # in minutes
    is_available = db.Column(db.Boolean, default=True)
    image_url = db.Column(db.String(200))
    
    # Nutritional info (optional)
    calories = db.Column(db.Integer)
    protein = db.Column(db.Float)
    carbs = db.Column(db.Float)
    fat = db.Column(db.Float)
    
    # Popularity and recommendations
    order_count = db.Column(db.Integer, default=0)
    rating_average = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    is_popular = db.Column(db.Boolean, default=False)
    is_recommended = db.Column(db.Boolean, default=False)
    
    # Availability control
    available_time_slots = db.Column(db.Text)  # JSON string: ['breakfast', 'lunch', 'dinner']
    available_days = db.Column(db.Text)  # JSON string: [0,1,2,3,4,5,6] (Monday=0)
    
    # Admin fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(50))
    
    def __repr__(self):
        return f'<MenuItem {self.name}>'
    
    def set_tags(self, tags_list):
        """Set tags as JSON"""
        import json
        self.tags = json.dumps(tags_list)
    
    def get_tags(self):
        """Get tags from JSON"""
        import json
        if self.tags:
            return json.loads(self.tags)
        return []
    
    def set_available_time_slots(self, slots_list):
        """Set available time slots as JSON"""
        import json
        self.available_time_slots = json.dumps(slots_list)
    
    def get_available_time_slots(self):
        """Get available time slots from JSON"""
        import json
        if self.available_time_slots:
            return json.loads(self.available_time_slots)
        return ['breakfast', 'lunch', 'dinner']  # Default to all slots
    
    def set_available_days(self, days_list):
        """Set available days as JSON"""
        import json
        self.available_days = json.dumps(days_list)
    
    def get_available_days(self):
        """Get available days from JSON"""
        import json
        if self.available_days:
            return json.loads(self.available_days)
        return [0, 1, 2, 3, 4, 5, 6]  # Default to all days
    
    def is_available_now(self, time_slot=None, day_of_week=None):
        """Check if item is available for given time slot and day"""
        if not self.is_available:
            return False
        
        if time_slot:
            available_slots = self.get_available_time_slots()
            if time_slot not in available_slots:
                return False
        
        if day_of_week is not None:
            available_days = self.get_available_days()
            if day_of_week not in available_days:
                return False
        
        return True
    
    def update_rating(self, new_rating):
        """Update average rating"""
        total_rating = self.rating_average * self.rating_count + new_rating
        self.rating_count += 1
        self.rating_average = total_rating / self.rating_count
        
        # Update popularity based on rating and order count
        self.update_popularity()
    
    def increment_order_count(self):
        """Increment order count"""
        self.order_count += 1
        self.update_popularity()
    
    def update_popularity(self):
        """Update popularity status based on orders and ratings"""
        # Item is popular if it has high orders or high rating
        self.is_popular = (
            self.order_count >= 50 or 
            (self.rating_average >= 4.0 and self.rating_count >= 10)
        )
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'item_id': self.item_id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'category': self.category,
            'tags': self.get_tags(),
            'prep_time': self.prep_time,
            'is_available': self.is_available,
            'image_url': self.image_url,
            'nutrition': {
                'calories': self.calories,
                'protein': self.protein,
                'carbs': self.carbs,
                'fat': self.fat
            } if self.calories else None,
            'stats': {
                'order_count': self.order_count,
                'rating_average': round(self.rating_average, 1) if self.rating_average else 0,
                'rating_count': self.rating_count,
                'is_popular': self.is_popular,
                'is_recommended': self.is_recommended
            },
            'availability': {
                'time_slots': self.get_available_time_slots(),
                'days': self.get_available_days()
            },
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class MenuManager:
    """Manager class for menu operations"""
    
    @staticmethod
    def load_menu_from_yaml():
        """Load menu from YAML file and update database"""
        yaml_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'menu.yaml')
        
        if not os.path.exists(yaml_path):
            print(f"❌ Menu YAML file not found at {yaml_path}")
            return False
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as file:
                menu_data = yaml.safe_load(file)
            
            # Process each category
            for category, items in menu_data.get('menu', {}).items():
                for item_data in items:
                    MenuManager.create_or_update_item(category, item_data)
            
            db.session.commit()
            print("✅ Menu loaded successfully from YAML")
            return True
            
        except Exception as e:
            print(f"❌ Error loading menu from YAML: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def create_or_update_item(category, item_data):
        """Create or update a menu item"""
        item = MenuItem.query.filter_by(item_id=item_data['id']).first()
        
        if not item:
            item = MenuItem(item_id=item_data['id'])
            db.session.add(item)
        
        # Update item fields
        item.name = item_data['name']
        item.description = item_data.get('description', '')
        item.price = item_data['price']
        item.category = category
        item.set_tags(item_data.get('tags', []))
        item.prep_time = item_data.get('prep_time', 20)
        item.is_available = item_data.get('available', True)
        item.image_url = item_data.get('image', '')
        
        # Set availability based on category
        if category == 'breakfast':
            item.set_available_time_slots(['breakfast'])
        elif category == 'lunch_dinner':
            item.set_available_time_slots(['lunch', 'dinner'])
        else:
            item.set_available_time_slots(['breakfast', 'lunch', 'dinner'])
        
        item.updated_at = datetime.utcnow()
    
    @staticmethod
    def get_menu_by_time_slot(time_slot):
        """Get available menu items for a specific time slot"""
        items = MenuItem.query.filter_by(is_available=True).all()
        
        available_items = []
        for item in items:
            if item.is_available_now(time_slot=time_slot):
                available_items.append(item)
        
        # Group by category
        menu = {}
        for item in available_items:
            if item.category not in menu:
                menu[item.category] = []
            menu[item.category].append(item.to_dict())
        
        return menu
    
    @staticmethod
    def get_popular_items(limit=10):
        """Get popular menu items"""
        return MenuItem.query.filter_by(
            is_available=True, 
            is_popular=True
        ).order_by(
            MenuItem.order_count.desc()
        ).limit(limit).all()
    
    @staticmethod
    def search_items(query, category=None, tags=None):
        """Search menu items by name, description, category, or tags"""
        items_query = MenuItem.query.filter_by(is_available=True)
        
        if query:
            items_query = items_query.filter(
                db.or_(
                    MenuItem.name.contains(query),
                    MenuItem.description.contains(query)
                )
            )
        
        if category:
            items_query = items_query.filter_by(category=category)
        
        items = items_query.all()
        
        # Filter by tags if specified
        if tags:
            filtered_items = []
            for item in items:
                item_tags = item.get_tags()
                if any(tag in item_tags for tag in tags):
                    filtered_items.append(item)
            items = filtered_items
        
        return items
    
    @staticmethod
    def get_recommendations_for_user(user):
        """Get personalized recommendations for a user"""
        recommendations = []
        
        # Get user's dietary restrictions
        dietary_restrictions = user.get_dietary_restrictions() if user else []
        favorite_items = user.get_favorite_items() if user else []
        
        # Get popular items that match user preferences
        popular_items = MenuManager.get_popular_items()
        
        for item in popular_items:
            item_tags = item.get_tags()
            
            # Check if item matches dietary restrictions
            matches_diet = True
            if dietary_restrictions:
                # If user is vegetarian, exclude non-vegetarian items
                if 'vegetarian' in dietary_restrictions and 'non_vegetarian' in item_tags:
                    matches_diet = False
                # Add more dietary restriction logic as needed
            
            if matches_diet:
                recommendations.append(item)
        
        return recommendations[:6]  # Return top 6 recommendations