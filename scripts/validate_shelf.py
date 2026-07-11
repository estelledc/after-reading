#!/usr/bin/env python3
"""Validate the public bookshelf's source evidence and rendered HTML contract."""

from __future__ import annotations

import json
import os
import sys
from html.parser import HTMLParser
from urllib.parse import urlsplit
from xml.etree import ElementTree

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
        "constellations": len(curation.get("constellations", [])),
    }

    page_specs = (
        (
            "index.html",
            build_shelf.OUTPUT_PATH,
            build_shelf.render_html(shelf, curation, takes, identity),
            build_shelf.SITE_URL,
        ),
        (
            "shelf.html",
            build_shelf.SHELF_OUTPUT_PATH,
            build_shelf.render_shelf_html(shelf, curation, takes, identity),
            f"{build_shelf.SITE_URL}shelf.html",
        ),
    )
    pages: dict[str, tuple[str, ShelfHTMLFacts, str]] = {}
    for name, output_path, expected_html, canonical in page_specs:
        if not os.path.isfile(output_path):
            errors.append(f"{name} is missing")
            continue
        with open(output_path, encoding="utf-8") as handle:
            html = handle.read()
        if html != expected_html:
            errors.append(f"{name} is stale; run python3 scripts/build_shelf.py")
        facts = ShelfHTMLFacts()
        facts.feed(html)
        pages[name] = (html, facts, canonical)

        for tag in ("main", "h1", "footer"):
            if facts.tag_counts.get(tag, 0) != 1:
                errors.append(
                    f"{name}: expected exactly one <{tag}>, found {facts.tag_counts.get(tag, 0)}"
                )
        duplicate_ids = sorted({value for value in facts.ids if facts.ids.count(value) > 1})
        if duplicate_ids:
            errors.append(f"{name}: duplicate HTML IDs: {', '.join(duplicate_ids)}")
        if facts.canonical != [canonical]:
            errors.append(f"{name}: canonical must be exactly {canonical}")

    rendered_facts = build_shelf.reading_facts(shelf, curation, takes)
    auxiliary_specs = (
        (
            "404.html",
            build_shelf.NOT_FOUND_OUTPUT_PATH,
            build_shelf.render_not_found_html(rendered_facts),
            f"{build_shelf.SITE_URL}404.html",
            {"./#constellations", "shelf.html"},
        ),
        (
            "划线/划线.html",
            build_shelf.LEGACY_HIGHLIGHTS_OUTPUT_PATH,
            build_shelf.render_legacy_highlights_html(rendered_facts),
            build_shelf.LEGACY_HIGHLIGHTS_URL,
            {"../", "../shelf.html", "../#notes"},
        ),
    )
    global_destinations = {
        "https://estelledc.github.io/",
        "https://estelledc.github.io/about/",
        "https://estelledc.github.io/resume/",
        build_shelf.REPO_URL,
    }
    for name, output_path, expected_html, canonical, local_destinations in auxiliary_specs:
        if not os.path.isfile(output_path):
            errors.append(f"{name} is missing")
            continue
        with open(output_path, encoding="utf-8") as handle:
            html = handle.read()
        if html != expected_html:
            errors.append(f"{name} is stale; run python3 scripts/build_shelf.py")
        facts = ShelfHTMLFacts()
        facts.feed(html)
        for tag in ("main", "h1", "footer"):
            if facts.tag_counts.get(tag, 0) != 1:
                errors.append(
                    f"{name}: expected exactly one <{tag}>, found {facts.tag_counts.get(tag, 0)}"
                )
        if facts.canonical != [canonical]:
            errors.append(f"{name}: canonical must be exactly {canonical}")
        robots = next((item.get("content") for item in facts.meta if item.get("name") == "robots"), "")
        if not robots.startswith("noindex"):
            errors.append(f"{name}: public-boundary page must be noindex")
        hrefs = {link.get("href", "") for link in facts.links}
        missing_links = sorted((global_destinations | local_destinations) - hrefs)
        if missing_links:
            errors.append(f"{name}: required global/local exits missing: {', '.join(missing_links)}")
        if facts.json_ld:
            errors.append(f"{name}: noindex boundary page must not publish JSON-LD")

    if os.path.isfile(build_shelf.LEGACY_HIGHLIGHTS_OUTPUT_PATH):
        with open(build_shelf.LEGACY_HIGHLIGHTS_OUTPUT_PATH, encoding="utf-8") as handle:
            legacy_html = handle.read()
        for marker in ("NotionHQ", "notion.site", "ClientFramework", "app-d17407a06b4582d3.js"):
            if marker in legacy_html:
                errors.append(f"划线/划线.html: stale third-party export marker remains: {marker}")
        if "第三方导出壳已移除" not in legacy_html:
            errors.append("划线/划线.html: public boundary explanation is missing")

    if os.path.isfile(build_shelf.NOT_FOUND_OUTPUT_PATH):
        with open(build_shelf.NOT_FOUND_OUTPUT_PATH, encoding="utf-8") as handle:
            not_found_html = handle.read()
        if "这页没有留下划线" not in not_found_html or "404 · Missing page" not in not_found_html:
            errors.append("404.html: high-quality recovery copy is missing")

    expected_robots = build_shelf.render_robots_txt()
    try:
        with open(build_shelf.ROBOTS_OUTPUT_PATH, encoding="utf-8") as handle:
            robots_txt = handle.read()
        if robots_txt != expected_robots:
            errors.append("robots.txt is stale or malformed")
    except OSError:
        errors.append("robots.txt is missing")

    expected_sitemap = build_shelf.render_sitemap_xml(rendered_facts)
    try:
        with open(build_shelf.SITEMAP_OUTPUT_PATH, encoding="utf-8") as handle:
            sitemap_xml = handle.read()
        if sitemap_xml != expected_sitemap:
            errors.append("sitemap.xml is stale")
        root = ElementTree.fromstring(sitemap_xml)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemap_urls = {item.text for item in root.findall("sm:url/sm:loc", namespace)}
        if sitemap_urls != {build_shelf.SITE_URL, f"{build_shelf.SITE_URL}shelf.html"}:
            errors.append(f"sitemap.xml URLs are unexpected: {sorted(sitemap_urls)}")
    except (OSError, ElementTree.ParseError) as exc:
        errors.append(f"sitemap.xml is missing or invalid: {exc}")

    if len(pages) != len(page_specs):
        return errors, counts

    home_html, home, _ = pages["index.html"]
    shelf_html, shelf_facts, _ = pages["shelf.html"]

    home_ids = {"main-content", "constellations", "notes", "timeline", "reading-system"}
    shelf_ids = {
        "main-content",
        "shelf",
        "shelf-search-input",
        "shelf-search-count",
        *(f"s-{section['slug']}" for section in curation["sections"]),
        *(f"b-{book_id}" for book_id in ids),
    }
    for name, facts, expected_ids in (
        ("index.html", home, home_ids),
        ("shelf.html", shelf_facts, shelf_ids),
    ):
        missing_ids = sorted(expected_ids - set(facts.ids))
        if missing_ids:
            errors.append(f"{name}: rendered IDs missing: {', '.join(missing_ids)}")

    class_contracts = {
        "index.html": {
            "book": 0,
            "shelf-section": 0,
            "reading-constellation": counts["constellations"],
            "note-archive": counts["archives"],
        },
        "shelf.html": {
            "book": counts["curated"],
            "shelf-section": counts["sections"],
            "reading-constellation": 0,
            "note-archive": 0,
        },
    }
    for name, contract in class_contracts.items():
        facts = pages[name][1]
        for class_name, expected in contract.items():
            actual = facts.class_counts.get(class_name, 0)
            if actual != expected:
                errors.append(
                    f"{name}: expected {expected} .{class_name} elements, found {actual}"
                )

    required_stylesheets = {
        "assets/jx/tokens.css",
        "assets/jx/base.css",
        "assets/jx/components.css",
        "assets/style.css",
    }
    for name, (_, facts, _) in pages.items():
        missing_stylesheets = sorted(required_stylesheets - set(facts.stylesheets))
        if missing_stylesheets:
            errors.append(
                f"{name}: required stylesheets missing: {', '.join(missing_stylesheets)}"
            )
    for stylesheet in required_stylesheets:
        if not os.path.isfile(os.path.join(build_shelf.ROOT, stylesheet)):
            errors.append(f"stylesheet file is missing: {stylesheet}")

    favicon = os.path.join(build_shelf.ROOT, "assets", "favicon.svg")
    for name, (html, _, _) in pages.items():
        if 'rel="icon" href="assets/favicon.svg"' not in html:
            errors.append(f"{name}: SVG favicon link is missing")
    if not os.path.isfile(favicon):
        errors.append("assets/favicon.svg is missing")

    metadata_keys = (
        "description", "og:title", "og:description", "og:url",
        "twitter:card", "twitter:title", "twitter:description",
    )
    for name, (_, facts, canonical) in pages.items():
        for key in metadata_keys:
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
                errors.append(f"{name}: metadata missing non-empty content: {key}")

        schema_nodes = []
        for document in facts.json_ld:
            try:
                schema = json.loads(document)
                schema_nodes.extend(schema.get("@graph", [schema]) if isinstance(schema, dict) else [])
            except json.JSONDecodeError as exc:
                errors.append(f"{name}: invalid JSON-LD: {exc}")
        person = next((item for item in schema_nodes if item.get("@type") == "Person"), None)
        collection = next((item for item in schema_nodes if item.get("@type") == "CollectionPage"), None)
        if not person or person.get("@id") != build_shelf.PERSON_ID or person.get("name") != "Jason Xun":
            errors.append(f"{name}: canonical Person JSON-LD identity is missing")
        if collection is None:
            errors.append(f"{name}: CollectionPage JSON-LD is missing")
        else:
            if collection.get("mainEntity", {}).get("numberOfItems") != counts["curated"]:
                errors.append(f"{name}: JSON-LD numberOfItems does not match curated evidence")
            if collection.get("url") != canonical:
                errors.append(f"{name}: JSON-LD URL does not match canonical URL")
            if collection.get("author", {}).get("@id") != build_shelf.PERSON_ID:
                errors.append(f"{name}: CollectionPage author does not reference canonical Person")

    required_links = {
        "index.html": {
            "#main-content", "#constellations", "shelf.html",
            "https://estelledc.github.io/", "https://estelledc.github.io/about/",
            "https://estelledc.github.io/resume/", build_shelf.REPO_URL,
        },
        "shelf.html": {
            "#main-content", "./", "./#constellations", "#s-serious-fiction",
            "https://estelledc.github.io/", "https://estelledc.github.io/about/",
            "https://estelledc.github.io/resume/", build_shelf.REPO_URL,
        },
    }
    for name, (_, facts, _) in pages.items():
        hrefs = {link.get("href", "") for link in facts.links}
        missing_links = sorted(required_links[name] - hrefs)
        if missing_links:
            errors.append(f"{name}: required public links missing: {', '.join(missing_links)}")
        for link in facts.links:
            href = link.get("href", "")
            if href.startswith("#") and len(href) > 1 and href[1:] not in facts.ids:
                errors.append(f"{name}: fragment link has no target: {href}")
            if link.get("target") == "_blank" and urlsplit(href).scheme in {"http", "https"}:
                rel = set(link.get("rel", "").split())
                if not {"noopener", "noreferrer"}.issubset(rel):
                    errors.append(f"{name}: target=_blank link lacks noopener noreferrer: {href}")

    for href in (link.get("href", "") for link in home.links):
        if href.startswith("shelf.html#") and href.split("#", 1)[1] not in shelf_facts.ids:
            errors.append(f"index.html: cross-page fragment has no shelf target: {href}")

    for text in (
        "我不展示读过多少",
        "3 条阅读星座",
        "这不是排行榜，是一条判断链。",
        "Jason / 判断与验收",
        "AI / 辅助",
        "不再统一称作“深度笔记”",
    ):
        if text not in home.text:
            errors.append(f"index.html: public evidence text missing: {text}")

    if home.class_counts.get("jx-proof-rail__label", 0) != 3:
        errors.append("index.html: representative proof rail must contain exactly three outcomes")
    if 'id="shelf-search-input"' not in shelf_html or "addEventListener(\"input\"" not in shelf_html:
        errors.append("shelf.html: progressive search contract is missing")
    if shelf_html.count('data-search="') != counts["curated"]:
        errors.append("shelf.html: every book must expose searchable text")

    version_path = os.path.join(build_shelf.ROOT, "assets", "jx", "VERSION")
    try:
        with open(version_path, encoding="utf-8") as handle:
            version = handle.read().strip()
        if version != "2.1.0":
            errors.append(f"expected Jason DS 2.1.0, found {version or 'empty'}")
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
            "3 条阅读星座",
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
