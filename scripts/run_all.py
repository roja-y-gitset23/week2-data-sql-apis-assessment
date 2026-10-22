import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Use a separate demo database
demo_db = ROOT / "demo.db"
if demo_db.exists():
    demo_db.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{demo_db}"

# 1) Run the pytest suite and read the pass count
'''proc = subprocess.run([sys.executable, "-m", "pytest", "-q"],
                      capture_output=True, text=True, cwd=ROOT)
match = re.search(r"(\d+) passed", proc.stdout)
passed = match.group(1) if match else "0"
if proc.returncode != 0:
    print(proc.stdout)
    sys.exit("Tests failed, fix them first.")'''
# 1) Run the pytest suite and read the pass count
proc = subprocess.run(
    [sys.executable, "-m", "pytest", "-o", "addopts=", "-q"],
    capture_output=True, text=True, cwd=ROOT,
)
output = proc.stdout + proc.stderr
match = re.search(r"(\d+) passed", output)
if proc.returncode != 0 or not match:
    print(output)
    sys.exit("Tests failed or no result line found, fix this first.")
passed = match.group(1)

# 2) Call the real app against the demo database
from fastapi.testclient import TestClient

from src import models  # noqa: F401
from src.database import Base, engine
from src.main import app

Base.metadata.create_all(engine)
client = TestClient(app)
headers = {"X-API-Key": os.getenv("API_KEY")}

client.post("/customers", json={"name": "Asha", "email": "asha@example.com"},
            headers=headers)
resp = client.get("/customers?page=1&per_page=5", headers=headers)
print(f"{passed} passed | GET /customers?page=1&per_page=5 -> {resp.status_code}")

# 3) Tampered webhook
body = json.dumps({"order_id": 1, "status": "shipped"}).encode()
bad_sig = hmac.new(b"attacker-secret", body, hashlib.sha256).hexdigest()
resp = client.post("/webhooks/order-events", content=body,
                   headers={"X-Signature": bad_sig,
                            "Content-Type": "application/json"})
print(f"Webhook tampered -> {resp.status_code}")