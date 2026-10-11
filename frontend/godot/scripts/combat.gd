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
	var nominal=float(plate.thickness_mm)
	var calibre=float(ammo.get("calibre_mm",0.0))
	# Calibre overmatch reduces the likelihood of a shallow-angle bounce. This
	# is a bounded approximation, not a reproduction of a proprietary solver.
	var overmatch=calibre/maxf(1.0,nominal)
	var normalization=float(ammo.get("normalization_deg",0.0))*clampf(overmatch,.5,2.0)
	var normalized=maxf(0.0,angle-normalization)
	var effective=nominal/maxf(.05,cos(deg_to_rad(normalized)))
	var capability=penetration(ammo,distance_m)
	var ricochet_limit=float(ammo.get("ricochet_deg",72.0))
	if overmatch>=3.0:ricochet_limit=90.0
	elif overmatch>=2.0:ricochet_limit=minf(89.0,ricochet_limit+10.0)
	var bounced=angle>=ricochet_limit
	return {"angle":angle,"nominal":nominal,"effective":effective,"capability":capability,"remaining_penetration_mm":maxf(0.0,capability-effective),"penetrated":not bounced and capability>effective,"ricochet":bounced}
