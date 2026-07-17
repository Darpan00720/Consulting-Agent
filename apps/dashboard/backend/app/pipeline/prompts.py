"""Load specialist agent prompts from the plugin's agents/*.md files.

The markdown body (frontmatter stripped) becomes the system prompt for the
corresponding Claude API call — the same prompts the Claude Code plugin uses,
so dashboard engagements and CLI engagements run the same consultants.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import cache, lru_cache

from app import config


@cache
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
        p.stem
        for p in config.VAULT_FRAMEWORKS_DIR.glob("*.md")
        if not p.stem.startswith("_")
    )
    return "\n".join(f"- {n}" for n in names)


def framework_note(name: str) -> str | None:
    """Full text of one vault framework note, if it exists.

    ``name`` is expected to be a bare note stem (today it only ever comes from
    globbed vault filenames), but this is the one place a caller-influenced
    string is joined to a filesystem path — so it is defended in depth against
    traversal: a name with a path separator or ``..`` is rejected, and the
    resolved path is confirmed to sit inside the vault directory before any
    read. A malformed name returns ``None``, exactly like a missing note.
    """
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    vault = config.VAULT_FRAMEWORKS_DIR.resolve()
    path = (vault / f"{name}.md").resolve()
    if vault not in path.parents or not path.is_file():
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
    [
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "were",
        "has",
        "have",
        "not",
        "but",
        "its",
        "can",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "all",
        "any",
        "each",
        "which",
        "what",
        "when",
        "where",
        "how",
        "who",
        "why",
        "into",
        "out",
        "over",
        "under",
        "between",
        "within",
        "without",
        "more",
        "most",
        "other",
        "some",
        "such",
        "than",
        "then",
        "them",
        "they",
        "their",
        "there",
        "these",
        "those",
        "you",
        "your",
        "our",
    ]
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


# --- what the client actually asked -----------------------------------------

# Below this many explicit questions, a prompt is a narrative brief that happens
# to contain a question or two ("Should it add a cafe format?") — the normal
# issue-tree pipeline handles it. At or above it, the client has handed us a
# structured question list and expects each one answered; a synthesized memo
# that covers none of them is a wrong answer no matter how well written.
EXPLICIT_QUESTION_THRESHOLD = 5

# A bare "Question 12" / "Q12." line, used as a delimiter between asks.
_QUESTION_MARKER = re.compile(r"^\s*(?:question|q)\s*(\d+)\s*[.):\-]?\s*$", re.I)
# Section headers ("Section 3 — Financial Analysis") end the preceding question.
_SECTION_MARKER = re.compile(r"^\s*(?:section|part)\b", re.I)
_INLINE_LABEL = re.compile(r"^(?:question|q)\s*\d+\s*[.):\-]?\s*", re.I)
_SEPARATOR = re.compile(r"^[\s\u2014\u2013\-_=*#>·•]*$")


def explicit_questions(case_prompt: str) -> list[str]:
    """Questions the client asked, in order, verbatim.

    Deterministic on purpose: this is the checklist the reviewer grades coverage
    against, so it must come from the CLIENT'S text — never from anything the
    pipeline generated. The reviewer used to judge coverage by the issue tree,
    which the pipeline invents itself, so it could not notice that the client's
    own questions went unanswered.

    Two shapes are supported:

    * **Marked** — a ``Question 38`` line followed by the ask. The whole block is
      captured, because these are frequently multi-line and frequently do NOT end
      in a question mark::

          Question 38
          Each store serves 600 customers/day.
          Traffic falls 8%.
          Estimate annual revenue impact.        <- imperative, no "?"

      Taking only "?" lines would silently drop exactly the arithmetic asks.
    * **Unmarked** — plain lines ending in "?".
    """
    lines = case_prompt.splitlines()
    if (
        sum(1 for ln in lines if _QUESTION_MARKER.match(ln))
        >= EXPLICIT_QUESTION_THRESHOLD
    ):
        return _marked_questions(lines)
    return _unmarked_questions(lines)


def _marked_questions(lines: list[str]) -> list[str]:
    """Each `Question N` marker opens a block that runs to the next marker or
    section header. Keeps multi-line asks (and their numbers) intact."""
    out: list[str] = []
    buf: list[str] | None = None
    for raw in lines:
        if _QUESTION_MARKER.match(raw):
            if buf:
                out.append(" ".join(buf).strip())
            buf = []
            continue
        if buf is None:
            continue
        if _SECTION_MARKER.match(raw):  # a section header closes the open block
            if buf:
                out.append(" ".join(buf).strip())
            buf = None
            continue
        line = raw.strip()
        if line and not _SEPARATOR.match(line):
            buf.append(line)
    if buf:
        out.append(" ".join(buf).strip())
    return [q for q in out if len(q) >= 12]


def _unmarked_questions(lines: list[str]) -> list[str]:
    out: list[str] = []
    for raw in lines:
        line = raw.strip().lstrip("#-*\u2022> ").strip()
        if not line.endswith("?"):
            continue
        line = _INLINE_LABEL.sub("", line).strip()
        if len(line) >= 12 and line not in out:
            out.append(line)
    return out


def question_checklist(case_prompt: str) -> str:
    """The client's questions as a numbered checklist, or "" when the prompt is
    a narrative brief rather than a structured question list."""
    asked = explicit_questions(case_prompt)
    if len(asked) < EXPLICIT_QUESTION_THRESHOLD:
        return ""
    return "\n".join(f"Q{i}. {q}" for i, q in enumerate(asked, 1))
