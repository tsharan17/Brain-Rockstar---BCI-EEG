#include <Wire.h>
#include <Adafruit_ADS1X15.h>

// ========== CONFIGURATION ==========
const int SAMPLE_RATE = 250;  // Hz - MUST match Python code
const int DELAY_US = 1000000 / SAMPLE_RATE;

// Create ADS1115 object
Adafruit_ADS1115 ads;

// Timing
unsigned long lastSampleTime = 0;

// Statistics for diagnostics
unsigned long lastDiagnostic = 0;
const unsigned long DIAGNOSTIC_INTERVAL = 3000;  // 3 seconds
int sampleCount = 0;
float minVoltage = 999.0;
float maxVoltage = -999.0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n╔════════════════════════════════════╗");
  Serial.println("║   AD8232 EEG SYSTEM - READY       ║");
  Serial.println("╚════════════════════════════════════╝\n");
  
  // Initialize I2C
  Wire.begin(21, 22);  // SDA=21, SCL=22
  
  // Initialize ADS1115
  if (!ads.begin()) {
    Serial.println("❌ ERROR: ADS1115 not found!");
    Serial.println("Check connections:");
    Serial.println("  - VDD → 3.3V");
    Serial.println("  - GND → GND");
    Serial.println("  - SCL → GPIO 22");
    Serial.println("  - SDA → GPIO 21");
    while (1) {
      delay(1000);
    }
  }
  
  Serial.println("✅ ADS1115 initialized successfully");
  
  // Configure ADS1115 for AD8232
  // AD8232 outputs 0-3.3V centered at ~1.65V
  ads.setGain(GAIN_ONE);  // ±4.096V range (covers 0-3.3V)
  ads.setDataRate(RATE_ADS1115_860SPS);  // Maximum speed
  
  Serial.println("✅ Gain set to ±4.096V");
  Serial.println("✅ Sample rate: 860 SPS");
  
  // Test read
  delay(100);
  int16_t testRead = ads.readADC_Differential_0_1();
  float testVoltage = ads.computeVolts(testRead);
  
  Serial.print("\n📊 Initial reading: ");
  Serial.print(testVoltage, 6);
  Serial.println("V");
  
  if (testVoltage < 0.5 || testVoltage > 2.5) {
    Serial.println("\n⚠️  WARNING: Initial voltage out of range!");
    Serial.println("Expected: 1.0V - 2.0V (AD8232 baseline)");
    Serial.println("Check:");
    Serial.println("  - AD8232 VCC connected to 3.3V");
    Serial.println("  - AD8232 SDN connected to 3.3V (enables chip)");
    Serial.println("  - AD8232 OUTPUT connected to ADS1115 A0");
    Serial.println("  - ADS1115 A1 connected to GND");
  } else {
    Serial.println("✅ Baseline voltage looks good!");
  }
  
  Serial.println("\n🧠 Starting EEG acquisition at 250 Hz...");
  Serial.println("   (Data streaming to Python)\n");
  
  delay(500);
}

void loop() {
  unsigned long currentTime = micros();
  
  // Maintain precise sampling rate
  if (currentTime - lastSampleTime >= DELAY_US) {
    lastSampleTime = currentTime;
    
    // Read differential voltage (A0 - A1)
    // A0 = AD8232 output (signal)
    // A1 = GND (reference)
    int16_t adc_value = ads.readADC_Differential_0_1();
    float voltage = ads.computeVolts(adc_value);
    
    // Center the signal at 0V for better visualization
    // AD8232 baseline is ~1.65V, so subtract it
    voltage = voltage - 1.65;
    
    // Send to Python (ONLY the number, no extra text!)
    Serial.println(voltage, 6);  // 6 decimal places
    
    // Track statistics
    sampleCount++;
    if (voltage < minVoltage) minVoltage = voltage;
    if (voltage > maxVoltage) maxVoltage = voltage;
  }
  
  // Periodic diagnostics (won't interfere with Python)
  // These appear in Arduino Serial Monitor, not Python
  unsigned long currentMillis = millis();
  if (currentMillis - lastDiagnostic >= DIAGNOSTIC_INTERVAL) {
    lastDiagnostic = currentMillis;
    
    // Only print diagnostics if Serial Monitor is open
    // (These lines start with special character so Python ignores them)
    // Commenting out for now to avoid any interference
    
    /*
    Serial.print("# Samples: ");
    Serial.print(sampleCount);
    Serial.print(" | Range: ");
    Serial.print(maxVoltage - minVoltage, 6);
    Serial.print("V | Rate: ");
    Serial.print(sampleCount / 3.0);
    Serial.println(" Hz");
    */
    
    // Reset counters
    minVoltage = 999.0;
    maxVoltage = -999.0;
    sampleCount = 0;
  }
}