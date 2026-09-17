"""Vehicle/role conditioning for FlySwarm MARL.

These are engineered tactical priors for experiments, not claims that MaleCNS
contains tank doctrine and not a historical reconstruction of national doctrine.
The frozen connectome never receives these values; only the external policy does.
"""
from __future__ import annotations
from functools import lru_cache
import numpy as np
from flyswarm.catalog import vehicle

DEFAULT_COMPOSITION=(
    "panther_g","panther_g","panther_g","panther_g",
    "tiger_i","tiger_i","jagdpanther","jagdpanther",
    "t34_85","t34_85","t34_85","t34_85",
    "is2_1944","is2_1944","su100","su100",
)

# Small priors only. Team/objective reward remains dominant.
PROFILES={
    "panther_g": dict(tactical_role="medium_flanker", aggression=.62, objective_bias=.85, standoff_m=160., effective_range_m=650., damage_per_hit=.34),
    "tiger_i": dict(tactical_role="heavy_anchor", aggression=.68, objective_bias=.95, standoff_m=90., effective_range_m=520., damage_per_hit=.38),
    "jagdpanther": dict(tactical_role="td_overwatch", aggression=.45, objective_bias=.50, standoff_m=260., effective_range_m=800., damage_per_hit=.46),
    "t34_85": dict(tactical_role="medium_assault", aggression=.82, objective_bias=1.00, standoff_m=80., effective_range_m=450., damage_per_hit=.31),
    "is2_1944": dict(tactical_role="heavy_breakthrough", aggression=.74, objective_bias=.95, standoff_m=100., effective_range_m=500., damage_per_hit=.52),
    "su100": dict(tactical_role="td_support", aggression=.52, objective_bias=.55, standoff_m=240., effective_range_m=750., damage_per_hit=.44),
}
ROLE_FEATURE_DIM=8

@lru_cache(None)
def vehicle_profile(identifier: str) -> dict:
    obj=vehicle(identifier)
    params=obj["parameters"]
    role=str(obj.get("role","medium"))
    nation=str(obj.get("nation","germany" if identifier in {"panther_g","tiger_i","jagdpanther"} else "ussr"))
    prior=dict(PROFILES.get(identifier,{}))
    prior.update({
        "vehicle_id":identifier,
        "vehicle_class":role,
        "nation":nation,
        "max_speed_m_s":float(params["max_speed_kph"])/3.6,
        "reverse_m_s":float(params.get("reverse_kph",4.0))/3.6,
        "turn_rate_rad_s":np.deg2rad(float(params.get("turn_rate_deg_s",25.0))),
        "reload_s":float(params["reload_s"]),
        "accel_m_s2":float(np.clip((float(params["engine_kw"])*1000.0/max(1.0,float(params["mass_kg"]))) * .42, 2.0, 6.5)),
    })
    prior.setdefault("tactical_role",role)
    prior.setdefault("aggression",.6)
    prior.setdefault("objective_bias",.8)
    prior.setdefault("standoff_m",120.)
    prior.setdefault("effective_range_m",550.)
    prior.setdefault("damage_per_hit",.34)
    return prior

def role_features(identifier: str) -> np.ndarray:
    """8 policy-only conditioning features: class, nation, tactical priors."""
    p=vehicle_profile(identifier)
    classes=("medium","heavy","tank_destroyer")
    class_onehot=[1.0 if p["vehicle_class"]==name else 0.0 for name in classes]
    nation_onehot=[1.0 if p["nation"]==name else 0.0 for name in ("germany","ussr")]
    return np.asarray(class_onehot+nation_onehot+[
        float(p["aggression"]),
        float(p["objective_bias"]),
        float(p["standoff_m"])/300.0,
    ],dtype=np.float32)
