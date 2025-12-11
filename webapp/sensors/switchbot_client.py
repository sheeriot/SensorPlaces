import time
import uuid
import hmac
import base64
import json
import requests
from hashlib import sha256

from django.conf import settings

BASE = "https://api.switch-bot.com"

def _headers(token: str, secret: str):
    """Builds the required authentication headers for the SwitchBot API."""

    if not token or not secret:
        raise Exception(
            "SwitchBot token and secret must be provided."
        )

    t = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    data = f"{token}{t}{nonce}".encode("utf-8")
    secret_bytes = secret.encode("utf-8")
    sign = base64.b64encode(hmac.new(secret_bytes, msg=data, digestmod=sha256).digest()).decode("utf-8")

    return {
        "Authorization": token,
        "Content-Type": "application/json; charset=utf8",
        "t": t,
        "sign": sign,
        "nonce": nonce,
    }

def list_devices(token: str, secret: str):
    """Fetches a list of all devices from the SwitchBot API."""
    api_headers = _headers(token, secret)
    r = requests.get(f"{BASE}/v1.1/devices", headers=api_headers, timeout=15)
    r.raise_for_status()
    return r.json()

def get_status(device_id: str, token: str, secret: str):
    """Fetches the status of a specific device from the SwitchBot API."""
    api_headers = _headers(token, secret)
    r = requests.get(f"{BASE}/v1.1/devices/{device_id}/status", headers=api_headers, timeout=15)
    r.raise_for_status()
    return r.json()
