"""Use Home Assistant's shared Bluetooth infrastructure, including discovery."""

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .ble.transport import BrpcConnection, ConnectionLost


def create_connection(hass: HomeAssistant, address: str, *, disconnected=None) -> BrpcConnection:
    """Resolve a fresh connectable device for every connection attempt."""

    async def connect(callback):
        device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
        if device is None:
            raise ConnectionLost("BORA is not within range of a connectable Bluetooth adapter")
        return await establish_connection(
            BleakClientWithServiceCache,
            device,
            "BORA",
            disconnected_callback=callback,
            ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                hass, address, connectable=True
            ),
            max_attempts=2,
            timeout=20,
        )

    return BrpcConnection(connect, disconnected=disconnected)
