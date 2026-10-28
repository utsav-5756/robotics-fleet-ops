# Simulation timestamp and coordinate frame.
std_msgs/Header header

# Stable robot identifier, for example robot_01.
string robot_id

# Monotonically increasing sample number within this simulator process.
uint64 sequence

# Repeatable scenario identity derived from scenario and seed.
string run_id

# Selected deterministic fault scenario.
string scenario

# Seed used to generate repeatable baseline state.
uint32 seed

# Position in meters and heading in radians.
geometry_msgs/Pose2D pose

# Battery level in percent, from 0 through 100.
float32 battery_percentage

# Current mission state: EN_ROUTE, RETURNING, BLOCKED, STALLED, or UNKNOWN.
string mission_state

# Supervisor-observed connectivity; this is an aggregate simulation signal.
bool connected

# Deterministic fault codes for the current robot state.
string[] fault_codes

# Synthetic range reading in meters. Normal values are between 0.1 and 10.0.
float32 sensor_range_m
