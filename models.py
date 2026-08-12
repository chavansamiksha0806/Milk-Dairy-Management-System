from db import get_connection
import hashlib
from sklearn.linear_model import LinearRegression
import numpy as np

# AI MODEL (Milk Price Prediction)
X = np.array([[4,8],[5,9],[6,10]])
y = np.array([40,50,60])
model = LinearRegression()
model.fit(X,y)

def predict_price(fat, snf):
    return model.predict([[fat,snf]])[0]

# CREATE TABLES
def init_db():
    con = get_connection()

    con.execute("""
    CREATE TABLE IF NOT EXISTS user(
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT
    )
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS farmer(
        id INTEGER PRIMARY KEY,
        name TEXT,
        contact TEXT
    )
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS milk(
        id INTEGER PRIMARY KEY,
        farmer_id INTEGER,
        animal_type TEXT,
        litres REAL,
        fat REAL,
        snf REAL,
        degree TEXT,
        rate REAL,
        total REAL,
        session TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ✅ FIXED PAYMENT TABLE (NOW INSIDE FUNCTION)
    con.execute("""
    CREATE TABLE IF NOT EXISTS payment(
        id INTEGER PRIMARY KEY,
        farmer_id INTEGER,
        amount REAL,
        status TEXT,
        transaction_id TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    con.commit()
    con.close()
# ADMIN LOGIN
def create_admin():
    con = get_connection()
    pwd = hashlib.sha256("admin".encode()).hexdigest()

    if not con.execute("SELECT * FROM user WHERE username='admin'").fetchone():
        con.execute("INSERT INTO user(username,password) VALUES('admin',?)",(pwd,))

    con.commit()
    con.close()

# FARMER MODULE
def get_next_farmer_id():
    con = get_connection()
    data = con.execute("SELECT MAX(id) FROM farmer").fetchone()[0]
    con.close()
    return (data + 1) if data else 101

def add_farmer(fid, name, contact):
    con = get_connection()

    if con.execute("SELECT * FROM farmer WHERE id=?",(fid,)).fetchone():
        return False

    con.execute("INSERT INTO farmer(id,name,contact) VALUES(?,?,?)",(fid,name,contact))
    con.commit()
    con.close()
    return True

def get_farmers():
    con = get_connection()
    data = con.execute("SELECT * FROM farmer").fetchall()
    con.close()
    return data

# MILK MODULE
def add_milk(fid, animal, litres, fat, snf, degree, session):
    con = get_connection()

    rate = predict_price(fat, snf)
    total = litres * rate

    con.execute("""
    INSERT INTO milk(farmer_id,animal_type,litres,fat,snf,degree,rate,total,session)
    VALUES(?,?,?,?,?,?,?,?,?)
    """,(fid,animal,litres,fat,snf,degree,rate,total,session))

    con.execute("INSERT INTO payment(farmer_id,amount,status) VALUES(?,?,?)",
                (fid,total,"Pending"))

    con.commit()
    con.close()

def get_records():
    con = get_connection()
    data = con.execute("""
    SELECT f.name,m.animal_type,m.litres,m.degree,m.session,m.date,m.total
    FROM milk m JOIN farmer f ON m.farmer_id=f.id
    """).fetchall()
    con.close()
    return data

# PAYMENT MODULE
def get_payments():
    con = get_connection()
    data = con.execute("""
        SELECT p.id, f.name, p.amount, p.status, p.transaction_id, p.date
        FROM payment p JOIN farmer f ON p.farmer_id=f.id
    """).fetchall()
    con.close()
    return data

def mark_paid(id, txn_id=None):
    con = get_connection()
    con.execute(
        "UPDATE payment SET status='Paid', transaction_id=? WHERE id=?",
        (txn_id, id)
    )
    con.commit()
    con.close()
# DASHBOARD
def dashboard_data():
    con = get_connection()
    farmers = con.execute("SELECT COUNT(*) FROM farmer").fetchone()[0]
    milk = con.execute("SELECT SUM(litres) FROM milk").fetchone()[0] or 0
    payment = con.execute("SELECT SUM(amount) FROM payment").fetchone()[0] or 0
    con.close()
    return farmers, milk, payment

# MONTHLY SUMMARY
def monthly_summary():
    con = get_connection()
    data = con.execute("""
    SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
    FROM payment GROUP BY month
    """).fetchall()
    con.close()
    return data
