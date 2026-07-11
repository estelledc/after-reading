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

    def test_generated_homepage_is_current_and_deterministic(self) -> None:
        first = build_shelf.render_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        second = build_shelf.render_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        self.assertEqual(first, second)
        self.assertEqual(first, (ROOT / "index.html").read_text(encoding="utf-8"))

    def test_hero_exposes_actions_before_the_long_editorial_context(self) -> None:
        html = build_shelf.render_html(
            self.shelf,
            self.curation,
            self.takes,
            self.identity,
        )
        self.assertLess(html.index('class="hero-actions"'), html.index('class="hero-intro"'))

    def test_rendered_public_contract_is_valid(self) -> None:
        errors, counts = validate_shelf.validate()
        self.assertEqual([], errors)
        expected = len(build_shelf.curated_ids(self.curation))
        self.assertEqual(expected, counts["curated"])
        self.assertEqual(expected, counts["takes"])

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


if __name__ == "__main__":
    unittest.main()
