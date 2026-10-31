import pytest
from datetime import datetime, timedelta, timezone
import jwt

from app.core.security import (
    get_password_hash,
    verify_password,
    get_password_hash_async,
    verify_password_async,
    create_access_token,
    create_refresh_token,
    decode_token,
    new_token_family,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    TokenError,
    MAX_PASSWORD_BYTES,
    ALGORITHM,
    _ISSUER,
    _AUDIENCE,
)
from app.config import settings


@pytest.mark.unit
def test_bcrypt_password_hashing():
    password = "CorrectHorseBatteryStaple!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(password, None) is False


@pytest.mark.unit
def test_bcrypt_72_byte_truncation():
    # Passwords up to 72 bytes hash and verify properly
    valid_pwd = "A" * MAX_PASSWORD_BYTES
    hashed = get_password_hash(valid_pwd)
    assert verify_password(valid_pwd, hashed) is True

    # Bcrypt truncates verification at 72 bytes
    long_pwd = valid_pwd + "EXTRA_BYTES_BEYOND_72"
    assert verify_password(long_pwd, hashed) is True


@pytest.mark.unit
async def test_async_password_hashing():
    password = "AsyncPassword123!"
    hashed = await get_password_hash_async(password)
    assert await verify_password_async(password, hashed) is True
    assert await verify_password_async("Incorrect", hashed) is False


@pytest.mark.unit
def test_jwt_access_and_refresh_tokens():
    family_id = new_token_family()
    user_id = "user-uuid-1234"

    access_tok, jti, expire = create_access_token(user_id, family=family_id)
    assert isinstance(access_tok, str)
    assert jti is not None
    assert expire > datetime.now(timezone.utc)

    # Decode access token
    decoded = decode_token(access_tok, expected_type=TOKEN_TYPE_ACCESS)
    assert decoded["sub"] == user_id
    assert decoded["fam"] == family_id
    assert decoded["typ"] == TOKEN_TYPE_ACCESS
    assert decoded["iss"] == _ISSUER
    assert decoded["aud"] == _AUDIENCE

    # Fails if decoded with expected type 'refresh'
    with pytest.raises(TokenError, match="Expected a refresh token"):
        decode_token(access_tok, expected_type=TOKEN_TYPE_REFRESH)

    # Refresh token issuance and decode
    refresh_tok, r_jti, r_expire = create_refresh_token(user_id, family=family_id)
    decoded_refresh = decode_token(refresh_tok, expected_type=TOKEN_TYPE_REFRESH)
    assert decoded_refresh["sub"] == user_id
    assert decoded_refresh["typ"] == TOKEN_TYPE_REFRESH


@pytest.mark.unit
def test_jwt_expired_token():
    user_id = "user-expired-123"
    now = datetime.now(timezone.utc)
    # Mint token with expired time and required claims
    payload = {
        "sub": user_id,
        "typ": TOKEN_TYPE_ACCESS,
        "jti": "test-jti-123",
        "fam": "test-fam-123",
        "iat": now - timedelta(minutes=20),
        "nbf": now - timedelta(minutes=20),
        "exp": now - timedelta(minutes=5),
        "iss": _ISSUER,
        "aud": _AUDIENCE,
    }
    expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

    with pytest.raises(TokenError, match="Signature has expired"):
        decode_token(expired_token, expected_type=TOKEN_TYPE_ACCESS)


@pytest.mark.unit
def test_jwt_tampered_signature():
    family_id = new_token_family()
    token, _, _ = create_access_token("user-legit", family=family_id)
    # Tamper with the secret key signature
    tampered = token[:-4] + "abcd"

    with pytest.raises(TokenError, match="Invalid token"):
        decode_token(tampered, expected_type=TOKEN_TYPE_ACCESS)
