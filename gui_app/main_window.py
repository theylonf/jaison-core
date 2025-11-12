import os
import sys
import subprocess
import shutil
import threading
import time
import json
import base64
import re
from pathlib import Path

import requests
import sounddevice as sd
import numpy as np
from PySide6 import QtCore, QtWidgets

# Handle both relative and absolute imports
try:
    from .constants import JAISON_DIR, PLUGIN_DIR
    from .processes import ProcessHandle, LogReader
    from .audio_listener import AudioListener
    from .ui_components import AudioLevelWithThreshold
except ImportError:
    from constants import JAISON_DIR, PLUGIN_DIR
    from processes import ProcessHandle, LogReader
    from audio_listener import AudioListener
    from ui_components import AudioLevelWithThreshold


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JAIson - Launcher & Chat")
        self.resize(900, 650)

        self.server = ProcessHandle("server")
        self.plugin = ProcessHandle("plugin")
        self.server_log_reader = LogReader(self.server)
        self.plugin_log_reader = LogReader(self.plugin)
        self.server_log_reader.new_line.connect(self._append_server_log)
        self.plugin_log_reader.new_line.connect(self._append_plugin_log)
        
        # Audio listener for server responses
        self.audio_listener = None
        
        # Store project directories as instance variables
        self.jaison_dir = JAISON_DIR
        self.plugin_dir = PLUGIN_DIR
        
        # Audio recording
        self.is_recording = False
        self.audio_data = None
        self.sample_rate = 16000
        
        # Continuous listening (VAD)
        self.is_listening_continuously = False
        self.current_phrase_audio = []
        self.is_speaking = False
        self.silence_start_time = None
        self.voice_threshold = 500  # RMS threshold for voice detection
        self.silence_duration = 1.5  # seconds of silence before auto-send
        self.continuous_stream = None
        
        # Store last received audio from AI
        self.last_ai_audio = None
        self.last_ai_audio_sr = 16000
        self.last_ai_audio_sw = 2
        self.last_ai_audio_ch = 1
        
        # Store audio chunks for reassembly
        self.audio_chunks_buffer = []
        
        # Audio output device (None = default, or device name/index)
        self.audio_output_device = None
        # Audio input device (None = default, or device name/index)
        self.audio_input_device = None

        self._build_ui()
        self._wire_events()
        self.server_log_reader.start()
        self.plugin_log_reader.start()
        
        # Check if server is already running and start listener if needed
        QtCore.QTimer.singleShot(2000, self._check_and_start_listener)

    def closeEvent(self, event):
        try:
            self.server_log_reader.stop()
            self.plugin_log_reader.stop()
            if self.audio_listener:
                self.audio_listener.stop()
                self.audio_listener.wait(2000)
            if self.is_listening_continuously:
                self._stop_continuous_listening()
            if self.is_recording:
                self._stop_recording()
            self.server.stop()
            self.plugin.stop()
        finally:
            return super().closeEvent(event)

    def _build_ui(self):
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # Controls tab
        controls = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(controls)

        self.host = QtWidgets.QLineEdit("127.0.0.1")
        self.port = QtWidgets.QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(7272)
        self.config_name = QtWidgets.QLineEdit("sammy")

        self.btn_start_server = QtWidgets.QPushButton("Iniciar Servidor")
        self.btn_stop_server = QtWidgets.QPushButton("Parar Servidor")
        self.btn_start_plugin = QtWidgets.QPushButton("Iniciar Plugin")
        self.btn_stop_plugin = QtWidgets.QPushButton("Parar Plugin")

        self.server_log = QtWidgets.QPlainTextEdit()
        self.server_log.setReadOnly(True)
        self.plugin_log = QtWidgets.QPlainTextEdit()
        self.plugin_log.setReadOnly(True)
        
        self.btn_clear_server_log = QtWidgets.QPushButton("Limpar Logs")
        self.btn_clear_plugin_log = QtWidgets.QPushButton("Limpar Logs")

        form.addRow("Host:", self.host)
        form.addRow("Porta:", self.port)
        form.addRow("Config:", self.config_name)
        form.addRow(self.btn_start_server, self.btn_stop_server)
        form.addRow(self.btn_start_plugin, self.btn_stop_plugin)
        form.addRow(QtWidgets.QLabel("Logs do Servidor:"), self.btn_clear_server_log)
        form.addRow(self.server_log)
        form.addRow(QtWidgets.QLabel("Logs do Plugin:"), self.btn_clear_plugin_log)
        form.addRow(self.plugin_log)

        # Chat tab
        chat = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(chat)
        
        # Chat header with clear button
        hbox_chat_header = QtWidgets.QHBoxLayout()
        hbox_chat_header.addWidget(QtWidgets.QLabel("Histórico do Chat:"))
        self.btn_clear_chat = QtWidgets.QPushButton("Limpar Chat")
        hbox_chat_header.addWidget(self.btn_clear_chat, 0)
        hbox_chat_header.addStretch(1)
        
        self.chat_history = QtWidgets.QPlainTextEdit()
        self.chat_history.setReadOnly(True)
        
        # Text input
        hbox_text = QtWidgets.QHBoxLayout()
        self.input_text = QtWidgets.QLineEdit()
        self.btn_send_text = QtWidgets.QPushButton("Enviar texto")
        hbox_text.addWidget(self.input_text, 1)
        hbox_text.addWidget(self.btn_send_text, 0)
        
        # Audio input
        hbox_audio = QtWidgets.QHBoxLayout()
        self.btn_record_audio = QtWidgets.QPushButton("🎤 Gravar Áudio")
        self.btn_record_audio.setCheckable(True)
        self.btn_listen_continuous = QtWidgets.QPushButton("👂 Escuta Contínua")
        self.btn_listen_continuous.setCheckable(True)
        self.btn_stop_listening = QtWidgets.QPushButton("⏹ Parar Escuta")
        self.btn_stop_listening.setEnabled(False)
        self.btn_test_audio = QtWidgets.QPushButton("🔊 Testar Áudio")
        self.btn_test_audio.setEnabled(False)
        self.btn_send_audio = QtWidgets.QPushButton("Enviar Áudio")
        self.btn_send_audio.setEnabled(False)
        self.audio_status = QtWidgets.QLabel("Pronto para gravar")
        hbox_audio.addWidget(self.btn_record_audio)
        hbox_audio.addWidget(self.btn_listen_continuous)
        hbox_audio.addWidget(self.btn_stop_listening)
        hbox_audio.addWidget(self.btn_test_audio)
        hbox_audio.addWidget(self.btn_send_audio)
        hbox_audio.addWidget(self.audio_status, 1)
        
        # VAD settings
        hbox_vad_settings = QtWidgets.QHBoxLayout()
        hbox_vad_settings.addWidget(QtWidgets.QLabel("Sensibilidade:"))
        self.slider_sensitivity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_sensitivity.setMinimum(100)
        self.slider_sensitivity.setMaximum(2000)
        self.slider_sensitivity.setValue(500)
        self.slider_sensitivity.setEnabled(True)  # Enable even when not listening to allow pre-configuration
        self.label_sensitivity = QtWidgets.QLabel("500")
        hbox_vad_settings.addWidget(self.slider_sensitivity, 1)
        hbox_vad_settings.addWidget(self.label_sensitivity)
        
        hbox_vad_settings.addWidget(QtWidgets.QLabel("  Silêncio (s):"))
        self.slider_silence = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_silence.setMinimum(5)
        self.slider_silence.setMaximum(50)
        self.slider_silence.setValue(15)  # 1.5 seconds in 0.1s units
        self.slider_silence.setEnabled(False)
        self.label_silence = QtWidgets.QLabel("1.5s")
        hbox_vad_settings.addWidget(self.slider_silence, 1)
        hbox_vad_settings.addWidget(self.label_silence)
        
        # Voice indicator
        self.voice_indicator = QtWidgets.QLabel("🔇")
        self.voice_indicator.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        hbox_vad_settings.addWidget(self.voice_indicator)
        
        # Audio level indicator with threshold visualization
        hbox_audio_level = QtWidgets.QHBoxLayout()
        hbox_audio_level.addWidget(QtWidgets.QLabel("Nível RMS:"))
        
        # Use custom widget from ui_components module
        self.audio_level_widget = AudioLevelWithThreshold()
        hbox_audio_level.addWidget(self.audio_level_widget, 1)
        
        # Keep old progress bar for compatibility (hidden)
        self.audio_level_bar = QtWidgets.QProgressBar()
        self.audio_level_bar.setMinimum(0)
        self.audio_level_bar.setMaximum(2000)
        self.audio_level_bar.setValue(0)
        self.audio_level_bar.hide()  # Hide old bar, use custom widget instead
        
        # Labels for values
        value_container = QtWidgets.QHBoxLayout()
        self.audio_level_label = QtWidgets.QLabel("0")
        value_container.addWidget(self.audio_level_label)
        value_container.addWidget(QtWidgets.QLabel(" / "))
        self.threshold_indicator = QtWidgets.QLabel("500")
        self.threshold_indicator.setStyleSheet("font-weight: bold; color: #FF5722;")
        value_container.addWidget(self.threshold_indicator)
        hbox_audio_level.addLayout(value_container)
        
        # Audio playback controls
        hbox_audio_playback = QtWidgets.QHBoxLayout()
        self.btn_play_last_audio = QtWidgets.QPushButton("▶ Reproduzir Último Áudio da IA")
        self.btn_play_last_audio.setEnabled(False)
        self.btn_select_audio_output = QtWidgets.QPushButton("⚙ Saída de Áudio")
        self.btn_select_audio_input = QtWidgets.QPushButton("🎤 Entrada de Áudio")
        hbox_audio_playback.addWidget(self.btn_play_last_audio)
        hbox_audio_playback.addWidget(self.btn_select_audio_output)
        hbox_audio_playback.addWidget(self.btn_select_audio_input)
        hbox_audio_playback.addStretch(1)
        
        vbox.addLayout(hbox_chat_header)
        vbox.addWidget(self.chat_history, 1)
        vbox.addLayout(hbox_text)
        vbox.addLayout(hbox_audio)
        vbox.addLayout(hbox_vad_settings)
        vbox.addLayout(hbox_audio_level)
        
        # VAD logs removed - now only in terminal
        vbox.addLayout(hbox_audio_playback)

        self.tabs.addTab(controls, "Controles")
        self.tabs.addTab(chat, "Chat")

    def _wire_events(self):
        self.btn_start_server.clicked.connect(self._on_start_server)
        self.btn_stop_server.clicked.connect(self._on_stop_server)
        self.btn_start_plugin.clicked.connect(self._on_start_plugin)
        self.btn_stop_plugin.clicked.connect(self._on_stop_plugin)
        self.btn_send_text.clicked.connect(self._on_send_text)
        self.btn_record_audio.clicked.connect(self._on_toggle_record)
        self.btn_listen_continuous.clicked.connect(self._on_toggle_continuous_listening)
        self.btn_stop_listening.clicked.connect(self._on_stop_listening)
        self.btn_test_audio.clicked.connect(self._on_test_audio)
        self.btn_send_audio.clicked.connect(self._on_send_audio)
        self.btn_play_last_audio.clicked.connect(self._on_play_last_audio)
        self.btn_select_audio_output.clicked.connect(self._on_select_audio_output)
        self.btn_select_audio_input.clicked.connect(self._on_select_audio_input)
        
        # VAD settings
        self.slider_sensitivity.valueChanged.connect(self._on_sensitivity_changed)
        self.slider_silence.valueChanged.connect(self._on_silence_changed)
        self.btn_clear_server_log.clicked.connect(lambda: self.server_log.clear())
        self.btn_clear_plugin_log.clicked.connect(lambda: self.plugin_log.clear())
        self.btn_clear_chat.clicked.connect(lambda: self.chat_history.clear())
        
        # Enter key to send text
        self.input_text.returnPressed.connect(self._on_send_text)

    def _append_server_log(self, line: str):
        """Append log to terminal only (server logs)."""
        print(f"[Server] {line}")
        # Optionally keep in UI for reference (commented out)
        # self.server_log.appendPlainText(line)

    def _append_plugin_log(self, line: str):
        """Append log to terminal only (plugin logs)."""
        print(f"[Plugin] {line}")
        # Optionally keep in UI for reference (commented out)
        # self.plugin_log.appendPlainText(line)
    
    def _append_vad_log(self, line: str):
        """Append log to terminal only (thread-safe)."""
        # Just print to terminal - no UI logging
        print(line)

    def _on_start_server(self):
        if self.server.is_running():
            return
        cfg = self.config_name.text().strip() or "sammy"
        
        # Find Python executable
        python_exe = None
        
        # Try to find conda environment Python
        conda_exe = shutil.which("conda")
        if conda_exe:
            try:
                # Get conda environment path
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
            else:
                self._append_server_log("Erro: Python do ambiente jaison-core nao encontrado")
                return
        
        # Verify and find main.py
        main_py = (self.jaison_dir / "src" / "main.py").resolve()
        if not main_py.exists():
            # Try to find Jaison directory
            self._append_server_log(f"Arquivo nao encontrado em: {main_py}")
            self._append_server_log("Tentando localizar diretorio do projeto...")
            
            # Show dialog to select directory
            selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Selecione o diretorio do projeto Jaison",
                str(Path.home()),
                QtWidgets.QFileDialog.Option.ShowDirsOnly
            )
            
            if selected_dir:
                jaison_dir = Path(selected_dir)
                main_py = jaison_dir / "src" / "main.py"
                if main_py.exists():
                    self.jaison_dir = jaison_dir
                    self._append_server_log(f"Diretorio selecionado: {jaison_dir}")
                else:
                    self._append_server_log(f"Erro: Arquivo main.py nao encontrado em: {jaison_dir}")
                    return
            else:
                self._append_server_log("Operacao cancelada pelo usuario")
                return
        
        cmd = [str(python_exe), str(main_py), "--config", cfg]
        self.server.start(cmd=cmd, cwd=str(self.jaison_dir.resolve()))
        self._append_server_log(f"Iniciando servidor com config '{cfg}'...")
        self._append_server_log(f"Python: {python_exe}")
        self._append_server_log(f"Script: {main_py}")
        
        # Start audio listener after a short delay to let server start
        print("[MainWindow] Agendando início do audio listener em 3 segundos...")
        QtCore.QTimer.singleShot(3000, self._start_audio_listener)

    def _on_stop_server(self):
        if self.audio_listener:
            self.audio_listener.stop()
            self.audio_listener.wait(2000)
            self.audio_listener = None
        self.server.stop()
        self._append_server_log("Servidor parado.")
    
    def _check_server_running(self) -> bool:
        """Check if server is actually running by trying to connect."""
        host = self.host.text().strip() or "127.0.0.1"
        port = self.port.value()
        url = f"http://{host}:{port}/"
        
        try:
            response = requests.get(url, timeout=1)
            return True
        except Exception:
            return False
    
    def _check_and_start_listener(self):
        """Check if server is running and start listener if needed."""
        print("[MainWindow] Verificando se servidor está rodando para iniciar listener...")
        
        # Check both ProcessHandle and actual HTTP connection
        process_running = self.server.is_running()
        server_accessible = self._check_server_running()
        
        print(f"[MainWindow] ProcessHandle.is_running() = {process_running}")
        print(f"[MainWindow] Servidor acessível via HTTP = {server_accessible}")
        
        if process_running or server_accessible:
            print("[MainWindow] ✅ Servidor está rodando, iniciando listener...")
            self._start_audio_listener()
        else:
            print("[MainWindow] ⚠️ Servidor não está rodando ainda, listener será iniciado quando servidor iniciar")
    
    def _start_audio_listener(self):
        """Start listening to websocket for audio responses."""
        print("[MainWindow] _start_audio_listener chamado")
        
        if self.audio_listener and self.audio_listener.isRunning():
            print("[WebSocket] ⚠️ Listener já está rodando, parando e reiniciando...")
            self.audio_listener.stop()
            self.audio_listener.wait(2000)
            self.audio_listener = None
        
        host = self.host.text().strip() or "127.0.0.1"
        port = self.port.value()
        ws_url = f"ws://{host}:{port}/"
        
        print(f"[WebSocket] 🔌 Iniciando listener em {ws_url}")
        print(f"[WebSocket] Verificando se servidor está rodando...")
        
        # Check both ProcessHandle and actual server accessibility
        process_running = self.server.is_running()
        server_accessible = self._check_server_running()
        
        print(f"[WebSocket] ProcessHandle.is_running() = {process_running}")
        print(f"[WebSocket] Servidor acessível via HTTP = {server_accessible}")
        
        if not process_running and not server_accessible:
            print(f"[WebSocket] ⚠️ Servidor não está rodando! Listener não será iniciado.")
            print(f"[WebSocket] ⚠️ Aguardando servidor iniciar...")
            # Try again in 2 seconds
            QtCore.QTimer.singleShot(2000, self._start_audio_listener)
            return
        
        try:
            print(f"[WebSocket] Criando AudioListener...")
            self.audio_listener = AudioListener(ws_url)
            print(f"[WebSocket] Conectando sinais...")
            self.audio_listener.audio_received.connect(self._play_audio)
            self.audio_listener.audio_chunk_received.connect(self._on_audio_chunk)
            self.audio_listener.audio_complete.connect(self._on_audio_complete)
            self.audio_listener.text_received.connect(self._on_received_text)
            self.audio_listener.error_received.connect(self._on_received_error)
            print(f"[WebSocket] Iniciando thread do listener...")
            self.audio_listener.start()
            print(f"[WebSocket] ✅ Thread do listener iniciada (isRunning={self.audio_listener.isRunning()})")
            self._append_server_log(f"Audio listener iniciado em {ws_url}")
            print(f"[WebSocket] ✅ Listener iniciado e aguardando eventos...")
        except Exception as e:
            print(f"[WebSocket] ❌ Erro ao iniciar listener: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_audio_chunk(self, audio_b64_chunk: str, sr: int, sw: int, ch: int):
        """Handle audio chunk received from server."""
        try:
            # Decode chunk and add to buffer
            chunk_bytes = base64.b64decode(audio_b64_chunk)
            self.audio_chunks_buffer.append(chunk_bytes)
            # Store audio parameters from last chunk (these will be used for playback)
            self.last_ai_audio_sr = sr
            self.last_ai_audio_sw = sw
            self.last_ai_audio_ch = ch
            total_bytes = sum(len(c) for c in self.audio_chunks_buffer)
            print(f"[Audio] Chunk #{len(self.audio_chunks_buffer)} recebido: {len(chunk_bytes)} bytes")
            print(f"[Audio] Total acumulado: {total_bytes} bytes em {len(self.audio_chunks_buffer)} chunks")
            print(f"[Audio] Parâmetros: sr={sr}, sw={sw}, ch={ch}")
        except Exception as e:
            print(f"Erro ao decodificar chunk de audio: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_audio_complete(self, sr: int, sw: int, ch: int):
        """Handle audio completion signal."""
        print(f"[Audio] ===== EVENTO DE CONCLUSÃO RECEBIDO =====")
        print(f"[Audio] Parâmetros recebidos: sr={sr}, sw={sw}, ch={ch}")
        print(f"[Audio] Chunks no buffer: {len(self.audio_chunks_buffer)}")
        print(f"[Audio] Parâmetros armazenados: sr={self.last_ai_audio_sr}, sw={self.last_ai_audio_sw}, ch={self.last_ai_audio_ch}")
        
        if self.audio_chunks_buffer:
            # Use stored parameters if provided ones are default/zero
            if sr == 16000 and self.last_ai_audio_sr != 16000:
                print(f"[Audio] Usando parâmetros armazenados ao invés dos recebidos")
                sr = self.last_ai_audio_sr
                sw = self.last_ai_audio_sw
                ch = self.last_ai_audio_ch
            
            total_bytes = sum(len(c) for c in self.audio_chunks_buffer)
            print(f"[Audio] Montando {len(self.audio_chunks_buffer)} chunks ({total_bytes} bytes total)")
            print(f"[Audio] Com parâmetros: sr={sr}, sw={sw}, ch={ch}")
            self._assemble_and_play_audio(sr, sw, ch)
        else:
            print(f"[Audio] ⚠️ Buffer vazio quando evento de conclusão chegou!")
            print(f"[Audio] Possíveis causas:")
            print(f"  - Os chunks já foram montados anteriormente (verifique logs acima)")
            print(f"  - Os chunks ainda não chegaram (problema de timing)")
            print(f"  - O áudio não foi incluído na resposta")
    
    def _try_assemble_audio_on_text(self):
        """Try to assemble audio when text is received."""
        if self.audio_chunks_buffer:
            print(f"[Audio] Tentando montar áudio após receber texto: {len(self.audio_chunks_buffer)} chunks")
            # Usa os parâmetros do último chunk recebido
            self._assemble_and_play_audio(
                self.last_ai_audio_sr or 16000,
                self.last_ai_audio_sw or 2,
                self.last_ai_audio_ch or 1
            )
    
    def _assemble_and_play_audio(self, sr: int, sw: int, ch: int):
        """Assemble audio chunks and play."""
        if not self.audio_chunks_buffer:
            print("[Audio] ❌ _assemble_and_play_audio chamado mas buffer está vazio")
            return
        
        try:
            # Make a copy of buffer to avoid race conditions
            chunks_to_assemble = list(self.audio_chunks_buffer)
            num_chunks = len(chunks_to_assemble)
            
            # Concatenate all chunks
            complete_audio = b''.join(chunks_to_assemble)
            
            if len(complete_audio) == 0:
                print("[Audio] ❌ Áudio completo tem 0 bytes, ignorando")
                self.audio_chunks_buffer = []
                return
            
            print(f"[Audio] ✅ Montando áudio: {len(complete_audio)} bytes de {num_chunks} chunks")
            
            # Store for playback button
            audio_array = np.frombuffer(complete_audio, dtype=np.int16)
            if ch == 2:
                audio_array = audio_array.reshape(-1, 2)
            
            duration = len(audio_array) / sr
            print(f"[Audio] ✅ Áudio processado: {len(audio_array)} amostras, {duration:.2f}s de duração")
            print(f"[Audio] ✅ Parâmetros finais: sr={sr}, sw={sw}, ch={ch}")
            
            self.last_ai_audio = audio_array
            self.last_ai_audio_sr = sr
            self.last_ai_audio_sw = sw
            self.last_ai_audio_ch = ch
            self.btn_play_last_audio.setEnabled(True)
            
            # Clear buffer BEFORE playing to avoid duplicate assembly
            self.audio_chunks_buffer = []
            
            print(f"[Audio] 🎵 Iniciando reprodução...")
            
            # Play audio
            self._play_audio(complete_audio, sr, sw, ch)
        except Exception as e:
            error_msg = f"Erro ao montar audio: {e}"
            print(f"[Audio] ❌ {error_msg}")
            import traceback
            traceback.print_exc()
            self.audio_chunks_buffer = []
            # Show error in status
            self.audio_status.setText(error_msg)
    
    def _play_audio(self, audio_bytes: bytes, sr: int, sw: int, ch: int):
        """Play audio received from server."""
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Reshape if stereo
            if ch == 2:
                audio_array = audio_array.reshape(-1, 2)
            
            # Play audio in a separate thread to avoid blocking
            def play_thread():
                try:
                    # Use specified device or default
                    if self.audio_output_device is not None:
                        sd.play(audio_array, samplerate=sr, device=self.audio_output_device)
                    else:
                        sd.play(audio_array, samplerate=sr)
                    sd.wait()  # Wait for playback to finish
                except Exception as e:
                    print(f"Erro ao reproduzir audio: {e}")
            
            threading.Thread(target=play_thread, daemon=True).start()
        except Exception as e:
            error_msg = f"Erro ao processar audio: {e}"
            print(f"[Audio] ❌ {error_msg}")
            import traceback
            traceback.print_exc()
            self.audio_status.setText(error_msg)
    
    def _on_test_audio(self):
        """Test/playback the recorded audio before sending."""
        if not self.audio_data:
            error_msg = "Erro: Nenhum áudio gravado para testar"
            print(f"[Audio] ❌ {error_msg}")
            self.audio_status.setText(error_msg)
            return
        
        try:
            audio_array = np.concatenate(self.audio_data, axis=0)
            duration = len(audio_array) / self.sample_rate
            self.audio_status.setText(f"Reproduzindo áudio gravado ({duration:.1f}s)...")
            
            def play_thread():
                try:
                    # Use specified output device or default
                    if self.audio_output_device is not None:
                        print(f"[Audio] Reproduzindo teste no dispositivo {self.audio_output_device}")
                        sd.play(audio_array, samplerate=self.sample_rate, device=self.audio_output_device)
                    else:
                        print(f"[Audio] Reproduzindo teste no dispositivo padrão")
                        sd.play(audio_array, samplerate=self.sample_rate)
                    sd.wait()
                    QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText("Áudio testado. Pronto para enviar."))
                except Exception as e:
                    error_msg = f"Erro ao reproduzir: {e}"
                    print(f"[Audio] {error_msg}")
                    QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText(error_msg))
            
            threading.Thread(target=play_thread, daemon=True).start()
        except Exception as e:
            self.chat_history.appendPlainText(f"Erro ao testar áudio: {e}")
    
    def _on_play_last_audio(self):
        """Play the last audio received from AI."""
        if self.last_ai_audio is None:
            self.chat_history.appendPlainText("Nenhum áudio da IA disponível para reproduzir")
            return
        
        try:
            def play_thread():
                try:
                    if self.audio_output_device is not None:
                        sd.play(self.last_ai_audio, samplerate=self.last_ai_audio_sr, device=self.audio_output_device)
                    else:
                        sd.play(self.last_ai_audio, samplerate=self.last_ai_audio_sr)
                    sd.wait()
                except Exception as e:
                    print(f"Erro ao reproduzir áudio da IA: {e}")
            
            threading.Thread(target=play_thread, daemon=True).start()
            self.chat_history.appendPlainText("Reproduzindo último áudio da IA...")
        except Exception as e:
            self.chat_history.appendPlainText(f"Erro ao reproduzir áudio: {e}")
    
    def _on_select_audio_output(self):
        """Open dialog to select audio output device."""
        try:
            devices = sd.query_devices()
            output_devices = []
            device_names = []
            
            for i, device in enumerate(devices):
                if device['max_output_channels'] > 0:
                    output_devices.append(i)
                    device_name = f"{i}: {device['name']} ({device['hostapi']})"
                    device_names.append(device_name)
            
            if not device_names:
                self.chat_history.appendPlainText("Nenhum dispositivo de saída encontrado")
                return
            
            # Create dialog
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Selecionar Dispositivo de Saída de Áudio")
            layout = QtWidgets.QVBoxLayout(dialog)
            
            label = QtWidgets.QLabel("Selecione o dispositivo de saída de áudio:")
            layout.addWidget(label)
            
            list_widget = QtWidgets.QListWidget()
            list_widget.addItems(device_names)
            layout.addWidget(list_widget)
            
            buttons = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.StandardButton.Ok | 
                QtWidgets.QDialogButtonBox.StandardButton.Cancel |
                QtWidgets.QDialogButtonBox.StandardButton.Reset
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Reset).clicked.connect(lambda: self._reset_audio_output_device(dialog))
            layout.addWidget(buttons)
            
            if dialog.exec():
                selected = list_widget.currentRow()
                if selected >= 0:
                    self.audio_output_device = output_devices[selected]
                    device_name = devices[output_devices[selected]]['name']
                    self.chat_history.appendPlainText(f"Dispositivo de saída selecionado: {device_name}")
                    self._append_server_log(f"Dispositivo de saída: {device_name}")
                else:
                    self.chat_history.appendPlainText("Nenhum dispositivo selecionado")
        except Exception as e:
            self.chat_history.appendPlainText(f"Erro ao selecionar dispositivo de saída: {e}")
    
    def _on_select_audio_input(self):
        """Open dialog to select audio input device."""
        try:
            devices = sd.query_devices()
            input_devices = []
            device_names = []
            
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append(i)
                    device_name = f"{i}: {device['name']} ({device['hostapi']})"
                    device_names.append(device_name)
            
            if not device_names:
                self.chat_history.appendPlainText("Nenhum dispositivo de entrada encontrado")
                return
            
            # Create dialog
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Selecionar Dispositivo de Entrada de Áudio")
            layout = QtWidgets.QVBoxLayout(dialog)
            
            label = QtWidgets.QLabel("Selecione o dispositivo de entrada de áudio (microfone):")
            layout.addWidget(label)
            
            list_widget = QtWidgets.QListWidget()
            list_widget.addItems(device_names)
            layout.addWidget(list_widget)
            
            buttons = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.StandardButton.Ok | 
                QtWidgets.QDialogButtonBox.StandardButton.Cancel |
                QtWidgets.QDialogButtonBox.StandardButton.Reset
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Reset).clicked.connect(lambda: self._reset_audio_input_device(dialog))
            layout.addWidget(buttons)
            
            if dialog.exec():
                selected = list_widget.currentRow()
                if selected >= 0:
                    self.audio_input_device = input_devices[selected]
                    device_name = devices[input_devices[selected]]['name']
                    self.chat_history.appendPlainText(f"Dispositivo de entrada selecionado: {device_name}")
                    self._append_server_log(f"Dispositivo de entrada: {device_name}")
                else:
                    self.chat_history.appendPlainText("Nenhum dispositivo selecionado")
        except Exception as e:
            self.chat_history.appendPlainText(f"Erro ao selecionar dispositivo de entrada: {e}")
    
    def _reset_audio_output_device(self, dialog):
        """Reset to default audio output device."""
        self.audio_output_device = None
        self.chat_history.appendPlainText("Dispositivo de saída resetado para padrão do sistema")
        dialog.accept()
    
    def _reset_audio_input_device(self, dialog):
        """Reset to default audio input device."""
        self.audio_input_device = None
        self.chat_history.appendPlainText("Dispositivo de entrada resetado para padrão do sistema")
        dialog.accept()
    
    def _on_received_text(self, text: str):
        """Handle text received from server."""
        if text.strip():
            self.chat_history.appendPlainText(f"Aeliana: {text}")
            self._append_server_log(f"Texto recebido da IA: {text[:100]}...")
            
            # Extract emotions between [] and send to plugin
            emotions = re.findall(r'\[([^\]]+)\]', text)
            if emotions:
                # Send emotion to plugin via websocket (if plugin is connected)
                # This will be handled by the plugin's websocket listener
                pass
            
            # Se temos chunks de áudio no buffer, tenta montar e reproduzir
            # Isso garante que mesmo se o evento response_success não chegar,
            # o áudio será reproduzido quando o texto chegar
            if self.audio_chunks_buffer:
                print(f"[Audio] Texto recebido, temos {len(self.audio_chunks_buffer)} chunks no buffer")
                print(f"[Audio] Aguardando 1 segundo para garantir que todos os chunks chegaram...")
                # Aguarda um pouco mais para garantir que todos os chunks chegaram
                QtCore.QTimer.singleShot(1000, self._try_assemble_audio_on_text)
            else:
                print(f"[Audio] Texto recebido, mas nenhum chunk de áudio no buffer")
                print(f"[Audio] Aguardando chunks ou evento de conclusão...")
    
    def _on_received_error(self, error_msg: str):
        """Handle error received from server via WebSocket."""
        error_display = f"❌ Erro do servidor: {error_msg}"
        print(f"[WebSocket] {error_display}")
        self.chat_history.appendPlainText(error_display)
        self._append_server_log(f"Erro recebido via WebSocket: {error_msg}")
        
        # Check if it's an API key error
        if "API key" in error_msg or "401" in error_msg or "authentication" in error_msg.lower():
            self.chat_history.appendPlainText("💡 Dica: Verifique se a API key da OpenAI está configurada corretamente no servidor")
    
    def _request_response(self):
        """Request a response from the server after adding context."""
        host = self.host.text().strip() or "127.0.0.1"
        port = self.port.value()
        url = f"http://{host}:{port}/api/response"
        
        try:
            payload = {
                "include_audio": True  # Solicita áudio na resposta
            }
            self._append_server_log(f"Solicitando resposta com audio (include_audio=True)...")
            r = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=60)
            
            if r.ok:
                response_data = r.json()
                job_id = response_data.get("response", {}).get("job_id", "desconhecido")
                self._append_server_log(f"Resposta solicitada -> job_id: {job_id} (include_audio=True)")
                print(f"[Chat] Resposta solicitada (job_id: {job_id}). Aguardando audio...")
            else:
                error_msg = r.text[:500] if r.text else "Sem detalhes"
                self.chat_history.appendPlainText(f"Erro ao solicitar resposta ({r.status_code}): {error_msg}")
                self._append_server_log(f"Erro ao solicitar resposta: {r.status_code} - {error_msg}")
        except Exception as e:
            self.chat_history.appendPlainText(f"Falha ao solicitar resposta: {e}")
            self._append_server_log(f"Excecao ao solicitar resposta: {e}")

    def _on_start_plugin(self):
        if self.plugin.is_running():
            return
        
        # Use absolute paths
        venv_python = (self.plugin_dir / ".venv" / "Scripts" / "python.exe").resolve()
        if not venv_python.exists():
            self._append_plugin_log(f"Erro: Python nao encontrado: {venv_python}")
            return
        
        main_py = (self.plugin_dir / "src" / "main.py").resolve()
        config_yaml = (self.plugin_dir / "config.yaml").resolve()
        
        if not main_py.exists():
            self._append_plugin_log(f"Erro: Arquivo nao encontrado: {main_py}")
            # Try to find plugin directory
            selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Selecione o diretorio do plugin VTube Studio",
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
                    self._append_plugin_log(f"Erro: Arquivo main.py nao encontrado em: {plugin_dir}")
                    return
            else:
                return
        
        cmd = [str(venv_python), str(main_py), "--config", str(config_yaml)]
        self.plugin.start(cmd=cmd, cwd=str(self.plugin_dir.resolve()))
        self._append_plugin_log("Plugin iniciado.")
        self._append_plugin_log(f"Python: {venv_python}")
        self._append_plugin_log(f"Script: {main_py}")

    def _on_stop_plugin(self):
        self.plugin.stop()
        self._append_plugin_log("Plugin parado.")

    def _on_send_text(self):
        text = self.input_text.text().strip()
        if not text:
            return
        
        # Check if server is running
        if not self.server.is_running():
            self.chat_history.appendPlainText("Erro: Servidor nao esta rodando. Inicie o servidor primeiro.")
            return
        
        host = self.host.text().strip() or "127.0.0.1"
        port = self.port.value()
        url = f"http://{host}:{port}/api/context/conversation/text"
        
        try:
            payload = {
                "user": "Usuario",
                "content": text,
                "timestamp": int(time.time())
            }
            self.chat_history.appendPlainText(f"Você: {text}")
            print("[Chat] Enviando para servidor...")
            
            r = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=30)
            
            if r.ok:
                response_data = r.json()
                job_id = response_data.get("response", {}).get("job_id", "desconhecido")
                print(f"[Chat] Pedido enviado (job_id: {job_id}). Gerando resposta...")
                self._append_server_log(f"Texto enviado: '{text}' -> job_id: {job_id}")
                
                # Request response after adding text to context
                self._request_response()
            else:
                error_msg = r.text[:500] if r.text else "Sem detalhes"
                self.chat_history.appendPlainText(f"Erro do servidor ({r.status_code}): {error_msg}")
                self._append_server_log(f"Erro ao enviar texto: {r.status_code} - {error_msg}")
        except requests.exceptions.ConnectionError as e:
            self.chat_history.appendPlainText(f"Erro de conexao: Nao foi possivel conectar ao servidor em {url}")
            self.chat_history.appendPlainText("Verifique se o servidor esta rodando e a porta esta correta.")
            self._append_server_log(f"Erro de conexao: {e}")
        except requests.exceptions.Timeout:
            self.chat_history.appendPlainText("Timeout: O servidor demorou muito para responder.")
            self._append_server_log("Timeout ao enviar texto")
        except Exception as e:
            self.chat_history.appendPlainText(f"Falha ao enviar: {e}")
            self._append_server_log(f"Excecao ao enviar texto: {e}")
        finally:
            self.input_text.clear()

    def _on_toggle_record(self, checked: bool):
        if checked:
            # Stop continuous listening if active
            if self.is_listening_continuously:
                self.btn_listen_continuous.setChecked(False)
                self._stop_continuous_listening()
            self._start_recording()
        else:
            self._stop_recording()
    
    def _on_toggle_continuous_listening(self, checked: bool):
        if checked:
            # Stop manual recording if active
            if self.is_recording:
                self.btn_record_audio.setChecked(False)
                self._stop_recording()
            self._start_continuous_listening()
        else:
            self._stop_continuous_listening()
    
    def _on_sensitivity_changed(self, value: int):
        old_threshold = self.voice_threshold
        self.voice_threshold = value
        # Update all UI elements immediately
        self.label_sensitivity.setText(str(value))
        self.threshold_indicator.setText(str(value))
        # Update custom widget threshold
        if hasattr(self, 'audio_level_widget'):
            self.audio_level_widget.set_threshold(value)
        # Force update the audio level bar to show new threshold (fallback)
        if hasattr(self, 'audio_level_bar'):
            self.audio_level_bar.setFormat(f"%v / {value}")
        log_msg = f"[VAD] Threshold alterado: {old_threshold} -> {value}"
        print(log_msg)
        self._append_vad_log(log_msg)
    
    def _on_silence_changed(self, value: int):
        self.silence_duration = value / 10.0  # Convert to seconds (5-50 = 0.5s-5.0s)
        self.label_silence.setText(f"{self.silence_duration:.1f}s")

    def _start_recording(self):
        self.is_recording = True
        self.audio_data = []
        self._recording_chunks_count = 0  # Counter for debugging
        self.btn_record_audio.setText("⏹ Parar Gravação")
        self.audio_status.setText("Gravando... (clique novamente para parar)")
        self.btn_send_audio.setEnabled(False)
        print(f"[Audio] 🎤 Iniciando gravação manual...")
        print(f"[Audio] Dispositivo de entrada: {self.audio_input_device if self.audio_input_device is not None else 'padrão'}")
        
        def record_thread():
            try:
                # Use specified input device or default
                if self.audio_input_device is not None:
                    print(f"[Audio] Gravando do dispositivo de entrada {self.audio_input_device}")
                    stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype=np.int16, 
                                          callback=self._audio_callback, device=self.audio_input_device)
                else:
                    print(f"[Audio] Gravando do dispositivo de entrada padrão")
                    stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype=np.int16, 
                                          callback=self._audio_callback)
                
                with stream:
                    print(f"[Audio] Stream de gravação ativo, aguardando dados...")
                    while self.is_recording:
                        time.sleep(0.1)
                    print(f"[Audio] Gravação parada. Total de chunks: {self._recording_chunks_count}")
            except Exception as e:
                error_msg = f"Erro na gravação: {e}"
                print(f"[Audio] ❌ {error_msg}")
                import traceback
                traceback.print_exc()
                QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText(error_msg))
        
        threading.Thread(target=record_thread, daemon=True).start()
    
    def _start_continuous_listening(self):
        """Start continuous listening with voice activity detection."""
        self.is_listening_continuously = True
        self.current_phrase_audio = []
        self.is_speaking = False
        self.silence_start_time = None
        self._callback_logged = False  # Reset callback log flag
        self.btn_listen_continuous.setText("👂 Escuta Ativa")
        self.btn_listen_continuous.setChecked(True)
        self.btn_stop_listening.setEnabled(True)
        self.audio_status.setText("Escutando... (fale para começar)")
        self.slider_sensitivity.setEnabled(True)
        self.slider_silence.setEnabled(True)
        self.voice_indicator.setText("🔇")
        if hasattr(self, 'audio_level_bar'):
            self.audio_level_bar.setValue(0)
        if hasattr(self, 'audio_level_widget'):
            self.audio_level_widget.set_level(0)
            self.audio_level_widget.set_threshold(self.voice_threshold)
        self.audio_level_label.setText("0")
        self.threshold_indicator.setText(str(self.voice_threshold))
        log_msg = f"[VAD] Escuta contínua iniciada - Threshold: {self.voice_threshold}"
        print(log_msg)
        self._append_vad_log(log_msg)
        
        def listen_thread():
            try:
                print(f"[VAD] Iniciando stream de áudio (sr={self.sample_rate}, channels=1)")
                print(f"[VAD] Verificando dispositivos de entrada disponíveis...")
                devices = sd.query_devices()
                default_input = sd.query_devices(kind='input')
                print(f"[VAD] Dispositivo padrão de entrada: {default_input['name']}")
                
                # Use specified input device or default
                if self.audio_input_device is not None:
                    print(f"[VAD] Usando dispositivo de entrada {self.audio_input_device}")
                    self.continuous_stream = sd.InputStream(
                        samplerate=self.sample_rate, 
                        channels=1, 
                        dtype=np.int16, 
                        callback=self._audio_callback,
                        blocksize=1024,
                        device=self.audio_input_device
                    )
                else:
                    print(f"[VAD] Usando dispositivo de entrada padrão")
                    self.continuous_stream = sd.InputStream(
                        samplerate=self.sample_rate, 
                        channels=1, 
                        dtype=np.int16, 
                        callback=self._audio_callback,
                        blocksize=1024
                    )
                print(f"[VAD] Stream criado, iniciando captura...")
                with self.continuous_stream:
                    print(f"[VAD] ✅ Stream ativo! Callback deve ser chamado agora.")
                    callback_count = 0
                    while self.is_listening_continuously:
                        time.sleep(0.1)
                        # Log every 5 seconds to confirm it's running
                        callback_count += 1
                        if callback_count % 50 == 0:  # ~5 seconds
                            print(f"[VAD] Stream ainda ativo (aguardando callback)...")
            except Exception as e:
                error_msg = f"Erro na escuta: {e}"
                print(f"[VAD] ❌ {error_msg}")
                import traceback
                traceback.print_exc()
                QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText(error_msg))
        
        threading.Thread(target=listen_thread, daemon=True).start()
    
    def _stop_continuous_listening(self):
        """Stop continuous listening."""
        self.is_listening_continuously = False
        self.is_speaking = False
        self.current_phrase_audio = []
        self.silence_start_time = None
        self.btn_listen_continuous.setText("👂 Escuta Contínua")
        self.btn_listen_continuous.setChecked(False)
        self.btn_stop_listening.setEnabled(False)
        self.audio_status.setText("Escuta contínua parada")
        self.slider_sensitivity.setEnabled(False)
        self.slider_silence.setEnabled(False)
        self.voice_indicator.setText("🔇")
        if hasattr(self, 'audio_level_bar'):
            self.audio_level_bar.setValue(0)
        if hasattr(self, 'audio_level_widget'):
            self.audio_level_widget.set_level(0)
        self.audio_level_label.setText("0")
        print(f"[VAD] Escuta contínua parada")
        if self.continuous_stream:
            self.continuous_stream.close()
            self.continuous_stream = None
    
    def _on_stop_listening(self):
        """Handle stop listening button click."""
        if self.is_listening_continuously:
            self._stop_continuous_listening()
    
    def _auto_send_phrase(self):
        """Automatically send the detected phrase."""
        # Make a copy of phrase audio to avoid race conditions
        if not self.current_phrase_audio:
            return
        
        # Check if still listening (might have been stopped)
        if not self.is_listening_continuously:
            print("[VAD] Escuta parada, cancelando envio automático")
            return
        
        try:
            # Make a copy to avoid issues if callback modifies it
            phrase_audio_copy = list(self.current_phrase_audio)
            
            if not phrase_audio_copy:
                return
            
            # Concatenate audio
            audio_array = np.concatenate(phrase_audio_copy, axis=0)
            duration = len(audio_array) / self.sample_rate
            
            # Only send if duration is reasonable (at least 0.5 seconds)
            if duration < 0.5:
                QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText("Frase muito curta, ignorando..."))
                self.current_phrase_audio = []
                return
            
            # Update UI in main thread
            QtCore.QTimer.singleShot(0, lambda d=duration: self.audio_status.setText(f"Enviando frase ({d:.1f}s)..."))
            QtCore.QTimer.singleShot(0, lambda d=duration: self.chat_history.appendPlainText(f"Você: [Áudio - {d:.1f}s]"))
            
            # Convert to bytes and encode
            audio_bytes = audio_array.tobytes()
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Send to server in a separate thread to avoid blocking
            def send_thread():
                try:
                    host = self.host.text().strip() or "127.0.0.1"
                    port = self.port.value()
                    url = f"http://{host}:{port}/api/context/conversation/audio"
                    
                    payload = {
                        "user": "Usuario",
                        "timestamp": int(time.time()),
                        "audio_bytes": audio_b64,
                        "sr": self.sample_rate,
                        "sw": 2,
                        "ch": 1
                    }
                    
                    r = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=30)
                    
                    # Update UI in main thread
                    if r.ok:
                        response_data = r.json()
                        job_id = response_data.get("response", {}).get("job_id", "desconhecido")
                        QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText(f"Áudio enviado! Aguardando resposta..."))
                        QtCore.QTimer.singleShot(0, lambda: self._append_server_log(f"Áudio automático enviado ({duration:.1f}s) -> job_id: {job_id}"))
                        
                        # Request response
                        QtCore.QTimer.singleShot(0, self._request_response)
                    else:
                        error_text = r.text[:200] if r.text else "Sem detalhes"
                        QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText(f"Erro ao enviar: {r.status_code}"))
                        QtCore.QTimer.singleShot(0, lambda: self.chat_history.appendPlainText(f"Erro ({r.status_code}): {error_text}"))
                    
                    # Clear phrase in main thread
                    QtCore.QTimer.singleShot(0, lambda: setattr(self, 'current_phrase_audio', []))
                except Exception as e:
                    error_msg = str(e)
                    print(f"[VAD] Erro ao enviar frase: {error_msg}")
                    import traceback
                    traceback.print_exc()
                    QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText(f"Erro: {error_msg}"))
                    QtCore.QTimer.singleShot(0, lambda: self.chat_history.appendPlainText(f"Falha ao enviar frase: {error_msg}"))
                    QtCore.QTimer.singleShot(0, lambda: setattr(self, 'current_phrase_audio', []))
            
            threading.Thread(target=send_thread, daemon=True).start()
            
        except Exception as e:
            error_msg = str(e)
            print(f"[VAD] Erro em _auto_send_phrase: {error_msg}")
            import traceback
            traceback.print_exc()
            QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText(f"Erro: {error_msg}"))
            QtCore.QTimer.singleShot(0, lambda: self.chat_history.appendPlainText(f"Falha ao processar frase: {error_msg}"))
            self.current_phrase_audio = []

    def _audio_callback(self, indata, frames, time_info, status):
        # Log first callback to confirm it's working
        if not hasattr(self, '_callback_logged'):
            log_msg = "[VAD] ✅ Callback de áudio está funcionando! Recebendo dados..."
            print(log_msg)
            self._append_vad_log(log_msg)
            self._callback_logged = True
        
        if status:
            print(f"[VAD] Status do áudio: {status}")
        
        # Handle manual recording
        if self.is_recording:
            chunk = indata.copy()
            self.audio_data.append(chunk)
            self._recording_chunks_count = getattr(self, '_recording_chunks_count', 0) + 1
            # Log first few chunks to confirm it's working
            if self._recording_chunks_count <= 3:
                print(f"[Audio] Chunk #{self._recording_chunks_count} recebido: {len(chunk)} frames")
        
        # Handle continuous listening with VAD
        if self.is_listening_continuously:
            audio_chunk = indata.copy()
            
            # Calculate RMS (Root Mean Square) for voice detection
            # Convert to float32 to avoid overflow, then calculate RMS
            audio_float = audio_chunk.astype(np.float32)
            rms = np.sqrt(np.mean(audio_float**2))
            
            # Update audio level indicator (throttle updates to avoid UI lag)
            rms_int = int(rms)
            QtCore.QTimer.singleShot(0, lambda r=rms_int, t=self.voice_threshold: self._update_audio_level(r, t))
            
            # Debug: log RMS values occasionally
            if not hasattr(self, '_last_rms_log_time'):
                self._last_rms_log_time = 0
            current_time = time.time()
            if current_time - self._last_rms_log_time > 2.0:  # Log every 2 seconds
                log_msg = f"[VAD] RMS: {rms:.1f}, Threshold: {self.voice_threshold}, Detecção: {'✅ SIM' if rms > self.voice_threshold else '❌ NÃO'}"
                print(log_msg)
                self._append_vad_log(log_msg)
                self._last_rms_log_time = current_time
            
            # Check if voice is detected
            if rms > self.voice_threshold:
                # Voice detected
                if not self.is_speaking:
                    self.is_speaking = True
                    self.silence_start_time = None
                    self.current_phrase_audio = []
                    log_msg = f"[VAD] 🎤 Voz detectada! RMS: {rms:.1f} > Threshold: {self.voice_threshold}"
                    print(log_msg)
                    self._append_vad_log(log_msg)
                    QtCore.QTimer.singleShot(0, lambda: self.voice_indicator.setText("🎤"))
                    QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText("Falando..."))
                
                # Add to current phrase
                self.current_phrase_audio.append(audio_chunk)
            else:
                # Silence detected
                if self.is_speaking:
                    # We were speaking, now silence
                    if self.silence_start_time is None:
                        self.silence_start_time = time.time()
                        log_msg = f"[VAD] 🔇 Silêncio detectado após falar. RMS: {rms:.1f} <= Threshold: {self.voice_threshold}"
                        print(log_msg)
                        self._append_vad_log(log_msg)
                        QtCore.QTimer.singleShot(0, lambda: self.voice_indicator.setText("🔇"))
                        QtCore.QTimer.singleShot(0, lambda: self.audio_status.setText("Silêncio detectado, aguardando..."))
                    
                    # Check if silence duration exceeded threshold
                    silence_duration = time.time() - self.silence_start_time
                    if silence_duration >= self.silence_duration:
                        # Auto-send the phrase (only if we still have audio and are still listening)
                        if self.current_phrase_audio and self.is_listening_continuously:
                            log_msg = f"[VAD] ⏱️ Silêncio de {silence_duration:.1f}s excedeu threshold de {self.silence_duration:.1f}s. Enviando frase..."
                            print(log_msg)
                            self._append_vad_log(log_msg)
                            # Schedule in main thread to avoid race conditions
                            QtCore.QTimer.singleShot(0, self._auto_send_phrase)
                            # Reset state after scheduling send
                            self.is_speaking = False
                            self.silence_start_time = None
                            # Don't clear current_phrase_audio here - let _auto_send_phrase handle it
                else:
                    # Not speaking, show idle (only update occasionally to reduce spam)
                    pass  # Don't update UI constantly when idle
    
    def _update_audio_level(self, rms_value: int, threshold: int = None):
        """Update audio level indicator in UI thread."""
        if not self.is_listening_continuously:
            return
        
        # Use provided threshold or current threshold
        if threshold is None:
            threshold = self.voice_threshold
        
        # Update custom widget if it exists
        if hasattr(self, 'audio_level_widget'):
            self.audio_level_widget.set_level(rms_value)
            self.audio_level_widget.set_threshold(threshold)
        
        # Update progress bar (scale to max 2000 for display) - fallback if custom widget doesn't exist
        if hasattr(self, 'audio_level_bar'):
            display_value = min(rms_value, 2000)
            threshold_display = min(threshold, 2000)
            self.audio_level_bar.setValue(display_value)
            
            # Change color based on threshold
            if rms_value > threshold:
                # Voice detected - green (above threshold)
                style = """
                QProgressBar {
                    border: 1px solid #333;
                    border-radius: 3px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #4CAF50;
                    border-radius: 2px;
                }
                """
                self.audio_level_bar.setStyleSheet(style)
            else:
                # Silence - gray (below threshold)
                style = """
                QProgressBar {
                    border: 1px solid #333;
                    border-radius: 3px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #9E9E9E;
                    border-radius: 2px;
                }
                """
                self.audio_level_bar.setStyleSheet(style)
            
            self.audio_level_bar.setFormat(f"{rms_value} / {threshold}")
        
        # Update labels
        self.audio_level_label.setText(str(rms_value))
        self.threshold_indicator.setText(str(threshold))

    def _stop_recording(self):
        print(f"[Audio] Parando gravação...")
        self.is_recording = False
        
        # Wait a bit for any remaining callbacks to finish
        time.sleep(0.2)
        
        self.btn_record_audio.setChecked(False)
        self.btn_record_audio.setText("🎤 Gravar Áudio")
        
        chunks_count = len(self.audio_data) if self.audio_data else 0
        print(f"[Audio] Gravação parada. Chunks coletados: {chunks_count}")
        
        if self.audio_data and len(self.audio_data) > 0:
            try:
                audio_array = np.concatenate(self.audio_data, axis=0)
                duration = len(audio_array) / self.sample_rate
                total_samples = len(audio_array)
                print(f"[Audio] ✅ Áudio gravado: {total_samples} amostras, {duration:.2f}s de duração")
                print(f"[Audio] ✅ Gravação concluída: {duration:.1f}s ({total_samples} amostras)")
                self.audio_status.setText(f"Gravação concluída ({duration:.1f}s). Clique em 'Testar Áudio' ou 'Enviar Áudio'.")
                self.btn_send_audio.setEnabled(True)
                self.btn_test_audio.setEnabled(True)
            except Exception as e:
                error_msg = f"Erro ao processar áudio gravado: {e}"
                print(f"[Audio] ❌ {error_msg}")
                self.audio_status.setText("Erro ao processar áudio gravado")
                self.btn_send_audio.setEnabled(False)
                self.btn_test_audio.setEnabled(False)
        else:
            error_msg = f"Nenhum áudio gravado (chunks: {chunks_count})"
            print(f"[Audio] ❌ {error_msg}")
            print("[Audio] Dica: Verifique se o microfone está funcionando e selecionado corretamente")
            self.audio_status.setText("Nenhum áudio gravado")
            self.btn_send_audio.setEnabled(False)
            self.btn_test_audio.setEnabled(False)

    def _on_send_audio(self):
        if not self.audio_data:
            print("[Audio] Erro: Nenhum áudio gravado")
            self.audio_status.setText("Erro: Nenhum áudio gravado")
            return
        
        host = self.host.text().strip() or "127.0.0.1"
        port = self.port.value()
        url = f"http://{host}:{port}/api/context/conversation/audio"
        
        try:
            # Convert audio to bytes
            audio_array = np.concatenate(self.audio_data, axis=0)
            audio_bytes = audio_array.tobytes()
            
            # Encode to base64
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Prepare payload
            payload = {
                "user": "Usuario",
                "timestamp": int(time.time()),
                "audio_bytes": audio_b64,
                "sr": self.sample_rate,  # sample rate
                "sw": 2,  # sample width (bytes per sample, int16 = 2)
                "ch": 1   # channels (mono)
            }
            
            self.chat_history.appendPlainText("Você: [Áudio enviado]")
            self.audio_status.setText("Enviando áudio...")
            self.btn_send_audio.setEnabled(False)
            
            r = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=30)
            
            if r.ok:
                response_data = r.json()
                job_id = response_data.get("response", {}).get("job_id", "desconhecido")
                print("[Chat] Áudio enviado. Gerando resposta...")
                self.audio_status.setText("Áudio enviado com sucesso!")
                self._append_server_log(f"Áudio enviado -> job_id: {job_id}")
                
                # Request response after adding audio to context
                self._request_response()
            else:
                self.chat_history.appendPlainText(f"Erro ({r.status_code}): {r.text[:500]}")
                self.audio_status.setText(f"Erro ao enviar: {r.status_code}")
            
            # Clear audio data
            self.audio_data = None
            self.btn_send_audio.setEnabled(False)
            
        except Exception as e:
            self.chat_history.appendPlainText(f"Falha ao enviar áudio: {e}")
            self.audio_status.setText(f"Erro: {e}")
            self.btn_send_audio.setEnabled(False)

