"""The waiting game's leaderboard: everyone's all-time best, under their display name."""

from __future__ import annotations

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


async def test_no_score_yet_and_bad_scores(app, vivian):
    board = (await vivian.get("/api/game/leaderboard")).json()
    assert board == {"top": [], "mine": None}
    assert (await vivian.post("/api/game/scores", json={"score": -1})).status_code == 422
    assert (await vivian.post("/api/game/scores", json={"score": 10**9})).status_code == 422


async def test_leaderboard_requires_login(app):
    async with client_for(app) as anon:
        assert (await anon.get("/api/game/leaderboard")).status_code == 401
        assert (await anon.post("/api/game/scores", json={"score": 1})).status_code == 401
