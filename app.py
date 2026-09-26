import os
import shutil

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session
from datetime import datetime, timezone, timedelta
from database import get_db, create_tables

app = Flask(__name__)

app.secret_key = os.environ.get(
    "POLAR_SECRET_KEY",
    "polar-command-demo-secret-key"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False
)

# ==========================================
# SERVICE WORKER
# ==========================================

@app.route("/service-worker.js")
def service_worker():
    return send_from_directory(
        os.path.join(app.static_folder, "js"),
        "service-worker.js",
        mimetype="application/javascript"
    )


create_tables()

# =========================================================
# AUDIT / ACTIVITY LOG
# =========================================================

def create_audit_table():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_email TEXT,

            user_role TEXT,

            action TEXT,

            details TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP

        )
    """)

    conn.commit()
    conn.close()


def log_audit(action, details=""):

    try:

        conn = get_db()

        conn.execute("""
INSERT INTO audit_log
(
    user_email,
    user_role,
    action,
    details,
    created_at
)

VALUES (?, ?, ?, ?, ?)

        """, (

            session.get(
                "email",
                "System"
            ),

            session.get(
                "role",
                "System"
            ),

            action,

                       details,

            datetime.now(
                timezone(timedelta(hours=5, minutes=30))
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        ))

        conn.commit()

        print(
            "AUDIT LOG SAVED:",
            action,
            details
        )

        conn.close()

    except Exception as e:

        print(
            "Audit log error:",
            e
        )


create_audit_table()

# =========================================================
# DATABASE BACKUP
# =========================================================

def create_database_backup():

    try:

        backup_folder = "backups"

        os.makedirs(
            backup_folder,
            exist_ok=True
        )

        timestamp = datetime.now(
            timezone(
                timedelta(hours=5, minutes=30)
            )
        ).strftime(
            "%Y%m%d_%H%M%S"
        )

        backup_filename = (
            "database_backup_" +
            timestamp +
            ".db"
        )

        backup_path = os.path.join(
            backup_folder,
            backup_filename
        )

        shutil.copy2(
            "database.db",
            backup_path
        )

        print(
            "DATABASE BACKUP CREATED:",
            backup_path
        )

        return backup_path

    except Exception as e:

        print(
            "Database backup error:",
            e
        )

        return None


# =========================================================
# INVENTORY RISK CALCULATION
# =========================================================

def calculate_inventory_risk(
    quantity,
    minimum_quantity,
    daily_consumption
):

    quantity = float(quantity or 0)
    minimum_quantity = float(
        minimum_quantity or 0
    )
    daily_consumption = float(
        daily_consumption or 0
    )

    # No stock
    if quantity <= 0:
        return "Critical"

    # Calculate remaining days
    if daily_consumption > 0:

        remaining_days = (
            quantity / daily_consumption
        )

    else:

        remaining_days = 999


    # Risk classification
    if remaining_days <= 3:

        return "Critical"

    elif quantity <= minimum_quantity:

        return "High"

    elif quantity <= (
        minimum_quantity * 1.5
    ):

        return "Medium"

    else:

        return "Low"


# =========================================================
# UPDATE ALL INVENTORY RISK LEVELS
# =========================================================

def recalculate_inventory_risks(conn):

    inventory = conn.execute("""
        SELECT *
        FROM inventory
    """).fetchall()


    for item in inventory:

        risk = calculate_inventory_risk(
            item["quantity"],
            item["minimum_quantity"],
            item["daily_consumption"]
        )

        conn.execute("""
            UPDATE inventory

            SET risk_level = ?

            WHERE id = ?
        """, (
            risk,
            item["id"]
        ))


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "login.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/logout")
def logout():

    log_audit(
        "LOGOUT",
        f"{session.get('role', 'User')} logged out of POLAR COMMAND"
    )

    session.clear()

    return redirect("/")

@app.route("/login", methods=["POST"])
def login():

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    # Demo Commander account
    if (
        email == "commander@polar.local"
        and password == "commander123@"
    ):
        session.pop("demo_mode", None)
        session["logged_in"] = True
        session["email"] = email
        session["role"] = "Commander"

        log_audit(
            "LOGIN",
            "Commander logged into POLAR COMMAND"
        )

        return redirect("/dashboard")

    elif (
        email == "operator@polar.local"
        and password == "operator123@"
    ):
        session.pop("demo_mode", None)
        session["logged_in"] = True
        session["email"] = email
        session["role"] = "Operator"

        log_audit(
            "LOGIN",
            "Operator logged into POLAR COMMAND"
        )

        return redirect("/dashboard")

    return """
    <script>

        alert(
            "Invalid email or password!"
        );

        window.location.href = "/";

    </script>
    """, 401

# =========================================================
# LOGIN PROTECTION
# =========================================================

@app.before_request
def protect_routes():

    public_routes = [
        "/",
        "/login",
        "/demo",
        "/service-worker.js"
    ]

    if request.path.startswith("/static/"):
        return None

    # Public pages
    if request.path in public_routes:
        return None

    # ==========================================
    # DEMO MODE - READ ONLY ACCESS
    # ==========================================

    if session.get("demo_mode"):

        # Block admin / internal pages
        if request.path in [
            "/audit",
            "/conflicts",
            "/backups"
        ]:
            return redirect("/demo")

        # Block data-changing GET routes
        if (
            request.path.startswith("/inventory/delete/")
            or request.path.startswith("/inventory/recalculate")
            or request.path.startswith("/stations/delete/")
            or request.path.startswith("/cargo/delete/")
            or request.path.startswith("/personnel/delete/")
            or request.path.startswith("/equipment/delete/")
            or request.path.startswith("/emergency/delete/")
            or request.path.startswith("/decision/generate/")
            or request.path.startswith("/decision/select/")
            or request.path.startswith("/decision/reset")
            or request.path.startswith("/backup")
            or request.path.startswith("/recovery/")
        ):
            return redirect("/demo")

        # Block all data-changing requests
        if request.method in [
            "POST",
            "PUT",
            "PATCH",
            "DELETE"
        ]:
            return redirect("/demo")

        # Allow read-only pages
        return None

    # ==========================================
    # NORMAL LOGIN REQUIRED
    # ==========================================

    if not session.get("logged_in"):
        return redirect("/")

    # ==========================================
    # OPERATOR ACCESS CONTROL
    # ==========================================

    operator_blocked = [
        "/audit",
        "/conflicts"
    ]

    if (
        session.get("role") == "Operator"
        and request.path in operator_blocked
    ):
        return redirect("/dashboard")

    return None


# =========================================================
# DEMO DASHBOARD
# =========================================================

@app.route("/demo")
def demo():

    session["demo_mode"] = True
    session["logged_in"] = True
    session["role"] = "Demo"
    session["email"] = "demo@polar.local"

    return redirect("/dashboard")

@app.route("/dashboard")
def dashboard():

    if not session.get("logged_in"):
        return redirect("/")

    conn = get_db()

    recalculate_inventory_risks(conn)
    conn.commit()

    stations = conn.execute("""
        SELECT *
        FROM stations
    """).fetchall()

    inventory = conn.execute("""
        SELECT *
        FROM inventory
    """).fetchall()

    personnel = conn.execute("""
        SELECT *
        FROM personnel
    """).fetchall()

    cargo = conn.execute("""
        SELECT *
        FROM cargo
    """).fetchall()

    conn.close()


    # =====================================================
    # DASHBOARD COUNTERS
    # =====================================================

    low_stock_count = 0

    critical_risks = 0

    medium_risks = 0

    high_risks = 0


    for item in inventory:

        quantity = float(
            item["quantity"] or 0
        )

        minimum_quantity = float(
            item["minimum_quantity"] or 0
        )

        risk = calculate_inventory_risk(
            item["quantity"],
            item["minimum_quantity"],
            item["daily_consumption"]
        )


        if risk == "Critical":

            critical_risks += 1


        elif risk == "High":

            high_risks += 1


        elif risk == "Medium":

            medium_risks += 1


        if quantity <= minimum_quantity:

            low_stock_count += 1


    # =====================================================
    # DELAYED CARGO
    # =====================================================

    delayed_cargo_count = sum(

        1

        for c in cargo

        if c["status"] == "Delayed"

    )


    return render_template(

        "dashboard.html",

        stations=stations,

        inventory=inventory,

        personnel=personnel,

        cargo=cargo,

        low_stock_count=low_stock_count,

        critical_risks=critical_risks,

        high_risks=high_risks,

        medium_risks=medium_risks,

        delayed_cargo_count=delayed_cargo_count

    )


# =========================================================
# MANUAL INVENTORY RISK RECALCULATION
# =========================================================

@app.route(
    "/inventory/recalculate"
)
def recalculate_inventory():

    conn = get_db()


    recalculate_inventory_risks(
        conn
    )


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Inventory risk levels recalculated successfully!"
        );

        window.location.href =
            "/module/inventory";

    </script>
    """


# =========================================================
# MODULE ROUTES
# =========================================================

@app.route("/module/<name>")
def module(name):


    # =====================================================
    # STATIONS
    # =====================================================

    if name == "stations":

        conn = get_db()

        stations = conn.execute("""
            SELECT *
            FROM stations
        """).fetchall()

        conn.close()

        return render_template(
            "stations.html",
            stations=stations
        )


    # =====================================================
    # INVENTORY
    # =====================================================

    if name == "inventory":

        conn = get_db()


        recalculate_inventory_risks(
            conn
        )

        conn.commit()


        inventory = conn.execute("""
            SELECT *
            FROM inventory
        """).fetchall()


        conn.close()


        return render_template(
            "inventory.html",
            inventory=inventory
        )


    # =====================================================
    # PERSONNEL
    # =====================================================

    if name == "personnel":

        conn = get_db()

        personnel = conn.execute("""
            SELECT *
            FROM personnel
        """).fetchall()

        conn.close()

        return render_template(
            "personnel.html",
            personnel=personnel
        )


    # =====================================================
    # EQUIPMENT
    # =====================================================

    if name == "equipment":

        conn = get_db()

        equipment = conn.execute("""
            SELECT *
            FROM equipment
        """).fetchall()

        conn.close()

        return render_template(
            "equipment.html",
            equipment=equipment
        )


    # =====================================================
    # CARGO
    # =====================================================

    if name == "cargo":

        conn = get_db()

        cargo = conn.execute("""
            SELECT *
            FROM cargo
        """).fetchall()

        conn.close()

        return render_template(
            "cargo.html",
            cargo=cargo
        )


    # =====================================================
    # EMERGENCY
    # =====================================================

    if name == "emergency":

        conn = get_db()

        emergencies = conn.execute("""
            SELECT *
            FROM emergencies

            ORDER BY id DESC
        """).fetchall()

        conn.close()

        return render_template(
            "emergency.html",
            emergencies=emergencies
        )


    # =====================================================
    # DECISION CENTER
    # =====================================================

    if name == "decision":

        conn = get_db()


        emergencies = conn.execute("""
            SELECT *
            FROM emergencies

            WHERE status = 'Open'

            ORDER BY id DESC
        """).fetchall()


        decisions = conn.execute("""
            SELECT

                decisions.*,

                emergencies.title
                AS emergency_title

            FROM decisions

            LEFT JOIN emergencies

            ON decisions.emergency_id =
               emergencies.id

            ORDER BY decisions.id DESC

        """).fetchall()


        conn.close()


        return render_template(

            "decision.html",

            emergencies=emergencies,

            decisions=decisions

        )


    # =====================================================
    # MODULE TITLES
    # =====================================================

    titles = {

        "stations":
            "Station Management",

        "inventory":
            "Inventory Management",

        "cargo":
            "Cargo Tracking",

        "personnel":
            "Personnel Management",

        "equipment":
            "Equipment Management",

        "emergency":
            "Emergency Center",

        "decision":
            "Decision Center",

        "simulator":
            "What-If Simulator",

        "analytics":
            "Analytics",

        "reports":
            "Mission Reports"

    }


    title = titles.get(
        name,
        "Module"
    )


    return render_template(
        "module.html",
        title=title
    )


# =========================================================
# INVENTORY CRUD
# =========================================================

@app.route(
    "/inventory/add",
    methods=["POST"]
)
def add_inventory():

    conn = get_db()


    conn.execute("""
        INSERT INTO inventory

        (
            item_name,
            station,
            quantity,
            minimum_quantity,
            daily_consumption,
            unit
        )

        VALUES (?, ?, ?, ?, ?, ?)

    """, (

        request.form["item_name"],

        request.form["station"],

        float(
            request.form["quantity"]
        ),

        float(
            request.form[
                "minimum_quantity"
            ]
        ),

        float(
            request.form[
                "daily_consumption"
            ]
        ),

        request.form["unit"]

    ))


    # Recalculate risk
    recalculate_inventory_risks(
        conn
    )


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Inventory added successfully!"
        );

        window.location.href =
            "/module/inventory";

    </script>
    """


# =========================================================
# DELETE INVENTORY
# =========================================================

@app.route(
    "/inventory/delete/<int:item_id>"
)
def delete_inventory(item_id):

    conn = get_db()

    try:

        # Check whether this inventory item
        # is already used in resource history
        usage = conn.execute("""
            SELECT COUNT(*)
            FROM task_resources
            WHERE inventory_id = ?
        """, (item_id,)).fetchone()[0]

        if usage > 0:

            conn.close()

            return """
            <script>

                alert(
                    "This inventory item cannot be deleted because it is already used in Resource History."
                );

                window.location.href =
                    "/module/inventory";

            </script>
            """, 409


        # Safe to delete
        conn.execute("""
            DELETE FROM inventory
            WHERE id = ?
        """, (item_id,))


        conn.commit()
        conn.close()


        return """
        <script>

            alert(
                "Inventory deleted successfully!"
            );

            window.location.href =
                "/module/inventory";

        </script>
        """


    except Exception as e:

        print(
            "Inventory delete error:",
            e
        )

        conn.rollback()
        conn.close()

        return """
        <script>

            alert(
                "Inventory deletion failed. Please try again."
            );

            window.location.href =
                "/module/inventory";

        </script>
        """, 500


# =========================================================
# UPDATE INVENTORY
# =========================================================

@app.route(
    "/inventory/update/<int:item_id>",
    methods=["POST"]
)
def update_inventory(item_id):

    conn = get_db()

    try:

        quantity = float(
            request.form["quantity"]
        )

        conn.execute("""
            UPDATE inventory

            SET quantity = ?

            WHERE id = ?
        """, (
            quantity,
            item_id
        ))

        # Recalculate inventory risk
        recalculate_inventory_risks(
            conn
        )

        conn.commit()
        conn.close()

        return """
        <script>

            alert(
                "Inventory updated!"
            );

            window.location.href =
                "/module/inventory";

        </script>
        """

    except Exception as e:

        print(
            "Inventory update error:",
            e
        )

        conn.rollback()
        conn.close()

        return """
        <script>

            alert(
                "Inventory update failed!"
            );

            window.location.href =
                "/module/inventory";

        </script>
        """, 500


# =========================================================
# STATION CRUD
# =========================================================

@app.route(
    "/stations/add",
    methods=["POST"]
)
def add_station():

    conn = get_db()


    conn.execute("""
        INSERT INTO stations

        (
            name,
            location,
            status
        )

        VALUES (?, ?, ?)

    """, (

        request.form["name"],

        request.form["location"],

        request.form["status"]

    ))


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Station added successfully!"
        );

        window.location.href =
            "/module/stations";

    </script>
    """


# =========================================================
# DELETE STATION
# =========================================================

@app.route(
    "/stations/delete/<int:station_id>"
)
def delete_station(station_id):

    conn = get_db()


    conn.execute(
        """
        DELETE FROM stations
        WHERE id = ?
        """,
        (station_id,)
    )


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Station deleted!"
        );

        window.location.href =
            "/module/stations";

    </script>
    """


# =========================================================
# CARGO CRUD
# =========================================================

# =========================================================
# CARGO CRUD + OPERATIONAL TRACKING
# =========================================================

@app.route(
    "/cargo/add",
    methods=["POST"]
)
def add_cargo():

    conn = get_db()

    try:

        cargo_name = request.form.get(
            "cargo_name", ""
        ).strip()

        source = request.form.get(
            "source", ""
        ).strip()

        destination = request.form.get(
            "destination", ""
        ).strip()

        weight = float(
            request.form.get("weight", 0) or 0
        )

        priority = request.form.get(
            "priority", "Medium"
        )

        # Keep the existing status field for
        # compatibility with dashboard/simulator.
        tracking_status = request.form.get(
            "tracking_status",
            request.form.get("status", "Planned")
        )

        current_location = request.form.get(
            "current_location",
            source
        ).strip()

        if not current_location:
            current_location = source

        last_updated = datetime.now(
            timezone(timedelta(hours=5, minutes=30))
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        conn.execute("""
            INSERT INTO cargo
            (
                cargo_name,
                source,
                destination,
                weight,
                priority,
                status,
                current_location,
                last_updated,
                tracking_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cargo_name,
            source,
            destination,
            weight,
            priority,
            tracking_status,
            current_location,
            last_updated,
            tracking_status
        ))

        conn.commit()
        conn.close()

        return """
        <script>
            alert("Cargo added successfully!");
            window.location.href = "/module/cargo";
        </script>
        """

    except Exception as e:

        print(
            "Cargo add error:",
            e
        )

        conn.rollback()
        conn.close()

        return """
        <script>
            alert("Cargo addition failed. Please try again.");
            window.location.href = "/module/cargo";
        </script>
        """, 500


# =========================================================
# UPDATE CARGO TRACKING
# =========================================================

@app.route(
    "/cargo/update/<int:cargo_id>",
    methods=["POST"]
)
def update_cargo(cargo_id):

    conn = get_db()

    try:

        cargo = conn.execute("""
            SELECT *
            FROM cargo
            WHERE id = ?
        """, (
            cargo_id,
        )).fetchone()

        if cargo is None:

            conn.close()

            return (
                "Cargo not found",
                404
            )

        tracking_status = request.form.get(
            "tracking_status",
            request.form.get(
                "status",
                cargo["tracking_status"]
                if "tracking_status" in cargo.keys()
                and cargo["tracking_status"]
                else cargo["status"]
            )
        )

        current_location = request.form.get(
            "current_location",
            cargo["current_location"]
            if "current_location" in cargo.keys()
            and cargo["current_location"]
            else cargo["source"]
        ).strip()

        if not current_location:

            current_location = (
                cargo["source"] or ""
            )

        last_updated = datetime.now(
            timezone(timedelta(hours=5, minutes=30))
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Keep status and tracking_status synchronized.
        conn.execute("""
            UPDATE cargo
            SET
                status = ?,
                tracking_status = ?,
                current_location = ?,
                last_updated = ?
            WHERE id = ?
        """, (
            tracking_status,
            tracking_status,
            current_location,
            last_updated,
            cargo_id
        ))

        conn.commit()
        conn.close()

        return """
        <script>
            alert("Cargo tracking updated successfully!");
            window.location.href = "/module/cargo";
        </script>
        """

    except Exception as e:

        print(
            "Cargo tracking update error:",
            e
        )

        conn.rollback()
        conn.close()

        return """
        <script>
            alert("Cargo tracking update failed. Please try again.");
            window.location.href = "/module/cargo";
        </script>
        """, 500

@app.route("/cargo/update-tracking/<int:cargo_id>", methods=["POST"])
def update_cargo_tracking(cargo_id):

    tracking_status = request.form["tracking_status"]
    current_location = request.form["current_location"]

    conn = get_db()

    conn.execute("""
        UPDATE cargo
        SET
            tracking_status = ?,
            current_location = ?,
            last_updated = datetime('now')
        WHERE id = ?
    """, (
        tracking_status,
        current_location,
        cargo_id
    ))

    conn.commit()
    conn.close()

    return """
    <script>
        alert("Cargo tracking updated successfully!");
        window.location.href = "/module/cargo";
    </script>
    """

# =========================================================
# DELETE CARGO
# =========================================================

@app.route(
    "/cargo/delete/<int:cargo_id>"
)
def delete_cargo(cargo_id):

    conn = get_db()


    conn.execute(
        """
        DELETE FROM cargo
        WHERE id = ?
        """,
        (cargo_id,)
    )


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Cargo deleted!"
        );

        window.location.href =
            "/module/cargo";

    </script>
    """


# =========================================================
# PERSONNEL CRUD
# =========================================================

@app.route(
    "/personnel/add",
    methods=["POST"]
)
def add_personnel():

    conn = get_db()


    conn.execute("""
        INSERT INTO personnel

        (
            name,
            role,
            station,
            skill,
            availability
        )

        VALUES (?, ?, ?, ?, ?)

    """, (

        request.form["name"],

        request.form["role"],

        request.form["station"],

        request.form["skill"],

        request.form["availability"]

    ))


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Personnel added successfully!"
        );

        window.location.href =
            "/module/personnel";

    </script>
    """


# =========================================================
# DELETE PERSONNEL
# =========================================================

@app.route(
    "/personnel/delete/<int:person_id>"
)
def delete_personnel(person_id):

    conn = get_db()


    conn.execute(
        """
        DELETE FROM personnel
        WHERE id = ?
        """,
        (person_id,)
    )


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Personnel deleted!"
        );

        window.location.href =
            "/module/personnel";

    </script>
    """


# =========================================================
# EQUIPMENT CRUD
# =========================================================

@app.route(
    "/equipment/add",
    methods=["POST"]
)
def add_equipment():

    conn = get_db()


    conn.execute("""
        INSERT INTO equipment

        (
            equipment_name,
            station,
            category,
            condition,
            quantity
        )

        VALUES (?, ?, ?, ?, ?)

    """, (

        request.form["equipment_name"],

        request.form["station"],

        request.form["category"],

        request.form["condition"],

        int(
            request.form["quantity"]
        )

    ))


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Equipment added successfully!"
        );

        window.location.href =
            "/module/equipment";

    </script>
    """


# =========================================================
# DELETE EQUIPMENT
# =========================================================

@app.route(
    "/equipment/delete/<int:equipment_id>"
)
def delete_equipment(
    equipment_id
):

    conn = get_db()


    conn.execute(
        """
        DELETE FROM equipment
        WHERE id = ?
        """,
        (equipment_id,)
    )


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Equipment deleted!"
        );

        window.location.href =
            "/module/equipment";

    </script>
    """


# =========================================================
# EMERGENCY CRUD
# =========================================================

@app.route(
    "/emergency/add",
    methods=["POST"]
)
def add_emergency():

    conn = get_db()


    conn.execute("""
        INSERT INTO emergencies

        (
            title,
            station,
            severity,
            description,
            status
        )

        VALUES (?, ?, ?, ?, ?)

    """, (

        request.form["title"],

        request.form["station"],

        request.form["severity"],

        request.form["description"],

        request.form.get("status", "Open")

    ))


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Emergency reported successfully!"
        );

        window.location.href =
            "/module/emergency";

    </script>
    """


# =========================================================
# DELETE EMERGENCY
# =========================================================

@app.route(
    "/emergency/delete/<int:emergency_id>"
)
def delete_emergency(
    emergency_id
):

    conn = get_db()


    conn.execute(
        """
        DELETE FROM emergencies
        WHERE id = ?
        """,
        (emergency_id,)
    )


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Emergency deleted!"
        );

        window.location.href =
            "/module/emergency";

    </script>
    """


# =========================================================
# EMERGENCY RESOURCE MATCHING
# =========================================================

@app.route(
    "/emergency/match/<int:emergency_id>"
)
def match_resources(
    emergency_id
):

    conn = get_db()


    emergency = conn.execute(
        """
        SELECT *
        FROM emergencies
        WHERE id = ?
        """,
        (emergency_id,)
    ).fetchone()


    if emergency is None:

        conn.close()

        return (
            "Emergency not found",
            404
        )


    station = emergency["station"]


    personnel = conn.execute("""
        SELECT *
        FROM personnel

        WHERE station = ?

        AND availability = 'Available'

    """, (
        station,
    )).fetchall()


    equipment = conn.execute("""
        SELECT *
        FROM equipment

        WHERE station = ?

        AND condition = 'Operational'

        AND quantity > 0

    """, (
        station,
    )).fetchall()


    inventory = conn.execute("""
        SELECT *
        FROM inventory

        WHERE station = ?

        AND quantity > 0

    """, (
        station,
    )).fetchall()


    conn.close()


    return render_template(

        "resource_match.html",

        emergency=emergency,

        personnel=personnel,

        equipment=equipment,

        inventory=inventory

    )


# =========================================================
# GENERATE EMERGENCY DECISIONS
# =========================================================

@app.route(
    "/decision/generate/<int:emergency_id>"
)
def generate_decisions(
    emergency_id
):

    conn = get_db()

    emergency = conn.execute("""
        SELECT *
        FROM emergencies
        WHERE id = ?
    """, (emergency_id,)).fetchone()

    if emergency is None:
        conn.close()

        return (
            "Emergency not found",
            404
        )


    # Remove previous options
    conn.execute("""
        DELETE FROM decisions

        WHERE emergency_id = ?

    """, (
        emergency_id,
    ))


    # =====================================================
    # OPTION A
    # =====================================================

    conn.execute("""
        INSERT INTO decisions

        (
            emergency_id,
            station,
            scenario,
            option_name,
            action,
            risk_level,
            estimated_time,
            resource_needed,
            status
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')

    """, (

        emergency_id,

        emergency["station"],

        emergency["title"],

        "Option A",

        "Use local station resources",

        "Low",

        "2 hours",

        "Available personnel + equipment"

    ))


    # =====================================================
    # OPTION B
    # =====================================================

    conn.execute("""
        INSERT INTO decisions

        (
            emergency_id,
            station,
            scenario,
            option_name,
            action,
            risk_level,
            estimated_time,
            resource_needed,
            status
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')

    """, (

        emergency_id,

        emergency["station"],

        emergency["title"],

        "Option B",

        "Transfer resources from nearby station",

        "Medium",

        "5 hours",

        "Personnel + equipment transfer"

    ))


    # =====================================================
    # OPTION C
    # =====================================================

    conn.execute("""
        INSERT INTO decisions

        (
            emergency_id,
            station,
            scenario,
            option_name,
            action,
            risk_level,
            estimated_time,
            resource_needed,
            status
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')

    """, (

        emergency_id,

        emergency["station"],

        emergency["title"],

        "Option C",

        "Request external resupply",

        "High",

        "24 hours",

        "Cargo + transport"

    ))


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Response options generated!"
        );

        window.location.href =
            "/module/decision";

    </script>
    """


# =========================================================
# SIMULATOR
# =========================================================

@app.route("/simulator")
def simulator():

    conn = get_db()

    stations = conn.execute("""
        SELECT *
        FROM stations
        ORDER BY name
    """).fetchall()

    conn.close()

    return render_template(
        "simulator.html",
        stations=stations
    )


# =========================================================
# RUN SIMULATOR
# =========================================================

@app.route(
    "/simulator/run",
    methods=["POST"]
)
def run_simulator():

    station = request.form["station"]

    delay_days = float(
        request.form["delay_days"]
    )

    conn = get_db()

    # =====================================================
    # GET INVENTORY FOR SELECTED STATION
    # =====================================================

    inventory = conn.execute("""
        SELECT *
        FROM inventory
        WHERE station = ?
    """, (
        station,
    )).fetchall()

    # =====================================================
    # GET ALL STATIONS
    # Keep station dropdown available after simulation
    # =====================================================

    stations = conn.execute("""
        SELECT *
        FROM stations
        ORDER BY name
    """).fetchall()

    conn.close()

    # =====================================================
    # CALCULATE SIMULATION RESULTS
    # =====================================================

    results = []

    for item in inventory:

        current_quantity = float(
            item["quantity"] or 0
        )

        daily_consumption = float(
            item["daily_consumption"] or 0
        )

        expected_quantity = (

            current_quantity

            -

            (
                daily_consumption
                *
                delay_days
            )

        )

        # =================================================
        # RISK CALCULATION
        # =================================================

        if expected_quantity <= 0:

            risk = "Critical"

        elif expected_quantity <= float(
            item["minimum_quantity"] or 0
        ):

            risk = "High"

        elif expected_quantity <= (
            float(item["minimum_quantity"] or 0)
            * 1.5
        ):

            risk = "Medium"

        else:

            risk = "Low"

        # =================================================
        # ADD RESULT
        # =================================================

        results.append({

            "item_name":
                item["item_name"],

            "current_quantity":
                current_quantity,

            "daily_consumption":
                daily_consumption,

            "expected_quantity":
                max(
                    expected_quantity,
                    0
                ),

            "unit":
                item["unit"],

            "risk":
                risk

        })

    # =====================================================
    # RETURN SIMULATOR WITH STATIONS
    # =====================================================

    return render_template(

        "simulator.html",

        stations=stations,

        results=results,

        selected_station=station,

        delay_days=delay_days

    )


# =========================================================
# ALTERNATIVE ACTION GENERATOR
# =========================================================

@app.route(
    "/simulator/alternatives",
    methods=["POST"]
)
def generate_alternatives():

    station = request.form["station"]


    delay_days = float(
        request.form["delay_days"]
    )


    conn = get_db()


    inventory = conn.execute("""
        SELECT *
        FROM inventory

        WHERE station = ?

    """, (
        station,
    )).fetchall()


    other_stations = conn.execute("""
        SELECT *
        FROM stations

        WHERE name != ?

    """, (
        station,
    )).fetchall()


    cargo = conn.execute("""
        SELECT *
        FROM cargo

        WHERE destination = ?

        AND status != 'Delivered'

    """, (
        station,
    )).fetchall()


    conn.close()


    critical_items = []


    for item in inventory:

        expected_quantity = (

            item["quantity"]

            -

            item["daily_consumption"]
            *
            delay_days

        )


        if expected_quantity <= item[
            "minimum_quantity"
        ]:

            critical_items.append({

                "name":
                    item["item_name"],

                "expected":
                    max(
                        expected_quantity,
                        0
                    ),

                "unit":
                    item["unit"]

            })


    alternatives = [

        {

            "name":
                "Option A",

            "title":
                "Transfer Resources From Another Station",

            "description":
                "Move required resources from a nearby station with available stock.",

            "risk":
                "Medium",

            "time":
                "6 hours",

            "resource":
                "Station inventory + transport"

        },

        {

            "name":
                "Option B",

            "title":
                "Expedite Incoming Cargo",

            "description":
                "Prioritize the delayed cargo shipment and arrange faster transport.",

            "risk":
                "Medium",

            "time":
                "12 hours",

            "resource":
                "Cargo + transport"

        },

        {

            "name":
                "Option C",

            "title":
                "Reduce Resource Consumption",

            "description":
                "Temporarily reduce non-critical consumption to extend available stock.",

            "risk":
                "Low",

            "time":
                "Immediate",

            "resource":
                "Existing station resources"

        }

    ]


    return render_template(

        "alternatives.html",

        station=station,

        delay_days=delay_days,

        critical_items=critical_items,

        alternatives=alternatives,

        other_stations=other_stations,

        cargo=cargo

    )


# =========================================================
# OPTION COMPARISON
# =========================================================

@app.route(
    "/simulator/compare",
    methods=["POST"]
)
def compare_alternatives():

    station = request.form["station"]


    delay_days = float(
        request.form["delay_days"]
    )


    conn = get_db()


    inventory = conn.execute("""
        SELECT *
        FROM inventory

        WHERE station = ?

    """, (
        station,
    )).fetchall()


    cargo = conn.execute("""
        SELECT *
        FROM cargo

        WHERE destination = ?

        AND status != 'Delivered'

    """, (
        station,
    )).fetchall()


    other_stations = conn.execute("""
        SELECT *
        FROM stations

        WHERE name != ?

    """, (
        station,
    )).fetchall()


    conn.close()


    critical_count = 0


    for item in inventory:

        expected_quantity = (

            item["quantity"]

            -

            item["daily_consumption"]
            *
            delay_days

        )


        if expected_quantity <= item[
            "minimum_quantity"
        ]:

            critical_count += 1


    incoming_cargo = len(cargo)


    available_stations = len(
        other_stations
    )


    options = []


    # =====================================================
    # OPTION A
    # =====================================================

    risk_a = "Medium"


    if available_stations == 0:

        risk_a = "High"


    options.append({

        "name":
            "Option A",

        "title":
            "Transfer Resources From Another Station",

        "risk":
            risk_a,

        "time":
            "6 hours",

        "resource":
            "Station inventory + transport",

        "availability":
            (
                "Available"

                if available_stations > 0

                else "Limited"
            )

    })


    # =====================================================
    # OPTION B
    # =====================================================

    risk_b = "Medium"


    if incoming_cargo == 0:

        risk_b = "High"


    options.append({

        "name":
            "Option B",

        "title":
            "Expedite Incoming Cargo",

        "risk":
            risk_b,

        "time":
            "12 hours",

        "resource":
            "Cargo + transport",

        "availability":
            (
                "Available"

                if incoming_cargo > 0

                else "No incoming cargo"
            )

    })


    # =====================================================
    # OPTION C
    # =====================================================

    risk_c = "Low"


    if critical_count >= 2:

        risk_c = "Medium"


    options.append({

        "name":
            "Option C",

        "title":
            "Reduce Resource Consumption",

        "risk":
            risk_c,

        "time":
            "Immediate",

        "resource":
            "Existing station resources",

        "availability":
            "Available"

    })


    # =====================================================
    # COMPARISON SCORE
    # =====================================================

    risk_score = {

        "Low": 1,

        "Medium": 2,

        "High": 3

    }


    time_score = {

        "Immediate": 0,

        "6 hours": 6,

        "12 hours": 12

    }


    for option in options:

        option["risk_score"] = (
            risk_score[
                option["risk"]
            ]
        )


        option["time_score"] = (
            time_score[
                option["time"]
            ]
        )


        if option[
            "availability"
        ] == "Available":

            availability_score = 1

        else:

            availability_score = 3


        option[
            "availability_score"
        ] = availability_score


        option[
            "comparison_score"
        ] = (

            option["risk_score"]

            +

            option["time_score"] / 6

            +

            option["availability_score"]

        )


    return render_template(

        "compare.html",

        station=station,

        delay_days=delay_days,

        options=options,

        critical_count=critical_count,

        incoming_cargo=incoming_cargo,

        available_stations=available_stations

    )


# =========================================================
# SEND SIMULATOR OPTIONS TO DECISION CENTER
# =========================================================

@app.route(
    "/simulator/send-to-decision",
    methods=["POST"]
)
def send_simulator_options_to_decision():

    station = request.form["station"]


    delay_days = float(
        request.form["delay_days"]
    )


    conn = get_db()


    # Delete old simulator decisions
    conn.execute("""
        DELETE FROM decisions

        WHERE emergency_id IS NULL

        AND station = ?

    """, (
        station,
    ))


    scenario = (
        f"Inventory delay of "
        f"{delay_days} days"
    )


    # =====================================================
    # OPTION A
    # =====================================================

    conn.execute("""
        INSERT INTO decisions

        (
            emergency_id,
            station,
            scenario,
            option_name,
            action,
            risk_level,
            estimated_time,
            resource_needed,
            status
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')

    """, (

        None,

        station,

        scenario,

        "Option A",

        "Transfer Resources From Another Station",

        "Medium",

        "6 hours",

        "Station inventory + transport"

    ))


    # =====================================================
    # OPTION B
    # =====================================================

    conn.execute("""
        INSERT INTO decisions

        (
            emergency_id,
            station,
            scenario,
            option_name,
            action,
            risk_level,
            estimated_time,
            resource_needed,
            status
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')

    """, (

        None,

        station,

        scenario,

        "Option B",

        "Expedite Incoming Cargo",

        "Medium",

        "12 hours",

        "Cargo + transport"

    ))


    # =====================================================
    # OPTION C
    # =====================================================

    conn.execute("""
        INSERT INTO decisions

        (
            emergency_id,
            station,
            scenario,
            option_name,
            action,
            risk_level,
            estimated_time,
            resource_needed,
            status
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')

    """, (

        None,

        station,

        scenario,

        "Option C",

        "Reduce Resource Consumption",

        "Low",

        "Immediate",

        "Existing station resources"

    ))


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Simulator options sent to Decision Center!"
        );

        window.location.href =
            "/module/decision";

    </script>
    """


# =========================================================
# RESET DECISION TEST DATA
# =========================================================

@app.route(
    "/decision/reset"
)
def reset_decisions():

    conn = get_db()


    conn.execute("""
        DELETE FROM tasks

        WHERE decision_id IN (

            SELECT id
            FROM decisions

        )

    """)


    conn.execute("""
        DELETE FROM decisions
    """)


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Old decision test data reset successfully!"
        );

        window.location.href =
            "/module/decision";

    </script>
    """


# =========================================================
# SELECT DECISION
# =========================================================

@app.route(
    "/decision/select/<int:decision_id>"
)
def select_decision(
    decision_id
):

    conn = get_db()


    decision = conn.execute("""
        SELECT *
        FROM decisions

        WHERE id = ?

    """, (
        decision_id,
    )).fetchone()


    if decision is None:

        conn.close()

        return (
            "Decision not found",
            404
        )


    # =====================================================
    # FIND STATION
    # =====================================================

    if decision["emergency_id"] is not None:

        emergency = conn.execute("""
            SELECT *
            FROM emergencies

            WHERE id = ?

        """, (
            decision["emergency_id"],
        )).fetchone()


        if emergency is None:

            conn.close()

            return (
                "Emergency not found",
                404
            )


        station = emergency["station"]


        # Reset same emergency options

        conn.execute("""
            UPDATE decisions

            SET status = 'Pending'

            WHERE emergency_id = ?

        """, (
            decision["emergency_id"],
        ))


    else:

        station = decision["station"]


        if station is None:

            conn.close()

            return (
                "Station information missing",
                400
            )


        # Reset simulator options
        # of the same scenario

        conn.execute("""
            UPDATE decisions

            SET status = 'Pending'

            WHERE emergency_id IS NULL

            AND station = ?

            AND scenario = ?

        """, (

            station,

            decision["scenario"]

        ))


    # =====================================================
    # SELECT CURRENT OPTION
    # =====================================================

    conn.execute("""
        UPDATE decisions

        SET status = 'Selected'

        WHERE id = ?

    """, (
        decision_id,
    ))


    # =====================================================
    # FIND AVAILABLE PERSON
    # =====================================================

    person = conn.execute("""
        SELECT *
        FROM personnel

        WHERE station = ?

        AND availability = 'Available'

        LIMIT 1

    """, (
        station,
    )).fetchone()


    if person:

        assigned_to = person["name"]

    else:

        assigned_to = "Commander"


    # =====================================================
    # CREATE TASK
    # =====================================================

    existing_task = conn.execute("""
        SELECT *
        FROM tasks

        WHERE decision_id = ?

    """, (
        decision_id,
    )).fetchone()


    if existing_task is None:

        task_title = (

            decision["action"]

            +

            " - "

            +

            station

        )


        conn.execute("""
            INSERT INTO tasks

            (
                emergency_id,
                decision_id,
                task_title,
                assigned_to,
                station,
                status
            )

            VALUES (?, ?, ?, ?, ?, 'Assigned')

        """, (

            decision["emergency_id"],

            decision_id,

            task_title,

            assigned_to,

            station

        ))


    conn.commit()

    conn.close()


    return """
    <script>

        alert(
            "Decision selected and response task created!"
        );

        window.location.href =
            "/tasks";

    </script>
    """


# =========================================================
# TASKS
# =========================================================

@app.route("/tasks")
def tasks():

    conn = get_db()

    # ==========================================
    # TASK + EMERGENCY + DECISION INFORMATION
    # ==========================================

    tasks = conn.execute("""
        SELECT
            tasks.*,

            emergencies.title AS emergency_title,
            emergencies.severity AS emergency_severity,

            decisions.option_name AS decision_option,
            decisions.action AS decision_action,
            decisions.risk_level AS decision_risk,
            decisions.estimated_time AS decision_time

        FROM tasks

        LEFT JOIN emergencies
        ON tasks.emergency_id = emergencies.id

        LEFT JOIN decisions
        ON tasks.decision_id = decisions.id

        ORDER BY tasks.id DESC
    """).fetchall()


    # ==========================================
    # AVAILABLE INVENTORY
    # ==========================================

    inventory = conn.execute("""
        SELECT *
        FROM inventory
        ORDER BY station, item_name
    """).fetchall()


    # ==========================================
    # RESOURCE USAGE HISTORY
    # ==========================================

    resource_usage = conn.execute("""
        SELECT
            task_resources.task_id,
            task_resources.quantity_used,
            task_resources.used_by,
            task_resources.used_at,

            inventory.item_name,
            inventory.unit

        FROM task_resources

        LEFT JOIN inventory
        ON task_resources.inventory_id = inventory.id

        ORDER BY task_resources.id DESC
    """).fetchall()


    conn.close()


    return render_template(
        "tasks.html",
        tasks=tasks,
        inventory=inventory,
        resource_usage=resource_usage
    )


# =========================================================
# APPLY ACTUAL RESOURCE ACTION
# =========================================================

def apply_resource_action(
    conn,
    task
):

    action = ""


    if "action" in task.keys():

        action = task["action"] or ""


    station = task["station"]


    changes = []


    # =====================================================
    # OPTION C
    # REDUCE RESOURCE CONSUMPTION
    # =====================================================

    if action == "Reduce Resource Consumption":

        inventory = conn.execute("""
            SELECT *
            FROM inventory

            WHERE station = ?

        """, (
            station,
        )).fetchall()


        for item in inventory:

            old_consumption = float(
                item["daily_consumption"] or 0
            )


            new_consumption = (
                old_consumption * 0.75
            )


            conn.execute("""
                UPDATE inventory

                SET daily_consumption = ?

                WHERE id = ?

            """, (

                new_consumption,

                item["id"]

            ))


            changes.append(

                item["item_name"]

                +

                ": consumption reduced by 25%"

            )


    # =====================================================
    # OPTION B
    # EXPEDITE INCOMING CARGO
    # =====================================================

    elif action == "Expedite Incoming Cargo":

        cargo_items = conn.execute("""
            SELECT *
            FROM cargo

            WHERE destination = ?

            AND status != 'Delivered'

            ORDER BY id ASC

        """, (
            station,
        )).fetchall()


        if cargo_items:

            for cargo in cargo_items:

                conn.execute("""
                    UPDATE cargo

                    SET status = 'Expedited'

                    WHERE id = ?

                """, (
                    cargo["id"],
                ))


                changes.append(

                    cargo["cargo_name"]

                    +

                    ": cargo expedited"

                )

        else:

            changes.append(
                "No incoming cargo available"
            )


    # =====================================================
    # OPTION A
    # TRANSFER RESOURCES
    # =====================================================

    elif action == (
        "Transfer Resources "
        "From Another Station"
    ):

        target_items = conn.execute("""
            SELECT *
            FROM inventory

            WHERE station = ?

        """, (
            station,
        )).fetchall()


        transferred = False


        for target in target_items:

            source = conn.execute("""
                SELECT *
                FROM inventory

                WHERE item_name = ?

                AND station != ?

                AND quantity > minimum_quantity

                ORDER BY quantity DESC

                LIMIT 1

            """, (

                target["item_name"],

                station

            )).fetchone()


            if source is None:

                continue


            shortage = max(

                target["minimum_quantity"]

                -

                target["quantity"],

                0

            )


            if shortage <= 0:

                shortage = (

                    target["minimum_quantity"]
                    *
                    0.25

                )


            available = max(

                source["quantity"]

                -

                source["minimum_quantity"],

                0

            )


            transfer_amount = min(

                shortage,

                available

            )


            if transfer_amount > 0:

                # Add to target
                conn.execute("""
                    UPDATE inventory

                    SET quantity =
                        quantity + ?

                    WHERE id = ?

                """, (

                    transfer_amount,

                    target["id"]

                ))


                # Remove from source
                conn.execute("""
                    UPDATE inventory

                    SET quantity =
                        quantity - ?

                    WHERE id = ?

                """, (

                    transfer_amount,

                    source["id"]

                ))


                changes.append(

                    str(
                        round(
                            transfer_amount,
                            2
                        )
                    )

                    +

                    " "

                    +

                    target["unit"]

                    +

                    " of "

                    +

                    target["item_name"]

                    +

                    " transferred"

                )


                transferred = True


        if not transferred:

            changes.append(
                "No matching transferable resource found"
            )


    # =====================================================
    # EMERGENCY OPTION A
    # =====================================================

    elif action == "Use local station resources":

        inventory = conn.execute("""
            SELECT *
            FROM inventory

            WHERE station = ?

            AND quantity > 0

        """, (
            station,
        )).fetchall()


        for item in inventory:

            consumption = float(
                item["daily_consumption"] or 0
            )


            amount_used = min(

                consumption,

                item["quantity"]

            )


            if amount_used > 0:

                conn.execute("""
                    UPDATE inventory

                    SET quantity =
                        quantity - ?

                    WHERE id = ?

                """, (

                    amount_used,

                    item["id"]

                ))


                changes.append(

                    item["item_name"]

                    +

                    ": local resource used"

                )


    # =====================================================
    # EMERGENCY OPTION B
    # =====================================================

    elif action == (
        "Transfer resources "
        "from nearby station"
    ):

        target_items = conn.execute("""
            SELECT *
            FROM inventory

            WHERE station = ?

        """, (
            station,
        )).fetchall()


        transferred = False


        for target in target_items:

            source = conn.execute("""
                SELECT *
                FROM inventory

                WHERE item_name = ?

                AND station != ?

                AND quantity > minimum_quantity

                ORDER BY quantity DESC

                LIMIT 1

            """, (

                target["item_name"],

                station

            )).fetchone()


            if source is None:

                continue


            transfer_amount = min(

                source["quantity"]
                -
                source["minimum_quantity"],

                max(

                    target["minimum_quantity"]
                    -
                    target["quantity"],

                    0

                )

            )


            if transfer_amount > 0:

                conn.execute("""
                    UPDATE inventory

                    SET quantity =
                        quantity + ?

                    WHERE id = ?

                """, (

                    transfer_amount,

                    target["id"]

                ))


                conn.execute("""
                    UPDATE inventory

                    SET quantity =
                        quantity - ?

                    WHERE id = ?

                """, (

                    transfer_amount,

                    source["id"]

                ))


                changes.append(
                    "Resource transfer completed"
                )


                transferred = True


        if not transferred:

            changes.append(
                "No transferable matching resource found"
            )


    # =====================================================
    # EMERGENCY OPTION C
    # =====================================================

    elif action == "Request external resupply":

        cargo_items = conn.execute("""
            SELECT *
            FROM cargo

            WHERE destination = ?

            AND status != 'Delivered'

        """, (
            station,
        )).fetchall()


        if cargo_items:

            for cargo in cargo_items:

                conn.execute("""
                    UPDATE cargo

                    SET status = 'Requested'

                    WHERE id = ?

                """, (
                    cargo["id"],
                ))


                changes.append(

                    cargo["cargo_name"]

                    +

                    ": resupply requested"

                )

        else:

            changes.append(
                "External resupply request created"
            )


    # =====================================================
    # DEFAULT
    # =====================================================

    else:

        changes.append(
            "Task completed without resource modification"
        )


    # =====================================================
    # RECALCULATE INVENTORY RISK
    # =====================================================

    recalculate_inventory_risks(
        conn
    )


    return changes


# =========================================================
# UPDATE TASK STATUS
# =========================================================

@app.route(
    "/tasks/update/<int:task_id>/<status>"
)
def update_task_status(
    task_id,
    status
):

    allowed_status = [

        "Assigned",

        "In Progress",

        "Completed"

    ]


    if status not in allowed_status:

        return (
            "Invalid task status",
            400
        )


    conn = get_db()


    # =====================================================
    # FIND TASK
    # =====================================================

    task = conn.execute("""
        SELECT

            tasks.*,

            decisions.action

        FROM tasks

        LEFT JOIN decisions

        ON tasks.decision_id =
           decisions.id

        WHERE tasks.id = ?

    """, (
        task_id,
    )).fetchone()


    if task is None:

        conn.close()

        return (
            "Task not found",
            404
        )


    # =====================================================
    # UPDATE TASK STATUS
    # =====================================================

    conn.execute("""
        UPDATE tasks

        SET status = ?

        WHERE id = ?

    """, (

        status,

        task_id

    ))


    # =====================================================
    # PERSONNEL BUSY
    # =====================================================

    if task["assigned_to"] != "Commander":

        if status == "In Progress":

            conn.execute("""
                UPDATE personnel

                SET availability = 'Busy'

                WHERE name = ?

            """, (
                task["assigned_to"],
            ))


    # =====================================================
    # COMPLETED
    # =====================================================

    if status == "Completed":


        # -------------------------------------------------
        # PERSONNEL AVAILABLE
        # -------------------------------------------------

        if task["assigned_to"] != "Commander":

            conn.execute("""
                UPDATE personnel

                SET availability = 'Available'

                WHERE name = ?

            """, (
                task["assigned_to"],
            ))


        # -------------------------------------------------
        # APPLY RESOURCE ACTION
        # -------------------------------------------------

        changes = apply_resource_action(

            conn,

            task

        )


        # -------------------------------------------------
        # EMERGENCY RESOLVED
        # -------------------------------------------------

        if task["emergency_id"] is not None:

            conn.execute("""
                UPDATE emergencies

                SET status = 'Resolved'

                WHERE id = ?

            """, (
                task["emergency_id"],
            ))


        # -------------------------------------------------
        # DECISION COMPLETED
        # -------------------------------------------------

        conn.execute("""
            UPDATE decisions

            SET status = 'Completed'

            WHERE id = ?

        """, (
            task["decision_id"],
        ))


    else:

        changes = []


    # =====================================================
    # SAVE DATABASE
    # =====================================================

    conn.commit()

    conn.close()


    # =====================================================
    # RESULT MESSAGE
    # =====================================================

    if changes:

        change_text = "\\n".join(
            changes
        )

    else:

        change_text = (
            "Task status updated successfully."
        )


    return f"""
    <script>

        alert(
            "Task updated successfully!\\n\\n"
            + {change_text!r}
        );

        window.location.href =
    "/tasks?task_status={status}&task_id={task_id}";

    </script>
    """


# =========================================================
# RUN APPLICATION
# =========================================================

@app.route("/tasks/use-resource/<int:task_id>", methods=["POST"])
def use_task_resource(task_id):

    inventory_id = request.form.get("inventory_id")
    quantity_used = request.form.get("quantity_used")

    if not inventory_id or not quantity_used:
        return redirect("/tasks")

    conn = None

    try:

        quantity_used = float(quantity_used)

        if quantity_used <= 0:
            return redirect("/tasks")

        conn = get_db()
        cursor = conn.cursor()

        # Find task
        task = cursor.execute("""
            SELECT *
            FROM tasks
            WHERE id = ?
        """, (task_id,)).fetchone()

        if not task:
            conn.close()
            return redirect("/tasks")

        # Find inventory
        inventory = cursor.execute("""
            SELECT *
            FROM inventory
            WHERE id = ?
        """, (inventory_id,)).fetchone()

        if not inventory:
            conn.close()
            return redirect("/tasks")

        current_quantity = float(inventory["quantity"])

        # Prevent over-use
        if quantity_used > current_quantity:
            conn.close()
            return redirect("/tasks")

        # Start transaction

        # New quantity
        new_quantity = current_quantity - quantity_used

        # Recalculate risk
        risk = calculate_inventory_risk(
            new_quantity,
            inventory["minimum_quantity"],
            inventory["daily_consumption"]
        )

        # Update inventory
        cursor.execute("""
            UPDATE inventory
            SET quantity = ?,
                risk_level = ?
            WHERE id = ?
        """, (
            new_quantity,
            risk,
            inventory_id
        ))

        # Save usage history
        cursor.execute("""
    INSERT INTO task_resources
    (
        task_id,
        inventory_id,
        quantity_used,
        used_by,
        used_at
    )
    VALUES (?, ?, ?, ?, datetime('now', '+5 hours', '+30 minutes'))
""", (
    task_id,
    inventory_id,
    quantity_used,
    task["assigned_to"]
))

        conn.commit()
        conn.close()

    except Exception as e:

        import traceback
        traceback.print_exc()

        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass

    return redirect("/tasks")

@app.route("/resource-history")
def resource_history():

    conn = get_db()

    history = conn.execute("""
        SELECT
            tr.id,
            tr.quantity_used,
            tr.used_by,
            tr.used_at,
            t.task_title,
            t.station,
            i.item_name,
            i.unit
        FROM task_resources tr

        JOIN tasks t
            ON tr.task_id = t.id

        JOIN inventory i
            ON tr.inventory_id = i.id

        ORDER BY tr.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "resource_history.html",
        history=history
    )

# =========================================================
# OFFLINE DATA API
# =========================================================

@app.route("/api/offline-data")
def offline_data():

    conn = get_db()

    data = {}

    table_mapping = {
        "stations": "stations",
        "inventory": "inventory",
        "cargo": "cargo",
        "personnel": "personnel",
        "equipment": "equipment",
        "emergencies": "emergencies",
        "tasks": "tasks",
        "decisions": "decisions",
        "resource_usage": "task_resources"
    }

    try:

        for local_store, database_table in table_mapping.items():

            rows = conn.execute(
                f"SELECT * FROM {database_table}"
            ).fetchall()

            data[local_store] = [
                dict(row) for row in rows
            ]

        conn.close()

        return data

    except Exception as e:

        print("Offline data API error:", e)

        conn.close()

        return {
            "error": "Unable to load offline data"
        }, 500

    # =========================================================
# OFFLINE SYNC API
# =========================================================

@app.route("/api/sync", methods=["POST"])
def sync_offline_data():

    conn = None

    try:

        payload = request.get_json()

        if not payload:
            return {
                "success": False,
                "message": "No sync data received"
            }, 400

        store = payload.get("store")
        action = payload.get("action")
        data = payload.get("data", {})
        local_id = payload.get("local_id")

        if not store or not action:
            return {
                "success": False,
                "message": "Invalid sync request"
            }, 400

        conn = get_db()
        cursor = conn.cursor()

        # =================================================
        # INVENTORY CREATE
        # =================================================

        if store == "inventory" and action == "CREATE":

            item_name = data.get("item_name")
            station = data.get("station")
            quantity = float(data.get("quantity", 0))
            minimum_quantity = float(
                data.get("minimum_quantity", 0)
            )
            daily_consumption = float(
                data.get("daily_consumption", 0)
            )
            unit = data.get("unit")

            risk_level = calculate_inventory_risk(
                quantity,
                minimum_quantity,
                daily_consumption
            )

            cursor.execute("""
                INSERT INTO inventory
                (
                    item_name,
                    station,
                    quantity,
                    minimum_quantity,
                    daily_consumption,
                    unit,
                    risk_level
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item_name,
                station,
                quantity,
                minimum_quantity,
                daily_consumption,
                unit,
                risk_level
            ))

            server_id = cursor.lastrowid

            conn.commit()

            conn.close()

            return {
                "success": True,
                "action": "CREATE",
                "local_id": local_id,
                "server_id": server_id
            }


        # =================================================
# INVENTORY UPDATE + CONFLICT DETECTION
# =================================================

        if store == "inventory" and action == "UPDATE":

            record_id = data.get("id")

            if not record_id:
                conn.close()

                return {
                    "success": False,
                    "message": "Inventory ID missing"
                }, 400


    # ---------------------------------------------
    # Get current server record
    # ---------------------------------------------

            server_record = cursor.execute("""
                SELECT *
                FROM inventory
                WHERE id = ?
            """, (record_id,)).fetchone()


            if not server_record:

                conn.close()

                return {
                    "success": False,
                    "message": "Inventory record not found",
                    "conflict": True,
                    "conflict_type": "RECORD_NOT_FOUND"
                }, 409


            server_quantity = float(server_record["quantity"])

            local_quantity = float(data.get("quantity", 0))


    # ---------------------------------------------
    # Conflict detection
    # ---------------------------------------------

            base_quantity = data.get("base_quantity")


            if base_quantity is not None:

                base_quantity = float(base_quantity)

                print("SYNC DEBUG:")
                print("Server Quantity:", server_quantity)
                print("Local Quantity:", local_quantity)
                print("Base Quantity:", base_quantity)
                print("Full Data:", data)


        # Server changed after local copy
                if server_quantity != base_quantity:

                    conn.close()

                    return {
                        "success": False,
                        "conflict": True,
                        "conflict_type": "QUANTITY_CHANGED",

                        "server_record": dict(server_record),

                        "local_record": data
                    }, 409


    # ---------------------------------------------
    # No conflict → update server
    # ---------------------------------------------

            minimum_quantity = float(data.get(
                "minimum_quantity", server_record["minimum_quantity"]
            ))

            daily_consumption = float(data.get(
                "daily_consumption", server_record["daily_consumption"]
            ))


            risk_level = calculate_inventory_risk(
                local_quantity, minimum_quantity, daily_consumption
            )


            cursor.execute("""
                UPDATE inventory
                SET quantity = ?, risk_level = ?
                WHERE id = ?
            """, (local_quantity, risk_level, record_id))


            conn.commit()
            conn.close()


            return {
                "success": True,
                "action": "UPDATE",
                "server_id": record_id
            }


        # =================================================
        # INVENTORY DELETE
        # =================================================

        if store == "inventory" and action == "DELETE":

            record_id = data.get("id")

            if not record_id:
                conn.close()

                return {
                    "success": False,
                    "message": "Inventory ID missing"
                }, 400

            cursor.execute("""
                DELETE FROM inventory
                WHERE id = ?
            """, (record_id,))

            if cursor.rowcount == 0:

                conn.close()

                return {
                    "success": False,
                    "message": "Inventory record not found",
                    "conflict": True
                }, 409

            conn.commit()

            conn.close()

            return {
                "success": True,
                "action": "DELETE",
                "server_id": record_id
            }


        conn.close()

        return {
            "success": False,
            "message": "Unsupported sync operation"
        }, 400


    except Exception as e:

        print(
            "Offline synchronization error:",
            e
        )

        if conn:

            try:
                conn.rollback()
                conn.close()
            except:
                pass

        return {
            "success": False,
            "message": "Server synchronization failed"
        }, 500

# =========================================================
# DATABASE BACKUP ROUTE
# =========================================================

@app.route("/backup")
def backup_database():

    if session.get("role") != "Commander":
        return redirect("/dashboard")

    backup_path = create_database_backup()

    if backup_path:

        log_audit(
            "DATABASE_BACKUP",
            "SQLite database backup created"
        )

    return redirect("/dashboard")

# =========================================================
# BACKUP LIST ROUTE
# =========================================================

@app.route("/backups")
def list_backups():

    if session.get("role") not in ["Commander", "Operator"]:
        return redirect("/dashboard")

    backup_folder = "backups"

    os.makedirs(
        backup_folder,
        exist_ok=True
    )

    backups = []

    for filename in os.listdir(backup_folder):

        if filename.endswith(".db"):

            backup_path = os.path.join(
                backup_folder,
                filename
            )

            backups.append({
                "filename": filename,
                "created": datetime.fromtimestamp(
                    os.path.getmtime(backup_path),
                    timezone(
                        timedelta(hours=5, minutes=30)
                    )
                ).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            })

    backups.sort(
        key=lambda x: x["filename"],
        reverse=True
    )

    return render_template(
        "backups.html",
        backups=backups,
        can_manage_backups=(session.get("role") == "Commander")
    )

# =========================================================
# DATABASE RECOVERY ROUTE
# =========================================================

@app.route("/recovery/<filename>")
def recover_database(filename):

    if session.get("role") != "Commander":
        return redirect("/dashboard")

    backup_folder = "backups"

    backup_path = os.path.join(
        backup_folder,
        filename
    )

    # Security check
    if not os.path.abspath(backup_path).startswith(
        os.path.abspath(backup_folder)
    ):
        return redirect("/dashboard")

    if not os.path.exists(backup_path):
        return redirect("/dashboard")

    try:

        # Create safety backup before recovery
        create_database_backup()

        # Restore selected backup
        shutil.copy2(
            backup_path,
            "database.db"
        )

        log_audit(
            "DATABASE_RECOVERY",
            "Database restored from backup: " + filename
        )

        print(
            "DATABASE RECOVERY SUCCESSFUL:",
            filename
        )

    except Exception as e:

        print(
            "Database recovery error:",
            e
        )

    return redirect("/dashboard")
    

# =========================================================
# AUDIT LOG PAGE
# =========================================================

@app.route("/audit")
def audit():

    conn = get_db()

    logs = conn.execute("""
        SELECT
            id,
            user_email,
            user_role,
            action,
            details,
            created_at
        FROM audit_log
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "audit.html",
        logs=logs
    )

# =========================================================
# CONFLICT RESOLUTION PAGE
# =========================================================

@app.route("/conflicts")
def conflicts_page():

    return render_template(
        "conflicts.html"
    )

# =========================================================
# CONFLICT RESOLUTION API
# =========================================================

@app.route(
    "/api/conflict/resolve",
    methods=["POST"]
)
def resolve_conflict():

    conn = None

    try:

        payload = request.get_json()

        if not payload:

            return {
                "success": False,
                "message": "No resolution data received"
            }, 400


        decision =payload.get("decision")


        record = payload.get("record")


        conflict_id = payload.get("conflict_id")


        if decision not in [
            "LOCAL",
            "SERVER"
        ]:

            return {
                "success": False,
                "message": "Invalid conflict decision"
            }, 400


        if not record:

            return {
                "success": False,
                "message": "No record supplied"
            }, 400


        conn = get_db()

        cursor = conn.cursor()


        record_id = record.get("id")


        if not record_id:

            conn.close()

            return {
                "success": False,
                "message": "Record ID missing"
            }, 400


        quantity =float(
                record.get(
                    "quantity",
                    0
                )
            )


        minimum_quantity = float(
                record.get(
                    "minimum_quantity",
                    0
                )
            )


        daily_consumption = float(
                record.get(
                    "daily_consumption",
                    0
                )
            )


        risk_level = calculate_inventory_risk(
                quantity,
                minimum_quantity,
                daily_consumption
            )


        cursor.execute("""
            UPDATE inventory

            SET quantity = ?,
                risk_level = ?

            WHERE id = ?
        """, (
            quantity,
            risk_level,
            record_id
        ))


        if cursor.rowcount == 0:

            conn.close()

            return {
                "success": False,
                "message":
                    "Inventory record not found"
            }, 404


        conn.commit()

        conn.close()


        return {

            "success": True,

            "message":
                "Conflict resolved successfully",

            "decision":
                decision,

            "conflict_id":
                conflict_id,

            "server_id":
                record_id

        }


    except Exception as e:

        print(
            "Conflict resolution error:",
            e
        )


        if conn:

            try:

                conn.rollback()
                conn.close()

            except:

                pass


        return {

            "success": False,

            "message":
                "Conflict resolution failed"

        }, 500

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
