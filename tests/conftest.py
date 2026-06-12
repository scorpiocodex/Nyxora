"""Shared pytest fixtures for the Nyxora test suite."""
from __future__ import annotations

import gc
import sqlite3

import pytest


@pytest.fixture(autouse=True)
def close_sqlite_connections():
    """Ensure all sqlite3 connections are closed after each test.

    Prevents ResourceWarning: unclosed database warnings that occur when
    mock-heavy tests create VaultStore instances without explicit close().
    """
    yield
    # After each test, close any lingering sqlite3 connections
    gc.collect()
    for obj in gc.get_objects():
        try:
            if isinstance(obj, sqlite3.Connection):
                try:
                    obj.close()
                except Exception:
                    pass
        except Exception:
            pass
