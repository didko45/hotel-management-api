// ========================================
// API Client for Static Frontend
// ========================================

class HotelAPI {
    constructor() {
        this.baseURL = CONFIG.API_URL;
    }

    getToken() {
        return localStorage.getItem(CONFIG.TOKEN_KEY);
    }

    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            ...options,
            headers: this.getHeaders()
        };

        try {
            const response = await fetch(url, config);

            // Handle unauthorized (token expired)
            if (response.status === 401) {
                localStorage.removeItem(CONFIG.TOKEN_KEY);
                localStorage.removeItem(CONFIG.USER_KEY);
                window.location.href = 'index.html';
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // GET request
    async get(endpoint) {
        return this.request(endpoint);
    }

    // POST request
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    // PUT request
    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    // DELETE request
    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }

    // ========================================
    // API Methods
    // ========================================

    // Auth
    async getCurrentUser() {
        return this.get('/api/current-user');
    }

    async logout() {
        localStorage.removeItem(CONFIG.TOKEN_KEY);
        localStorage.removeItem(CONFIG.USER_KEY);
        window.location.href = 'index.html';
    }

    // Dashboard
    async getDashboardStats() {
        return this.get('/api/dashboard-stats');
    }

    // Rooms
    async getRooms() {
        return this.get('/api/rooms');
    }

    async createRoom(data) {
        return this.post('/api/rooms', data);
    }

    async updateRoom(roomId, data) {
        return this.put(`/api/rooms/${roomId}`, data);
    }

    async deleteRoom(roomId) {
        return this.delete(`/api/rooms/${roomId}`);
    }

    // Reservations
    async getReservations() {
        return this.get('/api/reservations');
    }

    async createReservation(data) {
        return this.post('/api/reservations', data);
    }

    async updateReservation(id, data) {
        return this.put(`/api/reservations/${id}`, data);
    }

    async deleteReservation(id) {
        return this.delete(`/api/reservations/${id}`);
    }

    async checkIn(id) {
        return this.post(`/api/reservations/${id}/checkin`);
    }

    async checkOut(id) {
        return this.post(`/api/reservations/${id}/checkout`);
    }

    // Calendar
    async getCalendarData(year, month) {
        return this.get(`/api/calendar?year=${year}&month=${month}`);
    }

    // Settings
    async getSettings() {
        return this.get('/api/settings');
    }

    async updateSettings(data) {
        return this.put('/api/settings', data);
    }

    // Booking.com
    async getBookingConfig() {
        return this.get('/api/booking-config');
    }

    async updateBookingConfig(data) {
        return this.put('/api/booking-config', data);
    }

    async syncBooking() {
        return this.post('/api/booking/sync');
    }

    async testBookingConnection() {
        return this.post('/api/booking/test-connection');
    }
}

// Create global API instance
window.api = new HotelAPI();
