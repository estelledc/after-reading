#!/usr/bin/env python3
"""Build index.html from the public bookshelf source files.

Output:
    index.html — single-file Editorial / publication style 「Jason 的书架」hub.
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
SITE_URL = "https://estelledc.github.io/after-reading/"
REPO_URL = "https://github.com/estelledc/after-reading"

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

    return f"""<article class="book" id="b-{escape(bid)}">
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


def render_html(shelf: dict, curation: dict, takes: dict, identity: dict) -> str:
    books_by_id = {str(b["bookId"]): b for b in shelf.get("books", [])}
    ids = curated_ids(curation)
    selected_books = [books_by_id[book_id] for book_id in ids]
    curated_count = len(ids)
    section_count = len(curation["sections"])
    take_count = sum(bool(takes.get(book_id, "").strip()) for book_id in ids)
    data_timestamps = [book.get("readUpdateTime", 0) for book in selected_books if book.get("readUpdateTime")]
    data_start = fmt_date(min(data_timestamps))
    data_through = fmt_date(max(data_timestamps))
    temporal_coverage = f"{data_start[:7]}/{data_through[:7]}"

    section_blocks = []
    idx = 1
    for section in curation["sections"]:
        block, idx = render_section(section, books_by_id, takes, idx)
        section_blocks.append(block)
    sections_html = "\n\n".join(section_blocks)
    shelf_index_html = render_shelf_index(curation)
    note_archives_html = render_note_archives()

    intro = escape(identity.get("intro", ""))
    timeline = escape(identity.get("timeline_narrative", ""))
    hero_lead = escape(identity.get("hero_lead", ""))
    english_summary = escape(identity.get("english_summary", ""))
    problem = escape(identity.get("problem", ""))
    role_jason = escape(identity.get("role_jason", ""))
    role_ai = escape(identity.get("role_ai", ""))
    system = escape(identity.get("system", ""))
    limitations = escape(identity.get("limitations", ""))
    data_through_dot = data_through.replace("-", "·")
    social_title = "after-reading · Jason 的公开阅读系统"
    social_description = "把原始书架、人工分类、短判断与阅读轨迹串成一条可追溯的个人阅读系统。"
    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": social_title,
        "url": SITE_URL,
        "description": social_description,
        "inLanguage": ["zh-CN", "en"],
        "dateModified": data_through,
        "temporalCoverage": temporal_coverage,
        "author": {
            "@type": "Person",
            "name": "Jason",
            "url": "https://estelledc.github.io/about/",
        },
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": curated_count,
            "itemListOrder": "https://schema.org/ItemListOrderAscending",
        },
        "sameAs": REPO_URL,
    }
    schema_json = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{social_title}</title>
  <meta name="description" content="{social_description}">
  <link rel="canonical" href="{SITE_URL}">
  <meta property="og:title" content="{social_title}">
  <meta property="og:description" content="{social_description}">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="zh_CN">
  <meta property="og:url" content="{SITE_URL}">
  <meta property="og:site_name" content="after-reading">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{social_title}">
  <meta name="twitter:description" content="{social_description}">
  <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
  <script type="application/ld+json">{schema_json}</script>
  <link rel="stylesheet" href="assets/jx/tokens.css">
  <link rel="stylesheet" href="assets/jx/base.css">
  <link rel="stylesheet" href="assets/jx/components.css">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  <a class="jx-skip-link" href="#main-content">跳到主要内容</a>
  <header class="jx-site-header">
    <div class="jx-site-header__inner">
      <a class="jx-site-header__identity" href="./" aria-label="after-reading 首页">
        <strong>after-reading</strong>
        <span>Jason 的公开阅读系统</span>
      </a>
      <div class="jx-site-nav">
        <nav class="jx-site-nav__links" aria-label="Jason 全局导航">
          <a class="jx-return-to-hub" href="https://estelledc.github.io/">Jason Hub</a>
          <a href="https://estelledc.github.io/about/">About</a>
          <a href="https://estelledc.github.io/resume/">Resume</a>
          <a href="{REPO_URL}">GitHub</a>
        </nav>
        <details class="jx-site-nav__menu">
          <summary aria-label="打开全局导航">导航</summary>
          <nav aria-label="Jason 移动端全局导航">
            <a class="jx-return-to-hub" href="https://estelledc.github.io/">Jason Hub</a>
            <a href="https://estelledc.github.io/about/">About</a>
            <a href="https://estelledc.github.io/resume/">Resume</a>
            <a href="{REPO_URL}">GitHub</a>
          </nav>
        </details>
      </div>
    </div>
  </header>
  <div class="shell">
    <main id="main-content">
    <section class="hero">
      <p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Reading as evidence</p>
      <span class="jx-chip" data-state="maintained">Curated · Maintained</span>
      <h1 class="hero-title">读完之后，留下些什么？</h1>
      <p class="hero-kicker">Jason 的书架 · after-reading</p>
      <p class="hero-lead">{hero_lead}</p>
      <div class="hero-actions">
        <a class="jx-action" href="#reading-system">了解阅读系统</a>
        <a class="jx-action jx-action--secondary" href="#s-serious-fiction">进入书架</a>
      </div>
      <p class="hero-intro">{intro}</p>
      <p class="hero-summary-en" lang="en">{english_summary}</p>
      <p class="hero-boundary"><strong>协作边界：</strong>{role_jason} {role_ai}</p>
    </section>

    <section class="system-section" id="reading-system" aria-labelledby="system-title">
      <header class="section-intro">
        <p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>System · Evidence</p>
        <h2 id="system-title">这不是排行榜，是一条判断链。</h2>
        <p>{problem}</p>
      </header>
      <div class="jx-proof">
        <div>
          <span class="jx-chip" data-state="maintained">Source-matched</span>
          <p class="jx-proof__summary">{system}</p>
          <p class="jx-proof__summary-en" lang="en">The value lies in the chain: source state → curation → personal judgment → public artifact.</p>
          <div class="jx-proof__metrics" aria-label="可机械核验的书架证据">
            <div class="jx-proof__metric"><strong>{curated_count}</strong><span>个唯一策展条目，源数据均标记完读</span></div>
            <div class="jx-proof__metric"><strong>{section_count}</strong><span>个由 Jason 维护的阅读分类</span></div>
            <div class="jx-proof__metric"><strong>{take_count}/{curated_count}</strong><span>策展条目具备短判断</span></div>
          </div>
          <div class="jx-proof__links" aria-label="项目证据入口">
            <a class="jx-pill" href="#notes">查看笔记档案</a>
            <a class="jx-pill" href="{REPO_URL}/blob/main/scripts/validate_shelf.py">查看验证契约</a>
          </div>
        </div>
        <dl class="jx-proof__meta">
          <div><dt>Problem / 问题</dt><dd>{problem}</dd></div>
          <div><dt>Jason / 判断与验收</dt><dd>{role_jason}</dd></div>
          <div><dt>AI / 辅助</dt><dd>{role_ai}</dd></div>
          <div><dt>Evidence / 证据</dt><dd>当前 {curated_count} 个策展 ID 均唯一、可回查，并在源缓存中标记为完读；生成前后由脚本检查。</dd></div>
          <div><dt>Limitations / 局限</dt><dd class="jx-proof__limitation">{limitations} 当前公开样本截至 {data_through}。</dd></div>
        </dl>
      </div>
    </section>

    <section class="notes-section" id="notes" aria-labelledby="notes-title">
      <header class="section-intro">
        <p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Reading artifacts</p>
        <h2 id="notes-title">笔记不是统一模板，而是逐步形成的方法痕迹。</h2>
        <p>仓库目前保留 4 个按书组织的笔记目录与 1 组早期划线实验。它们深浅不一，因此不再统一称作“深度笔记”。</p>
      </header>
      <div class="note-archives">
        {note_archives_html}
      </div>
    </section>

    <section class="timeline" id="timeline" aria-labelledby="timeline-title">
      <p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Timeline</p>
      <h2 class="section-title" id="timeline-title">阅读轨迹</h2>
      <p class="timeline-narrative">{timeline}</p>
    </section>

    <nav class="shelf-index" aria-labelledby="shelf-index-title">
      <div>
        <p class="jx-eyebrow"><span class="jx-eyebrow__rule"></span>Curated shelf</p>
        <h2 id="shelf-index-title">按阅读作用进入，而不是按“高级程度”排序。</h2>
      </div>
      <ol>
        {shelf_index_html}
      </ol>
    </nav>

    {sections_html}

    </main>

    <footer class="jx-footer">
      <div class="jx-footer__colophon">
        <strong>after-reading</strong>
        <span lang="en">PUBLIC READING SYSTEM</span>
      </div>
      <nav class="jx-footer__index" aria-label="作品集导航">
        <a href="https://estelledc.github.io/">hub</a>
        <a href="https://estelledc.github.io/about/">about</a>
        <a href="https://estelledc.github.io/resume/">resume</a>
        <a href="{REPO_URL}">github</a>
      </nav>
      <time class="jx-footer__stamp" datetime="{data_through}" lang="en">DATA THROUGH {data_through_dot}</time>
    </footer>
  </div>
</body>
</html>"""


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
    if args.check:
        current = ""
        if os.path.exists(OUTPUT_PATH):
            with open(OUTPUT_PATH, encoding="utf-8") as f:
                current = f.read()
        if current != html:
            print("SHELF_BUILD_STALE: run python scripts/build_shelf.py", file=sys.stderr)
            return 1
        print(f"SHELF_BUILD_OK: {OUTPUT_PATH}")
    else:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"WROTE: {OUTPUT_PATH} ({len(html)} bytes)")

    n_articles = html.count('<article class="book"')
    n_sections = html.count('class="shelf-section"')
    n_returns = html.count("return-to-hub")
    print(f"articles: {n_articles}, sections: {n_sections}, return-to-hub: {n_returns}")
    expected_articles = len(curated_ids(curation))
    expected_sections = len(curation["sections"])
    if n_articles != expected_articles or n_sections != expected_sections:
        print(
            f"ERROR: expected {expected_articles} articles + {expected_sections} sections, "
            f"got {n_articles}/{n_sections}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
