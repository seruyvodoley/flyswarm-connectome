extends SceneTree

var failures := 0

func _initialize() -> void:
	var bridge = load("res://scripts/bridge.gd").new()
	bridge.tick = 12
	var actions := []
	for _agent in 16:
		actions.append([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	var response := {"seq": 12, "actions": actions}
	_check(bridge._valid_reply(response), "accepts current response sequence")
	_check(not bridge._valid_reply({"seq": 11, "actions": actions}), "rejects stale response sequence")
	_check(not bridge._valid_reply({"seq": 12, "actions": actions.slice(0, 15)}), "rejects incomplete action batch")
	var invalid_actions := actions.duplicate(true)
	invalid_actions[8][0] = INF
	_check(not bridge._valid_reply({"seq": 12, "actions": invalid_actions}), "rejects non-finite motor values")
	bridge.last_reply_seq = 12
	_check(not bridge._valid_reply(response), "does not accept a duplicate neural response")
	print("BRIDGE PROTOCOL VALIDATION failures=", failures)
	quit(0 if failures == 0 else 1)

func _check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
