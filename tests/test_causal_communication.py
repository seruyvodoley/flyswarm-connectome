"""Tests for directed causal communication; no MaleCNS model files required."""
import unittest
import numpy as np

from flyswarm.sensory import audio_frame
from flyswarm.research.causal_comm import CausalCommunication, DirectedEvent


class CausalCommunicationTests(unittest.TestCase):
    def setUp(self):
        self.song = np.arange(1, 17, dtype=float)
        self.positions = np.zeros((16, 3), dtype=float)
        self.alive = np.ones(16, dtype=bool)

    def test_identity_matches_existing_audio_frame(self):
        for mode in ("no_audio", "team_audio", "all_audio"):
            controller = CausalCommunication()
            expected_heard, expected_contributions, expected_distances = audio_frame(
                self.song, self.positions, self.alive, mode)
            heard, contributions, distances, info = controller.step(
                self.song, self.positions, self.alive, mode, 1)
            np.testing.assert_allclose(heard, expected_heard, rtol=0, atol=1e-12)
            np.testing.assert_allclose(contributions, expected_contributions, rtol=0, atol=1e-12)
            np.testing.assert_allclose(distances, expected_distances, rtol=0, atol=1e-12)
            self.assertEqual(info["interventions"], [])

    def test_one_directed_link_mute_changes_only_receiver_under_cap(self):
        original = CausalCommunication()
        changed = CausalCommunication({"events": [
            {"tick": 1, "sender": 0, "receiver": 1, "kind": "mute"}
        ]})
        small_song = self.song * .01  # No receiver saturation; mute must reduce total.
        neutral, neutral_links, _, _ = original.step(small_song, self.positions, self.alive, "team_audio", 1)
        actual, actual_links, _, report = changed.step(small_song, self.positions, self.alive, "team_audio", 1)
        self.assertEqual(actual_links[1, 0], 0.0)
        self.assertLess(actual[1], neutral[1])
        np.testing.assert_allclose(np.delete(actual, 1), np.delete(neutral, 1))
        self.assertEqual(len(report["interventions"]), 1)
        self.assertEqual(report["interventions"][0]["receiver"], 1)

    def test_cap_redistribution_is_recorded(self):
        high = np.ones(16, dtype=float) * 1000
        baseline = CausalCommunication()
        altered = CausalCommunication({"events":[{"tick":1,"sender":0,"receiver":1,"kind":"mute"}]})
        _, old_links, _, _ = baseline.step(high, self.positions, self.alive, "team_audio", 1)
        delivered, new_links, _, report = altered.step(high, self.positions, self.alive, "team_audio", 1)
        self.assertAlmostEqual(delivered[1], .8)
        self.assertGreater(new_links[1, 2], old_links[1, 2])
        self.assertEqual(report["saturation_receivers"], list(range(16)))

    def test_independent_team_receiver_communication(self):
        mixed = CausalCommunication({"enabled_teams":[True,False]})
        heard, links, _, _ = mixed.step(self.song, self.positions, self.alive, "team_audio", 1)
        self.assertGreater(np.sum(heard[:8]), 0)
        self.assertTrue(np.all(heard[8:] == 0))
        self.assertTrue(np.all(links[8:,:] == 0))

    def test_time_shift_uses_past_signals(self):
        delayed = CausalCommunication({"events":[
            {"tick":3,"sender":0,"receiver":1,"kind":"time_shift","lag_steps":1}
        ]})
        delayed.step(self.song, self.positions, self.alive, "team_audio", 1)
        delayed.step(self.song * 2, self.positions, self.alive, "team_audio", 2)
        _, links, _, frame = delayed.step(self.song * 3, self.positions, self.alive, "team_audio", 3)
        link = next(x for x in frame["links"] if x["sender"] == 0 and x["receiver"] == 1)
        self.assertAlmostEqual(links[1, 0], self.song[0] * .08 * link["cap_scale"])
        self.assertEqual(frame["interventions"][0]["effective_signal"], self.song[0])

    def test_bad_interventions_fail_closed(self):
        bad = [
            {"tick":1,"sender":0,"receiver":0,"kind":"mute"},
            {"tick":1,"sender":0,"receiver":1,"kind":"time_shift","lag_steps":0},
            {"tick":1,"sender":0,"receiver":1,"kind":"replace","value":-1},
            {"tick":1,"sender":0,"receiver":1,"kind":"shuffle_sender","substitute_sender":8},
        ]
        for event in bad:
            with self.subTest(event=event), self.assertRaises(ValueError):
                DirectedEvent.parse(event)
        with self.assertRaises(ValueError):
            CausalCommunication({"events":[
                {"tick":1,"sender":0,"receiver":1,"kind":"mute"},
                {"tick":1,"sender":0,"receiver":1,"kind":"mute"},
            ]})
        with self.assertRaises(ValueError):
            CausalCommunication({"events":[{"tick":1,"sender":0,"receiver":1,"kind":"mute"}]}).step(
                self.song,self.positions,self.alive,"no_audio",1)


if __name__ == "__main__":
    unittest.main()
