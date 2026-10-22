import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError

PASSWORD = "Tommyset@123"


def connect(db):
    return psycopg2.connect(host="localhost", dbname=db,
                            user="postgres", password=PASSWORD)

# ---------- create database if missing ----------
admin = connect("postgres")
admin.autocommit = True
acur = admin.cursor()
acur.execute("SELECT 1 FROM pg_database WHERE datname = 'perf_demo'")
if not acur.fetchone():
    acur.execute("CREATE DATABASE perf_demo")
admin.close()

conn = connect("perf_demo")
conn.autocommit = True
cur = conn.cursor()

# PART 1: 200000 rows + EXPLAIN ANALYZE before/after index
print("=== PART 1: Index performance ===")
cur.execute("SET max_parallel_workers_per_gather = 0")
cur.execute("DROP TABLE IF EXISTS big_orders")
cur.execute("""
    CREATE TABLE big_orders (
        id INT PRIMARY KEY,
        customer_id INT,
        amount NUMERIC,
        note TEXT
    )
""")
cur.execute("""
    INSERT INTO big_orders
    SELECT i, i, (random()*1000)::numeric(10,2), repeat(md5(i::text), 5)
    FROM generate_series(1, 200000) AS i
""")
cur.execute("ANALYZE big_orders")

QUERY = "SELECT * FROM big_orders WHERE customer_id = 150000"


def run_explain():
    # full text plan (for screenshot)
    cur.execute("EXPLAIN ANALYZE " + QUERY)
    for row in cur.fetchall():
        print("   ", row[0])
    # JSON plan (to read scan type and time)
    cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + QUERY)
    result = cur.fetchone()[0]
    plan = result[0]["Plan"]
    while "Scan" not in plan["Node Type"]:
        plan = plan["Plans"][0]
    return plan["Node Type"].replace("Parallel ", ""), result[0]["Execution Time"]


print("-- BEFORE index")
scan1, t1 = run_explain()
cur.execute("CREATE INDEX idx_big_orders_customer ON big_orders(customer_id)")
cur.execute("ANALYZE big_orders")
print("-- AFTER index")
scan2, t2 = run_explain()

print()
print(f"Before index: {scan1} ~{t1:.1f} ms | After index: {scan2} ~{t2:.1f} ms")

# PART 2: Parameterised get_orders + injection test
print("\n=== PART 2: SQL injection test ===")


def get_orders(customer_id):
    # value is sent as a parameter, never pasted into the SQL text
    cur.execute(
        "SELECT id, customer_id, amount FROM big_orders "
        "WHERE customer_id::text = %s",
        (str(customer_id),),
    )
    return cur.fetchall()


print("Normal input '1' ->", len(get_orders("1")), "rows")
print("Injection input '1 OR 1=1' ->", len(get_orders("1 OR 1=1")), "rows")

# PART 3: Constraint violations
print("\n=== PART 3: Constraint errors ===")
cur.execute("DROP TABLE IF EXISTS staff, depts CASCADE")
cur.execute("CREATE TABLE depts (id INT PRIMARY KEY, name TEXT NOT NULL)")
cur.execute("INSERT INTO depts VALUES (1, 'IT')")
cur.execute("""
    CREATE TABLE staff (
        id INT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        dept_id INT REFERENCES depts(id),
        salary NUMERIC CHECK (salary > 0)
    )
""")
cur.execute("INSERT INTO staff VALUES (1, 'Arun', 'arun@x.com', 1, 50000)")

tests = [
    ("NOT NULL",    "INSERT INTO staff VALUES (2, NULL, 'a@x.com', 1, 40000)"),
    ("UNIQUE",      "INSERT INTO staff VALUES (3, 'Priya', 'arun@x.com', 1, 40000)"),
    ("FOREIGN KEY", "INSERT INTO staff VALUES (4, 'Rahul', 'r@x.com', 99, 40000)"),
    ("CHECK",       "INSERT INTO staff VALUES (5, 'Divya', 'd@x.com', 1, -100)"),
]
for label, sql in tests:
    try:
        cur.execute(sql)
    except psycopg2.Error as e:
        print(f"{label}: {str(e).splitlines()[0]}")

conn.close()