# Application delivery — 2026-09-17

1. Reused working subsystems: deterministic Godot battle, ballistics, armour and
   modules, objectives, replay stream, pressure/slip track marks, two independent
   CPU FlyBrain instances with eight environments each, ridge motor adapter.
2. Previous application infrastructure: command-line direct battle entry only;
   no complete menu/setup/results lifecycle. Audit: application_audit.md.
3. Added Bootstrap, persistent settings/AppState/SessionConfig, eleven UI pages,
   process supervision, backend recovery, run.sh and local macOS export preset.
4. Working flows: main menu, battle setup/loading/results, pause/resume/menu,
   manual range, replay browsing/playback, settings, research jobs and cancellation,
   supported training collection/fit/save/reload/held-out evaluation.
5. Partial/disabled: unsupported training tasks disabled; rewards N/A for ridge
   imitation; no claim of reinforcement learning. Sound playback not implemented.
   Export preset prepared; self-contained signed macOS application not built.
6. Backend: launched only for neural controllers, progress reports real stages,
   two objects load locally, missing dependencies expose retry/rule/menu options.
   Workers own and reap children; parent monitoring and cancellation are implemented.
7. Actual neural smoke: 2 × 8 × 166700 = 2,667,200 neuron states, CPU, independent
   objects. Application test completed a real neural battle and stopped backend.
8. All six GLBs updated. Tiger dedicated source: 224036 triangles; Panther 16776,
   Jagdpanther 17292, IS-2 14796, T-34-85 13208, SU-100 13644. Other five are
   accelerated intermediate recognition geometry, not finished historical models.
9. Historical acceptance: NOT PASSED. Reference gaps, provisional dimensions,
   Tiger budget/LOD work and variant details are recorded in model_validation/pass_02.md.
   Seven Blender views/model and three actual Godot views/model regenerated.
10. Checks: 18 Python tests and Godot physics validation passed; application UI
    integration failures=0; real neural application check passed. Three audio
    conditions verified with real backend. Tiny training run saved/reloaded an
    adapter and evaluated on a distinct seed. Cancellation check reaped children.
    All 47 historical manifest SHA256 values unchanged. No full FlySwarm0.5 run.
11. Launch: ./run.sh from repository root. New assets appear in a newly started
    scene; an already open battle retains its previously loaded meshes.
12. Limitations: performance of sixteen high-detail Tigers not benchmarked;
    current terrain marks approximate pressure/slip and do not deform colliders;
    fixed neural connectome is not trained. Dataset, raw job outputs, local
    reference images, virtual environment, caches and macOS sidecars stay ignored.

Repeatable checks: tools/run run-tests; ./run.sh --headless --script
res://scripts/app/validation.gd (add -- --real-brains for local real data);
.venv/bin/python tools/application_cancel_smoke.py.
