from __future__ import annotations

import json
from dataclasses import dataclass, field

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
    # tag definitions the project already has, and whether this user may create new ones
    existing_tags: set[str] = field(default_factory=lambda: {"ticket-sprite", "role:pm"})
    can_create_tags: bool = True

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
        if path.endswith("/_apis/wit/workitems") and request.method == "GET":
            ids = [int(i) for i in request.url.params["ids"].split(",")]
            if request.url.params.get("fields") == "System.AssignedTo":
                return httpx.Response(200, json={"value": [
                    {"id": i, "fields": {"System.AssignedTo": self.assigned[i]}} for i in ids
                ]})
            return httpx.Response(
                200,
                json={"value": [
                    {"id": i, "fields": {"System.Title": "Middleware", "System.WorkItemType": "Feature",
                                         "System.State": "Active"}}
                    for i in ids
                ]},
            )
        if path.endswith("/_apis/wit/tags") and request.method == "GET":
            return httpx.Response(200, json={"value": [{"name": t} for t in sorted(self.existing_tags)]})
        if "/_apis/wit/workitems/$" in path and request.method == "POST":
            ops = json.loads(request.content)
            tags = next((op["value"] for op in ops if op["path"] == "/fields/System.Tags"), "")
            new = [t for t in tags.split("; ") if t and t.lower() not in self.existing_tags]
            if new and not self.can_create_tags:
                return httpx.Response(403, json={
                    "message": "TF401289: The current user does not have permissions to create tags."})
            self.next_id += 1
            wi_type = path.rsplit("$", 1)[1]
            self.created.append({"type": wi_type, "ops": json.loads(request.content)})
            return httpx.Response(200, json={"id": self.next_id})
        return httpx.Response(404, json={"message": f"unexpected {request.method} {path}"})


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
    )


@pytest.fixture
def llm() -> FakeInterviewer:
    return FakeInterviewer()


@pytest.fixture
def notifier(settings) -> Notifier:
    return Notifier(settings)


@pytest.fixture
async def app(settings, llm, notifier, fake_ado):
    application = create_app(settings, llm=llm, notifier=notifier, background_jobs=False)
    application.state.ado_transport = httpx.MockTransport(fake_ado.handler)
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
