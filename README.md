# COIN-D6 lidar — ROS 2 driver

ROS 2 (Jazzy) driver for the **COIN-D6** 2D triangulation lidar (Tucker Innovations / Guoke
Optoelectronics, vendor package name `m1ct_d2`). It reads the lidar through the bundled
CH340 USB-serial adapter and publishes `sensor_msgs/LaserScan` on `/scan`.

This repo is a colcon workspace: the package is `src/m1ct_d2`, a fixed-up copy of the vendor
driver (`vendor/m1ct_d4_ros2_v16.zip`). The first commit is the unmodified vendor code, so
`git diff <first-commit>` shows every change.

Tested on Ubuntu 24.04 + ROS 2 Jazzy: 10 Hz, ~400 points per revolution, 230400 baud.

## Quick start

```bash
# 1. once: udev rule -> /dev/coin_d6 on whatever USB port the adapter is plugged into
sudo cp src/m1ct_d2/99-coin-d6.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
sudo usermod -aG dialout $USER     # serial access, if not already in dialout (re-login)

# 2. build
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash

# 3. run + visualize
ros2 launch m1ct_d2 coin_d6.launch.py rviz:=true
```

Without RViz (e.g. on the robot): `ros2 launch m1ct_d2 coin_d6.launch.py`.
Check it's running: `ros2 topic hz /scan` should show about 10 Hz.

## udev rule

`src/m1ct_d2/99-coin-d6.rules` matches the adapter by USB vendor/product ID (`1a86:7523`)
and creates `/dev/coin_d6`, so it doesn't matter which port you use or what `ttyUSB*` number
the device gets. Check it with `ls -l /dev/coin_d6`.

Limitation: the CH340 has no serial number, so **any** CH340 device (many Arduino clones,
for example) also gets the symlink. If you have more than one plugged in, pin the lidar to
one physical port instead. Get the port path:

```bash
udevadm info -q property -n /dev/ttyUSB0 | grep ID_PATH=
```

and swap the `ATTRS{idVendor}`/`ATTRS{idProduct}` match for `ENV{ID_PATH}=="<that value>"`
in the rule. The trade-off is that the lidar then has to stay in that port.

## Launch arguments

| arg        | default        | |
|------------|----------------|---|
| `port`     | `/dev/coin_d6` | serial device |
| `frame_id` | `laser_link`   | `header.frame_id` of the scans |
| `rviz`     | `false`        | also start RViz, plus a static identity TF `base_link -> frame_id` so RViz has a TF tree |

On a robot, publish `base_link -> laser_link` from your URDF / robot_state_publisher and
leave `rviz:=false`. Otherwise the two transforms would conflict.

## Node interface

Node `m1ct_d2`. Parameters (defaults in `src/m1ct_d2/params/m1ct_d2.yaml`):

| parameter  | default        | |
|------------|----------------|---|
| `port`     | `/dev/coin_d6` | |
| `frame_id` | `laser_link`   | |
| `version`  | `4`            | protocol variant; 4 = D6/D2 (230400 baud, intensities). The baud rate comes from this. |

| topic           | type                     | |
|-----------------|--------------------------|---|
| `/scan`         | `sensor_msgs/LaserScan`  | published, angles 0..2π CCW, range 0.10–10 m |
| `/lsd_error`    | `std_msgs/String`        | published on errors (port can't be opened, motor stuck, rotation frequency out of range, blocked) |
| `/lidar_status` | `std_msgs/UInt16`        | subscribed commands: 1 start, 2 stop, 3/4 high/low exposure, 5 clear error, 6/7 high/low speed |

Running the node directly: `ros2 run m1ct_d2 m1ct_d2 --ros-args -p port:=/dev/ttyUSB0`.
The vendor's robot-vacuum CLI options (`-cover`, `-angle`, `-diameter`, …, see
`src/main.cpp`) still work, but only **before** `--ros-args`.

## Known limitations

- **Points per scan vary** (about 398–405) because the motor speed drifts slightly.
  RViz and Nav2 costmaps don't mind, but slam_toolbox/Karto expects a fixed count and may
  reject scans. The fix is to bin the points into a fixed number of angle steps; it isn't
  implemented yet.
- **Stop command:** on our unit, `/lidar_status` = 2 (and the vendor stop byte sequence)
  does not stop the data stream.
- **No reconnect:** if the USB cable is unplugged while running, the node publishes errors
  on `/lsd_error` but never reopens the port. Restart it.
- Scan angles assume evenly spaced samples starting at the sync point (vendor behaviour).
  Measured raw angles are within about 1° of that.
- Check that the sensor's forward direction lines up with +x (red axis in RViz) for your
  mounting. If it doesn't, rotate it in the TF.

## Changes from the vendor driver

See the commit messages for details. In short:

- builds on Jazzy (`declare_parameter` defaults, missing `std_msgs` dependency)
- one node instead of two, so launch-file renaming/remapping works
- the parameter YAML is actually applied (its node name never matched before)
- the vendor's `getopt` no longer reorders `--ros-args`, which used to scramble launch arguments
- timestamps are ROS (wall-clock) time instead of seconds since boot
- mutex double-unlock and lock-leak fixes; `angle_max` matches the number of ranges
- udev rule, launch file and RViz config

## Layout

```
src/m1ct_d2/            ROS 2 package
  99-coin-d6.rules      udev rule
  launch/ params/ rviz/
  src/ include/         vendor driver sources (protocol parsing, serial port, filter)
vendor/                 original archives + user guide (Chinese PDF), unmodified
  cspc_lidar_sdk_ros1_0802.tar.gz   ROS 1 driver, same core code
```

## License

The vendor code came without a license (`package.xml` says `TODO`). Check with the vendor
before publishing this repo publicly.
