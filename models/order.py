from app import db
from datetime import datetime, timedelta
import json
import random
import string

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Customer info (snapshot at time of order)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(15), nullable=False)
    customer_email = db.Column(db.String(120))
    
    # Order items (JSON)
    items = db.Column(db.Text, nullable=False)  # JSON string
    
    # Pricing
    subtotal = db.Column(db.Float, nullable=False)
    delivery_charges = db.Column(db.Float, default=0.0)
    taxes = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    wallet_used = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, nullable=False)
    
    # Delivery address (snapshot)
    delivery_name = db.Column(db.String(100), nullable=False)
    delivery_phone = db.Column(db.String(15), nullable=False)
    delivery_address_line1 = db.Column(db.String(200), nullable=False)
    delivery_address_line2 = db.Column(db.String(200))
    delivery_landmark = db.Column(db.String(100))
    delivery_city = db.Column(db.String(50), nullable=False)
    delivery_pincode = db.Column(db.String(10), nullable=False)
    delivery_latitude = db.Column(db.Float)
    delivery_longitude = db.Column(db.Float)
    delivery_zone = db.Column(db.String(50), nullable=False)
    
    # Time and scheduling
    time_slot = db.Column(db.String(20), nullable=False)  # 'breakfast', 'lunch', 'dinner'
    scheduled_for = db.Column(db.DateTime, nullable=False)
    
    # Status
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    status_history = db.Column(db.Text)  # JSON string
    
    # Payment
    payment_method = db.Column(db.String(20), nullable=False)  # 'online', 'cod', 'wallet'
    payment_status = db.Column(db.String(20), default='pending')
    payment_transaction_id = db.Column(db.String(100))
    razorpay_order_id = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))
    paid_at = db.Column(db.DateTime)
    
    # Delivery
    estimated_delivery_time = db.Column(db.Integer)  # in minutes
    actual_delivery_time = db.Column(db.DateTime)
    delivery_partner_name = db.Column(db.String(100))
    delivery_partner_phone = db.Column(db.String(15))
    delivery_partner_vehicle = db.Column(db.String(50))
    tracking_updates = db.Column(db.Text)  # JSON string
    
    # Additional fields
    special_instructions = db.Column(db.Text)
    cancellation_reason = db.Column(db.String(200))
    refund_amount = db.Column(db.Float)
    refund_reason = db.Column(db.String(200))
    refund_processed_at = db.Column(db.DateTime)
    refund_transaction_id = db.Column(db.String(100))
    
    # Feedback
    rating = db.Column(db.Integer)  # 1-5
    feedback_comment = db.Column(db.Text)
    feedback_submitted_at = db.Column(db.DateTime)
    
    # Source and metadata
    source = db.Column(db.String(20), default='website')  # 'website', 'zomato', 'swiggy', 'admin'
    loyalty_points_earned = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Order {self.order_number}>'
    
    def __init__(self, **kwargs):
        super(Order, self).__init__(**kwargs)
        if not self.order_number:
            self.order_number = self.generate_order_number()
        
        # Initialize status history
        if not self.status_history:
            self.set_status_history([{
                'status': self.status,
                'timestamp': datetime.utcnow().isoformat(),
                'note': 'Order placed',
                'updated_by': 'system'
            }])
    
    def generate_order_number(self):
        """Generate unique order number"""
        today = datetime.utcnow()
        date_str = today.strftime('%Y%m%d')
        
        # Count orders for today
        count = db.session.query(Order).filter(
            db.func.date(Order.created_at) == today.date()
        ).count()
        
        return f"GKK{date_str}{str(count + 1).zfill(3)}"
    
    def set_items(self, items_list):
        """Set order items as JSON"""
        self.items = json.dumps(items_list)
    
    def get_items(self):
        """Get order items from JSON"""
        if self.items:
            return json.loads(self.items)
        return []
    
    def set_status_history(self, history_list):
        """Set status history as JSON"""
        self.status_history = json.dumps(history_list)
    
    def get_status_history(self):
        """Get status history from JSON"""
        if self.status_history:
            return json.loads(self.status_history)
        return []
    
    def set_tracking_updates(self, updates_list):
        """Set tracking updates as JSON"""
        self.tracking_updates = json.dumps(updates_list)
    
    def get_tracking_updates(self):
        """Get tracking updates from JSON"""
        if self.tracking_updates:
            return json.loads(self.tracking_updates)
        return []
    
    def update_status(self, new_status, note="", updated_by="system"):
        """Update order status and add to history"""
        self.status = new_status
        
        # Get current history and add new entry
        history = self.get_status_history()
        history.append({
            'status': new_status,
            'timestamp': datetime.utcnow().isoformat(),
            'note': note,
            'updated_by': updated_by
        })
        self.set_status_history(history)
        
        # Update timestamp
        self.updated_at = datetime.utcnow()
        
        db.session.commit()
    
    def add_tracking_update(self, message, location=None):
        """Add tracking update"""
        updates = self.get_tracking_updates()
        update = {
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        if location:
            update['location'] = location
        
        updates.append(update)
        self.set_tracking_updates(updates)
        db.session.commit()
    
    def calculate_estimated_delivery_time(self):
        """Calculate estimated delivery time based on items and location"""
        items = self.get_items()
        max_prep_time = max([item.get('prep_time', 20) for item in items]) if items else 20
        
        # Add delivery time based on zone
        delivery_time = 10 if self.delivery_zone == 'brigade_gateway' else 20
        
        self.estimated_delivery_time = max_prep_time + delivery_time
        return self.estimated_delivery_time
    
    def can_be_cancelled(self):
        """Check if order can be cancelled"""
        return self.status in ['pending', 'confirmed']
    
    def can_be_modified(self):
        """Check if order can be modified"""
        return self.status == 'pending'
    
    def calculate_loyalty_points(self):
        """Calculate loyalty points (1 point per ₹10 spent)"""
        points = int(self.total // 10)
        self.loyalty_points_earned = points
        return points
    
    @property
    def item_count(self):
        """Get total item count"""
        items = self.get_items()
        return sum(item.get('quantity', 0) for item in items)
    
    @property
    def delivery_address_full(self):
        """Get full delivery address"""
        parts = [self.delivery_address_line1]
        if self.delivery_address_line2:
            parts.append(self.delivery_address_line2)
        if self.delivery_landmark:
            parts.append(f"Near {self.delivery_landmark}")
        parts.extend([self.delivery_city, self.delivery_pincode])
        return ", ".join(parts)
    
    def to_dict(self, include_items=True):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'order_number': self.order_number,
            'customer': {
                'id': self.customer_id,
                'name': self.customer_name,
                'phone': self.customer_phone,
                'email': self.customer_email
            },
            'pricing': {
                'subtotal': self.subtotal,
                'delivery_charges': self.delivery_charges,
                'taxes': self.taxes,
                'discount': self.discount,
                'wallet_used': self.wallet_used,
                'total': self.total
            },
            'delivery_address': {
                'name': self.delivery_name,
                'phone': self.delivery_phone,
                'address_line1': self.delivery_address_line1,
                'address_line2': self.delivery_address_line2,
                'landmark': self.delivery_landmark,
                'city': self.delivery_city,
                'pincode': self.delivery_pincode,
                'coordinates': {
                    'lat': self.delivery_latitude,
                    'lng': self.delivery_longitude
                } if self.delivery_latitude and self.delivery_longitude else None,
                'zone': self.delivery_zone,
                'full_address': self.delivery_address_full
            },
            'time_slot': self.time_slot,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'status': self.status,
            'status_history': self.get_status_history(),
            'payment': {
                'method': self.payment_method,
                'status': self.payment_status,
                'transaction_id': self.payment_transaction_id,
                'razorpay_order_id': self.razorpay_order_id,
                'razorpay_payment_id': self.razorpay_payment_id,
                'paid_at': self.paid_at.isoformat() if self.paid_at else None
            },
            'delivery': {
                'estimated_time': self.estimated_delivery_time,
                'actual_delivery_time': self.actual_delivery_time.isoformat() if self.actual_delivery_time else None,
                'partner': {
                    'name': self.delivery_partner_name,
                    'phone': self.delivery_partner_phone,
                    'vehicle': self.delivery_partner_vehicle
                } if self.delivery_partner_name else None,
                'tracking_updates': self.get_tracking_updates()
            },
            'special_instructions': self.special_instructions,
            'cancellation_reason': self.cancellation_reason,
            'refund': {
                'amount': self.refund_amount,
                'reason': self.refund_reason,
                'processed_at': self.refund_processed_at.isoformat() if self.refund_processed_at else None,
                'transaction_id': self.refund_transaction_id
            } if self.refund_amount else None,
            'feedback': {
                'rating': self.rating,
                'comment': self.feedback_comment,
                'submitted_at': self.feedback_submitted_at.isoformat() if self.feedback_submitted_at else None
            } if self.rating else None,
            'source': self.source,
            'loyalty_points_earned': self.loyalty_points_earned,
            'item_count': self.item_count,
            'can_be_cancelled': self.can_be_cancelled(),
            'can_be_modified': self.can_be_modified(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_items:
            data['items'] = self.get_items()
        
        return data
    
    def to_summary_dict(self):
        """Convert to summary dictionary for lists"""
        return {
            'id': self.id,
            'order_number': self.order_number,
            'customer_name': self.customer_name,
            'total': self.total,
            'status': self.status,
            'time_slot': self.time_slot,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'item_count': self.item_count,
            'delivery_zone': self.delivery_zone,
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }