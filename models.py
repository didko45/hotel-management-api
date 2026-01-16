# Database Models for Hotel Management SaaS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    """User model - each user owns their hotel(s)"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hotels = db.relationship('Hotel', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Hotel(db.Model):
    """Hotel model - multi-tenant isolation"""
    __tablename__ = 'hotels'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False, default='My Hotel')
    address = db.Column(db.String(255), default='')
    phone = db.Column(db.String(20), default='')
    email = db.Column(db.String(100), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    rooms = db.relationship('Room', backref='hotel', lazy=True, cascade='all, delete-orphan')
    guests = db.relationship('Guest', backref='hotel', lazy=True, cascade='all, delete-orphan')
    reservations = db.relationship('Reservation', backref='hotel', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'phone': self.phone,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Room(db.Model):
    """Room model - belongs to a hotel"""
    __tablename__ = 'rooms'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    room_number = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), default='')
    room_type = db.Column(db.String(50), default='Standard')
    price_per_night = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), default='available')  # available, maintenance
    amenities = db.Column(db.Text, default='')  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint: room_number per hotel
    __table_args__ = (
        db.UniqueConstraint('hotel_id', 'room_number', name='unique_room_per_hotel'),
    )

    # Relationships
    reservations = db.relationship('Reservation', backref='room', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'room_number': self.room_number,
            'name': self.name,
            'type': self.room_type,
            'price': float(self.price_per_night),
            'status': self.status,
            'amenities': self.amenities
        }


class Guest(db.Model):
    """Guest model - belongs to a hotel"""
    __tablename__ = 'guests'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), default='')
    email = db.Column(db.String(100), default='')
    phone = db.Column(db.String(20), default='')
    id_number = db.Column(db.String(50), default='')  # Passport/ID
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    reservations = db.relationship('Reservation', backref='guest', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': f"{self.first_name} {self.last_name}".strip(),
            'email': self.email,
            'phone': self.phone,
            'id_number': self.id_number,
            'notes': self.notes
        }


class Reservation(db.Model):
    """Reservation model - belongs to a hotel"""
    __tablename__ = 'reservations'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey('guests.id'), nullable=True)

    # Guest info (for quick access without join)
    guest_name = db.Column(db.String(100), nullable=False)
    guest_email = db.Column(db.String(100), default='')
    guest_phone = db.Column(db.String(20), default='')

    # Booking details
    check_in_date = db.Column(db.Date, nullable=False)
    check_out_date = db.Column(db.Date, nullable=False)
    nights = db.Column(db.Integer, default=1)

    # Pricing
    total_price = db.Column(db.Numeric(10, 2), default=0)
    amount_paid = db.Column(db.Numeric(10, 2), default=0)
    payment_status = db.Column(db.String(20), default='pending')  # pending, partial, paid

    # Status
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, active, completed, cancelled

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    checked_in_at = db.Column(db.DateTime, nullable=True)
    checked_out_at = db.Column(db.DateTime, nullable=True)

    notes = db.Column(db.Text, default='')

    def to_dict(self):
        return {
            'id': self.id,
            'room_id': self.room_id,
            'room_number': self.room.room_number if self.room else None,
            'room_name': self.room.name if self.room else None,
            'guest_id': self.guest_id,
            'guest_name': self.guest_name,
            'guest_email': self.guest_email,
            'guest_phone': self.guest_phone,
            'check_in_date': self.check_in_date.isoformat() if self.check_in_date else None,
            'check_out_date': self.check_out_date.isoformat() if self.check_out_date else None,
            'nights': self.nights,
            'total_price': float(self.total_price) if self.total_price else 0,
            'amount_paid': float(self.amount_paid) if self.amount_paid else 0,
            'payment_status': self.payment_status,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'notes': self.notes
        }
