#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <BLEClient.h>
#include <BLERemoteCharacteristic.h>

const char* targetName = "MyoWare_EMG";
const char* serviceUUIDStr = "12345678-1234-1234-1234-1234567890ab";
const char* charUUIDStr    = "abcdefab-1234-5678-1234-abcdefabcdef";

BLEAddress foundAddress((uint8_t*)"\0");
bool found = false;

static void notifyCallback(
  BLERemoteCharacteristic* c,
  uint8_t* data,
  size_t length,
  bool isNotify
) {
  for (int i = 0; i < length; i++) {

  String value = "";

for (int i = 0; i < length; i++) {
  value += (char)data[i];
}

Serial.println(value);
}

void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println("RECEIVER: init");

  BLEDevice::init("");
}

void loop() {

  // 🔍 Scan for sender
  if (!found) {
    Serial.println("RECEIVER: scanning...");

    BLEScan* scan = BLEDevice::getScan();
    scan->setActiveScan(true);
    scan->setInterval(100);
    scan->setWindow(99);

    BLEScanResults* results = scan->start(5);

    int count = results->getCount();

    for (int i = 0; i < count; i++) {
      BLEAdvertisedDevice d = results->getDevice(i);

      String name = d.haveName() ? String(d.getName().c_str()) : "";

      if (name.equals(targetName)) {
        foundAddress = d.getAddress();
        found = true;
        Serial.println("TARGET FOUND");
        break;
      }
    }

    scan->clearResults();
    delay(500);
    return;
  }

  // 🔗 Connect
  Serial.println("Connecting...");

  BLEClient* client = BLEDevice::createClient();

  if (!client->connect(foundAddress)) {
    Serial.println("Connect failed");
    delete client;
    found = false;
    return;
  }

  Serial.println("Connected!");

  // 🔍 Get service
  BLERemoteService* service = client->getService(BLEUUID(serviceUUIDStr));

  if (!service) {
    Serial.println("Service not found");
    client->disconnect();
    delete client;
    found = false;
    return;
  }

  // 🔍 Get characteristic
  BLERemoteCharacteristic* remoteChar =
    service->getCharacteristic(BLEUUID(charUUIDStr));

  if (!remoteChar) {
    Serial.println("Characteristic not found");
    client->disconnect();
    delete client;
    found = false;
    return;
  }

  // 📡 Subscribe
  remoteChar->registerForNotify(notifyCallback);

  Serial.println("Streaming EMG...");

  // 🔄 Stay connected
  while (client->isConnected()) {
    delay(10);
  }

  Serial.println("Disconnected...");
  delete client;
  found = false;
}