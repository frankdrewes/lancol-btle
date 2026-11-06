import asyncio
from datetime import datetime

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.message import Message
from textual.widgets import Footer, Header, Static


MANUFACTURER_ID = 58428
DEVICE_ADDRESSES = (
    "3C:E4:B0:A4:DF:89",
    "3C:E4:B0:A4:DF:F6",
)


def decode_voltage(name: str | None) -> float | None:
    if not name:
        return None

    try:
        return float(name.split()[-1].rstrip("V"))
    except (IndexError, ValueError):
        return None


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
        self.name = "Waiting for advertisement"
        self.voltage: float | None = None
        self.rssi: int | None = None
        self.received_at: str | None = None

    def render(self) -> Text:
        text = Text()
        text.append("Device Address\n", style="bold cyan")
        text.append(f"{self.address}\n\n")
        text.append("Name\n", style="bold cyan")
        text.append(f"{self.name}\n\n")
        text.append("Voltage\n", style="bold cyan")
        if self.voltage is not None:
            voltage = f"{self.voltage:.2f} V"
        elif self.received_at:
            voltage = "Unavailable (unrecognized name)"
        else:
            voltage = "Waiting for data"
        text.append(f"{voltage}\n\n")
        text.append("Signal\n", style="bold cyan")
        signal = f"{self.rssi} dBm" if self.rssi is not None else "Waiting for data"
        text.append(f"{signal}\n\n")
        text.append("Last update\n", style="bold cyan")
        text.append(self.received_at or "—")
        return text

    def update_telemetry(self, message: DeviceUpdate) -> None:
        self.name = message.name
        self.voltage = message.voltage
        self.rssi = message.rssi
        self.received_at = message.received_at
        self.refresh()


class LancolApp(App[None]):
    TITLE = "Lancol BTLE Monitor"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit", False),
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
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid():
            yield DevicePanel(DEVICE_ADDRESSES[0], panel_id="device-one")
            yield DevicePanel(DEVICE_ADDRESSES[1], panel_id="device-two")
        yield Static("Starting Bluetooth scan…", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self.scan_devices(), name="ble-scan", exclusive=True)

    def on_device_update(self, message: DeviceUpdate) -> None:
        panel_id = (
            "device-one"
            if message.address.upper() == DEVICE_ADDRESSES[0]
            else "device-two"
        )
        self.query_one(f"#{panel_id}", DevicePanel).update_telemetry(message)

    async def scan_devices(self) -> None:
        scanner = BleakScanner(self.on_advertisement)
        try:
            await scanner.start()
        except (BleakError, OSError) as error:
            self.query_one("#status", Static).update(f"Bluetooth scan failed: {error}")
            return

        self.query_one("#status", Static).update(
            "Scanning for the two Lancol devices — press Q to quit."
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
