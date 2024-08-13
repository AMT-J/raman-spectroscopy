"""This module contains the code for the GUI"""

import os
import sys
from pathlib import Path
import json
import threading

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
                            QLabel, QLineEdit, QPushButton, QTextEdit, QGridLayout, QDialog,QGraphicsDropShadowEffect,
                            QFileDialog, QMessageBox, QListWidget, QListView)
from PyQt6.QtGui import QColor, QShortcut, QKeySequence,QGuiApplication,QIcon
from PyQt6.QtCore import Qt
import pyqtgraph as pg

import numpy as np
import sqlite3

from utils import find_spectrum_matches, get_unique_mineral_combinations_optimized
from utils import get_xy_from_file, deserialize, baseline_als, get_peaks

from discretize import DraggableGraph, DraggableScatter
from spectra import Spectrum
from plots import CroppablePlotWidget
from commands import CommandHistory, LoadSpectrumCommand, PointDragCommand
from commands import CommandSpectrum, EstimateBaselineCommand, CorrectBaselineCommand
from commands import CropCommand

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'Raman Spectra Analyzer'
        self.database_path = None
        self.baseline_data = None
        self.baseline_plot = None
        self.loaded_spectrum = None
        self.spectrum = None
        self.cropping = False
        self.crop_region = None
        with open('config.json', 'r') as f:
            self.config = json.load(f)
        self.init_UI()
        self.Resize()
        self.init_keyboard_shortcuts()

        self.command_history = CommandHistory()

    def resizeEvent(self, event):
        """Ensure both plot widgets have the same width and height during resize"""
        # Let the resizing occur
        QApplication.processEvents()

        # Get the maximum width and height of the two plot widgets
        max_width = max(self.plot1.width(), self.plot2.width())
        max_height = max(self.plot1.height(), self.plot2.height())

        # Set both plot widgets to have that max width and height as their minimum dimensions
        self.plot1.setMinimumWidth(max_width)
        self.plot1.setMinimumHeight(max_height)
        self.plot2.setMinimumWidth(max_width)
        self.plot2.setMinimumHeight(max_height)

        # Additionally, set their size policy to be Preferred for both width and height
        policy1 = self.plot1.sizePolicy()
        policy1.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        policy1.setVerticalPolicy(QSizePolicy.Policy.Preferred)
        self.plot1.setSizePolicy(policy1)

        policy2 = self.plot2.sizePolicy()
        policy2.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        policy2.setVerticalPolicy(QSizePolicy.Policy.Preferred)
        self.plot2.setSizePolicy(policy2)

        # Call the base class' method to ensure the event is handled properly
        super().resizeEvent(event)

        # Center the window on the screen
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.geometry()
        new_x = (screen_geometry.width() - window_geometry.width()) // 2
        new_y = (screen_geometry.height() - window_geometry.height()) // 2
        self.move(new_x, new_y)


    def Resize(self):
        screen_geometry = QApplication.primaryScreen().geometry()
        half_screen_size = screen_geometry.width()  *2// 3, screen_geometry.height() //2
        self.resize(*half_screen_size)

    def show_whats_new(self):
        # Load the new features from whats_new.py
        try:
            from whats_new import new_features, WhatsNewDialog
            platform_key = 'nt' if os.name == 'nt' else 'posix'
            messages = new_features.get(platform_key, [])

            # Display the custom dialog
            dialog = WhatsNewDialog(messages, self)
            response = dialog.exec()
            
            # If the dialog was closed after viewing all messages, set show_whats_new to False
            if response == QDialog.DialogCode.Accepted and dialog.current_index == len(messages) - 1:
                self.config['show_whats_new'] = False
                with open('config.json', 'w') as f:
                    json.dump(self.config, f, indent=4)

        except ImportError:
            pass  # If whats_new.py is not found, just skip showing the messages

    def init_keyboard_shortcuts(self):
        undo_shortcut = QShortcut(QKeySequence('Ctrl+Z'), self)
        undo_shortcut.activated.connect(self.undo)

        redo_shortcut = QShortcut(QKeySequence('Ctrl+Shift+Z'), self)
        redo_shortcut.activated.connect(self.redo)

        load_spectrum_shortcut = QShortcut(QKeySequence('Ctrl+L'), self)
        load_spectrum_shortcut.activated.connect(self.load_unknown_spectrum)

        crop_shortcut = QShortcut(QKeySequence('Ctrl+R'), self)
        crop_shortcut.activated.connect(self.toggle_crop_mode)

        baseline_shortcut = QShortcut(QKeySequence('Ctrl+E'), self)
        baseline_shortcut.activated.connect(self.baseline_callback)

        discretize_shortcut = QShortcut(QKeySequence('Ctrl+D'), self)
        discretize_shortcut.activated.connect(self.discretize_baseline)

        save_shortcut = QShortcut(QKeySequence('Ctrl+S'), self)
        save_shortcut.activated.connect(self.save_edited_spectrum)
        
    def undo(self):
        print('Undo activated')
        self.command_history.undo()
    
    def redo(self):
        print('Redo activated')
        self.command_history.redo()

    def init_UI(self):
        """Initialization method for the User Interface
        main_layout
          |--search_layout
          |    |--database_layout
          |    |--peaks_layout
          |    |--tolerance_layout
          |--results_layout
          |--plot1_layout
          |--plot2_layout
        """
        # Set window icon
        self.setWindowIcon(QIcon('1.ico'))
   
        # 全局设置所有样式
        self.setStyleSheet("""
            QPushButton {
                border-radius: 5px;              
                background-color: #ADD8E6;       /* 淡蓝色背景 */
                border: 1px solid #B0C4DE;       /* 边框颜色 */
                font-family: 'Segoe UI';   
                font-size: 12pt;
            }

            QPushButton:hover {
                background-color: #87CEEB;       /* 悬停时稍深的蓝色 */
                border: 1px solid #A2B5CD;       /* 悬停时的边框颜色 */
            }

            QPushButton:pressed {
                background-color: #4682B4;       /* 点击时更深的蓝色 */
                border: 2px solid #4682B4;       /* 点击时的边框颜色 */
            }
                           
            QLabel {
                font-family: 'Segoe UI';   /* 字体类型 */
                font-size: 12pt;           /* 字体大小 */
                color: #333333;            /* 字体颜色 */
            }
                    
            QLineEdit {
                border-radius: 5px;                      /* 圆角 */
                border: 1px solid #b0b0b0;              /* 边框颜色和宽度 */
                padding: 5px;                           /* 内边距 */
                background-color: #f0f8ff;              /* 背景色（淡蓝色） */
                font-family: 'Segoe UI';                /* 字体 */
                font-size: 12pt;                        /* 字体大小 */
            }

            QLineEdit:hover {
                border: 1px solid #808080;              /* 鼠标悬停时的边框颜色 */
                background-color: #e6f2ff;              /* 鼠标悬停时的背景色（稍深的蓝色） */
            }

            QLineEdit:focus {
                border: 1px solid #4682b4;              /* 获取焦点时的边框颜色 */
                background-color: #d9ecff;              /* 获取焦点时的背景色 */
            }
                           
            
            QTextEdit {
                background-color: #ffffff;  /* 白色背景 */
                border: 1px solid #b0b0b0;  /* 边框颜色 */
                border-radius: 5px;         /* 圆角边框 */
                font-family: 'Segoe UI';    /* 字体类型 */
                font-size: 12pt;            /* 字体大小 */
            }

         
            QTextEdit:hover {
                border: 1px solid #808080;
                background-color: #e6f0ff;  /* 悬停时稍深的蓝色背景 */
            }
            QTextEdit:focus {
                border: 1px solid #4682b4;              /* 获取焦点时的边框颜色 */
                background-color: #d9ecff;              /* 获取焦点时的背景色 */
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # DATABASE & SEARCH AREA
        search_layout = QHBoxLayout()
        search_widget = QWidget()
        search_widget.setLayout(search_layout)

        # Database selection
        database_layout = QHBoxLayout()
        database_widget = QWidget()
        database_widget.setLayout(database_layout)
        self.database_label = QLabel("数据库：未选择", self)
        self.load_database_button = QPushButton('加载数据库', self)
        self.load_database_button.clicked.connect(self.load_database_file)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.load_database_button)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.load_database_button.setGraphicsEffect(shadow_effect)
        database_layout.addWidget(self.database_label)
        database_layout.addWidget(self.load_database_button)
        search_layout.addWidget(database_widget)
        
        # Peaks entry 
        peaks_layout = QHBoxLayout()
        peaks_widget = QWidget()
        peaks_widget.setLayout(peaks_layout)
        self.label_peaks = QLabel("峰值（逗号分隔）：", self)
        self.textbox_peaks = QLineEdit(self)
        peaks_layout.addWidget(self.label_peaks)
        peaks_layout.addWidget(self.textbox_peaks)
        search_layout.addWidget(peaks_widget)

        # Tolerance Entry
        tolerance_layout = QHBoxLayout()
        tolerance_widget = QWidget()
        tolerance_widget.setLayout(tolerance_layout)
        self.label_tolerance = QLabel("容差：", self)
        self.textbox_tolerance = QLineEdit(self)
        tolerance_layout.addWidget(self.label_tolerance)
        tolerance_layout.addWidget(self.textbox_tolerance)
        search_layout.addWidget(tolerance_widget)

        # Search Button
        self.button_search = QPushButton('搜索', self)
        self.button_search.clicked.connect(self.on_search)
        search_layout.addWidget(self.button_search)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.button_search)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.button_search.setGraphicsEffect(shadow_effect)
        main_layout.addWidget(search_widget)

        # RESULTS AREA
        results_layout = QHBoxLayout()
        results_widget = QWidget()
        results_widget.setLayout(results_layout)
        self.result_single = QTextEdit(self)
        self.result_double = QTextEdit(self)
        self.result_triple = QTextEdit(self)
        
        # Set QTextEdit widgets to be read-only and disable text selection
        ''''
        for text_edit in [self.result_single, self.result_double, self.result_triple]:
            text_edit.setReadOnly(True)
        '''
            
              
        results_layout.addWidget(self.result_single)
        results_layout.addWidget(self.result_double)
        results_layout.addWidget(self.result_triple)
        main_layout.addWidget(results_widget)

        # ADD A THIN LINE HERE

        # LOADED SPECTRUM GRAPH AND UTILITIES
        plot1_layout = QGridLayout()
        plot1_widget = QWidget()
        plot1_widget.setLayout(plot1_layout)
        plot1_layout.setColumnStretch(0, 1) # TODO align more precisely
        plot1_buttons_layout = QVBoxLayout()
        plot1_buttons_widget = QWidget()
        plot1_buttons_widget.setLayout(plot1_buttons_layout)
        plot1_layout.addWidget(plot1_buttons_widget, 0, 2, 1, 1)
        main_layout.addWidget(plot1_widget)
        
        # PlotWidget: Plot 1
        #self.plot1 = pg.PlotWidget(self)
        self.plot1 = CroppablePlotWidget(self)
        self.plot1.setLabel('left', '强度')
        self.plot1.setLabel('bottom', '拉曼位移', units='cm<sup>-1</sup>')
        plot1_layout.addWidget(self.plot1, 0, 0, 1, 2)

        # Button: load spectrum
        self.button_load_file = QPushButton('加载文件', self)
        self.button_load_file.clicked.connect(self.load_unknown_spectrum)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.button_load_file)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.button_load_file.setGraphicsEffect(shadow_effect)
        plot1_buttons_layout.addWidget(self.button_load_file)

        # Button: estimate / correct baseline
        self.button_baseline = QPushButton('基线估计', self)
        self.button_baseline.clicked.connect(self.baseline_callback)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.button_baseline)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.button_baseline.setGraphicsEffect(shadow_effect)
        plot1_buttons_layout.addWidget(self.button_baseline)

        # Button: discretize baseline
        self.button_discretize = QPushButton('基线离散化', self)
        self.button_discretize.clicked.connect(self.discretize_baseline)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.button_discretize)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.button_discretize.setGraphicsEffect(shadow_effect)
        plot1_buttons_layout.addWidget(self.button_discretize)

        # Button: crop
        self.crop_button = QPushButton("裁剪", self)
        self.crop_button.clicked.connect(self.toggle_crop_mode)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.crop_button)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.crop_button.setGraphicsEffect(shadow_effect)
        plot1_buttons_layout.addWidget(self.crop_button)

        # Button: save spectrum
        self.button_save_spectrum = QPushButton('保存光谱', self)
        self.button_save_spectrum.clicked.connect(self.save_edited_spectrum)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.button_save_spectrum)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.button_save_spectrum.setGraphicsEffect(shadow_effect)
        plot1_buttons_layout.addWidget(self.button_save_spectrum)

        # LineEdits: scipy.signal.find_peaks() parameters
        plot1_peak_params_layout = QGridLayout()
        plot1_peak_params_widget = QWidget()
        plot1_peak_params_widget.setLayout(plot1_peak_params_layout)
        plot1_buttons_layout.addWidget(plot1_peak_params_widget)

        # LineEdit: width
        self.textbox_width = QLineEdit(self)
        self.textbox_width.setPlaceholderText('宽度')
        plot1_peak_params_layout.addWidget(self.textbox_width, 0, 0)

        # LineEdit: rel_height
        self.textbox_rel_height = QLineEdit(self)
        self.textbox_rel_height.setPlaceholderText('相对高度')
        plot1_peak_params_layout.addWidget(self.textbox_rel_height, 0, 1)

        # LineEdit: height
        self.textbox_height = QLineEdit(self)
        self.textbox_height.setPlaceholderText('高度')
        plot1_peak_params_layout.addWidget(self.textbox_height, 1, 0)

        # LineEdit: prominence
        self.textbox_prominence = QLineEdit(self)
        self.textbox_prominence.setPlaceholderText('显著性')
        plot1_peak_params_layout.addWidget(self.textbox_prominence, 1, 1)

        # Button: Find peaks
        plot1_peaks_buttons_layout = QHBoxLayout()
        plot1_peaks_buttons_widget = QWidget()
        plot1_peaks_buttons_widget.setLayout(plot1_peaks_buttons_layout)
        plot1_buttons_layout.addWidget(plot1_peaks_buttons_widget)

        self.button_find_peaks = QPushButton('寻找峰值', self)
        self.button_find_peaks.clicked.connect(self.find_peaks)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.button_find_peaks)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.button_find_peaks.setGraphicsEffect(shadow_effect)
        #plot1_buttons_layout.addWidget(self.button_find_peaks)
        plot1_peaks_buttons_layout.addWidget(self.button_find_peaks)

        # Button: Show peak positions
        self.button_show_peak_labels = QPushButton('显示标签', self)
        self.button_show_peak_labels.clicked.connect(self.toggle_labels_callback)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.button_show_peak_labels)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.button_show_peak_labels.setGraphicsEffect(shadow_effect)
        plot1_peaks_buttons_layout.addWidget(self.button_show_peak_labels)

        # LisWidget: Log for Plot 1
        self.plot1_log = QListWidget()
        plot1_buttons_layout.addWidget(self.plot1_log)

        # ADD A THIN LINE

        # DATABASE SPECTRA GRAPH AND UTILITIES
        plot2_layout = QGridLayout()
        plot2_widget = QWidget()
        plot2_widget.setLayout(plot2_layout)
        plot2_layout.setColumnStretch(0, 1)
        main_layout.addWidget(plot2_widget)
        plot2_buttons_layout = QVBoxLayout()
        plot2_buttons_widget = QWidget()
        plot2_buttons_widget.setLayout(plot2_buttons_layout)
        plot2_layout.addWidget(plot2_buttons_widget, 0, 2, 1, 1)

        # PlotWidget: Plot 2
        self.plot2 = pg.PlotWidget(self)
        self.plot2.setLabel('left', '强度')
        self.plot2.setLabel('bottom', '拉曼位移', units='cm<sup>-1</sup>')
        plot2_layout.addWidget(self.plot2, 0, 0, 1, 2)
        
        # LineEdit: mineral name
        # TODO add auto-fill from database here
        self.mineral_input = QLineEdit(self)
        self.mineral_input.setPlaceholderText("输入矿物名称")
        plot2_buttons_layout.addWidget(self.mineral_input)

        # LineEdit: wavelength
        self.wavelength_input = QLineEdit(self)
        self.wavelength_input.setPlaceholderText("输入波长")
        plot2_buttons_layout.addWidget(self.wavelength_input)

        # Button: search database
        self.search_button = QPushButton('搜索', self)
        self.search_button.clicked.connect(self.search_database)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.search_button)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.search_button.setGraphicsEffect(shadow_effect)
        plot2_buttons_layout.addWidget(self.search_button)

        # Button: plot selected spectra
        self.plot_button = QPushButton('绘制光谱', self)
        self.plot_button.clicked.connect(self.plot_selected_spectra)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.plot_button)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.plot_button.setGraphicsEffect(shadow_effect)
        plot2_buttons_layout.addWidget(self.plot_button)

        # Button: Align axes with above graph
        self.align_button = QPushButton('对齐X轴', self)
        self.align_button.clicked.connect(self.match_range)
        # Add shadow effect
        shadow_effect = QGraphicsDropShadowEffect(self.align_button)
        shadow_effect.setBlurRadius(10)  # 模糊半径，越大阴影越柔和
        shadow_effect.setXOffset(3)  # X轴偏移
        shadow_effect.setYOffset(3)  # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色，灰色带一点透明度

        self.align_button.setGraphicsEffect(shadow_effect)
        plot2_buttons_layout.addWidget(self.align_button)

        # ListWidget: results from searching database
        self.results_list = QListWidget(self)
        self.results_list.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        plot2_buttons_layout.addWidget(self.results_list)
        
        # Setting central widget and layout
        self.setWindowTitle(self.title)
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setLayout(main_layout)
        self.show()

    def toggle_crop_mode(self):
        if self.cropping:
            self.crop_region = self.plot1.get_crop_region()
            self.apply_crop()
            self.crop_button.setText("裁剪")
            self.cropping = False
            self.plot1.cropping = self.cropping
            if self.crop_region:
                self.plot1.removeItem(self.crop_region)
                self.crop_region = None
        else:
            self.crop_button.setText("应用裁剪")
            self.cropping = True
            self.plot1.cropping = self.cropping

    def save_edited_spectrum(self):
        default_name = f"{self.unknown_spectrum_path.stem}_processed.txt"
        suggested_path = self.unknown_spectrum_path.parent / default_name
        #options = QFileDialog.Option()
        fname, _ = QFileDialog.getSaveFileName(self, "Save Spectrum", str(suggested_path), "Text Files (*.txt);;All Files (*)")

        if fname:  # Check if user didn't cancel the dialog
            with open(fname, 'w') as f:
                for x, y in zip(self.spectrum.x, self.spectrum.y):
                    f.write(f"{x} {y}\n")
            
            self.plot1_log.addItem(f'Saved edited spectrum to: {fname}')

    def apply_crop(self):
        # If there's no crop_region, do nothing.
        if self.crop_region is None:
            return
        
        crop_start_x, crop_end_x = self.crop_region.getRegion()
        
        command = CropCommand(self, crop_start_x, crop_end_x)
        self.command_history.execute(command)

        # Remove the crop_region item from the plot.
        self.plot1.removeItem(self.crop_region)
        self.crop_region = None
        self.plot1.crop_region = None


    def update_discretized_baseline(self):
        """Updates the baseline data of the loaded spectrum whenever user moves a point after discretization"""
        self.draggableGraph.setData(pos=np.array(list(zip(self.draggableScatter.data['x'], self.draggableScatter.data['y']))))
        self.baseline_data = np.interp(self.spectrum.x, self.draggableScatter.data['x'], self.draggableScatter.data['y'])
        if hasattr(self, 'interpolated_baseline'):
            self.plot1.removeItem(self.interpolated_baseline)
        self.interpolated_baseline = self.plot1.plot(self.spectrum.x, self.baseline_data, pen='g')

    def discretize_baseline(self):
        # Discretizing the baseline
        x_vals = np.arange(self.spectrum.x[0], self.spectrum.x[-1], self.config['discrete baseline step size'])
        y_vals = np.interp(x_vals, self.spectrum.x, self.baseline_data)

        # Clear the previous discretized baseline if it exists
        if hasattr(self, 'draggableScatter'):
            self.plot1.removeItem(self.draggableScatter)
        if hasattr(self, 'draggableGraph'):
            self.plot1.removeItem(self.draggableGraph)

        # TODO fix color not working... not sure if we need to set bursh or color or symbolBrush or pen or what...
        self.draggableScatter = DraggableScatter(x=x_vals, y=y_vals, size=self.config['discrete baseline point size'], symbolBrush=eval(self.config['discrete baseline point color']))
        self.draggableScatter.pointDragged.connect(self.update_discretized_baseline)
        self.draggableScatter.dragFinished.connect(self.handle_drag_finished)
        self.draggableGraph = DraggableGraph(scatter_data={'x': x_vals, 'y': y_vals})
        
        self.plot1.addItem(self.draggableScatter)
        self.plot1.addItem(self.draggableGraph)

        # Replace the smooth baseline with the discretized one
        self.plot1.removeItem(self.baseline_plot)

    def handle_drag_finished(self, index, startX, startY, endX, endY):
        print('handle_drag_finished was called')
        command = PointDragCommand(self, index, startX, startY, endX, endY)
        self.command_history.execute(command)

    def match_range(self):
        name = self.align_button.text()
        if name == '对齐X轴':
            if self.spectrum.x is not None:
                lower, upper = min(self.spectrum.x), max(self.spectrum.x)
                self.plot2.setXRange(lower, upper)
                self.align_button.setText('重置X轴')
        else: # Reset case
            self.plot2.autoRange()
            self.align_button.setText('对齐X轴')

    def load_database_file(self):
        # 获取当前工作目录
        current_directory = Path('.').resolve()
        
        # 打开文件对话框，默认路径为当前工作目录
        fname = QFileDialog.getOpenFileName(self, 'Open Database', str(current_directory), "Database Files (*.db);")
        
        if fname[0]:
            self.database_path = Path(fname[0])
            self.database_label.setText(f"Database: {self.database_path.name}")


    def load_unknown_spectrum(self):
        fname = QFileDialog.getOpenFileName(self, 'Select Raman Spectrum', '..')
        if fname[0]:
            self.unknown_spectrum_path = Path(fname[0])
            command = LoadSpectrumCommand(self, *get_xy_from_file(self.unknown_spectrum_path))
            self.command_history.execute(command)

    def baseline_callback(self):
        if self.button_baseline.text() == "基线估计":
            command = EstimateBaselineCommand(self, baseline_als(self.spectrum.y))
            self.command_history.execute(command)
        else:
            command = CorrectBaselineCommand(self)
            self.command_history.execute(command)

    def search_database(self):
        if self.database_label.text() == "数据库：未选择":
            # Show an error message
            QMessageBox.critical(self, 'Error', 'Please select a database first.')
            return
        mineral_name = self.mineral_input.text()
        wavelength = self.wavelength_input.text()

        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

        # Convert the mineral name to lowercase
        mineral_name_lower = mineral_name.lower()

        # Search takes place in its own thread (not quite working yet)
        # TODO fix threading
        if wavelength != '':
            # Use the LOWER function on names column and = operator for comparison
            cursor.execute("SELECT filename, data_x, data_y FROM Spectra WHERE LOWER(names) = ? AND wavelength=?", (mineral_name_lower, wavelength))
        else:
            cursor.execute("SELECT filename, data_x, data_y FROM Spectra WHERE LOWER(names) = ?", (mineral_name_lower,))
        results = cursor.fetchall()

        # Populate the results list
        self.results_list.clear()
        self.data_to_plot = {}
        for result in results:
            self.results_list.addItem(result[0])
            self.data_to_plot[result[0]] = (result[1], result[2])

        connection.close()  
        

    def plot_selected_spectra(self):
        selected_files = [item.text() for item in self.results_list.selectedItems()]
        
        # Clear previous plots
        self.plot2.clear()

        for file in selected_files:
            data_x, data_y = self.data_to_plot[file]
            x = deserialize(data_x)
            y = deserialize(data_y)
            self.plot2.plot(x, y)
        
        self.plot2.autoRange()

    def toggle_labels_callback(self):
        # Remove any previous text items (assuming you have them stored in a list attribute `self.peak_texts`)
        if hasattr(self, 'peak_texts') and self.peak_texts:
            for text_item in self.peak_texts:
                self.plot1.removeItem(text_item)
            self.peak_texts = []

        show = self.button_show_peak_labels.text() == '显示标签'

        if show:
            # Create and add the text items to the plot
            for x, y in zip(self.peaks_x, self.peaks_y):
                text_item = pg.TextItem(str(round(x, 1)), anchor=(0, 0), color=(255, 0, 0), angle=90)
                text_item.setPos(x, y)  # Adjusting the y position to be slightly above the peak
                self.plot1.addItem(text_item)
                if not hasattr(self, 'peak_texts'):
                    self.peak_texts = []
                self.peak_texts.append(text_item)
            self.button_show_peak_labels.setText('隐藏标签')
        else:
            self.button_show_peak_labels.setText('显示标签')
        
    def find_peaks(self):
        width = self.textbox_width.text()
        rel_height = self.textbox_rel_height.text()
        height = self.textbox_height.text()
        prominence = self.textbox_prominence.text()

        width = eval(width) if width else None
        rel_height = float(rel_height) if rel_height else None
        height = float(height) if height else None
        prominence = float(prominence) if prominence else None

        self.peaks_x, self.peaks_y = get_peaks(
            self.spectrum.x, 
            self.spectrum.y, 
            width=width, 
            rel_height=rel_height, 
            height=height, 
            prominence=prominence)
        
        if hasattr(self, 'peak_plot') and self.peak_plot:
            self.plot1.removeItem(self.peak_plot)
            self.peak_plot = None
        self.peak_plot = self.plot1.plot(self.peaks_x, self.peaks_y, pen=None, symbol='o', symbolSize=7, symbolBrush=(255, 0, 0))
        
        if len(self.peaks_x) < 15:
            self.plot1_log.addItem(f'Peaks: {", ".join([str(x) for x in sorted(self.peaks_x)])}')
            self.textbox_peaks.setText(','.join([str(round(x,1)) for x in sorted(self.peaks_x)]))
        else:
            first_15_peaks = self.peaks_x[:15]
            self.plot1_log.addItem(f'Peaks: {", ".join([str(x) for x in sorted(first_15_peaks)])}...')
            self.textbox_peaks.setText(','.join([str(round(x,1)) for x in sorted(first_15_peaks)]))

    def on_search(self):
        if self.database_label.text() == "数据库：未选择":
            # Show an error message
            QMessageBox.critical(self, 'Error', 'Please select a database first.')
            return
    
        # 1. Get values from textboxes
        peaks = self.textbox_peaks.text().split(',')
        peaks = [float(x) for x in peaks]
        tolerance = float(self.textbox_tolerance.text())
        
        # 2. Call search function
        result = find_spectrum_matches(self.database_path, peaks, tolerance) # Dict with keys 1,2,3
        unqiue_singletons = sorted(get_unique_mineral_combinations_optimized(self.database_path, result[1]))
        unique_pairs = sorted(get_unique_mineral_combinations_optimized(self.database_path, result[2]))
        unique_triples = sorted(get_unique_mineral_combinations_optimized(self.database_path, result[3]))
        msg_singletons = f'Found {len(unqiue_singletons)} unique mineral(s) containing your peak(s):\n'
        msg_pairs = f'Found {len(unique_pairs)} unique combinations of 2 minerals matching your peak(s):\n'
        msg_triples = f'Found {len(unique_triples)} unique combinations of 3 minerals matching your peak(s):\n'
        
        # 3. Populate the QTextEdits with the results:
        self.result_single.setText(msg_singletons)
        self.result_double.setText(msg_pairs)
        self.result_triple.setText(msg_triples)

        for line in unqiue_singletons:
            self.result_single.append(line[0])
        for line in unique_pairs:
            self.result_double.append(f'{line[0]},   {line[1]}')
        for line in unique_triples:
            self.result_triple.append(f'{line[0]},   {line[1]},   {line[2]}')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MainApp()
    if ex.config.get('show_whats_new', False):
        ex.show_whats_new()
    ex.show()
    sys.exit(app.exec())