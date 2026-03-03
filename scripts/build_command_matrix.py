"""Build a command coverage matrix from exported ShowDoc markdown."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

COMMAND_RE = re.compile(
    r"\b("
    r"(?:Draw|Device|Channel|Sys|Tools|App|Clock|Dial|Time|User)/"
    r"[A-Za-z0-9_]+"
    r")\b"
)


def _load_supported_commands(src_root: Path) -> set[str]:
    supported: set[str] = set()
    for path in src_root.rglob("*.py"):
        text = path.read_text()
        for match in COMMAND_RE.findall(text):
            supported.add(match)
    return supported


def _load_commands_from_docs(md_dir: Path) -> dict[str, set[str]]:
    commands: dict[str, set[str]] = {}
    for path in sorted(md_dir.glob("*.md")):
        text = path.read_text()
        title = ""
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        for match in COMMAND_RE.findall(text):
            commands.setdefault(match, set()).add(title or path.name)
    return commands


def build_matrix(docs_dir: Path, out_path: Path, src_root: Path) -> None:
    md_dir = docs_dir / "markdown"
    commands = _load_commands_from_docs(md_dir)
    supported = _load_supported_commands(src_root)

    rows = []
    for cmd in sorted(commands.keys()):
        category = cmd.split("/", 1)[0]
        notes = "; ".join(sorted(commands[cmd]))
        rows.append((cmd, category, "yes" if cmd in supported else "no", notes))

    out_lines = [
        "| Command | Category | SDK Support | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for cmd, category, support, notes in rows:
        out_lines.append(f"| {cmd} | {category} | {support} | {notes} |")

    out_path.write_text("\n".join(out_lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build command coverage matrix")
    parser.add_argument("--docs", default="docs/api/showdoc", help="ShowDoc export directory")
    parser.add_argument("--out", default="docs/api/command_matrix.md", help="Output markdown path")
    parser.add_argument("--src", default="src/pypixoo", help="Source root for SDK support scan")
    args = parser.parse_args()

    build_matrix(Path(args.docs), Path(args.out), Path(args.src))


if __name__ == "__main__":
    main()
