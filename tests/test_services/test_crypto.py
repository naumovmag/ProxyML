from src.utils.crypto import hash_password, verify_password, generate_api_key, hash_api_key, get_key_prefix


def test_password_hashing():
    hashed = hash_password("test123")
    assert verify_password("test123", hashed)
    assert not verify_password("wrong", hashed)


def test_api_key_generation():
    key = generate_api_key()
    assert key.startswith("pml_")
    assert len(key) > 10


def test_api_key_hashing():
    key = generate_api_key()
    h = hash_api_key(key)
    assert len(h) == 64  # SHA256 hex digest


def test_key_prefix():
    key = "pml_abcdefghijk"
    assert get_key_prefix(key) == "pml_abcd"
