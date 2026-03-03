"""Export ShowDoc pages to local markdown/JSON."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import requests


def _server_base(base_url: str) -> str:
    return base_url.rstrip("/") + "/server/index.php?s="


def _post(base: str, path: str, data: dict) -> dict:
    resp = requests.post(base + path, data=data, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "page"


def _collect_pages(menu: dict) -> List[dict]:
    pages: Dict[str, dict] = {}

    def add_page(page: dict, path: List[str]) -> None:
        page_id = str(page.get("page_id"))
        if not page_id:
            return
        pages[page_id] = {
            "page_id": page_id,
            "page_title": page.get("page_title") or "",
            "path": path,
            "cat_id": page.get("cat_id"),
        }

    def walk_catalog(cat: dict, path: List[str]) -> None:
        cat_name = cat.get("cat_name") or ""
        next_path = path + ([cat_name] if cat_name else [])
        for page in cat.get("pages", []) or []:
            add_page(page, next_path)
        for child in cat.get("catalogs", []) or []:
            walk_catalog(child, next_path)

    for page in menu.get("pages", []) or []:
        add_page(page, [])
    for cat in menu.get("catalogs", []) or []:
        walk_catalog(cat, [])

    return list(pages.values())


def export_showdoc(item_id: int, base_url: str, out_dir: Path) -> None:
    server = _server_base(base_url)
    item_info = _post(server, "/api/item/info", {"item_id": item_id})
    if item_info.get("error_code") != 0:
        raise RuntimeError(f"ShowDoc item info error: {item_info}")

    raw_dir = out_dir / "raw"
    md_dir = out_dir / "markdown"
    raw_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    (raw_dir / "item_info.json").write_text(json.dumps(item_info, indent=2, ensure_ascii=False))

    menu = item_info.get("data", {}).get("menu", {})
    pages = _collect_pages(menu)

    index = []
    for page in pages:
        page_id = page["page_id"]
        page_resp = _post(server, "/api/page/info", {"page_id": page_id})
        if page_resp.get("error_code") != 0:
            continue
        raw_path = raw_dir / f"page_{page_id}.json"
        raw_path.write_text(json.dumps(page_resp, indent=2, ensure_ascii=False))

        data = page_resp.get("data", {})
        title = data.get("page_title") or page.get("page_title") or f"Page {page_id}"
        slug = _slugify(title)
        md_path = md_dir / f"{page_id}-{slug}.md"
        content = data.get("page_content") or ""
        content = html.unescape(content)
        md_path.write_text(f"# {title}\n\n{content}\n")

        index.append(
            {
                "page_id": page_id,
                "title": title,
                "path": page.get("path", []),
                "markdown": str(md_path.relative_to(out_dir)),
                "raw": str(raw_path.relative_to(out_dir)),
            }
        )

    (out_dir / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Export ShowDoc to markdown/JSON")
    parser.add_argument("--item-id", type=int, default=5, help="ShowDoc item_id")
    parser.add_argument("--base-url", default="http://docin.divoom-gz.com", help="ShowDoc base URL")
    parser.add_argument("--out-dir", default="docs/api/showdoc", help="Output directory")
    args = parser.parse_args()

    export_showdoc(args.item_id, args.base_url, Path(args.out_dir))


if __name__ == "__main__":
    main()
