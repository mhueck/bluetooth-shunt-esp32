# bluetooth-shunt-esp32
MicroPython code for a BLE server that sends out shunt and battery data to a connected client.

It measures the voltage and shunt current twice per second and sends out the information through bluetooth.
In addition it keeps track of the watt-hour usage in the last hour and the last 24 hours.
This information is stored to flash every 5 minutes to not loose track of the historic data in case of power outage or watchdog triggered reset.
The watch dog triggers after 8 seconds but is fed with every read.

You can configure the capacity of the battery in the code - this will be used as the starting capacity when it is initially launched and ensures that the capacity does not grow higher than this value (e.g. in case of continuous trickle charging).

You should also check out the configured shunt resistor value.
I am using a 0.01 ohm resistor in parallel to the built in 0.1 ohm of the INA3221 board, resulting in 0.00909 ohm (1/ (1/R1 + 1/R2)) ohm.

The shunt voltage of the INA3221 should not exceed 160 mV. My resistor is good for I = U / R = 0.16 / 0.00909 = 17.6 A. Or for my battery with nominal voltage of 12.8 V about 225 watts. The resistor will consume about 3W at the maximum power.

Choose your resistor according to the maximum power you need to support. Lower is usually better, but the accuracy at low power will obviously suffer (but then you don't have so much heat and less noise from the resistor...).

All the data is encoded into 10 bytes and sent out within one BLE characteristic:
- 16 bit signed int for the voltage times 100 (1234 = 12.34V)
- 16 bit signed int for the current times 100 (423 = 4.23A)
- 16 bit signed int for the remaining capacity in AH times 100 (9934 = 99.34 Ah)
- 16 bit signed int for the power consumption of the last 1h in Wh times 10 (5670 = 567.0 Wh)
- 16 bit signed int for the power consumption of the last 24h in Wh (5670 = 5670 Wh)

Negative current and power values mean that the battery is getting drained, positive values mean that the battery is being charged. If your setup shows the opposite then swap the connection to the INA3221 channel.

There is also a rudimentary Android project which shows all of these values and some derived ones on your phone/tablet.

