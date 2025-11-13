"""Audio device selection manager."""

import sounddevice as sd
from PySide6 import QtWidgets
from typing import Optional


class AudioDeviceManager:
    """Manages audio input and output device selection."""
    
    def __init__(self):
        self.audio_output_device: Optional[int] = None
        self.audio_input_device: Optional[int] = None
    
    def select_output_device(self, parent_widget=None) -> bool:
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
                return False
            
            dialog = QtWidgets.QDialog(parent_widget)
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
            buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Reset).clicked.connect(
                lambda: self._reset_output_device(dialog)
            )
            layout.addWidget(buttons)
            
            if dialog.exec():
                selected = list_widget.currentRow()
                if selected >= 0:
                    self.audio_output_device = output_devices[selected]
                    return True
            return False
        except Exception:
            return False
    
    def select_input_device(self, parent_widget=None) -> bool:
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
                return False
            
            dialog = QtWidgets.QDialog(parent_widget)
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
            buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Reset).clicked.connect(
                lambda: self._reset_input_device(dialog)
            )
            layout.addWidget(buttons)
            
            if dialog.exec():
                selected = list_widget.currentRow()
                if selected >= 0:
                    self.audio_input_device = input_devices[selected]
                    return True
            return False
        except Exception:
            return False
    
    def _reset_output_device(self, dialog):
        """Reset to default audio output device."""
        self.audio_output_device = None
        dialog.accept()
    
    def _reset_input_device(self, dialog):
        """Reset to default audio input device."""
        self.audio_input_device = None
        dialog.accept()
    
    def get_output_device_name(self) -> str:
        """Get name of selected output device."""
        if self.audio_output_device is None:
            return "Padrão"
        try:
            devices = sd.query_devices()
            return devices[self.audio_output_device]['name']
        except Exception:
            return "Desconhecido"
    
    def get_input_device_name(self) -> str:
        """Get name of selected input device."""
        if self.audio_input_device is None:
            return "Padrão"
        try:
            devices = sd.query_devices()
            return devices[self.audio_input_device]['name']
        except Exception:
            return "Desconhecido"


