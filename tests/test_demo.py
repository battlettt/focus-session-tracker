"""The browser demo must show exactly what the CLI prints."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_builder():
    spec = importlib.util.spec_from_file_location("build_demo", ROOT / "scripts" / "build_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_page_matches_current_cli_output():
    builder = load_builder()
    expected = builder.build()
    actual = (ROOT / "demo" / "index.html").read_text(encoding="utf-8")
    assert actual == expected, "demo/index.html is stale: run python3 scripts/build_demo.py"


def test_demo_is_offline_only():
    page = (ROOT / "demo" / "index.html").read_text(encoding="utf-8")
    for marker in ("http://", "https://", "<script", "<link"):
        assert marker not in page, marker
