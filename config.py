# config.py
# ---------------------------------------------------------
# Stores all configuration settings for SmartCart Application
# like Secret Key, Database connection details, Email settings, etc.
# ---------------------------------------------------------

SECRET_KEY = "your_secret_key_here"   # Used for sessions and flash messages

# MySQL Database Configuration
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "Harshith@16"  # Keep empty if no password, or update if password is set
DB_NAME = "smartcart_db"

# Email SMTP Settings (Flask-Mail Configuration)
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'harshithcheripally16@gmail.com'
MAIL_PASSWORD = 'neft ofei rmed vzyd'   # Gmail App Password

# Razorpay Payment Gateway Credentials (Test Mode)
RAZORPAY_KEY_ID = 'rzp_test_TLeM6Ox9b7K9Dp'
RAZORPAY_KEY_SECRET = 'dU4b4haEuqjJU1pc61pvF0UE'
