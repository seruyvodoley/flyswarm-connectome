extends RefCounted

# Shared metre-scale geometry for the Open Day renderer, navigation and checks.
# Scientific maps do not use this layout.
const SIZE=700.0
const BUILDINGS=[
	[-54.0,-66.0,0.0,true],[-12.0,-66.0,PI,false],[32.0,-62.0,0.0,false],
	[70.0,-60.0,PI,true],[-66.0,0.0,PI/2.0,false],[0.0,0.0,0.0,true],
	[64.0,0.0,-PI/2.0,false],[-52.0,64.0,PI,true],[-8.0,65.0,0.0,false],[42.0,62.0,PI,false]
]
const ROCKS=[Vector2(-180,-58),Vector2(-142,58),Vector2(-215,82),Vector2(125,-105),Vector2(190,-38),Vector2(170,96),Vector2(102,160),Vector2(-116,-154),Vector2(225,160),Vector2(-235,-160)]
const ROUTES=[
	[Vector2(-24,-205),Vector2(-100,-140),Vector2(-142,-55),Vector2(-140,65),Vector2(-95,145),Vector2(24,205)],
	[Vector2(-24,-205),Vector2(-28,-110),Vector2(-29,-28),Vector2(-28,28),Vector2(18,112),Vector2(24,205)],
	[Vector2(-24,-205),Vector2(98,-148),Vector2(142,-62),Vector2(143,65),Vector2(102,150),Vector2(24,205)]
]

static func spawn(team: int, seed_value: int) -> Vector2:
	var offsets=[-36.0,-24.0,24.0,36.0]
	var x=float(offsets[posmod(seed_value,offsets.size())])
	return Vector2(x,-205.0) if team==0 else Vector2(-x,205.0)

static func route_distance(p: Vector2) -> float:
	var best=INF
	for route in ROUTES:
		for i in range(route.size()-1):
			best=minf(best,p.distance_to(Geometry2D.get_closest_point_to_segment(p,route[i],route[i+1])))
	return best

static func building_blocked(p: Vector2, margin: float=5.0) -> bool:
	for building in BUILDINGS:
		var local=(p-Vector2(building[0],building[1])).rotated(float(building[2]))
		local-=Vector2(3.3,-.4) if building[3] else Vector2(.21,.14)
		var half=Vector2(6.7,3.4) if building[3] else Vector2(3.8,3.3)
		if absf(local.x)<half.x+margin and absf(local.y)<half.y+margin:return true
	return false
