# Dual MaleCNS interface

Start `./tools/run run-brains`, then `./tools/run run-battle`.
Server listens on 127.0.0.1:8765 only; configure both with --port if needed.
No secrets or network services required. Missing MaleCNS data causes a clear
error; this server does not download it. CPU, two separate FlyBrain(batch=8),
seeds s and s+1000. In this environment n=166700 each, 2667200 logical neurons.
Weights and voltage arrays must not share memory. Wiring is never modified.

Godot packet {version:1, seq, audio, observations:[16 ordered rows]} includes
relative bearing/elevation, angular size, positive looming derivative, visible,
alive, six proprioceptive scalars and transforms. Absolute transforms are used
only for audio distance; they do not enter the visual encoder or policy.
Vehicle ID selects a head, not a role command. Teacher actions are present for
imitation collection; evaluation ignores them. No armour/reload specification
is an input feature. Server rejects duplicate sequence IDs, invalid sizes,
nonfinite floats and oversized/incomplete packets (1 MiB limit).

LC10a bilateral stimulation uses relative angular error, LC9 pursuit uses
visibility/centredness, LC4/LPLC2 receive looming. Natural readouts are DNp09 L/R,
DNa02 L/R, DNp01 and wing counts, exponentially smoothed (0.9 previous + 0.1 new).
This encoder is experimental; vertical vision has no validated neural channel.

Wing motor counts from the PREVIOUS step are attenuated by 1/(1+(d/250)^2),
scaled by a fixed provisional gain .08 and capped at .8 into JO-A/JO-B.
Self/dead sender/dead receiver links excluded; no_audio/team_audio/all_audio.
Gain is not the calibrated gain from the 2D scientific experiment: keep results
separate. The 2D code and its calibration remain intact.

BIOLOGICAL_BASELINE uses natural pursuit/steering with explicit rule-based
fire/elevation auxiliary control. TRAINED_ADAPTER uses a frozen compact ridge
head. CONNECTOME_ONLY inputs six log-scaled traces; the optional
CONNECTOME_PLUS_PROPRIOCEPTION adds six permitted internal measurements.
Neither mode claims a full biological retina or an emulation of consciousness.

Renderer never blocks on a synchronous socket read. One outstanding request
limits queue growth. Initial backend wait times out after 180 s. An outstanding reply times out after 10 s and exits with failure; reconnect
recovery is not implemented.
