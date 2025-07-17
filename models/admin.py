from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Admin(db.Model):
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(15), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='admin')  # 'super_admin', 'admin', 'kitchen_staff', 'delivery_manager'
    
    # Permissions
    can_manage_menu = db.Column(db.Boolean, default=True)
    can_manage_orders = db.Column(db.Boolean, default=True)
    can_view_analytics = db.Column(db.Boolean, default=True)
    can_manage_users = db.Column(db.Boolean, default=False)
    can_manage_admins = db.Column(db.Boolean, default=False)
    can_manage_settings = db.Column(db.Boolean, default=False)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('admins.id'))
    
    def __repr__(self):
        return f'<Admin {self.email}>'
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password"""
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self, ip_address=None):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        if ip_address:
            self.last_login_ip = ip_address
        db.session.commit()
    
    def has_permission(self, permission):
        """Check if admin has specific permission"""
        if self.role == 'super_admin':
            return True
        
        permission_map = {
            'manage_menu': self.can_manage_menu,
            'manage_orders': self.can_manage_orders,
            'view_analytics': self.can_view_analytics,
            'manage_users': self.can_manage_users,
            'manage_admins': self.can_manage_admins,
            'manage_settings': self.can_manage_settings
        }
        
        return permission_map.get(permission, False)
    
    def set_role_permissions(self, role):
        """Set permissions based on role"""
        self.role = role
        
        if role == 'super_admin':
            self.can_manage_menu = True
            self.can_manage_orders = True
            self.can_view_analytics = True
            self.can_manage_users = True
            self.can_manage_admins = True
            self.can_manage_settings = True
        elif role == 'admin':
            self.can_manage_menu = True
            self.can_manage_orders = True
            self.can_view_analytics = True
            self.can_manage_users = True
            self.can_manage_admins = False
            self.can_manage_settings = False
        elif role == 'kitchen_staff':
            self.can_manage_menu = True
            self.can_manage_orders = True
            self.can_view_analytics = False
            self.can_manage_users = False
            self.can_manage_admins = False
            self.can_manage_settings = False
        elif role == 'delivery_manager':
            self.can_manage_menu = False
            self.can_manage_orders = True
            self.can_view_analytics = True
            self.can_manage_users = False
            self.can_manage_admins = False
            self.can_manage_settings = False
    
    def to_dict(self, include_permissions=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_permissions:
            data['permissions'] = {
                'can_manage_menu': self.can_manage_menu,
                'can_manage_orders': self.can_manage_orders,
                'can_view_analytics': self.can_view_analytics,
                'can_manage_users': self.can_manage_users,
                'can_manage_admins': self.can_manage_admins,
                'can_manage_settings': self.can_manage_settings
            }
        
        return data


class AdminSession(db.Model):
    __tablename__ = 'admin_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)
    session_token = db.Column(db.String(200), unique=True, nullable=False, index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    admin = db.relationship('Admin', backref='sessions')
    
    def __repr__(self):
        return f'<AdminSession {self.admin_id}>'
    
    def is_valid(self):
        """Check if session is valid"""
        return (
            self.is_active and 
            self.expires_at > datetime.utcnow()
        )
    
    def extend_session(self, hours=24):
        """Extend session expiry"""
        from datetime import timedelta
        self.expires_at = datetime.utcnow() + timedelta(hours=hours)
        self.last_used_at = datetime.utcnow()
        db.session.commit()
    
    def invalidate(self):
        """Invalidate session"""
        self.is_active = False
        db.session.commit()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'admin_id': self.admin_id,
            'ip_address': self.ip_address,
            'is_active': self.is_active,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None
        }