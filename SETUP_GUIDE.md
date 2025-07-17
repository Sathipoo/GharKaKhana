# Ghar ka Khana - Quick Setup Guide

## 🚀 Quick Start (5 minutes)

### 1. Prerequisites
```bash
# Install Python 3.8+
python --version

# Install Git
git --version
```

### 2. Clone and Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd GharKaKhana

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings (optional for development)
nano .env
```

### 4. Initialize and Run
```bash
# Initialize the application (creates DB, loads menu, creates admin)
python run.py init

# Start the server
python run.py
```

🎉 **That's it!** Your application is now running at `http://localhost:5000`

## 📱 Test the Application

### API Health Check
```bash
curl http://localhost:5000/api/health
```

### Admin Login
- **URL**: `http://localhost:5000/admin`
- **Email**: `admin@gharkaakhana.com`
- **Password**: `admin123`

### Customer API Test
```bash
# Get menu
curl http://localhost:5000/api/menu/

# Send OTP (replace with valid Indian mobile number)
curl -X POST http://localhost:5000/api/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"phone": "+919876543210"}'
```

## 🔧 Development Commands

```bash
# Reload menu from YAML
python run.py loadmenu

# Open Python shell with app context
python run.py shell

# Initialize database (if needed)
python run.py init
```

## 📊 Key Features Ready to Test

✅ **Customer Features**:
- OTP-based registration/login
- Browse menu by categories/time slots
- Add items to cart
- Place orders with delivery address
- Track order status
- Wallet and loyalty points

✅ **Admin Features**:
- Admin dashboard with statistics
- Real-time order management
- Update order status
- Export order reports
- Menu item availability toggle

✅ **System Features**:
- Location-based delivery zones
- Payment integration (Razorpay)
- SMS notifications (Twilio)
- Real-time updates (WebSocket)
- Rate limiting and security

## 🎯 Next Steps

1. **Configure External Services** (optional):
   - Add Twilio credentials for SMS
   - Add Razorpay keys for payments
   - Add Google Maps API for location services

2. **Customize Menu**:
   - Edit `data/menu.yaml`
   - Run `python run.py loadmenu`

3. **Deploy to Production**:
   - Use PostgreSQL instead of SQLite
   - Configure Redis for rate limiting
   - Use Nginx + Gunicorn
   - Set up SSL certificates

## 🆘 Troubleshooting

### Common Issues:

**1. Import Errors**
```bash
# Make sure you're in the virtual environment
source venv/bin/activate
pip install -r requirements.txt
```

**2. Database Errors**
```bash
# Reinitialize database
rm gharkaakhana.db
python run.py init
```

**3. Port Already in Use**
```bash
# Use different port
PORT=8000 python run.py
```

**4. SMS/Payment Not Working**
- These features require external service credentials
- For development, OTP is logged to console
- Payment gateway needs Razorpay configuration

## 📞 Support

- Check the main README.md for detailed documentation
- All API endpoints are documented in the README
- Default admin credentials: `admin@gharkaakhana.com` / `admin123`

**Happy Cooking! 🍽️**