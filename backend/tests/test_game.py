"""The waiting games' leaderboards: everyone's all-time best under their display name."""

from __future__ import annotations

import sqlite3

from ticket_sprite import db

from .conftest import client_for


async def test_leaderboard_keeps_each_persons_best(app, vivian, kevin):
    for score in (3, 9, 5):
        assert (await vivian.post("/api/game/scores", json={"score": score})).status_code == 200
    await kevin.post("/api/game/scores", json={"score": 7})

    board = (await kevin.get("/api/game/leaderboard")).json()
    assert [(p["name"], p["best"], p["me"]) for p in board["top"]] == [("vivian", 9, False), ("kevin", 7, True)]
    assert board["mine"] == {"rank": 2, "best": 7}


async def test_saving_a_score_returns_the_new_standing(app, vivian):
    r = (await vivian.post("/api/game/scores", json={"score": 4})).json()
    assert r["record"] and r["mine"] == {"rank": 1, "best": 4}
    r = (await vivian.post("/api/game/scores", json={"score": 2})).json()
    assert not r["record"] and r["mine"] == {"rank": 1, "best": 4}


async def test_minesweeper_ranks_the_fastest_clear_first(app, vivian, kevin):
    for ms in (90_000, 41_500, 60_000):
        await vivian.post("/api/game/scores", json={"game": "mines", "score": ms})
    r = (await kevin.post("/api/game/scores", json={"game": "mines", "score": 52_000})).json()
    assert r["record"] and r["mine"] == {"rank": 2, "best": 52_000}

    board = (await kevin.get("/api/game/leaderboard?game=mines")).json()
    assert [(p["name"], p["best"]) for p in board["top"]] == [("vivian", 41_500), ("kevin", 52_000)]
    # each game keeps its own board
    assert (await kevin.get("/api/game/leaderboard")).json() == {"top": [], "mine": None}


async def test_the_leaderboard_page_shows_more_than_the_waiting_card(app, vivian):
    await vivian.post("/api/game/scores", json={"score": 1})
    assert len((await vivian.get("/api/game/leaderboard?limit=20")).json()["top"]) == 1
    assert (await vivian.get("/api/game/leaderboard?limit=21")).status_code == 422


async def test_no_score_yet_and_bad_scores(app, vivian):
    board = (await vivian.get("/api/game/leaderboard")).json()
    assert board == {"top": [], "mine": None}
    assert (await vivian.post("/api/game/scores", json={"score": -1})).status_code == 422
    assert (await vivian.post("/api/game/scores", json={"score": 10**9})).status_code == 422
    assert (await vivian.post("/api/game/scores", json={"game": "mines", "score": 100})).status_code == 422
    assert (await vivian.post("/api/game/scores", json={"game": "tetris", "score": 1})).status_code == 422


async def test_leaderboard_requires_login(app):
    async with client_for(app) as anon:
        assert (await anon.get("/api/game/leaderboard")).status_code == 401
        assert (await anon.post("/api/game/scores", json={"score": 1})).status_code == 401


async def test_firefly_scores_from_before_minesweeper_are_kept(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE game_scores (email VARCHAR(320) PRIMARY KEY, best INTEGER, achieved_at DATETIME)")
        conn.execute("INSERT INTO game_scores VALUES ('vivian@linkervision.com', 14, '2026-10-08 15:00:00')")
    db.init_engine(f"sqlite+aiosqlite:///{path}")
    await db.create_all()
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT game, email, best FROM game_bests").fetchall() == [
            ("firefly", "vivian@linkervision.com", 14)
        ]
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name = 'game_scores'").fetchall()
