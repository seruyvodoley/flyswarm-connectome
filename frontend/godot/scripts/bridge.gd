extends RefCounted
var tcp=StreamPeerTCP.new()
var buffer=""
var enabled=false
var pending=false
var commands=[]
var last_reply={}
var sent_at=0
var latency_ms=0.0
var tick=0
var responses_received=0
var last_reply_seq=0
var fresh_response=false
var last_valid_commands=[]
var last_response_at_usec=0
var timeout_count=0
var disconnect_count=0
var repeated_command_steps=0
var tick_ms_samples: Array[float]=[]
var latency_ms_samples: Array[float]=[]
var error=""
func connect_backend(port: int):
	enabled=true
	tcp.connect_to_host("127.0.0.1",port)
func poll():
	fresh_response=false
	if not enabled:return
	tcp.poll()
	if tcp.get_status()!=StreamPeerTCP.STATUS_CONNECTED:return
	var n=tcp.get_available_bytes()
	if n>0:
		buffer+=tcp.get_utf8_string(n)
	if buffer.length()>1048576:
		error="oversized backend packet"
		tcp.disconnect_from_host()
		return
	while "\n" in buffer:
		var at=buffer.find("\n")
		var data=JSON.parse_string(buffer.substr(0,at))
		buffer=buffer.substr(at+1)
		if _valid_reply(data):
			commands=data.actions.duplicate(true)
			last_valid_commands=commands.duplicate(true)
			last_reply=data
			last_reply_seq=int(data.seq)
			responses_received+=1
			last_response_at_usec=Time.get_ticks_usec()
			latency_ms=(last_response_at_usec-sent_at)/1000.0
			latency_ms_samples.append(latency_ms)
			if latency_ms_samples.size()>5000:latency_ms_samples.pop_front()
			var neural_ms=float(data.get("tick_ms",0.0))
			tick_ms_samples.append(neural_ms)
			if tick_ms_samples.size()>5000:tick_ms_samples.pop_front()
			pending=false
			fresh_response=true

	# Interactive autonomous battles used to freeze the entire Godot world
	# while the two real MaleCNS batches were computing their next 20 ms tick.
	# On the current CPU a neural reply can take ~60-80 ms, so vehicles were
	# physically advanced only on reply frames and appeared several times
	# slower than the exact same vehicles under Rule AI.
	#
	# For the visual battle only, hold the last motor command while a new neural
	# response is pending. This is ordinary zero-order-hold control: MaleCNS is
	# still frozen and still updates only through the backend, but vehicle/world
	# physics no longer stops between controller updates. Research/training jobs
	# are deliberately excluded so their neural/world stepping semantics remain
	# unchanged and reproducible.
	if (
		not fresh_response
		and pending
		and commands.is_empty()
		and not last_reply.is_empty()
		and last_reply.get("actions",[]).size()==16
		and is_instance_valid(AppState)
		and AppState.session!=null
		and str(AppState.session.mode) in ["battle","demo"]
	):
		commands=last_reply.actions.duplicate(true)

func _valid_reply(data) -> bool:
	if not data is Dictionary:return false
	if int(data.get("seq",-1))!=tick or int(data.get("seq",-1))<=last_reply_seq:return false
	var actions=data.get("actions",[])
	if not actions is Array or actions.size()!=16:return false
	for action in actions:
		if not action is Array or action.size()!=6:return false
		for value in action:
			if not (value is int or value is float) or not is_finite(float(value)):return false
	return true
func request(observations: Array, audio_mode: String):
	if pending or tcp.get_status()!=StreamPeerTCP.STATUS_CONNECTED:return
	tick+=1
	var packet={"version":1,"seq":tick,"audio":audio_mode,"observations":observations}
	tcp.put_data((JSON.stringify(packet)+"\n").to_utf8_buffer())
	sent_at=Time.get_ticks_usec()
	pending=true
func connected() -> bool:
	return tcp.get_status()==StreamPeerTCP.STATUS_CONNECTED and not last_reply.is_empty()
