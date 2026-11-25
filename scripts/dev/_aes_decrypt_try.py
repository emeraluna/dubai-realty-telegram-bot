"""Brute simple decrypt guesses for Trakheesi Token header."""
from Crypto.Cipher import AES  # may not exist

CIPHER = "ElDEQZ"
KEYS = ["7!FAu&9", "7!FAu&9P", "tqPJHE!", "UPA1BTGGKGZAWAGSKYI30B2LO"]

try:
    from Crypto.Cipher import AES  # type: ignore
except ImportError:
  AES = None

if AES is None:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        print("no crypto libs")
        raise SystemExit(0)


def try_cryptojs_style(ct: str, key: str) -> None:
    import base64
    import hashlib

    try:
        raw = base64.b64decode(ct + "==")
    except Exception:
        raw = ct.encode()
    k = hashlib.md5(key.encode()).digest()
    # ECB guess
    try:
        if AES:
            cipher = AES.new(k, AES.MODE_ECB)
            pt = cipher.decrypt(raw[:16])
            print("ecb", key, pt)
    except Exception as e:
        print("ecb fail", key, e)


for k in KEYS:
    try_cryptojs_style(CIPHER, k)