import json
import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE = os.path.abspath(os.path.dirname(__file__))
DB = os.path.join(BASE, "milan.db")
UPLOADS = os.path.join(BASE, "static", "uploads")
LANGUAGES = {"en": "English", "hi": "हिंदी", "or": "ଓଡ଼ିଆ"}

app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-before-production"), MAX_CONTENT_LENGTH=12 * 1024 * 1024)
os.makedirs(UPLOADS, exist_ok=True)

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_=None):
    conn = g.pop("db", None)
    if conn: conn.close()

def tr(value, lang, fallback=""):
    try:
        data = json.loads(value or "{}")
        return data.get(lang) or data.get("en") or fallback
    except (TypeError, json.JSONDecodeError):
        return value or fallback

def pack(form, prefix):
    return json.dumps({lang: form.get(f"{prefix}_{lang}", "").strip() for lang in LANGUAGES})

def upload(file):
    if not file or not file.filename: return None
    name = secure_filename(file.filename)
    if not name: return None
    filename = f"{uuid.uuid4().hex}_{name}"
    file.save(os.path.join(UPLOADS, filename))
    return f"uploads/{filename}"

def settings():
    rows = db().execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("login", next=request.url))
        return view(*args, **kwargs)
    return wrapped

def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, category TEXT, name TEXT, description TEXT, specifications TEXT, price TEXT, offer TEXT, image TEXT, video TEXT, active INTEGER DEFAULT 1, created_at TEXT);
    CREATE TABLE IF NOT EXISTS banners(id INTEGER PRIMARY KEY, title TEXT, subtitle TEXT, image TEXT, link TEXT, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS gallery(id INTEGER PRIMARY KEY, caption TEXT, image TEXT, type TEXT DEFAULT 'Factory');
    """)
    if not conn.execute("SELECT 1 FROM admins").fetchone():
        conn.execute("INSERT INTO admins(username,password) VALUES(?,?)", ("admin", generate_password_hash("Milan@2026")))
    defaults = {"company_name":"MILAN ENTERPRISE Pvt Ltd", "phone":"+91 79782 66937", "whatsapp":"917978266937", "email":"sales@milanenterprises.in", "address":"India", "logo":"", "hero_background":""}
    for k,v in defaults.items(): conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k,v))
    # Upgrade the original demo contact details on existing installations.
    for key, old, new in (("company_name", "Milan Enterprises", "MILAN ENTERPRISE Pvt Ltd"), ("company_name", "Milan Private Limited", "MILAN ENTERPRISE Pvt Ltd"), ("phone", "+91 98765 43210", "+91 79782 66937"), ("whatsapp", "919876543210", "917978266937")):
        conn.execute("UPDATE settings SET value=? WHERE key=? AND value=?", (new, key, old))
    if not conn.execute("SELECT 1 FROM products").fetchone():
        seed = [
          ("Hydraulic Paper Plate Machine", {"en":"Single Die Hydraulic Paper Plate Machine","hi":"सिंगल डाई हाइड्रोलिक पेपर प्लेट मशीन","or":"ସିଙ୍ଗଲ ଡାଇ ହାଇଡ୍ରୋଲିକ୍ ପେପର ପ୍ଲେଟ୍ ମେସିନ୍"}, "Single Die", "₹ 48,000", "Festival Offer: Save ₹3,000"),
          ("Hydraulic Paper Plate Machine", {"en":"Double Die Hydraulic Paper Plate Machine","hi":"डबल डाई हाइड्रोलिक पेपर प्लेट मशीन","or":"ଡବଲ ଡାଇ ହାଇଡ୍ରୋଲିକ୍ ପେପର ପ୍ଲେଟ୍ ମେସିନ୍"}, "Double Die", "₹ 78,000", "Free die set with limited offer"),
          ("Paper Cup Machine", {"en":"Automatic Paper Cup Making Machine","hi":"ऑटोमैटिक पेपर कप मेकिंग मशीन","or":"ଅଟୋମେଟିକ୍ ପେପର କପ୍ ମେକିଂ ମେସିନ୍"}, "45–60 cups/min", "₹ 3,25,000", "Diwali business starter offer"),
          ("Automatic Agarbatti Machine", {"en":"Automatic Agarbatti Making Machine","hi":"ऑटोमैटिक अगरबत्ती मेकिंग मशीन","or":"ଅଟୋମେଟିକ୍ ଅଗରବତୀ ମେକିଂ ମେସିନ୍"}, "High-output automatic", "₹ 1,15,000", "Installation support included"),
        ]
        for category, name, spec, price, offer in seed:
            conn.execute("INSERT INTO products(category,name,description,specifications,price,offer,image,video,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (category,json.dumps(name),json.dumps({"en":"Reliable machinery for growing manufacturing businesses.","hi":"बढ़ते मैन्युफैक्चरिंग बिज़नेस के लिए भरोसेमंद मशीनरी।","or":"ବଢୁଥିବା ଉତ୍ପାଦନ ବ୍ୟବସାୟ ପାଇଁ ଭରସାଯୋଗ୍ୟ ମେସିନ୍।"}),json.dumps({"en":spec,"hi":spec,"or":spec}),price,offer,"","",datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

@app.context_processor
def inject():
    lang = request.args.get("lang", session.get("lang", "en"))
    if lang not in LANGUAGES: lang = "en"
    session["lang"] = lang
    return dict(lang=lang, languages=LANGUAGES, tr=tr, site=settings(), now=datetime.now())

@app.route("/")
def home():
    conn = db()
    return render_template("home.html", banners=conn.execute("SELECT * FROM banners WHERE active=1").fetchall(), products=conn.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC").fetchall(), gallery=conn.execute("SELECT * FROM gallery ORDER BY id DESC LIMIT 6").fetchall())

@app.route("/products")
def products():
    category = request.args.get("category")
    query = "SELECT * FROM products WHERE active=1"; args=[]
    if category: query += " AND category=?"; args.append(category)
    return render_template("products.html", products=db().execute(query+" ORDER BY id DESC",args).fetchall(), category=category)

@app.route("/product/<int:id>")
def product(id):
    item = db().execute("SELECT * FROM products WHERE id=? AND active=1", (id,)).fetchone()
    if not item: abort(404)
    return render_template("product.html", item=item)

@app.route("/gallery")
def gallery(): return render_template("gallery.html", gallery=db().execute("SELECT * FROM gallery ORDER BY id DESC").fetchall())

@app.route("/contact", methods=["GET","POST"])
def contact():
    if request.method == "POST":
        flash("Thank you! MILAN ENTERPRISE Pvt Ltd will contact you shortly.", "success")
        return redirect(url_for("contact", lang=request.args.get("lang", "en")))
    return render_template("contact.html")

@app.route("/admin/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = db().execute("SELECT * FROM admins WHERE username=?", (request.form.get("username"),)).fetchone()
        if user and check_password_hash(user["password"], request.form.get("password", "")):
            session["admin_id"] = user["id"]; return redirect(url_for("admin"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/admin/logout")
def logout(): session.clear(); return redirect(url_for("home"))

@app.route("/admin/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(username) < 3 or len(password) < 8:
            flash("Username must have 3 characters and password must have at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif db().execute("SELECT 1 FROM admins WHERE username=?", (username,)).fetchone():
            flash("This username is already registered. Please log in.", "error")
        else:
            db().execute("INSERT INTO admins(username,password) VALUES(?,?)", (username, generate_password_hash(password)))
            db().commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/admin")
@login_required
def admin():
    conn=db(); return render_template("admin.html", products=conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall(), banners=conn.execute("SELECT * FROM banners ORDER BY id DESC").fetchall(), gallery=conn.execute("SELECT * FROM gallery ORDER BY id DESC").fetchall())

@app.route("/admin/product/<int:id>/edit")
@login_required
def edit_product(id):
    item = db().execute("SELECT * FROM products WHERE id=?", (id,)).fetchone()
    if not item: abort(404)
    return render_template("product_edit.html", item=item)

@app.route("/admin/product/save", methods=["POST"])
@login_required
def save_product():
    conn=db(); pid=request.form.get("id"); old=conn.execute("SELECT image FROM products WHERE id=?",(pid,)).fetchone() if pid else None
    image=upload(request.files.get("image")) or (old["image"] if old else "")
    values=(request.form["category"],pack(request.form,"name"),pack(request.form,"description"),pack(request.form,"specifications"),request.form.get("price"),request.form.get("offer"),image,request.form.get("video"),1 if request.form.get("active") else 0)
    if pid: conn.execute("UPDATE products SET category=?,name=?,description=?,specifications=?,price=?,offer=?,image=?,video=?,active=? WHERE id=?", values+(pid,))
    else: conn.execute("INSERT INTO products(category,name,description,specifications,price,offer,image,video,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", values+(datetime.utcnow().isoformat(),))
    conn.commit(); flash("Product saved.","success"); return redirect(url_for("admin"))

@app.route("/admin/banner/save", methods=["POST"])
@login_required
def save_banner():
    image=upload(request.files.get("image")); db().execute("INSERT INTO banners(title,subtitle,image,link,active) VALUES(?,?,?,?,?)",(pack(request.form,"title"),pack(request.form,"subtitle"),image,request.form.get("link"),1)); db().commit(); flash("Festival banner added.","success"); return redirect(url_for("admin"))

@app.route("/admin/gallery/save", methods=["POST"])
@login_required
def save_gallery():
    image=upload(request.files.get("image"));
    if image: db().execute("INSERT INTO gallery(caption,image,type) VALUES(?,?,?)",(pack(request.form,"caption"),image,request.form.get("type","Factory"))); db().commit()
    flash("Gallery image uploaded.","success"); return redirect(url_for("admin"))

@app.route("/admin/settings", methods=["POST"])
@login_required
def save_settings():
    conn=db()
    for key in ("company_name","phone","whatsapp","email","address"):
        conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,request.form.get(key,"")))
    logo=upload(request.files.get("logo"))
    if logo: conn.execute("INSERT INTO settings(key,value) VALUES('logo',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(logo,))
    hero_background=upload(request.files.get("hero_background"))
    if hero_background: conn.execute("INSERT INTO settings(key,value) VALUES('hero_background',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(hero_background,))
    conn.commit(); flash("Company details updated.","success"); return redirect(url_for("admin"))

@app.route("/admin/delete/<kind>/<int:id>", methods=["POST"])
@login_required
def delete(kind,id):
    table={"product":"products","banner":"banners","gallery":"gallery"}.get(kind)
    if table: db().execute(f"DELETE FROM {table} WHERE id=?",(id,)); db().commit(); flash("Item removed.","success")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db(); app.run(debug=True)
else:
    with app.app_context(): init_db()
