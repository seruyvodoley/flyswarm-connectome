# Experiment log

Статусы основаны на сохранённых исходниках и результатах; исторические
эксперименты при cleanup заново не запускались. Новые научные результаты
не заявляются. Карта файлов — `file_manifest.json`.

## Single-agent / Experiments 001–008

Сохранены lateral steering LC10a/DNa02, tracking, motor/DN screens,
LC9/DNp09 chase pathway, escape curve и escape ablation.
Experiments 003 (controls) и 008 (ablation) размещены в experiments/controls/.
CSV, summary и JSON конфигурация доступны через прежние results/ пути.

## FlyTank 0.2

Turret tracking: исходник experiments/flytank/flytank_02_turret.py и
per-step CSV сохранены. Численные итоги здесь не пересчитывались.

## FlyTank 0.3

Pursuit / forward locomotion: исходник и trajectory CSV сохранены.

## FlyTank 0.4

Chase/escape с looming encoder: исходник и CSV сохранены.
Causal escape ablation представлена отдельно Experiment 008.

## FlySwarm 0.1

Batch=8: исходник, точная WORKING-копия и per-agent/per-step CSV сохранены.

## FlySwarm 0.2

Physical 4v4 battle: исходник, точная WORKING-копия и CSV боя сохранены.

## FlySwarm 0.3

Learned fire: исходник, training dataset и readout NPZ сохранены.
Статус по контексту проекта — слабый/отрицательный результат; убедительное
преимущество обученного readout не установлено. Connectome не обучается.

## Experiment 010

010a: threshold config JSON и OOF predictions NPZ сохранены.
010b: AUTO / LEARNED / RANDOM, 10 seeds на режим в
results/summaries/experiment_010b_fire_controls.csv.
Среднее арифметическое per-battle accuracy: AUTO 0.436806,
LEARNED 0.488397, RANDOM 0.474341. Это описательные средние исходного CSV,
не проверка значимости и не доказательство преимущества learning.

## FlySwarm 0.4

Auditory communication: исходник и обе таблицы сохранены. По
results/summaries/flyswarm_04_audio_summary.csv средняя accuracy:
no_audio 0.476806; audio 0.536056. Mean duration: 15.7533 и 10.4767 секунд
соответственно. Эти агрегаты не устанавливают причинный биологический эффект;
per-seed метрики сохранены в flyswarm_04_audio_raw.csv.

## FlySwarm 0.5

Current; full experiment pending. Приложенный оригинал скопирован без изменений.
BLUE и RED — отдельные FlyBrain(device="cpu", batch=8), всего 16 агентов.
Условия no_audio / team_audio / all_audio, одинаковый AUTO-FIRE.

Синтаксис, pure-function tests и импорт сокращённой временной копии проверены.
Smoke: 0.2 simulated seconds на бой, calibration seed 200, test seeds 204/205,
25 warmup steps, 5 rest steps; настоящие независимые connectome objects.
Все режимы и запись raw/summary прошли проверку. Временные данные удалены
вместе с временным каталогом и не используются как исследовательский результат.
Полные параметры оригинала (45 секунд, 2 calibration и 6 test seeds) сохранены.


## 2026-09-16 — isolated 3D prototype

Historical scripts and results preserved byte-for-byte against file_manifest.json.
No full FlySwarm 0.5 run. Added Godot 4.7.2 scene with 16 vehicles, six original
blockout GLBs, finite-flight shells, module damage, objectives, replay, and a
localhost neural bridge. Two independent real CPU FlyBrain(batch=8) instances
retain 166,700 neurons each per batch member (2,667,200 across 16 agents).

18 Python tests and the Godot integration validation pass. Godot checks include
LOS occlusion, capture/ticket bleed, movement, casemate limits, module damage,
projectile spawning, pressure-surface ordering, differential belt direction,
repeated rut settlement and step-splitting invariance.

Bounded real-connectome pipeline: 1 second train seed 100, 800 imitation samples,
ridge fit/save/reload, 1 second frozen eval seed 200. Approximate reported final
neural ticks: 67.29 / 67.36 ms, eval simulation/wall factor 0.190. This is an
integration smoke, not evidence of learning quality. A separate 60-second
rule-based run fired 30 shots and ended with 8 vs 6 alive; no objective changed
owner in that run. Unit integration separately exercised zone capture.

After the cumulative-rut correction: 20.02 sim seconds / 20.281 wall seconds,
4.671 ms mean physics step in headless mode on this M2. Earlier rendered
23-second smoke showed about 59–60 FPS at the captured frame (not a sustained
minimum-FPS guarantee). Measured summaries are in results/summaries/3d/.

Historical visual acceptance explicitly FAIL / incomplete: reference dimensions
and exact production details are unverified. Seven neutral Blender views plus
three consistent Godot views per vehicle document the present blockouts. The
strict dimension gate rejects missing reference targets instead of approving
models against their own guessed input dimensions.
