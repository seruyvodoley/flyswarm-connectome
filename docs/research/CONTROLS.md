# Experimental controls

`MALECNS_REAL`: unmodified MaleCNS output decoded by the current biological baseline, with documented auxiliary layers.

`MALECNS_ABLATED`: same frozen network and decoder; default ablation zeros DNp09 L/R, DNa02 L/R, and DNp01 only for BLUE after raw traces are retained. The manifest records the exact channel set.

`MALECNS_SHUFFLED`: deterministic cyclic reassignment of six-channel outputs among BLUE agents at each step. The full per-team channel-value multiset is unchanged; the source-agent mapping is logged.

`NON_NEURAL_TRAINED` remains an unqualified required condition. The existing separately fitted ridge adapter has six proprioceptive and sixteen task-vector inputs and cannot load a checkpoint with a different schema. It distills the existing teacher action, so retain it only as a diagnostic imitation baseline; it does **not** satisfy the required independently trained, budget-matched, held-out comparison. The matched training/evaluation procedure and disjoint final-test checkpoint have not been implemented.

`RULE_BASED`: existing Godot teacher/Rule AI, retained as an engineering reference. It is not interchangeable with the non-neural trained adapter.
