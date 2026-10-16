extends "res://scripts/demo/destructible_section.gd"
class_name DestructibleTree

var falling := false
var visual_asset_path := ""
var visual_scale := 1.0
var batched_visuals: Array[MultiMeshInstance3D] = []
var batched_index := -1

func bind_batched_visual(path: String, scale_value: float, batches: Array[MultiMeshInstance3D], index: int) -> void:
	visual_asset_path = path
	visual_scale = scale_value
	batched_visuals = batches
	batched_index = index

func _hide_batched_visual() -> void:
	if batched_index < 0:
		return
	for batch in batched_visuals:
		if not is_instance_valid(batch) or batch.multimesh == null or batched_index >= batch.multimesh.instance_count:
			continue
		batch.multimesh.set_instance_transform(batched_index,Transform3D(Basis.IDENTITY,Vector3(0.0,-10000.0,0.0)))

func _break_section(point: Vector3) -> void:
	if broken or falling:
		return
	falling = true
	# Disable the upright trunk safely, then keep the tree visible as it falls.
	for child in get_children():
		if child is CollisionShape3D:
			child.set_deferred("disabled", true)
	_hide_batched_visual()
	if not is_instance_valid(visual_piece) and not visual_asset_path.is_empty():
		var packed := load(visual_asset_path) as PackedScene
		if packed != null:
			var fallen_visual := packed.instantiate() as Node3D
			if fallen_visual != null:
				fallen_visual.scale = Vector3.ONE * visual_scale
				add_child(fallen_visual)
	var local_impact := to_local(point)
	var direction := Vector3(local_impact.x, 0.0, local_impact.z).normalized()
	if direction.length_squared() < 0.01:
		direction = Vector3.RIGHT.rotated(Vector3.UP, rotation.y)
	var axis := Vector3.UP.cross(direction).normalized()
	if axis.length_squared() < 0.01:
		axis = Vector3.RIGHT
	var final_rotation := (Basis.from_euler(rotation) * Basis(axis,deg_to_rad(78.0))).get_euler()
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	tween.tween_property(self, "rotation", final_rotation, 1.15)
	tween.tween_callback(func():
		broken = true
		falling = false
		set_meta("destroyed", true)
	)
