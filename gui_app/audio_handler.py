"""Audio handling module for recording, playback, and VAD."""

import time
import threading
import base64
import json
from typing import Optional, Callable

import sounddevice as sd
import numpy as np
from PySide6 import QtCore


class AudioHandler:
    """Handles all audio operations: recording, playback, and VAD."""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        
        # Manual recording state
        self.is_recording = False
        self.audio_data = []
        self._recording_chunks_count = 0
        
        # Continuous listening (VAD) state
        self.is_listening_continuously = False
        self.current_phrase_audio = []
        self.is_speaking = False
        self.silence_start_time = None
        self.voice_threshold = 500  # RMS threshold for voice detection
        self.silence_duration = 1.5  # seconds of silence before auto-send
        self.continuous_stream = None
        self._callback_logged = False
        self._last_rms_log_time = 0
        
        # Audio device selection
        self.audio_output_device = None
        self.audio_input_device = None
        
        # Last received audio from AI
        self.last_ai_audio = None
        self.last_ai_audio_sr = 16000
        self.last_ai_audio_sw = 2
        self.last_ai_audio_ch = 1
        
        # Audio chunks buffer for reassembly
        self.audio_chunks_buffer = []
        
        # Callbacks
        self.on_voice_detected: Optional[Callable] = None
        self.on_silence_detected: Optional[Callable] = None
        self.on_phrase_ready: Optional[Callable] = None
        self.on_audio_level_update: Optional[Callable] = None
        self.on_vad_log: Optional[Callable] = None
    
    def start_recording(self):
        """Start manual audio recording."""
        self.is_recording = True
        self.audio_data = []
        self._recording_chunks_count = 0
        
        def record_thread():
            try:
                if self.audio_input_device is not None:
                    stream = sd.InputStream(
                        samplerate=self.sample_rate, 
                        channels=1, 
                        dtype=np.int16, 
                        callback=self._audio_callback, 
                        device=self.audio_input_device
                    )
                else:
                    stream = sd.InputStream(
                        samplerate=self.sample_rate, 
                        channels=1, 
                        dtype=np.int16, 
                        callback=self._audio_callback
                    )
                
                with stream:
                    while self.is_recording:
                        time.sleep(0.1)
            except Exception as e:
                if self.on_vad_log:
                    self.on_vad_log(f"[Audio] ❌ Erro na gravação: {e}")
        
        threading.Thread(target=record_thread, daemon=True).start()
    
    def stop_recording(self) -> tuple[bool, Optional[np.ndarray], float]:
        """
        Stop manual recording.
        Returns: (success, audio_array, duration)
        """
        self.is_recording = False
        time.sleep(0.2)  # Wait for callbacks to finish
        
        if self.audio_data and len(self.audio_data) > 0:
            try:
                audio_array = np.concatenate(self.audio_data, axis=0)
                duration = len(audio_array) / self.sample_rate
                return True, audio_array, duration
            except Exception as e:
                if self.on_vad_log:
                    self.on_vad_log(f"[Audio] ❌ Erro ao processar áudio: {e}")
                return False, None, 0.0
        return False, None, 0.0
    
    def start_continuous_listening(self):
        """Start continuous listening with voice activity detection."""
        self.is_listening_continuously = True
        self.current_phrase_audio = []
        self.is_speaking = False
        self.silence_start_time = None
        self._callback_logged = False
        
        def listen_thread():
            try:
                if self.audio_input_device is not None:
                    self.continuous_stream = sd.InputStream(
                        samplerate=self.sample_rate,
                        channels=1,
                        dtype=np.int16,
                        callback=self._audio_callback,
                        blocksize=1024,
                        device=self.audio_input_device
                    )
                else:
                    self.continuous_stream = sd.InputStream(
                        samplerate=self.sample_rate,
                        channels=1,
                        dtype=np.int16,
                        callback=self._audio_callback,
                        blocksize=1024
                    )
                
                with self.continuous_stream:
                    while self.is_listening_continuously:
                        time.sleep(0.1)
            except Exception as e:
                if self.on_vad_log:
                    self.on_vad_log(f"[VAD] ❌ Erro na escuta: {e}")
        
        threading.Thread(target=listen_thread, daemon=True).start()
    
    def stop_continuous_listening(self):
        """Stop continuous listening."""
        self.is_listening_continuously = False
        if self.continuous_stream:
            self.continuous_stream.close()
            self.continuous_stream = None
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Audio callback for both recording and VAD."""
        if status and self.on_vad_log:
            self.on_vad_log(f"[VAD] Status do áudio: {status}")
        
        # Handle manual recording
        if self.is_recording:
            chunk = indata.copy()
            self.audio_data.append(chunk)
            self._recording_chunks_count += 1
        
        # Handle continuous listening with VAD
        if self.is_listening_continuously:
            audio_chunk = indata.copy()
            
            # Calculate RMS for voice detection
            audio_float = audio_chunk.astype(np.float32)
            rms = np.sqrt(np.mean(audio_float**2))
            rms_int = int(rms)
            
            # Update audio level indicator
            if self.on_audio_level_update:
                QtCore.QTimer.singleShot(0, lambda: self.on_audio_level_update(rms_int, self.voice_threshold))
            
            # Log RMS values occasionally
            current_time = time.time()
            if current_time - self._last_rms_log_time > 2.0:
                if self.on_vad_log:
                    log_msg = f"[VAD] RMS: {rms:.1f}, Threshold: {self.voice_threshold}, Detecção: {'✅ SIM' if rms > self.voice_threshold else '❌ NÃO'}"
                    self.on_vad_log(log_msg)
                self._last_rms_log_time = current_time
            
            # Check if voice is detected
            if rms > self.voice_threshold:
                # Voice detected
                if not self.is_speaking:
                    self.is_speaking = True
                    self.silence_start_time = None
                    self.current_phrase_audio = []
                    if self.on_voice_detected:
                        QtCore.QTimer.singleShot(0, self.on_voice_detected)
                    if self.on_vad_log:
                        self.on_vad_log(f"[VAD] 🎤 Voz detectada! RMS: {rms:.1f} > Threshold: {self.voice_threshold}")
                
                # Add to current phrase
                self.current_phrase_audio.append(audio_chunk)
            else:
                # Silence detected
                if self.is_speaking:
                    # We were speaking, now silence
                    if self.silence_start_time is None:
                        self.silence_start_time = time.time()
                        if self.on_silence_detected:
                            QtCore.QTimer.singleShot(0, self.on_silence_detected)
                        if self.on_vad_log:
                            self.on_vad_log(f"[VAD] 🔇 Silêncio detectado após falar. RMS: {rms:.1f} <= Threshold: {self.voice_threshold}")
                    
                    # Check if silence duration exceeded threshold
                    silence_duration = time.time() - self.silence_start_time
                    if silence_duration >= self.silence_duration:
                        # Auto-send the phrase
                        if self.current_phrase_audio and self.is_listening_continuously:
                            if self.on_vad_log:
                                self.on_vad_log(f"[VAD] ⏱️ Silêncio de {silence_duration:.1f}s excedeu threshold de {self.silence_duration:.1f}s. Enviando frase...")
                            if self.on_phrase_ready:
                                QtCore.QTimer.singleShot(0, self.on_phrase_ready)
                            self.is_speaking = False
                            self.silence_start_time = None
    
    def get_current_phrase_audio(self) -> Optional[np.ndarray]:
        """Get the current phrase audio as numpy array."""
        if not self.current_phrase_audio:
            return None
        
        try:
            audio_array = np.concatenate(self.current_phrase_audio, axis=0)
            duration = len(audio_array) / self.sample_rate
            
            # Only return if duration is reasonable
            if duration >= 0.5:
                return audio_array
            return None
        except Exception:
            return None
    
    def clear_current_phrase(self):
        """Clear the current phrase audio."""
        self.current_phrase_audio = []
    
    def play_audio(self, audio_array: np.ndarray, sr: int, sw: int = 2, ch: int = 1):
        """Play audio array."""
        def play_thread():
            try:
                if self.audio_output_device is not None:
                    sd.play(audio_array, samplerate=sr, device=self.audio_output_device)
                else:
                    sd.play(audio_array, samplerate=sr)
                sd.wait()
            except Exception as e:
                if self.on_vad_log:
                    self.on_vad_log(f"Erro ao reproduzir áudio: {e}")
        
        threading.Thread(target=play_thread, daemon=True).start()
    
    def play_audio_bytes(self, audio_bytes: bytes, sr: int, sw: int = 2, ch: int = 1):
        """Play audio from bytes."""
        try:
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            if ch == 2:
                audio_array = audio_array.reshape(-1, 2)
            self.play_audio(audio_array, sr, sw, ch)
        except Exception as e:
            if self.on_vad_log:
                self.on_vad_log(f"Erro ao processar áudio: {e}")
    
    def encode_audio_to_base64(self, audio_array: np.ndarray) -> str:
        """Encode audio array to base64 string."""
        audio_bytes = audio_array.tobytes()
        return base64.b64encode(audio_bytes).decode('utf-8')
    
    def prepare_audio_payload(self, audio_array: np.ndarray, user: str = "Usuario") -> dict:
        """Prepare audio payload for API request."""
        audio_b64 = self.encode_audio_to_base64(audio_array)
        return {
            "user": user,
            "timestamp": int(time.time()),
            "audio_bytes": audio_b64,
            "sr": self.sample_rate,
            "sw": 2,
            "ch": 1
        }





