from flask import Flask, render_template, request, redirect, session, send_file
from models import *
from db import get_connection
import hashlib
from functools import wraps
from reportlab.platypus import SimpleDocTemplate, Paragraph
import qrcode
app = Flask(__name__)
app.secret_key = "secret"

# ================= INIT =================
init_db()
create_admin()

# ================= LOGIN REQUIRED =================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


# ================= HOME =================
@app.route('/')
def home():
    return redirect('/login')


# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        user = request.form['username']
        pwd = hashlib.sha256(request.form['password'].encode()).hexdigest()

        con = get_connection()
        data = con.execute(
            "SELECT * FROM user WHERE username=? AND password=?",
            (user, pwd)
        ).fetchone()

        if data:
            session['user'] = user
            return redirect('/dashboard')
        else:
            error = "Invalid Username or Password ❌"

    return render_template("login.html", error=error)


# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ================= DASHBOARD =================
@app.route('/dashboard')
@login_required
def dashboard():
    farmers, milk, payment = dashboard_data()

    return render_template(
        "dashboard.html",
        farmers=farmers,
        milk=milk,
        payment=payment
    )


# ================= FARMERS =================
@app.route('/farmers')
@login_required
def farmers():
    return render_template("farmers.html", data=get_farmers())


# ================= ADD FARMER =================
@app.route('/farmer/add', methods=['GET', 'POST'])
@login_required
def add_farmer_route():
    error = None

    if request.method == 'POST':
        fid = request.form['id']
        name = request.form['name']
        contact = request.form['contact']

        if not contact.isdigit() or len(contact) != 10:
            error = "Contact must be 10 digits ❌"
            return render_template("farmer_add.html",
                                   fid=get_next_farmer_id(),
                                   error=error)

        if not add_farmer(fid, name, contact):
            error = "Farmer ID already exists ❌"
            return render_template("farmer_add.html",
                                   fid=get_next_farmer_id(),
                                   error=error)

        return redirect('/farmers')

    return render_template("farmer_add.html",
                           fid=get_next_farmer_id(),
                           error=error)


# ================= EDIT FARMER =================
@app.route('/farmer/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_farmer(id):
    con = get_connection()

    if request.method == 'POST':
        name = request.form['name']
        contact = request.form['contact']

        if not contact.isdigit() or len(contact) != 10:
            return render_template("farmer_edit.html",
                                   f={'id': id, 'name': name, 'contact': contact},
                                   error="Contact must be 10 digits ❌")

        con.execute("UPDATE farmer SET name=?, contact=? WHERE id=?",
                    (name, contact, id))
        con.commit()
        con.close()
        return redirect('/farmers')

    f = con.execute("SELECT * FROM farmer WHERE id=?", (id,)).fetchone()
    con.close()

    return render_template("farmer_edit.html", f=f)


# ================= DELETE FARMER =================
@app.route('/farmer/delete/<int:id>')
@login_required
def delete_farmer(id):
    con = get_connection()
    con.execute("DELETE FROM farmer WHERE id=?", (id,))
    con.commit()
    con.close()
    return redirect('/farmers')


# ================= MILK ENTRY =================
@app.route('/milk/add', methods=['GET', 'POST'])
@login_required
def milk():
    farmers = get_farmers()

    if request.method == 'POST':
        add_milk(
            request.form['farmer_id'],
            request.form['animal_type'],
            float(request.form['litres']),
            float(request.form['fat']),
            float(request.form['snf']),
            request.form['degree'],
            request.form['session']
        )
        return redirect('/records')

    return render_template("milk_entry.html", farmers=farmers)


# ================= RECORDS =================
@app.route('/records')
@login_required
def records():
    return render_template("records.html", data=get_records())


# ================= PAYMENTS =================
@app.route('/payments')
@login_required
def payments():
    return render_template("payments.html", data=get_payments())


# ================= MARK PAID =================
@app.route('/success/<int:id>')
@login_required
def success_payment(id):
    txn_id = "TXN" + str(id)
    mark_paid(id, txn_id)
    return redirect('/payments?msg=success')


# ================= UPI =================
@app.route('/upi/<int:id>/<amount>')
@login_required
def upi(id, amount):
    upi_id = "yourupi@upi"

    upi_link = f"upi://pay?pa={upi_id}&pn=DairySystem&am={amount}&cu=INR"

    # Generate QR
    img = qrcode.make(upi_link)
    qr_path = f"static/qr_{id}.png"
    img.save(qr_path)

    return render_template("upi.html",
                           link=upi_link,
                           id=id,
                           amount=amount,
                           qr=qr_path)


# ================= PDF BILL =================
@app.route('/bill/<int:id>')
@login_required
def bill(id):
    con = get_connection()
    data = con.execute("""
        SELECT f.name, p.amount, p.date
        FROM payment p
        JOIN farmer f ON p.farmer_id = f.id
        WHERE p.id = ?
    """, (id,)).fetchone()

    file = f"bill_{id}.pdf"
    doc = SimpleDocTemplate(file)

    content = []
    content.append(Paragraph(f"Farmer: {data['name']}"))
    content.append(Paragraph(f"Amount: ₹{data['amount']}"))
    content.append(Paragraph(f"Date: {data['date']}"))

    doc.build(content)

    return send_file(file, as_attachment=True)


# ================= SUMMARY =================
@app.route('/summary')
@login_required
def summary():
    return render_template("summary.html", data=monthly_summary())


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)