"""Load specialist agent prompts from the plugin's agents/*.md files.

The markdown body (frontmatter stripped) becomes the system prompt for the
corresponding Claude API call — the same prompts the Claude Code plugin uses,
so dashboard engagements and CLI engagements run the same consultants.
"""

from __future__ import annotations

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
