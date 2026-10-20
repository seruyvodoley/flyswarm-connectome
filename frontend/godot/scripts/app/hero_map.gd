extends Control
## Lightweight vector battlefield illustration; avoids generating a large image pixel by pixel.

func _ready() -> void:
	custom_minimum_size = Vector2(420, 280)
	queue_redraw()

func _draw() -> void:
	var rect := Rect2(Vector2.ZERO, size)
	draw_rect(rect, Color("14232a"), true)
	var grid := Color(0.28, 0.49, 0.53, 0.24)
	for x in range(0, int(size.x), 36):
		draw_line(Vector2(x, 0), Vector2(x, size.y), grid, 1.0)
	for y in range(0, int(size.y), 36):
		draw_line(Vector2(0, y), Vector2(size.x, y), grid, 1.0)
	for contour in range(9):
		var points := PackedVector2Array()
		for step in range(81):
			var x := size.x * float(step) / 80.0
			var phase := float(contour) * 0.68
			var y := size.y * (0.18 + float(contour) * 0.085) + sin(x * 0.017 + phase) * 18.0 + cos(x * 0.009 - phase) * 11.0
			points.append(Vector2(x, y))
		draw_polyline(points, Color(0.30, 0.72, 0.70, 0.40 if contour % 2 == 0 else 0.22), 1.5, true)
	var route := PackedVector2Array([Vector2(size.x * 0.14, size.y * 0.76), Vector2(size.x * 0.33, size.y * 0.61), Vector2(size.x * 0.49, size.y * 0.66), Vector2(size.x * 0.71, size.y * 0.35), Vector2(size.x * 0.86, size.y * 0.28)])
	draw_polyline(route, Color("f2bd6d"), 2.5, true)
	for i in range(route.size()):
		var colour := Color("67d7ce") if i == 0 or i == route.size() - 1 else Color("f2bd6d")
		draw_circle(route[i], 5.0 if i == 0 or i == route.size() - 1 else 3.0, colour)
	draw_string(ThemeDB.fallback_font, Vector2(18, size.y - 18), "KRASNY VALLEY   /   FIELD MAP", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color("d7e5e2"))
