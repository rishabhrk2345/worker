"""
apps/api/core/security.py

Security utilities:
1. AES-256-GCM symmetric encryption for external source credentials.
2. JWT generation and verification for API & WebSocket authentication.
3. Password hashing using PBKDF2/HMAC-SHA256 (no external C dependencies required).
"""

import base64
import os
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .config import settings

# ------------------------------------------------------------------------------
# 1. Symmetric Credential Encryption (AES-256-GCM)
# ------------------------------------------------------------------------------

def _get_encryption_key() -> bytes:
    key_b64 = settings.CREDENTIAL_ENCRYPTION_KEY
    key_bytes = base64.b64decode(key_b64)
    if len(key_bytes) != 32:
        # Pad or derive 32 bytes deterministically if provided key is shorter
        key_bytes = hashlib.sha256(key_bytes).digest()
    return key_bytes

def encrypt_credential(data: str) -> str:
    """
    Encrypts sensitive string (API key, OAuth token, password) using AES-256-GCM.
    Returns base64-encoded string containing nonce (12 bytes) + ciphertext + tag.
    """
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    data_bytes = data.encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, data_bytes, None)
    payload = nonce + ciphertext
    return base64.b64encode(payload).decode("utf-8")

def decrypt_credential(encrypted_b64: str) -> str:
    """
    Decrypts AES-256-GCM base64-encoded credential string.
    """
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    payload = base64.b64decode(encrypted_b64.encode("utf-8"))
    nonce = payload[:12]
    ciphertext = payload[12:]
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode("utf-8")

# ------------------------------------------------------------------------------
# 2. Password Hashing (PBKDF2-HMAC-SHA256)
# ------------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{base64.b64encode(salt).decode('utf-8')}${base64.b64encode(hashed).decode('utf-8')}"

def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        salt_b64, hash_b64 = stored_hash.split("$")
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        stored_bytes = base64.b64decode(hash_b64.encode("utf-8"))
        computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(stored_bytes, computed)
    except Exception:
        return False

# ------------------------------------------------------------------------------
# 3. JWT Authentication & Tenant Context
# ------------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    organization_id: str,
    role: str = "member",
    permissions: Optional[list] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    
    payload: Dict[str, Any] = {
        "sub": user_id,
        "org_id": organization_id,
        "role": role,
        "permissions": permissions or [],
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT token.
    Raises jwt.PyJWTError on invalid or expired token.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
