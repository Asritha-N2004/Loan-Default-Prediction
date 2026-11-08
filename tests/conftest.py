import os
import tempfile
import uuid
from pathlib import Path

TEST_ROOT = Path('runtime/tests') / str(uuid.uuid4())
TEST_ROOT.mkdir(parents=True, exist_ok=True)
TEST_ROOT = TEST_ROOT.resolve()
os.environ['RUNTIME_DIR'] = str(TEST_ROOT)
os.environ['DATABASE_URL'] = 'sqlite:///' + str(TEST_ROOT / 'test.db').replace('\\', '/')
os.environ['API_KEY'] = ''
