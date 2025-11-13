"""Audio playback handler."""

import threading
from typing import Optional, Callable

import sounddevice as sd
import numpy as np


class AudioPlayer:
    """Handles audio playback."""
    
    def __init__(self):
        self.audio_output_device = None
        self.last_ai_audio = None
        self.last_ai_audio_sr = 16000
        self.last_ai_audio_sw = 2
        self.last_ai_audio_ch = 1
        
        self.on_log: Optional[Callable] = None
    
    def play_audio(self, audio_array: np.ndarray, sr: int, sw: int = 2, ch: int = 1, on_complete=None):
        """Play audio array."""
        def play_thread():
            try:
                if self.audio_output_device is not None:
                    sd.play(audio_array, samplerate=sr, device=self.audio_output_device)
                else:
                    sd.play(audio_array, samplerate=sr)
                sd.wait()
                if on_complete:
                    on_complete()
            except Exception as e:
                if self.on_log:
                    self.on_log(f"Erro ao reproduzir áudio: {e}")
                if on_complete:
                    on_complete()
        
        threading.Thread(target=play_thread, daemon=True).start()
    
    def play_audio_bytes(self, audio_bytes: bytes, sr: int, sw: int = 2, ch: int = 1, on_complete=None):
        """Play audio from bytes."""
        try:
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            if ch == 2:
                audio_array = audio_array.reshape(-1, 2)
            self.play_audio(audio_array, sr, sw, ch, on_complete)
        except Exception as e:
            if self.on_log:
                self.on_log(f"Erro ao processar áudio: {e}")
            if on_complete:
                on_complete()
    
    def store_last_audio(self, audio_array: np.ndarray, sr: int, sw: int = 2, ch: int = 1):
        """Store last audio for replay."""
        self.last_ai_audio = audio_array
        self.last_ai_audio_sr = sr
        self.last_ai_audio_sw = sw
        self.last_ai_audio_ch = ch
    
    def play_last_audio(self):
        """Play the last stored audio."""
        if self.last_ai_audio is not None:
            self.play_audio(self.last_ai_audio, self.last_ai_audio_sr, self.last_ai_audio_sw, self.last_ai_audio_ch)

