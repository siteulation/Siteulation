from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
import google.generativeai as genai
import os
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='.')
CORS(app)

# Environment variables - validate they exist
DATABASE_URL = os.getenv('DATABASE_URL')
DATABASE_KEY = os.getenv('DATABASE_KEY')
GEMINI_API_KEY = os.getenv('APIKEY')

# Validate required environment variables
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")
if not DATABASE_KEY:
    raise ValueError("DATABASE_KEY environment variable is required")
if not GEMINI_API_KEY:
    raise ValueError("APIKEY environment variable is required")

print(f"Initializing with DATABASE_URL: {DATABASE_URL[:30]}...")  # Print first 30 chars for debugging

# Initialize Supabase client
try:
    supabase: Client = create_client(DATABASE_URL, DATABASE_KEY)
    print("Supabase client initialized successfully")
except Exception as e:
    print(f"Failed to initialize Supabase client: {e}")
    raise

genai.configure(api_key=GEMINI_API_KEY)

# Initialize database tables
def init_tables():
    try:
        # Check if tables exist, if not they should be created via Supabase dashboard
        # We'll just verify we can connect
        supabase.table('users').select('id').limit(1).execute()
        print("Database tables verified")
    except Exception as e:
        print(f"Warning: Could not verify tables - {e}")
        print("Please ensure the following tables exist in your Supabase database:")
        print("- users (id uuid, email text, tokens int, last_token_refill timestamp)")
        print("- carts (id uuid, owner_id uuid, name text, created_at timestamp, pinned_version int)")
        print("- versions (id uuid, cart_id uuid, version_number int, content text, created_at timestamp)")

init_tables()

@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'database_url_set': bool(DATABASE_URL),
        'database_key_set': bool(DATABASE_KEY),
        'gemini_key_set': bool(GEMINI_API_KEY)
    })

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        user_id = response.user.id
        user_data = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if not user_data.data:
            supabase.table('users').insert({
                'id': user_id,
                'email': email,
                'tokens': 16,
                'last_token_refill': datetime.now().isoformat()
            }).execute()
            tokens = 16
        else:
            tokens = user_data.data[0]['tokens']
            last_refill = datetime.fromisoformat(user_data.data[0]['last_token_refill'])
            
            if datetime.now() - last_refill >= timedelta(days=1):
                tokens += 16
                supabase.table('users').update({
                    'tokens': tokens,
                    'last_token_refill': datetime.now().isoformat()
                }).eq('id', user_id).execute()
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'email': email,
            'tokens': tokens,
            'access_token': response.session.access_token
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        
        user_id = response.user.id
        supabase.table('users').insert({
            'id': user_id,
            'email': email,
            'tokens': 16,
            'last_token_refill': datetime.now().isoformat()
        }).execute()
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'email': email,
            'tokens': 16,
            'access_token': response.session.access_token
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/user/tokens', methods=['GET'])
def get_tokens():
    user_id = request.headers.get('X-User-Id')
    
    user_data = supabase.table('users').select('*').eq('id', user_id).execute()
    if not user_data.data:
        return jsonify({'error': 'User not found'}), 404
    
    tokens = user_data.data[0]['tokens']
    last_refill = datetime.fromisoformat(user_data.data[0]['last_token_refill'])
    
    if datetime.now() - last_refill >= timedelta(days=1):
        tokens += 16
        supabase.table('users').update({
            'tokens': tokens,
            'last_token_refill': datetime.now().isoformat()
        }).eq('id', user_id).execute()
    
    return jsonify({'tokens': tokens})

@app.route('/api/carts/recent', methods=['GET'])
def get_recent_carts():
    carts = supabase.table('carts').select('*, users(email)').order('created_at', desc=True).limit(20).execute()
    return jsonify(carts.data)

@app.route('/api/cart/<cart_id>', methods=['GET'])
def get_cart(cart_id):
    cart = supabase.table('carts').select('*').eq('id', cart_id).execute()
    if not cart.data:
        return jsonify({'error': 'Cart not found'}), 404
    
    versions = supabase.table('versions').select('*').eq('cart_id', cart_id).order('version_number', desc=True).execute()
    
    return jsonify({
        'cart': cart.data[0],
        'versions': versions.data
    })

@app.route('/api/cart/create', methods=['POST'])
def create_cart():
    data = request.json
    user_id = request.headers.get('X-User-Id')
    
    cart = supabase.table('carts').insert({
        'owner_id': user_id,
        'name': data.get('name', 'Untitled'),
        'created_at': datetime.now().isoformat(),
        'pinned_version': None
    }).execute()
    
    cart_id = cart.data[0]['id']
    
    supabase.table('versions').insert({
        'cart_id': cart_id,
        'version_number': 1,
        'content': data.get('content', '<!DOCTYPE html><html><body><h1>New Site</h1></body></html>'),
        'created_at': datetime.now().isoformat()
    }).execute()
    
    return jsonify({'cart_id': cart_id})

@app.route('/api/cart/<cart_id>/remix', methods=['POST'])
def remix_cart(cart_id):
    user_id = request.headers.get('X-User-Id')
    
    original_cart = supabase.table('carts').select('*').eq('id', cart_id).execute()
    if not original_cart.data:
        return jsonify({'error': 'Cart not found'}), 404
    
    original_version = supabase.table('versions').select('*').eq('cart_id', cart_id).order('version_number', desc=True).limit(1).execute()
    
    new_cart = supabase.table('carts').insert({
        'owner_id': user_id,
        'name': f"{original_cart.data[0]['name']} (Remix)",
        'created_at': datetime.now().isoformat(),
        'pinned_version': None
    }).execute()
    
    new_cart_id = new_cart.data[0]['id']
    
    supabase.table('versions').insert({
        'cart_id': new_cart_id,
        'version_number': 1,
        'content': original_version.data[0]['content'],
        'created_at': datetime.now().isoformat()
    }).execute()
    
    return jsonify({'cart_id': new_cart_id})

@app.route('/api/cart/<cart_id>/generate', methods=['POST'])
def generate_version(cart_id):
    data = request.json
    user_id = request.headers.get('X-User-Id')
    prompt = data.get('prompt')
    model_type = data.get('model', 'flash')
    
    cart = supabase.table('carts').select('*').eq('id', cart_id).execute()
    if not cart.data:
        return jsonify({'error': 'Cart not found'}), 404
    
    if cart.data[0]['owner_id'] != user_id:
        return jsonify({'error': 'Not authorized'}), 403
    
    token_cost = 2 if model_type == 'flash' else 4
    user_data = supabase.table('users').select('*').eq('id', user_id).execute()
    
    if user_data.data[0]['tokens'] < token_cost:
        return jsonify({'error': 'Insufficient tokens'}), 400
    
    versions = supabase.table('versions').select('*').eq('cart_id', cart_id).order('version_number', desc=True).limit(10).execute()
    
    context = "\n\n---VERSION HISTORY---\n\n"
    for v in reversed(versions.data):
        context += f"Version {v['version_number']}:\n{v['content']}\n\n"
    
    model_name = 'gemini-2.0-flash-exp' if model_type == 'flash' else 'gemini-1.5-pro'
    model = genai.GenerativeModel(model_name)
    
    full_prompt = f"{context}\n\n---USER REQUEST---\n{prompt}\n\nGenerate the complete HTML for the next version:"
    
    response = model.generate_content(full_prompt)
    new_content = response.text
    
    if '```html' in new_content:
        new_content = new_content.split('```html')[1].split('```')[0].strip()
    elif '```' in new_content:
        new_content = new_content.split('```')[1].split('```')[0].strip()
    
    new_version_number = versions.data[0]['version_number'] + 1 if versions.data else 1
    
    supabase.table('versions').insert({
        'cart_id': cart_id,
        'version_number': new_version_number,
        'content': new_content,
        'created_at': datetime.now().isoformat()
    }).execute()
    
    new_tokens = user_data.data[0]['tokens'] - token_cost
    supabase.table('users').update({'tokens': new_tokens}).eq('id', user_id).execute()
    
    return jsonify({
        'success': True,
        'version_number': new_version_number,
        'content': new_content,
        'tokens_remaining': new_tokens
    })

@app.route('/api/cart/<cart_id>/pin/<int:version_number>', methods=['POST'])
def pin_version(cart_id, version_number):
    user_id = request.headers.get('X-User-Id')
    
    cart = supabase.table('carts').select('*').eq('id', cart_id).execute()
    if not cart.data or cart.data[0]['owner_id'] != user_id:
        return jsonify({'error': 'Not authorized'}), 403
    
    supabase.table('carts').update({'pinned_version': version_number}).eq('id', cart_id).execute()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
