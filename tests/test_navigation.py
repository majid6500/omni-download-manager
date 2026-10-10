"""Bottom navigation retains the existing download view filters."""

import unittest

from PySide6.QtWidgets import QApplication, QHBoxLayout

from omni_download_manager.ui.models import ViewFilter
from omni_download_manager.ui.sidebar import BottomNavigation
from omni_download_manager.ui.theme import ThemeManager


class BottomNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.navigation = BottomNavigation(ThemeManager())

    def test_navigation_contains_only_the_four_existing_download_views(self) -> None:
        self.assertEqual(
            list(self.navigation._buttons),
            [view.value for view in ViewFilter],
        )
        self.assertEqual(self.navigation.objectName(), "BottomNavigation")
        self.assertIsInstance(self.navigation.layout(), QHBoxLayout)
        self.assertGreater(self.navigation.width(), self.navigation.height())
        self.assertEqual(self.navigation._buttons[ViewFilter.ALL.value].text(), "All downloads")

    def test_all_downloads_is_selected_initially_and_clicking_changes_selection(self) -> None:
        self.assertTrue(self.navigation._buttons[ViewFilter.ALL.value].isChecked())
        self.assertFalse(self.navigation._buttons[ViewFilter.FAILED.value].isChecked())
        selected: list[str] = []
        self.navigation.selected.connect(selected.append)

        self.navigation._buttons[ViewFilter.FAILED.value].click()

        self.assertEqual(selected, [ViewFilter.FAILED.value])
        self.assertTrue(self.navigation._buttons[ViewFilter.FAILED.value].isChecked())
        self.assertFalse(self.navigation._buttons[ViewFilter.ALL.value].isChecked())

    def test_programmatic_selection_keeps_the_active_button_in_sync(self) -> None:
        selected: list[str] = []
        self.navigation.selected.connect(selected.append)

        self.navigation.select(ViewFilter.COMPLETED.value)

        self.assertEqual(selected, [ViewFilter.COMPLETED.value])
        self.assertTrue(self.navigation._buttons[ViewFilter.COMPLETED.value].isChecked())

    def test_counts_are_forwarded_to_the_corresponding_navigation_button(self) -> None:
        self.navigation.set_counts(
            {
                ViewFilter.ALL: 12,
                ViewFilter.ACTIVE: 3,
                ViewFilter.COMPLETED: 7,
                ViewFilter.FAILED: 2,
            }
        )

        self.assertEqual(
            [self.navigation._buttons[view.value]._count for view in ViewFilter],
            [12, 3, 7, 2],
        )


if __name__ == "__main__":
    unittest.main()
