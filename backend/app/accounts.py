"""Real research accounts: private immutable records, scrypt hashes and revocable cookies."""
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from . import cloud_storage as storage
from .cloud_session import cookie_claims


def normalized_email(email):
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r'[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,63}', email):
        raise ValueError('Enter a valid email address')
    return email


def _derive(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=3,
                          maxmem=128*1024*1024, dklen=64).hex()


def password_hash(password):
    if not 15 <= len(password) <= 128:
        raise ValueError('Use a password between 15 and 128 characters')
    salt = secrets.token_bytes(16)
    return {'algorithm':'scrypt', 'n':32768, 'r':8, 'p':3, 'salt':salt.hex(), 'digest':_derive(password,salt)}


def verify_password(password, record):
    salt = bytes.fromhex(record['salt']) if record else b'\0'*16
    actual = _derive(password, salt)
    expected = record['digest'] if record else '0'*128
    return hmac.compare_digest(actual, expected) and record is not None


def global_read(path):
    client = storage.sdk()
    try:
        result = client.get_blob('auth/'+path, access='private')
        return json.loads(result.body)
    except client.BlobNotFoundError:
        return None


def global_exists(path):
    """Read authoritative metadata, not a delivery URL that may cache a prior 404."""
    client = storage.sdk()
    try:
        client.head_blob('auth/'+path)
        return True
    except client.BlobNotFoundError:
        return False


def put_once(path, value):
    try:
        return storage.sdk().put_blob('auth/'+path, json.dumps(value,allow_nan=False).encode(),
            access='private', allow_overwrite=False, add_random_suffix=False,
            cache_control_max_age=0, content_type='application/json')
    except Exception as exc:
        if getattr(exc,'status_code',None) in (409,412) or (
            getattr(exc,'status_code',None)==400 and 'already exists' in str(exc).lower()):
            return None
        raise


def _email_key(email):
    return hashlib.sha256(email.encode()).hexdigest()


def auth_rate_limit(email, address):
    """Atomic immutable slots give a durable ten-minute limit across function instances."""
    secret = os.environ['CLOUD_SESSION_SECRET'].encode()
    bucket = int(time.time())//600
    for label, identity, limit in [('address',address,30),('credential',address+'|'+email,10)]:
        key = hmac.new(secret,identity.encode(),hashlib.sha256).hexdigest()
        for slot in range(limit):
            if put_once(f'attempts/{label}/{bucket}/{key}/{slot}.json', {'time':int(time.time())}):
                break
        else:
            raise HTTPException(429,'Too many sign-in attempts. Try again in ten minutes.')


def _public(account):
    return {'id':account['id'], 'email':account['email'], 'email_verified':False}


def auth_event(account_id, event):
    put_once(f'events/{uuid.uuid4()}.json', {'account_id':account_id,'event':event,
             'created_at':datetime.now(timezone.utc).isoformat()})


def register(email, password, address):
    email = normalized_email(email)
    auth_rate_limit(email,address)
    hashed = password_hash(password)
    account = {'id':str(uuid.uuid4()),'email':email,'password':hashed,
               'created_at':datetime.now(timezone.utc).isoformat()}
    if not put_once(f'accounts/{_email_key(email)}.json',account):
        raise HTTPException(409,'An account with this email already exists. Please sign in.')
    public = _public(account)
    put_once(f'ids/{account["id"]}.json',public)
    auth_event(account['id'],'account_created')
    return public


def login(email,password,address):
    email = normalized_email(email)
    auth_rate_limit(email,address)
    account = global_read(f'accounts/{_email_key(email)}.json')
    if not verify_password(password, account['password'] if account else None):
        raise HTTPException(401,'Email or password is incorrect')
    public = _public(account)
    if not global_read(f'ids/{account["id"]}.json'):
        put_once(f'ids/{account["id"]}.json',public)
    auth_event(account['id'],'signed_in')
    return public


def current_account(cookie):
    claims = cookie_claims(cookie)
    if not claims or global_exists(f'revoked/{claims["nonce"]}.json'):
        return None
    return global_read(f'ids/{claims["account_id"]}.json')


def logout(cookie):
    claims = cookie_claims(cookie)
    if claims:
        put_once(f'revoked/{claims["nonce"]}.json',{'revoked_at':int(time.time())})
        auth_event(claims['account_id'],'signed_out')


def initialize_workspace(account_id, create_dataset, train_model):
    """Prepare once per account; a private, leased lock prevents concurrent duplicate training."""
    from . import database as db
    reference = global_read(f'starters/{account_id}.json')
    if reference:
        db.get(reference['dataset_id'],'dataset')
        db.get(reference['model_id'],'model')
        return {**reference,'created':False}
    lock_path = f'locks/{account_id}.json'
    existing = global_read(lock_path)
    if existing and existing['expires'] <= time.time():
        client = storage.sdk()
        stale = client.get_blob('auth/'+lock_path,access='private')
        client.delete_blob('auth/'+lock_path,if_match=stale.metadata.etag)
    lock = put_once(lock_path,{'expires':int(time.time())+300})
    if not lock:
        raise HTTPException(409,'Your workspace is being prepared in another session. Please wait.')
    try:
        reference = global_read(f'starters/{account_id}.json')
        if reference:
            return {**reference,'created':False}
        datasets = db.listing('dataset',0,100)
        dataset = next((d for d in datasets if d.get('provenance',{}).get('synthetic')
                        and d['quality']['rows']==2000 and d['provenance'].get('seed')==42),None)
        dataset = dataset or create_dataset()
        models = db.listing('model',0,100)
        model = next((m for m in models if m['dataset_id']==dataset['id']),None)
        model = model or train_model(dataset['id'])
        reference = {'ready':True,'dataset_id':dataset['id'],'model_id':model['id']}
        put_once(f'starters/{account_id}.json',reference)
        return {**reference,'created':True}
    finally:
        storage.sdk().delete_blob('auth/'+lock_path,if_match=lock.etag)
