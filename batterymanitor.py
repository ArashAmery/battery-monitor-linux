import psutil
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import time
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import json
import os
import threading
import subprocess
import re

class BatteryMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Battery Monitor - Linux")
        self.root.geometry("1200x800")
        
        self.update_interval = 1000
        self.save_to_json = False
        self.history_file = "battery_history.json"
        self.update_job = None
        
        self.alerts_enabled = True
        self.low_battery_alerts = {15: False, 10: False, 5: False}
        self.overheat_threshold = 45
        self.charge_limit = 80
        self.last_alert_time = 0
        self.alert_cooldown = 300
        
        self.battery_path = self.find_battery_path()
        self.is_linux = os.path.exists('/sys/class/power_supply/')
        
        self.history = []
        self.consumption_data = deque(maxlen=86400)
        self.last_percent = None
        self.last_update_time = time.time()
        self.last_temperature = 0
        self.data_lock = threading.Lock()
        
        self.last_analytics_time = 0
        
        self.ask_user_preferences()
        self.setup_gui()
        self.start_data_collection()
        self.update_battery()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if messagebox.askokcancel("Exit", "Are you sure you want to exit the program?"):
            if self.update_job:
                try:
                    self.root.after_cancel(self.update_job)
                except:
                    pass
                self.update_job = None
            
            if self.save_to_json:
                self.save_history()
            self.root.destroy()

    def find_battery_path(self):
        battery_paths = [
            '/sys/class/power_supply/BAT0/',
            '/sys/class/power_supply/BAT1/',
            '/sys/class/power_supply/BAT/'
        ]
        for path in battery_paths:
            if os.path.exists(path):
                return path
        return None

    def get_linux_battery_info(self):
        if not self.battery_path:
            return None
        try:
            info = {}
            with open(os.path.join(self.battery_path, 'capacity'), 'r') as f:
                info['percent'] = float(f.read().strip())
            with open(os.path.join(self.battery_path, 'status'), 'r') as f:
                status = f.read().strip().upper()
                info['power_plugged'] = status in ['CHARGING', 'FULL']
                info['status'] = status
            temp_paths = [
                os.path.join(self.battery_path, 'temp'),
                os.path.join(self.battery_path, 'temperature'),
                '/sys/class/thermal/thermal_zone0/temp'
            ]
            for temp_path in temp_paths:
                if temp_path and os.path.exists(temp_path):
                    with open(temp_path, 'r') as f:
                        temp = float(f.read().strip())
                        if temp > 1000:
                            temp = temp / 1000
                        info['temperature'] = temp
                        break
            return info
        except Exception as e:
            print(f"Error reading Linux battery info: {e}")
            return None

    def get_linux_temperature(self):
        temp_sources = [
            f"{self.battery_path}/temp" if self.battery_path else None,
            f"{self.battery_path}/temperature" if self.battery_path else None,
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/thermal/thermal_zone1/temp",
            "/sys/class/hwmon/hwmon0/temp1_input",
            "/sys/class/hwmon/hwmon1/temp1_input",
            "/proc/acpi/thermal_zone/THM0/temperature",
            "/proc/acpi/thermal_zone/THM1/temperature"
        ]
        for source in temp_sources:
            if source and os.path.exists(source):
                try:
                    with open(source, 'r') as f:
                        temp = float(f.read().strip())
                        if temp > 1000:
                            temp = temp / 1000
                        return temp
                except:
                    continue
        try:
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'temp' in line.lower() and ':' in line:
                        match = re.search(r'([+-]?\d+\.\d+)°C', line)
                        if match:
                            return float(match.group(1))
        except:
            pass
        return 0

    def ask_user_preferences(self):
        try:
            result = messagebox.askyesno(
                "JSON Storage", 
                "Do you want to save battery data to JSON file?\n\nThis will create a battery_history.json file to store your battery usage history."
            )
            self.save_to_json = result
        except:
            self.save_to_json = False
        
        try:
            interval = simpledialog.askinteger(
                "Update Interval",
                "Enter update interval in milliseconds (default: 1000):",
                initialvalue=1000,
                minvalue=500,
                maxvalue=10000
            )
            if interval:
                self.update_interval = interval
        except:
            pass

    def setup_gui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.monitor_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.monitor_frame, text="📊 Real-time Monitor")
        self.setup_monitor_tab()
        
        self.analytics_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.analytics_frame, text="📈 Analytics")
        self.setup_analytics_tab()
        
        self.alerts_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.alerts_frame, text="🔔 Alerts")
        self.setup_alerts_tab()
        
        self.settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.settings_frame, text="⚙️ Settings")
        self.setup_settings_tab()
        
        if self.is_linux:
            self.linux_frame = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(self.linux_frame, text="🐧 Linux Info")
            self.setup_linux_tab()
        
        self.add_exit_button()

    def add_exit_button(self):
        exit_frame = ttk.Frame(self.root)
        exit_frame.pack(fill=tk.X, padx=10, pady=5)
        exit_button = ttk.Button(exit_frame, text="Exit Program", command=self.on_closing, style="Exit.TButton")
        exit_button.pack(side=tk.RIGHT, padx=5)
        style = ttk.Style()
        style.configure("Exit.TButton", foreground="red", font=("Arial", 10, "bold"))

    def setup_linux_tab(self):
        linux_frame = ttk.LabelFrame(self.linux_frame, text="Linux Battery Information", padding="10")
        linux_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        path_frame = ttk.Frame(linux_frame)
        path_frame.pack(fill=tk.X, pady=5)
        ttk.Label(path_frame, text="Battery Path:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(path_frame, text=self.battery_path or "Not detected", font=("Arial", 9)).pack(anchor=tk.W)
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = f.read()
            lines = os_info.split('\n')
            distro_info = {}
            for line in lines:
                if '=' in line:
                    key, value = line.split('=', 1)
                    distro_info[key] = value.strip('"')
            info_frame = ttk.Frame(linux_frame)
            info_frame.pack(fill=tk.X, pady=5)
            ttk.Label(info_frame, text="Distribution:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
            ttk.Label(info_frame, text=distro_info.get('PRETTY_NAME', 'Unknown'), font=("Arial", 9)).pack(anchor=tk.W)
        except Exception as e:
            print(f"Error getting OS info: {e}")

    def setup_monitor_tab(self):
        status_frame = ttk.LabelFrame(self.monitor_frame, text="Live Status", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        percent_frame = ttk.Frame(status_frame)
        percent_frame.pack(fill=tk.X, pady=5)
        ttk.Label(percent_frame, text="Battery Level:", font=("Arial", 14)).pack(side=tk.LEFT)
        self.percent_var = tk.StringVar(value="0.00%")
        self.percent_label = ttk.Label(percent_frame, textvariable=self.percent_var, font=("Arial", 24, "bold"))
        self.percent_label.pack(side=tk.LEFT, padx=10)
        self.alert_indicator = ttk.Label(percent_frame, text="", font=("Arial", 16))
        self.alert_indicator.pack(side=tk.RIGHT, padx=10)
        self.progress = ttk.Progressbar(status_frame, length=400, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)
        indicators_frame = ttk.Frame(status_frame)
        indicators_frame.pack(fill=tk.X, pady=10)
        left_frame = ttk.Frame(indicators_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.status_var = tk.StringVar(value="Checking...")
        ttk.Label(left_frame, text="Status:", font=("Arial", 11)).pack(anchor=tk.W)
        ttk.Label(left_frame, textvariable=self.status_var, font=("Arial", 11)).pack(anchor=tk.W)
        self.power_var = tk.StringVar(value="0.0 W")
        ttk.Label(left_frame, text="Power Consumption:", font=("Arial", 11)).pack(anchor=tk.W, pady=(5,0))
        ttk.Label(left_frame, textvariable=self.power_var, font=("Arial", 11)).pack(anchor=tk.W)
        right_frame = ttk.Frame(indicators_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.time_full_var = tk.StringVar(value="--:--")
        ttk.Label(right_frame, text="Time to Full:", font=("Arial", 11)).pack(anchor=tk.W)
        ttk.Label(right_frame, textvariable=self.time_full_var, font=("Arial", 11)).pack(anchor=tk.W)
        self.time_empty_var = tk.StringVar(value="--:--")
        ttk.Label(right_frame, text="Time to Empty:", font=("Arial", 11)).pack(anchor=tk.W, pady=(5,0))
        ttk.Label(right_frame, textvariable=self.time_empty_var, font=("Arial", 11)).pack(anchor=tk.W)
        temp_frame = ttk.LabelFrame(self.monitor_frame, text="🌡️ Temperature", padding="10")
        temp_frame.pack(fill=tk.X, pady=5)
        temp_main_frame = ttk.Frame(temp_frame)
        temp_main_frame.pack(fill=tk.X)
        self.temp_var = tk.StringVar(value="N/A")
        ttk.Label(temp_main_frame, textvariable=self.temp_var, font=("Arial", 12)).pack(side=tk.LEFT)
        self.temp_alert_indicator = ttk.Label(temp_main_frame, text="", font=("Arial", 12))
        self.temp_alert_indicator.pack(side=tk.RIGHT)
        info_frame = ttk.LabelFrame(self.monitor_frame, text="ℹ️ Information", padding="10")
        info_frame.pack(fill=tk.X, pady=5)
        info_text = f"Update interval: {self.update_interval}ms | JSON saving: {'Enabled' if self.save_to_json else 'Disabled'}"
        ttk.Label(info_frame, text=info_text, font=("Arial", 10)).pack()

    def setup_alerts_tab(self):
        alerts_config_frame = ttk.LabelFrame(self.alerts_frame, text="Alert Settings", padding="10")
        alerts_config_frame.pack(fill=tk.X, pady=5)
        ttk.Label(alerts_config_frame, text="Low Battery Alerts:", font=("Arial", 11, "bold")).pack(anchor=tk.W)
        self.alert_vars = {}
        for percent in [15, 10, 5]:
            var = tk.BooleanVar(value=True)
            self.alert_vars[percent] = var
            check = ttk.Checkbutton(alerts_config_frame, text=f"Alert at {percent}%", variable=var)
            check.pack(anchor=tk.W, padx=20, pady=2)
        ttk.Label(alerts_config_frame, text="\nOverheat Alert:", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(10,0))
        overheat_frame = ttk.Frame(alerts_config_frame)
        overheat_frame.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(overheat_frame, text="Temperature threshold:").pack(side=tk.LEFT)
        self.overheat_var = tk.StringVar(value=str(self.overheat_threshold))
        overheat_spin = ttk.Spinbox(overheat_frame, from_=35, to=60, increment=1, textvariable=self.overheat_var, width=5)
        overheat_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(overheat_frame, text="°C").pack(side=tk.LEFT)
        ttk.Label(alerts_config_frame, text="\nCharge Limit Alert:", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(10,0))
        charge_frame = ttk.Frame(alerts_config_frame)
        charge_frame.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(charge_frame, text="Notify when charged to:").pack(side=tk.LEFT)
        self.charge_limit_var = tk.StringVar(value=str(self.charge_limit))
        charge_spin = ttk.Spinbox(charge_frame, from_=70, to=95, increment=5, textvariable=self.charge_limit_var, width=5)
        charge_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(charge_frame, text="%").pack(side=tk.LEFT)
        ttk.Button(alerts_config_frame, text="Apply Alert Settings", command=self.apply_alert_settings).pack(pady=10)
        alert_history_frame = ttk.LabelFrame(self.alerts_frame, text="Alert History", padding="10")
        alert_history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.alert_history_text = tk.Text(alert_history_frame, height=10, font=("Arial", 9))
        scrollbar = ttk.Scrollbar(alert_history_frame, orient="vertical", command=self.alert_history_text.yview)
        self.alert_history_text.configure(yscrollcommand=scrollbar.set)
        self.alert_history_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.alert_history_text.insert(tk.END, "Alert history will be displayed here...\n")
        self.alert_history_text.config(state=tk.DISABLED)

    def setup_analytics_tab(self):
        chart_frame = ttk.LabelFrame(self.analytics_frame, text="24-Hour Consumption History", padding="10")
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.fig1, self.ax1 = plt.subplots(figsize=(10, 4))
        self.canvas1 = FigureCanvasTkAgg(self.fig1, chart_frame)
        self.canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        stats_frame = ttk.LabelFrame(self.analytics_frame, text="Statistics", padding="10")
        stats_frame.pack(fill=tk.X, pady=5)
        self.daily_stats = {
            'avg_consumption': tk.StringVar(value="Avg Consumption: - W"),
            'peak_consumption': tk.StringVar(value="Peak Consumption: - W"),
            'data_points': tk.StringVar(value="Data Points: 0"),
            'update_interval': tk.StringVar(value=f"Update Interval: {self.update_interval}ms")
        }
        for i, (key, var) in enumerate(self.daily_stats.items()):
            ttk.Label(stats_frame, textvariable=var, font=("Arial", 10)).grid(row=i//2, column=i%2, sticky=tk.W, padx=10, pady=2)

    def setup_settings_tab(self):
        settings_frame = ttk.LabelFrame(self.settings_frame, text="Application Settings", padding="10")
        settings_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        interval_frame = ttk.Frame(settings_frame)
        interval_frame.pack(fill=tk.X, pady=5)
        ttk.Label(interval_frame, text="Update Interval (ms):", font=("Arial", 11)).pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value=str(self.update_interval))
        interval_spinbox = ttk.Spinbox(interval_frame, from_=500, to=10000, increment=500, textvariable=self.interval_var, width=10)
        interval_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Button(interval_frame, text="Apply", command=self.apply_settings).pack(side=tk.LEFT, padx=5)
        json_frame = ttk.Frame(settings_frame)
        json_frame.pack(fill=tk.X, pady=5)
        self.json_var = tk.BooleanVar(value=self.save_to_json)
        json_check = ttk.Checkbutton(json_frame, text="Save data to JSON file", variable=self.json_var, command=self.toggle_json_saving)
        json_check.pack(anchor=tk.W)
        alert_frame = ttk.Frame(settings_frame)
        alert_frame.pack(fill=tk.X, pady=5)
        self.alerts_var = tk.BooleanVar(value=self.alerts_enabled)
        alert_check = ttk.Checkbutton(alert_frame, text="Enable all alerts", variable=self.alerts_var, command=self.toggle_alerts)
        alert_check.pack(anchor=tk.W)
        status_frame = ttk.Frame(settings_frame)
        status_frame.pack(fill=tk.X, pady=10)
        ttk.Label(status_frame, text=f"Current JSON file: {self.history_file}", font=("Arial", 9)).pack(anchor=tk.W)
        ttk.Label(status_frame, text=f"Data points in memory: {len(self.consumption_data)}", font=("Arial", 9)).pack(anchor=tk.W)

    def start_data_collection(self):
        def collect_data():
            while True:
                try:
                    battery = psutil.sensors_battery()
                    now_iso = datetime.now().isoformat()
                    if battery:
                        consumption = self.calculate_consumption_rate_threadsafe(battery.percent)
                        data_point = {
                            'timestamp': now_iso,
                            'percent': battery.percent,
                            'power_plugged': battery.power_plugged,
                            'consumption_rate': consumption
                        }
                        with self.data_lock:
                            self.consumption_data.append(data_point)
                            if self.save_to_json:
                                self.history.append(data_point)
                                if len(self.history) % 60 == 0:
                                    self.save_history()
                    else:
                        pass
                except Exception as e:
                    print(f"Data collection error: {e}")
                time.sleep(1)
        thread = threading.Thread(target=collect_data, daemon=True)
        thread.start()

    def apply_alert_settings(self):
        try:
            self.overheat_threshold = int(self.overheat_var.get())
            self.charge_limit = int(self.charge_limit_var.get())
            for percent in self.low_battery_alerts:
                self.low_battery_alerts[percent] = False
            messagebox.showinfo("Success", "Alert settings applied successfully!")
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for alert settings")

    def apply_settings(self):
        try:
            new_interval = int(self.interval_var.get())
            if 500 <= new_interval <= 10000:
                self.update_interval = new_interval
                messagebox.showinfo("Success", f"Update interval set to {new_interval}ms")
            else:
                messagebox.showerror("Error", "Please enter a value between 500 and 10000")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number")

    def toggle_json_saving(self):
        self.save_to_json = self.json_var.get()
        status = "enabled" if self.save_to_json else "disabled"
        messagebox.showinfo("JSON Saving", f"JSON saving {status}")

    def toggle_alerts(self):
        self.alerts_enabled = self.alerts_var.get()
        status = "enabled" if self.alerts_enabled else "disabled"
        messagebox.showinfo("Alerts", f"All alerts {status}")

    def add_alert_to_history(self, message):
        self.alert_history_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.alert_history_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.alert_history_text.see(tk.END)
        self.alert_history_text.config(state=tk.DISABLED)

    def play_linux_alert_sound(self):
        try:
            methods = [
                ['paplay', '/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga'],
                ['aplay', '/usr/share/sounds/alsa/Front_Center.wav'],
                ['beep']
            ]
            for method in methods:
                try:
                    subprocess.run(method, timeout=1, check=False)
                    break
                except:
                    continue
        except:
            pass

    def check_low_battery_alerts(self, percent):
        if not self.alerts_enabled:
            return
        current_time = time.time()
        for alert_percent in sorted(self.low_battery_alerts.keys(), reverse=True):
            if (percent <= alert_percent and 
                not self.low_battery_alerts[alert_percent] and
                current_time - self.last_alert_time > self.alert_cooldown):
                message = f"⚠️ LOW BATTERY: {percent}% remaining!"
                messagebox.showwarning("Low Battery", message)
                self.add_alert_to_history(message)
                self.play_linux_alert_sound()
                self.alert_indicator.config(text="⚠️", foreground="red")
                self.low_battery_alerts[alert_percent] = True
                self.last_alert_time = current_time
                break

    def check_overheat_alert(self, temperature):
        if not self.alerts_enabled or temperature <= 0:
            return
        current_time = time.time()
        if (temperature >= self.overheat_threshold and
            current_time - self.last_alert_time > self.alert_cooldown):
            message = f"🔥 OVERHEATING: Battery temperature is {temperature}°C!"
            messagebox.showwarning("Overheating", message)
            self.add_alert_to_history(message)
            self.play_linux_alert_sound()
            self.temp_alert_indicator.config(text="🔥", foreground="red")
            self.last_alert_time = current_time

    def check_charge_limit_alert(self, percent, is_charging):
        if not self.alerts_enabled or not is_charging:
            return
        current_time = time.time()
        if (percent >= self.charge_limit and
            current_time - self.last_alert_time > self.alert_cooldown):
            message = f"🔌 CHARGE LIMIT: Battery reached {percent}% - Consider unplugging!"
            messagebox.showinfo("Charge Limit", message)
            self.add_alert_to_history(message)
            self.play_linux_alert_sound()
            self.alert_indicator.config(text="🔌", foreground="orange")
            self.last_alert_time = current_time

    def get_temperature(self):
        if not self.is_linux:
            return "Not available"
        temp = self.get_linux_temperature()
        if temp > 0:
            self.last_temperature = temp
            return f"{temp:.1f}°C / {(temp * 9/5) + 32:.1f}°F"
        else:
            self.last_temperature = 0
            return "Not available"

    def update_battery(self):
        try:
            battery = psutil.sensors_battery()
            current_time = time.time()
            if battery:
                percent = battery.percent
                plugged = battery.power_plugged
                consumption_rate = 0.0
                with self.data_lock:
                    if len(self.consumption_data) > 0:
                        consumption_rate = self.consumption_data[-1].get('consumption_rate', 0.0)
                self.percent_var.set(f"{percent:.2f}%")
                self.progress['value'] = percent
                status_text = "⚡ Charging" if plugged else "🔋 Discharging"
                if percent == 100 and plugged:
                    status_text = "✅ Fully Charged"
                self.status_var.set(status_text)
                self.power_var.set(f"{consumption_rate:.1f} W")
                self.time_full_var.set(self.calculate_time_remaining(percent, consumption_rate, True))
                self.time_empty_var.set(self.calculate_time_remaining(percent, consumption_rate, False))
                temp_display = self.get_temperature()
                self.temp_var.set(temp_display)
                self.check_low_battery_alerts(percent)
                self.check_overheat_alert(self.last_temperature)
                self.check_charge_limit_alert(percent, plugged)
                if percent > 15 and self.alert_indicator.cget("text") == "⚠️":
                    self.alert_indicator.config(text="")
                if self.last_temperature < self.overheat_threshold - 5 and self.temp_alert_indicator.cget("text") == "🔥":
                    self.temp_alert_indicator.config(text="")
                if percent < self.charge_limit - 5 and self.alert_indicator.cget("text") == "🔌":
                    self.alert_indicator.config(text="")
                if current_time - self.last_analytics_time >= 5:
                    self.update_analytics()
                    self.last_analytics_time = current_time
            else:
                self.status_var.set("No battery detected")
        except Exception as e:
            print(f"Error updating battery info: {e}")
        self.update_job = self.root.after(self.update_interval, self.update_battery)

    def calculate_consumption_rate_threadsafe(self, current_percent):
        typical_capacity_wh = 50.0
        now = time.time()
        with self.data_lock:
            if self.last_percent is None:
                self.last_percent = current_percent
                self.last_update_time = now
                return 0.0
            elapsed = now - self.last_update_time
            if elapsed <= 0:
                return 0.0
            percent_change = self.last_percent - current_percent
            if percent_change == 0:
                self.last_update_time = now
                return 0.0
            percent_per_hour = (percent_change / elapsed) * 3600.0
            wh_per_hour = (percent_per_hour / 100.0) * typical_capacity_wh
            watts = abs(wh_per_hour)
            self.last_percent = current_percent
            self.last_update_time = now
            return round(watts, 2)

    def calculate_time_remaining(self, percent, power_watts, is_charging):
        try:
            power = float(power_watts)
        except:
            return "--:--"
        if power <= 0:
            return "--:--"
        typical_capacity = 50.0
        if is_charging:
            percent_needed = max(0.0, 100.0 - percent)
        else:
            percent_needed = max(0.0, percent)
        if percent_needed <= 0:
            return "00:00"
        energy_needed_wh = (percent_needed / 100.0) * typical_capacity
        hours_needed = energy_needed_wh / power if power > 0 else 0
        if hours_needed > 100:
            return "--:--"
        hours = int(hours_needed)
        minutes = int((hours_needed - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"

    def update_analytics(self):
        try:
            self.ax1.clear()
            twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
            with self.data_lock:
                recent_data = [d for d in self.consumption_data if datetime.fromisoformat(d['timestamp']) >= twenty_four_hours_ago]
            if recent_data:
                timestamps = [datetime.fromisoformat(d['timestamp']) for d in recent_data]
                consumption = [d['consumption_rate'] for d in recent_data]
                self.ax1.plot(timestamps, consumption, linewidth=2, alpha=0.7)
                self.ax1.set_xlabel('Time')
                self.ax1.set_ylabel('Power Consumption (W)')
                self.ax1.set_title('24-Hour Power Consumption History')
                self.ax1.grid(True, alpha=0.3)
                self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                self.canvas1.draw()
                avg_consumption = sum(consumption) / len(consumption) if consumption else 0
                peak_consumption = max(consumption) if consumption else 0
                self.daily_stats['avg_consumption'].set(f"Avg Consumption: {avg_consumption:.1f} W")
                self.daily_stats['peak_consumption'].set(f"Peak Consumption: {peak_consumption:.1f} W")
                self.daily_stats['data_points'].set(f"Data Points: {len(recent_data)}")
                self.daily_stats['update_interval'].set(f"Update Interval: {self.update_interval}ms")
        except Exception as e:
            print(f"Error updating analytics: {e}")

    def save_history(self):
        if self.save_to_json:
            try:
                with open(self.history_file, 'w') as f:
                    json.dump(self.history, f, indent=2)
            except Exception as e:
                print(f"Error saving history: {e}")

    def load_history(self):
        if os.path.exists(self.history_file) and self.save_to_json:
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

if __name__ == "__main__":
    root = tk.Tk()
    app = BatteryMonitor(root)
    root.mainloop()
