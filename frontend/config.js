// ========================================
// API Configuration
// ========================================
// Change this to your AWS backend URL after deployment

const CONFIG = {
    // Development (local)
    // API_URL: 'http://localhost:5000',

    // Production (Render - HTTPS)
    API_URL: 'https://hotel-management-api-3s92.onrender.com',

    // Token storage key
    TOKEN_KEY: 'hotel_auth_token',
    USER_KEY: 'hotel_current_user',
};

// Don't modify below this line
window.CONFIG = CONFIG;
