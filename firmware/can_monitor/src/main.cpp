#include <Arduino.h>
#include <Adafruit_MCP2515.h>

// ======================= CAN Config =======================

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

// Adjust pins here as needed for your board / wiring
Adafruit_MCP2515 mcp(19, 15, 8, 14);

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
  // Just decode & print — no control logic, no I2C, no channel updates.

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

  // No further action: purely a CAN sniffer / logger now.
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

// ======================= Setup & Loop =======================

void setup()
{
  Serial.begin(115200);
  // delay(5000); // optional: wait for Serial monitor

  Serial.println("Simple CAN sniffer starting...");

  // Optional LED indicator
  pinMode(13, OUTPUT);
  digitalWrite(13, LOW);

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
  Serial.println("CAN sniffer ready.");
}

void loop()
{
  handleCanInput();
  // Small idle if desired
  // delay(1);
}
