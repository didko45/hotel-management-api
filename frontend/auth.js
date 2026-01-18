// ========================================
// Authentication Handler for Static Frontend
// ========================================

const alertContainer = document.getElementById('alert-container');
const loginForm = document.getElementById('loginForm');
const registerBtn = document.getElementById('registerBtn');

// Check if already logged in
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem(CONFIG.TOKEN_KEY);
    if (token) {
        // Verify token is still valid
        verifyToken(token);
    }
});

async function verifyToken(token) {
    try {
        const response = await fetch(`${CONFIG.API_URL}/api/current-user`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        if (response.ok) {
            window.location.href = 'dashboard.html';
        } else {
            // Token invalid, clear it
            localStorage.removeItem(CONFIG.TOKEN_KEY);
            localStorage.removeItem(CONFIG.USER_KEY);
        }
    } catch (error) {
        console.error('Token verification error:', error);
    }
}

function showAlert(message, type = 'danger') {
    alertContainer.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
}

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    try {
        const response = await fetch(`${CONFIG.API_URL}/api/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success) {
            // Store token and user info
            localStorage.setItem(CONFIG.TOKEN_KEY, data.token);
            localStorage.setItem(CONFIG.USER_KEY, data.username);

            showAlert('Login successful! Redirecting...', 'success');
            setTimeout(() => {
                window.location.href = 'dashboard.html';
            }, 1000);
        } else {
            showAlert(data.message || 'Invalid username or password');
        }
    } catch (error) {
        showAlert('Cannot connect to server. Please check your connection.');
        console.error('Login error:', error);
    }
});

registerBtn.addEventListener('click', async () => {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if (!username || !password) {
        showAlert('Please enter username and password');
        return;
    }

    try {
        const response = await fetch(`${CONFIG.API_URL}/api/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success) {
            showAlert('Account created successfully! You can now login.', 'success');
            document.getElementById('password').value = '';
        } else {
            showAlert(data.message || 'Registration failed');
        }
    } catch (error) {
        showAlert('Cannot connect to server. Please check your connection.');
        console.error('Registration error:', error);
    }
});
