"""Versioned NDJSON, localhost only. World transforms are used ONLY for audio."""
import json,math
MAX_LINE=1048576

def validate(packet):
    if packet.get('version')!=1 or not isinstance(packet.get('seq'),int):raise ValueError('Protocol version/sequence')
    obs=packet.get('observations',[])
    if len(obs)!=16 or [o.get('id') for o in obs]!=list(range(16)):raise ValueError('Ordered BLUE 0..7 RED 8..15 required')
    for o in obs:
        for field,n in [('position',3),('proprio',6),('teacher',6)]:
            if len(o.get(field,[]))!=n or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in o[field]):raise ValueError(field)
        for field in ['bearing','elevation','looming','angular_size']:
            if not math.isfinite(o[field]):raise ValueError(field)
    return packet

def encode(packet):return (json.dumps(packet,allow_nan=False,separators=(',',':'))+'\n').encode()

def read(stream):
    line=stream.readline(MAX_LINE+1)
    if not line:return None
    if len(line)>MAX_LINE or not line.endswith(b'\n'):raise ValueError('Oversized or incomplete packet')
    return validate(json.loads(line))
