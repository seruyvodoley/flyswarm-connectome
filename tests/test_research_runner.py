import unittest

from tools.research import fatal_godot_log_lines


class GodotLogClassificationTests(unittest.TestCase):
    def test_headless_dummy_shader_teardown_warning_is_nonfatal(self):
        log = """READY Krasny Valley 16 vehicles; NORMALIZED backend=true
SUMMARY {\"sim_s\":3.0}
ERROR: 1 RID allocations of type 'N13RendererDummy15MaterialStorage11DummyShaderE' were leaked at exit.
"""
        self.assertEqual(fatal_godot_log_lines(log), [])

    def test_simulation_errors_remain_fatal(self):
        log = """ERROR: Node not found: Vehicle
SCRIPT ERROR: Invalid call. Nonexistent function.
"""
        self.assertEqual(fatal_godot_log_lines(log), [
            "ERROR: Node not found: Vehicle",
            "SCRIPT ERROR: Invalid call. Nonexistent function.",
        ])

    def test_only_exact_dummy_renderer_teardown_message_is_ignored(self):
        log = "ERROR: 2 RID allocations of type 'N13RendererDummy15MaterialStorage11DummyShaderE' were leaked at exit.\n"
        self.assertEqual(fatal_godot_log_lines(log), [log.strip()])

    def test_unmapped_gamepad_diagnostic_is_ignored_but_other_input_errors_are_not(self):
        harmless = "ERROR: Error opening gamepad at index 3: Couldn't find mapping for device (3)"
        self.assertEqual(fatal_godot_log_lines(harmless + "\n"), [])
        unexpected = "ERROR: Error opening gamepad at index 4: Device failed to open"
        self.assertEqual(fatal_godot_log_lines(unexpected + "\n"), [unexpected])


if __name__ == "__main__":
    unittest.main()
