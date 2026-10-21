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
	print("STUDENT EDITION VALIDATION failures=", failures)
	quit(1 if failures else 0)
