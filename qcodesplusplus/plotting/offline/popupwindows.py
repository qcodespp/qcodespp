from PyQt5 import QtWidgets, QtCore, QtGui
import io
from json import load as jsonload
from json import dump as jsondump
from csv import writer as csvwriter
import qcodesplusplus.plotting.offline.fits as fits
from scipy.ndimage import map_coordinates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.colors import LogNorm
from matplotlib.widgets import Cursor
from matplotlib import rcParams
from matplotlib import colormaps as cm
import numpy as np
try: # lmfit is used for fitting the evolution of the properties of multiple peaks 
    from lmfit.models import LorentzianModel, GaussianModel, ConstantModel
    from lmfit.model import save_modelresult
    lmfit_imported = True
except ModuleNotFoundError:
    lmfit_imported = False

try: # used for single peak fitting
    from scipy.signal import find_peaks
    find_peaks_imported = True
except ModuleNotFoundError:
    find_peaks_imported = False

try:
    import qdarkstyle # pip install qdarkstyle
    qdarkstyle_imported = True
except ModuleNotFoundError:
    qdarkstyle_imported = False

DARK_THEME = True

from .helpers import rcParams_to_dark_theme, rcParams_to_light_theme, cmaps

class LineCutWindow(QtWidgets.QWidget):
    def __init__(self, parent, orientation, init_cmap='viridis',init_canvas=True):
        super().__init__()
        # The parent is the DATA object.
        self.parent = parent
        self.running = True
        self.orientation = orientation
        self.init_cmap = init_cmap
        try:
            self.setWindowTitle(f'Inspectra Gadget - {orientation} linecuts for {self.parent.label}')
        except:
            self.setWindowTitle('Inspectra Gadget - Linecut and Fitting Window')
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

        applymethods=['All by #', 'All by ind', 'Chkd by #','Chkd by ind']
        self.apply_colormap_to_box.addItems(applymethods)
        for cmap_type in cmaps:    
            self.colormap_type_box.addItem(cmap_type)
        self.colormap_box.addItems(list(cmaps.values())[0])
        self.colormap_box.setCurrentText(self.init_cmap)

        # Plotting widgets
        self.reset_plot_limits_button = QtWidgets.QPushButton('Autoscale axes')
        self.save_button = QtWidgets.QPushButton('Save Data')
        self.save_image_button = QtWidgets.QPushButton('Save Image')
        self.copy_image_button = QtWidgets.QPushButton('Copy Image')

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
        self.generate_button.clicked.connect(self.generate_cuts)
        self.move_up_button.clicked.connect(lambda: self.move_cut('up'))
        self.move_down_button.clicked.connect(lambda: self.move_cut('down'))
        self.reorder_by_index_button.clicked.connect(self.reorder_cuts)
        self.apply_button.clicked.connect(self.apply_colormap)

        self.cuts_table.itemClicked.connect(self.item_clicked)

        self.reset_plot_limits_button.clicked.connect(self.autoscale_axes)
        self.save_button.clicked.connect(self.save_data)
        self.save_image_button.clicked.connect(self.save_image)
        self.copy_image_button.clicked.connect(self.copy_image)
        self.clear_fit_button.clicked.connect(self.clear_fit)
        self.fit_class_box.currentIndexChanged.connect(self.fit_class_changed)
        self.fit_box.currentIndexChanged.connect(self.fit_type_changed)
        self.fit_button.clicked.connect(self.start_fitting)
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
        self.generate_layout = QtWidgets.QHBoxLayout()
        self.move_buttons_layout = QtWidgets.QHBoxLayout()
        self.colormap_layout = QtWidgets.QHBoxLayout()

        # Populating
        self.table_buttons_layout.addWidget(self.add_cut_button)
        self.table_buttons_layout.addWidget(self.remove_cut_button)
        self.table_buttons_layout.addWidget(self.clear_cuts_button)

        self.move_buttons_layout.addWidget(self.move_up_button)
        self.move_buttons_layout.addWidget(self.move_down_button)
        self.move_buttons_layout.addWidget(self.reorder_by_index_button)

        self.generate_layout.addWidget(self.generate_label)
        self.generate_layout.addWidget(self.generate_line_edit)
        self.generate_layout.addWidget(self.generate_button)

        self.colormap_layout.addWidget(self.colormap_type_box)
        self.colormap_layout.addWidget(self.colormap_box)
        self.colormap_layout.addWidget(self.apply_colormap_to_box)
        self.colormap_layout.addWidget(self.apply_button)

        # Sublayout(s) in plotting box:
        self.top_buttons_layout = QtWidgets.QHBoxLayout()

        # Populating
        #self.top_buttons_layout.addWidget(self.navi_toolbar)
        self.top_buttons_layout.addWidget(self.reset_plot_limits_button)
        self.top_buttons_layout.addStretch()
        self.top_buttons_layout.addWidget(self.save_button)
        self.top_buttons_layout.addWidget(self.save_image_button)
        self.top_buttons_layout.addWidget(self.copy_image_button)
        #self.top_buttons_layout.addStretch()
        # if self.orientation in ['horizontal','vertical']:
        #     #self.top_buttons_layout.addWidget(self.orientation_button)
        #     self.top_buttons_layout.addWidget(self.down_button)
        #     self.top_buttons_layout.addWidget(self.up_button)
        
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
        self.fit_buttons_layout.addWidget(self.save_parameters_dependency_button)
        self.fit_buttons_layout.addWidget(self.clear_all_fits_button)


    def set_main_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout()
        self.top_half_layout = QtWidgets.QHBoxLayout()

        self.tablebox=QtWidgets.QGroupBox('Linecut list')
        self.table_layout = QtWidgets.QVBoxLayout()
        self.table_layout.addLayout(self.table_buttons_layout)
        self.table_layout.addLayout(self.generate_layout)
        self.table_layout.addWidget(self.cuts_table)
        self.table_layout.addLayout(self.move_buttons_layout)
        self.table_layout.addLayout(self.colormap_layout)
        self.tablebox.setLayout(self.table_layout)
        self.tablebox.setMaximumWidth(450)
        
        self.plotbox=QtWidgets.QGroupBox('Plotting')
        self.plottinglayout = QtWidgets.QVBoxLayout()
        self.plottinglayout.addLayout(self.top_buttons_layout)
        self.plottinglayout.addWidget(self.navi_toolbar)
        self.plottinglayout.addWidget(self.canvas)
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
        self.cuts_table.setColumnCount(6)
        self.cuts_table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked)
        h = self.cuts_table.horizontalHeader()
        h.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for col in range(6):
            h.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
        self.cuts_table.setHorizontalHeaderLabels(['cut #','index','value','offset','color','show fit'])
        v=self.cuts_table.verticalHeader()
        v.setVisible(False)

        self.cuts_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.cuts_table.customContextMenuRequested.connect(self.open_cuts_table_menu)


    def item_clicked(self, item):
        # displays the fit result and/or information.
        row = self.cuts_table.currentRow()
        line = int(self.cuts_table.item(row,0).text())
        if 'fit' in self.parent.linecuts[self.orientation]['lines'][line].keys():
            fit_result = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result']
            self.output_window.setText(fit_result.fit_report())
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

        linecut_item = QtWidgets.QTableWidgetItem(str(linecut_name))
        linecut_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                                 QtCore.Qt.ItemIsEnabled | 
                                 QtCore.Qt.ItemIsUserCheckable)
        linecut_item.setText(str(linecut_name))
        linecut_item.setCheckState(linecut['checkstate'])
        index_box=QtWidgets.QSpinBox()
        if self.orientation=='horizontal':
            index_box.setRange(0,np.shape(self.parent.processed_data[-1])[1]-1)
        elif self.orientation=='vertical':
            index_box.setRange(0,np.shape(self.parent.processed_data[-1])[0]-1)
        index_box.setSingleStep(1)
        index_box.setValue(linecut['data_index'])
        index_box.valueChanged[int].connect(lambda: self.cuts_table_edited('index'))
        value_box=QtWidgets.QTableWidgetItem(f'{linecut['cut_axis_value']:6g}')
        offset_box=QtWidgets.QTableWidgetItem(f'{linecut['offset']:6g}')
        color_box=QtWidgets.QTableWidgetItem('')
        rgbavalue = [int(linecut['linecolor'][0]*255), int(linecut['linecolor'][1]*255), int(linecut['linecolor'][2]*255),int(linecut['linecolor'][3]*255)]
        plot_fit_item = QtWidgets.QTableWidgetItem('')
        if 'fit' in linecut.keys():
            plot_fit_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                            QtCore.Qt.ItemIsEnabled | 
                            QtCore.Qt.ItemIsUserCheckable)
            plot_fit_item.setCheckState(linecut['fit']['fit_checkstate'])

        self.cuts_table.setItem(row,0,linecut_item)
        self.cuts_table.setCellWidget(row,1,index_box)
        self.cuts_table.setItem(row,2,value_box)
        self.cuts_table.item(row, 2).setTextAlignment(int(QtCore.Qt.AlignRight) | 
                                                    int(QtCore.Qt.AlignVCenter))
        self.cuts_table.setItem(row,3,offset_box)
        self.cuts_table.item(row, 3).setTextAlignment(int(QtCore.Qt.AlignRight) | 
                                                    int(QtCore.Qt.AlignVCenter))
        self.cuts_table.setItem(row,4,color_box)
        self.cuts_table.item(row,4).setBackground(QtGui.QColor(*rgbavalue))

        self.cuts_table.setItem(row,5,plot_fit_item)

        self.cuts_table.setCurrentCell(row,0)
        self.cuts_table.itemChanged.connect(self.cuts_table_edited)

    def cuts_table_edited(self,setting=None):
        if setting=='index':
            current_row = self.cuts_table.currentRow()
            self.index_changed(current_row)

        else:
            current_item = self.cuts_table.currentItem()
            current_col = self.cuts_table.currentColumn()
            current_row = self.cuts_table.currentRow()

            if current_col == 2: # The user is trying to edit the value of the data. Let's find a new index for them.
                linecut = self.cuts_table.item(current_row,0).text()
                linecut = int(linecut)
                inputval = float(current_item.text())
                if self.orientation == 'horizontal':
                    new_index = (np.abs(self.parent.processed_data[1][0,:]-inputval)).argmin()
                elif self.orientation == 'vertical':
                    new_index = (np.abs(self.parent.processed_data[0][:,0]-inputval)).argmin()
                self.cuts_table.cellWidget(current_row,1).setValue(new_index)
                self.index_changed(current_row)

            elif current_col == 3: #Change the offset in the dictionary and then replot.
                linecut = self.cuts_table.item(current_row,0).text()
                linecut = int(linecut)
                offset = float(current_item.text())
                self.parent.linecuts[self.orientation]['lines'][linecut]['offset'] = offset
                self.update()
    
            elif current_col == 0: # It's the checkstate, so need to replot and update dictionary
                linecut = int(self.cuts_table.item(current_row,0).text())
                self.parent.linecuts[self.orientation]['lines'][linecut]['checkstate'] = current_item.checkState()
                self.update()

            elif current_col == 5: # It's the checkstate for the fit.
                linecut = int(self.cuts_table.item(current_row,0).text())
                self.parent.linecuts[self.orientation]['lines'][linecut]['fit']['fit_checkstate'] = current_item.checkState()
                self.update()


    def index_changed(self,row):
        index_box = self.cuts_table.cellWidget(row,1)
        data_index=index_box.value()
        linecut = self.cuts_table.item(row,0).text()
        linecut = int(linecut)
        try:
            if self.orientation == 'horizontal':
                self.parent.linecuts[self.orientation]['lines'][linecut]['cut_axis_value']=self.parent.processed_data[1][0,data_index]
                self.cuts_table.item(row,2).setText(f'{self.parent.processed_data[1][0,data_index]:6g}')
            elif self.orientation == 'vertical':
                self.parent.linecuts[self.orientation]['lines'][linecut]['cut_axis_value']=self.parent.processed_data[0][data_index,0]
                self.cuts_table.item(row,2).setText(f'{self.parent.processed_data[0][data_index,0]:6g}')
            self.parent.linecuts[self.orientation]['lines'][linecut]['data_index'] = data_index
            self.update()
        except Exception as e:
            print(e)
        self.cuts_table.setCurrentItem(self.cuts_table.item(row,0)) # Hopefully fixes a bug that if the index is changed, the focus goes weird.

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
                linecut={'data_index':data_index, 'checkstate':QtCore.Qt.Checked,
                        'cut_axis_value':self.parent.processed_data[1][0,data_index],
                        'offset':offset,
                        'linecolor':line_colors[data_index]}
            elif self.orientation == 'vertical':
                line_colors = selected_colormap(np.linspace(0.1,0.9,len(self.parent.processed_data[0][:,0])))
                linecut={'data_index':data_index, 'checkstate':QtCore.Qt.Checked,
                        'cut_axis_value':self.parent.processed_data[0][data_index,0],
                        'offset':offset,
                        'linecolor':line_colors[data_index]}
            self.parent.linecuts[self.orientation]['lines'][int(max_index+1)] = linecut
            self.append_cut_to_table(int(max_index+1))
        except IndexError:
            print('Index out of range.')
        if update: # Don't update every time a cut is added when 'generate' is used
            self.update()

    def remove_cut(self,which='selected'):
        # which = 'selected', 'all'
        if which=='selected':
            try:
                row = self.cuts_table.currentRow()
                linecut = self.cuts_table.item(row,0).text()
                linecut = int(linecut)
                self.parent.linecuts[self.orientation]['lines'].pop(linecut)
                self.cuts_table.removeRow(row)
            except Exception as e:
                print(e)
        elif which=='all':
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
                oldSpinBox = self.cuts_table.cellWidget(current_row, 1)
                self.cuts_table.removeRow(current_row)
                new_row = current_row + delta
                self.cuts_table.insertRow(new_row)
                for i, item in enumerate(items):
                    self.cuts_table.setItem(new_row, i, item)
                if isinstance(oldSpinBox, QtWidgets.QAbstractSpinBox):
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
        # Super broken; the spin box really affects everything. It will be hard to make it work I think.
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
        if applymethod == 'All by #':
            for row in range(self.cuts_table.rowCount()):
                linecut = int(self.cuts_table.item(row,0).text())
                line_colors = selected_colormap(np.linspace(0.1,0.9,self.cuts_table.rowCount()))
                self.parent.linecuts[self.orientation]['lines'][linecut]['linecolor'] = line_colors[row]
                rgbavalue = [int(line_colors[linecut][0]*255), int(line_colors[linecut][1]*255), int(line_colors[linecut][2]*255),int(line_colors[linecut][3]*255)]
                self.cuts_table.item(row,4).setBackground(QtGui.QColor(*rgbavalue))
        elif applymethod == 'All by ind':
            for row in range(self.cuts_table.rowCount()):
                index = int(self.cuts_table.cellWidget(row,1).value())
                linecut = int(self.cuts_table.item(row,0).text())
                if self.orientation == 'horizontal':
                    line_colors = selected_colormap(np.linspace(0.1,0.9,len(self.parent.processed_data[1][0,:])))
                    self.parent.linecuts[self.orientation]['lines'][linecut]['linecolor'] = line_colors[index]
                    rgbavalue = [int(line_colors[index][0]*255), int(line_colors[index][1]*255), int(line_colors[index][2]*255),int(line_colors[index][3]*255)]
                    self.cuts_table.item(row,4).setBackground(QtGui.QColor(*rgbavalue))
                elif self.orientation == 'vertical':
                    line_colors = selected_colormap(np.linspace(0.1,0.9,len(self.parent.processed_data[0][:,0])))
                    self.parent.linecuts[self.orientation]['lines'][linecut]['linecolor'] = line_colors[index]
                    rgbavalue = [int(line_colors[index][0]*255), int(line_colors[index][1]*255), int(line_colors[index][2]*255),int(line_colors[index][3]*255)]
                    self.cuts_table.item(row,4).setBackground(QtGui.QColor(*rgbavalue))

        elif applymethod == 'Chkd by #':
            checked_items = self.get_checked_items(cuts_or_fits='cuts')
            for linecut in checked_items:
                line_colors = selected_colormap(np.linspace(0.1,0.9,len(checked_items)))
                self.parent.linecuts[self.orientation]['lines'][linecut]['linecolor'] = line_colors[linecut]
                rgbavalue = [int(line_colors[linecut][0]*255), int(line_colors[linecut][1]*255), int(line_colors[linecut][2]*255),int(line_colors[linecut][3]*255)]
                self.cuts_table.item(linecut,4).setBackground(QtGui.QColor(*rgbavalue))
        elif applymethod == 'Chkd by ind':
            checked_items = self.get_checked_items(cuts_or_fits='cuts')
            for linecut in checked_items:
                index = int(self.cuts_table.cellWidget(linecut,1).value())
                if self.orientation == 'horizontal':
                    line_colors = selected_colormap(np.linspace(0.1,0.9,len(self.parent.processed_data[1][0,:])))
                    self.parent.linecuts[self.orientation]['lines'][linecut]['linecolor'] = line_colors[index]
                    rgbavalue = [int(line_colors[index][0]*255), int(line_colors[index][1]*255), int(line_colors[index][2]*255),int(line_colors[index][3]*255)]
                    self.cuts_table.item(linecut,4).setBackground(QtGui.QColor(*rgbavalue))
                elif self.orientation == 'vertical':
                    line_colors = selected_colormap(np.linspace(0.1,0.9,len(self.parent.processed_data[0][:,0])))
                    self.parent.linecuts[self.orientation]['lines'][linecut]['linecolor'] = line_colors[index]
                    rgbavalue = [int(line_colors[index][0]*255), int(line_colors[index][1]*255), int(line_colors[index][2]*255),int(line_colors[index][3]*255)]
                    self.cuts_table.item(linecut,4).setBackground(QtGui.QColor(*rgbavalue))

        self.cuts_table.itemChanged.connect(self.cuts_table_edited)
        self.update()

    def colormap_type_edited(self):
        self.colormap_box.clear()
        self.colormap_box.addItems(cmaps[self.colormap_type_box.currentText()])

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
                        self.update()
        
        elif column==0:
            menu = QtWidgets.QMenu(self)
            check_all_action = menu.addAction("Check all")
            uncheck_all_action = menu.addAction("Uncheck all")

            action = menu.exec_(self.cuts_table.viewport().mapToGlobal(position))
            if action == check_all_action:
                self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
                for row in range(self.cuts_table.rowCount()):
                    item = self.cuts_table.item(row, 0)
                    item.setCheckState(QtCore.Qt.Checked)
                    linecut=int(self.cuts_table.item(row,0).text())
                    self.parent.linecuts[self.orientation]['lines'][linecut]['checkstate'] = item.checkState()
                self.cuts_table.itemChanged.connect(self.cuts_table_edited)
                self.update()
            elif action == uncheck_all_action:
                self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
                for row in range(self.cuts_table.rowCount()):
                    item = self.cuts_table.item(row, 0)
                    item.setCheckState(QtCore.Qt.Unchecked)
                    linecut=int(self.cuts_table.item(row,0).text())
                    self.parent.linecuts[self.orientation]['lines'][linecut]['checkstate'] = item.checkState()
                self.cuts_table.itemChanged.connect(self.cuts_table_edited)
                self.update()

        elif column==5:
            menu = QtWidgets.QMenu(self)
            check_all_action = menu.addAction("Show all fits")
            uncheck_all_action = menu.addAction("Hide all fits")

            action = menu.exec_(self.cuts_table.viewport().mapToGlobal(position))
            if action == check_all_action:
                self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
                for row in range(self.cuts_table.rowCount()):
                    item = self.cuts_table.item(row, 5)
                    item.setCheckState(QtCore.Qt.Checked)
                    linecut=int(self.cuts_table.item(row,0).text())
                    self.parent.linecuts[self.orientation]['lines'][linecut]['fit']['fit_checkstate'] = item.checkState()
                self.cuts_table.itemChanged.connect(self.cuts_table_edited)
                self.update()
            elif action == uncheck_all_action:
                self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
                for row in range(self.cuts_table.rowCount()):
                    item = self.cuts_table.item(row, 5)
                    item.setCheckState(QtCore.Qt.Unchecked)
                    linecut=int(self.cuts_table.item(row,0).text())
                    self.parent.linecuts[self.orientation]['lines'][linecut]['fit']['fit_checkstate'] = item.checkState()
                self.cuts_table.itemChanged.connect(self.cuts_table_edited)
                self.update()

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
               
    def clear_lines(self):
        for line in reversed(self.axes.get_lines()):
            if line.get_linestyle() == '--':
                line.remove()
                del line
        if hasattr(self, 'peak_estimates'):
            self.peak_estimates = []
        self.update()
        self.output_window.clear()
        self.fit_type_changed(resetinputs=False)
        self.canvas.draw()
    
    def fit_class_changed(self):
        self.fit_box.clear()
        self.fit_box.addItems(fits.get_names(fitclass=self.fit_class_box.currentText()))
        self.fit_box.setCurrentIndex(0)
        self.fit_type_changed()
        #self.pars_label.setText(fits.get_names(parameters=self.fit_box.currentText()))
    
    def fit_type_changed(self,resetinputs=True):
        fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]
        if resetinputs:
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
        if self.orientation in ['horizontal','vertical','1D']:
            if self.xmin_box.text() != '':
                xmin = float(self.xmin_box.text())
                min_ind=(np.abs(x - xmin)).argmin()
            else:
                min_ind = x.argmin()
            if self.xmax_box.text() != '':
                xmax = float(self.xmax_box.text())
                max_ind=(np.abs(x - xmax)).argmin()
            else:
                max_ind = x.argmax()
            # Need to check if indices in 'wrong' order; i.e. x data descending.
            if min_ind > max_ind:
                x_forfit=x[max_ind:min_ind]
                y_forfit=y[max_ind:min_ind]
            else:
                x_forfit=x[min_ind:max_ind]
                y_forfit=y[min_ind:max_ind]
        else:
            x_forfit = x
            y_forfit = y
        return x_forfit, y_forfit

        # if self.x_forfit[-1]<self.x_forfit[0]:
        #     self.x_forfit=self.x_forfit[::-1]
        #     self.y_forfit=self.y_forfit[::-1]

    def collect_fit_inputs(self,function_class,function_name):
        if function_name=='Expression':
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

    def start_fitting(self,line=None,multilinefit=False):
        if line is None:
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
        try:
            fit_result = fits.fit_data(function_class=function_class, function_name=function_name,
                                                xdata=x_forfit,ydata=y_forfit, p0=p0, inputinfo=inputinfo)
            y_fit = fit_result.best_fit
        except Exception as e:
            self.output_window.setText(f'Curve could not be fitted: {e}')
            fit_parameters = [np.nan]*len(fits.get_names(function_name).split(','))
            y_fit = np.nan

        self.parent.linecuts[self.orientation]['lines'][line]['fit'] = {'fit_result': fit_result,
                                                                        'xdata': x_forfit,
                                                                        'ydata': y_forfit,
                                                                        'fitted_y': y_fit,
                                                                        'fit_checkstate': QtCore.Qt.Checked}

        # Add a checkbox to the table now a fit exists.
        self.cuts_table.itemChanged.disconnect(self.cuts_table_edited)
        plot_fit_item = QtWidgets.QTableWidgetItem('')
        plot_fit_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                            QtCore.Qt.ItemIsEnabled | 
                            QtCore.Qt.ItemIsUserCheckable)
        plot_fit_item.setCheckState(QtCore.Qt.Checked)
        self.cuts_table.setItem(current_row,5,plot_fit_item)
        self.cuts_table.itemChanged.connect(self.cuts_table_edited)
        
        if not multilinefit:
            self.print_parameters(line)
            self.update()

    def fit_checked(self):
        # Fit all checked items in the table.
        fit_lines = self.get_checked_items(cuts_or_fits='cuts')
        for line in fit_lines:
            self.start_fitting(line,multilinefit=True)
        self.print_parameters(line)
        self.update()


    def print_parameters(self,line):
        self.output_window.clear()
        try:
            self.output_window.setText(self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result'].fit_report())

        except Exception as e:
            self.output_window.setText('Could not print fit parameters:', e)

    def get_line_data(self,line):
        # Returns the actual x,y,z data for a particular entry in the linecuts/orientation/lines dictionary
        if self.orientation == '1D':
            x = self.parent.processed_data[0]
            y = self.parent.processed_data[1]
            z = None
        
        elif self.orientation == 'horizontal':
            x = self.parent.processed_data[0][:,self.parent.linecuts[self.orientation]['lines'][line]['data_index']]
            y = self.parent.processed_data[2][:,self.parent.linecuts[self.orientation]['lines'][line]['data_index']]
            z = self.parent.processed_data[1][0,self.parent.linecuts[self.orientation]['lines'][line]['data_index']]
            # Confusingly enough, z here is just the value of the y axis of the parent plot/data where the cut is taken
        
        elif self.orientation == 'vertical':
            x = self.parent.processed_data[1][self.parent.linecuts[self.orientation]['lines'][line]['data_index'],:]
            y = self.parent.processed_data[2][self.parent.linecuts[self.orientation]['lines'][line]['data_index'],:]
            z = self.parent.processed_data[0][self.parent.linecuts[self.orientation]['lines'][line]['data_index'],0]
        return (x,y,z)

    def draw_plot(self,parent_marker=True):
        self.running = True
        self.figure.clear()

        self.axes = self.figure.add_subplot(111)

        lines = self.get_checked_items()

        if self.orientation == '1D':
            x,y,z=self.get_line_data(0)
            self.xlabel = self.parent.settings['xlabel']
            self.ylabel = self.parent.settings['ylabel']
            self.title = self.parent.settings['title']
            self.axes.plot(x, y, linewidth=self.parent.settings['linewidth'])

        elif self.orientation == 'horizontal':
            if hasattr(self.parent,'horimarkers') and len(self.parent.horimarkers)>0:
                for marker in self.parent.horimarkers:
                    marker.remove()
            self.parent.horimarkers = []
            self.xlabel = self.parent.settings['xlabel']
            self.title = f'Cuts at fixed {self.parent.settings['ylabel']}'
            for line in lines:
                x,y,z= self.get_line_data(line)
                self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value'] = z
                if parent_marker:
                    self.parent.horimarkers.append(self.parent.axes.axhline(y=z, linestyle='dashed', linewidth=1, xmax=0.1,
                                                    color=self.parent.linecuts[self.orientation]['lines'][line]['linecolor']))
                    self.parent.horimarkers.append(self.parent.axes.axhline(y=z, linestyle='dashed', linewidth=1, xmin=0.9,
                                                    color=self.parent.linecuts[self.orientation]['lines'][line]['linecolor']))
                self.ylabel = self.parent.settings['clabel']
                offset = self.parent.linecuts[self.orientation]['lines'][line]['offset']
                self.axes.plot(x, y+offset, linewidth=self.parent.settings['linewidth'],
                                color=self.parent.linecuts[self.orientation]['lines'][line]['linecolor'])

        elif self.orientation == 'vertical':
            if hasattr(self.parent,'vertmarkers') and len(self.parent.vertmarkers)>0:
                for marker in self.parent.vertmarkers:
                    marker.remove()
            self.parent.vertmarkers = []
            self.xlabel = self.parent.settings['ylabel']
            self.title = f'Cuts at fixed {self.parent.settings['xlabel']}'
            for line in lines:
                x,y,z= self.get_line_data(line)
                self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value'] = z
                if parent_marker:
                    self.parent.vertmarkers.append(self.parent.axes.axvline(x=z, linestyle='dashed', linewidth=1, ymax=0.1,
                                                    color=self.parent.linecuts[self.orientation]['lines'][line]['linecolor']))
                    self.parent.vertmarkers.append(self.parent.axes.axvline(x=z, linestyle='dashed', linewidth=1, ymin=0.9,
                                                    color=self.parent.linecuts[self.orientation]['lines'][line]['linecolor']))
                self.ylabel = self.parent.settings['clabel']
                offset = self.parent.linecuts[self.orientation]['lines'][line]['offset']
                self.axes.plot(x, y+offset, linewidth=self.parent.settings['linewidth'],
                                color=self.parent.linecuts[self.orientation]['lines'][line]['linecolor'])

        elif self.orientation == 'diagonal' or self.orientation == 'circular':
            x0 = self.parent.linecut_points[0].x 
            y0 = self.parent.linecut_points[0].y
            x1 = self.parent.linecut_points[1].x 
            y1 = self.parent.linecut_points[1].y                
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
                self.y = map_coordinates(self.parent.processed_data[-1], 
                                        np.vstack((x_diag, y_diag)))
                self.x = map_coordinates(self.parent.processed_data[0],
                                        np.vstack((x_diag, y_diag)))                
                self.xlabel = self.parent.settings['xlabel']
                self.title = f'({x0:5g},{y0:5g}) : ({x1:5g},{y1:5g})'
            elif self.orientation == 'circular':
                n = int(8*np.sqrt((i_x0-i_x1)**2+(i_y0-i_y1)**2))
                theta = np.linspace(0, 2*np.pi, n)
                i_x_circ = i_x0+(i_x1-i_x0)*np.cos(theta) 
                i_y_circ = i_y0+(i_y1-i_y0)*np.sin(theta)
                self.y = map_coordinates(self.parent.processed_data[-1], 
                                        np.vstack((i_x_circ, i_y_circ)))
                self.x = theta
                self.xlabel = 'Angle (rad)'
                self.title = ''
            self.ylabel = self.parent.settings['clabel']
            self.axes.plot(x, y, linewidth=self.parent.settings['linewidth'])
        self.cursor = Cursor(self.axes, useblit=True, color='grey', linewidth=0.5)
        self.axes.set_xlabel(self.xlabel, size='x-large')
        self.axes.set_ylabel(self.ylabel, size='x-large')
        self.axes.tick_params(labelsize='x-large', color=rcParams['axes.edgecolor'])
        if hasattr(self,'title'):
            self.axes.set_title(self.title, size='x-large')
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
                linewidth=self.parent.settings['linewidth'])
            fit_components=fit_result.eval_components()
            if self.colormap_box.currentText() == 'viridis':
                selected_colormap = cm.get_cmap('plasma')
            elif self.colormap_box.currentText() == 'plasma':
                selected_colormap = cm.get_cmap('viridis')
            line_colors = selected_colormap(np.linspace(0.1,0.9,len(fit_components.keys())))
            for i,key in enumerate(fit_components.keys()):
                self.axes.plot(x_forfit, fit_components[key]+offset, '--', color=line_colors[i],alpha=0.75, linewidth=self.parent.settings['linewidth'])
        except Exception as e:
            self.output_window.setText(f'Could not plot fit components: {e}')
        self.canvas.draw()

    def autoscale_axes(self):
        self.axes.autoscale()
        self.canvas.draw()

    def closeEvent(self, event):
        if hasattr(self.parent,'vertmarkers'):
            for marker in self.parent.vertmarkers:
                marker.remove()
                del marker
            del self.parent.vertmarkers
        if hasattr(self.parent,'horimarkers'):
            for marker in self.parent.horimarkers:
                marker.remove()
                del marker
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
                        for i in range(len(data[f'linecut{lines[0]}_X'])):
                            row = []
                            for param in data:
                                try:
                                    row.append(data[param][i])
                                except IndexError:
                                    row.append('')
                            writer.writerow(row)
            except Exception as e:
                print(e)
    
    def save_fit_result(self):
        current_row = self.cuts_table.currentRow()
        line = int(self.cuts_table.item(current_row,0).text())
        if 'fit' in self.parent.linecuts[self.orientation]['lines'][line].keys():
            fit_result = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result']
            formats = 'lmfit Model Result (*.sav)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Fit Result','', formats)
            save_modelresult(fit_result,filename)

    def save_all_fits(self):
        fit_lines = self.get_checked_items(cuts_or_fits='fits')
        if len(fit_lines) > 0:
            formats = 'lmfit Model Result (*.sav)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Fit Result: Select base name','', formats)
            for line in fit_lines:
                fit_result = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result']
                save_modelresult(fit_result,filename.replace('.sav',f'_{line}.sav'))

    def clear_fit(self):
        current_row = self.cuts_table.currentRow()
        line = int(self.cuts_table.item(current_row,0).text())
        if 'fit' in self.parent.linecuts[self.orientation]['lines'][line].keys():
            self.parent.linecuts[self.orientation]['lines'][line].pop('fit')
            empty_box=QtWidgets.QTableWidgetItem('')
            self.cuts_table.setItem(current_row,5,empty_box)
            fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]
            self.output_window.setText('Information about selected fit type:\n'+
                                   fit_function['description'])
            self.update()

    def clear_all_fits(self):
        fit_lines = self.get_checked_items(cuts_or_fits='fits')
        for line in fit_lines:
            self.parent.linecuts[self.orientation]['lines'][line].pop('fit')
        for row in range(self.cuts_table.rowCount()):
            empty_box=QtWidgets.QTableWidgetItem('')
            self.cuts_table.setItem(row,5,empty_box)
        fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]
        self.output_window.setText('Information about selected fit type:\n'+fit_function['description'])
        self.update()

    def save_parameters_dependency(self):
        try:
            fit_lines = self.get_checked_items(cuts_or_fits='fits')
            first_result = self.parent.linecuts[self.orientation]['lines'][fit_lines[0]]['fit']['fit_result']
            data=np.zeros((len(fit_lines),len(first_result.params.keys())+1))
            for i,line in enumerate(fit_lines):
                data[i,0] = self.parent.linecuts[self.orientation]['lines'][line]['cut_axis_value']
                for j,param in enumerate(first_result.params.keys()):
                    data[i,j+1] = self.parent.linecuts[self.orientation]['lines'][line]['fit']['fit_result'].params[param].value
            success=True
        except Exception as e:
            print('Could not compile array: {e}')
            success=False
        if success:
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Fiting Result','', 'numpy dat file (*.dat)')
            if filename:
                np.savetxt(filename, data, delimiter='\t', header='X,'+','.join(first_result.params.keys()), fmt='%s')
                print('Saved!')

    def save_image(self):
        formats = 'Portable Network Graphic (*.png);;Adobe Acrobat (*.pdf)'
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Figure As', '', formats)
        if filename:
            print('Save Figure as '+filename+' ...')
            if DARK_THEME and qdarkstyle_imported:
                rcParams_to_light_theme()
                self.update()
            self.figure.savefig(filename)
            if DARK_THEME and qdarkstyle_imported:
                rcParams_to_dark_theme()
                self.update()
            print('Saved!')
    
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
            
    def mouse_scroll_canvas(self, event):
        if event.inaxes:

            scale=1.2
            scale_factor = np.power(scale, -event.step)
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

class Popup1D(LineCutWindow):
    def __init__(self, parent):
        super().__init__(parent, orientation='1D', init_canvas=False)
        try:
            self.setWindowTitle(f'Inspectra Gadget - Options for {parent.label}')
        except:
            self.setWindowTitle('Inspectra Gadget - Options for 1D data')
        self.resize(900, 900)
        self.parent = parent
        self.running = True
        self.init_widgets()
        self.init_connections()
        self.init_layouts()
        self.set_main_layout()
        self.init_cuts_table()
        self.fit_type_changed()

    def init_layouts(self):
        # Sub-layouts in Linecut list box:
        self.table_buttons_layout = QtWidgets.QHBoxLayout()
        self.colormap_layout = QtWidgets.QHBoxLayout()

        # Populating
        self.table_buttons_layout.addWidget(self.add_cut_button)
        self.table_buttons_layout.addWidget(self.remove_cut_button)
        self.table_buttons_layout.addWidget(self.clear_cuts_button)
        self.table_buttons_layout.addWidget(self.move_up_button)
        self.table_buttons_layout.addWidget(self.move_down_button)

        self.colormap_layout.addWidget(self.colormap_type_box)
        self.colormap_layout.addWidget(self.colormap_box)
        self.colormap_layout.addWidget(self.apply_colormap_to_box)
        self.colormap_layout.addWidget(self.apply_button)
        
        # Sub-layouts(s) in fitting box
        self.lims_layout = QtWidgets.QHBoxLayout()
        self.fit_layout = QtWidgets.QHBoxLayout()
        self.inputs_layout = QtWidgets.QHBoxLayout()
        self.guess_layout = QtWidgets.QHBoxLayout()
        self.output_layout = QtWidgets.QVBoxLayout()
        self.fit_buttons_layout = QtWidgets.QHBoxLayout()
        self.fit_all_buttons_layout = QtWidgets.QHBoxLayout()

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
        self.fit_all_buttons_layout.addWidget(self.fit_checked_button)
        self.fit_all_buttons_layout.addWidget(self.save_all_fits_button)
        self.fit_all_buttons_layout.addWidget(self.clear_all_fits_button)
        self.fit_all_buttons_layout.addWidget(self.save_parameters_dependency_button)
        self.fit_all_buttons_layout.addStretch()

    def set_main_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout()

        self.tablebox=QtWidgets.QGroupBox('Traces list')
        self.table_layout = QtWidgets.QVBoxLayout()
        self.table_layout.addLayout(self.table_buttons_layout)
        self.table_layout.addWidget(self.cuts_table)
        self.table_layout.addLayout(self.colormap_layout)
        self.tablebox.setLayout(self.table_layout)
        

        self.fittingbox=QtWidgets.QGroupBox('Curve Fitting')
        self.fittinglayout = QtWidgets.QVBoxLayout()
        self.fittinglayout.addLayout(self.lims_layout)
        self.fittinglayout.addLayout(self.fit_layout)
        self.fittinglayout.addLayout(self.inputs_layout)
        self.fittinglayout.addLayout(self.guess_layout)
        self.fittinglayout.addLayout(self.output_layout)
        self.fittinglayout.addLayout(self.fit_buttons_layout)
        self.fittinglayout.addLayout(self.fit_all_buttons_layout)
        self.fittingbox.setLayout(self.fittinglayout)

        self.main_layout.addWidget(self.tablebox)
        self.main_layout.addWidget(self.fittingbox)
        self.setLayout(self.main_layout)

    def init_cuts_table(self):
        self.cuts_table.setColumnCount(6)
        self.cuts_table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked)
        h = self.cuts_table.horizontalHeader()
        h.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for col in range(6):
            h.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
        self.cuts_table.setHorizontalHeaderLabels(['#','X data','Y data','linetype','color','show fit'])
        v=self.cuts_table.verticalHeader()
        v.setVisible(False)

        self.cuts_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.cuts_table.customContextMenuRequested.connect(self.open_cuts_table_menu)
            
class FFTWindow(QtWidgets.QWidget):
    def __init__(self, fftdata):
        super().__init__()
        self.resize(600, 600)
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        #zoom_factory(self.axes)
        self.canvas = FigureCanvas(self.figure)
        self.navi_toolbar = NavigationToolbar(self.canvas, self)
        self.fft = np.absolute(fftdata).transpose()
        self.image = self.axes.pcolormesh(self.fft, shading='auto', norm=LogNorm(vmin=self.fft.min(), vmax=self.fft.max()))
        self.cbar = self.figure.colorbar(self.image, orientation='vertical')
        self.figure.tight_layout(pad=2)
        self.axes.tick_params(color=rcParams['axes.edgecolor'])
        self.canvas.draw()
        self.vertical_layout.addWidget(self.navi_toolbar)
        self.vertical_layout.addWidget(self.canvas)
        self.setLayout(self.vertical_layout)