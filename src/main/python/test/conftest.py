# SPDX-License-Identifier: GPL-2.0-or-later
"""Pytest configuration - runs before any tests."""

import sys
from types import ModuleType


class MockHidDevice:
    """Mock HID device that does nothing."""

    def open_path(self, path):
        pass

    def close(self):
        pass

    def write(self, data):
        return len(data)

    def read(self, size, timeout=None):
        return []


class MockHidModule(ModuleType):
    """Mock hid module that doesn't touch real hardware.

    This is a real module object so that tests can override
    attributes like `enumerate` and `device`.
    """

    def __init__(self, name='hid'):
        super().__init__(name)
        self._enumerate_result = []

    def enumerate(self):
        """Return empty list by default - no real hardware."""
        return self._enumerate_result

    def device(self):
        """Return a mock device."""
        return MockHidDevice()


# Mock hid and hidraw modules BEFORE any imports can use them
# hidproxy.py imports hidraw on Linux, hid on other platforms
# This prevents tests from connecting to real keyboards
#
# IMPORTANT: Use the SAME mock instance for both hid and hidraw.
# This ensures that when test_gui.py does `hid.enumerate = mock_enumerate`,
# it affects the same object that hidproxy.hid references (which is hidraw on Linux).
_mock_hid = MockHidModule('hid')

# Both 'hid' and 'hidraw' point to the same mock instance
for module_name in ('hid', 'hidraw'):
    if module_name not in sys.modules:
        sys.modules[module_name] = _mock_hid

# Also patch hidproxy if it's already been imported
if 'hidproxy' in sys.modules:
    import hidproxy
    hidproxy.hid = _mock_hid


def pytest_configure(config):
    """Pytest hook - runs before test collection.

    Ensure hidproxy uses our mock even if imported during collection.
    """
    # Force re-patch after any imports during collection
    if 'hidproxy' in sys.modules:
        import hidproxy
        hidproxy.hid = _mock_hid


def pytest_sessionstart(session):
    """Pytest hook - runs at session start.

    Final chance to ensure all HID access is mocked.
    """
    if 'hidproxy' in sys.modules:
        import hidproxy
        hidproxy.hid = _mock_hid


