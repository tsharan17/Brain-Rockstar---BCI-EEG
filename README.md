# BCI EEG Monitor – Prototype Release

Initial public prototype of a low-cost brain-computer interface stack that combines a Python-based visualizer with ESP32 firmware for single-channel EEG capture. The system focuses on rapid experimentation: the desktop app (`receiverbci.py`) ingests serial samples, runs a multi-stage signal pipeline, and presents time/frequency analytics; the embedded code streams differential voltages from an AD8232 front-end via ADS1115.

## Prototype Status
- **Maturity:** Alpha-quality reference design suitable for lab prototyping, not medical or consumer deployment.
- **Coverage:** Single EEG channel with baseline filtering and band-power estimation; no multi-user calibration or artifact rejection yet.
- **Safety:** No electrical isolation or regulatory safeguards are included—use with fully battery-powered hardware and follow safety best practices.
- **Roadmap:** Planned upgrades include multi-channel support, firmware calibration assistants, and richer analytics (see Roadmap below).

## System Overview
- **Desktop monitor:** Matplotlib-based dashboard with raw/filtered waveforms, relative band power visualization, live PSD, and health metrics.
- **Signal chain:** Rolling baseline removal → dual-notch mains suppression → configurable SOS bandpass → Welch PSD and band-power summary.
- **Data logging:** Optional CSV capture of raw and processed voltages under `eeg_recordings/` with timestamped filenames.
- **Embedded firmware:** ESP32 sketch samples AD8232 output through ADS1115 at 250 Hz, re-centers to 0 V, and streams float values over UART (115200 baud).

## Hardware Requirements
- ESP32 development board with I²C pins (prototype uses SDA = 21, SCL = 22).
- AD8232 ECG/EEG analog front-end connected to ADS1115 (A0 = signal, A1 = GND) running from 3.3 V.
- Shielded electrodes and reference/ground leads suitable for dry prototyping; ensure low-noise contact.
- USB connection to host PC (Windows 10+ tested) for serial streaming; adjust `Config.PORT` to match your COM identifier.

## Software Dependencies
- Python 3.9 or newer.
- Packages: `numpy`, `matplotlib`, `scipy`, `pyserial`.

Recommended setup:

```
python -m venv .venv
.venv\Scripts\activate
pip install numpy matplotlib scipy pyserial
```

## Quick Start
1. Flash the ESP32 using `bci_values/bci_values.ino` (Arduino IDE or PlatformIO). Confirm `SAMPLE_RATE` stays at 250 Hz and UART speed is 115200 baud.
2. Connect the hardware, verify electrode contacts, and open the Python project on the host PC.
3. Optionally update `receiverbci.py`:
   - `Config.PORT` → active COM port.
   - `Config.POWERLINE_FREQ` → `60` for regions with 60 Hz mains.
   - Disable `Config.SAVE_DATA` to skip CSV logging.
4. Launch the visualizer:

```
python receiverbci.py
```

5. Observe the dashboard:
   - Waveform panel superimposes raw (gray) and filtered (cyan) signals with auto-scaling.
   - Voltage HUD reports instantaneous values, range, and mean.
   - Band-power bars compare Delta–Gamma energy distribution.
   - PSD plot highlights frequency bands and updates in real time.
6. Close the Matplotlib window to end the session. Serial and recording resources shut down cleanly.

## Recorded Data
- CSV files land in `eeg_recordings/` with UTC-stamped names when logging is enabled.
- Each entry includes elapsed seconds plus raw and filtered voltages—ready for replay in Python, MATLAB, or spreadsheets.

## ESP32 Firmware Snapshot

```
```1:133:bci_values/bci_values.ino
#include <Wire.h>
#include <Adafruit_ADS1X15.h>
const int SAMPLE_RATE = 250;
const int DELAY_US = 1000000 / SAMPLE_RATE;
Adafruit_ADS1115 ads;
...
Serial.println("🧠 Starting EEG acquisition at 250 Hz...");
Serial.println("   (Data streaming to Python)\n");
```
```

- Proof-of-concept loop maintains a 250 Hz cadence (`micros()` based) and outputs centered voltages with six decimal precision.
- Diagnostics block is commented to avoid polluting the serial stream; re-enable when using the Arduino Serial Monitor.
- Future firmware milestones: impedance self-checks, persistent configuration, battery monitoring, watchdog recovery, and multi-channel MUX handling.

## Configuration Reference

```
```12:44:receiverbci.py
class Config:
    PORT = "COM6"
    BAUD = 115200
    FS = 250
    WINDOW_SEC = 5
    BANDPASS_LOW = 0.5
    BANDPASS_HIGH = 50
    POWERLINE_FREQ = 50
    SAVE_DATA = True
    OUTPUT_DIR = Path("eeg_recordings")
```
```

- Keep `FS` aligned with firmware sampling rate (`SAMPLE_RATE`).
- Switch `POWERLINE_FREQ` between 50 Hz and 60 Hz depending on region.
- Increase `WINDOW_SEC` for longer history or reduce for faster updates.
- Adjust `SATURATION_THRESHOLD`, `MIN_SIGNAL_RANGE`, and `GOOD_NOISE_THRESHOLD` when using different analog front ends.

## Processing Pipeline

```
```56:121:receiverbci.py
class SignalProcessor:
    def process(self, data):
        data = self._remove_baseline(data)
        data = self._apply_notch_filters(data)
        data = self._apply_bandpass(data)
        return data
```
```

- Rolling-baseline subtraction mitigates DC drift when enough samples are present; otherwise a global mean is removed.
- Dual-notch filters target mains frequency fundamentals and first harmonics.
- 4th-order SOS bandpass constrains the pass band (0.5–50 Hz by default).

## Spectral Analysis

```
```163:516:receiverbci.py
freqs, psd = self.analyzer.compute_psd(data)
band_powers = self.analyzer.compute_band_powers(freqs, psd)
```
```

- Welch PSD uses segments up to four seconds for smoother spectra.
- Relative band powers normalize against total PSD energy for quick rhythm comparison.

## Known Limitations
- Single-channel acquisition only; multi-channel synchronization is not implemented.
- Requires stable USB power and good electrode contact—no impedance measurement or auto re-referencing yet.
- No automated artifact rejection; motion and blink artifacts appear in raw data.
- Matplotlib dashboard may stutter on low-end machines at 50 FPS—reduce `FPS_TARGET` or `WINDOW_SEC` if needed.

## Troubleshooting
- **No data:** verify COM port, baud rate, and that firmware outputs line-terminated floats.
- **Clipping:** lower analog gain or improve electrode placement; raw display turns red when exceeding `SATURATION_THRESHOLD`.
- **Noisy readings:** check ground/shielding, reduce motion, or widen notch `Q` carefully.
- **UI lag:** close other heavy apps, shorten window size, or disable CSV logging during exploration.

## Roadmap
- Multi-channel plotting with per-channel processing and synchronized PSDs.
- Firmware calibration utilities (offset/gain trim, impedance checks, OTA updates).
- Automated artifact detection and ML-based brain-state inference.
- Export pipelines for EDF/BDF and integration with neuroscience toolkits (MNE, EEGLAB).

