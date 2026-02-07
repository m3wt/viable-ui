# SPDX-License-Identifier: GPL-2.0-or-later
import ssl
import certifi
import os

if ssl.get_default_verify_paths().cafile is None:
    os.environ['SSL_CERT_FILE'] = certifi.where()

import traceback

from qtpy import QtWidgets, QtCore
from qtpy.QtCore import Signal

from app_context import cached_property, ApplicationContext

import sys

# Enable non-exclusive HID access on macOS so multiple apps can share a device
if sys.platform == "darwin":
    try:
        import hid
        if hasattr(hid, 'darwin_set_open_exclusive'):
            hid.darwin_set_open_exclusive(False)
    except (ImportError, AttributeError):
        pass  # Old hidapi version or not available


# http://timlehr.com/python-exception-hooks-with-qt-message-box/
from util import init_logger


def show_exception_box(log_msg):
    if QtWidgets.QApplication.instance() is not None:
        errorbox = QtWidgets.QMessageBox()
        errorbox.setText(log_msg)
        errorbox.exec()


class UncaughtHook(QtCore.QObject):
    _exception_caught = Signal(object)

    def __init__(self, *args, **kwargs):
        super(UncaughtHook, self).__init__(*args, **kwargs)

        # this registers the exception_hook() function as hook with the Python interpreter
        sys._excepthook = sys.excepthook
        sys.excepthook = self.exception_hook

        # connect signal to execute the message box function always on main thread
        self._exception_caught.connect(show_exception_box)

    def exception_hook(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # ignore keyboard interrupt to support console applications
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
        else:
            log_msg = '\n'.join([''.join(traceback.format_tb(exc_traceback)),
                                 '{0}: {1}'.format(exc_type.__name__, exc_value)])

            # trigger message box show
            self._exception_caught.emit(log_msg)
        sys._excepthook(exc_type, exc_value, exc_traceback)

class VialApplicationContext(ApplicationContext):
    @cached_property
    def app(self):
        # Override the app definition in order to set WM_CLASS.
        result = QtWidgets.QApplication(sys.argv)
        result.setApplicationName(self.build_settings["app_name"])
        result.setOrganizationDomain("viable-kb.github.io")

        #TODO: Qt sets applicationVersion on non-Linux platforms if the exe/pkg metadata is correctly configured.
        # https://doc.qt.io/qt-5/qcoreapplication.html#applicationVersion-prop
        # Verify it is, and only set manually on Linux.
        #if sys.platform.startswith("linux"):
        result.setApplicationVersion(self.build_settings["version"])
        return result

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == "--linux-recorder":
        from linux_keystroke_recorder import linux_keystroke_recorder

        linux_keystroke_recorder()
    else:
        # Parse command line arguments
        initial_tab = None
        if "--matrix-test" in sys.argv:
            initial_tab = "Matrix tester"

        appctxt = VialApplicationContext()       # 1. Instantiate ApplicationContext
        _ = appctxt.app                          # 2. Create QApplication (needed before Qt class imports)
        init_logger()
        qt_exception_hook = UncaughtHook()
        from main_window import MainWindow       # 3. Import after QApplication exists
        window = MainWindow(appctxt, initial_tab=initial_tab)
        window.show()
        exit_code = appctxt.app.exec()           # 4. Invoke appctxt.app.exec()
        sys.exit(exit_code)
