extends Control
## Compact, visual Open Day health and match clock display.

var player_health := 1.0
var fly_health := 1.0
var remaining_seconds := 120.0

func set_state(player_value: float, fly_value: float, seconds_left: float) -> void:
	player_health = clampf(player_value, 0.0, 1.0)
	fly_health = clampf(fly_value, 0.0, 1.0)
	remaining_seconds = maxf(0.0, seconds_left)
	queue_redraw()

func _draw() -> void:
	var card := StyleBoxFlat.new()
	card.bg_color = Color(0.035, 0.055, 0.052, 0.88)
	card.border_color = Color(0.73, 0.66, 0.48, 0.82)
	card.set_border_width_all(1)
	card.set_corner_radius_all(12)
	draw_style_box(card, Rect2(Vector2.ZERO, size))
	var font := ThemeDB.fallback_font
	var title_color := Color("f0ead8")
	var muted := Color("b9c2b7")
	var russian := str(AppState.settings.language) == "ru"
	var row_width := size.x - 28.0
	var clock := "%02d:%02d" % [int(int(remaining_seconds) / 60), int(remaining_seconds) % 60]
	draw_string(font, Vector2(14, 21), "ВЫ" if russian else "YOU", HORIZONTAL_ALIGNMENT_LEFT, row_width - 64.0, 12, title_color)
	draw_string(font, Vector2(size.x - 64, 21), clock, HORIZONTAL_ALIGNMENT_RIGHT, 50, 12, Color("ead58f"))
	draw_string(font, Vector2(14, 43), "%d%%" % roundi(player_health * 100.0), HORIZONTAL_ALIGNMENT_RIGHT, row_width, 10, muted)
	_draw_health_bar(Vector2(14, 49), row_width, player_health, Color("84b9a0"))
	draw_string(font, Vector2(14, 72), "МУХА" if russian else "FLY", HORIZONTAL_ALIGNMENT_LEFT, row_width, 12, title_color)
	draw_string(font, Vector2(14, 91), "%d%%" % roundi(fly_health * 100.0), HORIZONTAL_ALIGNMENT_RIGHT, row_width, 10, muted)
	_draw_health_bar(Vector2(14, 97), row_width, fly_health, Color("e79a62"))
	draw_string(font, Vector2(14, 121), "MATCH" if not russian else "БОЙ", HORIZONTAL_ALIGNMENT_LEFT, row_width, 10, muted)
	_draw_health_bar(Vector2(14, 126), row_width, 1.0 - clampf(remaining_seconds / 120.0, 0.0, 1.0), Color("67d7ce"))

func _draw_health_bar(position: Vector2, width: float, value: float, colour: Color) -> void:
	draw_rect(Rect2(position, Vector2(width, 8)), Color(0.12, 0.16, 0.15, 0.95), true)
	if value > 0.0:
		draw_rect(Rect2(position, Vector2(width * value, 8)), colour, true)
