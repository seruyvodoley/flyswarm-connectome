extends RefCounted

const Layout=preload("res://scripts/demo/arena_layout.gd")
const CELL=14.0
var grid=AStarGrid2D.new()
var graph=AStar2D.new()
var battle
var ready=false
var build_ms=0.0
var route_ms=0.0
var routes=0
var ray_count=0
var query=PhysicsShapeQueryParameters3D.new()

func configure(world) -> void:
	if ready:return
	battle=world
	var start=Time.get_ticks_usec()
	grid.region=Rect2i(-24,-24,49,49)
	grid.cell_size=Vector2(CELL,CELL)
	grid.diagonal_mode=AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	grid.default_compute_heuristic=AStarGrid2D.HEURISTIC_OCTILE
	grid.default_estimate_heuristic=AStarGrid2D.HEURISTIC_OCTILE
	grid.update()
	var shape=BoxShape3D.new();shape.size=Vector3(9.0,3.0,9.0)
	query.shape=shape;query.collision_mask=8
	for z in range(-24,25):
		for x in range(-24,25):
			var id=Vector2i(x,z);var p=Vector2(x*CELL,z*CELL)
			var h=battle.terrain.height_at(p.x,p.y)
			var grade=Vector2(battle.terrain.height_at(p.x+3,p.y)-battle.terrain.height_at(p.x-3,p.y),battle.terrain.height_at(p.x,p.y+3)-battle.terrain.height_at(p.x,p.y-3)).length()/6.0
			query.transform=Transform3D(Basis.IDENTITY,Vector3(p.x,h+1.6,p.y))
			var blocked=grade>.31 or Layout.building_blocked(p) or not battle.get_world_3d().direct_space_state.intersect_shape(query,1).is_empty()
			grid.set_point_solid(id,blocked)
			grid.set_point_weight_scale(id,1.0+grade*3.0)
	# Cell occupancy alone cannot rule out clipping a thin wall diagonally
	# between two free cells. Validate the full hull-width corridor of every
	# graph edge once; A* can then never select an unchecked corner cut.
	graph.clear()
	for z in range(-24,25):
		for x in range(-24,25):
			var id=Vector2i(x,z)
			if not grid.is_point_solid(id):graph.add_point(key(id),Vector2(id)*CELL,grid.get_point_weight_scale(id))
	for z in range(-24,25):
		for x in range(-24,25):
			var id=Vector2i(x,z)
			if not graph.has_point(key(id)):continue
			for offset in [Vector2i(1,0),Vector2i(0,1),Vector2i(1,1),Vector2i(-1,1)]:
				var next=id+offset
				if not grid.is_in_boundsv(next) or not graph.has_point(key(next)):continue
				if offset.x!=0 and offset.y!=0 and (grid.is_point_solid(id+Vector2i(offset.x,0)) or grid.is_point_solid(id+Vector2i(0,offset.y))):continue
				if drive_clear(point(Vector2(id)*CELL),point(Vector2(next)*CELL)):graph.connect_points(key(id),key(next))
	ready=true;build_ms=(Time.get_ticks_usec()-start)/1000.0

func key(id: Vector2i) -> int:
	return (id.y+24)*49+id.x+24

func closest(p: Vector2) -> Vector2i:
	var origin=Vector2i(roundi(p.x/CELL),roundi(p.y/CELL))
	origin=origin.clamp(grid.region.position,grid.region.end-Vector2i.ONE)
	for radius in range(0,7):
		var best=Vector2i(999,999);var cost=INF
		for z in range(-radius,radius+1):
			for x in range(-radius,radius+1):
				var id=origin+Vector2i(x,z)
				if grid.is_in_boundsv(id) and not grid.is_point_solid(id):
					var d=p.distance_squared_to(Vector2(id)*CELL)
					if d<cost:best=id;cost=d
		if cost<INF:return best
	return origin

func passable(p: Vector2) -> bool:
	var id=Vector2i(roundi(p.x/CELL),roundi(p.y/CELL))
	return grid.is_in_boundsv(id) and not grid.is_point_solid(id) and Vector2(id).distance_to(p/CELL)<.8

func line_clear(a: Vector3,b: Vector3, exclude: Array[RID]=[]) -> bool:
	ray_count+=1
	var hit=battle.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(a,b,1,exclude))
	return hit.is_empty()

func drive_clear(a: Vector3,b: Vector3) -> bool:
	var direction=b-a;direction.y=0
	if direction.length()<.1:return true
	var side=direction.normalized().cross(Vector3.UP)*3.2
	for offset in [Vector3.ZERO,side,-side]:
		var first=a+offset+Vector3.UP*1.2
		var last=b+offset+Vector3.UP*1.2
		if not line_clear(first,last):return false
	return true

func path(a: Vector3,b: Vector3) -> PackedVector3Array:
	var start=Time.get_ticks_usec()
	var points=PackedVector3Array()
	if not ready:return points
	var start_id=key(closest(Vector2(a.x,a.z)));var end_id=key(closest(Vector2(b.x,b.z)))
	if not graph.has_point(start_id) or not graph.has_point(end_id):return points
	var ids=graph.get_id_path(start_id,end_id)
	for id in ids:
		var position=graph.get_point_position(id)
		var x=position.x;var z=position.y
		points.append(Vector3(x,battle.terrain.height_at(x,z)+.1,z))
	# Keep the route inside the collision-tested graph. No untested diagonal
	# smoothing through cottage corners; local sensors handle dynamic debris.
	route_ms+=(Time.get_ticks_usec()-start)/1000.0;routes+=1
	return points

func point(p: Vector2) -> Vector3:
	return Vector3(p.x,battle.terrain.height_at(p.x,p.y)+.1,p.y)
