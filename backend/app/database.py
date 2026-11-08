"""Select a durable repository for the current deployment."""
from .config import CLOUD_DEMO

if CLOUD_DEMO:
    from .cloud_database import get, listing, save
else:
    from .sqlite_database import get, listing, save
