# FlyTank / FlySwarm

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
src/flyswarm/              каркас будущего общего пакета
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
pythontools/smoke_flyswarm05.py
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
