"""PyInstaller entry point; the native shell supplies lifecycle and window handling."""

import multiprocessing

from monkey_api.main import run

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
