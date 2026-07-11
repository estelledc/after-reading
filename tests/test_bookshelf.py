from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_shelf  # noqa: E402
import validate_shelf  # noqa: E402


class BookshelfContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.shelf = build_shelf.load_shelf()
        cls.curation = build_shelf.load_curation()
        cls.takes = build_shelf.load_takes()
        cls.identity = build_shelf.load_identity()

    def test_repository_source_contract_is_valid(self) -> None:
        self.assertEqual(
            [],
            build_shelf.validate_sources(
                self.shelf,
                self.curation,
                self.takes,
                self.identity,
            ),
        )

    def test_generated_pages_are_current_and_deterministic(self) -> None:
        first_home = build_shelf.render_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        second_home = build_shelf.render_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        first_shelf = build_shelf.render_shelf_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        second_shelf = build_shelf.render_shelf_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        facts = build_shelf.reading_facts(self.shelf, self.curation, self.takes)
        first_not_found = build_shelf.render_not_found_html(facts)
        second_not_found = build_shelf.render_not_found_html(facts)
        first_legacy = build_shelf.render_legacy_highlights_html(facts)
        second_legacy = build_shelf.render_legacy_highlights_html(facts)
        self.assertEqual(first_home, second_home)
        self.assertEqual(first_shelf, second_shelf)
        self.assertEqual(first_not_found, second_not_found)
        self.assertEqual(first_legacy, second_legacy)
        self.assertEqual(first_home, (ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(first_shelf, (ROOT / "shelf.html").read_text(encoding="utf-8"))
        self.assertEqual(first_not_found, (ROOT / "404.html").read_text(encoding="utf-8"))
        self.assertEqual(first_legacy, (ROOT / "划线" / "划线.html").read_text(encoding="utf-8"))
        self.assertEqual(build_shelf.render_robots_txt(), (ROOT / "robots.txt").read_text(encoding="utf-8"))
        self.assertEqual(build_shelf.render_sitemap_xml(facts), (ROOT / "sitemap.xml").read_text(encoding="utf-8"))

    def test_hero_exposes_actions_before_the_long_editorial_context(self) -> None:
        html = build_shelf.render_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        self.assertLess(html.index('class="hero-actions"'), html.index('class="hero-intro"'))

    def test_homepage_uses_three_constellations_instead_of_the_full_book_wall(self) -> None:
        html = build_shelf.render_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        self.assertEqual(3, html.count('class="reading-constellation"'))
        self.assertEqual(0, html.count('<article class="book"'))
        self.assertIn('href="shelf.html"', html)
        self.assertIn("How this shelf is made", html)

    def test_full_shelf_keeps_all_books_and_progressive_search(self) -> None:
        html = build_shelf.render_shelf_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        expected = len(build_shelf.curated_ids(self.curation))
        self.assertEqual(expected, html.count('<article class="book"'))
        self.assertEqual(expected, html.count('data-search="'))
        self.assertIn('id="shelf-search-input"', html)
        self.assertIn("全部书目仍可浏览", html)

    def test_json_ld_uses_the_canonical_portfolio_identity(self) -> None:
        html = build_shelf.render_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        self.assertIn('"@id": "https://estelledc.github.io/#person"', html)
        self.assertIn('"name": "Jason Xun"', html)

    def test_rendered_public_contract_is_valid(self) -> None:
        errors, counts = validate_shelf.validate()
        self.assertEqual([], errors)
        expected = len(build_shelf.curated_ids(self.curation))
        self.assertEqual(expected, counts["curated"])
        self.assertEqual(expected, counts["takes"])

    def test_discovery_and_error_pages_expose_safe_recovery_routes(self) -> None:
        facts = build_shelf.reading_facts(self.shelf, self.curation, self.takes)
        not_found = build_shelf.render_not_found_html(facts)
        legacy = build_shelf.render_legacy_highlights_html(facts)
        for html in (not_found, legacy):
            self.assertIn('name="robots" content="noindex', html)
            self.assertIn('href="https://estelledc.github.io/"', html)
            self.assertIn('href="https://estelledc.github.io/about/"', html)
            self.assertIn('href="https://estelledc.github.io/resume/"', html)
            self.assertIn(f'href="{build_shelf.REPO_URL}"', html)
        self.assertIn("这页没有留下划线", not_found)
        self.assertIn("第三方导出壳已移除", legacy)
        self.assertNotIn("NotionHQ", legacy)
        self.assertNotIn("ClientFramework", legacy)
        self.assertIn(f"Sitemap: {build_shelf.SITE_URL}sitemap.xml", build_shelf.render_robots_txt())

    def test_duplicate_curation_id_is_rejected(self) -> None:
        curation = copy.deepcopy(self.curation)
        duplicate = curation["sections"][0]["book_ids"][0]
        curation["sections"][1]["book_ids"].append(duplicate)
        errors = build_shelf.validate_sources(
            self.shelf,
            curation,
            self.takes,
            self.identity,
        )
        self.assertTrue(any("must be unique" in error for error in errors))

    def test_constellation_book_must_also_be_curated(self) -> None:
        curation = copy.deepcopy(self.curation)
        curation["constellations"][0]["book_ids"][0] = "not-curated"
        errors = build_shelf.validate_sources(
            self.shelf,
            curation,
            self.takes,
            self.identity,
        )
        self.assertTrue(any("must also exist" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
