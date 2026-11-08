"""Private Blob storage scoped to a signed browser workspace, never /tmp as persistence."""
import uuid
from contextvars import ContextVar
from pathlib import Path

workspace: ContextVar[str | None] = ContextVar('workspace', default=None)
request_files: ContextVar[set[str] | None] = ContextVar('request_files', default=None)


def prefix():
    scope = workspace.get()
    if scope is None:
        raise PermissionError('Cloud storage requires an authenticated browser workspace')
    return f'workspaces/{uuid.UUID(scope)}/'


def sdk():
    from vercel.blob import sync
    return sync


def put(name: str, content: bytes):
    return sdk().put_blob(prefix()+name, content, access='private', add_random_suffix=False,
                          allow_overwrite=False, content_type='application/octet-stream')


def read(name: str):
    client = sdk()
    try:
        return client.get_blob(prefix()+name, access='private').body
    except client.BlobNotFoundError as exc:
        raise KeyError('Record not found') from exc


def query(name: str):
    return sdk().query_blobs(prefix=prefix()+name, page_size=100)


def persist_artifact(path: Path):
    put('artifacts/'+path.name, path.read_bytes())
    cached = request_files.get()
    if cached is not None:
        cached.add(path.name)


def fetch_artifact(path: Path):
    cached = request_files.get()
    if cached is not None and path.name in cached and path.exists():
        return path
    content = read('artifacts/'+path.name)
    temporary = path.with_suffix(path.suffix+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_bytes(content)
    temporary.replace(path)
    if cached is not None:
        cached.add(path.name)
    return path
