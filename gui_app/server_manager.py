"""Server and plugin management module."""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Callable

from PySide6 import QtCore, QtWidgets

try:
    from .constants import JAISON_DIR, PLUGIN_DIR
    from .processes import ProcessHandle, LogReader
except ImportError:
    from constants import JAISON_DIR, PLUGIN_DIR
    from processes import ProcessHandle, LogReader


class ServerManager:
    """Manages server and plugin processes."""
    
    def __init__(self):
        self.server = ProcessHandle("server")
        self.plugin = ProcessHandle("plugin")
        self.server_log_reader = LogReader(self.server)
        self.plugin_log_reader = LogReader(self.plugin)
        
        self.jaison_dir = JAISON_DIR
        self.plugin_dir = PLUGIN_DIR
        
        # Callbacks
        self.on_server_log: Optional[Callable[[str], None]] = None
        self.on_plugin_log: Optional[Callable[[str], None]] = None
    
    def setup_log_connections(self, on_server_log, on_plugin_log):
        """Setup log connections."""
        self.on_server_log = on_server_log
        self.on_plugin_log = on_plugin_log
        self.server_log_reader.new_line.connect(on_server_log)
        self.plugin_log_reader.new_line.connect(on_plugin_log)
    
    def start_log_readers(self):
        """Start log readers."""
        self.server_log_reader.start()
        self.plugin_log_reader.start()
    
    def stop_log_readers(self):
        """Stop log readers."""
        self.server_log_reader.stop()
        self.plugin_log_reader.stop()
    
    def find_python_executable(self) -> Optional[Path]:
        """Find Python executable in conda environment."""
        python_exe = None
        
        # Try to find conda environment Python
        conda_exe = shutil.which("conda")
        if conda_exe:
            try:
                result = subprocess.run(
                    ["conda", "info", "--envs"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if "jaison-core" in line and not line.strip().startswith("#"):
                            parts = line.split()
                            if len(parts) >= 2:
                                env_path = Path(parts[-1])
                                python_exe = env_path / "python.exe"
                                if python_exe.exists():
                                    break
            except Exception:
                pass
        
        # Fallback: try common conda locations
        if not python_exe or not python_exe.exists():
            possible_paths = [
                Path.home() / "miniconda3" / "envs" / "jaison-core" / "python.exe",
                Path.home() / "anaconda3" / "envs" / "jaison-core" / "python.exe",
            ]
            for path in possible_paths:
                if path.exists():
                    python_exe = path
                    break
        
        # Fallback to venv if conda not found
        if not python_exe or not python_exe.exists():
            venv_python = JAISON_DIR / ".venv" / "Scripts" / "python.exe"
            if venv_python.exists():
                python_exe = venv_python
        
        return python_exe
    
    def start_server(self, config_name: str = "sammy", parent_widget=None) -> bool:
        """Start the server."""
        if self.server.is_running():
            return False
        
        python_exe = self.find_python_executable()
        if not python_exe or not python_exe.exists():
            if self.on_server_log:
                self.on_server_log("Erro: Python do ambiente jaison-core não encontrado")
            return False
        
        # Find main.py
        main_py = (self.jaison_dir / "src" / "main.py").resolve()
        if not main_py.exists():
            if parent_widget:
                selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
                    parent_widget,
                    "Selecione o diretório do projeto Jaison",
                    str(Path.home()),
                    QtWidgets.QFileDialog.Option.ShowDirsOnly
                )
                
                if selected_dir:
                    jaison_dir = Path(selected_dir)
                    main_py = jaison_dir / "src" / "main.py"
                    if main_py.exists():
                        self.jaison_dir = jaison_dir
                        if self.on_server_log:
                            self.on_server_log(f"Diretório selecionado: {jaison_dir}")
                    else:
                        if self.on_server_log:
                            self.on_server_log(f"Erro: Arquivo main.py não encontrado em: {jaison_dir}")
                        return False
                else:
                    if self.on_server_log:
                        self.on_server_log("Operação cancelada pelo usuário")
                    return False
            else:
                if self.on_server_log:
                    self.on_server_log(f"Arquivo não encontrado em: {main_py}")
                return False
        
        cmd = [str(python_exe), str(main_py), "--config", config_name]
        self.server.start(cmd=cmd, cwd=str(self.jaison_dir.resolve()))
        
        if self.on_server_log:
            self.on_server_log(f"Iniciando servidor com config '{config_name}'...")
            self.on_server_log(f"Python: {python_exe}")
            self.on_server_log(f"Script: {main_py}")
        
        return True
    
    def stop_server(self):
        """Stop the server."""
        self.server.stop()
        if self.on_server_log:
            self.on_server_log("Servidor parado.")
    
    def start_plugin(self, parent_widget=None) -> bool:
        """Start the plugin."""
        if self.plugin.is_running():
            return False
        
        venv_python = (self.plugin_dir / ".venv" / "Scripts" / "python.exe").resolve()
        if not venv_python.exists():
            if self.on_plugin_log:
                self.on_plugin_log(f"Erro: Python não encontrado: {venv_python}")
            return False
        
        main_py = (self.plugin_dir / "src" / "main.py").resolve()
        config_yaml = (self.plugin_dir / "config.yaml").resolve()
        
        if not main_py.exists():
            if parent_widget:
                selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
                    parent_widget,
                    "Selecione o diretório do plugin VTube Studio",
                    str(Path.home()),
                    QtWidgets.QFileDialog.Option.ShowDirsOnly
                )
                if selected_dir:
                    plugin_dir = Path(selected_dir)
                    main_py = plugin_dir / "src" / "main.py"
                    if main_py.exists():
                        self.plugin_dir = plugin_dir
                        venv_python = (self.plugin_dir / ".venv" / "Scripts" / "python.exe").resolve()
                        config_yaml = (self.plugin_dir / "config.yaml").resolve()
                    else:
                        if self.on_plugin_log:
                            self.on_plugin_log(f"Erro: Arquivo main.py não encontrado em: {plugin_dir}")
                        return False
                else:
                    return False
            else:
                if self.on_plugin_log:
                    self.on_plugin_log(f"Erro: Arquivo não encontrado: {main_py}")
                return False
        
        cmd = [str(venv_python), str(main_py), "--config", str(config_yaml)]
        self.plugin.start(cmd=cmd, cwd=str(self.plugin_dir.resolve()))
        
        if self.on_plugin_log:
            self.on_plugin_log("Plugin iniciado.")
            self.on_plugin_log(f"Python: {venv_python}")
            self.on_plugin_log(f"Script: {main_py}")
        
        return True
    
    def stop_plugin(self):
        """Stop the plugin."""
        self.plugin.stop()
        if self.on_plugin_log:
            self.on_plugin_log("Plugin parado.")
    
    def is_server_running(self) -> bool:
        """Check if server is running."""
        return self.server.is_running()
    
    def is_plugin_running(self) -> bool:
        """Check if plugin is running."""
        return self.plugin.is_running()

