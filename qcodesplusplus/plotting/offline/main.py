# -*- coding: utf-8 -*-
"""
Inspectra-Gadget

Author: Joeri de Bruijckere

Adapted for qcodes++ by: Dags Olsteins and Damon Carrad

To convert QtDesigner UI to python file:
pyuic5 -x design.ui -o design.py

"""

from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import os
import copy
import io
import tarfile
from webbrowser import open as href_open
from csv import writer as csvwriter
from stat import ST_CTIME
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib import rcParams
from matplotlib import colormaps as cm
from cycler import cycler
from collections import OrderedDict
try:
    import qdarkstyle # pip install qdarkstyle
    qdarkstyle_imported = True
except ModuleNotFoundError:
    qdarkstyle_imported = False

from lmfit.model import save_modelresult, load_modelresult

import qcodesplusplus.plotting.offline.design as design
from .popupwindows import LineCutWindow, FFTWindow
from .sidebars import Sidebar1D
from .helpers import (cmaps, MidpointNormalize,NavigationToolbarMod,
                      rcParams_to_dark_theme,rcParams_to_light_theme,
                      NoScrollQComboBox,DraggablePoint)
from .filters import Filter
from .datatypes import DataItem, BaseClassData, NumpyData
from .qcodes_pp_extension import qcodesppData
from .qcodes_extension import QCodesData
from .qd_extension import QdData

from qcodes import initialise_or_create_database_at, load_last_experiment

# UI settings
DARK_THEME = True
AUTO_REFRESH_INTERVAL_2D = 1
AUTO_REFRESH_INTERVAL_3D = 30

# List of custom presets
PRESETS = [{'title': '', 'labelsize': '9', 'ticksize': '9', 'spinewidth': '0.5',
            'titlesize': '9',
            'canvas_bounds': (0.425,0.4,0.575,0.6), # (left, bottom, right, top)
            'show_meta_settings': False},
           {'title': '<label>', 'labelsize': '16', 'ticksize': '16', 
            'spinewidth': '0.8', 'titlesize': '16', 
            'canvas_bounds': (0.425,0.4,0.575,0.6), # (left, bottom, right, top)
            'show_meta_settings': True},
           {'title': '', 'labelsize': '9', 'ticksize': '9', 'spinewidth': '0.5'},
           {'title': '', 'labelsize': '9', 'ticksize': '9', 'spinewidth': '0.5'}]

# Matplotlib settings; font type is chosen such that text (labels, ticks, ...) 
# can be recognized by Illustrator
rcParams['pdf.fonttype'] = 42
rcParams['ps.fonttype'] = 42
rcParams['font.family'] = 'sans-serif'
rcParams['font.sans-serif'] = ['Arial']
rcParams['font.cursive'] = ['Arial']
rcParams['mathtext.fontset'] = 'custom'
if DARK_THEME and qdarkstyle_imported:
    DARK_COLOR = '#19232D'
    GREY_COLOR = '#505F69'
    LIGHT_COLOR = '#F0F0F0'
    BLUE_COLOR = '#148CD2'
    rcParams['figure.facecolor'] = DARK_COLOR
    rcParams['axes.facecolor'] = DARK_COLOR
    rcParams['axes.edgecolor'] = GREY_COLOR
    rcParams['text.color'] = LIGHT_COLOR
    rcParams['xtick.color'] = LIGHT_COLOR
    rcParams['ytick.color'] = LIGHT_COLOR
    rcParams['axes.labelcolor'] = LIGHT_COLOR
    rcParams['savefig.facecolor'] = 'white'
    color_cycle = [BLUE_COLOR, 'ff7f0e', '2ca02c', 'd62728', '9467bd', 
                   '8c564b', 'e377c2', '7f7f7f', 'bcbd22', '17becf']
    rcParams['axes.prop_cycle'] = cycler('color', color_cycle)


# Add custom hybrid colormaps to matplotlib register
# cmaps['Hybrid'] = ['magma+bone_r','inferno+bone_r']
# for cmap in cmaps['Hybrid']:
#     n_colors = 512
#     top = cm.get_cmap(cmap.split('+')[1], n_colors)
#     bottom = cm.get_cmap(cmap.split('+')[0], n_colors)
#     newcolors = np.vstack((top(np.linspace(0, 1, n_colors)),
#                            bottom(np.linspace(0, 1, n_colors))))
#     newcolors_r = newcolors[::-1]
#     newcmp = ListedColormap(newcolors, name=cmap)
#     newcmp_r = ListedColormap(newcolors_r, name=cmap+'_r')
#     cm.register_cmap(cmap=newcmp)
#     cm.register_cmap(cmap=newcmp_r)    

# Only include colormaps that are in the matplotlib register
for cmap_type in cmaps.copy():
    cmaps[cmap_type][:] = [cmap for cmap in cmaps[cmap_type] 
                           if cmap in plt.colormaps()]
    if cmaps[cmap_type] == []:
        del cmaps[cmap_type]
        
FONT_SIZES = ['8', '9', '10', '12', '14', '16', '18', '24']
SETTINGS_MENU_OPTIONS = OrderedDict()
SETTINGS_MENU_OPTIONS['title'] = [' ','<label>']
SETTINGS_MENU_OPTIONS['xlabel'] = ['Gate voltage (V)', 
                                   '$V_g$ (V)',
                                   'Bias voltage (mV)', 
                                   '$V$ (mV)',
                                   'Magnetic Field (T)', 
                                   '$B$ (T)', 
                                   'Angle (degrees)', 
                                   'Temperature (K)']
SETTINGS_MENU_OPTIONS['ylabel'] = ['Bias voltage (mV)', 
                                   '$V$ (mV)', 
                                   'Gate voltage (V)', 
                                   '$V_g$ (V)', 
                                   '$I$ (A)',
                                   '$I$ (nA)',
                                   'Current (A)',
                                   'Current (nA)',
                                   'd$I$/d$V$ (μS)', 
                                   'd$I$/d$V$ $(e^{2}/h)$',
                                   '(d$I$/d$V$ $(e^{2}/h)$)$^{1/4}$',
                                   'Angle (degrees)', 
                                   'Temperature (K)',
                                   'Magnetic Field (T)', 
                                   '$B$ (T)', ]
SETTINGS_MENU_OPTIONS['clabel'] = ['$I$ (A)',
                                   '$I$ (nA)',
                                   'Current (A)',
                                   'Current (nA)',
                                   'Voltage (V)',
                                    'Voltage (mV)',
                                   'd$I$/d$V$ (S)',
                                   'd$V$/d$I$ (Ohm)',
                                   'd$I$/d$V$ (a.u.)', 
                                   'd$I$/d$V$ $(2e^{2}/h)$', 
                                   'd$I$/d$V$ $(e^{2}/h)$', 
                                   'd$I$/d$V$ ($G_0$)', 
                                   '(d$I$/d$V$ $(e^{2}/h)$)$^{1/4}$',
                                   'log$^{10}$(d$I$/d$V$ $(e^{2}/h)$)', 
                                   'd$^2I$/d$V^2$ (a.u.)', 
                                   '|d$^2I$/d$V^2$| (a.u.)']
SETTINGS_MENU_OPTIONS['titlesize'] = FONT_SIZES
SETTINGS_MENU_OPTIONS['labelsize'] = FONT_SIZES
SETTINGS_MENU_OPTIONS['ticksize'] = FONT_SIZES
SETTINGS_MENU_OPTIONS['colorbar'] = ['True', 'False']
SETTINGS_MENU_OPTIONS['columns'] = ['0,1,2','0,1,3','0,2,3','1,2,4']
SETTINGS_MENU_OPTIONS['minorticks'] = ['True','False']
SETTINGS_MENU_OPTIONS['delimiter'] = [' ',',']
SETTINGS_MENU_OPTIONS['linecolor'] = ['black', 'red', 'white', 
                                        'blue', 'green']
SETTINGS_MENU_OPTIONS['maskcolor'] = ['black','white']
SETTINGS_MENU_OPTIONS['lut'] = ['128','256','512','1024']
SETTINGS_MENU_OPTIONS['rasterized'] = ['True','False']
SETTINGS_MENU_OPTIONS['dpi'] = ['figure','300']
SETTINGS_MENU_OPTIONS['transparent'] = ['True', 'False']
SETTINGS_MENU_OPTIONS['shading'] = ['auto', 'flat', 'gouraud', 'nearest']

AXIS_SCALING_OPTIONS = ['linear', 'log', 'symlog', 'logit']

class Editor(QtWidgets.QMainWindow, design.Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.window_title = 'Inspectra Gadget'
        self.window_title_auto_refresh = ''
        self.setupUi(self)
        self.init_plot_settings()
        self.init_view_settings()
        self.init_axis_scaling()
        self.init_filters()
        self.init_connections()
        self.init_canvas()
        self.linked_folder = None
        self.linked_files = []
        self.resize(1400,1000)
    
    def init_plot_settings(self):
        self.settings_table.setColumnCount(2)
        self.settings_table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked)
        for col in range(2):
            h = self.settings_table.horizontalHeader()
            h.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
        self.settings_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        # Opens options menu with right-click
        self.settings_table.customContextMenuRequested.connect(self.open_plot_settings_menu)
    
    def init_view_settings(self):
        self.cmaps = cmaps
        for cmap_type in self.cmaps:    
            self.colormap_type_box.addItem(cmap_type)
        self.colormap_box.addItems(list(self.cmaps.values())[0])
        self.min_line_edit.setAlignment(QtCore.Qt.AlignRight | 
                                        QtCore.Qt.AlignVCenter)
        self.max_line_edit.setAlignment(QtCore.Qt.AlignRight | 
                                        QtCore.Qt.AlignVCenter)
        self.mid_line_edit.setAlignment(QtCore.Qt.AlignRight | 
                                        QtCore.Qt.AlignVCenter)
        
    def init_axis_scaling(self):
        self.xaxis_combobox.addItems(AXIS_SCALING_OPTIONS)
        self.yaxis_combobox.addItems(AXIS_SCALING_OPTIONS)
    
    def init_filters(self):                
        self.filters_combobox.addItem('<Add Filter>')
        self.filters_combobox.addItems(Filter.DEFAULT_SETTINGS.keys())
        self.filters_table.setColumnCount(4)
        self.filters_table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked)
        h = self.filters_table.horizontalHeader()
        h.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for col in range(1,4):
            h.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
        self.filters_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        # Opens options menu with right-click
        self.filters_table.customContextMenuRequested.connect(self.open_filter_settings_menu)
        
    def init_connections(self):
        self.open_files_button.clicked.connect(self.open_files)
        self.open_folder_button.clicked.connect(self.open_files_from_folder)
        self.link_folder_button.clicked.connect(lambda: self.update_link_to_folder(new_folder=True))
        self.delete_files_button.clicked.connect(lambda: self.remove_files('current'))
        self.clear_files_button.clicked.connect(lambda: self.remove_files('all'))
        self.unlink_folder_button.clicked.connect(self.unlink_folder)
        self.file_list.itemChanged.connect(self.file_checked)
        self.file_list.itemClicked.connect(self.file_clicked)
        self.file_list.itemDoubleClicked.connect(self.file_double_clicked)
        self.settings_table.itemChanged.connect(self.plot_setting_edited)
        self.filters_table.itemChanged.connect(self.filters_table_edited)
        self.copy_settings_button.clicked.connect(self.copy_plot_settings)
        self.paste_settings_button.clicked.connect(lambda: self.paste_plot_settings('copied'))
        self.reset_settings_button.clicked.connect(lambda: self.paste_plot_settings('default'))
        self.filters_combobox.currentIndexChanged.connect(self.filters_box_changed)
        self.xaxis_combobox.currentIndexChanged.connect(self.axis_scaling_changed)
        self.yaxis_combobox.currentIndexChanged.connect(self.axis_scaling_changed)
        self.delete_filters_button.clicked.connect(lambda: self.remove_filters('current'))
        self.clear_filters_button.clicked.connect(lambda: self.remove_filters('all'))
        self.copy_filters_button.clicked.connect(self.copy_filters)
        self.paste_filters_button.clicked.connect(lambda: self.paste_filters('copied'))
        self.up_filters_button.clicked.connect(lambda: self.move_filter(-1))
        self.down_filters_button.clicked.connect(lambda: self.move_filter(1))
        # self.previous_button.clicked.connect(self.to_previous_file)
        # self.next_button.clicked.connect(self.to_next_file)
        self.new_plot_button.clicked.connect(lambda: self.duplicate_item(new_plot_button=True))
        self.copy_view_button.clicked.connect(self.copy_view_settings)
        self.paste_view_button.clicked.connect(lambda: self.paste_view_settings('copied'))
        self.colormap_type_box.currentIndexChanged.connect(self.colormap_type_edited)
        self.colormap_box.currentIndexChanged.connect(self.colormap_edited)
        self.reverse_colors_box.clicked.connect(self.colormap_edited)
        self.xmin_line_edit.editingFinished.connect(lambda: self.axlim_setting_edited('Xmin'))
        self.xmax_line_edit.editingFinished.connect(lambda: self.axlim_setting_edited('Xmax'))
        self.ymin_line_edit.editingFinished.connect(lambda: self.axlim_setting_edited('Ymin'))
        self.ymax_line_edit.editingFinished.connect(lambda: self.axlim_setting_edited('Ymax'))
        self.copy_xy_button.clicked.connect(self.copy_axlim_settings)
        self.paste_xy_button.clicked.connect(lambda: self.paste_axlim_settings('copied'))
        self.reset_xy_button.clicked.connect(self.reset_axlim_settings)
        self.min_line_edit.editingFinished.connect(lambda: self.view_setting_edited('Minimum'))
        self.max_line_edit.editingFinished.connect(lambda: self.view_setting_edited('Maximum'))
        self.mid_line_edit.editingFinished.connect(lambda: self.view_setting_edited('Midpoint'))
        self.lock_checkbox.clicked.connect(lambda: self.view_setting_edited('Locked'))
        self.mid_checkbox.clicked.connect(lambda: self.view_setting_edited('MidLock'))
        self.reset_limits_button.clicked.connect(self.reset_color_limits)
        self.save_image_button.clicked.connect(self.save_image)
        self.copy_image_button.clicked.connect(self.copy_canvas_to_clipboard)
        self.load_filters_button.clicked.connect(self.load_filters)
        self.action_filters.triggered.connect(self.save_filters)
        self.action_current_file.triggered.connect(lambda: self.save_session('current'))
        self.action_all_files.triggered.connect(lambda: self.save_session('all'))
        self.action_checked_files.triggered.connect(lambda: self.save_session('checked'))
        self.action_restore_session.triggered.connect(self.load_session)
        self.action_combine_files.triggered.connect(self.combine_plots)
        self.action_duplicate_file.triggered.connect(self.duplicate_item)
        self.action_save_data_selected_file.triggered.connect(lambda: self.save_processed_data('current'))
        self.track_button.clicked.connect(self.track_button_clicked)
        self.refresh_line_edit.editingFinished.connect(lambda: self.refresh_interval_changed(self.refresh_line_edit.text()))
        self.actionSave_plot_s_as.triggered.connect(self.save_image)
        self.action_open_file.triggered.connect(self.open_files)
        self.action_open_files_from_folder.triggered.connect(self.open_files_from_folder)
        self.action_copy_plot_as_image.triggered.connect(self.copy_canvas_to_clipboard)
        self.action_save_files_as_PNG.triggered.connect(lambda: self.save_images_as('.png'))
        self.action_save_files_as_PDF.triggered.connect(lambda: self.save_images_as('.pdf'))
        # self.action_preset_0.triggered.connect(lambda: self.apply_preset(0))
        # self.action_preset_1.triggered.connect(lambda: self.apply_preset(1))
        # self.action_preset_2.triggered.connect(lambda: self.apply_preset(2))
        # self.action_preset_3.triggered.connect(lambda: self.apply_preset(3))
        self.action_refresh_stop.setEnabled(False)
        self.action_link_to_folder.triggered.connect(lambda: self.update_link_to_folder(new_folder=True))
        self.action_unlink_folder.triggered.connect(self.unlink_folder)
        self.action_track_data.triggered.connect(self.track_button_clicked)
        self.refresh_file_button.clicked.connect(self.refresh_files)
        self.up_file_button.clicked.connect(lambda: self.move_file('up'))
        self.down_file_button.clicked.connect(lambda: self.move_file('down'))
        self.file_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.open_item_menu)
        self.actionOnline_help.triggered.connect(lambda: href_open('https://github.com/djcarrad/qcodesplusplus/wiki/Offline-plotting:-InSpectra-Gadget'))

        # Keyboard shortcuts
        self.open_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+O"), self)
        self.open_shortcut.activated.connect(self.open_files)
        self.open_folder_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+O"), self)
        self.open_folder_shortcut.activated.connect(self.open_files_from_folder)
        self.link_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+L"), self)
        self.link_shortcut.activated.connect(lambda: self.update_link_to_folder(new_folder=True))
        self.unlink_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+L"), self)
        self.unlink_shortcut.activated.connect(self.unlink_folder)
        self.track_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+T"), self)
        self.track_shortcut.activated.connect(self.track_button_clicked)
        self.save_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+S"), self)
        self.save_shortcut.activated.connect(self.save_image)
        self.copy_image_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+C"), self)
        self.copy_image_shortcut.activated.connect(self.copy_canvas_to_clipboard)
        self.duplicate_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+D"), self)
        self.duplicate_shortcut.activated.connect(self.duplicate_item)
        self.save_session_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"),self)
        self.save_session_shortcut.activated.connect(lambda: self.save_session('all'))
        self.load_session_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"),self)
        self.load_session_shortcut.activated.connect(self.load_session)
    
    def init_canvas(self):
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect('button_press_event', self.mouse_click_canvas)
        self.canvas.mpl_connect('scroll_event', self.mouse_scroll_canvas)
        self.navi_toolbar = NavigationToolbarMod(self.canvas, self)
        self.graph_layout.addWidget(self.navi_toolbar)
        self.graph_layout.addWidget(self.canvas)
        self.subplot_grid = [(1,1),(1,2),(2,2),(2,2),(2,3),(2,3),(2,4),(2,4),
                             (3,4),(3,4),(3,4),(3,4),(4,4),(4,4),(4,4),(4,4),
                             (4,5),(4,5),(4,5),(4,5),(4,5),(5,5),(5,5),(5,5),
                             (5,5)]
        self.figure.subplots_adjust(top=0.893, bottom=0.137, 
                                    left=0.121, right=0.86)
        
    def load_data_item(self,filepath,load_the_data=True):
        #print(f'Open {filepath}...')
        filename, extension = os.path.splitext(filepath)
        if extension == '.npy': # Numpy files (saved session)
            dataset_list = np.load(filepath, allow_pickle=True)
            for dataset in dataset_list:
                try:
                    item = DataItem(NumpyData(filepath, self.canvas, dataset))
                    return item
                except Exception as e:
                    print(f'Failed to add NumPy dataset '
                            f'{dataset["File Name"]}:', e)
                    
        elif (extension == '.dat' and # qcodes++ files
                os.path.isfile(os.path.dirname(filepath)+'/snapshot.json')):
            metapath = os.path.dirname(filepath)+'/snapshot.json'
            try:
                item = DataItem(qcodesppData(filepath, self.canvas, metapath,load_the_data))
                return item
            except Exception as e:
                print(f'Failed to add qcodes++ dataset {filepath}:', e)
        
        elif extension == '.db': # QCoDeS files
            initialise_or_create_database_at(filepath)
            datasets = load_last_experiment().data_sets()
            for dataset in datasets:
                try:
                    item = DataItem(QCodesData(filepath, self.canvas, dataset))
                    return item
                except Exception as e:
                    print(f'Failed to add QCoDes dataset '
                            f'#{dataset.captured_run_id}:', e)
        
        elif (os.path.basename(filepath) == 'data.dat' and # Matlab qd files
                os.path.isfile(os.path.dirname(filepath)+'/meta.json')):
            metapath = os.path.dirname(filepath)+'/meta.json'
            item = DataItem(QdData(filepath, self.canvas, metapath))
            return item
        
        else: # bare column-based data file
            item = DataItem(BaseClassData(filepath, self.canvas))
            return item

    def open_files(self, filepaths=None, load_the_data=True, attr_dicts=None, dirpath=None,overrideautocheck=False):
        self.file_list.itemChanged.disconnect(self.file_checked)
        if not filepaths:
            filepaths, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self, 'Open File', '', 'Data Files (*.dat *.npy *.db *.csv)')
        if filepaths:
            for i,filepath in enumerate(filepaths):
                try:
                    item=self.load_data_item(filepath,load_the_data)
                    item.filepath=filepath
                    self.file_list.addItem(item)

                    if attr_dicts is not None: #then a previous session is being loaded
                        for attr in attr_dicts[i]:
                            if attr not in ['filename','checkState']:
                                setattr(item.data,attr,attr_dicts[i][attr])
                            
                            elif attr=='checkState':
                                item.setCheckState(attr_dicts[i][attr])
                                if attr_dicts[i][attr]==2:
                                    self.file_checked(item)
                                    overrideautocheck=True #If any item is checked, override autochecking. But if NONE of them are checked, let autocheck do it's thing.
                            
                            if hasattr(item.data,'linecuts'):
                                for orientation in item.data.linecuts.keys():
                                    if len(item.data.linecuts[orientation]['lines']) > 0:
                                        for line in item.data.linecuts[orientation]['lines'].keys():
                                            if 'fit' in item.data.linecuts[orientation]['lines'][line].keys():
                                                item.data.linecuts[orientation]['lines'][line]['fit']['fit_result'] = load_modelresult(dirpath+'/igtemp/'+item.data.linecuts[orientation]['lines'][line]['fit']['fit_result']+'.sav')
                                    #Then make the linecut window
                                        item.data.linecuts[orientation]['linecut_window'] = LineCutWindow(item.data,orientation=orientation,init_cmap='plasma')
                                        item.data.linecuts[orientation]['linecut_window'].running = True
                                        for line in item.data.linecuts[orientation]['lines']:
                                            item.data.linecuts[orientation]['linecut_window'].append_cut_to_table(line)
                                        item.data.linecuts[orientation]['linecut_window'].activateWindow()
                                        item.data.linecuts[orientation]['linecut_window'].update()
                                        item.data.linecuts[orientation]['linecut_window'].show()
                            
                            if hasattr(item.data,'plotted_lines'):
                                if len(item.data.plotted_lines) > 0:
                                    item.data.sidebar1D = Sidebar1D(item.data,self)
                                    item.data.sidebar1D.running = True
                                    for line in item.data.plotted_lines.keys():
                                        if 'fit' in item.data.plotted_lines[line].keys():
                                            item.data.plotted_lines[line]['fit']['fit_result'] = load_modelresult(dirpath+'/igtemp/'+item.data.plotted_lines[line]['fit']['fit_result']+'.sav')
                                    for line in item.data.plotted_lines:
                                        item.data.sidebar1D.append_trace_to_table(line)
                                    item.data.sidebar1D.update()
                            
                except Exception as e:
                    print(f'Failed to open {filepath}:', e)

            if self.file_list.count() > 0:
                last_item = self.file_list.item(self.file_list.count()-1)
                self.file_list.setCurrentItem(last_item)
                if not overrideautocheck:
                    for item_index in range(self.file_list.count()-1):
                        self.file_list.item(item_index).setCheckState(QtCore.Qt.Unchecked)
                    last_item.setCheckState(QtCore.Qt.Checked)
                    self.file_checked(last_item)
        self.file_list.itemChanged.connect(self.file_checked)
    
    def remove_files(self, which='current'):
        if self.file_list.count() > 0:
            if which == 'current':
                items = [self.file_list.currentItem()]
            elif which == 'all':
                items = [self.file_list.item(n) for n in range(self.file_list.count())]
            elif which == 'unchecked':
                items = self.get_unchecked_items()
            update_plots = any([item.checkState() == 2 for item in items]) # only update plots if any of the items are checked
            for item in items: 
                if (item.data.filepath in self.linked_files
                    and not hasattr(item, 'duplicate')):
                    self.linked_files.remove(item.data.filepath)
                index = self.file_list.row(item)
                self.file_list.takeItem(index)
                del item
        self.show_current_all()
        if update_plots:
            self.update_plots()

    def open_files_from_folder(self): 			
        rootdir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory to Open")
        filepaths = []
        for subdir, dirs, files in os.walk(rootdir):
            for file in files:
                filename, file_extension = os.path.splitext(file)
                if file_extension == '.dat':
                    already_loaded=self.check_already_loaded(subdir,[file[1] for file in filepaths])
                    if not already_loaded:
                        filepath = os.path.join(subdir, file)
                        try: # on Windows
                            st_ctime = os.path.getctime(filepath)
                        except Exception:
                            try: # on Mac
                                st_ctime = os.stat(filepath).st_birthtime
                            except Exception as e:
                                print(e)
                        filepaths.append((st_ctime,filepath,subdir))
        if not os.path.split(filepaths[0][2])[1].startswith('#'): #If it's qcodespp data, it's already sorted. If not, sort by time
            filepaths.sort(key=lambda tup: tup[0])
        self.open_files([file[1] for file in filepaths],load_the_data=False)
    
    def check_already_loaded(self, subdir, filepaths):
        loaded=False
        for filepath in filepaths:
            if subdir in filepath:
                loaded=True
        return loaded
        
    def update_link_to_folder(self, new_folder=True):
        if new_folder:
            self.linked_folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory to Link")
        if self.linked_folder:
            self.window_title = f'InSpectra Gadget - Linked to folder {self.linked_folder}'
            self.setWindowTitle(self.window_title+self.window_title_auto_refresh)
            new_files = []
            for subdir, dirs, files in os.walk(self.linked_folder):
                for file in files:
                    filename, file_extension = os.path.splitext(file)
                    if file_extension == '.dat':
                        already_loaded=self.check_already_loaded(subdir,[file[1] for file in new_files])
                        if not already_loaded:
                            filepath = os.path.join(subdir, file)
                            # Need to deal with qcodespp data differently during refresh since multiple
                            # .dat files may belong to the same dataset
                            if os.path.isfile(subdir+'/snapshot.json'):
                                already_linked=False
                                for file in self.linked_files:
                                    if subdir in file:
                                        already_linked=True
                                if not already_linked:
                                    try: # on Windows
                                        st_ctime = os.path.getctime(filepath)
                                    except Exception:
                                        try: # on Mac
                                            st_ctime = os.stat(filepath).st_birthtime
                                        except Exception as e:
                                            print(e)
                                    new_files.append((st_ctime,filepath,subdir))

                            else:
                                if filepath not in self.linked_files:
                                    try: # on Windows
                                        st_ctime = os.path.getctime(filepath)
                                    except Exception:
                                        try: # on Mac
                                            st_ctime = os.stat(filepath).st_birthtime
                                        except Exception as e:
                                            print(e)
                                    new_files.append((st_ctime,filepath,subdir))
            if new_files:
                if not os.path.split(new_files[0][2])[1].startswith('#'): #If it's qcodespp data, it's already sorted. If not, sort by time
                    new_files.sort(key=lambda tup: tup[0])
                new_filepaths = [new_file[1] for new_file in new_files]
                self.open_files(new_filepaths,load_the_data=False)
                for new_filepath in new_filepaths:
                    self.linked_files.append(new_filepath)              
                    
    def unlink_folder(self):
        if self.linked_folder:
            self.linked_folder = None
            self.window_title = 'InSpectra Gadget'
            self.setWindowTitle(self.window_title+
                                self.window_title_auto_refresh)
            
    def save_session(self, which='current'):
        current_item = self.file_list.currentItem()
        if current_item:
            if which == 'current':
                suggested_filename = os.path.splitext(current_item.data.filepath)[0].replace(':','')
                filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save Session As...', suggested_filename, '*.igs')
                items = [current_item]
            elif which == 'all':
                filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save Session As...', '', '*.igs')
                items = [self.file_list.item(n) for n in range(self.file_list.count())]
            elif which == 'checked':
                filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save Session As...', '', '*.igs')
                items = [self.file_list.item(n) for n in range(self.file_list.count()) 
                         if self.file_list.item(n).checkState() == 2]         
            if filepath:
                dirpath = os.path.dirname(filepath)
                dictionary_list = []
                os.makedirs(dirpath+'/igtemp', exist_ok=True)
                for item in items:
                    item_dictionary = {}
                    if hasattr(item,'filepath'):
                        item_dictionary['filepath']=item.filepath
                    if hasattr(item,'checkState'):
                        item_dictionary['checkState']=item.checkState()
                    attributes=['label','settings','filters','view_settings','axlim_settings',
                                'raw_data','processed_data']
                    for attribute in attributes:
                        if hasattr(item.data,attribute):
                            item_dictionary[attribute]=getattr(item.data,attribute)

                    self.i=0
                    if hasattr(item.data,'linecuts'):
                        item_dictionary['linecuts'] = self.remove_linecutwindows_and_fits(item.data.linecuts,dirpath)

                    if hasattr(item.data,'plotted_lines'):
                        item_dictionary['plotted_lines'] = self.remove_linecutwindows_and_fits(item.data.plotted_lines,dirpath)
                    
                    dictionary_list.append(item_dictionary)

                # Save all needed files to a temperorary directory and add them to the tarball
                np.save(dirpath+'/igtemp/numpyfile.npy', dictionary_list)
                with tarfile.open(filepath, 'w:gz') as tar:
                    for filename in os.listdir(dirpath+'/igtemp'):
                        tar.add('./igtemp/'+filename, recursive=False)

                print(f'Session saved as {filepath}')

                # Delete unnecessary information
                for filename in os.listdir(dirpath+'/igtemp'):
                    file_path = os.path.join(dirpath+'/igtemp', filename)
                    os.remove(file_path)
                os.rmdir(dirpath+'/igtemp')
                del dictionary_list,lmfit_names

    def remove_linecutwindows_and_fits(self,d,dirpath,exclude_key='linecut_window',exclude_key2='fit_result'):
    # Remove linecut window object and lmfit object from the dictionary. Neither can be pickled. lmfit fit results are saved to
    # file, added to the tarball, and loaded again when the session is loaded.
        new_dict = {}
        for key, value in d.items():
            if isinstance(value, dict):
                # Recurse into nested dictionaries
                new_dict[key] = self.remove_linecutwindows_and_fits(value, dirpath,exclude_key,exclude_key2)
            else:
                # For non-dictionary values, just copy them
                new_dict[key] = value

        if exclude_key in new_dict:
            new_dict[exclude_key] = None  # Remove the linecut window object
            # if new_dict[exclude_key] is not None:
            #     new_dict[exclude_key]=True
            # else:
            #     new_dict[exclude_key]=False
        if exclude_key2 in new_dict:
            try:
                save_modelresult(new_dict[exclude_key2], dirpath+'/igtemp/lmfit_result'+str(self.i).zfill(4)+'.sav') # Save the lmfit object to a file
                new_dict[exclude_key2]='lmfit_result'+str(self.i).zfill(4) # Replace the lmfit model with the name.
                self.i+=1
            except Exception as e:
                print('Error saving lmfit object:', e)
        return new_dict

    def load_session(self):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Session', '', 'Inspectra Gadget session (*.igs)')
        if filepath:
            dirpath = os.path.dirname(filepath)
            if self.file_list.count() > 0:
                self.remove_files('all')
            with tarfile.open(filepath, 'r') as tar:
                tar.extractall(dirpath)
            try:
                data=np.load(dirpath+'/igtemp/numpyfile.npy', allow_pickle=True)
                file_list=[]
                for attr_dict in data:
                    file_list.append(attr_dict['filepath'])
                self.open_files(file_list,load_the_data=False,attr_dicts=data,dirpath=dirpath)
            except Exception as e:
                print('Error loading session:', e)

            for filename in os.listdir(dirpath+'/igtemp'):
                file_path = os.path.join(dirpath+'/igtemp', filename)
                os.remove(file_path)
            os.rmdir(dirpath+'/igtemp')
    

    def save_processed_data(self, which='current'):
        current_item = self.file_list.currentItem()
        if current_item:
            formats='Numpy text (*.dat);;Numpy format (*.npy);;CSV (*.csv)'
            if which == 'current':
                suggested_filename = current_item.data.label
                filepath, ext = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Export Data As', suggested_filename, formats)
                item = current_item
                if hasattr(item.data,'processed_data'):
                    if '.dat' in ext:
                        header=''
                        for label in ['xlabel','ylabel','clabel']:
                            if item.data.settings[label] != '':
                                header+=f'{item.data.settings[label]}\t'
                        header=header.strip('\t')
                        with open(filepath, "w") as dat_file:
                            if len(current_item.data.get_columns()) == 2:
                                np.savetxt(filepath, np.column_stack(current_item.data.processed_data),header=header)
                            elif len(current_item.data.get_columns()) == 3:
                                dat_file.write(f'# {header}\n')
                                for j in range(np.shape(item.data.processed_data[2])[0]):
                                    for k in range(np.shape(item.data.processed_data[2])[1]):
                                        dat_file.write('{}\t{}\t{}\n'.format(item.data.processed_data[0][j,k],item.data.processed_data[1][j,k],item.data.processed_data[2][j,k]))
                    elif '.npy' in ext:
                            if len(current_item.data.get_columns()) == 2:
                                np.save(filepath, np.column_stack(current_item.data.processed_data))
                            elif len(current_item.data.get_columns()) == 3:
                                np.save(filepath, np.stack(current_item.data.processed_data, axis=2))
                    elif '.csv' in ext:
                        with open(filepath, 'w', newline='') as f:
                            writer = csvwriter(f,delimiter='\t')
                            header=[]
                            for label in ['xlabel','ylabel','clabel']:
                                if item.data.settings[label] != '':
                                    header.append(f'#{item.data.settings[label]}')
                            writer.writerow(header)
                            if len(current_item.data.get_columns())==2:
                                for i,x in enumerate(item.data.processed_data[0]):
                                    writer.writerow([x,item.data.processed_data[1][i]])
                            elif len(current_item.data.get_columns()) == 3:
                                for j in range(np.shape(item.data.processed_data[2])[0]):
                                    for k in range(np.shape(item.data.processed_data[2])[1]):
                                        writer.writerow([item.data.processed_data[0][j,k],item.data.processed_data[1][j,k],item.data.processed_data[2][j,k]])

                else:
                    print('No processed data to export')
            # else:
            #     if which == 'all':
            #         filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            #             self, 'Export Data As: Specify Base Filename', '', formats)
            #         items = [self.file_list.item(n) for n in range(self.file_list.count())]
            #     elif which == 'checked':
            #         filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            #             self, 'Export Data As: Specify Base Filename', '', formats)
            #         items = [self.file_list.item(n) for n in range(self.file_list.count()) 
            #                 if self.file_list.item(n).checkState() == 2]
            #     for i,item in enumerate(items):
            #         if hasattr(item.data,'processed_data'):
            #             np.savetxt(filepath+'_'+str(i).zfill(2),item.data.processed_data)
                
    def file_checked(self, item):
        if item.checkState() == 2:
            self.file_list.setCurrentItem(item)
        self.update_plots()
    
    def file_clicked(self):
        self.show_current_all()
        current_item = self.file_list.currentItem()
        for i in reversed(range(self.oneD_layout.count())): 
            widgetToRemove = self.oneD_layout.itemAt(i).widget()
            # remove it from the layout list
            self.oneD_layout.removeWidget(widgetToRemove)
            # remove it from the gui
            widgetToRemove.setParent(None)
        if hasattr(current_item.data,'sidebar1D'):
            self.oneD_layout.addWidget(current_item.data.sidebar1D)
            
    def file_double_clicked(self, item):
        self.file_list.itemChanged.disconnect(self.file_checked)
        for item_index in range(self.file_list.count()):
            self.file_list.item(item_index).setCheckState(QtCore.Qt.Unchecked)
        item.setCheckState(QtCore.Qt.Checked)
        self.file_list.itemChanged.connect(self.file_checked)
        self.update_plots()
    
    def reinstate_markers(self, item, orientation):
        orientations={'horizontal':'horimarkers','vertical':'vertmarkers'}
        arrayname=orientations[orientation]
        setattr(item.data,arrayname,[])
        if orientation == 'horizontal':
            for line in item.data.linecuts['horizontal']['lines']:
                z=item.data.linecuts[orientation]['lines'][line]['cut_axis_value']
                item.data.horimarkers.append(item.data.axes.axhline(y=z, linestyle='dashed', linewidth=1, xmax=0.1,
                    color=item.data.linecuts[orientation]['lines'][line]['linecolor']))
                item.data.horimarkers.append(item.data.axes.axhline(y=z, linestyle='dashed', linewidth=1, xmin=0.9,
                    color=item.data.linecuts[orientation]['lines'][line]['linecolor']))  

        elif orientation == 'vertical':
            for line in item.data.linecuts['vertical']['lines']:
                z=item.data.linecuts[orientation]['lines'][line]['cut_axis_value']
                item.data.vertmarkers.append(item.data.axes.axvline(x=z, linestyle='dashed', linewidth=1, ymax=0.1,
                    color=item.data.linecuts[orientation]['lines'][line]['linecolor']))
                item.data.vertmarkers.append(item.data.axes.axvline(x=z, linestyle='dashed', linewidth=1, ymin=0.9,
                    color=item.data.linecuts[orientation]['lines'][line]['linecolor']))

    def update_plots(self, item=None,update_data=True):
        self.figure.clf()
        
        checked_items = self.get_checked_items()
        if checked_items:
            rows, cols = self.subplot_grid[len(checked_items)-1]
            for index, item in enumerate(checked_items):
                try:
                    if update_data:
                        item.data.prepare_data_for_plot()
                    item.data.figure = self.figure
                    item.data.axes = item.data.figure.add_subplot(rows, cols, index+1)
                    item.data.add_plot(dim=len(item.data.get_columns()),editor_window=self)
                    if hasattr(item.data, 'linecuts'):
                        for orientation in ['horizontal','vertical']:#,'diagonal','circular']:
                            if len(item.data.linecuts[orientation]['lines']) > 0:
                                self.reinstate_markers(item,orientation)
                            if item.data.linecuts[orientation]['linecut_window'] is not None:
                                item.data.linecuts[orientation]['linecut_window'].update()
                except Exception as e:
                    print(f'Could not plot {item.data.filepath}:', e)
                    raise
        self.show_current_all()
        self.figure.tight_layout()
        self.canvas.draw()
        if hasattr(self, 'live_track_item') and self.live_track_item:
            if (self.live_track_item.checkState() and 
                self.track_button.text() == 'Stop tracking' and 
                hasattr(self.live_track_item.data, 'remaining_time_string')):
                self.remaining_time_label.setText(self.live_track_item.data.remaining_time_string)
            else:
                self.remaining_time_label.setText('')
          
    def refresh_files(self):
        checked_items = self.get_checked_items()
        if checked_items:
            for item in checked_items:
                item.data.prepare_data_for_plot(reload_data=True)
            self.update_plots()
        if self.linked_folder:
            old_number_of_items = self.file_list.count()
            self.update_link_to_folder(new_folder=False)
            if self.file_list.count() > old_number_of_items:
                last_item = self.file_list.item(self.file_list.count()-1)
                self.file_double_clicked(last_item)
                self.file_list.setCurrentItem(last_item)
                self.track_button_clicked()
    
    # The below is not working and not implemented, but could be useful to fix and include.
    # def to_next_file(self):
    #     checked_items, indices = self.get_checked_items(return_indices=True)
    #     if (len(checked_items) == 1 and self.file_list.count() > 1 and 
    #         indices[0]+1 < self.file_list.count()):
    #         item = checked_items[0]
    #         next_item = self.file_list.item(indices[0]+1)
    #         self.file_list.itemChanged.disconnect(self.file_checked)
    #         item.setCheckState(QtCore.Qt.Unchecked)
    #         next_item.setCheckState(QtCore.Qt.Checked)
    #         self.file_list.setCurrentItem(next_item)
    #         self.file_list.itemChanged.connect(self.file_checked)
    #         self.update_plots()
        
    # def to_previous_file(self):
    #     checked_items, indices = self.get_checked_items(return_indices=True)
    #     if (len(checked_items) == 1 and self.file_list.count() > 1 
    #         and indices[0] > 0):
    #         item = checked_items[0]
    #         previous_item = self.file_list.item(indices[0]-1)
    #         self.file_list.itemChanged.disconnect(self.file_checked)
    #         item.setCheckState(QtCore.Qt.Unchecked)
    #         previous_item.setCheckState(QtCore.Qt.Checked)
    #         self.file_list.setCurrentItem(previous_item)
    #         self.file_list.itemChanged.connect(self.file_checked)
    #         self.update_plots()
            
    def get_checked_items(self, return_indices = False):
        indices = [index for index in range(self.file_list.count()) 
                   if self.file_list.item(index).checkState() == 2]
        checked_items = [self.file_list.item(index) for index in indices]
        if return_indices:    
            return checked_items, indices
        else:
            return checked_items
        
    def get_unchecked_items(self, return_indices = False):
        indices = [index for index in range(self.file_list.count()) 
                   if self.file_list.item(index).checkState() != 2]
        unchecked_items = [self.file_list.item(index) for index in indices]
        if return_indices:    
            return unchecked_items, indices
        else:
            return unchecked_items
    
    def get_all_items(self, return_indices = False):
        indices = [index for index in range(self.file_list.count())]
        all_items = [self.file_list.item(index) for index in indices]
        if return_indices:    
            return all_items, indices
        else:
            return all_items
        
    def refresh_interval_changed(self, interval):
        AUTO_REFRESH_INTERVAL_3D=float(interval)
        if self.track_button.text() == 'Stop tracking':
            self.track_button_clicked()
        
    def track_button_clicked(self):
        current_item = self.file_list.currentItem()
        if (self.track_button.text() == 'Track data' and 
            current_item and current_item.checkState() and
            not current_item.data.file_finished()):
            self.live_track_item = current_item
            self.live_track_item.setText('[LIVE] '+self.live_track_item.data.label)
            self.live_track_item.data.prepare_data_for_plot(reload_data=True)
            if self.live_track_item.data.raw_data:
                if len(self.live_track_item.data.get_columns()) == 3: # if file is 3D
                    self.start_auto_refresh(AUTO_REFRESH_INTERVAL_3D)
                elif len(self.live_track_item.data.get_columns()) == 2: # if file is 2D
                    self.start_auto_refresh(AUTO_REFRESH_INTERVAL_2D)
            else:
                self.start_auto_refresh(AUTO_REFRESH_INTERVAL_2D, 
                                        wait_for_file=True)
        elif self.track_button.text() == 'Stop tracking':
            self.stop_auto_refresh()
        
    def start_auto_refresh(self, time_interval, wait_for_file=False):
        self.track_button.setText('Stop tracking')
        self.auto_refresh_timer = QtCore.QTimer()
        self.auto_refresh_timer.setInterval(time_interval*1000)
        if wait_for_file:
            self.auto_refresh_timer.timeout.connect(self.wait_for_file_call)
        else:
            self.auto_refresh_timer.timeout.connect(self.auto_refresh_call)
        self.action_refresh_stop.setEnabled(True)
        self.auto_refresh_timer.start()
        self.window_title_auto_refresh = ' - Auto-Refreshing Enabled'
        self.setWindowTitle(self.window_title+self.window_title_auto_refresh)
        self.auto_refresh_call()
        
    def wait_for_file_call(self):
        if self.live_track_item and self.live_track_item.checkState():
            self.live_track_item.data.prepare_data_for_plot(reload_data=True)
            if self.live_track_item.data.raw_data:
                self.auto_refresh_timer.stop()
                self.track_button.setText('Track data')
                self.track_button_clicked()            
            
    def auto_refresh_call(self):
        if self.live_track_item and self.live_track_item.checkState():
            if self.live_track_item.data.file_finished():
                print('Stop auto refresh...')
                self.live_track_item.data.remaining_time_string = ''
                self.stop_auto_refresh()
            else:
                if hasattr(self.live_track_item.data, 'remaining_time_string'):
                    self.remaining_time_label.setText(self.live_track_item.data.remaining_time_string)
                else:
                    self.remaining_time_label.setText('')
            self.window_title_auto_refresh = ' - Auto-Refreshing Enabled (Refreshing...)'
            self.setWindowTitle(self.window_title+self.window_title_auto_refresh)
            self.refresh_files()
            self.window_title_auto_refresh = ' - Auto-Refreshing Enabled'
            self.setWindowTitle(self.window_title+self.window_title_auto_refresh)
        
    def stop_auto_refresh(self):
        self.track_button.setText('Track data')
        self.auto_refresh_timer.stop()
        self.action_refresh_stop.setEnabled(False)
        self.window_title_auto_refresh = ''
        self.setWindowTitle(self.window_title+self.window_title_auto_refresh)
        self.remaining_time_label.setText('')
        self.live_track_item.setText(self.live_track_item.data.label)
        
    def move_file(self, direction):
        current_item = self.file_list.currentItem()
        if current_item:
            current_row = self.file_list.currentRow()
            if direction == 'up' and current_row > 0:
                new_row = current_row-1
            elif direction == 'down' and current_row < self.file_list.count()-1:
                new_row = current_row+1
            else:
                new_row = current_row
            if new_row != current_row:
                if (current_item.checkState() == 2 and 
                    self.file_list.item(new_row).checkState() == 2):
                    update_canvas = True
                else:
                    update_canvas = False
                self.file_list.takeItem(current_row)
                self.file_list.insertItem(new_row, current_item)
                self.file_list.setCurrentRow(new_row)
                if update_canvas:
                    self.update_plots()
        
    def show_current_all(self):
        self.show_current_plot_settings()
        self.show_current_view_settings()
        self.show_current_filters()
        self.show_current_axscale_settings()
        self.show_current_axlim_settings()
        self.populate_new_plot_settings()
        self.show_data_shape()
    
    def show_data_shape(self):
        current_item = self.file_list.currentItem()
        if current_item:
            try:
                self.data_shape_label.setText(f'Data shape: {current_item.data.processed_data[-1].shape}')
            except:
                self.data_shape_label.setText('Data shape:')
        else:
            self.data_shape_label.setText('Data shape:')
   
    def populate_new_plot_settings(self):
        boxes= [self.new_plot_X_box, self.new_plot_Y_box, self.new_plot_Z_box]
        for combobox in boxes:
            combobox.clear()

        current_item = self.file_list.currentItem()
        if current_item:
            if isinstance(current_item.data, qcodesppData): #Currently only supports qcodespp data
                dim = len(current_item.data.get_columns())
                if dim == 2:
                    boxes= [self.new_plot_X_box, self.new_plot_Y_box]
                else:
                    boxes= [self.new_plot_X_box, self.new_plot_Y_box, self.new_plot_Z_box]
                for combobox in boxes:
                    combobox.addItems(current_item.data.all_parameter_names)
                self.new_plot_X_box.setCurrentIndex(0)
                self.new_plot_Y_box.setCurrentIndex(1)
                if dim == 3:
                    self.new_plot_Z_box.setCurrentIndex(2)
    
    def show_current_plot_settings(self):
        self.settings_table.clear()
        self.settings_table.setRowCount(0)
        current_item = self.file_list.currentItem()
        if current_item:
            self.settings_table.itemChanged.disconnect(self.plot_setting_edited)
            self.settings_table.setRowCount(0)
            old_settings = current_item.data.settings
            preferred_order= ['X data', 'Y data', 'Z data',
                              'title', 'xlabel', 'ylabel', 'clabel']
            settings = OrderedDict()
            for key in preferred_order:
                if key in old_settings:
                    settings[key] = old_settings[key]
            for key, value in old_settings.items():
                if key not in preferred_order:
                    settings[key] = value
            for key, value in list(settings.items()):
                row = self.settings_table.rowCount()
                self.settings_table.insertRow(row)
                property_item = QtWidgets.QTableWidgetItem(key)
                property_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                                       QtCore.Qt.ItemIsEnabled)
                self.settings_table.setItem(row, 0, property_item)
                self.settings_table.setItem(row, 1, QtWidgets.QTableWidgetItem(value))
            self.settings_table.itemChanged.connect(self.plot_setting_edited)
            
    def show_current_view_settings(self):
        current_item = self.file_list.currentItem()
        if current_item:
            settings = current_item.data.view_settings
            self.min_line_edit.setText(f'{settings["Minimum"]:.4g}')
            self.max_line_edit.setText(f'{settings["Maximum"]:.4g}')
            self.mid_line_edit.setText(f'{settings["Midpoint"]:.4g}')
            if settings['Locked']:
                self.lock_checkbox.setCheckState(QtCore.Qt.Checked)
            else:
                self.lock_checkbox.setCheckState(QtCore.Qt.Unchecked)
            if settings['MidLock']:
                self.mid_checkbox.setCheckState(QtCore.Qt.Checked)
            else:
                self.mid_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.colormap_type_box.currentIndexChanged.disconnect(self.colormap_type_edited)
            self.colormap_type_box.setCurrentText(settings['Colormap Type'])
            self.colormap_type_box.currentIndexChanged.connect(self.colormap_type_edited)
            self.fill_colormap_box()
            self.colormap_box.currentIndexChanged.disconnect(self.colormap_edited)
            self.colormap_box.setCurrentText(settings['Colormap'])
            self.colormap_box.currentIndexChanged.connect(self.colormap_edited)
            if settings['Reverse']:
                self.reverse_colors_box.setCheckState(QtCore.Qt.Checked)
            else:
                self.reverse_colors_box.setCheckState(QtCore.Qt.Unchecked)
        else:
            self.min_line_edit.setText('')
            self.max_line_edit.setText('')
            self.lock_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.mid_checkbox.setCheckState(QtCore.Qt.Unchecked)
    
    def show_current_axlim_settings(self):
        current_item = self.file_list.currentItem()
        if current_item:
            axlim_settings = current_item.data.axlim_settings
            if axlim_settings['Xmin'] is None:
                self.xmin_line_edit.setText('')
            else:
                self.xmin_line_edit.setText(f'{axlim_settings["Xmin"]:.5g}')
            if axlim_settings['Xmax'] is None:
                self.xmax_line_edit.setText('')
            else:
                self.xmax_line_edit.setText(f'{axlim_settings["Xmax"]:.5g}')
            if axlim_settings['Ymin'] is None:
                self.ymin_line_edit.setText('')
            else:
                self.ymin_line_edit.setText(f'{axlim_settings["Ymin"]:.5g}')
            if axlim_settings['Ymax'] is None:
                self.ymax_line_edit.setText('')
            else:
                self.ymax_line_edit.setText(f'{axlim_settings["Ymax"]:.5g}')

    def show_current_axscale_settings(self):
        current_item = self.file_list.currentItem()
        if current_item:
            axlim_settings = current_item.data.axlim_settings

            self.xaxis_combobox.currentIndexChanged.disconnect(self.axis_scaling_changed)
            self.xaxis_combobox.setCurrentText(axlim_settings['Xscale'])
            self.xaxis_combobox.currentIndexChanged.connect(self.axis_scaling_changed)

            self.yaxis_combobox.currentIndexChanged.disconnect(self.axis_scaling_changed)
            self.yaxis_combobox.setCurrentText(axlim_settings['Yscale'])
            self.yaxis_combobox.currentIndexChanged.connect(self.axis_scaling_changed)
            
    def show_current_filters(self):
        self.filters_table.setRowCount(0)
        current_item = self.file_list.currentItem()
        if current_item:
            if hasattr(current_item.data, 'sidebar1D'):
                current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                try:
                    filters= current_item.data.plotted_lines[current_line]['filters']
                except:
                    filters=[]
            else:
                filters = current_item.data.filters
            for _ in filters:
                self.append_filter_to_table()
    
    def plot_setting_edited(self,setting_name=None):
        current_item = self.file_list.currentItem()
        if current_item:
            current_item.data.old_settings = current_item.data.settings.copy()
            row = self.settings_table.currentRow()
            if setting_name is not None:
                setting_name = self.settings_table.item(row, 0).text()
            value = self.settings_table.item(row, 1).text()
            current_item.data.settings[setting_name] = value
            self.settings_table.clearFocus()
            try:
                if setting_name == 'X data' or setting_name == 'Y data' or setting_name == 'Z data':
                    current_item.data.prepare_data_for_plot(reload_data=True,reload_from_file=False)
                    # IF the plotted data has happened, all fits are likely to be irrelevant. Not sure whether to remove by force or not.
                    # I think keep the fits, because it's easy for the user to remove them, but could be a total pain to re-do if the user has
                    # changed an axis by mistake. It's also the case for applying a filter.
                    self.update_plots()
                    self.reset_axlim_settings()
                if setting_name == 'columns' or setting_name == 'delimiter':
                    current_item.data.prepare_data_for_plot(reload_data=True,reload_from_file=False)
                    self.update_plots()
                    self.reset_axlim_settings()
                elif setting_name == 'linecolor':
                    for line in current_item.data.axes.get_lines():
                        line.set_color(value)
                    self.canvas.draw()
                elif setting_name == 'maskcolor' or setting_name == 'lut':
                    current_item.data.apply_colormap()
                elif (setting_name == 'rasterized' or setting_name == 'colorbar'
                      or setting_name == 'minorticks'):
                    self.update_plots()
                elif setting_name == 'shading':
                    self.update_plots()
                current_item.data.extension_setting_edited(self, setting_name)
                current_item.data.apply_plot_settings()
                self.canvas.draw()
            except Exception as e: # if invalid value is typed: reset to previous settings
                print('Invalid value of plot setting!', e)
                self.paste_plot_settings(which='old')

    def axlim_setting_edited(self, edited_setting):
        current_item = self.file_list.currentItem()
        axlim_settings = current_item.data.axlim_settings
        current_item.data.old_axlim_settings = axlim_settings.copy()
        if current_item:
            try:
                if edited_setting == 'Xmin':
                    text_box = self.xmin_line_edit
                elif edited_setting == 'Xmax':
                    text_box = self.xmax_line_edit
                elif edited_setting == 'Ymin':
                    text_box = self.ymin_line_edit
                else:
                    text_box = self.ymax_line_edit

                if text_box.text() == '':
                    new_value=None
                else:
                    new_value = float(text_box.text())
                axlim_settings[edited_setting] = new_value
                if new_value is None:
                    text_box.setText('')
                else:
                    text_box.setText(f'{new_value:.4g}')
                text_box.clearFocus()
                current_item.data.apply_axlim_settings()
                self.canvas.draw()
            except Exception as e:
                print('Invalid axis limit!', e)
                self.paste_axlim_settings(which='old')

    def reset_axlim_settings(self):
        current_item = self.file_list.currentItem()
        if current_item:
            current_item.data.reset_axlim_settings()
            self.show_current_axlim_settings()
            self.canvas.draw()

    def axis_scaling_changed(self):
        current_item = self.file_list.currentItem()
        if current_item:
            settings = current_item.data.axlim_settings
            settings['Xscale'] = self.xaxis_combobox.currentText()
            settings['Yscale'] = self.yaxis_combobox.currentText()
            #if current_item.checkState():
            current_item.data.apply_axscale_settings()
            self.canvas.draw()
    
    def view_setting_edited(self, edited_setting):
        current_item = self.file_list.currentItem()
        view_settings = current_item.data.view_settings
        current_item.data.old_view_settings = view_settings.copy()
        if current_item:
            try:
                if edited_setting == 'Minimum' or edited_setting == 'Maximum':
                    if edited_setting == 'Minimum':
                        text_box = self.min_line_edit
                    else:
                        text_box = self.max_line_edit
                    new_value = float(text_box.text())
                    view_settings[edited_setting] = new_value
                    text_box.setText(f'{new_value:.4g}')
                    text_box.clearFocus()
                    current_item.data.reset_midpoint()
                    self.mid_line_edit.setText(f'{view_settings["Midpoint"]:.4g}')
                elif edited_setting == 'Midpoint':
                    if self.mid_line_edit.text():
                        new_value = float(self.mid_line_edit.text())
                        view_settings[edited_setting] = new_value
                    else:
                        current_item.data.reset_midpoint()
                        new_value = view_settings[edited_setting]
                    self.mid_line_edit.setText(f'{new_value:.4g}')
                    self.mid_line_edit.clearFocus()
                elif edited_setting == 'Locked':
                    if self.lock_checkbox.isChecked():
                        view_settings[edited_setting] = True
                    else:
                        view_settings[edited_setting] = False
                elif edited_setting == 'MidLock':
                    if self.mid_checkbox.isChecked():
                        view_settings[edited_setting] = True
                    else:
                        view_settings[edited_setting] = False
                current_item.data.apply_view_settings()
                self.canvas.draw()
            except Exception as e:
                print('Invalid value of view setting!', e)
                self.paste_view_settings(which='old')
                
    def fill_colormap_box(self):
        self.colormap_box.currentIndexChanged.disconnect(self.colormap_edited)
        self.colormap_box.clear()
        self.colormap_box.addItems(self.cmaps[self.colormap_type_box.currentText()])
        self.colormap_box.currentIndexChanged.connect(self.colormap_edited)
    
    def colormap_type_edited(self):
        self.fill_colormap_box()
        self.colormap_edited()
        
    def colormap_edited(self):
        current_item = self.file_list.currentItem()
        if current_item:
            settings = current_item.data.view_settings
            settings['Colormap Type'] = self.colormap_type_box.currentText()
            settings['Colormap'] = self.colormap_box.currentText()
            settings['Reverse'] = self.reverse_colors_box.isChecked()
            if current_item.checkState():
                current_item.data.apply_colormap()
                self.canvas.draw()
    
    def filters_table_edited(self, item):
        current_item = self.file_list.currentItem()
        current_item.data.old_filters = copy.deepcopy(current_item.data.filters)
        if current_item:
            if hasattr(current_item.data, 'sidebar1D'):
                current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                filters= current_item.data.plotted_lines[current_line]['filters']
            else:
                filters = current_item.data.filters
            try:
                row = item.row()
                filt = filters[row]
                filter_item = self.filters_table.item(row, 0)
                filt.method = self.filters_table.cellWidget(row, 1).currentText()
                filt.settings = [self.filters_table.item(row, 2).text(), 
                                 self.filters_table.item(row, 3).text()]
                filt.checkstate = filter_item.checkState()
                self.filters_table.clearFocus()
                current_item.data.apply_all_filters()
                current_item.data.reset_view_settings()
                if current_item.checkState():
                    self.update_plots()
                    self.show_current_filters()
                    self.show_current_view_settings()
                    self.reset_axlim_settings()
            except Exception as e:
                print('Invalid value of filter!', e)
                self.paste_filters(which='old')
    
    def copy_plot_settings(self):
        current_item = self.file_list.currentItem()
        if current_item:
            self.copied_settings = current_item.data.settings.copy()
    
    def copy_filters(self):
        current_item = self.file_list.currentItem()
        if current_item:
            if hasattr(current_item.data, 'sidebar1D'):
                current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                filters= current_item.data.plotted_lines[current_line]['filters']
            else:
                filters = current_item.data.filters
            self.copied_filters = copy.deepcopy(filters)
            
    def copy_view_settings(self):
        current_item = self.file_list.currentItem()
        if current_item:
            self.copied_view_settings = current_item.data.view_settings.copy()

    def copy_axlim_settings(self):
        current_item = self.file_list.currentItem()
        if current_item:
            self.copied_axlim_settings = current_item.data.axlim_settings.copy()
    
    def paste_plot_settings(self, which='copied'):
        current_item = self.file_list.currentItem()
        if current_item:
            if which == 'copied':
                if self.copied_settings:
                    current_item.data.settings = self.copied_settings.copy()
            elif which == 'default':
                current_item.data.settings = current_item.data.DEFAULT_PLOT_SETTINGS.copy()
            elif which == 'old':
                current_item.data.settings = current_item.data.old_settings.copy()
            self.show_current_plot_settings()
            if current_item.checkState():
                current_item.data.apply_plot_settings()
                self.canvas.draw()
    
    def paste_filters(self, which='copied'):
        current_item = self.file_list.currentItem()
        if current_item:
            if hasattr(current_item.data, 'sidebar1D'):
                current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                filters= current_item.data.plotted_lines[current_line]['filters']
            else:
                filters = current_item.data.filters
            if which == 'copied':
                if self.copied_filters:
                    filters = copy.deepcopy(self.copied_filters)
            elif which == 'old':
                filters = copy.deepcopy(current_item.data.old_filters)
            self.show_current_filters()
            current_item.data.apply_all_filters()
            self.show_current_view_settings()
            if current_item.checkState():
                self.update_plots()
                self.canvas.draw()

    def paste_view_settings(self, which='copied'):
        current_item = self.file_list.currentItem()
        if current_item:
            if which == 'copied':
                if self.copied_view_settings:
                    current_item.data.view_settings = self.copied_view_settings.copy()
            elif which == 'old':
                current_item.data.view_settings = current_item.data.old_view_settings.copy()
            self.show_current_view_settings()
            if current_item.checkState():
                current_item.data.apply_view_settings()
                current_item.data.apply_colormap()
                self.canvas.draw()

    def paste_axlim_settings(self, which='copied'):
        current_item = self.file_list.currentItem()
        if current_item:
            if which == 'copied':
                if self.copied_axlim_settings:
                    current_item.data.axlim_settings = self.copied_axlim_settings.copy()
            elif which == 'old':
                current_item.data.axlim_settings = current_item.data.old_axlim_settings.copy()
            self.show_current_axlim_settings()
            if current_item.checkState():
                current_item.data.apply_axlim_settings()
                self.canvas.draw()

    def open_item_menu(self):
        current_item = self.file_list.currentItem()
        if current_item:
            checked_items = self.get_checked_items()
            menu = QtWidgets.QMenu(self)
            actions = ['Duplicate (Ctrl+D)','Remove file','Check all','Uncheck all','Clear list','Remove unchecked']
            if len(checked_items) > 1:
                actions.append('Combine plots')
            for entry in actions:
                action = QtWidgets.QAction(entry, self)
                menu.addAction(action)
            menu.triggered[QtWidgets.QAction].connect(self.do_item_action)
            menu.popup(QtGui.QCursor.pos())
            
    def do_item_action(self, signal):
        current_item = self.file_list.currentItem()
        if current_item:
            if signal.text() == 'Duplicate (Ctrl+D)':
                self.duplicate_item()
            elif signal.text() == 'Remove file':
                self.remove_files(which='current')
            elif signal.text() == 'Check all':
                self.file_list.itemChanged.disconnect(self.file_checked)
                for item_index in range(self.file_list.count()):                        
                    self.file_list.item(item_index).setCheckState(QtCore.Qt.Checked)
                    self.file_list.itemChanged.connect(self.file_checked)
                self.update_plots()
            elif signal.text() == 'Uncheck all':
                checked_items = self.get_checked_items()
                self.file_list.itemChanged.disconnect(self.file_checked)
                for item in checked_items:
                    item.setCheckState(QtCore.Qt.Unchecked)
                self.file_list.itemChanged.connect(self.file_checked)
                self.update_plots()
            elif signal.text() == 'Clear list':
                self.remove_files(which='all')
            elif signal.text() == 'Remove unchecked':
                self.remove_files(which='unchecked')
            elif signal.text() == 'Combine plots':
                try:
                    self.combine_plots()
                except Exception as e:
                    print('Cannot combine these plots:', e)
                    
    def duplicate_item(self, new_plot_button=False):
        original_item = self.file_list.currentItem()
        if original_item:
            if new_plot_button:
                if not isinstance(original_item.data, qcodesppData):
                    print('Feature not available for this data type')
                else:
                    X = self.new_plot_X_box.currentText()
                    Y = self.new_plot_Y_box.currentText()
                    Z = self.new_plot_Z_box.currentText()
            self.open_files(filepaths=[original_item.data.filepath],overrideautocheck=True)
            new_item = self.file_list.currentItem()
            new_item.duplicate = True
            new_item.data.settings = original_item.data.settings.copy()
            new_item.data.view_settings = original_item.data.view_settings.copy()
            new_item.data.filters = copy.deepcopy(original_item.data.filters)
            if isinstance(original_item.data, qcodesppData):
                original_label= original_item.data.label
                if hasattr(original_item,'duplicate'):
                    index_str=original_label.split('-')[0]
                else:
                    index_str=original_label.split('_')[0]
                items=[item for item in self.get_all_items() if index_str in item.data.label]
                duplicate_index=len(list(items))-1
                if hasattr(original_item,'duplicate'):
                    new_label=f'{original_label.split('-')[0]}-{duplicate_index}-{original_label.split("-")[2]}'
                else:
                    new_label= f'{original_label.split('_')[0]}-{duplicate_index}-{original_label.split("_")[1]}'
                new_item.setText(new_label)
                new_item.data.label = new_label
                new_item.data.settings['title']=f'{new_item.data.dataset_id}-{duplicate_index}'
                if new_plot_button:
                    new_item.data.settings['X data'] = X
                    new_item.data.settings['Y data'] = Y
                    if 'Z data' in new_item.data.settings.keys():
                        new_item.data.settings['Z data'] = Z

            else:
                new_item.setText(f'[DUPLICATE] {new_item.data.label}')
                new_item.data.label = f'[DUPLICATE] {new_item.data.label}'
                
            new_item.setCheckState(QtCore.Qt.Checked)
            self.update_plots()
                
    def combine_plots(self):
        checked_items = self.get_checked_items()
        if checked_items:
            try:
                data_list = []
                three_dimensional_data = False
                for item in checked_items:
                    data_list.append(item.data)
                    if len(item.data.get_columns()) != 2:
                         three_dimensional_data = True
                # if not three_dimensional_data:
                    #self.multi_plot_window = MultiPlotWindow(data_list)
                    #self.multi_plot_window.draw_plot()
                    #self.multi_plot_window.show()
                # else:
                #     print('Cannot combine three-dimensional data')
            except Exception as e:
                print('Cannot combine data:', e)
    
    def open_plot_settings_menu(self):
        row = self.settings_table.currentRow()
        column = self.settings_table.currentColumn()
        if column == 1:
            setting_name = self.settings_table.item(row, 0).text()
            menu = QtWidgets.QMenu(self)
            settings = SETTINGS_MENU_OPTIONS.copy()
            current_item = self.file_list.currentItem()
            if current_item and hasattr(current_item.data, 'settings_menu_options'):
                settings.update(current_item.data.settings_menu_options)
            if setting_name in settings.keys():
                for entry in settings[setting_name]:
                    action = QtWidgets.QAction(entry, self)
                    menu.addAction(action)
                menu.triggered[QtWidgets.QAction].connect(self.replace_plot_setting)
                menu.popup(QtGui.QCursor.pos())

    def replace_plot_setting(self, signal):
        item = self.settings_table.currentItem()
        item.setText(signal.text())

    def open_filter_settings_menu(self):
        row = self.filters_table.currentRow()
        column = self.filters_table.currentColumn()
        filter_name = self.filters_table.item(row, 0).text()
        if filter_name in ['Multiply','Divide','Offset'] and column == 2:
            menu = QtWidgets.QMenu(self)
            filter_settings={}
            current_item = self.file_list.currentItem()
            if current_item and hasattr(current_item.data, 'filter_menu_options'):
                filter_settings.update(current_item.data.filter_menu_options)
            if filter_name in filter_settings.keys():
                for entry in filter_settings[filter_name]:
                    action = QtWidgets.QAction(entry, self)
                    menu.addAction(action)
                menu.triggered[QtWidgets.QAction].connect(self.replace_filter_setting)
                menu.popup(QtGui.QCursor.pos())

    def replace_filter_setting(self,signal):
        item = self.filters_table.currentItem()
        item.setText(signal.text())


    def reset_color_limits(self):
        current_item = self.file_list.currentItem()
        if current_item:
            current_item.data.reset_view_settings(overrule=True)
            self.show_current_view_settings()
            if current_item.checkState():
                current_item.data.apply_view_settings()
                self.canvas.draw()
   
    def filters_box_changed(self):
        current_item = self.file_list.currentItem()
        if current_item:
            filt = Filter(self.filters_combobox.currentText())
            if hasattr(current_item.data, 'sidebar1D'): # Then it's 1D data and we apply the filter only to the selected line
                current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                current_item.data.plotted_lines[current_line]['filters'].append(filt)
            else:
                current_item.data.filters.append(filt)
            if current_item.checkState() and filt.checkstate:
                self.update_plots()
            else:
                self.append_filter_to_table()
        self.filters_combobox.currentIndexChanged.disconnect(self.filters_box_changed)
        self.filters_combobox.setCurrentIndex(0)
        self.filters_combobox.clearFocus()
        self.filters_combobox.currentIndexChanged.connect(self.filters_box_changed)
        
    
    def append_filter_to_table(self):
        current_item = self.file_list.currentItem()
        if current_item:
            row = self.filters_table.rowCount()
            if hasattr(current_item.data, 'sidebar1D'):
                current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                filt = current_item.data.plotted_lines[current_line]['filters'][row]
            else:
                filt = current_item.data.filters[row]
            self.filters_table.itemChanged.disconnect(self.filters_table_edited)
            self.filters_table.insertRow(row) 
            filter_item = QtWidgets.QTableWidgetItem(filt.name)
            filter_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                                 QtCore.Qt.ItemIsEnabled | 
                                 QtCore.Qt.ItemIsUserCheckable)
            filter_item.setText(filt.name)
            filter_item.setCheckState(filt.checkstate)
            method_box = NoScrollQComboBox()
            method_box.addItems(filt.method_list)
            method_box.setCurrentIndex(filt.method_list.index(filt.method))
            setting_1 = QtWidgets.QTableWidgetItem(filt.settings[0])
            setting_2 = QtWidgets.QTableWidgetItem(filt.settings[1])
            method_box.currentIndexChanged.connect(lambda: self.filters_table_edited(setting_1))
            self.filters_table.setItem(row, 0, filter_item)
            self.filters_table.setCellWidget(row, 1, method_box)
            self.filters_table.setItem(row, 2, setting_1)
            self.filters_table.setItem(row, 3, setting_2)
            self.filters_table.item(row, 2).setTextAlignment(int(QtCore.Qt.AlignRight) | 
                                                             int(QtCore.Qt.AlignVCenter))
            self.filters_table.item(row, 3).setTextAlignment(int(QtCore.Qt.AlignRight) | 
                                                             int(QtCore.Qt.AlignVCenter))
            self.filters_table.setCurrentCell(row, 0)
            self.filters_table.itemChanged.connect(self.filters_table_edited)
    
    def remove_filters(self, which='current'):
        current_item = self.file_list.currentItem()
        if current_item:
            if hasattr(current_item.data, 'sidebar1D'):
                current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                filters= current_item.data.plotted_lines[current_line]['filters']
            else:
                filters = current_item.data.filters
            if which == 'current':
                filter_row = self.filters_table.currentRow()
                if filter_row != -1:
                    self.filters_table.removeRow(filter_row)
                    del filters[filter_row]
                    current_item.data.apply_all_filters()
                    current_item.data.reset_view_settings()
            elif which == 'all':
                self.filters_table.setRowCount(0)
                filters = []
                current_item.data.apply_all_filters()
                current_item.data.reset_view_settings()
            if current_item.checkState():
                current_item.data.apply_view_settings()
                self.update_plots()
                self.show_current_view_settings()
     
    def move_filter(self, to):
        current_item = self.file_list.currentItem()
        if current_item:
            if hasattr(current_item.data, 'sidebar1D'):
                current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                filters= current_item.data.plotted_lines[current_line]['filters']
            else:
                filters = current_item.data.filters
            row = self.filters_table.currentRow()
            if ((row > 0 and to == -1) or
                (row < self.filters_table.rowCount()-1 and to == 1)):
                filters[row], filters[row+to] = filters[row+to], filters[row]
                self.show_current_filters()
                self.filters_table.setCurrentCell(row+to, 0)
                if (self.filters_table.item(row,0).checkState() and 
                    self.filters_table.item(row+to,0).checkState()):
                    current_item.data.apply_all_filters()
                    self.update_plots()
                    self.show_current_view_settings()

    def save_image(self):
        current_item = self.file_list.currentItem()
        if current_item:
            data_name, _ = os.path.splitext(current_item.data.label)
            formats = 'Adobe Acrobat (*.pdf);;Portable Network Graphic (*.png)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save Figure As...', data_name.replace(':',''), formats)
            if filename:
                print('Save Figure as ', filename)                    
                if current_item.data.settings['dpi'] == 'figure':
                    dpi = 'figure'
                else:
                    dpi = int(current_item.data.settings['dpi']) 
                if DARK_THEME and qdarkstyle_imported:             
                    rcParams_to_light_theme()
                    self.update_plots(update_data=False)
                transparent = current_item.data.settings['transparent']=='True'
                self.figure.savefig(filename, dpi=dpi, transparent=transparent,
                                    bbox_inches='tight')
                if DARK_THEME and qdarkstyle_imported:
                    rcParams_to_dark_theme()
                    self.update_plots(update_data=False)
                print('Saved!')
        
    def save_images_as(self, extension='.png'):
        save_folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory")
        if save_folder: 
            if DARK_THEME and qdarkstyle_imported:
                rcParams_to_light_theme()
                self.update_plots(update_data=False)
            for index in range(self.file_list.count()):
                self.figure.clear()
                item = self.file_list.item(index)
                filename = os.path.join(save_folder, item.data.label.replace(':','')+extension)
                if not os.path.isfile(filename):
                    try:
                        item.data.prepare_data_for_plot()
                        item.data.figure = self.figure
                        item.data.axes = self.figure.add_subplot(1, 1, 1)
                        item.data.add_plot(dim=len(item.data.get_columns()))
                        if item.data.settings['dpi'] == 'figure':
                            dpi = 'figure'
                        else:
                            dpi = int(item.data.settings['dpi']) 
                        transparent = item.data.settings['transparent']=='True'
                        self.figure.savefig(filename, dpi=dpi, 
                                            transparent=transparent,
                                            bbox_inches='tight')
                        item.data.raw_data = None
                        item.data.processed_data = None
                    except Exception as e:
                        print(f'Could not plot {item.data.filepath}:', e)
            if DARK_THEME and qdarkstyle_imported:
                rcParams_to_dark_theme()
                self.update_plots(update_data=False)
           
    def save_filters(self):
        current_item = self.file_list.currentItem()
        if current_item:
            if hasattr(current_item.data, 'sidebar1D'):
                current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                filters= current_item.data.plotted_lines[current_line]['filters']
            else:
                filters = current_item.data.filters
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save Filters As...', '', '.npy')
            np.save(filename, filters)
            
    def load_filters(self):
        current_item = self.file_list.currentItem()
        if current_item:
            if hasattr(current_item.data, 'sidebar1D'):
                current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                filters= current_item.data.plotted_lines[current_line]['filters']
            else:
                filters = current_item.data.filters
            filename, _ = QtWidgets.QFileDialog.getOpenFileNames(
                    self, 'Open Filters File...', '', '*.npy')
            loaded_filters = list(np.load(filename[0], allow_pickle=True))
            filters += copy.deepcopy(loaded_filters)
            current_item.data.apply_all_filters()
            self.update_plots()
            self.show_current_view_settings()
    
    def mouse_click_canvas(self, event):
        if self.navi_toolbar.mode == '': # If not using the navigation toolbar tools
            if event.inaxes:
                x, y = event.xdata, event.ydata
                checked_items = self.get_checked_items()
                self.plot_in_focus = [checked_item for checked_item in checked_items 
                                      if checked_item.data.axes == event.inaxes]
                if self.plot_in_focus:
                    data = self.plot_in_focus[0].data
                    data.selected_x, data.selected_y = x, y

                    if (event.button == 1  and 
                        len(data.get_columns()) == 2):
                        # Set fit limits for 1D data.
                        if hasattr(data, 'sidebar1D'):
                            current_row=data.sidebar1D.trace_table.currentRow()
                            xdata,ydata=data.sidebar1D.get_line_data(int(data.sidebar1D.trace_table.item(current_row,0).text()))
                            # snap to data
                            index=(np.abs(x-xdata)).argmin()
                            x_value=xdata[index]
                            if data.sidebar1D.xmin_box.text()=='':
                                data.sidebar1D.xmin_box.setText(str(x_value))
                            elif data.sidebar1D.xmax_box.text()=='':
                                data.sidebar1D.xmax_box.setText(str(x_value))
                            else:
                                if np.abs(float(data.sidebar1D.xmin_box.text())-x_value)<np.abs(float(data.sidebar1D.xmax_box.text())-x_value):
                                    data.sidebar1D.xmin_box.setText(str(x_value))
                                else:
                                    data.sidebar1D.xmax_box.setText(str(x_value))
                            data.sidebar1D.limits_edited()

                    elif ((event.button == 1 or event.button == 2) and 
                        len(data.get_columns()) == 3):
                        # Opening linecut/fitting window for 2D data
                        index_x = np.argmin(np.abs(data.processed_data[0][:,0]-x))
                        index_y = np.argmin(np.abs(data.processed_data[1][0,:]-y))
                        data.selected_indices = [int(index_x), int(index_y)]
                        if self.colormap_box.currentText() == 'viridis':
                            selected_colormap = cm.get_cmap('plasma')
                        else:
                            selected_colormap = cm.get_cmap('viridis')
                        #Make entry to store linecuts in
                        if not hasattr(data,'linecuts'):
                            data.linecuts={'horizontal':{'linecut_window':None,'lines':{}},
                                           'vertical':{'linecut_window':None,'lines':{}},
                                           'diagonal':{'linecut_window':None,'lines':{}},
                                           'circular':{'linecut_window':None,'lines':{}}
                                            }
                        if event.button == 1:
                            line_colors = selected_colormap(np.linspace(0.1,0.9,len(data.processed_data[1][0,:])))
                            orientation='horizontal'
                            try:
                                max_index=np.max(list(data.linecuts[orientation]['lines'].keys()))
                            except ValueError:
                                max_index=-1
                            data.linecuts[orientation]['lines'][int(max_index+1)]={'data_index':index_y,
                                                                                'cut_axis_value':data.processed_data[1][0,index_y],
                                                                                'checkstate':2,
                                                                                'offset':0,
                                                                                'linecolor':line_colors[int(index_y)]}
                        elif event.button == 2:
                            line_colors = selected_colormap(np.linspace(0.1,0.9,len(data.processed_data[0][:,0])))
                            orientation='vertical'
                            try:
                                max_index=np.max(list(data.linecuts[orientation]['lines'].keys()))
                            except ValueError:
                                max_index=-1
                            data.linecuts[orientation]['lines'][int(max_index+1)]={'data_index':index_x,
                                                                                'cut_axis_value':data.processed_data[0][index_x,0],
                                                                                'checkstate':2,
                                                                                'offset':0,
                                                                                'linecolor':line_colors[int(index_x)]}
                        if data.linecuts[orientation]['linecut_window']==None:
                            data.linecuts[orientation]['linecut_window'] = LineCutWindow(data,orientation=orientation,init_cmap=selected_colormap.name)
                        data.linecuts[orientation]['linecut_window'].running = True
                        data.linecuts[orientation]['linecut_window'].append_cut_to_table(int(max_index+1))
                        data.linecuts[orientation]['linecut_window'].update()
                        data.linecuts[orientation]['linecut_window'].activateWindow()
                        self.canvas.draw()
                        
                    elif event.button == 3:
                        # Open right-click menu
                        rightclick_menu = QtWidgets.QMenu(self)

                        index_x = np.argmin(np.abs(data.processed_data[0]-x))
                        index_y = np.argmin(np.abs(data.processed_data[1]-y))
                        coordinates = (f'x = {x:.4g}, y = {y:.4g}'
                                           f' ({index_x}, {index_y})')
                        if len(data.get_columns()) == 3:
                            index_x = np.argmin(np.abs(data.processed_data[0][:,0]-x))
                            index_y = np.argmin(np.abs(data.processed_data[1][0,:]-y))
                            z = data.processed_data[2][index_x,index_y]
                            coordinates = (f'x = {x:.4g}, y = {y:.4g}, z = {z:.4g}'
                                           f' ({index_x}, {index_y})')
                        action = QtWidgets.QAction(coordinates, self)
                        action.setEnabled(False)
                        rightclick_menu.addAction(action)
                        rightclick_menu.addSeparator()

                        actions = []
                        actions.append(QtWidgets.QAction(f'Offset X by {x:6g}', self))
                        actions.append(QtWidgets.QAction(f'Offset Y by {y:6g}', self))
                        if len(data.get_columns()) == 3:
                            actions.append(QtWidgets.QAction(f'Offset Z by {z:6g}', self))
                        for action in actions:
                            rightclick_menu.addAction(action)
                        # Add actions from extension modules
                        rightclick_menu.addSeparator()
                        data.add_extension_actions(self, rightclick_menu)
                        rightclick_menu.addSeparator()
                        actions=[]
                        if len(data.get_columns()) == 3:
                            actions.append(QtWidgets.QAction('Draw diagonal linecut', self))
                            actions.append(QtWidgets.QAction('Draw circular linecut', self))
                            actions.append(QtWidgets.QAction('Plot vertical linecuts', self))
                            actions.append(QtWidgets.QAction('Plot horizontal linecuts', self))
                            actions.append(QtWidgets.QAction('FFT vertical', self))
                            actions.append(QtWidgets.QAction('FFT horizontal', self))
                        for action in actions:
                            rightclick_menu.addAction(action)
                        rightclick_menu.triggered[QtWidgets.QAction].connect(self.popup_canvas)
                        rightclick_menu.popup(QtGui.QCursor.pos())
                    
                else: # if colorbar in focus
                    self.cbar_in_focus = [checked_item for checked_item in checked_items
                                          if checked_item.data.cbar.ax == event.inaxes]
                    if self.cbar_in_focus:
                        data = self.cbar_in_focus[0].data
                        if event.button == 1:
                            data.view_settings['Minimum'] = y
                            data.reset_midpoint()
                        elif event.button == 2:
                            data.view_settings['Midpoint'] = y
                        elif event.button == 3:
                            data.view_settings['Maximum'] = y
                            data.reset_midpoint()
                        data.apply_view_settings()
                        self.canvas.draw()
                        self.show_current_view_settings()
    
    def popup_canvas(self, signal):
        # Actions for right-click menu on the plot(s)
        current_item = self.plot_in_focus[0]
        data = self.plot_in_focus[0].data
        if 'Offset' in signal.text():
            axis=signal.text().split()[1]
            value=-float(signal.text().split()[3])
            if current_item:
                filt = Filter('Offset',method=axis, settings=[str(value),''], checkstate=2)
                if hasattr(current_item.data, 'sidebar1D'):
                    current_1D_row = current_item.data.sidebar1D.trace_table.currentRow()
                    current_line = int(current_item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                    current_item.data.plotted_lines[current_line]['filters'].append(filt)
                else:
                    current_item.data.filters.append(filt)
            if current_item.checkState() and filt.checkstate:
                self.update_plots()
                self.reset_axlim_settings()
        
        elif 'linecut' in signal.text():
            if not hasattr(data,'linecuts'):
                data.linecuts={'horizontal':{'linecut_window':None,'lines':{}},
                               'vertical':{'linecut_window':None,'lines':{}},
                               'diagonal':{'linecut_window':None,'lines':{}},
                               'circular':{'linecut_window':None,'lines':{}}
                                }
            
            orientation=signal.text().split()[1]

            if orientation == 'diagonal':
                x,y=data.selected_x, data.selected_y
                left,right= data.axes.get_xlim()
                bottom,top= data.axes.get_ylim()
                x_mid, y_mid = 0.5*(left+right), 0.5*(top+bottom)
                if self.colormap_box.currentText() == 'viridis':
                    selected_colormap = cm.get_cmap('plasma')
                else:
                    selected_colormap = cm.get_cmap('viridis')
                line_colors = selected_colormap(np.linspace(0.1,0.9,len(data.processed_data[1][0,:])))
                try:
                    max_index=np.max(list(data.linecuts[orientation]['lines'].keys()))
                except ValueError:
                    max_index=-1
                data.linecuts[orientation]['lines'][int(max_index+1)]={'points':[DraggablePoint(data, x, y),
                                                                                DraggablePoint(data, x_mid, y_mid,draw_line=True)],
                                                                    'checkstate':2,
                                                                    'offset':0,
                                                                    'linecolor':line_colors[int(max_index+1)]}

            if data.linecuts[orientation]['linecut_window']==None:
                if self.colormap_box.currentText() == 'viridis':
                    selected_colormap = cm.get_cmap('plasma')
                else:
                    selected_colormap = cm.get_cmap('viridis')
                data.linecuts[orientation]['linecut_window'] = LineCutWindow(data,orientation=orientation,init_cmap=selected_colormap.name)

            data.linecuts[orientation]['linecut_window'].running = True
            data.linecuts[orientation]['linecut_window'].activateWindow()
            if len(data.linecuts[orientation]['lines']) > 0:
                data.linecuts[orientation]['linecut_window'].update()
            data.linecuts[orientation]['linecut_window'].show()

        # elif signal.text() == 'Draw diagonal linecut':
        #     if hasattr(data, 'linecut_points'):
        #         data.hide_linecuts()
        #     x, y = data.selected_x, data.selected_y
        #     data.linecut_points = [DraggablePoint(data, x, y)]            
        #     left, right = data.axes.get_xlim() 
        #     bottom, top = data.axes.get_ylim()
        #     x_mid, y_mid = 0.5*(left+right), 0.5*(top+bottom)
        #     data.linecut_points.append(DraggablePoint(data, x_mid, y_mid, 
        #                                               draw_line=True))
        #     if not hasattr(data, 'linecut_window'):
        #         data.linecut_window = LineCutWindow(data,orientation='diagonal')
        #     else:
        #         data.linecut_window.orientation='diagonal'
        #     data.linecut_window.running = True
        #     data.linecut_window.update()
        #     self.canvas.draw()
        #     data.linecut_window.activateWindow()
        elif signal.text() == 'Draw circular linecut':
            if hasattr(data, 'linecut_points'):
                data.hide_linecuts()
            left, right = data.axes.get_xlim() 
            bottom, top = data.axes.get_ylim()                
            x, y = data.selected_x, data.selected_y
            data.xr, data.yr = 0.1*(right-left), 0.1*(top-bottom)
            data.linecut_points = [DraggablePoint(data, x, y),
                                   DraggablePoint(data, x+data.xr, y)]
            data.linecut_points.append(DraggablePoint(data, x, y+data.yr,
                                                      draw_circle=True))
            if not hasattr(data, 'linecut_window'):
                data.linecut_window = LineCutWindow(data,orientation='circular')
            else:
                data.linecut_window.orientation='circular'
            data.linecut_window.running = True
            data.linecut_window.update()
            self.canvas.draw()
            data.linecut_window.activateWindow()
        elif signal.text() == 'FFT vertical':
            data.fft_orientation = 'vertical'
            data.open_fft_window()
        elif signal.text() == 'FFT horizontal':
            data.fft_orientation = 'horizontal'
            data.open_fft_window()
        else:
            data.do_extension_actions(self, signal)
            
    def copy_canvas_to_clipboard(self):
        checked_items = self.get_checked_items()
        for item in checked_items:
            item.data.cursor.horizOn = False
            item.data.cursor.vertOn = False            
        self.canvas.draw()
        if DARK_THEME and qdarkstyle_imported:
            rcParams_to_light_theme()
            self.update_plots(update_data=False)
        buf = io.BytesIO()
        if item.data.settings['dpi'] == 'figure':
            dpi = 'figure'
        else:
            dpi = int(item.data.settings['dpi'])
        self.figure.savefig(buf, dpi=dpi, bbox_inches='tight')
        QtWidgets.QApplication.clipboard().setImage(QtGui.QImage.fromData(buf.getvalue()))
        buf.close()
        for item in checked_items:
            item.data.cursor.horizOn = True
            item.data.cursor.vertOn = True                       
        self.canvas.draw()
        if DARK_THEME and qdarkstyle_imported:
            rcParams_to_dark_theme()
            self.update_plots(update_data=False)
            
    def mouse_scroll_canvas(self, event):
        if event.inaxes:
            checked_items = self.get_checked_items()
            self.plot_in_focus = [checked_item for checked_item in checked_items 
                                  if checked_item.data.axes == event.inaxes]
            
            # Scolling within plot bounds zooms
            if self.plot_in_focus:
                scale=1.2
                data = self.plot_in_focus[0].data
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
                    data.axlim_settings['Xmin']=newxlims[0]
                    data.axlim_settings['Xmax']=newxlims[1]
                elif QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
                    data.axlim_settings['Ymin']=newylims[0]
                    data.axlim_settings['Ymax']=newylims[1]
                else:
                    data.axlim_settings['Xmin']=newxlims[0]
                    data.axlim_settings['Xmax']=newxlims[1]
                    data.axlim_settings['Ymin']=newylims[0]
                    data.axlim_settings['Ymax']=newylims[1]
                data.apply_axlim_settings()
                event.inaxes.figure.canvas.draw()
                self.show_current_axlim_settings()
                # Update toolbar so back/forward buttons work
                fig = event.inaxes.get_figure()
                fig.canvas.toolbar.push_current()

            self.cbar_in_focus = [checked_item for checked_item in checked_items
                                    if hasattr(checked_item.data, 'cbar') and checked_item.data.cbar.ax == event.inaxes]
            
            #Scrolling within colourbar changes limits
            if self.cbar_in_focus:
                y = event.ydata
                data = self.cbar_in_focus[0].data
                min_map = data.view_settings['Minimum']
                max_map = data.view_settings['Maximum']
                range_map = max_map-min_map
                if y > min_map+0.5*range_map:    
                    new_max = max_map + event.step*range_map*0.02
                    data.view_settings['Maximum'] = new_max
                else:
                    new_min = min_map + event.step*range_map*0.02
                    data.view_settings['Minimum'] = new_min
                data.reset_midpoint()
                data.apply_view_settings()
                self.canvas.draw()
                self.show_current_view_settings()

        # Scrolling outside of plot bounds changes the whitespace around/between plots
        else:
            width, height = self.canvas.get_width_height()
            speed = 0.03
            lb, rb, tb, bb = 0.15*width, 0.85*width, 0.85*height, 0.15*height
            if (event.x < lb and event.y > bb and event.y < tb):
                if (event.step > 0 or 
                    (event.step < 0 and self.figure.subplotpars.left > 0.07)):
                    self.figure.subplots_adjust(left=(1+speed*event.step)*
                                                self.figure.subplotpars.left)
            elif (event.x > rb and event.y > bb and event.y < tb):
                  if (event.step < 0 or 
                      (event.step > 0 and self.figure.subplotpars.right < 0.97)):
                      self.figure.subplots_adjust(right=(1+speed*0.5*event.step)*
                                                  self.figure.subplotpars.right)
            elif (event.y < bb and event.x > lb and event.x < rb):
                  if (event.step > 0 or 
                      (event.step < 0 and self.figure.subplotpars.bottom > 0.07)):
                      self.figure.subplots_adjust(bottom=(1+speed*event.step)*
                                                  self.figure.subplotpars.bottom)
            elif (event.y > tb and event.x > lb and event.x < rb):
                  if (event.step < 0 or 
                      (event.step > 0 and self.figure.subplotpars.top < 0.94)):
                      self.figure.subplots_adjust(top=(1+speed*0.5*event.step)*
                                                  self.figure.subplotpars.top)
            else:
                self.figure.subplots_adjust(wspace=(1+speed*event.step)*self.figure.subplotpars.wspace)
            self.canvas.draw()
            
    def keyPressEvent(self, event): 
        if event.key() == QtCore.Qt.Key_C and event.modifiers() == QtCore.Qt.ControlModifier:
            self.copy_canvas_to_clipboard()
        elif event.key() == QtCore.Qt.Key_T and event.modifiers() == QtCore.Qt.ControlModifier:
            if not self.action_refresh_stop.isEnabled():
                self.start_auto_refresh(1)
                print('Start live tracking...')
            else:
                self.stop_auto_refresh()
                print('Stop live tracking...')

                              
    def apply_preset(self, preset_number):
        checked_items = self.get_checked_items()
        if checked_items:
            for item in checked_items:
                for preset_item in PRESETS[preset_number].items():
                    if preset_item[0] in item.data.settings.keys():
                        item.data.settings[preset_item[0]] = preset_item[1]
                    elif preset_item[0] == 'canvas_bounds':
                        b = preset_item[1] # (left, bottom, right, top)
                        item.data.figure.subplots_adjust(b[0], b[1], b[2], b[3])
                    elif preset_item[0] == 'show_meta_settings':
                        item.data.show_settings = preset_item[1]
            self.update_plots()


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.aboutToQuit.connect(app.deleteLater)
    app.lastWindowClosed.connect(app.quit)
    
    edit_window = Editor()
    
    if DARK_THEME and qdarkstyle_imported:
        app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    
    edit_window.show()
    app.exec_()

if __name__ == '__main__':
    main()

import threading

def offline_plotting(use_thread=True):
    if use_thread:
        plot_thread = threading.Thread(target = main)
        plot_thread.start()
    else:
        main()