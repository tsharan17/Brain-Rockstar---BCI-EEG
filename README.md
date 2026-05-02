<div align="center">

# 🧠 EEG-Based Brain-Computer Interface

**A low-cost, open-source BCI prototype built on ESP32 + EXG BioAmp Pill + Python**

Real-time EEG acquisition · Eye-blink detection · Alpha/Beta brain-state classification

![Platform](https://img.shields.io/badge/platform-ESP32-blue?style=flat-square)
![Language](https://img.shields.io/badge/python-3.9%2B-yellow?style=flat-square)
![Status](https://img.shields.io/badge/status-alpha%20prototype-orange?style=flat-square)
![Cost](https://img.shields.io/badge/BOM%20cost-under%20%2425-green?style=flat-square)

</div>

---

> ⚠️ **Safety Notice:** This design has no medical-grade electrical isolation. Always power the system from a **USB battery bank** — never a mains-connected USB port — when electrodes are in contact with skin.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Prototype Status](#-prototype-status)
- [System Architecture](#️-system-architecture)
- [Hardware Requirements](#-hardware-requirements)
- [Software Dependencies](#-software-dependencies)
- [Circuit Summary](#-circuit-summary)
- [Quick Start](#-quick-start)
- [ESP32 Firmware](#-esp32-firmware)
- [Python Analyzer](#-python-analyzer)
- [Configuration Reference](#️-configuration-reference)
- [Signal Processing Pipeline](#-signal-processing-pipeline)
- [Brain-State Classification](#-brain-state-classification)
- [Serial Data Format](#-serial-data-format)
- [Dashboard Overview](#️-dashboard-overview)
- [Results & Performance](#-results--performance)
- [Known Limitations](#-known-limitations)
- [Troubleshooting](#️-troubleshooting)
- [Roadmap](#️-roadmap)

---

## 🔍 Overview

This project implements a complete EEG-BCI stack on accessible, off-the-shelf hardware.

The **ESP32 firmware** samples differential bio-signals from an EXG BioAmp Pill through the onboard 12-bit ADC, performs adaptive EMA baseline tracking, triggers an LED on blink events, and streams three-value packets over UART at 115200 baud.

The **Python analyzer** (`bci_v2.py`) ingests that stream in a background thread, runs Welch PSD analysis, computes relative alpha/beta band powers, and drives a live six-panel Matplotlib dashboard that classifies brain state as **FOCUS** or **RELAX** in real time.

No proprietary software. No dedicated EEG dongle. Total BOM cost well under ₹2,000 / $25 USD.

---

## 🟡 Prototype Status

| Dimension            | Status                                                        |
| :------------------- | :------------------------------------------------------------ |
| Maturity             | Alpha — lab prototyping only, not for medical use             |
| Channels             | Single EEG channel (FP1 vs. FP2 differential)                |
| Blink Detection      | ✅ Threshold + differential method, ~88% accuracy             |
| Band Classification  | ✅ Alpha / Beta relative power via Welch PSD                  |
| Artifact Rejection   | ❌ Not yet implemented                                        |
| Multi-channel        | ❌ Planned                                                    |
| Electrical Isolation | ❌ Not included — use battery-powered hardware only           |

---

## 🏗️ System Architecture

```
Brain (µV)
    │
    ▼
Ag/AgCl Electrodes  (FP1, FP2, Ear Lobe)
    │
    ▼
EXG BioAmp Pill  ──  Gain ≈ 1000×  │  BW: 0.5–40 Hz  │  3.3 V single-supply
    │
    ▼
LM358 Op-Amp  ──  Unity-gain voltage follower (impedance buffer)
    │
    ▼
RC Low-Pass Filter  ──  10 kΩ + 100 nF  →  f_c ≈ 159 Hz
    │
    ▼
ESP32 GPIO34  ──  12-bit ADC  │  ~200 Hz sampling
    │
    ├── Adaptive EMA baseline tracking
    ├── Blink threshold: diff > 300  →  LED on GPIO2
    └── UART stream @ 115200 baud:  "eegValue  baseline  diff\n"
                │
                ▼
        Python  bci_v2.py
            ├── Serial reader thread  (512-sample deque)
            ├── Welch PSD  (Hann window · nperseg=128 · noverlap=64)
            ├── Band power  (α: 8–12 Hz · β: 13–30 Hz)
            ├── β − α state machine  (FOCUS / RELAX)
            └── Live Matplotlib dashboard  (6-panel · TkAgg · ~10 fps)
```

---

## 🔧 Hardware Requirements

| Component            | Specification / Notes                                                            |
| :------------------- | :------------------------------------------------------------------------------- |
| **ESP32**            | Any dev board with GPIO34 (ADC1_CH6) and GPIO2 · dual-core 240 MHz · 12-bit ADC |
| **EXG BioAmp Pill**  | Single-supply bio-amplifier · Gain ≈ 1000× · BW: 0.5–40 Hz · 3.3 V operation   |
| **Electrodes**       | Ag/AgCl disposable gel · FP1 (active) · FP2 (reference) · Ear Lobe (ground)     |
| **LM358 Op-Amp**     | DIP-8 or SMD · Op-Amp A only (pins 1–3) wired as voltage follower               |
| **Resistor**         | 10 kΩ — between LM358 output and GPIO34                                         |
| **Capacitor**        | 100 nF — between GPIO34 and GND (RC anti-aliasing filter)                       |
| **LED + Resistor**   | Any 3–5 mm LED with 220 Ω series resistor on GPIO2                              |
| **Power**            | 3.3 V for EXG Pill + LM358 · **battery pack required for skin contact**          |
| **USB Cable**        | USB to host PC · Windows 10+ tested · Linux/macOS also supported                |

---

## 💻 Software Dependencies

**Python 3.9 or newer** is required.

```bash
pip install numpy matplotlib scipy pyserial
```

**Recommended — virtual environment setup:**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install numpy matplotlib scipy pyserial
```

> **TkAgg not available?** Install `PyQt5` and swap the backend in `bci_v2.py`:
> ```bash
> pip install pyqt5
> # Change:  matplotlib.use("TkAgg")  →  matplotlib.use("Qt5Agg")
> ```

**Firmware (Arduino IDE or PlatformIO):**
- Board package: `esp32` by Espressif — install via Arduino Board Manager
- No external libraries needed — uses only built-in `analogRead`, `digitalWrite`, `Serial`

---

## ⚡ Circuit Summary

See **[`PIN_CONNECTIONS.md`](PIN_CONNECTIONS.md)** for the complete pin-by-pin wiring table, full ASCII schematic, and LM358 pinout diagram.

**Signal path in brief:**

```
FP1 ──► EXG IN+          FP2 ──► EXG IN−          Ear Lobe ──► EXG GND_E
EXG OUT ──► LM358 Pin 3 (+)
LM358 Pin 1 (OUT) ──► Pin 2 (−)    ← unity-gain feedback
LM358 Pin 1 ──── 10 kΩ ──── GPIO34 ──── 100 nF ──── GND
GPIO2  ──── 220 Ω ──── LED (+) ──── LED (−) ──── GND
EXG VCC / LM358 Pin 8 ──► 3.3 V       EXG GND / LM358 Pin 4 ──► GND
```

The RC filter at GPIO34 gives a hardware anti-aliasing cutoff of ≈ 159 Hz — above the 40 Hz EEG upper bound and below the ~200 Hz ADC sampling rate.

---

## 🚀 Quick Start

### Step 1 — Flash the Firmware

1. Open `bci26esp.ino` in Arduino IDE.
2. Go to **Tools → Board → ESP32 Dev Module** and select your COM port.
3. Click **Upload**. Open Serial Monitor at **115200 baud** and confirm output like:

   ```
   2051 2048.34 2
   2310 2052.11 257
   ```

4. **Close Serial Monitor** before running the Python script.

### Step 2 — Attach Electrodes

- Apply gel electrodes: **FP1** (left forehead) · **FP2** (right forehead) · **Ear Lobe** (ground).
- Wipe skin with an alcohol swab first to lower contact impedance.
- Keep electrode leads short and shielded where possible.

### Step 3 — Configure & Launch Python

Edit the `Config` class at the top of `bci_v2.py`:

```python
port        = "COM3"   # ← change to your port e.g. "COM5" or "/dev/ttyUSB0"
sample_rate = 200      # must match firmware delay(5) cadence
```

Then run:

```bash
python bci_v2.py
```

### Step 4 — Read the Dashboard

| Panel                  | What it shows                                                            |
| :--------------------- | :----------------------------------------------------------------------- |
| **Raw EEG + Baseline** | Blue = ADC samples · Orange dashed = ESP32 EMA adaptive baseline         |
| **Diff Signal**        | Red = `│eeg − baseline│` · shaded fill = LED trigger zone (diff > 300)  |
| **Welch PSD**          | Log-scale power spectrum · α and β frequency bands highlighted           |
| **Band Power Bars**    | Relative alpha and beta power normalized to broadband total (1–45 Hz)   |
| **Score History**      | β − α ratio over time · green = focus tendency · orange = relax          |
| **State Indicator**    | ◉ FOCUS / ○ RELAX with live score and ESP32 LED status note             |

### Step 5 — Stop

Close the Matplotlib window or press **Ctrl-C**. The serial port and threads shut down cleanly.

---

## 🔌 ESP32 Firmware

**File:** `bci26esp.ino`

```cpp
int eegPin = 34;        // ADC1_CH6 — EEG signal input
int ledPin = 2;         // Onboard LED — blink event output

float baseline = 0;
float alpha    = 0.01;  // EMA smoothing factor
```

#### Startup Calibration

200 ADC readings are averaged at boot to seed the baseline, preventing a cold-start spike:

```cpp
for (int i = 0; i < 200; i++) {
    baseline += analogRead(eegPin);
    delay(5);
}
baseline /= 200;
```

#### Main Loop (~200 Hz)

```
1. Read ADC  →  eegValue
2. Update EMA:  baseline = 0.99 × baseline + 0.01 × eegValue
3. diff = abs(eegValue − baseline)
4. diff > 300  →  LED HIGH  (blink / spike detected)
5. Serial.println:  "eegValue  baseline  diff"
```

Compatible with the Arduino **Serial Plotter** for quick visual debugging.

---

## 🐍 Python Analyzer

**File:** `bci_v2.py`

#### Architecture

```
main()
 ├── Opens serial port
 ├── Spawns serial_reader()  ← daemon thread
 │         └── parse_line() → fills SharedState deques (eeg, baseline, diff)
 ├── Builds 6-panel Matplotlib figure
 └── FuncAnimation (interval = 100 ms)
           └── update() → SharedState.snapshot() → redraws all panels
```

#### Thread Safety

All buffers and derived values live in `SharedState`, guarded by a `threading.Lock`. The serial thread writes; the animation callback reads through `snapshot()`. No mutable state is shared outside the lock.

#### Signal Analysis

```python
def analyse(samples):
    samples -= np.mean(samples)              # remove DC offset
    freqs, psd = welch(samples, fs=200,
                       window="hann",
                       nperseg=128,
                       noverlap=64)
    alpha_power = band_power(freqs, psd,  8.0, 12.0)
    beta_power  = band_power(freqs, psd, 13.0, 30.0)
    total_power = band_power(freqs, psd,  1.0, 45.0)
    return alpha_power / total_power, beta_power / total_power, freqs, psd
```

#### State Machine

| Score (β − α) | Condition                          | Resulting State |
| :------------ | :--------------------------------- | :-------------- |
| `> 0.030`     | Sustained over rolling history     | **FOCUS**       |
| `< 0.008`     | 15 consecutive low-score ticks     | **RELAX**       |
| Between       | Minimum 30-tick hold in effect     | No change       |

---

## ⚙️ Configuration Reference

All tunable parameters are in the `Config` dataclass at the top of `bci_v2.py`:

```python
@dataclass
class Config:
    # ── Serial ──────────────────────────────────────────────
    port:      str = "COM3"       # ← Your COM port
    baud_rate: int = 115_200

    # ── Signal ──────────────────────────────────────────────
    sample_rate:    int = 200     # Must match firmware delay(5)
    buffer_size:    int = 512     # Rolling deque depth (samples)
    welch_nperseg:  int = 128     # Welch PSD segment length
    welch_noverlap: int = 64      # Welch PSD overlap

    # ── EEG bands (Hz) ──────────────────────────────────────
    alpha_low:  float = 8.0
    alpha_high: float = 12.0
    beta_low:   float = 13.0
    beta_high:  float = 30.0

    # ── State machine ────────────────────────────────────────
    history_len:         int   = 40     # Rolling average window (ticks)
    focus_threshold:     float = 0.030  # β−α threshold → FOCUS
    relax_threshold:     float = 0.008  # β−α threshold → RELAX
    min_state_hold:      int   = 30     # Min ticks before state can change
    relax_streak_needed: int   = 15     # Consecutive low ticks → FOCUS→RELAX

    # ── LED mirror ───────────────────────────────────────────
    diff_spike_threshold: int = 300     # Mirrors ESP32 firmware constant
```

**Key tips:**
- Keep `sample_rate = 200` in sync with firmware `delay(5)`.
- Increase `buffer_size` to improve PSD frequency resolution (at cost of latency).
- Lower `focus_threshold` if alpha dominance is unusually strong on your hardware.
- The EXG Pill's 40 Hz upper bandwidth sufficiently attenuates 50/60 Hz mains — no software notch filter is needed for this prototype.

---

## 📡 Signal Processing Pipeline

```
ADC integer (0–4095)
        │
        ▼
ESP32: EMA baseline subtraction  (α = 0.01)
        │
        ▼  UART @ 115200 baud
Python: 512-sample rolling deque
        │
        ▼
DC removal  (subtract numpy mean)
        │
        ▼
Welch PSD  (Hann window · nperseg=128 · noverlap=64 · density scaling)
        │
        ▼
Trapezoidal band-power integration
        ├── Alpha   8–12 Hz
        ├── Beta   13–30 Hz
        └── Total   1–45 Hz  →  normalize  →  relative powers
        │
        ▼
Score = β_ratio − α_ratio  →  rolling average  →  state machine
```

---

## 🧠 Brain-State Classification

The classifier uses a transparent, single-variable rule:

- **β − α > 0.030** → sustained cognitive engagement → classified as **FOCUS**
- **β − α < 0.008** for 15 consecutive ticks → classified as **RELAX**
- A minimum 30-tick hold prevents rapid flickering between states.

The logic lives entirely in `update_state()`. It can be replaced with an SVM, LDA, or small MLP without changing any other part of the pipeline.

---

## 📤 Serial Data Format

One line is emitted per sample at ~200 Hz:

```
<eegValue>  <baseline>  <diff>
```

| Field      | Type    | Description                                             |
| :--------- | :------ | :------------------------------------------------------ |
| `eegValue` | integer | Raw 12-bit ADC reading (0–4095)                         |
| `baseline` | float   | Current EMA baseline value                              |
| `diff`     | integer | `abs(eegValue − baseline)` — drives the LED blink logic |

Lines with a token count other than 3 are silently discarded by the Python parser.

---

## 🖥️ Dashboard Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│             EEG Brain-Computer Interface — Real-Time Analysis        │
├────────────────────────────────────────────────────────┬─────────────┤
│                                                        │             │
│   Raw EEG Signal + ESP32 Adaptive Baseline             │  Relative   │
│                         [full width]                   │  Band Power │
├────────────────────────────────────────────────────────┤  Alpha|Beta │
│  Diff  │eeg − baseline│                                │             │
│  (shaded region above LED threshold of 300)            │             │
├────────────────────────────────────────────────────────┤─────────────┤
│  Welch Power Spectral Density                          │    ◉        │
│  (log scale · α and β bands highlighted)               │   FOCUS     │
│                                                        │  +0.0412    │
├────────────────────────────────────────────────────────┼─────────────┤
│  β − α Score History                                   │  LED: ESP32 │
│  (green fill = focus tendency · orange = relax)        │  controlled │
└────────────────────────────────────────────────────────┴─────────────┘
```

---

## 📊 Results & Performance

| Metric                   | Value      | Notes                                        |
| :----------------------- | :--------- | :------------------------------------------- |
| Blink detection accuracy | ~88%       | Controlled trials, stable electrode contact  |
| Response latency         | < 50 ms    | Blink peak to LED output trigger             |
| Effective sample rate    | ~200 Hz    | Firmware `delay(5)` loop cadence             |
| ADC resolution           | 12-bit     | Range 0–4095, ESP32 ADC1 channel 6           |
| Supply voltage           | 3.3 V      | Single-rail for EXG Pill and LM358           |
| Anti-aliasing cutoff     | ≈ 159 Hz   | 10 kΩ + 100 nF RC filter at GPIO34           |
| PSD update rate          | ~10 Hz     | FuncAnimation at 100 ms interval             |

---

## ⚠️ Known Limitations

- **Single channel only** — no multi-channel synchronization.
- **No electrical isolation** — hardware must be battery-powered during any skin contact.
- **No artifact rejection** — eye movements, jaw clenches, and body motion appear in raw data.
- **ESP32 ADC non-linearity** — ADC is non-linear below ~100 mV; per-unit variation may require threshold tuning.
- **Windows-focused testing** — Linux/macOS users should set `port = "/dev/ttyUSB0"` and may need udev rules for the CH340/CP210x USB-serial driver.
- **UI stutter** — FuncAnimation can lag on low-end machines; try reducing `buffer_size` or increasing the `interval` argument.

---

## 🛠️ Troubleshooting

| Symptom                        | Likely Cause                               | Fix                                                                     |
| :----------------------------- | :----------------------------------------- | :---------------------------------------------------------------------- |
| `Cannot open COMx`             | Wrong port or port in use                  | Close Serial Monitor; check Device Manager or `ls /dev/tty*`           |
| Dashboard opens, no signal     | Firmware not flashed or baud mismatch      | Re-flash; confirm `Serial.begin(115200)` matches `baud_rate = 115_200` |
| All values read `0 0 0`        | No electrode contact or EXG Pill unpowered | Verify 3.3 V at EXG VCC; check electrode placement                     |
| LED permanently ON             | Threshold too low or motion artifact       | Sit still; raise diff threshold in firmware (`300` → `400`)            |
| Very noisy PSD                 | Poor ground or missing RC capacitor        | Re-seat ear-lobe electrode; confirm 100 nF cap on GPIO34               |
| Blank Matplotlib window        | TkAgg backend missing                      | `pip install tk` or switch to `Qt5Agg` + `pip install pyqt5`           |
| Score stuck at `0.000`         | 512-sample buffer not filled yet           | Wait ~3 seconds after launch for the buffer to fill                    |

---

## 🗺️ Roadmap

- [ ] Multi-channel EEG with per-channel independent PSDs
- [ ] Software IIR notch filter (50/60 Hz) in the Python pipeline
- [ ] Firmware impedance self-check on startup
- [ ] BLE wireless streaming to a mobile dashboard
- [ ] ML-based multi-class brain-state classification (SVM / LDA / MLP)
- [ ] EDF/BDF export for MNE-Python and EEGLAB compatibility
- [ ] OTA firmware updates over Wi-Fi
- [ ] Adaptive per-session threshold calibration

---

<div align="center">

*Alpha-quality prototype — not for medical, clinical, or consumer use.*
*Always use battery-powered hardware when electrodes are in contact with skin.*

</div>