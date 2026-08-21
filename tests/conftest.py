from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "source").mkdir()
    (tmp_path / "artifact").mkdir()
    (tmp_path / "policy").mkdir()
    (tmp_path / "source" / "draft.txt").write_text(
        "synthetic draft\n", encoding="utf-8", newline="\n"
    )
    (tmp_path / "artifact" / "report.txt").write_text(
        "synthetic report\n", encoding="utf-8", newline="\n"
    )
    (tmp_path / "policy" / "review.json").write_text(
        json.dumps({"policy": "synthetic/v1", "required": ["review"]}) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return tmp_path
