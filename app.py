"""
Hotel Management SaaS - Multi-tenant Backend
=============================================
Each user has their own isolated hotel data.
"""

from flask import Flask, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime, timedelta, date
from functools import wraps
import os
import secrets
from dotenv import load_dotenv
import jwt

from models import db, User, Hotel, Room, Guest, Reservation

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ============================================
# DATABASE CONFIGURATION
# ============================================

# Neon PostgreSQL connection
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # Fix for SQLAlchemy compatibility with psycopg3
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
    elif DATABASE_URL.startswith('postgresql://'):
        DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///hotel.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Initialize database
db.init_app(app)

# Create tables on startup
with app.app_context():
    db.create_all()

# ============================================
# SECURITY CONFIGURATION
# ============================================

app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
)

# CORS configuration
CORS(app,
     supports_credentials=True,
     origins=["*"],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# JWT Configuration
JWT_SECRET = app.secret_key
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# ============================================
# JWT HELPERS
# ============================================

def create_jwt_token(user_id: int, username: str) -> str:
    """Create a JWT token for the user"""
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict:
    """Verify JWT token and return payload if valid"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user():
    """Get current user from JWT token"""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        payload = verify_jwt_token(token)
        if payload:
            return User.query.get(payload.get('user_id'))
    return None


def get_current_hotel():
    """Get current user's hotel (creates one if doesn't exist)"""
    user = get_current_user()
    if not user:
        return None

    hotel = Hotel.query.filter_by(user_id=user.id).first()
    if not hotel:
        # Create default hotel for user
        hotel = Hotel(user_id=user.id, name=f"{user.username}'s Hotel")
        db.session.add(hotel)
        db.session.commit()

    return hotel


def login_required(f):
    """Authentication decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ============================================
# AUTHENTICATION API ROUTES
# ============================================

@app.route('/api/login', methods=['POST'])
def login():
    """User login - returns JWT token"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        token = create_jwt_token(user.id, user.username)
        return jsonify({
            'success': True,
            'username': username,
            'token': token
        })
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401


@app.route('/api/register', methods=['POST'])
def register():
    """User registration - creates user and their hotel"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400

    # Create user
    user = User(username=username, email=email or None)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Create default hotel for user
    hotel = Hotel(user_id=user.id, name=f"{username}'s Hotel")
    db.session.add(hotel)

    # Create some default rooms
    default_rooms = [
        Room(hotel_id=hotel.id, room_number='101', name='Standard Room 1', room_type='Standard', price_per_night=50),
        Room(hotel_id=hotel.id, room_number='102', name='Standard Room 2', room_type='Standard', price_per_night=50),
        Room(hotel_id=hotel.id, room_number='201', name='Deluxe Room 1', room_type='Deluxe', price_per_night=80),
    ]
    for room in default_rooms:
        db.session.add(room)

    db.session.commit()

    return jsonify({'success': True, 'message': 'Account created successfully'})


@app.route('/api/logout', methods=['POST'])
def logout():
    """User logout"""
    return jsonify({'success': True})


@app.route('/api/current-user')
@login_required
def current_user():
    """Get current logged in user"""
    user = get_current_user()
    return jsonify({'username': user.username})


@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    """Change password for current user"""
    data = request.get_json()
    current_password = data.get('current_password', '').strip()
    new_password = data.get('new_password', '').strip()

    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'Current and new password required'}), 400

    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'New password must be at least 6 characters'}), 400

    user = get_current_user()

    if not user.check_password(current_password):
        return jsonify({'success': False, 'message': 'Current password is incorrect'}), 401

    user.set_password(new_password)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Password changed successfully'})


# ============================================
# DASHBOARD API ROUTES
# ============================================

@app.route('/api/dashboard-stats')
@login_required
def dashboard_stats():
    """Get dashboard statistics for current user's hotel"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    today = date.today()

    # Get stats for THIS hotel only
    total_rooms = Room.query.filter_by(hotel_id=hotel.id).count()

    active_reservations = Reservation.query.filter_by(
        hotel_id=hotel.id,
        status='active'
    ).count()

    occupied_rooms = active_reservations
    available_rooms = total_rooms - occupied_rooms

    # Check-ins and check-outs today
    checkins_today = Reservation.query.filter_by(hotel_id=hotel.id).filter(
        Reservation.check_in_date == today
    ).count()

    checkouts_today = Reservation.query.filter_by(hotel_id=hotel.id, status='active').filter(
        Reservation.check_out_date == today
    ).count()

    # Monthly revenue
    first_of_month = today.replace(day=1)
    monthly_revenue = db.session.query(
        db.func.coalesce(db.func.sum(Reservation.total_price), 0)
    ).filter(
        Reservation.hotel_id == hotel.id,
        Reservation.check_in_date >= first_of_month
    ).scalar()

    return jsonify({
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'available_rooms': available_rooms,
        'occupancy_rate': (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0,
        'checkins_today': checkins_today,
        'checkouts_today': checkouts_today,
        'monthly_revenue': float(monthly_revenue) if monthly_revenue else 0
    })


# ============================================
# ROOM API ROUTES (Multi-tenant)
# ============================================

@app.route('/api/rooms')
@login_required
def get_rooms():
    """Get all rooms for current user's hotel"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    # Only get rooms belonging to THIS hotel
    rooms = Room.query.filter_by(hotel_id=hotel.id).all()

    rooms_with_status = []
    for room in rooms:
        # Check if room has any active reservation
        is_occupied = Reservation.query.filter_by(
            room_id=room.id,
            status='active'
        ).first() is not None

        room_data = room.to_dict()
        room_data['is_occupied'] = is_occupied
        rooms_with_status.append(room_data)

    return jsonify(rooms_with_status)


@app.route('/api/rooms', methods=['POST'])
@login_required
def create_room():
    """Create a new room for current user's hotel"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    data = request.get_json()

    # Check if room number already exists in this hotel
    existing = Room.query.filter_by(
        hotel_id=hotel.id,
        room_number=data.get('room_number')
    ).first()

    if existing:
        return jsonify({'success': False, 'message': 'Room number already exists'}), 400

    room = Room(
        hotel_id=hotel.id,
        room_number=data.get('room_number'),
        name=data.get('name', ''),
        room_type=data.get('type', 'Standard'),
        price_per_night=data.get('price', 0)
    )
    db.session.add(room)
    db.session.commit()

    return jsonify({'success': True, 'room': room.to_dict()})


@app.route('/api/rooms/<int:room_id>', methods=['PUT'])
@login_required
def update_room(room_id):
    """Update room details"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    # Only update if room belongs to this hotel
    room = Room.query.filter_by(id=room_id, hotel_id=hotel.id).first()
    if not room:
        return jsonify({'success': False, 'message': 'Room not found'}), 404

    data = request.get_json()

    if 'name' in data:
        room.name = data['name']
    if 'price' in data:
        room.price_per_night = float(data['price'])
    if 'type' in data:
        room.room_type = data['type']

    db.session.commit()
    return jsonify({'success': True, 'room': room.to_dict()})


@app.route('/api/rooms/<int:room_id>', methods=['DELETE'])
@login_required
def delete_room(room_id):
    """Delete a room"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    room = Room.query.filter_by(id=room_id, hotel_id=hotel.id).first()
    if not room:
        return jsonify({'success': False, 'message': 'Room not found'}), 404

    db.session.delete(room)
    db.session.commit()
    return jsonify({'success': True})


# ============================================
# RESERVATION API ROUTES (Multi-tenant)
# ============================================

@app.route('/api/reservations')
@login_required
def get_reservations():
    """Get all reservations for current user's hotel"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    # Only get reservations belonging to THIS hotel
    reservations = Reservation.query.filter_by(hotel_id=hotel.id).order_by(
        Reservation.check_in_date.desc()
    ).all()

    return jsonify([r.to_dict() for r in reservations])


@app.route('/api/reservations', methods=['POST'])
@login_required
def create_reservation():
    """Create new reservation for current user's hotel"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    data = request.get_json()

    # Validate required fields
    required_fields = ['guest_name', 'room_id', 'check_in_date', 'check_out_date']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'message': f'Missing field: {field}'}), 400

    # Get room (must belong to this hotel)
    room = Room.query.filter_by(id=data['room_id'], hotel_id=hotel.id).first()
    if not room:
        return jsonify({'success': False, 'message': 'Room not found'}), 404

    # Parse dates
    check_in = datetime.strptime(data['check_in_date'], '%Y-%m-%d').date()
    check_out = datetime.strptime(data['check_out_date'], '%Y-%m-%d').date()

    # Check for booking conflicts
    conflict = Reservation.query.filter(
        Reservation.room_id == room.id,
        Reservation.status != 'completed',
        Reservation.status != 'cancelled',
        Reservation.check_in_date < check_out,
        Reservation.check_out_date > check_in
    ).first()

    if conflict:
        return jsonify({'success': False, 'message': 'Room is already booked for these dates'}), 400

    # Calculate price
    nights = (check_out - check_in).days
    total_price = float(room.price_per_night) * nights

    # Create reservation
    reservation = Reservation(
        hotel_id=hotel.id,
        room_id=room.id,
        guest_name=data['guest_name'],
        guest_email=data.get('guest_email', ''),
        guest_phone=data.get('guest_phone', ''),
        check_in_date=check_in,
        check_out_date=check_out,
        nights=nights,
        total_price=total_price,
        amount_paid=float(data.get('amount_paid', 0)),
        payment_status=data.get('payment_status', 'pending'),
        status='pending',
        notes=data.get('notes', '')
    )

    db.session.add(reservation)
    db.session.commit()

    return jsonify({'success': True, 'reservation': reservation.to_dict()})


@app.route('/api/reservations/<int:reservation_id>', methods=['PUT'])
@login_required
def update_reservation(reservation_id):
    """Update reservation"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    # Only update if reservation belongs to this hotel
    reservation = Reservation.query.filter_by(id=reservation_id, hotel_id=hotel.id).first()
    if not reservation:
        return jsonify({'success': False, 'message': 'Reservation not found'}), 404

    data = request.get_json()

    # Update simple fields
    for key in ['guest_name', 'guest_email', 'guest_phone', 'notes', 'payment_status', 'status']:
        if key in data:
            setattr(reservation, key, data[key])

    if 'amount_paid' in data:
        reservation.amount_paid = float(data['amount_paid'])

    # If dates or room changed, recalculate
    if 'check_in_date' in data or 'check_out_date' in data or 'room_id' in data:
        check_in = datetime.strptime(
            data.get('check_in_date', reservation.check_in_date.isoformat()),
            '%Y-%m-%d'
        ).date()
        check_out = datetime.strptime(
            data.get('check_out_date', reservation.check_out_date.isoformat()),
            '%Y-%m-%d'
        ).date()
        room_id = data.get('room_id', reservation.room_id)

        # Check conflict (excluding current reservation)
        conflict = Reservation.query.filter(
            Reservation.id != reservation_id,
            Reservation.room_id == room_id,
            Reservation.status != 'completed',
            Reservation.status != 'cancelled',
            Reservation.check_in_date < check_out,
            Reservation.check_out_date > check_in
        ).first()

        if conflict:
            return jsonify({'success': False, 'message': 'Room already booked for these dates'}), 400

        room = Room.query.filter_by(id=room_id, hotel_id=hotel.id).first()
        if not room:
            return jsonify({'success': False, 'message': 'Room not found'}), 404

        nights = (check_out - check_in).days
        reservation.check_in_date = check_in
        reservation.check_out_date = check_out
        reservation.room_id = room_id
        reservation.nights = nights
        reservation.total_price = float(room.price_per_night) * nights

    db.session.commit()
    return jsonify({'success': True, 'reservation': reservation.to_dict()})


@app.route('/api/reservations/<int:reservation_id>', methods=['DELETE'])
@login_required
def delete_reservation(reservation_id):
    """Delete reservation"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    reservation = Reservation.query.filter_by(id=reservation_id, hotel_id=hotel.id).first()
    if not reservation:
        return jsonify({'success': False, 'message': 'Reservation not found'}), 404

    db.session.delete(reservation)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/reservations/<int:reservation_id>/checkin', methods=['POST'])
@login_required
def checkin_guest(reservation_id):
    """Check in guest"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    reservation = Reservation.query.filter_by(id=reservation_id, hotel_id=hotel.id).first()
    if not reservation:
        return jsonify({'success': False, 'message': 'Reservation not found'}), 404

    reservation.status = 'active'
    reservation.checked_in_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'reservation': reservation.to_dict()})


@app.route('/api/reservations/<int:reservation_id>/checkout', methods=['POST'])
@login_required
def checkout_guest(reservation_id):
    """Check out guest"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    reservation = Reservation.query.filter_by(id=reservation_id, hotel_id=hotel.id).first()
    if not reservation:
        return jsonify({'success': False, 'message': 'Reservation not found'}), 404

    reservation.status = 'completed'
    reservation.checked_out_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'reservation': reservation.to_dict()})


# ============================================
# CALENDAR API ROUTES
# ============================================

@app.route('/api/calendar')
@login_required
def get_calendar_data():
    """Get calendar data for reservations"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    # Get start and end of month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    # Get reservations that overlap with this month
    reservations = Reservation.query.filter(
        Reservation.hotel_id == hotel.id,
        Reservation.check_in_date < end_date,
        Reservation.check_out_date > start_date
    ).all()

    return jsonify([r.to_dict() for r in reservations])


# ============================================
# SETTINGS API ROUTES
# ============================================

@app.route('/api/settings')
@login_required
def get_settings():
    """Get hotel settings"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    return jsonify({
        'hotel_name': hotel.name,
        'hotel_address': hotel.address,
        'hotel_phone': hotel.phone,
        'hotel_email': hotel.email
    })


@app.route('/api/settings', methods=['PUT'])
@login_required
def update_settings():
    """Update hotel settings"""
    hotel = get_current_hotel()
    if not hotel:
        return jsonify({'error': 'No hotel found'}), 404

    data = request.get_json()

    if 'hotel_name' in data:
        hotel.name = data['hotel_name']
    if 'hotel_address' in data:
        hotel.address = data['hotel_address']
    if 'hotel_phone' in data:
        hotel.phone = data['hotel_phone']
    if 'hotel_email' in data:
        hotel.email = data['hotel_email']

    db.session.commit()
    return jsonify({'success': True})


# ============================================
# HEALTH CHECK
# ============================================

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/')
def index():
    """Root endpoint"""
    return jsonify({'message': 'Hotel Management API', 'status': 'running'})


# ============================================
# DATABASE INITIALIZATION
# ============================================

def init_db():
    """Initialize database tables"""
    with app.app_context():
        db.create_all()
        print("Database tables created!")


# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == '__main__':
    init_db()

    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))

    print(f"""
    ========================================
    Hotel Management SaaS - Multi-tenant
    ========================================
    Running on: http://{host}:{port}
    Debug mode: {debug_mode}
    Database: PostgreSQL (Neon)
    ========================================
    """)

    app.run(debug=debug_mode, host=host, port=port)
