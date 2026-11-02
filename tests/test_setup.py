"""Checks that the environment is set up. These should pass right away."""

import shutil

import pytest


def test_package_imports():
    import schemadiagram.cli
    import schemadiagram.model
    import schemadiagram.parser
    import schemadiagram.render_dot
    import schemadiagram.tokenizer  # noqa: F401


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed yet (winget install graphviz)")
def test_graphviz_renders(tmp_path):
    from pathlib import Path

    from schemadiagram.render_dot import render

    out = render("digraph { a -> b }", tmp_path / "smoke.svg")
    assert Path(out).read_text().lstrip().startswith("<?xml")
