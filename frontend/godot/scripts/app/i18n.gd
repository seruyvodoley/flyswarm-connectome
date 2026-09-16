extends RefCounted

const LANGUAGES = ["en", "ru"]

# Semantic strings that do not already exist as English UI source strings.
const EN = {
	"hud.header":
		"KRASNY VALLEY   /   FLYSWARM RESEARCH\n"
		+ "GERMANY  %03d  (%d alive)     USSR  %03d  (%d alive)\n"
		+ "A %s   B %s   C %s   |   %.1fs   %s   %s\n"
		+ "%s\n"
		+ "Brain tick %d  %.1fms   IPC %.1fms   FPS %d",

	"hud.detail":
		"%s  ·  %s  ·  %s%d / local brain %d\n"
		+ "Speed %.1f km/h    Gear %d    Ammo %d    Reload %.1fs\n"
		+ "Target %d   Range %.0fm   LOS %s   Gun %.1f°\n"
		+ "Wing song %.2f    JO %.3f    DN %s\n"
		+ "Camera: %s   |   TAB agent   |   C camera   |   T comms   |   F1 debug\n"
		+ "%s",

	"results.team":
		"%s · tickets %.1f · survivors %d · shots %d · penetrations %d · kills %d · capture contribution %.1f vehicle·s",

	"results.duration":
		"Duration: %.2f simulation seconds · %.2f wall seconds",

	"results.saved":
		"Results saved:\n%s",

	"job.progress":
		"%s\nCondition: %s · seed %s · run %s / %s\n"
		+ "Simulation: %.2fs · wall: %.1fs\n%s\nSaved: %s\nCheckpoint: %s",

	"camera.button": "Camera: %s",

	"comms.line":
		"%.2f  %s → %s   out %.2f · recv %.3f · %.0f m",
}

const RU = {
	"1500 m": "1500 м",
	"1000 m": "1000 м",
	"500 m": "500 м",
	"100 m": "100 м",
	"Tiger I · late 1944": "Tiger I · поздний 1944",
	"unknown": "неизвестно",
	"mixed_1944": "смешанный 1944",
	"adapter": "адаптер",
	"brain": "MaleCNS",
	"rule": "Rule AI",
	"range": "полигон",
	"research": "исследование",
	"training": "обучение",
	"replay": "повтор",
	"battle": "бой",
	"Worker exited unexpectedly; inspect the results folder.": "Задание неожиданно завершилось; проверьте папку результатов.",
	"Python .venv is missing. Configure dependencies before starting this job.": "Окружение Python .venv отсутствует. Установите зависимости перед запуском задания.",
	"The previous job is still stopping. Please retry shortly.": "Предыдущее задание ещё останавливается. Повторите немного позже.",
	"Backend error: ": "Ошибка бэкенда: ",
	". Rule AI and Test Range remain available.": ". Rule AI и полигон остаются доступны.",
	"Python environment is missing: ": "Не найдено окружение Python: ",
	"Backend exited. Check the Python environment and MaleCNS dataset.": "Бэкенд завершился. Проверьте Python и dataset MaleCNS.",
	"Warming up two independent brains": "Прогрев двух независимых нейросетей",
	"Loading RED MaleCNS · FlyBrain(batch=8)": "Загрузка красного FlyBrain(batch=8)",
	"Loading BLUE MaleCNS · FlyBrain(batch=8)": "Загрузка синего FlyBrain(batch=8)",
	"Connecting backend": "Подключение бэкенда",
	"Starting Python backend…": "Запуск бэкенда Python…",
	"Only the local managed backend is supported. Choose localhost in Settings.": "Поддерживается локальный бэкенд. Выберите localhost в настройках.",
	"Loading battlefield · spawning vehicles": "Загрузка поля боя · размещение техники",
	"error": "ошибка",
	"cancelled": "отменено",
	"complete": "завершено",
	"starting": "запуск",
	"not saved yet": "ещё не сохранён",
	"RED: select an existing .npz policy.": "Красные: выберите существующую политику .npz.",
	"BLUE: select an existing .npz policy.": "Синие: выберите существующую политику .npz.",
	"Replay file is missing.": "Файл повтора не найден.",
	"Training and validation seeds must differ.": "Seed обучения и проверки должны различаться.",
	"Duration must be positive.": "Длительность должна быть больше нуля.",
	"Readout policy": "Политика моторного адаптера",
	"Move this replay recording to Trash?": "Переместить запись повтора в Корзину?",
	"BATTLE COMPLETE": "БОЙ ЗАВЕРШЁН",
	"TARGET IMPACT: ": "ПОПАДАНИЕ В ЦЕЛЬ: ",
	"MANUAL · WASD drive · Q/E turret · R/F elevation · Space/LMB fire · ESC menu": "РУЧНОЙ · WASD ход · Q/E башня · R/F орудие · Пробел/ЛКМ огонь · ESC меню",
	# General application
	"F / S     FLYSWARM": "F / S     FLYSWARM",
	"CONNECTOME / EMBODIMENT": "КОННЕКТОМ / ВОПЛОЩЕНИЕ",
	"FLYSWARM": "FLYSWARM",
	"A world to observe. A network to study.": "Мир для наблюдения. Сеть для исследования.",

	"HISTORICAL BATTLE": "ИСТОРИЧЕСКИЙ БОЙ",
	"RESEARCH LABORATORY": "ИССЛЕДОВАТЕЛЬСКАЯ ЛАБОРАТОРИЯ",
	"TRAINING": "ОБУЧЕНИЕ",
	"TEST RANGE": "ПОЛИГОН",
	"REPLAYS": "ПОВТОРЫ",
	"SETTINGS": "НАСТРОЙКИ",
	"EXIT": "ВЫХОД",

	"SESSION PREPARATION": "ПОДГОТОВКА СЕССИИ",
	"Loading": "Загрузка",
	"Preparing simulation…": "Подготовка симуляции…",
	"Cancel": "Отмена",

	"LOCAL RESEARCH BUILD     /     Historical geometry and armour data remain under validation":
		"ЛОКАЛЬНАЯ ИССЛЕДОВАТЕЛЬСКАЯ СБОРКА     /     Геометрия и броня техники ещё проходят проверку",

	"KRASNY VALLEY  /  1944": "КРАСНАЯ ДОЛИНА  /  1944",

	"16 embodied agents · 6 vehicle families\nTwo independent MaleCNS instances: 2 × batch 8\n2,667,200 simulated neuron states\n\nRule AI and the manual test range work offline.":
		"16 воплощённых агентов · 6 семейств техники\n"
		+ "Два независимых MaleCNS: 2 × batch 8\n"
		+ "2 667 200 моделируемых нейронных состояний\n\n"
		+ "Rule AI и ручной полигон работают без нейробэкенда.",

	# Common buttons
	"Back": "Назад",
	"Browse": "Выбрать",
	"START": "ЗАПУСТИТЬ",
	"START BATTLE": "НАЧАТЬ БОЙ",
	"RUN EXPERIMENT": "ЗАПУСТИТЬ ЭКСПЕРИМЕНТ",
	"START TRAINING": "НАЧАТЬ ОБУЧЕНИЕ",
	"EVALUATE POLICY": "ОЦЕНИТЬ ПОЛИТИКУ",
	"PLAY": "ВОСПРОИЗВЕСТИ",
	"DELETE": "УДАЛИТЬ",
	"SAVE SETTINGS": "СОХРАНИТЬ НАСТРОЙКИ",
	"RESET DEFAULTS": "СБРОСИТЬ НАСТРОЙКИ",
	"RESUME": "ПРОДОЛЖИТЬ",
	"DEBUG VIEW": "ОТЛАДОЧНЫЙ РЕЖИМ",
	"SAVE REPLAY": "СОХРАНИТЬ ПОВТОР",
	"RETURN TO MAIN MENU": "В ГЛАВНОЕ МЕНЮ",
	"RETURN TO MENU": "В МЕНЮ",
	"EXIT APPLICATION": "ВЫЙТИ ИЗ ПРИЛОЖЕНИЯ",
	"VIEW REPLAY": "ПОСМОТРЕТЬ ПОВТОР",
	"RUN AGAIN": "ЗАПУСТИТЬ ЕЩЁ РАЗ",
	"CANCEL": "ОТМЕНА",
	"OPEN RESULTS FOLDER": "ОТКРЫТЬ ПАПКУ РЕЗУЛЬТАТОВ",
	"RETURN": "НАЗАД",
	"Retry": "Повторить",
	"Use Rule AI": "Использовать Rule AI",
	"RECONNECT": "ПЕРЕПОДКЛЮЧИТЬСЯ",

	# Main battle setup
	"Map": "Карта",
	"Krasny Valley": "Красная долина",
	"Physics": "Физика",
	"Historical · provisional data": "Историческая · предварительные данные",
	"Normalized research control": "Нормализованный исследовательский контроль",

	"BLUE controller": "Контроллер синих",
	"RED controller": "Контроллер красных",
	"BLUE policy": "Политика синих",
	"RED policy": "Политика красных",

	"Rule AI": "Rule AI",
	"MaleCNS": "MaleCNS",
	"Trained adapter": "Обученный адаптер",

	"Communication": "Коммуникация",
	"No Audio": "Без связи",
	"Team Audio": "Только внутри команды",
	"All Audio": "Связь между всеми",

	"Battle seed": "Seed боя",
	"Map seed": "Seed карты",
	"Duration (simulation seconds)": "Длительность (секунды симуляции)",
	"Side swap": "Поменять стороны",
	"Record replay": "Записывать повтор",

	"1944 MIXED BATTLE": "СМЕШАННЫЙ БОЙ 1944",
	"Historical Battle": "Исторический бой",

	"BLUE / GERMANY\n4 × Panther G\n2 × Tiger I\n2 × Jagdpanther":
		"СИНИЕ / ГЕРМАНИЯ\n4 × Panther G\n2 × Tiger I\n2 × Jagdpanther",

	"RED / USSR\n4 × T-34-85\n2 × IS-2 Model 1944\n2 × SU-100":
		"КРАСНЫЕ / СССР\n4 × T-34-85\n2 × IS-2 обр. 1944\n2 × SU-100",

	# Research
	"REPRODUCIBLE CONDITIONS": "ВОСПРОИЗВОДИМЫЕ УСЛОВИЯ",
	"Research Laboratory": "Исследовательская лаборатория",
	"Experiment": "Эксперимент",

	"Communication: none / team / all": "Коммуникация: нет / команда / все",
	"Historical vs normalized": "Историческая физика против нормализованной",
	"Same-vehicle mirror": "Зеркальный бой одинаковой техники",
	"Side-swap control": "Контроль со сменой сторон",
	"Vehicle-specific policy evaluation": "Оценка политики конкретной машины",
	"Zero-shot vehicle transfer": "Zero-shot перенос между машинами",
	"Trained vs baseline": "Обученная политика против baseline",

	"Runs measured conditions with independent seeds. Rule AI ignores neural communication; select MaleCNS for communication experiments. Transfer keeps the loaded readout unchanged.":
		"Запускает измеряемые условия на независимых seed. "
		+ "Rule AI не использует нейронную коммуникацию; для экспериментов связи выбери MaleCNS. "
		+ "При переносе загруженный readout не изменяется.",

	"Seed count": "Количество seed",
	"Vehicle preset": "Набор техники",
	"1944 mixed": "Смешанный 1944",
	"Source / mirror vehicle": "Исходная / зеркальная машина",
	"Transfer target": "Целевая машина переноса",
	"Render": "Рендер",
	"Headless · measured wall time": "Без графики · фактическое время",
	"Visual": "С графикой",

	# Training
	"READOUT ADAPTATION": "АДАПТАЦИЯ READOUT",
	"Training": "Обучение",

	"MaleCNS: FIXED / FROZEN · only the small motor readout is fitted. The available task uses teacher imitation; reward is not defined.":
		"MaleCNS: FIXED / FROZEN · обучается только небольшой моторный readout. "
		+ "Доступная задача использует подражание учителю; награда не определена.",

	"Vehicle": "Машина",
	"Task": "Задача",

	"Turret tracking · available": "Сопровождение башней · доступно",
	"Mobility familiarisation · unavailable": "Освоение движения · недоступно",
	"Waypoint navigation · unavailable": "Навигация по точкам · недоступно",
	"Slope traversal · unavailable": "Прохождение склонов · недоступно",
	"Stationary gunnery · unavailable": "Стрельба с места · недоступно",
	"Moving-target gunnery · unavailable": "Стрельба по движущейся цели · недоступно",
	"1v1 combat · unavailable": "Бой 1 на 1 · недоступно",
	"Capture objective · unavailable": "Захват точки · недоступно",

	"Other curriculum tasks have no training implementation yet and are disabled.":
		"Остальные этапы программы обучения пока не реализованы и отключены.",

	"Adapter": "Адаптер",
	"Vehicle-specific": "Для конкретной машины",
	"Shared policy": "Общая политика",
	"Episodes": "Эпизоды",
	"Training seed": "Seed обучения",
	"Validation seed": "Seed проверки",
	"Seconds per episode": "Секунд на эпизод",
	"Render during training": "Показывать рендер во время обучения",
	"Load policy": "Загрузить политику",
	"Select a frozen .npz readout": "Выбери замороженный .npz readout",

	# Test range
	"MANUAL VEHICLE CONTROL": "РУЧНОЕ УПРАВЛЕНИЕ ТЕХНИКОЙ",
	"Test Range": "Полигон",
	"Target vehicle": "Машина-цель",
	"Distance": "Дистанция",
	"Target angle": "Угол цели",
	"Mode": "Режим",

	"Free drive": "Свободная езда",
	"Mobility": "Ходовые испытания",
	"Gunnery": "Стрельба",
	"Armour": "Броня",
	"Module damage": "Повреждение модулей",

	"W/S drive · A/D steer · Q/E turret · R/F elevation · left mouse/Space fire\nRight mouse drag aims. C camera · F1 armour debug · ESC pause/menu. Target remains stationary.":
		"W/S — движение · A/D — поворот · Q/E — башня · R/F — вертикальная наводка · ЛКМ/Space — выстрел\n"
		+ "Зажатая ПКМ — наведение. C — камера · F1 — броня/отладка · ESC — пауза/меню. Цель остаётся неподвижной.",

	# Replays
	"RECORDED WORLD STATES": "ЗАПИСАННЫЕ СОСТОЯНИЯ МИРА",
	"Replays": "Повторы",

	"Playback uses recorded transforms and projectiles; no MaleCNS is loaded.":
		"Повтор воспроизводит записанные трансформы и снаряды; MaleCNS не загружается.",

	"No saved replays yet. Enable recording in a battle or use Save Replay in the pause menu.":
		"Сохранённых повторов пока нет. Включи запись боя или используй «Сохранить повтор» в меню паузы.",

	# Settings
	"LOCAL PREFERENCES": "ЛОКАЛЬНЫЕ НАСТРОЙКИ",
	"Settings": "Настройки",
	"Language": "Язык",
	"English": "Английский",

	"Graphics preset": "Качество графики",
	"Low": "Низкое",
	"Medium": "Среднее",
	"High": "Высокое",
	"Window resolution": "Разрешение окна",
	"Fullscreen": "Полный экран",
	"Shadows": "Тени",
	"Vegetation density": "Плотность растительности",
	"Sparse": "Редкая",
	"Balanced": "Сбалансированная",
	"Full": "Полная",
	"LOD bias": "Смещение LOD",
	"Performance": "Производительность",
	"Detail": "Детализация",
	"Effects quality": "Качество эффектов",
	"Debug overlays by default": "Отладочные оверлеи по умолчанию",
	"Brain server host": "Адрес brain server",
	"Brain server port": "Порт brain server",
	"Default communication": "Коммуникация по умолчанию",

	"The launcher manages localhost only. Audio communication is a neural signal; application sound playback is not implemented. LOD bias uses imported mesh LODs where present.":
		"Запуск управляет только localhost. Коммуникация здесь является нейронным сигналом; "
		+ "воспроизведение звука приложением не реализовано. LOD bias использует импортированные LOD мешей, где они есть.",

	# Pause/results
	"SESSION PAUSED": "СЕССИЯ НА ПАУЗЕ",
	"Pause": "Пауза",
	"MEASURED SESSION RESULTS": "РЕЗУЛЬТАТЫ СЕССИИ",
	"Session complete": "Сессия завершена",
	"DRAW": "НИЧЬЯ",
	"BLUE / GERMANY": "СИНИЕ / ГЕРМАНИЯ",
	"RED / USSR": "КРАСНЫЕ / СССР",

	"MEASURED EXPERIMENT": "ИЗМЕРЯЕМЫЙ ЭКСПЕРИМЕНТ",
	"Running session": "Сессия выполняется",
	"Starting worker…": "Запуск worker…",
	"Reward / rolling reward: N/A for ridge imitation. No scientific interpretation is generated.":
		"Reward / rolling reward: N/A для ridge imitation. Автоматическая научная интерпретация не выполняется.",

	# Backend
	"BACKEND": "БЭКЕНД",
	"NOT REQUIRED": "НЕ ТРЕБУЕТСЯ",
	"STARTING": "ЗАПУСК",
	"CONNECTING": "ПОДКЛЮЧЕНИЕ",
	"READY": "ГОТОВ",
	"BUSY": "ЗАНЯТ",
	"DISCONNECTED": "ОТКЛЮЧЁН",
	"ERROR": "ОШИБКА",

	"MaleCNS backend is unavailable.": "Бэкенд MaleCNS недоступен.",
	"BRAIN BACKEND DISCONNECTED": "СОЕДИНЕНИЕ С BRAIN BACKEND ПОТЕРЯНО",
	"Reconnect starts fresh neural state; the resumed episode is not scientifically continuous.":
		"При переподключении создаётся новое нейронное состояние; продолженный эпизод не является научно непрерывным.",

	"BRAIN BACKEND DISCONNECTED · RULE_BASED_CONTROL":
		"BRAIN BACKEND ОТКЛЮЧЁН · RULE_BASED_CONTROL",
	"BRAIN WAITING": "ОЖИДАНИЕ BRAIN BACKEND",

	# Roles/yes-no
	"medium": "средний",
	"heavy": "тяжёлый",
	"tank_destroyer": "САУ",
	"true": "да",
	"false": "нет",
	"yes": "да",
	"no": "нет",

	# Objectives
	"BLUE": "СИНИЕ",
	"RED": "КРАСНЫЕ",
	"NEUTRAL": "НЕЙТР.",
	"CONTESTED": "СПОРНАЯ",

	# Test Range killcam
	"TARGET DESTROYED": "ЦЕЛЬ УНИЧТОЖЕНА",
	"TARGET RESTORED": "ЦЕЛЬ ВОССТАНОВЛЕНА",
	"RESET TARGET": "ВОССТАНОВИТЬ ЦЕЛЬ",
	"Killcam": "Киллкам",
	"PENETRATION": "ПРОБИТИЕ",
	"RICOCHET": "РИКОШЕТ",
	"NO PENETRATION": "НЕ ПРОБИЛ",
	"Ammo rack detonation": "Поражение боеукладки",
	"Crew incapacitated": "Экипаж выведен из строя",
	"Critical internal damage": "Критические внутренние повреждения",
	"Shell": "Снаряд",
	"Hit zone": "Зона попадания",
	"Impact distance": "Дистанция попадания",
	"Damaged modules": "Повреждённые модули",
	"Destruction reason": "Причина уничтожения",
	"Press C to skip killcam": "C — пропустить киллкам",
	"Press Enter to reset target": "Enter — восстановить цель",
	"none": "нет",
	"To destroy the target: destroy its ammo rack, or disable driver + gunner + commander. Every hit shows penetration feedback. A kill starts Killcam; Enter restores the target.":
		"Чтобы уничтожить цель: поразите боеукладку либо выведите из строя водителя + наводчика + командира. После каждого попадания показывается результат. После уничтожения запускается киллкам; Enter восстанавливает цель.",

	# Cameras
	"Battlefield": "Поле боя",
	"Third-person": "От третьего лица",
	"Gunner": "Прицел",
	"Free camera": "Свободная камера",

	# Communication monitor
	"Comms: Off": "Связь: выкл.",
	"Comms: Red": "Связь: красные",
	"Comms: Blue": "Связь: синие",
	"Comms: All": "Связь: все",

	"Team Communication · Red": "Связь команды · красные",
	"Team Communication · Blue": "Связь команды · синие",
	"Team Communication · All": "Связь команд · все",

	"Communication channel disabled": "Канал связи отключён",
	"No neural communication telemetry in Rule AI mode.":
		"В режиме Rule AI нейронная телеметрия связи отсутствует.",
	"No signal above threshold yet.": "Сигналов выше порога пока нет.",

	"Interface shows physical/neural signal telemetry, not decoded language.":
		"Интерфейс показывает физический/нейронный сигнал, а не расшифрованную речь.",

	# Semantic format strings
	"hud.header":
		"КРАСНАЯ ДОЛИНА   /   ИССЛЕДОВАНИЕ FLYSWARM\n"
		+ "ГЕРМАНИЯ  %03d  (%d в строю)     СССР  %03d  (%d в строю)\n"
		+ "A %s   B %s   C %s   |   %.1fс   %s   %s\n"
		+ "%s\n"
		+ "Brain tick %d  %.1fмс   IPC %.1fмс   FPS %d",

	"hud.detail":
		"%s  ·  %s  ·  %s%d / локальный brain %d\n"
		+ "Скорость %.1f км/ч    Передача %d    БК %d    Перезарядка %.1fс\n"
		+ "Цель %d   Дальность %.0fм   LOS %s   Орудие %.1f°\n"
		+ "Wing song %.2f    JO %.3f    DN %s\n"
		+ "Камера: %s   |   TAB агент   |   C камера   |   T связь   |   F1 отладка\n"
		+ "%s",

	"results.team":
		"%s · tickets %.1f · в строю %d · выстрелы %d · пробития %d · уничтожено %d · вклад в захват %.1f маш·с",

	"results.duration":
		"Длительность: %.2f секунд симуляции · %.2f секунд реального времени",

	"results.saved":
		"Результаты сохранены:\n%s",

	"job.progress":
		"%s\nУсловие: %s · seed %s · запуск %s / %s\n"
		+ "Симуляция: %.2fс · wall: %.1fс\n%s\nСохранено: %s\nCheckpoint: %s",

	"camera.button": "Камера: %s",

	"comms.line":
		"%.2f  %s → %s   исх. %.2f · принято %.3f · %.0f м",
}

static func t(key: String, language: String) -> String:
	var english = str(EN.get(key, key))
	if language == "ru":
		return str(RU.get(key, RU.get(english, english)))
	return english

static func format(key: String, language: String, args: Array) -> String:
	return t(key, language) % args

static func next_language_label(language: String) -> String:
	return "ENGLISH" if language == "ru" else "РУССКИЙ"
