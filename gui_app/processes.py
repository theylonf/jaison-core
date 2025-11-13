import os
import subprocess
import time
from PySide6 import QtCore


class ProcessHandle:
    def __init__(self, name: str):
        self.name = name
        self.proc: subprocess.Popen | None = None

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, cmd: list[str], cwd: str | None = None, env: dict | None = None) -> None:
        if self.is_running():
            return
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        self.proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env or os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            text=True,
        )

    def stop(self) -> None:
        if not self.is_running():
            return
        try:
            if os.name == "nt":
                self.proc.send_signal(subprocess.signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                time.sleep(0.5)
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        finally:
            self.proc = None


class LogReader(QtCore.QThread):
    new_line = QtCore.Signal(str)

    def __init__(self, handle: ProcessHandle):
        super().__init__()
        self.handle = handle
        self._stop = False

    def run(self) -> None:
        while not self._stop:
            if self.handle.is_running() and self.handle.proc.stdout:
                line = self.handle.proc.stdout.readline()
                if line:
                    self.new_line.emit(line.rstrip())
            else:
                time.sleep(0.2)

    def stop(self) -> None:
        self._stop = True







