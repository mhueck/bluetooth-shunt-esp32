# This example demonstrates a simple temperature sensor peripheral.
#
# The sensor's local value updates every second, and it will notify
# any connected central every 10 seconds.

from machine import SoftI2C, Pin, Timer, WDT
import machine
import esp32
import ujson
import time
import random
import ble_function
import bluetooth
import struct
from collections import deque


# You might want to modify these three parameters - the rest of the code is probablt good to go
MODE = "dummy" # or ina3221 or ina226
MAX_CAPACITY_AS = 105.0 * 3600.0
SHUNT_RESISTOR = 0.0091

print(f"Reset cause: {machine.reset_cause()}")

wdt = WDT(timeout=8000)

try:
    with open('/status.json') as f:
        status = ujson.loads(f.read())
except Exception as e:
    print(f"Cannot read status: {e}")
    status = {}
if "capacity_AS" not in status:
    status["capacity_AS"] = MAX_CAPACITY_AS
print(f"Status at boot: {status}")

if "wm_history_list" not in status:
    wm_history = deque([], 60)
else:
    wm_history = deque(status["wm_history_list"], 60)

if "wh_history_list" not in status:
    wh_history = deque([], 24)
else:
    wh_history = deque(status["wh_history_list"], 24)

if "minutes_passed" not in status:
    minutes_passed = 0
else:
    minutes_passed = status["minutes_passed"]

# GATT service battery
_BATTERY_UUID = bluetooth.UUID(0x180A)
_VOLTAGE_CHAR = (
    bluetooth.UUID(0X2AE1),
    ble_function.FLAG_READ | ble_function.FLAG_NOTIFY,
)

_BATTERY_SERVICE = (
    _BATTERY_UUID,
    (_VOLTAGE_CHAR,),
)
temp = ble_function.BLEFunction(
    name="mBLEBattery", ble_service=_BATTERY_SERVICE)


# main
if MODE == "ina3221":
    from ina3221 import *
    i2c = SoftI2C(scl=Pin(18), sda=Pin(19), freq=400000)
    ina3221 = INA3221(i2c, shunt_resistor=(SHUNT_RESISTOR, 0.1, 0.1))
    ina3221.update(reg=C_REG_CONFIG,
                   mask=C_AVERAGING_MASK |
                   C_VBUS_CONV_TIME_MASK |
                   C_SHUNT_CONV_TIME_MASK |
                   C_MODE_MASK,
                   value=C_AVERAGING_64_SAMPLES |
                   C_VBUS_CONV_TIME_4MS |
                   C_SHUNT_CONV_TIME_4MS |
                   C_MODE_SHUNT_AND_BUS_CONTINOUS)
    ina3221.enable_channel(1)
    print("INA3221 configured.")
elif MODE == "ina226":
    import ina226_jcf as ina226      
    i2c = SoftI2C(0, scl=Pin(9), sda=Pin(8), freq=100000)
    ina = ina226.INA226(i2c, 0x40, Rs = SHUNT_RESISTOR, voltfactor = 1)
else:
    print("running in dummy mode.")



last_reading = 0
last_save = time.ticks_ms()
watt_ms = 0.0
watt_ms_start = time.ticks_ms()
loop_start = 0
touch_values = deque([], 20)
while True:

    if MODE != "ina3221" or ina3221.is_ready:
        wdt.feed()
        loop_start = time.ticks_ms()
        if MODE == "ina3221":
            curr1 = ina3221.current(1)
            volt1 = ina3221.bus_voltage(1)
        elif MODE == "ina226":
            volt1, curr1, _ = ina.get_VIP()
        else:
            curr1 = 8.0*random.random() - 6
            volt1 = 12 + 2.0*random.random()
        if last_reading > 0:
            time_spent = time.ticks_diff(time.ticks_ms(), last_reading)
            status["capacity_AS"] = max(0, min(
                MAX_CAPACITY_AS, status["capacity_AS"] + time_spent * curr1 / 1000.0))
            watt_ms += time_spent * curr1 * volt1
            watt_ms_dur = time.ticks_diff(time.ticks_ms(), watt_ms_start)
            if watt_ms_dur >= 60 * 1000:
                wm_history.append(watt_ms/watt_ms_dur)
                watt_ms = 0.0
                watt_ms_start = time.ticks_ms()
                minutes_passed += 1
                if minutes_passed >= 60:
                    wh_history.append(sum(wm_history)/len(wm_history))
                    minutes_passed = 0

        last_reading = time.ticks_ms()

        if len(wm_history) > 0:
            wh_last_h = sum(wm_history)/len(wm_history)
        else:
            wh_last_h = 0.0
        if len(wh_history) > 0:
            wh_last_d = sum(wh_history)
        else:
            wh_last_d = 0.0
        print(f"Current: {curr1}, voltage: {volt1}, AS: {status["capacity_AS"]}, WH H: {wh_last_h}, WH D: {wh_last_d}")
        data = struct.pack("<h", int(volt1 * 100)) + struct.pack("<h", int(curr1 * 100)) + struct.pack("<h", int(
            status["capacity_AS"] * 100 / 60 / 60)) + struct.pack("<h", int(wh_last_h * 10)) + struct.pack("<h", int(wh_last_d))
        temp.set_data(data, notify=True, indicate=False)

        # write only every 5 minutes
        if time.ticks_diff(time.ticks_ms(), last_save) >= 5 * 60 * 1000:
            status["wm_history_list"] = list(wm_history)
            status["wh_history_list"] = list(wh_history)
            status["minutes_passed"] = minutes_passed
            with open('/status.json', 'w') as f:
                f.write(ujson.dumps(status))
            last_save = time.ticks_ms()
            print("Saved status to flash.")

        time.sleep_ms(max(1, 500-time.ticks_diff(time.ticks_ms(), loop_start)))
