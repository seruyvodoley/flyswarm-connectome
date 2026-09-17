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
var error=""
func connect_backend(port: int):
	enabled=true
	tcp.connect_to_host("127.0.0.1",port)
func poll():
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
	var received_fresh=false
	while "\n" in buffer:
		var at=buffer.find("\n")
		var data=JSON.parse_string(buffer.substr(0,at))
		buffer=buffer.substr(at+1)
		if data is Dictionary and data.get("seq",-1)==tick and data.get("actions",[]).size()==16:
			commands=data.actions
			last_reply=data
			latency_ms=(Time.get_ticks_usec()-sent_at)/1000.0
			pending=false
			received_fresh=true

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
		not received_fresh
		and pending
		and commands.is_empty()
		and not last_reply.is_empty()
		and last_reply.get("actions",[]).size()==16
		and is_instance_valid(AppState)
		and AppState.session!=null
		and str(AppState.session.mode)=="battle"
	):
		commands=last_reply.actions.duplicate(true)
func request(observations: Array, audio_mode: String):
	if pending or tcp.get_status()!=StreamPeerTCP.STATUS_CONNECTED:return
	tick+=1
	var packet={"version":1,"seq":tick,"audio":audio_mode,"observations":observations}
	tcp.put_data((JSON.stringify(packet)+"\n").to_utf8_buffer())
	sent_at=Time.get_ticks_usec()
	pending=true
func connected() -> bool:
	return tcp.get_status()==StreamPeerTCP.STATUS_CONNECTED and not last_reply.is_empty()
