#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ---------------------- Pins ----------------------
#define ONE_WIRE_BUS 7
#define MOSFET_PIN   28

// ---------------------- Sensor ----------------------
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// ---------------------- Temperature control ----------------------
double Input = 0.0;
double targetTemp = 24.0;
const double HYSTERESIS_BAND = 0.25;

bool heaterOn = false;

// ---------------------- Timing ----------------------
unsigned long lastTempRead = 0;
const unsigned long tempInterval = 500;  // ms

// ---------------------- Segment logging ----------------------
const unsigned long logInterval = 30000;  // log every 30 s (control still at 500 ms)
const uint16_t MAX_LOG_SAMPLES = 512;     // ~4.3 h at 30 s intervals
float logBuffer[MAX_LOG_SAMPLES];
uint16_t logCount = 0;
bool loggingActive = false;
unsigned long lastLogWrite = 0;

String serialLine;

double heaterOnThreshold() {
  return targetTemp - HYSTERESIS_BAND;
}

double heaterOffThreshold() {
  return targetTemp + HYSTERESIS_BAND;
}

void applyHeaterControl() {
  if (Input <= heaterOnThreshold()) {
    heaterOn = true;
  } else if (Input >= heaterOffThreshold()) {
    heaterOn = false;
  }
  digitalWrite(MOSFET_PIN, heaterOn ? HIGH : LOW);
}

bool parseSetCommand(const String &line) {
  int comma = line.indexOf(',');
  if (comma < 0) {
    return false;
  }
  float value = line.substring(comma + 1).toFloat();
  if (value < 0.0f || value > 80.0f) {
    return false;
  }
  targetTemp = value;
  return true;
}

void handleSerialCommand(const String &line) {
  if (line.length() == 0) {
    return;
  }

  if (line.startsWith("SET,")) {
    if (parseSetCommand(line)) {
      Serial.print("OK,SET,");
      Serial.println(targetTemp, 2);
    } else {
      Serial.println("ERR,SET");
    }
    return;
  }

  if (line == "GET") {
    Serial.print("OK,TEMP,");
    Serial.print(Input, 3);
    Serial.print(",");
    Serial.print(targetTemp, 2);
    Serial.print(",");
    Serial.print(heaterOn ? 1 : 0);
    Serial.println();
    return;
  }

  if (line == "LOG,START") {
    logCount = 0;
    lastLogWrite = 0;
    loggingActive = true;
    Serial.println("OK,LOG,START");
    return;
  }

  if (line == "LOG,STOP") {
    loggingActive = false;
    Serial.print("OK,LOG,DATA,");
    Serial.print(logCount);
    for (uint16_t i = 0; i < logCount; i++) {
      Serial.print(",");
      Serial.print(logBuffer[i], 3);
    }
    Serial.println();
    return;
  }

  if (line == "PING") {
    Serial.println("OK,PONG");
    return;
  }

  Serial.println("ERR,UNKNOWN");
}

void processSerialInput() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialLine.length() > 0) {
        serialLine.trim();
        handleSerialCommand(serialLine);
        serialLine = "";
      }
    } else {
      serialLine += c;
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000);

  pinMode(MOSFET_PIN, OUTPUT);
  digitalWrite(MOSFET_PIN, LOW);

  sensors.begin();
  sensors.setResolution(11);

  Serial.println("OK,READY");
  Serial.print("Number of sensors found: ");
  Serial.println(sensors.getDeviceCount());
}

void loop() {
  unsigned long now = millis();
  processSerialInput();

  if (now - lastTempRead >= tempInterval) {
    lastTempRead = now;

    sensors.requestTemperatures();
    float tempC = sensors.getTempCByIndex(0);

    if (tempC == DEVICE_DISCONNECTED_C) {
      heaterOn = false;
      digitalWrite(MOSFET_PIN, LOW);
      Serial.println("ERR,SENSOR");
      return;
    }

    Input = tempC;
    applyHeaterControl();

    if (loggingActive && logCount < MAX_LOG_SAMPLES) {
      if (lastLogWrite == 0 || (now - lastLogWrite >= logInterval)) {
        lastLogWrite = now;
        logBuffer[logCount++] = tempC;
      }
    }
  }

  static unsigned long lastPrint = 0;
  if (now - lastPrint >= 1000) {
    lastPrint = now;
    Serial.print("DBG,TEMP,");
    Serial.print(Input, 3);
    Serial.print(",SET,");
    Serial.print(targetTemp, 2);
    Serial.print(",ON,");
    Serial.print(heaterOnThreshold(), 2);
    Serial.print(",OFF,");
    Serial.print(heaterOffThreshold(), 2);
    Serial.print(",HEATER,");
    Serial.println(heaterOn ? 1 : 0);
  }
}
