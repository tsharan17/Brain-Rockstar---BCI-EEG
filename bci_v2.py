"""
EEG BCI Analyzer — Full Python Script
══════════════════════════════════════
Compatible ESP32 output format (one line per sample):
    eegValue baseline diff
    e.g.  "2051 2048 3"

Fixes in this version:
  - matplotlib.use("TkAgg") set before pyplot import — fixes blank plot on Windows
  - FuncAnimation stored in variable — prevents garbage collector killing animation
  - ani reference kept alive through plt.show()

Requirements:
  pip install pyserial numpy scipy matplotlib

If TkAgg fails, replace with: matplotlib.use("Qt5Agg") and pip install pyqt5

Usage:
  1. Flash the baseline-tracking ESP32 sketch
  2. Change PORT in Config below to your COM port (e.g. 'COM5')
  3. Run:  python eeg_bci.py
"""

# ─────────────────────────────────────────────────────────────────────────────
# Backend — MUST be set before importing pyplot
# ─────────────────────────────────────────────────────────────────────────────
import matplotlib
matplotlib.use("TkAgg")   # stable on Windows; swap to "Qt5Agg" if tk missing

# ─────────────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────────────
import sys
import logging
import threading
from collections import deque
from dataclasses import dataclass

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.animation as animation
from scipy.signal import welch
import serial


# ─────────────────────────────────────────────────────────────────────────────
# NumPy 2.x compatibility
# ─────────────────────────────────────────────────────────────────────────────
_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz", None)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Config:
    # Serial
    port:      str = "COM3"         # ← Change to your port
    baud_rate: int = 115_200

    # Signal
    sample_rate:    int = 200
    buffer_size:    int = 512
    welch_nperseg:  int = 128
    welch_noverlap: int = 64

    # EEG bands (Hz)
    alpha_low:  float = 8.0
    alpha_high: float = 12.0
    beta_low:   float = 13.0
    beta_high:  float = 30.0

    # State machine
    history_len:         int   = 40
    focus_threshold:     float = 0.030
    relax_threshold:     float = 0.008
    min_state_hold:      int   = 30
    relax_streak_needed: int   = 15

    # Mirrors ESP32 LED trigger threshold — used for display only
    diff_spike_threshold: int = 300


CFG = Config()


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Thread-safe shared state
# ─────────────────────────────────────────────────────────────────────────────
class SharedState:
    def __init__(self):
        self._lock          = threading.Lock()
        self.eeg_buf        = deque(maxlen=CFG.buffer_size)
        self.baseline_buf   = deque(maxlen=CFG.buffer_size)
        self.diff_buf       = deque(maxlen=CFG.buffer_size)
        self.score_hist     = deque(maxlen=CFG.history_len)
        self.alpha_ratio    = 0.0
        self.beta_ratio     = 0.0
        self.avg_score      = 0.0
        self.state          = "—"
        self.state_hold     = 0
        self.relax_streak   = 0
        self.psd_freqs      = None
        self.psd_power      = None
        self.running        = True

    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def snapshot(self):
        with self._lock:
            return {
                "eeg_buf":      list(self.eeg_buf),
                "baseline_buf": list(self.baseline_buf),
                "diff_buf":     list(self.diff_buf),
                "alpha_ratio":  self.alpha_ratio,
                "beta_ratio":   self.beta_ratio,
                "avg_score":    self.avg_score,
                "state":        self.state,
                "relax_streak": self.relax_streak,
                "psd_freqs":    self.psd_freqs,
                "psd_power":    self.psd_power,
            }


SHARED = SharedState()


# ─────────────────────────────────────────────────────────────────────────────
# Serial parser — handles "eegValue baseline diff\n"
# ─────────────────────────────────────────────────────────────────────────────

def parse_line(raw_bytes: bytes):
    try:
        parts = raw_bytes.decode(errors="replace").strip().split()
        if len(parts) != 3:
            return None
        return float(parts[0]), float(parts[1]), float(parts[2])
    except (ValueError, AttributeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Signal analysis
# ─────────────────────────────────────────────────────────────────────────────

def band_power(freqs: np.ndarray, psd: np.ndarray, low: float, high: float) -> float:
    mask = (freqs >= low) & (freqs <= high)
    if not np.any(mask):
        return 0.0
    return float(_trapz(psd[mask], freqs[mask]))


def analyse(samples: np.ndarray):
    samples = samples - np.mean(samples)    # remove DC offset
    freqs, psd = welch(
        samples,
        fs=CFG.sample_rate,
        window="hann",
        nperseg=CFG.welch_nperseg,
        noverlap=CFG.welch_noverlap,
        scaling="density",
    )
    alpha = band_power(freqs, psd, CFG.alpha_low,  CFG.alpha_high)
    beta  = band_power(freqs, psd, CFG.beta_low,   CFG.beta_high)
    total = band_power(freqs, psd, 1.0, 45.0)
    if total < 1e-12:
        return 0.0, 0.0, freqs, psd
    return alpha / total, beta / total, freqs, psd


def update_state(score: float) -> str:
    SHARED.score_hist.append(score)
    avg     = float(np.mean(SHARED.score_hist))
    current = SHARED.state
    hold    = SHARED.state_hold

    SHARED.update(avg_score=avg)

    if hold < CFG.min_state_hold:
        SHARED.update(state_hold=hold + 1)
        return current

    new_state = current

    if current != "FOCUS":
        if avg > CFG.focus_threshold:
            new_state = "FOCUS"
            SHARED.update(relax_streak=0)
        elif current == "—":
            new_state = "RELAX"
    else:
        if avg < CFG.relax_threshold:
            streak = SHARED.relax_streak + 1
            SHARED.update(relax_streak=streak)
            if streak >= CFG.relax_streak_needed:
                new_state = "RELAX"
                SHARED.update(relax_streak=0)
                log.info("FOCUS → RELAX after %d low-score ticks", CFG.relax_streak_needed)
        else:
            SHARED.update(relax_streak=0)

    if new_state != current:
        SHARED.update(state=new_state, state_hold=0)
    else:
        SHARED.update(state_hold=hold + 1)

    return new_state


# ─────────────────────────────────────────────────────────────────────────────
# Serial reader thread
# ─────────────────────────────────────────────────────────────────────────────

def serial_reader(ser: serial.Serial) -> None:
    log.info("Serial reader started on %s", CFG.port)

    while SHARED.running:
        try:
            raw = ser.readline()
            if not raw:
                continue
        except serial.SerialException as exc:
            log.error("Serial error: %s", exc)
            SHARED.update(running=False)
            break

        parsed = parse_line(raw)
        if parsed is None:
            continue

        eeg_val, baseline_val, diff_val = parsed
        SHARED.eeg_buf.append(eeg_val)
        SHARED.baseline_buf.append(baseline_val)
        SHARED.diff_buf.append(diff_val)

        if len(SHARED.eeg_buf) < CFG.buffer_size:
            continue

        samples = np.array(SHARED.eeg_buf)
        alpha_r, beta_r, freqs, psd = analyse(samples)
        score = beta_r - alpha_r
        state = update_state(score)

        SHARED.update(
            alpha_ratio=alpha_r,
            beta_ratio=beta_r,
            psd_freqs=freqs,
            psd_power=psd,
        )

        log.info(
            "α=%.3f  β=%.3f  score=%+.4f  avg=%+.4f  streak=%d  → %s",
            alpha_r, beta_r, score, SHARED.avg_score, SHARED.relax_streak, state,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Plot theme
# ─────────────────────────────────────────────────────────────────────────────

BG       = "#0e0e0e"
PANEL    = "#161616"
BORDER   = "#2a2a2a"
TEXT_PRI = "#e0e0e0"
TEXT_SEC = "#888888"
COL_EEG  = "#4fc3f7"
COL_BASE = "#f9a825"
COL_DIFF = "#ef5350"
COL_ALP  = "#4fc3f7"
COL_BET  = "#ff8a65"
COL_PSD  = "#ce93d8"
COL_FOC  = "#69f0ae"
COL_REL  = "#ff7043"
COL_GRID = "#1e1e1e"


def _style_ax(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=TEXT_SEC, labelsize=8)
    ax.yaxis.label.set_color(TEXT_SEC)
    ax.xaxis.label.set_color(TEXT_SEC)
    ax.title.set_color(TEXT_PRI)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER)
    ax.grid(color=COL_GRID, linewidth=0.5, linestyle="--", alpha=0.7)


def build_figure():
    fig = plt.figure(figsize=(14, 8), facecolor=BG)
    fig.canvas.manager.set_window_title("EEG BCI — Live Analyzer")

    gs = gridspec.GridSpec(
        4, 3, figure=fig,
        hspace=0.60, wspace=0.38,
        left=0.06, right=0.97,
        top=0.91, bottom=0.07,
    )

    ax_eeg   = fig.add_subplot(gs[0, :])
    ax_diff  = fig.add_subplot(gs[1, :2])
    ax_psd   = fig.add_subplot(gs[2, :2])
    ax_bar   = fig.add_subplot(gs[1:3, 2])
    ax_hist  = fig.add_subplot(gs[3, :2])
    ax_state = fig.add_subplot(gs[3, 2])

    for ax in (ax_eeg, ax_diff, ax_psd, ax_bar, ax_hist, ax_state):
        _style_ax(ax)

    ax_state.set_xticks([]); ax_state.set_yticks([])
    for spine in ax_state.spines.values():
        spine.set_visible(False)

    fig.text(0.5, 0.965,
             "EEG Brain-Computer Interface — Real-Time Analysis",
             ha="center", color=TEXT_PRI, fontsize=12, fontweight="500")

    return fig, ax_eeg, ax_diff, ax_psd, ax_bar, ax_hist, ax_state


# ─────────────────────────────────────────────────────────────────────────────
# Animation
# ─────────────────────────────────────────────────────────────────────────────

def make_animator(fig, ax_eeg, ax_diff, ax_psd, ax_bar, ax_hist, ax_state):
    score_history = []

    def update(_frame):
        snap         = SHARED.snapshot()
        eeg_buf      = snap["eeg_buf"]
        base_buf     = snap["baseline_buf"]
        diff_buf     = snap["diff_buf"]
        alpha_r      = snap["alpha_ratio"]
        beta_r       = snap["beta_ratio"]
        avg_score    = snap["avg_score"]
        state        = snap["state"]
        relax_streak = snap["relax_streak"]
        freqs        = snap["psd_freqs"]
        psd          = snap["psd_power"]

        state_color = COL_FOC if state == "FOCUS" else (COL_REL if state == "RELAX" else TEXT_SEC)

        if not score_history or score_history[-1] != avg_score:
            score_history.append(avg_score)
        if len(score_history) > CFG.buffer_size:
            score_history.pop(0)

        xs = np.arange(len(eeg_buf))

        # ── Raw EEG + Baseline ────────────────────────────────────────────
        ax_eeg.cla(); _style_ax(ax_eeg)
        if eeg_buf:
            ax_eeg.plot(xs, eeg_buf,  color=COL_EEG,  linewidth=0.7, label="EEG raw",  alpha=0.9)
            ax_eeg.plot(xs, base_buf, color=COL_BASE, linewidth=1.2, label="Baseline", alpha=0.85, linestyle="--")
            ax_eeg.set_xlim(0, len(eeg_buf))
            ax_eeg.legend(fontsize=7, labelcolor=TEXT_SEC,
                          facecolor=PANEL, edgecolor=BORDER, loc="upper right")
        ax_eeg.set_title("Raw EEG Signal + ESP32 Adaptive Baseline", fontsize=9, pad=4)
        ax_eeg.set_ylabel("ADC Value", fontsize=8)

        # ── Diff signal ───────────────────────────────────────────────────
        ax_diff.cla(); _style_ax(ax_diff)
        if diff_buf:
            diff_arr = np.array(diff_buf)
            ax_diff.plot(xs, diff_arr, color=COL_DIFF, linewidth=0.7, alpha=0.85)
            ax_diff.axhline(CFG.diff_spike_threshold, color="#ff5252",
                            linewidth=0.8, linestyle="--", alpha=0.7,
                            label=f"LED threshold ({CFG.diff_spike_threshold})")
            ax_diff.fill_between(xs, CFG.diff_spike_threshold, diff_arr,
                                 where=diff_arr >= CFG.diff_spike_threshold,
                                 color="#ff5252", alpha=0.25, interpolate=True)
            ax_diff.set_xlim(0, len(diff_buf))
            ax_diff.legend(fontsize=7, labelcolor=TEXT_SEC,
                           facecolor=PANEL, edgecolor=BORDER)
        ax_diff.set_title("Diff  |eeg − baseline|  (ESP32 LED trigger)", fontsize=9, pad=4)
        ax_diff.set_ylabel("Amplitude", fontsize=8)

        # ── Welch PSD ─────────────────────────────────────────────────────
        ax_psd.cla(); _style_ax(ax_psd)
        if freqs is not None:
            ax_psd.semilogy(freqs, psd + 1e-12, color=COL_PSD, linewidth=0.9)
            ax_psd.set_xlim(0, 50)
            ax_psd.axvspan(CFG.alpha_low, CFG.alpha_high, alpha=0.12, color=COL_ALP, label="α 8–12 Hz")
            ax_psd.axvspan(CFG.beta_low,  CFG.beta_high,  alpha=0.12, color=COL_BET, label="β 13–30 Hz")
            ax_psd.legend(fontsize=7, labelcolor=TEXT_SEC,
                          facecolor=PANEL, edgecolor=BORDER, loc="upper right")
        ax_psd.set_title("Welch Power Spectral Density", fontsize=9, pad=4)
        ax_psd.set_xlabel("Frequency (Hz)", fontsize=8)
        ax_psd.set_ylabel("Power (log)", fontsize=8)

        # ── Band-power bars ───────────────────────────────────────────────
        ax_bar.cla(); _style_ax(ax_bar)
        bars = ax_bar.bar(
            ["Alpha\n8–12 Hz", "Beta\n13–30 Hz"],
            [alpha_r, beta_r],
            color=[COL_ALP, COL_BET],
            width=0.5, edgecolor=BORDER,
        )
        top = max(alpha_r, beta_r, 0.01) * 1.45
        ax_bar.set_ylim(0, top)
        ax_bar.set_title("Relative Band Power", fontsize=9, pad=4)
        ax_bar.set_ylabel("Power / Broadband", fontsize=8)
        for bar, val in zip(bars, [alpha_r, beta_r]):
            ax_bar.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + top * 0.03,
                f"{val:.3f}",
                ha="center", va="bottom", color=TEXT_PRI, fontsize=9,
            )

        # ── Score history ─────────────────────────────────────────────────
        ax_hist.cla(); _style_ax(ax_hist)
        if len(score_history) > 1:
            hs = np.arange(len(score_history))
            ys = np.array(score_history)
            ax_hist.fill_between(hs, 0, ys, where=ys >= 0,
                                 color=COL_FOC, alpha=0.25, interpolate=True)
            ax_hist.fill_between(hs, 0, ys, where=ys <  0,
                                 color=COL_REL, alpha=0.25, interpolate=True)
            ax_hist.plot(hs, ys, color=TEXT_SEC, linewidth=0.8)
            ax_hist.axhline(CFG.focus_threshold, color=COL_FOC, linewidth=0.8,
                            linestyle="--", alpha=0.8,
                            label=f"Focus threshold ({CFG.focus_threshold})")
            ax_hist.axhline(CFG.relax_threshold, color=COL_REL, linewidth=0.8,
                            linestyle="--", alpha=0.8,
                            label=f"Relax threshold ({CFG.relax_threshold})")
            ax_hist.axhline(0, color=BORDER, linewidth=0.5)
            ax_hist.set_xlim(0, max(len(score_history) - 1, 1))
            ax_hist.legend(fontsize=7, labelcolor=TEXT_SEC,
                           facecolor=PANEL, edgecolor=BORDER, loc="upper left")
        ax_hist.set_title("β−α Score History  (positive → focus tendency)", fontsize=9, pad=4)
        ax_hist.set_xlabel("Update ticks", fontsize=8)
        ax_hist.set_ylabel("β − α ratio", fontsize=8)

        # ── State indicator ───────────────────────────────────────────────
        ax_state.cla()
        ax_state.set_facecolor(PANEL)
        ax_state.set_xticks([]); ax_state.set_yticks([])
        for spine in ax_state.spines.values():
            spine.set_edgecolor(state_color)
            spine.set_linewidth(1.5)
            spine.set_visible(True)

        icon = "◉" if state == "FOCUS" else ("○" if state == "RELAX" else "·")
        ax_state.text(0.5, 0.65, icon,
                      ha="center", va="center",
                      color=state_color, fontsize=34,
                      transform=ax_state.transAxes)
        ax_state.text(0.5, 0.42, state,
                      ha="center", va="center",
                      color=state_color, fontsize=16, fontweight="500",
                      transform=ax_state.transAxes)
        ax_state.text(0.5, 0.26, f"score {avg_score:+.4f}",
                      ha="center", va="center",
                      color=TEXT_SEC, fontsize=8,
                      transform=ax_state.transAxes)
        ax_state.text(0.5, 0.14, "LED: ESP32 controlled",
                      ha="center", va="center",
                      color=TEXT_SEC, fontsize=7, alpha=0.6,
                      transform=ax_state.transAxes)

        if state == "FOCUS" and relax_streak > 0:
            ax_state.text(0.5, 0.05,
                          f"relax streak  {relax_streak}/{CFG.relax_streak_needed}",
                          ha="center", va="center",
                          color=COL_REL, fontsize=7, alpha=0.8,
                          transform=ax_state.transAxes)

        return []

    return update


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        ser = serial.Serial(CFG.port, CFG.baud_rate, timeout=2)
        log.info("Opened %s @ %d baud", CFG.port, CFG.baud_rate)
    except serial.SerialException as exc:
        log.error("Cannot open %s: %s", CFG.port, exc)
        sys.exit(1)

    reader_thread = threading.Thread(
        target=serial_reader, args=(ser,), daemon=True, name="serial-reader"
    )
    reader_thread.start()

    fig, ax_eeg, ax_diff, ax_psd, ax_bar, ax_hist, ax_state = build_figure()
    update_fn = make_animator(fig, ax_eeg, ax_diff, ax_psd, ax_bar, ax_hist, ax_state)

    # ── IMPORTANT: store ani in a variable — if not stored, Python's garbage
    #    collector destroys the FuncAnimation object and the plot goes blank.
    ani = animation.FuncAnimation(
        fig, update_fn,
        interval=100,
        blit=False,
        cache_frame_data=False,
    )

    log.info("Live plot open. Close the window or press Ctrl-C to quit.")

    try:
        plt.show()          # blocks here; ani stays alive while show() runs
    except KeyboardInterrupt:
        pass
    finally:
        SHARED.update(running=False)
        reader_thread.join(timeout=2)
        ser.close()
        log.info("Serial port closed. Goodbye.")

    # Keep reference alive until after plt.show() returns
    _ = ani


if __name__ == "__main__":
    main()