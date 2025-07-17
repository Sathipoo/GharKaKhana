from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app import db, limiter
from models.user import User, UserAddress
from utils.sms_service import SMSService
from utils.validators import validate_phone_number, validate_email
import phonenumbers
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/send-otp', methods=['POST'])
@limiter.limit("5 per minute")
def send_otp():
    """Send OTP to user's phone number"""
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        
        if not phone:
            return jsonify({'error': 'Phone number is required'}), 400
        
        # Validate and format phone number
        try:
            parsed = phonenumbers.parse(phone, "IN")
            if not phonenumbers.is_valid_number(parsed):
                return jsonify({'error': 'Invalid phone number'}), 400
            phone = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            return jsonify({'error': 'Invalid phone number format'}), 400
        
        # Find or create user
        user = User.query.filter_by(phone=phone).first()
        if not user:
            user = User(phone=phone)
            db.session.add(user)
        
        # Generate and send OTP
        otp = user.generate_otp()
        db.session.commit()
        
        # Send OTP via SMS
        sms_service = SMSService()
        success = sms_service.send_otp(phone, otp)
        
        if not success:
            return jsonify({'error': 'Failed to send OTP. Please try again.'}), 500
        
        return jsonify({
            'message': 'OTP sent successfully',
            'phone': phone,
            'expires_in_minutes': 10
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Send OTP error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.route('/verify-otp', methods=['POST'])
@limiter.limit("10 per minute")
def verify_otp():
    """Verify OTP and login user"""
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        otp = data.get('otp', '').strip()
        
        if not phone or not otp:
            return jsonify({'error': 'Phone number and OTP are required'}), 400
        
        # Format phone number
        try:
            parsed = phonenumbers.parse(phone, "IN")
            phone = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            return jsonify({'error': 'Invalid phone number format'}), 400
        
        # Find user
        user = User.query.filter_by(phone=phone).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Verify OTP
        if not user.verify_otp(otp):
            if user.otp_attempts >= 3:
                return jsonify({'error': 'Too many failed attempts. Please request a new OTP.'}), 429
            return jsonify({'error': 'Invalid or expired OTP'}), 400
        
        db.session.commit()
        
        # Create JWT token
        access_token = create_access_token(identity=str(user.id))
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Verify OTP error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get user profile"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Include addresses in profile
        profile = user.to_dict()
        profile['addresses'] = [addr.to_dict() for addr in user.addresses.all()]
        
        return jsonify({'user': profile}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get profile error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Update basic info
        if 'name' in data:
            user.name = data['name'].strip()
        
        if 'email' in data:
            email = data['email'].strip()
            if email and not validate_email(email):
                return jsonify({'error': 'Invalid email format'}), 400
            user.email = email
        
        # Update preferences
        if 'dietary_restrictions' in data:
            user.set_dietary_restrictions(data['dietary_restrictions'])
        
        if 'spice_level' in data:
            if data['spice_level'] in ['mild', 'medium', 'spicy']:
                user.spice_level = data['spice_level']
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update profile error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.route('/addresses', methods=['GET'])
@jwt_required()
def get_addresses():
    """Get user addresses"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        addresses = [addr.to_dict() for addr in user.addresses.all()]
        
        return jsonify({'addresses': addresses}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get addresses error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.route('/addresses', methods=['POST'])
@jwt_required()
def add_address():
    """Add new address"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'phone', 'address_line1', 'city', 'pincode']
        for field in required_fields:
            if not data.get(field, '').strip():
                return jsonify({'error': f'{field.replace("_", " ").title()} is required'}), 400
        
        # Validate phone number
        if not validate_phone_number(data['phone']):
            return jsonify({'error': 'Invalid phone number'}), 400
        
        # Create address
        address = UserAddress(
            user_id=user.id,
            name=data['name'].strip(),
            phone=data['phone'].strip(),
            address_line1=data['address_line1'].strip(),
            address_line2=data.get('address_line2', '').strip(),
            landmark=data.get('landmark', '').strip(),
            city=data['city'].strip(),
            pincode=data['pincode'].strip(),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            delivery_zone=data.get('delivery_zone', 'other_areas'),
            is_default=data.get('is_default', False)
        )
        
        # If this is set as default, unset other defaults
        if address.is_default:
            user.addresses.update({'is_default': False})
        
        db.session.add(address)
        db.session.commit()
        
        return jsonify({
            'message': 'Address added successfully',
            'address': address.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Add address error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.route('/addresses/<int:address_id>', methods=['PUT'])
@jwt_required()
def update_address(address_id):
    """Update address"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        address = UserAddress.query.filter_by(id=address_id, user_id=user.id).first()
        if not address:
            return jsonify({'error': 'Address not found'}), 404
        
        data = request.get_json()
        
        # Update fields
        if 'name' in data:
            address.name = data['name'].strip()
        if 'phone' in data:
            if not validate_phone_number(data['phone']):
                return jsonify({'error': 'Invalid phone number'}), 400
            address.phone = data['phone'].strip()
        if 'address_line1' in data:
            address.address_line1 = data['address_line1'].strip()
        if 'address_line2' in data:
            address.address_line2 = data['address_line2'].strip()
        if 'landmark' in data:
            address.landmark = data['landmark'].strip()
        if 'city' in data:
            address.city = data['city'].strip()
        if 'pincode' in data:
            address.pincode = data['pincode'].strip()
        if 'latitude' in data:
            address.latitude = data['latitude']
        if 'longitude' in data:
            address.longitude = data['longitude']
        if 'delivery_zone' in data:
            address.delivery_zone = data['delivery_zone']
        
        # Handle default address
        if data.get('is_default'):
            # Unset other defaults
            user.addresses.filter(UserAddress.id != address_id).update({'is_default': False})
            address.is_default = True
        
        address.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Address updated successfully',
            'address': address.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update address error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.route('/addresses/<int:address_id>', methods=['DELETE'])
@jwt_required()
def delete_address(address_id):
    """Delete address"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        address = UserAddress.query.filter_by(id=address_id, user_id=user.id).first()
        if not address:
            return jsonify({'error': 'Address not found'}), 404
        
        db.session.delete(address)
        db.session.commit()
        
        return jsonify({'message': 'Address deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete address error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.route('/wallet', methods=['GET'])
@jwt_required()
def get_wallet():
    """Get wallet balance and transactions"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get recent transactions
        transactions = [txn.to_dict() for txn in user.wallet_transactions.order_by(
            user.wallet_transactions.desc()
        ).limit(20).all()]
        
        return jsonify({
            'balance': user.wallet_balance,
            'loyalty_points': {
                'current': user.loyalty_points_current,
                'total': user.loyalty_points_total
            },
            'transactions': transactions
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get wallet error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (client-side token removal)"""
    return jsonify({'message': 'Logged out successfully'}), 200