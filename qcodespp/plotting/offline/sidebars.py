from PyQt5 import QtWidgets, QtCore, QtGui
from json import load as jsonload
from json import dump as jsondump

import copy

import qcodespp.plotting.offline.fits as fits

from matplotlib import colormaps as cm
import numpy as np
from lmfit.model import save_modelresult

import matplotlib.style as mplstyle

from qcodespp.plotting.offline.popupwindows import ErrorWindow
mplstyle.use('fast')

from qcodespp.plotting.offline.helpers import cmaps

class Sidebar1D(QtWidgets.QWidget):
    def __init__(self, parent, editor_window=None):
        super().__init__()

        self.init_cmap='viridis'
        self.setMaximumWidth(500)
        self.parent = parent
        self.running = True
        self.init_widgets()
        self.init_connections()
        self.init_layouts()
        self.set_main_layout()
        self.init_trace_table()
        self.fit_type_changed()
        if editor_window:
            self.editor_window = editor_window

    def init_widgets(self):
        # Widgets in trace list box
        self.add_trace_button = QtWidgets.QPushButton('Add')
        self.remove_trace_button = QtWidgets.QPushButton('Remove')
        self.clear_traces_button = QtWidgets.QPushButton('Clear list')

        self.trace_table = QtWidgets.QTableWidget()

        self.duplicate_trace_button = QtWidgets.QPushButton('Duplicate')
        self.move_up_button = QtWidgets.QPushButton('Move Up')
        self.move_down_button = QtWidgets.QPushButton('Move Down')

        self.colormap_type_box = QtWidgets.QComboBox()
        self.colormap_box = QtWidgets.QComboBox()
        self.apply_colormap_to_box = QtWidgets.QComboBox() # All by index, all by num, selected by ind, selected by num, checked by ind, checked by num
        self.apply_button = QtWidgets.QPushButton('Apply')

        applymethods=['All', 'Checked']
        self.apply_colormap_to_box.addItems(applymethods)
        for cmap_type in cmaps:    
            self.colormap_type_box.addItem(cmap_type)
        self.colormap_box.addItems(list(cmaps.values())[0])
        self.colormap_box.setCurrentText(self.init_cmap)

        # Fitting widgets
        self.lims_label = QtWidgets.QLabel('Fit limits (left-click plot):')
        self.xmin_label = QtWidgets.QLabel('Xmin:')
        self.xmin_label.setStyleSheet("QLabel { color : blue; }")
        self.xmax_label = QtWidgets.QLabel('Xmax:')
        self.xmax_label.setStyleSheet("QLabel { color : red; }")
        self.xmin_box = QtWidgets.QLineEdit()
        self.xmax_box = QtWidgets.QLineEdit()
        self.reset_axes_button = QtWidgets.QPushButton('Reset')

        self.fit_functions_label = QtWidgets.QLabel('Select fit function:')
        self.fit_class_box = QtWidgets.QComboBox()
        self.fit_class_box.addItems(fits.get_class_names())
        self.fit_class_box.setCurrentIndex(0)
        self.fit_class_box.SizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.fit_box = QtWidgets.QComboBox()
        self.fit_box.addItems(fits.get_names(fitclass=self.fit_class_box.currentText()))
        self.fit_box.setCurrentIndex(0)
        self.fit_box.SizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)

        self.input_label = QtWidgets.QLabel('Input info:')
        self.input_edit = QtWidgets.QLineEdit()

        self.guess_checkbox = QtWidgets.QCheckBox('Initial guess:')
        self.guess_edit = QtWidgets.QLineEdit()

        self.output_window = QtWidgets.QTextEdit()
        self.output_window.setReadOnly(True)

        self.fit_button = QtWidgets.QPushButton('Fit')
        self.save_result_button = QtWidgets.QPushButton('Save fit result')
        self.clear_fit_button = QtWidgets.QPushButton('Clear fit')
        self.fit_checked_button = QtWidgets.QPushButton('Fit checked')
        self.save_all_fits_button = QtWidgets.QPushButton('Save all fits')
        self.clear_all_fits_button = QtWidgets.QPushButton('Clear all fits')
        self.save_preset_button = QtWidgets.QPushButton('Save fit preset')
        self.load_preset_button = QtWidgets.QPushButton('Load fit preset')

    def init_connections(self):
        self.add_trace_button.clicked.connect(self.add_trace_manually)
        self.remove_trace_button.clicked.connect(lambda: self.remove_trace('selected'))
        self.clear_traces_button.clicked.connect(lambda: self.remove_trace('all'))
        self.duplicate_trace_button.clicked.connect(self.duplicate_trace)
        self.move_up_button.clicked.connect(lambda: self.move_trace('up'))
        self.move_down_button.clicked.connect(lambda: self.move_trace('down'))
        self.apply_button.clicked.connect(self.apply_colormap)

        self.trace_table.itemClicked.connect(self.item_clicked)

        self.clear_fit_button.clicked.connect(lambda: self.clear_fit(line='manual'))
        self.fit_class_box.currentIndexChanged.connect(self.fit_class_changed)
        self.fit_box.currentIndexChanged.connect(self.fit_type_changed)
        self.fit_button.clicked.connect(lambda: self.start_fitting(line='manual'))
        self.save_result_button.clicked.connect(self.save_fit_result)
        self.fit_checked_button.clicked.connect(self.fit_checked)
        self.save_all_fits_button.clicked.connect(self.save_all_fits)
        self.clear_all_fits_button.clicked.connect(self.clear_all_fits)
        self.save_preset_button.clicked.connect(self.save_fit_preset)
        self.load_preset_button.clicked.connect(self.load_fit_preset)
        self.xmin_box.editingFinished.connect(self.limits_edited)
        self.xmax_box.editingFinished.connect(self.limits_edited)
        self.reset_axes_button.clicked.connect(self.reset_limits)
        self.trace_table.itemChanged.connect(self.trace_table_edited)
        self.colormap_type_box.currentIndexChanged.connect(self.colormap_type_edited)

    def init_layouts(self):
        # Sub-layouts in Linetrace list box:
        self.table_buttons_layout_top = QtWidgets.QHBoxLayout()
        self.table_buttons_layout_bot = QtWidgets.QHBoxLayout()
        self.colormap_layout = QtWidgets.QHBoxLayout()

        # Populating
        self.table_buttons_layout_top.addWidget(self.add_trace_button)
        self.table_buttons_layout_top.addWidget(self.remove_trace_button)
        self.table_buttons_layout_top.addWidget(self.clear_traces_button)
        self.table_buttons_layout_top.addStretch()

        self.table_buttons_layout_bot.addWidget(self.duplicate_trace_button)
        self.table_buttons_layout_bot.addWidget(self.move_up_button)
        self.table_buttons_layout_bot.addWidget(self.move_down_button)
        self.table_buttons_layout_bot.addStretch()

        self.colormap_layout.addWidget(self.colormap_type_box)
        self.colormap_layout.addWidget(self.colormap_box)
        self.colormap_layout.addWidget(self.apply_colormap_to_box)
        self.colormap_layout.addWidget(self.apply_button)
        
        # Sub-layouts(s) in fitting box
        self.lims_layout_top = QtWidgets.QHBoxLayout()
        self.lims_layout_bot = QtWidgets.QHBoxLayout()
        self.fit_layout = QtWidgets.QHBoxLayout()
        self.inputs_layout = QtWidgets.QHBoxLayout()
        self.guess_layout = QtWidgets.QHBoxLayout()
        self.guess_input_layout = QtWidgets.QHBoxLayout()
        self.output_layout = QtWidgets.QVBoxLayout()
        self.fit_buttons_layout = QtWidgets.QHBoxLayout()
        self.fit_all_buttons_layout = QtWidgets.QHBoxLayout()
        self.fit_presets_layout = QtWidgets.QHBoxLayout()

        # Populating
        self.lims_layout_top.addWidget(self.lims_label)
        self.lims_layout_top.addStretch()
        self.lims_layout_bot.addWidget(self.xmin_label)
        self.lims_layout_bot.addWidget(self.xmin_box)
        self.lims_layout_bot.addWidget(self.xmax_label)
        self.lims_layout_bot.addWidget(self.xmax_box)
        self.lims_layout_bot.addWidget(self.reset_axes_button)
        self.lims_layout_bot.addStretch()

        self.fit_layout.addWidget(self.fit_functions_label)
        self.fit_layout.addWidget(self.fit_class_box)
        self.fit_layout.addWidget(self.fit_box)
        self.fit_layout.addStretch()

        self.inputs_layout.addWidget(self.input_label)
        self.inputs_layout.addWidget(self.input_edit)
        #self.inputs_layout.addStretch()

        self.guess_layout.addWidget(self.guess_checkbox)
        self.guess_input_layout.addWidget(self.guess_edit)
        #self.guess_layout.addStretch()

        self.output_layout.addWidget(self.output_window)

        self.fit_buttons_layout.addWidget(self.fit_button)
        self.fit_buttons_layout.addWidget(self.save_result_button)
        self.fit_buttons_layout.addWidget(self.clear_fit_button)
        self.fit_buttons_layout.addStretch()
        self.fit_buttons_layout.addWidget(self.save_preset_button)
        self.fit_all_buttons_layout.addWidget(self.fit_checked_button)
        self.fit_all_buttons_layout.addWidget(self.save_all_fits_button)
        self.fit_all_buttons_layout.addWidget(self.clear_all_fits_button)
        self.fit_all_buttons_layout.addStretch()
        self.fit_all_buttons_layout.addWidget(self.load_preset_button)

    def set_main_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout()

        self.tablebox=QtWidgets.QGroupBox(f'1D traces: {self.parent.label}')
        self.table_layout = QtWidgets.QVBoxLayout()
        self.table_layout.addLayout(self.table_buttons_layout_top)
        self.table_layout.addLayout(self.table_buttons_layout_bot)
        self.table_layout.addWidget(self.trace_table)
        self.table_layout.addLayout(self.colormap_layout)
        self.tablebox.setLayout(self.table_layout)

        self.fittingbox=QtWidgets.QGroupBox('Curve Fitting')
        self.fittinglayout = QtWidgets.QVBoxLayout()
        self.fittinglayout.addLayout(self.lims_layout_top)
        self.fittinglayout.addLayout(self.lims_layout_bot)
        self.fittinglayout.addLayout(self.fit_layout)
        self.fittinglayout.addLayout(self.inputs_layout)
        self.fittinglayout.addLayout(self.guess_layout)
        self.fittinglayout.addLayout(self.guess_input_layout)
        self.fittinglayout.addLayout(self.output_layout)
        self.fittinglayout.addLayout(self.fit_buttons_layout)
        self.fittinglayout.addLayout(self.fit_all_buttons_layout)
        #self.fittinglayout.addLayout(self.fit_presets_layout)
        self.fittingbox.setLayout(self.fittinglayout)

        self.main_layout.addWidget(self.tablebox)
        self.main_layout.addWidget(self.fittingbox)
        self.setLayout(self.main_layout)

    def init_trace_table(self):
        headerlabels=['#','X data','Y data','style','color', 'width',
                      'Xerr','Yerr','show fit','show fit cmpts','show fit err']
        self.trace_table.setColumnCount(len(headerlabels))
        self.trace_table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked)
        h = self.trace_table.horizontalHeader()
        h.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for col in range(len(headerlabels)):
            h.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
        self.trace_table.setHorizontalHeaderLabels(headerlabels)
        v=self.trace_table.verticalHeader()
        v.setVisible(False)

        self.trace_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.trace_table.customContextMenuRequested.connect(self.open_trace_table_menu)

    def plot_type_changed(self):
        # This is called when the data type is changed in the main window.
        # It updates the trace table with the new data.
        self.trace_table.setRowCount(0)
        self.trace_table.clear()
        if self.parent.plot_type == 'Histogram':
            self.trace_table.setHorizontalHeaderLabels(['#','Bins','Data','style','color', 'width',
                                                        'Xerr','Yerr','show fit','show fit cmpts','show fit err'])
        else:
            self.trace_table.setHorizontalHeaderLabels(['#','X data','Y data','style','color', 'width',
                                                        'Xerr','Yerr','show fit','show fit cmpts','show fit err'])
        for line in self.parent.plotted_lines.keys():
            self.append_trace_to_table(line)

    def item_clicked(self, item):
        # displays the fit result and/or information.
        row = self.trace_table.currentRow()
        line = int(self.trace_table.item(row,0).text())
        if 'fit' in self.parent.plotted_lines[line].keys():
            fit_result = self.parent.plotted_lines[line]['fit']['fit_result']
            self.output_window.setText(fit_result.fit_report())
        elif 'stats' in self.parent.plotted_lines[line].keys():
            text='Statistics:\n'
            for key in self.parent.plotted_lines[line]['stats'].keys():
                text+=f'{key}: {self.parent.plotted_lines[line]['stats'][key]}\n'
            self.output_window.setText(text)
        else:
            fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]
            self.output_window.setText('Information about selected fit type:\n'+
                                   fit_function['description'])
            
        # ... and the filters.
        self.editor_window.show_current_filters()

    def get_checked_items(self, return_indices = False, traces_or_fits='traces'):
        # Note this is a bit different to the main window, where the entire item is returned.
        # Here we just return the identifier for the linetrace
        if traces_or_fits == 'traces':
            column = 0
        elif traces_or_fits == 'fits':
            column = 8
        indices = [index for index in range(self.trace_table.rowCount()) 
                   if self.trace_table.item(index,column).checkState() == 2 or 
                   self.trace_table.item(index,column).checkState()== QtCore.Qt.Checked]
        checked_items = [int(self.trace_table.item(index,0).text()) for index in indices]
        if return_indices:
            return checked_items, indices
        else:
            return checked_items
        
    def duplicate_trace(self):
        try:
            max_index=np.max(list(self.parent.plotted_lines.keys()))
        except ValueError:
            max_index=-1
        current_row = self.trace_table.currentRow()
        try:
            line = int(self.trace_table.item(current_row,0).text())
            new_line = int(max_index+1)
            self.parent.plotted_lines[new_line] = copy.deepcopy(self.parent.plotted_lines[line])
            self.append_trace_to_table(new_line)
            self.editor_window.show_current_plot_settings()
            self.editor_window.update_plots(update_data=False)
        except Exception as e:
            self.editor_window.log_error(f'Cannot duplicate data:\n{type(e).__name__}: {e}', show_popup=True)

    def add_trace_manually(self): # When 'add' button pressed
        try:
            max_index=np.max(list(self.parent.plotted_lines.keys()))
        except ValueError:
            max_index=-1
        try:
            line={'checkstate': 2,
                'X data': self.parent.all_parameter_names[0],
                'Y data': self.parent.all_parameter_names[1],
                'Bins': 100,
                'Xerr':0,
                'Yerr':0,
                'linecolor': (1,0,0,1),
                'linewidth': 1.5,
                'linestyle': '-',
                'filters':[]}
            self.parent.plotted_lines[int(max_index+1)] = line
            self.parent.prepare_data_for_plot(reload_data=True,reload_from_file=False,linefrompopup=int(max_index+1))
            self.parent.plotted_lines[int(max_index+1)]['processed_data'] = self.parent.processed_data
            self.parent.plotted_lines[int(max_index+1)]['raw_data'] = self.parent.raw_data
            self.append_trace_to_table(int(max_index+1))
            self.editor_window.show_current_plot_settings()
        except Exception as e:
            self.editor_window.log_error(f'Cannot add data:\n{type(e).__name__}: {e}', show_popup=True)
        self.editor_window.update_plots(update_data=False)

    def append_trace_to_table(self,index):
        row = self.trace_table.rowCount()
        line=self.parent.plotted_lines[index]


        self.trace_table.itemChanged.disconnect(self.trace_table_edited)
        self.trace_table.insertRow(row)
        v = self.trace_table.verticalHeader()
        v.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for rownum in range(int(row+1)):
            v.setSectionResizeMode(rownum, QtWidgets.QHeaderView.ResizeToContents)

        linetrace_item = QtWidgets.QTableWidgetItem(str(index))
        linetrace_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                                 QtCore.Qt.ItemIsEnabled | 
                                 QtCore.Qt.ItemIsUserCheckable)
        linetrace_item.setText(str(index))
        linetrace_item.setCheckState(line['checkstate'])

        Xdata_item = QtWidgets.QTableWidgetItem(line['X data'])
        bins_item = QtWidgets.QTableWidgetItem(str(line['Bins']))
        Ydata_item = QtWidgets.QTableWidgetItem(line['Y data'])

        style_item = QtWidgets.QTableWidgetItem(line['linestyle'])

        color_box = QtWidgets.QTableWidgetItem('')
        if type(line['linecolor'])==str:
            color_box.setBackground(QtGui.QColor(line['linecolor']))
        else:
            rgbavalue = [int(line['linecolor'][0]*255), 
                         int(line['linecolor'][1]*255), 
                         int(line['linecolor'][2]*255), 
                         int(line['linecolor'][3]*255)]
            color_box.setBackground(QtGui.QColor(*rgbavalue))

        width_item = QtWidgets.QTableWidgetItem(str(line['linewidth']))

        plot_fit_item = QtWidgets.QTableWidgetItem('')
        if 'fit' in line.keys():
            plot_fit_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                            QtCore.Qt.ItemIsEnabled | 
                            QtCore.Qt.ItemIsUserCheckable)
            plot_fit_item.setCheckState(line['fit']['fit_checkstate'])

        plot_components_item = QtWidgets.QTableWidgetItem('')
        if 'fit' in line.keys():
            plot_components_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                            QtCore.Qt.ItemIsEnabled | 
                            QtCore.Qt.ItemIsUserCheckable)
            plot_components_item.setCheckState(line['fit']['fit_components_checkstate'])

        plot_uncertainty_item = QtWidgets.QTableWidgetItem('')
        if 'fit' in line.keys():
            plot_uncertainty_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                            QtCore.Qt.ItemIsEnabled | 
                            QtCore.Qt.ItemIsUserCheckable)
            plot_uncertainty_item.setCheckState(line['fit']['fit_uncertainty_checkstate'])
        
        Xerr_item = QtWidgets.QTableWidgetItem(str(line['Xerr']))
        Yerr_item = QtWidgets.QTableWidgetItem(str(line['Yerr']))

        self.trace_table.setItem(row,0,linetrace_item)
        if self.parent.plot_type == 'Histogram':
            self.trace_table.setItem(row,1,bins_item)
        else:
            self.trace_table.setItem(row,1,Xdata_item)
        self.trace_table.setItem(row,2,Ydata_item)
        self.trace_table.setItem(row,3,style_item)
        self.trace_table.setItem(row,4,color_box)
        self.trace_table.setItem(row,5,width_item)
        self.trace_table.setItem(row,6,Xerr_item)
        self.trace_table.setItem(row,7,Yerr_item)
        self.trace_table.setItem(row,8,plot_fit_item)
        self.trace_table.setItem(row,9,plot_components_item)
        self.trace_table.setItem(row,10,plot_uncertainty_item)

        self.trace_table.itemChanged.connect(self.trace_table_edited)
        self.trace_table.setCurrentCell(row,0)
        self.item_clicked(self.trace_table.currentItem())

    def trace_table_edited(self,item):
        current_item = item
        current_col = item.column()
        current_row = item.row()
        line = int(self.trace_table.item(current_row,0).text())

        if self.parent.plot_type == 'Histogram':
            edit_dict={1:'Bins',2:'Y data',3:'linestyle',5:'linewidth',6:'Xerr',7:'Yerr'}
        else:
            edit_dict={1:'X data',2:'Y data',3:'linestyle',5:'linewidth',6:'Xerr',7:'Yerr'}

        if current_col in edit_dict.keys():
            self.parent.plotted_lines[line][edit_dict[current_col]] = current_item.text()

        elif current_col == 8:
            self.parent.plotted_lines[line]['fit']['fit_checkstate'] = current_item.checkState()
        elif current_col == 9:
            self.parent.plotted_lines[line]['fit']['fit_components_checkstate'] = current_item.checkState()
        elif current_col == 10:
            self.parent.plotted_lines[line]['fit']['fit_uncertainty_checkstate'] = current_item.checkState()

        elif current_col == 0: # It's the checkstate for the linetrace.
            self.parent.plotted_lines[line]['checkstate'] = current_item.checkState()

        # If the X or Y data is changed, we need to update the processed data.
        if current_col in [1,2,6,7]:
            try:
                self.parent.prepare_data_for_plot(reload_data=True,reload_from_file=False,linefrompopup=line)
                self.parent.plotted_lines[line]['processed_data'] = [self.parent.processed_data[0],
                                                                    self.parent.processed_data[1]]
                self.editor_window.show_current_plot_settings()

            except Exception as e:
                self.editor_window.log_error(f'Error changing plotted data:\n{type(e).__name__}: {e}', show_popup=True)
        self.editor_window.update_plots(update_data=False)

    def remove_trace(self,which='selected'):
        # which = 'selected', 'all'
        if which=='selected':
            try:
                row = self.trace_table.currentRow()
                linetrace = int(self.trace_table.item(row,0).text())
                self.parent.plotted_lines.pop(linetrace)
                self.trace_table.removeRow(row)
            except Exception as e:
                self.editor_window.log_error(f'Cannot remove selected trace:\n{type(e).__name__}: {e}', show_popup=True)
        elif which=='all':
            self.parent.plotted_lines = {}
            self.trace_table.setRowCount(0)

        self.editor_window.update_plots(update_data=False)

    def move_trace(self, direction):
        self.trace_table.itemChanged.disconnect(self.trace_table_edited)
        try:
            current_row = self.trace_table.currentRow()
            if direction == 'up' and current_row > 0:
                delta=-1
            elif direction == 'down' and current_row < self.trace_table.rowCount()-1:
                delta=1
            if delta in [-1,1]:
                current_col = self.trace_table.currentColumn()
                items = [self.trace_table.takeItem(current_row, c) for c in range(self.trace_table.columnCount())]
                self.trace_table.removeRow(current_row)
                new_row = current_row + delta
                self.trace_table.insertRow(new_row)
                for i, item in enumerate(items):
                    self.trace_table.setItem(new_row, i, item)
                if current_col >= 0:
                    self.trace_table.setCurrentCell(new_row, current_col)

        except Exception as e:
            pass
        self.trace_table.itemChanged.connect(self.trace_table_edited)

    def apply_colormap(self):
        # Apply the colormap to the selected lines in the traces table.
        self.trace_table.itemChanged.disconnect(self.trace_table_edited)
        selected_colormap = cm.get_cmap(self.colormap_box.currentText())
        applymethod = self.apply_colormap_to_box.currentText()

        if applymethod == 'All':
            lines_to_color = [int(self.trace_table.item(row,0).text()) for row in range(self.trace_table.rowCount())]

        elif applymethod == 'Checked':
            lines_to_color = self.get_checked_items(traces_or_fits='traces')

        line_colors = selected_colormap(np.linspace(0.1,0.9,len(lines_to_color)))
        rows = [self.trace_table.row(self.trace_table.findItems(str(line), QtCore.Qt.MatchExactly)[0]) for line in lines_to_color]

        for i,line in enumerate(lines_to_color):
            self.parent.plotted_lines[line]['linecolor'] = line_colors[i]
            rgbavalue = [int(line_colors[i][0]*255),
                         int(line_colors[i][1]*255),
                         int(line_colors[i][2]*255),
                         int(line_colors[i][3]*255)]
            self.trace_table.item(rows[i],4).setBackground(QtGui.QColor(*rgbavalue))
            
        self.trace_table.itemChanged.connect(self.trace_table_edited)
        self.editor_window.update_plots(update_data=False)

    def colormap_type_edited(self):
        self.colormap_box.clear()
        self.colormap_box.addItems(cmaps[self.colormap_type_box.currentText()])

    def open_trace_table_menu(self,position):
        item=self.trace_table.currentItem()
        column=self.trace_table.currentColumn()
        row=self.trace_table.currentRow()
        if column==4:
            # Choose colour
            menu = QtWidgets.QMenu(self)
            color_action = menu.addAction("Choose Color")

            # Show the menu at the cursor position
            action = menu.exec_(self.trace_table.viewport().mapToGlobal(position))

            if action == color_action:
                if item:
                    color = QtWidgets.QColorDialog.getColor()
                    if color.isValid():
                        item.setBackground(color)
                        linetrace=int(self.trace_table.item(self.trace_table.currentRow(),0).text())
                        self.parent.plotted_lines[linetrace]['linecolor'] = color.name()
                        self.trace_table.setCurrentItem(self.trace_table.item(row,0)) # Otherwise the cell stays blue since it's selected.
                        self.editor_window.update_plots(update_data=False)
        
        elif column in [1,2,6,7]:
            menu = QtWidgets.QMenu(self)
            for entry in self.parent.all_parameter_names:
                action = QtWidgets.QAction(entry, self)
                menu.addAction(action)
            menu.triggered[QtWidgets.QAction].connect(self.replace_table_entry)
            menu.popup(QtGui.QCursor.pos())
            #self.update()
            
        elif column==3:
            menu = QtWidgets.QMenu(self)
            styles=['-', '--', '-.', ':','.','o','v', '^', '<', '>', '8', 's', 'p', '*', 'h', 'H', 'D', 'd', 'P', 'X']
            for entry in styles:
                action = QtWidgets.QAction(entry, self)
                menu.addAction(action)
            menu.triggered[QtWidgets.QAction].connect(self.replace_table_entry)
            menu.popup(QtGui.QCursor.pos())
            #self.update()

        elif column in [0,8,9,10]:
            menu = QtWidgets.QMenu(self)
            check_all_action = menu.addAction("Check all")
            uncheck_all_action = menu.addAction("Uncheck all")

            if column==0:
                check_all_action = menu.addAction("Check all")
                uncheck_all_action = menu.addAction("Uncheck all")

            elif column==8:
                check_all_action = menu.addAction("Show all fits")
                uncheck_all_action = menu.addAction("Hide all fits")

            elif column==9:
                check_all_action = menu.addAction("Show all fit components")
                uncheck_all_action = menu.addAction("Hide all fit components")
            elif column==10:
                check_all_action = menu.addAction("Show all fit errors")
                uncheck_all_action = menu.addAction("Hide all fit errors")

            action = menu.exec_(self.trace_table.viewport().mapToGlobal(position))
            self.trace_table.itemChanged.disconnect(self.trace_table_edited)
            if action == check_all_action:
                self.change_all_checkstate(column, QtCore.Qt.Checked)
            elif action == uncheck_all_action:
                self.change_all_checkstate(column, QtCore.Qt.Unchecked)
            self.trace_table.itemChanged.connect(self.trace_table_edited)
            self.editor_window.update_plots(update_data=False)

    def change_all_checkstate(self,column,checkstate):
        for row in range(self.trace_table.rowCount()):
            item = self.trace_table.item(row, column)
            item.setCheckState(checkstate)
            linetrace=int(self.trace_table.item(row,0).text())
            if column==0:
                self.parent.plotted_lines[linetrace]['checkstate'] = item.checkState()
            elif column==8:
                self.parent.plotted_lines[linetrace]['fit']['fit_checkstate'] = item.checkState()
            elif column==9:
                self.parent.plotted_lines[linetrace]['fit']['fit_components_checkstate'] = item.checkState()
            elif column==10:
                self.parent.plotted_lines[linetrace]['fit']['fit_uncertainty_checkstate'] = item.checkState()

    def replace_table_entry(self, signal):
        item = self.trace_table.currentItem()
        item.setText(signal.text())

    def limits_edited(self):
        try:
            if hasattr(self, 'minline'):
                self.minline.remove()
                del self.minline
            if hasattr(self, 'maxline'):
                self.maxline.remove()
                del self.maxline
        except:
            pass
        xmin=self.xmin_box.text()
        xmax=self.xmax_box.text()
        if xmin != '':
            xmin=float(xmin)
            self.minline=self.parent.axes.axvline(xmin, 0,0.1, color='blue', linestyle='--')
        if xmax != '':
            xmax=float(xmax)
            self.maxline=self.parent.axes.axvline(xmax, 0,0.1, color='red', linestyle='--')
        self.parent.canvas.draw()
    
    def reset_limits(self):
        try:
            if hasattr(self, 'minline'):
                self.minline.remove()
                del self.minline
            if hasattr(self, 'maxline'):
                self.maxline.remove()
                del self.maxline
        except:
            pass
        self.xmin_box.clear()
        self.xmax_box.clear()

        self.parent.canvas.draw()
  
    def update(self,clearplot=True):
        if self.running:
            self.draw_plot(clearplot)
            fit_lines = self.get_checked_items(traces_or_fits='fits')
            if len(fit_lines) > 0:
                for line in fit_lines:
                    if 'fit' in self.parent.plotted_lines[line].keys():
                        self.draw_fits(line)
                        
            if self.xmin_box.text() != '' or self.xmax_box.text() != '':
                self.limits_edited()
        
        self.parent.canvas.draw()
    
    def fit_class_changed(self):
        self.fit_box.currentIndexChanged.disconnect(self.fit_type_changed)
        self.fit_box.clear()
        self.fit_box.addItems(fits.get_names(fitclass=self.fit_class_box.currentText()))
        self.fit_box.setCurrentIndex(0)
        self.fit_type_changed()
        self.fit_box.currentIndexChanged.connect(self.fit_type_changed)
    
    def fit_type_changed(self):
        fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]

        if 'default_inputs' in fit_function.keys():
            self.input_edit.setText(fit_function['default_inputs'])
        else:
            self.input_edit.setText('')
        if 'default_guess' in fit_function.keys():
            self.guess_edit.setText(fit_function['default_guess'])
        else:
            self.guess_edit.setText('')
        if 'inputs' in fit_function.keys():
            self.input_label.setText(f'Input info: {fit_function['inputs']}')
        else:
            self.input_label.setText(f'Input info:')
        if 'parameters' in fit_function.keys():
            self.guess_checkbox.setText(f'Initial guess: {fit_function['parameters']}')
        else:
            self.guess_checkbox.setText(f'Initial guess:')
        self.output_window.setText('Information about selected fit type:\n'+
                                   fit_function['description'])
        
    def collect_fit_data(self,x,y):
        if self.xmin_box.text() != '':
            xmin = float(self.xmin_box.text())
            min_ind=(np.abs(x - xmin)).argmin()
        else:
            min_ind = 0
        if self.xmax_box.text() != '':
            xmax = float(self.xmax_box.text())
            max_ind=(np.abs(x - xmax)).argmin()
        else:
            max_ind = len(x)-1
        # Need to check if indices in 'wrong' order; i.e. x data descending.
        if min_ind > max_ind:
            x_forfit=x[max_ind:min_ind]
            y_forfit=y[max_ind:min_ind]
        else:
            x_forfit=x[min_ind:max_ind]
            y_forfit=y[min_ind:max_ind]
        
        # if self.x_forfit[-1]<self.x_forfit[0]:
        #     x_forfit=x_forfit[::-1]
        #     y_forfit=y_forfit[::-1]
        #     self.fit_flipped=True
        # else:
        #     self.fit_flipped=False

        return x_forfit, y_forfit

    def collect_fit_inputs(self,function_class,function_name):
        if function_name in ['Expression','Statistics']:
            inputinfo=self.input_edit.text()
        elif 'inputs' in fits.functions[function_class][function_name].keys():
            try:
                inputinfo = [float(par) for par in self.input_edit.text().split(',')]
            except Exception as e:
                self.output_window.setText(f'Could not parse inputs: {e}\n'
                                            'Review information below:\n'
                                            f'{fits.functions[function_class][function_name]['description']}')
                inputinfo=None
        else:
            inputinfo=None
        return inputinfo
        
    def collect_init_guess(self,function_class, function_name):
        # Collect parameters/initial guess
        if self.guess_checkbox.checkState():
            try:
                p0 = self.guess_edit.text().split(',')
            except Exception as e:
                self.output_window.setText(f'Could not parse Initial guess: {e}\n'
                                            'Review information below:\n'
                                            f'{fits.functions[function_class][function_name]['description']}')
                p0 = None
        else:
            p0 = None
        return p0

    def start_fitting(self,line='manual',multilinefit=False):
        success=False
        if line=='manual':
            current_row = self.trace_table.currentRow()
            line = int(self.trace_table.item(current_row,0).text())
        else: # We are being passed the line from fit_checked
            # Still need to find the 'current row' to put a checkbox there later
            labels=[int(self.trace_table.item(row,0).text()) for row in range(self.trace_table.rowCount())]
            current_row=labels.index(line)
        x,y=self.get_line_data(line)
        x_forfit, y_forfit = self.collect_fit_data(x,y)
        function_class = self.fit_class_box.currentText()
        function_name = self.fit_box.currentText()
        inputinfo=self.collect_fit_inputs(function_class,function_name)
        p0=self.collect_init_guess(function_class,function_name)

        # Try to do the fit.
        if function_name != 'Statistics':
            if 'stats' in self.parent.plotted_lines[line].keys():
                self.parent.plotted_lines[line].pop('stats')
            try:
                fit_result = fits.fit_data(function_class=function_class, function_name=function_name,
                                                    xdata=x_forfit,ydata=y_forfit, p0=p0, inputinfo=inputinfo)

                if isinstance(fit_result, Exception):
                    self.output_window.setText(f'Curve could not be fitted:\n{type(fit_result).__name__}: {fit_result}')
                    self.editor_window.log_error(f'Curve could not be fitted:\n{type(fit_result).__name__}: {fit_result}')
                    if multilinefit:
                        return fit_result
                else:
                    y_fit = fit_result.best_fit

                    self.parent.plotted_lines[line]['fit'] = {'fit_result': fit_result,
                                                            'xdata': x_forfit,
                                                            'ydata': y_forfit,
                                                            'fitted_y': y_fit,
                                                            'fit_checkstate': QtCore.Qt.Checked,
                                                            'fit_components_checkstate': QtCore.Qt.Unchecked,
                                                            'fit_uncertainty_checkstate': QtCore.Qt.Checked}

                    # Add a checkbox to the table now a fit exists.
                    self.trace_table.itemChanged.disconnect(self.trace_table_edited)
                    plot_fit_item = QtWidgets.QTableWidgetItem('')
                    plot_fit_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                                        QtCore.Qt.ItemIsEnabled | 
                                        QtCore.Qt.ItemIsUserCheckable)
                    plot_fit_item.setCheckState(QtCore.Qt.Checked)
                    self.trace_table.setItem(current_row,8,plot_fit_item)

                    plot_components_item = QtWidgets.QTableWidgetItem('')
                    plot_components_item.setFlags(QtCore.Qt.ItemIsSelectable |
                                        QtCore.Qt.ItemIsEnabled | 
                                        QtCore.Qt.ItemIsUserCheckable)
                    plot_components_item.setCheckState(QtCore.Qt.Unchecked)
                    self.trace_table.setItem(current_row,9,plot_components_item)

                    plot_uncertainty_item = QtWidgets.QTableWidgetItem('')
                    plot_uncertainty_item.setFlags(QtCore.Qt.ItemIsSelectable |
                                        QtCore.Qt.ItemIsEnabled | 
                                        QtCore.Qt.ItemIsUserCheckable)
                    plot_uncertainty_item.setCheckState(QtCore.Qt.Checked)
                    self.trace_table.setItem(current_row,10,plot_uncertainty_item)
                    self.trace_table.itemChanged.connect(self.trace_table_edited)
                    success=True

            except Exception as e:
                self.output_window.setText(f'Curve could not be fitted:\n{type(e).__name__}: {e}')
                self.editor_window.log_error(f'Curve could not be fitted:\n{type(e).__name__}: {e}')
                if multilinefit:
                    return e
        
        else:
            if 'fit' in self.parent.plotted_lines[line].keys():
                self.clear_fit(line)
            self.parent.plotted_lines[line]['stats'] = fits.fit_data(function_class=function_class, 
                                                                                           function_name=function_name,
                                                    xdata=x_forfit,ydata=y_forfit, p0=p0, inputinfo=inputinfo)
            if 'autocorrelation' in self.parent.plotted_lines[line]['stats'].keys():
                self.parent.add_array_to_data_dict(self.parent.plotted_lines[line]['stats']['xdata'],'x_for_autocorr')
                self.parent.add_array_to_data_dict(self.parent.plotted_lines[line]['stats']['autocorrelation'],'autocorrelation')
            if 'autocorrelation_norm' in self.parent.plotted_lines[line]['stats'].keys():
                self.parent.add_array_to_data_dict(self.parent.plotted_lines[line]['stats']['xdata'],'x_for_autocorr')
                self.parent.add_array_to_data_dict(self.parent.plotted_lines[line]['stats']['autocorrelation_norm'],'autocorrelation_norm')
            if 'percentile' in self.parent.plotted_lines[line]['stats'].keys():
                self.parent.add_array_to_data_dict(self.parent.plotted_lines[line]['stats']['percentile'],'percentile')
                self.parent.add_array_to_data_dict(self.parent.plotted_lines[line]['stats']['percentiles'],'percentiles')
            success=True

            #self.parent.prepare_data_for_plot(reload_data=True,reload_from_file=False,linefrompopup=line)
        
        if success and not multilinefit:
            self.print_parameters(line)
            self.editor_window.update_plots(update_data=False)

    def fit_checked(self):
        # Fit all checked items in the table.
        fit_lines = self.get_checked_items(traces_or_fits='traces')
        minilog=[]
        for line in fit_lines:
            error=self.start_fitting(line,multilinefit=True)
            if error:
                minilog.append(f'Trace {line} could not be fitted: {error}')
        if len(minilog)>0:
            error_message = 'The following errors occurred while fitting:\n\n' + '\n\n'.join(minilog)
            self.ew = ErrorWindow(error_message)
        if not error:
            self.print_parameters(line)
        self.editor_window.update_plots(update_data=False)
    
    def print_parameters(self,line):
        self.output_window.clear()
        if 'stats' in self.parent.plotted_lines[line].keys():
            text='Statistics:\n'
            for key in self.parent.plotted_lines[line]['stats'].keys():
                text+=f'{key}: {self.parent.plotted_lines[line]['stats'][key]}\n'
            self.output_window.setText(text)
        else:
            try:
                self.output_window.setText(self.parent.plotted_lines[line]['fit']['fit_result'].fit_report())

            except Exception as e:
                self.output_window.setText('Could not print fit parameters:', e)

    def get_line_data(self,line):
        # Returns the processed x,y data for a particular entry in the plotted lines dictionary
        self.parent.prepare_data_for_plot(reload_data=True,reload_from_file=False,
                                          linefrompopup=line,plot_type=self.parent.plot_type)
        x=self.parent.plotted_lines[line]['processed_data'][0]
        y=self.parent.plotted_lines[line]['processed_data'][1]
        return (x,y)
    
    def plot_Yerr(self,x,y,error,line):
        if self.parent.plot_type == 'Histogram':
            self.parent.axes.errorbar(x, y,
                                    yerr=error,
                                    fmt='none',
                                    ecolor=self.parent.plotted_lines[line]['linecolor'],
                                    elinewidth=self.parent.plotted_lines[line]['linewidth'],
                                    capsize=4)
        else:
            self.parent.axes.fill_between(x, y+error, y-error,
                                    alpha=0.2, color=self.parent.plotted_lines[line]['linecolor'])
                                    
    def plot_Xerr(self,x,y,error,line):
        if self.parent.plot_type == 'Histogram':
            self.parent.axes.errorbar(x, y,
                                    xerr=error,
                                    fmt='none',
                                    ecolor=self.parent.plotted_lines[line]['linecolor'],
                                    elinewidth=self.parent.plotted_lines[line]['linewidth'],
                                    capsize=4)
        else:
            self.parent.axes.fill_betweenx(y, x+error, x-error,
                                    alpha=0.2, color=self.parent.plotted_lines[line]['linecolor'])
    
    def process_uncertainties(self,line,x,y):
        for axiserr in ['Xerr','Yerr']:
            if self.parent.plotted_lines[line][axiserr] not in [0,'0']:
                try: # if a single number
                    error = float(self.parent.plotted_lines[line][axiserr])
                except ValueError: # if name of array or has %, value error is thrown
                    if '%' in self.parent.plotted_lines[line][axiserr]:
                    # For percentage errors, make the absolute value array
                        if axiserr=='Yerr':
                            error = np.abs(y) * float(self.parent.plotted_lines[line][axiserr].replace('%','')) / 100
                        else:
                            error = np.abs(x) * float(self.parent.plotted_lines[line][axiserr].replace('%','')) / 100
                    else:
                    # Get the error data from the loaded data
                        errorname = self.parent.plotted_lines[line][axiserr]
                        error = copy.deepcopy(self.parent.data_dict[errorname])
                # Only apply multiply or divide filters (and only if they are checked of course)
                if 'filters' in self.parent.plotted_lines[line].keys():
                    for filt in self.parent.plotted_lines[line]['filters']:
                        if filt.checkstate and filt.name in ['Multiply','Divide'] and ((filt.method == 'X' and axiserr=='Xerr') 
                                                                                    or (filt.method == 'Y' and axiserr=='Yerr')):
                            if filt.name == 'Multiply':
                                error = error * float(filt.settings[0])
                            elif filt.name == 'Divide':
                                error = error / float(filt.settings[0])
                
                if axiserr=='Yerr':
                    self.plot_Yerr(x,y,error,line)
                else:
                    self.plot_Xerr(x,y,error,line)

    def draw_plot(self,clearplot=True):
        if clearplot:
            self.parent.axes.clear()
        lines = self.get_checked_items()
        if len(lines) > 0:
            for line in lines:
                x,y= self.get_line_data(line)
                if len(x)!=len(y):
                    pass # This can happen for combined datasets with good reason: 
                        # the user may haves e.g. _just_ chosen a new x axis that doesn't match the y axis,
                        # and are about to choose an appropriate y axis. 
                        # Instead of crashing the program and throwing an error, 
                        # just skip plotting until they choose something sensible.
                else:
                    if self.parent.plot_type == 'Histogram':
                        self.parent.settings['ylabel'] = 'Counts'
                        if 'default_ylabel' in self.parent.settings.keys():
                            self.parent.settings['xlabel'] = self.parent.settings['default_ylabel']
                        drawstyle='steps-mid'
                    else:
                        drawstyle='default'
                    if 'FFT' in self.editor_window.plot_type_box.currentText():
                        self.parent.settings['ylabel'] = 'Amplitude (a.u.)'
                        self.parent.settings['xlabel'] = 'Frequency'
                    #self.parent.image = 
                    self.parent.axes.plot(x, y,
                                        self.parent.plotted_lines[line]['linestyle'],
                                        linewidth=self.parent.plotted_lines[line]['linewidth'],
                                        markersize=self.parent.plotted_lines[line]['linewidth'],
                                        color=self.parent.plotted_lines[line]['linecolor'],
                                        drawstyle=drawstyle,
                                        label=self.parent.plotted_lines[line]['Y data'])

                    if self.parent.plotted_lines[line]['Xerr'] not in [0,'0'] or self.parent.plotted_lines[line]['Yerr'] not in [0,'0']:
                        self.process_uncertainties(line,x,y)
            self.parent.apply_plot_settings()
            #self.parent.apply_axlim_settings()
            self.parent.apply_axscale_settings()
            if self.parent.legend:
                self.parent.axes.legend()
        self.editor_window.figure.tight_layout()

    def draw_fits(self,line):
        try:
            fit_result=self.parent.plotted_lines[line]['fit']['fit_result']
            x_forfit=self.parent.plotted_lines[line]['fit']['xdata']
            y_fit=fit_result.best_fit
            self.parent.axes.plot(x_forfit, y_fit, 'k--',
                linewidth=self.parent.plotted_lines[line]['linewidth'])
            if self.parent.plotted_lines[line]['fit']['fit_uncertainty_checkstate'] == QtCore.Qt.Checked:
                uncertainty = fit_result.eval_uncertainty()
                self.parent.axes.fill_between(x_forfit, y_fit+uncertainty, y_fit-uncertainty,
                    alpha=0.2, color='grey', linewidth=0)
            if self.parent.plotted_lines[line]['fit']['fit_components_checkstate'] == QtCore.Qt.Checked:
                fit_components=fit_result.eval_components()
                if self.colormap_box.currentText() == 'viridis':
                    selected_colormap = cm.get_cmap('plasma')
                elif self.colormap_box.currentText() == 'plasma':
                    selected_colormap = cm.get_cmap('viridis')
                line_colors = selected_colormap(np.linspace(0.1,0.9,len(fit_components.keys())))
                for i,key in enumerate(fit_components.keys()):
                    self.parent.axes.plot(x_forfit, fit_components[key], '--', color=line_colors[i],alpha=0.75, linewidth=self.parent.plotted_lines[line]['linewidth'])
        except Exception as e:
            self.output_window.setText(f'Could not plot fit: {e}')

    def save_fit_result(self):
        current_row = self.trace_table.currentRow()
        line = int(self.trace_table.item(current_row,0).text())

        # Fits get saved in the lmfit format.
        if 'fit' in self.parent.plotted_lines[line].keys():
            fit_result = self.parent.plotted_lines[line]['fit']['fit_result']
            formats = 'lmfit Model Result (*.sav)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Fit Result','', formats)
            save_modelresult(fit_result,filename)

        #Stats can simply be saved in a json
        elif 'stats' in self.parent.plotted_lines[line].keys():
            formats = 'JSON (*.json)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Statistics','', formats)
            export_dict={'data_name':self.parent.label,
                         'X_param':self.parent.plotted_lines[line]['X data'],
                         'Y_param':self.parent.plotted_lines[line]['Y data']}
            for key in self.parent.plotted_lines[line]['stats'].keys():
                if isinstance(self.parent.plotted_lines[line]['stats'][key],np.ndarray):
                    export_dict[key] = self.parent.plotted_lines[line]['stats'][key].tolist()
                else:
                    export_dict[key] = self.parent.plotted_lines[line]['stats'][key]
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    jsondump(export_dict, f, ensure_ascii=False,indent=4)
            except Exception as e:
                self.editor_window.log_error(f'Could not save statistics:\n{type(e).__name__}: {e}', show_popup=True)

    def save_all_fits(self):
        current_row = self.trace_table.currentRow()
        line = int(self.trace_table.item(current_row,0).text())
        # Can save _either_ fits or stats, and decide which to do based on whether the current line has a fit or stats.
        if 'fit' in self.parent.plotted_lines[line].keys():
            fit_lines = self.get_checked_items(traces_or_fits='fits')
            formats = 'lmfit Model Result (*.sav)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Fit Result: Select base name','', formats)
            for line in fit_lines:
                fit_result = self.parent.plotted_lines[line]['fit']['fit_result']
                save_modelresult(fit_result,filename.replace('.sav',f'_{line}.sav'))

        elif 'stats' in self.parent.plotted_lines[line].keys():
            # All the stats can go into a single json.
            stat_lines=[]
            for line in self.parent.plotted_lines.keys():
                if 'stats' in self.parent.plotted_lines[line].keys():
                    stat_lines.append(line)
            formats = 'JSON (*.json)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Statistics','', formats)
            export_dict={'data_name':self.parent.label,
                         'linetrace_stats':{}}
            for line in stat_lines:
                export_dict['linetrace_stats'][line]={}
                export_dict['linetrace_stats'][line]['X_param']=self.parent.plotted_lines[line]['X data']
                export_dict['linetrace_stats'][line]['Y_param']=self.parent.plotted_lines[line]['Y data']
                for key in self.parent.plotted_lines[line]['stats'].keys():
                    if isinstance(self.parent.plotted_lines[line]['stats'][key],np.ndarray):
                        export_dict['linetrace_stats'][line][key] = self.parent.plotted_lines[line]['stats'][key].tolist()
                    else:
                        export_dict['linetrace_stats'][line][key] = self.parent.plotted_lines[line]['stats'][key]
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    jsondump(export_dict, f, ensure_ascii=False,indent=4)
            except Exception as e:
                self.editor_window.log_error(f'Could not save statistics:\n{type(e).__name__}: {e}', show_popup=True)
        else:
            self.editor_window.log_error('First select a trace with either a fit or statistics. '
                                        'Either the fits or statistics for all traces will be saved, based on that.',
                                        show_popup=True)

    def clear_fit(self,line='manual'):
        self.trace_table.itemChanged.disconnect(self.trace_table_edited)
        if line=='manual':
            manual=True
            row = self.trace_table.currentRow()
            line = int(self.trace_table.item(row,0).text())
        else:
            manual=False
            for row in range(self.trace_table.rowCount()):
                if int(self.trace_table.item(row,0).text())==line:
                    break        

        if 'fit' in self.parent.plotted_lines[line].keys():
            self.parent.plotted_lines[line].pop('fit')
            self.trace_table.setItem(row,8,QtWidgets.QTableWidgetItem(''))
            self.trace_table.setItem(row,9,QtWidgets.QTableWidgetItem(''))
            self.trace_table.setItem(row,10,QtWidgets.QTableWidgetItem(''))
            if manual:
                self.editor_window.update_plots(update_data=False)

        # should never be both, but use 'if' just in case
        if 'stats' in self.parent.plotted_lines[line].keys():
            self.parent.plotted_lines[line].pop('stats')

        if manual:
            fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]
            self.output_window.setText('Information about selected fit type:\n'+
                                   fit_function['description'])
            
        self.trace_table.itemChanged.connect(self.trace_table_edited)

    def clear_all_fits(self):
        try:
            for line in self.parent.plotted_lines.keys():
                self.clear_fit(line)
        except Exception as e:
            self.editor_window.log_error(f'Could not clear all fits:\n{type(e).__name__}: {e}', show_popup=True)

        fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]
        self.output_window.setText('Information about selected fit type:\n'+fit_function['description'])
        self.editor_window.update_plots(update_data=False)

    def save_fit_preset(self):
        preset_dict={}
        preset_dict['xlims']=[self.xmin_box.text(),self.xmax_box.text()]
        preset_dict['function_class']=self.fit_class_box.currentText()
        preset_dict['function_name']=self.fit_box.currentText()
        preset_dict['inputinfo']=self.input_edit.text()
        preset_dict['initial_guess']=self.guess_edit.text()
        if self.guess_checkbox.isChecked():
            preset_dict['intial_checkbox']=True
                
        formats = 'JSON (*.json)'
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Figure As', '', formats)
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                jsondump(preset_dict, f, ensure_ascii=False)

    def load_fit_preset(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self, 'Open Fitting Preset', '', '*.json')
        if filename:
            with open(filename) as f:
                preset_dict=jsonload(f)
            self.xmin_box.setText(preset_dict['xlims'][0])
            self.xmax_box.setText(preset_dict['xlims'][1])
            self.fit_class_box.setCurrentText(preset_dict['function_class'])
            self.fit_box.setCurrentText(preset_dict['function_name'])
            self.input_edit.setText(preset_dict['inputinfo'])
            self.guess_edit.setText(preset_dict['initial_guess'])
            if preset_dict['intial_checkbox']:
                self.guess_checkbox.setCheckState(QtCore.Qt.Checked)
            else:
                self.guess_checkbox.setCheckState(QtCore.Qt.UnChecked)
            self.editor_window.update_plots(update_data=False)

    def closeEvent(self, event):
        self.running = False
