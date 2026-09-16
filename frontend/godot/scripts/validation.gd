extends SceneTree
const Combat=preload("res://scripts/combat.gd")
const Catalog=preload("res://scripts/catalog.gd")
var failures=0
func check(ok: bool,message: String):
	if not ok:
		failures+=1
		push_error(message)
func _initialize():call_deferred("run")
func run():
	var ammo=Catalog.read_json("ammunition/kwk42_ap.json")
	check(is_equal_approx(Combat.penetration(ammo,300),175),"penetration interpolation")
	for distance in [100,500,1000,1500]:
		var flight=float(distance)/ammo.muzzle_velocity_m_s
		var y=-4.905*flight*flight
		check(y<0 and flight>0,"gravity/time")
		print("BALLISTICS vacuum check range=",distance," time=",flight," drop=",y)
	var frontal=Combat.impact(ammo,100,Vector3.FORWARD,Vector3.BACK,{"thickness_mm":80})
	check(frontal.penetrated,"normal impact should penetrate")
	var oblique=Combat.impact(ammo,100,Vector3.FORWARD,Vector3(1,0,.1),{"thickness_mm":80})
	check(oblique.ricochet and not oblique.penetrated,"grazing ricochet")
	var scene=load("res://scenes/Battle.tscn").instantiate()
	root.add_child(scene)
	await physics_frame
	await physics_frame
	scene.paused=true
	check(scene.vehicles.size()==16,"16 vehicles")
	var types={}
	for v in scene.vehicles:
		types[v.cfg.id]=true
		check(v.muzzle!=null and v.armour_bodies.size()>=9,"asset and armour")
	check(types.size()==6,"six models")
	var a=scene.vehicles[0]
	var b=scene.vehicles[8]
	a.position=Vector3(500,100,100)
	b.position=Vector3(500,100,200)
	a.rotation.y=0
	b.rotation.y=PI
	await physics_frame
	check(scene.has_los(a,b),"clear LOS")
	var blocker=scene.terrain.box(Vector3(500,102,150),Vector3(20,10,5),Color.GRAY)
	await physics_frame
	check(not scene.has_los(a,b),"building blocks LOS")
	blocker.queue_free()
	for v in scene.vehicles:v.position=Vector3(-600,100,-600)
	a.position=scene.objectives[0].position
	scene.step_objectives(13)
	check(scene.objectives[0].owner==0,"capture")
	check(scene.tickets[1]<300,"ticket bleed")
	for v in scene.vehicles:
		v.position=Vector3(0,100,0)
		v.rotation=Vector3.ZERO
		v.cmd=[1,0,1,1,1,0]
		v.step(.1)
		check(v.speed>0,"accelerates "+v.cfg.id)
		if not v.cfg.turreted:check(absf(v.turret_angle)<=deg_to_rad(v.cfg.traverse_limit_deg),"casemate limit")
		var shell={"ammo":Catalog.read_json("ammunition/pak43_ap.json"),"distance":100.0,"velocity":Vector3.FORWARD*1000,"owner":8 if v.team==0 else 0}
		v.rotation=Vector3.ZERO
		v.hit(shell,v.to_global(Vector3(.8,1.1,3)),Vector3.BACK,"side")
		check(not v.modules.ammo_rack and not v.alive,"module destruction "+v.cfg.id)
	# actual projectile entity spawns with finite velocity (not a hitscan damage call)
	scene.fire(a)
	check(scene.shells.size()==1 and scene.shells[0].velocity.length()>700,"projectile spawn")
	check(scene.tracks.soil(Vector3(0,0,100)).name=="road","road surface")
	check(scene.tracks.soil(Vector3(300,0,25*sin(300.0/180))).name=="riverbed","soft riverbed")
	check(scene.tracks.soil(Vector3(300,0,300)).stiffness<scene.tracks.soil(Vector3(0,0,100)).stiffness,"soil stiffness ordering")
	check(scene.tracks.belt_velocity(4,0,3,-1)==4,"straight belt velocity")
	check(scene.tracks.belt_velocity(0,1,3,-1)==1.5 and scene.tracks.belt_velocity(0,1,3,1)==-1.5,"opposite belts in pivot")
	check(scene.tracks.belt_velocity(4,1,3,1)<scene.tracks.belt_velocity(4,1,3,-1),"right turn inner belt")
	var first=scene.tracks.settlement(0,.08,1,.3)
	var second=scene.tracks.settlement(first,.08,1,.3)
	check(second>first and second<.18,"repeated passage accumulates bounded settlement")
	check(is_equal_approx(second,scene.tracks.settlement(0,.08,2,.3)),"settlement invariant to step splitting")
	check(scene.tracks.settlement(first,.01,0,0)==first,"ruts do not heal without soil model")
	check(scene.tracks.settlement(0,.08,0,1)==0,"no travel no settlement")
	check(scene.tracks.settlement(0,.08,3,1)>scene.tracks.settlement(0,.08,3,0),"slip increases soil remoulding")
	print("VALIDATION failures=",failures)
	scene.queue_free()
	await process_frame
	quit(0 if failures==0 else 1)
