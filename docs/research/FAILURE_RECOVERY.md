# Interruption and recovery contract

Each run has an exclusive UUID-suffixed directory. Run JSONL is streamed, and only a run with a complete `summary.json`, all expected 20 ms simulation steps, valid neural/game synchronization, valid combat-event lifecycle, and a clean Godot exit is eligible for analysis. A crash-truncated final JSONL line is invalid, not repaired. Only completed condition/seed/side runs are reused on resume; incomplete directories remain as diagnostics and receive new run IDs if repeated.

Resume only with the exact original config and unchanged source fingerprint:

```sh
tools/run-research resume --config <same-config.json> --run results/research/<interrupted-experiment-id>
```

Completed and checksummed experiment archives are immutable. If code, assets, scenario, or config changes, the runner refuses resume; start a new experiment directory and preserve the old one. Never combine partial runs from different source fingerprints. Stop/resume and backend crash/disconnect tests against a real interrupted collection are still required before readiness. The earlier mixed-source 30-second attempt remains archived as an invalid interrupted diagnostic and must not be resumed.

The refusal path was verified against `experiment-20261018T153518Z-5d8bae10`: using its saved original config after the source changed returned `Source code/assets changed since this experiment began`, and hashes of its manifest and progress file were unchanged. This confirms fail-closed protection against mixing sources; it does **not** verify successful resume or backend crash/disconnect recovery. A controlled combat harness is now part of `tools/run run-tests`; it does not exercise interruption behavior.

`tools/run-research validate --run <run-or-experiment>` checks run status, neural/game step IDs, combat events, and archive checksums. To test checksum corruption, use a disposable copied fixture rather than changing a real pilot. Missing MaleCNS data must fail the backend preflight; no automatic fallback controller is permitted.
