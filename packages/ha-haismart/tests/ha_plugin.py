"""The Home Assistant pytest helpers, from whichever official package is installed.

Home Assistant 2026.11 moved this infrastructure into ``pytest-homeassistant``, published from
``home-assistant/core``; the older ``pytest-homeassistant-custom-component`` package now says it is
broken and points custom-component authors at the new one. Both expose the same helpers under
``common``, so tests import them from here and work in either test environment.
"""
from __future__ import annotations

try:  # Home Assistant 2026.11+ (official package, auto-registers its pytest plugin)
    from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
except ImportError:  # the pre-2026.11 compatibility package
    from pytest_homeassistant_custom_component.common import (  # type: ignore[no-redef]
        MockConfigEntry,
        async_fire_time_changed,
    )

__all__ = ["MockConfigEntry", "async_fire_time_changed"]
