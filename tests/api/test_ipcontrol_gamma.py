"""Tests for the authenticated, read-only gamma-mode getter."""

import asyncio
import json

import pytest

from .test_ipcontrol_channel import _FakeHass, ipcontrol


def _client():
    ipcontrol._HOST_LOCKS.clear()
    return ipcontrol.SamsungIPControl(_FakeHass(), "192.0.2.1", token="test-token")


@pytest.mark.parametrize("value", ["2.2", "BT.1886", "ST.2084", "HLG", "FutureMode"])
async def test_gamma_getter_preserves_raw_value_and_sends_no_setting(value):
    client = _client()
    sent = {}

    def fake_post(payload, timeout):
        sent.update(json.loads(payload))
        return json.dumps({"result": {"gammaMode": value}})

    client._sync_post = fake_post

    assert await client.async_get_gamma_mode() == value
    assert sent["method"] == "gammaModeControl"
    assert sent["params"] == {"AccessToken": "test-token"}
    assert sent["jsonrpc"] == "2.0"


@pytest.mark.parametrize("value", [None, "", "  ", 2.2, False, [], {}])
async def test_invalid_gamma_value_is_not_a_successful_read(value):
    client = _client()
    client._sync_post = lambda *_: json.dumps({"result": {"gammaMode": value}})
    with pytest.raises(ipcontrol.SamsungIPControlError):
        await client.async_get_gamma_mode()


@pytest.mark.parametrize(
    ("code", "error_type"),
    [
        (-32601, ipcontrol.SamsungIPControlUnsupportedError),
        (-32010, ipcontrol.SamsungIPControlAuthError),
        (-32700, ipcontrol.SamsungIPControlAuthError),
        (-32002, ipcontrol.SamsungIPControlModeLockedError),
    ],
)
async def test_gamma_getter_preserves_existing_error_handling(code, error_type):
    client = _client()
    client._sync_post = lambda *_: json.dumps({"error": {"code": code}})
    with pytest.raises(error_type):
        await client.async_get_gamma_mode()


async def test_gamma_getter_requires_existing_token():
    client = _client()
    client.set_token(None)
    with pytest.raises(ipcontrol.SamsungIPControlAuthError):
        await client.async_get_gamma_mode()


async def test_gamma_getter_shares_host_serialization_with_other_clients():
    active = 0
    peak = 0

    class Executor:
        async def async_add_executor_job(self, func, *args):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            try:
                return func(*args)
            finally:
                active -= 1

    ipcontrol._HOST_LOCKS.clear()
    first = ipcontrol.SamsungIPControl(Executor(), "192.0.2.1", token="test-token")
    second = ipcontrol.SamsungIPControl(Executor(), "192.0.2.1", token="test-token")
    first._sync_post = lambda *_: json.dumps({"result": {"gammaMode": "2.2"}})
    second._sync_post = lambda *_: json.dumps({"result": {"power": "powerOn"}})

    assert await asyncio.gather(
        first.async_get_gamma_mode(), second.async_get_power_state()
    ) == ["2.2", "powerOn"]
    assert peak == 1
