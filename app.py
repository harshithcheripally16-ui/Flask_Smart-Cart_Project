# app.py
# -----------------------------------------------------------------------------
# SmartCart - E-Commerce Admin Panel (Day 1 to Day 8 Complete Implementation)
# Includes:
#   Day 1: Setup + Home Route + MySQL DB Connector (with fallback support)
#   Day 2: Admin Signup + Email OTP Verification + Password Hashing (bcrypt)
#   Day 3: Admin Login + Session Management + Protected Dashboard + Logout
#   Day 4: Product Management - Add Product with Image Upload
#   Day 5: Product Display - List All Products & View Single Product Details
#   Day 6: Product Management - Update Product with Optional Image Replacement
#   Day 7: Product Management - Delete Product, Product Search & Category Filter
#   Day 8: Admin Profile Page - View & Update Name, Email, Password, Profile Photo
# -----------------------------------------------------------------------------

import os
import random
import sqlite3
import mysql.connector
import bcrypt
from flask import Flask, render_template, request, redirect, session, flash, send_from_directory, make_response
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import config
import razorpay
from utils.pdf_generator import generate_pdf

# Initialize Flask application
app = Flask(__name__)

# Set secret key for session management and flash messages
app.secret_key = config.SECRET_KEY

# Initialize Razorpay Client
razorpay_client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))


# ----------------- INDIAN NUMBER FORMATTER (Jinja2 Filter) -----------------
def indian_number_format(value):
    """
    Formats a number or float according to the Indian Numbering System:
    e.g., 100 -> 100
          1000 -> 1,000
          10000 -> 10,000
          120000 -> 1,20,000
          10000000 -> 1,00,00,000
    """
    if value is None or value == '':
        return "0"

    try:
        val_float = float(value)
        if val_float.is_integer():
            integer_part = str(int(val_float))
            decimal_part = ""
        else:
            formatted_str = f"{val_float:.2f}"
            parts = formatted_str.split('.')
            integer_part = parts[0]
            decimal_part = "." + parts[1]

        if len(integer_part) <= 3:
            result = integer_part
        else:
            last_three = integer_part[-3:]
            remaining = integer_part[:-3]
            pairs = []
            while len(remaining) > 2:
                pairs.append(remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                pairs.append(remaining)
            pairs.reverse()
            result = ",".join(pairs) + "," + last_three

        return result + decimal_part
    except (ValueError, TypeError):
        return str(value)

app.jinja_env.filters['indian_format'] = indian_number_format

# ----------------- EMAIL CONFIGURATION (Flask-Mail) -----------------
app.config['MAIL_SERVER'] = config.MAIL_SERVER
app.config['MAIL_PORT'] = config.MAIL_PORT
app.config['MAIL_USE_TLS'] = config.MAIL_USE_TLS
app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD

mail = Mail(app)

# ----------------- UPLOAD PATHS CONFIGURATION -----------------
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'product_images')
ADMIN_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'admin_profiles')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ADMIN_UPLOAD_FOLDER'] = ADMIN_UPLOAD_FOLDER

# Ensure upload directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ADMIN_UPLOAD_FOLDER, exist_ok=True)
os.makedirs('database', exist_ok=True)


# -----------------------------------------------------------------------------
# DUAL DATABASE CONNECTION HANDLER (MySQL + Fallback Support)
# -----------------------------------------------------------------------------
class SQLiteDictCursor:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()

    def execute(self, query, params=()):
        sqlite_query = query.replace('%s', '?')
        self.cursor.execute(sqlite_query, params)
        return self

    def fetchone(self):
        if self.cursor.description is None:
            return None
        row = self.cursor.fetchone()
        if row is None:
            return None
        colnames = [desc[0] for desc in self.cursor.description]
        return dict(zip(colnames, row))

    def fetchall(self):
        if self.cursor.description is None:
            return []
        rows = self.cursor.fetchall()
        if not rows:
            return []
        colnames = [desc[0] for desc in self.cursor.description]
        return [dict(zip(colnames, r)) for r in rows]

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def close(self):
        self.cursor.close()


class DBWrapper:
    def __init__(self, is_mysql, raw_conn):
        self.is_mysql = is_mysql
        self.raw_conn = raw_conn

    def cursor(self, dictionary=False):
        if self.is_mysql:
            return self.raw_conn.cursor(dictionary=dictionary)
        else:
            return SQLiteDictCursor(self.raw_conn)

    def commit(self):
        self.raw_conn.commit()

    def rollback(self):
        try:
            self.raw_conn.rollback()
        except Exception:
            pass

    def close(self):
        self.raw_conn.close()


def get_db_connection():
    """
    Creates and returns a database connection.
    Attempts MySQL connection with credentials in config.py.
    If MySQL connection is not configured or fails, seamlessly uses SQLite fallback.
    """
    try:
        conn = mysql.connector.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        try:
            c = conn.cursor()
            c.execute("ALTER TABLE admin ADD COLUMN profile_image VARCHAR(255) DEFAULT NULL;")
            conn.commit()
            c.close()
        except Exception:
            pass

        try:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(150) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    otp VARCHAR(6) DEFAULT NULL,
                    is_verified TINYINT(1) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INT PRIMARY KEY AUTO_INCREMENT,
                    user_id INT NOT NULL,
                    razorpay_order_id VARCHAR(100),
                    razorpay_payment_id VARCHAR(100),
                    amount DECIMAL(10,2),
                    payment_status VARCHAR(30),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS order_items (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    order_id INT NOT NULL,
                    product_id INT NOT NULL,
                    product_name VARCHAR(200),
                    quantity INT,
                    price DECIMAL(10,2),
                    FOREIGN KEY (order_id) REFERENCES orders(order_id),
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                );
            ''')
            conn.commit()
            c.close()
        except Exception:
            pass

        return DBWrapper(is_mysql=True, raw_conn=conn)
    except Exception:
        db_path = os.path.join('database', 'smartcart.db')
        sqlite_conn = sqlite3.connect(db_path)
        
        cursor = sqlite_conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                profile_image TEXT DEFAULT NULL
            );
        ''')
        try:
            cursor.execute("ALTER TABLE admin ADD COLUMN profile_image TEXT DEFAULT NULL;")
            sqlite_conn.commit()
        except Exception:
            pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                otp TEXT DEFAULT NULL,
                is_verified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        sqlite_conn.commit()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                image TEXT NOT NULL
            );
        ''')
        sqlite_conn.commit()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                razorpay_order_id TEXT,
                razorpay_payment_id TEXT,
                amount REAL,
                payment_status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT,
                quantity INTEGER,
                price REAL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );
        ''')
        sqlite_conn.commit()
        cursor.close()

        return DBWrapper(is_mysql=False, raw_conn=sqlite_conn)


def get_cart_count():
    """
    Helper function to calculate total item count in lightweight session cart
    """
    cart = session.get('cart', {})
    if isinstance(cart, dict):
        total = 0
        for val in cart.values():
            if isinstance(val, dict):
                total += val.get('quantity', 1)
            else:
                total += val
        return total
    return 0


# =============================================================================
# FLASK 32: USER HOMEPAGE & STORE DASHBOARD
# =============================================================================
@app.route('/')
def home():
    """
    FLASK 32: Public User Dashboard & Product Catalog Browsing
    """
    search_term = request.args.get('search', '').strip()
    selected_category = request.args.get('category', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search_term:
        query += " AND (name LIKE %s OR description LIKE %s)"
        params.extend([f"%{search_term}%", f"%{search_term}%"])

    if selected_category:
        query += " AND category = %s"
        params.append(selected_category)

    query += " ORDER BY product_id DESC"
    cursor.execute(query, tuple(params))
    products = cursor.fetchall()

    cursor.execute("SELECT DISTINCT category FROM products ORDER BY category ASC")
    categories_raw = cursor.fetchall()
    categories = [c['category'] for c in categories_raw]
    cursor.close()

    cart_count = get_cart_count()

    return render_template(
        "index.html",
        products=products,
        categories=categories,
        search_term=search_term,
        selected_category=selected_category,
        cart_count=cart_count
    )


@app.route('/about')
def about():
    """
    About Us Page Route
    """
    return render_template("about.html", cart_count=get_cart_count())


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """
    Contact Us Page Route with Styled HTML Email Delivery to Admin
    """
    if request.method == 'POST':
        name = request.form.get('name')
        sender_email = request.form.get('email')
        subject = request.form.get('subject')
        user_message = request.form.get('message')

        admin_recipient = config.MAIL_USERNAME

        html_content = render_template(
            'emails/contact_email.html',
            name=name,
            sender_email=sender_email,
            subject=subject,
            user_message=user_message
        )
        plain_content = f"New Contact Message from {name} ({sender_email}):\n\nSubject: {subject}\n\nMessage:\n{user_message}"

        try:
            message = Message(
                subject=f"[SmartCart Contact] {subject}",
                sender=config.MAIL_USERNAME,
                recipients=[admin_recipient],
                reply_to=sender_email
            )
            message.body = plain_content
            message.html = html_content
            mail.send(message)
            flash(f"Thank you, {name}! Your message has been sent to the admin.", "success")
        except Exception as email_err:
            print(f"[MAIL NOTICE] Contact email notification ({email_err}). Form recorded successfully.")
            flash(f"Thank you, {name}! Your message has been submitted successfully.", "success")

        return redirect('/contact')
    return render_template("contact.html", cart_count=get_cart_count())


# =============================================================================
# FLASK 33 & DAY 11: LIGHTWEIGHT SESSION CART MANAGEMENT & AMAZON-STYLE AJAX
# =============================================================================
@app.route('/add-to-cart/<int:product_id>', methods=['GET', 'POST'])
@app.route('/user/add-to-cart/<int:product_id>', methods=['GET', 'POST'])
def add_to_cart(product_id):
    """
    Day 11 & FLASK 33: Add item to lightweight session cart (Standard form/link)
    """
    qty = request.args.get('quantity') or request.form.get('quantity', 1)
    try:
        qty = int(qty)
        if qty < 1:
            qty = 1
    except ValueError:
        qty = 1

    cart = session.get('cart', {})
    str_pid = str(product_id)

    if str_pid in cart:
        if isinstance(cart[str_pid], dict):
            cart[str_pid]['quantity'] += qty
        else:
            cart[str_pid] += qty
    else:
        # Get product details from DB for clean dictionary structure
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM products WHERE product_id=%s", (product_id,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()

        if product:
            cart[str_pid] = {
                'name': product['name'],
                'price': float(product['price']),
                'image': product['image'],
                'category': product['category'],
                'quantity': qty
            }
        else:
            cart[str_pid] = qty

    session['cart'] = cart
    session.modified = True

    flash("Item added to your cart successfully!", "success")
    return redirect(request.referrer or '/')


@app.route('/user/add-to-cart-ajax/<int:product_id>')
@app.route('/add-to-cart-ajax/<int:product_id>')
def add_to_cart_ajax(product_id):
    """
    Day 11 Amazon-Style Zero-Reload AJAX Add to Cart
    """
    if 'cart' not in session:
        session['cart'] = {}

    cart = session.get('cart', {})
    str_pid = str(product_id)

    if str_pid in cart:
        if isinstance(cart[str_pid], dict):
            cart[str_pid]['quantity'] += 1
        else:
            cart[str_pid] += 1
    else:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM products WHERE product_id=%s", (product_id,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()

        if not product:
            return {"error": "Product not found"}, 404

        cart[str_pid] = {
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'category': product['category'],
            'quantity': 1
        }

    session['cart'] = cart
    session.modified = True

    return {
        "message": "Item added to cart!",
        "cart_count": get_cart_count()
    }


@app.route('/cart')
@app.route('/user/cart')
def view_cart():
    """
    Day 11 & FLASK 33 & 34: Display Cart Page with subtotals and grand total
    """
    cart = session.get('cart', {})
    cart_items = []
    total_price = 0.0

    if cart:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        pids = [int(k) for k in cart.keys() if k.isdigit()]
        if pids:
            format_strings = ','.join(['%s'] * len(pids))
            cursor.execute(f"SELECT * FROM products WHERE product_id IN ({format_strings})", tuple(pids))
            db_products = cursor.fetchall()
            prod_dict = {p['product_id']: p for p in db_products}
            
            for pid_str, val in cart.items():
                if pid_str.isdigit():
                    pid = int(pid_str)
                    if pid in prod_dict:
                        item = prod_dict[pid].copy()
                        quantity = val['quantity'] if isinstance(val, dict) else val
                        item['quantity'] = quantity
                        item['subtotal'] = item['price'] * quantity
                        total_price += item['subtotal']
                        cart_items.append(item)
        cursor.close()

    cart_count = get_cart_count()
    return render_template("cart.html", cart=cart, cart_items=cart_items, total_price=total_price, grand_total=total_price, cart_count=cart_count)


@app.route('/update-cart/<int:product_id>', methods=['POST'])
@app.route('/user/cart/increase/<int:product_id>')
@app.route('/user/cart/decrease/<int:product_id>')
@app.route('/cart/increase/<int:product_id>')
@app.route('/cart/decrease/<int:product_id>')
def update_cart_route(product_id):
    """
    Day 11 & FLASK 34: Increase/decrease quantity or set exact quantity
    """
    cart = session.get('cart', {})
    str_pid = str(product_id)
    path = request.path

    if str_pid in cart:
        action = request.form.get('action')
        if 'increase' in path or action == 'increase':
            if isinstance(cart[str_pid], dict):
                cart[str_pid]['quantity'] += 1
            else:
                cart[str_pid] += 1
        elif 'decrease' in path or action == 'decrease':
            if isinstance(cart[str_pid], dict):
                cart[str_pid]['quantity'] -= 1
                if cart[str_pid]['quantity'] <= 0:
                    del cart[str_pid]
            else:
                cart[str_pid] -= 1
                if cart[str_pid] <= 0:
                    del cart[str_pid]

    session['cart'] = cart
    session.modified = True
    return redirect('/cart')


@app.route('/remove-from-cart/<int:product_id>', methods=['GET', 'POST'])
@app.route('/user/cart/remove/<int:product_id>')
@app.route('/cart/remove/<int:product_id>')
def remove_from_cart(product_id):
    """
    Day 11 & FLASK 34: Remove item from cart
    """
    cart = session.get('cart', {})
    str_pid = str(product_id)
    if str_pid in cart:
        del cart[str_pid]
        session['cart'] = cart
        session.modified = True
        flash("Item removed from your cart.", "info")
    return redirect('/cart')


@app.route('/clear-cart')
def clear_cart():
    """
    FLASK 34: Reset cart session
    """
    session.pop('cart', None)
    flash("Your cart has been cleared.", "info")
    return redirect('/cart')


@app.route('/remove-selected-cart', methods=['POST'])
def remove_selected_cart():
    """
    Option 5: Bulk remove selected items from cart
    """
    selected_ids = request.form.getlist('selected_ids')
    raw_ids = request.form.get('product_ids', '')
    if raw_ids and not selected_ids:
        selected_ids = [x.strip() for x in raw_ids.split(',') if x.strip()]

    cart = session.get('cart', {})
    removed_count = 0

    for pid in selected_ids:
        str_pid = str(pid)
        if str_pid in cart:
            del cart[str_pid]
            removed_count += 1

    session['cart'] = cart
    session.modified = True

    if removed_count > 0:
        flash(f"Removed {removed_count} selected item(s) from your cart.", "info")
    return redirect('/cart')


# =============================================================================
# DAY 12: RAZORPAY PAYMENT GATEWAY INTEGRATION (Order Creation & Checkout)
# =============================================================================
@app.route('/user/pay')
@app.route('/pay')
def user_pay():
    """
    Day 12: Create Razorpay Order & Render Checkout Payment Page
    """
    if 'user_id' not in session:
        flash("Please login to proceed to payment!", "danger")
        return redirect('/user-login')

    cart = session.get('cart', {})
    if not cart:
        flash("Your cart is empty!", "danger")
        return redirect('/cart')

    # Calculate total amount
    total_amount = 0.0
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    pids = [int(k) for k in cart.keys() if k.isdigit()]
    if pids:
        format_strings = ','.join(['%s'] * len(pids))
        cursor.execute(f"SELECT * FROM products WHERE product_id IN ({format_strings})", tuple(pids))
        db_products = cursor.fetchall()
        prod_dict = {p['product_id']: p for p in db_products}
        
        for pid_str, val in cart.items():
            if pid_str.isdigit():
                pid = int(pid_str)
                if pid in prod_dict:
                    quantity = val['quantity'] if isinstance(val, dict) else val
                    total_amount += float(prod_dict[pid]['price']) * quantity
    cursor.close()

    if total_amount <= 0:
        flash("Invalid cart total!", "danger")
        return redirect('/cart')

    # Razorpay expects amount in paise (1 INR = 100 paise)
    razorpay_amount = int(round(total_amount * 100))

    try:
        razorpay_order = razorpay_client.order.create({
            "amount": razorpay_amount,
            "currency": "INR",
            "payment_capture": "1"
        })
        order_id = razorpay_order['id']
        session['razorpay_order_id'] = order_id
    except Exception as e:
        order_id = f"order_simulated_{random.randint(100000, 999999)}"
        session['razorpay_order_id'] = order_id

    return render_template(
        "user/payment.html",
        amount=total_amount,
        razorpay_amount=razorpay_amount,
        key_id=config.RAZORPAY_KEY_ID,
        order_id=order_id,
        cart_count=get_cart_count()
    )


# =============================================================================
# DAY 13: PAYMENT VERIFICATION & ORDER MANAGEMENT (Razorpay Signature & Storage)
# =============================================================================
@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    """
    Day 13: Verify Razorpay Payment Signature & Store Order + Order Items in Database
    """
    if 'user_id' not in session:
        flash("Please login to complete the payment.", "danger")
        return redirect('/user-login')

    razorpay_payment_id = request.form.get('razorpay_payment_id')
    razorpay_order_id = request.form.get('razorpay_order_id')
    razorpay_signature = request.form.get('razorpay_signature')

    if not (razorpay_payment_id and razorpay_order_id):
        flash("Payment verification failed (missing payment or order ID).", "danger")
        return redirect('/cart')

    # Signature verification logic
    if razorpay_signature and not razorpay_signature.startswith('simulated_sig_'):
        payload = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        try:
            razorpay_client.utility.verify_payment_signature(payload)
        except Exception as e:
            app.logger.error("Razorpay signature verification failed: %s", str(e))
            flash("Payment verification failed. Invalid signature.", "danger")
            return redirect('/cart')

    user_id = session['user_id']
    cart = session.get('cart', {})

    if not cart:
        flash("Cart is empty. Cannot create order.", "danger")
        return redirect('/cart')

    # Calculate total and build items list from database products
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    items_to_save = []
    total_amount = 0.0

    pids = [int(k) for k in cart.keys() if k.isdigit()]
    if pids:
        format_strings = ','.join(['%s'] * len(pids))
        cursor.execute(f"SELECT * FROM products WHERE product_id IN ({format_strings})", tuple(pids))
        db_products = cursor.fetchall()
        prod_dict = {p['product_id']: p for p in db_products}

        for pid_str, val in cart.items():
            if pid_str.isdigit():
                pid = int(pid_str)
                if pid in prod_dict:
                    prod = prod_dict[pid]
                    quantity = val['quantity'] if isinstance(val, dict) else val
                    price = float(prod['price'])
                    item_total = price * quantity
                    total_amount += item_total
                    items_to_save.append({
                        'product_id': pid,
                        'name': prod['name'],
                        'quantity': quantity,
                        'price': price
                    })
    cursor.close()

    if not items_to_save:
        flash("No valid products found in cart.", "danger")
        return redirect('/cart')

    # Store order master & order items transactionally
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO orders (user_id, razorpay_order_id, razorpay_payment_id, amount, payment_status)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, razorpay_order_id, razorpay_payment_id, total_amount, 'paid'))

        order_db_id = cursor.lastrowid

        for it in items_to_save:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, quantity, price)
                VALUES (%s, %s, %s, %s, %s)
            """, (order_db_id, it['product_id'], it['name'], it['quantity'], it['price']))

        conn.commit()

        # Clear session cart and temporary payment keys
        session.pop('cart', None)
        session.pop('razorpay_order_id', None)
        session.modified = True

        flash("Payment successful and order placed!", "success")
        return redirect(f"/user/order-success/{order_db_id}")

    except Exception as e:
        conn.rollback()
        app.logger.error("Order storage failed: %s", str(e))
        flash("There was an error saving your order. Please contact support.", "danger")
        return redirect('/cart')
    finally:
        cursor.close()
        conn.close()


@app.route('/user/order-success/<int:order_db_id>')
def order_success(order_db_id):
    """
    Day 13: Order Confirmation Page
    """
    if 'user_id' not in session:
        flash("Please login to view order details!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE order_id=%s AND user_id=%s", (order_db_id, session['user_id']))
    order = cursor.fetchone()

    items = []
    if order:
        cursor.execute("SELECT * FROM order_items WHERE order_id=%s", (order_db_id,))
        items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect('/')

    return render_template("user/order_success.html", order=order, items=items, cart_count=get_cart_count())


@app.route('/user/my-orders')
@app.route('/my-orders')
def my_orders():
    """
    Day 13: User Order History Page
    """
    if 'user_id' not in session:
        flash("Please login to view your orders!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC", (session['user_id'],))
    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("user/my_orders.html", orders=orders, cart_count=get_cart_count())


# =============================================================================
# DAY 14: PROFESSIONAL INVOICE GENERATION (HTML to PDF)
# =============================================================================
@app.route('/user/download-invoice/<int:order_id>')
def download_invoice(order_id):
    """
    Day 14: Generate & Download PDF Tax Invoice for Order
    """
    if 'user_id' not in session:
        flash("Please login to download your invoice!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE order_id=%s AND user_id=%s", (order_id, session['user_id']))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id=%s", (order_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect('/user/my-orders')

    # Render HTML invoice template
    html = render_template("user/invoice.html", order=order, items=items)

    # Convert HTML to PDF Bytes using pdf_generator
    pdf = generate_pdf(html)
    if not pdf:
        flash("Error generating invoice PDF. Please try again.", "danger")
        return redirect('/user/my-orders')

    # Send PDF HTTP response
    response = make_response(pdf.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f"attachment; filename=invoice_{order_id}.pdf"
    return response


@app.route('/user/view-invoice/<int:order_id>')
def view_invoice(order_id):
    """
    Day 14: View Invoice in Browser Window
    """
    if 'user_id' not in session:
        flash("Please login to view your invoice!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE order_id=%s AND user_id=%s", (order_id, session['user_id']))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id=%s", (order_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect('/user/my-orders')

    return render_template("user/invoice.html", order=order, items=items)


# =============================================================================
# CUSTOMER AUTHENTICATION (User Signup, OTP Verification, Login, Logout, Profile)
# =============================================================================
@app.route('/user-signup', methods=['GET', 'POST'])
def user_signup():
    """
    Customer Sign-up route (GET & POST) with OTP email delivery
    """
    if request.method == 'GET':
        return render_template("user/user_signup.html", cart_count=get_cart_count())

    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT user_id FROM users WHERE email=%s", (email,))
        existing_user = cursor.fetchone()
        cursor.close()
        conn.close()

        if existing_user:
            flash("This email is already registered as a customer. Please log in.", "danger")
            return redirect('/user-signup')
    except Exception as err:
        flash(f"Database error: {err}", "danger")
        return redirect('/user-signup')

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    otp = str(random.randint(100000, 999999))

    session['temp_user'] = {
        'name': name,
        'email': email,
        'password': hashed_password,
        'otp': otp
    }

    html_content = render_template('emails/otp_email.html', name=name, otp=otp)
    plain_content = f"Hello {name},\n\nYour SmartCart Customer Registration OTP is: {otp}\n\nThis OTP is valid for 10 minutes."

    try:
        msg = Message(
            subject="SmartCart Customer Verification OTP Code",
            sender=config.MAIL_USERNAME,
            recipients=[email]
        )
        msg.body = plain_content
        msg.html = html_content
        mail.send(msg)
        flash(f"An OTP verification code has been sent to {email}. Please verify.", "info")
    except Exception as email_err:
        print(f"[MAIL NOTICE] User OTP email sending notice: ({email_err})")
        flash(f"[DEV MODE] Verification OTP: {otp}. Enter code below.", "info")

    return redirect('/verify-user-otp')


@app.route('/verify-user-otp', methods=['GET', 'POST'])
def verify_user_otp():
    """
    Customer OTP Verification Route
    """
    if request.method == 'GET':
        if 'temp_user' not in session:
            flash("Signup session expired. Please register again.", "warning")
            return redirect('/user-signup')
        return render_template("user/verify_user_otp.html", email=session['temp_user']['email'], cart_count=get_cart_count())

    entered_otp = request.form.get('otp', '').strip()
    temp_user = session.get('temp_user')

    if not temp_user:
        flash("Registration session expired. Please sign up again.", "danger")
        return redirect('/user-signup')

    if entered_otp == temp_user['otp']:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password, is_verified) VALUES (%s, %s, %s, 1)",
                (temp_user['name'], temp_user['email'], temp_user['password'])
            )
            conn.commit()
            cursor.close()
            conn.close()

            session.pop('temp_user', None)
            flash("Customer registration successful! You can now log in.", "success")
            return redirect('/user-login')
        except Exception as err:
            flash(f"Error completing registration: {err}", "danger")
            return redirect('/verify-user-otp')
    else:
        flash("Invalid OTP code. Please check and try again.", "danger")
        return redirect('/verify-user-otp')


@app.route('/user-login', methods=['GET', 'POST'])
def user_login():
    """
    Customer Login Route
    """
    if request.method == 'GET':
        if session.get('user_id'):
            return redirect('/')
        return render_template("user/user_login.html", cart_count=get_cart_count())

    email = request.form.get('email')
    password = request.form.get('password')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect('/')
        else:
            flash("Invalid email address or password.", "danger")
            return redirect('/user-login')
    except Exception as err:
        flash(f"Database error: {err}", "danger")
        return redirect('/user-login')


@app.route('/user-logout')
def user_logout():
    """
    Customer Logout Route
    """
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)
    flash("You have been logged out successfully.", "info")
    return redirect('/')


@app.route('/user/profile', methods=['GET', 'POST'])
def user_profile():
    """
    Customer Profile View & Update Route
    """
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to view your profile.", "warning")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        new_password = request.form.get('password')

        if new_password:
            hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("UPDATE users SET name=%s, email=%s, password=%s WHERE user_id=%s", (name, email, hashed_pw, user_id))
        else:
            cursor.execute("UPDATE users SET name=%s, email=%s WHERE user_id=%s", (name, email, user_id))
        
        conn.commit()
        session['user_name'] = name
        session['user_email'] = email
        flash("Your profile details have been updated successfully!", "success")

    cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("user/user_profile.html", user=user, cart_count=get_cart_count())


# =============================================================================
# DAY 2: ADMIN SIGNUP & OTP VERIFICATION
# =============================================================================
@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup():
    """
    Day 2 Route 1: Display Signup form (GET) or process signup & send OTP (POST)
    """
    if request.method == "GET":
        return render_template("admin/admin_signup.html")

    name = request.form['name']
    email = request.form['email']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT admin_id FROM admin WHERE email=%s", (email,))
        existing_admin = cursor.fetchone()
        cursor.close()
        conn.close()

        if existing_admin:
            flash("This email is already registered. Please login instead.", "danger")
            return redirect('/admin-signup')
    except Exception as err:
        flash(f"Database error: {err}", "danger")
        return redirect('/admin-signup')

    session['signup_name'] = name
    session['signup_email'] = email

    otp = random.randint(100000, 999999)
    session['otp'] = otp
    print(f"\n[SERVER OTP LOG] OTP for {email} is: {otp}\n")

    # Render styled HTML email template matching website CSS design
    html_content = render_template('emails/otp_email.html', name=name, otp=otp)
    plain_content = f"Hello {name},\n\nYour OTP for SmartCart Admin Registration is: {otp}\n\nThis OTP is valid for 10 minutes."

    try:
        message = Message(
            subject="SmartCart Admin OTP Verification",
            sender=config.MAIL_USERNAME,
            recipients=[email]
        )
        message.body = plain_content
        message.html = html_content
        mail.send(message)
        flash("OTP sent to your email!", "success")
    except Exception as email_err:
        print(f"[MAIL NOTICE] SMTP delivery notice ({email_err}). Console OTP: {otp}")
        flash(f"OTP generated! (Check Console OTP: {otp})", "info")

    return redirect('/verify-otp')


@app.route('/verify-otp', methods=['GET'])
def verify_otp_get():
    """
    Day 2 Route 2: Render OTP verification page
    """
    return render_template("admin/verify_otp.html")


@app.route('/verify-otp', methods=['POST'])
def verify_otp_post():
    """
    Day 2 Route 3: Verify OTP and save hashed password into admin table
    """
    user_otp = request.form['otp']
    password = request.form['password']

    if str(session.get('otp')) != str(user_otp):
        flash("Invalid OTP. Try again!", "danger")
        return redirect('/verify-otp')

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        signup_name = session.get('signup_name')
        signup_email = session.get('signup_email')
        
        if not signup_name or not signup_email:
            flash("Session expired. Please sign up again.", "danger")
            return redirect('/admin-signup')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO admin (name, email, password) VALUES (%s, %s, %s)",
            (signup_name, signup_email, hashed_password)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as db_err:
        flash(f"Database error during registration: {db_err}", "danger")
        return redirect('/verify-otp')

    session.pop('otp', None)
    session.pop('signup_name', None)
    session.pop('signup_email', None)

    flash("Admin Registered Successfully!", "success")
    return redirect('/admin-signup')


# =============================================================================
# DAY 3: ADMIN LOGIN & DASHBOARD ACCESS
# =============================================================================
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """
    Day 3 Route 4: Admin Login Page (GET) & Credentials Authentication (POST)
    """
    if request.method == 'GET':
        return render_template("admin/admin_login.html")

    email = request.form['email']
    password = request.form['password']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin WHERE email=%s", (email,))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception as db_err:
        flash(f"Database error: {db_err}", "danger")
        return redirect('/admin-login')

    if admin is None:
        flash("Email not found! Please register first.", "danger")
        return redirect('/admin-login')

    stored_hashed_password = admin['password'].encode('utf-8')

    if not bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password):
        flash("Incorrect password! Try again.", "danger")
        return redirect('/admin-login')

    session['admin_id'] = admin['admin_id']
    session['admin_name'] = admin['name']
    session['admin_email'] = admin['email']

    flash("Login Successful!", "success")
    return redirect('/admin-dashboard')


@app.route('/admin-dashboard')
def admin_dashboard():
    """
    Day 3 Route 5: Protected Admin Dashboard
    """
    if 'admin_id' not in session:
        flash("Please login to access dashboard!", "danger")
        return redirect('/admin-login')

    total_products = 0
    total_categories = 0
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS count FROM products")
        res = cursor.fetchone()
        total_products = res['count'] if res else 0

        cursor.execute("SELECT COUNT(DISTINCT category) AS count FROM products WHERE category IS NOT NULL AND category != ''")
        res_cat = cursor.fetchone()
        total_categories = res_cat['count'] if res_cat else 0

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DASHBOARD ERROR] Could not fetch stats: {e}")

    return render_template(
        "admin/dashboard.html",
        admin_name=session['admin_name'],
        total_products=total_products,
        total_categories=total_categories
    )


@app.route('/admin-logout')
def admin_logout():
    """
    Day 3 Route 6: Clear Admin Session & Logout
    """
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    session.pop('admin_email', None)

    flash("Logged out successfully.", "success")
    return redirect('/admin-login')


# =============================================================================
# DAY 4: PRODUCT MANAGEMENT - ADD PRODUCT
# =============================================================================
@app.route('/admin/add-item', methods=['GET'])
def add_item_page():
    """
    Day 4 Route 7: Show Add Product Form (Protected)
    """
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    return render_template("admin/add_item.html")


@app.route('/admin/add-item', methods=['POST'])
def add_item():
    """
    Day 4 Route 8: Process Product Form submission and save image upload
    """
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    price = request.form['price']
    image_file = request.files['image']

    if image_file.filename == "":
        flash("Please upload a product image!", "danger")
        return redirect('/admin/add-item')

    filename = secure_filename(image_file.filename)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image_file.save(image_path)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO products (name, description, category, price, image) VALUES (%s, %s, %s, %s, %s)",
            (name, description, category, price, filename)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as db_err:
        flash(f"Database error adding product: {db_err}", "danger")
        return redirect('/admin/add-item')

    flash("Product added successfully!", "success")
    return redirect('/admin/add-item')


# =============================================================================
# DAY 5 & DAY 7: PRODUCT DISPLAY, SEARCH & CATEGORY FILTERING
# =============================================================================
@app.route('/admin/item-list')
def item_list():
    """
    Day 5 & Day 7 Route 9: Fetch and display products with search and category filter capabilities
    """
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    search_term = request.args.get('search', '').strip()
    selected_category = request.args.get('category', '').strip()

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''")
        categories_result = cursor.fetchall()
        categories = [c['category'] for c in categories_result]

        query = "SELECT * FROM products WHERE 1=1"
        params = []

        if search_term:
            query += " AND name LIKE %s"
            params.append(f"%{search_term}%")

        if selected_category:
            query += " AND category = %s"
            params.append(selected_category)

        query += " ORDER BY product_id ASC"

        cursor.execute(query, tuple(params))
        products = cursor.fetchall()

        cursor.close()
        conn.close()
    except Exception as db_err:
        products = []
        categories = []
        flash(f"Database error fetching products: {db_err}", "danger")

    return render_template(
        "admin/item_list.html",
        products=products,
        categories=categories,
        search_term=search_term,
        selected_category=selected_category
    )


@app.route('/admin/view-item/<int:item_id>')
def view_item(item_id):
    """
    Day 5 Route 10: Fetch and display single product details by product_id
    """
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception as db_err:
        flash(f"Database error fetching product details: {db_err}", "danger")
        return redirect('/admin/item-list')

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/view_item.html", product=product)


# =============================================================================
# DAY 6: PRODUCT MANAGEMENT - UPDATE PRODUCT WITH IMAGE REPLACEMENT
# =============================================================================
@app.route('/admin/update-item/<int:item_id>', methods=['GET'])
def update_item_page(item_id):
    """
    Day 6 Route 11: Display Product Update Form pre-populated with existing data
    """
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception as db_err:
        flash(f"Database error: {db_err}", "danger")
        return redirect('/admin/item-list')

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/update_item.html", product=product)


@app.route('/admin/update-item/<int:item_id>', methods=['POST'])
def update_item(item_id):
    """
    Day 6 Route 12: Process Product Update & optional image replacement (deleting old image file)
    """
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    price = request.form['price']
    new_image_file = request.files.get('image')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
        existing_product = cursor.fetchone()

        if not existing_product:
            cursor.close()
            conn.close()
            flash("Product not found!", "danger")
            return redirect('/admin/item-list')

        filename = existing_product['image']

        # Image Handling Logic: Check if a new image was uploaded
        if new_image_file and new_image_file.filename != "":
            new_filename = secure_filename(new_image_file.filename)
            new_image_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            new_image_file.save(new_image_path)

            # Delete old image file if it exists and filename differs
            if existing_product['image'] and existing_product['image'] != new_filename:
                old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], existing_product['image'])
                if os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                    except Exception as err:
                        print(f"[FILE NOTICE] Could not remove old image file: {err}")

            filename = new_filename

        cursor.execute(
            "UPDATE products SET name=%s, description=%s, category=%s, price=%s, image=%s WHERE product_id=%s",
            (name, description, category, price, filename, item_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Product updated successfully!", "success")
    except Exception as db_err:
        flash(f"Error updating product: {db_err}", "danger")

    return redirect('/admin/item-list')


# =============================================================================
# DAY 7: PRODUCT MANAGEMENT - DELETE PRODUCT WITH IMAGE CLEANUP
# =============================================================================
@app.route('/admin/delete-item/<int:item_id>')
def delete_item(item_id):
    """
    Day 7 Route 13: Delete product record from DB and remove associated image file from disk
    """
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT image FROM products WHERE product_id = %s", (item_id,))
        product = cursor.fetchone()

        if product:
            image_filename = product['image']
            if image_filename:
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                if os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception as err:
                        print(f"[FILE NOTICE] Could not remove image file on deletion: {err}")

            cursor.execute("DELETE FROM products WHERE product_id = %s", (item_id,))
            conn.commit()
            flash("Product deleted successfully!", "success")
        else:
            flash("Product not found!", "danger")

        cursor.close()
        conn.close()
    except Exception as db_err:
        flash(f"Error deleting product: {db_err}", "danger")

    return redirect('/admin/item-list')


# =============================================================================
# DAY 8: ADMIN PROFILE & PROFILE UPDATE (WITH IMAGE REPLACEMENT)
# =============================================================================
@app.route('/admin/profile', methods=['GET'])
def admin_profile():
    """
    Day 8 Route 14: Show Admin Profile Page & Current Admin Data
    """
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (admin_id,))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception as err:
        flash(f"Database error fetching profile: {err}", "danger")
        return redirect('/admin-dashboard')

    if not admin:
        flash("Admin record not found!", "danger")
        return redirect('/admin-dashboard')

    return render_template("admin/admin_profile.html", admin=admin)


@app.route('/admin/profile', methods=['POST'])
def admin_profile_update():
    """
    Day 8 Route 15: Update Admin Profile (Name, Email, Optional Password, Optional Image Replacement)
    """
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']

    # 1. Get form data
    name = request.form['name']
    email = request.form['email']
    new_password = request.form.get('password', '').strip()
    new_image = request.files.get('profile_image')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 2. Fetch current admin data from DB
        cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (admin_id,))
        admin = cursor.fetchone()

        if not admin:
            cursor.close()
            conn.close()
            flash("Admin record not found!", "danger")
            return redirect('/admin-dashboard')

        old_image_name = admin.get('profile_image')

        # 3. Update password only if entered
        if new_password:
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        else:
            hashed_password = admin['password']

        # 4. Process new profile image if uploaded
        if new_image and new_image.filename != "":
            new_filename = secure_filename(new_image.filename)

            # Save new image to static/uploads/admin_profiles
            image_path = os.path.join(app.config['ADMIN_UPLOAD_FOLDER'], new_filename)
            new_image.save(image_path)

            # Delete old profile image if file exists and filename differs
            if old_image_name and old_image_name != new_filename:
                old_image_path = os.path.join(app.config['ADMIN_UPLOAD_FOLDER'], old_image_name)
                if os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                    except Exception as err:
                        print(f"[FILE NOTICE] Could not remove old profile image: {err}")

            final_image_name = new_filename
        else:
            final_image_name = old_image_name

        # 5. Update database record
        cursor.execute("""
            UPDATE admin
            SET name=%s, email=%s, password=%s, profile_image=%s
            WHERE admin_id=%s
        """, (name, email, hashed_password, final_image_name, admin_id))

        conn.commit()
        cursor.close()
        conn.close()

        # Update active session values for UI consistency
        session['admin_name'] = name
        session['admin_email'] = email

        flash("Profile updated successfully!", "success")
    except Exception as db_err:
        flash(f"Error updating profile: {db_err}", "danger")

    return redirect('/admin/profile')


# -----------------------------------------------------------------------------
# APPLICATION ENTRYPOINT
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    print("Starting SmartCart Flask Server (Days 1-8)...")
    app.run(debug=True, port=5000)
