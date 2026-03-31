from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from models.database import fetch_one, execute_query
from werkzeug.security import generate_password_hash, check_password_hash
import bcrypt

auth_bp = Blueprint('auth_routes', __name__)

def verify_password(hash_from_db, password):
    if hash_from_db.startswith(('$2y$', '$2b$')):
        # bcrypt library requires bytes and handles $2b$ (normalize $2y$ to $2b$)
        normalized_hash = hash_from_db.replace('$2y$', '$2b$', 1)
        return bcrypt.checkpw(password.encode('utf-8'), normalized_hash.encode('utf-8'))
    return check_password_hash(hash_from_db, password)

def hash_password(password):
    return generate_password_hash(password)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('store_routes.index'))
    
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        
        user = fetch_one("SELECT * FROM users WHERE email = %s", (email,))
        
        if user and verify_password(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('store_routes.index'))
        else:
            error = "Invalid email or password."
            
    return render_template('login.html', error=error)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('store_routes.index'))
        
    error = None
    if request.method == 'POST':
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        phone = request.form.get('phone', '')
        
        if not name or not email or not password:
            error = "Please fill all required fields."
        else:
            existing = fetch_one("SELECT id FROM users WHERE email = %s", (email,))
            if existing:
                error = "Email already registered."
            else:
                hashed_pw = hash_password(password)
                user_id = execute_query("INSERT INTO users (name, email, password, phone) VALUES (%s, %s, %s, %s)", (name, email, hashed_pw, phone))
                if user_id:
                    session['user_id'] = user_id
                    session['user_name'] = name
                    return redirect(url_for('store_routes.index'))
                else:
                    error = "Registration failed."
                    
    return render_template('register.html', error=error)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('store_routes.index'))

@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin_routes.dashboard'))
        
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        
        if not email or not password:
            error = "Please fill all fields."
        else:
            admin = fetch_one("SELECT * FROM admin WHERE email = %s", (email,))
            if admin and verify_password(admin['password'], password):
                session['admin_id'] = admin['id']
                session['admin_name'] = admin['name']
                return redirect(url_for('admin_routes.dashboard'))
            else:
                error = "Invalid email or password."
                
    return render_template('admin/index.html', error=error)
