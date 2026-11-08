import os
from pathlib import Path

CLOUD_DEMO = os.getenv('CLOUD_DEMO', '') == '1'
RUNTIME = Path(os.getenv('RUNTIME_DIR', '/tmp/causallens' if CLOUD_DEMO else 'runtime'))
RUNTIME.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./runtime/research.db')
API_KEY = os.getenv('API_KEY', '')
SEED = 42
