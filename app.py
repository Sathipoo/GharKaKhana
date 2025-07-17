from flask import Flask, jsonify, send_from_directory, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_mail import Mail
from flask_socketio import SocketIO, join_room
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'ghar-ka-khana-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///gharkaakhana.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-string')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Email configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'orders@gharkaakhana.com')

# Payment configuration
app.config['RAZORPAY_KEY_ID'] = os.getenv('RAZORPAY_KEY_ID')
app.config['RAZORPAY_KEY_SECRET'] = os.getenv('RAZORPAY_KEY_SECRET')

# Twilio configuration
app.config['TWILIO_ACCOUNT_SID'] = os.getenv('TWILIO_ACCOUNT_SID')
app.config['TWILIO_AUTH_TOKEN'] = os.getenv('TWILIO_AUTH_TOKEN')
app.config['TWILIO_PHONE_NUMBER'] = os.getenv('TWILIO_PHONE_NUMBER')

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
cors = CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])
mail = Mail(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv('REDIS_URL', 'memory://')
)

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Import models (after db initialization)
from models.user import User
from models.order import Order
from models.menu import MenuItem
from models.admin import Admin

# Import routes
from routes.auth import auth_bp
from routes.menu import menu_bp
from routes.orders import orders_bp
from routes.admin import admin_bp
from routes.payment import payment_bp
from routes.location import location_bp

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(menu_bp, url_prefix='/api/menu')
app.register_blueprint(orders_bp, url_prefix='/api/orders')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(payment_bp, url_prefix='/api/payment')
app.register_blueprint(location_bp, url_prefix='/api/location')

# Health check endpoint
@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'OK',
        'service': 'Ghar ka Khana API',
        'version': '1.0.0',
        'timestamp': db.func.now()
    })

# Serve static files
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# Socket.io events
@socketio.on('connect')
def handle_connect():
    print(f'📱 Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    print(f'📱 Client disconnected: {request.sid}')

@socketio.on('join_admin')
def handle_join_admin():
    join_room('admin')
    print('👤 Admin joined room')

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded', 'message': str(e.description)}), 429

# JWT error handlers
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({'error': 'Token has expired'}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({'error': 'Invalid token'}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({'error': 'Authorization token required'}), 401

# Initialize database tables
@app.before_first_request
def create_tables():
    db.create_all()
    
    # Create default admin user if not exists
    admin = Admin.query.filter_by(email='admin@gharkaakhana.com').first()
    if not admin:
        admin = Admin(
            name='Admin User',
            email='admin@gharkaakhana.com',
            phone='+919876543210',
            role='super_admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('✅ Default admin user created')

if __name__ == '__main__':
    # Development server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
else:
    # Production server (gunicorn)
    pass