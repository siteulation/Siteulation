const API_URL = window.location.origin;

let currentUser = null;
let cartId = null;
let cartData = null;
let currentVersion = null;

function loadUser() {
    const user = localStorage.getItem('user');
    if (user) {
        currentUser = JSON.parse(user);
        loadTokens();
    } else {
        alert('Please login first');
        window.location.href = 'index.html';
    }
}

async function loadTokens() {
    const response = await fetch(`${API_URL}/api/user/tokens`, {
        headers: {
            'X-User-Id': currentUser.user_id
        }
    });    

    const data = await response.json();
    document.getElementById('editor-tokens').textContent = `${data.tokens} tokens`;
}

async function loadCart() {
    const params = new URLSearchParams(window.location.search);
    cartId = params.get('cart');
    const versionParam = params.get('version');    

    if (!cartId) {
        alert('No cart specified');
        window.location.href = 'index.html';
        return;
    }    

    const response = await fetch(`${API_URL}/api/cart/${cartId}`);
    cartData = await response.json();    

    if (cartData.error) {
        alert('Cart not found');
        window.location.href = 'index.html';
        return;
    }    

    if (cartData.cart.owner_id !== currentUser.user_id) {
        const remix = confirm('This cart belongs to someone else. Create a remix?');
        if (remix) {
            const response = await fetch(`${API_URL}/api/cart/${cartId}/remix`, {
                method: 'POST',
                headers: {
                    'X-User-Id': currentUser.user_id
                }
            });
            const data = await response.json();
            window.location.href = `editor.html?cart=${data.cart_id}`;
        } else {
            window.location.href = 'index.html';
        }
        return;
    }    

    document.getElementById('cart-name').textContent = cartData.cart.name;

    const versionSelect = document.getElementById('version-select');
    versionSelect.innerHTML = '';

    cartData.versions.forEach(v => {
        const option = document.createElement('option');
        option.value = v.version_number;
        option.textContent = `v${v.version_number}${v.version_number === cartData.cart.pinned_version ? ' (pinned)' : ''}`;
        versionSelect.appendChild(option);
    });    

    if (versionParam) {
        currentVersion = parseInt(versionParam);
        versionSelect.value = currentVersion;
    } else if (cartData.cart.pinned_version) {
        currentVersion = cartData.cart.pinned_version;
        versionSelect.value = currentVersion;
    } else {
        currentVersion = cartData.versions[0].version_number;
        versionSelect.value = currentVersion;
    }    

    loadVersion(currentVersion);
    updateHistory();
}

function loadVersion(versionNumber) {
    const version = cartData.versions.find(v => v.version_number === versionNumber);
    if (version) {
        const frame = document.getElementById('preview-frame');
        const blob = new Blob([version.content], { type: 'text/html' });
        frame.src = URL.createObjectURL(blob);
    }
}

function updateHistory() {
    const historyList = document.getElementById('history-list');
    historyList.innerHTML = '';

    cartData.versions.forEach(v => {
        const item = document.createElement('div');
        item.className = 'history-item';
        if (v.version_number === currentVersion) {
            item.classList.add('active');
        }
        item.innerHTML = `
            <strong>Version ${v.version_number}</strong>
            ${v.version_number === cartData.cart.pinned_version ? '<span> (pinned)</span>' : ''}
            <br>
            <small>${new Date(v.created_at).toLocaleString()}</small>
        `;
        item.onclick = () => {
            currentVersion = v.version_number;
            document.getElementById('version-select').value = currentVersion;
            loadVersion(currentVersion);
            updateHistory();
        };
        historyList.appendChild(item);
    });
}

document.getElementById('version-select').onchange = (e) => {
    currentVersion = parseInt(e.target.value);
    loadVersion(currentVersion);
    updateHistory();
};

document.getElementById('pin-btn').onclick = async () => {
    await fetch(`${API_URL}/api/cart/${cartId}/pin/${currentVersion}`, {
        method: 'POST',
        headers: {
            'X-User-Id': currentUser.user_id
        }
    });    

    cartData.cart.pinned_version = currentVersion;
    document.getElementById('version-select').innerHTML = '';
    cartData.versions.forEach(v => {
        const option = document.createElement('option');
        option.value = v.version_number;
        option.textContent = `v${v.version_number}${v.version_number === cartData.cart.pinned_version ? ' (pinned)' : ''}`;
        document.getElementById('version-select').appendChild(option);
    });
    updateHistory();
};

document.getElementById('generate-btn').onclick = async () => {
    const prompt = document.getElementById('prompt').value;
    if (!prompt) {
        alert('Please enter a prompt');
        return;
    }    

    const model = document.querySelector('input[name="model"]:checked').value;

    document.getElementById('generate-btn').disabled = true;
    document.getElementById('generate-btn').textContent = 'Generating...';

    try {
        const response = await fetch(`${API_URL}/api/cart/${cartId}/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-Id': currentUser.user_id
            },
            body: JSON.stringify({ prompt, model })
        });    

        const data = await response.json();    

        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            cartData.versions.unshift({
                version_number: data.version_number,
                content: data.content,
                created_at: new Date().toISOString()
            });    

            currentVersion = data.version_number;

            const versionSelect = document.getElementById('version-select');
            const option = document.createElement('option');
            option.value = data.version_number;
            option.textContent = `v${data.version_number}`;
            versionSelect.insertBefore(option, versionSelect.firstChild);
            versionSelect.value = currentVersion;

            loadVersion(currentVersion);
            updateHistory();

            document.getElementById('editor-tokens').textContent = `${data.tokens_remaining} tokens`;
            document.getElementById('prompt').value = '';
        }
    } catch (error) {
        alert('Generation failed: ' + error.message);
    }    

    document.getElementById('generate-btn').disabled = false;
    document.getElementById('generate-btn').textContent = 'Generate';
};

document.getElementById('back-home').onclick = () => {
    window.location.href = 'index.html';
};

loadUser();
loadCart();