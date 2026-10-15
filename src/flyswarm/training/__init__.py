"""Training seeds must be disjoint from held-out evaluation seeds."""
TRAIN_SEEDS=(100,101,102)
TEST_SEEDS=(200,201,202)
assert set(TRAIN_SEEDS).isdisjoint(TEST_SEEDS)
CURRICULUM={0:'mobility',1:'waypoint',2:'obstacles',3:'turret_tracking',4:'stationary_gunnery',5:'moving_gunnery',6:'duel',7:'capture',8:'mixed_battle'}
# Only stage 3 imitation collection is currently validated end-to-end.
