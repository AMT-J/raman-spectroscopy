"""This module contains commands for handling spectrum manipulation

Each class (aside from CommandSpectrum and CommandHistory) derive from the Command
class. Each has an `undo` and an `execute` method. The commands are stored in the
GUI's `command_history` list. This structure enables Undo/Redo functionality in the GUI.
"""

import numpy as np
from PyQt6.QtGui import QTextCursor
import pyqtgraph as pg

class Command:
    """Base class for Commands"""

    def execute(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError



class CommandSpectrum:
    """Represents a Spectrum for Command classes"""
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def copy(self):
        """Deep copy"""
        return CommandSpectrum(self.x.copy(), self.y.copy())

    def __iter__(self):
        return [self.x, self.y].__iter__()



class CommandHistory:
    """Container class for seuqnece of commands"""

    def __init__(self):
        self.commands = []
        self.index = -1

    def execute(self, command):
        """Disable further redoing after executing"""
        self.commands = self.commands[:self.index + 1]
        command.execute()
        self.commands.append(command)
        self.index += 1
    
    def undo(self):
        if self.index < 0:
            return
            # Add the "play" sound
        self.commands[self.index].undo()
        self.index -= 1

    def redo(self):
        if self.index == len(self.commands) - 1:
            return
            # Add the "play" sound
        self.index += 1
        self.commands[self.index].execute()


class LoadSpectrumCommand(Command):
    """Command to load a spectrum"""
    def __init__(self, app, xdata, ydata):
        self.app = app
        self.new_spectrum = CommandSpectrum(xdata, ydata)
        if self.app.spectrum is not None:
            self.old_spectrum = self.app.spectrum.copy()
        else:
            self.old_spectrum = None

        self.old_plot1_log = []

    def execute(self):
        # Backup plot log
        for idx in range(self.app.plot1_log.count()):
            line_to_back_up = self.app.plot1_log.item(idx).text()
            #print('backing up:', line_to_back_up)
            self.old_plot1_log.append(line_to_back_up)

        # Aesthetics
        self.app.plot1_log.clear()
        self.app.button_baseline.setText('基线估计')

        self.app.spectrum = self.new_spectrum
        if self.app.spectrum is not None:
            self.app.plot1.clear()
            pen=pg.mkPen(color='k',width=3)
            self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y,pen=pen)
            self.app.plot1.autoRange()

        # Communicate
        self.app.plot1_log.addItem(f"Loaded file: {str(self.app.unknown_spectrum_path)}")
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()

    def undo(self):
        if self.old_plot1_log:
            self.app.plot1_log.clear()
            self.app.plot1_log.addItems(self.old_plot1_log)
            # 选中最后一个项目并滚动到该项目
            self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
            self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
            self.app.plot1_log.clearSelection()

        self.app.spectrum = self.old_spectrum
        if self.app.spectrum is not None:
            self.app.plot1.clear()
            self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y)
            self.app.plot1.autoRange()
        else:
            self.app.plot1.clear()



class PointDragCommand(Command):
    """Command for moving a point on the baseline"""
    def __init__(self, app, index, startX, startY, endX, endY):
        self.app = app
        self.index = index
        self.startX = startX
        self.startY = startY
        self.endX = endX
        self.endY = endY

    def execute(self):
        self.app.draggableScatter.data['x'][self.index] = self.endX
        self.app.draggableScatter.data['y'][self.index] = self.endY
        self.app.update_discretized_baseline()
    
    def undo(self):
        self.app.draggableScatter.data['x'][self.index] = self.startX
        self.app.draggableScatter.data['y'][self.index] = self.startY
        self.app.update_discretized_baseline()
    


class EstimateBaselineCommand(Command):
    """This command stores the baseline estimate calculation and necessary GUI updates"""
    def __init__(self, app, estimated_baseline):
        self.app = app
        self.new_baseline = estimated_baseline
        if self.app.baseline_data is not None:
            self.old_baseline = self.app.baseline_data.copy()
        else:
            self.old_baseline = None

    def execute(self):

        # Aesthetics
        self.app.button_baseline.setText('应用基线校准')
        self.app.plot1_log.addItem('基线估计已计算') # Communicate
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()

        # Update data
        self.app.baseline_data = self.new_baseline
        
        # Update plot
        if self.app.baseline_plot is not None:
            self.app.plot1.removeItem(self.app.baseline_plot)
        pen=pg.mkPen(color='r',width=3)
        self.app.baseline_plot = self.app.plot1.plot(self.app.spectrum.x, self.app.baseline_data, pen=pen)
        
    def undo(self):
        # Aesthetics
        self.app.button_baseline.setText('基线估计') # TODO refactor with a toggle function

        self.app.baseline_data = self.old_baseline
        
        # Update the plot and baseline_data
        if self.app.baseline_plot is not None:
            self.app.plot1.removeItem(self.app.baseline_plot)
            self.app.baseline_data = None
        
        if self.app.baseline_data is not None:
            pen=pg.mkPen(color='r',width=3)
            self.app.baseline_plot = self.app.plot1.plot(self.app.spectrum.x, self.app.baseline_data, pen=pen)
        self.app.plot1_log.addItem("基线估计已撤销")
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()



class CorrectBaselineCommand(Command):
    """Command for subtracting the baseline estimate from the loaded spectrum"""
    def __init__(self, app):
        self.app = app

        # Store the old spectrum
        if self.app.spectrum is not None:
            self.old_spectrum = self.app.spectrum.copy()
        else:
            self.old_spectrum = None

        # Update the new spectrum
        if self.app.baseline_data is not None:
            self.new_spectrum = CommandSpectrum(self.app.spectrum.x, self.app.spectrum.y - self.app.baseline_data)
            self.old_baseline_data = self.app.baseline_data.copy()
        else:
            self.new_spectrum = CommandSpectrum(self.app.spectrum.x, self.app.spectrum.y)
            self.old_baseline_data = None
        
    def execute(self):
        # Aesthetics
        self.app.button_baseline.setText('基线估计')
        # Communicate
        self.app.plot1_log.addItem("基线已修正")
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()
        
        self.app.spectrum = self.new_spectrum
        self.app.plot1.clear()
        self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y)
        self.app.plot1.autoRange()

    def undo(self):
        # Aesthetics
        self.app.button_baseline.setText('应用基线校准')

        self.app.spectrum = self.old_spectrum
        self.app.baseline_data = self.old_baseline_data # Resture baseline data from before subtraction
        self.app.plot1.clear()
        if self.app.spectrum is not None:
            self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y)
        if self.app.baseline_data is not None:
            pen=pg.mkPen(color='r',width=3)
            self.app.baseline_plot = self.app.plot1.plot(self.app.spectrum.x, self.app.baseline_data, pen=pen)
        self.app.plot1.autoRange()

        # Message
        self.app.plot1_log.addItem("基线已恢复")
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()



class CropCommand(Command):
    def __init__(self, app, crop_start_x, crop_end_x):
        self.app = app
        self.crop_start_x = crop_start_x
        self.crop_end_x = crop_end_x
        
        # Back up app spectrum if not none        
        if self.app.spectrum is not None:
            self.old_spectrum = self.app.spectrum.copy()
        else:
            self.old_spectrum = None
        
        self.new_spectrum = self._get_cropped_spectrum()

    def _get_cropped_spectrum(self):
        indices_to_crop = np.where((self.old_spectrum.x >= self.crop_start_x) & (self.old_spectrum.x <= self.crop_end_x))
        new_y = self.old_spectrum.y.copy()
        new_y[indices_to_crop] = np.nan
        return CommandSpectrum(self.old_spectrum.x, new_y)

    def execute(self):
        self.app.spectrum = self.new_spectrum
        self.app.plot1.clear()
        self.app.plot1.plot(*self.app.spectrum)
        self.app.plot1_log.addItem(f'Cropped spectrum from {round(self.crop_start_x)} to {round(self.crop_end_x)} cm^-1')
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()


    def undo(self):
        self.app.spectrum = self.old_spectrum
        self.app.plot1.clear()
        if self.app.spectrum is not None:
            self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y)
        



class AddPeakPointCommand(Command):
    """TODO Implement peak point adding"""
    def __init__(self, app):
        self.app = app

    def execute(self):
        pass

    def undo(self):
        pass



class RemovePeakPointCommand(Command):
    """TODO Implement peak point removal"""
    def __init__(self, app):
        self.app = app

    def execute(self):
        pass

    def undo(self):
        pass
