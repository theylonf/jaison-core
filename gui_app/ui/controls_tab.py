"""Controls tab UI component."""

from PySide6 import QtWidgets


class ControlsTab(QtWidgets.QWidget):
    """Controls tab for server and plugin management."""
    
    def __init__(self):
        super().__init__()
        self._build_ui()
    
    def _build_ui(self):
        form = QtWidgets.QFormLayout(self)
        
        self.host = QtWidgets.QLineEdit("127.0.0.1")
        self.port = QtWidgets.QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(7272)
        self.config_name = QtWidgets.QLineEdit("sammy")
        self.user_name = QtWidgets.QLineEdit("Você")
        
        # Contexto do usuário (prompt configurável)
        self.user_context = QtWidgets.QTextEdit()
        self.user_context.setPlaceholderText(
            "Exemplo:\n"
            "Nome: João\n"
            "Idade: 25 anos\n"
            "Profissão: Desenvolvedor\n"
            "Interesses: Programação, jogos, música\n"
            "Personalidade: Extrovertido, curioso, gosta de aprender coisas novas\n"
            "Contexto adicional: Trabalha remotamente, gosta de café"
        )
        self.user_context.setMaximumHeight(150)
        self.btn_update_user_context = QtWidgets.QPushButton("Atualizar Contexto do Usuário")
        
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
        form.addRow("Nome do Usuário:", self.user_name)
        form.addRow("Contexto do Usuário:", self.user_context)
        form.addRow(self.btn_update_user_context)
        form.addRow(self.btn_start_server, self.btn_stop_server)
        form.addRow(self.btn_start_plugin, self.btn_stop_plugin)
        form.addRow(QtWidgets.QLabel("Logs do Servidor:"), self.btn_clear_server_log)
        form.addRow(self.server_log)
        form.addRow(QtWidgets.QLabel("Logs do Plugin:"), self.btn_clear_plugin_log)
        form.addRow(self.plugin_log)

