from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from datetime import date

app = Flask(__name__)
app.secret_key = "ration-security-2026"

DB = "ration.db"

# Product details
PRODUCTS = {
    "Rice": {"unit": "bag", "label": "bags", "size": 25, "measure": "kg"},
    "Sugar": {"unit": "bag", "label": "bags", "size": 25, "measure": "kg"},
    "Dal": {"unit": "bag", "label": "bags", "size": 25, "measure": "kg"},
    "Oil": {"unit": "packet", "label": "packets", "size": 5, "measure": "litre"}
}

SHOPS = ["Shop 01", "Shop 02", "Shop 03"]


# ---------------- DATABASE ----------------

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():

    con = get_db()
    cur = con.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        shop TEXT
    );

    CREATE TABLE IF NOT EXISTS godown_stock(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product TEXT UNIQUE NOT NULL,
        quantity REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS dispatch(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product TEXT NOT NULL,
        quantity REAL NOT NULL,
        shop TEXT NOT NULL,
        dispatch_date TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS shop_stock(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop TEXT NOT NULL,
        product TEXT NOT NULL,
        quantity REAL DEFAULT 0,
        UNIQUE(shop, product)
    );

    CREATE TABLE IF NOT EXISTS receiving(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop TEXT NOT NULL,
        product TEXT NOT NULL,
        expected REAL NOT NULL,
        received REAL NOT NULL,
        difference REAL NOT NULL,
        status TEXT NOT NULL,
        receive_date TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS families(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ration_card TEXT UNIQUE NOT NULL,
        family_name TEXT NOT NULL,
        shop TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS distribution(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ration_card TEXT NOT NULL,
        shop TEXT NOT NULL,
        product TEXT NOT NULL,
        quantity REAL NOT NULL,
        measure TEXT NOT NULL,
        distribution_date TEXT NOT NULL
    );
    """)

    # -------- GODOWN LOGIN --------

    cur.execute("""
        INSERT OR IGNORE INTO users
        (username,password,role,shop)
        VALUES(?,?,?,?)
    """, ("godown01", "godown123", "godown", None))

    # -------- SHOP LOGINS --------

    for i, shop in enumerate(SHOPS, 1):

        username = f"shop0{i}"
        password = f"shop0{i}123"

        cur.execute("""
            INSERT OR IGNORE INTO users
            (username,password,role,shop)
            VALUES(?,?,?,?)
        """, (username, password, "shop", shop))

    # -------- GODOWN PRODUCTS --------

    for product in PRODUCTS:

        cur.execute("""
            INSERT OR IGNORE INTO godown_stock
            (product,quantity)
            VALUES(?,?)
        """, (product, 0))

    # -------- SHOP STOCK --------

    for shop in SHOPS:

        for product in PRODUCTS:

            cur.execute("""
                INSERT OR IGNORE INTO shop_stock
                (shop,product,quantity)
                VALUES(?,?,?)
            """, (shop, product, 0))

    # -------- 50 MEMBERS FOR EACH SHOP --------

    member_number = 1001

    for shop in SHOPS:

        for number in range(1, 51):

            ration_card = f"RC{member_number}"

            family_name = f"{shop} Family {number:02d}"

            cur.execute("""
                INSERT OR IGNORE INTO families
                (ration_card,family_name,shop)
                VALUES(?,?,?)
            """, (
                ration_card,
                family_name,
                shop
            ))

            # People login
            cur.execute("""
                INSERT OR IGNORE INTO users
                (username,password,role,shop)
                VALUES(?,?,?,?)
            """, (
                ration_card,
                f"{ration_card}@123",
                "people",
                shop
            ))

            member_number += 1

    con.commit()
    con.close()


# ---------------- LOGIN PROTECTION ----------------

def login_required(role=None):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if "username" not in session:
                return redirect(url_for("login"))

            if role and session.get("role") != role:

                flash("Access denied.")

                return redirect(url_for("home"))

            return function(*args, **kwargs)

        return wrapper

    return decorator


# ---------------- HOME ----------------

@app.route("/")
def home():

    role = session.get("role")

    if role == "godown":
        return redirect(url_for("godown"))

    if role == "shop":
        return redirect(url_for("shop"))

    if role == "people":
        return redirect(url_for("people"))

    return redirect(url_for("login"))


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        role = request.form.get("role")
        username = request.form.get("username")
        password = request.form.get("password")

        con = get_db()

        user = con.execute("""
            SELECT *
            FROM users
            WHERE username=?
            AND password=?
            AND role=?
        """, (
            username,
            password,
            role
        )).fetchone()

        con.close()

        if user:

            session.clear()

            session["username"] = user["username"]
            session["role"] = user["role"]
            session["shop"] = user["shop"]

            return redirect(url_for("home"))

        flash("Invalid username, password or portal.")

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# GODOWN
# =========================================================

@app.route("/godown", methods=["GET", "POST"])
@login_required("godown")
def godown():

    con = get_db()

    if request.method == "POST":

        action = request.form.get("action")
        product = request.form.get("product")

        if product not in PRODUCTS:

            flash("Invalid product.")

            return redirect(url_for("godown"))

        # -------- UPDATE STOCK --------

        if action == "stock":

            try:

                quantity = float(
                    request.form.get("quantity", 0)
                )

                if quantity < 0:
                    raise ValueError

            except:

                flash("Enter valid quantity.")

                return redirect(url_for("godown"))

            con.execute("""
                UPDATE godown_stock
                SET quantity=?
                WHERE product=?
            """, (
                quantity,
                product
            ))

            con.commit()

            flash(
                f"{product} stock updated."
            )

        # -------- DISPATCH --------

        elif action == "dispatch":

            try:

                quantity = float(
                    request.form.get("quantity", 0)
                )

                if quantity <= 0:
                    raise ValueError

            except:

                flash("Enter valid dispatch quantity.")

                return redirect(url_for("godown"))

            shop = request.form.get("shop")

            if shop not in SHOPS:

                flash("Invalid ration shop.")

                return redirect(url_for("godown"))

            stock = con.execute("""
                SELECT quantity
                FROM godown_stock
                WHERE product=?
            """, (product,)).fetchone()

            if stock["quantity"] < quantity:

                flash("Not enough godown stock.")

                return redirect(url_for("godown"))

            # Reduce godown stock

            con.execute("""
                UPDATE godown_stock
                SET quantity=quantity-?
                WHERE product=?
            """, (
                quantity,
                product
            ))

            # Add dispatch record

            con.execute("""
                INSERT INTO dispatch
                (product,quantity,shop,dispatch_date)
                VALUES(?,?,?,?)
            """, (
                product,
                quantity,
                shop,
                str(date.today())
            ))

            con.commit()

            flash(
                f"{quantity} {PRODUCTS[product]['label']} dispatched to {shop}."
            )

        return redirect(url_for("godown"))

    stocks = con.execute("""
        SELECT *
        FROM godown_stock
        ORDER BY id
    """).fetchall()

    dispatches = con.execute("""
        SELECT *
        FROM dispatch
        ORDER BY id DESC
    """).fetchall()

    con.close()

    return render_template(
        "godown.html",
        stocks=stocks,
        dispatches=dispatches,
        products=PRODUCTS,
        shops=SHOPS
    )


# =========================================================
# RATION SHOP
# =========================================================

@app.route("/shop", methods=["GET", "POST"])
@login_required("shop")
def shop():

    shop = session["shop"]

    con = get_db()

    if request.method == "POST":

        action = request.form.get("action")

        # =============================================
        # RECEIVE FROM GODOWN
        # =============================================

        if action == "receive":

            product = request.form.get("product")

            try:

                received = float(
                    request.form.get("received", 0)
                )

                if received < 0:
                    raise ValueError

            except:

                flash("Enter valid received quantity.")

                return redirect(url_for("shop"))

            dispatch = con.execute("""
                SELECT *
                FROM dispatch
                WHERE product=?
                AND shop=?
                ORDER BY id DESC
                LIMIT 1
            """, (
                product,
                shop
            )).fetchone()

            if not dispatch:

                flash("No dispatch found.")

                return redirect(url_for("shop"))

            expected = dispatch["quantity"]

            difference = expected - received

            if difference == 0:

                status = "MATCH"

            else:

                status = "MISMATCH"

            # Record receiving

            con.execute("""
                INSERT INTO receiving
                (
                    shop,
                    product,
                    expected,
                    received,
                    difference,
                    status,
                    receive_date
                )
                VALUES(?,?,?,?,?,?,?)
            """, (
                shop,
                product,
                expected,
                received,
                difference,
                status,
                str(date.today())
            ))

            # Add received stock

            con.execute("""
                UPDATE shop_stock
                SET quantity=quantity+?
                WHERE shop=?
                AND product=?
            """, (
                received,
                shop,
                product
            ))

            con.commit()

            flash(
                f"{product}: {status}. "
                f"Expected {expected}, Received {received}."
            )

        # =============================================
        # DISTRIBUTE RATION
        # =============================================

        elif action == "distribute":

            ration_card = request.form.get(
                "ration_card"
            ).strip()

            product = request.form.get(
                "product"
            )

            try:

                quantity = float(
                    request.form.get("quantity", 0)
                )

                if quantity <= 0:
                    raise ValueError

            except:

                flash("Enter valid quantity.")

                return redirect(url_for("shop"))

            # Check member belongs to this shop

            family = con.execute("""
                SELECT *
                FROM families
                WHERE ration_card=?
                AND shop=?
            """, (
                ration_card,
                shop
            )).fetchone()

            if not family:

                flash(
                    "This ration card does not belong to this shop."
                )

                return redirect(url_for("shop"))

            # Product bag/packet size

            size = PRODUCTS[product]["size"]

            stock = con.execute("""
                SELECT quantity
                FROM shop_stock
                WHERE shop=?
                AND product=?
            """, (
                shop,
                product
            )).fetchone()

            # Current stock in kg/litre

            available_measure = (
                stock["quantity"] * size
            )

            if quantity > available_measure:

                flash(
                    f"Not enough {product} stock. "
                    f"Available: {available_measure} "
                    f"{PRODUCTS[product]['measure']}."
                )

                return redirect(url_for("shop"))

            # Reduce stock

            bags_used = quantity / size

            con.execute("""
                UPDATE shop_stock
                SET quantity=quantity-?
                WHERE shop=?
                AND product=?
            """, (
                bags_used,
                shop,
                product
            ))

            # Save distribution

            con.execute("""
                INSERT INTO distribution
                (
                    ration_card,
                    shop,
                    product,
                    quantity,
                    measure,
                    distribution_date
                )
                VALUES(?,?,?,?,?,?)
            """, (
                ration_card,
                shop,
                product,
                quantity,
                PRODUCTS[product]["measure"],
                str(date.today())
            ))

            con.commit()

            flash(
                f"{quantity} "
                f"{PRODUCTS[product]['measure']} "
                f"{product} distributed."
            )

        return redirect(url_for("shop"))

    # Current shop stock

    stocks = con.execute("""
        SELECT *
        FROM shop_stock
        WHERE shop=?
        ORDER BY id
    """, (shop,)).fetchall()

    # Godown dispatches

    dispatches = con.execute("""
        SELECT *
        FROM dispatch
        WHERE shop=?
        ORDER BY id DESC
    """, (shop,)).fetchall()

    # Receive history

    receiving = con.execute("""
        SELECT *
        FROM receiving
        WHERE shop=?
        ORDER BY id DESC
    """, (shop,)).fetchall()

    # 50 members

    families = con.execute("""
        SELECT *
        FROM families
        WHERE shop=?
        ORDER BY id
    """, (shop,)).fetchall()

    # Distribution history

    distributions = con.execute("""
        SELECT *
        FROM distribution
        WHERE shop=?
        ORDER BY id DESC
    """, (shop,)).fetchall()

    con.close()

    return render_template(
        "shop.html",
        shop=shop,
        stocks=stocks,
        dispatches=dispatches,
        receiving=receiving,
        families=families,
        distributions=distributions,
        products=PRODUCTS
    )


# =========================================================
# PEOPLE
# =========================================================

@app.route("/people")
@login_required("people")
def people():

    ration_card = session["username"]

    shop = session["shop"]

    con = get_db()

    # Own member details

    family = con.execute("""
        SELECT *
        FROM families
        WHERE ration_card=?
        AND shop=?
    """, (
        ration_card,
        shop
    )).fetchone()

    # Shop stock visible to people

    stocks = con.execute("""
        SELECT *
        FROM shop_stock
        WHERE shop=?
        ORDER BY id
    """, (shop,)).fetchall()

    # Only own transactions

    distributions = con.execute("""
        SELECT *
        FROM distribution
        WHERE ration_card=?
        AND shop=?
        ORDER BY id DESC
    """, (
        ration_card,
        shop
    )).fetchall()

    con.close()

    return render_template(
        "people.html",
        family=family,
        shop=shop,
        stocks=stocks,
        distributions=distributions,
        products=PRODUCTS
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True
    )