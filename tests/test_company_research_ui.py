"""Regression tests for the Company Research Streamlit workflow."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import careerlens.database as database


class CompanyResearchUiTests(unittest.TestCase):
    """Verify repeated create actions stay independent in one UI session."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def database_patches(self):
        """Route every page database call to this test's temporary database."""
        initialize_database = database.initialize_database
        list_companies = database.list_companies
        get_company = database.get_company
        create_company = database.create_company
        update_company = database.update_company
        delete_company = database.delete_company
        list_sources = database.list_sources
        get_source = database.get_source
        create_source = database.create_source
        update_source = database.update_source
        delete_source = database.delete_source
        database_path = self.database_path

        return patch.multiple(
            database,
            initialize_database=lambda: initialize_database(database_path),
            list_companies=lambda: list_companies(database_path),
            get_company=lambda company_id: get_company(company_id, database_path),
            create_company=lambda name, main_business="", strengths="", strategy="", dx_ai_initiatives="", overseas_business="", roles_work="", free_notes="": create_company(
                name,
                main_business,
                strengths,
                strategy,
                dx_ai_initiatives,
                overseas_business,
                roles_work,
                free_notes,
                database_path,
            ),
            update_company=lambda company_id, name, main_business, strengths, strategy, dx_ai_initiatives, overseas_business, roles_work, free_notes: update_company(
                company_id,
                name,
                main_business,
                strengths,
                strategy,
                dx_ai_initiatives,
                overseas_business,
                roles_work,
                free_notes,
                database_path,
            ),
            delete_company=lambda company_id: delete_company(
                company_id, database_path
            ),
            list_sources=lambda company_id: list_sources(company_id, database_path),
            get_source=lambda source_id, company_id: get_source(
                source_id, company_id, database_path
            ),
            create_source=lambda company_id, title, url, source_type, publication_date=None, notes="": create_source(
                company_id,
                title,
                url,
                source_type,
                publication_date,
                notes,
                database_path,
            ),
            update_source=lambda source_id, company_id, title, url, source_type, publication_date, notes: update_source(
                source_id,
                company_id,
                title,
                url,
                source_type,
                publication_date,
                notes,
                database_path,
            ),
            delete_source=lambda source_id, company_id: delete_source(
                source_id, company_id, database_path
            ),
        )

    @staticmethod
    def add_company(app: AppTest, name: str, main_business: str) -> None:
        """Create one company through the same controls used by a user."""
        app.button(key="add_company").click().run()
        next(widget for widget in app.text_input if widget.label == "企業名").set_value(
            name
        )
        next(
            widget for widget in app.text_area if widget.label == "主な事業"
        ).set_value(main_business)
        next(button for button in app.button if button.label == "企業を保存").click().run()

    def test_repeated_create_edit_delete_and_source_isolation(self) -> None:
        """Keep three companies and their research data isolated end to end."""
        with self.database_patches():
            page_path = (
                Path(__file__).resolve().parents[1]
                / "pages"
                / "2_company_research.py"
            )
            app = AppTest.from_file(page_path).run()

            self.add_company(app, "NEC", "NECの事業")
            self.add_company(app, "横浜銀行", "横浜銀行の事業")
            self.add_company(app, "キーエンス", "キーエンスの事業")

            companies = database.list_companies()
            self.assertEqual(
                {company["name"] for company in companies},
                {"NEC", "横浜銀行", "キーエンス"},
            )
            self.assertEqual(len(companies), 3)

            company_ids = {
                str(company["name"]): int(company["id"]) for company in companies
            }
            expected_business = {
                "NEC": "NECの事業",
                "横浜銀行": "横浜銀行の事業",
                "キーエンス": "キーエンスの事業",
            }
            for name, company_id in company_ids.items():
                app.selectbox(key="company_selector").select(company_id).run()
                selected = database.get_company(company_id)
                self.assertEqual(selected["main_business"], expected_business[name])

            nec_id = company_ids["NEC"]
            app.selectbox(key="company_selector").select(nec_id).run()
            app.button(key=f"edit_company_{nec_id}").click().run()
            next(
                widget for widget in app.text_area if widget.label == "主な事業"
            ).set_value("NECの更新済み事業")
            next(button for button in app.button if button.label == "変更を保存").click().run()

            self.assertEqual(
                database.get_company(nec_id)["main_business"],
                "NECの更新済み事業",
            )
            self.assertEqual(
                database.get_company(company_ids["横浜銀行"])["main_business"],
                "横浜銀行の事業",
            )
            self.assertEqual(
                database.get_company(company_ids["キーエンス"])["main_business"],
                "キーエンスの事業",
            )

            nec_source_id = database.create_source(
                nec_id,
                "NEC公式サイト",
                "https://example.com/nec",
                "企業公式サイト",
            )
            keyence_id = company_ids["キーエンス"]
            keyence_source_id = database.create_source(
                keyence_id,
                "キーエンス公式サイト",
                "https://example.com/keyence",
                "企業公式サイト",
            )

            app.selectbox(key="company_selector").select(nec_id).run()
            visible_button_keys = {button.key for button in app.button}
            self.assertIn(f"edit_source_{nec_source_id}", visible_button_keys)
            self.assertNotIn(f"edit_source_{keyence_source_id}", visible_button_keys)

            app.selectbox(key="company_selector").select(keyence_id).run()
            visible_button_keys = {button.key for button in app.button}
            self.assertIn(f"edit_source_{keyence_source_id}", visible_button_keys)
            self.assertNotIn(f"edit_source_{nec_source_id}", visible_button_keys)

            yokohama_id = company_ids["横浜銀行"]
            app.selectbox(key="company_selector").select(yokohama_id).run()
            app.button(key=f"delete_company_{yokohama_id}").click().run()
            app.button(key=f"confirm_delete_company_{yokohama_id}").click().run()

            remaining_companies = database.list_companies()
            self.assertEqual(
                {company["name"] for company in remaining_companies},
                {"NEC", "キーエンス"},
            )
            self.assertEqual(len(database.list_sources(nec_id)), 1)
            self.assertEqual(len(database.list_sources(keyence_id)), 1)


if __name__ == "__main__":
    unittest.main()
