"""Immutable private object snapshots, indexed per kind without shared mutable indexes."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from . import cloud_storage as storage


def save(kind, payload, parent_id=None):
    if parent_id:
        get(parent_id)
    body = json.dumps(payload, sort_keys=True, allow_nan=False)
    record = {'id': str(uuid.uuid4()), 'kind': kind, 'parent_id': parent_id,
              'created_at': datetime.now(timezone.utc).isoformat(),
              'checksum': hashlib.sha256(body.encode()).hexdigest(), **json.loads(body)}
    content = json.dumps(record, allow_nan=False).encode()
    storage.put('records/'+record['id']+'.json', content)
    storage.put(f"kinds/{kind}/{record['id']}.json", content)
    return record


def get(record_id, kind=None):
    try:
        identifier = str(uuid.UUID(record_id))
    except ValueError as exc:
        raise KeyError('Record not found') from exc
    record = json.loads(storage.read('records/'+identifier+'.json'))
    if kind and record['kind'] != kind:
        raise KeyError('Record not found')
    return record


def listing(kind, offset=0, limit=25):
    objects = list(storage.query(f'kinds/{kind}/'))
    objects.sort(key=lambda item: item.uploaded_at, reverse=True)
    return [json.loads(storage.sdk().get_blob(item.pathname, access='private').body) for item in objects[offset:offset+limit]]
