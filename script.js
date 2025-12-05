const API_URL = window.location.origin;

let currentUser = null;

function loadUser() {
    const user = localStorage.getItem('user');
    if (user) {
        currentUser = JSON.parse(user);
        updateUI();
        loadTokens();
    }
}

function updateUI() {
    if (currentUser) {
        document.getElementById('auth-section').style.display = 'none';
        document.getElementById('user-section').style.display = 'flex';
    } else {
        document.getElementById('auth-section').style.display = 'flex';
        document.getElementById('user-section').style.display = 'none';
    }
}

async function loadTokens() {
    if (!currentUser) return;
    
    const response = await fetch(`${API_URL}/api/user/tokens`, {
        headers: {
            'X-User-Id': currentUser.user_id
        }
    });
    
    const data = await response.json();
    document.getElementById('token-display').textContent = `${data.tokens} tokens`;
}

async function loadRecentCarts() {
    const response = await fetch(`${API_URL}/api/carts/recent`);
    const carts = await response.json();
    
    const grid = document.getElementById('carts-grid');
    grid.innerHTML = '';
    
    carts.forEach(cart => {
        const card = document.createElement('div');
        card.className = 'cart-card';
        card.innerHTML = `
            <h4>${cart.name}</h4>
            <p>by ${cart.owner_email || 'Unknown'}</p>
            <p>${new Date(cart.created_at).toLocaleDateString()}</p>
        `;
        card.onclick = () => {
            window.location.href = `editor.html?cart=${cart.id}`;
        };
        grid.appendChild(card);
    });
}

document.getElementById('login-btn').onclick = () => {
    document.getElementById('modal-title').textContent = 'Login';
    document.getElementById('auth-modal').style.display = 'block';
    document.getElementById('auth-form').onsubmit = handleLogin;
};

document.getElementById('signup-btn').onclick = () => {
    document.getElementById('modal-title').textContent = 'Sign Up';
    document.getElementById('auth-modal').style.display = 'block';
    document.getElementById('auth-form').onsubmit = handleSignup;
};

document.querySelector('.close').onclick = () => {
    document.getElementById('auth-modal').style.display = 'none';
};

async function handleLogin(e) {
    e.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    const response = await fetch(`${API_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });
    
    const data = await response.json();
    
    if (data.success) {
        currentUser = data;
        localStorage.setItem('user', JSON.stringify(data));
        document.getElementById('auth-modal').style.display = 'none';
        updateUI();
        loadTokens();
    } else {
        alert('Login failed: ' + data.error);
    }
}

async function handleSignup(e) {
    e.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    const response = await fetch(`${API_URL}/api/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });
    
    const data = await response.json();
    
    if (data.success) {
        currentUser = data;
        localStorage.setItem('user', JSON.stringify(data));
        document.getElementById('auth-modal').style.display = 'none';
        updateUI();
        loadTokens();
    } else {
        alert('Signup failed: ' + data.error);
    }
}

document.getElementById('logout-btn').onclick = () => {
    currentUser = null;
    localStorage.removeItem('user');
    updateUI();
};

document.getElementById('new-cart-btn').onclick = async () => {
    if (!currentUser) {
        alert('Please login first');
        return;
    }
    
    const name = prompt('Cart name:');
    if (!name) return;
    
    const response = await fetch(`${API_URL}/api/cart/create`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-User-Id': currentUser.user_id
        },
        body: JSON.stringify({ name })
    });
    
    const data = await response.json();
    window.location.href = `editor.html?cart=${data.cart_id}`;
};

loadUser();
loadRecentCarts();

