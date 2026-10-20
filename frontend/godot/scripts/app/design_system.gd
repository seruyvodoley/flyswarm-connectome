extends RefCounted
## Shared high-contrast interface styling for mouse, keyboard and controller use.

const INK := Color("101820")
const SURFACE := Color("1a2731")
const SURFACE_HOVER := Color("243845")
const SURFACE_PRESSED := Color("14232b")
const BORDER := Color("3c5260")
const ACCENT := Color("67d7ce")
const GOLD := Color("f2bd6d")
const TEXT := Color("f2f5f3")
const MUTED := Color("b4c2c6")

static func make_theme(font_size: int = 18) -> Theme:
	var result := Theme.new()
	result.default_font_size = font_size
	for kind in ["normal", "hover", "pressed", "focus", "disabled"]:
		var style := StyleBoxFlat.new()
		style.bg_color = SURFACE
		if kind == "hover": style.bg_color = SURFACE_HOVER
		if kind == "pressed": style.bg_color = SURFACE_PRESSED
		if kind == "disabled": style.bg_color = Color("182127")
		style.border_color = ACCENT if kind in ["hover", "focus"] else BORDER
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
	result.set_color("font_color", "Button", TEXT)
	result.set_color("font_hover_color", "Button", TEXT)
	result.set_color("font_pressed_color", "Button", ACCENT)
	result.set_color("font_focus_color", "Button", TEXT)
	result.set_color("font_disabled_color", "Button", MUTED)
	var progress_bg := StyleBoxFlat.new()
	progress_bg.bg_color = Color("26343d")
	progress_bg.set_corner_radius_all(6)
	var progress_fill := StyleBoxFlat.new()
	progress_fill.bg_color = ACCENT
	progress_fill.set_corner_radius_all(6)
	result.set_stylebox("background", "ProgressBar", progress_bg)
	result.set_stylebox("fill", "ProgressBar", progress_fill)
	result.set_color("font_color", "ProgressBar", TEXT)
	return result

static func panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color("17242c")
	style.border_color = BORDER
	style.set_border_width_all(1)
	style.set_corner_radius_all(14)
	style.content_margin_left = 22
	style.content_margin_right = 22
	style.content_margin_top = 20
	style.content_margin_bottom = 20
	return style
