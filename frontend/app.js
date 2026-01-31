// ========================================
// Hotel Management Dashboard - Main App
// ========================================

// Global state
let currentUser = null;
let rooms = [];
let reservations = [];
let currentMonth = new Date();

// Initialize app
document.addEventListener('DOMContentLoaded', async () => {
    // Check authentication
    const token = localStorage.getItem(CONFIG.TOKEN_KEY);
    if (!token) {
        window.location.href = 'index.html';
        return;
    }

    // Load user info
    currentUser = localStorage.getItem(CONFIG.USER_KEY);
    document.getElementById('username').textContent = currentUser || 'User';

    // Initialize app
    try {
        await loadSettings();
        await refreshDashboard();
        await loadRooms();
        await loadReservations();
        initializeCalendar();
        setupEventListeners();

        // Set min date for reservations to today
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('checkInDate').min = today;
        document.getElementById('checkOutDate').min = today;
    } catch (error) {
        console.error('Initialization error:', error);
        showAlert('Failed to load data. Please try again.', 'danger');
    }
});

// Refresh dashboard
async function refreshDashboard() {
    try {
        const stats = await api.getDashboardStats();

        // Update stat cards
        document.getElementById('occupiedRooms').textContent = stats.occupied_rooms;
        document.getElementById('availableRooms').textContent = stats.available_rooms;
        document.getElementById('checkinsToday').textContent = stats.checkins_today;
        document.getElementById('monthlyRevenue').textContent = stats.monthly_revenue.toFixed(2);

        // Load recent reservations
        await loadRecentReservations();
    } catch (error) {
        console.error('Error refreshing dashboard:', error);
    }
}

// Load recent reservations
async function loadRecentReservations() {
    try {
        const allReservations = await api.getReservations();

        // Get last 5 reservations
        const recent = allReservations.slice(-5).reverse();

        const tbody = document.getElementById('recentReservations');
        tbody.innerHTML = '';

        if (recent.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center">No reservations yet</td></tr>';
            return;
        }

        recent.forEach(res => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${res.guest_name}</td>
                <td>${res.room_name}</td>
                <td>${formatDate(res.check_in_date)}</td>
                <td>${formatDate(res.check_out_date)}</td>
                <td>${getStatusBadge(res.status)}</td>
                <td>${getPaymentBadge(res.payment_status)}</td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading recent reservations:', error);
    }
}

// Load rooms
async function loadRooms() {
    try {
        rooms = await api.getRooms();

        // Update room select dropdown
        const roomSelect = document.getElementById('roomSelect');
        roomSelect.innerHTML = '<option value="">Select Room</option>';
        rooms.forEach(room => {
            roomSelect.innerHTML += `
                <option value="${room.id}">
                    Room ${room.room_number} - ${room.name || room.type} - &#8364;${room.price}/night
                </option>
            `;
        });

        // Render room cards
        renderRoomCards();
    } catch (error) {
        console.error('Error loading rooms:', error);
    }
}

// Render room cards
function renderRoomCards() {
    const roomsList = document.getElementById('roomsList');
    roomsList.innerHTML = '';

    if (rooms.length === 0) {
        roomsList.innerHTML = `
            <div class="col-12 text-center">
                <p class="text-muted">No rooms yet. Click "Add Room" to create your first room.</p>
            </div>
        `;
        return;
    }

    rooms.forEach(room => {
        const col = document.createElement('div');
        col.className = 'col-md-4 col-lg-3 mb-4';

        const statusClass = room.is_occupied ? 'occupied' : 'available';

        col.innerHTML = `
            <div class="room-card ${statusClass}">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h5 class="mb-0">Room ${room.room_number}</h5>
                    <span class="badge ${room.is_occupied ? 'badge-danger' : 'badge-success'}">
                        ${room.is_occupied ? 'Occupied' : 'Available'}
                    </span>
                </div>
                <p class="text-muted mb-2">${room.name || 'No name'}</p>
                <p class="mb-2"><strong>Type:</strong> ${room.type}</p>
                <p class="mb-3"><strong>Price:</strong> &#8364;${room.price}/night</p>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-outline-primary" onclick="editRoom(${room.id})">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteRoom(${room.id}, '${room.room_number}')" ${room.is_occupied ? 'disabled title="Cannot delete occupied room"' : ''}>
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
        roomsList.appendChild(col);
    });
}

// Load all reservations
async function loadReservations() {
    try {
        reservations = await api.getReservations();
        renderReservations();
    } catch (error) {
        console.error('Error loading reservations:', error);
    }
}

// Render reservations table
function renderReservations() {
    const tbody = document.getElementById('allReservations');
    tbody.innerHTML = '';

    if (reservations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="text-center">No reservations found</td></tr>';
        return;
    }

    // Sort by check-in date (newest first)
    const sorted = [...reservations].sort((a, b) =>
        new Date(b.check_in_date) - new Date(a.check_in_date)
    );

    sorted.forEach(res => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${res.id}</td>
            <td>${res.guest_name}</td>
            <td>
                ${res.guest_email ? `<div><i class="fas fa-envelope"></i> ${res.guest_email}</div>` : ''}
                ${res.guest_phone ? `<div><i class="fas fa-phone"></i> ${res.guest_phone}</div>` : ''}
            </td>
            <td>${res.room_name}</td>
            <td>${formatDate(res.check_in_date)}</td>
            <td>${formatDate(res.check_out_date)}</td>
            <td>${res.nights}</td>
            <td>&#8364;${res.total_price.toFixed(2)}</td>
            <td>&#8364;${res.amount_paid.toFixed(2)}</td>
            <td>${getStatusBadge(res.status)}</td>
            <td>
                <div class="btn-group btn-group-sm">
                    ${res.status === 'pending' ? `
                        <button class="btn btn-success" onclick="checkIn(${res.id})" title="Check In">
                            <i class="fas fa-sign-in-alt"></i>
                        </button>
                    ` : ''}
                    ${res.status === 'active' ? `
                        <button class="btn btn-warning" onclick="checkOut(${res.id})" title="Check Out">
                            <i class="fas fa-sign-out-alt"></i>
                        </button>
                    ` : ''}
                    <button class="btn btn-primary" onclick="editReservation(${res.id})" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-danger" onclick="deleteReservation(${res.id})" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Show new reservation modal
function showNewReservationModal() {
    const modal = new bootstrap.Modal(document.getElementById('newReservationModal'));
    document.getElementById('newReservationForm').reset();
    modal.show();
}

// Setup event listeners
function setupEventListeners() {
    // New reservation form
    document.getElementById('newReservationForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await createReservation();
    });

    // Add room form
    document.getElementById('addRoomForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = {
            room_number: document.getElementById('newRoomNumber').value,
            name: document.getElementById('newRoomName').value,
            type: document.getElementById('newRoomType').value,
            price: parseFloat(document.getElementById('newRoomPrice').value)
        };
        await createRoom(data);
    });

    // Settings form
    document.getElementById('settingsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveSettings();
    });

    // Update checkout date min when checkin changes
    document.getElementById('checkInDate').addEventListener('change', (e) => {
        const checkIn = new Date(e.target.value);
        checkIn.setDate(checkIn.getDate() + 1);
        document.getElementById('checkOutDate').min = checkIn.toISOString().split('T')[0];
    });

    // Edit reservation form
    document.getElementById('editReservationForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveReservation();
    });

    // Update edit checkout date min when edit checkin changes
    document.getElementById('editCheckInDate').addEventListener('change', (e) => {
        const checkIn = new Date(e.target.value);
        checkIn.setDate(checkIn.getDate() + 1);
        document.getElementById('editCheckOutDate').min = checkIn.toISOString().split('T')[0];
    });
}

// Create reservation
async function createReservation() {
    const data = {
        guest_name: document.getElementById('guestName').value,
        guest_email: document.getElementById('guestEmail').value,
        guest_phone: document.getElementById('guestPhone').value,
        room_id: parseInt(document.getElementById('roomSelect').value),
        check_in_date: document.getElementById('checkInDate').value,
        check_out_date: document.getElementById('checkOutDate').value,
        amount_paid: parseFloat(document.getElementById('amountPaid').value),
        payment_status: document.getElementById('paymentStatus').value,
        notes: document.getElementById('reservationNotes').value
    };

    try {
        const result = await api.createReservation(data);

        if (result.success) {
            bootstrap.Modal.getInstance(document.getElementById('newReservationModal')).hide();
            showAlert('Reservation created successfully!', 'success');
            await refreshDashboard();
            await loadReservations();
            await loadRooms();
        } else {
            showAlert(result.message || 'Failed to create reservation', 'danger');
        }
    } catch (error) {
        console.error('Error creating reservation:', error);
        showAlert('An error occurred', 'danger');
    }
}

// Check in guest
async function checkIn(reservationId) {
    if (!confirm('Check in this guest?')) return;

    try {
        const result = await api.checkIn(reservationId);

        if (result.success) {
            showAlert('Guest checked in successfully!', 'success');
            await refreshDashboard();
            await loadReservations();
            await loadRooms();
        } else {
            showAlert(result.message || 'Failed to check in', 'danger');
        }
    } catch (error) {
        console.error('Error checking in:', error);
        showAlert('An error occurred', 'danger');
    }
}

// Check out guest
async function checkOut(reservationId) {
    if (!confirm('Check out this guest?')) return;

    try {
        const result = await api.checkOut(reservationId);

        if (result.success) {
            showAlert('Guest checked out successfully!', 'success');
            await refreshDashboard();
            await loadReservations();
            await loadRooms();
        } else {
            showAlert(result.message || 'Failed to check out', 'danger');
        }
    } catch (error) {
        console.error('Error checking out:', error);
        showAlert('An error occurred', 'danger');
    }
}

// Delete reservation
async function deleteReservation(reservationId) {
    if (!confirm('Are you sure you want to delete this reservation?')) return;

    try {
        const result = await api.deleteReservation(reservationId);

        if (result.success) {
            showAlert('Reservation deleted successfully!', 'success');
            await refreshDashboard();
            await loadReservations();
            await loadRooms();
        } else {
            showAlert(result.message || 'Failed to delete reservation', 'danger');
        }
    } catch (error) {
        console.error('Error deleting reservation:', error);
        showAlert('An error occurred', 'danger');
    }
}

// Edit room
function editRoom(roomId) {
    const room = rooms.find(r => r.id === roomId);
    if (!room) return;

    const newPrice = prompt(`Edit price for ${room.name || 'Room ' + room.room_number}:`, room.price);
    if (newPrice !== null && !isNaN(newPrice)) {
        updateRoom(roomId, { price: parseFloat(newPrice) });
    }
}

// Update room
async function updateRoom(roomId, data) {
    try {
        const result = await api.updateRoom(roomId, data);

        if (result.success) {
            showAlert('Room updated successfully!', 'success');
            await loadRooms();
        } else {
            showAlert(result.message || 'Failed to update room', 'danger');
        }
    } catch (error) {
        console.error('Error updating room:', error);
        showAlert('An error occurred', 'danger');
    }
}

// Create new room
async function createRoom(data) {
    try {
        const result = await api.createRoom(data);

        if (result.success) {
            showAlert('Room created successfully!', 'success');
            await loadRooms();
            await refreshDashboard();
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('addRoomModal'));
            if (modal) modal.hide();
            // Reset form
            document.getElementById('addRoomForm').reset();
        } else {
            showAlert(result.message || 'Failed to create room', 'danger');
        }
    } catch (error) {
        console.error('Error creating room:', error);
        showAlert('An error occurred', 'danger');
    }
}

// Delete room
async function deleteRoom(roomId, roomNumber) {
    if (!confirm(`Are you sure you want to delete Room ${roomNumber}?`)) {
        return;
    }

    try {
        const result = await api.deleteRoom(roomId);

        if (result.success) {
            showAlert('Room deleted successfully!', 'success');
            await loadRooms();
            await refreshDashboard();
        } else {
            showAlert(result.message || 'Failed to delete room', 'danger');
        }
    } catch (error) {
        console.error('Error deleting room:', error);
        showAlert('An error occurred', 'danger');
    }
}

// Edit reservation
function editReservation(reservationId) {
    const reservation = reservations.find(r => r.id === reservationId);
    if (!reservation) {
        showAlert('Reservation not found', 'danger');
        return;
    }

    // Populate edit room select dropdown
    const editRoomSelect = document.getElementById('editRoomSelect');
    editRoomSelect.innerHTML = '<option value="">Select Room</option>';
    rooms.forEach(room => {
        editRoomSelect.innerHTML += `
            <option value="${room.id}" ${room.id === reservation.room_id ? 'selected' : ''}>
                Room ${room.room_number} - ${room.name || room.type} - &#8364;${room.price}/night
            </option>
        `;
    });

    // Fill form with reservation data
    document.getElementById('editReservationId').value = reservation.id;
    document.getElementById('editGuestName').value = reservation.guest_name;
    document.getElementById('editGuestEmail').value = reservation.guest_email || '';
    document.getElementById('editGuestPhone').value = reservation.guest_phone || '';
    document.getElementById('editCheckInDate').value = reservation.check_in_date;
    document.getElementById('editCheckOutDate').value = reservation.check_out_date;
    document.getElementById('editAmountPaid').value = reservation.amount_paid;
    document.getElementById('editPaymentStatus').value = reservation.payment_status;
    document.getElementById('editReservationNotes').value = reservation.notes || '';

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('editReservationModal'));
    modal.show();
}

// Save edited reservation
async function saveReservation() {
    const reservationId = parseInt(document.getElementById('editReservationId').value);

    const data = {
        guest_name: document.getElementById('editGuestName').value,
        guest_email: document.getElementById('editGuestEmail').value,
        guest_phone: document.getElementById('editGuestPhone').value,
        room_id: parseInt(document.getElementById('editRoomSelect').value),
        check_in_date: document.getElementById('editCheckInDate').value,
        check_out_date: document.getElementById('editCheckOutDate').value,
        amount_paid: parseFloat(document.getElementById('editAmountPaid').value),
        payment_status: document.getElementById('editPaymentStatus').value,
        notes: document.getElementById('editReservationNotes').value
    };

    try {
        const result = await api.updateReservation(reservationId, data);

        if (result.success) {
            bootstrap.Modal.getInstance(document.getElementById('editReservationModal')).hide();
            showAlert('Reservation updated successfully!', 'success');
            await refreshDashboard();
            await loadReservations();
            await loadRooms();
        } else {
            showAlert(result.message || 'Failed to update reservation', 'danger');
        }
    } catch (error) {
        console.error('Error updating reservation:', error);
        showAlert('An error occurred', 'danger');
    }
}

// Load settings
async function loadSettings() {
    try {
        const settings = await api.getSettings();

        document.getElementById('hotelNameInput').value = settings.hotel_name;
        document.getElementById('hotelAddress').value = settings.hotel_address;
        document.getElementById('hotelPhone').value = settings.hotel_phone;
        document.getElementById('emailEnabled').checked = settings.email_enabled;
        document.getElementById('smtpServer').value = settings.smtp_server;
        document.getElementById('smtpPort').value = settings.smtp_port;
        document.getElementById('emailAddress').value = settings.email_address;

        // Update hotel name in navbar
        document.getElementById('hotelName').textContent = settings.hotel_name;
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

// Save settings
async function saveSettings() {
    const data = {
        hotel_name: document.getElementById('hotelNameInput').value,
        hotel_address: document.getElementById('hotelAddress').value,
        hotel_phone: document.getElementById('hotelPhone').value,
        email_enabled: document.getElementById('emailEnabled').checked,
        smtp_server: document.getElementById('smtpServer').value,
        smtp_port: parseInt(document.getElementById('smtpPort').value),
        email_address: document.getElementById('emailAddress').value,
        email_password: document.getElementById('emailPassword').value
    };

    try {
        const result = await api.updateSettings(data);

        if (result.success) {
            showAlert('Settings saved successfully!', 'success');
            document.getElementById('hotelName').textContent = data.hotel_name;
        } else {
            showAlert('Failed to save settings', 'danger');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        showAlert('An error occurred', 'danger');
    }
}

// Calendar functions
function initializeCalendar() {
    renderCalendar();
}

async function renderCalendar() {
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'];
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();

    document.getElementById('currentMonth').textContent =
        `${monthNames[month]} ${year}`;

    // Get first day of month and number of days
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const daysInPrevMonth = new Date(year, month, 0).getDate();

    // Get reservations for this month
    const monthReservations = reservations.filter(res => {
        const checkIn = new Date(res.check_in_date);
        const checkOut = new Date(res.check_out_date);
        const monthStart = new Date(year, month, 1);
        const monthEnd = new Date(year, month + 1, 0);

        return (checkIn <= monthEnd && checkOut >= monthStart);
    });

    // Build calendar HTML
    let calendarHTML = `<div class="calendar-grid">`;

    // Add day headers
    dayNames.forEach(day => {
        calendarHTML += `<div class="calendar-day-header">${day}</div>`;
    });

    // Add empty cells for days before month starts
    for (let i = 0; i < firstDay; i++) {
        const prevMonthDay = daysInPrevMonth - firstDay + i + 1;
        calendarHTML += `<div class="calendar-day other-month"><div class="day-number">${prevMonthDay}</div></div>`;
    }

    // Add days of current month
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    for (let day = 1; day <= daysInMonth; day++) {
        const currentDate = new Date(year, month, day);
        currentDate.setHours(0, 0, 0, 0);
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

        const isToday = currentDate.getTime() === today.getTime();

        // Find bookings for this day (exclude check-out date - guest leaves that day)
        const dayBookings = monthReservations.filter(res => {
            const checkIn = new Date(res.check_in_date);
            const checkOut = new Date(res.check_out_date);
            checkIn.setHours(0, 0, 0, 0);
            checkOut.setHours(0, 0, 0, 0);
            return currentDate >= checkIn && currentDate < checkOut;
        });

        const hasBooking = dayBookings.length > 0;
        const todayClass = isToday ? 'today' : '';
        const bookingClass = hasBooking ? 'has-booking' : '';

        calendarHTML += `
            <div class="calendar-day ${todayClass} ${bookingClass}" data-date="${dateStr}">
                <div class="day-number">${day}</div>
                <div class="day-bookings">
        `;

        dayBookings.forEach(booking => {
            calendarHTML += `
                <div class="booking-dot" title="${booking.guest_name} - ${booking.room_name}">
                    ${booking.room_name}
                </div>
            `;
        });

        calendarHTML += `</div></div>`;
    }

    // Add remaining cells
    const totalCells = firstDay + daysInMonth;
    const remainingCells = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (let i = 1; i <= remainingCells; i++) {
        calendarHTML += `<div class="calendar-day other-month"><div class="day-number">${i}</div></div>`;
    }

    calendarHTML += `</div>`;

    document.getElementById('calendarView').innerHTML = calendarHTML;

    // Add click events
    document.querySelectorAll('.calendar-day').forEach(dayEl => {
        dayEl.addEventListener('click', function() {
            const date = this.dataset.date;
            if (date) showDayDetails(date);
        });
    });
}

function showDayDetails(date) {
    const dayReservations = reservations.filter(res => {
        const checkIn = new Date(res.check_in_date);
        const checkOut = new Date(res.check_out_date);
        const selectedDate = new Date(date);
        checkIn.setHours(0, 0, 0, 0);
        checkOut.setHours(0, 0, 0, 0);
        selectedDate.setHours(0, 0, 0, 0);
        return selectedDate >= checkIn && selectedDate < checkOut;
    });

    if (dayReservations.length === 0) {
        showAlert('No bookings for this date', 'info');
        return;
    }

    let detailsHTML = `<strong>Bookings for ${formatDate(date)}:</strong><br><br>`;
    dayReservations.forEach(res => {
        detailsHTML += `
            - ${res.guest_name} - ${res.room_name}<br>
            &nbsp;&nbsp;${formatDate(res.check_in_date)} to ${formatDate(res.check_out_date)}<br>
            &nbsp;&nbsp;Status: ${res.status}<br><br>
        `;
    });

    showAlert(detailsHTML, 'info');
}

async function prevMonth() {
    currentMonth.setMonth(currentMonth.getMonth() - 1);
    await renderCalendar();
}

async function nextMonth() {
    currentMonth.setMonth(currentMonth.getMonth() + 1);
    await renderCalendar();
}

// Utility functions
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

function getStatusBadge(status) {
    const badges = {
        'pending': '<span class="badge badge-warning">Pending</span>',
        'active': '<span class="badge badge-info">Active</span>',
        'completed': '<span class="badge bg-secondary">Completed</span>'
    };
    return badges[status] || status;
}

function getPaymentBadge(status) {
    const badges = {
        'pending': '<span class="badge badge-danger">Pending</span>',
        'partial': '<span class="badge badge-warning">Partial</span>',
        'paid': '<span class="badge badge-success">Paid</span>'
    };
    return badges[status] || status;
}

function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
    alertDiv.style.zIndex = '9999';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alertDiv);

    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}
