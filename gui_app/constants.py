import sys
from pathlib import Path


def get_base_dir():
    """Get the base directory of the project, whether running as script or executable."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        # sys.executable points to the exe, but when running it's in temp
        # We need to find where the exe was originally located
        # PyInstaller sets _MEIPASS to temp dir, but we can use os.path.dirname(sys.executable)
        # However, when running, sys.executable is the temp path
        
        # Try to get original exe location from environment or registry
        # Or search for the exe file in common locations
        exe_name = "JAIsonGUI.exe"
        
        # Search in common locations for the exe file
        search_locations = [
            Path("D:\\Repositories\\Jaison\\gui_app\\dist"),
            Path("C:\\Repositories\\Jaison\\gui_app\\dist"),
            Path.home() / "Repositories" / "Jaison" / "gui_app" / "dist",
            Path.home() / "Documents" / "Repositories" / "Jaison" / "gui_app" / "dist",
        ]
        
        # Also search all drives
        for search_path in search_locations:
            exe_path = search_path / exe_name
            if exe_path.exists():
                # Found exe, go up to Jaison directory
                jaison_dir = search_path.parent.parent
                if (jaison_dir / "src" / "main.py").exists():
                    return jaison_dir
        
        # If exe not found, try to find Jaison directory directly
        jaison_search_paths = [
            Path("D:\\Repositories\\Jaison"),
            Path("C:\\Repositories\\Jaison"),
            Path.home() / "Repositories" / "Jaison",
            Path.home() / "Documents" / "Repositories" / "Jaison",
        ]
        for path in jaison_search_paths:
            if (path / "src" / "main.py").exists():
                return path
        
        # Last resort: return a default and let user configure
        return Path("D:\\Repositories\\Jaison")
    else:
        # Running as script
        return Path(__file__).resolve().parents[1]


REPO_ROOT = get_base_dir()
JAISON_DIR = REPO_ROOT
PLUGIN_DIR = REPO_ROOT.parent / "VTube studio" / "app-jaison-vts-hotkeys-lcc"






