extends SceneTree

const DestructibleSection=preload("res://scripts/demo/destructible_section.gd")
const DestructibleTree=preload("res://scripts/demo/destructible_tree.gd")
const FlyBrainPreview=preload("res://scripts/app/fly_brain_preview.gd")
const Terrain=preload("res://scripts/terrain.gd")
const DemoArena=preload("res://scripts/demo/demo_arena.gd")
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)

func run() -> void:
	var world := Node3D.new()
	root.add_child(world)
	var wall: DestructibleSection=DestructibleSection.new()
	wall.configure("MASONRY",1_800_000.0,Color("b5a781"))
	wall.position=Vector3(0,1.5,0)
	wall.collision_layer=1
	var wall_shape := CollisionShape3D.new()
	var wall_box := BoxShape3D.new()
	wall_box.size=Vector3(8.0,3.0,.5)
	wall_shape.shape=wall_box
	wall.add_child(wall_shape)
	world.add_child(wall)
	var tank := CharacterBody3D.new()
	tank.position=Vector3(0,.8,-6)
	tank.collision_layer=2
	tank.collision_mask=1
	var tank_shape := CollisionShape3D.new()
	var tank_box := BoxShape3D.new()
	tank_box.size=Vector3(2.5,1.6,3.5)
	tank_shape.shape=tank_box
	tank_shape.position.y=.8
	tank.add_child(tank_shape)
	world.add_child(tank)
	for _i in 36:
		await physics_frame
		tank.velocity=Vector3(0,0,8)
		tank.move_and_slide()
	check(tank.global_position.z < -1.4,"Tank CharacterBody contact blocks passage through an intact stone wall")
	check(tank.get_slide_collision_count()>0,"Intact wall is reported as a real CharacterBody slide contact")
	var wall_contact=tank.get_slide_collision(0)
	wall.damage_ram(0,26000.0,Vector3(0,0,8),wall_contact.get_position(),wall_contact.get_normal())
	check(not wall.broken and wall.remaining_j<wall.resistance_j,"A real high-mass tank contact applies bounded impact damage without instantly erasing masonry")
	var light_round={"mass_kg":1.0}
	wall.damage_projectile(light_round,Vector3(0,0,100),Vector3(0,0,-1),wall.global_position)
	check(not wall.broken and wall.remaining_j>0.0,"Low-energy projectile does not destroy masonry")
	var tank_round={"mass_kg":10.2}
	wall.damage_projectile(tank_round,Vector3(0,0,1000),Vector3(0,0,-1),wall.global_position)
	check(wall.broken,"Projectile kinetic energy destroys a sufficiently damaged wall section")
	await physics_frame
	check(wall_shape.disabled,"Destroyed section disables its collider after the physics step")
	var query=PhysicsRayQueryParameters3D.create(Vector3(0,3.3,-5),Vector3(0,3.3,5),1,[])
	check(root.get_world_3d().direct_space_state.intersect_ray(query).is_empty(),"Raycast and line of sight pass through the cleared wall section")
	var tree: DestructibleTree=DestructibleTree.new()
	tree.position=Vector3(12,0,0)
	tree.configure("WOOD",310_000.0,Color("62513b"))
	var trunk_shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius=.3
	capsule.height=3.2
	trunk_shape.shape=capsule
	trunk_shape.position.y=1.6
	tree.add_child(trunk_shape)
	world.add_child(tree)
	tree.damage_projectile(light_round,Vector3(0,0,100),Vector3(0,0,-1),tree.global_position)
	check(not tree.broken,"Small hit cannot snap a mature tree")
	tree.damage_projectile(tank_round,Vector3(0,0,1000),Vector3(0,0,-1),tree.global_position+Vector3(0,0,1))
	await create_timer(1.4).timeout
	check(tree.broken and trunk_shape.disabled and absf(tree.rotation.z)+absf(tree.rotation.x)>0.5,"Damaged tree falls over and clears its upright trunk collider")
	var preview=FlyBrainPreview.new()
	preview.size=Vector2(360,190)
	root.add_child(preview)
	await process_frame
	var brain_meshes=preview.brain_root.find_children("*","MeshInstance3D",true,false)
	check(brain_meshes.size()>=15 and preview.zone_materials.has("optic_l") and preview.zone_materials.has("thoracic_ganglion"),"Schematic insect brain creates paired optic lobes, central zones, tracts and descending ganglia")
	var optic_material: StandardMaterial3D=preview.zone_materials["optic_l"]
	var initial_glow=optic_material.emission_energy_multiplier
	preview.set_traces([18.0,0.0,0.0,0.0,0.0,0.0])
	preview._process(.1)
	check(optic_material.emission_energy_multiplier>initial_glow,"Live DNp09 telemetry increases optic-zone glow without modifying trace values")
	preview.pulse_event("hit")
	preview._process(.1)
	check(preview.event_flash>0.0 and preview.trace_values[0]==18.0,"Impact flash is visual-only and leaves the displayed neural trace unchanged")
	preview.hide()
	preview._process(.1)
	check(preview.viewport.render_target_update_mode==SubViewport.UPDATE_DISABLED,"Hidden brain preview stops offscreen rendering")
	var terrain: Node3D=Terrain.new()
	world.add_child(terrain)
	terrain.build(false,19441004,300.0)
	var arena: Node3D=DemoArena.new()
	arena.configure(terrain,.25)
	world.add_child(arena)
	await process_frame
	var arena_sections=arena.find_children("*","DestructibleSection",true,false)
	var interactive_trees=arena.find_children("*","DestructibleTree",true,false)
	check(arena_sections.size()>=15,"Open Day arena builds separate wall, house-foundation and barrier sections")
	check(interactive_trees.size()==9,"Playable area has a capped set of nine interactive trees while distant forest remains instanced")
	var imported_section: DestructibleSection
	var imported_faces: PackedVector3Array
	for candidate in arena_sections:
		for child in candidate.get_children():
			if child is CollisionShape3D and child.shape is ConcavePolygonShape3D:
				var faces: PackedVector3Array=child.shape.get_faces()
				if faces.size()>=3:
					imported_section=candidate
					imported_faces=faces
					break
		if is_instance_valid(imported_section):break
	check(is_instance_valid(imported_section) and is_instance_valid(imported_section.visual_piece),"Imported building mesh is paired with its own visible mesh and triangle-mesh collider")
	if is_instance_valid(imported_section):
		var exclude_sections:Array[RID]=[]
		for other in root.find_children("*","CollisionObject3D",true,false):
			if other!=imported_section:exclude_sections.append(other.get_rid())
		var surface_normal=Vector3.ZERO
		var surface_point=Vector3.ZERO
		var found_mesh_hit=false
		# Imported houses contain hidden and ground-facing surfaces, so probe a
		# handful of elevated triangles and keep one the real physics ray reaches.
		for face_index in range(0,imported_faces.size()-2,3):
			var local_normal=(imported_faces[face_index+1]-imported_faces[face_index]).cross(imported_faces[face_index+2]-imported_faces[face_index]).normalized()
			var candidate_normal=(imported_section.global_transform.basis*local_normal).normalized()
			var candidate_point=imported_section.global_transform*((imported_faces[face_index]+imported_faces[face_index+1]+imported_faces[face_index+2])/3.0)
			var candidate_ray=PhysicsRayQueryParameters3D.create(candidate_point+candidate_normal*1.0,candidate_point-candidate_normal*1.0,1,exclude_sections)
			var candidate_hit=root.get_world_3d().direct_space_state.intersect_ray(candidate_ray)
			if not candidate_hit.is_empty() and candidate_hit.collider==imported_section:
				surface_normal=candidate_normal
				surface_point=candidate_point
				found_mesh_hit=true
				break
		check(found_mesh_hit,"Projectile ray hits the real imported house mesh section")
		var source_mesh=imported_section.visual_piece
		imported_section.damage_projectile({"mass_kg":10.2},-surface_normal*1000.0,surface_normal,surface_point)
		await physics_frame
		check(imported_section.broken and not source_mesh.visible and imported_section.get_child(0).disabled,"Destroying an imported section hides that mesh and disables its matching collider")
	var interactive_count=0
	for node in arena.find_children("*","StaticBody3D",true,false):
		if node.collision_layer==1:interactive_count+=1
	check(interactive_count<40,"Interactive environment colliders stay under the arena object budget")
	print("ENVIRONMENT PHYSICS validation failures=",failures)
	quit(1 if failures>0 else 0)
