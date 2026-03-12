import asyncio
import secrets
import hashlib
from functools import partial
import bcrypt


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(
        lambda: bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    )


async def verify_password(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(
        partial(bcrypt.checkpw, plain.encode(), hashed.encode())
    )


def generate_api_key() -> str:
    return "pml_" + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_key_prefix(key: str) -> str:
    return key[:8]
