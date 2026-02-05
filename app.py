from flask import Flask, render_template, request, jsonify, session, redirect
from datetime import date, datetime, time

app = Flask(__name__)
app.secret_key = "clinic-secret-key"   # REQUIRED for session

# ================== CONFIG ==================
MAX_TOKENS_PER_DAY = 30
SESSION_START_TIME = time(17, 0)   # 5:00 PM
SESSION_END_TIME   = time(20, 0)   # 8:00 PM

# In-memory storage
bookings = {}        # { date: [booking, booking] }
availability = {}    # { date: {available, booked_count} }

today_str = date.today().isoformat()

# ================== HELPERS ==================
def get_availability(d):
    if d not in availability:
        availability[d] = {
            'available': True,
            'booked_count': 0
        }
    return availability[d]

def can_book_today():
    return datetime.now().time() < SESSION_START_TIME

# ================== ROUTES ==================

# ---------- HOME (PATIENT + ADMIN SAME PAGE) ----------
@app.route('/')
def home():
    return render_template(
        'index.html',
        today=today_str,
        is_admin=session.get('admin_logged_in', False),
        bookings=bookings
    )

# ---------- CHECK TOKEN PAGE ----------
@app.route('/my-token')
def my_token():
    return render_template('my-token.html')

# ---------- ADMIN LOGIN ----------
@app.route('/admin/login', methods=['POST'])
def admin_login():
    username = request.form.get('username')
    password = request.form.get('password')

    if username == "admin" and password == "admin123":
        session['admin_logged_in'] = True

    return redirect('/')

# ---------- ADMIN LOGOUT ----------
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/')

# ---------- BOOK TOKEN ----------
@app.route('/api/book', methods=['POST'])
def api_book():
    data = request.get_json()

    name  = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    b_date = data.get('date', '').strip()

    if not name or not phone or not b_date:
        return jsonify({"success": False, "message": "All fields are required"}), 400

    if len(phone) != 10 or not phone.isdigit():
        return jsonify({"success": False, "message": "Invalid phone number"}), 400

    if b_date < today_str:
        return jsonify({"success": False, "message": "Cannot book past dates"}), 400

    if b_date == today_str and not can_book_today():
        return jsonify({"success": False, "message": "Booking window closed"}), 400

    avail = get_availability(b_date)

    if not avail['available']:
        return jsonify({"success": False, "message": "Bookings closed for this date"}), 400

    if avail['booked_count'] >= MAX_TOKENS_PER_DAY:
        return jsonify({"success": False, "message": "Tokens full"}), 400

    token_number = avail['booked_count'] + 1
    avail['booked_count'] += 1

    booking = {
        "name": name,
        "phone": phone,
        "token": token_number,
        "status": "confirmed",
        "booked_at": datetime.now().strftime("%H:%M")
    }

    bookings.setdefault(b_date, []).append(booking)

    return jsonify({
        "success": True,
        "message": "Token booked successfully",
        "token": token_number,
        "date": b_date
    })

# ---------- CLOSE TODAY (EMERGENCY) ----------
@app.route('/api/close-today', methods=['POST'])
def close_today():
    availability[today_str] = {'available': False, 'booked_count': 0}

    if today_str in bookings:
        for b in bookings[today_str]:
            b['status'] = 'cancelled'

    return jsonify({"success": True, "message": "Today's OPD closed"})

# ---------- CHECK TOKEN ----------
@app.route('/api/check-token', methods=['POST'])
def check_token():
    data = request.get_json()
    phone = data.get('phone', '').strip()

    for d, blist in bookings.items():
        for b in blist:
            if b['phone'] == phone:
                return jsonify({
                    "success": True,
                    "found": True,
                    "name": b['name'],
                    "date": d,
                    "token": b['token'],
                    "status": b['status'],
                    "booked_at": b['booked_at']
                })

    return jsonify({"success": True, "found": False})

# ================== RUN ==================
if __name__ == '__main__':
    app.run(debug=True, port=5000)
