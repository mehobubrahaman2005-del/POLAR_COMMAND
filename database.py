import sqlite3


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    # Foreign key support
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# ============================================================
# CREATE ALL TABLES
# ============================================================

def create_tables():

    conn = get_db()
    cursor = conn.cursor()

    # ========================================================
    # STATIONS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            status TEXT DEFAULT 'Normal'
        )
    """)

    # ========================================================
    # INVENTORY
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            station TEXT,
            quantity REAL DEFAULT 0,
            minimum_quantity REAL DEFAULT 0,
            daily_consumption REAL DEFAULT 0,
            unit TEXT,
            risk_level TEXT DEFAULT 'Low'
        )
    """)

    # ========================================================
    # PERSONNEL
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personnel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT,
            station TEXT,
            skill TEXT,
            availability TEXT DEFAULT 'Available'
        )
    """)

    # ========================================================
    # CARGO
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cargo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cargo_name TEXT NOT NULL,
            source TEXT,
            destination TEXT,
            weight REAL,
            priority TEXT,
            status TEXT DEFAULT 'Preparing'
        )
    """)

    # ========================================================
    # EQUIPMENT
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT NOT NULL,
            station TEXT,
            category TEXT,
            condition TEXT DEFAULT 'Operational',
            quantity INTEGER DEFAULT 1
        )
    """)

    # ========================================================
    # EMERGENCIES
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            station TEXT,
            severity TEXT DEFAULT 'Medium',
            description TEXT,
            status TEXT DEFAULT 'Open'
        )
    """)

    # ========================================================
    # DECISIONS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emergency_id INTEGER,
            station TEXT,
            scenario TEXT,
            option_name TEXT,
            action TEXT,
            risk_level TEXT,
            estimated_time TEXT,
            resource_needed TEXT,
            status TEXT DEFAULT 'Pending'
        )
    """)

    # ========================================================
    # TASKS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emergency_id INTEGER,
            decision_id INTEGER,
            task_title TEXT NOT NULL,
            assigned_to TEXT,
            station TEXT,
            status TEXT DEFAULT 'Assigned'
        )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        inventory_id INTEGER NOT NULL,
        quantity_used REAL NOT NULL
    )
""")

        # Resource usage history columns
    resource_columns = [
        row[1]
        for row in cursor.execute(
            "PRAGMA table_info(task_resources)"
        ).fetchall()
    ]

    if "used_by" not in resource_columns:
        cursor.execute("""
            ALTER TABLE task_resources
            ADD COLUMN used_by TEXT
        """)

    if "used_at" not in resource_columns:
        cursor.execute("""
            ALTER TABLE task_resources
            ADD COLUMN used_at TEXT
        """)

    # ========================================================
    # TASK RESOURCES
    #
    # এই table future resource usage tracking-এর জন্য।
    # কোন task-এ কোন inventory item কত quantity ব্যবহার হয়েছে
    # সেটা এখানে রাখা যাবে।
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            inventory_id INTEGER NOT NULL,
            quantity_used REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (inventory_id) REFERENCES inventory(id)
        )
    """)

    # ========================================================
    # UPDATE OLD DATABASE
    # ========================================================
    #
    # পুরনো database.db থাকলে missing columns add করা হবে।
    # Existing data delete হবে না।
    #
    # ========================================================

    # --------------------------------------------------------
    # DECISIONS TABLE COLUMNS
    # --------------------------------------------------------

    decision_columns = [
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(decisions)"
        ).fetchall()
    ]

    if "station" not in decision_columns:
        cursor.execute("""
            ALTER TABLE decisions
            ADD COLUMN station TEXT
        """)

    if "scenario" not in decision_columns:
        cursor.execute("""
            ALTER TABLE decisions
            ADD COLUMN scenario TEXT
        """)

    # --------------------------------------------------------
    # INVENTORY TABLE COLUMNS
    # --------------------------------------------------------

    inventory_columns = [
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(inventory)"
        ).fetchall()
    ]

    if "risk_level" not in inventory_columns:
        cursor.execute("""
            ALTER TABLE inventory
            ADD COLUMN risk_level TEXT DEFAULT 'Low'
        """)

            # --------------------------------------------------------
    # CARGO TRACKING TABLE COLUMNS
    # --------------------------------------------------------

    cargo_columns = [
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(cargo)"
        ).fetchall()
    ]

    if "current_location" not in cargo_columns:
        cursor.execute("""
            ALTER TABLE cargo
            ADD COLUMN current_location TEXT
        """)

    if "last_updated" not in cargo_columns:
        cursor.execute("""
            ALTER TABLE cargo
            ADD COLUMN last_updated TEXT
        """)

    if "tracking_status" not in cargo_columns:
        cursor.execute("""
            ALTER TABLE cargo
            ADD COLUMN tracking_status TEXT DEFAULT 'Planned'
        """)

    # ========================================================
    # SAMPLE STATIONS
    # ========================================================

    cursor.execute("""
        INSERT INTO stations
        (name, location, status)

        SELECT
            'Bharati Antarctica',
            'Antarctica',
            'Normal'

        WHERE NOT EXISTS (
            SELECT 1
            FROM stations
            WHERE name = 'Bharati Antarctica'
        )
    """)

    cursor.execute("""
        INSERT INTO stations
        (name, location, status)

        SELECT
            'Maitri Antarctica',
            'Antarctica',
            'Warning'

        WHERE NOT EXISTS (
            SELECT 1
            FROM stations
            WHERE name = 'Maitri Antarctica'
        )
    """)

    cursor.execute("""
        INSERT INTO stations
        (name, location, status)

        SELECT
            'Himadri Arctic',
            'Arctic',
            'Normal'

        WHERE NOT EXISTS (
            SELECT 1
            FROM stations
            WHERE name = 'Himadri Arctic'
        )
    """)

    cursor.execute("""
        INSERT INTO stations
        (name, location, status)

        SELECT
            'Research Station Antarctica',
            'Antarctica',
            'Critical'

        WHERE NOT EXISTS (
            SELECT 1
            FROM stations
            WHERE name = 'Research Station Antarctica'
        )
    """)

    # ========================================================
    # SAMPLE INVENTORY
    # ========================================================

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

        SELECT
            'Diesel Fuel',
            'Bharati Antarctica',
            800,
            300,
            120,
            'L',
            'Low'

        WHERE NOT EXISTS (
            SELECT 1
            FROM inventory
            WHERE item_name = 'Diesel Fuel'
            AND station = 'Bharati Antarctica'
        )
    """)

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

        SELECT
            'Medical Kit',
            'Maitri Antarctica',
            15,
            10,
            1,
            'Unit',
            'Low'

        WHERE NOT EXISTS (
            SELECT 1
            FROM inventory
            WHERE item_name = 'Medical Kit'
            AND station = 'Maitri Antarctica'
        )
    """)

    # ========================================================
    # SAMPLE PERSONNEL
    # ========================================================

    cursor.execute("""
        INSERT INTO personnel
        (
            name,
            role,
            station,
            skill,
            availability
        )

        SELECT
            'Dr. Arjun',
            'Medical Officer',
            'Bharati Antarctica',
            'Medical',
            'Available'

        WHERE NOT EXISTS (
            SELECT 1
            FROM personnel
            WHERE name = 'Dr. Arjun'
        )
    """)

    cursor.execute("""
        INSERT INTO personnel
        (
            name,
            role,
            station,
            skill,
            availability
        )

        SELECT
            'Rahul Das',
            'Engineer',
            'Maitri Antarctica',
            'Mechanical',
            'Available'

        WHERE NOT EXISTS (
            SELECT 1
            FROM personnel
            WHERE name = 'Rahul Das'
        )
    """)

    # ========================================================
    # SAMPLE CARGO
    # ========================================================

    cursor.execute("""
        INSERT INTO cargo
        (
            cargo_name,
            source,
            destination,
            weight,
            priority,
            status
        )

        SELECT
            'Fuel Shipment',
            'Port',
            'Bharati Antarctica',
            5000,
            'High',
            'In Transit'

        WHERE NOT EXISTS (
            SELECT 1
            FROM cargo
            WHERE cargo_name = 'Fuel Shipment'
        )
    """)

    # ========================================================
    # COMMIT DATABASE CHANGES
    # ========================================================

    conn.commit()
    conn.close()


# ============================================================
# RUN DATABASE SETUP
# ============================================================

if __name__ == "__main__":

    create_tables()

    print("Database created successfully!")