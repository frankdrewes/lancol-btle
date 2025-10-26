#!/usr/bin/env python3

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
import json
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os

console = Console()

load_dotenv()  # Loads from .env by default

# Flag to stop scanning once a value is found
found = asyncio.Event()

MQTT_SERVER = os.getenv("MQTT_SERVER")
MQTT_SERVER_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

MQTT_TOPIC =  "sensor/boat/battery/1"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
   
def detection_callback(device: BLEDevice, data: AdvertisementData):
        
    if not device.address == '3C:E4:B0:A4:DF:89':
        return

    device_data = data.manufacturer_data.get(58428) # manufacturer ID
    if not device_data :
        return
    
    voltage = decode_voltage(device.name)
    
    signal = data.rssi
    voltage = decode_voltage(device.name)
        
    table = Table(show_header=False,  title="Lancol BLE Sensor Telemetry")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")
    
    table.add_row("Name", device.name)
    table.add_row("Device Address", device.address)
    table.add_row("Voltage", f"{voltage:.2f} V")
    table.add_row("Signal", f"{signal} dBm")
    console.print(table)

    log_to_mqtt(voltage, signal)

    # Signal that we're done
    found.set()   
    
def decode_voltage(name):
    value = float(name.split()[-1].rstrip('V'))
    return value

def log_to_mqtt(voltage,signal):

    print(f"Connecting to {MQTT_SERVER}:{MQTT_SERVER_PORT}")
    print(f"writing to MQTT topic {MQTT_TOPIC}")
    
    payload = {
    "voltage": f"{voltage}",
    "signal": f"{signal}",
                }
    
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME,MQTT_PASSWORD)
    client.connect(MQTT_SERVER,int(MQTT_SERVER_PORT), 60)
    mqtt_result= client.publish(MQTT_TOPIC, json.dumps(payload))
    
    if mqtt_result.is_published:
        print(f"MQTT publish results -> {mqtt_result.rc}")
    
    print(f"MQTT publish done")

async def main():
    clear_screen()
    scanner = BleakScanner(detection_callback)
    await scanner.start()

    # Countdown from 240 seconds
    with Progress(
        TextColumn("[cyan]Scanning for Lancol #1 BLE devices..."),
        BarColumn(),
        TextColumn("[progress.remaining] {task.remaining} sec left"),
    ) as progress:
        task = progress.add_task("scan", total=240)
        for remaining in reversed(range(240)):
            if found.is_set():
                break
            await asyncio.sleep(1)
            progress.update(task, completed=240 - remaining)

    await scanner.stop()
    
    if not found.is_set() :
        print(f"Timeout without finding device")
        
asyncio.run(main())
