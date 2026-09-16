# FlyTank / FlySwarm

## Запуск приложения

```sh
./run.sh
```

Открывается главное меню Godot: бой, Research Lab, обучение, ручной полигон,
повторы и настройки. Для MaleCNS используется локальная `.venv` и отдельно
установленный dataset; Rule-based режим работает без нейробэкенда.
[Потоки приложения](docs/application.md), [аудит](docs/application_audit.md),
[состояние моделей](docs/model_validation/pass_02.md),
[упаковка macOS](docs/macos_packaging.md).

Модели улучшены, но полная историческая валидация всех шести **не пройдена**.


Исследовательский Python-проект: реконструированный connectome центральной
нервной системы Drosophila MaleCNS используется как контроллер embodied agents
в танковой симуляционной среде. Это эксперимент с фиксированной сетью связей,
а не утверждение о настоящем интеллекте мухи или эмуляции сознания.

```text
sensory encoder
    ↓
fixed MaleCNS connectome
    ↓
descending neurons
    ↓
motor decoder
    ↓
tank/world
```

Исследуемые каналы управления:

```text
LC10a → DNa02 → lateral steering / turret control
LC9 → DNp09 → pursuit / forward locomotion
LC4/LPLC2 → escape-related descending activity
wing MN → JO-A/JO-B → inter-agent auditory signalling
```

Последний канал реализован через передачу сигнала в симуляционной среде.
Наличие эффекта в модели не доказывает биологическую функцию коммуникации.

Этапы: single-agent tracking, pursuit, chase/escape, causal ablation,
8-agent FlySwarm, physical 4v4 battle, learned-fire (слабый/отрицательный
результат по описанию проекта; превосходство не установлено), auditory
communication и текущая архитектура two-brain 8v8.
Состояние файлов и наблюдения записаны в [журнале](docs/experiment_log.md).

Ограничения: MaleCNS wiring фиксирован. Большая часть learning experiments
обучает readout, а не connectome. Visual encoder использует признаки,
а не raw retina. Базовая стрельба rule-based. Friend/foe и выбор цели
частично задаются environment layer. Эти допущения нужно учитывать при
интерпретации нейронных и поведенческих результатов.

Структура:

```text
src/flyswarm/              3D neural backend и исторический Python-проект
experiments/single_agent/  нейронные экраны, tracking, pursuit/escape pathways
experiments/flytank/       FlyTank 0.2–0.4
experiments/swarm/         FlySwarm 0.1–0.5
experiments/controls/      Experiments 003, 008, 010a/010b
archive/prototypes/       три исторические версии *_WORKING.py
results/raw/              локальные подробные записи, исключены из Git
results/summaries/        компактные метрики и конфигурации
results/models/           сохранённые NPZ datasets/readouts/predictions
results/figures/           графики
tests/                   быстрые тесты без загрузки MaleCNS
tools/                   ограниченный smoke test
docs/                    журнал, аудит, карта перемещений с SHA-256
```

Подготовка (проверенное окружение: macOS Apple Silicon, Python 3.11.16):

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

MaleCNS data настраиваются отдельно согласно установленному `flybrain`.
В проверенном окружении `flybrain 0.1.0` использует `~/fly-data` или `FLY_DATA`;
данные расположены вне репозитория. Проверьте их через `python -m flybrain info`.
Connectome dataset не включён в Git.

Запускайте скрипты **из корня репозитория**:

```bash
python experiments/swarm/flyswarm_05_two_brains_8v8.py
```

Это полный, потенциально длительный эксперимент. BLUE и RED имеют **два
отдельных `FlyBrain(device="cpu", batch=8)`**, всего 16 агентов. Условия:
`no_audio`, `team_audio`, `all_audio`; AUTO-FIRE одинаков во всех условиях.
Исходные параметры: 45 секунд симуляции на бой, calibration seeds 200/201,
test seeds 204–209. Скрипт сохранён без изменений, включая запуск при импорте.
Не импортируйте его для получения вспомогательных функций.

0.5 пишет `results/flyswarm_05_two_brains_8v8_raw.csv` (одна строка на бой,
не per-step trace) и `results/flyswarm_05_two_brains_8v8_summary.csv`.
Обычный запуск перезаписывает одноимённые результаты; сохраняйте нужные
снимки перед повторением. Исторические пути остальных результатов сохранены
относительными symlink; правила описаны в [results/README.md](results/README.md).

Проверки:

```bash
python -m compileall -x '/\._' experiments src archive
python -m unittest discover -s tests -v
# Необязательно: pip install -r requirements-dev.txt
# python -m pytest -q
python tools/smoke_flyswarm05.py
```

На внешнем macOS-диске исключение `/\._` пропускает служебные AppleDouble
файлы, не являющиеся Python-исходниками.

Unit tests проверяют исходные pure functions через AST без исполнения тела
эксперимента и без загрузки мозга. Smoke test отдельно импортирует временную
копию с настоящими двумя мозгами: 0.2 секунды на бой, один calibration seed,
два test seeds, все три режима, 180 секунд wall timeout. Результаты временные;
они не являются научными результатами и не оценивают качество боя.

Phase 2 refactor: extract common world/combat/audio/perception code into
`src/flyswarm/`. Добавить безопасный `main()`/CLI, явные каталоги результатов,
конфигурации и метаданные воспроизводимости. Отдельно проверить физический
смысл `segment_circle_t`: сейчас возвращается проекция ближайшей точки,
а не первое пересечение с окружностью. Сохранить исторические baseline и
архитектуру двух независимых мозгов при дальнейших изменениях.


## 3D research prototype (Godot + Python)

Новая 3D-среда находится в `frontend/godot`; исторические 2D-эксперименты
сохранены без изменений. Это рабочий прототип, **не завершённый исторический
симулятор**: все шесть GLB пока являются blockout-моделями и не прошли
проверку визуальной достоверности. Таблицы брони/боеприпасов приближённые.

Проверено: Godot 4.7.2, Blender 5.0.1, macOS M2 8 GB, Python 3.11.
`tools/run` использует `.venv/bin/python` и Godot из PATH или Applications.
Другие пути можно задать переменными `PYTHON` и `GODOT`.

```bash
# Самостоятельный 3D-бой с явно обозначенным rule-based контроллером
./tools/run run-demo
# Ограниченный запуск и запись в новый локальный каталог
./tools/run headless --seconds 30 --quit --record /tmp/flyswarm-demo-new
# Python + Godot проверки без загрузки MaleCNS
./tools/run run-tests
# Настоящие два FlyBrain(batch=8): запустить в двух терминалах
./tools/run run-brains
./tools/run run-battle --seconds 5 --quit
# Короткий train → save → reload → frozen eval с реальным connectome
./tools/run run-training --seconds 1
# Чтение записанного replay
./tools/run run-demo --replay /tmp/flyswarm-demo-new/replay.jsonl
```

TAB выбирает агента, C переключает четыре камеры, F1 показывает сенсоры,
SPACE ставит на паузу. В свободной камере WASD / Q / E / стрелки.
Без Python HUD сообщает `BRAIN BACKEND DISCONNECTED · RULE_BASED_CONTROL`.
При `--connect` отказ backend останавливает интеграцию; скрытой подмены мозга нет.

Карты: Krasny Valley 1.5 км, отдельный `--training` стенд. Флаги
`--normalized`, `--swap`, `--mirror`, `--audio no_audio|team_audio|all_audio`
задают сравнительные условия. Пример readout в `results/models/3d/shared`
обучен только на 800 smoke samples и не предназначен для оценки качества боя.

Документация: [архитектура](docs/simulator_architecture.md),
[физика и следы](docs/vehicle_physics.md), [броня](docs/armour_and_ballistics.md),
[нейронный интерфейс](docs/brain_vehicle_interface.md), [обучение](docs/training.md),
[известные ограничения](docs/known_approximations.md),
[проверка моделей](docs/vehicle_visual_references.md).
