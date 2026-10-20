extends RefCounted
## Shared high-contrast interface styling for mouse, keyboard and controller use.

const INK := Color("151915")
const SURFACE := Color("202720")
const SURFACE_HOVER := Color("2b352b")
const SURFACE_PRESSED := Color("1b221c")
const BORDER := Color("465044")
const ACCENT := Color("a8b989")
const GOLD := Color("cda46a")
const TEXT := Color("f0eee4")
const MUTED := Color("c0c3b5")

static func is_light(appearance: String) -> bool:
	return appearance == "light"

static func ink_for(appearance: String) -> Color:
	return Color("f1f0e9") if is_light(appearance) else INK

static func surface_for(appearance: String) -> Color:
	return Color("ffffff") if is_light(appearance) else SURFACE

static func text_for(appearance: String) -> Color:
	return Color("202820") if is_light(appearance) else TEXT

static func muted_for(appearance: String) -> Color:
	return Color("626b60") if is_light(appearance) else MUTED

static func accent_for(appearance: String) -> Color:
	return Color("56724f") if is_light(appearance) else ACCENT

static func gold_for(appearance: String) -> Color:
	return Color("8c6035") if is_light(appearance) else GOLD

static func make_theme(font_size: int = 18, appearance: String = "dark") -> Theme:
	var light := is_light(appearance)
	var surface := surface_for(appearance)
	var text := text_for(appearance)
	var muted := muted_for(appearance)
	var accent := accent_for(appearance)
	var border := Color("c5c8bd") if light else BORDER
	var result := Theme.new()
	result.default_font_size = font_size
	for kind in ["normal", "hover", "pressed", "focus", "disabled"]:
		var style := StyleBoxFlat.new()
		style.bg_color = surface
		if kind == "hover": style.bg_color = Color("e4e9dc") if light else SURFACE_HOVER
		if kind == "pressed": style.bg_color = Color("dbe1d1") if light else SURFACE_PRESSED
		if kind == "disabled": style.bg_color = Color("e9e9e3") if light else Color("182127")
		style.border_color = accent if kind in ["hover", "focus"] else border
		style.set_border_width_all(1)
		if kind == "focus": style.set_border_width_all(2)
		style.set_corner_radius_all(10)
		style.content_margin_left = 18
		style.content_margin_right = 18
		style.content_margin_top = 12
		style.content_margin_bottom = 12
		result.set_stylebox(kind, "Button", style)
		result.set_stylebox(kind, "OptionButton", style)
		result.set_stylebox(kind, "CheckBox", style)
		result.set_stylebox(kind, "LineEdit", style)
		result.set_stylebox(kind, "TextEdit", style)
		result.set_stylebox(kind, "CodeEdit", style)
		result.set_stylebox(kind, "SpinBox", style)
	var readonly_style := StyleBoxFlat.new()
	readonly_style.bg_color = surface
	readonly_style.border_color = border
	readonly_style.set_border_width_all(1)
	readonly_style.set_corner_radius_all(6)
	result.set_stylebox("read_only", "TextEdit", readonly_style)
	result.set_stylebox("read_only", "CodeEdit", readonly_style)
	result.set_color("font_color", "Button", text)
	result.set_color("font_hover_color", "Button", text)
	result.set_color("font_pressed_color", "Button", accent)
	result.set_color("font_focus_color", "Button", text)
	result.set_color("font_disabled_color", "Button", muted)
	for type_name in ["Label", "LineEdit", "TextEdit", "CodeEdit", "OptionButton", "SpinBox", "CheckBox", "TabBar"]:
		result.set_color("font_color", type_name, text)
		result.set_color("font_selected_color", type_name, text)
		result.set_color("font_hover_color", type_name, text)
		result.set_color("font_pressed_color", type_name, accent)
		result.set_color("font_placeholder_color", type_name, muted)
	var tab_panel := StyleBoxFlat.new()
	tab_panel.bg_color = Color("f1f0e9") if light else INK
	result.set_stylebox("panel", "TabContainer", tab_panel)
	for state in ["selected", "unselected", "hovered", "focus"]:
		var tab_style := StyleBoxFlat.new()
		tab_style.bg_color = Color("ffffff") if light and state == "selected" else Color("e5e8df") if light else Color("202720") if state == "selected" else Color("1b211b")
		tab_style.border_color = accent if state in ["selected", "focus"] else border
		tab_style.set_border_width_all(1)
		tab_style.set_corner_radius_all(5)
		tab_style.content_margin_left = 14
		tab_style.content_margin_right = 14
		tab_style.content_margin_top = 5
		tab_style.content_margin_bottom = 5
		result.set_stylebox("tab_" + state, "TabBar", tab_style)
	result.set_color("font_selected_color", "TabBar", text)
	result.set_color("font_unselected_color", "TabBar", muted)
	result.set_color("font_hovered_color", "TabBar", text)
	var progress_bg := StyleBoxFlat.new()
	progress_bg.bg_color = Color("e1e4dc") if light else Color("26343d")
	progress_bg.set_corner_radius_all(6)
	var progress_fill := StyleBoxFlat.new()
	progress_fill.bg_color = accent
	progress_fill.set_corner_radius_all(6)
	result.set_stylebox("background", "ProgressBar", progress_bg)
	result.set_stylebox("fill", "ProgressBar", progress_fill)
	result.set_color("font_color", "ProgressBar", text)
	return result

static func panel_style(appearance: String = "dark") -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color("fbfaf6") if is_light(appearance) else Color("1b211b")
	style.border_color = Color("d5d7cd") if is_light(appearance) else BORDER
	style.set_border_width_all(1)
	style.set_corner_radius_all(14)
	style.content_margin_left = 22
	style.content_margin_right = 22
	style.content_margin_top = 20
	style.content_margin_bottom = 20
	return style

static func preview_frame_style(appearance: String = "dark") -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color("edf0ec") if is_light(appearance) else Color("303840")
	style.border_color = Color("9ba39e") if is_light(appearance) else Color("626d75")
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	style.content_margin_left = 8
	style.content_margin_right = 8
	style.content_margin_top = 6
	style.content_margin_bottom = 6
	return style

static func tab_style(appearance: String, selected: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color("ffffff") if is_light(appearance) and selected else Color("e5e8df") if is_light(appearance) else Color("2b352b") if selected else Color("202720")
	style.border_color = accent_for(appearance) if selected else (Color("c5c8bd") if is_light(appearance) else BORDER)
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	style.content_margin_left = 14
	style.content_margin_right = 14
	style.content_margin_top = 5
	style.content_margin_bottom = 5
	return style
