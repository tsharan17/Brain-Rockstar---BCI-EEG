int eegPin = 34;
int ledPin = 2;

float baseline = 0;
float alpha = 0.01;

void setup() {
  Serial.begin(115200);
  pinMode(ledPin, OUTPUT);

  // Initial calibration
  for (int i = 0; i < 200; i++) {
    baseline += analogRead(eegPin);
    delay(5);
  }
  baseline /= 200;
}

void loop() {
  int eegValue = analogRead(eegPin);

  // Update baseline slowly
  baseline = (1 - alpha) * baseline + alpha * eegValue;

  int diff = abs(eegValue - baseline);

  // LED trigger
  if (diff > 300) {
    digitalWrite(ledPin, HIGH);
  } else {
    digitalWrite(ledPin, LOW);
  }

  // 👇 IMPORTANT: Serial Plotter format
  Serial.print(eegValue);
  Serial.print(" ");
  Serial.print(baseline);
  Serial.print(" ");
  Serial.println(diff);

  delay(5);
}