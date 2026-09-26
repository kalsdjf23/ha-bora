"""Run real HA config flows with appliance I/O mocked at one boundary."""

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from homeassistant import config_entries, setup
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bora.ble.transport import SERVICE_UUID, ConnectionLost, PairingRequired
from custom_components.bora.ble.wire import ProtocolError
from custom_components.bora.const import CONF_ENABLE_CONTROLS, CONF_ENABLE_COOKING, DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"
OTHER_ADDRESS = "11:22:33:44:55:66"


def advertisement(address=ADDRESS, name="X PURE", service_uuids=()):
    """Construct discovery data without a scanner or physical adapter."""
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-50,
        manufacturer_data={},
        service_data={},
        service_uuids=list(service_uuids),
        source="test_adapter",
        device=BLEDevice(address, name, {}),
        advertisement=None,
        connectable=True,
        time=0,
        tx_power=None,
    )


def config_entry(hass, *, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        title="BORA kitchen",
        data={"address": ADDRESS},
        options=options or {CONF_ENABLE_CONTROLS: False, CONF_ENABLE_COOKING: False},
    )
    entry.add_to_hass(hass)
    return entry


async def start_reauth(hass, entry, *, address=ADDRESS):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data={"address": address},
    )


@pytest.fixture(autouse=True)
def custom_components(enable_custom_integrations):
    pass


@pytest.fixture(autouse=True)
def mocks(mock_bluetooth):
    original_dependencies = setup.async_process_deps_reqs

    async def dependencies(hass, config, integration):
        # Exercise HA's real flow manager without starting a physical scanner.
        if integration.domain == DOMAIN:
            return
        return await original_dependencies(hass, config, integration)

    with (
        patch("homeassistant.config_entries.async_process_deps_reqs", side_effect=dependencies),
        patch(
            "custom_components.bora.config_flow.bluetooth.async_discovered_service_info",
            return_value=[],
        ),
        patch(
            "custom_components.bora.config_flow.async_probe",
            new_callable=AsyncMock,
            return_value={"product_name": "X PURE"},
        ) as probe,
        patch("custom_components.bora.async_setup_entry", return_value=True),
    ):
        yield probe


async def test_setup_requires_pair_confirmation_and_defaults_to_monitoring(hass, mocks):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"address": ADDRESS})
    assert result["step_id"] == "pair"
    mocks.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BORA X PURE"
    assert result["data"] == {"address": ADDRESS}
    assert result["options"] == {CONF_ENABLE_CONTROLS: False, CONF_ENABLE_COOKING: False}
    assert result["result"].unique_id == ADDRESS
    mocks.assert_awaited_once_with(hass, ADDRESS)
    await hass.async_block_till_done()


async def test_duplicate_does_not_pair_again(hass, mocks):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={"address": ADDRESS})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={"address": ADDRESS.lower()}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mocks.assert_not_awaited()


async def test_pair_failure_keeps_form_open(hass, mocks):
    mocks.side_effect = PairingRequired()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={"address": ADDRESS}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "pairing_failed"}
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize(
    ("name", "services"),
    [("X PURE", []), ("BORA test", [SERVICE_UUID.upper()])],
)
async def test_discovery_requires_confirmation_before_pairing(hass, mocks, name, services):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=advertisement(ADDRESS.lower(), name, services),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["description_placeholders"] == {"name": name}
    assert not hass.config_entries.async_entries(DOMAIN)
    mocks.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ADDRESS
    assert result["data"] == {"address": ADDRESS}
    assert result["options"] == {CONF_ENABLE_CONTROLS: False, CONF_ENABLE_COOKING: False}
    mocks.assert_awaited_once_with(hass, ADDRESS)
    await hass.async_block_till_done()


async def test_discovery_rejects_unrelated_advertisement_without_pairing(hass, mocks):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=advertisement(name="Other appliance", service_uuids=["unrelated-service"]),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_device"
    mocks.assert_not_awaited()


async def test_discovery_of_existing_device_does_not_pair(hass, mocks):
    config_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=advertisement(ADDRESS.lower()),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mocks.assert_not_awaited()


async def test_user_choices_only_include_supported_unconfigured_devices(hass, mocks):
    config_entry(hass)
    with patch(
        "custom_components.bora.config_flow.bluetooth.async_discovered_service_info",
        return_value=[
            advertisement(ADDRESS),
            advertisement(OTHER_ADDRESS),
            advertisement("22:33:44:55:66:77", name="Other appliance"),
        ],
    ) as discovered:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    discovered.assert_called_once_with(hass, connectable=True)
    assert result["data_schema"]({"address": OTHER_ADDRESS}) == {"address": OTHER_ADDRESS}
    for rejected in (ADDRESS, "22:33:44:55:66:77"):
        with pytest.raises(vol.Invalid):
            result["data_schema"]({"address": rejected})
    mocks.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": OTHER_ADDRESS}
    )
    assert result["step_id"] == "pair"
    mocks.assert_not_awaited()


async def test_blank_manual_address_remains_on_form_without_pairing(hass, mocks):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"address": "   "},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"address": "invalid_address"}
    mocks.assert_not_awaited()


@pytest.mark.parametrize("address", [ADDRESS, ADDRESS.lower()])
async def test_reauth_confirmation_success_preserves_entry_and_reloads(hass, mocks, address):
    options = {CONF_ENABLE_CONTROLS: True, CONF_ENABLE_COOKING: False}
    entry = config_entry(hass, options=options)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload_entry:
        result = await start_reauth(hass, entry, address=address)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert result["description_placeholders"]["name"] == entry.title
        mocks.assert_not_awaited()
        reload_entry.assert_not_awaited()

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        reload_entry.assert_awaited_once_with(entry.entry_id)

    mocks.assert_awaited_once_with(hass, ADDRESS)
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.unique_id == ADDRESS
    assert entry.data == {"address": ADDRESS}
    assert entry.title == "BORA kitchen"
    assert entry.options == options


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (PairingRequired(), "pairing_failed"),
        (ConnectionLost(), "cannot_connect"),
        (BleakError("adapter failed"), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (ProtocolError("invalid descriptor"), "cannot_connect"),
    ],
)
async def test_reauth_failure_keeps_entry_and_allows_explicit_retry(hass, mocks, failure, error):
    entry = config_entry(hass)
    mocks.side_effect = [failure, {"product_name": "X PURE"}]
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload_entry:
        result = await start_reauth(hass, entry)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert result["errors"] == {"base": error}
        assert hass.config_entries.async_entries(DOMAIN) == [entry]
        assert entry.data == {"address": ADDRESS}
        assert entry.options == {CONF_ENABLE_CONTROLS: False, CONF_ENABLE_COOKING: False}
        assert mocks.await_count == 1
        reload_entry.assert_not_awaited()

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert mocks.await_count == 2
        reload_entry.assert_awaited_once_with(entry.entry_id)


async def test_reauth_rejects_different_address_before_pairing(hass, mocks):
    entry = config_entry(hass)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload_entry:
        result = await start_reauth(hass, entry, address=OTHER_ADDRESS)
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unique_id_mismatch"
        reload_entry.assert_not_awaited()
    mocks.assert_not_awaited()
    assert entry.unique_id == ADDRESS
    assert entry.data == {"address": ADDRESS}


@pytest.mark.parametrize(
    ("controls", "cooking"), [(False, False), (False, True), (True, False), (True, True)]
)
async def test_options_gate_cooking_and_reload_changed_entry(hass, mocks, controls, cooking):
    initial = {CONF_ENABLE_CONTROLS: not controls, CONF_ENABLE_COOKING: not controls}
    entry = config_entry(hass, options=initial)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload_entry:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["data_schema"]({}) == initial
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_ENABLE_CONTROLS: controls, CONF_ENABLE_COOKING: cooking},
        )
        await hass.async_block_till_done()
        expected = {CONF_ENABLE_CONTROLS: controls, CONF_ENABLE_COOKING: controls and cooking}
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == expected
        assert entry.options == expected
        reload_entry.assert_awaited_once_with(entry.entry_id)
    mocks.assert_not_awaited()


async def test_default_options_do_not_enable_controls_or_reload_unchanged_entry(hass, mocks):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={"address": ADDRESS})
    entry.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload_entry:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        defaults = result["data_schema"]({})
        assert defaults == {CONF_ENABLE_CONTROLS: False, CONF_ENABLE_COOKING: False}
        reload_entry.assert_not_awaited()
        # Saving the explicit defaults changes a legacy entry's empty options once.
        result = await hass.config_entries.options.async_configure(result["flow_id"], defaults)
        await hass.async_block_till_done()
        reload_entry.assert_awaited_once_with(entry.entry_id)
        reload_entry.reset_mock()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(result["flow_id"], defaults)
        await hass.async_block_till_done()
        reload_entry.assert_not_awaited()
    assert entry.options == defaults
    mocks.assert_not_awaited()
