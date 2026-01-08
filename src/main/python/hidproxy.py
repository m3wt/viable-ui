# SPDX-License-Identifier: GPL-2.0-or-later
import sys

if sys.platform == "emscripten":

    import vialglue
    import json

    class hiddevice:

        def open_path(self, path):
            print("opening {}...".format(path))

        def write(self, data):
            return vialglue.write_device(data)

        def read(self, length, timeout_ms=0):
            data = vialglue.read_device()
            return data

        def close(self):
            pass


    class hid:

        @staticmethod
        def enumerate():
            desc = json.loads(vialglue.get_device_desc())

            # Viable devices use usage page 0xFF61
            if desc.get("usage_page") == 0xFF61:
                desc["serial_number"] = "viable:web"
            # VIA3 devices will be detected by is_via3_device() probe

            return [desc]

        @staticmethod
        def device():
            return hiddevice()

elif sys.platform == "linux":
    # On Linux, prefer hidraw for proper usage_page/serial_number support
    try:
        import hidraw as hid
    except ImportError:
        import hid
else:
    # Use hidapi on macOS and Windows
    try:
        import hid
    except ImportError:
        import hidraw as hid

# Enable non-exclusive mode on macOS to allow multiple HID clients
if sys.platform == "darwin" and hasattr(hid, "darwin_set_open_exclusive"):
    hid.darwin_set_open_exclusive(0)
