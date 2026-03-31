from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from models.database import fetch_all, fetch_one, execute_query

store_bp = Blueprint('store_routes', __name__)

@store_bp.route('/')
def index():
    categories = fetch_all("SELECT * FROM categories LIMIT 6")
    for cat in categories:
        imgs = fetch_all("SELECT image_path FROM category_images WHERE category_id = %s", (cat['id'],))
        cat['category_images'] = imgs
    
    user_id = session.get('user_id')
    # Fetch top products with rating and wishlist status
    sql = """
        SELECT p.*, 
               (SELECT 1 FROM wishlist WHERE user_id = %s AND product_id = p.id) as is_wishlist,
               (SELECT AVG(rating) FROM reviews WHERE product_id = p.id) as avg_rating,
               (SELECT COUNT(id) FROM reviews WHERE product_id = p.id) as review_count
        FROM products p 
        ORDER BY p.created_at DESC 
        LIMIT 8
    """
    products = fetch_all(sql, (user_id,))
    return render_template('index.html', categories=categories, products=products)

@store_bp.route('/shop')
def shop():
    category_id = request.args.get('category', '')
    search = request.args.get('search', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    availability = request.args.get('availability', 'all')
    sort = request.args.get('sort', 'newest')
    user_id = session.get('user_id')

    # Base SQL with rating aggregation
    sql_base = """
        SELECT p.*, c.name as cat_name,
               (SELECT AVG(rating) FROM reviews WHERE product_id = p.id) as avg_rating,
               (SELECT COUNT(id) FROM reviews WHERE product_id = p.id) as review_count
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id 
        WHERE 1=1
    """
    params = []

    if category_id:
        sql_base += " AND p.category_id = %s"
        params.append(category_id)

    if search:
        sql_base += " AND (p.name LIKE %s OR p.description LIKE %s)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")

    if min_price:
        sql_base += " AND p.price >= %s"
        params.append(min_price)
    
    if max_price:
        sql_base += " AND p.price <= %s"
        params.append(max_price)

    if availability == 'in_stock':
        sql_base += " AND p.stock > 0"
    elif availability == 'out_of_stock':
        sql_base += " AND p.stock <= 0"

    # Determine sort order
    sort_sql = "ORDER BY t.id DESC" # Default newest
    if sort == 'price_low':
        sort_sql = "ORDER BY t.price ASC"
    elif sort == 'price_high':
        sort_sql = "ORDER BY t.price DESC"

    # Combine with wishlist check and sorting
    sql = f"""SELECT t.*, (SELECT id FROM wishlist WHERE user_id = %s AND product_id = t.id) as is_wishlist 
              FROM ({sql_base}) t {sort_sql}"""
    
    final_params = [user_id] + params
    products = fetch_all(sql, tuple(final_params))
    categories = fetch_all("SELECT * FROM categories")
    
    return render_template('shop.html', 
                          products=products, 
                          categories=categories, 
                          category_id=category_id, 
                          search_query=search,
                          min_price=min_price,
                          max_price=max_price,
                          availability=availability,
                          sort_by=sort)

@store_bp.route('/product/<int:id>')
def product(id):
    product = fetch_one("""
        SELECT p.*, c.name as cat_name,
               (SELECT AVG(rating) FROM reviews WHERE product_id = p.id) as avg_rating,
               (SELECT COUNT(id) FROM reviews WHERE product_id = p.id) as review_count
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id 
        WHERE p.id = %s
    """, (id,))
    
    if not product:
        return render_template('product.html', product=None)

    # Fetch existing reviews
    reviews = fetch_all("""
        SELECT r.*, u.name as user_name 
        FROM reviews r 
        JOIN users u ON r.user_id = u.id 
        WHERE r.product_id = %s 
        ORDER BY r.created_at DESC
    """, (id,))

    in_stock = product['stock'] > 0
    in_wishlist = False
    has_reviewed = False
    
    user_id = session.get('user_id')
    if user_id:
        wishlist_item = fetch_one("SELECT id FROM wishlist WHERE user_id = %s AND product_id = %s", (user_id, product['id']))
        in_wishlist = bool(wishlist_item)
        
        # Check if user already reviewed
        review_count = fetch_one("SELECT COUNT(id) as count FROM reviews WHERE user_id = %s AND product_id = %s", (user_id, product['id']))
        has_reviewed = review_count['count'] > 0
        
    # Fetch related products (same category, excluding current product)
    related_products = []
    if product:
        related_products = fetch_all("""
            SELECT p.*, 
                   (SELECT AVG(rating) FROM reviews WHERE product_id = p.id) as avg_rating,
                   (SELECT COUNT(id) FROM reviews WHERE product_id = p.id) as review_count
            FROM products p 
            WHERE p.category_id = %s AND p.id != %s 
            LIMIT 4
        """, (product['category_id'], id))

    return render_template('product.html', 
                          product=product, 
                          in_stock=in_stock, 
                          in_wishlist=in_wishlist,
                          reviews=reviews,
                          has_reviewed=has_reviewed,
                          related_products=related_products)

@store_bp.route('/wishlist')
def wishlist():
    if 'user_id' not in session:
        return redirect(url_for('auth_routes.login'))
        
    user_id = session['user_id']
    wishlist_items = fetch_all("""SELECT w.id as wishlist_id, p.*, c.name as cat_name 
                                  FROM wishlist w 
                                  JOIN products p ON w.product_id = p.id 
                                  JOIN categories c ON p.category_id = c.id
                                  WHERE w.user_id = %s 
                                  ORDER BY w.created_at DESC""", (user_id,))
                                  
    return render_template('wishlist.html', wishlist_items=wishlist_items)

@store_bp.route('/wishlist_action', methods=['POST'])
def wishlist_action():
    if 'user_id' not in session:
        return redirect(url_for('auth_routes.login'))
        
    user_id = session['user_id']
    action = request.form.get('action')
    product_id = request.form.get('product_id')
    redirect_url = request.form.get('redirect') or url_for('store_routes.wishlist')
    
    if not product_id:
        return redirect(redirect_url)
        
    try:
        if action == 'add':
            existing = fetch_one("SELECT id FROM wishlist WHERE user_id = %s AND product_id = %s", (user_id, product_id))
            if not existing:
                execute_query("INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)", (user_id, product_id))
            flash("Added to wishlist!", "success")
            
        elif action == 'remove':
            execute_query("DELETE FROM wishlist WHERE user_id = %s AND product_id = %s", (user_id, product_id))
            flash("Removed from wishlist.", "success")
            
        elif action == 'move_to_cart':
            stock_info = fetch_one("SELECT stock FROM products WHERE id = %s", (product_id,))
            if stock_info and stock_info['stock'] < 1:
                flash("This product is out of stock.", "danger")
            else:
                cart_item = fetch_one("SELECT id, quantity FROM cart WHERE user_id = %s AND product_id = %s", (user_id, product_id))
                if cart_item:
                    execute_query("UPDATE cart SET quantity = quantity + 1 WHERE id = %s", (cart_item['id'],))
                else:
                    execute_query("INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, 1)", (user_id, product_id))
                
                execute_query("DELETE FROM wishlist WHERE user_id = %s AND product_id = %s", (user_id, product_id))
                flash("Moved to cart!", "success")
                redirect_url = url_for('cart_routes.cart')
                
    except Exception as e:
        flash(f"Action failed: {str(e)}", "danger")
        
    return redirect(redirect_url)

@store_bp.route('/wishlist/toggle', methods=['POST'])
def wishlist_toggle():
    if 'user_id' not in session:
        return {"status": "error", "message": "Please login first"}, 401
        
    user_id = session['user_id']
    data = request.get_json()
    product_id = data.get('product_id')
    
    if not product_id:
        return {"status": "error", "message": "Product ID required"}, 400
        
    try:
        existing = fetch_one("SELECT id FROM wishlist WHERE user_id = %s AND product_id = %s", (user_id, product_id))
        if existing:
            execute_query("DELETE FROM wishlist WHERE user_id = %s AND product_id = %s", (user_id, product_id))
            return {"status": "success", "action": "removed", "message": "Removed from wishlist"}
        else:
            execute_query("INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)", (user_id, product_id))
            return {"status": "success", "action": "added", "message": "Added to wishlist"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@store_bp.route('/my_account')
def my_account():
    if 'user_id' not in session:
        return redirect(url_for('auth_routes.login'))
        
    user_id = session['user_id']
    
    # Fetch user's orders with delivery status
    orders = fetch_all("""
        SELECT o.*, d.status_name 
        FROM orders o 
        JOIN delivery_status d ON o.delivery_status_id = d.id 
        WHERE o.user_id = %s 
        ORDER BY o.order_date DESC
    """, (user_id,))
    
    # Fetch order items for each order
    for order in orders:
        items = fetch_all("""
            SELECT oi.*, p.name as product_name, p.image,
                   (SELECT id FROM reviews WHERE user_id = %s AND product_id = p.id LIMIT 1) as has_reviewed
            FROM order_items oi 
            JOIN products p ON oi.product_id = p.id 
            WHERE oi.order_id = %s
        """, (user_id, order['id']))
        order['items'] = items
        
    return render_template('my_account.html', orders=orders)


@store_bp.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email', '').strip()
    if not email:
        flash("Invalid email", "danger")
        return redirect(request.referrer or url_for('store_routes.index'))
    
    # Check if already subscribed
    existing = fetch_one("SELECT id FROM newsletter_subscribers WHERE email = %s", (email,))
    if existing:
        flash("Already subscribed", "warning")
    else:
        # Insert new subscriber
        success = execute_query("INSERT INTO newsletter_subscribers (email) VALUES (%s)", (email,))
        if success:
            flash("Subscribed successfully", "success")
        else:
            flash("Database error occurred", "danger")
            
    return redirect(request.referrer or url_for('store_routes.index'))

@store_bp.route('/track_order/<int:id>')
def track_order(id):
    if 'user_id' not in session:
        return redirect(url_for('auth_routes.login'))
        
    user_id = session['user_id']
    order = fetch_one("""
        SELECT o.*, d.status_name, d.id as status_id
        FROM orders o 
        JOIN delivery_status d ON o.delivery_status_id = d.id 
        WHERE o.id = %s AND o.user_id = %s
    """, (id, user_id))
    
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for('store_routes.my_account'))
        
    # Get all status options for the timeline (Pending, Packed, Shipped, Delivered)
    statuses = fetch_all("SELECT * FROM delivery_status WHERE id <= 4 ORDER BY id ASC")
    
    # Progress percentage based on status ID
    progress = 0
    if order['status_id'] == 1: progress = 20    # Pending
    elif order['status_id'] == 2: progress = 50  # Packed
    elif order['status_id'] == 3: progress = 80  # Shipped
    elif order['status_id'] == 4: progress = 100 # Delivered

    return render_template('track_order.html', order=order, statuses=statuses, progress=progress)
