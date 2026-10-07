"""Additive schema changes reach a database created by an older version."""

from __future__ import annotations

import sqlite3

from ticket_sprite import db


async def test_create_all_adds_new_nullable_columns(tmp_path):
    path = tmp_path / "old.db"
    engine = db.init_engine(f"sqlite+aiosqlite:///{path}")
    await db.create_all()
    await engine.dispose()
    # An older version of the schema: same tables, without the column added later
    with sqlite3.connect(path) as conn:
        conn.execute("ALTER TABLE interviews DROP COLUMN question_budget")

    engine = db.init_engine(f"sqlite+aiosqlite:///{path}")
    await db.create_all()
    await engine.dispose()

    with sqlite3.connect(path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(interviews)")}
    assert "question_budget" in columns
