# 🔌 Pin Connections — EEG BCI Hardware

> Complete wiring reference for the ESP32 + EXG BioAmp Pill + LM358 EEG acquisition circuit.

---

## Table of Contents

- [Components at a Glance](#components-at-a-glance)
- [ESP32 Pin Assignment](#esp32-pin-assignment)
- [Electrode → EXG BioAmp Pill](#electrode--exg-bioamp-pill)
- [EXG BioAmp Pill → Power](#exg-bioamp-pill--power)
- [EXG BioAmp Pill → LM358](#exg-bioamp-pill--lm358)
- [LM358 Internal Wiring](#lm358-internal-wiring)
- [LM358 → ESP32 (with RC Filter)](#lm358--esp32-with-rc-filter)
- [LED Indicator](#led-indicator)
- [Full Wiring Table](#full-wiring-table)
- [ASCII Schematic](#ascii-schematic)
- [LM358 DIP-8 Pinout](#lm358-dip-8-pinout)
- [Signal Flow Summary](#signal-flow-summary)
- [RC Low-Pass Filter Calculation](#rc-low-pass-filter-calculation)
- [Notes & Best Practices](#notes--best-practices)

---

## Components at a Glance

| ID | Component | Role |
|---|---|---|
| U1 | ESP32 Dev Board | ADC sampling, baseline tracking, serial streaming, LED output |
| U2 | EXG BioAmp Pill | Bio-signal amplifier (Gain ≈ 1000×, BW: 0.5–40 Hz) |
| U3 | LM358 (Op-Amp A) | Unity-gain voltage follower — impedance buffer between EXG and ESP32 ADC |
| E1 | Ag/AgCl Electrode | FP1 — left forehead (active / positive input) |
| E2 | Ag/AgCl Electrode | FP2 — right forehead (reference / negative input) |
| E3 | Ag/AgCl Electrode | Ear lobe (circuit ground / driven right leg) |
| R1 | 10 kΩ Resistor | RC LPF resistor between LM358 output and GPIO34 |
| C1 | 100 nF Capacitor | RC LPF capacitor between GPIO34 and GND |
| R2 | 220 Ω Resistor | Current-limiting resistor for LED indicator |
| D1 | LED (any color) | Visual blink / event indicator |

---

## ESP32 Pin Assignment

| GPIO | Function | Connected To |
|---|---|---|
| **GPIO 34** | ADC1_CH6 — EEG signal input | LM358 Pin 1 via R1 (10 kΩ) |
| **GPIO 2** | Digital output — LED trigger | R2 (220 Ω) → LED anode |
| **3.3 V** | Power rail | EXG VCC, LM358 Pin 8 |
| **GND** | Common ground | EXG GND, LM358 Pin 4, C1 bottom, LED cathode |

> ℹ️ GPIO34 is input-only on ESP32 (no internal pull-up/pull-down). This is intentional — it avoids loading the analog signal path.

---

## Electrode → EXG BioAmp Pill

| Electrode | Placement | → EXG BioAmp Pill Pin |
|---|---|---|
| E1 — FP1 | Left forehead (active) | **IN+** (positive differential input) |
| E2 — FP2 | Right forehead (reference) | **IN−** (negative differential input) |
| E3 — Ear Lobe | Ear lobe (ground) | **GND_ELECTRODE** (DRL / body ground) |

Use shielded cable for electrode leads to minimize 50/60 Hz mains pickup. Keep lead lengths as short as practical.

---

## EXG BioAmp Pill → Power

| EXG BioAmp Pill Pin | → ESP32 Pin | Notes |
|---|---|---|
| VCC | 3.3 V | Single-rail supply; do not use 5 V |
| GND | GND | Common ground reference |

Add a 100 nF decoupling capacitor from VCC to GND, placed as close to the EXG Pill as possible.

---

## EXG BioAmp Pill → LM358

| EXG BioAmp Pill Pin | → LM358 Pin | Notes |
|---|---|---|
| OUT | Pin 3 (IN+A) | Amplified EEG signal into non-inverting op-amp input |

---

## LM358 Internal Wiring

| LM358 Pin | Function | Connected To | Notes |
|---|---|---|---|
| Pin 1 | OUT A | LM358 Pin 2 (IN−A) | Short Pin 1 to Pin 2: unity-gain (voltage follower) feedback |
| Pin 2 | IN−A | LM358 Pin 1 (OUT A) | Feedback loop — sets gain = 1 |
| Pin 3 | IN+A | EXG BioAmp OUT | Signal input |
| Pin 4 | GND (V−) | ESP32 GND | Negative supply rail |
| Pin 5 | IN+B | — | Unused (Op-Amp B) |
| Pin 6 | IN−B | — | Unused (Op-Amp B) |
| Pin 7 | OUT B | — | Unused (Op-Amp B) |
| Pin 8 | VCC (V+) | ESP32 3.3 V | Positive supply rail |

Only **Op-Amp A** (pins 1, 2, 3) is used.

---

## LM358 → ESP32 (with RC Filter)

```
LM358 Pin 1 (OUT)
        │
       [R1]  10 kΩ
        │
        ├──────────── ESP32 GPIO 34  (ADC1_CH6)
        │
       [C1]  100 nF
        │
       GND
```

| Node | Component | Value | Role |
|---|---|---|---|
| LM358 Pin 1 → GPIO34 | R1 | 10 kΩ | RC filter resistor + source impedance protection |
| GPIO34 → GND | C1 | 100 nF | RC filter capacitor + ADC input decoupling |

Cutoff frequency: **f_c = 1 / (2π × 10,000 × 0.0000001) ≈ 159 Hz**

This hardware anti-aliasing filter prevents frequencies above ~159 Hz from aliasing into the EEG band, while the ESP32 samples at ~200 Hz.

---

## LED Indicator

```
ESP32 GPIO 2 ──── R2 (220 Ω) ──── LED Anode (+) ──── LED Cathode (−) ──── GND
```

| GPIO | Resistor | LED |
|---|---|---|
| GPIO 2 | 220 Ω | Any 3 mm or 5 mm LED |

The LED illuminates when `abs(eegValue − baseline) > 300` — indicating a blink event or high-amplitude signal transient. Most ESP32 development boards have an onboard LED already wired to GPIO2.

---

## Full Wiring Table

| From | From Pin / Point | To | To Pin / Point | Wire / Component |
|---|---|---|---|---|
| Electrode E1 (FP1) | Signal | EXG BioAmp Pill | IN+ | Shielded electrode lead |
| Electrode E2 (FP2) | Signal | EXG BioAmp Pill | IN− | Shielded electrode lead |
| Electrode E3 (Ear Lobe) | Ground | EXG BioAmp Pill | GND_ELECTRODE | Shielded electrode lead |
| EXG BioAmp Pill | VCC | ESP32 | 3.3 V | Power wire |
| EXG BioAmp Pill | GND | ESP32 | GND | Power wire |
| EXG BioAmp Pill | OUT | LM358 | Pin 3 (IN+A) | Signal wire |
| LM358 | Pin 1 (OUT A) | LM358 | Pin 2 (IN−A) | Short — unity gain feedback |
| LM358 | Pin 8 (VCC) | ESP32 | 3.3 V | Power wire |
| LM358 | Pin 4 (GND) | ESP32 | GND | Power wire |
| LM358 | Pin 1 (OUT A) | R1 (10 kΩ) | One end | Signal wire |
| R1 (10 kΩ) | Other end | ESP32 | GPIO 34 | Signal wire |
| ESP32 | GPIO 34 | C1 (100 nF) | Top plate | Anti-alias cap |
| C1 (100 nF) | Bottom plate | ESP32 | GND | Ground wire |
| ESP32 | GPIO 2 | R2 (220 Ω) | One end | Output wire |
| R2 (220 Ω) | Other end | LED D1 | Anode (+) | Output wire |
| LED D1 | Cathode (−) | ESP32 | GND | Ground wire |

---

## ASCII Schematic

```
  3.3V ────────────┬───────────────────────────┬────────── LM358 Pin 8
                   │                           │
              [EXG VCC]                    [100nF]   ← bypass decoupling cap
                   │                           │
                   │                          GND


  FP1  ────── IN+ ─┐
                   │  EXG
  FP2  ────── IN− ─┤  BioAmp ── OUT ──────────────── LM358 Pin 3 (+)
                   │  Pill                                   │
  Ear  ────── GND ─┘                               LM358 Pin 2 (−) ← ──┐
                                                   LM358 Pin 1 (OUT)────┘
  3.3V ───── LM358 Pin 8                                    │
  GND  ───── LM358 Pin 4                               10 kΩ [R1]
                                                            │
                                                        GPIO 34 ──── 100 nF [C1] ──── GND
                                                            │
                                                     (12-bit ADC)
                                                            │
                                                       ESP32 MCU
                                                            │
                                                        GPIO 2
                                                            │
                                                       220 Ω [R2]
                                                            │
                                                       LED Anode
                                                       LED Cathode ──── GND
```

---

## LM358 DIP-8 Pinout

```
              ┌──────────────┐
  OUT A   1 ──┤              ├── 8   VCC  (3.3 V)
  IN−A    2 ──┤    LM358     ├── 7   OUT B   (unused)
  IN+A    3 ──┤              ├── 6   IN−B    (unused)
  GND     4 ──┤              ├── 5   IN+B    (unused)
              └──────────────┘
                    ↑ notch
```

**Configuration used:**

```
  IN+A (Pin 3)  ← EXG BioAmp OUT          [signal input]
  IN−A (Pin 2)  ← short to OUT A (Pin 1)   [unity-gain feedback]
  OUT A (Pin 1) → 10 kΩ → GPIO 34          [buffered output]
```

---

## Signal Flow Summary

```
  Brain Neural Activity  (µV range)
         │
         ▼
  Ag/AgCl Electrodes  ─  FP1 / FP2 (differential)
         │
         ▼
  EXG BioAmp Pill  ─  Gain × 1000, BW: 0.5–40 Hz, 3.3 V single supply
         │
         ▼  (mV range signal, centered around VCC/2)
  LM358 Voltage Follower  ─  Unity gain, high input Z, low output Z
         │
         ▼
  RC Low-Pass Filter  ─  10 kΩ + 100 nF  →  f_c ≈ 159 Hz  (anti-aliasing)
         │
         ▼
  GPIO 34 — ESP32 ADC1_CH6  (12-bit, 0–3.3 V, ~200 Hz)
         │
         ├── EMA Baseline tracking  (α = 0.01)
         ├── Blink detection:  │eeg − baseline│ > 300  →  GPIO 2 HIGH
         └── Serial stream:    "eegValue baseline diff\n"  @ 115200 baud
                                        │
                                        ▼
                               Python  bci_v2.py
                                        │
                               Welch PSD → α / β power
                                        │
                               State machine: FOCUS / RELAX
                                        │
                               Live Matplotlib dashboard
```

---

## RC Low-Pass Filter Calculation

The passive RC filter between the LM358 output and GPIO34 serves as a hardware anti-aliasing filter:

```
R = 10,000 Ω   (10 kΩ)
C = 0.0000001 F (100 nF)

f_c = 1 / (2 × π × R × C)
    = 1 / (2 × 3.14159 × 10000 × 0.0000001)
    = 1 / 0.006283
    ≈ 159 Hz
```

With the ESP32 sampling at ~200 Hz, the 159 Hz cutoff provides meaningful attenuation of signals that would otherwise alias into the EEG analysis band (1–45 Hz). The EXG BioAmp Pill's own 40 Hz upper bandwidth ensures no physiological EEG signal is lost by this filter.

---

## Notes & Best Practices

**Power:**
- Always supply EXG BioAmp Pill and LM358 from the ESP32's **3.3 V rail**, not 5 V. The EXG Pill is a single-supply 3.3 V device.
- When skin electrodes are connected, power the entire system from a **USB battery bank**, not a mains-connected USB port. This eliminates the risk of mains leakage current through the electrode path.
- Place 100 nF ceramic bypass capacitors at the VCC pins of both the EXG Pill and the LM358, as close to the IC as possible.

**Electrode placement:**
- Follow the **10-20 international system**: FP1 = left pre-frontal, FP2 = right pre-frontal, A1/A2 = ear lobes.
- Clean the skin with an alcohol swab before applying gel electrodes to reduce contact impedance.
- Keep electrode leads as short as possible and use shielded or twisted-pair cable.

**GPIO34 specifics:**
- GPIO34 on ESP32 is **input-only** — there is no internal pull-up or pull-down, which is ideal for a sensitive analog input.
- Avoid routing the GPIO34 trace near high-frequency digital signals (SPI, I2C, PWM) on the PCB/breadboard.
- The 10 kΩ series resistor also protects the ADC pin from overvoltage transients (ESD protection).

**LM358 supply:**
- The LM358 is a single-supply op-amp and works well at 3.3 V.
- Its output swing does not fully reach the supply rails (typ. ~1.5 V below VCC). Ensure the EXG Pill output is biased toward mid-rail (~1.65 V) for maximum ADC headroom.

**Grounding:**
- All GND connections (ESP32, EXG Pill, LM358, electrode reference, C1 bottom) must share a **single common ground point** to avoid ground loops that introduce 50/60 Hz interference.
