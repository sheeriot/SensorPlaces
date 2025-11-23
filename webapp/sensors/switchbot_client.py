import time, uuid, hmac, base64, json
import requests
from hashlib import sha256

from django.conf import settings

BASE = "https://api.switch-bot.com"

def _headers():
    """Builds the required authentication headers for the SwitchBot API."""
    token = getattr(settings, 'SWITCHBOT_TOKEN', None)
    secret = getattr(settings, 'SWITCHBOT_SECRET', None)

    if not token or not secret:
        raise Exception(
            "SWITCHBOT_TOKEN and SWITCHBOT_SECRET must be configured in your Django settings and cannot be empty. "
            "Please check your environment variables (e.g., env/django.env)."
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

def list_devices():
    """Fetches a list of all devices from the SwitchBot API."""
    r = requests.get(f"{BASE}/v1.1/devices", headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()

def get_status(device_id: str):
    """Fetches the status of a specific device from the SwitchBot API."""
    r = requests.get(f"{BASE}/v1.1/devices/{device_id}/status", headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()
