#include <Arduino.h>
#include <SPI.h>
#include <Adafruit_MCP2515.h>

// --------------------------------------------------
// CAN / MCP2515 CONFIG (PiCowbell for Pico)
// --------------------------------------------------

#define CS_PIN 20
#define CAN_BAUDRATE 250000 // 250 kbps (make sure all nodes match)

Adafruit_MCP2515 mcp(CS_PIN);

// --------------------------------------------------
// PROTOCOL CONSTANTS (from your CAN spec)
// --------------------------------------------------

// Node IDs
static const uint8_t CONTROLLER_NODE_ID = 0x90; // Controller / HMI

// Message classes
static const uint8_t MSG_CLASS_PCM_CONTROL = 0x01;

// Subjects for PCM Control
static const uint8_t SUBJECT_SINGLE_CHANNEL_CMD = 0x00;

// Commands (PCM Control → Single Channel Command)
static const uint8_t CMD_OFF = 0x00;
static const uint8_t CMD_ON = 0x01;
static const uint8_t CMD_TOGGLE = 0x02;
static const uint8_t CMD_SET_PWM = 0x03;

// Priority (3 bits, 0 = highest)
static const uint8_t PRIORITY_CONTROL = 0b010; // Control commands

// --------------------------------------------------
// SWITCH INPUTS
// --------------------------------------------------
// Physical pins used for switches (active LOW, INPUT_PULLUP)
const uint8_t switchPins[] = {
    // switch index → pin:
    // 0 → GP0
    // 1 → GP1
    // 2 → GP2
    // 3 → GP3
    // 4 → GP6
    // 5 → GP7
    // 6 → GP8
    // 7 → GP9
    // 8 → GP10
    // 9 → GP11
    // 10 → GP12
    // 11 → GP13
    // 12 → GP17
    // 13 → GP22
    // 14 → GP26
    // 15 → GP27
    // 16 → GP28
    0, 1, 2, 3, 6,
    7, 8, 9, 10,
    11, 12,
    13,
    17,
    22,
    26, 27, 28};

const uint8_t NUM_SWITCHES = sizeof(switchPins) / sizeof(switchPins[0]);

// Bitfield of current switch states (we only need lower bits)
uint32_t switchStates = 0;

// --------------------------------------------------
// HELPER: Build 29-bit CAN ID
//
// Layout:
// [28..26] PRIORITY   (3 bits)
// [25..21] MSG_CLASS  (5 bits)
// [20..13] SRC_NODE   (8 bits)
// [12..5]  DST_NODE   (8 bits)
// [4..0]   SUBJECT    (5 bits)
// --------------------------------------------------
static uint32_t buildCanId(uint8_t priority,
                           uint8_t msgClass,
                           uint8_t srcNode,
                           uint8_t dstNode,
                           uint8_t subject)
{
  uint32_t id = 0;
  id |= ((uint32_t)(priority & 0x07) << 26);
  id |= ((uint32_t)(msgClass & 0x1F) << 21);
  id |= ((uint32_t)(srcNode & 0xFF) << 13);
  id |= ((uint32_t)(dstNode & 0xFF) << 5);
  id |= (uint32_t)(subject & 0x1F);
  return id;
}

// --------------------------------------------------
// SWITCH → ACTION MAPPING
// --------------------------------------------------

struct SwitchAction
{
  uint8_t dstNode;      // PCM node ID
  uint8_t channelIndex; // Channel index on that PCM
  uint8_t onCommand;    // Command when switch goes ON
  uint8_t offCommand;   // Command when switch goes OFF
};

struct SwitchConfig
{
  const SwitchAction *actions;
  uint8_t numActions;
};

// Switch 0 (Rear Amber):
const SwitchAction switch0Actions[] = {
    // Rear Amber
    {0x02, 10, CMD_ON, CMD_OFF}, // Amber Chase
    {0x02, 6, CMD_ON, CMD_OFF},  // Driver Rear Turn
    {0x02, 3, CMD_ON, CMD_OFF}   // Passenger Rear Turn
};

// Switch 1 (Rear White):
const SwitchAction switch1Actions[] = {
    // Rear White
    {0x02, 11, CMD_ON, CMD_OFF}, // White Chase
    {0x02, 4, CMD_ON, CMD_OFF},  // Driver Reverse
    {0x02, 0, CMD_ON, CMD_OFF}   // Passenger Reverse
};

// Switch 2 (Cabin Lights):
const SwitchAction switch2Actions[] = {
    // Cabin Lights
    {0x02, 7, CMD_ON, CMD_OFF} // Rear Cargo Lights
};

// Switch 3 Empty (Red)
const SwitchAction switch3Actions[] = {};

// Switch 4 Empty (Running Strobe)
const SwitchAction switch4Actions[] = {};

// Switch 5 (Front Strobe +):
const SwitchAction switch5Actions[] = {
    {0x02, 33, CMD_ON, CMD_OFF} // Front Fast Flash Macro
};

// Switch 6 (Front Strobe - ):
const SwitchAction switch6Actions[] = {
    {0x02, 34, CMD_ON, CMD_OFF} // Front Slow Flash Macro
};

// Switch 7 (Chase +):
const SwitchAction switch7Actions[] = {
    {0x01, 31, CMD_ON, CMD_OFF} // Rear Fast Flash Macro
};

// Switch 8 (Chase -):
const SwitchAction switch8Actions[] = {
    {0x01, 32, CMD_ON, CMD_OFF} // Rear Slow Flash Macro
};

// Switch 9 (Air Compressor):
const SwitchAction switch9Actions[] = {
    {0x01, 20, CMD_ON, CMD_OFF} // Air Compressor Toggle
};

// Switch 10 (Ditch Lights High):
const SwitchAction switch10Actions[] = {
    {0x01, 17, CMD_ON, CMD_OFF},  // Driver Ditch Light High
    {0x01, 10, CMD_ON, CMD_OFF},  // Passenger Ditch Light High
    {0x01, 18, CMD_OFF, CMD_OFF}, // Driver Ditch Light Low (Safety Turn Off)
    {0x01, 11, CMD_OFF, CMD_OFF}  // Passenger Ditch Light Low (Safety Turn Off)
};

// Switch 11 (Front Lights High):
const SwitchAction switch11Actions[] = {
    {0x01, 15, CMD_ON, CMD_OFF},  // Grill Inner Lights High
    {0x01, 13, CMD_ON, CMD_OFF},  // Grill Outer Lights High
    {0x01, 16, CMD_OFF, CMD_OFF}, // Grill Inner Lights Low (Safety Turn Off)
    {0x01, 14, CMD_OFF, CMD_OFF}, // Grill Outer Lights Low (Safety Turn Off)
    {0x01, 5, CMD_ON, CMD_OFF}    // Lightbar
};

// Switch 12 (Rock Lights):
const SwitchAction switch12Actions[] = {
    {0x01, 6, CMD_ON, CMD_OFF}, // Rock Lights Front
    {0x02, 8, CMD_ON, CMD_OFF}  // Rock Lights Rear
};

// Switch 13 Empty (Engine Lights):
const SwitchAction switch13Actions[] = {};

// Switch 14 (Fog Lights):
const SwitchAction switch14Actions[] = {
    {0x01, 2, CMD_ON, CMD_OFF}, // Fog Lights
};

// Switch 15 (Ditch Lights Low):
const SwitchAction switch15Actions[] = {
    {0x01, 18, CMD_ON, CMD_OFF},  // Driver Ditch Light Low
    {0x01, 11, CMD_ON, CMD_OFF},  // Passenger Ditch Light Low
    {0x01, 17, CMD_OFF, CMD_OFF}, // Driver Ditch Light High (Safety Turn Off)
    {0x01, 10, CMD_OFF, CMD_OFF}  // Passenger Ditch Light High (Safety Turn Off)
};

// Switch 16 (Front Lights Low):
const SwitchAction switch16Actions[] = {
    {0x01, 16, CMD_ON, CMD_OFF},  // Grill Inner Lights Low
    {0x01, 14, CMD_ON, CMD_OFF},  // Grill Outer Lights Low
    {0x01, 15, CMD_OFF, CMD_OFF}, // Grill Inner Lights High (Safety Turn Off)
    {0x01, 13, CMD_OFF, CMD_OFF}, // Grill Outer Lights High (Safety Turn Off)
};

// Map each switch index → its SwitchConfig
// Index here MUST match index in switchPins[].
SwitchConfig switchConfigs[NUM_SWITCHES] = {
    {switch0Actions, sizeof(switch0Actions) / sizeof(switch0Actions[0])},
    {switch1Actions, sizeof(switch1Actions) / sizeof(switch1Actions[0])},
    {switch2Actions, sizeof(switch2Actions) / sizeof(switch2Actions[0])},
    {switch3Actions, sizeof(switch3Actions) / sizeof(switch3Actions[0])},
    {switch4Actions, sizeof(switch4Actions) / sizeof(switch4Actions[0])},
    {switch5Actions, sizeof(switch5Actions) / sizeof(switch5Actions[0])},
    {switch6Actions, sizeof(switch6Actions) / sizeof(switch6Actions[0])},
    {switch7Actions, sizeof(switch7Actions) / sizeof(switch7Actions[0])},
    {switch8Actions, sizeof(switch8Actions) / sizeof(switch8Actions[0])},
    {switch9Actions, sizeof(switch9Actions) / sizeof(switch9Actions[0])},
    {switch10Actions, sizeof(switch10Actions) / sizeof(switch10Actions[0])},
    {switch11Actions, sizeof(switch11Actions) / sizeof(switch11Actions[0])},
    {switch12Actions, sizeof(switch12Actions) / sizeof(switch12Actions[0])},
    {switch13Actions, sizeof(switch13Actions) / sizeof(switch13Actions[0])},
    {switch14Actions, sizeof(switch14Actions) / sizeof(switch14Actions[0])},
    {switch15Actions, sizeof(switch15Actions) / sizeof(switch15Actions[0])},
    {switch16Actions, sizeof(switch16Actions) / sizeof(switch16Actions[0])},
};

// --------------------------------------------------
// HELPER: Send a single-channel command over CAN
//
// Payload (DLC = 3):
//   Byte 0: Channel index (0-based)
//   Byte 1: Command (0x00 OFF, 0x01 ON, 0x02 TOGGLE, 0x03 SET_PWM)
//   Byte 2: PWM duty (0-255) if SET_PWM, otherwise 0
// --------------------------------------------------
static bool sendChannelCommand(uint8_t dstNode,
                               uint8_t channelIndex,
                               uint8_t cmd)
{
  // Build extended 29-bit ID
  uint32_t canId = buildCanId(
      PRIORITY_CONTROL,          // priority
      MSG_CLASS_PCM_CONTROL,     // class
      CONTROLLER_NODE_ID,        // src
      dstNode,                   // dst
      SUBJECT_SINGLE_CHANNEL_CMD // subject
  );

  mcp.beginExtendedPacket(canId);
  mcp.write(channelIndex);
  mcp.write(cmd);
  mcp.endPacket();

  Serial.print("CAN TX: dst=0x");
  Serial.print(dstNode, HEX);
  Serial.print(" ch=");
  Serial.print(channelIndex);
  Serial.print(" cmd=");
  Serial.println(cmd, HEX);

  return true;
}

// --------------------------------------------------
// SETUP & LOOP
// --------------------------------------------------

void setup()
{
  Serial.begin(115200);
  // while (!Serial)
  // {
  //   delay(10);
  // }

  Serial.println("RP2040 Switch Controller with MCP2515 CAN starting...");

  // Initialize CAN controller
  if (!mcp.begin(CAN_BAUDRATE))
  {
    Serial.println("Error initializing MCP2515. Check wiring and PiCowbell.");
    while (1)
    {
      delay(100);
    }
  }
  Serial.println("MCP2515 initialized at 250 kbps.");

  // Initialize switch GPIOs
  for (uint8_t i = 0; i < NUM_SWITCHES; i++)
  {
    pinMode(switchPins[i], INPUT_PULLUP); // active LOW switches
  }
  pinMode(15, OUTPUT); // Status LED
  digitalWrite(15, LOW); // Turn off status LED initially

  Serial.print("Configured ");
  Serial.print(NUM_SWITCHES);
  Serial.println(" switches with mapping.");
}

void loop()
{
  uint32_t newStates = 0;

  // Read all switches and build bitfield
  for (uint8_t i = 0; i < NUM_SWITCHES; i++)
  {
    if (digitalRead(switchPins[i]) == LOW)
    { // Active LOW = ON
      newStates |= (1UL << i);
    }
  }

  // Compare with previous state and send mapped CAN commands
  for (uint8_t i = 0; i < NUM_SWITCHES; i++)
  {
    bool newState = (newStates & (1UL << i)) != 0;
    bool currentState = (switchStates & (1UL << i)) != 0;

    if (newState != currentState)
    {
      // Update cached state
      if (newState)
      {
        switchStates |= (1UL << i);
      }
      else
      {
        switchStates &= ~(1UL << i);
      }

      // Get mapping for this switch
      SwitchConfig &cfg = switchConfigs[i];

      Serial.print("Switch ");
      Serial.print(i);
      Serial.println(newState ? " ON" : " OFF");

      // Fire all actions for this switch
      for (uint8_t a = 0; a < cfg.numActions; a++)
      {
        const SwitchAction &act = cfg.actions[a];

        uint8_t cmd = newState ? act.onCommand : act.offCommand;

        // If you want "no action on release" for a specific mapping,
        // you can encode that by setting offCommand to 0xFF or similar
        // and skip here. Example:
        if (cmd == 0xFF)
        {
          continue;
        }

        sendChannelCommand(act.dstNode, act.channelIndex, cmd);
      }
    }
  }

  // If any switch is ON, turn on status LED
  if (switchStates != 0)
  {
    digitalWrite(15, HIGH);
  }
  else
  {
    digitalWrite(15, LOW);
  }

  delay(50); // Poll at ~20 Hz
}
