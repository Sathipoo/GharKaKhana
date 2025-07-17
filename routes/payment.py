from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import razorpay
from app import db
from models.user import User
from models.order import Order
import hashlib
import hmac

payment_bp = Blueprint('payment', __name__)

def get_razorpay_client():
    """Get Razorpay client instance"""
    key_id = current_app.config.get('RAZORPAY_KEY_ID')
    key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')
    
    if not key_id or not key_secret:
        return None
    
    return razorpay.Client(auth=(key_id, key_secret))

@payment_bp.route('/create-order', methods=['POST'])
@jwt_required()
def create_payment_order():
    """Create Razorpay payment order"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        amount = data.get('amount')  # Amount in rupees
        
        if not amount or amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        
        # Get Razorpay client
        client = get_razorpay_client()
        if not client:
            return jsonify({'error': 'Payment gateway not configured'}), 500
        
        # Convert to paise (Razorpay expects amount in paise)
        amount_paise = int(amount * 100)
        
        # Create Razorpay order
        razorpay_order = client.order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': f'order_rcptid_{user.id}_{int(amount)}',
            'notes': {
                'user_id': str(user.id),
                'user_phone': user.phone
            }
        })
        
        return jsonify({
            'razorpay_order_id': razorpay_order['id'],
            'amount': amount,
            'currency': 'INR',
            'key_id': current_app.config.get('RAZORPAY_KEY_ID')
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Create payment order error: {str(e)}")
        return jsonify({'error': 'Failed to create payment order'}), 500


@payment_bp.route('/verify', methods=['POST'])
@jwt_required()
def verify_payment():
    """Verify Razorpay payment"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        required_fields = ['razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'order_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Get the order
        order = Order.query.filter_by(id=data['order_id'], customer_id=user.id).first()
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Verify signature
        client = get_razorpay_client()
        if not client:
            return jsonify({'error': 'Payment gateway not configured'}), 500
        
        # Verify payment signature
        try:
            params_dict = {
                'razorpay_order_id': data['razorpay_order_id'],
                'razorpay_payment_id': data['razorpay_payment_id'],
                'razorpay_signature': data['razorpay_signature']
            }
            client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            current_app.logger.error(f"Payment verification failed: {str(e)}")
            return jsonify({'error': 'Payment verification failed'}), 400
        
        # Update order with payment details
        order.payment_status = 'completed'
        order.payment_transaction_id = data['razorpay_payment_id']
        order.razorpay_order_id = data['razorpay_order_id']
        order.razorpay_payment_id = data['razorpay_payment_id']
        order.paid_at = db.func.now()
        
        # Update order status to confirmed
        order.update_status('confirmed', 'Payment completed successfully')
        
        # Add loyalty points to user
        user.add_loyalty_points(order.loyalty_points_earned, f"Order {order.order_number}")
        
        db.session.commit()
        
        return jsonify({
            'message': 'Payment verified successfully',
            'order_status': 'confirmed',
            'loyalty_points_earned': order.loyalty_points_earned
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Verify payment error: {str(e)}")
        return jsonify({'error': 'Payment verification failed'}), 500


@payment_bp.route('/wallet/add-money', methods=['POST'])
@jwt_required()
def add_money_to_wallet():
    """Add money to user wallet"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        amount = data.get('amount')
        
        if not amount or amount < 50 or amount > 5000:
            return jsonify({'error': 'Amount must be between ₹50 and ₹5000'}), 400
        
        # Create Razorpay order for wallet top-up
        client = get_razorpay_client()
        if not client:
            return jsonify({'error': 'Payment gateway not configured'}), 500
        
        amount_paise = int(amount * 100)
        
        razorpay_order = client.order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': f'wallet_topup_{user.id}_{int(amount)}',
            'notes': {
                'user_id': str(user.id),
                'user_phone': user.phone,
                'type': 'wallet_topup'
            }
        })
        
        return jsonify({
            'razorpay_order_id': razorpay_order['id'],
            'amount': amount,
            'currency': 'INR',
            'key_id': current_app.config.get('RAZORPAY_KEY_ID')
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Add money to wallet error: {str(e)}")
        return jsonify({'error': 'Failed to initiate wallet top-up'}), 500


@payment_bp.route('/wallet/verify', methods=['POST'])
@jwt_required()
def verify_wallet_payment():
    """Verify wallet top-up payment"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        required_fields = ['razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'amount']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Verify signature
        client = get_razorpay_client()
        if not client:
            return jsonify({'error': 'Payment gateway not configured'}), 500
        
        try:
            params_dict = {
                'razorpay_order_id': data['razorpay_order_id'],
                'razorpay_payment_id': data['razorpay_payment_id'],
                'razorpay_signature': data['razorpay_signature']
            }
            client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            current_app.logger.error(f"Wallet payment verification failed: {str(e)}")
            return jsonify({'error': 'Payment verification failed'}), 400
        
        # Add money to wallet
        amount = float(data['amount'])
        user.wallet_balance += amount
        
        # Record transaction
        from models.user import WalletTransaction
        transaction = WalletTransaction(
            user_id=user.id,
            transaction_type='credit',
            amount=amount,
            description=f"Wallet top-up via Razorpay - {data['razorpay_payment_id']}"
        )
        db.session.add(transaction)
        
        # Add bonus loyalty points for wallet top-up
        bonus_points = int(amount // 100) * 5  # 5 points per ₹100
        if bonus_points > 0:
            user.add_loyalty_points(bonus_points, "Wallet top-up bonus")
        
        db.session.commit()
        
        return jsonify({
            'message': 'Money added to wallet successfully',
            'new_balance': user.wallet_balance,
            'amount_added': amount,
            'bonus_loyalty_points': bonus_points
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Verify wallet payment error: {str(e)}")
        return jsonify({'error': 'Wallet payment verification failed'}), 500


@payment_bp.route('/config', methods=['GET'])
def get_payment_config():
    """Get payment configuration for frontend"""
    try:
        return jsonify({
            'razorpay_key_id': current_app.config.get('RAZORPAY_KEY_ID'),
            'currency': 'INR',
            'wallet_limits': {
                'min_amount': 50,
                'max_amount': 5000
            },
            'payment_methods': ['online', 'cod', 'wallet']
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get payment config error: {str(e)}")
        return jsonify({'error': 'Failed to get payment configuration'}), 500