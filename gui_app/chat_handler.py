"""Chat and message handling module."""

import time
import json
import base64
import re
from typing import Optional, Callable

import requests
import numpy as np

try:
    from .audio_listener import AudioListener
except ImportError:
    from audio_listener import AudioListener


class ChatHandler:
    """Handles chat messages and audio communication with server."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 7272):
        self.host = host
        self.port = port
        self.audio_listener: Optional[AudioListener] = None
        
        # Audio chunks buffer for reassembly
        self.audio_chunks_buffer = []
        self.last_ai_audio = None
        self.last_ai_audio_sr = 16000
        self.last_ai_audio_sw = 2
        self.last_ai_audio_ch = 1
        
        # Callbacks
        self.on_text_received: Optional[Callable[[str], None]] = None
        self.on_audio_received: Optional[Callable[[bytes, int, int, int], None]] = None
        self.on_audio_chunk_received: Optional[Callable[[str, int, int, int], None]] = None
        self.on_audio_complete: Optional[Callable[[int, int, int], None]] = None
        self.on_error_received: Optional[Callable[[str], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None
    
    def set_host_port(self, host: str, port: int):
        """Update host and port."""
        self.host = host
        self.port = port
    
    def start_audio_listener(self):
        """Start WebSocket audio listener."""
        if self.audio_listener and self.audio_listener.isRunning():
            return
        
        ws_url = f"ws://{self.host}:{self.port}/"
        
        self.audio_listener = AudioListener(ws_url)
        self.audio_listener.audio_received.connect(self._on_audio_received)
        self.audio_listener.audio_chunk_received.connect(self._on_audio_chunk_received)
        self.audio_listener.audio_complete.connect(self._on_audio_complete)
        self.audio_listener.text_received.connect(self._on_text_received)
        self.audio_listener.image_received.connect(self._on_image_received)
        self.audio_listener.error_received.connect(self._on_error_received)
        self.audio_listener.connection_closed.connect(self._on_connection_closed)
        self.audio_listener.start()
        
        if self.on_log:
            self.on_log(f"Audio listener iniciado em {ws_url}")
    
    def stop_audio_listener(self):
        """Stop WebSocket audio listener."""
        if self.audio_listener:
            self.audio_listener.stop()
            self.audio_listener.wait(2000)
            self.audio_listener = None
    
    def _on_audio_received(self, audio_bytes: bytes, sr: int, sw: int, ch: int):
        """Handle complete audio received."""
        if self.on_audio_received:
            self.on_audio_received(audio_bytes, sr, sw, ch)
    
    def _on_audio_chunk_received(self, audio_b64_chunk: str, sr: int, sw: int, ch: int):
        """Handle audio chunk received."""
        try:
            chunk_bytes = base64.b64decode(audio_b64_chunk)
            self.audio_chunks_buffer.append(chunk_bytes)
            self.last_ai_audio_sr = sr
            self.last_ai_audio_sw = sw
            self.last_ai_audio_ch = ch
            
            if self.on_audio_chunk_received:
                self.on_audio_chunk_received(audio_b64_chunk, sr, sw, ch)
        except Exception as e:
            if self.on_log:
                self.on_log(f"Erro ao decodificar chunk de áudio: {e}")
    
    def _on_audio_complete(self, sr: int, sw: int, ch: int):
        """Handle audio completion signal."""
        print(f"[ChatHandler] _on_audio_complete recebido: buffer tem {len(self.audio_chunks_buffer)} chunks, sr={sr}, sw={sw}, ch={ch}")
        if self.audio_chunks_buffer:
            # Use stored parameters if provided ones are default
            if sr == 16000 and self.last_ai_audio_sr != 16000:
                sr = self.last_ai_audio_sr
                sw = self.last_ai_audio_sw
                ch = self.last_ai_audio_ch
            
            print(f"[ChatHandler] Chamando on_audio_complete callback (sr={sr}, sw={sw}, ch={ch})")
            if self.on_audio_complete:
                self.on_audio_complete(sr, sw, ch)
            else:
                print("[ChatHandler] ⚠️ on_audio_complete callback não está definido!")
        else:
            error_msg = "⚠️ Buffer vazio quando evento de conclusão chegou!"
            if self.on_log:
                self.on_log(error_msg)
            print(f"[ChatHandler] {error_msg}")
    
    def _on_text_received(self, text: str):
        """Handle text received from server."""
        if text.strip() and self.on_text_received:
            self.on_text_received(text)
    
    def _on_connection_closed(self):
        """Handle WebSocket connection closed unexpectedly."""
        print(f"[ChatHandler] Conexão WebSocket fechada, verificando se há áudio no buffer para montar...")
        # Se há chunks no buffer, tenta montar como fallback
        if self.audio_chunks_buffer:
            print(f"[ChatHandler] Buffer tem {len(self.audio_chunks_buffer)} chunks, tentando montar como fallback")
            if self.on_audio_complete:
                # Usa os parâmetros armazenados
                self.on_audio_complete(self.last_ai_audio_sr, self.last_ai_audio_sw, self.last_ai_audio_ch)
            else:
                print("[ChatHandler] ⚠️ on_audio_complete callback não está definido!")
        else:
            print("[ChatHandler] Buffer vazio, nada para montar")
    
    def _on_image_received(self, image_bytes_b64: str, user_name: str, image_format: str, error: str):
        """Handle image received from server."""
        if self.on_image_received:
            self.on_image_received(image_bytes_b64, user_name, image_format, error or None)
    
    def _on_error_received(self, error_msg: str):
        """Handle error received from server."""
        if self.on_error_received:
            self.on_error_received(error_msg)
    
    def send_text(self, text: str, user: str = "Usuario") -> tuple[bool, Optional[str]]:
        """
        Send text message to server.
        Returns: (success, job_id or error_message)
        """
        url = f"http://{self.host}:{self.port}/api/context/conversation/text"
        
        try:
            payload = {
                "user": user,
                "content": text,
                "timestamp": int(time.time())
            }
            
            r = requests.post(
                url, 
                headers={"Content-Type": "application/json"}, 
                data=json.dumps(payload), 
                timeout=30
            )
            
            if r.ok:
                response_data = r.json()
                job_id = response_data.get("response", {}).get("job_id", "desconhecido")
                return True, job_id
            else:
                error_msg = r.text[:500] if r.text else "Sem detalhes"
                return False, f"Erro ({r.status_code}): {error_msg}"
        except requests.exceptions.ConnectionError:
            return False, f"Não foi possível conectar ao servidor em {url}"
        except requests.exceptions.Timeout:
            return False, "Timeout: O servidor demorou muito para responder."
        except Exception as e:
            return False, f"Falha ao enviar: {e}"
    
    def update_user_context(self, user_context: str) -> tuple[bool, Optional[str]]:
        """
        Update user context on server.
        Returns: (success, message or error_message)
        """
        url = f"http://{self.host}:{self.port}/api/context/config"
        
        try:
            payload = {
                "user_context": user_context
            }
            
            r = requests.put(
                url, 
                headers={"Content-Type": "application/json"}, 
                data=json.dumps(payload), 
                timeout=30
            )
            
            if r.ok:
                response_data = r.json()
                job_id = response_data.get("response", {}).get("job_id", "desconhecido")
                return True, job_id
            else:
                error_msg = r.text[:500] if r.text else "Sem detalhes"
                return False, f"Erro ({r.status_code}): {error_msg}"
        except requests.exceptions.ConnectionError:
            return False, f"Não foi possível conectar ao servidor em {url}"
        except Exception as e:
            return False, f"Erro inesperado: {str(e)}"
    
    def send_audio(self, audio_array: np.ndarray, sample_rate: int, user: str = "Usuario") -> tuple[bool, Optional[str]]:
        """
        Send audio to server.
        Returns: (success, job_id or error_message)
        """
        url = f"http://{self.host}:{self.port}/api/context/conversation/audio"
        
        try:
            audio_bytes = audio_array.tobytes()
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            payload = {
                "user": user,
                "timestamp": int(time.time()),
                "audio_bytes": audio_b64,
                "sr": sample_rate,
                "sw": 2,
                "ch": 1
            }
            
            r = requests.post(
                url, 
                headers={"Content-Type": "application/json"}, 
                data=json.dumps(payload), 
                timeout=30
            )
            
            if r.ok:
                response_data = r.json()
                job_id = response_data.get("response", {}).get("job_id", "desconhecido")
                return True, job_id
            else:
                error_msg = r.text[:500] if r.text else "Sem detalhes"
                return False, f"Erro ({r.status_code}): {error_msg}"
        except Exception as e:
            return False, f"Falha ao enviar áudio: {e}"
    
    def request_response(self, include_audio: bool = True) -> tuple[bool, Optional[str]]:
        """
        Request a response from the server.
        Returns: (success, job_id or error_message)
        """
        url = f"http://{self.host}:{self.port}/api/response"
        
        try:
            payload = {"include_audio": include_audio}
            r = requests.post(
                url, 
                headers={"Content-Type": "application/json"}, 
                data=json.dumps(payload), 
                timeout=60
            )
            
            if r.ok:
                response_data = r.json()
                job_id = response_data.get("response", {}).get("job_id", "desconhecido")
                return True, job_id
            else:
                error_msg = r.text[:500] if r.text else "Sem detalhes"
                return False, f"Erro ({r.status_code}): {error_msg}"
        except Exception as e:
            return False, f"Falha ao solicitar resposta: {e}"
    
    def assemble_audio_chunks(self) -> tuple[Optional[bytes], Optional[int], Optional[int], Optional[int]]:
        """
        Assemble audio chunks from buffer.
        Returns: (audio_bytes, sr, sw, ch) or (None, None, None, None) if buffer is empty
        """
        if not self.audio_chunks_buffer:
            return None, None, None, None
        
        try:
            complete_audio = b''.join(self.audio_chunks_buffer)
            chunks_to_clear = len(self.audio_chunks_buffer)
            self.audio_chunks_buffer = []
            
            return (
                complete_audio,
                self.last_ai_audio_sr,
                self.last_ai_audio_sw,
                self.last_ai_audio_ch
            )
        except Exception as e:
            if self.on_log:
                self.on_log(f"Erro ao montar áudio: {e}")
            return None, None, None, None
    
    def clear_audio_buffer(self):
        """Clear the audio chunks buffer."""
        self.audio_chunks_buffer = []





