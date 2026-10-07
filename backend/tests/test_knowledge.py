from __future__ import annotations

import pytest

from ticket_sprite.engine.templates import DEFAULT_TEMPLATE, TEMPLATES, depth_for
from ticket_sprite.knowledge import Depth, KnowledgeError, KnowledgeSource
from ticket_sprite.models import Role


def test_docs_depth_hides_code(settings):
    ks = KnowledgeSource(root=settings.product_root, depth=Depth.DOCS)
    listing = ks.list_files()
    assert "CONTEXT.md" in listing and "docs/adr/0001-x.md" in listing
    assert "gate.py" not in listing
    assert "(no matches)" == ks.grep("ensemble_gate")
    with pytest.raises(KnowledgeError):
        ks.read_file("app/gate.py")
    assert "Exclusion Area" in ks.read_file("CONTEXT.md")


def test_docs_depth_sees_the_console_screens(settings):
    """PM and Solution Engineer find things on the console, so its pages are visible without code access."""
    ks = KnowledgeSource(root=settings.product_root, depth=Depth.DOCS)
    listing = ks.list_files()
    assert "app/ui_static/index.html" in listing and "app/ui_static/js/features/index.js" in listing
    assert "base.css" not in listing
    assert "whitelistFeature" in ks.read_file("app/ui_static/js/features/index.js")


def test_code_depth_reads_code(settings):
    ks = KnowledgeSource(root=settings.product_root, depth=Depth.CODE)
    assert "app/gate.py:1:" in ks.grep("ensemble_gate")
    assert "1\tdef ensemble_gate" in ks.read_file("app/gate.py")


@pytest.mark.parametrize("path", ["../../secret", "/etc/passwd", "app/../../x"])
def test_paths_cannot_escape(settings, path):
    ks = KnowledgeSource(root=settings.product_root, depth=Depth.CODE)
    with pytest.raises(KnowledgeError):
        ks.read_file(path)


def test_role_depth_and_defaults():
    assert depth_for(Role.PM) is Depth.DOCS and depth_for(Role.FAE) is Depth.DOCS
    assert depth_for(Role.RD) is Depth.CODE
    assert set(DEFAULT_TEMPLATE.values()) <= set(TEMPLATES)
