import secrets
import hashlib
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def generate_api_key() -> str:
    return "pml_" + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_key_prefix(key: str) -> str:
    return key[:8]
