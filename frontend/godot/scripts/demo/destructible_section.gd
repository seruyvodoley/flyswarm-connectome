extends StaticBody3D
class_name DestructibleSection

## Shared, energy-based damage model for the small set of interactive arena
## structures. Energy thresholds are gameplay approximations, not material data.
const DEBRIS_LIMIT := 18
static var active_debris := 0

var material_kind := "MASONRY"
var resistance_j := 1_800_000.0
var remaining_j := 1_800_000.0
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
	_apply_energy(energy * 0.36, point)

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
	if not is_inside_tree():
		return
	for index in 3:
		if active_debris >= DEBRIS_LIMIT:
			break
		var fragment := RigidBody3D.new()
		fragment.name = "EnvironmentDebris"
		fragment.mass = 90.0 if material_kind in ["WOOD", "BRICK"] else 180.0
		fragment.gravity_scale = 1.0
		fragment.can_sleep = true
		fragment.linear_damp = 1.4
		fragment.angular_damp = 1.8
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = Vector3(.42 + index * .08, .3 + index * .04, .38)
		shape.shape = box
		fragment.add_child(shape)
		var mesh_node := MeshInstance3D.new()
		var mesh := BoxMesh.new()
		mesh.size = box.size
		mesh_node.mesh = mesh
		var mat := StandardMaterial3D.new()
		mat.albedo_color = dust_color.darkened(.12)
		mesh_node.material_override = mat
		fragment.add_child(mesh_node)
		get_parent().add_child(fragment)
		fragment.global_position = point + Vector3(randf_range(-.35,.35),.35 + index*.12,randf_range(-.35,.35))
		fragment.linear_velocity = Vector3(randf_range(-2.0,2.0),randf_range(1.0,4.0),randf_range(-2.0,2.0))
		active_debris += 1
		var timer := get_tree().create_timer(7.0)
		timer.timeout.connect(func():
			if is_instance_valid(fragment):
				fragment.queue_free()
			active_debris = maxi(0, active_debris - 1)
		)
