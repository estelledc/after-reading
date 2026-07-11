#!/usr/bin/env python3
"""Validate the public bookshelf's source evidence and rendered HTML contract."""

from __future__ import annotations

import json
import os
import sys
from html.parser import HTMLParser
from urllib.parse import urlsplit

import build_shelf


class ShelfHTMLFacts(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tag_counts: dict[str, int] = {}
        self.class_counts: dict[str, int] = {}
        self.ids: list[str] = []
        self.links: list[dict[str, str]] = []
        self.meta: list[dict[str, str]] = []
        self.canonical: list[str] = []
        self.stylesheets: list[str] = []
        self.json_ld: list[str] = []
        self.text_parts: list[str] = []
        self._json_ld_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tag_counts[tag] = self.tag_counts.get(tag, 0) + 1
        data = {key: value or "" for key, value in attrs}
        if data.get("id"):
            self.ids.append(data["id"])
        for class_name in data.get("class", "").split():
            self.class_counts[class_name] = self.class_counts.get(class_name, 0) + 1
        if tag == "a":
            self.links.append(data)
        elif tag == "meta":
            self.meta.append(data)
        elif tag == "link":
            rel = set(data.get("rel", "").split())
            if "canonical" in rel:
                self.canonical.append(data.get("href", ""))
            if "stylesheet" in rel:
                self.stylesheets.append(data.get("href", ""))
        elif tag == "script" and data.get("type") == "application/ld+json":
            self._json_ld_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_ld_parts is not None:
            self.json_ld.append("".join(self._json_ld_parts).strip())
            self._json_ld_parts = None

    def handle_data(self, data: str) -> None:
        if self._json_ld_parts is not None:
            self._json_ld_parts.append(data)
        if data.strip():
            self.text_parts.append(data.strip())

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)


def validate() -> tuple[list[str], dict[str, int]]:
    shelf = build_shelf.load_shelf()
    curation = build_shelf.load_curation()
    takes = build_shelf.load_takes()
    identity = build_shelf.load_identity()
    errors = build_shelf.validate_sources(shelf, curation, takes, identity)

    ids = build_shelf.curated_ids(curation)
    counts = {
        "curated": len(ids),
        "sections": len(curation.get("sections", [])),
        "takes": sum(bool(takes.get(book_id, "").strip()) for book_id in ids),
        "archives": len(build_shelf.NOTE_ARCHIVES),
    }

    if not os.path.isfile(build_shelf.OUTPUT_PATH):
        return errors + ["index.html is missing"], counts
    with open(build_shelf.OUTPUT_PATH, encoding="utf-8") as handle:
        html = handle.read()

    expected_html = build_shelf.render_html(shelf, curation, takes, identity)
    if html != expected_html:
        errors.append("index.html is stale; run python scripts/build_shelf.py")

    facts = ShelfHTMLFacts()
    facts.feed(html)

    for tag in ("main", "h1", "footer"):
        if facts.tag_counts.get(tag, 0) != 1:
            errors.append(f"expected exactly one <{tag}>, found {facts.tag_counts.get(tag, 0)}")

    duplicate_ids = sorted({value for value in facts.ids if facts.ids.count(value) > 1})
    if duplicate_ids:
        errors.append(f"duplicate HTML IDs: {', '.join(duplicate_ids)}")

    expected_ids = {
        "main-content",
        "reading-system",
        "notes",
        "timeline",
        *(f"s-{section['slug']}" for section in curation["sections"]),
        *(f"b-{book_id}" for book_id in ids),
    }
    missing_ids = sorted(expected_ids - set(facts.ids))
    if missing_ids:
        errors.append(f"rendered IDs missing: {', '.join(missing_ids)}")

    expected_classes = {
        "book": counts["curated"],
        "shelf-section": counts["sections"],
        "note-archive": counts["archives"],
    }
    for class_name, expected in expected_classes.items():
        actual = facts.class_counts.get(class_name, 0)
        if actual != expected:
            errors.append(f"expected {expected} .{class_name} elements, found {actual}")

    if facts.canonical != [build_shelf.SITE_URL]:
        errors.append(f"canonical must be exactly {build_shelf.SITE_URL}")

    required_stylesheets = {
        "assets/jx/tokens.css",
        "assets/jx/base.css",
        "assets/jx/components.css",
        "assets/style.css",
    }
    missing_stylesheets = sorted(required_stylesheets - set(facts.stylesheets))
    if missing_stylesheets:
        errors.append(f"required stylesheets missing from HTML: {', '.join(missing_stylesheets)}")
    for stylesheet in required_stylesheets:
        if not os.path.isfile(os.path.join(build_shelf.ROOT, stylesheet)):
            errors.append(f"stylesheet file is missing: {stylesheet}")

    favicon = os.path.join(build_shelf.ROOT, "assets", "favicon.svg")
    if 'rel="icon" href="assets/favicon.svg"' not in html:
        errors.append("SVG favicon link is missing from HTML")
    if not os.path.isfile(favicon):
        errors.append("assets/favicon.svg is missing")

    for key in (
        "description",
        "og:title",
        "og:description",
        "og:url",
        "twitter:card",
        "twitter:title",
        "twitter:description",
    ):
        match = next(
            (
                item
                for item in facts.meta
                if (item.get("name") == key or item.get("property") == key)
                and item.get("content", "").strip()
            ),
            None,
        )
        if match is None:
            errors.append(f"metadata missing non-empty content: {key}")

    schemas = []
    for document in facts.json_ld:
        try:
            schemas.append(json.loads(document))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON-LD: {exc}")
    collection = next(
        (item for item in schemas if isinstance(item, dict) and item.get("@type") == "CollectionPage"),
        None,
    )
    if collection is None:
        errors.append("CollectionPage JSON-LD is missing")
    else:
        main_entity = collection.get("mainEntity", {})
        if main_entity.get("numberOfItems") != counts["curated"]:
            errors.append("JSON-LD numberOfItems does not match curated evidence")
        if collection.get("url") != build_shelf.SITE_URL:
            errors.append("JSON-LD URL does not match canonical URL")

    hrefs = {link.get("href", "") for link in facts.links}
    required_links = {
        "#main-content",
        "#reading-system",
        "#s-serious-fiction",
        "https://estelledc.github.io/",
        "https://estelledc.github.io/about/",
        "https://estelledc.github.io/resume/",
        build_shelf.REPO_URL,
    }
    missing_links = sorted(required_links - hrefs)
    if missing_links:
        errors.append(f"required public links missing: {', '.join(missing_links)}")

    for link in facts.links:
        href = link.get("href", "")
        if href.startswith("#") and len(href) > 1 and href[1:] not in facts.ids:
            errors.append(f"fragment link has no target: {href}")
        if link.get("target") == "_blank" and urlsplit(href).scheme in {"http", "https"}:
            rel = set(link.get("rel", "").split())
            if not {"noopener", "noreferrer"}.issubset(rel):
                errors.append(f"target=_blank link lacks noopener noreferrer: {href}")

    for text in (
        "这不是排行榜，是一条判断链。",
        "Jason / 判断与验收",
        "AI / 辅助",
        "Limitations / 局限",
        "不再统一称作“深度笔记”",
    ):
        if text not in facts.text:
            errors.append(f"public evidence text missing: {text}")

    version_path = os.path.join(build_shelf.ROOT, "assets", "jx", "VERSION")
    try:
        with open(version_path, encoding="utf-8") as handle:
            version = handle.read().strip()
        if version != "2.0.0":
            errors.append(f"expected Jason DS 2.0.0, found {version or 'empty'}")
    except OSError:
        errors.append("Jason DS version file is missing")

    readme_path = os.path.join(build_shelf.ROOT, "README.md")
    try:
        with open(readme_path, encoding="utf-8") as handle:
            readme = handle.read()
        for claim in (
            f"{counts['curated']} 个唯一策展 ID",
            f"{counts['sections']} 个由人工维护的分类",
            f"{counts['takes']}/{counts['curated']} 个策展条目",
        ):
            if claim not in readme:
                errors.append(f"README evidence is stale or missing: {claim}")
    except OSError:
        errors.append("README.md is missing")

    return errors, counts


def main() -> int:
    errors, counts = validate()
    if errors:
        print("SHELF_VALIDATION_INVALID", file=sys.stderr)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "SHELF_VALIDATION_OK "
        f"curated={counts['curated']} sections={counts['sections']} "
        f"takes={counts['takes']} archives={counts['archives']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
