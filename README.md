# Battery Monitor - Linux

![Battery Monitor](screenshot.png)

**Battery Monitor** is a **real-time battery monitoring tool for Linux**. It provides detailed information about battery percentage, temperature, alerts, and power consumption analytics. Built using **Python**, **Tkinter**, and **Matplotlib**, it offers a user-friendly interface for monitoring and managing battery usage.

---

## Features

### Real-Time Monitoring

* Display battery percentage with a progress bar.
* Show charging status (Charging / Discharging / Fully Charged).
* Display battery temperature with overheat warnings.
* Update information at configurable intervals.

### Alerts

* Low battery alerts at 15%, 10%, and 5%.
* Overheat alert when battery temperature exceeds a threshold.
* Charge limit alert when battery reaches a specified charge level.
* Alert history display with timestamps.

### Analytics

* 24-hour power consumption chart.
* Consumption rate calculation in Watts.
* Option to save historical data to a JSON file.

### Settings

* Adjust update interval (in milliseconds).
* Enable or disable JSON data saving.
* Configure battery and temperature alerts.
* Clean, tab-based GUI for easy navigation.

### Linux Support

* Automatic detection of battery path.
* Display Linux distribution information.
* Support for multiple battery and temperature sensor paths.

---

## Requirements

* Python 3.8 or higher
* Python libraries:

  * `psutil`
  * `tkinter` (usually included with Python)
  * `matplotlib`

### Install Dependencies

```bash
pip install psutil matplotlib
```

> If `tkinter` is missing:

```bash
sudo apt install python3-tk
```

---

## Installation & Run

1. Clone the repository:

```bash
git clone https://github.com/username/battery-monitor-linux.git
cd battery-monitor-linux
```

2. Run the application:

```bash
python3 battery_monitor.py
```

3. On first launch, configure preferences like JSON saving and update interval through simple dialogs.

---

## File Structure

```
battery-monitor-linux/
│
├─ battery_monitor.py      # Main application file
├─ battery_history.json    # (Optional) Saved battery data
├─ README.md               # This file
└─ screenshot.png          # Screenshot of the app (optional)
```

---

## Usage

1. **Real-time Monitor Tab**: Shows current battery level, status, and temperature.
2. **Analytics Tab**: Displays 24-hour power consumption and statistics.
3. **Alerts Tab**: Manage alert settings and view alert history.
4. **Settings Tab**: Adjust update interval and JSON saving options.
5. **Linux Info Tab**: Shows battery path and Linux distribution info.

---

## Notes

* The program uses **threading for background data collection** to keep the UI responsive.
* Historical data is saved to JSON if enabled, allowing long-term analysis.
* Alerts have a **cooldown period of 5 minutes** to prevent repeated notifications.
* Designed for **Linux systems**, automatically detecting battery and thermal sensor paths.

---

## Contributing

* Add new features, such as multi-battery support or improved UI.
* Pull requests are welcome.

---

## License

This project is licensed under the **MIT License** – free to use, modify, and distribute.

