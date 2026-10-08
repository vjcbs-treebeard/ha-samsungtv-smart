# Raw gamma mode

This fork adds a read-only **Gamma mode** diagnostic sensor, normally named
`sensor.<tv_name>_gamma_mode`. It reads `gammaModeControl` with only the existing
IP Control access token and publishes the exact non-empty string returned by the
TV (for example, `2.2`). It does not change gamma or any picture setting.

The sensor shares the integration's IP Control state coordinator, configured
poll interval, entry token and per-host request serialization. IP Control must
already be paired and enabled. No additional token or pairing is needed.

A `2.2` response has been observed on a Samsung QE65S95FATXXN in Filmmaker Mode
on HDMI1. SDR/HDR transitions have **not** been verified. This is a raw picture
field, **not a universally confirmed HDR detector**; no HDR binary sensor or
classification is provided. Other firmware may expose different strings or not
support the getter at all.

The sensor is unavailable while the TV is off, in Art Mode, IP Control is
disabled, or no current gamma reading is available. Unsupported, malformed and
transient gamma responses do not invalidate unrelated TV sensors, and a failed
read does not carry a previous gamma value forward as a fresh reading. The
getter is retried on later normal-viewing polls because a method-not-found
response can be temporary. Token rejection uses the existing IP Control
notification and recovery path.

## Installing this fork

Add `https://github.com/vjcbs-treebeard/ha-samsungtv-smart` as a HACS custom
repository, category **Integration**, and download the **master** branch. This
change is on the default branch, not a new GitHub release; the upstream manifest
version remains `8.11.3`. Do not select the upstream `8.11.3` tag if you want this
addition. The fork keeps the `samsungtv_smart` domain, so it replaces rather than
runs alongside another integration using that domain. The general installation
instructions in the main README otherwise apply; their upstream release links
do not contain this fork's addition.

Manual installation: copy this branch's `custom_components/samsungtv_smart`
directory into Home Assistant's `config/custom_components/`, then restart Home
Assistant. Installing or restarting a live system is not part of this repository
change.

## Development

Use `direnv allow` (or `nix develop`) for the pinned Python 3.13 development shell.
Create a repository-local test environment from that shell:

```sh
uv venv --python "$(command -v python3)"
uv pip install -r requirements_test.txt "pycares<5"
.venv/bin/python -m pytest \
  tests/api/test_ipcontrol_gamma.py \
  tests/test_ipcontrol_gamma_sensor.py \
  tests/test_ipcontrol_channel_coordinator.py \
  --disable-socket --allow-unix-socket --timeout=15 \
  -o asyncio_default_fixture_loop_scope=function
black --check custom_components
isort --check-only custom_components
flake8 custom_components
```

The `pycares<5` constraint works around an incompatible transitive dependency in
the existing Home Assistant 2025.6 test environment. Tests use synthetic responses
and mocked transport; they do not pair with or contact a television.
