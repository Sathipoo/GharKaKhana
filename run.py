#!/usr/bin/env python
"""
Ghar ka Khana - Flask Application Runner
"""

import os
import sys
from app import app, db, socketio
from models.menu import MenuManager
from models.admin import Admin

def create_default_admin():
    """Create default admin user if not exists"""
    admin = Admin.query.filter_by(email='admin@gharkaakhana.com').first()
    if not admin:
        admin = Admin(
            name='Admin User',
            email='admin@gharkaakhana.com',
            phone='+919876543210',
            role='super_admin'
        )
        admin.set_password('admin123')
        admin.set_role_permissions('super_admin')
        db.session.add(admin)
        db.session.commit()
        print('✅ Default admin user created:')
        print('   Email: admin@gharkaakhana.com')
        print('   Password: admin123')
        return True
    return False

def initialize_app():
    """Initialize the application"""
    print("🍽️  Initializing Ghar ka Khana...")
    
    # Create database tables
    with app.app_context():
        db.create_all()
        print("✅ Database tables created")
        
        # Create default admin
        admin_created = create_default_admin()
        if not admin_created:
            print("ℹ️  Default admin user already exists")
        
        # Load menu from YAML
        print("📋 Loading menu from YAML...")
        success = MenuManager.load_menu_from_yaml()
        if success:
            print("✅ Menu loaded successfully")
        else:
            print("⚠️  Failed to load menu from YAML")
        
        print("🚀 Application initialized successfully!")

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'init':
            initialize_app()
            return
        elif command == 'shell':
            with app.app_context():
                import code
                code.interact(local=locals())
            return
        elif command == 'loadmenu':
            with app.app_context():
                success = MenuManager.load_menu_from_yaml()
                if success:
                    print("✅ Menu reloaded successfully")
                else:
                    print("❌ Failed to reload menu")
            return
    
    # Default: run the application
    print("🍽️  Starting Ghar ka Khana server...")
    print("📱 API will be available at: http://localhost:5000")
    print("🔧 Admin Panel: http://localhost:5000/admin")
    print("📚 Health Check: http://localhost:5000/api/health")
    print("\n📋 Default Admin Credentials:")
    print("   Email: admin@gharkaakhana.com")
    print("   Password: admin123")
    print("\n🛑 Press Ctrl+C to stop the server")
    
    # Run with SocketIO for real-time features
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV') == 'development'
    )

if __name__ == '__main__':
    main()