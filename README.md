# lancol-btle

Decodes BTLE data from Lancol battery monitors.

## Side-by-side terminal monitor

The Textual app displays voltage and signal strength for both configured Lancol
devices:

- `3C:E4:B0:A4:DF:89`
- `3C:E4:B0:A4:DF:F6`

Install the dependencies and start the monitor from a terminal:

```powershell
python -m pip install -r requirements.txt
python lancol_tui.py
```

The app scans continuously and exits when you press `Q` or `Ctrl+C`. Voltage is
decoded from the device name, and advertisements are accepted only when they
contain Lancol's manufacturer data. Each device panel also shows a live
plotext voltage chart of its last 30 readings, with labeled voltage and reading
axes. Press `T` to switch to a scrolling table of the latest 100 timestamped
readings, or press `T` again to return to the device panels.
