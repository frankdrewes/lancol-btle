import sqlite3
import time
import struct
import asyncio
import os
from datetime import datetime
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table
from rich.console import Console

console = Console()

def detection_callback( device: BLEDevice, data: AdvertisementData):
        """
        Summary:
            Called when an update is received from the bluetooth device.
        Parameters:
            BLEDevice: 
                The BLE device.
            AdvertisementData: 
                The advertisement data.
        Returns:
            A dictionary with the sensor data if the device is a Lancol, otherwise None.
        """
        if not data.local_name or not data.local_name.startswith('Lancol'):
            return
        
        device_data = data.manufacturer_data.get(58428)
        if not device_data :
            return

        voltage = decode_voltage(device.name)
        
        table = Table(show_header=False,  title="Lancol BLE Sensor Telemetry")
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value", style="magenta")
        table.add_row("Name", device.name)
        table.add_row("Device Address", device.address)
        #table.add_row("Sensor ID", sensor_id)
        table.add_row("Voltage", f"{voltage:.2f} V")
        #table.add_row("Signal", f"{signal} dBm")
        console.print(table)

        return voltage
    
def decode_voltage(name):
    value = float(name.split()[-1].rstrip('V'))
    print(value)  # Output: 12.92
    return value

async def scan():
    """
    summary_ 
    Peforms scanning
    """
    print("Starting scan...")
    scanner = BleakScanner(detection_callback)
    await scanner.start()
    await asyncio.sleep(60)
    await scanner.stop()

asyncio.run(scan())