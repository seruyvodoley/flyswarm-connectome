extends SceneTree
var b
var output=""
func _initialize():call_deferred("run")
func capture(name: String, eye: Vector3, target: Vector3, orthographic: float=0):
	b.camera.projection=Camera3D.PROJECTION_ORTHOGONAL if orthographic>0 else Camera3D.PROJECTION_PERSPECTIVE
	b.camera.size=orthographic if orthographic>0 else 1.0
	b.camera.fov=58;b.camera.far=1800;b.camera.position=eye;b.camera.look_at(target)
	for i in 8:await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output.path_join(name+".png"))
func run():
	output=ProjectSettings.globalize_path("res://../../docs/media/open-day-beta5")
	DirAccess.make_dir_recursive_absolute(output)
	var app=root.get_node("AppState");app.clear_view();app.configure_demo("t34_85")
	app.session.red_controller="rule";app.session.blue_controller="rule";app.session.record=false
	app.settings.fullscreen=false;app.settings.resolution=0;app.apply_settings()
	root.content_scale_mode=Window.CONTENT_SCALE_MODE_VIEWPORT;root.content_scale_size=Vector2i(1280,800)
	b=load("res://scenes/Battle.tscn").instantiate();b.session_config=app.session;root.add_child(b)
	b.set_process(false);b.set_physics_process(false);b.demo_intro_left=0;b.demo_intro.hide();b.sim_time=12;b.update_demo_smoke_screen()
	for n in b.find_children("*","CanvasLayer",true,false):n.hide()
	await physics_frame;await physics_frame
	b.demo_navigation.configure(b)
	b.observer_environment.fog_enabled=false
	for batch in b.demo_arena_root.find_children("*","MultiMeshInstance3D",true,false):batch.visibility_range_end=0
	await capture("map-after",Vector3(0,760,1),Vector3.ZERO,760)
	await capture("village",Vector3(-75,45,-115),Vector3(0,2,5))
	await capture("ridges-and-swale",Vector3(-225,33,-115),Vector3(-125,3,65))
	await capture("forest-belt",Vector3(237,22,-244),Vector3(215,1,-155))
	var player=b.vehicles[0];var fly=b.vehicles[8]
	player.position=Vector3(105,b.terrain.height_at(105,-120)+.1,-120)
	fly.position=Vector3(105,b.terrain.height_at(105,120)+.1,120)
	player.rotation.y=0;fly.rotation.y=PI
	await capture("long-range-field",player.position+Vector3(14,12,-22),fly.position+Vector3.UP*1.5)
	player.position=Vector3(-45,b.terrain.height_at(-45,-22)+.1,-22)
	await capture("cover-position",player.position+Vector3(-22,12,-22),player.position+Vector3(10,1,15))
	# Diagnostic route overlay is rendered in Godot, used only for the report.
	var path=b.demo_navigation.path(Vector3(24,b.terrain.height_at(24,205),205),Vector3(-196,b.terrain.height_at(-196,-168),-168))
	var mesh=ImmediateMesh.new();var mat=StandardMaterial3D.new();mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;mat.albedo_color=Color("dfb86e")
	mesh.surface_begin(Mesh.PRIMITIVE_LINES,mat)
	for i in range(1,path.size()):mesh.surface_add_vertex(path[i-1]+Vector3.UP*2);mesh.surface_add_vertex(path[i]+Vector3.UP*2)
	mesh.surface_end();var line=MeshInstance3D.new();line.mesh=mesh;b.add_child(line)
	await capture("flanking-route",Vector3(0,530,320),Vector3(0,0,0),650)
	line.hide()
	player.position=Vector3(-28,b.terrain.height_at(-28,-105)+.1,-105)
	await capture("player-camera",player.position+Vector3(0,6,-13),Vector3(-10,2,10))
	print("OPEN_DAY_GALLERY ",output);quit()
