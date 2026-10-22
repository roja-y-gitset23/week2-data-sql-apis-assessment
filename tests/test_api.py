import hashlib
import hmac
import json

AUTH = {"X-API-Key": "test-key"}
WEBHOOK_SECRET = "test-secret"


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def post_webhook(client, body: bytes, signature: str):
    return client.post("/webhooks/order-events", content=body,
                       headers={"X-Signature": signature,
                                "Content-Type": "application/json"})


# 1. success: full CRUD happy path
def test_crud_success(client):
    r = client.post("/customers", json={"name": "Asha", "email": "asha@example.com"},
                    headers=AUTH)
    assert r.status_code == 201
    cid = r.json()["id"]

    r = client.get("/customers?page=1&per_page=5", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["total"] == 1

    assert client.get(f"/customers/{cid}", headers=AUTH).status_code == 200

    r = client.put(f"/customers/{cid}",
                   json={"name": "Asha K", "email": "asha@example.com"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["name"] == "Asha K"

    assert client.delete(f"/customers/{cid}", headers=AUTH).status_code == 204
    assert client.get(f"/customers/{cid}", headers=AUTH).status_code == 404


# 2. 401: missing key
def test_missing_api_key_returns_401(client):
    assert client.get("/customers").status_code == 401


# 3. 403: wrong key
def test_wrong_api_key_returns_403(client):
    r = client.get("/customers", headers={"X-API-Key": "wrong"})
    assert r.status_code == 403


# 4. 404: unknown customer
def test_unknown_customer_returns_404(client):
    assert client.get("/customers/9999", headers=AUTH).status_code == 404


# 5. 409: duplicate email
def test_duplicate_email_returns_409(client):
    body = {"name": "Ravi", "email": "ravi@example.com"}
    assert client.post("/customers", json=body, headers=AUTH).status_code == 201
    assert client.post("/customers", json=body, headers=AUTH).status_code == 409


# 6. 422: invalid body
def test_invalid_body_returns_422(client):
    r = client.post("/customers", json={"name": "Bad", "email": "not-an-email"},
                    headers=AUTH)
    assert r.status_code == 422


# 7. webhook with valid signature
def test_webhook_valid_signature(client):
    body = json.dumps({"order_id": 1, "status": "shipped"}).encode()
    r = post_webhook(client, body, sign(body, WEBHOOK_SECRET))
    assert r.status_code == 200


# 8. webhook with tampered signature
def test_webhook_tampered_signature(client):
    body = json.dumps({"order_id": 1, "status": "shipped"}).encode()
    r = post_webhook(client, body, sign(body, "wrong-secret"))
    assert r.status_code == 401