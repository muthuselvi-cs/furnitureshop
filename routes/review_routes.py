from flask import Blueprint, request, session, redirect, url_for, flash
from models.database import execute_query, fetch_one

review_bp = Blueprint('review_routes', __name__)

@review_bp.route('/submit_review', methods=['POST'])
def submit_review():
    if 'user_id' not in session:
        flash("Please login to post a review.", "danger")
        return redirect(url_for('auth_routes.login'))
        
    user_id = session['user_id']
    product_id = request.form.get('product_id')
    rating = request.form.get('rating')
    comment = request.form.get('comment', '').strip()
    
    if not rating or not product_id:
        flash("Rating and Product ID are required.", "warning")
        return redirect(request.referrer or url_for('store_routes.index'))

    try:
        # 1. Check if user already reviewed
        existing = fetch_one("SELECT id FROM reviews WHERE user_id = %s AND product_id = %s", (user_id, product_id))
        if existing:
            flash("You have already reviewed this product.", "info")
            return redirect(request.referrer or url_for('store_routes.product', id=product_id))
            
        # 2. Check if user actually purchased and received the product (Status: Delivered = 4)
        has_purchased = fetch_one("""
            SELECT o.id 
            FROM orders o 
            JOIN order_items oi ON o.id = oi.order_id 
            WHERE o.user_id = %s AND oi.product_id = %s AND o.delivery_status_id = 4
            LIMIT 1
        """, (user_id, product_id))

        if not has_purchased:
            flash("You can only review products that have been delivered to you.", "danger")
            return redirect(request.referrer or url_for('store_routes.my_account'))

        # 3. Insert review
        execute_query("INSERT INTO reviews (user_id, product_id, rating, comment) VALUES (%s, %s, %s, %s)", 
                     (user_id, product_id, rating, comment))
        
        flash("Thank you for your verified review!", "success")
        
    except Exception as e:
        flash(f"Error submitting review: {str(e)}", "danger")
        
    return redirect(request.referrer or url_for('store_routes.product', id=product_id))

