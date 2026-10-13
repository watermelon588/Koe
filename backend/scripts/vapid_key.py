"""Print a new Web Push (VAPID) private key for VAPID_PRIVATE_KEY on the host. Keep it secret; never commit it.
Usage: uv run python -m scripts.vapid_key
"""
from py_vapid import Vapid02, b64urlencode

key = Vapid02()
key.generate_keys()
print(b64urlencode(key.private_key.private_numbers().private_value.to_bytes(32, "big")))
