"""Feature encoder and causal wing-song topology. No role labels in policy input."""
import numpy as np
MODES=('no_audio','team_audio','all_audio')

def audio_signal(song,positions,alive,mode):
    if mode not in MODES:raise ValueError(mode)
    p=np.asarray(positions,dtype=float); live=np.asarray(alive,dtype=bool)
    if p.shape!=(16,3) or live.shape!=(16,):raise ValueError('Expected 16 world transforms')
    distance=np.linalg.norm(p[:,None]-p[None,:],axis=-1)
    links=~np.eye(16,dtype=bool)
    links &= live[:,None]&live[None,:]
    if mode=='no_audio':links[:]=False
    if mode=='team_audio':links &= (np.arange(16)//8)[:,None]==(np.arange(16)//8)[None,:]
    return np.minimum(.8, np.sum(links*np.asarray(song)[None,:]/(1+(distance/250)**2),axis=1)*.08)

def visual(observations):
    bearing=np.array([o['bearing'] for o in observations])
    visible=np.array([o['visible'] and o['alive'] for o in observations])
    loom=np.array([o['looming'] for o in observations])
    left=.8*visible*np.clip(-bearing/.4,0,1)
    right=.8*visible*np.clip(bearing/.4,0,1)
    centre=.5*visible*(1-np.clip(abs(bearing)/1.7,0,1))
    return {'lc10_l':left,'lc10_r':right,'lc9_l':centre+left*.25,'lc9_r':centre+right*.25,'loom':np.clip(loom*4,0,.8)}
