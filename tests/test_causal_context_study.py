from tools.causal_context_study import choose_events


def candidate(tick, sender, receiver, delta, activity):
    return {
        "tick": tick,
        "sender": sender,
        "receiver": receiver,
        "signal": float(max(1, tick // 40)),
        "mute_input_delta": delta,
        "recipient_pre_activity": activity,
        "donor_options": [
            {"donor": (sender + 1) % 8, "signal": 0.5,
             "delivered_delta": delta * 0.9},
            {"donor": (sender + 2) % 8, "signal": 2.0,
             "delivered_delta": -delta * 1.1},
        ],
    }


def test_event_selection_matches_preintervention_input_and_contrasts_state():
    rows = [
        candidate(40, 0, 1, 0.10, 4.0),
        candidate(45, 2, 3, 0.105, 80.0),
        candidate(50, 4, 5, 0.30, 40.0),
    ]

    selected = choose_events(rows)

    assert {(x["tick"], x["receiver"]) for x in selected} == {(40, 1), (45, 3)}
    assert abs(selected[0]["mute_input_delta"] - selected[1]["mute_input_delta"]) <= 0.02


def test_unmatched_fallback_uses_only_nonzero_baseline_channel_effects():
    rows = [
        candidate(40, 0, 1, 0.0, 10.0),
        candidate(45, 2, 3, 0.03, 20.0),
        candidate(50, 4, 5, 0.20, 30.0),
    ]

    selected = choose_events(rows)

    assert {x["tick"] for x in selected} == {45, 50}


def test_same_amplitude_shuffle_is_not_accepted_as_active_control():
    rows = [
        candidate(40, 0, 1, 0.08, 10.0),
        candidate(45, 2, 3, 0.08, 50.0),
        candidate(50, 4, 5, 0.08, 90.0),
    ]
    for row in rows:
        row["donor_options"] = [{"donor": 6, "signal": 1.0, "delivered_delta": 0.0}]

    assert choose_events(rows) == []
