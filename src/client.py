import os
import time

import requests

TOKEN_URL = os.getenv("TOKEN_URL", "http://localhost:8000/mock/token")


class TokenManager:
    """Client-credentials flow against the mock token endpoint."""

    def __init__(self, session, token_url, client_id, client_secret):
        self.session = session
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.refresh_count = 0

    def refresh(self):
        resp = self.session.post(self.token_url, data={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        self.refresh_count += 1


def fetch_all(url, per_page=5, api_key=None, session=None,
              token_url=TOKEN_URL, client_id="demo-client",
              client_secret="demo-secret", sleep=time.sleep):
    """Fetch every page. Refreshes the token on 401 and sleeps when
    X-RateLimit-Remaining is 0."""
    session = session or requests.Session()
    tokens = TokenManager(session, token_url, client_id, client_secret)
    results, page = [], 1

    def get_page(p):
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        if tokens.token:
            headers["Authorization"] = f"Bearer {tokens.token}"
        return session.get(url, params={"page": p, "per_page": per_page},
                           headers=headers)

    while True:
        resp = get_page(page)
        if resp.status_code == 401:          # token missing or expired
            tokens.refresh()
            resp = get_page(page)            # retry once with the new token
        resp.raise_for_status()

        if resp.headers.get("X-RateLimit-Remaining") == "0":
            sleep(float(resp.headers.get("X-RateLimit-Reset", "1")))

        items = resp.json()["items"]
        if not items:
            break
        results.extend(items)
        if len(items) < per_page:
            break
        page += 1
    return results