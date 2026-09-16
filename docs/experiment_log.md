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
