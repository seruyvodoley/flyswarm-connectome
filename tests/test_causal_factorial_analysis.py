from tools.analyze_causal_factorial import cumulative_presence_delta


def test_cumulative_presence_counts_only_increment_not_each_frame():
    first = {0: 0.0, 1: 1.0}
    last = {0: 2.0, 1: 4.5}

    assert cumulative_presence_delta(first, last) == 5.5


def test_cumulative_presence_ignores_negative_reset_and_missing_agents():
    first = {0: 3.0, 1: 2.0, 2: 0.0}
    last = {0: 1.0, 1: 2.75}

    assert cumulative_presence_delta(first, last) == 0.75
