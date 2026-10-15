extends RefCounted
## Open Day's controller bindings and analog shaping. This is deliberately
## separate from the input used by the research and historical battle modes.
const STICK_DEADZONE := 0.16
const TRIGGER_THRESHOLD := 0.56

const STICK_ACTIONS := [
	"od_move_left", "od_move_right", "od_move_forward", "od_move_reverse",
	"od_look_left", "od_look_right", "od_look_up", "od_look_down",
]
const ALL_ACTIONS := STICK_ACTIONS + [
	"od_fire", "od_zoom", "od_confirm", "od_back", "od_pause",
	"od_ui_up", "od_ui_down", "od_ui_left", "od_ui_right",
]

static func configure() -> void:
	for action in ALL_ACTIONS:
		if InputMap.has_action(action):
			InputMap.erase_action(action)
		InputMap.add_action(action, 0.0)
	_add_axis("od_move_left", JoyAxis.JOY_AXIS_LEFT_X, -1.0)
	_add_axis("od_move_right", JoyAxis.JOY_AXIS_LEFT_X, 1.0)
	_add_axis("od_move_forward", JoyAxis.JOY_AXIS_LEFT_Y, -1.0)
	_add_axis("od_move_reverse", JoyAxis.JOY_AXIS_LEFT_Y, 1.0)
	_add_axis("od_look_left", JoyAxis.JOY_AXIS_RIGHT_X, -1.0)
	_add_axis("od_look_right", JoyAxis.JOY_AXIS_RIGHT_X, 1.0)
	_add_axis("od_look_up", JoyAxis.JOY_AXIS_RIGHT_Y, -1.0)
	_add_axis("od_look_down", JoyAxis.JOY_AXIS_RIGHT_Y, 1.0)
	_add_axis("od_fire", JoyAxis.JOY_AXIS_TRIGGER_RIGHT, 1.0)
	_add_axis("od_zoom", JoyAxis.JOY_AXIS_TRIGGER_LEFT, 1.0)
	_add_button("od_confirm", JoyButton.JOY_BUTTON_A)
	_add_button("od_back", JoyButton.JOY_BUTTON_B)
	_add_button("od_pause", JoyButton.JOY_BUTTON_START)
	_add_ui_direction("od_ui_up", JoyButton.JOY_BUTTON_DPAD_UP, JoyAxis.JOY_AXIS_LEFT_Y, -1.0)
	_add_ui_direction("od_ui_down", JoyButton.JOY_BUTTON_DPAD_DOWN, JoyAxis.JOY_AXIS_LEFT_Y, 1.0)
	_add_ui_direction("od_ui_left", JoyButton.JOY_BUTTON_DPAD_LEFT, JoyAxis.JOY_AXIS_LEFT_X, -1.0)
	_add_ui_direction("od_ui_right", JoyButton.JOY_BUTTON_DPAD_RIGHT, JoyAxis.JOY_AXIS_LEFT_X, 1.0)
	for action in ["od_ui_up","od_ui_down","od_ui_left","od_ui_right"]:InputMap.action_set_deadzone(action,.22)

static func _add_axis(action: String, axis: int, direction: float) -> void:
	var event := InputEventJoypadMotion.new()
	event.axis = axis
	event.axis_value = direction
	InputMap.action_add_event(action, event)

static func _add_button(action: String, button: int) -> void:
	var event := InputEventJoypadButton.new()
	event.button_index = button
	InputMap.action_add_event(action, event)

static func _add_ui_direction(action: String, button: int, axis: int, direction: float) -> void:
	_add_button(action, button)
	_add_axis(action, axis, direction)

static func _shaped_axis(value: float, deadzone: float = STICK_DEADZONE) -> float:
	var magnitude := absf(value)
	if magnitude <= deadzone:
		return 0.0
	var normalized := clampf((magnitude - deadzone) / (1.0 - deadzone), 0.0, 1.0)
	return signf(value) * pow(normalized, 1.2)

static func shape_vector(value: Vector2, deadzone: float = STICK_DEADZONE) -> Vector2:
	var magnitude := value.length()
	if magnitude <= deadzone:
		return Vector2.ZERO
	var normalized := clampf((magnitude - deadzone) / (1.0 - deadzone), 0.0, 1.0)
	return value / magnitude * pow(normalized, 1.2)

static func drive_command(movement: Vector2, fire: bool) -> Array:
	# The DualSense reports the left-stick movement axes in the opposite
	# direction on the target macOS setup; normalize once at the input boundary.
	var shaped := shape_vector(-movement)
	return [-shaped.y, 0.0, shaped.x, 0.0, 0.0, 1.0 if fire else 0.0]

static func advance_camera(yaw: float, pitch: float, look: Vector2, delta: float, scoped: bool) -> Vector2:
	var sensitivity := 0.42 if scoped else 1.0
	var next_yaw := wrapf(yaw + _shaped_axis(look.x) * 1.8 * sensitivity * delta, -PI, PI)
	var next_pitch := clampf(pitch - _shaped_axis(look.y) * 1.35 * sensitivity * delta, deg_to_rad(-24.0), deg_to_rad(22.0))
	return Vector2(next_yaw, next_pitch)

static func camera_forward(yaw: float, pitch: float) -> Vector3:
	return Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch)).normalized()

static func normalize_trigger(raw_value: float, rest_value: float) -> float:
	var span := 1.0 - rest_value
	if span <= 0.05:
		return 0.0
	return clampf((raw_value - rest_value) / span, 0.0, 1.0)
