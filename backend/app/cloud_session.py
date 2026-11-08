"""Signed, HttpOnly workspace cookies for the synthetic research deployment."""
import hashlib
import hmac
import os
import uuid
import secrets
import time

COOKIE_NAME = '__Host-causallens-account'
SESSION_TTL = 30 * 24 * 60 * 60


def signed_cookie(identifier):
    secret = os.environ.get('CLOUD_SESSION_SECRET', '')
    if len(secret) < 32:
        raise RuntimeError('CLOUD_SESSION_SECRET must be configured with at least 32 random characters')
    payload = f'{uuid.UUID(identifier)}.{int(time.time())}.{secrets.token_hex(16)}'
    return payload+'.'+hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def cookie_claims(value):
    if not value:
        return None
    try:
        identifier, issued, nonce, signature = value.split('.')
        if str(uuid.UUID(identifier)) != identifier:
            return None
        secret = os.environ.get('CLOUD_SESSION_SECRET', '')
        if len(secret) < 32:
            return None
        payload = '.'.join([identifier, issued, nonce])
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature) or len(nonce) != 32:
            return None
        if not -60 <= time.time()-int(issued) < SESSION_TTL:
            return None
        return {'account_id': identifier, 'issued': int(issued), 'nonce': nonce}
    except (ValueError, TypeError):
        return None


def verify_cookie(value):
    claims = cookie_claims(value)
    return claims['account_id'] if claims else None
