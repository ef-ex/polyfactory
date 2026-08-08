"""
Skills registry — the extendable recipe library the MCP serves to agents.

Pure stdlib (no `hou`, no `mcp`) so it is testable standalone. Each skill is a
markdown file in ./skills/ with simple frontmatter. The library grows over time:
agents bank reliable procedures via save_skill(), future agents discover them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

SKILLS_DIR = Path(__file__).parent / "skills"
_SLUG_RE = re.compile(r"[^a-z0-9\-]+")


def _parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    """Split `---`-delimited frontmatter from the markdown body.

    Frontmatter is simple `key: value` lines (no nested YAML). `tags` is parsed
    as a comma-separated list. Returns (meta, body).
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: Dict[str, Any] = {}
    for line in parts[1].strip().splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "tags":
            meta[key] = [t.strip() for t in value.split(",") if t.strip()]
        else:
            meta[key] = value
    return meta, parts[2].lstrip("\n")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.strip().lower()).strip("-")


def _skill_files() -> List[Path]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(
        p for p in SKILLS_DIR.glob("*.md") if p.name.lower() != "readme.md"
    )


def list_skills() -> List[Dict[str, Any]]:
    """Discovery: summary metadata for every skill (not the bodies)."""
    out: List[Dict[str, Any]] = []
    for path in _skill_files():
        meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
        out.append({
            "name": meta.get("name", path.stem),
            "description": meta.get("description", ""),
            "when_to_use": meta.get("when_to_use", ""),
            "tags": meta.get("tags", []),
        })
    return out


def get_skill(name: str) -> str:
    """Retrieval: the full markdown of one skill, by `name` or filename stem."""
    target = _slugify(name)
    for path in _skill_files():
        meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if _slugify(meta.get("name", path.stem)) == target or path.stem == name:
            return path.read_text(encoding="utf-8")
    available = ", ".join(s["name"] for s in list_skills()) or "(none)"
    raise KeyError(f"No skill named '{name}'. Available: {available}")


def save_skill(
    name: str,
    description: str,
    when_to_use: str,
    body: str,
    tags: Optional[List[str]] = None,
) -> str:
    """Self-extension: write a new skill (or update an existing one). Returns the path."""
    slug = _slugify(name)
    if not slug:
        raise ValueError(f"Invalid skill name: {name!r}")
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    tag_line = ", ".join(tags) if tags else ""
    content = (
        "---\n"
        f"name: {slug}\n"
        f"description: {description.strip()}\n"
        f"when_to_use: {when_to_use.strip()}\n"
        f"tags: {tag_line}\n"
        "---\n\n"
        f"{body.strip()}\n"
    )
    path = SKILLS_DIR / f"{slug}.md"
    path.write_text(content, encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    # Standalone smoke test (no Houdini / no mcp needed).
    skills = list_skills()
    print(f"{len(skills)} skill(s):")
    for s in skills:
        print(f"  - {s['name']}: {s['description']}")
    if skills:
        first = skills[0]["name"]
        body = get_skill(first)
        print(f"\nget_skill('{first}') -> {len(body)} chars, "
              f"{len(body.splitlines())} lines")
