"""Voice Activity Detection (VAD) handler."""

import time
import threading
import base64
import json
from typing import Optional, Callable

import sounddevice as sd
import numpy as np
from PySide6 import QtCore
import requests


class VADHandler:
    """Handles continuous listening with voice activity detection."""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        
        self.is_listening_continuously = False
        self.current_phrase_audio = []
        self.is_speaking = False
        self.silence_start_time = None
        self.voice_threshold = 500
        self.silence_duration = 1.5
        self._auto_send_scheduled = False
        self.continuous_stream = None
        self._was_listening_before_playback = False
        self.is_playing_ai_audio = False
        
        self._callback_logged = False
        self._last_rms_log_time = 0
        self._last_silence_log = -1
        
        self.audio_input_device = None
        
        self.on_voice_detected: Optional[Callable] = None
        self.on_silence_detected: Optional[Callable] = None
        self.on_phrase_ready: Optional[Callable] = None
        self.on_audio_level_update: Optional[Callable] = None
        self.on_log: Optional[Callable] = None
    
    def start_listening(self):
        """Start continuous listening with VAD."""
        if self.continuous_stream:
            try:
                self.continuous_stream.close()
            except:
                pass
            self.continuous_stream = None
        
        self.is_listening_continuously = True
        self.current_phrase_audio = []
        self.is_speaking = False
        self.silence_start_time = None
        self._auto_send_scheduled = False
        self._was_listening_before_playback = False
        self.is_playing_ai_audio = False
        self._callback_logged = False
        self._last_rms_log_time = 0
        self._last_silence_log = -1
        
        def listen_thread():
            try:
                if self.audio_input_device is not None:
                    self.continuous_stream = sd.InputStream(
                        samplerate=self.sample_rate,
                        channels=1,
                        dtype=np.float32,
                        callback=self._audio_callback,
                        blocksize=1024,
                        device=self.audio_input_device
                    )
                else:
                    self.continuous_stream = sd.InputStream(
                        samplerate=self.sample_rate,
                        channels=1,
                        dtype=np.float32,
                        callback=self._audio_callback,
                        blocksize=1024
                    )
                
                with self.continuous_stream:
                    while self.is_listening_continuously:
                        time.sleep(0.1)
            except Exception as e:
                if self.on_log:
                    self.on_log(f"[VAD] ❌ Erro na escuta: {e}")
        
        threading.Thread(target=listen_thread, daemon=True).start()
    
    def stop_listening(self):
        """Stop continuous listening."""
        self.is_listening_continuously = False
        self._was_listening_before_playback = False
        self.is_playing_ai_audio = False
        self.is_speaking = False
        self.current_phrase_audio = []
        self.silence_start_time = None
        self._auto_send_scheduled = False
        self._callback_logged = False
        self._last_rms_log_time = 0
        self._last_silence_log = -1
        
        if self.continuous_stream:
            try:
                self.continuous_stream.close()
            except:
                pass
            self.continuous_stream = None
    
    def pause_listener(self):
        """Temporarily pause the listener."""
        if not self.is_listening_continuously:
            return
        
        if self.continuous_stream:
            try:
                self.continuous_stream.close()
            except:
                pass
            self.continuous_stream = None
        
        self.current_phrase_audio = []
        self.is_speaking = False
        self.silence_start_time = None
        self._auto_send_scheduled = False
    
    def resume_listener(self):
        """Resume the listener after it was paused."""
        if not self._was_listening_before_playback:
            return
        
        if self.is_listening_continuously and not self.continuous_stream:
            def listen_thread():
                try:
                    if self.audio_input_device is not None:
                        self.continuous_stream = sd.InputStream(
                            samplerate=self.sample_rate,
                            channels=1,
                            dtype=np.float32,
                            callback=self._audio_callback,
                            blocksize=1024,
                            device=self.audio_input_device
                        )
                    else:
                        self.continuous_stream = sd.InputStream(
                            samplerate=self.sample_rate,
                            channels=1,
                            dtype=np.float32,
                            callback=self._audio_callback,
                            blocksize=1024
                        )
                    
                    with self.continuous_stream:
                        while self.is_listening_continuously:
                            time.sleep(0.1)
                except Exception as e:
                    if self.on_log:
                        self.on_log(f"[VAD] ❌ Erro na escuta: {e}")
            
            threading.Thread(target=listen_thread, daemon=True).start()
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Audio callback for VAD."""
        if not hasattr(self, '_callback_logged'):
            if self.on_log:
                self.on_log("[VAD] ✅ Callback de áudio está funcionando!")
            self._callback_logged = True
        
        if status and self.on_log:
            self.on_log(f"[VAD] Status do áudio: {status}")
        
        if self.is_playing_ai_audio:
            return
        
        if self.is_listening_continuously:
            audio_chunk = indata.copy()
            
            rms_normalized = np.sqrt(np.mean(audio_chunk**2))
            rms_scaled = int(rms_normalized * 32767.0)
            
            if self.on_audio_level_update:
                self.on_audio_level_update(rms_scaled, self.voice_threshold)
            
            current_time = time.time()
            if current_time - self._last_rms_log_time > 2.0:
                if self.on_log:
                    log_msg = f"[VAD] RMS: {rms_scaled}, Threshold: {self.voice_threshold}, Detecção: {'✅ SIM' if rms_scaled > self.voice_threshold else '❌ NÃO'}"
                    self.on_log(log_msg)
                self._last_rms_log_time = current_time
            
            if rms_scaled > self.voice_threshold:
                if not self.is_speaking:
                    self.is_speaking = True
                    self.silence_start_time = None
                    self.current_phrase_audio = []
                    self._auto_send_scheduled = False
                    if self.on_log:
                        self.on_log(f"[VAD] 🎤 Voz detectada! RMS: {rms_scaled} > Threshold: {self.voice_threshold}")
                    if self.on_voice_detected:
                        self.on_voice_detected()
                
                self.current_phrase_audio.append(audio_chunk)
            else:
                if self.is_speaking:
                    if self.silence_start_time is None:
                        self.silence_start_time = time.time()
                        if self.on_log:
                            self.on_log(f"[VAD] 🔇 Silêncio detectado após falar. RMS: {rms_scaled} <= Threshold: {self.voice_threshold}")
                        if self.on_silence_detected:
                            self.on_silence_detected()
                    
                    silence_duration = time.time() - self.silence_start_time
                    if int(silence_duration * 2) != self._last_silence_log:
                        self._last_silence_log = int(silence_duration * 2)
                        if silence_duration < self.silence_duration:
                            if self.on_log:
                                self.on_log(f"[VAD] ⏳ Aguardando silêncio: {silence_duration:.1f}s / {self.silence_duration:.1f}s")
                    
                    if silence_duration >= self.silence_duration and not self._auto_send_scheduled:
                        if self.current_phrase_audio and self.is_listening_continuously:
                            self._auto_send_scheduled = True
                            if self.on_log:
                                self.on_log(f"[VAD] ⏱️ Silêncio de {silence_duration:.1f}s excedeu threshold. Enviando frase...")
                            if self.on_phrase_ready:
                                self.on_phrase_ready()
                            self.is_speaking = False
                            self.silence_start_time = None
    
    def get_current_phrase_audio(self) -> Optional[tuple[np.ndarray, float]]:
        """Get the current phrase audio as numpy array and duration."""
        if not self.current_phrase_audio:
            return None
        
        try:
            phrase_audio_copy = list(self.current_phrase_audio)
            audio_array = np.concatenate(phrase_audio_copy, axis=0)
            
            if audio_array.dtype == np.float32:
                audio_array = np.clip(audio_array, -1.0, 1.0)
                audio_array = (audio_array * 32767.0).astype(np.int16)
            
            duration = len(audio_array) / self.sample_rate
            
            if duration >= 0.5:
                return audio_array, duration
            return None
        except Exception as e:
            if self.on_log:
                self.on_log(f"[VAD] ❌ Erro ao processar frase: {e}")
            return None
    
    def clear_current_phrase(self):
        """Clear the current phrase audio."""
        self.current_phrase_audio = []

