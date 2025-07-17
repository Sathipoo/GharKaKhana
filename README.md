# Ghar ka Khana - Cloud Kitchen Management System

**Your Home-style Cloud Kitchen's Online Presence – Simplified & Scalable**

A complete Flask-based web application for managing a cloud kitchen with mobile-first customer ordering, OTP authentication, admin dashboard, and integrated payment processing.

## 🚀 Features

### Phase 1 Implementation

✅ **Customer Ordering Web App (Mobile-First)**
- Clean interface to view and order from daily menu
- Category navigation: Breakfast, Lunch/Dinner, Snacks, Salads, Beverages
- Add-to-cart with quantity and notes
- Checkout with delivery address and time slot selection
- Razorpay-based online payment gateway
- Brigade Gateway customers get auto-filled free delivery options

✅ **OTP-Based Authentication**
- 4-digit mobile OTP-based login (no password required)
- View previous orders and save multiple delivery addresses
- Quick reorder functionality

✅ **Admin Dashboard**
- Real-time order management
- Dynamic daily menu updates
- Order reports export (CSV)
- Order tracking and status updates

✅ **Location-Aware Delivery Control**
- Only accepts orders within 5 km of Brigade Gateway
- Brigade Gateway orders highlighted for zero delivery charges
- Coordinate-based address validation

✅ **Smart Notifications**
- SMS notifications for order updates
- Email confirmations
- Real-time status tracking

## 🛠️ Technology Stack

- **Backend**: Flask, SQLAlchemy, Flask-JWT-Extended
- **Database**: SQLite (development) / PostgreSQL (production)
- **Authentication**: OTP-based via Twilio SMS
- **Payments**: Razorpay integration
- **Real-time**: SocketIO for live updates
- **Caching**: Redis for rate limiting
- **Email**: Flask-Mail for notifications

## 📋 Installation & Setup

### Prerequisites

- Python 3.8+
- Redis (for rate limiting)
- Git

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd GharKaKhana
```

### 2. Set Up Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` file with your configurations:

```env
# Flask Configuration
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret-key
FLASK_ENV=development

# Database
DATABASE_URL=sqlite:///gharkaakhana.db

# SMS Configuration (Twilio)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Payment Gateway (Razorpay)
RAZORPAY_KEY_ID=your-razorpay-key-id
RAZORPAY_KEY_SECRET=your-razorpay-key-secret

# Email Configuration
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

### 5. Initialize Database

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 6. Load Menu Data

```bash
python -c "
from app import app, db
from models.menu import MenuManager
with app.app_context():
    MenuManager.load_menu_from_yaml()
"
```

### 7. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## 📱 API Endpoints

### Authentication
- `POST /api/auth/send-otp` - Send OTP to phone
- `POST /api/auth/verify-otp` - Verify OTP and login
- `GET /api/auth/profile` - Get user profile
- `PUT /api/auth/profile` - Update user profile

### Menu
- `GET /api/menu/` - Get menu items
- `GET /api/menu/item/<item_id>` - Get specific item
- `GET /api/menu/search` - Search menu items
- `GET /api/menu/popular` - Get popular items
- `GET /api/menu/recommendations` - Get personalized recommendations

### Orders
- `POST /api/orders/` - Place new order
- `GET /api/orders/` - Get user orders
- `GET /api/orders/<order_id>` - Get order details
- `PUT /api/orders/<order_id>/cancel` - Cancel order

### Payments
- `POST /api/payment/create-order` - Create Razorpay order
- `POST /api/payment/verify` - Verify payment

### Admin (Protected)
- `GET /api/admin/orders` - Get all orders
- `PUT /api/admin/orders/<order_id>/status` - Update order status
- `GET /api/admin/analytics` - Get analytics data

## 🗂️ Project Structure

```
GharKaKhana/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── data/
│   └── menu.yaml         # Menu configuration
├── models/
│   ├── user.py           # User and address models
│   ├── order.py          # Order management models
│   ├── menu.py           # Menu item models
│   └── admin.py          # Admin user models
├── routes/
│   ├── auth.py           # Authentication routes
│   ├── menu.py           # Menu routes
│   ├── orders.py         # Order management routes
│   ├── admin.py          # Admin dashboard routes
│   ├── payment.py        # Payment processing routes
│   └── location.py       # Location services routes
├── utils/
│   ├── sms_service.py    # SMS/OTP utilities
│   └── validators.py     # Input validation utilities
└── static/
    └── uploads/          # File uploads directory
```

## 📊 Menu Configuration

The menu is configured using YAML format in `data/menu.yaml`. This allows for easy menu updates without code changes.

Example menu item:
```yaml
menu:
  breakfast:
    - id: "bf001"
      name: "Poha with Sev"
      description: "Traditional flattened rice with onions, tomatoes, and crunchy sev"
      price: 60
      category: "breakfast"
      tags: ["vegetarian", "light", "maharashtrian"]
      prep_time: 15
      available: true
      image: "/images/poha.jpg"
```

## 🔐 Security Features

- Rate limiting on API endpoints
- JWT-based authentication
- Input validation and sanitization
- CORS protection
- SQL injection prevention
- Password-less authentication (OTP only)

## 📈 Monitoring & Analytics

- Order tracking and status updates
- Customer analytics
- Popular item tracking
- Revenue analytics
- Delivery zone analysis

## 🚀 Deployment

### Production Environment

1. **Database**: Switch to PostgreSQL
```env
DATABASE_URL=postgresql://username:password@localhost/gharkaakhana
```

2. **Web Server**: Use Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

3. **Process Manager**: Use systemd or supervisor
4. **Reverse Proxy**: Use Nginx
5. **SSL**: Configure HTTPS certificates

### Docker Deployment

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## 🧪 Testing

Run tests:
```bash
python -m pytest tests/
```

## 📝 API Documentation

Detailed API documentation is available at `/api/docs` when running in development mode.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

For support and queries:
- Email: support@gharkaakhana.com
- Phone: +91-9876543210

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Built with ❤️ for home-style cooking lovers**