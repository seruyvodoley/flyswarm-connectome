extends RefCounted

static func penetration(ammo: Dictionary, distance_m: float) -> float:
	var curve=ammo.penetration_mm
	if distance_m<=curve[0][0]: return float(curve[0][1])
	for i in range(1,curve.size()):
		if distance_m<=curve[i][0]:
			return lerpf(curve[i-1][1],curve[i][1],(distance_m-curve[i-1][0])/(curve[i][0]-curve[i-1][0]))
	return float(curve[-1][1])

static func impact(ammo: Dictionary, distance_m: float, direction: Vector3, normal: Vector3, plate: Dictionary) -> Dictionary:
	var cosine=clampf(-direction.normalized().dot(normal.normalized()),0,1)
	var angle=rad_to_deg(acos(cosine))
	var normalized=maxf(0,angle-float(ammo.normalization_deg))
	var effective=float(plate.thickness_mm)/maxf(.05,cos(deg_to_rad(normalized)))
	var capability=penetration(ammo,distance_m)
	return {"angle":angle,"nominal":plate.thickness_mm,"effective":effective,"capability":capability,"penetrated":angle<float(ammo.ricochet_deg) and capability>effective,"ricochet":angle>=float(ammo.ricochet_deg)}
