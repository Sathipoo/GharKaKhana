import re
import phonenumbers
from phonenumbers import NumberParseException
from email_validator import validate_email as email_validate, EmailNotValidError

def validate_phone_number(phone):
    """Validate Indian phone number"""
    try:
        # Parse phone number
        parsed = phonenumbers.parse(phone, "IN")
        return phonenumbers.is_valid_number(parsed)
    except NumberParseException:
        return False

def format_phone_number(phone):
    """Format phone number to E164 format"""
    try:
        parsed = phonenumbers.parse(phone, "IN")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except NumberParseException:
        pass
    return None

def validate_email(email):
    """Validate email address"""
    try:
        valid = email_validate(email)
        return True
    except EmailNotValidError:
        return False

def validate_pincode(pincode):
    """Validate Indian pincode"""
    pattern = r'^[1-9][0-9]{5}$'
    return bool(re.match(pattern, pincode))

def validate_order_items(items):
    """Validate order items structure"""
    if not isinstance(items, list) or len(items) == 0:
        return False, "Order must contain at least one item"
    
    for item in items:
        if not isinstance(item, dict):
            return False, "Invalid item format"
        
        required_fields = ['item_id', 'name', 'price', 'quantity']
        for field in required_fields:
            if field not in item:
                return False, f"Missing required field: {field}"
        
        if not isinstance(item['quantity'], int) or item['quantity'] <= 0:
            return False, "Item quantity must be a positive integer"
        
        if not isinstance(item['price'], (int, float)) or item['price'] <= 0:
            return False, "Item price must be a positive number"
    
    return True, "Valid"

def validate_delivery_address(address):
    """Validate delivery address"""
    required_fields = ['name', 'phone', 'address_line1', 'city', 'pincode']
    
    for field in required_fields:
        if not address.get(field, '').strip():
            return False, f"{field.replace('_', ' ').title()} is required"
    
    if not validate_phone_number(address['phone']):
        return False, "Invalid phone number"
    
    if not validate_pincode(address['pincode']):
        return False, "Invalid pincode"
    
    return True, "Valid"

def validate_coordinates(lat, lng):
    """Validate latitude and longitude"""
    try:
        lat = float(lat)
        lng = float(lng)
        
        # Check if coordinates are within valid range
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return True
    except (ValueError, TypeError):
        pass
    
    return False

def sanitize_string(text, max_length=None):
    """Sanitize string input"""
    if not isinstance(text, str):
        return ""
    
    # Remove extra whitespace
    text = text.strip()
    
    # Remove potentially harmful characters
    text = re.sub(r'[<>"\']', '', text)
    
    # Limit length if specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text

def validate_time_slot(time_slot):
    """Validate time slot"""
    valid_slots = ['breakfast', 'lunch', 'dinner']
    return time_slot in valid_slots

def validate_payment_method(method):
    """Validate payment method"""
    valid_methods = ['online', 'cod', 'wallet']
    return method in valid_methods

def validate_order_status(status):
    """Validate order status"""
    valid_statuses = [
        'pending', 'confirmed', 'preparing', 'ready_for_pickup',
        'out_for_delivery', 'delivered', 'cancelled', 'refunded'
    ]
    return status in valid_statuses

def validate_rating(rating):
    """Validate rating (1-5)"""
    try:
        rating = int(rating)
        return 1 <= rating <= 5
    except (ValueError, TypeError):
        return False