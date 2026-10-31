"""Use an isolated in-memory database when importing the backend test app."""

import os


# The module-level ASGI app is created during test collection. Never let a local
# developer's Compose DATABASE_URL make collection require a running `db` host.
os.environ["DATABASE_URL"] = "sqlite://"
