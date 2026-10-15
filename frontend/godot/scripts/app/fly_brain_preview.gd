extends SubViewportContainer

## Compact schematic visualization only. The numeric labels in the adjacent
## panel continue to come from the live MaleCNS trace.
var viewport: SubViewport
var brain_root: Node3D
var zone_materials: Dictionary = {}
var zone_colors: Dictionary = {}
var trace_values: Array[float] = [0.0,0.0,0.0,0.0,0.0,0.0]
var event_flash := 0.0
var render_elapsed := 0.0
var angle := 0.0

func _ready() -> void:
	stretch=true
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	viewport=SubViewport.new()
	viewport.size=Vector2i(512,220)
	viewport.transparent_bg=false
	viewport.render_target_update_mode=SubViewport.UPDATE_ONCE
	viewport.world_3d=World3D.new()
	add_child(viewport)
	var environment=WorldEnvironment.new()
	var env=Environment.new()
	env.background_mode=Environment.BG_COLOR
	env.background_color=Color("101817")
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color=Color("9caf9d")
	env.ambient_light_energy=.8
	environment.environment=env
	viewport.add_child(environment)
	var key=DirectionalLight3D.new()
	key.rotation_degrees=Vector3(-35,-28,0)
	key.light_color=Color("f1d8a8")
	key.light_energy=1.7
	viewport.add_child(key)
	var fill=OmniLight3D.new()
	fill.position=Vector3(-2,2,3)
	fill.light_color=Color("78d8c0")
	fill.omni_range=9.0
	fill.light_energy=2.2
	viewport.add_child(fill)
	var camera=Camera3D.new()
	camera.position=Vector3(0,1.0,7.6)
	camera.fov=38.0
	camera.quaternion=Quaternion(Vector3.FORWARD,Vector3(0,-.85,-7.6).normalized())
	viewport.add_child(camera)
	brain_root=Node3D.new()
	viewport.add_child(brain_root)
	_build_brain()
	_sync_size()
	resized.connect(_sync_size)

func _material(color: Color) -> StandardMaterial3D:
	var mat=StandardMaterial3D.new()
	mat.albedo_color=color
	mat.emission_enabled=true
	mat.emission=color
	mat.emission_energy_multiplier=.35
	mat.roughness=.42
	return mat

func _lobe(name: String, position: Vector3, scale: Vector3, color: Color) -> MeshInstance3D:
	var node=MeshInstance3D.new()
	node.name=name
	var mesh=SphereMesh.new()
	mesh.radius=.5
	mesh.height=1.0
	node.mesh=mesh
	node.position=position
	node.scale=scale
	var mat=_material(color)
	node.material_override=mat
	brain_root.add_child(node)
	zone_materials[name]=mat
	zone_colors[name]=color
	return node

func _tract(a: Vector3,b: Vector3,radius: float,color: Color) -> void:
	var node=MeshInstance3D.new()
	var mesh=CylinderMesh.new()
	mesh.top_radius=radius
	mesh.bottom_radius=radius
	mesh.height=a.distance_to(b)
	mesh.radial_segments=7
	node.mesh=mesh
	node.position=(a+b)*.5
	node.quaternion=Quaternion(Vector3.UP,(b-a).normalized())
	node.material_override=_material(color)
	brain_root.add_child(node)

func _build_brain() -> void:
	# Paired optic lobes, central protocerebrum, mushroom-body-like lobes,
	# subesophageal region and descending ventral nerve cord.
	var optic_l=Vector3(-1.25,.32,0.0)
	var optic_r=Vector3(1.25,.32,0.0)
	var central=Vector3(0,.30,.08)
	var mushroom_l=Vector3(-.53,.70,-.18)
	var mushroom_r=Vector3(.53,.70,-.18)
	var sub=Vector3(0,-.45,.10)
	var neck=Vector3(0,-1.0,.14)
	var thorax=Vector3(0,-1.55,.18)
	_lobe("optic_l",optic_l,Vector3(.9,.78,.72),Color("477e9b"))
	_lobe("optic_r",optic_r,Vector3(.9,.78,.72),Color("477e9b"))
	_lobe("central",central,Vector3(1.45,.92,.88),Color("4c9b87"))
	_lobe("mushroom_l",mushroom_l,Vector3(.63,.48,.58),Color("c79d54"))
	_lobe("mushroom_r",mushroom_r,Vector3(.63,.48,.58),Color("c79d54"))
	_lobe("subesophageal",sub,Vector3(.73,.56,.64),Color("a66e61"))
	_lobe("neck_ganglion",neck,Vector3(.44,.38,.42),Color("b77c62"))
	_lobe("thoracic_ganglion",thorax,Vector3(.55,.42,.48),Color("a66e61"))
	for edge in [[optic_l,central],[optic_r,central],[central,mushroom_l],[central,mushroom_r],[central,sub],[sub,neck],[neck,thorax]]:
		_tract(edge[0],edge[1],.075,Color("72bca1"))
	for offset in [-.16,.16]:
		_tract(Vector3(offset,-.48,.1),Vector3(offset,-1.52,.18),.035,Color("d7b875"))

func set_traces(values: Array) -> void:
	for i in range(mini(6,values.size())):
		trace_values[i]=float(values[i])

func pulse_event(kind: String) -> void:
	event_flash=1.0 if kind=="hit" else .7

func _process(delta: float) -> void:
	angle+=delta*.22
	brain_root.rotation.y=sin(angle)*.23
	event_flash=move_toward(event_flash,0.0,delta*1.7)
	if not is_visible_in_tree():
		viewport.render_target_update_mode=SubViewport.UPDATE_DISABLED
		return
	render_elapsed+=delta
	if render_elapsed<1.0/15.0:
		return
	render_elapsed=fmod(render_elapsed,1.0/15.0)
	var groups={"optic_l":maxf(absf(trace_values[0]),absf(trace_values[2])),"optic_r":maxf(absf(trace_values[1]),absf(trace_values[3])),"central":maxf(absf(trace_values[4]),absf(trace_values[0])),"mushroom_l":absf(trace_values[2]),"mushroom_r":absf(trace_values[3]),"subesophageal":absf(trace_values[4]),"neck_ganglion":absf(trace_values[5]),"thoracic_ganglion":absf(trace_values[5])}
	for key in groups:
		var mat: StandardMaterial3D=zone_materials[key]
		# A square-root response keeps modest MaleCNS traces visible while still
		# reserving full saturation for the strongest recorded activity.
		var energy=sqrt(clampf(float(groups[key])/18.0,0.0,1.0))
		if event_flash>0.0:energy=maxf(energy,event_flash)
		mat.emission_energy_multiplier=.45+energy*3.0
		mat.albedo_color=zone_colors[key].lerp(Color("fff0a8"),energy*.68)
	viewport.render_target_update_mode=SubViewport.UPDATE_ONCE

func _sync_size() -> void:
	# SubViewportContainer stretches this fixed-resolution render target itself.
	pass
