const API_URL = window.location.origin;

async function loadContent() {
    const params = new URLSearchParams(window.location.search);
    const cartId = params.get('cart');
    const versionParam = params.get('version');
    
    if (!cartId) {
        document.getElementById('content').innerHTML = '<h1>No cart specified</h1>';
        return;
    }
    
    const response = await fetch(`${API_URL}/api/cart/${cartId}`);
    const data = await response.json();
    
    if (data.error) {
        document.getElementById('content').innerHTML = '<h1>Cart not found</h1>';
        return;
    }
    
    let version;
    if (versionParam) {
        version = data.versions.find(v => v.version_number === parseInt(versionParam));
    } else if (data.cart.pinned_version) {
        version = data.versions.find(v => v.version_number === data.cart.pinned_version);
    } else {
        version = data.versions[0];
    }
    
    if (version) {
        document.getElementById('content').innerHTML = version.content;
    }
}

loadContent();

