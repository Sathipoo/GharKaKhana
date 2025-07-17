from twilio.rest import Client
from flask import current_app
import os

class SMSService:
    """SMS service for sending OTP and notifications"""
    
    def __init__(self):
        self.account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        self.auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        self.phone_number = current_app.config.get('TWILIO_PHONE_NUMBER')
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            current_app.logger.warning("Twilio credentials not configured")
    
    def send_otp(self, phone_number, otp):
        """Send OTP to phone number"""
        try:
            if not self.client:
                # In development, just log the OTP
                current_app.logger.info(f"📱 OTP for {phone_number}: {otp}")
                return True
            
            message = f"Your Ghar ka Khana OTP is: {otp}. Valid for 10 minutes. Do not share with anyone."
            
            message = self.client.messages.create(
                body=message,
                from_=self.phone_number,
                to=phone_number
            )
            
            current_app.logger.info(f"📱 OTP sent to {phone_number}: {message.sid}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"❌ SMS error: {str(e)}")
            # In case of SMS failure, log OTP for development
            current_app.logger.info(f"📱 Fallback OTP for {phone_number}: {otp}")
            return True  # Return True to not block user flow
    
    def send_order_notification(self, phone_number, order_number, status):
        """Send order status notification"""
        try:
            if not self.client:
                current_app.logger.info(f"📱 Order notification for {phone_number}: Order {order_number} is {status}")
                return True
            
            status_messages = {
                'confirmed': f"Your order {order_number} has been confirmed! We're preparing your delicious meal.",
                'preparing': f"Great news! Your order {order_number} is being prepared in our kitchen.",
                'ready_for_pickup': f"Your order {order_number} is ready for pickup!",
                'out_for_delivery': f"Your order {order_number} is on its way to you!",
                'delivered': f"Your order {order_number} has been delivered. Enjoy your meal! Please rate us.",
                'cancelled': f"Your order {order_number} has been cancelled. Any payment will be refunded."
            }
            
            message_body = status_messages.get(status, f"Update on your order {order_number}: {status}")
            
            message = self.client.messages.create(
                body=message_body,
                from_=self.phone_number,
                to=phone_number
            )
            
            current_app.logger.info(f"📱 Order notification sent to {phone_number}: {message.sid}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"❌ Order notification SMS error: {str(e)}")
            return False
    
    def send_promotional_message(self, phone_number, message_body):
        """Send promotional message"""
        try:
            if not self.client:
                current_app.logger.info(f"📱 Promotional message for {phone_number}: {message_body}")
                return True
            
            message = self.client.messages.create(
                body=f"🍽️ Ghar ka Khana: {message_body}",
                from_=self.phone_number,
                to=phone_number
            )
            
            current_app.logger.info(f"📱 Promotional message sent to {phone_number}: {message.sid}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"❌ Promotional SMS error: {str(e)}")
            return False