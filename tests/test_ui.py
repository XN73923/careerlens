"""Regression tests for the shared CareerLens navigation foundation."""

import unittest

from careerlens.ui import GLOBAL_UI_CSS, NAVIGATION_ITEMS


class NavigationConfigurationTests(unittest.TestCase):
    def test_navigation_has_approved_labels_and_destinations(self) -> None:
        self.assertEqual(
            [(item.label, item.path) for item in NAVIGATION_ITEMS],
            [
                ("Home", "app.py"),
                ("My Profile", "pages/1_my_profile.py"),
                ("Company Research", "pages/2_company_research.py"),
                ("Research Assistant", "pages/3_research_assistant.py"),
                (
                    "Selection Preparation",
                    "pages/4_selection_preparation.py",
                ),
            ],
        )

    def test_default_streamlit_navigation_is_hidden(self) -> None:
        self.assertIn('[data-testid="stSidebarNav"]', GLOBAL_UI_CSS)
        self.assertIn("display: none !important", GLOBAL_UI_CSS)

    def test_visible_labels_do_not_expose_implementation_filenames(self) -> None:
        labels = [item.label for item in NAVIGATION_ITEMS]
        self.assertNotIn("app", labels)
        self.assertTrue(all(".py" not in label for label in labels))

    def test_direct_url_fallbacks_use_public_page_slugs(self) -> None:
        self.assertEqual(
            [item.fallback_url for item in NAVIGATION_ITEMS],
            [
                "/",
                "/my_profile",
                "/company_research",
                "/research_assistant",
                "/selection_preparation",
            ],
        )


if __name__ == "__main__":
    unittest.main()
