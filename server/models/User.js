const mongoose = require('mongoose');

const addressSchema = new mongoose.Schema({
  name: { type: String, required: true },
  phone: { type: String, required: true },
  addressLine1: { type: String, required: true },
  addressLine2: { type: String },
  landmark: { type: String },
  city: { type: String, required: true, default: 'Bangalore' },
  pincode: { type: String, required: true },
  coordinates: {
    lat: { type: Number },
    lng: { type: Number }
  },
  isDefault: { type: Boolean, default: false },
  deliveryZone: { 
    type: String, 
    enum: ['brigade_gateway', 'other_areas'],
    required: true 
  }
}, { timestamps: true });

const userSchema = new mongoose.Schema({
  phone: {
    type: String,
    required: true,
    unique: true,
    match: [/^[6-9]\d{9}$/, 'Please enter a valid Indian mobile number']
  },
  name: {
    type: String,
    trim: true
  },
  email: {
    type: String,
    trim: true,
    lowercase: true
  },
  addresses: [addressSchema],
  isVerified: {
    type: Boolean,
    default: false
  },
  lastOTP: {
    code: String,
    expiresAt: Date,
    attempts: { type: Number, default: 0 }
  },
  preferences: {
    dietaryRestrictions: [String], // ['vegetarian', 'jain', 'vegan']
    favoriteItems: [String], // Item IDs
    spiceLevel: { type: String, enum: ['mild', 'medium', 'spicy'], default: 'medium' }
  },
  wallet: {
    balance: { type: Number, default: 0 },
    transactions: [{
      type: { type: String, enum: ['credit', 'debit'] },
      amount: Number,
      description: String,
      orderId: { type: mongoose.Schema.Types.ObjectId, ref: 'Order' },
      createdAt: { type: Date, default: Date.now }
    }]
  },
  loyaltyPoints: {
    current: { type: Number, default: 0 },
    total: { type: Number, default: 0 }
  },
  isActive: {
    type: Boolean,
    default: true
  },
  lastLogin: Date,
  deviceTokens: [String] // For push notifications
}, {
  timestamps: true
});

// Index for fast phone number lookups
userSchema.index({ phone: 1 });
userSchema.index({ 'addresses.coordinates': '2dsphere' });

// Virtual for full name
userSchema.virtual('displayName').get(function() {
  return this.name || `User ${this.phone.slice(-4)}`;
});

// Method to add address
userSchema.methods.addAddress = function(addressData) {
  if (addressData.isDefault) {
    this.addresses.forEach(addr => addr.isDefault = false);
  }
  this.addresses.push(addressData);
  return this.save();
};

// Method to update default address
userSchema.methods.setDefaultAddress = function(addressId) {
  this.addresses.forEach(addr => {
    addr.isDefault = addr._id.toString() === addressId.toString();
  });
  return this.save();
};

// Method to add loyalty points
userSchema.methods.addLoyaltyPoints = function(points, description) {
  this.loyaltyPoints.current += points;
  this.loyaltyPoints.total += points;
  
  // Add wallet credit for every 100 points
  if (this.loyaltyPoints.current >= 100) {
    const creditAmount = Math.floor(this.loyaltyPoints.current / 100) * 10;
    this.loyaltyPoints.current = this.loyaltyPoints.current % 100;
    this.wallet.balance += creditAmount;
    this.wallet.transactions.push({
      type: 'credit',
      amount: creditAmount,
      description: `Loyalty points conversion: ${description}`
    });
  }
  
  return this.save();
};

module.exports = mongoose.model('User', userSchema);