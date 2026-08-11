# 🛒 SmartCart — Modern Full-Stack E-Commerce Application

SmartCart is a feature-rich, production-ready E-Commerce application built with **Flask**, **MySQL / SQLite**, **HTML5**, **Bootstrap 5.3.3**, and **Vanilla JavaScript**, styled with **"The Year of Greta"** light visual design system.

---

## 🌟 Key Features

- **🛒 Interactive Storefront**: Dynamic product catalog with category filter, search bar, and infinite marquee banner.
- **🔍 Enhanced Product Modal**: Zero-reload product detail popups with image zoom and direct quantity controls.
- **🛍️ Option 5 Shopping Cart**: Selective item checkboxes, dynamic subtotal calculation, bulk clear, and terms agreement lock.
- **🔐 User & Admin Authentication**:
  - Customer signup/login with BCrypt password hashing.
  - Admin registration with OTP verification via Flask-Mail.
- **💳 Razorpay Payment Gateway**: Integrated test-mode payment modal with signature verification and order creation.
- **📦 Order History & Management**: Master `orders` and detail `order_items` database tracking with Indian currency formatting (`₹1,49,999`).
- **📄 On-the-Fly PDF Invoice Generation**: Download professional tax invoices generated dynamically via `xhtml2pdf`.
- **☀️ "The Year of Greta" Light Visual Aesthetic**: Modern light theme palette featuring electric teal accents (`#00a896`), dark slate typography, and sleek glassmorphic containers.

---

## 🚀 Technology Stack

- **Backend**: Python 3.x, Flask, Werkzeug, Flask-Mail
- **Database**: MySQL / SQLite (`database/schema.sql`)
- **Frontend**: HTML5, CSS3, JavaScript (ES6), Bootstrap 5.3.3, Bootstrap Icons
- **Payment Gateway**: Razorpay API
- **PDF Generator**: `xhtml2pdf`

---

## 💻 Local Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/harshithcheripally16-ui/Flask_Smart-Cart_Project.git
   cd Flask_Smart-Cart_Project
   ```

2. **Create & Activate Virtual Environment**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Application**:
   ```bash
   python app.py
   ```
   Open your browser at `http://127.0.0.1:5000/`.

---

## ☁️ Deployment on PythonAnywhere

1. Open a Bash console on **PythonAnywhere**.
2. Clone repository:
   ```bash
   git clone https://github.com/harshithcheripally16-ui/Flask_Smart-Cart_Project.git
   cd Flask_Smart-Cart_Project
   python3.10 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Set Virtualenv and Working Directory in Web Tab.
4. Edit `/var/www/yourusername_pythonanywhere_com_wsgi.py`:
   ```python
   import sys, os
   project_folder = '/home/yourusername/Flask_Smart-Cart_Project'
   if project_folder not in sys.path:
       sys.path.append(project_folder)
   from app import app as application
   ```
5. Reload web app!
