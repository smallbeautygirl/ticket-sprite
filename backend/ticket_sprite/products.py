"""Products the sprite can interview about (ADR-0004).

A Product names its Knowledge Source (a branch and a directory of KNOWLEDGE_REPO_SOURCE, kept in its
own clone), the default Parent for its Tickets, what PM and FAE may see besides documents, what nobody
needs to see, and notes that tell the interviewer how this product's sources are laid out.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .config import Settings


@dataclass(frozen=True)
class Product:
    id: str
    label: str
    # PM and FAE see documents plus these files (fnmatch on the path relative to the product root;
    # `*` also crosses directories): the screens, so what they saw can be mapped to the glossary
    screen_globs: tuple[str, ...] = ()
    screens_note: str = ""  # how the docs-depth note names those screens
    # Hidden at every depth: bulky data that only slows searches down
    hidden_globs: tuple[str, ...] = ()
    notes: str = ""  # interviewer guidance specific to this product (a markdown bullet list)
    # Where it lives; filled in from Settings by `products()`
    clone_dir: str = ""
    branch: str = "main"
    subdir: str = ""
    default_parent_id: int = 0

    def root(self, settings: Settings) -> Path:
        return settings.knowledge_root / self.clone_dir / self.subdir


MIDDLEWARE = Product(
    id="middleware",
    label="Middleware",
    # The console's pages (their on-screen words and hash routes), without its styles or vendored libraries
    screen_globs=("app/ui_static/*.html", "app/ui_static/js/*"),
    screens_note="the console's screens (app/ui_static)",
    notes=(
        "- The middleware console's screens are in app/ui_static. A console page URL such as "
        "https://<host>/middleware-ui/#/whitelist names a page by the id after \"#/\": find it in "
        "app/ui_static/js/features (each feature's id, title and description). Use the screens to map what the "
        "Requester saw on screen to glossary terms and the API behind it, but write the Spec in the words on "
        "screen and in product terms, not code."
    ),
)

TAIPEI_MRT = Product(
    id="taipei_mrt",
    label="北捷",
    screen_globs=("frontend/src/App.tsx", "frontend/src/*components/*.tsx", "frontend/src/modules/*/constants.ts"),
    screens_note="the simulator's screens (frontend/src components and module constants)",
    hidden_globs=("frontend/public/scenarios/*",),
    notes=(
        "- This product is the 台北捷運文湖線 dynamic passenger-load simulator: frontend/ is the live monitoring "
        "UI (React), train-sim-sdk/ the simulation engine, a copy of upstream mirra-trainSim (see its "
        "PROVENANCE.md). The UI is organised by module under frontend/src/modules (setup, line, incident, "
        "diagram, simulation).\n"
        "- Scenario JSON under frontend/public/scenarios is not visible; train-sim-sdk/docs/SCENARIO_FORMAT.md "
        "describes the format. It is tied to the SDK version.\n"
        "- There is no CONTEXT.md glossary yet: take terms from the READMEs, the SDK docs and the words on "
        "screen, and record every term the Requester uses that those do not define in new_terms."
    ),
)


def _all(settings: Settings) -> dict[str, Product]:
    return {
        MIDDLEWARE.id: replace(
            MIDDLEWARE,
            clone_dir=settings.knowledge_repo_dir,
            branch=settings.knowledge_branch,
            subdir=settings.knowledge_product_subdir,
            default_parent_id=settings.ado_default_parent_id,
        ),
        TAIPEI_MRT.id: replace(
            TAIPEI_MRT,
            clone_dir=settings.taipei_mrt_repo_dir,
            branch=settings.taipei_mrt_branch,
            subdir=settings.taipei_mrt_subdir,
            default_parent_id=settings.taipei_mrt_parent_id,
        ),
    }


def products(settings: Settings) -> dict[str, Product]:
    """The enabled Products, in the order the UI offers them (Middleware when none is)."""
    known = _all(settings)
    enabled = [p.strip() for p in settings.products_enabled.split(",") if p.strip()]
    return {pid: known[pid] for pid in enabled if pid in known} or {MIDDLEWARE.id: known[MIDDLEWARE.id]}


def product(settings: Settings, product_id: str) -> Product:
    """An Interview's Product. One disabled since keeps working, so its Interviews still open."""
    known = _all(settings)
    return known.get(product_id, known[MIDDLEWARE.id])


def label(product_id: str) -> str:
    return {p.id: p.label for p in (MIDDLEWARE, TAIPEI_MRT)}.get(product_id, product_id)
