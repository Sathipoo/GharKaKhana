from flask import Blueprint, request, jsonify, current_app
from geopy.distance import geodesic
from geopy.geocoders import GoogleV3
import os

location_bp = Blueprint('location', __name__)

# Brigade Gateway coordinates
BRIGADE_GATEWAY_COORDS = (12.9716, 77.5946)
DELIVERY_RADIUS_KM = 5

def get_geocoder():
    """Get Google geocoder instance"""
    api_key = current_app.config.get('GOOGLE_MAPS_API_KEY')
    if api_key:
        return GoogleV3(api_key=api_key)
    return None

@location_bp.route('/validate-address', methods=['POST'])
def validate_address():
    """Validate and geocode address"""
    try:
        data = request.get_json()
        address_parts = [
            data.get('address_line1', ''),
            data.get('address_line2', ''),
            data.get('landmark', ''),
            data.get('city', 'Bangalore'),
            data.get('pincode', '')
        ]
        
        full_address = ', '.join([part for part in address_parts if part.strip()])
        
        # Get geocoder
        geocoder = get_geocoder()
        if not geocoder:
            # If no geocoding service, check if coordinates are provided
            lat = data.get('latitude')
            lng = data.get('longitude')
            
            if lat and lng:
                coords = (lat, lng)
                distance = geodesic(BRIGADE_GATEWAY_COORDS, coords).kilometers
                
                delivery_zone = 'brigade_gateway' if distance <= 0.5 else 'other_areas'
                is_deliverable = distance <= DELIVERY_RADIUS_KM
                
                return jsonify({
                    'is_valid': True,
                    'coordinates': {'lat': lat, 'lng': lng},
                    'delivery_zone': delivery_zone,
                    'is_deliverable': is_deliverable,
                    'distance_km': round(distance, 2),
                    'delivery_charge': 0 if delivery_zone == 'brigade_gateway' else 30,
                    'formatted_address': full_address
                }), 200
            else:
                # Default validation without geocoding
                return jsonify({
                    'is_valid': True,
                    'coordinates': None,
                    'delivery_zone': 'other_areas',
                    'is_deliverable': True,
                    'distance_km': None,
                    'delivery_charge': 30,
                    'formatted_address': full_address
                }), 200
        
        # Geocode the address
        try:
            location = geocoder.geocode(full_address, timeout=10)
            
            if not location:
                return jsonify({
                    'is_valid': False,
                    'error': 'Address not found. Please check the address details.'
                }), 400
            
            # Get coordinates
            coords = (location.latitude, location.longitude)
            
            # Calculate distance from Brigade Gateway
            distance = geodesic(BRIGADE_GATEWAY_COORDS, coords).kilometers
            
            # Determine delivery zone
            if distance <= 0.5:  # Within 500m of Brigade Gateway
                delivery_zone = 'brigade_gateway'
            else:
                delivery_zone = 'other_areas'
            
            # Check if deliverable (within 5km radius)
            is_deliverable = distance <= DELIVERY_RADIUS_KM
            
            # Calculate delivery charge
            delivery_charge = 0 if delivery_zone == 'brigade_gateway' else 30
            
            return jsonify({
                'is_valid': True,
                'coordinates': {
                    'lat': location.latitude,
                    'lng': location.longitude
                },
                'delivery_zone': delivery_zone,
                'is_deliverable': is_deliverable,
                'distance_km': round(distance, 2),
                'delivery_charge': delivery_charge,
                'formatted_address': location.address
            }), 200
            
        except Exception as e:
            current_app.logger.error(f"Geocoding error: {str(e)}")
            return jsonify({
                'is_valid': False,
                'error': 'Unable to validate address. Please try again.'
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Validate address error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@location_bp.route('/check-delivery', methods=['POST'])
def check_delivery_availability():
    """Check if delivery is available to given coordinates"""
    try:
        data = request.get_json()
        lat = data.get('latitude')
        lng = data.get('longitude')
        
        if not lat or not lng:
            return jsonify({'error': 'Latitude and longitude are required'}), 400
        
        # Calculate distance from Brigade Gateway
        coords = (lat, lng)
        distance = geodesic(BRIGADE_GATEWAY_COORDS, coords).kilometers
        
        # Determine delivery zone
        if distance <= 0.5:
            delivery_zone = 'brigade_gateway'
            delivery_charge = 0
            delivery_message = "You're in Brigade Gateway! Enjoy free delivery."
        elif distance <= DELIVERY_RADIUS_KM:
            delivery_zone = 'other_areas'
            delivery_charge = 30
            delivery_message = f"Delivery available for ₹{delivery_charge}. Distance: {distance:.1f}km"
        else:
            delivery_zone = 'out_of_range'
            delivery_charge = None
            delivery_message = f"Sorry, we don't deliver to this area yet. Distance: {distance:.1f}km (Max: {DELIVERY_RADIUS_KM}km)"
        
        is_deliverable = distance <= DELIVERY_RADIUS_KM
        
        return jsonify({
            'is_deliverable': is_deliverable,
            'delivery_zone': delivery_zone,
            'delivery_charge': delivery_charge,
            'distance_km': round(distance, 2),
            'message': delivery_message,
            'estimated_delivery_time': 15 if delivery_zone == 'brigade_gateway' else 30
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Check delivery error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@location_bp.route('/search-places', methods=['GET'])
def search_places():
    """Search for places using Google Places API"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        geocoder = get_geocoder()
        if not geocoder:
            return jsonify({'error': 'Location service not available'}), 503
        
        # Search for places
        try:
            results = geocoder.geocode(query, exactly_one=False, timeout=10)
            
            if not results:
                return jsonify({'places': []}), 200
            
            places = []
            for result in results[:5]:  # Limit to 5 results
                coords = (result.latitude, result.longitude)
                distance = geodesic(BRIGADE_GATEWAY_COORDS, coords).kilometers
                
                places.append({
                    'name': result.address,
                    'coordinates': {
                        'lat': result.latitude,
                        'lng': result.longitude
                    },
                    'distance_km': round(distance, 2),
                    'is_deliverable': distance <= DELIVERY_RADIUS_KM,
                    'delivery_zone': 'brigade_gateway' if distance <= 0.5 else 'other_areas'
                })
            
            return jsonify({'places': places}), 200
            
        except Exception as e:
            current_app.logger.error(f"Places search error: {str(e)}")
            return jsonify({'error': 'Search failed. Please try again.'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Search places error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@location_bp.route('/delivery-info', methods=['GET'])
def get_delivery_info():
    """Get delivery information and zones"""
    try:
        return jsonify({
            'restaurant_location': {
                'name': 'Ghar ka Khana - Brigade Gateway',
                'coordinates': {
                    'lat': BRIGADE_GATEWAY_COORDS[0],
                    'lng': BRIGADE_GATEWAY_COORDS[1]
                },
                'address': 'Brigade Gateway, Dr Rajkumar Road, Bangalore'
            },
            'delivery_zones': {
                'brigade_gateway': {
                    'name': 'Brigade Gateway',
                    'radius_km': 0.5,
                    'delivery_charge': 0,
                    'estimated_time_minutes': 15,
                    'description': 'Free delivery within Brigade Gateway campus'
                },
                'other_areas': {
                    'name': 'Other Areas',
                    'radius_km': DELIVERY_RADIUS_KM,
                    'delivery_charge': 30,
                    'estimated_time_minutes': 30,
                    'description': f'Delivery available within {DELIVERY_RADIUS_KM}km radius'
                }
            },
            'max_delivery_radius_km': DELIVERY_RADIUS_KM,
            'currency': 'INR'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get delivery info error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@location_bp.route('/nearby-landmarks', methods=['GET'])
def get_nearby_landmarks():
    """Get nearby landmarks for address suggestions"""
    try:
        landmarks = [
            {
                'name': 'Brigade Gateway',
                'type': 'office_complex',
                'coordinates': {'lat': 12.9716, 'lng': 77.5946},
                'delivery_zone': 'brigade_gateway'
            },
            {
                'name': 'Orion Mall',
                'type': 'shopping_mall',
                'coordinates': {'lat': 12.9698, 'lng': 77.5986},
                'delivery_zone': 'other_areas'
            },
            {
                'name': 'World Trade Center',
                'type': 'office_complex',
                'coordinates': {'lat': 12.9731, 'lng': 77.5905},
                'delivery_zone': 'other_areas'
            },
            {
                'name': 'Rajajinagar Metro Station',
                'type': 'metro_station',
                'coordinates': {'lat': 12.9731, 'lng': 77.5547},
                'delivery_zone': 'other_areas'
            },
            {
                'name': 'Malleswaram',
                'type': 'locality',
                'coordinates': {'lat': 12.9924, 'lng': 77.5752},
                'delivery_zone': 'other_areas'
            }
        ]
        
        # Add delivery info to each landmark
        for landmark in landmarks:
            coords = (landmark['coordinates']['lat'], landmark['coordinates']['lng'])
            distance = geodesic(BRIGADE_GATEWAY_COORDS, coords).kilometers
            landmark['distance_km'] = round(distance, 2)
            landmark['is_deliverable'] = distance <= DELIVERY_RADIUS_KM
            landmark['delivery_charge'] = 0 if landmark['delivery_zone'] == 'brigade_gateway' else 30
        
        return jsonify({'landmarks': landmarks}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get landmarks error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500