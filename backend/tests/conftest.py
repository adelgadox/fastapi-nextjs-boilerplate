"""Test environment defaults.

Settings requires DATABASE_URL and SECRET_KEY at import time; give the suite
safe values so `python -m pytest` runs without a .env file. setdefault means a
real environment (CI secrets, local .env already exported) always wins.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789abcdef")
