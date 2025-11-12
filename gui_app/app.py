import sys
import os
from pathlib import Path
from PySide6 import QtWidgets

# Add current directory to path for imports when running as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))

# Ensure stdout/stderr are visible in terminal (Windows)
if sys.platform == "win32":
    # Also ensure console is attached (for Windows)
    # Only allocate console if running from GUI (not from terminal)
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        
        # Check if we already have a console
        has_console = kernel32.GetConsoleWindow() != 0
        
        if not has_console:
            # AllocConsole creates a new console window only if we don't have one
            kernel32.AllocConsole()
            # Redirect stdout/stderr to console
            sys.stdout = open('CONOUT$', 'w', encoding='utf-8')
            sys.stderr = open('CONOUT$', 'w', encoding='utf-8')
        else:
            # We have a console, ensure stdout/stderr are properly set
            if sys.stdout is None:
                sys.stdout = sys.__stdout__
            if sys.stderr is None:
                sys.stderr = sys.__stderr__
            
            # Try to reconfigure for unbuffered output (Python 3.7+)
            try:
                if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
                    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
                if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
                    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
            except (AttributeError, OSError):
                # Python < 3.7 or reconfigure not available, or already redirected
                pass
    except Exception:
        # If console allocation fails, ensure stdout/stderr are at least not None
        if sys.stdout is None:
            sys.stdout = sys.__stdout__
        if sys.stderr is None:
            sys.stderr = sys.__stderr__

from main_window import MainWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
