from app import db
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import json
import phonenumbers
from phonenumbers import NumberParseException

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), index=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # OTP fields
    last_otp_code = db.Column(db.String(6))
    last_otp_expires_at = db.Column(db.DateTime)
    otp_attempts = db.Column(db.Integer, default=0)
    
    # Preferences
    dietary_restrictions = db.Column(db.Text)  # JSON string
    favorite_items = db.Column(db.Text)  # JSON string
    spice_level = db.Column(db.String(20), default='medium')
    
    # Wallet and loyalty
    wallet_balance = db.Column(db.Float, default=0.0)
    loyalty_points_current = db.Column(db.Integer, default=0)
    loyalty_points_total = db.Column(db.Integer, default=0)
    
    # Tracking
    last_login = db.Column(db.DateTime)
    device_tokens = db.Column(db.Text)  # JSON string for push notifications
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    addresses = db.relationship('UserAddress', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    wallet_transactions = db.relationship('WalletTransaction', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.phone}>'
    
    @property
    def display_name(self):
        return self.name or f"User {self.phone[-4:]}"
    
    def set_dietary_restrictions(self, restrictions):
        """Set dietary restrictions as JSON"""
        self.dietary_restrictions = json.dumps(restrictions)
    
    def get_dietary_restrictions(self):
        """Get dietary restrictions from JSON"""
        if self.dietary_restrictions:
            return json.loads(self.dietary_restrictions)
        return []
    
    def set_favorite_items(self, items):
        """Set favorite items as JSON"""
        self.favorite_items = json.dumps(items)
    
    def get_favorite_items(self):
        """Get favorite items from JSON"""
        if self.favorite_items:
            return json.loads(self.favorite_items)
        return []
    
    def set_device_tokens(self, tokens):
        """Set device tokens as JSON"""
        self.device_tokens = json.dumps(tokens)
    
    def get_device_tokens(self):
        """Get device tokens from JSON"""
        if self.device_tokens:
            return json.loads(self.device_tokens)
        return []
    
    def add_device_token(self, token):
        """Add a new device token"""
        tokens = self.get_device_tokens()
        if token not in tokens:
            tokens.append(token)
            self.set_device_tokens(tokens)
    
    def validate_phone(self):
        """Validate Indian phone number"""
        try:
            parsed = phonenumbers.parse(self.phone, "IN")
            return phonenumbers.is_valid_number(parsed)
        except NumberParseException:
            return False
    
    def generate_otp(self):
        """Generate 4-digit OTP"""
        import random
        otp = str(random.randint(1000, 9999))
        self.last_otp_code = otp
        self.last_otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        self.otp_attempts = 0
        return otp
    
    def verify_otp(self, otp):
        """Verify OTP"""
        if not self.last_otp_code or not self.last_otp_expires_at:
            return False
        
        if datetime.utcnow() > self.last_otp_expires_at:
            return False
        
        if self.otp_attempts >= 3:
            return False
        
        if self.last_otp_code == otp:
            self.is_verified = True
            self.last_otp_code = None
            self.last_otp_expires_at = None
            self.otp_attempts = 0
            self.last_login = datetime.utcnow()
            return True
        else:
            self.otp_attempts += 1
            return False
    
    def add_loyalty_points(self, points, description=""):
        """Add loyalty points and convert to wallet credit"""
        self.loyalty_points_current += points
        self.loyalty_points_total += points
        
        # Convert every 100 points to ₹10 wallet credit
        if self.loyalty_points_current >= 100:
            credit_amount = (self.loyalty_points_current // 100) * 10
            self.loyalty_points_current = self.loyalty_points_current % 100
            self.wallet_balance += credit_amount
            
            # Record wallet transaction
            transaction = WalletTransaction(
                user_id=self.id,
                transaction_type='credit',
                amount=credit_amount,
                description=f"Loyalty points conversion: {description}"
            )
            db.session.add(transaction)
        
        db.session.commit()
    
    def deduct_wallet_balance(self, amount, description="", order_id=None):
        """Deduct amount from wallet"""
        if self.wallet_balance >= amount:
            self.wallet_balance -= amount
            transaction = WalletTransaction(
                user_id=self.id,
                transaction_type='debit',
                amount=amount,
                description=description,
                order_id=order_id
            )
            db.session.add(transaction)
            db.session.commit()
            return True
        return False
    
    def get_default_address(self):
        """Get default delivery address"""
        return self.addresses.filter_by(is_default=True).first()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'phone': self.phone,
            'name': self.name,
            'email': self.email,
            'is_verified': self.is_verified,
            'dietary_restrictions': self.get_dietary_restrictions(),
            'favorite_items': self.get_favorite_items(),
            'spice_level': self.spice_level,
            'wallet_balance': self.wallet_balance,
            'loyalty_points': {
                'current': self.loyalty_points_current,
                'total': self.loyalty_points_total
            },
            'display_name': self.display_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class UserAddress(db.Model):
    __tablename__ = 'user_addresses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    address_line1 = db.Column(db.String(200), nullable=False)
    address_line2 = db.Column(db.String(200))
    landmark = db.Column(db.String(100))
    city = db.Column(db.String(50), nullable=False, default='Bangalore')
    pincode = db.Column(db.String(10), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    delivery_zone = db.Column(db.String(50), nullable=False)  # 'brigade_gateway' or 'other_areas'
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserAddress {self.name} - {self.city}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'address_line1': self.address_line1,
            'address_line2': self.address_line2,
            'landmark': self.landmark,
            'city': self.city,
            'pincode': self.pincode,
            'coordinates': {
                'lat': self.latitude,
                'lng': self.longitude
            } if self.latitude and self.longitude else None,
            'delivery_zone': self.delivery_zone,
            'is_default': self.is_default
        }


class WalletTransaction(db.Model):
    __tablename__ = 'wallet_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'credit' or 'debit'
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<WalletTransaction {self.transaction_type} ₹{self.amount}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.transaction_type,
            'amount': self.amount,
            'description': self.description,
            'order_id': self.order_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }