const mongoose = require('mongoose');

const orderItemSchema = new mongoose.Schema({
  itemId: { type: String, required: true },
  name: { type: String, required: true },
  description: String,
  price: { type: Number, required: true },
  quantity: { type: Number, required: true, min: 1 },
  specialInstructions: String,
  category: String,
  tags: [String]
});

const orderSchema = new mongoose.Schema({
  orderNumber: {
    type: String,
    unique: true,
    required: true
  },
  customer: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  customerInfo: {
    name: { type: String, required: true },
    phone: { type: String, required: true },
    email: String
  },
  items: [orderItemSchema],
  pricing: {
    subtotal: { type: Number, required: true },
    deliveryCharges: { type: Number, default: 0 },
    taxes: { type: Number, default: 0 },
    discount: { type: Number, default: 0 },
    walletUsed: { type: Number, default: 0 },
    total: { type: Number, required: true }
  },
  deliveryAddress: {
    name: { type: String, required: true },
    phone: { type: String, required: true },
    addressLine1: { type: String, required: true },
    addressLine2: String,
    landmark: String,
    city: { type: String, required: true },
    pincode: { type: String, required: true },
    coordinates: {
      lat: Number,
      lng: Number
    },
    deliveryZone: { 
      type: String, 
      enum: ['brigade_gateway', 'other_areas'],
      required: true 
    }
  },
  timeSlot: {
    type: String,
    enum: ['breakfast', 'lunch', 'dinner'],
    required: true
  },
  scheduledFor: {
    type: Date,
    required: true
  },
  status: {
    type: String,
    enum: [
      'pending',           // Order placed, awaiting confirmation
      'confirmed',         // Order confirmed by restaurant
      'preparing',         // Food being prepared
      'ready_for_pickup',  // Food ready for delivery
      'out_for_delivery',  // Order picked up by delivery partner
      'delivered',         // Order delivered to customer
      'cancelled',         // Order cancelled
      'refunded'          // Order refunded
    ],
    default: 'pending'
  },
  statusHistory: [{
    status: String,
    timestamp: { type: Date, default: Date.now },
    note: String,
    updatedBy: String
  }],
  payment: {
    method: { 
      type: String, 
      enum: ['online', 'cod', 'wallet'], 
      required: true 
    },
    status: { 
      type: String, 
      enum: ['pending', 'completed', 'failed', 'refunded'], 
      default: 'pending' 
    },
    transactionId: String,
    razorpayOrderId: String,
    razorpayPaymentId: String,
    paidAt: Date
  },
  delivery: {
    estimatedTime: Number, // in minutes
    actualDeliveryTime: Date,
    deliveryPartner: {
      name: String,
      phone: String,
      vehicleNumber: String
    },
    trackingUpdates: [{
      message: String,
      timestamp: { type: Date, default: Date.now },
      location: {
        lat: Number,
        lng: Number
      }
    }]
  },
  specialInstructions: String,
  cancellationReason: String,
  refund: {
    amount: Number,
    reason: String,
    processedAt: Date,
    refundTransactionId: String
  },
  feedback: {
    rating: { type: Number, min: 1, max: 5 },
    comment: String,
    submittedAt: Date
  },
  source: {
    type: String,
    enum: ['website', 'zomato', 'swiggy', 'admin'],
    default: 'website'
  },
  loyaltyPointsEarned: { type: Number, default: 0 },
  isActive: { type: Boolean, default: true }
}, {
  timestamps: true
});

// Index for efficient queries
orderSchema.index({ customer: 1, createdAt: -1 });
orderSchema.index({ orderNumber: 1 });
orderSchema.index({ status: 1, scheduledFor: 1 });
orderSchema.index({ 'deliveryAddress.coordinates': '2dsphere' });
orderSchema.index({ timeSlot: 1, scheduledFor: 1 });

// Generate order number
orderSchema.pre('save', async function(next) {
  if (this.isNew) {
    const today = new Date();
    const dateStr = today.toISOString().split('T')[0].replace(/-/g, '');
    const count = await this.constructor.countDocuments({
      createdAt: {
        $gte: new Date(today.getFullYear(), today.getMonth(), today.getDate()),
        $lt: new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1)
      }
    });
    this.orderNumber = `GKK${dateStr}${String(count + 1).padStart(3, '0')}`;
    
    // Add initial status to history
    this.statusHistory.push({
      status: this.status,
      timestamp: new Date(),
      note: 'Order placed',
      updatedBy: 'system'
    });
  }
  next();
});

// Method to update status
orderSchema.methods.updateStatus = function(newStatus, note, updatedBy = 'system') {
  this.status = newStatus;
  this.statusHistory.push({
    status: newStatus,
    timestamp: new Date(),
    note,
    updatedBy
  });
  return this.save();
};

// Method to calculate estimated delivery time
orderSchema.methods.calculateEstimatedDeliveryTime = function() {
  const maxPrepTime = Math.max(...this.items.map(item => item.prepTime || 20));
  const deliveryTime = this.deliveryAddress.deliveryZone === 'brigade_gateway' ? 10 : 20;
  this.delivery.estimatedTime = maxPrepTime + deliveryTime;
  return this.delivery.estimatedTime;
};

// Virtual for order summary
orderSchema.virtual('summary').get(function() {
  return {
    orderNumber: this.orderNumber,
    itemCount: this.items.reduce((sum, item) => sum + item.quantity, 0),
    total: this.pricing.total,
    status: this.status,
    scheduledFor: this.scheduledFor,
    customer: this.customerInfo.name
  };
});

// Method to check if order can be cancelled
orderSchema.methods.canBeCancelled = function() {
  return ['pending', 'confirmed'].includes(this.status);
};

// Method to check if order can be modified
orderSchema.methods.canBeModified = function() {
  return this.status === 'pending';
};

module.exports = mongoose.model('Order', orderSchema);