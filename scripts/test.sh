#!/usr/bin/env bash
# Run every package's test suite. No hardware, no network.
# The ha-haismart suite SKIPS ITSELF unless Home Assistant and a matching test package are
# installed, so a green run here does not prove it ran. CI pins both per Home Assistant version and
# fails the job if that suite does not execute every test; locally, install them if you are touching
# the integration - `pytest-homeassistant` for 2026.11+, or the older
# `pytest-homeassistant-custom-component` for 2026.10 and earlier.
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
py="${PYTHON:-python3}"
fail=0
# Packaging/provenance checks are stdlib unittest on purpose: they must not need the Home
# Assistant pytest plugin, whose autouse fixtures are incompatible with plain sync tests.
echo "=== packaging (repo root) ==="
( cd "$root" && "$py" -m unittest discover -s tests -v ) || fail=1
echo
for pkg in haismart-hrdp haismart-extractor ha-haismart; do
  echo "=== $pkg ==="
  if [ "$pkg" = ha-haismart ] && [ -n "${HA_JUNIT:-}" ]; then
    # CI parses this with scripts/check-ha-suite-ran.py; pytest alone exits 0 on an empty suite.
    ( cd "$root/packages/$pkg" && \
      "$py" -m pytest -q -p no:cacheprovider --junitxml="$HA_JUNIT" ) || fail=1
  else
    ( cd "$root/packages/$pkg" && "$py" -m pytest -q -p no:cacheprovider ) || fail=1
  fi
  echo
done
# custom_components/ is generated from packages/ and committed for HACS. The suites above import
# the packages/ copy, so a stale or hand-edited generated tree passes them all. Check it here too,
# rather than letting CI be the first thing that notices.
echo "=== HACS build in sync ==="
"$root/scripts/check-hacs-build.sh" || fail=1

exit $fail
