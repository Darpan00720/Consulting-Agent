"""Load specialist agent prompts from the plugin's agents/*.md files.

The markdown body (frontmatter stripped) becomes the system prompt for the
corresponding Claude API call — the same prompts the Claude Code plugin uses,
so dashboard engagements and CLI engagements run the same consultants.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

from app import config


@lru_cache(maxsize=None)
def agent_system_prompt(agent_name: str) -> str:
    path = config.AGENTS_DIR / f"{agent_name}.md"
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        # strip YAML frontmatter: ---\n...\n---\n
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    return text.strip()


@lru_cache(maxsize=1)
def vault_framework_index() -> str:
    """A name-only index of the governed framework vault, for the selector."""
    names = sorted(
        p.stem for p in config.VAULT_FRAMEWORKS_DIR.glob("*.md") if not p.stem.startswith("_")
    )
    return "\n".join(f"- {n}" for n in names)


def framework_note(name: str) -> str | None:
    """Full text of one vault framework note, if it exists."""
    path = config.VAULT_FRAMEWORKS_DIR / f"{name}.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    return text.strip()


_TOKEN_RE = re.compile(r"[a-z][a-z0-9\-]{2,}")
_STOPWORDS = frozenset(
    "the and for with that this from are was were has have not but its can "
    "will would should could may might all any each which what when where "
    "how who why into out over under between within without more most other "
    "some such than then them they their there these those you your our".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


@lru_cache(maxsize=1)
def _vault_corpus() -> list[tuple[str, str, Counter[str]]]:
    """(name, stripped body, term counts) for every vault note — built once."""
    corpus: list[tuple[str, str, Counter[str]]] = []
    for path in sorted(config.VAULT_FRAMEWORKS_DIR.glob("*.md")):
        if path.stem.startswith("_"):
            continue
        body = _strip_frontmatter(path.read_text(encoding="utf-8"))
        # Note names are the strongest signal — weight them into the counts.
        counts = Counter(_tokens(body))
        for token in _tokens(path.stem.replace("-", " ")):
            counts[token] += 5
        corpus.append((path.stem, body, counts))
    return corpus


def rank_vault_notes(query_text: str, *, top_k: int = 5) -> list[str]:
    """TF-IDF-ranked vault note names most relevant to the query text.

    Lightweight retrieval (pure Python, no embedding model): scores every
    vault note against the case + framing text so relevant frameworks are
    found even when the selector didn't name them verbatim.
    """
    corpus = _vault_corpus()
    if not corpus:
        return []
    n_docs = len(corpus)
    df: Counter[str] = Counter()
    for _, _, counts in corpus:
        df.update(counts.keys())
    query = Counter(_tokens(query_text))
    scored: list[tuple[float, str]] = []
    for name, _, counts in corpus:
        score = 0.0
        for term, q_freq in query.items():
            if term in counts:
                idf = math.log(1 + n_docs / df[term])
                score += q_freq * math.log(1 + counts[term]) * idf
        # normalize by doc length so long notes don't dominate
        length = sum(counts.values())
        if score > 0 and length > 0:
            scored.append((score / math.sqrt(length), name))
    scored.sort(reverse=True)
    return [name for _, name in scored[:top_k]]


def selected_framework_notes(frame_text: str, *, cap_chars: int = 8000) -> str:
    """Retrieve full vault notes for the engagement — RAG over the vault.

    Two retrieval passes, merged: (1) exact-name hits — every framework the
    selector explicitly named; (2) TF-IDF ranked hits — the vault notes most
    relevant to the framing text even if not named verbatim. Named hits come
    first (the selector's judgment outranks the ranker). Capped so the
    injected knowledge never crowds out the case context on small-context
    providers.
    """
    low = frame_text.lower()
    named = sorted(
        {
            p.stem
            for p in config.VAULT_FRAMEWORKS_DIR.glob("*.md")
            if not p.stem.startswith("_") and p.stem.lower() in low
        }
    )
    ranked = [n for n in rank_vault_notes(frame_text) if n not in named]
    parts: list[str] = []
    used = 0
    for name in named + ranked:
        note = framework_note(name)
        if not note:
            continue
        body = _strip_frontmatter(note)
        remaining = cap_chars - used
        if remaining <= 200:  # no room for a meaningful excerpt
            break
        if len(body) > remaining:
            body = body[:remaining] + "\n[... note truncated]"
        parts.append(f"### {name}\n\n{body}")
        used += len(body)
    return "\n\n".join(parts)
