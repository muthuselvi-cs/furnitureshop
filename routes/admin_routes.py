from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from models.database import fetch_all, fetch_one, execute_query
import os
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin_routes', __name__, url_prefix='/admin')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = 'static/uploads'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def handle_image_upload(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Ensure unique filename if possible or just use original secure name
        path = os.path.join(UPLOAD_FOLDER, filename).replace('\\', '/')
        file.save(path)
        return f"uploads/{filename}"
    return None

@admin_bp.before_request
def check_admin_login():
    if request.endpoint != 'admin_routes.login' and 'admin_id' not in session:
        if not request.path.startswith('/admin/login'):
             return redirect(url_for('auth_routes.admin_login'))

@admin_bp.route('/')
def index():
    return redirect(url_for('admin_routes.dashboard'))

@admin_bp.route('/dashboard')
def dashboard():
    stats = {
        'total_users': fetch_one("SELECT COUNT(*) as count FROM users")['count'],
        'total_products': fetch_one("SELECT COUNT(*) as count FROM products")['count'],
        'total_orders': fetch_one("SELECT COUNT(*) as count FROM orders")['count'],
        'pending_orders': fetch_one("SELECT COUNT(*) as count FROM orders WHERE delivery_status_id = 1")['count'],
        'total_revenue': fetch_one("SELECT SUM(total_amount) as total FROM orders WHERE payment_status = 'Paid'")['total'] or 0,
    }
    
    recent_orders = fetch_all("""
        SELECT o.*, u.name as user_name 
        FROM orders o 
        JOIN users u ON o.user_id = u.id 
        ORDER BY o.order_date DESC 
        LIMIT 5
    """)
    
    low_stock_products = fetch_all("""
        SELECT id, name, stock 
        FROM products 
        WHERE stock < 10 
        ORDER BY stock ASC 
        LIMIT 5
    """)
    
    recent_reviews = fetch_all("""
        SELECT r.*, p.name as product_name, u.name as user_name 
        FROM reviews r 
        JOIN products p ON r.product_id = p.id 
        JOIN users u ON r.user_id = u.id 
        ORDER BY r.created_at DESC 
        LIMIT 5
    """)

    return render_template('admin/dashboard.html', 
                          stats=stats, 
                          recent_orders=recent_orders,
                          low_stock=low_stock_products,
                          recent_reviews=recent_reviews)


@admin_bp.route('/products')
def products():
    products = fetch_all("SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id = c.id")
    return render_template('admin/products.html', products=products)

@admin_bp.route('/products/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        category_id = request.form.get('category_id')
        price = request.form.get('price')
        stock = request.form.get('stock')
        description = request.form.get('description')
        
        # Handle File Upload
        image_path = "images/placeholder.png"
        if 'image_file' in request.files:
            file = request.files['image_file']
            uploaded_path = handle_image_upload(file)
            if uploaded_path:
                image_path = uploaded_path
        
        execute_query("INSERT INTO products (name, category_id, price, stock, description, image) VALUES (%s, %s, %s, %s, %s, %s)",
                     (name, category_id, price, stock, description, image_path))
        flash("Product added successfully!", "success")
        return redirect(url_for('admin_routes.products'))
        
    categories = fetch_all("SELECT * FROM categories")
    return render_template('admin/product_form.html', product=None, categories=categories)

@admin_bp.route('/products/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if request.method == 'POST':
        name = request.form.get('name')
        category_id = request.form.get('category_id')
        price = request.form.get('price')
        stock = request.form.get('stock')
        description = request.form.get('description')
        
        # Handle File Upload
        image_path = request.form.get('existing_image')
        if 'image_file' in request.files:
            file = request.files['image_file']
            uploaded_path = handle_image_upload(file)
            if uploaded_path:
                image_path = uploaded_path
        
        execute_query("UPDATE products SET name=%s, category_id=%s, price=%s, stock=%s, description=%s, image=%s WHERE id=%s",
                     (name, category_id, price, stock, description, image_path, id))
        flash("Product updated successfully!", "success")
        return redirect(url_for('admin_routes.products'))
        
    product = fetch_one("SELECT * FROM products WHERE id = %s", (id,))
    categories = fetch_all("SELECT * FROM categories")
    return render_template('admin/product_form.html', product=product, categories=categories)

@admin_bp.route('/products/delete/<int:id>', methods=['POST'])
def delete_product(id):
    execute_query("DELETE FROM products WHERE id = %s", (id,))
    flash("Product deleted successfully!", "success")
    return redirect(url_for('admin_routes.products'))

@admin_bp.route('/categories')
def categories():
    categories = fetch_all("SELECT * FROM categories")
    return render_template('admin/categories.html', categories=categories)

@admin_bp.route('/categories/add', methods=['POST'])
def add_category():
    name = request.form.get('name')
    if name:
        execute_query("INSERT INTO categories (name) VALUES (%s)", (name,))
        flash("Category added successfully!", "success")
    else:
        flash("Category name is required.", "danger")
    return redirect(url_for('admin_routes.categories'))

@admin_bp.route('/categories/edit/<int:id>', methods=['POST'])
def edit_category(id):
    name = request.form.get('name')
    if name:
        execute_query("UPDATE categories SET name = %s WHERE id = %s", (name, id))
        flash("Category updated successfully!", "success")
    return redirect(url_for('admin_routes.categories'))

@admin_bp.route('/categories/delete/<int:id>', methods=['POST'])
def delete_category(id):
    try:
        execute_query("DELETE FROM categories WHERE id = %s", (id,))
        flash("Category deleted successfully!", "success")
    except Exception as e:
        flash("Cannot delete category. It may be linked to existing products.", "danger")
    return redirect(url_for('admin_routes.categories'))

@admin_bp.route('/orders')
def orders():
    orders = fetch_all("SELECT o.*, u.name as user_name, d.status_name FROM orders o JOIN users u ON o.user_id = u.id JOIN delivery_status d ON o.delivery_status_id = d.id ORDER BY o.order_date DESC")
    return render_template('admin/orders.html', orders=orders)

@admin_bp.route('/orders/view/<int:id>')
def view_order(id):
    order = fetch_one("""SELECT o.*, u.name as user_name, u.email, d.status_name 
                         FROM orders o 
                         JOIN users u ON o.user_id = u.id 
                         JOIN delivery_status d ON o.delivery_status_id = d.id 
                         WHERE o.id = %s""", (id,))
    
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for('admin_routes.orders'))
        
    order_items = fetch_all("""SELECT oi.*, p.name as product_name, p.image 
                               FROM order_items oi 
                               JOIN products p ON oi.product_id = p.id 
                               WHERE oi.order_id = %s""", (id,))
                               
    statuses = fetch_all("SELECT * FROM delivery_status")
    
    return render_template('admin/order_details.html', order=order, items=order_items, statuses=statuses)

@admin_bp.route('/orders/update_status/<int:id>', methods=['POST'])
def update_order_status(id):
    status_id = request.form.get('status_id')
    if status_id:
        execute_query("UPDATE orders SET delivery_status_id = %s WHERE id = %s", (status_id, id))
        flash("Order status updated successfully!", "success")
    return redirect(url_for('admin_routes.view_order', id=id))

@admin_bp.route('/users')
def users():
    users = fetch_all("SELECT * FROM users")
    return render_template('admin/users.html', users=users)

@admin_bp.route('/sales_report')
def sales_report():
    # Daily revenue (last 30 days)
    sales_data = fetch_all("""SELECT DATE(order_date) as date, SUM(total_amount) as total 
                              FROM orders 
                              WHERE payment_status = 'Paid' 
                              GROUP BY DATE(order_date) 
                              ORDER BY date DESC LIMIT 30""")
    
    # Total Revenue (Paid)
    summary = {
        'total_revenue': fetch_one("SELECT SUM(total_amount) as total FROM orders WHERE payment_status = 'Paid'")['total'] or 0,
        'total_orders': fetch_one("SELECT COUNT(*) as count FROM orders WHERE payment_status = 'Paid'")['count'],
        'best_seller': fetch_one("""SELECT p.name FROM products p 
                                    JOIN order_items oi ON p.id = oi.product_id 
                                    GROUP BY p.id ORDER BY SUM(oi.quantity) DESC LIMIT 1"""),
        'top_category': fetch_one("""SELECT c.name FROM categories c 
                                     JOIN products p ON c.id = p.category_id 
                                     JOIN order_items oi ON p.id = oi.product_id 
                                     GROUP BY c.id ORDER BY SUM(oi.quantity) DESC LIMIT 1""")
    }
    
    return render_template('admin/sales_report.html', sales_data=sales_data, summary=summary)
