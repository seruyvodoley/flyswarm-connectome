extends RefCounted

static func read_json(path: String) -> Dictionary:
	var full = "res://data/"+path if FileAccess.file_exists("res://data/"+path) else ProjectSettings.globalize_path("res://../../data/" + path)
	var f = FileAccess.open(full, FileAccess.READ)
	assert(f != null, "Missing data: " + full)
	var value = JSON.parse_string(f.get_as_text())
	assert(value is Dictionary, "Invalid JSON " + full)
	return value

static func vehicle(id: String, normalized: bool = false) -> Dictionary:
	var nation = "germany" if id in ["panther_g", "tiger_i", "jagdpanther"] else "ussr"
	var visual = read_json("vehicles/" + nation + "/" + id + ".json")
	var model = read_json("vehicles/ussr/t34_85.json") if normalized else visual
	var p = model.parameters.duplicate(true)
	p.id = id
	p.display_name = visual.name
	p.role = visual.role
	p.visual_turreted = visual.parameters.turreted
	p.gun_data = read_json("guns/" + p.gun + ".json")
	p.ammo_data = read_json("ammunition/" + p.gun_data.ammo + ".json")
	p.armour_data = read_json("armour/" + p.armour + ".json").zones
	return p
