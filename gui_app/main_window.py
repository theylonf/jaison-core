"""Main window for JAIson GUI application."""

import time
import re
import threading
from pathlib import Path

import requests
import numpy as np
from PySide6 import QtCore, QtWidgets, QtGui

try:
    from .constants import JAISON_DIR
    from .server_manager import ServerManager
    from .chat_handler import ChatHandler
    from .ui.controls_tab import ControlsTab
    from .ui.chat_tab import ChatTab
    from .audio.vad_handler import VADHandler
    from .audio.recorder import AudioRecorder
    from .audio.player import AudioPlayer
    from .audio.device_manager import AudioDeviceManager
except ImportError:
    from constants import JAISON_DIR
    from server_manager import ServerManager
    from chat_handler import ChatHandler
    from ui.controls_tab import ControlsTab
    from ui.chat_tab import ChatTab
    from audio.vad_handler import VADHandler
    from audio.recorder import AudioRecorder
    from audio.player import AudioPlayer
    from audio.device_manager import AudioDeviceManager


class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""
    
    rms_update_signal = QtCore.Signal(int, int)
    voice_detected_signal = QtCore.Signal()
    silence_detected_signal = QtCore.Signal()
    auto_send_triggered_signal = QtCore.Signal()
    request_response_signal = QtCore.Signal()
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("JAIson - Launcher & Chat")
        self.resize(900, 650)
        
        self.sample_rate = 16000
        
        self.server_manager = ServerManager()
        self.chat_handler = ChatHandler()
        self.vad_handler = VADHandler(self.sample_rate)
        self.audio_recorder = AudioRecorder(self.sample_rate)
        self.audio_player = AudioPlayer()
        self.device_manager = AudioDeviceManager()
        
        self._setup_managers()
        self._build_ui()
        self._wire_events()
        
        self.server_manager.start_log_readers()
        QtCore.QTimer.singleShot(2000, self._check_and_start_listener)
    
    def _setup_managers(self):
        """Setup callbacks for managers."""
        self.server_manager.setup_log_connections(
            self._append_server_log,
            self._append_plugin_log
        )
        
        self.chat_handler.on_text_received = self._on_received_text
        self.chat_handler.on_image_received = self._on_received_image
        self.chat_handler.on_audio_received = self._on_audio_received
        self.chat_handler.on_audio_chunk_received = self._on_audio_chunk
        self.chat_handler.on_audio_complete = self._on_audio_complete
        self.chat_handler.on_error_received = self._on_received_error
        self.chat_handler.on_log = self._append_server_log
        
        self.vad_handler.on_voice_detected = lambda: self.voice_detected_signal.emit()
        self.vad_handler.on_silence_detected = lambda: self.silence_detected_signal.emit()
        self.vad_handler.on_phrase_ready = lambda: self.auto_send_triggered_signal.emit()
        self.vad_handler.on_audio_level_update = lambda rms, th: self.rms_update_signal.emit(rms, th)
        self.vad_handler.on_log = self._append_vad_log
        
        self.audio_recorder.on_log = self._append_vad_log
        self.audio_player.on_log = self._append_vad_log
        
        self.rms_update_signal.connect(self._update_audio_level)
        self.voice_detected_signal.connect(self._on_voice_detected)
        self.silence_detected_signal.connect(self._on_silence_detected)
        self.auto_send_triggered_signal.connect(self._auto_send_phrase)
        self.request_response_signal.connect(self._request_response)
    
    def _build_ui(self):
        """Build the UI."""
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)
        
        self.controls_tab = ControlsTab()
        self.chat_tab = ChatTab()
        
        self.tabs.addTab(self.controls_tab, "Controles")
        self.tabs.addTab(self.chat_tab, "Chat")
        
        # Load default user context from file
        self._load_user_context_file()
    
    def _wire_events(self):
        """Wire UI events to handlers."""
        self.controls_tab.btn_start_server.clicked.connect(self._on_start_server)
        self.controls_tab.btn_stop_server.clicked.connect(self._on_stop_server)
        self.controls_tab.btn_start_plugin.clicked.connect(self._on_start_plugin)
        self.controls_tab.btn_stop_plugin.clicked.connect(self._on_stop_plugin)
        self.controls_tab.btn_clear_server_log.clicked.connect(lambda: self.controls_tab.server_log.clear())
        self.controls_tab.btn_clear_plugin_log.clicked.connect(lambda: self.controls_tab.plugin_log.clear())
        self.controls_tab.btn_update_user_context.clicked.connect(self._on_update_user_context)
        
        self.chat_tab.btn_send_text.clicked.connect(self._on_send_text)
        self.chat_tab.input_text.returnPressed.connect(self._on_send_text)
        self.chat_tab.btn_record_audio.clicked.connect(self._on_toggle_record)
        self.chat_tab.btn_listen_continuous.clicked.connect(self._on_toggle_continuous_listening)
        self.chat_tab.btn_stop_listening.clicked.connect(self._on_stop_listening)
        self.chat_tab.btn_test_audio.clicked.connect(self._on_test_audio)
        self.chat_tab.btn_send_audio.clicked.connect(self._on_send_audio)
        self.chat_tab.btn_play_last_audio.clicked.connect(self._on_play_last_audio)
        self.chat_tab.btn_select_audio_output.clicked.connect(self._on_select_audio_output)
        self.chat_tab.btn_select_audio_input.clicked.connect(self._on_select_audio_input)
        self.chat_tab.btn_clear_chat.clicked.connect(lambda: self.chat_tab.chat_history.clear())
        
        self.chat_tab.slider_sensitivity.valueChanged.connect(self._on_sensitivity_changed)
        self.chat_tab.slider_silence.valueChanged.connect(self._on_silence_changed)
    
    def closeEvent(self, event):
        """Handle window close event."""
        try:
            self.server_manager.stop_log_readers()
            if self.chat_handler.audio_listener:
                self.chat_handler.stop_audio_listener()
            if self.vad_handler.is_listening_continuously:
                self.vad_handler.stop_listening()
            if self.audio_recorder.is_recording:
                self.audio_recorder.stop_recording()
            self.server_manager.stop_server()
            self.server_manager.stop_plugin()
        finally:
            return super().closeEvent(event)
    
    def _append_chat_message(self, text: str, is_html: bool = False):
        """Append message to chat history (supports plain text and HTML)."""
        if is_html:
            self.chat_tab.chat_history.append(text)
        else:
            # Escape HTML special characters for plain text
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            self.chat_tab.chat_history.append(escaped_text)
        # Auto-scroll to bottom
        scrollbar = self.chat_tab.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _append_server_log(self, line: str):
        """Append log to server log widget."""
        print(f"[Server] {line}")
        self.controls_tab.server_log.appendPlainText(line)
    
    def _append_plugin_log(self, line: str):
        """Append log to plugin log widget."""
        print(f"[Plugin] {line}")
        self.controls_tab.plugin_log.appendPlainText(line)
    
    def _append_vad_log(self, line: str):
        """Append VAD log to terminal."""
        print(line)
    
    def _on_start_server(self):
        """Handle start server button click."""
        if self.server_manager.is_server_running():
            return
        
        config_name = self.controls_tab.config_name.text().strip() or "sammy"
        success = self.server_manager.start_server(config_name, self)
        
        if success:
            QtCore.QTimer.singleShot(3000, self._start_audio_listener)
    
    def _on_stop_server(self):
        """Handle stop server button click."""
        if self.chat_handler.audio_listener:
            self.chat_handler.stop_audio_listener()
        self.server_manager.stop_server()
    
    def _on_update_user_context(self):
        """Handle update user context button click."""
        if not self.server_manager.is_server_running():
            self.controls_tab.server_log.appendPlainText("Erro: Servidor não está rodando. Inicie o servidor primeiro.")
            return
        
        user_context = self.controls_tab.user_context.toPlainText().strip()
        
        host = self.controls_tab.host.text().strip() or "127.0.0.1"
        port = self.controls_tab.port.value()
        self.chat_handler.set_host_port(host, port)
        
        success, result = self.chat_handler.update_user_context(user_context)
        
        if success:
            job_id = result
            self.controls_tab.server_log.appendPlainText(f"Contexto do usuário atualizado -> job_id: {job_id}")
            self._append_chat_message(f"[Sistema] Contexto do usuário atualizado com sucesso!")
        else:
            error_msg = result
            self.controls_tab.server_log.appendPlainText(f"Erro ao atualizar contexto: {error_msg}")
            self._append_chat_message(f"[Sistema] Erro ao atualizar contexto: {error_msg}")
    
    def _load_user_context_file(self):
        """Load user context from file into the UI."""
        try:
            user_context_path = Path(JAISON_DIR) / "prompts" / "user_context.txt"
            if user_context_path.exists():
                with open(user_context_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if hasattr(self.controls_tab, 'user_context'):
                        self.controls_tab.user_context.setPlainText(content)
        except Exception as e:
            # Se não conseguir carregar, deixa vazio
            pass
    
    def _check_server_running(self) -> bool:
        """Check if server is actually running."""
        host = self.controls_tab.host.text().strip() or "127.0.0.1"
        port = self.controls_tab.port.value()
        url = f"http://{host}:{port}/"
        
        try:
            response = requests.get(url, timeout=1)
            return True
        except Exception:
            return False
    
    def _check_and_start_listener(self):
        """Check if server is running and start listener if needed."""
        process_running = self.server_manager.is_server_running()
        server_accessible = self._check_server_running()
        
        if process_running or server_accessible:
            self._start_audio_listener()
    
    def _start_audio_listener(self):
        """Start listening to websocket for audio responses."""
        if self.chat_handler.audio_listener and self.chat_handler.audio_listener.isRunning():
            self.chat_handler.stop_audio_listener()
        
        host = self.controls_tab.host.text().strip() or "127.0.0.1"
        port = self.controls_tab.port.value()
        self.chat_handler.set_host_port(host, port)
        
        process_running = self.server_manager.is_server_running()
        server_accessible = self._check_server_running()
        
        if not process_running and not server_accessible:
            QtCore.QTimer.singleShot(2000, self._start_audio_listener)
            return
        
        try:
            self.chat_handler.start_audio_listener()
        except Exception as e:
            print(f"[WebSocket] ❌ Erro ao iniciar listener: {e}")
    
    def _on_audio_chunk(self, audio_b64_chunk: str, sr: int, sw: int, ch: int):
        """Handle audio chunk received from server."""
        pass
    
    def _on_audio_complete(self, sr: int, sw: int, ch: int):
        """Handle audio completion signal - monta e reproduz áudio automaticamente."""
        print(f"[Audio] ✅ Sinal audio_complete recebido (sr={sr}, sw={sw}, ch={ch})")
        print(f"[Audio] Buffer tem {len(self.chat_handler.audio_chunks_buffer)} chunks antes de montar")
        audio_bytes, sr, sw, ch = self.chat_handler.assemble_audio_chunks()
        if audio_bytes:
            duration = len(audio_bytes) / (sr * sw * ch) if sr and sw and ch else 0
            print(f"[Audio] ✅ Montando e reproduzindo áudio automaticamente ({len(audio_bytes)} bytes, {duration:.2f}s, sr={sr}, sw={sw}, ch={ch})")
            self._assemble_and_play_audio(audio_bytes, sr, sw, ch)
        else:
            print("[Audio] ⚠️ Nenhum áudio para montar após sinal de conclusão (buffer vazio)")
    
    def _try_assemble_audio_on_text(self):
        """Try to assemble audio when text is received (fallback se audio_complete não foi emitido)."""
        print(f"[Audio] _try_assemble_audio_on_text: buffer tem {len(self.chat_handler.audio_chunks_buffer)} chunks")
        audio_bytes, sr, sw, ch = self.chat_handler.assemble_audio_chunks()
        if audio_bytes:
            duration = len(audio_bytes) / (sr * sw * ch) if sr and sw and ch else 0
            print(f"[Audio] ✅ Montando e reproduzindo áudio via fallback ({len(audio_bytes)} bytes, {duration:.2f}s, sr={sr}, sw={sw}, ch={ch})")
            self._assemble_and_play_audio(audio_bytes, sr, sw, ch)
        else:
            print("[Audio] ⚠️ Nenhum áudio para montar no fallback (buffer vazio ou já foi montado)")
    
    def _assemble_and_play_audio(self, audio_bytes: bytes, sr: int, sw: int, ch: int):
        """Assemble audio chunks and play."""
        try:
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            if ch == 2:
                audio_array = audio_array.reshape(-1, 2)
            
            self.audio_player.store_last_audio(audio_array, sr, sw, ch)
            self.chat_tab.btn_play_last_audio.setEnabled(True)
            
            # Se já está tocando um áudio, aguarda ou enfileira
            # Por enquanto, vamos pausar a escuta se ainda não estiver pausada
            # e garantir que apenas um áudio toque por vez
            if not self.vad_handler.is_playing_ai_audio:
                self.vad_handler.is_playing_ai_audio = True
                if self.vad_handler.is_listening_continuously:
                    # Se a escuta já estava pausada (por causa do envio), mantém pausada
                    # Se não estava pausada, pausa agora
                    if not self.vad_handler._was_listening_before_playback:
                        self.vad_handler._was_listening_before_playback = True
                        self.vad_handler.pause_listener()
            else:
                # Se já está tocando, aguarda o áudio atual terminar
                # Por enquanto, vamos tocar o novo áudio (pode sobrepor)
                # TODO: Implementar fila de áudios no futuro
                print("[Audio] ⚠️ Novo áudio recebido enquanto outro está tocando")
                self._append_server_log("[Audio] ⚠️ Novo áudio recebido enquanto outro está tocando")
            
            def on_playback_complete():
                # Retoma a escuta quando o áudio terminar
                if self.vad_handler._was_listening_before_playback:
                    self.vad_handler.is_playing_ai_audio = False
                    self.vad_handler.resume_listener()
                    self.vad_handler._was_listening_before_playback = False
            
            self.audio_player.play_audio_bytes(audio_bytes, sr, sw, ch, on_playback_complete)
        except Exception as e:
            print(f"[Audio] ❌ Erro ao montar áudio: {e}")
            self.chat_tab.audio_status.setText(f"Erro: {e}")
            # Em caso de erro, retoma a escuta
            if self.vad_handler._was_listening_before_playback:
                self.vad_handler.is_playing_ai_audio = False
                self.vad_handler._was_listening_before_playback = False
                self.vad_handler.resume_listener()
    
    def _on_audio_received(self, audio_bytes: bytes, sr: int, sw: int, ch: int):
        """Handle complete audio received."""
        self._assemble_and_play_audio(audio_bytes, sr, sw, ch)
    
    def _on_test_audio(self):
        """Test/playback the recorded audio before sending."""
        if not hasattr(self.audio_recorder, 'recorded_audio') or self.audio_recorder.recorded_audio is None:
            self.chat_tab.audio_status.setText("Erro: Nenhum áudio gravado para testar")
            return
        
        audio_array = self.audio_recorder.recorded_audio
        duration = len(audio_array) / self.sample_rate
        self.chat_tab.audio_status.setText(f"Reproduzindo áudio gravado ({duration:.1f}s)...")
        self.audio_player.play_audio(audio_array, self.sample_rate)
        QtCore.QTimer.singleShot(int(duration * 1000) + 500, 
                                 lambda: self.chat_tab.audio_status.setText("Áudio testado. Pronto para enviar."))
    
    def _on_play_last_audio(self):
        """Play the last audio received from AI."""
        self.audio_player.play_last_audio()
        self._append_chat_message("Reproduzindo último áudio da IA...")
    
    def _on_select_audio_output(self):
        """Open dialog to select audio output device."""
        if self.device_manager.select_output_device(self):
            device_name = self.device_manager.get_output_device_name()
            self._append_chat_message(f"Dispositivo de saída selecionado: {device_name}")
            self.audio_player.audio_output_device = self.device_manager.audio_output_device
        else:
            self._append_chat_message("Nenhum dispositivo selecionado")
    
    def _on_select_audio_input(self):
        """Open dialog to select audio input device."""
        if self.device_manager.select_input_device(self):
            device_name = self.device_manager.get_input_device_name()
            self._append_chat_message(f"Dispositivo de entrada selecionado: {device_name}")
            self.vad_handler.audio_input_device = self.device_manager.audio_input_device
            self.audio_recorder.audio_input_device = self.device_manager.audio_input_device
        else:
            self._append_chat_message("Nenhum dispositivo selecionado")
    
    def _on_received_image(self, image_bytes_b64: str, user_name: str, image_format: str, error: str = None):
        """Handle image received from server (screenshot from vision)."""
        import base64
        
        print(f"[DEBUG] _on_received_image chamado: image_bytes_b64 length={len(image_bytes_b64) if image_bytes_b64 else 0}, error={error}, format={image_format}")
        
        # Se houve erro na captura
        if error or not image_bytes_b64 or image_bytes_b64.strip() == "":
            error_msg = error or "Falha ao capturar screenshot"
            self._append_chat_message(f"[Sistema] Erro ao capturar screenshot: {error_msg}")
            if not error or "pyautogui" in error.lower():
                self._append_chat_message(f"[Sistema] Instale pyautogui: pip install pyautogui")
            return
        
        try:
            # Decode base64 image
            image_bytes = base64.b64decode(image_bytes_b64)
            
            # Create QPixmap from image bytes
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(image_bytes, image_format.upper())
            
            if pixmap.isNull():
                self._append_chat_message(f"[Sistema] Screenshot capturado (formato: {image_format}) - Erro ao decodificar imagem")
                return
            
            # Resize if too large (max 400px width, maintain aspect ratio)
            original_width = pixmap.width()
            original_height = pixmap.height()
            if pixmap.width() > 400:
                pixmap = pixmap.scaledToWidth(400, QtCore.Qt.TransformationMode.SmoothTransformation)
            
            # Convert pixmap to base64 data URI for HTML embedding
            # Use QBuffer to convert QPixmap to bytes
            byte_array = QtCore.QByteArray()
            buffer = QtCore.QBuffer(byte_array)
            buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
            # Save pixmap to buffer in the specified format
            pixmap.save(buffer, image_format.upper())
            buffer.close()
            
            # Create data URI from buffer bytes
            image_base64 = base64.b64encode(byte_array.data()).decode('utf-8')
            mime_type = f"image/{image_format.lower()}"
            data_uri = f"data:{mime_type};base64,{image_base64}"
            
            # Create HTML with embedded image
            image_html = f'<div style="margin: 5px 0;"><img src="{data_uri}" style="max-width: 400px; border: 1px solid #ccc; border-radius: 4px;" alt="Screenshot {original_width}x{original_height}px" /></div>'
            
            # Add to chat history with HTML
            self._append_chat_message(image_html, is_html=True)
            
            # Store image for potential future use (e.g., popup viewer)
            if not hasattr(self, '_last_screenshot'):
                self._last_screenshot = {}
            self._last_screenshot = {
                'pixmap': pixmap,
                'format': image_format,
                'user': user_name
            }
            
        except Exception as e:
            print(f"Erro ao processar imagem recebida: {e}")
            import traceback
            traceback.print_exc()
            self._append_chat_message(f"[Sistema] Screenshot capturado (erro ao exibir: {e})")
    
    def _on_received_text(self, text: str, user_name: str = ""):
        """Handle text received from server."""
        if not text.strip():
            return
        
        # Se user_name está vazio ou é None, assume que é da IA
        # Se user_name está presente, usa ele (pode ser "Usuario", "Você", etc.)
        if user_name and user_name.strip():
            display_name = user_name
        else:
            # Se não tem user_name, é resposta da IA
            try:
                from utils.prompter.prompter import Prompter
                prompter = Prompter()
                if prompter.character_name:
                    display_name = prompter.character_name
                else:
                    display_name = self.controls_tab.config_name.text().strip() if hasattr(self.controls_tab, 'config_name') else "Ana"
            except:
                display_name = self.controls_tab.config_name.text().strip() if hasattr(self.controls_tab, 'config_name') else "Ana"
        
        if not display_name:
            display_name = "Ana"
        
        self._append_chat_message(f"{display_name}: {text}")
        
        emotions = re.findall(r'\[([^\]]+)\]', text)
        
        # Se há chunks de áudio no buffer, monta e reproduz automaticamente
        # Isso funciona como fallback caso o sinal audio_complete não seja emitido
        if self.chat_handler.audio_chunks_buffer:
            print(f"[Audio] Texto recebido e há {len(self.chat_handler.audio_chunks_buffer)} chunks no buffer, montando áudio em 1s...")
            QtCore.QTimer.singleShot(1000, self._try_assemble_audio_on_text)
    
    def _on_received_error(self, error_msg: str):
        """Handle error received from server via WebSocket."""
        error_display = f"❌ Erro do servidor: {error_msg}"
        print(f"[WebSocket] {error_display}")
        self._append_chat_message(error_display)
        
        # IMPORTANTE: Retoma a escuta em caso de erro
        # Isso garante que o usuário possa falar novamente mesmo se houver erro
        if self.vad_handler._was_listening_before_playback:
            self.vad_handler.is_playing_ai_audio = False
            self.vad_handler._was_listening_before_playback = False
            self.vad_handler.resume_listener()
        
        if "API key" in error_msg or "401" in error_msg or "authentication" in error_msg.lower():
            self._append_chat_message("💡 Dica: Verifique se a API key da OpenAI está configurada corretamente no servidor")
    
    def _request_response(self):
        """Request a response from the server after adding context."""
        host = self.controls_tab.host.text().strip() or "127.0.0.1"
        port = self.controls_tab.port.value()
        self.chat_handler.set_host_port(host, port)
        
        success, result = self.chat_handler.request_response(include_audio=True)
        if success:
            job_id = result
            self._append_server_log(f"Resposta solicitada -> job_id: {job_id}")
            # IMPORTANTE: Configurar timeout para retomar escuta se áudio não chegar
            # Isso evita que a escuta fique pausada permanentemente se:
            # 1. O job de resposta falhar silenciosamente
            # 2. A conexão WebSocket fechar antes de completar
            # 3. O servidor não enviar finished=True
            # 4. Qualquer outro problema que impeça a resposta completa
            def timeout_resume():
                if self.vad_handler._was_listening_before_playback and not self.vad_handler.is_playing_ai_audio:
                    print("[VAD] ⏱️ Timeout: Nenhum áudio recebido após 30s, retomando escuta")
                    self._append_server_log("[VAD] ⏱️ Timeout: Nenhum áudio recebido após 30s, retomando escuta")
                    self.vad_handler._was_listening_before_playback = False
                    self.vad_handler.resume_listener()
            QtCore.QTimer.singleShot(30000, timeout_resume)  # 30 segundos
        else:
            error_msg = result
            print(f"[VAD] ❌ Erro ao solicitar resposta: {error_msg}")
            self._append_chat_message(f"Erro ao solicitar resposta: {error_msg}")
            # Retoma escuta em caso de erro ao solicitar resposta
            if self.vad_handler._was_listening_before_playback:
                self.vad_handler._was_listening_before_playback = False
                self.vad_handler.resume_listener()
    
    def _on_start_plugin(self):
        """Handle start plugin button click."""
        if self.server_manager.is_plugin_running():
            return
        self.server_manager.start_plugin(self)
    
    def _on_stop_plugin(self):
        """Handle stop plugin button click."""
        self.server_manager.stop_plugin()
    
    def _on_send_text(self):
        """Handle send text button click."""
        text = self.chat_tab.input_text.text().strip()
        if not text:
            return
        
        if not self.server_manager.is_server_running():
            self._append_chat_message("Erro: Servidor não está rodando. Inicie o servidor primeiro.")
            return
        
        host = self.controls_tab.host.text().strip() or "127.0.0.1"
        port = self.controls_tab.port.value()
        self.chat_handler.set_host_port(host, port)
        
        # Get user name from controls tab
        user_name = self.controls_tab.user_name.text().strip() if hasattr(self.controls_tab, 'user_name') else "Você"
        if not user_name:
            user_name = "Você"
        
        success, result = self.chat_handler.send_text(text, user=user_name)
        
        if success:
            job_id = result
            self._append_chat_message(f"{user_name}: {text}")
            self._append_server_log(f"Texto enviado: '{text}' -> job_id: {job_id}")
            self._request_response()
        else:
            error_msg = result
            self._append_chat_message(error_msg)
        
        self.chat_tab.input_text.clear()
    
    def _on_toggle_record(self, checked: bool):
        """Handle toggle record button."""
        if checked:
            if self.vad_handler.is_listening_continuously:
                self.chat_tab.btn_listen_continuous.setChecked(False)
                self._stop_continuous_listening()
            self._start_recording()
        else:
            self._stop_recording()
    
    def _on_toggle_continuous_listening(self, checked: bool):
        """Handle toggle continuous listening button."""
        if checked:
            if self.audio_recorder.is_recording:
                self.chat_tab.btn_record_audio.setChecked(False)
                self._stop_recording()
            if self.vad_handler.is_listening_continuously:
                self._stop_continuous_listening()
                QtCore.QTimer.singleShot(300, self._start_continuous_listening)
            else:
                self._start_continuous_listening()
        else:
            self._stop_continuous_listening()
    
    def _on_sensitivity_changed(self, value: int):
        """Handle sensitivity slider change."""
        old_threshold = self.vad_handler.voice_threshold
        self.vad_handler.voice_threshold = value
        self.chat_tab.label_sensitivity.setText(str(value))
        self.chat_tab.threshold_indicator.setText(str(value))
        if hasattr(self.chat_tab, 'audio_level_widget'):
            self.chat_tab.audio_level_widget.set_threshold(value)
        print(f"[VAD] Threshold alterado: {old_threshold} -> {value}")
    
    def _on_silence_changed(self, value: int):
        """Handle silence duration slider change."""
        self.vad_handler.silence_duration = value / 10.0
        self.chat_tab.label_silence.setText(f"{self.vad_handler.silence_duration:.1f}s")
    
    def _start_recording(self):
        """Start manual audio recording."""
        self.audio_recorder.start_recording()
        self.chat_tab.btn_record_audio.setText("⏹ Parar Gravação")
        self.chat_tab.audio_status.setText("Gravando... (clique novamente para parar)")
        self.chat_tab.btn_send_audio.setEnabled(False)
    
    def _stop_recording(self):
        """Stop manual audio recording."""
        success, audio_array, duration = self.audio_recorder.stop_recording()
        
        self.chat_tab.btn_record_audio.setChecked(False)
        self.chat_tab.btn_record_audio.setText("🎤 Gravar Áudio")
        
        if success and audio_array is not None:
            self.audio_recorder.recorded_audio = audio_array
            self.chat_tab.audio_status.setText(f"Gravação concluída ({duration:.1f}s). Clique em 'Testar Áudio' ou 'Enviar Áudio'.")
            self.chat_tab.btn_send_audio.setEnabled(True)
            self.chat_tab.btn_test_audio.setEnabled(True)
        else:
            self.audio_recorder.recorded_audio = None
            self.chat_tab.audio_status.setText("Nenhum áudio gravado")
            self.chat_tab.btn_send_audio.setEnabled(False)
            self.chat_tab.btn_test_audio.setEnabled(False)
    
    def _start_continuous_listening(self):
        """Start continuous listening with VAD."""
        self.vad_handler.start_listening()
        
        self.chat_tab.btn_listen_continuous.setText("👂 Escuta Ativa")
        self.chat_tab.btn_listen_continuous.setChecked(True)
        self.chat_tab.btn_stop_listening.setEnabled(True)
        self.chat_tab.audio_status.setText("Escutando... (fale para começar)")
        self.chat_tab.slider_sensitivity.setEnabled(True)
        self.chat_tab.slider_silence.setEnabled(True)
        self.chat_tab.voice_indicator.setText("🔇")
        if hasattr(self.chat_tab, 'audio_level_widget'):
            self.chat_tab.audio_level_widget.set_level(0)
            self.chat_tab.audio_level_widget.set_threshold(self.vad_handler.voice_threshold)
        self.chat_tab.audio_level_label.setText("0")
        self.chat_tab.threshold_indicator.setText(str(self.vad_handler.voice_threshold))
    
    def _stop_continuous_listening(self):
        """Stop continuous listening."""
        self.vad_handler.stop_listening()
        
        self.chat_tab.btn_listen_continuous.setText("👂 Escuta Contínua")
        self.chat_tab.btn_listen_continuous.setChecked(False)
        self.chat_tab.btn_stop_listening.setEnabled(False)
        self.chat_tab.audio_status.setText("Escuta contínua parada")
        self.chat_tab.slider_sensitivity.setEnabled(False)
        self.chat_tab.slider_silence.setEnabled(False)
        self.chat_tab.voice_indicator.setText("🔇")
        if hasattr(self.chat_tab, 'audio_level_widget'):
            self.chat_tab.audio_level_widget.set_level(0)
        self.chat_tab.audio_level_label.setText("0")
    
    def _on_stop_listening(self):
        """Handle stop listening button click."""
        if self.vad_handler.is_listening_continuously:
            self._stop_continuous_listening()
    
    def _on_phrase_ready(self):
        """Handle phrase ready from VAD."""
        result = self.vad_handler.get_current_phrase_audio()
        if result is None:
            return
        
        audio_array, duration = result
        self.vad_handler.clear_current_phrase()
        
        # Get user name from controls tab
        user_name = self.controls_tab.user_name.text().strip() if hasattr(self.controls_tab, 'user_name') else "Você"
        if not user_name:
            user_name = "Você"
        
        self.chat_tab.audio_status.setText(f"Enviando frase ({duration:.1f}s)...")
        self._append_chat_message(f"{user_name}: [Áudio - {duration:.1f}s]")
        
        if self.vad_handler.is_listening_continuously and not self.vad_handler.is_playing_ai_audio:
            self.vad_handler._was_listening_before_playback = True
            self.vad_handler.pause_listener()
        
        host = self.controls_tab.host.text().strip() or "127.0.0.1"
        port = self.controls_tab.port.value()
        self.chat_handler.set_host_port(host, port)
        
        success, result = self.chat_handler.send_audio(audio_array, self.sample_rate, user=user_name)
        
        if success:
            job_id = result
            self.chat_tab.audio_status.setText("Áudio enviado! Aguardando resposta...")
            self._append_server_log(f"Áudio automático enviado ({duration:.1f}s) -> job_id: {job_id}")
            # IMPORTANTE: Mantém a escuta pausada até o áudio da IA terminar de tocar
            # Isso evita:
            # 1. Usuário falar enquanto IA está processando (comportamento natural)
            # 2. Sobreposição de áudios se a IA enviar múltiplos áudios
            # 3. Envio de novo áudio enquanto IA ainda está respondendo
            # A escuta será retomada automaticamente quando o áudio da IA terminar (em on_playback_complete)
            # OU se houver erro (em _on_received_error)
            self._request_response()
        else:
            error_msg = result
            self.chat_tab.audio_status.setText(f"Erro ao enviar: {error_msg}")
            self._append_chat_message(f"Erro: {error_msg}")
            # Resume a escuta em caso de erro no envio
            if self.vad_handler._was_listening_before_playback:
                self.vad_handler._was_listening_before_playback = False
                self.vad_handler.resume_listener()
    
    def _auto_send_phrase(self):
        """Automatically send the detected phrase."""
        self._on_phrase_ready()
    
    def _on_voice_detected(self):
        """Handle voice detected signal."""
        self.chat_tab.voice_indicator.setText("🎤")
        self.chat_tab.audio_status.setText("Falando...")
    
    def _on_silence_detected(self):
        """Handle silence detected signal."""
        self.chat_tab.voice_indicator.setText("🔇")
        self.chat_tab.audio_status.setText("Silêncio detectado, aguardando...")
    
    def _update_audio_level(self, rms_value: int, threshold: int = None):
        """Update audio level indicator in UI thread."""
        if not self.vad_handler.is_listening_continuously:
            return
        
        if threshold is None:
            threshold = self.vad_handler.voice_threshold
        
        if hasattr(self.chat_tab, 'audio_level_widget'):
            self.chat_tab.audio_level_widget.set_level(rms_value)
            self.chat_tab.audio_level_widget.set_threshold(threshold)
            self.chat_tab.audio_level_widget.update()
        
        if hasattr(self.chat_tab, 'audio_level_bar'):
            display_value = min(rms_value, 2000)
            self.chat_tab.audio_level_bar.setValue(display_value)
            
            if rms_value > threshold:
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
            else:
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
            self.chat_tab.audio_level_bar.setStyleSheet(style)
            self.chat_tab.audio_level_bar.setFormat(f"{rms_value} / {threshold}")
        
        self.chat_tab.audio_level_label.setText(str(rms_value))
        self.chat_tab.threshold_indicator.setText(str(threshold))
    
    def _on_send_audio(self):
        """Handle send audio button click."""
        if not hasattr(self.audio_recorder, 'recorded_audio') or self.audio_recorder.recorded_audio is None:
            self.chat_tab.audio_status.setText("Erro: Nenhum áudio gravado")
            return
        
        audio_array = self.audio_recorder.recorded_audio
        host = self.controls_tab.host.text().strip() or "127.0.0.1"
        port = self.controls_tab.port.value()
        self.chat_handler.set_host_port(host, port)
        
        # Get user name from controls tab
        user_name = self.controls_tab.user_name.text().strip() if hasattr(self.controls_tab, 'user_name') else "Você"
        if not user_name:
            user_name = "Você"
        
        self._append_chat_message(f"{user_name}: [Áudio enviado]")
        self.chat_tab.audio_status.setText("Enviando áudio...")
        self.chat_tab.btn_send_audio.setEnabled(False)
        
        success, result = self.chat_handler.send_audio(audio_array, self.sample_rate, user=user_name)
        
        if success:
            job_id = result
            self.chat_tab.audio_status.setText("Áudio enviado com sucesso!")
            self._append_server_log(f"Áudio enviado -> job_id: {job_id}")
            self._request_response()
        else:
            error_msg = result
            self._append_chat_message(f"Erro ({error_msg})")
            self.chat_tab.audio_status.setText(f"Erro ao enviar: {error_msg}")
        
        self.audio_recorder.recorded_audio = None
        self.chat_tab.btn_send_audio.setEnabled(False)
