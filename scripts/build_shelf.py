#!/usr/bin/env python3
"""Build index.html from data/raw-shelf.json + content/curation.yaml + content/jason-takes.md.

Output:
    index.html — single-file Editorial / publication style 「Jason 的书架」hub.
"""

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

# 5 本有笔记的目录名（精确字符串，与仓内实际目录对应）
NOTE_DIRS = [
    "《outlive》",
    "《如何像列奥纳多·达芬奇一样思考》",
    "《未来世界的幸存者》阮一峰",
    "《温州人的性格》",
    "划线",
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
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def find_note_link(book: dict) -> str:
    """Match book title against NOTE_DIRS by 《title》prefix substring."""
    title = book.get("title", "")
    for d in NOTE_DIRS:
        if d == "划线":
            continue
        m = re.match(r"《(.+?)》", d)
        if m and m.group(1).lower() in title.lower():
            return quote(d) + "/"
    return ""


def render_book_card(idx: int, book: dict, take: str) -> str:
    bid = book.get("bookId", "")
    title = escape(book.get("title", "?"))
    author = escape(book.get("author", "?")) or "—"
    date = fmt_date(book.get("readUpdateTime", 0))
    take_html = escape(take) if take else "<em>(待补)</em>"

    notes_html = ""
    href = find_note_link(book)
    if href:
        notes_html = f'    <a class="book-notes" href="{href}">→ 笔记</a>\n'

    return f"""<article class="book" id="b-{escape(bid)}">
  <span class="book-num">№ {idx:03d}</span>
  <div class="book-body">
    <h3 class="book-title">{title}</h3>
    <p class="book-meta">{author} · {date} 完读</p>
    <p class="book-take">{take_html}</p>
{notes_html}  </div>
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
    section_html = f"""<section class="shelf-section" id="s-{slug}">
  <header class="section-head">
    <h2 class="section-title">{title}</h2>
    <p class="section-blurb">{blurb}</p>
    <p class="section-count">{len(section['book_ids'])} 本</p>
  </header>
  <div class="book-grid">
    {cards_html}
  </div>
</section>"""
    return section_html, idx


def render_html(shelf: dict, curation: dict, takes: dict, identity: dict) -> str:
    books_by_id = {b["bookId"]: b for b in shelf.get("books", [])}

    section_blocks = []
    idx = 1
    for section in curation["sections"]:
        block, idx = render_section(section, books_by_id, takes, idx)
        section_blocks.append(block)
    sections_html = "\n\n".join(section_blocks)

    intro = escape(identity.get("intro", ""))
    timeline = escape(identity.get("timeline_narrative", ""))
    hero_lead = escape(identity.get("hero_lead", ""))
    build_date = datetime.datetime.now().strftime("%Y-%m-%d")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Jason 的书架 · after-reading</title>
  <meta name="description" content="73 本完读书 · 5 本深度笔记 · 用阅读轨迹做自我表达">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  <div class="shell">
    <header class="masthead">
      <h1 class="mast-title">after-reading</h1>
      <a class="return-to-hub" href="https://estelledc.github.io/" rel="home">← estelledc.github.io</a>
    </header>

    <section class="hero">
      <p class="eyebrow">Bookshelf · Identity</p>
      <h1 class="hero-title">Jason 的书架</h1>
      <p class="hero-lead">{hero_lead}</p>
      <p class="hero-intro">{intro}</p>
    </section>

    <section class="timeline">
      <h2 class="section-title">阅读轨迹</h2>
      <p class="timeline-narrative">{timeline}</p>
    </section>

    {sections_html}

    <footer class="site-footer">
      <p>
        2026 · Jason Xun ·
        <a href="https://github.com/estelledc/after-reading" target="_blank" rel="noopener">GitHub</a>
        · last build {build_date}
      </p>
    </footer>
  </div>
</body>
</html>"""


def main() -> int:
    if not os.path.exists(SHELF_PATH):
        print(f"ERROR: {SHELF_PATH} not found. Run scripts/fetch_weread.py first.", file=sys.stderr)
        return 1

    shelf = load_shelf()
    curation = load_curation()
    takes = load_takes()
    identity = load_identity()

    html = render_html(shelf, curation, takes, identity)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"WROTE: {OUTPUT_PATH} ({len(html)} bytes)")

    n_articles = html.count('<article class="book"')
    n_sections = html.count('class="shelf-section"')
    n_returns = html.count("return-to-hub")
    print(f"articles: {n_articles}, sections: {n_sections}, return-to-hub: {n_returns}")
    if n_articles != 73 or n_sections != 8:
        print(f"WARN: expected 73 articles + 8 sections, got {n_articles}/{n_sections}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
