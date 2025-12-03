#include <Arduino.h>
#include <Adafruit_DotStar.h>
#include "pico/bootrom.h"
#include <Adafruit_TCA8418.h>

void enter_bootsel()
{
  delay(50);
  reset_usb_boot(0, 0);
}

// -------- APA102 Config --------
#define TOP_NUM_LEDS 18
#define TOP_DATAPIN 2  // GP2
#define TOP_CLOCKPIN 3 // GP3
#define BOTTOM_NUM_LEDS 45
#define BOTTOM_DATAPIN 14  // GP14
#define BOTTOM_CLOCKPIN 15 // GP15

Adafruit_DotStar strip_top(TOP_NUM_LEDS, TOP_DATAPIN, TOP_CLOCKPIN, DOTSTAR_BRG);
Adafruit_DotStar strip_bottom(BOTTOM_NUM_LEDS, BOTTOM_DATAPIN, BOTTOM_CLOCKPIN, DOTSTAR_BRG);

// -------- TCA8418 (Keypad) --------
#define TCA_ADDR TCA8418_DEFAULT_ADDR // 0x34 unless A0..A2 changed
#define TCA_ROWS 8
#define TCA_COLS 10
Adafruit_TCA8418 keypad;

// -------- Local 5x2 hand-scan pins (top board) --------
static const uint8_t ROWS[5] = {11, 12, 6, 7, 8};
static const uint8_t COLS[2] = {9, 10};

// -------- Debounce (for 5x2 hand-scan only) --------
struct Btn
{
  bool stable = false, lastStable = false, reading = false;
  uint32_t lastChange = 0;
};
static Btn buttons[10];
static const uint16_t DEBOUNCE_MS = 20;
inline uint8_t idxRC(uint8_t r, uint8_t c) { return r * 2 + c; }

// -------- Mapping (one LED per button) --------
struct LedBinding
{
  uint8_t stripId;
  int16_t pixel;
}; // 0=TOP, 1=BOTTOM
struct ButtonDef
{
  const char *name;
  LedBinding led;
  uint8_t row;
  uint8_t col;
};

inline Adafruit_DotStar &getStrip(uint8_t id) { return (id == 0) ? strip_top : strip_bottom; }
inline void setLED(const LedBinding &lb, uint8_t r, uint8_t g, uint8_t b)
{
  if (lb.pixel < 0)
    return;
  getStrip(lb.stripId).setPixelColor(lb.pixel, r, g, b);
}
inline void showLEDs()
{
  strip_top.show();
  strip_bottom.show();
}
inline void setIdle(const LedBinding &lb) { setLED(lb, 255, 160, 0); }   // amber
inline void setActive(const LedBinding &lb) { setLED(lb, 0, 255, 255); } // cyan

// ---- TOP (5x2) — order matches idxRC(r,c) so debounce can index by i directly
static const ButtonDef TOP_MAP[10] = {
    /* r0c0 */ {"HORN", {0, 3}, 0, 0},
    /* r0c1 */ {"SIREN", {0, 2}, 0, 1},
    /* r1c0 */ {"LIGHT FRONT", {0, 11}, 1, 0},
    /* r1c1 */ {"LIGHT RIGHT", {0, 14}, 1, 1},
    /* r2c0 */ {"LIGHT LEFT", {0, 15}, 2, 0},
    /* r2c1 */ {"SIREN SHARP", {0, 0}, 2, 1},
    /* r3c0 */ {"MANUAL", {0, 4}, 3, 0},
    /* r3c1 */ {"SIREN TOOTH", {0, 1}, 3, 1},
    /* r4c0 */ {"ORANGE BUTTON", {0, 12}, 4, 0},
    /* r4c1 */ {"PA", {0, 13}, 4, 1},
};

// ---- BOTTOM (TCA) — your 38 mappings with explicit row/col
static const ButtonDef BOTTOM_MAP[38] = {
    /* r0c0 */ {"NUM_3", {1, 36}, 0, 0},
    /* r0c1 */ {"NUM_6", {1, 35}, 0, 1},
    /* r0c2 */ {"NUM_9", {1, 34}, 0, 2},
    /* r0c3 */ {"NUM_#", {1, 33}, 0, 3},
    /* r0c4 */ {"COMPUTER", {1, 32}, 0, 4},
    /* r0c5 */ {"HOME", {1, 25}, 0, 5},

    /* r1c0 */ {"NUM_2", {1, 37}, 1, 0},
    /* r1c1 */ {"NUM_5", {1, 38}, 1, 1},
    /* r1c2 */ {"NUM_8", {1, 39}, 1, 2},
    /* r1c3 */ {"NUM_0", {1, 40}, 1, 3},
    /* r1c4 */ {"DPAD_RIGHT", {1, 31}, 1, 4},
    /* r1c5 */ {"DPAD_DOWN", {1, 28}, 1, 5},

    /* r2c0 */ {"NUM_1", {1, 44}, 2, 0},
    /* r2c1 */ {"NUM_4", {1, 43}, 2, 1},
    /* r2c2 */ {"NUM_7", {1, 42}, 2, 2},
    /* r2c3 */ {"NUM_*", {1, 41}, 2, 3},
    /* r2c4 */ {"DPAD_UP", {1, 30}, 2, 4},
    /* r2c5 */ {"DPAD_LEFT", {1, 29}, 2, 5},

    /* r3c6 */ {"T_ROW5", {1, 0}, 3, 6},
    /* r3c7 */ {"LIGHTBULB", {1, 12}, 3, 7},
    /* r3c8 */ {"B_ROW5", {1, 23}, 3, 8},
    /* r3c9 */ {"P5", {1, 24}, 3, 9},

    /* r4c6 */ {"T_ROW4", {1, 1}, 4, 6},
    /* r4c7 */ {"DAY/NIGHT", {1, 11}, 4, 7},
    /* r4c8 */ {"B_ROW4", {1, 21}, 4, 8},
    /* r4c9 */ {"P4", {1, 22}, 4, 9},

    /* r5c6 */ {"T_ROW3", {1, 2}, 5, 6},
    /* r5c7 */ {"BRIGHT -", {1, 10}, 5, 7},
    /* r5c8 */ {"B_ROW3", {1, 19}, 5, 8},
    /* r5c9 */ {"P3", {1, 20}, 5, 9},

    /* r6c6 */ {"T_ROW2", {1, 3}, 6, 6},
    /* r6c7 */ {"BRIGHT +", {1, 9}, 6, 7},
    /* r6c8 */ {"B_ROW2", {1, 17}, 6, 8},
    /* r6c9 */ {"P2", {1, 18}, 6, 9},

    /* r7c6 */ {"T_ROW1", {1, 4}, 7, 6},
    /* r7c7 */ {"POWER", {1, 5}, 7, 7},
    /* r7c8 */ {"B_ROW1", {1, 15}, 7, 8},
    /* r7c9 */ {"P1", {1, 16}, 7, 9},
};

// ---- helpers to find a mapping by (row,col)
int8_t findTopByRC(uint8_t r, uint8_t c)
{
  uint8_t i = idxRC(r, c);
  if (i < 10 && TOP_MAP[i].row == r && TOP_MAP[i].col == c)
    return i;
  return -1;
}
int8_t findBottomByRC(uint8_t r, uint8_t c)
{
  for (uint8_t i = 0; i < 38; ++i)
    if (BOTTOM_MAP[i].row == r && BOTTOM_MAP[i].col == c)
      return i;
  return -1;
}

// -------- Hand-scan (top 5x2 only) --------
void scanMatrixRaw(bool out[5][2])
{
  for (uint8_t r = 0; r < 5; ++r)
  {
    digitalWrite(ROWS[r], LOW);
    delayMicroseconds(60);
    for (uint8_t c = 0; c < 2; ++c)
      out[r][c] = (digitalRead(COLS[c]) == LOW);
    digitalWrite(ROWS[r], HIGH);
  }
}
void debounceAndReport(const bool raw[5][2])
{
  uint32_t now = millis();
  for (uint8_t r = 0; r < 5; ++r)
  {
    for (uint8_t c = 0; c < 2; ++c)
    {
      uint8_t i = idxRC(r, c);
      Btn &b = buttons[i];
      bool rawPressed = raw[r][c];

      if (rawPressed != b.reading)
      {
        b.reading = rawPressed;
        b.lastChange = now;
      }
      else if ((now - b.lastChange) >= DEBOUNCE_MS && b.stable != b.reading)
      {
        b.lastStable = b.stable;
        b.stable = b.reading;
        if (b.stable != b.lastStable)
        {
          const ButtonDef &def = TOP_MAP[i];
          Serial.print(b.stable ? "PRESS  " : "RELEASE ");
          Serial.print(def.name);
          Serial.print("  r=");
          Serial.print(r);
          Serial.print(" c=");
          Serial.println(c);
          if (b.stable)
            setActive(def.led);
          else
            setIdle(def.led);
          showLEDs();
        }
      }
    }
  }
}

// -------- Setup / Loop --------
void setup()
{
  Serial.begin(115200);
  delay(100);
  Serial.println("DB10: polling TCA + single-LED-per-button on top & bottom");

  // LED strips
  strip_top.begin();
  strip_top.show();
  strip_top.setBrightness(128);
  strip_bottom.begin();
  strip_bottom.show();
  strip_bottom.setBrightness(128);

  // Init all mapped LEDs to idle
  for (uint8_t i = 0; i < 10; ++i)
    setIdle(TOP_MAP[i].led);
  for (uint8_t i = 0; i < 38; ++i)
    setIdle(BOTTOM_MAP[i].led);
  showLEDs();

  // TCA bring-up
  Wire.begin();
  if (!keypad.begin(TCA_ADDR, &Wire))
  {
    Serial.println(F("ERROR: TCA8418 not found at 0x34. Check wiring/pull-ups."));
  }
  else
  {
    keypad.matrix(TCA_ROWS, TCA_COLS);
    keypad.flush();
    keypad.enableInterrupts();
    Serial.println(F("TCA8418 ready (polling)."));
  }

  // Local 5x2 hand-scan pins (top board)
  for (uint8_t r = 0; r < 5; ++r)
  {
    pinMode(ROWS[r], OUTPUT);
    digitalWrite(ROWS[r], HIGH);
  }
  for (uint8_t c = 0; c < 2; ++c)
    pinMode(COLS[c], INPUT_PULLUP);
}

void loop()
{
  // ---- POLL TCA (no INT pin) ----
  int intStat = keypad.readRegister(TCA8418_REG_INT_STAT);

  if (intStat & 0x02)
  { // GPIO ints: read/clear (even if unused)
    keypad.readRegister(TCA8418_REG_GPIO_INT_STAT_1);
    keypad.readRegister(TCA8418_REG_GPIO_INT_STAT_2);
    keypad.readRegister(TCA8418_REG_GPIO_INT_STAT_3);
    keypad.writeRegister(TCA8418_REG_INT_STAT, 0x02);
  }

  if (intStat & 0x01)
  {                        // Key events present
    bool needShow = false; // batch LED .show() once
    while (keypad.available())
    {
      int keyCode = keypad.getEvent();
      if (!keyCode)
        break;

      bool isPress = (keyCode & 0x80);
      uint8_t code = (keyCode & 0x7F);

      if (code <= 96)
      {
        code--;
        uint8_t row = code / 10, col = code % 10;

        // *** TCA == BOTTOM ONLY ***
        int8_t bi = findBottomByRC(row, col);
        if (bi >= 0)
        {
          const ButtonDef &def = BOTTOM_MAP[bi];
          Serial.print(isPress ? F("PRESS  ") : F("RELEASE "));
          Serial.print(def.name);
          Serial.print(F("  row="));
          Serial.print(row);
          Serial.print(F(" col="));
          Serial.println(col);

          if (isPress)
            setActive(def.led);
          else
            setIdle(def.led);
          needShow = true;
        }
        else
        {
          Serial.print(isPress ? F("PRESS  ") : F("RELEASE "));
          Serial.print(F("UNMAPPED row="));
          Serial.print(row);
          Serial.print(F(" col="));
          Serial.println(col);
        }
      }
      else
      {
        uint8_t gpio = code - 97;
        Serial.print(isPress ? F("PRESS  GPIO ") : F("RELEASE GPIO "));
        Serial.println(gpio);
      }
    }
    if (needShow)
      showLEDs();
    keypad.writeRegister(TCA8418_REG_INT_STAT, 0x01); // clear key flag
  }

  // ---- Local hand-scan for the top 5x2 (kept for bring-up) ----
  bool raw[5][2];
  scanMatrixRaw(raw);
  debounceAndReport(raw);

  // BOOTSEL command
  if (Serial.available())
  {
    String s = Serial.readStringUntil('\n');
    s.trim();
    if (s.equalsIgnoreCase("boot"))
    {
      Serial.println("Rebooting to BOOTSEL...");
      delay(100);
      reset_usb_boot(0, 0);
    }
  }

  delay(5);
}
