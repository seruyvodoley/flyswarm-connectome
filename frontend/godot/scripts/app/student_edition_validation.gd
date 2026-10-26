extends SceneTree

var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)

func run() -> void:
	var app = root.get_node_or_null("AppState")
	check(app != null, "AppState autoload is available")
	if app == null:
		quit(1)
		return
	check(app.STUDENT_EDITION, "Student edition build flag is enabled")
	check(ProjectSettings.get_setting("application/config/name") == "FlySwarm Student", "Student app name is configured")
	check(FileAccess.file_exists("res://assets/flyswarm-student-icon.icns"), "Silver macOS student icon is present")
	check(FileAccess.file_exists("res://assets/flyswarm-student-icon.png"), "Silver Windows student icon is present")

	app.show_page("MainMenu")
	await process_frame
	for node in app.view.find_children("*", "Button", true, false):
		var text := str(node.text).to_upper()
		check(not text.contains("OPEN DAY") and not text.contains("DEMO"), "Student main menu has no Open Day entry: " + text)
	for hidden_page in ["OpenDayMain", "HowItWorks", "DemoResult"]:
		app.show_page(hidden_page)
		await process_frame
		check(app.current_page == "MainMenu", "Student router blocks " + hidden_page)

	app.show_page("TrainingMenu")
	await process_frame
	for node in app.view.find_children("*", "Button", true, false):
		check(not str(node.text).to_upper().contains("OPEN DAY"), "Student training menu has no Open Day action")
	check(app.view.find_child("CombatCheckpoint", true, false) == null, "Student training menu hides the combat-opponent checkpoint controls")
	for node in app.view.find_children("*", "Label", true, false):
		check(str(node.text).to_upper() != "MALECNS COMBAT TRAINING", "Student training menu hides the Open Day opponent-training panel")
	app.session.mode = "combat_training"
	app.show_page("JobProgress")
	await process_frame
	check(app.current_page == "TrainingMenu", "Student Edition blocks a direct combat-training progress route")

	app.show_page("MarlLaboratory")
	await process_frame
	var marl_view = app.view
	marl_view.update_marl_status({
		"state": "complete", "phase": "process", "completed": 0, "total": 0,
		"message": "Starting the Python experiment worker…",
	}, "status-validation-output")
	await process_frame
	check(is_equal_approx(marl_view.status_progress.value, marl_view.status_progress.max_value), "Completed MARL status fills the progress bar even if the recorded target is zero")
	check(not marl_view.detail_label.text.contains("Запускаю процесс Python…") and not marl_view.detail_label.text.contains("Starting the Python experiment worker…"), "Completed MARL status does not retain stale startup text")
	check(marl_view.detail_label.text.contains("complete"), "Completed MARL status reports its final phase")
	print("STUDENT EDITION VALIDATION failures=", failures)
	quit(1 if failures else 0)
