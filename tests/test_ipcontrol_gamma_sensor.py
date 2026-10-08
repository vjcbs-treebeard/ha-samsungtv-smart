"""Regression tests for raw gamma-mode coordinator data and entity metadata."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from homeassistant.helpers.translation import async_get_translations

from .test_ipcontrol_channel_coordinator import HOST
from .test_ipcontrol_channel_coordinator import _client as _channel_client
from .test_ipcontrol_channel_coordinator import _entry, _update

# isort: split

from custom_components.samsungtv_smart.api.ipcontrol import (  # noqa: E402
    SamsungIPControlAuthError,
    SamsungIPControlError,
    SamsungIPControlModeLockedError,
    SamsungIPControlTransportError,
    SamsungIPControlUnsupportedError,
)
from custom_components.samsungtv_smart.sensor import (  # noqa: E402
    IP_CONTROL_STATE_SENSORS,
    IPControlStateCoordinator,
    IPControlStateSensor,
)


def _client(**kwargs):
    client = _channel_client(**kwargs)
    client.async_get_gamma_mode.side_effect = None
    return client


async def test_gamma_mode_uses_shared_client_and_raw_sensor_value(hass):
    entry = _entry(hass)
    coordinator = IPControlStateCoordinator(hass, entry, HOST)
    client = _client(source="HDMI1")
    client.async_get_gamma_mode.return_value = "2.2"

    data = await _update(coordinator, client)

    assert data["gamma"] == {"gammaMode": "2.2"}
    client.async_get_gamma_mode.assert_awaited_once_with()
    description = next(d for d in IP_CONTROL_STATE_SENSORS if d.key == "gammaMode")
    sensor = IPControlStateSensor(coordinator, entry, description, "TV", "stable-tv")
    sensor.hass = hass
    coordinator.async_set_updated_data(data)
    assert sensor.native_value == "2.2"
    assert sensor.unique_id == "stable-tv_ip_control_gammaMode"
    assert sensor.translation_key == "gamma_mode"
    assert sensor.has_entity_name
    with patch(
        "custom_components.samsungtv_smart.sensor._ip_control_active", return_value=True
    ):
        assert sensor.available


@pytest.mark.parametrize(
    "error_type",
    [
        SamsungIPControlUnsupportedError,
        SamsungIPControlTransportError,
        SamsungIPControlModeLockedError,
        SamsungIPControlError,
    ],
)
async def test_optional_gamma_failure_invalidates_only_gamma(hass, error_type):
    entry = _entry(hass)
    coordinator = IPControlStateCoordinator(hass, entry, HOST)
    client = _client(source="HDMI1")
    client.async_get_gamma_mode.return_value = "2.2"
    coordinator.async_set_updated_data(await _update(coordinator, client))
    description = next(d for d in IP_CONTROL_STATE_SENSORS if d.key == "gammaMode")
    sensor = IPControlStateSensor(coordinator, entry, description, "TV", "stable-tv")
    sensor.hass = hass
    client.async_get_gamma_mode.side_effect = error_type("getter unavailable")

    data = await _update(coordinator, client)
    coordinator.async_set_updated_data(data)

    assert data["tv"]["inputSource"] == "HDMI1"
    assert sensor.native_value is None
    with patch(
        "custom_components.samsungtv_smart.sensor._ip_control_active", return_value=True
    ):
        assert not sensor.available
        other_description = next(
            d for d in IP_CONTROL_STATE_SENSORS if d.key == "inputSource"
        )
        other = IPControlStateSensor(
            coordinator, entry, other_description, "TV", "stable-tv"
        )
        other.hass = hass
        assert other.available
        assert other.native_value == "HDMI1"

    client.async_get_gamma_mode.side_effect = None
    client.async_get_gamma_mode.return_value = "ST.2084"
    coordinator.async_set_updated_data(await _update(coordinator, client))
    assert sensor.native_value == "ST.2084"


async def test_tolerated_primary_read_failure_clears_gamma_without_mutating_old_data(
    hass,
):
    entry = _entry(hass)
    coordinator = IPControlStateCoordinator(hass, entry, HOST)
    client = _client(source="HDMI1")
    client.async_get_gamma_mode.return_value = "2.2"
    previous = await _update(coordinator, client)
    coordinator.async_set_updated_data(previous)
    client.async_get_tv_states.side_effect = SamsungIPControlModeLockedError("refused")

    data = await _update(coordinator, client)

    assert data["tv"] == previous["tv"]
    assert data["gamma"] == {}
    assert previous["gamma"] == {"gammaMode": "2.2"}


@pytest.mark.parametrize("state", ["off", "art", "transport"])
async def test_gamma_is_not_polled_when_picture_data_is_unavailable(hass, state):
    entry = _entry(hass)
    coordinator = IPControlStateCoordinator(hass, entry, HOST)
    client = _client(source="HDMI1")
    client.async_get_gamma_mode.return_value = "2.2"
    if state == "off":
        client.async_get_power_state.return_value = "powerOff"
    elif state == "art":
        client.async_get_tv_states.return_value["pictureMode"] = "Ambient"
    else:
        client.async_get_power_state.side_effect = SamsungIPControlTransportError(
            "offline"
        )

    data = await _update(coordinator, client)
    coordinator.async_set_updated_data(data)
    description = next(d for d in IP_CONTROL_STATE_SENSORS if d.key == "gammaMode")
    sensor = IPControlStateSensor(coordinator, entry, description, "TV", "stable-tv")
    sensor.hass = hass

    client.async_get_gamma_mode.assert_not_awaited()
    assert sensor.native_value is None
    with patch(
        "custom_components.samsungtv_smart.sensor._ip_control_active", return_value=True
    ):
        assert not sensor.available


async def test_gamma_auth_failure_uses_existing_notification_and_unavailability(hass):
    entry = _entry(hass)
    coordinator = IPControlStateCoordinator(hass, entry, HOST)
    client = _client(source="HDMI1")
    client.async_get_gamma_mode.return_value = "2.2"
    coordinator.async_set_updated_data(await _update(coordinator, client))
    client.async_get_gamma_mode.side_effect = SamsungIPControlAuthError("expired")
    description = next(d for d in IP_CONTROL_STATE_SENSORS if d.key == "gammaMode")
    sensor = IPControlStateSensor(coordinator, entry, description, "TV", "stable-tv")
    sensor.hass = hass

    with (
        patch.object(coordinator, "_get_ip_control", return_value=client),
        patch(
            "custom_components.samsungtv_smart.sensor.notify_token_problem"
        ) as notify,
        patch("custom_components.samsungtv_smart.sensor.clear_token_problem") as clear,
    ):
        await coordinator.async_refresh()

    notify.assert_called_once()
    clear.assert_not_called()
    assert not coordinator.last_update_success
    with patch(
        "custom_components.samsungtv_smart.sensor._ip_control_active", return_value=True
    ):
        assert not sensor.available


async def test_disabled_ip_control_does_not_expose_cached_gamma(hass):
    entry = _entry(hass)
    coordinator = IPControlStateCoordinator(hass, entry, HOST)
    coordinator.async_set_updated_data({"gamma": {"gammaMode": "2.2"}})
    description = next(d for d in IP_CONTROL_STATE_SENSORS if d.key == "gammaMode")
    sensor = IPControlStateSensor(coordinator, entry, description, "TV", "stable-tv")
    sensor.hass = hass
    with patch(
        "custom_components.samsungtv_smart.sensor._ip_control_active",
        return_value=False,
    ):
        assert coordinator._get_ip_control() is None
        assert not sensor.available


@pytest.mark.parametrize("language", ["en", "fr", "it", "es", "hu", "pt-BR"])
async def test_gamma_entity_name_is_translated(hass, language):
    translations = await async_get_translations(
        hass, language, "entity", {"samsungtv_smart"}
    )
    expected_name = translations[
        "component.samsungtv_smart.entity.sensor.gamma_mode.name"
    ]
    entry = _entry(hass)
    coordinator = IPControlStateCoordinator(hass, entry, HOST)
    description = next(d for d in IP_CONTROL_STATE_SENSORS if d.key == "gammaMode")
    sensor = IPControlStateSensor(coordinator, entry, description, "TV", "stable-tv")
    sensor.platform = SimpleNamespace(
        domain="sensor",
        platform_name="samsungtv_smart",
        component_translations={},
        platform_translations=translations,
    )
    assert sensor.name == expected_name
    assert sensor.device_info["identifiers"] == {("samsungtv_smart", "stable-tv")}


async def test_gamma_poll_client_reuses_and_refreshes_entry_token(hass):
    from custom_components.samsungtv_smart.const import CONF_IP_CONTROL_TOKEN

    entry = _entry(hass)
    hass.config_entries.async_update_entry(
        entry, data={CONF_IP_CONTROL_TOKEN: "first-test-token"}
    )
    coordinator = IPControlStateCoordinator(hass, entry, HOST)
    with patch(
        "custom_components.samsungtv_smart.sensor._ip_control_active", return_value=True
    ):
        first = coordinator._get_ip_control()
        assert first is not None
        assert first.token == "first-test-token"
        assert coordinator._get_ip_control() is first
        hass.config_entries.async_update_entry(
            entry, data={CONF_IP_CONTROL_TOKEN: "second-test-token"}
        )
        second = coordinator._get_ip_control()
        assert second is not None
        assert second.token == "second-test-token"
