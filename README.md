# Week 2 Assessment: Data + SQL + APIs

This repository holds all four tasks of the Week 2 assessment.

| Task | Topic | Files |
|------|-------|-------|
| Task 1 | SQL Analysis | `analysis.sql` |
| Task 2 | Performance and Safety | `task2_performance.sql`, `scripts/get_orders.py` |
| Task 3 | ORM, Migrations and Transactions | `ORM_Migration_Trans/` |
| Task 4 | Secured API with Integration Tests | `src/`, `tests/`, `scripts/run_all.py` |

## Project structure

```
Week2_Assessment_SQL/
├── README.md
├── pyproject.toml              # dependencies + pytest config
├── .env.example                # template for the Task 4 settings
├── .gitignore
│
├── analysis.sql                # Task 1: six numbered queries
├── task2_performance.sql       # Task 2: index timings + constraint errors
│
├── ORM_Migration_Trans/        # Task 3
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/           # 2 migrations: initial schema, add phone
│   ├── models.py               # Customer, Order, Product + connection pool
│   ├── orders_service.py       # place_order() in one transaction
│   └── demo.py                 # atomicity proof + MongoDB aggregation
│
├── src/                        # Task 4 application code
│   ├── __init__.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── main.py                 # FastAPI app (customers, webhook, mock token)
│   └── client.py               # fetch_all()
│
├── tests/                      # Task 4 integration tests
│   ├── conftest.py             # separate test database + fixtures
│   └── test_api.py             # 8 tests
│
└── scripts/
    ├── get_orders.py           # Task 2: parameterised query + injection test
    ├── run_all.py              # Task 4: prints the expected output
    └── demo_client.py          # Task 4: fetch_all demo with a fake session
```

## Databases used

| Database | Used by | Why |
|----------|---------|-----|
| `week2_sql` (PostgreSQL) | Task 1, Task 2 | The scripts drop and recreate tables named `customers`, `orders`, `products` |
| `orders_db` (PostgreSQL) | Task 3 | Alembic manages these tables, so keep them separate from `week2_sql` |
| MongoDB `shop` | Task 3 | Order events and the `$group` aggregation |
| SQLite files | Task 4 | `app.db`, `test.db`, `demo.db` are created automatically, no server needed |

## Prerequisites

- Python 3.10 or newer
- PostgreSQL (with `psql`) for Tasks 1 to 3, and MongoDB for Task 3
- Windows PowerShell commands are shown below; adapt the activation line on macOS or Linux

## Setup (once)
```powershell
cd C:\Week2_Assessment_SQL
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install alembic psycopg2-binary pymongo
```
The last line installs the packages used by Tasks 2 and 3. You can also add `alembic`, `psycopg2-binary` and `pymongo` to `dependencies` in `pyproject.toml`.

Set the PostgreSQL password for the current PowerShell window and create the two databases:

```powershell
$env:PGPASSWORD = "YOUR_POSTGRES_PASSWORD"
$psql = "C:\Program Files\PostgreSQL\16\bin\psql.exe"     # change 16 to your version
& $psql -U postgres -h localhost -c "CREATE DATABASE week2_sql;"
& $psql -U postgres -h localhost -c "CREATE DATABASE orders_db;"
```

`PGPASSWORD` is read automatically by `psql` and by `psycopg2`, so no password is stored in any file. Set it again if you open a new PowerShell window.

For Task 4, create a `.env` file in the project root (copy `.env.example` and fill in values):

```
API_KEY=my-secret-api-key
WEBHOOK_SECRET=whsec_demo_secret
DATABASE_URL=sqlite:///./app.db
```

`.env` is ignored by Git and must not be committed.

---

## Task 1: SQL Analysis

Tables: `customers`, `orders` (4 customers, 9 orders including 6 extra), and `products` with a JSONB `attrs` column.

| Query | Concept | Expected result |
|-------|---------|-----------------|
| 1 | Total per customer: JOIN + GROUP BY | Arun 2250, Priya 750, Rahul 1450 |
| 2 | Only totals above 1000: HAVING | Arun 2250, Rahul 1450 |
| 3 | Customers who never ordered: LEFT JOIN | Divya, Bangalore |
| 4 | Top customer per city: CTE + ROW_NUMBER | Bangalore: Divya (0), Chennai: Arun (2250), Mumbai: Priya (750) |
| 5 | `ROW_NUMBER()` rank by amount, `LAG()` previous amount | 9 rows, one per order |
| 6 | JSONB `@>` and `->>` | Laptop A, Dell, 16 |

Run:

```powershell
cd C:\Week2_Assessment_SQL
& $psql -U postgres -h localhost -d week2_sql -f analysis.sql
```

The file uses `psql` commands (`\echo`, `\pset`). If you use pgAdmin instead, delete those lines and run each numbered query separately.

---

## Task 2: Performance and Safety

### Index timings and constraint errors

```powershell
& $psql -U postgres -h localhost -d week2_sql -f task2_performance.sql
```

- Loads 200,000 rows into `big_orders` with `generate_series`.
- Runs `EXPLAIN ANALYZE` on `WHERE customer_id = 4242` before and after creating an index.
- Creates `employees` and `departments` with `NOT NULL`, `UNIQUE`, `FOREIGN KEY` and `CHECK` constraints, then breaks each one once.

Read the second `Execution Time` in each block (the first run warms the cache). Expected shape:

```
Before index: Seq Scan ~40 ms | After index: Index Scan ~0.1 ms
```

Your numbers will differ by machine. What matters is the plan changing from `Seq Scan` to `Index Scan` and the time dropping by a few hundred times.

The four `ERROR:` lines at the end of the output are intentional:

| Violation | Message contains |
|-----------|------------------|
| NOT NULL | `violates not-null constraint` |
| UNIQUE | `violates unique constraint "uq_employees_email"` |
| FOREIGN KEY | `violates foreign key constraint "fk_employees_dept"` |
| CHECK | `violates check constraint "ck_employees_salary"` |

### SQL injection test

Run `analysis.sql` first, because `get_orders` reads the `orders` table.

```powershell
python scripts\get_orders.py
```
Expected output:
```
Injection input '1 OR 1=1' -> 0 rows
```
`python scripts\get_orders.py --extras` also shows a valid lookup (4 rows for customer 1) and an unsafe string-built query that leaks all 9 orders, for comparison.

The query uses a `%s` parameter, so the input is sent to PostgreSQL as a single value and never becomes part of the SQL.

---

## Task 3: ORM, Migrations and Transactions

Run these commands from inside `ORM_Migration_Trans/`.

### What it covers

- SQLAlchemy models `Customer`, `Order` (one-to-many with `Customer`) and `Product`, with a configured connection pool (`pool_size=5`, `max_overflow=10`)
- First Alembic migration created with `--autogenerate`, then a second migration adding a `phone` column to `customers`
- `place_order(customer_id, product_id, qty)`: reduces stock and inserts the order in one transaction, rolling back on insufficient stock or any error
- An atomicity proof that forces an error after the stock update and shows the stock is unchanged
- Five order events stored in MongoDB with `pymongo`, plus a `$group` aggregation giving the total per customer

### Database connection

Set your PostgreSQL password in `models.py`, or override the URL for the current session:

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/orders_db"
```

URL-encode special characters in the password (for example `@` becomes `%40`).

### Run the migrations

```powershell
cd ORM_Migration_Trans
alembic revision --autogenerate -m "create customers products orders"
alembic upgrade head

# add the phone column to Customer in models.py, then:
alembic revision --autogenerate -m "add phone to customers"
alembic upgrade head
alembic history
```

`alembic history` should list two revisions, the second being "add phone to customers".

### Run the 

```powershell
python main.py
```
Expected output:

```
Order placed: stock 10 -> 8
Forced failure: rolled back, stock still 10
Mongo totals: customer 1 -> 1300
```
### How it works
- `session.begin()` wraps the stock update and the order insert in one transaction. The update is flushed first, then a forced `RuntimeError` makes the transaction roll back, so stock stays at 10 and no order row is written.
- `with_for_update=True` locks the product row so two concurrent orders cannot oversell.
- The MongoDB amounts (400 + 300 + 200 + 250 + 150) sum to 1300 for customer 1.
---
## Task 4: Secured API with Integration Tests
Run these commands from the project root with the virtual environment active.
### What it covers

- FastAPI endpoints: `POST /customers`, `GET /customers?page=&per_page=`, `GET /customers/{id}`, `PUT /customers/{id}`, `DELETE /customers/{id}`
- All customer endpoints protected by the `X-API-Key` header: 401 when missing, 403 when wrong, key read from `.env`
- `POST /webhooks/order-events` validates an HMAC-SHA256 signature (`X-Signature` header) and returns 200 immediately, processing the event in a background task
- `fetch_all(url)` client with page-based pagination, token refresh on 401 (client credentials against the mock endpoint `POST /mock/token`), and a sleep when `X-RateLimit-Remaining` is `0`
- 8 pytest integration tests on a separate test database (`test.db`)

### Other commands

```powershell
python -m pytest -v                  # list every test
python scripts\demo_client.py        # fetch_all demo (no server needed)
```
Expected output:
```
8 passed | GET /customers?page=1&per_page=5 -> 200
Webhook tampered -> 401
```
uvicorn src.main:app --reload        # run the API, docs at http://localhost:8000/docs
```

### Calling the API

```powershell
curl.exe -H "X-API-Key: my-secret-api-key" "http://localhost:8000/customers?page=1&per_page=5"
```

### Webhook signature

The signature is the hex HMAC-SHA256 of the raw request body using `WEBHOOK_SECRET`:

```python
import hashlib, hmac
signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
```

Send it in the `X-Signature` header. A wrong signature returns 401.

### Test cases

| # | Test | Expected |
|---|------|----------|
| 1 | Create, list, get, update, delete a customer | 201 / 200 / 200 / 200 / 204 |
| 2 | Request without `X-API-Key` | 401 |
| 3 | Request with a wrong key | 403 |
| 4 | Get a customer that does not exist | 404 |
| 5 | Create a customer with a duplicate email | 409 |
| 6 | Create a customer with an invalid email | 422 |
| 7 | Webhook with a valid signature | 200 |
| 8 | Webhook with a tampered signature | 401 |

---

## Expected output summary

```
Task 2   Before index: Seq Scan ~40 ms | After index: Index Scan ~0.1 ms
Task 2   Injection input '1 OR 1=1' -> 0 rows

Task 3   Order placed: stock 10 -> 8
Task 3   Forced failure: rolled back, stock still 10
Task 3   Mongo totals: customer 1 -> 1300

Task 4   8 passed | GET /customers?page=1&per_page=5 -> 200
Task 4   Webhook tampered -> 401
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named 'src'` | Run from the project root and make sure `pip install -e ".[dev]"` completed |
| `password authentication failed for user "postgres"` | Set `$env:PGPASSWORD` again, and use the real password in `ORM_Migration_Trans\models.py` |
| `Could not parse SQLAlchemy URL` | Clear any bad `$env:DATABASE_URL` and URL-encode special characters in the password |
| `database "..." does not exist` | Run the `CREATE DATABASE` commands from the setup section |
| `psql` is not recognized | Use the full path stored in `$psql` |
| `relation "orders" does not exist` in `get_orders.py` | Run `analysis.sql` first |
| Task 1 or 2 scripts wiped the Task 3 tables | They were run against `orders_db`; always use `-d week2_sql` for Tasks 1 and 2 |
| `run_all.py` prints `0 passed` | Make sure the pytest call uses `-o addopts=` and that `addopts` is not set twice |
| `database is locked` on Windows | Close any database viewer and delete `test.db` and `demo.db` |

## Notes

- `.env`, `venv/`, `*.db` and `__pycache__/` are excluded by `.gitignore`.
- Timings in Task 2 depend on the machine; report your own numbers.