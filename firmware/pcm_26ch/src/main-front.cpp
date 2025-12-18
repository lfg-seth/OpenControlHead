#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MCP2515.h>

// ======================= CAN Config =======================

// This PCM's node ID on the CAN bus (change per board)
#define PCM_NODE_ID 0x01

// MCP2515 CS pin selection (same style as Adafruit examples)
#ifdef ESP8266
#define CS_PIN 2
#elif defined(ESP32) && !defined(ARDUINO_ADAFRUIT_FEATHER_ESP32S2) && !defined(ARDUINO_ADAFRUIT_FEATHER_ESP32S3)
#define CS_PIN 14
#elif defined(TEENSYDUINO)
#define CS_PIN 8
#elif defined(ARDUINO_STM32_FEATHER)
#define CS_PIN PC5
#elif defined(ARDUINO_NRF52832_FEATHER)
#define CS_PIN 27
#elif defined(ARDUINO_MAX32620FTHR) || defined(ARDUINO_MAX32630FTHR)
#define CS_PIN P3_2
#elif defined(ARDUINO_ADAFRUIT_FEATHER_RP2040)
#define CS_PIN 7
#elif defined(ARDUINO_ADAFRUIT_FEATHER_RP2040_CAN)
#define CS_PIN PIN_CAN_CS
#elif defined(ARDUINO_RASPBERRY_PI_PICO) || defined(ARDUINO_RASPBERRY_PI_PICO_W)
#define CS_PIN 20
#else
#define CS_PIN 5
#endif

// Use whatever your bus is configured for
#define CAN_BAUDRATE (250000)

Adafruit_MCP2515 mcp(19, 15, 8, 14);

// ======================= Pin & Hardware Config =======================

// I²C pins (PCA9535 + INA219 bus)
#define I2C_SDA_PIN 2 // Adjust for your wiring if you want software reset
#define I2C_SCL_PIN 3 // Adjust for your wiring

// I²C addresses for PCA9535
#define PCA1_ADDR 0x20
#define PCA2_ADDR 0x21

// PCA9535 register definitions
#define PCA9535_OUTPUT_PORT_0 0x02
#define PCA9535_OUTPUT_PORT_1 0x03
#define PCA9535_CONFIG_PORT_0 0x06
#define PCA9535_CONFIG_PORT_1 0x07

#define TC74_ADDR 0x4D // Example temperature sensor address

// ======================= Channel & Switch Mapping =======================

// Channel states (26 channels)
bool channelStates[26] = {false};

// Define Channel Masks (bit 0 -> Channel 1, bit 1 -> Channel 2, etc.)
#define DRIVER_AMBER (1UL << 0)    // Channel 1
#define PASS_AMBER (1UL << 1)      // Channel 2
#define FOGS (1UL << 2)            // Channel 3
#define DRIVER_HIGHBEAM (1UL << 3) // Channel 4
#define PASS_HIGHBEAM (1UL << 4)   // Channel 5
#define LIGHTBAR (1UL << 5)        // Channel 6
#define ROCK_LIGHTS (1UL << 6)     // Channel 7

#define PASS_DITCH_HIGH (1UL << 10) // Channel 11
#define PASS_DITCH_LOW (1UL << 11)  // Channel 12

#define GRILL_OUTER_HIGH (1UL << 13)  // Channel 14
#define GRILL_OUTER_LOW (1UL << 14)   // Channel 15
#define GRILL_INNER_HIGH (1UL << 15)  // Channel 16
#define GRILL_INNER_LOW (1UL << 16)   // Channel 17
#define DRIVER_DITCH_HIGH (1UL << 17) // Channel 18
#define DRIVER_DITCH_LOW (1UL << 18)  // Channel 19
#define GRILL_AMBER (1UL << 19)       // Channel 20
#define EMPTY (0UL << 0)              // Undefined Channel

// PCM Channel-to-PCA Mapping
struct PCAMapping
{
  uint8_t pcaAddr; // PCA address
  uint8_t port;    // 0 for port 0, 1 for port 1
  uint8_t pin;     // Pin number (0-7)
};

// Define mappings for all 26 channels
const PCAMapping channelMappings[32] = {
    {PCA1_ADDR, 1, 7}, // Channel  1 -> PCA1, Port 1, Pin 7
    {PCA1_ADDR, 1, 6}, // Channel  2 -> PCA1, Port 1, Pin 6
    {PCA1_ADDR, 1, 5}, // Channel  3 -> PCA1, Port 1, Pin 5
    {PCA1_ADDR, 1, 4}, // Channel  4 -> PCA1, Port 1, Pin 4
    {PCA1_ADDR, 1, 3}, // Channel  5 -> PCA1, Port 1, Pin 3
    {PCA1_ADDR, 1, 2}, // Channel  6 -> PCA1, Port 1, Pin 2
    {PCA1_ADDR, 1, 1}, // Channel  7 -> PCA1, Port 1, Pin 1
    {PCA1_ADDR, 1, 0}, // Channel  8 -> PCA1, Port 1, Pin 0
    {PCA2_ADDR, 1, 1}, // Channel  9 -> PCA2, Port 1, Pin 1
    {PCA2_ADDR, 1, 0}, // Channel 10 -> PCA2, Port 1, Pin 0
    {PCA2_ADDR, 0, 7}, // Channel 11 -> PCA2, Port 0, Pin 7
    {PCA2_ADDR, 0, 6}, // Channel 12 -> PCA2, Port 0, Pin 6
    {PCA2_ADDR, 0, 5}, // Channel 13 -> PCA2, Port 0, Pin 5
    {PCA2_ADDR, 0, 4}, // Channel 14 -> PCA2, Port 0, Pin 4
    {PCA2_ADDR, 0, 3}, // Channel 15 -> PCA2, Port 0, Pin 3
    {PCA2_ADDR, 0, 2}, // Channel 16 -> PCA2, Port 0, Pin 2
    {PCA2_ADDR, 0, 1}, // Channel 17 -> PCA2, Port 0, Pin 1
    {PCA2_ADDR, 0, 0}, // Channel 18 -> PCA2, Port 0, Pin 0
    {PCA1_ADDR, 0, 7}, // Channel 19 -> PCA1, Port 0, Pin 7
    {PCA1_ADDR, 0, 6}, // Channel 20 -> PCA1, Port 0, Pin 6
    {PCA1_ADDR, 0, 5}, // Channel 21 -> PCA1, Port 0, Pin 5
    {PCA1_ADDR, 0, 4}, // Channel 22 -> PCA1, Port 0, Pin 4
    {PCA1_ADDR, 0, 3}, // Channel 23 -> PCA1, Port 0, Pin 3
    {PCA1_ADDR, 0, 2}, // Channel 24 -> PCA1, Port 0, Pin 2
    {PCA1_ADDR, 0, 0}, // Channel 25 -> PCA1, Port 0, Pin 0
    {PCA1_ADDR, 0, 1}, // Channel 26 -> PCA1, Port 0, Pin 1
    {PCA2_ADDR, 1, 2}, // Channel  27 -> PCA2, Port 1, Pin 2
    {PCA2_ADDR, 1, 3}, // Channel  28 -> PCA2, Port 1, Pin 3
    {PCA2_ADDR, 1, 4}, // Channel  29 -> PCA2, Port 1, Pin 4
    {PCA2_ADDR, 1, 5}, // Channel  30 -> PCA2, Port 1, Pin 5
    {PCA2_ADDR, 1, 6}, // Channel  31 -> PCA2, Port 1, Pin 6
    {PCA2_ADDR, 1, 7}, // Channel  32 -> PCA2, Port 1, Pin 7
};

// Switch-to-PCM Channel Mapping
struct SwitchConfig
{
  uint8_t switchId;  // Switch index
  uint32_t channels; // Bitmask of PCM channels controlled by the switch
  bool isPattern;    // Indicates if the switch uses a flashing pattern
};

// ==== Serial command buffer (USB) ====
String serialInput;

// Prototype
void handleSerialInput();

// Define mappings for switches (33-48)
const SwitchConfig switchMappings[18] = {
    {31, EMPTY, true},
    {32, EMPTY, true},
};

struct FlashingStep
{
  uint32_t channelMask; // Bitmask for channels in this step
  uint16_t duration;    // Duration of this step in ms
};

struct FlashingPattern
{
  FlashingStep steps[16]; // Up to 16 steps per pattern
  uint8_t stepCount;      // Number of steps
  uint8_t currentStep;    // Current step index
  bool active;            // Whether the pattern is active

  // Runtime state (for non-blocking timing)
  bool stepOn;             // Are we currently in the "on" phase of this step?
  unsigned long stepStart; // When the current step phase started (ms)
};

FlashingPattern flashingPatterns[50]; // Patterns for up to 50 switches

// ======================= Global State & Timing =======================

// Flags for PCA availability
bool pca1Available = false;
bool pca2Available = false;

// Cached output states for PCA9535
uint8_t pca1Port0State = 0x00;
uint8_t pca1Port1State = 0x00;
uint8_t pca2Port0State = 0x00;
uint8_t pca2Port1State = 0x00;

// Timing for background tasks
unsigned long lastRecoveryCheckMs = 0;
const unsigned long RECOVERY_PERIOD = 1000; // ms

unsigned long lastFlashingTickMs = 0;
const unsigned long FLASHING_TICK = 5; // ms

// ==== TC74 temperature monitor timing ====
unsigned long lastTempReadMs = 0;
const unsigned long TEMP_PERIOD = 1000; // ms

// ======================= Function Prototypes =======================

// Existing logic
void processCommand(const String &command);
void updateChannel(uint8_t channel, bool state);
void updateChannels(uint32_t channelMask, bool state);
void initPCA9535();
bool isPCAConnected(uint8_t address);
void writePCA9535(uint8_t address, uint8_t port0, uint8_t port1);
void applyFullUpdate(uint16_t states);
void updateSwitch(uint8_t switchId, bool state);
void resetI2CBus();

void runRecoveryCheck();
void runFlashingPatterns();

// ==== TC74 helpers ====
bool readTC74Temperature(int &tempC);
void runTemperatureMonitor();

// CAN handling
void handleCanInput();
static void decodeAndHandleFrame(uint32_t id,
                                 const uint8_t *data,
                                 int len,
                                 bool isExtended,
                                 bool isRTR);
static void printHexDataCompact(const uint8_t *data, int len);
static const char *msgClassToString(uint8_t cls);
static const char *nodeRangeToString(uint8_t id);
static const char *subjectToString(uint8_t cls, uint8_t subj);

// ======================= Core Logic =======================

// (Left in for potential USB debug text commands)
void processCommand(const String &command)
{
  if (command.startsWith("SWITCH_ON:"))
  {
    uint8_t switchId = command.substring(10).toInt();
    updateChannel(switchId, true);
  }
  else if (command.startsWith("SWITCH_OFF:"))
  {
    uint8_t switchId = command.substring(11).toInt();
    updateChannel(switchId, false);
  }
  else if (command.startsWith("FULL_UPDATE:"))
  {
    // Binary string of states, LSB -> channel 1, etc.
    uint16_t states = strtoul(command.substring(12).c_str(), NULL, 2);
    applyFullUpdate(states);
  }
  else if (command.startsWith("off"))
  {
    uint8_t switchId = command.substring(3).toInt();
    updateChannel(switchId, false);
  }
  else if (command.startsWith("on"))
  {
    uint8_t switchId = command.substring(2).toInt();
    updateChannel(switchId, true);
  }
  else
  {
    Serial.print("Invalid command: ");
    Serial.println(command);
  }
}

void updateSwitch(uint8_t switchId, bool state)
{
  Serial.print("Updating switch ");
  Serial.println(switchId);

  for (const auto &mapping : switchMappings)
  {
    if (mapping.switchId == switchId)
    {
      if (mapping.isPattern)
      {
        FlashingPattern &pattern = flashingPatterns[switchId];

        if (!state)
        {
          // turning pattern OFF – make sure all its channels are OFF
          uint32_t offMask = 0;
          for (uint8_t i = 0; i < pattern.stepCount; i++)
          {
            offMask |= pattern.steps[i].channelMask;
          }
          if (offMask)
          {
            updateChannels(offMask, false);
          }
        }

        pattern.active = state;
        pattern.currentStep = 0;
        pattern.stepOn = false;
        pattern.stepStart = millis();
      }
      else
      {
        // normal switch: just set its channels
        updateChannels(mapping.channels, state);
      }
      break;
    }
  }
}

void applyFullUpdate(uint16_t states)
{
  for (uint8_t i = 0; i < 18; i++)
  {
    bool state = (states & (1 << i)) != 0;
    updateChannel(i + 1, state); // Channels are 1-based
  }
  Serial.println("Applied full update.");
}

void updateChannels(uint32_t channelMask, bool state)
{
  for (uint8_t channel = 0; channel < 26; channel++)
  {
    if (channelMask & (1UL << channel))
    {
      updateChannel(channel + 1, state); // Channel IDs are 1-based
    }
  }
}

void updateChannel(uint8_t channel, bool state)
{
  if (channel < 1 || channel > 26)
    return;
  if (!(pca1Available || pca2Available))
    return;

  const auto &mapping = channelMappings[channel - 1];
  uint8_t *portState = nullptr;

  if (mapping.pcaAddr == PCA1_ADDR)
  {
    portState = (mapping.port == 0) ? &pca1Port0State : &pca1Port1State;
  }
  else if (mapping.pcaAddr == PCA2_ADDR)
  {
    portState = (mapping.port == 0) ? &pca2Port0State : &pca2Port1State;
  }

  if (portState == nullptr)
    return;

  if (state)
  {
    *portState |= (1 << mapping.pin);
  }
  else
  {
    *portState &= ~(1 << mapping.pin);
  }

  channelStates[channel - 1] = state;

  if (mapping.pcaAddr == PCA1_ADDR)
  {
    writePCA9535(PCA1_ADDR, pca1Port0State, pca1Port1State);
  }
  else if (mapping.pcaAddr == PCA2_ADDR)
  {
    writePCA9535(PCA2_ADDR, pca2Port0State, pca2Port1State);
  }

  Serial.print("Channel ");
  Serial.print(channel);
  Serial.print(state ? " ON" : " OFF");
  Serial.println();
}

// ======================= PCA9535 / I2C Helpers =======================

void initPCA9535()
{
  pca1Available = isPCAConnected(PCA1_ADDR);
  if (pca1Available)
  {
    Wire.beginTransmission(PCA1_ADDR);
    Wire.write(PCA9535_OUTPUT_PORT_0);
    Wire.write(0x00);
    Wire.write(0x00);
    Wire.endTransmission();

    Wire.beginTransmission(PCA1_ADDR);
    Wire.write(PCA9535_CONFIG_PORT_0);
    Wire.write(0x00);
    Wire.write(0x00);
    if (Wire.endTransmission() == 0)
    {
      writePCA9535(PCA1_ADDR, pca1Port0State, pca1Port1State);
      Serial.println("PCA9535 at 0x20 initialized.");
    }
  }
  else
  {
    Serial.println("Failed to initialize PCA9535 at 0x20.");
    digitalWrite(13, LOW); // Turn off indicator LED
  }

  pca2Available = isPCAConnected(PCA2_ADDR);
  if (pca2Available)
  {
    Wire.beginTransmission(PCA2_ADDR);
    Wire.write(PCA9535_OUTPUT_PORT_0);
    Wire.write(0x00);
    Wire.write(0x00);
    Wire.endTransmission();

    Wire.beginTransmission(PCA2_ADDR);
    Wire.write(PCA9535_CONFIG_PORT_0);
    Wire.write(0x00);
    Wire.write(0x00);
    if (Wire.endTransmission() == 0)
    {
      writePCA9535(PCA2_ADDR, pca2Port0State, pca2Port1State);
      Serial.println("PCA9535 at 0x21 initialized.");
    }
  }
  else
  {
    Serial.println("Failed to initialize PCA9535 at 0x21.");
    digitalWrite(13, LOW); // Turn off indicator LED
  }

  if (pca1Available && pca2Available)
  {
    Serial.println("Both PCA9535 devices initialized successfully.");
    digitalWrite(13, HIGH); // Turn on indicator LED
  }
}

bool isPCAConnected(uint8_t address)
{
  Wire.beginTransmission(address);
  return (Wire.endTransmission() == 0);
}

void writePCA9535(uint8_t address, uint8_t port0, uint8_t port1)
{
  Wire.beginTransmission(address);
  Wire.write(PCA9535_OUTPUT_PORT_0);
  Wire.write(port0);
  Wire.write(port1);
  Wire.endTransmission();
}

void resetI2CBus()
{
  Serial.println("Resetting I²C bus...");

  pinMode(I2C_SCL_PIN, OUTPUT);
  pinMode(I2C_SDA_PIN, INPUT_PULLUP);

  for (int i = 0; i < 10; i++)
  {
    digitalWrite(I2C_SCL_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(I2C_SCL_PIN, LOW);
    delayMicroseconds(10);
  }

  Wire.begin();

  Serial.println("I²C bus reset complete.");
}

// ======================= TC74 Helpers =======================

bool readTC74Temperature(int &tempC)
{
  // Point to temperature register 0x00
  Wire.beginTransmission(TC74_ADDR);
  Wire.write((uint8_t)0x00);
  // Use repeated start so we can immediately read
  if (Wire.endTransmission(false) != 0)
  {
    return false;
  }

  if (Wire.requestFrom((int)TC74_ADDR, 1) != 1)
  {
    return false;
  }

  int8_t raw = (int8_t)Wire.read(); // TC74 returns signed 8-bit °C
  tempC = (int)raw;
  return true;
}

void runTemperatureMonitor()
{
  unsigned long now = millis();
  if (now - lastTempReadMs < TEMP_PERIOD)
    return;

  lastTempReadMs = now;

  int tempC;
  if (readTC74Temperature(tempC))
  {
    Serial.print("TC74 temperature: ");
    Serial.print(tempC);
    Serial.println(" °C");
  }
  else
  {
    Serial.println("TC74 read error");
  }
}

// ======================= Background Tasks =======================

void runRecoveryCheck()
{
  unsigned long now = millis();
  if (now - lastRecoveryCheckMs < RECOVERY_PERIOD)
    return;
  lastRecoveryCheckMs = now;

  bool pca1Connected = isPCAConnected(PCA1_ADDR);
  bool pca2Connected = isPCAConnected(PCA2_ADDR);

  if (!pca1Connected || !pca2Connected)
  {
    Serial.println("PCA9535 not detected. Attempting recovery...");
    delay(100);
    resetI2CBus();
    delay(100);
    initPCA9535();
    writePCA9535(PCA1_ADDR, pca1Port0State, pca1Port1State);
    writePCA9535(PCA2_ADDR, pca2Port0State, pca2Port1State);
  }
}

void runFlashingPatterns()
{
  unsigned long now = millis();
  if (now - lastFlashingTickMs < FLASHING_TICK)
    return;
  lastFlashingTickMs = now;

  for (int i = 0; i < 50; i++)
  {
    FlashingPattern &pattern = flashingPatterns[i];
    if (!pattern.active || pattern.stepCount == 0)
      continue;

    FlashingStep &step = pattern.steps[pattern.currentStep];

    if (!pattern.stepOn)
    {
      updateChannels(step.channelMask, true);
      pattern.stepOn = true;
      pattern.stepStart = now;
    }
    else
    {
      if (now - pattern.stepStart >= step.duration)
      {
        updateChannels(step.channelMask, false);
        pattern.currentStep = (pattern.currentStep + 1) % pattern.stepCount;
        pattern.stepOn = false;
        pattern.stepStart = now;
      }
    }
  }
}

// ======================= CAN Helpers & Decoder =======================

static void printHexByteNoPrefix(uint8_t b)
{
  if (b < 0x10)
    Serial.print("0");
  Serial.print(b, HEX);
}

static void printHexDataCompact(const uint8_t *data, int len)
{
  if (len <= 0)
  {
    Serial.println("<no data>");
    return;
  }
  Serial.print("0x");
  for (int i = 0; i < len; i++)
  {
    printHexByteNoPrefix(data[i]);
  }
  Serial.println();
}

static const char *msgClassToString(uint8_t cls)
{
  switch (cls)
  {
  case 0x00:
    return "Reserved";
  case 0x01:
    return "PCM Control";
  case 0x02:
    return "PCM Status";
  case 0x03:
    return "PCM IO/ADC";
  case 0x04:
    return "Sensor Data";
  case 0x05:
    return "Config";
  case 0x06:
    return "Heartbeat/Discovery";
  default:
    return "Reserved/Unknown";
  }
}

static const char *nodeRangeToString(uint8_t id)
{
  if (id == 0x00)
    return "Unassigned/Reserved";
  else if (id <= 0x1F)
    return "26ch PCM";
  else if (id <= 0x5F)
    return "Small PCM (4ch/etc)";
  else if (id <= 0x8F)
    return "Sensor Node";
  else if (id <= 0xBF)
    return "Controller/HMI/Gateway";
  else if (id <= 0xEF)
    return "Reserved";
  else if (id <= 0xFE)
    return "Group ID";
  else
    return "Broadcast";
}

static const char *subjectToString(uint8_t cls, uint8_t subj)
{
  switch (cls)
  {
  case 0x01: // PCM Control
    switch (subj)
    {
    case 0x00:
      return "Single Channel Command";
    case 0x01:
      return "Bulk Channel Command";
    case 0x02:
      return "PWM Config";
    case 0x03:
      return "Request Status Snapshot";
    default:
      return "PCM Control (other)";
    }
  case 0x02: // PCM Status
    switch (subj)
    {
    case 0x00:
      return "Single Channel Status";
    case 0x01:
      return "Bulk Status Summary";
    case 0x02:
      return "Fault Report";
    case 0x03:
      return "Board Metrics";
    default:
      return "PCM Status (other)";
    }
  case 0x03: // PCM IO/ADC
    switch (subj)
    {
    case 0x00:
      return "ADC Reading";
    case 0x01:
      return "GPIO State";
    default:
      return "PCM IO/ADC (other)";
    }
  case 0x04: // Sensor Data
    switch (subj)
    {
    case 0x00:
      return "Temperature";
    case 0x01:
      return "Pressure";
    case 0x02:
      return "Voltage";
    case 0x03:
      return "Current";
    case 0x04:
      return "Humidity";
    default:
      return "Sensor (custom)";
    }
  case 0x06: // Heartbeat/Discovery
    switch (subj)
    {
    case 0x00:
      return "Heartbeat";
    case 0x01:
      return "Discovery Request";
    default:
      return "HB/Discovery (other)";
    }
  default:
    return "Unknown Subject";
  }
}

static void decodeAndHandleFrame(uint32_t id,
                                 const uint8_t *data,
                                 int len,
                                 bool isExtended,
                                 bool isRTR)
{
  if (!isExtended)
  {
    Serial.println("--------------------------------------------------");
    Serial.print("STD ID 0x");
    Serial.print(id, HEX);
    Serial.print("  DLC ");
    Serial.print(len);
    if (isRTR)
      Serial.print("  [RTR]");
    Serial.println();

    Serial.print("  DATA: ");
    if (isRTR || len == 0)
      Serial.println("<no data>");
    else
      printHexDataCompact(data, len);
    return;
  }

  // 29-bit layout per your spec
  uint8_t priority = (id >> 26) & 0x07;
  uint8_t msgClass = (id >> 21) & 0x1F;
  uint8_t srcNode = (id >> 13) & 0xFF;
  uint8_t dstNode = (id >> 5) & 0xFF;
  uint8_t subject = id & 0x1F;

  Serial.println("--------------------------------------------------");
  Serial.print("ID 0x");
  Serial.print(id, HEX);
  Serial.print("  (EXT)  DLC ");
  Serial.print(len);
  if (isRTR)
    Serial.print("  [RTR]");
  Serial.println();

  Serial.print("  PRIO ");
  Serial.print(priority);
  Serial.print("   CLASS 0x");
  Serial.print(msgClass, HEX);
  Serial.print(" (");
  Serial.print(msgClassToString(msgClass));
  Serial.println(")");

  Serial.print("  SRC 0x");
  Serial.print(srcNode, HEX);
  Serial.print(" (");
  Serial.print(nodeRangeToString(srcNode));
  Serial.println(")");

  Serial.print("  DST 0x");
  Serial.print(dstNode, HEX);
  Serial.print(" (");
  Serial.print(nodeRangeToString(dstNode));
  Serial.println(")");

  Serial.print("  SUBJ 0x");
  Serial.print(subject, HEX);
  Serial.print(" (");
  Serial.print(subjectToString(msgClass, subject));
  Serial.println(")");

  Serial.print("  DATA: ");
  if (isRTR || len == 0)
    Serial.println("<no data>");
  else
    printHexDataCompact(data, len); // 0x1F0200 style

  // Only act on frames addressed to us or broadcast
  bool forThisNode = (dstNode == PCM_NODE_ID) || (dstNode == 0xFF);
  if (!forThisNode || isRTR || len == 0)
    return;

  // Act on PCM Control / Single Channel Command
  if (msgClass == 0x01 && subject == 0x00 && len >= 2)
  {
    uint8_t chIndex = data[0]; // 0–25
    uint8_t cmd = data[1];
    uint8_t duty = (len >= 3) ? data[2] : 0;

    if (chIndex >= 26)
    {
      Serial.print("Switch command: ");
      Serial.println(chIndex);
      updateSwitch(chIndex, (cmd == 0x01)); // Treat as switch ON/OFF
      return;
    }

    uint8_t channel = chIndex + 1; // 1–26 for our API
    bool currentState = channelStates[chIndex];
    bool newState = currentState;

    switch (cmd)
    {
    case 0x00: // OFF
      newState = false;
      Serial.println("  -> CMD: OFF");
      break;
    case 0x01: // ON
      newState = true;
      Serial.println("  -> CMD: ON");
      break;
    case 0x02: // TOGGLE
      newState = !currentState;
      Serial.print("  -> CMD: TOGGLE -> ");
      Serial.println(newState ? "ON" : "OFF");
      break;
    case 0x03: // SET_PWM (for now map to ON/OFF by duty)
      newState = (duty > 0);
      Serial.print("  -> CMD: SET_PWM (duty=");
      Serial.print(duty);
      Serial.print(") -> ");
      Serial.println(newState ? "ON" : "OFF (no PWM HW yet)");
      break;
    default:
      Serial.print("  -> Unknown command: 0x");
      Serial.println(cmd, HEX);
      return;
    }

    updateChannel(channel, newState);
  }
  else
  {
    // Other classes/subjects: just decoded & printed, no action yet
  }
}

void handleCanInput()
{
  int packetSize = mcp.parsePacket();
  if (!packetSize)
    return;

  bool isExtended = mcp.packetExtended();
  bool isRtr = mcp.packetRtr();
  uint32_t id = mcp.packetId();

  uint8_t buf[8];
  int idx = 0;
  while (mcp.available() && idx < packetSize && idx < 8)
  {
    buf[idx++] = mcp.read();
  }

  decodeAndHandleFrame(id, buf, idx, isExtended, isRtr);
}

void handleSerialInput()
{
  while (Serial.available() > 0)
  {
    char c = Serial.read();

    // Treat newline or carriage return as "end of command"
    if (c == '\r' || c == '\n')
    {
      if (serialInput.length() > 0)
      {
        // Example: "on1", "off3", "SWITCH_ON:4", "FULL_UPDATE:1010..."
        processCommand(serialInput);
        serialInput = "";
      }
    }
    else
    {
      // Simple guard so we don't grow without bound
      if (serialInput.length() < 64)
      {
        serialInput += c;
      }
      // If longer than 64 chars, extra input is ignored until newline
    }
  }
}

// ======================= Setup & Loop =======================

void setup()
{
  Serial.begin(115200);
  // delay(5000); // Wait for Serial to initialize

  Serial.println("PCM Controller (RP2040/Pico) with CAN starting...");

  // I2C
  Wire.begin();
  Wire.setClock(50000); // 100kHz standard mode

  // Configure LED on pin 13
  pinMode(13, OUTPUT);
  digitalWrite(13, LOW); // Turn off

  // PCA init
  initPCA9535();

  // Example patterns

  // Chase ++ pattern on switch 6

    flashingPatterns[32] = {
      {{DRIVER_AMBER, 500},
       {PASS_AMBER, 500}},
      2,
      0,
      false,
      false,
      0};

  flashingPatterns[31] = {
      {{DRIVER_AMBER | PASS_DITCH_LOW, 50},
       {EMPTY, 50},
       {DRIVER_AMBER | PASS_DITCH_LOW, 50},
       {EMPTY, 200},
       {PASS_AMBER | DRIVER_DITCH_LOW, 50},
       {EMPTY, 50},
       {PASS_AMBER | DRIVER_DITCH_LOW, 50},
       {EMPTY, 200}},
      8,
      0,
      false,
      false,
      0};

  // CAN init
  if (!mcp.begin(CAN_BAUDRATE))
  {
    Serial.println("Error initializing MCP2515.");
    while (1)
    {
      delay(100);
    }
  }
  Serial.print("MCP2515 initialized at ");
  Serial.print(CAN_BAUDRATE);
  Serial.println(" bps, listening...");

  Serial.print("PCM_NODE_ID = 0x");
  Serial.println(PCM_NODE_ID, HEX);

  Serial.println("PCM Controller ready.");
}

void loop()
{
  // Replace UART input with CAN input
  handleCanInput();

  handleSerialInput(); // For USB debug commands

  runRecoveryCheck();
  runFlashingPatterns();
  // runTemperatureMonitor(); // <-- Periodically read & print TC74 temp

  // Cycle through pcm channels to test
  // for (uint8_t ch = 1; ch <= 26; ch++)
  // {
  //   updateChannel(ch, true);
  //   delay(50);
  //   updateChannel(ch, false);
  //   delay(50);
  // }

  // Small idle if you want
  // delay(1);
}
