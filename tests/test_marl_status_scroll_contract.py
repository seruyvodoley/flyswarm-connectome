from pathlib import Path
import ast
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

    def test_student_workers_allow_slow_frozen_windows_startup(self) -> None:
        student_code = SOURCE.parents[4] / "src" / "flyswarm" / "marl" / "student_code.py"
        tree = ast.parse(student_code.read_text(encoding="utf-8"))
        timeout = next(
            node.value.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "DEFAULT_STUDENT_WORKER_STARTUP_TIMEOUT_SECONDS"
                for target in node.targets
            )
        )
        self.assertGreaterEqual(timeout, 60.0)

    def test_student_evaluation_has_an_explicit_running_status(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('"running":_t("Проверка стратегии…","Evaluating strategy…")', source)
        self.assertIn('if state=="complete" and target<=0.0:target=1.0', source)
        self.assertIn('status_progress.value=status_progress.max_value if state=="complete" else current', source)
        self.assertIn('state in ["starting","initializing","finalizing"]', source)

    def test_finished_worker_without_progress_file_still_shows_complete(self) -> None:
        app_state = SOURCE.with_name("app_state.gd").read_text(encoding="utf-8")
        self.assertIn('marl_progress["state"]="complete" if has_result else "error"', app_state)
        self.assertIn('marl_progress["message"]="Experiment complete; results saved."', app_state)

if __name__ == "__main__":
    unittest.main()
