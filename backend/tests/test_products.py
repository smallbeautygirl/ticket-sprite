"""Products (ADR-0004): which are offered, what each lets the interviewer see, and keeping each clone fresh."""

import subprocess

from ticket_sprite import services
from ticket_sprite.engine.llm import system_prompt
from ticket_sprite.knowledge import Depth, KnowledgeSource, sync_product
from ticket_sprite.models import Interview
from ticket_sprite.products import TAIPEI_MRT, product, products


def _mrt_tree(root):
    files = {
        "README.md": "# 台北捷運文湖線 動態載客模擬器\n",
        "train-sim-sdk/docs/SCENARIO_FORMAT.md": "# Scenario\n",
        "train-sim-sdk/src/engine.ts": "export const headway = 90;\n",
        "frontend/src/App.tsx": "<AppShell />\n",
        "frontend/src/modules/line/components/StationMarker.tsx": "<span>月台</span>\n",
        "frontend/src/modules/line/lib/routeGeometry.ts": "export const km = 1;\n",
        "frontend/src/modules/incident/constants.ts": "export const INCIDENT = '事故';\n",
        "frontend/public/scenarios/weekday.json": '{"trains": []}\n',
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")


def test_both_products_are_offered_by_default_and_can_be_narrowed(settings):
    assert list(products(settings)) == ["middleware", "taipei_mrt"]
    assert products(settings)["taipei_mrt"].default_parent_id == 41490
    assert products(settings)["middleware"].default_parent_id == settings.ado_default_parent_id
    settings.products_enabled = "middleware, nope"
    assert list(products(settings)) == ["middleware"]
    # an Interview of a Product disabled since still resolves to it
    assert product(settings, "taipei_mrt").label == "北捷"


def test_mrt_docs_depth_sees_docs_and_screens_but_not_logic_or_scenarios(tmp_path):
    _mrt_tree(tmp_path)
    docs = {p.as_posix() for p in KnowledgeSource(tmp_path, Depth.DOCS, TAIPEI_MRT).visible_files()}
    assert docs == {
        "README.md",
        "train-sim-sdk/docs/SCENARIO_FORMAT.md",
        "frontend/src/App.tsx",
        "frontend/src/modules/line/components/StationMarker.tsx",
        "frontend/src/modules/incident/constants.ts",
    }
    code = {p.as_posix() for p in KnowledgeSource(tmp_path, Depth.CODE, TAIPEI_MRT).visible_files()}
    assert "frontend/src/modules/line/lib/routeGeometry.ts" in code and "train-sim-sdk/src/engine.ts" in code
    assert not any(p.startswith("frontend/public/scenarios") for p in code)


def test_system_prompt_carries_the_products_own_notes(settings, tmp_path):
    mw = system_prompt(KnowledgeSource(settings.product_root, Depth.DOCS))
    assert "Product Middleware" in mw and "middleware-ui/#/whitelist" in mw
    assert "the console's screens (app/ui_static); other code is not visible" in mw
    mrt = system_prompt(KnowledgeSource(tmp_path, Depth.DOCS, TAIPEI_MRT))
    assert "Product 北捷" in mrt and "SCENARIO_FORMAT.md" in mrt and "middleware-ui" not in mrt
    assert "the simulator's screens" in mrt


def test_interview_knowledge_follows_its_product(deps, settings):
    ks = services.knowledge_for(deps, Interview(product="taipei_mrt", role="rd"))
    assert ks.product.id == "taipei_mrt" and ks.depth is Depth.CODE
    assert ks.root == settings.knowledge_root / settings.taipei_mrt_repo_dir / settings.taipei_mrt_subdir


async def test_create_interview_for_mrt_and_reject_unknown(vivian):
    meta = (await vivian.get("/api/meta")).json()
    assert meta["products"] == [{"id": "middleware", "label": "Middleware"}, {"id": "taipei_mrt", "label": "北捷"}]
    r = await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "OD 矩陣可以匯入", "product": "taipei_mrt"})
    assert r.status_code == 200, r.text
    d = (await vivian.get(f"/api/interviews/{r.json()['id']}")).json()
    assert d["product"] == "taipei_mrt" and d["product_label"] == "北捷" and d["default_parent_id"] == 41490
    listed = (await vivian.get("/api/interviews", params={"scope": "mine"})).json()
    assert listed[0]["product_label"] == "北捷"
    bad = await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x", "product": "nope"})
    assert bad.status_code == 400
    # no product given: the first one offered
    r = await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x"})
    assert (await vivian.get(f"/api/interviews/{r.json()['id']}")).json()["product"] == "middleware"


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "HOME": str(cwd), "PATH": "/usr/bin:/bin"})


async def test_sync_tracks_a_branch_known_only_as_remote_tracking_and_survives_force_push(settings, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(upstream, "init", "-q", "-b", "main")
    (upstream / "README.md").write_text("main\n")
    _git(upstream, "add", ".")
    _git(upstream, "commit", "-q", "-m", "main")
    _git(upstream, "checkout", "-q", "-b", "feat/mrt")
    (upstream / "apps").mkdir()
    (upstream / "apps" / "mrt.md").write_text("v1\n")
    _git(upstream, "add", ".")
    _git(upstream, "commit", "-q", "-m", "mrt v1")
    # like /opt/lighthouse-saas-api: a clone that fetched the branch but never checked it out
    source = tmp_path / "source"
    _git(tmp_path, "clone", "-q", "--branch", "main", str(upstream), str(source))
    _git(source, "fetch", "-q", "origin")
    settings.knowledge_repo_source = str(source)
    settings.taipei_mrt_branch = "feat/mrt"
    mrt = products(settings)["taipei_mrt"]

    await sync_product(settings, mrt)
    clone = settings.knowledge_root / mrt.clone_dir
    assert (clone / "apps" / "mrt.md").read_text() == "v1\n"

    # the branch is rewritten upstream (rebase / force-push); the clone follows it
    (upstream / "apps" / "mrt.md").write_text("v2\n")
    _git(upstream, "commit", "-q", "-a", "--amend", "-m", "mrt v2")
    _git(source, "fetch", "-q", "origin", "+feat/mrt:refs/remotes/origin/feat/mrt")
    await sync_product(settings, mrt)
    assert (clone / "apps" / "mrt.md").read_text() == "v2\n"
