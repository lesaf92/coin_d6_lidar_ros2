# COIN-D6 lidar: ROS 2 driver guide

Reference for using the COIN-D6 360° 2D lidar with the `m1ct_d2` ROS 2 driver in this repo:
specs, wiring, mounting and frames, the ROS interface, the serial protocol, and
troubleshooting.

**How to read the numbers.** The vendor documentation is incomplete and sometimes contradicts
the hardware (see [Vendor docs vs. reality](#8-vendor-docs-vs-reality)). Every value below is
labelled:

- **vendor**: taken from the vendor spec sheet or manuals, not checked by us
- **measured**: observed on our unit with this driver (Ubuntu 24.04, ROS 2 Jazzy, the CH340
  USB adapter that ships with the sensor, indoor room)

Contents

1. [The sensor](#1-the-sensor)
2. [Specifications](#2-specifications)
3. [Wiring and power](#3-wiring-and-power)
4. [Mounting and coordinate frames](#4-mounting-and-coordinate-frames)
5. [Setup](#5-setup)
6. [ROS interface](#6-ros-interface)
7. [Serial protocol](#7-serial-protocol)
8. [Vendor docs vs. reality](#8-vendor-docs-vs-reality)
9. [Troubleshooting](#9-troubleshooting)
10. [Limitations and ideas](#10-limitations-and-ideas)
11. [Vendor resources](#11-vendor-resources)
12. [Changes from the vendor driver](#12-changes-from-the-vendor-driver)

---

## 1. The sensor

The COIN-D6 (Guoke Optoelectronics / CSPC, sold among others by XTARK/Tucker Innovations and
WitMotion) is a small 360° single-line lidar. It measures distance by **direct time of flight
(dToF)** with a coaxial optical design. The rotating ranging core gets power wirelessly and
sends its data back optically, so there is no slip ring. It talks UART at 230400 baud. The
bundled CH340 adapter turns that into a USB serial port.

The ROS 2 driver (`src/m1ct_d2`) reads that stream and publishes one
`sensor_msgs/LaserScan` per revolution on `/scan`.

## 2. Specifications

| | vendor | measured |
|---|---|---|
| Ranging principle | dToF, 905 nm laser (890–920 nm) | — |
| Laser safety | Class 1 (IEC 60825-1:2014 / EN 60825-1:2014+A11:2021, SGS test report for COIN-D6/D6A) | — |
| Range, 90 % reflectivity | 0.05–12 m (10 m typical) | longest return seen indoors: 4.4 m (room-limited, max range not tested) |
| Range, 10 % reflectivity | 0.05–10 m (8 m typical) | — |
| Accuracy | ±10 mm (0.05–1 m); ±30 mm typ / ±40 mm max (> 1 m) | not measured |
| Field of view | 360° | 360° |
| Angular resolution | 0.9° | 0.887–0.905° (varies with motor speed) |
| Points per revolution | ~400 (4000 Hz / 10 Hz) | 397–405, mean 400 |
| Sample rate | 4000 Hz | 4018 samples/s |
| Scan rate | 10 Hz typical, 15 Hz max; closed-loop speed control fixed at 10 Hz | 10.0 Hz (scan-frequency field reads 100–101, i.e. 10.0–10.1 Hz) |
| Beam pitch (tilt of the scan plane) | 0–2° | — |
| Ambient light immunity | 60 klx | — |
| Intensity | 8-bit echo strength + high-reflectivity flag | 4–255 seen |
| Supply | 5 V DC (4.5–5.5 V), ripple < 100 mV recommended | runs from a laptop USB port via the bundled adapter |
| Current | 240 mA typical (200–500 mA) at 5 V, 800 mA peak | — |
| Power | 1.2 W typical, 1.6 W max | — |
| Motor | brushless, > 10 000 h life | — |
| Interface | UART 230400 baud, 8N1, 3.3 V LVTTL | 230400 8N1 |
| Operating / storage temperature | −10…50 °C / −30…70 °C | — |
| Protection | IPX4 | — |
| Weight | 40 g without cable | — |
| Size (L × W × H) | 52.7 × 45.2 × 34.4 mm (with mounting ears) | — |
| Time to first scan | — | 1.3 s after the node starts |

What the driver publishes: `range_min` = 0.10 m and `range_max` = 10.0 m (both hard-coded),
so returns between 0.05 and 0.10 m and beyond 10 m are treated as invalid by consumers.

## 3. Wiring and power

The sensor has a 4-pin, 1.5 mm pitch connector. In the vendor drawing, looking at the
connector, the pins are labelled (left to right):

```
 TXD  RXD  GND  VCC
```

TXD/RXD are named from the lidar's side, so cross them to your UART: lidar TXD to host RX,
lidar RXD to host TX.

- **Logic level is 3.3 V** (vendor: input high max 3.6 V). Never connect a 5 V UART directly.
  A Raspberry Pi / Jetson 3.3 V UART is fine.
- **Don't trust the wire colours.** The vendor documents contradict each other: one says
  yellow = 5 V, white = GND, red = TXD, black = RXD, while the spec drawing shows red = VCC.
  Note that red may be a *data* line. Check the connector labels or measure with a
  multimeter.
- With the bundled adapter it is plug and play: a CH340 USB-serial chip (USB ID `1a86:7523`)
  that also supplies the 5 V.
- Power: 5 V, up to 800 mA peak (vendor). A standard USB 2.0 port is only rated for 500 mA.
  It works from a laptop port for us. If it browns out (resets, or no data after spin-up),
  use a powered hub or a separate 5 V supply.

## 4. Mounting and coordinate frames

### Native sensor convention (vendor)

Left-handed: the origin is the rotation axis of the ranging core and the angle **increases
clockwise** (seen from above), starting from the **zero direction, which points towards the
single mounting ear** (the one opposite the pair of side ears).

### What the driver publishes: `laser_link` (ROS REP-103)

The driver reverses the sample order, so the published scan is a normal right-handed ROS
frame:

```
                 +x  (sensor 0°, towards the single ear)
                  ^
                  |
                 (o)          single mounting ear
            +-----------+
            |    ___    |
   +y <-----|   ( + )   |     + = rotation axis = laser_link origin
            |    ---    |     z points up, out of the dome
         (o)+-----------+(o)  side mounting ears
```

- `angle_min` = 0 points along +x, and angles increase **counter-clockwise** up to
  `angle_max` ≈ 2π − one step.
- A point at sensor angle θ (clockwise) appears at ROS angle φ = −θ (mod 2π). For example,
  something at the sensor's 90° (to the right) shows up at φ = 270°, i.e. on −y.
- The output assumes evenly spaced samples starting at the sync point. On our unit the raw
  angle of the sync point is about −0.5°, so the published angles are within about 1° of
  the true ones.
- **Check it on your unit** (we haven't yet): put an object about 30 cm in front of the
  single ear. In RViz (`rviz:=true`) it should appear on the red (+x) axis.

### Dimensions for the URDF

| | value | source |
|---|---|---|
| Laser plane height above the bottom mounting plane | 26.9 mm | vendor |
| Total height | 34.4 mm | vendor |
| Body footprint | 38.2 × 38.2 mm | vendor drawing |
| Dome diameter | 35.3 mm | vendor drawing |
| Mounting holes | 3 × Ø3.2 mm (M3), ears R4.3 mm | vendor drawing |
| Side holes: spacing | 44.0 mm | vendor drawing |
| Single-ear hole to side-hole line | 30.8 mm | vendor drawing |
| Hole positions relative to the rotation axis (x forward, y left) | single ear (+21.8, 0); side ears (−9.0, ±22.0) mm | derived from the drawing (assumes the axis is at the body centre); measure before drilling |

URDF snippet (sensor upright, base plane `h` metres above `base_link`):

```xml
<link name="laser_link"/>
<joint name="laser_joint" type="fixed">
  <parent link="base_link"/>
  <child link="laser_link"/>
  <!-- z = h + 0.0269 (laser plane); rotate yaw if the single ear doesn't face +x -->
  <origin xyz="0.10 0.0 0.0869" rpy="0 0 0"/>
</joint>
```

Or without a URDF:

```bash
ros2 run tf2_ros static_transform_publisher --x 0.10 --z 0.0869 \
  --frame-id base_link --child-frame-id laser_link
```

If you mount it upside down, use `rpy="3.14159 0 0"`.

Keep the optical window clean and unobstructed all the way around. The vendor says to ask
them before putting it behind any cover, even a transparent one.

## 5. Setup

```bash
# serial access (log out and back in afterwards)
sudo usermod -aG dialout $USER

# udev: stable /dev/coin_d6 on any USB port
sudo cp src/m1ct_d2/99-coin-d6.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
ls -l /dev/coin_d6            # -> ttyUSB*

# build
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash

# run
ros2 launch m1ct_d2 coin_d6.launch.py              # driver only
ros2 launch m1ct_d2 coin_d6.launch.py rviz:=true   # + RViz + identity TF base_link->laser_link
```

The udev rule matches the CH340's USB ID. That chip has no serial number, so any other CH340
device (Arduino clones, for example) also matches. If you need two at once, pin the lidar to
a physical port with `ENV{ID_PATH}=="..."` (get the value from
`udevadm info -q property -n /dev/ttyUSB0 | grep ID_PATH=`). The lidar then has to stay in
that port.

## 6. ROS interface

### Launch arguments (`coin_d6.launch.py`)

| arg | default | |
|---|---|---|
| `port` | `/dev/coin_d6` | serial device |
| `frame_id` | `laser_link` | `header.frame_id` |
| `rviz` | `false` | also start RViz plus a static identity TF `base_link -> frame_id`. Don't use it alongside a URDF that already publishes that transform. |

### Node `m1ct_d2`

Parameters (`params/m1ct_d2.yaml`):

| parameter | default | |
|---|---|---|
| `port` | `/dev/coin_d6` | |
| `frame_id` | `laser_link` | |
| `version` | `4` | protocol variant. 4 = COIN-D6 / M1CT-D2: 230400 baud, 3-byte samples with intensity. The baud rate follows from it. |

Topics:

| topic | type | direction | |
|---|---|---|---|
| `/scan` | `sensor_msgs/LaserScan` | pub | one message per revolution, about 10 Hz, reliable QoS, depth 1 |
| `/lsd_error` | `std_msgs/String` | pub | error states, see below |
| `/lidar_status` | `std_msgs/UInt16` | sub | commands, see below |

### `/scan` contents

| field | value |
|---|---|
| `header.stamp` | wall-clock (ROS) time at which the driver received the start of that revolution, so it includes a few ms of serial/USB latency |
| `angle_min`, `angle_max`, `angle_increment` | 0, (n−1)·inc, 2π / (n+1), where n is the number of ranges (397–405, changes from scan to scan) |
| `scan_time` | measured duration of the revolution, ≈ 0.100 s |
| `time_increment` | `scan_time / n`. Samples are published in *reverse* time order (the sensor sweeps clockwise), so don't use this for per-point motion compensation. |
| `range_min`, `range_max` | 0.10, 10.0 m |
| `ranges` | metres; **0 = no return**. 30–50 % zeros is normal indoors, depending on the scene. |
| `intensities` | 0–254 = echo strength (8-bit). **255 = high-reflectivity flag** (retroreflector, polished metal, > 300 % reflectivity): range may be unreliable. |

A built-in vendor filter (always on) drops isolated points and smooths jumps between
neighbouring points.

### Error states (`/lsd_error`)

| message | trigger |
|---|---|
| `node_lidar init error` | the port couldn't be opened. Repeats every 3 s and the node stays up without data, so fix the port and restart. |
| `node_lidar is trapped` | no valid packet for 3 s, still none after one restart attempt |
| `node_lidar frequence abnormal` | scan frequency outside 9.7–10.3 Hz for 30 s |
| `node_lidar is blocked` | more than 70 % of points under 0.1 m *or without a return* (0) for 200 scans in a row (about 20 s). Can fire falsely in large open spaces where most directions return nothing. |

On any error the driver **stops publishing scans** until it gets `/lidar_status` = 1.

### Commands (`/lidar_status`)

```bash
ros2 topic pub --once /lidar_status std_msgs/msg/UInt16 "{data: 1}"
```

| value | effect |
|---|---|
| 1 | (re)start: clears the error state and resumes publishing. Use this to recover. |
| 2 | stop: driver stops publishing and sends the stop command (the sensor keeps streaming on our unit, see §8) |
| 5 | clear the error flags only. Publishing does *not* resume, use 1. |
| 3 / 4 | send the vendor's "high/low exposure" bytes. Not in the D6 protocol doc, effect unknown. |
| 6 / 7 | **avoid.** They send the same bytes as 3/4 and change the expected frequency window: 7 expects 5.2–6.8 Hz, but the D6 always runs at 10 Hz, so after 30 s you get a frequency error and scans stop. |

### Vendor command-line options

`ros2 run m1ct_d2 m1ct_d2 [options] --ros-args ...`. The options must come **before**
`--ros-args`. They were written for robot vacuums: `-cover [a,b][c,d]` (blank angle
sectors), `-angle`, `-diameter`, `-center`, `-gyr`, `-slam`, `-version`. See `src/main.cpp`.
Most aren't wired to anything useful for a generic robot.

## 7. Serial protocol

The vendor's "COIN-D6 Data Format Standard Specification", checked against the live stream
with the parser below. 230400 baud, 8N1, little-endian.

### Scan packets

```
offset  0   1   2    3    4    5    6    7    8   9   10 ...
       AA  55  M&T  LSN  FSAL FSAH LSAL LSAH CSL CSH  S1_L S1_2nd S1_H  S2_L ...
```

| field | meaning |
|---|---|
| `AA 55` | header (0x55AA, little-endian) |
| `M&T` | bit 0 = **T**, 1 for a start-of-revolution packet. Bits 7..1 = **M**, scan frequency in 0.1 Hz, only valid in start packets (100 = 10.0 Hz). |
| `LSN` | number of samples in the packet. 1 in start packets, 25 in normal packets on our unit. |
| `FSA`, `LSA` | angles of the first/last sample: `angle_deg = (raw >> 1) / 64`, bit 0 is always 1 (check bit) |
| `CS` | checksum, see below |
| `Si` | 3 bytes per sample: `distance_mm = S_H * 64 + (S_2nd >> 2)` (14 bit), `intensity = (S_2nd & 3) * 64 + (S_L >> 2)` (8 bit), `high_reflect = S_L & 1` |

Angle of sample i (0-based) inside a packet: `FSA + (LSA − FSA) · i / (LSN − 1)`. Add 360° to
LSA first when it wrapped past 0.

**Checksum:** XOR of 16-bit words `0x55AA`, `(LSN << 8) | M&T`, `FSA`, `LSA`, and for every
sample `(S_H << 8) | S_2nd` and `S_L`. The vendor PDF is unclear about this; the formula
comes from the vendor's `calibration.py` and matches 100 % of the packets we captured.

### Other frames (vendor, not seen by us)

- Device info `A5 5A 14 00 …`, sent once at power-on: model string, rotation direction
  (0 = clockwise), firmware revision.
- Start-scan header `A5 5A 00 00 80 01 81`, sent before the scan data.

### Commands

| | send | documented ACK |
|---|---|---|
| start | `AA 55 F0 0F` | `A5 5A 50 07 00…00 A8` |
| stop | `AA 55 F5 0A` | `A5 5A 55 07 00…00 AD` |

On our unit neither command is ever acknowledged and the stream doesn't stop (§8).

### Minimal standalone reader (for "driver or sensor?" debugging)

Stop the driver first, since only one program can read the port.

```python
#!/usr/bin/env python3
"""Read the raw COIN-D6 stream for 3 s and print packet/sample statistics."""
import serial, struct, sys, time
s = serial.Serial(sys.argv[1] if len(sys.argv) > 1 else '/dev/coin_d6', 230400, timeout=0.05)
buf, t0 = b'', time.time()
while time.time() - t0 < 3:
    buf += s.read(8192)
i = ok = bad = rings = 0
dist = []
while (i := buf.find(b'\xAA\x55', i)) >= 0 and i + 10 <= len(buf):
    mt, lsn = buf[i + 2], buf[i + 3]
    n = 10 + 3 * lsn
    if lsn == 0 or i + n > len(buf):
        i += 2; continue
    fsa, lsa, cs = struct.unpack_from('<HHH', buf, i + 4)
    x = 0x55AA ^ (lsn << 8 | mt) ^ fsa ^ lsa
    samples = [buf[i + 10 + 3 * k: i + 13 + 3 * k] for k in range(lsn)]
    for lo, mid, hi in samples:
        x ^= (hi << 8 | mid) ^ lo
    if x != cs:
        bad += 1; i += 2; continue
    ok += 1; rings += mt & 1
    dist += [hi * 64 + (mid >> 2) for lo, mid, hi in samples]
    i += n
valid = [d for d in dist if d]
print(f'packets ok={ok} bad={bad} revolutions={rings} samples/s={len(dist) / 3:.0f}')
print(f'zero={100 * (len(dist) - len(valid)) / max(len(dist), 1):.0f}%  '
      f'range {min(valid, default=0)}..{max(valid, default=0)} mm')
```

Expected output: about 30 revolutions, about 4000 samples/s, `bad=0`.

## 8. Vendor docs vs. reality

| topic | vendor docs | our unit |
|---|---|---|
| Power-on state | "stopped until the start command" | streams scan data continuously, with or without the start command |
| Start/stop ACK | 12-byte ACK frames | no ACK ever received. Stop is ignored and the stream keeps going. It's unclear whether the firmware differs or the adapter doesn't pass commands to the lidar. |
| DTR | WitMotion: "ensure DTR is not asserted" | toggling DTR changed nothing |
| Wire colours | two incompatible colour schemes | check the labels, don't trust colours |
| Device-info example frame | "COIN-D6" | the example bytes in the protocol doc decode to `COIN-D4` (copied from the D4 doc) |
| Max range 12 m | spec sheet | not verified, longest return indoors was 4.4 m |
| Angle correction | the device-info frame says "angle correction needed in the driver"; the vendor driver applies a distance-dependent `atan` correction | only affects the internal filter, not the published angles |

## 9. Troubleshooting

| symptom | check |
|---|---|
| no `/dev/coin_d6` | `lsusb` should list `1a86:7523 QinHeng CH340`. Rule installed? Run `sudo udevadm trigger`. |
| `ttyUSB0` appears and disappears right after plugging in | `brltty` claims CH340 devices on Ubuntu: `sudo apt remove brltty` |
| `Permission denied` on the port | `groups` must include `dialout`, then log out and back in |
| node prints `lidar_set_port wrong` / `init error` | wrong `port`, or another program has it open (`fuser /dev/coin_d6`) |
| node runs but `/scan` is silent | `ros2 topic echo /lsd_error`. If it's in an error state, publish `/lidar_status` 1. Check raw data with the reader in §7. |
| scans stop after about 30 s | frequency error, probably after `/lidar_status` 6/7. Restart or publish 1. |
| RViz: nothing shown / "frame does not exist" | the fixed frame needs a TF tree. Use `rviz:=true` or publish `base_link -> laser_link`. |
| object shows up mirrored or rotated | sensor mounted upside down (roll π) or the single ear isn't facing +x (fix the yaw in the TF) |
| unplugged while running | the driver doesn't reconnect, restart it |
| many 0 ranges | normal for open or absorbing directions (glass, black surfaces, out of range). Points under 0.10 m are invalid too. |

## 10. Limitations and ideas

- **Variable point count** (397–405). Fine for RViz and Nav2 costmaps, but slam_toolbox/Karto
  wants a fixed count and may reject scans. Fix: bin samples into a fixed number of angle
  steps using their real angles.
- **No reconnect** after unplugging. The node also stays alive when the port can't be
  opened, so launch `respawn` doesn't help yet.
- `range_min`/`range_max` are hard-coded (0.10 / 10.0 m), and the vendor filter can't be
  switched off.
- The "blocked" check counts no-return points, so it can stop the driver in large open
  areas (§6).
- Stop doesn't stop the sensor (§8).
- Tested on ROS 2 Jazzy only.

## 11. Vendor resources

Not included in this repo (copyright). They come with the sensor or from the vendor:

- *COIN-D6 Single-Line LiDAR Specification Sheet A1* (Chinese): specs, drawings, coordinate
  system
- *COIN-D6 Instruction Manual* (English): same specs plus Windows/ROS 2 quick start
- *COIN-D6 LiDAR Data Format Standard Specification V1.0* (EN/CN): serial protocol
- *COIN-D6/D6A Laser Safety Test* (SGS, 2025-07-22): Class 1 report
- Windows tools: CSPC host software, WitMotion LiDAR viewer, CH340 drivers, `calibration.py`
  (checksum reference)
- Vendor drivers, also in `vendor/`: `m1ct_d4_ros2_v16.zip` (the base of this driver) and
  `cspc_lidar_sdk_ros1_0802.tar.gz` (ROS 1, same core). The instruction manual also mentions
  a newer `cspc_lidar_sdk_ros2` package that we haven't seen.
- Vendor sites: [xtark.cn](https://www.xtark.cn) (XTARK/Tucker Innovations)

## 12. Changes from the vendor driver

The first commit in this repo is the untouched vendor package, so `git log -p` shows
everything. Summary:

- builds on Jazzy: `declare_parameter` defaults, missing `std_msgs` dependency
- one node instead of two, so launch-file renaming and remapping work
- the parameter YAML is actually applied (its node name never matched before)
- vendor `getopt` parsing no longer scrambles `--ros-args`
- timestamps in ROS time instead of seconds since boot
- mutex double-unlock and lock-leak fixes, missing return values (baud-rate setup)
- `angle_max` consistent with the number of ranges, empty scans not published
- udev rule, launch file, RViz config, this guide
