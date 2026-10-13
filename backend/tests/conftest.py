from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography.fernet import Fernet

from ticket_sprite.config import Settings
from ticket_sprite.engine.llm import FakeInterviewer
from ticket_sprite.main import create_app
from ticket_sprite.notify import Notifier


@dataclass
class FakeAdo:
    """Records Azure DevOps REST calls and answers like the real service."""

    valid_pats: set[str] = field(default_factory=lambda: {"good-pat-1234567890"})
    created: list[dict] = field(default_factory=list)
    uploads: list[str] = field(default_factory=list)
    next_id: int = 50000
    # work item id → System.AssignedTo, answered for the recent-assignees query
    assigned: dict[int, dict] = field(default_factory=lambda: {
        1: {"displayName": "Kevin Lin", "uniqueName": "Kevin@LinkerVision.com"},
        2: {"displayName": "Kevin Lin", "uniqueName": "kevin@linkervision.com"},
        3: {"displayName": "Froggy Hong", "uniqueName": "froggy@linkervision.com"},
        4: {"displayName": "Build Service", "uniqueName": "Build Service (linkerengineer)"},
    })
    wiql_calls: int = 0
    # people who edited a work item's description after it was created, and description updates sent
    description_editors: list[str] = field(default_factory=list)
    patched: list[dict] = field(default_factory=list)
    # work item id → System.IterationPath (anything not listed sits in SPRINT 1)
    iteration_of: dict[int, str] = field(default_factory=dict)
    # the team's sprints, as teamsettings/iterations lists them: SPRINT 1 is over, SPRINT 2 runs now
    team_iterations: list[dict] = field(default_factory=lambda: [
        _sprint("Deliver team\\2026 2nd Half", "past"),
        _sprint("Deliver team\\SPRINT 1", "past", "2026-10-12", "2026-10-23"),
        _sprint("Deliver team\\SPRINT 2", "current", "2026-10-26", "2026-11-06"),
        _sprint("Deliver team\\SPRINT 3", "future", "2026-11-09", "2026-11-20"),
    ])
    # the Parent 41152's children: open, in testing, closed lately, closed long ago, removed
    children: dict[int, dict] = field(default_factory=lambda: {
        45772: _child("新增轉發排除規則", "Active", "Vivian Fan"),
        45669: _child("Console 新增模型用量頁", "Testing", "Froggy Hong"),
        45736: _child("歷史事件新增場域篩選", "New", None),
        45615: _child("preprod 安裝 CD timer", "Closed", "Vivian Fan", closed_days_ago=5),
        41154: _child("v2 apiserver proxy - event", "Closed", "Froggy Hong", closed_days_ago=60),
        43256: _child("Judgment Agreement API", "Removed", "Vivian Fan"),
    })

    def _authorized(self, request: httpx.Request) -> bool:
        import base64

        header = request.headers.get("authorization", "")
        if not header.startswith("Basic "):
            return False
        pat = base64.b64decode(header[6:]).decode().split(":", 1)[1]
        return pat in self.valid_pats

    def handler(self, request: httpx.Request) -> httpx.Response:
        if not self._authorized(request):
            return httpx.Response(401, json={"message": "unauthorized"})
        path = request.url.path
        if path.endswith("/_apis/connectionData"):
            return httpx.Response(200, json={"authenticatedUser": {"providerDisplayName": "Vivian Fan"}})
        if path.endswith("/_apis/wit/attachments"):
            name = request.url.params["fileName"]
            self.uploads.append(name)
            return httpx.Response(201, json={"url": f"https://dev.azure.com/att/{name}"})
        if path.endswith("/_apis/wit/wiql"):
            self.wiql_calls += 1
            query = json.loads(request.content)["query"]
            if "@CurrentIteration('[Deliver team]\\Deliver team Team')" in query:
                return httpx.Response(200, json={"workItems": [{"id": 41152}, {"id": 41155}]})
            if "[System.AssignedTo] <> ''" in query:
                return httpx.Response(200, json={"workItems": [{"id": i} for i in self.assigned]})
            return httpx.Response(200, json={"workItems": [{"id": 41152}]})
        if path.endswith("/_apis/work/teamsettings/iterations"):
            return httpx.Response(200, json={"count": len(self.team_iterations), "value": self.team_iterations})
        if path.endswith("/_apis/wit/workitems/41152") and request.method == "GET":
            return httpx.Response(200, json={"id": 41152, "relations": [
                {"rel": "System.LinkTypes.Hierarchy-Forward",
                 "url": f"https://dev.azure.com/linkerengineer/_apis/wit/workItems/{i}"} for i in self.children
            ] + [{"rel": "ArtifactLink", "url": "vstfs:///GitHub/PullRequest/x%2f1"}]})
        if path.endswith("/_apis/wit/workitems") and request.method == "GET":
            ids = [int(i) for i in request.url.params["ids"].split(",")]
            if "Microsoft.VSTS.Common.ClosedDate" in request.url.params.get("fields", ""):
                return httpx.Response(200, json={"value": [
                    {"id": i, "fields": self.children[i]} for i in ids if i in self.children
                ]})
            if request.url.params.get("fields") == "System.AssignedTo":
                return httpx.Response(200, json={"value": [
                    {"id": i, "fields": {"System.AssignedTo": self.assigned[i]}} for i in ids
                ]})
            return httpx.Response(
                200,
                json={"value": [
                    {"id": i, "fields": {"System.Title": "Middleware", "System.WorkItemType": "Feature",
                                         "System.State": "Active",
                                         "System.IterationPath": self.iteration_of.get(i, "Deliver team\\SPRINT 1")}}
                    for i in ids
                ]},
            )
        if path.endswith("/updates") and request.method == "GET":
            updates = [{"rev": 1, "fields": {"System.Description": {"newValue": "first"}},
                        "revisedBy": {"displayName": "Vivian Fan"}}]
            updates += [{"rev": n + 2, "fields": {"System.Description": {"newValue": "edited"}},
                         "revisedBy": {"displayName": who}} for n, who in enumerate(self.description_editors)]
            updates.append({"rev": 99, "fields": {"System.State": {"newValue": "Active"}},
                            "revisedBy": {"displayName": "Someone Else"}})
            return httpx.Response(200, json={"value": updates})
        if "/_apis/wit/workitems/" in path and request.method == "PATCH":
            item_id = int(path.rsplit("/", 1)[1])
            self.patched.append({"id": item_id, "ops": json.loads(request.content)})
            return httpx.Response(200, json={"id": item_id})
        if "/_apis/wit/workitems/$" in path and request.method == "POST":
            self.next_id += 1
            wi_type = path.rsplit("$", 1)[1]
            self.created.append({"type": wi_type, "ops": json.loads(request.content)})
            return httpx.Response(200, json={"id": self.next_id})
        return httpx.Response(404, json={"message": f"unexpected {request.method} {path}"})


def _sprint(path: str, timeframe: str, start: str = "", finish: str = "") -> dict:
    attributes = {"timeFrame": timeframe}
    if start:
        attributes.update(startDate=f"{start}T00:00:00Z", finishDate=f"{finish}T00:00:00Z")
    return {"name": path.rsplit("\\", 1)[-1], "path": path, "attributes": attributes}


def _child(title: str, state: str, assignee: str | None, closed_days_ago: int | None = None) -> dict:
    now = datetime.now(timezone.utc)
    fields = {"System.Title": title, "System.WorkItemType": "Task", "System.State": state,
              "System.IterationPath": "Deliver team\\SPRINT 1", "System.ChangedDate": now.isoformat()}
    if assignee:
        fields["System.AssignedTo"] = {"displayName": assignee, "uniqueName": f"{assignee.split()[0].lower()}@x"}
    if closed_days_ago is not None:
        fields["Microsoft.VSTS.Common.ClosedDate"] = (now - timedelta(days=closed_days_ago)).isoformat()
    return fields


@dataclass
class FakeGitHub:
    """Answers the pull request listing of each repo; PRs name their work items with AB#."""

    pulls: dict[str, list[dict]] = field(default_factory=lambda: {
        "linkervision/lighthouse-saas-api": [
            {"number": 212, "title": "✨ add the 模型用量 page (AB#45669)", "body": "", "state": "closed",
             "merged_at": "2026-10-07T00:00:00Z", "html_url": "https://github.com/x/pull/212"},
            {"number": 211, "title": "fix: MAPP upstream failures", "body": None, "state": "open",
             "merged_at": None, "html_url": "https://github.com/x/pull/211"},
            {"number": 205, "title": "CD timer", "body": "Closes AB#45615", "state": "closed",
             "merged_at": "2026-10-05T00:00:00Z", "html_url": "https://github.com/x/pull/205"},
        ],
        "linkervision/deliver-heimdall": [
            {"number": 1, "title": "migrate", "body": "AB#41152 AB#45772", "state": "open",
             "merged_at": None, "html_url": "https://github.com/y/pull/1"},
        ],
    })

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization") != "Bearer gh-token":
            return httpx.Response(401, json={"message": "Bad credentials"})
        repo = request.url.path.removeprefix("/repos/").removesuffix("/pulls")
        return httpx.Response(200, json=self.pulls.get(repo, []))


@pytest.fixture
def fake_github() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
def fake_ado() -> FakeAdo:
    return FakeAdo()


@pytest.fixture
def settings(tmp_path) -> Settings:
    product = tmp_path / "knowledge" / "repo" / "apps" / "mw"
    (product / "docs" / "adr").mkdir(parents=True)
    (product / "app").mkdir()
    (product / "CONTEXT.md").write_text("# MW\n**Exclusion Area**: polygon\n", encoding="utf-8")
    (product / "docs" / "adr" / "0001-x.md").write_text("# ADR\n", encoding="utf-8")
    (product / "app" / "gate.py").write_text("def ensemble_gate():\n    return True\n", encoding="utf-8")
    screens = product / "app" / "ui_static"
    (screens / "js" / "features").mkdir(parents=True)
    (screens / "css").mkdir()
    (screens / "index.html").write_text("<title>Middleware Console</title>\n", encoding="utf-8")
    (screens / "js" / "features" / "index.js").write_text("export const FEATURES = [whitelistFeature];\n", encoding="utf-8")
    (screens / "css" / "base.css").write_text("body { margin: 0 }\n", encoding="utf-8")
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        auth_mode="dev",
        session_secret="test-secret",
        fernet_key=Fernet.generate_key().decode(),
        knowledge_root=tmp_path / "knowledge",
        knowledge_repo_dir="repo",
        knowledge_product_subdir="apps/mw",
        upload_dir=tmp_path / "uploads",
        teams_webhook_url="",
        public_base_url="http://sprite.test",
        github_token="gh-token",
    )


@pytest.fixture
def llm() -> FakeInterviewer:
    return FakeInterviewer()


@pytest.fixture
def notifier(settings) -> Notifier:
    return Notifier(settings)


@pytest.fixture
async def app(settings, llm, notifier, fake_ado, fake_github):
    application = create_app(settings, llm=llm, notifier=notifier, background_jobs=False)
    application.state.ado_transport = httpx.MockTransport(fake_ado.handler)
    application.state.github_transport = httpx.MockTransport(fake_github.handler)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
def deps(app):
    return app.state.deps


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://sprite.test")


async def login(app, email: str) -> httpx.AsyncClient:
    c = client_for(app)
    r = await c.post("/api/auth/login", json={"email": email, "password": "x"})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
async def vivian(app):
    c = await login(app, "vivian@linkervision.com")
    yield c
    await c.aclose()


@pytest.fixture
async def kevin(app):
    c = await login(app, "kevin@linkervision.com")
    yield c
    await c.aclose()
