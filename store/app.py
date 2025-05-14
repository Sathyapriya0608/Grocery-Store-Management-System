# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '@Gryffindor_10501',  # Enter your MySQL password here
    'database': 'store'
}

def get_db_connection():
    conn = mysql.connector.connect(**db_config)
    return conn

@app.route('/')
def home():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('signup'))
        
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO users (username, password, email, role) VALUES (%s, %s, %s, 'customer')",
                (username, hashed_password, email)
            )
            conn.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            conn.rollback()
            if err.errno == 1062:  # Duplicate entry
                flash('Username or email already exists', 'danger')
            else:
                flash('Registration failed. Please try again.', 'danger')
        finally:
            cursor.close()
            conn.close()
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Admin routes
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get product count
    cursor.execute("SELECT COUNT(*) as count FROM products")
    product_count = cursor.fetchone()['count']
    
    # Get user count
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'customer'")
    user_count = cursor.fetchone()['count']
    
    # Get order count
    cursor.execute("SELECT COUNT(*) as count FROM orders")
    order_count = cursor.fetchone()['count']
    
    # Get low stock products
    cursor.execute("SELECT * FROM products WHERE stock_quantity < 10 ORDER BY stock_quantity ASC LIMIT 5")
    low_stock = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         product_count=product_count,
                         user_count=user_count,
                         order_count=order_count,
                         low_stock=low_stock)

# Add this route to app.py
@app.route('/admin/orders')
def admin_orders():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all orders with customer details
    cursor.execute("""
        SELECT 
            o.id, 
            o.total_amount, 
            o.status, 
            o.created_at,
            u.username as customer_name,
            u.email as customer_email
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC
    """)
    orders = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin_orders.html', orders=orders)


@app.route('/admin/order/<int:order_id>')
def admin_order_details(order_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Corrected query - removed trailing comma after selected columns
    cursor.execute("""
        SELECT 
            o.*, 
            u.username as customer_name,
            u.email as customer_email
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.id = %s
    """, (order_id,))
    
    order = cursor.fetchone()
    
    # Get order items
    cursor.execute("""
        SELECT 
            p.id as product_id,
            p.name as product_name,
            p.image_url,
            oi.quantity,
            oi.price as unit_price,
            (oi.quantity * oi.price) as total_price
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = %s
    """, (order_id,))
    
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('admin_order_details.html', order=order, items=items)
@app.route('/admin/order/<int:order_id>/update', methods=['POST'])
def update_order_status(order_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    new_status = request.form.get('status')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE orders SET status = %s WHERE id = %s
    """, (new_status, order_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash(f'Order #{order_id} status updated to {new_status}', 'success')
    return redirect(url_for('admin_order_details', order_id=order_id))

@app.route('/admin/products')
def admin_products():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM products ORDER BY created_at DESC")
    products = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin_products.html', products=products)

@app.route('/admin/add_product', methods=['GET', 'POST'])
def add_product():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock_quantity = int(request.form['stock_quantity'])
        category = request.form['category']
        image_url = request.form['image_url'] or None
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """INSERT INTO products 
                (name, description, price, stock_quantity, category, image_url) 
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (name, description, price, stock_quantity, category, image_url)
            )
            conn.commit()
            flash('Product added successfully', 'success')
            return redirect(url_for('admin_products'))
        except mysql.connector.Error as err:
            conn.rollback()
            flash(f'Failed to add product: {err}', 'danger')
        finally:
            cursor.close()
            conn.close()
    
    return render_template('add_product.html')

@app.route('/admin/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock_quantity = int(request.form['stock_quantity'])
        category = request.form['category']
        image_url = request.form['image_url'] or None
        
        try:
            cursor.execute(
                """UPDATE products SET 
                name = %s, description = %s, price = %s, 
                stock_quantity = %s, category = %s, image_url = %s 
                WHERE id = %s""",
                (name, description, price, stock_quantity, category, image_url, product_id)
            )
            conn.commit()
            flash('Product updated successfully', 'success')
            return redirect(url_for('admin_products'))
        except mysql.connector.Error as err:
            conn.rollback()
            flash(f'Failed to update product: {err}', 'danger')
        finally:
            cursor.close()
            conn.close()
    
    cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('admin_products'))
    
    return render_template('edit_product.html', product=product)

@app.route('/admin/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
        flash('Product deleted successfully', 'success')
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f'Failed to delete product: {err}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_products'))

# User routes
@app.route('/user/dashboard')
def user_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get featured products
    cursor.execute("SELECT * FROM products ORDER BY RAND() LIMIT 8")
    featured_products = cursor.fetchall()
    
    # Get categories
    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
    categories = [row['category'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return render_template('user_dashboard.html', 
                         featured_products=featured_products,
                         categories=categories)

@app.route('/user/products')
def user_products():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    search_query = request.args.get('search', '')
    category = request.args.get('category', '')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if search_query:
        query += " AND (name LIKE %s OR description LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])
    
    if category:
        query += " AND category = %s"
        params.append(category)
    
    query += " ORDER BY name"
    
    cursor.execute(query, params)
    products = cursor.fetchall()
    
    # Get categories for filter
    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
    categories = [row['category'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return render_template('user_products.html', 
                         products=products,
                         categories=categories,
                         search_query=search_query,
                         selected_category=category)

@app.route('/user/product/<int:product_id>')
def view_product(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('user_products'))
    
    return render_template('view_product.html', product=product)

@app.route('/user/cart', methods=['GET', 'POST'])
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if 'cart' not in session:
        session['cart'] = {}
    
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        quantity = int(request.form.get('quantity', 1))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id, name, price, stock_quantity FROM products WHERE id = %s", (product_id,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not product:
            flash('Product not found', 'danger')
            return redirect(url_for('user_products'))
        
        if product['stock_quantity'] < quantity:
            flash(f'Only {product["stock_quantity"]} items available in stock', 'warning')
            return redirect(url_for('view_product', product_id=product_id))
        
        cart = session['cart']
        if product_id in cart:
            cart[product_id]['quantity'] += quantity
        else:
            cart[product_id] = {
                'name': product['name'],
                'price': float(product['price']),
                'quantity': quantity
            }
        
        session['cart'] = cart
        flash('Product added to cart', 'success')
        return redirect(url_for('view_product', product_id=product_id))
    
    # Calculate total
    cart = session.get('cart', {})
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    
    return render_template('cart.html', cart=cart, total=total)

@app.route('/user/update_cart', methods=['POST'])
def update_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cart = session.get('cart', {})
    
    for product_id, item in cart.items():
        new_quantity = int(request.form.get(f'quantity_{product_id}', 1))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT stock_quantity FROM products WHERE id = %s", (product_id,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if product and new_quantity <= product['stock_quantity']:
            item['quantity'] = new_quantity
        else:
            flash(f'Not enough stock for {item["name"]}', 'warning')
    
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/user/remove_from_cart/<string:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cart = session.get('cart', {})
    if product_id in cart:
        del cart[product_id]
        session['cart'] = cart
        flash('Item removed from cart', 'success')
    
    return redirect(url_for('cart'))

@app.route('/user/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session or 'cart' not in session or not session['cart']:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Validate form data exists
        required_fields = ['full_name', 'address', 'city', 'state', 'zip_code', 'phone']
        if not all(field in request.form for field in required_fields):
            flash('Please fill all required fields', 'danger')
            return redirect(url_for('checkout'))
        
        try:
            user_id = session['user_id']
            cart = session['cart']
            
            # Get address form data with validation
            full_name = request.form['full_name'].strip()
            address = request.form['address'].strip()
            city = request.form['city'].strip()
            state = request.form['state'].strip()
            zip_code = request.form['zip_code'].strip()
            phone = request.form['phone'].strip()

            # Validate phone and zip code format
            if not phone.isdigit() or len(phone) != 10:
                flash('Please enter a valid 10-digit phone number', 'danger')
                return redirect(url_for('checkout'))
            
            if not zip_code.isdigit() or len(zip_code) not in (5, 6):
                flash('Please enter a valid ZIP code', 'danger')
                return redirect(url_for('checkout'))

            # Calculate total
            total = sum(item['price'] * item['quantity'] for item in cart.values())
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            try:
                # Start transaction
                conn.start_transaction()
                
                # Create order
                cursor.execute(
                    "INSERT INTO orders (user_id, total_amount) VALUES (%s, %s)",
                    (user_id, total)
                )
                order_id = cursor.lastrowid
                
                # Save shipping address
                cursor.execute(
                    """INSERT INTO order_addresses 
                    (order_id, full_name, address, city, state, zip_code, phone)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (order_id, full_name, address, city, state, zip_code, phone)
                )
                
                # Add order items and update inventory
                for product_id, item in cart.items():
                    # Check stock availability with lock
                    cursor.execute(
                        "SELECT stock_quantity FROM products WHERE id = %s FOR UPDATE",
                        (product_id,)
                    )
                    product = cursor.fetchone()
                    
                    if not product or product['stock_quantity'] < item['quantity']:
                        raise ValueError(f"Not enough stock for {item['name']}")
                    
                    # Add order item
                    cursor.execute(
                        """INSERT INTO order_items 
                        (order_id, product_id, quantity, price) 
                        VALUES (%s, %s, %s, %s)""",
                        (order_id, product_id, item['quantity'], item['price'])
                    )
                    
                    # Update product stock
                    cursor.execute(
                        "UPDATE products SET stock_quantity = stock_quantity - %s WHERE id = %s",
                        (item['quantity'], product_id)
                    )
                
                # Commit transaction if all operations succeed
                conn.commit()
                session.pop('cart', None)
                flash('Order placed successfully!', 'success')
                return redirect(url_for('order_confirmation', order_id=order_id))
                
            except ValueError as e:
                conn.rollback()
                flash(str(e), 'danger')
            except mysql.connector.Error as err:
                conn.rollback()
                flash(f'Checkout failed: {err.msg}', 'danger')
            finally:
                cursor.close()
                conn.close()
                
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
        
        return redirect(url_for('checkout'))
    
    # GET request - show checkout form
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('user_dashboard'))
    
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    
    # Check product availability before checkout
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        unavailable_items = []
        for product_id, item in cart.items():
            cursor.execute(
                "SELECT name, stock_quantity FROM products WHERE id = %s",
                (product_id,)
            )
            product = cursor.fetchone()
            if not product or product['stock_quantity'] < item['quantity']:
                unavailable_items.append({
                    'name': product['name'] if product else f"Product ID {product_id}",
                    'available': product['stock_quantity'] if product else 0,
                    'requested': item['quantity']
                })
        
        if unavailable_items:
            flash('Some items in your cart are no longer available', 'danger')
            for item in unavailable_items:
                flash(f"{item['name']} - Available: {item['available']}, Requested: {item['requested']}", 'warning')
            return redirect(url_for('cart'))
            
    except mysql.connector.Error as err:
        flash(f'Could not verify product availability: {err.msg}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return render_template('checkout.html', cart=cart, total=total)

@app.route('/user/order_confirmation/<int:order_id>')
def order_confirmation(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get order details
    cursor.execute("""
        SELECT o.id, o.total_amount, o.created_at, 
               GROUP_CONCAT(p.name SEPARATOR ', ') as products
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.id = %s AND o.user_id = %s
        GROUP BY o.id
    """, (order_id, session['user_id']))
    
    order = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('user_dashboard'))
    
    return render_template('order_confirmation.html', order=order)

@app.route('/user/orders')
def user_orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT o.id, o.total_amount, o.status, o.created_at
        FROM orders o
        WHERE o.user_id = %s
        ORDER BY o.created_at DESC
    """, (session['user_id'],))
    
    orders = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('user_orders.html', orders=orders)

@app.route('/user/order_details/<int:order_id>')
def order_details(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Verify order belongs to user
    cursor.execute("SELECT id FROM orders WHERE id = %s AND user_id = %s", 
                  (order_id, session['user_id']))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        flash('Order not found', 'danger')
        return redirect(url_for('user_orders'))
    
    # Get order items
    cursor.execute("""
        SELECT p.name, oi.quantity, oi.price, (oi.quantity * oi.price) as total
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = %s
    """, (order_id,))
    
    items = cursor.fetchall()
    
    # Get order summary
    cursor.execute("""
        SELECT total_amount, status, created_at
        FROM orders
        WHERE id = %s
    """, (order_id,))
    
    order = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return render_template('order_details.html', items=items, order=order)

if __name__ == '__main__':
    app.run(debug=True)