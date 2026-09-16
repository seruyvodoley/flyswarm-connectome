extends RefCounted
class_name SessionConfig
var mode="battle"
var map="krasny_valley"
var map_seed=1944
var battle_seed=200
var blue_controller="rule"
var red_controller="rule"
var blue_policy=""
var red_policy=""
var physics_mode="historical"
var audio_mode="no_audio"
var vehicle_composition="mixed_1944"
var research_experiment="communication"
var render_mode="visual"
var replay_path=""
var training_vehicle="tiger_i"
var target_vehicle="t34_85"
var training_task="turret_tracking"
var adapter="vehicle"
var episodes=1
var validation_seed=200
var seed_count=1
var seconds=60.0
var swap=false
var record=true
var range_distance=500
var target_angle=0
var range_mode="gunnery"
var output=""
var host="127.0.0.1"
var port=8765
func needs_brain() -> bool:
	return mode!="range" and mode!="replay" and (blue_controller!="rule" or red_controller!="rule")
func as_dict() -> Dictionary:
	var result={}
	for property in get_property_list():
		if property.usage & PROPERTY_USAGE_SCRIPT_VARIABLE:result[property.name]=get(property.name)
	return result
func validate() -> String:
	if seconds<=0:return "Duration must be positive."
	if mode=="training" and battle_seed==validation_seed:return "Training and validation seeds must differ."
	for team in ["blue","red"]:
		if get(team+"_controller")=="adapter" and not FileAccess.file_exists(get(team+"_policy")):
			return team.to_upper()+": select an existing .npz policy."
	if mode=="replay" and not FileAccess.file_exists(replay_path):return "Replay file is missing."
	return ""
func cli_args() -> PackedStringArray:
	var args=PackedStringArray(["--seed",str(map_seed),"--battle-seed",str(battle_seed),"--seconds",str(seconds),"--audio",audio_mode])
	if needs_brain():args.append_array(["--connect","--port",str(port)])
	if physics_mode=="normalized":args.append("--normalized")
	if swap:args.append("--swap")
	if vehicle_composition!="mixed_1944":args.append_array(["--mirror",vehicle_composition])
	if mode=="range":args.append("--range")
	if map=="training_range":args.append("--training")
	if mode=="replay":args.append_array(["--replay",replay_path])
	if output!="":args.append_array(["--record",output])
	return args
