import numpy as np

import tools.analyze_causal_final_action as final_action
from tools.analyze_causal_final_action import backend_action, objective_action


def test_backend_aux_matches_teacher_command_rules():
    decoder = [0.2, 0.0, -0.4, 0.1, 0.0, 0.0]
    visible = {"alive": True, "visible": True, "elevation": 0.001, "bearing": 0.01}
    result = backend_action(decoder, visible)
    assert np.allclose(result, [0.2, 0.0, -0.4, 0.1, 0.006, 1.0])

    hidden = {"alive": True, "visible": False, "elevation": 0.0, "bearing": 0.0}
    assert backend_action([0.0] * 6, hidden)[0] == 0.18


def test_objective_aux_applies_same_state_and_obstacle_override():
    agent = {"agent_id": 2, "team": "blue", "position": [0.0, 0.0, -200.0],
             "hull_yaw_rad": 0.0, "visible": False, "alive": True}
    zones = [{"owner": -1, "contested": False, "position": [0.0, 0.0, 0.0]}]
    base = objective_action([0.0] * 6, agent, zones)
    assert base[0] == 0.82
    assert base[2] == 0.0
    blocked = objective_action([0.0] * 6, agent, zones, ray_blocked=True)
    assert blocked[0] == -0.15
    assert blocked[2] == 1.0


def test_final_action_figure_accepts_csv_numeric_strings(tmp_path, monkeypatch):
    monkeypatch.setattr(final_action, "OUT", tmp_path)
    (tmp_path / "intervention_event_metrics.csv").write_text(
        "seed,horizon_ms,decoder_l2_mute,decoder_l2_control\n"
        "93011,1000,0.2,0.1\n", encoding="utf-8")
    rows = [
        {"seed": 93011, "horizon_ms": 1000, "final_action_l2_mute": 0.3,
         "final_action_l2_control": 0.15}
    ]

    final_action.make_final_action_figure(rows)

    assert (tmp_path / "figures" / "fig4_final_action_control.png").is_file()
