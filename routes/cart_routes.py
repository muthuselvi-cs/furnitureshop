from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from models.database import fetch_all, fetch_one, execute_query
from datetime import datetime, timedelta

cart_bp = Blueprint('cart_routes', __name__)

def check_user_login():
    if 'user_id' not in session:
        return False
    return True

@cart_bp.route('/cart')
def cart():
    if not check_user_login():
        return redirect(url_for('auth_routes.login'))
        
    user_id = session['user_id']
    
    sql = """SELECT c.*, p.name, p.price, p.image 
             FROM cart c 
             JOIN products p ON c.product_id = p.id 
             WHERE c.user_id = %s"""
    cart_items = fetch_all(sql, (user_id,))
    
    total = sum([item['price'] * item['quantity'] for item in cart_items])
        
    return render_template('cart.html', cart_items=cart_items, total=total)

@cart_bp.route('/cart_actions', methods=['POST', 'GET'])
def cart_action():
    if not check_user_login():
        return redirect(url_for('auth_routes.login'))
        
    user_id = session['user_id']
    action = request.form.get('action') or request.args.get('action', '')
    
    if action == 'add':
        product_id = request.form.get('product_id')
        quantity = int(request.form.get('quantity', 1))
        
        existing = fetch_one("SELECT * FROM cart WHERE user_id = %s AND product_id = %s", (user_id, product_id))
        
        if existing:
            new_qty = existing['quantity'] + quantity
            execute_query("UPDATE cart SET quantity = %s WHERE id = %s", (new_qty, existing['id']))
        else:
            execute_query("INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, %s)", (user_id, product_id, quantity))
            
        if request.form.get('buy_now'):
            return redirect(url_for('cart_routes.checkout'))
            
        return redirect(url_for('cart_routes.cart'))
        
    elif action == 'update':
        cart_id = request.form.get('cart_id')
        quantity = int(request.form.get('quantity', 1))
        
        if quantity > 0:
            execute_query("UPDATE cart SET quantity = %s WHERE id = %s AND user_id = %s", (quantity, cart_id, user_id))
        return redirect(url_for('cart_routes.cart'))
        
    elif action == 'remove':
        cart_id = request.args.get('id')
        execute_query("DELETE FROM cart WHERE id = %s AND user_id = %s", (cart_id, user_id))
        return redirect(url_for('cart_routes.cart'))
        
    return redirect(url_for('store_routes.index'))

@cart_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if not check_user_login():
        return redirect(url_for('auth_routes.login'))
        
    user_id = session['user_id']
    
    sql = """SELECT c.*, p.price, p.name, p.stock, p.image 
             FROM cart c 
             JOIN products p ON c.product_id = p.id 
             WHERE c.user_id = %s"""
    cart_items = fetch_all(sql, (user_id,))
    
    if not cart_items:
        return redirect(url_for('cart_routes.cart'))
        
    total_amount = sum([item['price'] * item['quantity'] for item in cart_items])
    razorpay_key = 'rzp_test_YourKeyHere'
    
    error_msg = None
    
    show_razorpay = 'razorpay' in request.args and 'order_id' in request.args
    rp_order_id = request.args.get('order_id', '')
    rp_amount = request.args.get('amount', 0)
    
    if request.method == 'POST' and not show_razorpay:
        address = request.form.get('address')
        payment_method = request.form.get('payment_method')
        
        try:
            for item in cart_items:
                stock_info = fetch_one("SELECT stock FROM products WHERE id = %s", (item['product_id'],))
                if stock_info['stock'] < item['quantity']:
                    raise Exception(f"Sorry, only {stock_info['stock']} units of '{item['name']}' are available.")
            
            try:
                # Add estimated_delivery column if it exists in schema, wait DB schema didn't have estimated_delivery in order!
                # Ah database.sql for orders: id, user_id, total_amount, address, order_date, payment_status, delivery_status_id
                # So we won't insert estimated_delivery since it's not in the base SQL schema
                order_id = execute_query(
                    "INSERT INTO orders (user_id, total_amount, address, payment_status, delivery_status_id) VALUES (%s, %s, %s, 'Pending', 1)",
                    (user_id, total_amount, address)
                )
            except Exception as e:
                # If the DB has estimated_delivery from some migration, try again with it
                estimated_delivery = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
                order_id = execute_query(
                    "INSERT INTO orders (user_id, total_amount, address, payment_status, delivery_status_id, estimated_delivery) VALUES (%s, %s, %s, 'Pending', 1, %s)",
                    (user_id, total_amount, address, estimated_delivery)
                )

            for item in cart_items:
                execute_query("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (%s, %s, %s, %s)",
                             (order_id, item['product_id'], item['quantity'], item['price']))
                execute_query("UPDATE products SET stock = stock - %s WHERE id = %s", (item['quantity'], item['product_id']))
                
            execute_query("INSERT INTO payments (order_id, payment_method, payment_status) VALUES (%s, %s, 'Pending')", 
                         (order_id, payment_method))
            execute_query("DELETE FROM cart WHERE user_id = %s", (user_id,))
            
            if payment_method == 'Razorpay':
                session['pending_order_id'] = order_id
                session['pending_order_amount'] = float(total_amount)
                return redirect(url_for('cart_routes.checkout', razorpay=1, order_id=order_id, amount=int(total_amount*100)))
            else:
                execute_query("UPDATE orders SET payment_status='Paid', delivery_status_id=1 WHERE id=%s", (order_id,))
                execute_query("UPDATE payments SET payment_status='Paid' WHERE order_id=%s", (order_id,))
                return redirect(url_for('cart_routes.order_success', id=order_id))
                
        except Exception as e:
            error_msg = str(e)
            
    user_data = fetch_one("SELECT address, name FROM users WHERE id = %s", (user_id,))
    
    return render_template('checkout.html', 
                           cart_items=cart_items, 
                           total_amount=total_amount, 
                           user_data=user_data, 
                           error_msg=error_msg,
                           show_razorpay=show_razorpay,
                           rp_order_id=rp_order_id,
                           rp_amount=rp_amount,
                           razorpay_key=razorpay_key)

@cart_bp.route('/razorpay_verify', methods=['POST'])
def razorpay_verify():
    db_order_id = request.form.get('db_order_id')
    execute_query("UPDATE orders SET payment_status='Paid', delivery_status_id=1 WHERE id=%s", (db_order_id,))
    execute_query("UPDATE payments SET payment_status='Paid' WHERE order_id=%s", (db_order_id,))
    return redirect(url_for('cart_routes.order_success', id=db_order_id))

@cart_bp.route('/order_success')
def order_success():
    if not check_user_login():
        return redirect(url_for('auth_routes.login'))
        
    order_id = request.args.get('id', 0)
    user_id = session['user_id']
    
    order = fetch_one("""SELECT o.*, d.status_name, u.name as user_name, u.email 
                         FROM orders o 
                         JOIN delivery_status d ON o.delivery_status_id = d.id 
                         JOIN users u ON o.user_id = u.id
                         WHERE o.id = %s AND o.user_id = %s""", (order_id, user_id))
                         
    if not order:
        return redirect(url_for('store_routes.my_account'))
        
    order_items = fetch_all("SELECT oi.*, p.name as product_name FROM order_items oi JOIN products p ON oi.product_id = p.id WHERE oi.order_id = %s", (order_id,))
    
    return render_template('order_success.html', order=order, order_items=order_items)

@cart_bp.route('/cancel_order/<int:id>', methods=['POST'])
def cancel_order(id):
    if not check_user_login():
        return redirect(url_for('auth_routes.login'))
    
    user_id = session['user_id']
    order = fetch_one("SELECT * FROM orders WHERE id = %s AND user_id = %s", (id, user_id))
    
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for('store_routes.my_account'))
    
    # Only allow cancellation if status is 'Pending' (ID: 1)
    if order['delivery_status_id'] != 1:
        flash("Only pending orders can be cancelled.", "warning")
        return redirect(url_for('store_routes.my_account'))
    
    try:
        # Update order status to 'Cancelled' (ID: 5)
        execute_query("UPDATE orders SET delivery_status_id = 5 WHERE id = %s", (id,))
        
        # Restore product stock
        items = fetch_all("SELECT product_id, quantity FROM order_items WHERE order_id = %s", (id,))
        for item in items:
            execute_query("UPDATE products SET stock = stock + %s WHERE id = %s", (item['quantity'], item['product_id']))
            
        flash("Your order has been cancelled successfully and stock has been restored.", "success")
    except Exception as e:
        flash(f"An error occurred during cancellation: {str(e)}", "danger")
        
    return redirect(url_for('store_routes.my_account'))

