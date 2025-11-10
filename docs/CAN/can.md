# CAN Protocol Specification

_Accessory Control Network for PCMs, Sensors, and Controllers_

This document defines the CAN layout used by the **control head**, **PCMs**, **sensor nodes**, and other future accessories.

Goals:

- Scalable to many nodes (multiple 26-ch PCMs, many 4-ch PCMs, dedicated sensors, extra controllers).
- Simple to implement on RP2040 / Pico / ESP32 / Pi.
- Easy to route messages to a specific node or broadcast.
- Clean separation between:
  - Message priority
  - Message type (class)
  - Source / destination
  - Message subject (command/status subtype)

This is intentionally conservative and extensible; you can refine bit assignments as the hardware/protocol stabilizes.

---

## 1. Physical & General

- **Bus:** CAN 2.0B
- **Baud rate:** `500 kbps` (TBD; 250 kbps also acceptable if wiring is long/noisy)
- **Frame type:** Extended (29-bit) identifiers
- **Endianness:** Multi-byte integers are **big-endian** unless explicitly stated.
- **This is a dedicated accessory bus**, not the vehicle OEM CAN.

All nodes **must** ignore unknown classes/subjects and reserved bits.

---

## 2. 29-bit ID Layout

We use a fixed 29-bit layout to keep things organized and debuggable.

```
+------------+------------+----------------+----------------+------------+
| 28 .. 26   | 25 .. 21   | 20 .. 13       | 12 .. 5        | 4 .. 0     |
+------------+------------+----------------+----------------+------------+
| PRIORITY   | MSG_CLASS  | SRC_NODE_ID    | DST_NODE_ID    | SUBJECT    |
| (3 bits)   | (5 bits)   | (8 bits)       | (8 bits)       | (5 bits)   |
+------------+------------+----------------+----------------+------------+
```
| Field           | Bit Width | Possible Values | Notes                       |
| --------------- | --------- | --------------- | --------------------------- |
| **PRIORITY**    | 3 bits    | 2³ = **8**      | Priorities `0–7`            |
| **MSG_CLASS**   | 5 bits    | 2⁵ = **32**     | 0x00–0x1F message classes   |
| **SRC_NODE_ID** | 8 bits    | 2⁸ = **256**    | 0x00–0xFF source IDs        |
| **DST_NODE_ID** | 8 bits    | 2⁸ = **256**    | 0x00–0xFF destination IDs   |
| **SUBJECT**     | 5 bits    | 2⁵ = **32**     | 0x00–0x1F subjects/subtypes |


### 2.1 Priority (3 bits)

Lower value = higher priority.

Suggested:

- `000` — Critical safety / hard faults
- `001` — PCM fault/status
- `010` — Control commands (channel on/off/PWM)
- `011` — Sensor data / ADC
- `100` — Heartbeat / discovery / config
- `101`–`111` — Reserved / low-priority chatter

_Nodes should not starve others; be reasonable._

### 2.2 Message Class (5 bits)

High-level category:

|     Value | Name           | Notes                                  |
| --------: | -------------- | -------------------------------------- |
|      0x00 | Reserved       |                                        |
|      0x01 | PCM Control    | Commands to PCMs (set/toggle/PWM/etc.) |
|      0x02 | PCM Status     | Channel/board status and telemetry     |
|      0x03 | PCM IO/ADC     | ADC readings, GPIO state/config        |
|      0x04 | Sensor Data    | Generic sensor payloads                |
|      0x05 | Config         | Node configuration / parameters        |
|      0x06 | Heartbeat/Disc | Periodic alive, discovery, FW info     |
| 0x07–0x1F | Reserved       | Future use                             |

### 2.3 Source / Destination Node IDs (8 bits each)

- `SRC_NODE_ID`: sender’s logical ID
- `DST_NODE_ID`: intended recipient
  - `0xFF` = **broadcast** (all nodes)
  - `0xF0–0xFE` = group/broadcast ranges (optional, see below)

#### Node ID Ranges

|     Range | Usage                             |
| --------: | --------------------------------- |
| 0x01–0x1F | 26-ch PCMs                        |
| 0x20–0x5F | 4-ch (and other small) PCMs       |
| 0x60–0x8F | Dedicated sensor nodes            |
| 0x90–0xBF | Controllers / HMIs / gateways     |
| 0xC0–0xEF | Reserved for future devices       |
| 0xF0–0xFE | Group IDs (e.g. "all PCMs front") |
|      0xFF | Full broadcast                    |

Examples:

- Front 26-ch PCM: `0x01`
- Rear 26-ch PCM: `0x02`
- Small 4-ch module (roof lights): `0x20`
- Pi-based control head: `0x90`

### 2.4 Subject (5 bits)

Subject refines the meaning within a `MSG_CLASS`. Interpretation depends on `MSG_CLASS`.

Examples:

For `MSG_CLASS = 0x01 (PCM Control)`:

- `0x00` — Single channel command
- `0x01` — Bulk channel command (bitfield)
- `0x02` — PWM config
- `0x03` — Request status snapshot
- `0x1F` — Reserved

For `MSG_CLASS = 0x02 (PCM Status)`:

- `0x00` — Single channel status
- `0x01` — Bulk status summary
- `0x02` — Fault report
- `0x03` — Board-level metrics (supply V, temp, etc.)

---

## 3. Node Types

Each node advertises its type via heartbeat (see §6).

Suggested enum for node types:

```
0x01 = PCM_26CH
0x02 = PCM_4CH
0x03 = SENSOR_GENERIC
0x04 = CONTROLLER_HMI
0x05 = GATEWAY/BRIDGE
0xFE = RESERVED
0xFF = UNKNOWN
```

---

## 4. PCM Control Messages (MSG_CLASS = 0x01)

### 4.1 Single Channel Command

**ID:**

- `PRIO`: `010` (control)
- `CLASS`: `0x01`
- `SRC_NODE_ID`: controller ID (e.g. `0x90`)
- `DST_NODE_ID`: target PCM ID (e.g. `0x01`)
- `SUBJECT`: `0x00`

**Payload (DLC = 3):**

```
Byte 0: Channel index (0-25 for 26ch, 0-3 for 4ch)
Byte 1: Command
        0x00 = OFF
        0x01 = ON
        0x02 = TOGGLE
        0x03 = SET_PWM (duty in Byte 2)
Byte 2: PWM duty (0-255) if Command == SET_PWM, else reserved (0)
```

### 4.2 Bulk Channel Command (Optional / Nice to Have)

Allows setting multiple channels atomically.

**SUBJECT:** `0x01`  
**Payload:** implementation-defined; typical:

```
Byte 0: Start channel index
Byte 1: Channel count
Byte 2..7: Bitfield(s) or packed commands
```

### 4.3 Request Status Snapshot

Controller → PCM: “Send me all your channel states.”

**SUBJECT:** `0x03`  
**DLC:** 1

```
Byte 0: 0x01 = request channel snapshot
        0x02 = request ADC snapshot
        0x03 = request GPIO snapshot
```

PCM responds with appropriate `MSG_CLASS = 0x02/0x03` messages.

---

## 5. PCM Status Messages (MSG_CLASS = 0x02)

### 5.1 Single Channel Status

**SUBJECT:** `0x00`  
Sent by PCM in response to commands, faults, or periodically.

**Payload (DLC = 5):**

```
Byte 0: Channel index
Byte 1: State bits:
        bit0 = ACTUAL_ON
        bit1 = REQUESTED_ON
        bit2 = FAULT
        bit3 = SHORT_DETECTED
        bit4 = OPEN_LOAD
        bit5 = OVERCURRENT
        bit6 = OVERTEMP
        bit7 = RESERVED
Byte 2-3: Current in milliamps (uint16, big-endian)
Byte 4:   Reserved (0 for now)
```

### 5.2 Bulk Status Summary

**SUBJECT:** `0x01`  

Intended for fast UI refresh. Suggested:

- 26-ch PCM sends **two frames**:
  - One bitfield for ACTUAL_ON
  - One bitfield for FAULT

Define exact format later; placeholder:

```
Frame A (ON bitfield):
  Byte 0-3: Channel 0-25 ON bits (LSB = ch0)
  Byte 4-7: Reserved/future

Frame B (FAULT bitfield):
  Byte 0-3: Channel 0-25 FAULT bits
  Byte 4-7: Reserved/future
```

---

## 6. PCM ADC / GPIO (MSG_CLASS = 0x03)

### 6.1 ADC Reading

**SUBJECT:** `0x00`  
**Payload (DLC = 4):**

```
Byte 0: ADC channel index
Byte 1-2: Raw ADC counts (uint16, big-endian)
Byte 3:   Scaling info or reserved
```

Optionally, a node can send multiple ADC samples in one frame if needed; keep type consistent.

### 6.2 GPIO State

**SUBJECT:** `0x01`  

```
Byte 0: GPIO index
Byte 1: Direction: 0 = input, 1 = output
Byte 2: Level: 0 = low, 1 = high (for outputs) or sampled state (for inputs)
Byte 3: Reserved
```

### 6.3 GPIO Config Command

Controller → PCM, same class with DST=PCM and command in payload (TBD).

---

## 7. Sensor Data (MSG_CLASS = 0x04)

For dedicated sensors (temps, pressures, etc.). Keep generic.

### 7.1 Generic Sensor Frame

**SUBJECT:** defines reading type. Example mapping:

```
0x00 = Temperature (°C x100)
0x01 = Pressure (kPa x10)
0x02 = Voltage (mV)
0x03 = Current (mA)
0x04 = Humidity (RH x100)
0x10-0x1F = Custom/Module-specific
```

**Payload example (temp):**

```
Byte 0: Sensor local index
Byte 1-2: Value (int16 or uint16, big-endian)
Byte 3-7: Reserved
```

Each sensor node:

- Has its own `SRC_NODE_ID`.
- Uses `DST_NODE_ID = 0xFF` for broadcast unless directed otherwise.

---

## 8. Heartbeat & Discovery (MSG_CLASS = 0x06)

### 8.1 Heartbeat

**SUBJECT:** `0x00`  
Sent periodically by every node.

```
Byte 0: Node type (see §3)
Byte 1: Firmware major
Byte 2: Firmware minor
Byte 3: Optional status flags (e.g. fault summary)
Byte 4-7: Reserved / uptime / build ID / etc.
```

- `DST_NODE_ID = 0xFF` (broadcast)
- Priority: `100` (low-ish; tune as needed)

### 8.2 Discovery Request

Controller → `DST_NODE_ID = 0xFF`, SUBJECT `0x01`, empty or simple payload.

Nodes respond with a heartbeat immediately (randomized small delay to avoid collisions).

---

## 9. Group Addressing (Optional)

To command a set of nodes:

- Use `DST_NODE_ID` in `0xF0–0xFE` as **group IDs**.
- Each node can be configured (via `MSG_CLASS = 0x05 Config`) to belong to 0–N groups.
- Upon receiving a group-addressed frame, node processes it if subscribed.

Example:

- `0xF0` = “All PCMs”
- `0xF1` = “All 4-ch PCMs”
- `0xF2` = “Front-of-vehicle lighting modules”

---

## 10. Design Notes

- **Scalability:** 8-bit node IDs give you up to 255 addressable nodes.
- **Modularity:** `MSG_CLASS` + `SUBJECT` let you add new features (e.g. logging, firmware update) without breaking existing behavior.
- **Safety:** Use priorities so fault + control traffic wins over spammy sensor updates.
- **Simplicity:** Encoding uses straightforward fields so your `PCMManager` in Python can:
  - Mask & shift to determine class/src/dst/subject.
  - Route by `DST_NODE_ID` and `MSG_CLASS`.
- **Forward compatibility:** Unused classes and subjects are reserved, not repurposed.

---

## 11. TODOs / Open Items

To be refined as hardware/firmware solidifies:

- Exact bitfield definition for bulk status.
- Exact encoding for configuration (`MSG_CLASS = 0x05`).
- Support for firmware update over CAN (if desired).
- Error handling strategy (NACK frames, retries, rate limiting).
- Finalize baud rate and heartbeat interval (e.g. 1 Hz).

