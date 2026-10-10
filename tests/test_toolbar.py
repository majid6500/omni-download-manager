"""Selection-driven enable/disable of the fixed top toolbar."""

import unittest

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from omni_download_manager.constants import APP_NAME
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.ui.actions import ItemAction
from omni_download_manager.ui.icons import icon_pixmap, make_icon
from omni_download_manager.ui.theme import ThemeManager
from omni_download_manager.ui.toolbar import (
    ADD_ICON_COLOR,
    REMOVE_ICON_COLOR,
    TOOLBAR_ICON_COLOR,
    Toolbar,
)

S = DownloadStatus


def _item(status: DownloadStatus, *, name: str = "file.bin", resumable: bool | None = None) -> DownloadItem:
    return DownloadItem(
        url=f"https://example.com/{name}",
        directory="/downloads",
        filename=name,
        status=status,
        resumable=resumable,
    )


class ToolbarStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.toolbar = Toolbar(ThemeManager())

    def _enabled(self) -> set[ItemAction]:
        return {action for action, button in self.toolbar._buttons.items() if button.isEnabled()}

    def assertEnabled(self, expected: set[ItemAction]) -> None:  # noqa: N802
        self.assertEqual(self._enabled(), expected)

    def test_every_action_is_disabled_without_a_selection(self) -> None:
        self.toolbar.set_selection([])
        self.assertEnabled(set())
        self.assertEqual(self.toolbar._count.text(), "")

    def test_toolbar_uses_larger_controls_and_the_new_play_and_retry_icons(self) -> None:
        self.assertEqual(self.toolbar._buttons[ItemAction.RESUME]._spec.icon, "play-02")
        self.assertEqual(self.toolbar._buttons[ItemAction.PAUSE]._spec.icon, "pause-02")
        self.assertEqual(self.toolbar._buttons[ItemAction.RETRY]._spec.icon, "retry-02")
        self.assertEqual(self.toolbar._buttons[ItemAction.CANCEL]._spec.icon, "cancel-02")
        self.assertEqual(self.toolbar._buttons[ItemAction.REMOVE]._spec.icon, "trash-bin-02")
        self.assertEqual(self.toolbar._buttons[ItemAction.REMOVE].property("variant"), "tool-plain")
        self.assertEqual(self.toolbar._add.property("variant"), "tool-plain")
        self.assertEqual(self.toolbar._add.text(), "")
        self.assertEqual(self.toolbar._add.size().width(), 46)
        self.assertEqual(self.toolbar._buttons[ItemAction.REMOVE].size().width(), 46)
        self.assertEqual(self.toolbar._buttons[ItemAction.REMOVE].size().height(), 46)
        self.toolbar.set_selection([_item(S.PENDING)])
        self.assertEqual(self.toolbar._buttons[ItemAction.RESUME]._color(), TOOLBAR_ICON_COLOR)
        self.assertEqual(
            self.toolbar._buttons[ItemAction.REMOVE]._color(),
            REMOVE_ICON_COLOR,
        )
        remove_image = icon_pixmap("trash-bin-02", REMOVE_ICON_COLOR, 28).toImage()
        tint = QColor(REMOVE_ICON_COLOR).rgba()
        self.assertGreater(
            sum(
                remove_image.pixelColor(x, y).rgba() == tint
                for y in range(remove_image.height())
                for x in range(remove_image.width())
            ),
            50,
        )
        settings_image = icon_pixmap("settings-02", TOOLBAR_ICON_COLOR, 56).toImage()
        tint = QColor(TOOLBAR_ICON_COLOR).rgba()
        self.assertGreater(
            sum(
                settings_image.pixelColor(x, y).rgba() == tint
                for y in range(settings_image.height())
                for x in range(settings_image.width())
            ),
            50,
        )
        self.assertEqual(self.toolbar._buttons[ItemAction.RESUME].width(), 46)
        self.assertEqual(self.toolbar._buttons[ItemAction.RESUME].iconSize().width(), 28)
        self.assertEqual(self.toolbar._add.iconSize().width(), 28)
        self.assertFalse(self.toolbar._add.icon().isNull())
        add_image = icon_pixmap("add-02", ADD_ICON_COLOR, 28).toImage()
        tint = QColor(ADD_ICON_COLOR).rgba()
        self.assertGreater(
            sum(
                add_image.pixelColor(x, y).rgba() == tint
                for y in range(add_image.height())
                for x in range(add_image.width())
            ),
            50,
        )
        self.assertEqual(self.toolbar._settings.accessibleName(), "Settings")
        self.assertEqual(self.toolbar._settings.size().width(), 46)
        self.assertEqual(self.toolbar._settings.size().height(), 46)
        self.assertFalse(self.toolbar._settings.icon().isNull())
        brand_layout = self.toolbar._brand.layout()
        self.assertIsInstance(brand_layout.itemAt(0).widget(), QLabel)
        self.assertEqual(brand_layout.itemAt(0).widget().text(), APP_NAME)
        self.assertEqual(brand_layout.itemAt(0).widget().objectName(), "PageTitle")
        self.assertFalse(brand_layout.itemAt(1).widget().pixmap().isNull())
        for icon in (
            "add-02", "play-02", "pause-02", "folder-02", "retry-02",
            "cancel-02", "trash-bin-02", "settings-02",
        ):
            with self.subTest(icon=icon):
                self.assertFalse(make_icon(icon, "#FFFFFF", 28).isNull())

    def test_toolbar_buttons_follow_the_requested_left_to_right_order(self) -> None:
        expected = [
            self.toolbar._add,
            self.toolbar._buttons[ItemAction.RESUME],
            self.toolbar._buttons[ItemAction.PAUSE],
            self.toolbar._buttons[ItemAction.RETRY],
            self.toolbar._buttons[ItemAction.CANCEL],
            self.toolbar._buttons[ItemAction.REMOVE],
            self.toolbar._buttons[ItemAction.OPEN_FOLDER],
            self.toolbar._buttons[ItemAction.OPEN_FILE],
            self.toolbar._settings,
        ]
        layout_widgets = [
            self.toolbar.layout().itemAt(index).widget()
            for index in range(self.toolbar.layout().count())
        ]
        layout_buttons = [
            widget for widget in layout_widgets if isinstance(widget, QPushButton)
        ]
        self.assertEqual(layout_buttons, expected)
        self.assertIs(layout_widgets[-1], self.toolbar._brand)
        brand_layout = self.toolbar._brand.layout()
        self.assertEqual(brand_layout.itemAt(0).widget().text(), APP_NAME)
        self.assertFalse(brand_layout.itemAt(1).widget().pixmap().isNull())
        self.assertEqual(
            list(self.toolbar._buttons),
            [
                ItemAction.RESUME,
                ItemAction.PAUSE,
                ItemAction.RETRY,
                ItemAction.CANCEL,
                ItemAction.REMOVE,
                ItemAction.OPEN_FOLDER,
                ItemAction.OPEN_FILE,
            ],
        )
        self.assertEqual(self.toolbar._add.accessibleName(), "Add download")

    def test_settings_button_requests_navigation(self) -> None:
        observed: list[bool] = []
        self.toolbar.settingsRequested.connect(lambda: observed.append(True))

        self.toolbar._settings.click()

        self.assertEqual(observed, [True])

    def test_downloading_offers_pause_cancel_and_delete(self) -> None:
        self.toolbar.set_selection([_item(S.DOWNLOADING, resumable=True)])
        self.assertEnabled({ItemAction.PAUSE, ItemAction.CANCEL, ItemAction.REMOVE, ItemAction.OPEN_FOLDER})

    def test_downloading_that_cannot_resume_disables_pause(self) -> None:
        self.toolbar.set_selection([_item(S.DOWNLOADING, resumable=False)])
        self.assertEnabled({ItemAction.CANCEL, ItemAction.REMOVE, ItemAction.OPEN_FOLDER})

    def test_paused_offers_resume_cancel_and_delete(self) -> None:
        self.toolbar.set_selection([_item(S.PAUSED)])
        self.assertEnabled({ItemAction.RESUME, ItemAction.CANCEL, ItemAction.REMOVE, ItemAction.OPEN_FOLDER})

    def test_start_continue_button_starts_pending_and_resumes_paused(self) -> None:
        for status, expected_action in ((S.PENDING, "start"), (S.PAUSED, "resume")):
            with self.subTest(status=status):
                toolbar = Toolbar(ThemeManager())
                item = _item(status)
                toolbar.set_selection([item])
                observed: list[tuple[str, str]] = []
                toolbar.actionRequested.connect(
                    lambda action, item_id: observed.append((action, item_id))
                )

                toolbar._buttons[ItemAction.RESUME].click()

                self.assertEqual(observed[-1], (expected_action, item.id))

    def test_failed_offers_retry_and_delete(self) -> None:
        self.toolbar.set_selection([_item(S.FAILED)])
        enabled = self._enabled()
        self.assertIn(ItemAction.RETRY, enabled)
        self.assertIn(ItemAction.REMOVE, enabled)
        self.assertIn(ItemAction.OPEN_FOLDER, enabled)
        self.assertNotIn(ItemAction.PAUSE, enabled)
        self.assertNotIn(ItemAction.RESUME, enabled)
        self.assertNotIn(ItemAction.OPEN_FILE, enabled)

    def test_completed_offers_open_file_open_folder_and_delete(self) -> None:
        self.toolbar.set_selection([_item(S.COMPLETED)])
        self.assertEnabled({ItemAction.OPEN_FILE, ItemAction.OPEN_FOLDER, ItemAction.REMOVE})

    def test_queued_offers_start_and_delete(self) -> None:
        self.toolbar.set_selection([_item(S.QUEUED)])
        self.assertEnabled(
            {ItemAction.RESUME, ItemAction.PAUSE, ItemAction.CANCEL, ItemAction.REMOVE, ItemAction.OPEN_FOLDER}
        )

    def test_cancelled_download_can_be_started_again(self) -> None:
        self.toolbar.set_selection([_item(S.CANCELLED)])
        self.assertEnabled({ItemAction.RETRY, ItemAction.REMOVE, ItemAction.OPEN_FOLDER})

    def test_single_item_actions_are_disabled_for_a_multi_selection(self) -> None:
        self.toolbar.set_selection([_item(S.FAILED, name="a"), _item(S.COMPLETED, name="b")])
        enabled = self._enabled()
        for action in (ItemAction.START, ItemAction.RETRY, ItemAction.OPEN_FILE, ItemAction.OPEN_FOLDER):
            self.assertNotIn(action, enabled)
        self.assertIn(ItemAction.REMOVE, enabled)
        self.assertIn(ItemAction.CANCEL, enabled)
        self.assertEqual(self.toolbar._count.text(), "2 selected")

    def test_one_selected_item_emits_a_single_item_action(self) -> None:
        item = _item(S.PAUSED)
        self.toolbar.set_selection([item])
        observed: list[tuple[str, str]] = []
        self.toolbar.actionRequested.connect(lambda action, item_id: observed.append((action, item_id)))

        self.toolbar._buttons[ItemAction.RESUME].click()

        self.assertEqual(observed, [("resume", item.id)])

    def test_many_selected_items_emit_a_bulk_action(self) -> None:
        items = [_item(S.PAUSED, name="a"), _item(S.PAUSED, name="b")]
        self.toolbar.set_selection(items)
        observed: list[tuple[str, list[str]]] = []
        self.toolbar.bulkActionRequested.connect(lambda action, ids: observed.append((action, ids)))

        self.toolbar._buttons[ItemAction.RESUME].click()

        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][0], "resume")
        self.assertCountEqual(observed[0][1], [item.id for item in items])

    def test_add_download_stays_available_without_a_selection(self) -> None:
        self.toolbar.set_selection([])
        observed: list[bool] = []
        self.toolbar.addRequested.connect(lambda: observed.append(True))

        self.toolbar._add.click()

        self.assertEqual(observed, [True])


if __name__ == "__main__":
    unittest.main()
