"""Offline tests for SOP retrieval — no Anthropic API required.

Run: python agent/tests/test_index.py   (or: pytest agent/tests)
"""
from __future__ import annotations

import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

from sop_index import SOPIndex, load_sops  # noqa: E402


def test_sops_load():
    sops = load_sops()
    assert len(sops) >= 15, f"expected >=15 SOPs, got {len(sops)}"
    ids = {s.sop_id for s in sops}
    assert "DB-001" in ids
    assert "API-002" in ids


def test_db_pool_log_ranks_db001_first():
    idx = SOPIndex()
    log = (AGENT_DIR / "samples" / "incident-db.log").read_text()
    hits = idx.retrieve(log, top_k=3)
    assert hits, "expected at least one candidate"
    assert hits[0].sop.sop_id == "DB-001", f"top hit was {hits[0].sop.sop_id}"


def test_deploy_5xx_log_ranks_api002_first():
    idx = SOPIndex()
    log = (AGENT_DIR / "samples" / "incident-api-deploy.log").read_text()
    hits = idx.retrieve(log, top_k=3)
    assert hits[0].sop.sop_id == "API-002", f"top hit was {hits[0].sop.sop_id}"


def test_uncovered_log_has_weak_or_no_match():
    """A GPU/ML incident has no dedicated SOP; the top score should be low."""
    idx = SOPIndex()
    log = (AGENT_DIR / "samples" / "incident-uncovered.log").read_text()
    hits = idx.retrieve(log, top_k=3)
    top = hits[0].score if hits else 0.0
    assert top < 8.0, f"uncovered incident matched too strongly (score {top})"


def _run():
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ✓ {name}")
            passed += 1
    print(f"\n{passed} test(s) passed.")


if __name__ == "__main__":
    _run()
