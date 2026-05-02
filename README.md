# 🧠 EEG-Based Brain-Computer Interface

> A low-cost, open-source BCI prototype using an ESP32, EXG BioAmp Pill, and Python — capable of real-time EEG acquisition, blink detection, and alpha/beta brain-state classification.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Prototype Status](#prototype-status)
- [System Architecture](#system-architecture)
- [Hardware Requirements](#hardware-requirements)
- [Software Dependencies](#software-dependencies)
- [Circuit Summary](#circuit-summary)
- [Quick Start](#quick-start)
- [ESP32 Firmware](#esp32-firmware)
- [Python Analyzer](#python-analyzer)
- [Configuration Reference](#configuration-reference)
- [Signal Processing Pipeline](#signal-processing-pipeline)
- [Brain-State Classification](#brain-state-classification)
- [Serial Data Format](#serial-data-format)
- [Dashboard Overview](#dashboard-overview)
- [Results & Performance](#results--performance)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

---

## Overview

This project implements a full EEG-BCI stack on accessible, off-the-shelf hardware. The **ESP32 firmware** samples differential bio-signals from an EXG BioAmp Pill via its onboard 12-bit ADC, performs adaptive baseline tracking, triggers an LED on blink events, and streams three-value data packets over UART. The **Python analyzer** (`bci_v2.py`) consumes that stream in a background thread, runs Welch PSD analysis, computes relative alpha/beta band powers, and drives a live six-panel Matplotlib dashboard that classifies brain state as **FOCUS** or **RELAX** in real time.

The entire system is designed for student research and rapid prototyping — no proprietary software, no dedicated EEG hardware dongle, and a total BOM cost well under ₹2,000 / $25 USD.

---

## Prototype Status

| Dimension | Status |
|---|---|
| Maturity | Alpha — lab prototyping, not for medical or consumer use |
| Channels | Single EEG channel (FP1 vs. FP2 differential) |
| Blink Detection | ✅ Threshold + differential method, ~88% accuracy |
| Band Classification | ✅ Alpha / Beta relative power via Welch PSD |
| Artifact Rejection | ❌ Not yet implemented |
| Multi-channel | ❌ Planned |
| Electrical Isolation | ❌ Not included — use battery-powered hardware only |

> ⚠️ **Safety Notice:** This design contains no medical-grade electrical isolation. Always power the hardware from a battery (not mains USB) when electrodes are in contact with skin.

---

## System Architecture

```
Brain (µV)
    │
    ▼
Ag/AgCl Electrodes  (FP1, FP2, Ear Lobe)
    │
    ▼
EXG BioAmp Pill  ── Gain ≈ 1000×, BW: 0.5–40 Hz, 3.3 V single-supply
    │
    ▼
LM358 Op-Amp  ── Unity-gain voltage follower (impedance buffer)
    │
    ▼
RC Low-Pass Filter  ── 10 kΩ + 100 nF  →  f_c ≈ 159 Hz
    │
    ▼
ESP32 GPIO34  ── 12-bit ADC, ~200 Hz sampling
    │  Adaptive EMA baseline  │  Blink threshold detection  │  LED on GPIO2
    ▼
UART Serial  ──  115200 baud  ──  "eegValue  baseline  diff\n"
    │
    ▼
Python bci_v2.py
    ├── Serial reader thread  (deque buffers, 512 samples)
    ├── Welch PSD  (Hann window, nperseg=128, noverlap=64)
    ├── Band power  (α: 8–12 Hz,  β: 13–30 Hz)
    ├── State machine  (FOCUS / RELAX)
    └── Live Matplotlib dashboard  (6-panel, TkAgg, 10 fps)
```

---

## Hardware Requirements

| Component | Specification / Notes |
|---|---|
| **ESP32** | Any dev board with GPIO34 (ADC1_CH6) and GPIO2; dual-core 240 MHz, 12-bit ADC (0–3.3 V) |
| **EXG BioAmp Pill** | Single-supply bio-signal amplifier, Gain ≈ 1000×, BW: 0.5–40 Hz, 3.3 V operation |
| **Electrodes** | Ag/AgCl disposable gel electrodes — FP1 (active), FP2 (reference), Ear Lobe (ground) |
| **LM358 Op-Amp** | DIP-8 or SMD; only Op-Amp A (pins 1–3) used as unity-gain voltage follower |
| **Resistor** | 10 kΩ (between LM358 output and GPIO34) |
| **Capacitor** | 100 nF (between GPIO34 and GND — forms RC LPF with the resistor) |
| **LED** | Any 3 mm/5 mm LED with 220 Ω series resistor on GPIO2 |
| **Power** | 3.3 V for EXG Pill and LM358; USB-to-PC for serial streaming — **use a battery pack for skin contact** |
| **USB Cable** | USB to host PC (Windows 10+ tested; Linux/macOS also supported) |

---

## Software Dependencies

**Python 3.9 or newer** is required.

```bash
pip install numpy matplotlib scipy pyserial
```

Recommended virtual-environment setup:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install numpy matplotlib scipy pyserial
```

If `TkAgg` is unavailable on your system, install `PyQt5` and change the backend:

```bash
pip install pyqt5
# In bci_v2.py, change: matplotlib.use("TkAgg")  →  matplotlib.use("Qt5Agg")
```

**Arduino / Firmware dependencies:**

- Arduino IDE 1.8+ or PlatformIO
- Board package: `esp32` by Espressif (install via Arduino Board Manager)
- No additional libraries required — only built-in `analogRead`, `digitalWrite`, `Serial`

---

## Circuit Summary

See [`PIN_CONNECTIONS.md`](PIN_CONNECTIONS.md) for the full pin-by-pin wiring table and ASCII schematic.

**Signal path in brief:**

```
FP1 → EXG IN+    FP2 → EXG IN−    Ear Lobe → EXG GND_E
EXG OUT → LM358 Pin 3(+)
LM358 Pin 1(OUT) → Pin 2(−)   [unity gain feedback]
LM358 Pin 1 ──── 10 kΩ ──── GPIO34 ──── 100 nF ──── GND
GPIO2 ──── 220 Ω ──── LED(+) ──── LED(−) ──── GND
EXG VCC / LM358 Pin 8 → 3.3 V      EXG GND / LM358 Pin 4 → GND
```

The RC filter at GPIO34 provides a hardware anti-aliasing cutoff of ≈ 159 Hz, well above the 100 Hz EEG upper bound and below the ~200 Hz sampling rate.

---

## Quick Start

### 1. Flash the Firmware

1. Open `bci26esp.ino` in Arduino IDE.
2. Select **Board → ESP32 Dev Module** and the correct COM port.
3. Upload. Open Serial Monitor at **115200 baud** to verify output like:
   ```
   2051 2048 3
   2063 2049 14
   ```
4. Close Serial Monitor before launching the Python script.

### 2. Prepare Electrodes

- Apply gel electrodes: **FP1** (left forehead), **FP2** (right forehead), **Ear Lobe** (reference/ground).
- Ensure firm, low-impedance contact. Wipe skin with an alcohol swab first.

### 3. Launch the Python Analyzer

```bash
# Activate your virtual environment first, then:
python bci_v2.py
```

> ✏️ Edit the `Config` class in `bci_v2.py` before running:
> - `port = "COM3"` → change to your actual COM port (e.g. `"COM5"`, `"/dev/ttyUSB0"`)
> - Confirm `sample_rate = 200` matches the firmware `delay(5)` cadence.

### 4. Read the Dashboard

| Panel | Description |
|---|---|
| **Raw EEG + Baseline** | Blue = ADC samples; Orange dashed = ESP32 EMA adaptive baseline |
| **Diff Signal** | Red = `│eeg − baseline│`; shaded region = LED trigger zone (> 300) |
| **Welch PSD** | Log-scale power spectrum; blue/orange bands mark α and β regions |
| **Band Power Bars** | Relative alpha and beta power normalized to broadband total |
| **Score History** | β − α ratio over time; green fill = focus tendency, orange = relax |
| **State Indicator** | Large ◉ FOCUS / ○ RELAX label with live score and LED note |

### 5. Stop

Close the Matplotlib window or press **Ctrl-C**. The serial port closes cleanly.

---

## ESP32 Firmware

**File:** `bci26esp.ino`

```cpp
int eegPin = 34;   // ADC1_CH6 — EEG signal input
int ledPin = 2;    // Onboard LED — blink event output

float baseline = 0;
float alpha    = 0.01;  // EMA smoothing factor
```

### Startup Calibration

200 ADC readings are averaged at boot to seed the baseline, avoiding a cold-start spike:

```cpp
for (int i = 0; i < 200; i++) {
    baseline += analogRead(eegPin);
    delay(5);
}
baseline /= 200;
```

### Main Loop

Each iteration (~200 Hz):

1. Read ADC → `eegValue`
2. Update EMA baseline: `baseline = 0.99 × baseline + 0.01 × eegValue`
3. Compute `diff = │eegValue − baseline│`
4. If `diff > 300` → `LED HIGH` (blink detected), else `LED LOW`
5. Print: `eegValue baseline diff\n` over UART

### Serial Output Format

```
<eegValue>  <baseline>  <diff>
2051 2048.34 2
2310 2052.11 257
2689 2058.03 630       ← diff > 300: LED on
```

Compatible with the Arduino Serial Plotter for visual debugging.

---

## Python Analyzer

**File:** `bci_v2.py`

### Architecture

```
main()
 ├── Opens serial port
 ├── Spawns serial_reader() daemon thread
 │     └── Parses lines → fills SharedState deques
 ├── Builds Matplotlib figure (6 axes)
 └── Runs FuncAnimation (100 ms interval, ~10 fps)
       └── update() reads SharedState snapshot → redraws all panels
```

### Thread Safety

All buffers and computed values live in `SharedState`, protected by a `threading.Lock`. The serial thread writes; the animation callback reads via `snapshot()` — no shared mutable state outside the lock.

### Signal Analysis

```python
def analyse(samples):
    samples -= np.mean(samples)           # remove DC offset
    freqs, psd = welch(samples,
                       fs=200,
                       window="hann",
                       nperseg=128,
                       noverlap=64)
    alpha_power = band_power(freqs, psd,  8.0, 12.0)
    beta_power  = band_power(freqs, psd, 13.0, 30.0)
    total_power = band_power(freqs, psd,  1.0, 45.0)
    return alpha_power/total, beta_power/total, freqs, psd
```

### State Machine

| Score (β − α) | Condition | State |
|---|---|---|
| > 0.030 | Sustained over history window | **FOCUS** |
| < 0.008 | Sustained for 15 consecutive ticks | **RELAX** |
| Between | Holding period (30 ticks min) | No change |

---

## Configuration Reference

All tunable parameters live in the `Config` dataclass at the top of `bci_v2.py`:

```python
@dataclass
class Config:
    # Serial
    port:      str = "COM3"       # ← Your COM port
    baud_rate: int = 115_200

    # Signal
    sample_rate:    int = 200     # Must match firmware delay(5)
    buffer_size:    int = 512     # Samples held in rolling deque
    welch_nperseg:  int = 128     # Welch PSD segment length
    welch_noverlap: int = 64      # Welch PSD overlap

    # EEG bands (Hz)
    alpha_low:  float = 8.0
    alpha_high: float = 12.0
    beta_low:   float = 13.0
    beta_high:  float = 30.0

    # State machine
    history_len:         int   = 40     # Ticks for rolling score average
    focus_threshold:     float = 0.030  # β−α threshold for FOCUS
    relax_threshold:     float = 0.008  # β−α threshold for RELAX
    min_state_hold:      int   = 30     # Min ticks before state can change
    relax_streak_needed: int   = 15     # Low-score ticks before FOCUS→RELAX

    # LED mirror
    diff_spike_threshold: int = 300     # Mirrors ESP32 firmware constant
```

**Tips:**
- Keep `sample_rate` in sync with firmware — `delay(5)` → ~200 Hz.
- Increase `buffer_size` to improve PSD frequency resolution at the cost of latency.
- Lower `focus_threshold` if your alpha waves are unusually strong.
- On 60 Hz mains regions, note that the Python script does not apply a software notch — the hardware EXG Pill's 40 Hz upper cutoff already attenuates 50/60 Hz sufficiently for this prototype.

---

## Signal Processing Pipeline

```
ADC raw integer (0–4095)
        │
        ▼
ESP32: Adaptive EMA baseline subtraction  (alpha = 0.01)
        │
        ▼
UART stream → Python deque (512 samples)
        │
        ▼
DC removal: subtract numpy mean
        │
        ▼
Welch PSD (Hann window, nperseg=128, noverlap=64, density scaling)
        │
        ▼
Band-power integration (trapezoidal rule)
   ├── Alpha (8–12 Hz)
   ├── Beta  (13–30 Hz)
   └── Total (1–45 Hz) → normalize to relative power
        │
        ▼
Score = β_ratio − α_ratio → rolling average → state machine
```

---

## Brain-State Classification

The classifier uses a simple, interpretable rule:

- **β − α > 0.030** → active cognitive engagement → **FOCUS**
- **β − α < 0.008** sustained for 15 ticks → **RELAX**
- A minimum 30-tick hold prevents flickering between states.

This is intentionally transparent. Replace `update_state()` with an ML model (SVM, LDA, or a small MLP) for more robust classification — the rest of the pipeline stays unchanged.

---

## Serial Data Format

The firmware emits one line per sample at ~200 Hz:

```
<eegValue> <baseline> <diff>
```

| Field | Type | Description |
|---|---|---|
| `eegValue` | integer | Raw 12-bit ADC reading (0–4095) |
| `baseline` | float | Current EMA baseline value |
| `diff` | integer | `abs(eegValue − baseline)` — used for blink LED |

The Python parser splits on whitespace and expects exactly 3 tokens per line. Lines with a different token count are silently discarded.

---

## Dashboard Overview

```
┌────────────────────────────────────────────────────────────────┐
│            EEG Brain-Computer Interface — Real-Time Analysis   │
├─────────────────────────────────────────┬──────────────────────┤
│  Raw EEG Signal + ESP32 Adaptive        │                      │
│  Baseline  [full width]                 │                      │
├───────────────────────────────┬─────────┤  Relative Band Power │
│  Diff |eeg−baseline|          │         │   [Alpha | Beta]     │
│  (LED trigger zone shaded)    │         │                      │
├───────────────────────────────┤         ├──────────────────────┤
│  Welch Power Spectral Density │         │   ◉  FOCUS           │
│  (log scale, α/β bands)       │         │   score +0.0412      │
├───────────────────────────────┴─────────┼──────────────────────┤
│  β−α Score History                      │   LED: ESP32         │
│  (green fill = focus, orange = relax)   │   controlled         │
└─────────────────────────────────────────┴──────────────────────┘
```

---

## Results & Performance

| Metric | Value | Condition |
|---|---|---|
| Blink detection accuracy | ~88% | Controlled trials, stable electrode contact |
| Response latency | < 50 ms | Blink peak to LED output |
| Effective sample rate | ~200 Hz | `delay(5)` firmware loop |
| ADC resolution | 12-bit (0–4095) | ESP32 ADC1 channel 6 |
| Supply voltage | 3.3 V | Single-rail for EXG Pill + LM358 |
| Anti-aliasing cutoff | ≈ 159 Hz | 10 kΩ + 100 nF RC filter at GPIO34 |
| PSD update rate | ~10 Hz | FuncAnimation at 100 ms interval |

---

## Known Limitations

- **Single channel only** — no multi-channel synchronization.
- **No electrical isolation** — hardware must be battery-powered during skin contact.
- **No automated artifact rejection** — eye movements, jaw clenches, and motion appear in raw data.
- **ADC non-linearity at low voltages** — ESP32 ADC is non-linear below ~100 mV; the LM358 buffer and EXG Pill gain help keep the signal in a comfortable mid-rail range but calibration variation between units may require threshold tuning.
- **Windows-focused testing** — Linux/macOS require changing `port` to `/dev/ttyUSB0` or similar and may need udev rules for the ESP32 CH340/CP210x USB driver.
- **UI stutter** — Matplotlib FuncAnimation can lag on low-end machines; reduce `buffer_size` or increase `interval` in `FuncAnimation` if needed.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Cannot open COMx` | Wrong port or port in use | Close Serial Monitor; verify port in Device Manager / `ls /dev/tty*` |
| Dashboard opens but no signal | Firmware not flashed or baud mismatch | Re-flash; confirm `Serial.begin(115200)` matches `baud_rate = 115_200` |
| All values read `0 0 0` | No electrode contact or EXG Pill not powered | Check 3.3 V supply to EXG VCC; verify electrode placement |
| Constant LED ON | Threshold too low or heavy motion artifact | Sit still; increase diff threshold in firmware (`300` → `400`) |
| Very noisy PSD | Poor ground contact or missing RC cap | Re-seat ear-lobe electrode; verify 100 nF cap between GPIO34 and GND |
| Blank Matplotlib window | TkAgg backend missing | `pip install tk` or switch to `Qt5Agg` + `pip install pyqt5` |
| Score stuck at `0.000` | Buffer not full yet | Wait ~3 seconds for the 512-sample buffer to fill |

---

## Roadmap

- [ ] Multi-channel EEG with per-channel PSDs
- [ ] Software IIR notch filter (50/60 Hz) in Python pipeline
- [ ] Impedance self-check on firmware startup
- [ ] BLE wireless streaming to mobile dashboard
- [ ] ML-based multi-class gesture and brain-state classification (SVM / MLP)
- [ ] EDF/BDF export for compatibility with MNE-Python and EEGLAB
- [ ] OTA firmware updates via Wi-Fi
- [ ] Adaptive threshold calibration per session

---


*Alpha-quality prototype. Not for medical, clinical, or consumer use. Use battery-powered hardware only when electrodes are in contact with skin.*