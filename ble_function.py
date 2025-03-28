from micropython import const
from machine import Pin
import bluetooth
from ble_advertising import advertising_payload

LED_PIN = 2
LED_ON = 1
LED_OFF = 0
try:
    from machine import TouchPad
except ImportError:
    # ESP32-C3 is different
    LED_PIN = 8
    LED_ON = 0
    LED_OFF = 1

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_INDICATE_DONE = const(20)

FLAG_READ = const(0x0002)
FLAG_NOTIFY = const(0x0010)
FLAG_INDICATE = const(0x0020)


# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_COMPUTER = const(128)

led_pin = Pin(LED_PIN, Pin.OUT, value=LED_OFF, drive=Pin.DRIVE_1)

class BLEFunction:
    def __init__(self, name, ble_service):
        self._ble = bluetooth.BLE()

        self._ble.active(True)
        self._ble.irq(self._irq)
        ((self._char_handle,),) = self._ble.gatts_register_services((ble_service,))
        self._connections = set()
        self._payload = advertising_payload(
            name=name, services=[ble_service[0]], appearance=_ADV_APPEARANCE_GENERIC_COMPUTER
        )
        self._advertise()

    def _irq(self, event, data):
        # Track connections so we can send notifications.
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            led_pin.value(LED_ON)
            print("connected")
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.remove(conn_handle)
            # Start advertising again to allow a new connection.
            self._advertise()
            led_pin.value(LED_OFF)
            print("disconnected")
        elif event == _IRQ_GATTS_INDICATE_DONE:
            conn_handle, value_handle, status = data

    def set_data(self, data, notify=False, indicate=False):
        # Data is sint16 and sending in centiV, centiA
        self._ble.gatts_write(self._char_handle, data)
        if notify or indicate:
            for conn_handle in self._connections:
                if notify:
                    # Notify connected centrals.
                    self._ble.gatts_notify(conn_handle, self._char_handle)
                if indicate:
                    # Indicate connected centrals.
                    self._ble.gatts_indicate(conn_handle, self._char_handle)
   
    def _advertise(self, interval_us=500000):
        self._ble.gap_advertise(interval_us, adv_data=self._payload)
