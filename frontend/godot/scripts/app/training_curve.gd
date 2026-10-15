extends Control

var samples: Array[float] = []

func set_samples(values: Array[float]) -> void:
	samples = values.slice(maxi(0, values.size() - 200))
	queue_redraw()

func _draw() -> void:
	var rect := Rect2(Vector2.ZERO, size)
	draw_rect(rect, Color("101a18"), true)
	for row in range(1, 4):
		var y := size.y * float(row) / 4.0
		draw_line(Vector2(42, y), Vector2(size.x - 12, y), Color("34423c"), 1.0)
	if samples.size() < 2:
		draw_string(ThemeDB.fallback_font, Vector2(54, size.y * .56), "Episode rewards appear after the first completed rollout", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color("a5b2a9"))
		return
	var low := minf(-.1, samples.min())
	var high := maxf(.1, samples.max())
	var span := maxf(.001, high - low)
	var points := PackedVector2Array()
	for index in samples.size():
		var x := lerpf(44.0, size.x - 14.0, float(index) / float(samples.size() - 1))
		var y := remap(samples[index], low, high, size.y - 18.0, 12.0)
		points.append(Vector2(x, y))
	draw_polyline(points, Color("86d9af"), 2.0, true)
	draw_string(ThemeDB.fallback_font, Vector2(8, 18), "REWARD", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color("bac6bb"))
