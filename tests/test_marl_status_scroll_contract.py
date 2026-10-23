from pathlib import Path
import unittest


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "frontend"
    / "godot"
    / "scripts"
    / "app"
    / "marl_laboratory.gd"
)


class MarlStatusScrollContractTests(unittest.TestCase):
    def test_status_column_has_vertical_only_scroll_container(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        status_scroll = source.split('status_scroll.name="ExperimentStatusScroll"', 1)[1]
        status_card = source.split("var status_card=PanelContainer.new()", 1)[1]
        self.assertIn("status_card.size_flags_vertical=Control.SIZE_EXPAND_FILL", status_card)
        self.assertIn("status_scroll.vertical_scroll_mode=ScrollContainer.SCROLL_MODE_AUTO", status_scroll)
        self.assertIn("status_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED", status_scroll)
        self.assertIn("status_card.add_child(status_scroll)", status_card)
        self.assertIn("status_scroll.add_child(status_content)", status_scroll)

if __name__ == "__main__":
    unittest.main()
