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
	while "\n" in buffer:
		var at=buffer.find("\n")
		var data=JSON.parse_string(buffer.substr(0,at))
		buffer=buffer.substr(at+1)
		if data is Dictionary and data.get("seq",-1)==tick and data.get("actions",[]).size()==16:
			commands=data.actions
			last_reply=data
			latency_ms=(Time.get_ticks_usec()-sent_at)/1000.0
			pending=false
func request(observations: Array, audio_mode: String):
	if pending or tcp.get_status()!=StreamPeerTCP.STATUS_CONNECTED:return
	tick+=1
	var packet={"version":1,"seq":tick,"audio":audio_mode,"observations":observations}
	tcp.put_data((JSON.stringify(packet)+"\n").to_utf8_buffer())
	sent_at=Time.get_ticks_usec()
	pending=true
func connected() -> bool:
	return tcp.get_status()==StreamPeerTCP.STATUS_CONNECTED and not last_reply.is_empty()
