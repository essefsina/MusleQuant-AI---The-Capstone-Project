#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLEAdvertising.h>
#include <BLECharacteristic.h>

BLECharacteristic *pCharacteristic;

#define EMG_PIN 34  // Change if needed

void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println("SENDER: boot");

  BLEDevice::init("MyoWare_EMG");

  BLEServer *server = BLEDevice::createServer();

  BLEService *service = server->createService(
    "12345678-1234-1234-1234-1234567890ab"
  );

  pCharacteristic = service->createCharacteristic(
    "abcdefab-1234-5678-1234-abcdefabcdef",
    BLECharacteristic::PROPERTY_NOTIFY | BLECharacteristic::PROPERTY_READ
  );

  pCharacteristic->setValue("0");

  service->start();

  BLEAdvertising *adv = BLEDevice::getAdvertising();
  adv->addServiceUUID("12345678-1234-1234-1234-1234567890ab");
  adv->start();

  Serial.println("SENDER: advertising MyoWare_EMG");
}

void loop() {
  int emgValue = analogRead(EMG_PIN);

  // Optional: center signal (helps visualization)
  emgValue = abs(emgValue - 2048);

  char buffer[16];
  sprintf(buffer, "%d", emgValue);

  pCharacteristic->setValue(buffer);
  pCharacteristic->notify();

  Serial.println(buffer);

  delay(20); // ~50Hz
}