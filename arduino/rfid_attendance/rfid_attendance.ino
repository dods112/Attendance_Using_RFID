/*
  rfid_attendance.ino
  Reads RFID cards and sends each UID to the PC as "UID:XXXXXXXX".
  Shows messages on the LCD and beeps when the PC sends "LCD|line1|line2".
*/

#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#define SS_PIN     10
#define RST_PIN    9
#define BUZZER_PIN 8
#define LCD_ADDR   0x27   // if the LCD stays blank, try 0x3F

MFRC522 rfid(SS_PIN, RST_PIN);
LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);

bool showingMessage = false;
unsigned long messageUntil = 0;

void beep(int freq, int ms) {
  tone(BUZZER_PIN, freq, ms);
  delay(ms);
  noTone(BUZZER_PIN);
}

void beepSuccess() {          // two short high beeps
  beep(2500, 120);
  delay(80);
  beep(2500, 120);
}

void beepFailure() {          // one long low beep
  beep(400, 500);
}

void printLine(String text) {
  if (text.length() > 16) text = text.substring(0, 16);
  lcd.print(text);
}

void showIdle() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("RFID ATTENDANCE");
  lcd.setCursor(0, 1);
  lcd.print("SCAN YOUR CARD");
  showingMessage = false;
}

void showMessage(String line1, String line2, unsigned long ms) {
  lcd.clear();
  lcd.setCursor(0, 0);
  printLine(line1);
  lcd.setCursor(0, 1);
  printLine(line2);
  showingMessage = true;
  messageUntil = millis() + ms;
}

void sendUid() {
  Serial.print("UID:");
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) Serial.print("0");
    Serial.print(rfid.uid.uidByte[i], HEX);
  }
  Serial.println();
}

void handleSerialCommand() {
  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();

  // Expected format: LCD|WELCOME, NAME|ATTENDANCE SAVED
  if (line.startsWith("LCD|")) {
    int first = line.indexOf('|');
    int second = line.indexOf('|', first + 1);
    if (second > first) {
      String l1 = line.substring(first + 1, second);
      String l2 = line.substring(second + 1);
      showMessage(l1, l2, 2500);

      // Failure beep for unregistered, duplicate, or outside-time results
      String combined = l1 + " " + l2;
      if (combined.indexOf("UNKNOWN") >= 0 ||
          combined.indexOf("ALREADY") >= 0 ||
          combined.indexOf("OUTSIDE") >= 0 ||
          combined.indexOf("WRONG") >= 0) {
        beepFailure();
      } else {
        beepSuccess();
      }
    }
  }
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  Serial.begin(9600);
  SPI.begin();
  rfid.PCD_Init();

  lcd.init();
  lcd.backlight();
  showIdle();

  beepSuccess();  // startup beep confirms the buzzer is wired
}

void loop() {
  handleSerialCommand();

  if (showingMessage && millis() > messageUntil) {
    showIdle();
  }

  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    return;
  }

  beep(2000, 60);  // short tick on every card read
  showMessage("VERIFYING CARD...", "", 1500);
  sendUid();

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(800);  // short pause so one tap is not read twice
}