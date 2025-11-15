"""Chat tab UI component."""

from PySide6 import QtCore, QtWidgets, QtGui

try:
    from ..ui_components import AudioLevelWithThreshold
except ImportError:
    from ui_components import AudioLevelWithThreshold


class ChatTab(QtWidgets.QWidget):
    """Chat tab for text and audio communication."""
    
    def __init__(self):
        super().__init__()
        self._build_ui()
    
    def _build_ui(self):
        vbox = QtWidgets.QVBoxLayout(self)
        
        hbox_chat_header = QtWidgets.QHBoxLayout()
        hbox_chat_header.addWidget(QtWidgets.QLabel("Histórico do Chat:"))
        self.btn_clear_chat = QtWidgets.QPushButton("Limpar Chat")
        hbox_chat_header.addWidget(self.btn_clear_chat, 0)
        hbox_chat_header.addStretch(1)
        
        # Use QTextEdit instead of QPlainTextEdit to support images
        self.chat_history = QtWidgets.QTextEdit()
        self.chat_history.setReadOnly(True)
        # Enable word wrap to prevent UI stretching with long messages
        self.chat_history.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        self.chat_history.setWordWrapMode(QtGui.QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        
        hbox_text = QtWidgets.QHBoxLayout()
        self.input_text = QtWidgets.QLineEdit()
        self.btn_send_text = QtWidgets.QPushButton("Enviar texto")
        hbox_text.addWidget(self.input_text, 1)
        hbox_text.addWidget(self.btn_send_text, 0)
        
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
        
        hbox_vad_settings = QtWidgets.QHBoxLayout()
        hbox_vad_settings.addWidget(QtWidgets.QLabel("Sensibilidade:"))
        self.slider_sensitivity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_sensitivity.setMinimum(100)
        self.slider_sensitivity.setMaximum(2000)
        self.slider_sensitivity.setValue(500)
        self.slider_sensitivity.setEnabled(True)
        self.label_sensitivity = QtWidgets.QLabel("500")
        hbox_vad_settings.addWidget(self.slider_sensitivity, 1)
        hbox_vad_settings.addWidget(self.label_sensitivity)
        
        hbox_vad_settings.addWidget(QtWidgets.QLabel("  Silêncio (s):"))
        self.slider_silence = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_silence.setMinimum(5)
        self.slider_silence.setMaximum(50)
        self.slider_silence.setValue(15)
        self.slider_silence.setEnabled(False)
        self.label_silence = QtWidgets.QLabel("1.5s")
        hbox_vad_settings.addWidget(self.slider_silence, 1)
        hbox_vad_settings.addWidget(self.label_silence)
        
        self.voice_indicator = QtWidgets.QLabel("🔇")
        self.voice_indicator.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        hbox_vad_settings.addWidget(self.voice_indicator)
        
        hbox_audio_level = QtWidgets.QHBoxLayout()
        hbox_audio_level.addWidget(QtWidgets.QLabel("Nível RMS:"))
        
        self.audio_level_widget = AudioLevelWithThreshold()
        hbox_audio_level.addWidget(self.audio_level_widget, 1)
        
        self.audio_level_bar = QtWidgets.QProgressBar()
        self.audio_level_bar.setMinimum(0)
        self.audio_level_bar.setMaximum(2000)
        self.audio_level_bar.setValue(0)
        self.audio_level_bar.hide()
        
        value_container = QtWidgets.QHBoxLayout()
        self.audio_level_label = QtWidgets.QLabel("0")
        value_container.addWidget(self.audio_level_label)
        value_container.addWidget(QtWidgets.QLabel(" / "))
        self.threshold_indicator = QtWidgets.QLabel("500")
        self.threshold_indicator.setStyleSheet("font-weight: bold; color: #FF5722;")
        value_container.addWidget(self.threshold_indicator)
        hbox_audio_level.addLayout(value_container)
        
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
        vbox.addLayout(hbox_audio_playback)


