# Methodology and limits

The primary backend is the existing Godot 4 battle and two independent CPU `FlyBrain(batch=8)` instances. Each connection advances MaleCNS at its native 20 ms timestep. The brain is frozen; the repository's sensory encoder, motor decoder, and explicit objective/gunnery helpers remain part of the controller. Their command changes are recorded separately from raw neural output. Consequently, the result estimates the behavior of this complete controller stack under the listed neural intervention; it does not attribute all behavior to the connectome.

Both teams use the same normalized T-34-85 physics and battle map. BLUE is the evaluated controller and RED is the same Rule AI in every controlled comparison. `--swap` reverses physical start sides while keeping controller identities fixed. Historical mixed-vehicle battles, Open Day, analytical MARL, PPO, and old Python experiments are separate environments and must not be pooled with this dataset.

The current sensory encoder is a sparse experimental visual/audio mapping, not a validated fly retina. DN rate smoothing and the 3D motor mapping are engineering choices. The shuffled condition is a signal-assignment control, not a synaptic rewiring simulation. Conclusions must name these limits.
