extends "res://scripts/demo/demo_arena.gd"

## Reuses Open Day's CC0 vegetation, rock, building, fence and destruction
## components while giving the large battlefield and gunnery range their own
## reproducible layouts. Visual mode deliberately adds no new collision bodies.
const TREE_PATHS := {
	"maple": "res://assets/environment/vegetation/maple-light.glb",
	"conifer": "res://assets/environment/vegetation/conifer-light.glb",
	"oak": "res://assets/environment/vegetation/oak-detailed.glb"
}
const BUSH_PATH := "res://assets/environment/vegetation/elder-bush.glb"
const GRASS_PATH := "res://assets/environment/vegetation/meadow-grass.glb"
const ROCK_PATH := "res://assets/environment/rocks/rock-cluster.glb"
const FARM_PATH := "res://assets/environment/ruins/farmhouse-barn.glb"
const COTTAGE_PATH := "res://assets/environment/ruins/thatched-cottage.glb"
const WALL_PATH := "res://assets/environment/ruins/stone-cottage-wall.glb"
const FENCE_PATH := "res://assets/environment/props/cow-pen-fence.glb"
const RUBBLE_PATH := "res://assets/environment/props/stone-rubble-pile.glb"

var world_profile := "enhanced_visual"
var training_range := false

## The Open Day helper batches one MultiMesh for every imported mesh node. Some
## foliage GLBs contain dozens of tiny leaf meshes, which multiplies draw calls
## on the 8×8 field. Merge source surfaces by material once, then instance those
## merged meshes across the deterministic placements.
func add_instanced(path: String, placements: Array, cast_shadows: bool) -> Array[MultiMeshInstance3D]:
	var batches: Array[MultiMeshInstance3D] = []
	if placements.is_empty():
		return batches
	var template := _instantiate_model(path)
	if template == null:
		return batches
	add_child(template)
	var template_inverse := template.global_transform.affine_inverse()
	var tools: Dictionary = {}
	var materials: Dictionary = {}
	for node in template.find_children("*", "MeshInstance3D", true, false):
		var mesh_node := node as MeshInstance3D
		if mesh_node.mesh == null:
			continue
		var relative := template_inverse * mesh_node.global_transform
		for surface_index in range(mesh_node.mesh.get_surface_count()):
			var surface_material: Material = mesh_node.material_override
			if surface_material == null:
				surface_material = mesh_node.get_surface_override_material(surface_index)
			if surface_material == null:
				surface_material = mesh_node.mesh.surface_get_material(surface_index)
			var key := "material_%s" % str(surface_material.get_instance_id()) if surface_material != null else "no_material"
			if not tools.has(key):
				var surface_tool := SurfaceTool.new()
				surface_tool.begin(Mesh.PRIMITIVE_TRIANGLES)
				tools[key] = surface_tool
				materials[key] = surface_material
			(surface_tool_for_key(tools, key) as SurfaceTool).append_from(mesh_node.mesh, surface_index, relative)
	for key in tools:
		var surface_tool := tools[key] as SurfaceTool
		var material: Material = materials[key]
		if material != null:
			surface_tool.set_material(material)
		var combined_mesh := surface_tool.commit()
		if combined_mesh == null or combined_mesh.get_surface_count() == 0:
			continue
		var multimesh := MultiMesh.new()
		multimesh.transform_format = MultiMesh.TRANSFORM_3D
		multimesh.mesh = combined_mesh
		multimesh.instance_count = placements.size()
		for index in range(placements.size()):
			var placement: Dictionary = placements[index]
			var scale_value := float(placement.scale)
			var transform := Transform3D(Basis(Vector3.UP, float(placement.yaw)).scaled(Vector3.ONE * scale_value), placement.position)
			multimesh.set_instance_transform(index, transform)
		var batch := MultiMeshInstance3D.new()
		batch.multimesh = multimesh
		batch.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if cast_shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		batch.visibility_range_end = 330.0
		add_child(batch)
		batches.append(batch)
	template.queue_free()
	return batches

func surface_tool_for_key(tools: Dictionary, key: String) -> SurfaceTool:
	return tools[key] as SurfaceTool

func configure_world(terrain: Node3D, density: float, profile: String, is_training_range: bool) -> void:
	terrain_source = terrain
	vegetation_density = clampf(density, 0.25, 1.0)
	world_profile = profile
	training_range = is_training_range

func _ready() -> void:
	rng.seed = int(terrain_source.get("map_seed")) if is_instance_valid(terrain_source) else 1944
	set_meta("environment_profile", world_profile)
	set_meta("generator_version", "field_environment_v1")
	if training_range:
		build_training_range()
	else:
		build_krasny_valley()

func build_krasny_valley() -> void:
	build_forests()
	build_village()
	build_rocks_and_scrub()
	build_farm_fences()

func build_training_range() -> void:
	# The firing axis (x≈0) and all configured target distances stay clear.
	var field_extent: float = terrain_source.extent
	var z_min := -field_extent * .78
	var z_span := field_extent * 1.56
	var roadside := []
	for side in [-1.0, 1.0]:
		for index in range(42):
			var z: float = z_min + float(index) * z_span / 41.0 + rng.randf_range(-7.0, 7.0)
			var min_x := minf(138.0,field_extent*.48)
			var max_x := minf(225.0,field_extent*.78)
			var x: float = float(side) * rng.randf_range(min_x,maxf(min_x,max_x))
			var slope := _slope_at(x,z)
			if slope > 0.32:
				continue
			roadside.append(_placement(x,z,rng.randf_range(0.7,1.15)))
	var shrub_batches := add_instanced(BUSH_PATH, roadside, false)
	_set_batch_range(shrub_batches, 1650.0, false)
	var grass := []
	for index in range(roundi(520.0 * vegetation_density)):
		var x := rng.randf_range(-420.0,420.0)
		if absf(x) < 92.0:
			continue
		var z := rng.randf_range(-field_extent*.7,field_extent*.7)
		grass.append(_placement(x,z,rng.randf_range(.72,1.28)))
	_set_batch_range(add_instanced(GRASS_PATH,grass,false),1450.0,false)

func build_forests() -> void:
	var points: Array = _poisson_patch(terrain_source.forest_center, 160.0, roundi(265.0 * vegetation_density), 8.2)
	if world_profile == "enhanced_physical":
		for patch in terrain_source._physical_forest_patches():
			points.append_array(_poisson_patch(patch[0], float(patch[1]) - 8.0, roundi(105.0 * vegetation_density), 9.0))
	# Wooded roadside and field boundaries use sparse, irregular rows rather than
	# an even grid. They only extend the forest in the physical profile.
	if world_profile == "enhanced_physical":
		for side in [-1.0, 1.0]:
			for index in range(34):
				var x: float = float(side) * (610.0 + rng.randf_range(-32.0,32.0))
				var z: float = -650.0 + float(index) * 39.0 + rng.randf_range(-13.0,13.0)
				if _slope_at(x,z) < .34:
					points.append(_placement(x,z,rng.randf_range(.72,1.04)))
	var groups := {"maple":[],"conifer":[],"oak":[]}
	for point in points:
		var pick := rng.randf()
		var kind := "maple" if pick < .46 else ("conifer" if pick < .79 else "oak")
		groups[kind].append(point)
	for kind in groups:
		var shadows: bool = kind == "oak"
		var batches := add_instanced(TREE_PATHS[kind], groups[kind], shadows)
		_set_batch_range(batches, 2050.0, shadows)
		if world_profile == "enhanced_physical":
			for index in range(groups[kind].size()):
				_add_interactive_tree(TREE_PATHS[kind], groups[kind][index], kind, batches, index)

func build_village() -> void:
	var houses := [
		Vector2(116,-186), Vector2(143,-172), Vector2(184,-198), Vector2(212,-165),
		Vector2(-132,-208), Vector2(-166,-183), Vector2(-198,-221), Vector2(-226,-190),
		Vector2(286,174), Vector2(318,192), Vector2(347,165), Vector2(376,206),
		Vector2(-304,188), Vector2(-338,214), Vector2(-369,180), Vector2(-398,218)
	]
	var farm_placements := []
	var cottage_placements := []
	for index in range(houses.size()):
		var p: Vector2 = houses[index]
		var placement := _placement(p.x + rng.randf_range(-6.0,6.0), p.y + rng.randf_range(-5.0,5.0), rng.randf_range(.82,1.08))
		placement.yaw = rng.randf_range(-PI,PI)
		(farm_placements if index % 3 == 0 else cottage_placements).append(placement)
	if world_profile == "enhanced_physical":
		_add_physical_buildings(FARM_PATH, farm_placements, "MASONRY", 620_000.0)
		_add_physical_buildings(COTTAGE_PATH, cottage_placements, "MASONRY", 520_000.0)
	else:
		_set_batch_range(add_instanced(FARM_PATH,farm_placements,true),1900.0,true)
		_set_batch_range(add_instanced(COTTAGE_PATH,cottage_placements,true),1900.0,true)
	var walls := []
	for p in [Vector2(160,-230),Vector2(-184,-246),Vector2(333,232),Vector2(-354,249)]:
		var placement := _placement(p.x,p.y,rng.randf_range(.8,1.15))
		placement.yaw = rng.randf_range(-PI,PI)
		walls.append(placement)
	if world_profile == "enhanced_physical":
		_add_physical_buildings(WALL_PATH,walls,"MASONRY",360_000.0)
	else:
		_set_batch_range(add_instanced(WALL_PATH,walls,true),1500.0,true)
	var rubble := []
	for house in [Vector2(185,-202),Vector2(-343,223)]:
		for index in range(7):
			var x: float = house.x + rng.randf_range(-9.0,9.0)
			var z: float = house.y + rng.randf_range(-7.0,7.0)
			rubble.append(_placement(x,z,rng.randf_range(.55,1.2)))
	_set_batch_range(add_instanced(RUBBLE_PATH,rubble,false),950.0,false)

func _add_physical_buildings(path: String, placements: Array, kind: String, strength: float) -> void:
	for placement in placements:
		var root := Node3D.new()
		root.position = placement.position
		root.rotation.y = float(placement.yaw)
		root.scale = Vector3.ONE * float(placement.scale)
		add_child(root)
		var model := _instantiate_model(path)
		if model == null:
			continue
		root.add_child(model)
		if _add_mesh_sections(root,model,kind,strength,Color("b5a781")) == 0:
			_add_destructible_box(root,Vector3(0,2.0,0),Vector3(8.0,4.0,8.0),kind,strength,Color("b5a781"))

func build_rocks_and_scrub() -> void:
	var rocks := []
	var bushes := []
	for index in range(roundi(88.0 * vegetation_density)):
		var x := rng.randf_range(-680.0,680.0)
		var z := rng.randf_range(-680.0,680.0)
		if absf(x) < 75.0 and absf(z) < 105.0:
			continue
		if _slope_at(x,z) > .42:
			continue
		var p := _placement(x,z,rng.randf_range(.42,1.1))
		p.yaw = rng.randf_range(-PI,PI)
		rocks.append(p)
	for index in range(roundi(320.0 * vegetation_density)):
		var x := rng.randf_range(-690.0,690.0)
		var z := rng.randf_range(-690.0,690.0)
		if absf(x) < 72.0 and absf(z) < 90.0:
			continue
		bushes.append(_placement(x,z,rng.randf_range(.56,1.35)))
	var rock_batches := add_instanced(ROCK_PATH,rocks,false)
	_set_batch_range(rock_batches,1350.0,false)
	var bush_batches := add_instanced(BUSH_PATH,bushes,false)
	_set_batch_range(bush_batches,1050.0,false)
	var grass := []
	for index in range(roundi(680.0 * vegetation_density)):
		var x := rng.randf_range(-700.0,700.0)
		var z := rng.randf_range(-700.0,700.0)
		if absf(x) < 65.0 and absf(z) < 90.0:
			continue
		grass.append(_placement(x,z,rng.randf_range(.68,1.34)))
	_set_batch_range(add_instanced(GRASS_PATH,grass,false),720.0,false)
	if world_profile == "enhanced_physical":
		for index in range(mini(24,rocks.size())):
			var placement: Dictionary = rocks[index]
			var root := Node3D.new()
			root.position = placement.position
			root.rotation.y = float(placement.yaw)
			root.scale = Vector3.ONE * float(placement.scale)
			add_child(root)
			var model := _instantiate_model(ROCK_PATH)
			if model == null:
				continue
			root.add_child(model)
			_add_mesh_sections(root,model,"STONE",2_400_000.0,Color("77766f"))

func build_farm_fences() -> void:
	var placements := []
	for center_value in [Vector2(159,-190),Vector2(-181,-206),Vector2(342,189),Vector2(-353,205)]:
		var center: Vector2 = center_value
		for side in range(4):
			var yaw: float = float(side) * PI * .5
			var start: Vector2 = center + Vector2(cos(yaw),sin(yaw)) * -18.0
			for segment in range(7):
				var p: Vector2 = start + Vector2(cos(yaw),sin(yaw)) * (float(segment) * 5.1)
				if segment in [1,5]:
					continue
				var placement := _placement(p.x,p.y,1.0)
				placement.yaw = yaw
				placements.append(placement)
	_set_batch_range(add_instanced(FENCE_PATH,placements,false),1000.0,false)
	if world_profile == "enhanced_physical":
		for placement in placements:
			var fence := DestructibleSection.new()
			fence.configure("WOOD",90_000.0,Color("765638"))
			fence.collision_layer = 1
			fence.collision_mask = 0
			fence.position = placement.position
			fence.rotation.y = float(placement.yaw)
			var shape := CollisionShape3D.new()
			var box := BoxShape3D.new()
			box.size = Vector3(3.2,1.1,.18)
			shape.shape = box
			fence.add_child(shape)
			add_child(fence)

func _poisson_patch(center: Vector2, radius: float, count: int, spacing: float) -> Array:
	var result: Array = []
	var attempts := 0
	while result.size() < count and attempts < count * 26:
		attempts += 1
		var angle := rng.randf_range(0.0,TAU)
		var distance := sqrt(rng.randf()) * radius
		var x: float = center.x + cos(angle) * distance
		var z: float = center.y + sin(angle) * distance
		if _slope_at(x,z) > .36 or _on_road(x,z,14.0):
			continue
		var separated := true
		for previous in result:
			if Vector2(x,z).distance_to(Vector2(previous.position.x,previous.position.z)) < spacing:
				separated = false
				break
		if separated:
			result.append(_placement(x,z,rng.randf_range(.74,1.12)))
	return result

func _on_road(x: float, z: float, margin: float) -> bool:
	return absf(z - terrain_source._main_road_z(x)) < margin or absf(x-terrain_source._north_south_road_x(z)) < margin or absf(x-terrain_source._west_road_x(z)) < margin

func _slope_at(x: float, z: float) -> float:
	var hx: float = terrain_source.height_at(x+3.0,z) - terrain_source.height_at(x-3.0,z)
	var hz: float = terrain_source.height_at(x,z+3.0) - terrain_source.height_at(x,z-3.0)
	return Vector2(hx,hz).length() / 6.0

func _placement(x: float, z: float, scale_value: float) -> Dictionary:
	return {"position":Vector3(x,ground(x,z),z),"yaw":rng.randf_range(-PI,PI),"scale":scale_value}

func _set_batch_range(batches: Array[MultiMeshInstance3D], visible_to: float, shadows: bool) -> void:
	for batch in batches:
		if not is_instance_valid(batch):
			continue
		batch.visibility_range_end = visible_to
		batch.visibility_range_end_margin = minf(70.0,visible_to*.12)
		batch.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		batch.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
