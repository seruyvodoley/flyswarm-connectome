extends StaticBody3D
class_name DestructibleSection

## Shared, energy-based damage model for the small set of interactive arena
## structures. Energy thresholds are gameplay approximations, not material data.
const DEBRIS_LIMIT := 12
static var active_debris := 0

var material_kind := "MASONRY"
var resistance_j := 620_000.0
var remaining_j := 620_000.0
var broken := false
var dust_color := Color("bba982")
var ram_cooldowns: Dictionary = {}
var visual_piece: MeshInstance3D

func configure(kind: String, threshold_j: float, color: Color) -> void:
	material_kind = kind
	resistance_j = maxf(1000.0, threshold_j)
	remaining_j = resistance_j
	dust_color = color

func bind_visual_piece(piece: MeshInstance3D) -> void:
	visual_piece = piece

func damage_projectile(ammo: Dictionary, velocity: Vector3, normal: Vector3, point: Vector3) -> void:
	if broken:
		return
	var mass := maxf(0.01, float(ammo.get("mass_kg", 1.0)))
	var impact_speed := velocity.length()
	var incidence := clampf(absf(velocity.normalized().dot(normal.normalized())), 0.08, 1.0)
	# The impulse reaching the surface follows the projectile's real kinetic energy;
	# glancing hits couple less energy into masonry and timber.
	_apply_energy(0.5 * mass * impact_speed * impact_speed * incidence, point)

func damage_ram(vehicle_id: int, mass_kg: float, velocity: Vector3, point: Vector3, normal: Vector3) -> void:
	if broken or velocity.length() < 1.25:
		return
	var now := Time.get_ticks_msec()
	if int(ram_cooldowns.get(vehicle_id, 0)) > now:
		return
	ram_cooldowns[vehicle_id] = now + 650
	var incidence := clampf(absf(velocity.normalized().dot(normal.normalized())), 0.0, 1.0)
	if incidence < 0.28:
		return
	# Only a real CharacterBody slide contact calls this, and low-speed contact
	# cannot accumulate repeated damage while a tank rests against a wall.
	var energy := 0.5 * maxf(1000.0, mass_kg) * velocity.length_squared() * incidence
	# A tracked vehicle couples most of its forward kinetic energy into a rigid
	# obstacle. This lets one fast, square-on impact topple a tree or break the
	# struck wall section, while oblique and low-speed contacts remain weaker.
	_apply_energy(energy * 0.82, point)

func _apply_energy(energy_j: float, point: Vector3) -> void:
	if broken or energy_j <= 0.0:
		return
	remaining_j = maxf(0.0, remaining_j - energy_j)
	if remaining_j <= 0.0:
		_break_section(point)

func _break_section(point: Vector3) -> void:
	if broken:
		return
	broken = true
	# Deferred shape changes are safe after a physics contact or ray query.
	for child in get_children():
		if child is CollisionShape3D:
			child.set_deferred("disabled", true)
	if is_instance_valid(visual_piece):
		visual_piece.visible = false
	_spawn_debris(point)
	set_meta("destroyed", true)

func _spawn_debris(point: Vector3) -> void:
	if not is_inside_tree() or not is_instance_valid(visual_piece) or visual_piece.mesh == null:
		return
	if active_debris >= DEBRIS_LIMIT:
		return
	# Release the actual struck wall/roof/wood piece as one heavy chunk instead
	# of replacing it with several identical cubes. The remaining structure stays
	# in place until its own sections take damage, producing a partial collapse.
	var fragment := RigidBody3D.new()
	fragment.name = "EnvironmentDebris"
	fragment.mass = 90.0 if material_kind in ["WOOD", "BRICK"] else 180.0
	fragment.gravity_scale = 1.0
	fragment.can_sleep = true
	fragment.linear_damp = 1.4
	fragment.angular_damp = 1.8
	var mesh_node := MeshInstance3D.new()
	mesh_node.mesh = visual_piece.mesh
	mesh_node.material_override = visual_piece.material_override
	mesh_node.material_overlay = visual_piece.material_overlay
	mesh_node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	var bounds := visual_piece.mesh.get_aabb()
	mesh_node.position = -bounds.get_center()
	fragment.add_child(mesh_node)
	var collision := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = bounds.size.max(Vector3(.2, .2, .2))
	collision.shape = box
	collision.position = -bounds.get_center()
	fragment.add_child(collision)
	get_parent().add_child(fragment)
	fragment.global_transform = visual_piece.global_transform
	fragment.global_position += Vector3(0.0, 0.04, 0.0)
	fragment.linear_velocity = Vector3(randf_range(-1.5,1.5),randf_range(1.0,2.5),randf_range(-1.5,1.5))
	fragment.apply_torque_impulse(Vector3(randf_range(-250,250),randf_range(-180,180),randf_range(-250,250)))
	active_debris += 1
	var timer := get_tree().create_timer(9.0)
	timer.timeout.connect(func():
		if is_instance_valid(fragment):
			fragment.queue_free()
		active_debris = maxi(0, active_debris - 1)
	)
