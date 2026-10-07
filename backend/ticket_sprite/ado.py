"""Azure DevOps: the ADO Credential (ADR-0001) and the work-item REST calls.

`AdoCredentialProvider` is the seam that lets v1's personal PAT be swapped for
Entra delegated OAuth later without touching callers.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from cryptography.fernet import Fernet, InvalidToken

from .config import Settings
from .models import RequestType, User

API_VERSION = "7.1"

WORK_ITEM_TYPE = {
    RequestType.FEATURE: "User Story",
    RequestType.BUG: "Bug",
    RequestType.TASK: "Task",
}

SEVERITIES = ["1 - Critical", "2 - High", "3 - Medium", "4 - Low"]


class AdoCredentialMissing(Exception):
    """The user has not connected an ADO Credential yet (or it was rejected)."""


class AdoError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"ADO {status}: {message}")
        self.status = status


# ---------- ADO Credential ----------


class PatCipher:
    def __init__(self, key: str):
        if not key:
            raise RuntimeError("FERNET_KEY is not configured")
        self._fernet = Fernet(key.encode())

    def encrypt(self, pat: str) -> str:
        return self._fernet.encrypt(pat.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise AdoCredentialMissing("stored PAT cannot be decrypted") from exc


def pat_auth_header(pat: str) -> dict[str, str]:
    raw = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {raw}"}


class AdoCredentialProvider:
    """Resolves the Authorization header for acting as a given user."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def auth_header(self, user: User | None) -> dict[str, str]:
        if user is not None and user.ado_pat_encrypted:
            return pat_auth_header(PatCipher(self._settings.fernet_key).decrypt(user.ado_pat_encrypted))
        if self._settings.ado_dev_pat:
            return pat_auth_header(self._settings.ado_dev_pat)
        raise AdoCredentialMissing("尚未連結 Azure DevOps")


# ---------- REST client ----------


@dataclass(frozen=True)
class AdoIdentity:
    display_name: str
    email: str | None


@dataclass(frozen=True)
class WorkItemSummary:
    id: int
    title: str
    work_item_type: str
    state: str


@dataclass(frozen=True)
class CreatedWorkItem:
    id: int
    url: str


class AdoClient:
    def __init__(
        self,
        settings: Settings,
        auth_header: dict[str, str],
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._s = settings
        self._headers = auth_header
        self._transport = transport

    @property
    def _org_url(self) -> str:
        return f"https://dev.azure.com/{self._s.ado_org}"

    @property
    def _project_url(self) -> str:
        return f"{self._org_url}/{quote(self._s.ado_project)}"

    def work_item_web_url(self, item_id: int) -> str:
        return f"{self._project_url}/_workitems/edit/{item_id}"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=30, headers=self._headers, transport=self._transport)

    @staticmethod
    def _raise_for(resp: httpx.Response) -> None:
        if resp.status_code in (401, 203):
            # ADO answers 203 + sign-in HTML for a bad PAT
            raise AdoCredentialMissing("Azure DevOps 憑證無效或已過期")
        if resp.status_code >= 400:
            try:
                msg = resp.json().get("message", resp.text)
            except ValueError:
                msg = resp.text
            raise AdoError(resp.status_code, msg[:500])

    async def whoami(self) -> AdoIdentity:
        async with self._client() as c:
            resp = await c.get(f"{self._org_url}/_apis/connectionData", params={"api-version": "7.1-preview"})
        self._raise_for(resp)
        user = resp.json().get("authenticatedUser") or {}
        email = (user.get("properties") or {}).get("Account", {}).get("$value")
        return AdoIdentity(display_name=user.get("providerDisplayName") or "?", email=email)

    async def get_work_items(self, ids: list[int]) -> list[WorkItemSummary]:
        if not ids:
            return []
        async with self._client() as c:
            resp = await c.get(
                f"{self._org_url}/_apis/wit/workitems",
                params={
                    "ids": ",".join(str(i) for i in ids[:200]),
                    "fields": "System.Id,System.Title,System.WorkItemType,System.State",
                    "errorPolicy": "omit",
                    "api-version": API_VERSION,
                },
            )
        self._raise_for(resp)
        out = []
        for item in resp.json().get("value") or []:
            if not item:
                continue
            f = item.get("fields", {})
            out.append(
                WorkItemSummary(
                    id=item["id"],
                    title=f.get("System.Title", ""),
                    work_item_type=f.get("System.WorkItemType", ""),
                    state=f.get("System.State", ""),
                )
            )
        return out

    async def search_work_items(self, query: str, limit: int = 20) -> list[WorkItemSummary]:
        query = query.strip()
        if query.lstrip("#").isdigit():
            return await self.get_work_items([int(query.lstrip("#"))])
        escaped = query.replace("'", "''")
        wiql = (
            "SELECT [System.Id] FROM WorkItems "
            "WHERE [System.TeamProject] = @project "
            f"AND [System.Title] CONTAINS '{escaped}' "
            "AND [System.State] NOT IN ('Closed', 'Removed', 'Done') "
            "ORDER BY [System.ChangedDate] DESC"
        )
        async with self._client() as c:
            resp = await c.post(
                f"{self._project_url}/_apis/wit/wiql",
                params={"$top": limit, "api-version": API_VERSION},
                json={"query": wiql},
            )
        self._raise_for(resp)
        ids = [w["id"] for w in resp.json().get("workItems", [])][:limit]
        return await self.get_work_items(ids)

    async def upload_attachment(self, filename: str, data: bytes) -> str:
        async with self._client() as c:
            resp = await c.post(
                f"{self._project_url}/_apis/wit/attachments",
                params={"fileName": filename, "api-version": API_VERSION},
                content=data,
                headers={"Content-Type": "application/octet-stream"},
            )
        self._raise_for(resp)
        return resp.json()["url"]

    async def create_work_item(
        self,
        *,
        request_type: RequestType,
        title: str,
        description_html: str,
        parent_id: int | None,
        tags: list[str],
        priority: int | None,
        severity: str | None,
        attachment_urls: list[str],
    ) -> CreatedWorkItem:
        wi_type = WORK_ITEM_TYPE[request_type]
        ops: list[dict] = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
            {"op": "add", "path": "/fields/System.Description", "value": description_html},
            {"op": "add", "path": "/fields/System.AreaPath", "value": self._s.ado_area_path},
            {"op": "add", "path": "/fields/System.Tags", "value": "; ".join(tags)},
        ]
        if request_type is RequestType.BUG:
            # Bug forms show Repro Steps rather than Description
            ops.append({"op": "add", "path": "/fields/Microsoft.VSTS.TCM.ReproSteps", "value": description_html})
            if severity:
                ops.append({"op": "add", "path": "/fields/Microsoft.VSTS.Common.Severity", "value": severity})
        if priority:
            ops.append({"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority", "value": priority})
        if parent_id:
            ops.append(
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {
                        "rel": "System.LinkTypes.Hierarchy-Reverse",
                        "url": f"{self._org_url}/_apis/wit/workItems/{parent_id}",
                    },
                }
            )
        for url in attachment_urls:
            ops.append({"op": "add", "path": "/relations/-", "value": {"rel": "AttachedFile", "url": url}})

        async with self._client() as c:
            resp = await c.post(
                f"{self._project_url}/_apis/wit/workitems/${quote(wi_type)}",
                params={"api-version": API_VERSION},
                json=ops,
                headers={"Content-Type": "application/json-patch+json"},
            )
        self._raise_for(resp)
        item_id = resp.json()["id"]
        return CreatedWorkItem(id=item_id, url=self.work_item_web_url(item_id))
