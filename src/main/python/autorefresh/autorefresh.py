import sys
import logging

from qtpy.QtCore import QObject, Signal


class AutorefreshLocker:

    def __init__(self, autorefresh):
        self.autorefresh = autorefresh

    def __enter__(self):
        self.autorefresh._lock()

    def __exit__(self):
        self.autorefresh._unlock()


class Autorefresh(QObject):

    instance = None
    devices_updated = Signal(object, bool)

    def __init__(self):
        super().__init__()

        self.devices = []
        self.current_device = None

        Autorefresh.instance = self

        if sys.platform == "emscripten":
            from autorefresh.autorefresh_thread_web import AutorefreshThreadWeb

            self.thread = AutorefreshThreadWeb()
        elif sys.platform.startswith("win"):
            from autorefresh.autorefresh_thread_win import AutorefreshThreadWin

            self.thread = AutorefreshThreadWin()
        else:
            from autorefresh.autorefresh_thread import AutorefreshThread

            self.thread = AutorefreshThread()

        self.thread.devices_updated.connect(self.on_devices_updated)
        self.thread.start()

    def _lock(self):
        self.thread.lock()

    def _unlock(self):
        self.thread.unlock()

    @classmethod
    def lock(cls):
        return AutorefreshLocker(cls.instance)

    def load_dummy(self, data):
        self.thread.load_dummy(data)

    def sideload_via_json(self, data):
        self.thread.sideload_via_json(data)

    def load_via_stack(self, data):
        self.thread.load_via_stack(data)

    def select_device(self, idx):
        logging.debug(" select_device(%d) called", idx)
        if self.current_device is not None:
            self.current_device.close()
        self.current_device = None
        if idx >= 0:
            self.current_device = self.devices[idx]
            logging.debug(" Selected device: %s", self.current_device.title() if hasattr(self.current_device, 'title') else str(self.current_device))

        if self.current_device is not None:
            try:
                if self.current_device.sideload:
                    logging.debug(" Opening sideload device...")
                    self.current_device.open(self.thread.sideload_json)
                elif self.current_device.via_stack:
                    logging.debug(" Opening via_stack device...")
                    self.current_device.open(self.thread.via_stack_json["definitions"][self.current_device.via_id])
                else:
                    logging.debug(" Opening normal device...")
                    self.current_device.open(None)
                logging.debug(" Device opened successfully")
            except Exception as e:
                logging.warning(" Failed to open device: %s", e)
                self.current_device = None
        self.thread.set_device(self.current_device)
        logging.debug(" select_device() complete")

    def on_devices_updated(self, devices, changed):
        self.devices = devices
        self.devices_updated.emit(devices, changed)

    def update(self, quiet=True, hard=False):
        self.thread.update(quiet, hard)
