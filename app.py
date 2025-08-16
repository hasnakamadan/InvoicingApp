import os
from datetime import datetime
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///invoicer.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

COUNTRIES = ["United States", "Canada", "United Kingdom", "Australia"]

# --- Models ---
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    unit_price = db.Column(Numeric(10,2), nullable=False, default=0)
    is_service = db.Column(db.Boolean, default=False)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    customer = db.relationship("Customer", backref=db.backref("invoices", lazy=True))
    date = db.Column(db.Date, default=lambda: datetime.utcnow().date())
    due_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default="draft")  # draft/sent

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False)
    invoice = db.relationship("Invoice", backref=db.backref("items", lazy=True, cascade="all, delete-orphan"))
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(Numeric(10,2), nullable=False, default=1)
    unit_price = db.Column(Numeric(10,2), nullable=False, default=0)

# --- Utils ---
def to_decimal(v):
    """Safely convert a value to ``Decimal``.

    ``Decimal`` can produce surprising results when fed floats directly due to
    binary floating point representation (e.g. ``Decimal(1.1)`` yielding
    ``Decimal('1.1000000000000000888…')``).  To avoid this and to be resilient
    to ``None`` or other invalid values, convert the input to ``str`` first and
    fall back to ``Decimal(0)`` on failure.
    """
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(0)

def money(v):
    """Format a number as a currency string.

    The previous implementation placed the negative sign after the dollar sign
    (``$-1.00``) which is unconventional and confusing.  This version ensures
    the sign precedes the currency symbol (``-$1.00``).
    """
    n = Decimal(str(v)) if v is not None else Decimal(0)
    sign = "-" if n < 0 else ""
    return f"{sign}${abs(n):,.2f}"

app.jinja_env.filters["money"] = money

def send_invoice_email(to_email, subject, html_body):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM", user)

    if not all([host, port, user, password, from_addr]):
        raise RuntimeError("SMTP settings are missing in .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)

# --- Routes ---
@app.route("/initdb")
def initdb():
    db.create_all()
    flash("Database initialized", "success")
    return redirect(url_for("index"))

@app.route("/")
def index():
    invoices = Invoice.query.order_by(Invoice.id.desc()).limit(5).all()
    customers = Customer.query.order_by(Customer.created_at.desc()).limit(5).all()
    return render_template("index.html", invoices=invoices, customers=customers)

# Customers
@app.route("/customers")
def customers():
    q = request.args.get("q", "")
    qry = Customer.query
    if q:
        like = f"%{q}%"
        qry = qry.filter(
            (Customer.first_name.ilike(like))
            | (Customer.last_name.ilike(like))
            | (Customer.email.ilike(like))
        )
    rows = qry.order_by(Customer.first_name, Customer.last_name).all()
    return render_template("customers.html", customers=rows, q=q)

@app.route("/customers/new", methods=["GET", "POST"])
def customers_new():
    if request.method == "POST":
        c = Customer(
            first_name=request.form["first_name"],
            last_name=request.form["last_name"],
            email=request.form["email"],
            phone=request.form.get("phone"),
            address=request.form.get("address"),
            city=request.form.get("city"),
            state=request.form.get("state"),
            postal_code=request.form.get("postal_code"),
            country=request.form.get("country"),
        )
        db.session.add(c)
        db.session.commit()
        flash("Customer created", "success")
        return redirect(url_for("customers"))
    return render_template("customer_form.html", customer=None, countries=COUNTRIES)

@app.route("/customers/<int:cid>/edit", methods=["GET", "POST"])
def customers_edit(cid):
    c = Customer.query.get_or_404(cid)
    if request.method == "POST":
        c.first_name = request.form["first_name"]
        c.last_name = request.form["last_name"]
        c.email = request.form["email"]
        c.phone = request.form.get("phone")
        c.address = request.form.get("address")
        c.city = request.form.get("city")
        c.state = request.form.get("state")
        c.postal_code = request.form.get("postal_code")
        c.country = request.form.get("country")
        db.session.commit()
        flash("Customer updated", "success")
        return redirect(url_for("customers"))
    return render_template("customer_form.html", customer=c, countries=COUNTRIES)

# Products
@app.route("/products")
def products():
    rows = Product.query.order_by(Product.name).all()
    return render_template("products.html", products=rows)

@app.route("/products/new", methods=["GET", "POST"])
def products_new():
    if request.method == "POST":
        p = Product(
            name=request.form["name"],
            description=request.form.get("description"),
            unit_price=to_decimal(request.form.get("unit_price", "0")),
            is_service=("is_service" in request.form),
        )
        db.session.add(p)
        db.session.commit()
        flash("Item created", "success")
        return redirect(url_for("products"))
    return render_template("product_form.html", product=None)

@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
def products_edit(pid):
    p = Product.query.get_or_404(pid)
    if request.method == "POST":
        p.name = request.form["name"]
        p.description = request.form.get("description")
        p.unit_price = to_decimal(request.form.get("unit_price", "0"))
        p.is_service = ("is_service" in request.form)
        db.session.commit()
        flash("Item updated", "success")
        return redirect(url_for("products"))
    return render_template("product_form.html", product=p)

# Invoices
@app.route("/invoices")
def invoices():
    rows = Invoice.query.order_by(Invoice.id.desc()).all()
    return render_template("invoices.html", invoices=rows)

@app.route("/invoices/new", methods=["GET", "POST"])
def invoices_new():
    customers = Customer.query.order_by(Customer.first_name, Customer.last_name).all()
    products = Product.query.order_by(Product.name).all()
    if request.method == "POST":
        customer_id = int(request.form["customer_id"])
        date = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date() if request.form.get("date") else datetime.utcnow().date()
        due_date = datetime.strptime(request.form.get("due_date"), "%Y-%m-%d").date() if request.form.get("due_date") else None
        notes = request.form.get("notes")

        inv = Invoice(customer_id=customer_id, date=date, due_date=due_date, notes=notes, status="draft")
        db.session.add(inv)
        db.session.flush()  # get inv.id

        descs = request.form.getlist("item_description")
        qtys = request.form.getlist("item_quantity")
        prices = request.form.getlist("item_unit_price")

        for d, q, up in zip(descs, qtys, prices):
            if d.strip():
                item = InvoiceItem(
                    invoice_id=inv.id,
                    description=d.strip(),
                    quantity=to_decimal(q or "1"),
                    unit_price=to_decimal(up or "0"),
                )
                db.session.add(item)

        db.session.commit()
        flash("Invoice created", "success")
        return redirect(url_for("invoice_view", iid=inv.id))

    return render_template("invoice_new.html", customers=customers, products=products)

@app.route("/invoices/<int:iid>")
def invoice_view(iid):
    inv = Invoice.query.get_or_404(iid)
    subtotal = sum((item.quantity * item.unit_price for item in inv.items), Decimal(0))
    tax = subtotal * Decimal("0.00")  # adjust if needed
    total = subtotal + tax
    return render_template("invoice_view.html", inv=InvWrapper(inv, subtotal, tax, total))

@app.route("/invoices/<int:iid>/email", methods=["POST"])
def invoice_email(iid):
    inv = Invoice.query.get_or_404(iid)
    subtotal = sum((item.quantity * item.unit_price for item in inv.items), Decimal(0))
    tax = subtotal * Decimal("0.00")
    total = subtotal + tax
    subject = f"Invoice #{inv.id} from Your Company"
    html = render_template("invoice_email.html", inv=InvWrapper(inv, subtotal, tax, total))
    try:
        send_invoice_email(inv.customer.email, subject, html)
        inv.status = "sent"
        db.session.commit()
        flash("Invoice emailed", "success")
    except Exception as e:
        flash(f"Email error: {e}", "error")
    return redirect(url_for("invoice_view", iid=inv.id))

class InvWrapper:
    def __init__(self, inv, subtotal, tax, total):
        self.inv = inv
        self.subtotal = subtotal
        self.tax = tax
        self.total = total

    @property
    def customer(self): return self.inv.customer
    @property
    def items(self): return self.inv.items
    @property
    def id(self): return self.inv.id
    @property
    def date(self): return self.inv.date
    @property
    def due_date(self): return self.inv.due_date
    @property
    def notes(self): return self.inv.notes
    @property
    def status(self): return self.inv.status

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
