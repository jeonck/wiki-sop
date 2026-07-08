"""SOP index + lexical retrieval.

Loads every SOP under content/docs/sop/, parses its frontmatter + body, and
ranks SOPs against an incoming error log using a dependency-light lexical
scorer weighted toward the `symptoms` field (which is authored precisely for
this purpose). No embedding provider required — the agent reads the raw
Markdown the same way `git pull` + a RAG indexer would.

This module has NO Anthropic dependency and is unit-testable offline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SOP_DIR = REPO_ROOT / "content" / "docs" / "sop"

_TOKEN_RE = re.compile(r"[a-z0-9_]+")
# Common words that carry no diagnostic signal — excluded from token overlap.
_STOPWORDS = frozenset(
    "the a an of to for and or in on at is are was were be been being this that "
    "with from by as it its into over per not no error errors sop".split()
)


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1}


@dataclass
class SOP:
    sop_id: str
    title: str
    category: str
    severity: str
    symptoms: list[str]
    target_system: list[str]
    tags: list[str]
    escalation: dict
    verification_metrics: list[dict]
    body: str
    path: Path
    frontmatter: dict = field(repr=False, default_factory=dict)

    def full_text(self) -> str:
        """Frontmatter-derived searchable text + body, for prompt context."""
        return self.path.read_text(encoding="utf-8")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = yaml.safe_load(text[3:end]) or {}
    body = text[end + 4 :].lstrip("\n")
    return fm, body


def load_sops(sop_dir: Path = SOP_DIR) -> list[SOP]:
    sops: list[SOP] = []
    for md in sorted(sop_dir.rglob("*.md")):
        if md.name == "_index.md":
            continue
        fm, body = _parse_frontmatter(md.read_text(encoding="utf-8"))
        if not fm.get("sop_id"):
            continue
        sops.append(
            SOP(
                sop_id=fm["sop_id"],
                title=fm.get("title", ""),
                category=fm.get("category", ""),
                severity=fm.get("severity", ""),
                symptoms=list(fm.get("symptoms", []) or []),
                target_system=list(fm.get("target_system", []) or []),
                tags=list(fm.get("tags", []) or []),
                escalation=dict(fm.get("escalation", {}) or {}),
                verification_metrics=list(fm.get("verification_metrics", []) or []),
                body=body,
                path=md,
                frontmatter=fm,
            )
        )
    return sops


@dataclass
class ScoredSOP:
    sop: SOP
    score: float
    matched_symptoms: list[str]


class SOPIndex:
    """In-memory lexical index over the SOP library."""

    # Field weights — symptoms dominate because they are authored as log signatures.
    W_SYMPTOM_PHRASE = 6.0   # a full symptom phrase substring-matches the log
    W_SYMPTOM_TOKEN = 1.5    # per shared token between a symptom and the log
    W_TITLE_TOKEN = 1.0
    W_TAG_TOKEN = 1.2
    W_TARGET_TOKEN = 2.0     # service name appearing in the log is a strong signal

    def __init__(self, sops: list[SOP] | None = None):
        self.sops = sops if sops is not None else load_sops()

    def _score(self, sop: SOP, log: str, log_tokens: set[str]) -> ScoredSOP:
        log_l = log.lower()
        score = 0.0
        matched: list[str] = []

        for sym in sop.symptoms:
            sym_l = sym.lower()
            # Strong signal: a distinctive slice of the symptom appears verbatim.
            core = re.split(r"[<>]|\bfor\b|\bsustained\b", sym_l)[0].strip()
            if len(core) >= 6 and core in log_l:
                score += self.W_SYMPTOM_PHRASE
                matched.append(sym)
            shared = _tokens(sym) & log_tokens
            score += self.W_SYMPTOM_TOKEN * len(shared)

        score += self.W_TITLE_TOKEN * len(_tokens(sop.title) & log_tokens)
        for tag in sop.tags:
            score += self.W_TAG_TOKEN * len(_tokens(tag) & log_tokens)
        for svc in sop.target_system:
            if svc.lower() in log_l:
                score += self.W_TARGET_TOKEN
            else:
                score += 0.5 * len(_tokens(svc) & log_tokens)

        return ScoredSOP(sop=sop, score=score, matched_symptoms=matched)

    def retrieve(self, log: str, top_k: int = 3) -> list[ScoredSOP]:
        log_tokens = _tokens(log)
        scored = [self._score(s, log, log_tokens) for s in self.sops]
        scored = [s for s in scored if s.score > 0]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]


if __name__ == "__main__":
    import sys

    idx = SOPIndex()
    print(f"Loaded {len(idx.sops)} SOPs from {SOP_DIR}")
    log = sys.stdin.read() if not sys.stdin.isatty() else "connection pool exhausted, login-api p95 latency 1200ms"
    for hit in idx.retrieve(log):
        print(f"  {hit.sop.sop_id:14} score={hit.score:6.1f}  {hit.sop.title}")
