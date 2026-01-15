from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from functools import wraps
import secrets
import requests
from typing import Optional
from dotenv import load_dotenv
import jwt

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ============================================
# SECURITY CONFIGURATION
# ============================================

# Secret key: Use environment variable or generate secure default
# IMPORTANT: Set SECRET_KEY in .env file for production!
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Session security settings
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',  # HTTPS only in production
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE='Lax',  # CSRF protection
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),  # Session expires after 24 hours
)

# CORS configuration - Allow requests from GitHub Pages and localhost
CORS(app,
     supports_credentials=True,
     origins=["*"],  # In production, specify your GitHub Pages URL
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# JWT Configuration
JWT_SECRET = app.secret_key
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Data files
DATA_FILE = "hotel_data.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
BOOKING_CONFIG_FILE = "booking_config.json"

# ============================================
# AUTHENTICATION & SECURITY HELPERS
# ============================================

def create_jwt_token(username: str) -> str:
    """Create a JWT token for the user"""
    payload = {
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> Optional[str]:
    """Verify JWT token and return username if valid"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get('username')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user():
    """Get current user from session or JWT token"""
    # First check session (for template-based auth)
    if 'user' in session:
        return session['user']

    # Then check JWT token (for API auth)
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        return verify_jwt_token(token)

    return None


def login_required(f):
    """Authentication decorator - supports both session and JWT"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


def hash_password(password: str) -> str:
    """Hash a password using werkzeug's secure method (pbkdf2:sha256)"""
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verify a password against its hash. Also handles legacy plain-text passwords."""
    # Check if it's a hashed password (starts with hash method identifier)
    if stored_password.startswith('pbkdf2:') or stored_password.startswith('scrypt:'):
        return check_password_hash(stored_password, provided_password)
    else:
        # Legacy plain-text password - verify and flag for migration
        return stored_password == provided_password


def migrate_password_if_needed(username: str, password: str, users: dict) -> bool:
    """Migrate plain-text password to hashed version"""
    stored_password = users.get(username)
    if stored_password and not (stored_password.startswith('pbkdf2:') or stored_password.startswith('scrypt:')):
        # This is a plain-text password, migrate it
        users[username] = hash_password(password)
        save_users(users)
        return True
    return False


# ============================================
# DATA LOADING FUNCTIONS
# ============================================

def load_data():
    """Load hotel data from JSON file"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        default_data = {
            'rooms': [
                {"room_number": 101, "name": "АП. 2А сгр.1", "price": 70, "type": "Studio"},
                {"room_number": 102, "name": "АТ.14 сгр.1", "price": 70, "type": "Studio"},
                {"room_number": 103, "name": "АП.12 сгр.4", "price": 75, "type": "Studio"},
                {"room_number": 104, "name": "АТ.14 сгр.4", "price": 75, "type": "Studio"},
                {"room_number": 105, "name": "АТ.6А сгр.2", "price": 80, "type": "Studio"}
            ],
            'reservations': [],
            'guest_history': {}
        }
        save_data(default_data)
        return default_data


def save_data(data):
    """Save hotel data to JSON file"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4)


def load_settings():
    """Load settings from JSON file"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        default_settings = {
            'email_enabled': False,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'email_address': '',
            'email_password': '',
            'hotel_name': 'My Hotel',
            'hotel_address': '123 Main St',
            'hotel_phone': '555-0100'
        }
        save_settings(default_settings)
        return default_settings


def save_settings(settings):
    """Save settings to JSON file"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)


# ============================================
# PAGE ROUTES
# ============================================

@app.route('/')
def index():
    """Main page"""
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html')


@app.route('/login')
def login_page():
    """Login page"""
    return render_template('login.html')


# ============================================
# AUTHENTICATION API ROUTES
# ============================================

@app.route('/api/login', methods=['POST'])
def login():
    """User login with secure password verification - returns JWT token"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400

    users = load_users()

    if username in users and verify_password(users[username], password):
        # Migrate plain-text password to hashed if needed
        migrate_password_if_needed(username, password, users)

        # Create JWT token for API access
        token = create_jwt_token(username)

        # Also set session for template-based access
        session['user'] = username
        session.permanent = True

        return jsonify({
            'success': True,
            'username': username,
            'token': token  # JWT token for static frontend
        })
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401


@app.route('/api/register', methods=['POST'])
def register():
    """User registration with secure password hashing"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400

    # Password strength validation
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    users = load_users()

    if username in users:
        return jsonify({'success': False, 'message': 'Username already exists'}), 400

    # Store password securely hashed
    users[username] = hash_password(password)
    save_users(users)

    return jsonify({'success': True, 'message': 'Account created successfully'})


@app.route('/api/logout', methods=['POST'])
def logout():
    """User logout"""
    session.pop('user', None)
    return jsonify({'success': True})


@app.route('/api/current-user')
@login_required
def current_user():
    """Get current logged in user"""
    user = get_current_user()
    return jsonify({'username': user})


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

    users = load_users()
    username = get_current_user()

    if not verify_password(users.get(username, ''), current_password):
        return jsonify({'success': False, 'message': 'Current password is incorrect'}), 401

    users[username] = hash_password(new_password)
    save_users(users)

    return jsonify({'success': True, 'message': 'Password changed successfully'})


# ============================================
# DASHBOARD API ROUTES
# ============================================

@app.route('/api/dashboard-stats')
@login_required
def dashboard_stats():
    """Get dashboard statistics"""
    data = load_data()
    today = datetime.now().date()

    # Calculate statistics
    total_rooms = len(data['rooms'])
    active_reservations = [r for r in data['reservations']
                          if r.get('status') == 'active']
    occupied_rooms = len(active_reservations)
    available_rooms = total_rooms - occupied_rooms

    # Check-ins and check-outs today
    checkins_today = sum(1 for r in data['reservations']
                        if r.get('check_in_date') == str(today))
    checkouts_today = sum(1 for r in data['reservations']
                         if r.get('check_out_date') == str(today)
                         and r.get('status') == 'active')

    # Monthly revenue (current month)
    current_month = today.strftime('%Y-%m')
    monthly_revenue = sum(
        r.get('total_price', 0) for r in data['reservations']
        if r.get('check_in_date', '').startswith(current_month)
    )

    return jsonify({
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'available_rooms': available_rooms,
        'occupancy_rate': (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0,
        'checkins_today': checkins_today,
        'checkouts_today': checkouts_today,
        'monthly_revenue': monthly_revenue
    })


# ============================================
# ROOM API ROUTES
# ============================================

@app.route('/api/rooms')
@login_required
def get_rooms():
    """Get all rooms"""
    data = load_data()

    # Determine room availability
    rooms_with_status = []
    for room in data['rooms']:
        # Check if room has any active reservation
        is_occupied = any(
            r.get('room_number') == room['room_number'] and r.get('status') == 'active'
            for r in data['reservations']
        )
        room_data = room.copy()
        room_data['is_occupied'] = is_occupied
        rooms_with_status.append(room_data)

    return jsonify(rooms_with_status)


@app.route('/api/rooms/<int:room_number>', methods=['PUT'])
@login_required
def update_room(room_number):
    """Update room details"""
    data = load_data()
    update_data = request.get_json()

    for room in data['rooms']:
        if room['room_number'] == room_number:
            if 'name' in update_data:
                room['name'] = update_data['name']
            if 'price' in update_data:
                room['price'] = float(update_data['price'])
            if 'type' in update_data:
                room['type'] = update_data['type']

            save_data(data)
            return jsonify({'success': True, 'room': room})

    return jsonify({'success': False, 'message': 'Room not found'}), 404


# ============================================
# RESERVATION API ROUTES
# ============================================

@app.route('/api/reservations')
@login_required
def get_reservations():
    """Get all reservations"""
    data = load_data()
    return jsonify(data['reservations'])


@app.route('/api/reservations', methods=['POST'])
@login_required
def create_reservation():
    """Create new reservation"""
    data = load_data()
    reservation_data = request.get_json()

    # Validate required fields
    required_fields = ['guest_name', 'room_number', 'check_in_date', 'check_out_date']
    for field in required_fields:
        if field not in reservation_data:
            return jsonify({'success': False, 'message': f'Missing field: {field}'}), 400

    # Check for booking conflicts
    room_number = reservation_data['room_number']
    check_in = reservation_data['check_in_date']
    check_out = reservation_data['check_out_date']

    conflict = check_booking_conflict(data['reservations'], room_number, check_in, check_out)
    if conflict:
        return jsonify({'success': False, 'message': 'Room is already booked for these dates'}), 400

    # Calculate total price
    room = next((r for r in data['rooms'] if r['room_number'] == room_number), None)
    if not room:
        return jsonify({'success': False, 'message': 'Room not found'}), 404

    check_in_date = datetime.strptime(check_in, '%Y-%m-%d')
    check_out_date = datetime.strptime(check_out, '%Y-%m-%d')
    nights = (check_out_date - check_in_date).days
    total_price = room['price'] * nights

    # Create reservation
    reservation = {
        'id': len(data['reservations']) + 1,
        'guest_name': reservation_data['guest_name'],
        'guest_email': reservation_data.get('guest_email', ''),
        'guest_phone': reservation_data.get('guest_phone', ''),
        'room_number': room_number,
        'room_name': room['name'],
        'check_in_date': check_in,
        'check_out_date': check_out,
        'nights': nights,
        'total_price': total_price,
        'amount_paid': float(reservation_data.get('amount_paid', 0)),
        'payment_status': reservation_data.get('payment_status', 'pending'),
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'notes': reservation_data.get('notes', '')
    }

    data['reservations'].append(reservation)
    save_data(data)

    return jsonify({'success': True, 'reservation': reservation})


@app.route('/api/reservations/<int:reservation_id>', methods=['PUT'])
@login_required
def update_reservation(reservation_id):
    """Update reservation"""
    data = load_data()
    update_data = request.get_json()

    for i, reservation in enumerate(data['reservations']):
        if reservation['id'] == reservation_id:
            # Update fields
            for key in ['guest_name', 'guest_email', 'guest_phone', 'notes',
                       'amount_paid', 'payment_status', 'status']:
                if key in update_data:
                    reservation[key] = update_data[key]

            # If dates or room changed, recalculate
            if 'check_in_date' in update_data or 'check_out_date' in update_data or 'room_number' in update_data:
                check_in = update_data.get('check_in_date', reservation['check_in_date'])
                check_out = update_data.get('check_out_date', reservation['check_out_date'])
                room_number = update_data.get('room_number', reservation['room_number'])

                # Check conflict (excluding current reservation)
                conflict = check_booking_conflict(data['reservations'], room_number,
                                                 check_in, check_out, exclude_id=reservation_id)
                if conflict:
                    return jsonify({'success': False, 'message': 'Room already booked for these dates'}), 400

                # Recalculate price
                room = next((r for r in data['rooms'] if r['room_number'] == room_number), None)
                check_in_date = datetime.strptime(check_in, '%Y-%m-%d')
                check_out_date = datetime.strptime(check_out, '%Y-%m-%d')
                nights = (check_out_date - check_in_date).days

                reservation['check_in_date'] = check_in
                reservation['check_out_date'] = check_out
                reservation['room_number'] = room_number
                reservation['room_name'] = room['name']
                reservation['nights'] = nights
                reservation['total_price'] = room['price'] * nights

            save_data(data)
            return jsonify({'success': True, 'reservation': reservation})

    return jsonify({'success': False, 'message': 'Reservation not found'}), 404


@app.route('/api/reservations/<int:reservation_id>', methods=['DELETE'])
@login_required
def delete_reservation(reservation_id):
    """Delete reservation"""
    data = load_data()

    for i, reservation in enumerate(data['reservations']):
        if reservation['id'] == reservation_id:
            data['reservations'].pop(i)
            save_data(data)
            return jsonify({'success': True})

    return jsonify({'success': False, 'message': 'Reservation not found'}), 404


@app.route('/api/reservations/<int:reservation_id>/checkin', methods=['POST'])
@login_required
def checkin_guest(reservation_id):
    """Check in guest"""
    data = load_data()

    for reservation in data['reservations']:
        if reservation['id'] == reservation_id:
            reservation['status'] = 'active'
            save_data(data)
            return jsonify({'success': True, 'reservation': reservation})

    return jsonify({'success': False, 'message': 'Reservation not found'}), 404


@app.route('/api/reservations/<int:reservation_id>/checkout', methods=['POST'])
@login_required
def checkout_guest(reservation_id):
    """Check out guest"""
    data = load_data()

    for reservation in data['reservations']:
        if reservation['id'] == reservation_id:
            reservation['status'] = 'completed'
            reservation['checkout_time'] = datetime.now().isoformat()

            # Add to guest history
            guest_name = reservation['guest_name']
            if guest_name not in data['guest_history']:
                data['guest_history'][guest_name] = []

            data['guest_history'][guest_name].append({
                'check_in': reservation['check_in_date'],
                'check_out': reservation['check_out_date'],
                'room': reservation['room_name'],
                'total_paid': reservation.get('amount_paid', 0)
            })

            save_data(data)
            return jsonify({'success': True, 'reservation': reservation})

    return jsonify({'success': False, 'message': 'Reservation not found'}), 404


# ============================================
# CALENDAR API ROUTES
# ============================================

@app.route('/api/calendar')
@login_required
def get_calendar_data():
    """Get calendar data for reservations"""
    data = load_data()
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    # Get all reservations for the month
    month_str = f"{year}-{month:02d}"
    month_reservations = []

    for reservation in data['reservations']:
        check_in = reservation['check_in_date']
        check_out = reservation['check_out_date']

        # Check if reservation overlaps with this month
        if check_in.startswith(month_str) or check_out.startswith(month_str):
            month_reservations.append(reservation)

    return jsonify(month_reservations)


# ============================================
# SETTINGS API ROUTES
# ============================================

@app.route('/api/settings')
@login_required
def get_settings():
    """Get settings"""
    settings = load_settings()
    # Don't send email password to frontend
    settings_copy = settings.copy()
    if 'email_password' in settings_copy:
        settings_copy['email_password'] = '****' if settings['email_password'] else ''
    return jsonify(settings_copy)


@app.route('/api/settings', methods=['PUT'])
@login_required
def update_settings():
    """Update settings"""
    settings = load_settings()
    update_data = request.get_json()

    for key in ['hotel_name', 'hotel_address', 'hotel_phone',
                'email_enabled', 'smtp_server', 'smtp_port', 'email_address']:
        if key in update_data:
            settings[key] = update_data[key]

    # Only update password if provided
    if update_data.get('email_password') and update_data['email_password'] != '****':
        settings['email_password'] = update_data['email_password']

    save_settings(settings)
    return jsonify({'success': True})


# ============================================
# BOOKING CONFLICT CHECK
# ============================================

def check_booking_conflict(reservations, room_number, check_in, check_out, exclude_id=None):
    """Check if there's a booking conflict"""
    new_checkin = datetime.strptime(check_in, '%Y-%m-%d')
    new_checkout = datetime.strptime(check_out, '%Y-%m-%d')

    for reservation in reservations:
        if reservation.get('id') == exclude_id:
            continue

        if reservation['room_number'] != room_number:
            continue

        if reservation.get('status') == 'completed':
            continue

        existing_checkin = datetime.strptime(reservation['check_in_date'], '%Y-%m-%d')
        existing_checkout = datetime.strptime(reservation['check_out_date'], '%Y-%m-%d')

        # Check for overlap
        if (new_checkin < existing_checkout and new_checkout > existing_checkin):
            return True

    return False


# ============================================
# BOOKING.COM INTEGRATION
# ============================================

def load_booking_config():
    """Load Booking.com configuration"""
    if os.path.exists(BOOKING_CONFIG_FILE):
        with open(BOOKING_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        default_config = {
            'enabled': False,
            'api_key': '',
            'hotel_id': '',
            'room_mappings': {},
            'last_sync': None
        }
        save_booking_config(default_config)
        return default_config


def save_booking_config(config):
    """Save Booking.com configuration"""
    with open(BOOKING_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)


@app.route('/api/booking-config')
@login_required
def get_booking_config():
    """Get Booking.com configuration"""
    config = load_booking_config()
    config_copy = config.copy()
    if config_copy.get('api_key'):
        config_copy['api_key'] = '****' if config['api_key'] else ''
    return jsonify(config_copy)


@app.route('/api/booking-config', methods=['PUT'])
@login_required
def update_booking_config():
    """Update Booking.com configuration"""
    config = load_booking_config()
    update_data = request.get_json()

    if 'enabled' in update_data:
        config['enabled'] = update_data['enabled']
    if 'hotel_id' in update_data:
        config['hotel_id'] = update_data['hotel_id']
    if 'room_mappings' in update_data:
        config['room_mappings'] = update_data['room_mappings']

    if 'api_key' in update_data and update_data['api_key'] != '****':
        config['api_key'] = update_data['api_key']

    save_booking_config(config)
    return jsonify({'success': True})


@app.route('/api/booking/sync', methods=['POST'])
@login_required
def sync_booking_reservations():
    """Sync reservations from Booking.com"""
    config = load_booking_config()

    if not config['enabled']:
        return jsonify({'success': False, 'message': 'Booking.com integration not enabled'}), 400

    if not config['api_key'] or not config['hotel_id']:
        return jsonify({'success': False, 'message': 'Missing API credentials'}), 400

    try:
        demo_message = """
        Booking.com Sync - Demo Mode

        To complete setup:
        1. Apply for Booking.com API access at partner.booking.com
        2. Get your API key and Hotel ID
        3. Enter them in Settings > Booking.com Integration
        4. Map your rooms to Booking.com rooms
        """

        config['last_sync'] = datetime.now().isoformat()
        save_booking_config(config)

        return jsonify({
            'success': True,
            'message': demo_message,
            'reservations_imported': 0,
            'last_sync': config['last_sync']
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/booking/test-connection', methods=['POST'])
@login_required
def test_booking_connection():
    """Test Booking.com API connection"""
    config = load_booking_config()

    if not config['api_key'] or not config['hotel_id']:
        return jsonify({
            'success': False,
            'message': 'Please enter API Key and Hotel ID'
        }), 400

    return jsonify({
        'success': True,
        'message': 'Demo Mode - Enter real API credentials to test connection'
    })


# ============================================
# HEALTH CHECK (for deployment monitoring)
# ============================================

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == '__main__':
    # Development mode
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))

    print(f"""
    ========================================
    Hotel Management System
    ========================================
    Running on: http://{host}:{port}
    Debug mode: {debug_mode}

    For production, use:
    - Windows: waitress-serve --port={port} app:app
    - Linux: gunicorn -w 4 -b {host}:{port} app:app
    ========================================
    """)

    app.run(debug=debug_mode, host=host, port=port)
