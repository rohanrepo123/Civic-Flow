"""
CivicFlow Contracts — Shared Pydantic schemas for service-to-service communication.

Version: 1.0.0

This package is the SINGLE source of truth for every request/response schema
exchanged between Core API, AI Agent, and Browser Agent.

Rules
-----
* Members 2 & 3 treat this package as **read-only** after contract freeze.
* Any schema change requires agreement, version bump, and updated contract tests.
* Import only from this package — never re-define these schemas in service code.
"""

__version__ = "1.0.0"
CONTRACT_VERSION = "1.0.0"
"""CivicFlow's shared, strict service boundary contracts (v1)."""
from civicflow_contracts.common import CONTRACT_VERSION

__version__ = CONTRACT_VERSION
