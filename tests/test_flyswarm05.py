"""Test actual pure functions via AST, without executing top-level simulation."""
import ast
import math
from pathlib import Path
import types
import unittest
import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / 'experiments/swarm/flyswarm_05_two_brains_8v8.py'
FUNCTIONS = {'clamp', 'wrap_angle', 'bearing', 'distance', 'attenuation',
             'segment_circle_t', 'raw_heard_signal'}
tree = ast.parse(SOURCE.read_text())
selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS]
assert {n.name for n in selected} == FUNCTIONS
constants = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        if node.targets[0].id in {'AUDIO_DISTANCE_SCALE', 'N_TEAM', 'N_TOTAL'}:
            constants[node.targets[0].id] = ast.literal_eval(node.value)
namespace = {'math': math, 'np': np, **constants}
namespace['TEAMS'] = np.repeat([0, 1], constants['N_TEAM'])
exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), 'exec'), namespace)
m = types.SimpleNamespace(**namespace)


class GeometryTests(unittest.TestCase):
    def test_wrap_boundaries(self):
        for value, expected in [(0, 0), (180, 180), (-180, -180), (181, -179),
                                (-181, 179), (1081, 1), (-1081, -1)]:
            with self.subTest(value=value):
                self.assertEqual(m.wrap_angle(value), expected)

    def test_distance(self):
        self.assertEqual(m.distance(1, 2, 4, 6), 5)
        self.assertEqual(m.distance(4, 6, 1, 2), 5)
        self.assertEqual(m.distance(2, 2, 2, 2), 0)

    def test_attenuation(self):
        self.assertEqual(m.attenuation(0), 1)
        self.assertEqual(m.attenuation(m.AUDIO_DISTANCE_SCALE), 0.5)
        self.assertGreater(m.attenuation(100), m.attenuation(200))
        self.assertGreater(m.attenuation(10000), 0)

    def test_segment_crossing_and_tangent(self):
        # Legacy t is the closest-point projection, NOT the entry intersection.
        self.assertEqual(m.segment_circle_t(0, 0, 10, 0, 5, 0, 1), 0.5)
        self.assertEqual(m.segment_circle_t(0, 0, 10, 0, 5, 1, 1), 0.5)

    def test_segment_miss_and_endpoints(self):
        self.assertIsNone(m.segment_circle_t(0, 0, 10, 0, 5, 2, 1))
        self.assertIsNone(m.segment_circle_t(0, 0, 10, 0, 12, 0, 1))
        self.assertEqual(m.segment_circle_t(0, 0, 10, 0, 11, 0, 1), 1)
        self.assertEqual(m.segment_circle_t(0, 0, 10, 0, -1, 0, 1), 0)

    def test_zero_length_segment_legacy_behavior(self):
        self.assertIsNone(m.segment_circle_t(0, 0, 0, 0, 0, 0, 1))


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.sound = np.ones(m.N_TOTAL)
        self.xy = np.zeros(m.N_TOTAL)
        self.alive = np.ones(m.N_TOTAL, dtype=bool)

    def heard(self, mode):
        return m.raw_heard_signal(self.sound, self.xy, self.xy, self.alive, mode)

    def test_no_audio(self):
        np.testing.assert_array_equal(self.heard('no_audio'), np.zeros(m.N_TOTAL))

    def test_team_audio_excludes_self_and_enemies(self):
        np.testing.assert_array_equal(self.heard('team_audio'), np.full(m.N_TOTAL, 7))

    def test_all_audio_excludes_self(self):
        np.testing.assert_array_equal(self.heard('all_audio'), np.full(m.N_TOTAL, 15))

    def test_dead_sender_and_receiver(self):
        self.alive[0] = False
        heard = self.heard('team_audio')
        self.assertEqual(heard[0], 0)
        np.testing.assert_array_equal(heard[1:8], np.full(7, 6))
        np.testing.assert_array_equal(heard[8:], np.full(8, 7))


if __name__ == '__main__':
    unittest.main()
