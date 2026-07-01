"""Write the generated Engagement State JSON Schema to ``schema/``.

Run via ``make schema``. The committed schema must always equal this output
(enforced by ``tests/test_schema_generation.py``).
"""

from __future__ import annotations

from pathlib import Path

from state.schema import render

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schema" / "engagement-state.schema.json"
)


def main() -> None:
    _SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SCHEMA_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {_SCHEMA_PATH}")


if __name__ == "__main__":
    main()
