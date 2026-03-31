from flask import Flask, render_template, session
from routes.auth_routes import auth_bp
from routes.store_routes import store_bp
from routes.cart_routes import cart_bp
from routes.admin_routes import admin_bp
from routes.review_routes import review_bp
from models.database import fetch_one

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_furniture_shop'

# Context Processor for global variables
@app.context_processor
def inject_globals():
    cart_count = 0
    if 'user_id' in session:
        # Get total quantity of items in cart
        row = fetch_one("SELECT SUM(quantity) as total FROM cart WHERE user_id = %s", (session.get('user_id'),))
        if row and row['total']:
            cart_count = int(row['total'])
    return dict(cart_count=cart_count)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(store_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(review_bp)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True, port=5001)
