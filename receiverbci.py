import serial
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.signal import butter, sosfiltfilt, welch, iirnotch, filtfilt
from collections import deque
import time
from datetime import datetime
import csv
from pathlib import Path

# ===== CONFIGURATION =====
class Config:
    # Serial settings
    PORT = "COM6"
    BAUD = 115200
    TIMEOUT = 1
    
    # Signal processing
    FS = 250  # Sampling rate (Hz)
    WINDOW_SEC = 5  # Seconds of data to display
    BASELINE_WINDOW = 0.5  # seconds
    
    # Filtering
    BANDPASS_LOW = 0.5
    BANDPASS_HIGH = 50
    FILTER_ORDER = 4
    NOTCH_Q = 30
    POWERLINE_FREQ = 50  # Change to 60 for US
    
    # Display
    FPS_TARGET = 50
    FRAME_INTERVAL = 20  # ms
    AUTOSCALE_INTERVAL = 100  # frames
    DIAGNOSTIC_INTERVAL = 3.0  # seconds
    
    # Data saving
    SAVE_DATA = True
    OUTPUT_DIR = Path("eeg_recordings")
    
    # Signal quality thresholds
    SATURATION_THRESHOLD = 1.8
    MIN_SIGNAL_RANGE = 0.001
    GOOD_NOISE_THRESHOLD = 0.01

# ===== EEG BAND DEFINITIONS =====
EEG_BANDS = {
    "Delta": (0.5, 4, '#1f77b4'),
    "Theta": (4, 8, '#ff7f0e'),
    "Alpha": (8, 13, '#2ca02c'),
    "Beta": (13, 30, '#d62728'),
    "Gamma": (30, 50, '#9467bd')
}

# ===== SIGNAL PROCESSING =====
class SignalProcessor:
    def __init__(self, fs=Config.FS):
        self.fs = fs
        self.baseline_window = int(fs * Config.BASELINE_WINDOW)
        
        # Pre-compute filters
        self.sos_bandpass = self._create_bandpass()
        self.notch_filters = self._create_notch_filters()
    
    def _create_bandpass(self):
        """Create bandpass filter"""
        nyq = 0.5 * self.fs
        low = Config.BANDPASS_LOW / nyq
        high = Config.BANDPASS_HIGH / nyq
        return butter(Config.FILTER_ORDER, [low, high], btype='band', output='sos')
    
    def _create_notch_filters(self):
        """Create notch filters for powerline noise"""
        filters = []
        for freq in [Config.POWERLINE_FREQ, Config.POWERLINE_FREQ * 2]:
            b, a = iirnotch(freq, Config.NOTCH_Q, self.fs)
            filters.append((b, a))
        return filters
    
    def process(self, data):
        """Complete signal processing pipeline"""
        if len(data) < 18:
            return data
        
        data = np.array(data, dtype=float)
        
        # 1. Remove DC offset with rolling baseline
        data = self._remove_baseline(data)
        
        # 2. Apply notch filters
        data = self._apply_notch_filters(data)
        
        # 3. Apply bandpass filter
        data = self._apply_bandpass(data)
        
        return data
    
    def _remove_baseline(self, data):
        """Remove DC offset using rolling window"""
        if len(data) > self.baseline_window:
            baseline = np.convolve(data, np.ones(self.baseline_window)/self.baseline_window, mode='same')
            return data - baseline
        return data - np.mean(data)
    
    def _apply_notch_filters(self, data):
        """Apply notch filters for powerline noise"""
        try:
            for b, a in self.notch_filters:
                data = filtfilt(b, a, data)
        except Exception as e:
            print(f"Notch filter warning: {e}")
        return data
    
    def _apply_bandpass(self, data):
        """Apply bandpass filter"""
        try:
            padlen = min(len(data) - 1, 3 * len(self.sos_bandpass))
            return sosfiltfilt(self.sos_bandpass, data, padlen=padlen)
        except Exception as e:
            print(f"Bandpass filter warning: {e}")
            return data

# ===== SIGNAL QUALITY ASSESSMENT =====
class SignalQuality:
    @staticmethod
    def assess(data, fs=Config.FS):
        """Assess signal quality metrics"""
        if len(data) < fs:
            return {"contact": "Initializing", "saturation": False, "noise_level": 0.0, "snr": 0.0}
        
        recent = data[-fs:]  # Last second
        
        # Check saturation
        max_val = np.max(np.abs(recent))
        saturated = max_val > Config.SATURATION_THRESHOLD
        
        # Noise estimation
        diff = np.diff(recent)
        noise_level = np.std(diff)
        
        # Signal-to-noise ratio
        signal_power = np.var(recent)
        noise_power = noise_level ** 2
        snr = 10 * np.log10(signal_power / (noise_power + 1e-12))
        
        # Contact quality assessment
        signal_range = np.ptp(recent)
        if signal_range < Config.MIN_SIGNAL_RANGE:
            contact = "Poor/No Contact"
        elif noise_level < Config.GOOD_NOISE_THRESHOLD and signal_range > 0.01:
            contact = "Good"
        else:
            contact = "Noisy"
        
        return {
            "contact": contact,
            "saturation": saturated,
            "noise_level": noise_level,
            "snr": snr,
            "range": signal_range
        }

# ===== SPECTRAL ANALYSIS =====
class SpectralAnalyzer:
    def __init__(self, fs=Config.FS):
        self.fs = fs
        
    def compute_psd(self, data):
        """Compute power spectral density"""
        if len(data) < self.fs * 2:
            return None, None
        
        try:
            nperseg = min(self.fs * 4, len(data))
            freqs, psd = welch(data, self.fs, nperseg=nperseg, scaling='density')
            return freqs, psd
        except Exception as e:
            print(f"PSD computation error: {e}")
            return None, None
    
    def compute_band_powers(self, freqs, psd):
        """Compute relative power in each EEG band"""
        if freqs is None or psd is None:
            return {name: 0.0 for name in EEG_BANDS.keys()}
        
        total_power = np.sum(psd)
        if total_power < 1e-12:
            return {name: 0.0 for name in EEG_BANDS.keys()}
        
        band_powers = {}
        for name, (low, high, _) in EEG_BANDS.items():
            idx = np.logical_and(freqs >= low, freqs <= high)
            power = np.sum(psd[idx])
            band_powers[name] = power / total_power
        
        return band_powers

# ===== DATA RECORDING =====
class DataRecorder:
    def __init__(self, enabled=Config.SAVE_DATA):
        self.enabled = enabled
        self.file = None
        self.writer = None
        self.start_time = None
        
        if self.enabled:
            self._initialize()
    
    def _initialize(self):
        """Initialize CSV file for recording"""
        Config.OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = Config.OUTPUT_DIR / f"eeg_recording_{timestamp}.csv"
        
        self.file = open(filename, 'w', newline='')
        self.writer = csv.writer(self.file)
        self.writer.writerow(['Timestamp', 'Raw_V', 'Filtered_V'])
        self.start_time = time.time()
        
        print(f"Recording to: {filename}")
    
    def record(self, raw_value, filtered_value):
        """Record a data point"""
        if self.enabled and self.writer:
            timestamp = time.time() - self.start_time
            self.writer.writerow([f"{timestamp:.6f}", f"{raw_value:.6f}", f"{filtered_value:.6f}"])
    
    def close(self):
        """Close recording file"""
        if self.file:
            self.file.close()
            print("Recording saved")

# ===== MAIN APPLICATION =====
class EEGMonitor:
    def __init__(self):
        # Initialize components
        self.processor = SignalProcessor()
        self.analyzer = SpectralAnalyzer()
        self.recorder = DataRecorder()
        
        # Serial connection
        self.ser = self._connect_serial()
        
        # Data buffers
        buffer_size = Config.FS * Config.WINDOW_SEC
        self.raw_buffer = deque(maxlen=buffer_size)
        self.filtered_buffer = deque(maxlen=buffer_size)
        
        # Initialize with zeros
        for _ in range(buffer_size):
            self.raw_buffer.append(0.0)
            self.filtered_buffer.append(0.0)
        
        # State variables
        self.frame_count = 0
        self.samples_received = 0
        self.last_fps_time = time.time()
        self.last_diagnostic_time = time.time()
        self.autoscale_counter = 0
        self.filter_ready = False
        self.signal_quality = {}
        
        # Setup visualization
        self._setup_plot()
    
    def _connect_serial(self):
        """Establish serial connection"""
        try:
            ser = serial.Serial(Config.PORT, Config.BAUD, timeout=Config.TIMEOUT)
            time.sleep(2)
            ser.flushInput()
            print(f"Connected to {Config.PORT} at {Config.BAUD} baud")
            return ser
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            exit(1)
    
    def _setup_plot(self):
        """Setup matplotlib visualization"""
        plt.style.use('dark_background')
        self.fig = plt.figure(figsize=(16, 9))
        gs = self.fig.add_gridspec(3, 3, hspace=0.35, wspace=0.4)
        
        # Main EEG waveform
        self.ax_wave = self.fig.add_subplot(gs[0:2, :])
        xdata = np.linspace(-Config.WINDOW_SEC, 0, len(self.raw_buffer))
        self.line_filtered, = self.ax_wave.plot(xdata, list(self.filtered_buffer), 
                                                 linewidth=1.2, color='cyan', label='Filtered')
        self.line_raw, = self.ax_wave.plot(xdata, list(self.raw_buffer), 
                                           linewidth=0.5, color='gray', alpha=0.3, label='Raw')
        
        self.ax_wave.set_ylim(-0.5, 0.5)
        self.ax_wave.set_xlim(-Config.WINDOW_SEC, 0)
        self.ax_wave.set_title("EEG Waveform - Live Signal", fontsize=14, fontweight='bold')
        self.ax_wave.set_xlabel("Time (s)", fontsize=11)
        self.ax_wave.set_ylabel("Voltage (V)", fontsize=11)
        self.ax_wave.grid(True, alpha=0.2, linestyle='--')
        self.ax_wave.legend(loc='upper right', fontsize=10)
        
        # Voltage display panel
        self.ax_voltage = self.fig.add_subplot(gs[2, 0])
        self.ax_voltage.set_xlim(0, 1)
        self.ax_voltage.set_ylim(0, 1)
        self.ax_voltage.axis('off')
        
        # Create voltage display elements
        self.voltage_display = {
            'raw': self.ax_voltage.text(0.5, 0.75, '0.000 V', 
                                       ha='center', va='center', fontsize=36, 
                                       fontweight='bold', color='#00FF00', family='monospace'),
            'raw_label': self.ax_voltage.text(0.5, 0.9, 'RAW VOLTAGE', 
                                            ha='center', va='center', fontsize=12, 
                                            fontweight='bold', color='gray'),
            'filtered': self.ax_voltage.text(0.5, 0.35, '0.000 V', 
                                           ha='center', va='center', fontsize=28, 
                                           fontweight='bold', color='cyan', family='monospace'),
            'filtered_label': self.ax_voltage.text(0.5, 0.5, 'FILTERED', 
                                                  ha='center', va='center', fontsize=11, 
                                                  fontweight='bold', color='gray'),
            'range': self.ax_voltage.text(0.5, 0.15, 'Range: 0.000 V', 
                                        ha='center', va='center', fontsize=10, 
                                        color='white', family='monospace'),
            'mean': self.ax_voltage.text(0.5, 0.05, 'Mean: 0.000 V', 
                                       ha='center', va='center', fontsize=10, 
                                       color='white', family='monospace')
        }
        
        # Band power bars
        self.ax_bands = self.fig.add_subplot(gs[2, 1])
        band_names = list(EEG_BANDS.keys())
        colors = [EEG_BANDS[name][2] for name in band_names]
        self.bars = self.ax_bands.bar(band_names, [0]*len(band_names), 
                                       color=colors, alpha=0.8, edgecolor='white', linewidth=1)
        
        self.ax_bands.set_ylim(0, 1)
        self.ax_bands.set_title("Relative Band Power", fontsize=12, fontweight='bold')
        self.ax_bands.set_ylabel("Relative Power", fontsize=10)
        self.ax_bands.grid(True, alpha=0.2, axis='y')
        
        self.bar_labels = [self.ax_bands.text(bar.get_x() + bar.get_width()/2, 0, '0%',
                                               ha='center', va='bottom', fontsize=9, fontweight='bold')
                          for bar in self.bars]
        
        # Power spectral density
        self.ax_psd = self.fig.add_subplot(gs[2, 2])
        self.psd_line, = self.ax_psd.plot([], [], color='lime', linewidth=2)
        self.ax_psd.set_xlim(0, Config.BANDPASS_HIGH)
        self.ax_psd.set_ylim(0, 1)
        self.ax_psd.set_title("Power Spectral Density", fontsize=12, fontweight='bold')
        self.ax_psd.set_xlabel("Frequency (Hz)", fontsize=10)
        self.ax_psd.set_ylabel("Power (normalized)", fontsize=10)
        self.ax_psd.grid(True, alpha=0.2)
        
        # Add band region shading
        for name, (low, high, color) in EEG_BANDS.items():
            self.ax_psd.axvspan(low, high, alpha=0.1, color=color)
        
        # Status text
        self.status_text = self.ax_wave.text(0.02, 0.98, '', transform=self.ax_wave.transAxes,
                                             verticalalignment='top', fontsize=10, family='monospace',
                                             bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))
        
        self.fig.canvas.mpl_connect('close_event', self._on_close)
    
    def _read_serial_data(self):
        """Read and validate data from serial port"""
        samples_read = 0
        max_samples = 30
        
        while self.ser.in_waiting > 0 and samples_read < max_samples:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    break
                
                value = float(line)
                
                # Sanity check
                if abs(value) > 5.0:
                    continue
                
                self.raw_buffer.append(value)
                self.samples_received += 1
                samples_read += 1
                
                # Debug first samples
                if self.samples_received <= 5:
                    print(f"Sample {self.samples_received}: {value:.6f}V")
                    
            except ValueError:
                continue
        
        return samples_read
    
    def _print_diagnostics(self):
        """Print diagnostic information"""
        if len(self.raw_buffer) < 100:
            return
        
        recent = list(self.raw_buffer)[-Config.FS:]
        
        print(f"\n{'='*50}")
        print(f"DIAGNOSTICS @ {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*50}")
        print(f"Signal Range (P-P): {np.ptp(recent):.6f} V")
        print(f"Mean:               {np.mean(recent):.6f} V")
        print(f"Std Dev:            {np.std(recent):.6f} V")
        print(f"Min/Max:            {np.min(recent):.6f} / {np.max(recent):.6f} V")
        print(f"SNR:                {self.signal_quality.get('snr', 0):.1f} dB")
        print(f"Contact Quality:    {self.signal_quality.get('contact', 'Unknown')}")
        
        # Warnings
        if np.std(recent) < 0.0001:
            print("WARNING: Signal appears STUCK - check electrodes!")
        elif np.ptp(recent) < Config.MIN_SIGNAL_RANGE:
            print("WARNING: Very low signal - poor contact?")
        else:
            print("Signal variation looks healthy")
        
        print(f"{'='*50}\n")
    
    def _update_plots(self):
        """Update all plot elements"""
        raw_array = np.array(self.raw_buffer)
        self.line_raw.set_ydata(raw_array)
        
        # Update voltage display with current values
        current_raw = raw_array[-1] if len(raw_array) > 0 else 0.0
        self.voltage_display['raw'].set_text(f'{current_raw:+.4f} V')
        
        # Color code based on magnitude
        if abs(current_raw) > Config.SATURATION_THRESHOLD:
            self.voltage_display['raw'].set_color('#FF0000')  # Red if saturated
        elif abs(current_raw) > 0.5:
            self.voltage_display['raw'].set_color('#FFA500')  # Orange if high
        else:
            self.voltage_display['raw'].set_color('#00FF00')  # Green if normal
        
        # Wait for minimum samples before filtering
        min_samples = Config.FS
        
        if self.samples_received >= min_samples:
            if not self.filter_ready:
                print(f"Signal processing active ({self.samples_received} samples)")
                self.filter_ready = True
            
            # Process signal
            filtered = self.processor.process(raw_array)
            self.filtered_buffer.extend(filtered[-len(self.raw_buffer):])
            self.line_filtered.set_ydata(filtered)
            
            # Update filtered voltage display
            current_filtered = filtered[-1] if len(filtered) > 0 else 0.0
            self.voltage_display['filtered'].set_text(f'{current_filtered:+.4f} V')
            
            # Update statistics (last 1 second)
            recent_raw = raw_array[-Config.FS:]
            if len(recent_raw) > 0:
                signal_range = np.ptp(recent_raw)
                signal_mean = np.mean(recent_raw)
                self.voltage_display['range'].set_text(f'Range: {signal_range:.4f} V')
                self.voltage_display['mean'].set_text(f'Mean: {signal_mean:+.4f} V')
            
            # Record data
            if len(filtered) > 0:
                self.recorder.record(raw_array[-1], filtered[-1])
            
            # Assess quality
            self.signal_quality = SignalQuality.assess(raw_array)
            
            # Auto-scale
            self._autoscale(filtered)
            
            # Compute and update spectral analysis
            self._update_spectral_analysis(filtered)
    
    def _autoscale(self, data):
        """Auto-scale Y-axis based on signal amplitude"""
        self.autoscale_counter += 1
        if self.autoscale_counter <= Config.AUTOSCALE_INTERVAL:
            return
        
        self.autoscale_counter = 0
        recent = data[-Config.FS*2:]
        
        if len(recent) > 0:
            std = np.std(recent)
            mean = np.mean(recent)
            if std > 0.001:
                y_range = std * 4.5
                self.ax_wave.set_ylim(mean - y_range, mean + y_range)
    
    def _update_spectral_analysis(self, data):
        """Update PSD and band power visualizations"""
        if len(data) < Config.FS * 2:
            return
        
        try:
            freqs, psd = self.analyzer.compute_psd(data)
            if freqs is None:
                return
            
            # Update PSD plot
            idx = freqs <= Config.BANDPASS_HIGH
            psd_normalized = psd[idx] / (np.max(psd[idx]) + 1e-12)
            self.psd_line.set_data(freqs[idx], psd_normalized)
            
            # Update band powers
            band_powers = self.analyzer.compute_band_powers(freqs, psd)
            
            for i, (name, power) in enumerate(band_powers.items()):
                self.bars[i].set_height(power)
                self.bar_labels[i].set_text(f'{power*100:.1f}%')
                self.bar_labels[i].set_y(power)
                
        except Exception as e:
            print(f"Spectral analysis error: {e}")
    
    def _update_status(self):
        """Update status text display"""
        if self.frame_count % 30 != 0:
            return
        
        current_time = time.time()
        fps = 30 / (current_time - self.last_fps_time + 1e-6)
        
        status = f'FPS: {fps:.1f} | Samples: {self.samples_received:,}\n'
        status += f'Contact: {self.signal_quality.get("contact", "Unknown")}'
        
        if self.signal_quality.get("saturation", False):
            status += ' | SATURATED'
        
        snr = self.signal_quality.get("snr", 0)
        if snr > 0:
            status += f' | SNR: {snr:.1f}dB'
        
        self.status_text.set_text(status)
        self.last_fps_time = current_time
    
    def update(self, frame):
        """Main update function called by animation"""
        try:
            # Read serial data
            self._read_serial_data()
            
            # Print diagnostics periodically
            current_time = time.time()
            if current_time - self.last_diagnostic_time > Config.DIAGNOSTIC_INTERVAL:
                self.last_diagnostic_time = current_time
                self._print_diagnostics()
            
            # Update visualizations
            self._update_plots()
            
            # Update status display
            self.frame_count += 1
            self._update_status()
            
        except Exception as e:
            print(f"Update error: {e}")
        
        # Return all artists that need updating
        voltage_artists = list(self.voltage_display.values())
        return (self.line_filtered, self.line_raw, *self.bars, 
                *self.bar_labels, self.psd_line, self.status_text, *voltage_artists)
    
    def _on_close(self, event):
        """Cleanup on window close"""
        self.ser.close()
        self.recorder.close()
        print(f"\nSession ended - Total samples: {self.samples_received:,}")
    
    def run(self):
        """Start the monitoring application"""
        self.ani = FuncAnimation(self.fig, self.update, 
                                interval=Config.FRAME_INTERVAL, 
                                blit=True, cache_frame_data=False)
        plt.tight_layout()
        plt.show()
        
        # Cleanup
        self.ser.close()
        self.recorder.close()

# ===== ENTRY POINT =====
if __name__ == "__main__":
    print("="*60)
    print("BCI EEG Monitor - Enhanced Version")
    print("="*60)
    print(f"Sampling Rate: {Config.FS} Hz")
    print(f"Bandpass: {Config.BANDPASS_LOW}-{Config.BANDPASS_HIGH} Hz")
    print(f"Powerline Filter: {Config.POWERLINE_FREQ} Hz")
    print(f"Recording: {'Enabled' if Config.SAVE_DATA else 'Disabled'}")
    print("="*60 + "\n")
    
    monitor = EEGMonitor()
    monitor.run()