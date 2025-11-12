"""Custom UI components for the JAIson GUI application."""

from PySide6 import QtCore, QtWidgets, QtGui


class AudioLevelWithThreshold(QtWidgets.QWidget):
    """Custom widget to display audio level with threshold indicator."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.level_value = 0
        self.threshold_value = 500
        self.max_value = 2000
        self.setMinimumHeight(25)
        self.setMaximumHeight(25)
    
    def set_level(self, value):
        """Set the current audio level."""
        self.level_value = min(value, self.max_value)
        self.update()
    
    def set_threshold(self, value):
        """Set the threshold value."""
        self.threshold_value = min(value, self.max_value)
        self.update()
    
    def paintEvent(self, event):
        """Paint the audio level bar with threshold line."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        width = rect.width()
        height = rect.height()
        
        # Draw background
        bg_rect = QtCore.QRect(0, 0, width, height)
        painter.fillRect(bg_rect, QtCore.Qt.GlobalColor.lightGray)
        
        # Calculate positions
        level_pos = int((self.level_value / self.max_value) * width)
        threshold_pos = int((self.threshold_value / self.max_value) * width)
        
        # Draw level bar (green if above threshold, gray if below)
        if self.level_value > self.threshold_value:
            level_color = QtGui.QColor(76, 175, 80)  # Green
        else:
            level_color = QtGui.QColor(158, 158, 158)  # Gray
        
        level_rect = QtCore.QRect(0, 0, level_pos, height)
        painter.fillRect(level_rect, level_color)
        
        # Draw threshold line (red vertical line)
        threshold_color = QtGui.QColor(255, 87, 34)  # Red-orange
        painter.setPen(QtGui.QPen(threshold_color, 2))
        painter.drawLine(threshold_pos, 0, threshold_pos, height)
        
        # Draw text
        painter.setPen(QtCore.Qt.GlobalColor.black)
        text = f"{self.level_value} / {self.threshold_value}"
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)




