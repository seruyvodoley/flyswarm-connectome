extends SceneTree
class Probe extends CharacterBody3D:
	var frames=[]
	var angles=[]
	var elapsed=0.0
	func _physics_process(dt):
		elapsed+=dt
		# Combined forward motion, pivot-like turning, then a broad sweeping turn.
		var phase=elapsed*.72
		velocity=Vector3(sin(phase)*8,0,cos(phase)*8)
		move_and_slide()
		rotation.y=wrapf(rotation.y+sin(phase*.6)*.85*dt,-PI,PI)
	func _process(_dt):
		var t=get_global_transform_interpolated()
		frames.append(t.origin);angles.append(t.basis.z.normalized())
var probe: Probe
func _initialize():call_deferred("run")
func run():
	Engine.max_fps=120
	probe=Probe.new();root.add_child(probe);probe.reset_physics_interpolation()
	await create_timer(2.0).timeout
	var max_step=0.0;var angular_step=0.0;var changed=0
	for i in range(1,probe.frames.size()):
		var d=probe.frames[i].distance_to(probe.frames[i-1]);max_step=maxf(max_step,d);if d>.00001:changed+=1
		angular_step=maxf(angular_step,acos(clampf(probe.angles[i].dot(probe.angles[i-1]),-1,1)))
	var report={"project_interpolation":ProjectSettings.get_setting("physics/common/physics_interpolation"),"render_samples":probe.frames.size(),"moving_samples":changed,"max_frame_displacement_m":max_step,"max_frame_yaw_rad":angular_step}
	print("CAMERA_INTERPOLATION_VALIDATION ",JSON.stringify(report))
	if not report.project_interpolation or changed<80 or max_step>.5 or angular_step>.08:push_error("Camera target transform is not smoothly interpolated");quit(1)
	else:quit()
