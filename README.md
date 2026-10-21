# COIN-D6 lidar — ROS 2 driver

ROS 2 (Jazzy) driver for the **COIN-D6** 360° dToF 2D lidar (Guoke Optoelectronics / CSPC,
also sold by XTARK and WitMotion). It reads the sensor through the bundled CH340 USB-serial
adapter and publishes `sensor_msgs/LaserScan` on `/scan`.

| | |
|---|---|
| Range | 0.05–12 m (vendor), the driver publishes 0.10–10 m |
| Scan | 360°, ~400 points per revolution (0.9°), 10 Hz |
| Interface | UART 230400 8N1, 3.3 V logic, 5 V supply, USB via CH340 (`1a86:7523`) |
| Frame | `laser_link`: +x = towards the single mounting ear, z up, angles counter-clockwise |

**Full documentation: [docs/COIN-D6_ROS2_Guide.md](docs/COIN-D6_ROS2_Guide.md)**, covering
specs (vendor vs. measured), wiring, mounting and URDF, the ROS interface, the serial
protocol and troubleshooting.

## Quick start

```bash
# once: serial access + stable /dev/coin_d6 on any USB port
sudo usermod -aG dialout $USER     # then log out and back in
sudo cp src/m1ct_d2/99-coin-d6.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger

# build
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash

# run + visualize
ros2 launch m1ct_d2 coin_d6.launch.py rviz:=true
```

On a robot, leave out `rviz:=true` and publish `base_link -> laser_link` from your URDF.
Check it's running with `ros2 topic hz /scan`, which should show about 10 Hz.

## Layout

```
src/m1ct_d2/            ROS 2 package (fixed-up vendor driver)
  99-coin-d6.rules      udev rule
  launch/ params/ rviz/
  src/ include/         driver sources (protocol parsing, serial port, filter)
docs/                   driver guide
vendor/                 original vendor driver archives (ROS 2 + ROS 1), unmodified
```

This repo is a colcon workspace. The first commit is the unmodified vendor driver, so
`git log -p` shows every change made to it.

## License

MIT, see [LICENSE](LICENSE). The vendor driver code was distributed without a license
statement.
