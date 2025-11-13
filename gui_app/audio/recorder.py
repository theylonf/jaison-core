"""Audio recording handler."""

import time
import threading
from typing import Optional, Callable, Tuple

import sounddevice as sd
import numpy as np


class AudioRecorder:
    """Handles manual audio recording."""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.is_recording = False
        self.audio_data = []
        self.recorded_audio = None
        self._recording_chunks_count = 0
        self.audio_input_device = None
        
        self.on_log: Optional[Callable] = None
    
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
                if self.on_log:
                    self.on_log(f"[Audio] ❌ Erro na gravação: {e}")
        
        threading.Thread(target=record_thread, daemon=True).start()
    
    def stop_recording(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """Stop manual recording. Returns (success, audio_array, duration)."""
        self.is_recording = False
        time.sleep(0.2)
        
        if self.audio_data and len(self.audio_data) > 0:
            try:
                audio_array = np.concatenate(self.audio_data, axis=0)
                duration = len(audio_array) / self.sample_rate
                return True, audio_array, duration
            except Exception as e:
                if self.on_log:
                    self.on_log(f"[Audio] ❌ Erro ao processar áudio: {e}")
                return False, None, 0.0
        return False, None, 0.0
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Audio callback for recording."""
        if self.is_recording:
            chunk = indata.copy()
            self.audio_data.append(chunk)
            self._recording_chunks_count += 1
            if self._recording_chunks_count <= 3 and self.on_log:
                self.on_log(f"[Audio] Chunk #{self._recording_chunks_count} recebido: {len(chunk)} frames")

