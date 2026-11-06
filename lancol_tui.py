import asyncio
from collections import deque
from datetime import datetime
from itertools import count

import plotext as plt
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, Static


MANUFACTURER_ID = 58428
DEVICE_ADDRESSES = (
    "3C:E4:B0:A4:DF:89",
    "3C:E4:B0:A4:DF:F6",
)
VOLTAGE_HISTORY_SIZE = 30


def decode_voltage(name: str | None) -> float | None:
    if not name:
        return None

    try:
        return float(name.split()[-1].rstrip("V"))
    except (IndexError, ValueError):
        return None


def render_voltage_chart(values: list[float], width: int, height: int) -> Text:
    if not values:
        return Text("Waiting for voltage readings", style="dim")

    figure = plt.figure
    figure.clear()
    figure.plot_size(width, height)
    figure.theme("dark")
    figure.title("Voltage history (oldest to newest)")
    figure.label("Reading", "x")
    figure.label("Voltage (V)", "y")
    figure.draw(
        figure.signal(range(1, len(values) + 1), values).lines()
    )
    return Text.from_ansi(figure.build().string())


class DeviceUpdate(Message):
    def __init__(
        self,
        address: str,
        name: str,
        voltage: float | None,
        rssi: int,
        received_at: str,
    ) -> None:
        super().__init__()
        self.address = address
        self.name = name
        self.voltage = voltage
        self.rssi = rssi
        self.received_at = received_at


class DevicePanel(Static):
    def __init__(self, address: str, *, panel_id: str) -> None:
        super().__init__(id=panel_id)
        self.address = address
        self.device_name = "Waiting for advertisement"
        self.voltage: float | None = None
        self.rssi: int | None = None
        self.received_at: str | None = None
        self.voltage_history: deque[float] = deque(maxlen=VOLTAGE_HISTORY_SIZE)

    def render(self) -> Text:
        text = Text()
        text.append("Device Address\n", style="bold cyan")
        text.append(f"{self.address}\n\n")
        text.append("Name\n", style="bold cyan")
        text.append(f"{self.device_name}\n\n")
        text.append("Voltage\n", style="bold cyan")
        if self.voltage is not None:
            voltage = f"{self.voltage:.2f} V"
        elif self.received_at:
            voltage = "Unavailable (unrecognized name)"
        else:
            voltage = "Waiting for data"
        text.append(f"{voltage}\n\n")
        text.append("Voltage history\n", style="bold cyan")
        if self.voltage_history:
            history = list(self.voltage_history)
            text.append(
                render_voltage_chart(
                    history,
                    width=max(12, self.size.width - 6),
                    height=max(6, min(9, self.size.height - 15)),
                )
            )
            text.append("\n\n")
        else:
            text.append("Waiting for voltage readings\n\n", style="dim")
        text.append("Signal\n", style="bold cyan")
        signal = f"{self.rssi} dBm" if self.rssi is not None else "Waiting for data"
        text.append(f"{signal}\n\n")
        text.append("Last update\n", style="bold cyan")
        text.append(self.received_at or "—")
        return text

    def update_telemetry(self, message: DeviceUpdate) -> None:
        self.device_name = message.name
        self.voltage = message.voltage
        self.rssi = message.rssi
        self.received_at = message.received_at
        if message.voltage is not None:
            self.voltage_history.append(message.voltage)
        self.refresh()


class LancolApp(App[None]):
    TITLE = "Lancol BTLE Monitor"
    BINDINGS = [
        ("t", "toggle_view", "Toggle table/panels"),
        ("q", "quit", "Quit"),
    ]
    CSS = """
    Grid {
        grid-size: 2 1;
        grid-columns: 1fr 1fr;
        height: 1fr;
        padding: 1;
    }

    DevicePanel {
        border: round $accent;
        padding: 1 2;
        height: 1fr;
    }

    #status {
        height: 1;
        padding: 0 1;
    }

    #readings-table {
        height: 1fr;
        margin: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid(id="panel-view"):
            yield DevicePanel(DEVICE_ADDRESSES[0], panel_id="device-one")
            yield DevicePanel(DEVICE_ADDRESSES[1], panel_id="device-two")
        yield DataTable(id="readings-table")
        yield Static("Starting Bluetooth scan…", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#readings-table", DataTable)
        table.add_columns("Time", "Device", "Voltage", "Signal")
        table.display = False
        self._table_row_ids = deque(maxlen=100)
        self._row_id = count()
        self.run_worker(self.scan_devices(), name="ble-scan", exclusive=True)

    def action_toggle_view(self) -> None:
        panels = self.query_one("#panel-view", Grid)
        table = self.query_one("#readings-table", DataTable)
        show_table = not table.display
        panels.display = not show_table
        table.display = show_table

    def on_device_update(self, message: DeviceUpdate) -> None:
        panel_id = (
            "device-one"
            if message.address.upper() == DEVICE_ADDRESSES[0]
            else "device-two"
        )
        self.query_one(f"#{panel_id}", DevicePanel).update_telemetry(message)
        table = self.query_one("#readings-table", DataTable)
        row_id = str(next(self._row_id))
        table.add_row(
            message.received_at,
            message.address,
            f"{message.voltage:.2f} V" if message.voltage is not None else "Unavailable",
            f"{message.rssi} dBm",
            key=row_id,
        )
        if len(self._table_row_ids) == self._table_row_ids.maxlen:
            table.remove_row(self._table_row_ids[0])
        self._table_row_ids.append(row_id)

    async def scan_devices(self) -> None:
        scanner = BleakScanner(self.on_advertisement)
        try:
            await scanner.start()
        except (BleakError, OSError) as error:
            self.query_one("#status", Static).update(f"Bluetooth scan failed: {error}")
            return

        self.query_one("#status", Static).update(
            "Scanning for Lancol devices — press T to toggle views, Q to quit."
        )
        try:
            await asyncio.Event().wait()
        finally:
            await scanner.stop()

    def on_advertisement(
        self, device: BLEDevice, data: AdvertisementData
    ) -> None:
        address = device.address.upper()
        if address not in DEVICE_ADDRESSES:
            return
        if MANUFACTURER_ID not in data.manufacturer_data:
            return

        name = data.local_name or device.name or "Lancol"
        self.post_message(
            DeviceUpdate(
                address=address,
                name=name,
                voltage=decode_voltage(name),
                rssi=data.rssi,
                received_at=datetime.now().astimezone().strftime("%H:%M:%S"),
            )
        )


if __name__ == "__main__":
    LancolApp().run()
