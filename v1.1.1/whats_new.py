"""This file contains new feature messages to communicate updates to the user"""

from PyQt6.QtWidgets import QDialog, QPushButton, QVBoxLayout, QLabel, QHBoxLayout,QStyle
from PyQt6.QtGui import QGuiApplication,QIcon
from PyQt6.QtCore import Qt

class WhatsNewDialog(QDialog):
    def __init__(self, messages, parent=None):
        super().__init__(parent)
        
        self.messages = messages
        self.current_index = 0

        # Configure dialog appearance
        self.setWindowTitle("键盘快捷键提示")
        # 获取屏幕分辨率
        screen = QGuiApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        # 计算窗口的宽度和高度为屏幕的1/4
        window_width = screen_width // 4
        window_height = screen_height // 4
        
        self.setFixedSize(window_width, window_height)

        """将对话框居中显示在屏幕上"""
        screen = QGuiApplication.primaryScreen().availableGeometry()
        size = self.geometry()
        self.move(int((screen.width() - size.width()) / 2),
                  int((screen.height() - size.height()) / 2))
        
        # Setup UI components

        self.layout = QVBoxLayout(self)
        
        # 设置左上角的窗口图标
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        self.setWindowIcon(icon)

        self.message_label = QLabel(self)
        self.message_label.setStyleSheet("""
            QLabel {
                font-family: Trebuchet MS;
                font-size: 12pt;
                font-weight: bold;
            }
        """)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        self.layout.addWidget(self.message_label)

        self.button_layout = QHBoxLayout()
        # 定义按钮的基础样式、悬停效果、点击反馈
        button_style = """
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px 10px;
            }

            QPushButton:hover {
                background-color: #e0e0e0;
            }

            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """
        self.prev_button = QPushButton("上一个", self)
        self.prev_button.clicked.connect(self.show_previous_message)
        self.prev_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("下一个", self)
        self.next_button.clicked.connect(self.show_next_message)
        self.next_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.next_button)

        self.close_button = QPushButton("关闭", self)
        self.close_button.clicked.connect(self.accept)
        self.close_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.close_button)

        self.layout.addLayout(self.button_layout)
        self.setLayout(self.layout)

        self.show_current_message()

    def show_current_message(self):
        self.message_label.setText(self.messages[self.current_index])
        self.prev_button.setEnabled(self.current_index > 0)
        self.next_button.setEnabled(self.current_index < len(self.messages) - 1)

    def show_previous_message(self):
        if self.current_index > 0:
            self.current_index -= 1
        self.show_current_message()

    def show_next_message(self):
        if self.current_index < len(self.messages) - 1:
            self.current_index += 1
        self.show_current_message()

new_features = {
    'nt': [
        'Ctrl+Z：撤销文件加载、裁剪或基线编辑。\nCtrl+Shift+Z：重做操作。',
        'Ctrl+L：快捷键加载光谱按钮。',
        'Ctrl+E：快速估算基线,\n然后再次按下以应用基线校正。',
        'Ctrl+R：激活裁剪模式。\n点击并拖动以选择要裁剪的区域，\n然后再次按下以应用裁剪。',
        'Ctrl+D：离散化基线，\n然后再点击并拖动离散基线点以编辑线条。',
        'Ctrl+S：保存光谱。',
        '注意！\n按下关闭按钮后，后续程序将不会再弹出该窗口'
    ],
    'posix': [
        'Ctrl+Z：撤销文件加载、裁剪或基线编辑。\nCtrl+Shift+Z：重做操作。',
        'Ctrl+L：快捷键加载光谱按钮。',
        'Ctrl+E：快速估算基线,\n然后再次按下以应用基线校正。',
        'Ctrl+R：激活裁剪模式。\n点击并拖动以选择要裁剪的区域，\n然后再次按下以应用裁剪。',
        'Ctrl+D：离散化基线，\n然后再点击并拖动离散基线点以编辑线条。',
        'Ctrl+S：保存光谱。',
        '注意！\n按下关闭按钮后，后续程序将不会再弹出该窗口'
    ]
}