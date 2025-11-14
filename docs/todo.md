# Todo



## Feature List

* Turn lights on and off
  * Front Lights
  * Ditch Lights
  * Rock Lights
  * Interior Lights
  * Cargo Lights
  * Rear Lights Amber/White
  * Side Lights
* Control Emergency Lights
  * Code Selector
    * Code 1 - Static Amber
    * Code 2 - Rear Flashing
    * Code 3 - Front & Rear Flashing
  * Flash Pattern Controller
    * Control Flashing over multiple PCM's
    * Logic on the PCM's 
    * Sync code sent over CAN
    * Send command once to flash at xyz pattern/rate
* Control Air Compressor
  * Turn on/off compressor
  * Read tire pressure from truck CAN
  * Read comp pressure from sensor
  * Control Solonoids. 
  * Probably a dedicated Pico for air comp
* Show status
  * Vehicle Voltage
  * PCM Status
  * Channel Status
  * If lights are flashing
  * If Channels are shorted/overloaded
  * Vehicle CAN Data
    * Tire Pressure
    * Drivetrain Status 2hi/4hi/4lo
    * Check Engine Codes