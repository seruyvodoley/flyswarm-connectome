extends "res://scripts/demo/destructible_section.gd"
class_name DestructibleTree

var falling := false

func _break_section(point: Vector3) -> void:
	if broken or falling:
		return
	falling = true
	# Disable the upright trunk safely, then keep the tree visible as it falls.
	for child in get_children():
		if child is CollisionShape3D:
			child.set_deferred("disabled", true)
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
