#!/usr/bin/env python3
"""Build the editorial homepage and full public bookshelf.

Output:
    index.html — editorial landing with three reading constellations.
    shelf.html — complete searchable shelf with progressive enhancement.
    404.html / robots.txt / sitemap.xml — public-discovery boundary.
    划线/划线.html — sanitized context page for the legacy public URL.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from html import escape
from urllib.parse import quote

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELF_PATH = os.path.join(ROOT, "data", "raw-shelf.json")
CURATION_PATH = os.path.join(ROOT, "content", "curation.yaml")
TAKES_PATH = os.path.join(ROOT, "content", "jason-takes.md")
IDENTITY_PATH = os.path.join(ROOT, "content", "identity.md")
OUTPUT_PATH = os.path.join(ROOT, "index.html")
SHELF_OUTPUT_PATH = os.path.join(ROOT, "shelf.html")
ROBOTS_OUTPUT_PATH = os.path.join(ROOT, "robots.txt")
SITEMAP_OUTPUT_PATH = os.path.join(ROOT, "sitemap.xml")
NOT_FOUND_OUTPUT_PATH = os.path.join(ROOT, "404.html")
LEGACY_HIGHLIGHTS_OUTPUT_PATH = os.path.join(ROOT, "划线", "划线.html")
SITE_URL = "https://estelledc.github.io/after-reading/"
REPO_URL = "https://github.com/estelledc/after-reading"
PERSON_ID = "https://estelledc.github.io/#person"
LEGACY_HIGHLIGHTS_URL = f"{SITE_URL}{quote('划线/划线.html')}"

NOTE_ARCHIVES = [
    {
        "title": "《Outlive》",
        "path": "《outlive》",
        "summary": "围绕营养、运动与情绪健康留下的早期主题笔记。",
    },
    {
        "title": "《如何像列奥纳多·达芬奇一样思考》",
        "path": "《如何像列奥纳多·达芬奇一样思考》",
        "summary": "100 个问题、10Q×n 与划线照片组成的笔记实验。",
    },
    {
        "title": "《未来世界的幸存者》",
        "path": "《未来世界的幸存者》阮一峰",
        "summary": "划线、个人总结与一份以 kimi 命名的辅助读后感。",
    },
    {
        "title": "《温州人的性格》",
        "path": "《温州人的性格》",
        "summary": "用 Markdown 大纲整理商业群体性格的结构化尝试。",
    },
    {
        "title": "早期划线实验",
        "path": "划线",
        "summary": "保留最初尝试把划线导出为 HTML、Word 与 PDF 的痕迹。",
    },
]


def load_shelf() -> dict:
    with open(SHELF_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_curation() -> dict:
    with open(CURATION_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_takes() -> dict:
    """Parse jason-takes.md into {bookId: take_text}.
    Format: '## <bookId> <title...>\\n<text>...'
    """
    with open(TAKES_PATH, encoding="utf-8") as f:
        md = f.read()
    takes = {}
    pattern = re.compile(r"^## (\S+)[^\n]*\n(.+?)(?=^## |\Z)", re.M | re.S)
    for m in pattern.finditer(md):
        bid = m.group(1).strip()
        text = m.group(2).strip()
        takes[bid] = text
    return takes


def load_identity() -> dict:
    """Parse identity.md into sections by ## heading."""
    with open(IDENTITY_PATH, encoding="utf-8") as f:
        md = f.read()
    sections = {}
    pattern = re.compile(r"^## (\S+)\s*\n(.+?)(?=^## |\Z)", re.M | re.S)
    for m in pattern.finditer(md):
        sections[m.group(1).strip()] = m.group(2).strip()
    return sections


def fmt_date(ts: int) -> str:
    if not ts:
        return "—"
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d")


def curated_ids(curation: dict) -> list[str]:
    return [str(book_id) for section in curation.get("sections", []) for book_id in section.get("book_ids", [])]


def constellation_ids(curation: dict) -> list[str]:
    return [
        str(book_id)
        for constellation in curation.get("constellations", [])
        for book_id in constellation.get("book_ids", [])
    ]


def validate_sources(shelf: dict, curation: dict, takes: dict, identity: dict) -> list[str]:
    errors = []
    sections = curation.get("sections")
    if not isinstance(sections, list) or not sections:
        return ["curation must contain at least one section"]

    ids = curated_ids(curation)
    if len(ids) != len(set(ids)):
        errors.append("curated book IDs must be unique")

    books_by_id = {str(book.get("bookId")): book for book in shelf.get("books", [])}
    missing_books = [book_id for book_id in ids if book_id not in books_by_id]
    if missing_books:
        errors.append(f"curated IDs missing from raw shelf: {', '.join(missing_books)}")

    unfinished = [
        book_id
        for book_id in ids
        if book_id in books_by_id and books_by_id[book_id].get("finishReading") != 1
    ]
    if unfinished:
        errors.append(f"curated IDs are not marked finished in source data: {', '.join(unfinished)}")

    missing_takes = [book_id for book_id in ids if not takes.get(book_id, "").strip()]
    if missing_takes:
        errors.append(f"curated IDs missing a short judgment: {', '.join(missing_takes)}")

    constellations = curation.get("constellations")
    if not isinstance(constellations, list) or len(constellations) != 3:
        errors.append("curation must contain exactly three reading constellations")
    else:
        constellation_slugs = [str(item.get("slug", "")) for item in constellations]
        if any(not slug for slug in constellation_slugs) or len(constellation_slugs) != len(set(constellation_slugs)):
            errors.append("reading constellation slugs must be present and unique")
        for constellation in constellations:
            if not str(constellation.get("title", "")).strip() or not str(constellation.get("thesis", "")).strip():
                errors.append("each reading constellation needs a title and thesis")
            book_ids = [str(book_id) for book_id in constellation.get("book_ids", [])]
            if len(book_ids) != 3 or len(book_ids) != len(set(book_ids)):
                errors.append(f"reading constellation {constellation.get('slug', '?')} must contain three unique books")

        constellation_book_ids = constellation_ids(curation)
        missing_constellation_books = sorted(set(constellation_book_ids) - set(ids))
        if missing_constellation_books:
            errors.append(
                "constellation IDs must also exist in the curated shelf: "
                + ", ".join(missing_constellation_books)
            )

    required_identity = {
        "hero_lead",
        "intro",
        "english_summary",
        "problem",
        "role_jason",
        "role_ai",
        "system",
        "limitations",
        "timeline_narrative",
    }
    missing_identity = sorted(required_identity - set(identity))
    if missing_identity:
        errors.append(f"identity sections missing: {', '.join(missing_identity)}")

    for archive in NOTE_ARCHIVES:
        if not os.path.isdir(os.path.join(ROOT, archive["path"])):
            errors.append(f"note archive missing: {archive['path']}")
    return errors


def render_book_card(idx: int, book: dict, take: str) -> str:
    bid = book.get("bookId", "")
    title = escape(book.get("title", "?"))
    author = escape(book.get("author", "?")) or "—"
    date = fmt_date(book.get("readUpdateTime", 0))
    take_html = escape(take) if take else "<em>(待补)</em>"
    search_text = escape(
        " ".join((book.get("title", ""), book.get("author", ""), take, date)).casefold(),
        quote=True,
    )

    return f"""<article class="book" id="b-{escape(bid)}" data-search="{search_text}">
  <span class="book-num">№ {idx:03d}</span>
  <div class="book-body">
    <h3 class="book-title">{title}</h3>
    <p class="book-meta">{author} · {date} 完读</p>
    <p class="book-take">{take_html}</p>
  </div>
</article>"""


def render_section(section: dict, books_by_id: dict, takes: dict, idx_start: int):
    cards = []
    idx = idx_start
    for bid in section["book_ids"]:
        book = books_by_id.get(bid)
        if not book:
            cards.append(f'<!-- MISSING bookId={bid} -->')
            continue
        cards.append(render_book_card(idx, book, takes.get(bid, "")))
        idx += 1
    cards_html = "\n".join(cards)
    slug = escape(section["slug"])
    title = escape(section["title"])
    blurb = escape(section.get("blurb", ""))
    section_html = f"""<section class="shelf-section" id="s-{slug}" aria-labelledby="s-{slug}-title">
  <header class="section-head">
    <h2 class="section-title" id="s-{slug}-title">{title}</h2>
    <p class="section-blurb">{blurb}</p>
    <p class="section-count">{len(section['book_ids'])} 本</p>
  </header>
  <div class="book-grid">
    {cards_html}
  </div>
</section>"""
    return section_html, idx


def render_shelf_index(curation: dict) -> str:
    links = []
    for section in curation["sections"]:
        slug = escape(section["slug"])
        title = escape(section["title"])
        count = len(section["book_ids"])
        links.append(
            f'<li><a href="#s-{slug}"><span>{title}</span><strong>{count}</strong></a></li>'
        )
    return "\n".join(links)


def render_note_archives() -> str:
    cards = []
    for archive in NOTE_ARCHIVES:
        href = f"{REPO_URL}/tree/main/{quote(archive['path'])}"
        cards.append(
            f'''<a class="note-archive" href="{href}">
  <strong>{escape(archive['title'])}</strong>
  <span>{escape(archive['summary'])}</span>
</a>'''
        )
    return "\n".join(cards)


def reading_facts(shelf: dict, curation: dict, takes: dict) -> dict:
    books_by_id = {str(book["bookId"]): book for book in shelf.get("books", [])}
    ids = curated_ids(curation)
    selected_books = [books_by_id[book_id] for book_id in ids]
    timestamps = [book.get("readUpdateTime", 0) for book in selected_books if book.get("readUpdateTime")]
    data_start = fmt_date(min(timestamps))
    data_through = fmt_date(max(timestamps))
    return {
        "books_by_id": books_by_id,
        "ids": ids,
        "curated_count": len(ids),
        "section_count": len(curation["sections"]),
        "take_count": sum(bool(takes.get(book_id, "").strip()) for book_id in ids),
        "data_start": data_start,
        "data_through": data_through,
        "temporal_coverage": f"{data_start[:7]}/{data_through[:7]}",
    }


def take_excerpt(take: str, limit: int = 220) -> str:
    normalized = re.sub(r"\s+", " ", take).strip()
    sentences = [part for part in re.split(r"(?<=[。！？])", normalized) if part]
    excerpt = "".join(sentences[:2]) if sentences else normalized
    if len(excerpt) > limit:
        excerpt = excerpt[: limit - 1].rstrip() + "…"
    return excerpt


def render_constellations(curation: dict, books_by_id: dict, takes: dict) -> str:
    articles = []
    for idx, constellation in enumerate(curation["constellations"], start=1):
        book_items = []
        for book_id in constellation["book_ids"]:
            book = books_by_id[str(book_id)]
            book_items.append(
                f'''<li><a href="shelf.html#b-{escape(str(book_id), quote=True)}">
  <strong>{escape(book.get("title", "?"))}</strong>
  <span>{escape(book.get("author", "?")) or "—"} · {fmt_date(book.get("readUpdateTime", 0))}</span>
  <p>{escape(take_excerpt(takes.get(str(book_id), "")))}</p>
</a></li>'''
            )
        articles.append(
            f'''<article class="reading-constellation" id="c-{escape(constellation["slug"], quote=True)}">
  <p class="constellation-number">Constellation {idx:02d}</p>
  <h3>{escape(constellation["title"])}</h3>
  <p class="constellation-thesis">{escape(constellation["thesis"])}</p>
  <ul>{"".join(book_items)}</ul>
</article>'''
        )
    return "\n".join(articles)


def build_schema(name: str, description: str, canonical: str, facts: dict) -> dict:
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Person",
                "@id": PERSON_ID,
                "name": "Jason Xun",
                "url": "https://estelledc.github.io/",
                "sameAs": ["https://github.com/estelledc"],
            },
            {
                "@type": "CollectionPage",
                "@id": f"{canonical}#page",
                "name": name,
                "url": canonical,
                "description": description,
                "inLanguage": ["zh-CN", "en"],
                "dateModified": facts["data_through"],
                "temporalCoverage": facts["temporal_coverage"],
                "author": {"@id": PERSON_ID},
                "mainEntity": {
                    "@type": "ItemList",
                    "numberOfItems": facts["curated_count"],
                    "itemListOrder": "https://schema.org/ItemListOrderAscending",
                },
                "sameAs": REPO_URL,
            },
        ],
    }


def render_head(
    title: str,
    description: str,
    canonical: str,
    facts: dict,
    *,
    asset_prefix: str = "",
    robots: str | None = None,
    include_schema: bool = True,
) -> str:
    schema_html = ""
    if include_schema:
        schema_json = json.dumps(
            build_schema(title, description, canonical, facts), ensure_ascii=False
        ).replace("</", "<\\/")
        schema_html = f'\n  <script type="application/ld+json">{schema_json}</script>'
    robots_html = f'  <meta name="robots" content="{escape(robots, quote=True)}">\n' if robots else ""
    return f'''<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="author" content="Jason Xun">
  <meta name="description" content="{escape(description, quote=True)}">
{robots_html}  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{escape(title, quote=True)}">
  <meta property="og:description" content="{escape(description, quote=True)}">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="zh_CN">
  <meta property="og:url" content="{canonical}">
  <meta property="og:site_name" content="after-reading">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{escape(title, quote=True)}">
  <meta name="twitter:description" content="{escape(description, quote=True)}">
  <link rel="icon" href="{asset_prefix}assets/favicon.svg" type="image/svg+xml">{schema_html}
  <link rel="stylesheet" href="{asset_prefix}assets/jx/tokens.css">
  <link rel="stylesheet" href="{asset_prefix}assets/jx/base.css">
  <link rel="stylesheet" href="{asset_prefix}assets/jx/components.css">
  <link rel="stylesheet" href="{asset_prefix}assets/style.css">
</head>'''


def render_site_header(active: str, path_prefix: str = "") -> str:
    home_current = ' aria-current="page"' if active == "home" else ""
    shelf_current = ' aria-current="page"' if active == "shelf" else ""
    home_href = path_prefix or "./"
    local_links = f'''<a href="{home_href}"{home_current}>Home</a>
          <a href="{path_prefix}shelf.html"{shelf_current}>Shelf</a>'''
    return f'''<header class="jx-site-header">
    <div class="jx-site-header__inner">
      <a class="jx-site-header__identity" href="{home_href}" aria-label="after-reading 首页">
        <strong>after-reading</strong>
        <span>Jason Xun 的公开阅读系统</span>
      </a>
      <div class="jx-site-nav">
        <nav class="jx-site-nav__links" aria-label="站点与作品集导航">
          {local_links}
          <a class="jx-return-to-hub" href="https://estelledc.github.io/">Jason Hub</a>
          <a href="https://estelledc.github.io/about/">About</a>
          <a href="https://estelledc.github.io/resume/">Resume</a>
          <a href="{REPO_URL}">GitHub</a>
        </nav>
        <details class="jx-site-nav__menu">
          <summary aria-label="打开全局导航">导航</summary>
          <nav aria-label="移动端站点与作品集导航">
            {local_links}
            <a class="jx-return-to-hub" href="https://estelledc.github.io/">Jason Hub</a>
            <a href="https://estelledc.github.io/about/">About</a>
            <a href="https://estelledc.github.io/resume/">Resume</a>
            <a href="{REPO_URL}">GitHub</a>
          </nav>
        </details>
      </div>
    </div>
  </header>'''


def render_footer(data_through: str, path_prefix: str = "") -> str:
    home_href = path_prefix or "./"
    return f'''<footer class="jx-footer">
      <div class="jx-footer__colophon">
        <strong>after-reading</strong>
        <span lang="en">AN OWNER-LED READING EDITION</span>
      </div>
      <nav class="jx-footer__index" aria-label="作品集导航">
        <a href="{home_href}">home</a>
        <a href="{path_prefix}shelf.html">shelf</a>
        <a href="https://estelledc.github.io/">hub</a>
        <a href="https://estelledc.github.io/about/">about</a>
        <a href="https://estelledc.github.io/resume/">resume</a>
        <a href="{REPO_URL}">github</a>
      </nav>
      <time class="jx-footer__stamp" datetime="{data_through}" lang="en">DATA THROUGH {data_through.replace("-", "·")}</time>
    </footer>'''


def render_html(shelf: dict, curation: dict, takes: dict, identity: dict) -> str:
    facts = reading_facts(shelf, curation, takes)
    intro = escape(identity.get("intro", ""))
    timeline = escape(identity.get("timeline_narrative", ""))
    hero_lead = escape(identity.get("hero_lead", ""))
    english_summary = escape(identity.get("english_summary", ""))
    problem = escape(identity.get("problem", ""))
    role_jason = escape(identity.get("role_jason", ""))
    role_ai = escape(identity.get("role_ai", ""))
    system = escape(identity.get("system", ""))
    limitations = escape(identity.get("limitations", ""))
    title = "after-reading · Jason Xun 的公开阅读系统"
    description = "从三条个人阅读线索进入书架：个体与系统、工作与时间、阅读的不同重量。"
    constellations_html = render_constellations(
        curation, facts["books_by_id"], takes
    )
    note_archives_html = render_note_archives()

    return f'''<!doctype html>
<html lang="zh-CN">
{render_head(title, description, SITE_URL, facts)}
<body>
  <a class="jx-skip-link" href="#main-content">跳到主要内容</a>
  {render_site_header("home")}
  <div class="shell">
    <main id="main-content">
      <section class="hero hero--editorial">
        <p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Reading as judgment</p>
        <span class="jx-chip" data-state="maintained">Owner-led · Maintained</span>
        <h1 class="hero-title">我不展示读过多少，<br><em>只展示留下什么。</em></h1>
        <p class="hero-kicker">Jason Xun · after-reading</p>
        <p class="hero-lead">{hero_lead}</p>
        <div class="hero-actions">
          <a class="jx-action" href="#constellations">从三条阅读线进入</a>
          <a class="jx-action jx-action--secondary" href="shelf.html">浏览 {facts["curated_count"]} 本完整书架</a>
        </div>
        <p class="hero-intro">{intro}</p>
        <p class="hero-summary-en" lang="en">{english_summary}</p>
      </section>

      <ul class="jx-proof-rail home-proof-rail" aria-label="公开阅读系统的代表证据">
        <li><a href="#constellations"><span class="jx-proof-rail__label">Editorial entry</span><strong class="jx-proof-rail__value">3 条阅读星座</strong><span class="jx-proof-rail__detail">用跨题材判断代替排行榜式入口。</span><span class="jx-proof-rail__source">Source · curation.yaml</span></a></li>
        <li><a href="shelf.html"><span class="jx-proof-rail__label">Traceable shelf</span><strong class="jx-proof-rail__value">{facts["take_count"]}/{facts["curated_count"]} 条短判断</strong><span class="jx-proof-rail__detail">每个公开条目回连完读缓存与个人判断。</span><span class="jx-proof-rail__source">Source · raw shelf + takes</span></a></li>
        <li><a href="#notes"><span class="jx-proof-rail__label">Reading artifacts</span><strong class="jx-proof-rail__value">5 组笔记痕迹</strong><span class="jx-proof-rail__detail">保留深浅不一的真实方法演化。</span><span class="jx-proof-rail__source">Source · repository archive</span></a></li>
      </ul>

      <section class="constellations-section" id="constellations" aria-labelledby="constellations-title">
        <header class="section-intro section-intro--split">
          <div><p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Three constellations</p><h2 id="constellations-title">书不是按门类留在我这里，<br>而是按问题彼此照亮。</h2></div>
          <p>每条线只选三本，保留当时的个人判断。它们不是“必读书单”，而是我愿意公开承担的阅读关系。</p>
        </header>
        <div class="constellations-grid">{constellations_html}</div>
      </section>

      <section class="timeline" id="timeline" aria-labelledby="timeline-title">
        <p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Reading rhythm · 2024—2025</p>
        <h2 class="section-title" id="timeline-title">阅读轨迹不是增长曲线，<br>更像生活留下的潮汐。</h2>
        <details class="timeline-details">
          <summary>展开完整时间叙事</summary>
          <p class="timeline-narrative">{timeline}</p>
        </details>
      </section>

      <section class="notes-section" id="notes" aria-labelledby="notes-title">
        <header class="section-intro section-intro--split">
          <div><p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Reading artifacts</p><h2 id="notes-title">笔记深浅不一，<br>方法痕迹因此更真实。</h2></div>
          <p>仓库保留 4 个按书组织的笔记目录与 1 组早期划线实验；不再统一称作“深度笔记”。</p>
        </header>
        <div class="note-archives">{note_archives_html}</div>
      </section>

      <details class="method-section" id="reading-system">
        <summary><span>How this shelf is made</span><strong>来源、角色与验证边界</strong></summary>
        <div class="method-body">
          <div class="jx-case-question">
            <p class="jx-case-question__label">Editorial question / 编辑问题</p>
            <div><h2 class="jx-case-question__prompt">这不是排行榜，是一条判断链。</h2><p class="jx-case-question__context">{problem}</p></div>
          </div>
          <div class="method-grid">
            <div><span class="jx-source-tag" data-source="external">Source state</span><h3>原始缓存</h3><p>{system}</p></div>
            <div><span class="jx-source-tag" data-source="build">Owner</span><h3>Jason / 判断与验收</h3><p>{role_jason}</p></div>
            <div><span class="jx-source-tag" data-source="history">AI assisted</span><h3>AI / 辅助</h3><p>{role_ai}</p></div>
            <div><span class="jx-source-tag" data-source="history">Limitations</span><h3>尚未证明</h3><p>{limitations} 当前公开样本截至 {facts["data_through"]}。</p></div>
          </div>
          <p class="jx-verification-line">生成器会检查 {facts["curated_count"]} 个策展 ID 的唯一性、完读字段、判断覆盖和页面结构；这些门禁不证明阅读效果，也不等于逐条人工事实复核。</p>
          <p class="method-links"><a href="{REPO_URL}/blob/main/scripts/validate_shelf.py">查看验证契约</a><a href="shelf.html">进入完整书架</a></p>
        </div>
      </details>
    </main>
    {render_footer(facts["data_through"])}
  </div>
</body>
</html>'''


def render_shelf_html(shelf: dict, curation: dict, takes: dict, identity: dict) -> str:
    facts = reading_facts(shelf, curation, takes)
    section_blocks = []
    idx = 1
    for section in curation["sections"]:
        block, idx = render_section(section, facts["books_by_id"], takes, idx)
        section_blocks.append(block)
    sections_html = "\n\n".join(section_blocks)
    title = f"完整书架 · {facts['curated_count']} 本 · after-reading"
    description = f"按 {facts['section_count']} 个阅读作用分类、可搜索的 {facts['curated_count']} 本公开书架；每本保留完读日期与一句个人判断。"
    canonical = f"{SITE_URL}shelf.html"

    return f'''<!doctype html>
<html lang="zh-CN">
{render_head(title, description, canonical, facts)}
<body>
  <a class="jx-skip-link" href="#main-content">跳到主要内容</a>
  {render_site_header("shelf")}
  <div class="shell">
    <main id="main-content" class="full-shelf">
      <section class="shelf-hero">
        <p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Full shelf · source-matched</p>
        <span class="jx-chip" data-state="maintained">{facts["curated_count"]} entries · {facts["section_count"]} sections</span>
        <h1>完整书架，<em>需要时再查。</em></h1>
        <p>这里保留全部短判断、作者和完读日期。想先理解我怎样阅读，请从<a href="./#constellations">三条阅读星座</a>进入。</p>
      </section>

      <section class="shelf-search" id="shelf" aria-labelledby="shelf-search-title">
        <div><label for="shelf-search-input" id="shelf-search-title">搜索书名、作者或判断</label><p>不输入关键词时，下面按阅读作用展示全部条目。</p></div>
        <div class="shelf-search__control"><input id="shelf-search-input" type="search" autocomplete="off" placeholder="例如：工作、蒙田、悬疑"><output id="shelf-search-count" aria-live="polite">显示 {facts["curated_count"]} / {facts["curated_count"]} 本</output></div>
        <noscript><p class="shelf-search__fallback">当前未启用 JavaScript；全部书目仍可浏览，浏览器页内查找也可使用。</p></noscript>
      </section>

      <nav class="shelf-index" aria-labelledby="shelf-index-title">
        <div><p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Browse by role</p><h2 id="shelf-index-title">按阅读作用进入，<br>不按“高级程度”排序。</h2></div>
        <ol>{render_shelf_index(curation)}</ol>
      </nav>

      {sections_html}
    </main>
    {render_footer(facts["data_through"])}
  </div>
  <script>
  (function () {{
    const input = document.getElementById("shelf-search-input");
    const output = document.getElementById("shelf-search-count");
    const cards = Array.from(document.querySelectorAll(".book[data-search]"));
    const sections = Array.from(document.querySelectorAll(".shelf-section"));
    if (!input || !output) return;

    function applyFilter() {{
      const query = input.value.trim().toLocaleLowerCase();
      let visible = 0;
      cards.forEach(function (card) {{
        const matches = !query || card.dataset.search.includes(query);
        card.hidden = !matches;
        if (matches) visible += 1;
      }});
      sections.forEach(function (section) {{
        section.hidden = Boolean(query) && !section.querySelector(".book:not([hidden])");
      }});
      output.textContent = "显示 " + visible + " / " + cards.length + " 本";
    }}

    input.addEventListener("input", applyFilter);
    const initialQuery = new URLSearchParams(window.location.search).get("q");
    if (initialQuery) {{
      input.value = initialQuery.slice(0, 80);
      applyFilter();
    }}
  }})();
  </script>
</body>
</html>'''


def render_not_found_html(facts: dict) -> str:
    title = "404 · 这页没有留下划线 · after-reading"
    description = "请求的阅读页面不存在；回到三条阅读星座或完整书架继续浏览。"
    canonical = f"{SITE_URL}404.html"
    return f'''<!doctype html>
<html lang="zh-CN">
{render_head(title, description, canonical, facts, robots="noindex, nofollow", include_schema=False)}
<body>
  <a class="jx-skip-link" href="#main-content">跳到主要内容</a>
  {render_site_header("")}
  <div class="shell utility-shell">
    <main id="main-content" class="utility-page">
      <p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>404 · Missing page</p>
      <p class="utility-page__number" aria-hidden="true">404</p>
      <h1>这页没有留下划线。</h1>
      <p>地址可能已经移动，也可能从未被策展进公开书架。你可以从三条阅读线重新进入，或者直接搜索完整书架。</p>
      <div class="hero-actions"><a class="jx-action" href="./#constellations">回到阅读星座</a><a class="jx-action jx-action--secondary" href="shelf.html">打开完整书架</a></div>
    </main>
    {render_footer(facts["data_through"])}
  </div>
</body>
</html>'''


def render_legacy_highlights_html(facts: dict) -> str:
    title = "早期划线实验 · after-reading"
    description = "2024 年的早期划线导出实验；公开页保留上下文、来源边界与作品集出口。"
    source_url = f"{REPO_URL}/blob/main/{quote('划线/content.md')}"
    archive_url = f"{REPO_URL}/tree/main/{quote('划线')}"
    return f'''<!doctype html>
<html lang="zh-CN">
{render_head(title, description, LEGACY_HIGHLIGHTS_URL, facts, asset_prefix="../", robots="noindex, follow", include_schema=False)}
<body>
  <a class="jx-skip-link" href="#main-content">跳到主要内容</a>
  {render_site_header("", "../")}
  <div class="shell utility-shell">
    <main id="main-content" class="utility-page utility-page--archive">
      <p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Archive · 2024</p>
      <span class="jx-chip" data-state="archived">Archived experiment</span>
      <h1>一份划线导出，<br><em>不是一件完成作品。</em></h1>
      <p>这是我最早尝试把阅读痕迹从工具里带出来的页面。原始文字与截图仍保留在仓库；公开 URL 只保留上下文，避免把第三方网页壳误当成我的产品设计。</p>
      <div class="utility-page__ledger">
        <div><span>What remains</span><strong>文字摘录 + 2 张截图</strong><p>用于说明方法演化，不代表系统化读书笔记。</p></div>
        <div><span>Public boundary</span><strong>第三方导出壳已移除</strong><p>不加载 Notion 运行时代码、追踪脚本或过时品牌元数据。</p></div>
      </div>
      <div class="hero-actions"><a class="jx-action" href="{source_url}">查看文字源文件</a><a class="jx-action jx-action--secondary" href="{archive_url}">查看仓库归档</a><a class="jx-action jx-action--secondary" href="../#notes">回到阅读痕迹</a></div>
    </main>
    {render_footer(facts["data_through"], "../")}
  </div>
</body>
</html>'''


def render_robots_txt() -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n"


def render_sitemap_xml(facts: dict) -> str:
    urls = (SITE_URL, f"{SITE_URL}shelf.html")
    entries = "\n".join(
        f"  <url><loc>{url}</loc><lastmod>{facts['data_through']}</lastmod></url>"
        for url in urls
    )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>
'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when index.html differs from generated output")
    args = parser.parse_args(argv)

    if not os.path.exists(SHELF_PATH):
        print(f"ERROR: {SHELF_PATH} not found. Run scripts/fetch_weread.py first.", file=sys.stderr)
        return 1

    shelf = load_shelf()
    curation = load_curation()
    takes = load_takes()
    identity = load_identity()

    errors = validate_sources(shelf, curation, takes, identity)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    html = render_html(shelf, curation, takes, identity)
    shelf_html = render_shelf_html(shelf, curation, takes, identity)
    facts = reading_facts(shelf, curation, takes)
    outputs = (
        (OUTPUT_PATH, html),
        (SHELF_OUTPUT_PATH, shelf_html),
        (NOT_FOUND_OUTPUT_PATH, render_not_found_html(facts)),
        (ROBOTS_OUTPUT_PATH, render_robots_txt()),
        (SITEMAP_OUTPUT_PATH, render_sitemap_xml(facts)),
        (LEGACY_HIGHLIGHTS_OUTPUT_PATH, render_legacy_highlights_html(facts)),
    )
    if args.check:
        stale = []
        for output_path, generated in outputs:
            current = ""
            if os.path.exists(output_path):
                with open(output_path, encoding="utf-8") as f:
                    current = f.read()
            if current != generated:
                stale.append(os.path.basename(output_path))
        if stale:
            print("SHELF_BUILD_STALE: run python scripts/build_shelf.py", file=sys.stderr)
            print(f"STALE: {', '.join(stale)}", file=sys.stderr)
            return 1
        print(f"SHELF_BUILD_OK: {OUTPUT_PATH}, {SHELF_OUTPUT_PATH}")
    else:
        for output_path, generated in outputs:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(generated)
            print(f"WROTE: {output_path} ({len(generated)} bytes)")

    n_articles = shelf_html.count('<article class="book"')
    n_sections = shelf_html.count('class="shelf-section"')
    n_constellations = html.count('class="reading-constellation"')
    print(f"articles: {n_articles}, sections: {n_sections}, constellations: {n_constellations}")
    expected_articles = len(curated_ids(curation))
    expected_sections = len(curation["sections"])
    if n_articles != expected_articles or n_sections != expected_sections or n_constellations != 3:
        print(
            f"ERROR: expected {expected_articles} articles + {expected_sections} sections + 3 constellations, "
            f"got {n_articles}/{n_sections}/{n_constellations}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
