extends SubViewportContainer

var fly_root: Node3D
var rotation_speed=.28

func _ready():
	stretch=true
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	var viewport=SubViewport.new()
	viewport.size=Vector2i(640,420)
	viewport.transparent_bg=false
	viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS
	viewport.world_3d=World3D.new()
	add_child(viewport)
	var environment=WorldEnvironment.new()
	var env=Environment.new()
	env.background_mode=Environment.BG_COLOR
	env.background_color=Color("111d1a")
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color=Color("9caf9d")
	env.ambient_light_energy=.7
	environment.environment=env
	viewport.add_child(environment)
	var key=DirectionalLight3D.new();key.rotation_degrees=Vector3(-38,-32,0);key.light_color=Color("e4d39b");key.light_energy=2.2;viewport.add_child(key)
	var fill=OmniLight3D.new();fill.position=Vector3(-3,2,4);fill.light_color=Color("7ba795");fill.omni_range=12;fill.light_energy=4.;viewport.add_child(fill)
	var camera=Camera3D.new();camera.position=Vector3(0,1.0,7.2);camera.fov=38;viewport.add_child(camera);camera.look_at(Vector3(0,.25,0))
	fly_root=Node3D.new();fly_root.rotation_degrees=Vector3(-8,-24,0);viewport.add_child(fly_root)
	build_fly()

func material(colour: Color,roughness=.62,transparent=false) -> StandardMaterial3D:
	var value=StandardMaterial3D.new();value.albedo_color=colour;value.roughness=roughness
	if transparent:value.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;value.cull_mode=BaseMaterial3D.CULL_DISABLED
	return value

func ellipsoid(name: String,position: Vector3,scale_value: Vector3,colour: Color,parent=fly_root):
	var node=MeshInstance3D.new();node.name=name
	var mesh=SphereMesh.new();mesh.radius=1.;mesh.height=2.;mesh.radial_segments=24;mesh.rings=12
	node.mesh=mesh;node.position=position;node.scale=scale_value;node.material_override=material(colour,.55,colour.a<1.);parent.add_child(node)
	return node

func segment(a: Vector3,b: Vector3,radius: float,colour: Color,parent=fly_root):
	var node=MeshInstance3D.new();var mesh=CylinderMesh.new();mesh.top_radius=radius;mesh.bottom_radius=radius;mesh.height=a.distance_to(b);mesh.radial_segments=8
	node.mesh=mesh;node.position=(a+b)*.5;node.basis=Basis(Quaternion(Vector3.UP,(b-a).normalized()));node.material_override=material(colour);parent.add_child(node)
	return node

func build_fly():
	var dark=Color("211a14");var brown=Color("5b3420");var amber=Color("a76125");var leg=Color("2c2118")
	ellipsoid("Thorax",Vector3(0,.25,0),Vector3(.72,.72,.92),brown)
	ellipsoid("Abdomen",Vector3(0,.1,-1.25),Vector3(.58,.55,1.2),amber)
	ellipsoid("Head",Vector3(0,.35,1.05),Vector3(.64,.58,.58),dark)
	ellipsoid("EyeL",Vector3(-.48,.48,1.35),Vector3(.3,.36,.25),Color("9b2318"))
	ellipsoid("EyeR",Vector3(.48,.48,1.35),Vector3(.3,.36,.25),Color("9b2318"))
	for side in [-1.,1.]:
		var wing=ellipsoid("Wing",Vector3(side*.82,.52,-.55),Vector3(.55,.07,1.45),Color(0.72,0.82,0.73,.42))
		wing.rotation_degrees.y=side*20
		segment(Vector3(side*.28,.55,.85),Vector3(side*.55,.86,1.65),.025,leg)
		segment(Vector3(side*.55,.86,1.65),Vector3(side*.72,.7,1.92),.018,leg)
		for z in [.55,0.,-.55]:
			var hip=Vector3(side*.35,.2,z)
			var knee=Vector3(side*1.0,-.35,z+.25)
			var foot=Vector3(side*1.55,-.72,z+.65)
			segment(hip,knee,.045,leg);segment(knee,foot,.032,leg)
	# The striped abdomen and red compound eyes make this replaceable procedural
	# asset recognisable as Drosophila rather than a generic beetle.
	for z in [-.55,-.95,-1.35,-1.72]:segment(Vector3(-.48,.12,z),Vector3(.48,.12,z),.035,dark)

func _process(delta):
	if is_instance_valid(fly_root):fly_root.rotate_y(delta*rotation_speed)
