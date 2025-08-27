from PyQt5 import QtWidgets, QtCore, QtGui
import io
import os
import sys
from json import load as jsonload
from json import dump as jsondump
from csv import writer as csvwriter
import qcodespp.plotting.offline.fits as fits
from scipy.ndimage import map_coordinates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from matplotlib import rcParams
from matplotlib import colormaps as cm
import numpy as np
from lmfit.model import save_modelresult

import matplotlib.style as mplstyle
mplstyle.use('fast')

try:
    import qdarkstyle # pip install qdarkstyle
    qdarkstyle_imported = True
except ModuleNotFoundError:
    qdarkstyle_imported = False

DARK_THEME = True

from .helpers import rcParams_to_dark_theme, rcParams_to_light_theme, cmaps,DraggablePoint

class LineCutWindow(QtWidgets.QWidget):
    def __init__(self, parent, orientation, init_cmap='viridis',init_canvas=True,editor_window=None):
        super().__init__()
        # The parent is the DATA object.
        self.parent = parent
        # self.editor_window is the main window.
        self.editor_window = editor_window
        self.running = True
        self.orientation = orientation
        self.init_cmap = init_cmap

        try:
            self.setWindowTitle(f'InSpectra Gadget - {orientation} linecuts for {self.parent.label}')
        except:
            self.setWindowTitle('InSpectra Gadget - Linecut and Fitting Window')
        
        try:
            if sys.platform.startswith('win'):
                icon_file = 'iconGadget.ico'
            else:
                icon_file = 'iconGadget.png'
            self.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), icon_file)))
        except Exception as e:
            pass
        
        self.resize(1200, 900)
        self.init_widgets()
        if init_canvas:
            self.init_canvas()
        self.init_connections()
        self.init_layouts()
        self.set_main_layout()
        self.init_cuts_table()
        self.fit_type_changed()
        
    def init_widgets(self):
        # Widgets in Linecut list box
        self.add_cut_button = QtWidgets.QPushButton('Add')
        self.remove_cut_button = QtWidgets.QPushButton('Remove')
        self.clear_cuts_button = QtWidgets.QPushButton('Clear list')

        self.copy_button = QtWidgets.QPushButton('Copy all')
        self.copy_checked_button = QtWidgets.QPushButton('Copy checked')
        self.paste_button = QtWidgets.QPushButton('Paste')

        self.generate_label = QtWidgets.QLabel('start,end,step,offset')
        self.generate_line_edit=QtWidgets.QLineEdit('0,-1,1,0')
        self.generate_button=QtWidgets.QPushButton('Generate')

        self.cuts_table = QtWidgets.QTableWidget()

        self.move_up_button = QtWidgets.QPushButton('Move Up')
        self.move_down_button = QtWidgets.QPushButton('Move Down')
        self.reorder_by_index_button = QtWidgets.QPushButton('Reorder by ind')

        self.colormap_type_box = QtWidgets.QComboBox()
        self.colormap_box = QtWidgets.QComboBox()
        self.apply_colormap_to_box = QtWidgets.QComboBox() # All by index, all by num, selected by ind, selected by num, checked by ind, checked by num
        self.apply_button = QtWidgets.QPushButton('Apply')

        applymethods=['All by order', 'All by ind', 'Chkd by order','Chkd by ind']
        self.apply_colormap_to_box.addItems(applymethods)
        for cmap_type in cmaps:    
            self.colormap_type_box.addItem(cmap_type)
        self.colormap_box.addItems(list(cmaps.values())[0])
        self.colormap_box.setCurrentText(self.init_cmap)

        self.linestyle_label = QtWidgets.QLabel('Style:')
        self.linestyle_box = QtWidgets.QComboBox()
        self.linestyle_box.addItems(['-', '--', '-.', ':','.','o','v', '^', '<', '>', '8', 's', 'p', '*', 'h', 'H', 'D', 'd', 'P', 'X'])
        self.linestyle_box.setCurrentText(self.parent.linecuts[self.orientation]['linestyle'])
        self.linesize_label = QtWidgets.QLabel('Size:')
        self.linesize_box = QtWidgets.QDoubleSpinBox()
        self.linesize_box.setRange(0.25, 50)
        self.linesize_box.setSingleStep(0.25)
        self.linesize_box.setValue(self.parent.linecuts[self.orientation]['linesize'])

        # Plotting widgets
        self.reset_plot_limits_button = QtWidgets.QPushButton('Autoscale axes')
        self.plot_against_label = QtWidgets.QLabel('Plot against:')
        self.plot_against_box = QtWidgets.QComboBox() #For diagonal linecuts
        self.plot_against_box.addItems([f'X: {self.parent.settings['xlabel']}',f'Y: {self.parent.settings['ylabel']}','sqrt((x-x0)^2+(y-y0)^2)'])
        if self.orientation == 'diagonal':
            self.left_button = QtWidgets.QPushButton('Left')
            self.right_button = QtWidgets.QPushButton('Right')
            self.up_button = QtWidgets.QPushButton('Up')
            self.down_button = QtWidgets.QPushButton('Down')
        self.save_button = QtWidgets.QPushButton('Save Data')
        self.save_image_button = QtWidgets.QPushButton('Save Image')
        self.copy_image_button = QtWidgets.QPushButton('Copy Image')
        self.copy_table_button = QtWidgets.QPushButton('Copy Table')
        self.xscale_label = QtWidgets.QLabel('x-axis:')
        self.xscale_box = QtWidgets.QComboBox()
        self.xscale_box.addItems(['linear', 'log', 'symlog', 'logit'])
        self.xscale_box.setCurrentText(self.parent.linecuts[self.orientation]['xscale'])
        self.yscale_label = QtWidgets.QLabel('y-axis:')
        self.yscale_box = QtWidgets.QComboBox()
        self.yscale_box.addItems(['linear', 'log', 'symlog', 'logit'])
        self.yscale_box.setCurrentText(self.parent.linecuts[self.orientation]['yscale'])
        self.legend_checkbox = QtWidgets.QCheckBox('Show legend')
        self.legend_checkbox.setChecked(self.parent.linecuts[self.orientation]['legend'])

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
        self.save_parameters_dependency_button = QtWidgets.QPushButton('Generate param dependency')
        self.clear_all_fits_button = QtWidgets.QPushButton('Clear all fits')
        self.save_preset_button = QtWidgets.QPushButton('Save preset')
        self.load_preset_button = QtWidgets.QPushButton('Load preset')

        # if self.orientation in ['horizontal','vertical']:
        #     #self.orientation_button = QtWidgets.QPushButton('Hor./Vert.')
        #     self.up_button = QtWidgets.QPushButton('Up/Right')
        #     self.down_button = QtWidgets.QPushButton('Down/Left')

    def init_connections(self):
        self.add_cut_button.clicked.connect(self.add_cut_manually)
        self.remove_cut_button.clicked.connect(lambda: self.remove_cut('selected'))
        self.clear_cuts_button.clicked.connect(lambda: self.remove_cut('all'))
        self.copy_button.clicked.connect(self.copy_cuts)
        self.copy_checked_button.clicked.connect(lambda: self.copy_cuts('checked'))
        self.paste_button.clicked.connect(self.paste_cuts)
        self.generate_button.clicked.connect(self.generate_cuts)
        self.move_up_button.clicked.connect(lambda: self.move_cut('up'))
        self.move_down_button.clicked.connect(lambda: self.move_cut('down'))
        self.reorder_by_index_button.clicked.connect(self.reorder_cuts)
        self.apply_button.clicked.connect(self.apply_colormap)

        self.linesize_box.valueChanged.connect(lambda: self.style_changed('linesize', self.linesize_box.value()))
        self.linestyle_box.currentIndexChanged.connect(lambda: self.style_changed('linestyle', self.linestyle_box.currentText()))

        self.cuts_table.itemClicked.connect(self.item_clicked)

        self.reset_plot_limits_button.clicked.connect(self.autoscale_axes)
        self.plot_against_box.currentIndexChanged.connect(self.update)
        if self.orientation == 'diagonal':
            self.left_button.clicked.connect(lambda: self.move_diagonal_line('left'))
            self.right_button.clicked.connect(lambda: self.move_diagonal_line('right'))
            self.up_button.clicked.connect(lambda: self.move_diagonal_line('up'))
            self.down_button.clicked.connect(lambda: self.move_diagonal_line('down'))

        self.save_button.clicked.connect(self.save_data)
        self.save_image_button.clicked.connect(self.save_image)
        self.copy_image_button.clicked.connect(self.copy_image)
        self.copy_table_button.clicked.connect(self.copy_cuts_table_to_clipboard)
        self.xscale_box.currentIndexChanged.connect(lambda: self.update_axscale('xscale'))
        self.yscale_box.currentIndexChanged.connect(lambda: self.update_axscale('yscale'))
        self.legend_checkbox.toggled.connect(self.update_legend)

        self.clear_fit_button.clicked.connect(lambda: self.clear_fit(line='manual'))
        self.fit_class_box.currentIndexChanged.connect(self.fit_class_changed)
        self.fit_box.currentIndexChanged.connect(self.fit_type_changed)
        self.fit_button.clicked.connect(lambda: self.start_fitting(line='manual'))
        self.save_result_button.clicked.connect(self.save_fit_result)
        self.fit_checked_button.clicked.connect(self.fit_checked)
        self.save_all_fits_button.clicked.connect(self.save_all_fits)
        self.clear_all_fits_button.clicked.connect(self.clear_all_fits)
        self.save_parameters_dependency_button.clicked.connect(self.save_parameters_dependency)
        self.save_preset_button.clicked.connect(self.save_fit_preset)
        self.load_preset_button.clicked.connect(self.load_fit_preset)
        self.xmin_box.editingFinished.connect(self.limits_edited)
        self.xmax_box.editingFinished.connect(self.limits_edited)
        self.reset_axes_button.clicked.connect(self.reset_limits)
        self.cuts_table.itemChanged.connect(self.cuts_table_edited)
        self.colormap_type_box.currentIndexChanged.connect(self.colormap_type_edited)
        # if self.orientation in ['horizontal','vertical']:
        #     #self.orientation_button.clicked.connect(self.change_orientation)
        #     self.up_button.clicked.connect(lambda: self.change_index('up'))
        #     self.down_button.clicked.connect(lambda: self.change_index('down'))
        
    def init_canvas(self):
        self.figure = Figure(tight_layout={'pad':2})
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        # self.scroll_event_id = self.canvas.mpl_connect('scroll_event', 
        #                                                self.mouse_scroll_canvas)
        self.canvas.mpl_connect('button_press_event', self.mouse_click_canvas)
        self.canvas.mpl_connect('scroll_event', self.mouse_scroll_canvas)
        self.navi_toolbar = NavigationToolbar(self.canvas, self)
    
    def init_layouts(self):
        # Sub-layouts in Linecut list box:
        self.table_buttons_layout = QtWidgets.QHBoxLayout()
        self.copy_paste_layout = QtWidgets.QHBoxLayout()
        self.generate_layout = QtWidgets.QHBoxLayout()
        self.move_buttons_layout = QtWidgets.QHBoxLayout()
        self.colormap_layout = QtWidgets.QHBoxLayout()
        self.style_layout = QtWidgets.QHBoxLayout()

        # Populating
        self.table_buttons_layout.addWidget(self.add_cut_button)
        self.table_buttons_layout.addWidget(self.remove_cut_button)
        self.table_buttons_layout.addWidget(self.clear_cuts_button)

        self.copy_paste_layout.addWidget(self.copy_button)
        self.copy_paste_layout.addWidget(self.copy_checked_button)
        self.copy_paste_layout.addWidget(self.paste_button)

        self.move_buttons_layout.addWidget(self.move_up_button)
        self.move_buttons_layout.addWidget(self.move_down_button)
        #self.move_buttons_layout.addWidget(self.reorder_by_index_button)
        #self.move_buttons_layout.addStretch()

        self.generate_layout.addWidget(self.generate_label)
        self.generate_layout.addWidget(self.generate_line_edit)
        self.generate_layout.addWidget(self.generate_button)

        self.colormap_layout.addWidget(self.colormap_type_box)
        self.colormap_layout.addWidget(self.colormap_box)
        self.colormap_layout.addWidget(self.apply_colormap_to_box)
        self.colormap_layout.addWidget(self.apply_button)

        self.style_layout.addWidget(self.linestyle_label)
        self.style_layout.addWidget(self.linestyle_box)
        self.style_layout.addWidget(self.linesize_label)
        self.style_layout.addWidget(self.linesize_box)

        # Sublayout(s) in plotting box:
        self.top_buttons_layout = QtWidgets.QHBoxLayout()
        self.bot_buttons_layout = QtWidgets.QHBoxLayout()

        # Populating
        #self.top_buttons_layout.addWidget(self.navi_toolbar)
        if self.orientation =='diagonal':
            self.top_buttons_layout.addWidget(self.plot_against_label)
            self.top_buttons_layout.addWidget(self.plot_against_box)
            self.top_buttons_layout.addStretch()
            self.top_buttons_layout.addWidget(self.left_button)
            self.top_buttons_layout.addWidget(self.right_button)
            self.top_buttons_layout.addWidget(self.down_button)
            self.top_buttons_layout.addWidget(self.up_button)

        self.top_buttons_layout.addStretch()
        self.top_buttons_layout.addWidget(self.save_button)
        self.top_buttons_layout.addWidget(self.save_image_button)
        self.top_buttons_layout.addWidget(self.copy_image_button)
        self.top_buttons_layout.addWidget(self.copy_table_button)
        #self.top_buttons_layout.addStretch()
        # if self.orientation in ['horizontal','vertical']:
        #     #self.top_buttons_layout.addWidget(self.orientation_button)
        #     self.top_buttons_layout.addWidget(self.down_button)
        #     self.top_buttons_layout.addWidget(self.up_button)
        self.bot_buttons_layout.addWidget(self.legend_checkbox)
        self.bot_buttons_layout.addWidget(self.xscale_label)
        self.bot_buttons_layout.addWidget(self.xscale_box)
        self.bot_buttons_layout.addWidget(self.yscale_label)
        self.bot_buttons_layout.addWidget(self.yscale_box)
        self.bot_buttons_layout.addStretch()
        self.bot_buttons_layout.addWidget(self.reset_plot_limits_button)
        
        # Sub-layouts(s) in fitting box
        self.lims_layout = QtWidgets.QHBoxLayout()
        self.fit_layout = QtWidgets.QHBoxLayout()
        self.inputs_layout = QtWidgets.QHBoxLayout()
        self.guess_layout = QtWidgets.QHBoxLayout()
        self.output_layout = QtWidgets.QVBoxLayout()
        self.fit_buttons_layout = QtWidgets.QHBoxLayout()

        # Populating
        self.lims_layout.addWidget(self.lims_label)
        self.lims_layout.addWidget(self.xmin_label)
        self.lims_layout.addWidget(self.xmin_box)
        self.lims_layout.addWidget(self.xmax_label)
        self.lims_layout.addWidget(self.xmax_box)
        self.lims_layout.addWidget(self.reset_axes_button)
        self.lims_layout.addStretch()

        self.fit_layout.addWidget(self.fit_functions_label)
        self.fit_layout.addWidget(self.fit_class_box)
        self.fit_layout.addWidget(self.fit_box)
        self.fit_layout.addStretch()
        self.fit_layout.addWidget(self.save_preset_button)
        self.fit_layout.addWidget(self.load_preset_button)

        self.inputs_layout.addWidget(self.input_label)
        self.inputs_layout.addWidget(self.input_edit)
        #self.inputs_layout.addStretch()

        self.guess_layout.addWidget(self.guess_checkbox)
        self.guess_layout.addWidget(self.guess_edit)
        #self.guess_layout.addStretch()

        self.output_layout.addWidget(self.output_window)

        self.fit_buttons_layout.addWidget(self.fit_button)
        self.fit_buttons_layout.addWidget(self.save_result_button)
        self.fit_buttons_layout.addWidget(self.clear_fit_button)
        self.fit_buttons_layout.addStretch()
        self.fit_buttons_layout.addWidget(self.fit_checked_button)
        self.fit_buttons_layout.addWidget(self.save_all_fits_button)
        self.fit_buttons_layout.addWidget(self.clear_all_fits_button)
        self.fit_buttons_layout.addWidget(self.save_parameters_dependency_button)

    def set_main_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout()
        self.top_half_layout = QtWidgets.QHBoxLayout()

        self.tablebox=QtWidgets.QGroupBox('Linecut list')
        self.table_layout = QtWidgets.QVBoxLayout()
        self.table_layout.addLayout(self.table_buttons_layout)
        if self.orientation in ['horizontal','vertical']:
            self.table_layout.addLayout(self.generate_layout)
        self.table_layout.addWidget(self.cuts_table)
        self.table_layout.addLayout(self.move_buttons_layout)
        self.table_layout.addLayout(self.copy_paste_layout)
        self.table_layout.addLayout(self.colormap_layout)
        self.table_layout.addLayout(self.style_layout)
        self.tablebox.setLayout(self.table_layout)
        self.tablebox.setMaximumWidth(450)
        
        self.plotbox=QtWidgets.QGroupBox('Plotting')
        self.plottinglayout = QtWidgets.QVBoxLayout()
        self.plottinglayout.addLayout(self.top_buttons_layout)
        self.plottinglayout.addWidget(self.navi_toolbar)
        self.plottinglayout.addWidget(self.canvas)
        self.plottinglayout.addLayout(self.bot_buttons_layout)
        self.plotbox.setLayout(self.plottinglayout)

        self.fittingbox=QtWidgets.QGroupBox('Curve Fitting')
        self.fittingbox.setMaximumHeight(450)
        self.fittinglayout = QtWidgets.QVBoxLayout()
        self.fittinglayout.addLayout(self.lims_layout)
        self.fittinglayout.addLayout(self.fit_layout)
        self.fittinglayout.addLayout(self.inputs_layout)
        self.fittinglayout.addLayout(self.guess_layout)
        self.fittinglayout.addLayout(self.output_layout)
        self.fittinglayout.addLayout(self.fit_buttons_layout)
        self.fittingbox.setLayout(self.fittinglayout)

        self.top_half_layout.addWidget(self.tablebox)
        self.top_half_layout.addWidget(self.plotbox)
        self.main_layout.addLayout(self.top_half_layout)
        self.main_layout.addWidget(self.fittingbox)
        self.setLayout(self.main_layout)

    def init_cuts_table(self):
        self.cuts_table.setColumnCount(8)
        self.cuts_table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked)
        h = self.cuts_table.horizontalHeader()
        h.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for col in range(8):
            h.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
        headerlabels={'vertical':['cut #','index','value','offset','color','show fit','show fit cmpts','show fit err'],
                    'horizontal':['cut #','index','value','offset','color','show fit','show fit cmpts','show fit err'],
                    'diagonal':['cut #','point A','point B','offset','color','show fit','show fit cmpts','show fit err']}
        self.cuts_table.setHorizontalHeaderLabels(headerlabels[self.orientation])
        v=self.cuts_table.verticalHeader()
        v.setVisible(False)

        self.cuts_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.cuts_table.customContextMenuRequested.connect(self.open_cuts_table_menu)

    def copy_cuts(self,which='all'):
        # Call on editor_window's method, but need to know which item this is; it's not necessarily the current item in the file list.
        if which=='checked':
            lines = self.get_checked_items(return_indices=False, cuts_or_fits='cuts')
        else:
            lines = None

        items = self.editor_window.get_all_items()
        for item in items:
            if item.data == self.parent:
                self.editor_window.copy_linecuts(self.orientation, item,lines)
                break
    
    def paste_cuts(self):
        # Does the same as above but pastes
        items = self.editor_window.get_all_items()
        for item in items:
            if item.data == self.parent:
                self.editor_window.paste_linecuts(item)
                break

    def item_clicked(self, item):
        # displays the fit result and/or information.
        row = self.cuts_table.currentRow()
        line = int(self.cuts_table.item(row,0).text())
        if 'fit' in self.parent.linecuts[self.orientation]['lines'][line].keys():
            fit_result = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result']
            self.output_window.setText(fit_result.fit_report())
        elif 'stats' in self.parent.linecuts[self.orientation]['lines'][line].keys():
            text='Statistics:\n'
            for key in self.parent.linecuts[self.orientation]['lines'][line]['stats'].keys():
                text+=f'{key}: {self.parent.linecuts[self.orientation]['lines'][line]['stats'][key]}\n'
            self.output_window.setText(text)
        else:
            fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]
            self.output_window.setText('Information about selected fit type:\n'+
                                   fit_function['description'])

    def get_checked_items(self, return_indices = False, cuts_or_fits='cuts'):
        # Note this is a bit different to the main window, where the entire item is returned.
        # Here we just return the identifier for the linecut
        if cuts_or_fits == 'cuts':
            column = 0
        elif cuts_or_fits == 'fits':
            column = 5
        indices = [index for index in range(self.cuts_table.rowCount()) 
                   if self.cuts_table.item(index,column).checkState() == 2]
        checked_items = [int(self.cuts_table.item(index,0).text()) for index in indices]
        if return_indices:    
            return checked_items, indices
        else:
            return checked_items
        
    def append_cut_to_table(self,linecut_name):
        row = self.cuts_table.rowCount()
        linecut=self.parent.linecuts[self.orientation]['lines'][linecut_name]
        # linecut is an entry in the parent.linecuts['orientation']['lines'] dictionary
        # It has keys 'data_index', 'checkstate', 'cut_axis_value', and possibly 'linecolor'
        self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
        self.cuts_table.insertRow(row)
        v = self.cuts_table.verticalHeader()
        v.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for rownum in range(int(row+1)):
            v.setSectionResizeMode(rownum, QtWidgets.QHeaderView.ResizeToContents)

        # First column is the linecut identifier and checkbox
        linecut_item = QtWidgets.QTableWidgetItem(str(linecut_name))
        linecut_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                                 QtCore.Qt.ItemIsEnabled | 
                                 QtCore.Qt.ItemIsUserCheckable)
        linecut_item.setText(str(linecut_name))
        linecut_item.setCheckState(linecut['checkstate'])

        self.cuts_table.setItem(row,0,linecut_item)

        # Second and third line for horizontal and vertical is the index spin box and the value on the cut axis.
        if self.orientation in ['horizontal','vertical']:
            index_box=QtWidgets.QSpinBox()
            if self.orientation=='horizontal':
                index_box.setRange(0,np.shape(self.parent.processed_data[-1])[1]-1)
            elif self.orientation=='vertical':
                index_box.setRange(0,np.shape(self.parent.processed_data[-1])[0]-1)
            index_box.setSingleStep(1)
            index_box.setValue(linecut['data_index'])
            index_box.valueChanged[int].connect(lambda: self.cuts_table_edited('index'))

            value_box=QtWidgets.QTableWidgetItem(f'{linecut['cut_axis_value']:6g}')

            self.cuts_table.setCellWidget(row,1,index_box)
            self.cuts_table.setItem(row,2,value_box)
            self.cuts_table.item(row, 2).setTextAlignment(int(QtCore.Qt.AlignRight) | 
                                                    int(QtCore.Qt.AlignVCenter))

        elif self.orientation == 'diagonal':
            pointA_box=QtWidgets.QTableWidgetItem(f'{linecut['points'][0][0]:.4g}, {linecut['points'][0][1]:.4g}')
            pointB_box=QtWidgets.QTableWidgetItem(f'{linecut['points'][1][0]:.4g}, {linecut['points'][1][1]:.4g}')

            self.cuts_table.setItem(row,1,pointA_box)
            self.cuts_table.setItem(row,2,pointB_box)

        # All types; y-offset, color, and fit checkbox
        offset_box=QtWidgets.QTableWidgetItem(f'{linecut['offset']:6g}')

        self.cuts_table.setItem(row,3,offset_box)
        self.cuts_table.item(row, 3).setTextAlignment(int(QtCore.Qt.AlignRight) | 
                                                    int(QtCore.Qt.AlignVCenter))
        
        color_box=QtWidgets.QTableWidgetItem('')
        self.cuts_table.setItem(row,4,color_box)
        if type(linecut['linecolor'])==str and linecut['linecolor'].startswith('#'):
            self.cuts_table.item(row,4).setBackground(QtGui.QColor(linecut['linecolor']))
        else:
            rgbavalue = [int(linecut['linecolor'][0]*255), int(linecut['linecolor'][1]*255), int(linecut['linecolor'][2]*255),int(linecut['linecolor'][3]*255)]
            self.cuts_table.item(row,4).setBackground(QtGui.QColor(*rgbavalue))
        
        plot_fit_item = QtWidgets.QTableWidgetItem('')
        if 'fit' in linecut.keys():
            plot_fit_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                            QtCore.Qt.ItemIsEnabled | 
                            QtCore.Qt.ItemIsUserCheckable)
            plot_fit_item.setCheckState(linecut['fit']['fit_checkstate'])
        self.cuts_table.setItem(row,5,plot_fit_item)

        fit_components_item = QtWidgets.QTableWidgetItem('')
        if 'fit' in linecut.keys():
            fit_components_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                            QtCore.Qt.ItemIsEnabled | 
                            QtCore.Qt.ItemIsUserCheckable)
            fit_components_item.setCheckState(linecut['fit']['fit_components_checkstate'])
        self.cuts_table.setItem(row,6,fit_components_item)

        fit_error_item = QtWidgets.QTableWidgetItem('')
        if 'fit' in linecut.keys():
            fit_error_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                            QtCore.Qt.ItemIsEnabled | 
                            QtCore.Qt.ItemIsUserCheckable)
            fit_error_item.setCheckState(linecut['fit']['fit_uncertainty_checkstate'])
        self.cuts_table.setItem(row,7,fit_error_item)

        self.cuts_table.setCurrentCell(row,0)
        self.cuts_table.itemChanged.connect(self.cuts_table_edited)

    def points_dragged(self,line):
        self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
        line = int(line)
        row = [row for row in range(self.cuts_table.rowCount()) if int(self.cuts_table.item(row,0).text()) == line][0]
        linecut=self.parent.linecuts[self.orientation]['lines'][line]
        self.cuts_table.item(row, 1).setText(f'{linecut['points'][0][0]:.4g}, {linecut['points'][0][1]:.4g}')
        self.cuts_table.item(row, 2).setText(f'{linecut['points'][1][0]:.4g}, {linecut['points'][1][1]:.4g}')
        self.cuts_table.itemChanged.connect(self.cuts_table_edited)

    def cuts_table_edited(self,item):
        if item=='index':
            current_row = self.cuts_table.currentRow()
            self.index_changed(current_row)
            self.update()

        else:
            current_item = item
            current_col = item.column()
            current_row = item.row()

            if current_col == 2 and self.orientation in ['horizontal','vertical']: # The user is trying to edit the value of the data. Let's find a new index for them.
                linecut = self.cuts_table.item(current_row,0).text()
                linecut = int(linecut)
                inputval = float(current_item.text())
                if self.orientation == 'horizontal':
                    new_index = (np.abs(self.parent.processed_data[1][0,:]-inputval)).argmin()
                elif self.orientation == 'vertical':
                    new_index = (np.abs(self.parent.processed_data[0][:,0]-inputval)).argmin()
                self.cuts_table.cellWidget(current_row,1).setValue(new_index)
                self.index_changed(current_row)

            elif current_col in [1,2] and self.orientation in ['diagonal','circular']:
                linecut = self.cuts_table.item(current_row,0).text()
                linecut = int(linecut)
                x= float(current_item.text().split(',')[0])
                y= float(current_item.text().split(',')[1])

                if current_col == 1:
                    self.parent.linecuts[self.orientation]['lines'][linecut]['points'][0] = (x,y)
                elif current_col == 2:
                    self.parent.linecuts[self.orientation]['lines'][linecut]['points'][1] = (x,y)
                self.update_draggable_points(linecut)

            elif current_col == 3: #Change the offset in the dictionary and then replot.
                linecut = self.cuts_table.item(current_row,0).text()
                linecut = int(linecut)
                offset = float(current_item.text())
                self.parent.linecuts[self.orientation]['lines'][linecut]['offset'] = offset
    
            elif current_col == 0: # It's the checkstate, so need to replot and update dictionary
                linecut = int(self.cuts_table.item(current_row,0).text())
                self.parent.linecuts[self.orientation]['lines'][linecut]['checkstate'] = current_item.checkState()
                if self.orientation in ['diagonal','circular']:
                    if current_item.checkState() in [2,QtCore.Qt.Checked]:
                        replot=True
                    else:
                        replot=False
                    self.update_draggable_points(linecut,replot=replot)

            elif current_col == 5: # It's the checkstate for the fit.
                linecut = int(self.cuts_table.item(current_row,0).text())
                self.parent.linecuts[self.orientation]['lines'][linecut]['fit']['fit_checkstate'] = current_item.checkState()

            elif current_col == 6: # It's the checkstate for the fit components.
                linecut = int(self.cuts_table.item(current_row,0).text())
                self.parent.linecuts[self.orientation]['lines'][linecut]['fit']['fit_components_checkstate'] = current_item.checkState()

            elif current_col == 7: # It's the checkstate for the fit error.
                linecut = int(self.cuts_table.item(current_row,0).text())
                self.parent.linecuts[self.orientation]['lines'][linecut]['fit']['fit_uncertainty_checkstate'] = current_item.checkState()
        
            self.update()

    def style_changed(self, option, value):
        self.parent.linecuts[self.orientation][option] = value
        self.update()

    def update_draggable_points(self,linecut,replot=True):
        if 'draggable_points' in self.parent.linecuts[self.orientation]['lines'][linecut].keys():
            for i,artistname in zip([0,1,1],['point_on_plot','point_on_plot','line_on_plot']):
                if hasattr(self.parent.linecuts[self.orientation]['lines'][linecut]['draggable_points'][i], artistname):
                    try:
                        artist= getattr(self.parent.linecuts[self.orientation]['lines'][linecut]['draggable_points'][i], artistname)
                        artist.remove()
                    except Exception as e:
                        self.editor_window.log_error(f'Error removing diagonal linecut:\n{type(e).__name__}: {e}', show_popup=True)
            try:
                self.parent.linecuts[self.orientation]['lines'][linecut]['draggable_points'].pop()
            except Exception as e:
                self.editor_window.log_error(f'Error removing diagonal linecut:\n{type(e).__name__}: {e}', show_popup=True)
        if replot:
            newpoints=self.parent.linecuts[self.orientation]['lines'][linecut]['points']
            self.parent.linecuts[self.orientation]['lines'][linecut]['draggable_points']=[DraggablePoint(self.parent,newpoints[0][0],newpoints[0][1],linecut,self.orientation),
                                        DraggablePoint(self.parent,newpoints[1][0],newpoints[1][1],linecut,self.orientation,draw_line=True)]
            for point in self.parent.linecuts[self.orientation]['lines'][linecut]['draggable_points']:
                point.color = self.parent.linecuts[self.orientation]['lines'][linecut]['linecolor']

    def move_diagonal_line(self,direction):
        # Move the diagonal line in the direction specified.
        linecut = int(self.cuts_table.item(self.cuts_table.currentRow(),0).text())
        indices=self.parent.linecuts[self.orientation]['lines'][linecut]['indices']
        try:
            if direction == 'left':
                new_indices = [indices[0][0]-1,indices[1][0]-1]
                if all([i>=0 for i in new_indices]):
                    indices[0]=(new_indices[0],indices[0][1])
                    indices[1]=(new_indices[1],indices[1][1])
            elif direction == 'right':
                new_indices = [indices[0][0]+1,indices[1][0]+1]
                if all([i<self.parent.processed_data[0].shape[0] for i in new_indices]):
                    indices[0]=(new_indices[0],indices[0][1])
                    indices[1]=(new_indices[1],indices[1][1])
            elif direction == 'up':
                new_indices = [indices[0][1]+1,indices[1][1]+1]
                if all([i<self.parent.processed_data[1].shape[1] for i in new_indices]):
                    indices[0]=(indices[0][0],new_indices[0])
                    indices[1]=(indices[1][0],new_indices[1])
            elif direction == 'down':
                new_indices = [indices[0][1]-1,indices[1][1]-1]
                if all([i>=0 for i in new_indices]):
                    indices[0]=(indices[0][0],new_indices[0])
                    indices[1]=(indices[1][0],new_indices[1])

            newpoints=[(self.parent.processed_data[0][indices[0][0],0],self.parent.processed_data[1][0,indices[0][1]]),
                    (self.parent.processed_data[0][indices[1][0],0],self.parent.processed_data[1][0,indices[1][1]])]
            
            self.parent.linecuts[self.orientation]['lines'][linecut]['points'] = newpoints

            self.update_draggable_points(linecut)

            self.update()

        except Exception as e:
            self.editor_window.log_error(f'Error changing linecut position:\n{type(e).__name__}: {e}', show_popup=True)

    def index_changed(self,row):
        self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
        index_box = self.cuts_table.cellWidget(row,1)
        data_index=index_box.value()
        linecut = int(self.cuts_table.item(row,0).text())
        try:
            if self.orientation == 'horizontal':
                self.parent.linecuts[self.orientation]['lines'][linecut]['cut_axis_value']=self.parent.processed_data[1][0,data_index]
                self.cuts_table.item(row,2).setText(f'{self.parent.processed_data[1][0,data_index]:6g}')
            elif self.orientation == 'vertical':
                self.parent.linecuts[self.orientation]['lines'][linecut]['cut_axis_value']=self.parent.processed_data[0][data_index,0]
                self.cuts_table.item(row,2).setText(f'{self.parent.processed_data[0][data_index,0]:6g}')
            self.parent.linecuts[self.orientation]['lines'][linecut]['data_index'] = data_index
        except Exception as e:
            self.editor_window.log_error(f'Error changing linecut index:\n{type(e).__name__}: {e}', show_popup=True)
        self.cuts_table.setCurrentItem(self.cuts_table.item(row,0)) # Hopefully fixes a bug that if the index is changed, the focus goes weird.
        self.cuts_table.itemChanged.connect(self.cuts_table_edited)

    def add_cut_manually(self,data_index=0,offset=0,linecolor=None,update=True):
        # Add a linecut when the button is pushed or from the generator. Default to zero-th index if it's the push button.
        data_index=int(data_index)
        try:
            max_index=np.max(list(self.parent.linecuts[self.orientation]['lines'].keys()))
        except ValueError:
            max_index=-1
        try:
            selected_colormap = cm.get_cmap(self.colormap_box.currentText())
            if self.orientation == 'horizontal':
                line_colors = selected_colormap(np.linspace(0.1,0.9,len(self.parent.processed_data[1][0,:])))
                self.parent.linecuts[self.orientation]['lines'][int(max_index+1)]={'data_index':data_index, 
                        'checkstate':QtCore.Qt.Checked,
                        'cut_axis_value':self.parent.processed_data[1][0,data_index],
                        'offset':offset,
                        'linecolor':line_colors[data_index]}
            elif self.orientation == 'vertical':
                line_colors = selected_colormap(np.linspace(0.1,0.9,len(self.parent.processed_data[0][:,0])))
                self.parent.linecuts[self.orientation]['lines'][int(max_index+1)]={'data_index':data_index, 
                        'checkstate':QtCore.Qt.Checked,
                        'cut_axis_value':self.parent.processed_data[0][data_index,0],
                        'offset':offset,
                        'linecolor':line_colors[data_index]}
                
            elif self.orientation == 'diagonal':
                line_colors = selected_colormap(np.linspace(0.1,0.9,len(self.parent.processed_data[1][0,:])))
                left,right= self.parent.axes.get_xlim()
                bottom,top= self.parent.axes.get_ylim()
                x_0=left+(right-left)/10
                x_1=right-(right-left)/10
                y_0=bottom+(top-bottom)/10
                y_1=top-(top-bottom)/10
                self.parent.linecuts[self.orientation]['lines'][int(max_index+1)]={'points':[(x_0, y_0),(x_1, y_1)],
                            'checkstate':2,
                            'offset':0,
                            'linecolor':line_colors[int(max_index+1)]
                            }
                self.parent.linecuts[self.orientation]['lines'][int(max_index+1)]['draggable_points']=[DraggablePoint(self.parent,x_0,y_0,int(max_index+1),self.orientation),
                                                DraggablePoint(self.parent,x_1,y_1,int(max_index+1),self.orientation,draw_line=True)]
            self.append_cut_to_table(int(max_index+1))
        except IndexError as e:
            self.editor_window.log_error(f'Tried to add linecut with index out of range:\nIndexError: {e}')
        if update: # Don't update every time a cut is added when 'generate' is used
            self.update()

    def remove_cut(self,which='selected'):
        # which = 'selected', 'all'
        if which=='selected':
            try:
                row = self.cuts_table.currentRow()
                linecut = int(self.cuts_table.item(row,0).text())
                if 'draggable_points' in self.parent.linecuts[self.orientation]['lines'][linecut].keys():
                    self.update_draggable_points(linecut,replot=False)
                self.parent.linecuts[self.orientation]['lines'].pop(linecut)
                self.cuts_table.removeRow(row)
            except Exception as e:
                self.editor_window.log_error(f'Could not remove linecut:\n{type(e).__name__}: {e}', show_popup=True)
        elif which=='all':
            for linecut in self.parent.linecuts[self.orientation]['lines'].keys():
                if 'draggable_points' in self.parent.linecuts[self.orientation]['lines'][linecut].keys():
                    self.update_draggable_points(linecut,replot=False)
            self.parent.linecuts[self.orientation]['lines'] = {}
            self.cuts_table.setRowCount(0)
        self.update()

    def generate_cuts(self):
        # Generate a list of cuts based on the input in the line edit boxes.
        # The input is a string of the form 'start,end,step,offset'.
        inputstring=self.generate_line_edit.text()
        try:
            start=int(inputstring.split(',')[0])
            end=int(inputstring.split(',')[1])
            step=int(inputstring.split(',')[2])
            offset=float(inputstring.split(',')[3])
        except Exception as e:
            self.output_window.setText(f'Could not parse input: {e}')
            return
        if end == -1:
            if self.orientation == 'horizontal':
                end = self.parent.processed_data[1][0,:].shape[0]-1
            elif self.orientation == 'vertical':
                end = self.parent.processed_data[0][:,0].shape[0]-1
        for index in np.arange(start,end+1,step):
            self.add_cut_manually(data_index=index,offset=offset*index,update=False)
        self.update()

    def move_cut(self, direction):
        self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
        try:
            current_row = self.cuts_table.currentRow()
            if direction == 'up' and current_row > 0:
                delta=-1
            elif direction == 'down' and current_row < self.cuts_table.rowCount()-1:
                delta=1
            if delta in [-1,1]:
                current_col = self.cuts_table.currentColumn()
                items = [self.cuts_table.takeItem(current_row, c) for c in range(self.cuts_table.columnCount())]
                if self.orientation in ['horizontal','vertical']:
                    oldSpinBox = self.cuts_table.cellWidget(current_row, 1)
                self.cuts_table.removeRow(current_row)
                new_row = current_row + delta
                self.cuts_table.insertRow(new_row)
                for i, item in enumerate(items):
                    self.cuts_table.setItem(new_row, i, item)
                if self.orientation in ['horizontal','vertical'] and isinstance(oldSpinBox, QtWidgets.QAbstractSpinBox):
                    newSpinBox = QtWidgets.QSpinBox()
                    newSpinBox.setValue(oldSpinBox.value())
                    newSpinBox.setRange(0,oldSpinBox.maximum())
                    newSpinBox.valueChanged[int].connect(lambda: self.cuts_table_edited('index'))
                    self.cuts_table.setCellWidget(new_row, 1, newSpinBox)
                if current_col >= 0:
                    self.cuts_table.setCurrentCell(new_row, current_col)

        except Exception as e:
            pass
        self.cuts_table.itemChanged.connect(self.cuts_table_edited)

    def reorder_cuts(self):
        # Reorder the cuts in the list based on the data index.
        # Not implemented in the GUI since it's super broken; the spin box really affects everything. It will be hard to make it work I think.
        self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
        self.cuts_table.setSortingEnabled(False)
        for row in range(self.cuts_table.rowCount()):
            item = self.cuts_table.item(row, 1)
            if isinstance(item, QtWidgets.QSpinBox):
                oldSpinBox=item
                dummy_box=QtWidgets.QTableWidgetItem(str(oldSpinBox.value()))
                self.cuts_table.setItem(row, 1, dummy_box)

        self.cuts_table.sortItems(1, QtCore.Qt.AscendingOrder)
        for row in range(self.cuts_table.rowCount()):
            item = self.cuts_table.item(row, 1)
            newSpinBox = QtWidgets.QSpinBox()
            newSpinBox.setValue(int(item.text()))
            newSpinBox.setRange(0,oldSpinBox.maximum())
            self.cuts_table.setCellWidget(row, 1, newSpinBox)

        self.cuts_table.setSortingEnabled(True)
        self.cuts_table.itemChanged.connect(self.cuts_table_edited)

    def apply_colormap(self):
        # Apply the colormap to the selected lines in the cuts table.
        # The colormap is applied to the linecut number, not the index.
        self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
        selected_colormap = cm.get_cmap(self.colormap_box.currentText())
        applymethod = self.apply_colormap_to_box.currentText()

        if applymethod == 'All by order':
            lines_to_color = [int(self.cuts_table.item(row,0).text()) for row in range(self.cuts_table.rowCount())]

        elif applymethod == 'Chkd by order':
            lines_to_color = self.get_checked_items(cuts_or_fits='cuts')

        elif applymethod == 'All by ind':
            indexes= [int(self.cuts_table.cellWidget(row,1).value()) for row in range(self.cuts_table.rowCount())]
            lines_to_color = [int(self.cuts_table.item(row,0).text()) for row in range(self.cuts_table.rowCount())]

        elif applymethod == 'Chkd by ind':
            indexes = [int(self.cuts_table.cellWidget(row,1).value()) for row in range(self.cuts_table.rowCount()) 
                       if self.cuts_table.item(row,0).checkState() == QtCore.Qt.Checked]
            lines_to_color = self.get_checked_items(cuts_or_fits='cuts')

        if applymethod in ['All by ind', 'Chkd by ind']:
            # Reorder lines_to_color based on the order of indexes
            sorted_pairs = sorted(zip(indexes, lines_to_color))
            indexes, lines_to_color = zip(*sorted_pairs)
            indexes = list(indexes)
            lines_to_color = list(lines_to_color)

        line_colors = selected_colormap(np.linspace(0.1,0.9,len(lines_to_color)))
        rows = [self.cuts_table.row(self.cuts_table.findItems(str(line), QtCore.Qt.MatchExactly)[0]) for line in lines_to_color]
        
        for i,line in enumerate(lines_to_color):
            self.parent.linecuts[self.orientation]['lines'][line]['linecolor'] = line_colors[i]
            rgbavalue = [int(line_colors[i][0]*255), int(line_colors[i][1]*255), int(line_colors[i][2]*255),int(line_colors[i][3]*255)]
            self.cuts_table.item(rows[i],4).setBackground(QtGui.QColor(*rgbavalue))
            if 'draggable_points' in self.parent.linecuts[self.orientation]['lines'][line].keys():
                self.update_draggable_points(line,replot=True)

        self.cuts_table.itemChanged.connect(self.cuts_table_edited)
        self.update()

    def colormap_type_edited(self):
        self.colormap_box.clear()
        self.colormap_box.addItems(cmaps[self.colormap_type_box.currentText()])

    def change_all_checkstate(self,column,checkstate):
        for row in range(self.cuts_table.rowCount()):
            item = self.cuts_table.item(row, column)
            item.setCheckState(checkstate)
            linecut=int(self.cuts_table.item(row,0).text())
            if column == 0:
                self.parent.linecuts[self.orientation]['lines'][linecut]['checkstate'] = checkstate
            elif column == 5:
                self.parent.linecuts[self.orientation]['lines'][linecut]['fit']['fit_checkstate'] = checkstate
            elif column == 6:
                self.parent.linecuts[self.orientation]['lines'][linecut]['fit']['fit_components_checkstate'] = checkstate
            elif column == 7:
                self.parent.linecuts[self.orientation]['lines'][linecut]['fit']['fit_uncertainty_checkstate'] = checkstate
        self.update()
        
    def open_cuts_table_menu(self,position):
        item=self.cuts_table.currentItem()
        column=self.cuts_table.currentColumn()
        row=self.cuts_table.currentRow()
        if column==4:
            # Choose colour
            menu = QtWidgets.QMenu(self)
            color_action = menu.addAction("Choose Color")

            # Show the menu at the cursor position
            action = menu.exec_(self.cuts_table.viewport().mapToGlobal(position))

            if action == color_action:
                if item:
                    color = QtWidgets.QColorDialog.getColor()
                    if color.isValid():
                        item.setBackground(color)
                        linecut=int(self.cuts_table.item(self.cuts_table.currentRow(),0).text())
                        self.parent.linecuts[self.orientation]['lines'][linecut]['linecolor'] = color.name()
                        self.cuts_table.setCurrentItem(self.cuts_table.item(row,0)) # Otherwise the cell stays blue since it's selected.
                        if 'draggable_points' in self.parent.linecuts[self.orientation]['lines'][linecut].keys():
                            self.update_draggable_points(linecut,replot=True)
                        self.update()
        
        elif column in [0,5,6,7]:
            menu = QtWidgets.QMenu(self)
            
            if column==0:
                check_all_action = menu.addAction("Check all")
                uncheck_all_action = menu.addAction("Uncheck all")

            elif column==5:
                check_all_action = menu.addAction("Show all fits")
                uncheck_all_action = menu.addAction("Hide all fits")

            elif column==6:
                check_all_action = menu.addAction("Show all fit components")
                uncheck_all_action = menu.addAction("Hide all fit components")
            elif column==7:
                check_all_action = menu.addAction("Show all fit errors")
                uncheck_all_action = menu.addAction("Hide all fit errors")

            action = menu.exec_(self.cuts_table.viewport().mapToGlobal(position))
            self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
            try:
                if action == check_all_action:
                    self.change_all_checkstate(column,QtCore.Qt.Checked)
                elif action == uncheck_all_action:
                    self.change_all_checkstate(column,QtCore.Qt.Unchecked)
            except Exception as e:
                self.editor_window.log_error(f'Could not change checkstate in linecut window:\n{type(e).__name__}: {e}')
            self.cuts_table.itemChanged.connect(self.cuts_table_edited)

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
            self.minline=self.axes.axvline(xmin, 0,0.1, color='blue', linestyle='--')
        if xmax != '':
            xmax=float(xmax)
            self.maxline=self.axes.axvline(xmax, 0,0.1, color='red', linestyle='--')
        self.canvas.draw()
    
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

        self.canvas.draw()

    def update_axscale(self,which):
        if which == 'xscale':
            self.parent.linecuts[self.orientation]['xscale'] = self.xscale_box.currentText()
        elif which == 'yscale':
            self.parent.linecuts[self.orientation]['yscale'] = self.yscale_box.currentText()
        self.axes.set_xscale(self.parent.linecuts[self.orientation]['xscale'])
        self.axes.set_yscale(self.parent.linecuts[self.orientation]['yscale'])
        self.canvas.draw()

    def update_legend(self):
        self.parent.linecuts[self.orientation]['legend'] = self.legend_checkbox.isChecked()
        self.update()
  
    def update(self):
        if self.running:
            self.draw_plot()

            fit_lines = self.get_checked_items(cuts_or_fits='fits')
            if len(fit_lines) > 0:
                for line in fit_lines:
                    if 'fit' in self.parent.linecuts[self.orientation]['lines'][line].keys():
                        self.draw_fits(line)

            self.parent.canvas.draw()
            self.show()
               
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
        # If diagonal or circular, setting limits doesn't work; however, one can easily change the range during linecut definition anyway
        try:
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
        except:
            x_forfit = x
            y_forfit = y
        return x_forfit, y_forfit

        # if self.x_forfit[-1]<self.x_forfit[0]:
        #     self.x_forfit=self.x_forfit[::-1]
        #     self.y_forfit=self.y_forfit[::-1]

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
            current_row = self.cuts_table.currentRow()
            line = int(self.cuts_table.item(current_row,0).text())
        else: # We are being passed the line from fit_checked
            # Still need to find the 'current row' to put a checkbox there later
            labels=[int(self.cuts_table.item(row,0).text()) for row in range(self.cuts_table.rowCount())]
            current_row=labels.index(line)
        x,y,z=self.get_line_data(line)
        x_forfit, y_forfit = self.collect_fit_data(x,y)
        function_class = self.fit_class_box.currentText()
        function_name = self.fit_box.currentText()
        inputinfo=self.collect_fit_inputs(function_class,function_name)
        p0=self.collect_init_guess(function_class,function_name)
        
        # Try to do the fit.
        if function_name != 'Statistics':
            if 'stats' in self.parent.linecuts[self.orientation]['lines'][line].keys():
                self.clear_fit(line)
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

                    self.parent.linecuts[self.orientation]['lines'][line]['fit'] = {'fit_result': fit_result,
                                                                                    'xdata': x_forfit,
                                                                                    'ydata': y_forfit,
                                                                                    'fitted_y': y_fit,
                                                                                    'fit_checkstate': QtCore.Qt.Checked,
                                                                                    'fit_components_checkstate': QtCore.Qt.Unchecked,
                                                                                    'fit_uncertainty_checkstate': QtCore.Qt.Checked}

                    # Add a checkbox to the table now a fit exists.
                    self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)

                    plot_fit_item = QtWidgets.QTableWidgetItem('')
                    plot_fit_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                                        QtCore.Qt.ItemIsEnabled | 
                                        QtCore.Qt.ItemIsUserCheckable)
                    plot_fit_item.setCheckState(QtCore.Qt.Checked)
                    self.cuts_table.setItem(current_row,5,plot_fit_item)

                    fit_components_item = QtWidgets.QTableWidgetItem('')
                    fit_components_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                                                QtCore.Qt.ItemIsEnabled | 
                                                QtCore.Qt.ItemIsUserCheckable)
                    fit_components_item.setCheckState(QtCore.Qt.Unchecked)
                    self.cuts_table.setItem(current_row,6,fit_components_item)

                    fit_uncertainty_item = QtWidgets.QTableWidgetItem('')
                    fit_uncertainty_item.setFlags(QtCore.Qt.ItemIsSelectable |
                                                QtCore.Qt.ItemIsEnabled | 
                                                QtCore.Qt.ItemIsUserCheckable)
                    fit_uncertainty_item.setCheckState(QtCore.Qt.Checked)
                    self.cuts_table.setItem(current_row,7,fit_uncertainty_item)

                    self.cuts_table.itemChanged.connect(self.cuts_table_edited)
                    success=True

            except Exception as e:
                self.output_window.setText(f'Curve could not be fitted:\n{type(e).__name__}: {e}')
                self.editor_window.log_error(f'Curve could not be fitted:\n{type(e).__name__}: {e}')
                if multilinefit:
                    return e
        
        else:
            if 'fit' in self.parent.linecuts[self.orientation]['lines'][line].keys():
                self.clear_fit(line)
            self.parent.linecuts[self.orientation]['lines'][line]['stats'] = fits.fit_data(function_class=function_class, 
                                                                                           function_name=function_name,
                                                    xdata=x_forfit,ydata=y_forfit, p0=p0, inputinfo=inputinfo)
            success=True
        
        if success and not multilinefit:
            self.print_parameters(line)
            self.update()

    def fit_checked(self):
        # Fit all checked items in the table.
        fit_lines = self.get_checked_items(cuts_or_fits='cuts')
        minilog=[]
        for line in fit_lines:
            error=self.start_fitting(line,multilinefit=True)
            if error:
                minilog.append(f'Linecut {line} could not be fitted: {error}')
        if len(minilog)>0:
            error_message = 'The following errors occurred while fitting:\n\n' + '\n\n'.join(minilog)
            self.ew = ErrorWindow(error_message)
        if not error:
            self.print_parameters(line)
        self.update()

    def print_parameters(self,line):
        self.output_window.clear()
        if 'stats' in self.parent.linecuts[self.orientation]['lines'][line].keys():
            text='Statistics:\n'
            for key in self.parent.linecuts[self.orientation]['lines'][line]['stats'].keys():
                text+=f'{key}: {self.parent.linecuts[self.orientation]['lines'][line]['stats'][key]}\n'
            self.output_window.setText(text)
        else:
            try:
                self.output_window.setText(self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result'].fit_report())

            except Exception as e:
                self.output_window.setText('Could not print fit parameters:', e)

    def get_line_data(self,line):
        if self.orientation == 'horizontal':
            x = self.parent.processed_data[0][:,self.parent.linecuts[self.orientation]['lines'][line]['data_index']]
            y = self.parent.processed_data[2][:,self.parent.linecuts[self.orientation]['lines'][line]['data_index']]
            z = self.parent.processed_data[1][0,self.parent.linecuts[self.orientation]['lines'][line]['data_index']]
            # Confusingly enough, z here is just the value of the y axis of the parent plot/data where the cut is taken
        
        elif self.orientation == 'vertical':
            x = self.parent.processed_data[1][self.parent.linecuts[self.orientation]['lines'][line]['data_index'],:]
            y = self.parent.processed_data[2][self.parent.linecuts[self.orientation]['lines'][line]['data_index'],:]
            z = self.parent.processed_data[0][self.parent.linecuts[self.orientation]['lines'][line]['data_index'],0]
        
        elif self.orientation in ['diagonal', 'circular']:
            x0 = self.parent.linecuts[self.orientation]['lines'][line]['draggable_points'][0].x
            y0 = self.parent.linecuts[self.orientation]['lines'][line]['draggable_points'][0].y
            x1 = self.parent.linecuts[self.orientation]['lines'][line]['draggable_points'][1].x
            y1 = self.parent.linecuts[self.orientation]['lines'][line]['draggable_points'][1].y
            l_x, l_y = self.parent.processed_data[0].shape
            x_min = np.amin(self.parent.processed_data[0][:,0])
            x_max = np.amax(self.parent.processed_data[0][:,0])
            y_min = np.amin(self.parent.processed_data[1][0,:])
            y_max = np.amax(self.parent.processed_data[1][0,:])
            i_x0 = (l_x-1)*(x0-x_min)/(x_max-x_min)
            i_y0 = (l_y-1)*(y0-y_min)/(y_max-y_min)
            i_x1 = (l_x-1)*(x1-x_min)/(x_max-x_min)
            i_y1 = (l_y-1)*(y1-y_min)/(y_max-y_min)
            if self.orientation == 'diagonal':
                n = int(np.sqrt((i_x1-i_x0)**2+(i_y1-i_y0)**2))
                x_diag = np.linspace(i_x0, i_x1, n), 
                y_diag = np.linspace(i_y0, i_y1, n)
                y = map_coordinates(self.parent.processed_data[-1], 
                                        np.vstack((x_diag, y_diag)))
                if self.plot_against_box.currentText().split(':')[0] == 'X':
                    x = map_coordinates(self.parent.processed_data[0],
                                        np.vstack((x_diag, y_diag)))
                elif self.plot_against_box.currentText().split(':')[0] == 'Y':
                    x = map_coordinates(self.parent.processed_data[1],
                                        np.vstack((x_diag, y_diag)))
                else:
                    x_dummy=map_coordinates(self.parent.processed_data[0],
                                        np.vstack((x_diag, y_diag)))
                    y_dummy=map_coordinates(self.parent.processed_data[1],
                                        np.vstack((x_diag, y_diag)))
                    x = np.sqrt((x_dummy-x_dummy[0])**2+(y_dummy-y_dummy[0])**2)

            if self.orientation == 'circular':
                n = int(8*np.sqrt((i_x0-i_x1)**2+(i_y0-i_y1)**2))
                theta = np.linspace(0, 2*np.pi, n)
                i_x_circ = i_x0+(i_x1-i_x0)*np.cos(theta) 
                i_y_circ = i_y0+(i_y1-i_y0)*np.sin(theta)
                y = map_coordinates(self.parent.processed_data[-1], 
                                        np.vstack((i_x_circ, i_y_circ)))
                x = theta
            z=0
        return (x,y,z)

    def draw_lines(self,x,y,line):
        offset = self.parent.linecuts[self.orientation]['lines'][line]['offset']
        size=self.parent.linecuts[self.orientation]['linesize']
        if self.orientation in ['horizontal', 'vertical']:
            label = f'{self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value']:.5g}'
        else:
            points= self.parent.linecuts[self.orientation]['lines'][line]['points']
            label = (f'({points[0][0]:.5g}, {points[0][1]:.5g}) : '
                    f'({points[1][0]:.5g}, {points[1][1]:.5g})')
        self.axes.plot(x, y+offset, self.parent.linecuts[self.orientation]['linestyle'],
                    linewidth=size,
                    markersize=size,
                    color=self.parent.linecuts[self.orientation]['lines'][line]['linecolor'],
                    label= label)
    
    def draw_plot(self):
        checked_editor_items = self.editor_window.get_checked_items()
        parent_item=None
        for item in checked_editor_items:
            if item.data == self.parent:
                parent_item = item
                break

        self.running = True
        self.figure.clear()

        self.axes = self.figure.add_subplot(111)
        self.axes.set_xscale(self.parent.linecuts[self.orientation]['xscale'])
        self.axes.set_yscale(self.parent.linecuts[self.orientation]['yscale'])
        lines = self.get_checked_items()

        if self.orientation == 'horizontal':
            self.xlabel = self.parent.settings['xlabel']
            self.title = f'Cuts at fixed {self.parent.settings['ylabel']}'
            for line in lines:
                x,y,z= self.get_line_data(line)
                self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value'] = z
                self.draw_lines(x, y, line)
            if self.editor_window.show_linecut_markers and parent_item is not None:
                self.editor_window.reinstate_markers(parent_item,self.orientation)

        elif self.orientation == 'vertical':
            self.xlabel = self.parent.settings['ylabel']
            self.title = f'Cuts at fixed {self.parent.settings['xlabel']}'
            for line in lines:
                x,y,z= self.get_line_data(line)
                self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value'] = z
                self.draw_lines(x, y, line)
            if self.editor_window.show_linecut_markers and parent_item is not None:
                self.editor_window.reinstate_markers(parent_item,self.orientation)

        elif self.orientation == 'diagonal' or self.orientation == 'circular':
            for line in lines:
                x,y,z= self.get_line_data(line)
                self.draw_lines(x, y, line)
                try:
                    if self.orientation == 'diagonal':
                        if self.plot_against_box.currentText().split(':')[0] == 'X':
                            self.xlabel = self.parent.settings['xlabel']
                        elif self.plot_against_box.currentText().split(':')[0] == 'Y':
                            self.xlabel = self.parent.settings['ylabel']
                        else:
                            #self.xlabel = '$\sqrt{(x-x_0)^2+(y-y_0)^2}$'
                            self.xlabel = 'Vector length'
                        #self.title = f'({x0:5g},{y0:5g}) : ({x1:5g},{y1:5g})'
                    elif self.orientation == 'circular':
                        self.xlabel = 'Angle (rad)'
                except Exception as e:
                    self.editor_window.log_error(f'Could not plot diagonal linecut:\n{type(e).__name__}: {e}', 
                                                show_popup=True)

        self.ylabel = self.parent.settings['clabel']
        self.cursor = Cursor(self.axes, useblit=True, color='grey', linewidth=0.5)
        self.axes.set_xlabel(self.xlabel, size='x-large')
        self.axes.set_ylabel(self.ylabel, size='x-large')
        self.axes.tick_params(labelsize='x-large', color=rcParams['axes.edgecolor'])
        if hasattr(self,'title'):
            self.axes.set_title(self.title, size='x-large')
        if self.parent.linecuts[self.orientation]['legend']:
            self.axes.legend()
        self.limits_edited()
        self.canvas.draw()
        self.parent.canvas.draw()
              
    def draw_fits(self,line):
        try:
            offset=self.parent.linecuts[self.orientation]['lines'][line]['offset']
            fit_result=self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result']
            x_forfit=self.parent.linecuts[self.orientation]['lines'][line]['fit']['xdata']
            y_fit=fit_result.best_fit+offset
            self.axes.plot(x_forfit, y_fit, 'k--',
                linewidth=1.5)
            if self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_uncertainty_checkstate']==QtCore.Qt.Checked:
                uncertainty=fit_result.eval_uncertainty()
                self.axes.fill_between(x_forfit, y_fit-uncertainty, y_fit+uncertainty,
                                        color='grey', alpha=0.5, linewidth=0)
            if self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_components_checkstate']==QtCore.Qt.Checked:
                fit_components=fit_result.eval_components()
                if self.colormap_box.currentText() == 'viridis':
                    selected_colormap = cm.get_cmap('plasma')
                elif self.colormap_box.currentText() == 'plasma':
                    selected_colormap = cm.get_cmap('viridis')
                line_colors = selected_colormap(np.linspace(0.1,0.9,len(fit_components.keys())))
                for i,key in enumerate(fit_components.keys()):
                    self.axes.plot(x_forfit, fit_components[key]+offset, '--', color=line_colors[i],alpha=0.75, linewidth=1.5)
        except Exception as e:
            self.output_window.setText(f'Could not plot fit: {e}')
        self.canvas.draw()

    def autoscale_axes(self):
        self.axes.autoscale()
        self.canvas.draw()

    def closeEvent(self, event):
        if hasattr(self.parent,'vertmarkers') and len(self.parent.vertmarkers)>0:
            for marker in self.parent.vertmarkers:
                try:
                    marker.remove()
                    del marker
                except NotImplementedError:
                    pass
            del self.parent.vertmarkers
        if hasattr(self.parent,'horimarkers') and len(self.parent.horimarkers)>0:
            for marker in self.parent.horimarkers:
                try:
                    marker.remove()
                    del marker
                except NotImplementedError:
                    pass
            del self.parent.horimarkers
        # self.parent.hide_linecuts()
        self.running = False
        
    def save_data(self):
        # Save only the plotted data to json or csv. The complete dictionary is always saved with save session from the main window.
        lines= self.get_checked_items(cuts_or_fits='cuts')
        if len(lines) != 0:
            fit_lines = self.get_checked_items(cuts_or_fits='fits')

            formats = 'JSON (*.json);;Comma Separated Value (*.csv)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save Data As','',formats)
            try:
                data={}
                for line in lines:
                    x,y,z=self.get_line_data(line)
                    data[f'linecut{line}_X'] = x.tolist()
                    data[f'linecut{line}_Y'] = y.tolist()
                for line in fit_lines:
                    fit_result=self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result']
                    data[f'fit{line}_X'] = self.parent.linecuts[self.orientation]['lines'][line]['fit']['xdata'].tolist()
                    data[f'fit{line}_Y'] = fit_result.best_fit.tolist()
                    data[f'fit{line}_Y_err'] = fit_result.eval_uncertainty().tolist()
                    fit_components=fit_result.eval_components()
                    for key in fit_components.keys():
                        data[f'fit{line}_{key}Y'] = fit_components[key].tolist()

                if extension=='JSON (*.json)':
                    with open(filename, 'w', encoding='utf-8') as f:
                        jsondump(data, f, ensure_ascii=False,indent=4)
                elif extension=='Comma Separated Value (*.csv)':
                    with open(filename, 'w', newline='') as f:
                        writer = csvwriter(f)
                        writer.writerow([key for key in data])
                        lengths = [len(data[key]) for key in data.keys()]
                        for i in range(np.max(lengths)):
                            row = []
                            for param in data:
                                try:
                                    row.append(data[param][i])
                                except IndexError:
                                    row.append('')
                            writer.writerow(row)
            except Exception as e:
                self.editor_window.log_error(f'Could not save data:\n{type(e).__name__}: {e}', show_popup=True)

    def save_fit_result(self):
        current_row = self.cuts_table.currentRow()
        line = int(self.cuts_table.item(current_row,0).text())

        # Fits get saved in the lmfit format.
        if 'fit' in self.parent.linecuts[self.orientation]['lines'][line].keys():
            fit_result = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result']
            formats = 'lmfit Model Result (*.sav)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Fit Result','', formats)
            save_modelresult(fit_result,filename)

        #Stats can simply be saved in a json
        elif 'stats' in self.parent.linecuts[self.orientation]['lines'][line].keys():
            formats = 'JSON (*.json)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Statistics','', formats)
            export_dict={'data_name':self.parent.label,
                         'linecut_orientation':self.orientation}
            if self.orientation in ['horizontal', 'vertical']:
                export_dict['linecut_index']=int(self.parent.linecuts[self.orientation]['lines'][line]['data_index'])
                export_dict['linecut_axis_value']=float(self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value'])
            for key in self.parent.linecuts[self.orientation]['lines'][line]['stats'].keys():
                if isinstance(self.parent.linecuts[self.orientation]['lines'][line]['stats'][key],np.ndarray):
                    export_dict[key] = self.parent.linecuts[self.orientation]['lines'][line]['stats'][key].tolist()
                else:
                    export_dict[key] = self.parent.linecuts[self.orientation]['lines'][line]['stats'][key]
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    jsondump(export_dict, f, ensure_ascii=False,indent=4)
            except Exception as e:
                self.editor_window.log_error(f'Could not save statistics:\n{type(e).__name__}: {e}', show_popup=True)

    def save_all_fits(self):
        # Can save _either_ fits or stats, and decide which to do based on whether the current line has a fit or stats.
        current_line = int(self.cuts_table.item(self.cuts_table.currentRow(),0).text())
        if 'fit' in self.parent.linecuts[self.orientation]['lines'][current_line].keys():
            fit_lines = self.get_checked_items(cuts_or_fits='fits')

            formats = 'lmfit Model Result (*.sav)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Fit Result: Select base name','', formats)
            for line in fit_lines:
                fit_result = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result']
                save_modelresult(fit_result,filename.replace('.sav',f'_{line}.sav'))
        
        elif 'stats' in self.parent.linecuts[self.orientation]['lines'][current_line].keys():
            # We can put all the stats in a single json.
            stat_lines=[]
            for line in self.parent.linecuts[self.orientation]['lines'].keys():
                if 'stats' in self.parent.linecuts[self.orientation]['lines'][line].keys():
                    stat_lines.append(line)

            formats = 'JSON (*.json)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Statistics','', formats)
            export_dict={'data_name':self.parent.label,
                        'linecut_orientation':self.orientation,
                        'linecut_stats':{}}
            for line in stat_lines:
                export_dict['linecut_stats'][line] = {}
                if self.orientation in ['horizontal', 'vertical']:
                    export_dict['linecut_stats'][line]['linecut_index']=int(self.parent.linecuts[self.orientation]['lines'][line]['data_index'])
                    export_dict['linecut_stats'][line]['linecut_axis_value']=float(self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value'])
                for key in self.parent.linecuts[self.orientation]['lines'][line]['stats'].keys():
                    if isinstance(self.parent.linecuts[self.orientation]['lines'][line]['stats'][key],np.ndarray):
                        export_dict['linecut_stats'][line][key] = self.parent.linecuts[self.orientation]['lines'][line]['stats'][key].tolist()
                    else:
                        export_dict['linecut_stats'][line][key] = self.parent.linecuts[self.orientation]['lines'][line]['stats'][key]
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    jsondump(export_dict, f, ensure_ascii=False,indent=4)
            except Exception as e:
                self.editor_window.log_error(f'Could not save statistics:\n{type(e).__name__}: {e}', show_popup=True)
        else:
            self.editor_window.log_error('First select a linecut with either a fit or statistics. '
                                        'Either the fits or statistics for all linecuts will be saved, based on that.',
                                        show_popup=True)


    def clear_fit(self,line='manual'):
        self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
        if line=='manual':
            manual=True
            row = self.cuts_table.currentRow()
            line = int(self.cuts_table.item(row,0).text())
        else:
            manual=False
            for row in range(self.cuts_table.rowCount()):
                if int(self.cuts_table.item(row,0).text())==line:
                    break
        
        if 'fit' in self.parent.linecuts[self.orientation]['lines'][line].keys():
            self.parent.linecuts[self.orientation]['lines'][line].pop('fit')
            self.cuts_table.setItem(row,5,QtWidgets.QTableWidgetItem(''))
            self.cuts_table.setItem(row,6,QtWidgets.QTableWidgetItem(''))
            self.cuts_table.setItem(row,7,QtWidgets.QTableWidgetItem(''))
            if manual:
                self.update()

        # should never be both, but use 'if' just in case
        if 'stats' in self.parent.linecuts[self.orientation]['lines'][line].keys():
            self.parent.linecuts[self.orientation]['lines'][line].pop('stats')

        if manual:
            fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]
            self.output_window.setText('Information about selected fit type:\n'+
                                   fit_function['description'])
            
        self.cuts_table.itemChanged.connect(self.cuts_table_edited)

    def clear_all_fits(self):
        try:
            for line in self.parent.linecuts[self.orientation]['lines'].keys():
                self.clear_fit(line)
        except Exception as e:
            self.editor_window.log_error(f'Could not clear all fits:\n{type(e).__name__}: {e}', show_popup=True)

        fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]
        self.output_window.setText('Information about selected fit type:\n'+fit_function['description'])
        self.update()

    def save_parameters_dependency(self):
        # Save the parameters of all fits in a table. The first column is the x-axis value, and the rest are the parameters and their errors.
        # First, for actual fits, then statistics below. Decide between fits or stats based on current linecut
        current_line = int(self.cuts_table.item(self.cuts_table.currentRow(),0).text())
        if 'fit' in self.parent.linecuts[self.orientation]['lines'][current_line].keys():
            try:
                fit_lines = self.get_checked_items(cuts_or_fits='fits')
                first_result = self.parent.linecuts[self.orientation]['lines'][fit_lines[0]]['fit']['fit_result']
                if self.orientation in ['horizontal', 'vertical']:
                    data=np.zeros((len(fit_lines),len(first_result.params.keys())*2+1))
                    for i,line in enumerate(fit_lines):
                        data[i,0] = self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value']
                        for j,param in enumerate(first_result.params.keys()):
                            data[i,j+1] = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result'].params[param].value
                        last_column=j+2
                        for j,param in enumerate(first_result.params.keys()):
                            data[i,j+last_column] = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result'].params[param].stderr
                    header='X\t'+'\t'.join(first_result.params.keys())
                    for param in first_result.params.keys():
                        header += '\t'+param+'_error'
                elif self.orientation in ['diagonal', 'circular']:
                    data=np.zeros((len(fit_lines),len(first_result.params.keys())*2+5))
                    for i,line in enumerate(fit_lines):
                        data[i,0] = line
                        data[i,1] = self.parent.linecuts[self.orientation]['lines'][line]['points'][0][0]
                        data[i,2] = self.parent.linecuts[self.orientation]['lines'][line]['points'][0][1]
                        data[i,3] = self.parent.linecuts[self.orientation]['lines'][line]['points'][1][0]
                        data[i,4] = self.parent.linecuts[self.orientation]['lines'][line]['points'][1][1]
                        for j,param in enumerate(first_result.params.keys()):
                            data[i,j+5] = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result'].params[param].value
                        last_column=j+6
                        for j,param in enumerate(first_result.params.keys()):
                            data[i,j+last_column] = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result'].params[param].stderr
                    header='index\tX_1\tY_1\tX_2\tY_2\t'+'\t'.join(first_result.params.keys())
                    for param in first_result.params.keys():
                        header += '\t'+param+'_error'
                success=True
            except Exception as e:
                self.editor_window.log_error(f'Could not compile parameter dependency array:\n{type(e).__name__}: {e}', 
                                            show_popup=True)
                success=False

        elif 'stats' in self.parent.linecuts[self.orientation]['lines'][current_line].keys():
            try:
                stat_lines=[]
                for line in self.parent.linecuts[self.orientation]['lines'].keys():
                    if 'stats' in self.parent.linecuts[self.orientation]['lines'][line].keys():
                        stat_lines.append(line)

                first_result = self.parent.linecuts[self.orientation]['lines'][stat_lines[0]]['stats']
                params = [key for key in first_result.keys() if key not in ['xdata','ydata']]
                if 'percentiles' in params:
                    if len(params)>2:
                        raise Exception('If saving percentiles as a parameter dependency, it can _only_ be percentiles. '
                                        'The result must be a rectangular array.')
                    else:
                        percentiles_array=np.zeros((len(stat_lines),len(first_result['percentiles'])))
                        if self.orientation in ['horizontal', 'vertical']:
                            cut_axis_array=np.zeros_like(percentiles_array)
                        elif self.orientation in ['diagonal', 'circular']:
                            point1xarray=np.zeros_like(percentiles_array)
                            point1yarray=np.zeros_like(percentiles_array)
                            point2xarray=np.zeros_like(percentiles_array)
                            point2yarray=np.zeros_like(percentiles_array)
                            indexarray=np.zeros_like(percentiles_array)
                        percentile_values_array=np.zeros_like(percentiles_array)

                        for i,line in enumerate(stat_lines):
                            percentile_values_array[i,:]=self.parent.linecuts[self.orientation]['lines'][line]['stats']['percentiles']
                            for j,value in enumerate(first_result['percentiles']):
                                percentiles_array[i,j] = self.parent.linecuts[self.orientation]['lines'][line]['stats']['percentile'][j]
                                if self.orientation in ['horizontal', 'vertical']:
                                    cut_axis_array[i,j]=self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value']
                                elif self.orientation in ['diagonal', 'circular']:
                                    indexarray[i,j] = line
                                    point1xarray[i,j] = self.parent.linecuts[self.orientation]['lines'][line]['points'][0][0]
                                    point1yarray[i,j] = self.parent.linecuts[self.orientation]['lines'][line]['points'][0][1]
                                    point2xarray[i,j] = self.parent.linecuts[self.orientation]['lines'][line]['points'][1][0]
                                    point2yarray[i,j] = self.parent.linecuts[self.orientation]['lines'][line]['points'][1][1]
                        if self.orientation in ['horizontal', 'vertical']:
                            data=np.column_stack((cut_axis_array.flatten(), percentile_values_array.flatten(), percentiles_array.flatten()))
                            header='X\tpercentiles\tpercentile'
                        elif self.orientation in ['diagonal', 'circular']:
                            data=np.column_stack((indexarray.flatten(),point1xarray.flatten(), point1yarray.flatten(), point2xarray.flatten(), point2yarray.flatten(), percentile_values_array.flatten(), percentiles_array.flatten()))
                            header='index\tX_1\tY_1\tX_2\tY_2\tpercentiles\tpercentile'

                elif 'autocorrelation' in params or 'autocorrelation_norm' in params:
                    if len(params)>1:
                        raise Exception('If saving one of the autocorrelation fuctions as a parameter dependency, '
                                        'it can _only_ be that function. The result must be a rectangular array.')
                    elif self.orientation in ['horizontal', 'vertical']:
                        name=params[0]
                        autocorrelation_array=np.zeros((len(stat_lines),len(first_result[name])))
                        cut_axis_array=np.zeros_like(autocorrelation_array)
                        sweep_axis_array=np.zeros_like(autocorrelation_array)

                        for i,line in enumerate(stat_lines):
                            sweep_axis_array[i,:]=self.parent.linecuts[self.orientation]['lines'][line]['stats']['xdata']
                            cut_value = self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value']
                            for j,value in enumerate(first_result[name]):
                                autocorrelation_array[i,j] = self.parent.linecuts[self.orientation]['lines'][line]['stats'][name][j]
                                cut_axis_array[i,j] = cut_value
                        data=np.column_stack((cut_axis_array.flatten(), sweep_axis_array.flatten(), autocorrelation_array.flatten()))
                        header='X\tY\tautocorrelation'
                        
                    elif self.orientation in ['diagonal', 'circular']:
                        raise Exception('Generating a parameter dependency for autocorrelations along diagonal linecuts is not currently supported, '
                                    'since in general the arrays will not be rectangular. You can instead use Save All Fits which anyway puts all '
                                    'the arrays into a single json.')
                else:
                    if self.orientation in ['horizontal', 'vertical']:
                        data=np.zeros((len(stat_lines),len(params)+1)) # beccause we will exclude the x and y data that is present in stats dictinoaries
                        for i,line in enumerate(stat_lines):
                            data[i,0] = self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value']
                            for j,param in enumerate(params):
                                if param not in ['xdata','ydata']:
                                    data[i,j+1] = self.parent.linecuts[self.orientation]['lines'][line]['stats'][param]
                        header='X\t'+'\t'.join(params)
                    elif self.orientation in ['diagonal', 'circular']:
                        data=np.zeros((len(stat_lines),len(params)+5))
                        for i,line in enumerate(stat_lines):
                            data[i,0] = line
                            data[i,1] = self.parent.linecuts[self.orientation]['lines'][line]['points'][0][0]
                            data[i,2] = self.parent.linecuts[self.orientation]['lines'][line]['points'][0][1]
                            data[i,3] = self.parent.linecuts[self.orientation]['lines'][line]['points'][1][0]
                            data[i,4] = self.parent.linecuts[self.orientation]['lines'][line]['points'][1][1]
                            for j,param in enumerate(params):
                                if param not in ['xdata','ydata']:
                                    data[i,j+4] = self.parent.linecuts[self.orientation]['lines'][line]['stats'][param]
                        header='index\tX_1\tY_1\tX_2\tY_2\t'+'\t'.join(params)

                success=True

            except Exception as e:
                self.editor_window.log_error(f'Could not compile statistics array:\n{type(e).__name__}: {e}',
                                            show_popup=True)
                success=False

        if success:
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save dependency of fitted parameters/stats','', 'numpy dat file (*.dat)')
            if filename:
                np.savetxt(filename, data, delimiter='\t', header=header, fmt='%s')
                try:
                    self.editor_window.open_files([filename],overrideautocheck=True)
                except Exception as e:
                    self.editor_window.log_error(f'Fit dependency was saved at {filename}, '
                                                 f'but could not be opened in the main window:\n{type(e).__name__}: {e}',
                                                 show_popup=True)

    def save_image(self):
        formats = 'Portable Network Graphic (*.png);;Adobe Acrobat (*.pdf)'
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Figure As', '', formats)
        if filename:
            if DARK_THEME and qdarkstyle_imported:
                rcParams_to_light_theme()
                self.update()
            self.figure.savefig(filename)
            if DARK_THEME and qdarkstyle_imported:
                rcParams_to_dark_theme()
                self.update()
    
    def copy_image(self):
        self.cursor.horizOn = False
        self.cursor.vertOn = False            
        self.canvas.draw()
        if DARK_THEME and qdarkstyle_imported:
            rcParams_to_light_theme()
            self.parent.update()           
        buf = io.BytesIO()
        self.figure.savefig(buf, dpi=300, transparent=True, bbox_inches='tight')
        QtWidgets.QApplication.clipboard().setImage(QtGui.QImage.fromData(buf.getvalue()))
        buf.close()
        self.cursor.horizOn = True
        self.cursor.vertOn = True
        self.canvas.draw()
        if DARK_THEME and qdarkstyle_imported:
            rcParams_to_dark_theme()
            self.update()

    def copy_cuts_table_to_clipboard(self):
        # Copy the cuts table to clipboard as formatted text
        row_count = self.cuts_table.rowCount()
        col_count = 5 # i.e. only interesting ones self.cuts_table.columnCount()
        headers = [self.cuts_table.horizontalHeaderItem(col).text() for col in range(col_count)]
        lines = ['\t'.join(headers)]
        for row in range(row_count):
            row_items = []
            for col in range(col_count):
                item = self.cuts_table.item(row, col)
                if item is not None:
                    if col == 4:
                        text = item.background().color().name()
                    else:
                        text = item.text()
                    # # Add checkmark for checkable columns
                    if col == 0:
                        if item.checkState() == QtCore.Qt.Checked:
                            text = '✔ ' + text
                        elif item.checkState() == QtCore.Qt.Unchecked:
                            text = '✘ ' + text
                else:
                    # For cell widgets (e.g., spinboxes)
                    widget = self.cuts_table.cellWidget(row, col)
                    if isinstance(widget, QtWidgets.QSpinBox):
                        text = str(widget.value())
                    else:
                        text = ''
                row_items.append(text)
            lines.append('\t'.join(row_items))
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText('\n'.join(lines))
            
    def mouse_scroll_canvas(self, event):
        if event.inaxes:

            scale=1.2
            scale_factor = np.power(scale, -event.step)

            if any([scale != 'linear' for scale in [self.axes.get_xscale(), self.axes.get_yscale()]]):
                x = event.x
                y = event.y
                #convert pixels to axes
                tranP2A = event.inaxes.transAxes.inverted().transform
                #convert axes to data limits
                tranA2D= event.inaxes.transLimits.inverted().transform
                #convert the scale (for log plots)
                tranSclA2D = event.inaxes.transScale.inverted().transform
                #x,y position of the mouse in range (0,1)
                xa,ya = tranP2A((x,y))
                newxlims=[xa - xa*scale_factor, xa + (1-xa)*scale_factor]
                newylims=[ya - ya*scale_factor, ya + (1-ya)*scale_factor]
                new_xlim0,new_ylim0 = tranSclA2D(tranA2D((newxlims[0],newxlims[0])))
                new_xlim1,new_ylim1 = tranSclA2D(tranA2D((newylims[1],newylims[1])))
                if QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
                    self.axes.set_xlim([new_xlim0, new_xlim1])
                elif QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
                    self.axes.set_ylim([new_ylim0, new_ylim1])
                else:
                    self.axes.set_xlim([new_xlim0, new_xlim1])
                    self.axes.set_ylim([new_ylim0, new_ylim1])
            else:
                #Old method. renders slightly faster, but doesn't work well with log scale.
                xdata = event.xdata
                ydata = event.ydata
                x_left = xdata - event.inaxes.get_xlim()[0]
                x_right = event.inaxes.get_xlim()[1] - xdata
                y_top = ydata - event.inaxes.get_ylim()[0]
                y_bottom = event.inaxes.get_ylim()[1] - ydata
                newxlims=[xdata - x_left * scale_factor, xdata + x_right * scale_factor]
                newylims=[ydata - y_top * scale_factor, ydata + y_bottom * scale_factor]
                if QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
                    self.axes.set_xlim(newxlims)
                elif QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
                    self.axes.set_ylim(newylims)
                else:
                    self.axes.set_xlim(newxlims)
                    self.axes.set_ylim(newylims)

            event.inaxes.figure.canvas.draw()
            # Update toolbar so back/forward buttons work
            fig = event.inaxes.get_figure()
            fig.canvas.toolbar.push_current()

    def mouse_click_canvas(self, event):
        if self.navi_toolbar.mode == '': # If not using the navigation toolbar tools
            if event.inaxes and event.button == 1:
                current_row = self.cuts_table.currentRow()
                # Get the x data for the linecut
                x,y,z=self.get_line_data(int(self.cuts_table.item(current_row,0).text()))
                # Snap to data.
                index=(np.abs(x-event.xdata)).argmin()
                x_value = x[index]
                if self.xmin_box.text() == '':
                    self.xmin_box.setText(str(x_value))
                elif self.xmax_box.text() == '':
                    self.xmax_box.setText(str(x_value))
                else:
                    if np.abs(float(self.xmin_box.text())-float(x_value)) < np.abs(float(self.xmax_box.text())-float(x_value)):
                        self.xmin_box.setText(str(x_value))
                    else:
                        self.xmax_box.setText(str(x_value))
                self.limits_edited()

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
            self.update()


class StatsWindow(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__()
        # The parent is the DATA object.
        self.parent = parent
        self.resize(600,600)
        self.running = True

        self.setWindowTitle(f'Statistics for {self.parent.label}')
        statsdict=self.calculate_stats()
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setColumnCount(2)
        self.tree_widget.setHeaderLabels(["Name", "Value"])
        self.populate_tree(statsdict)
        self.main_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addWidget(self.tree_widget)
        self.setLayout(self.main_layout)

    def calculate_stats(self):
        if self.parent.filepath=='mixed_internal_data':
            data=self.parent.dataset2d.processed_data[-1]
        else:
            data=self.parent.processed_data[-1]
        statsdict={'mean':np.mean(data),
                   'std':np.std(data),
                    'variance':np.var(data),
                   'min':np.min(data),
                   'max':np.max(data),
                   'range':np.max(data)-np.min(data),
                   'median':np.median(data),
                   'percentiles':{}}
        percentiles=np.percentile(data,[1,5,10,25,50,75,90,95,99])
        for i,percentile in enumerate([1,5,10,25,50,75,90,95,99]):
            statsdict['percentiles'][f'{percentile}%'] = percentiles[i]
        
        return statsdict
    
    def populate_tree(self, metadata, parent_item=None):
        """
        Recursively populate the QTreeWidget with nested dictionary data.
        """
        if parent_item is None:
            parent_item = self.tree_widget

        for key, value in metadata.items():
            if isinstance(value, list):  # If the value is a list, create a parent node
                item = QtWidgets.QTreeWidgetItem(parent_item, [str(key)])
                for i, sub_value in enumerate(value):
                    if isinstance(sub_value, dict):
                        sub_item = QtWidgets.QTreeWidgetItem(item, [str(i)])
                        self.populate_tree(sub_value, sub_item)
                    else:
                        sub_item = QtWidgets.QTreeWidgetItem(item, [str(i), str(sub_value)])

            elif isinstance(value, dict):  # If the value is a dictionary, create a parent node
                item = QtWidgets.QTreeWidgetItem(parent_item, [str(key)])
                self.populate_tree(value, item)  # Recursively populate the child items
            else:  # If the value is not a dictionary, create a leaf node
                item = QtWidgets.QTreeWidgetItem(parent_item, [str(key), str(value)])

class MetadataWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowTitle(f"Metadata for {parent.label}")
        self.resize(600,600)
        self.parent = parent
        
        self.layout = QtWidgets.QVBoxLayout()
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setColumnCount(2)
        header_view = self.tree_widget.header()
        header_view.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header_view.setStretchLastSection(False)
        self.tree_widget.setHeaderLabels(["Key", "Value"])
        self.populate_tree(self.parent.meta)
        
        self.layout.addWidget(self.tree_widget)
        self.setLayout(self.layout)


    def populate_tree(self, metadata, parent_item=None):
        """
        Recursively populate the QTreeWidget with nested dictionary data.
        """
        if parent_item is None:
            parent_item = self.tree_widget

        for key, value in metadata.items():
            if isinstance(value, list):  # If the value is a list, create a parent node
                item = QtWidgets.QTreeWidgetItem(parent_item, [str(key)])
                for i, sub_value in enumerate(value):
                    if isinstance(sub_value, dict):
                        sub_item = QtWidgets.QTreeWidgetItem(item, [str(i)])
                        self.populate_tree(sub_value, sub_item)
                    else:
                        sub_item = QtWidgets.QTreeWidgetItem(item, [str(i), str(sub_value)])

            elif isinstance(value, dict):  # If the value is a dictionary, create a parent node
                item = QtWidgets.QTreeWidgetItem(parent_item, [str(key)])
                self.populate_tree(value, item)  # Recursively populate the child items
            else:  # If the value is not a dictionary, create a leaf node
                item = QtWidgets.QTreeWidgetItem(parent_item, [str(key), str(value)])
                # try:
                #     label=QtWidgets.QLabel(str(value))
                #     label.setWordWrap(True)
                #     label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
                #     item = QtWidgets.QTreeWidgetItem(parent_item, [str(key), ''])
                #     self.tree_widget.setItemWidget(item, 1, label)
                # except Exception as e:
                #     print(e)

class ErrorWindow(QtWidgets.QDialog):
    def __init__(self, text):
        super().__init__()
        self.setWindowTitle("InSpectra Gadget Error")
        self.resize(600, 300)
        self.layout = QtWidgets.QVBoxLayout()

        self.text_edit = QtWidgets.QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setText(text)
        self.layout.addWidget(self.text_edit)

        self.button_layout = QtWidgets.QHBoxLayout()
        self.copy_button = QtWidgets.QPushButton("Copy")
        self.close_button = QtWidgets.QPushButton("Close")
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.close_button)
        self.button_layout.addWidget(self.copy_button)
        self.layout.addLayout(self.button_layout)

        self.setLayout(self.layout)

        self.copy_button.clicked.connect(self.copy_text)
        self.close_button.clicked.connect(self.close)

        self.show()

    def copy_text(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())

class ErrorLogWindow(QtWidgets.QDialog):
    def __init__(self, error_log):
        self.error_log = error_log
        super().__init__()
        self.setWindowTitle("InSpectra Gadget Error and Event Log")
        self.resize(900, 500)
        self.layout = QtWidgets.QVBoxLayout()

        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setColumnCount(2)
        self.tree_widget.setHeaderLabels(["Timestamp", "Error Message"])
        self.populate_tree(error_log)
        self.layout.addWidget(self.tree_widget)

        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.layout.addWidget(self.close_button)

        self.save_button = QtWidgets.QPushButton("Save Log")
        self.save_button.clicked.connect(self.save_log)
        self.layout.addWidget(self.save_button)

        self.setLayout(self.layout)
        self.show()

    def populate_tree(self, error_log):
        for key in sorted(error_log.keys()):
            entry = error_log[key]
            timestamp = str(entry.get('timestamp', ''))
            message = str(entry.get('message', ''))
            QtWidgets.QTreeWidgetItem(self.tree_widget, [timestamp, message])

    def save_log(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save Error Log', '', 'JSON Files (*.json)')
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    jsondump(self.error_log, f, ensure_ascii=False, indent=4)
            except Exception as e:
                self.ew=ErrorWindow(f"Error saving log: {e}")

class AutoRefreshPopup(QtWidgets.QDialog):
    def __init__(self, editor_window, from_dropdown=False):
        super().__init__()
        self.editor_window = editor_window
        self.from_dropdown = from_dropdown
        self.setWindowTitle("Set intervals for autorefresh")
        self.resize(300, 150)

        layout = QtWidgets.QVBoxLayout()

        label = QtWidgets.QLabel("Set autorefresh intervals:")
        layout.addWidget(label)

        self.prev_2d= getattr(editor_window, "refresh_2d", 30)
        self.prev_1d= getattr(editor_window, "refresh_1d", 5)

        self.lineedit_2d = QtWidgets.QLineEdit(str(self.prev_2d))
        self.lineedit_2d.setValidator(QtGui.QIntValidator())

        self.lineedit_1d = QtWidgets.QLineEdit(str(self.prev_1d))
        self.lineedit_1d.setValidator(QtGui.QIntValidator())

        self.lineedit_2d.setMaximumWidth(60)
        self.lineedit_1d.setMaximumWidth(60)
        input_layout = QtWidgets.QHBoxLayout()
        input_layout.addWidget(QtWidgets.QLabel("2D:"))
        input_layout.addWidget(self.lineedit_2d)
        input_layout.addWidget(QtWidgets.QLabel("s"))
        input_layout.addWidget(QtWidgets.QLabel("1D:"))
        input_layout.addWidget(self.lineedit_1d)
        input_layout.addWidget(QtWidgets.QLabel("s"))

        layout.addLayout(input_layout)

        if not self.from_dropdown:
            self.save_until_restart_checkbox = QtWidgets.QCheckBox("Save until restart")
            self.save_until_restart_checkbox.setChecked(True)
            layout.addWidget(self.save_until_restart_checkbox)

        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("OK")
        cancel_button = QtWidgets.QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        self.show()

    def accept(self):
        try:
            self.editor_window.refresh_2d = int(self.lineedit_2d.text())
        except ValueError as e:
            self.editor_window.refresh_2d = self.prev_2d
            self.editor_window.log_error(f'Invalid input for 2D refresh interval:\n{type(e).__name__} {e}', show_popup=True)
        try:
            self.editor_window.refresh_1d = int(self.lineedit_1d.text())
        except ValueError as e:
            self.editor_window.refresh_1d = self.prev_1d
            self.editor_window.log_error(f'Invalid input for 1D refresh interval:\n{type(e).__name__} {e}', show_popup=True)
        if not self.from_dropdown:
            self.editor_window.ask_autorefresh = not self.save_until_restart_checkbox.isChecked()
        
        super().accept()