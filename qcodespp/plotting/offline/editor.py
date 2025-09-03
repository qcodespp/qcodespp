# -*- coding: utf-8 -*-
"""
Inspectra-Gadget

Author: Joeri de Bruijckere

Adapted for qcodes++ by: Dags Olsteins and Damon Carrad

"""

from PyQt5 import QtWidgets, QtCore, QtGui
import os
import copy
import io
import tarfile
import time
from webbrowser import open as href_open
from csv import writer as csvwriter
from json import load as jsonload
from json import dump as jsondump
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

import matplotlib.style as mplstyle
mplstyle.use('fast')

from lmfit.model import save_modelresult, load_modelresult

import qcodespp.plotting.offline.design as design
from qcodespp.plotting.offline.popupwindows import (LineCutWindow, MetadataWindow, StatsWindow, 
                                                    ErrorWindow, ErrorLogWindow,AutoRefreshPopup)
from qcodespp.plotting.offline.sidebars import Sidebar1D
from qcodespp.plotting.offline.helpers import (cmaps, NavigationToolbarMod,
                      rcParams_to_dark_theme,rcParams_to_light_theme,
                      NoScrollQComboBox,DraggablePoint)
from qcodespp.plotting.offline.filters import Filter
from qcodespp.plotting.offline.datatypes import DataItem, BaseClassData, NumpyData, InternalData, MixedInternalData
from qcodespp.plotting.offline.qcodespp_extension import qcodesppData
from qcodespp.plotting.offline.fits import load_lmfit_modelresult_s

from qcodespp.data.data_set import DataSetPP
import sys

# UI settings
DARK_THEME = True

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
SETTINGS_MENU_OPTIONS['transpose'] = ['True', 'False']
SETTINGS_MENU_OPTIONS['delimiter'] = [' ',',']
SETTINGS_MENU_OPTIONS['titlesize'] = FONT_SIZES
SETTINGS_MENU_OPTIONS['labelsize'] = FONT_SIZES
SETTINGS_MENU_OPTIONS['ticksize'] = FONT_SIZES
SETTINGS_MENU_OPTIONS['colorbar'] = ['True', 'False']
SETTINGS_MENU_OPTIONS['minorticks'] = ['True','False']
SETTINGS_MENU_OPTIONS['maskcolor'] = ['black','white']
SETTINGS_MENU_OPTIONS['cmap levels'] = ['128','256','512','1024']
SETTINGS_MENU_OPTIONS['rasterized'] = ['True','False']
SETTINGS_MENU_OPTIONS['dpi'] = ['figure','300']
SETTINGS_MENU_OPTIONS['transparent'] = ['True', 'False']
SETTINGS_MENU_OPTIONS['shading'] = ['auto', 'flat', 'gouraud', 'nearest']
SETTINGS_MENU_OPTIONS['columns'] = ['0,1,2','0,1,3','0,2,3','1,2,4']

AXIS_SCALING_OPTIONS = ['linear', 'log', 'symlog', 'logit']

class Editor(QtWidgets.QMainWindow, design.Ui_MainWindow):
    def __init__(self,folder=None,link_to_default=True):
        super().__init__()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle('InSpectra Gadget')
        try:
            if sys.platform.startswith('win'):
                icon_file = 'iconGadget.ico'
            else:
                icon_file = 'iconGadget.png'
            self.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), icon_file)))
        except Exception as e:
            pass
        self.window_title_auto_refresh = ''
        self.setupUi(self)
        self.init_plot_settings()
        self.init_view_settings()
        self.init_axis_scaling()
        self.init_connections()
        self.init_filters()
        self.init_canvas()
        self.linked_folder = None
        self.linked_files = []
        self.resize(1400,1000)

        self.refresh_2d = 30
        self.refresh_1d = 5
        self.ask_autorefresh = True
        self.live_tracking = False

        self.show_linecut_markers = True

        # Hide widgets related to specific data types: will not be shown at startup
        self.legend_checkbox.hide()
        self.mixeddata_filter_box.hide()
        self.binsX_label.hide()
        self.binsX_lineedit.hide()
        self.binsY_label.hide()
        self.binsY_lineedit.hide()
        self.metadata_button.hide()
        self.stats_button.hide()
        self.show_2d_data_checkbox.hide()

        self.global_text_size='12'
        self.global_text_lineedit.setText(self.global_text_size)

        self.error_log={}

        if folder:
            print(f'Linking to {folder}... This may take some time.')
            try:
                self.update_link_to_folder(folder=folder)
            except Exception as e:
                print(f'Failed to link to folder {folder}:', e)
                self.error_log[time.strftime('%Y-%m-%d %H:%M:%S')] = f'Failed to link to folder {folder}: {e}'
        elif link_to_default and DataSetPP.default_folder and os.path.isdir(DataSetPP.default_folder):
            try:
                print(f'Linking to qcodespp data folder at {DataSetPP.default_folder}... This may take some time.')
                self.update_link_to_folder(folder=DataSetPP.default_folder)
            except:
                pass

        self.setAcceptDrops(True)

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
        self.legend_checkbox.clicked.connect(self.legend_checkbox_changed)
        self.plot_type_box.currentIndexChanged.connect(self.plot_type_changed)
        self.binsX_lineedit.editingFinished.connect(lambda: self.bins_changed('X'))
        self.binsY_lineedit.editingFinished.connect(lambda: self.bins_changed('Y'))
        self.show_2d_data_checkbox.clicked.connect(self.show_2d_data_checkbox_changed)
        self.global_text_lineedit.editingFinished.connect(self.global_text_changed)
        self.stats_button.clicked.connect(self.show_stats)
        self.metadata_button.clicked.connect(self.show_metadata)
        self.settings_table.itemChanged.connect(self.plot_setting_edited)
        self.filters_table.itemChanged.connect(self.filters_table_edited)
        self.copy_settings_button.clicked.connect(self.copy_plot_settings)
        self.paste_settings_button.clicked.connect(lambda: self.paste_plot_settings('copied'))
        self.reset_settings_button.clicked.connect(lambda: self.paste_plot_settings('default'))
        self.filters_combobox.currentIndexChanged.connect(self.filters_box_changed)
        self.mixeddata_filter_box.currentIndexChanged.connect(self.mixeddata_filterbox_changed)
        self.xaxis_combobox.currentIndexChanged.connect(self.axis_scaling_changed)
        self.yaxis_combobox.currentIndexChanged.connect(self.axis_scaling_changed)
        self.delete_filters_button.clicked.connect(lambda: self.remove_filters('current'))
        self.clear_filters_button.clicked.connect(lambda: self.remove_filters('all'))
        self.copy_filters_button.clicked.connect(self.copy_filters)
        self.paste_filters_button.clicked.connect(lambda: self.paste_filters('copied'))
        self.up_filters_button.clicked.connect(lambda: self.move_filter(-1))
        self.down_filters_button.clicked.connect(lambda: self.move_filter(1))
        self.filtXtocol_button.clicked.connect(lambda: self.filttocol_clicked('X'))
        self.filtYtocol_button.clicked.connect(lambda: self.filttocol_clicked('Y'))
        self.filtZtocol_button.clicked.connect(lambda: self.filttocol_clicked('Z'))
        # self.previous_button.clicked.connect(self.to_previous_file)
        # self.next_button.clicked.connect(self.to_next_file)
        self.new_plot_button.clicked.connect(lambda: self.duplicate_item(new_plot_button=True))
        self.copy_view_button.clicked.connect(self.copy_view_settings)
        self.paste_view_button.clicked.connect(lambda: self.paste_view_settings('copied'))
        self.colormap_type_box.currentIndexChanged.connect(self.colormap_type_edited)
        self.colormap_box.currentIndexChanged.connect(self.colormap_edited)
        self.cbar_hist_checkbox.clicked.connect(lambda: self.view_setting_edited('CBarHist'))
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
        self.tight_layout_button.clicked.connect(self.tight_layout)
        self.save_image_button.clicked.connect(self.save_image)
        self.copy_image_button.clicked.connect(self.copy_canvas_to_clipboard)
        self.load_filters_button.clicked.connect(self.load_filters)
        self.actionOpenLinecutsHorizontal.triggered.connect(lambda: self.make_linecut_window('horizontal'))
        self.actionOpenLinecutsVertical.triggered.connect(lambda: self.make_linecut_window('vertical'))
        self.actionOpenLinecutsDiagonal.triggered.connect(lambda: self.make_linecut_window('diagonal'))
        self.actionCopyLinecutsAll.triggered.connect(lambda: self.copy_linecuts('all'))
        self.actionCopyLinecutsHorizontal.triggered.connect(lambda: self.copy_linecuts('horizontal'))
        self.actionCopyLinecutsVertical.triggered.connect(lambda: self.copy_linecuts('vertical'))
        self.actionCopyLinecutsDiagonal.triggered.connect(lambda: self.copy_linecuts('diagonal'))
        self.actionPasteLinecuts.triggered.connect(self.paste_linecuts)
        self.action_show_hide_lc_markers.triggered.connect(self.show_hide_linecuts_changed)
        self.action_filters.triggered.connect(self.save_filters)
        self.action_save_session.triggered.connect(self.save_session)
        self.action_save_session_as.triggered.connect(lambda: self.save_session(save_as=True))
        self.action_restore_session.triggered.connect(self.load_session)
        self.action_combine_files.triggered.connect(self.combine_plots)
        self.action_duplicate_file.triggered.connect(self.duplicate_item)
        self.action_export_data_columns.triggered.connect(lambda: self.export_processed_data('current'))
        self.action_export_data_Z.triggered.connect(lambda: self.export_processed_data('Z'))
        self.actionSave_plot_s_as.triggered.connect(self.save_image)
        self.action_open_file.triggered.connect(self.open_files)
        self.action_open_files_from_folder.triggered.connect(self.open_files_from_folder)
        self.action_copy_plot_as_image.triggered.connect(self.copy_canvas_to_clipboard)
        self.action_save_files_as_PNG.triggered.connect(lambda: self.save_images_as('.png'))
        self.action_save_files_as_PDF.triggered.connect(lambda: self.save_images_as('.pdf'))
        self.action_load_preset.triggered.connect(self.load_preset)
        self.action_save_preset.triggered.connect(self.save_preset)
        self.action_refresh_stop.setEnabled(False)
        self.action_link_to_folder.triggered.connect(lambda: self.update_link_to_folder(new_folder=True))
        self.action_unlink_folder.triggered.connect(self.unlink_folder)
        self.action_track_data.triggered.connect(self.start_stop_tracking)
        self.action_set_refresh_intervals.triggered.connect(lambda: self.set_refresh_intervals(from_dropdown=True))
        self.action_refresh.triggered.connect(self.refresh_files)
        self.refresh_file_button.clicked.connect(self.refresh_files)
        self.action_exit.triggered.connect(self.close)
        self.up_file_button.clicked.connect(lambda: self.move_file('up'))
        self.down_file_button.clicked.connect(lambda: self.move_file('down'))
        self.file_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.open_item_menu)
        self.actionOnline_help.triggered.connect(lambda: href_open('https://qcodespp.github.io/offline_plotting.html'))
        self.actionError_log.triggered.connect(self.open_error_log)

        # Keyboard shortcuts
        self.open_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+O"), self)
        self.open_shortcut.activated.connect(self.open_files)
        self.open_folder_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+O"), self)
        self.open_folder_shortcut.activated.connect(self.open_files_from_folder)
        self.link_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+L"), self)
        self.link_shortcut.activated.connect(lambda: self.update_link_to_folder(new_folder=True))
        self.unlink_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+L"), self)
        self.unlink_shortcut.activated.connect(self.unlink_folder)
        self.refresh_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+R"), self)
        self.refresh_shortcut.activated.connect(self.refresh_files)
        self.track_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+T"), self)
        self.track_shortcut.activated.connect(self.start_stop_tracking)
        self.save_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+S"), self)
        self.save_shortcut.activated.connect(self.save_image)
        self.copy_image_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+C"), self)
        self.copy_image_shortcut.activated.connect(self.copy_canvas_to_clipboard)
        self.duplicate_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+D"), self)
        self.duplicate_shortcut.activated.connect(self.duplicate_item)
        self.save_session_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"),self)
        self.save_session_shortcut.activated.connect(self.save_session)
        self.load_session_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"),self)
        self.load_session_shortcut.activated.connect(self.load_session)
        self.horizontal_linecut_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+H"), self)
        self.horizontal_linecut_shortcut.activated.connect(lambda: self.make_linecut_window('horizontal'))
        self.vertical_linecut_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+V"), self)
        self.vertical_linecut_shortcut.activated.connect(lambda: self.make_linecut_window('vertical'))
        self.diagonal_linecut_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+D"), self)
        self.diagonal_linecut_shortcut.activated.connect(lambda: self.make_linecut_window('diagonal'))
        self.copy_linecuts_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Alt+C"), self)
        self.copy_linecuts_shortcut.activated.connect(lambda: self.copy_linecuts('all'))
        self.paste_linecuts_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Alt+V"), self)
        self.paste_linecuts_shortcut.activated.connect(self.paste_linecuts)
        self.show_hide_linecut_markers_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+M"), self)
        self.show_hide_linecut_markers_shortcut.activated.connect(self.show_hide_linecuts_changed)

    def init_canvas(self):
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect('button_press_event', self.mouse_click_canvas)
        self.canvas.mpl_connect('scroll_event', self.mouse_scroll_canvas)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('pick_event', self.on_pick)
        self.navi_toolbar = NavigationToolbarMod(self.canvas, self)
        self.graph_layout.addWidget(self.navi_toolbar)
        self.graph_layout.addWidget(self.canvas)
        self.subplot_grid = [(1,1),(1,2),(2,2),(2,2),(2,3),(2,3),(2,4),(2,4),
                             (3,4),(3,4),(3,4),(3,4),(4,4),(4,4),(4,4),(4,4),
                             (4,5),(4,5),(4,5),(4,5),(4,5),(5,5),(5,5),(5,5),
                             (5,5)]
        self.figure.subplots_adjust(top=0.893, bottom=0.137, 
                                    left=0.121, right=0.86)
        
    def set_window_title(self):
        if hasattr(self, 'linked_folder') and self.linked_folder:
            linked_info = f' - Linked to {self.linked_folder}'
        else:
            linked_info = ''
        if hasattr(self, 'session_filepath') and self.session_filepath:
            session_name = f' - Session: {os.path.basename(self.session_filepath)}'
        else:
            session_name = ''

        self.setWindowTitle(f'InSpectra Gadget{linked_info}{self.window_title_auto_refresh}{session_name}')

    def load_data_item(self,filepath):
        filename, extension = os.path.splitext(filepath)
        if extension == '.npy': # Numpy files (old saved sessions)
            dataset_list = np.load(filepath, allow_pickle=True)
            for dataset in dataset_list:
                try:
                    item = DataItem(NumpyData(filepath, self.canvas, dataset))
                    return item
                except Exception as e:
                    error_type = type(e)
                    return error_type(f'Failed to add NumPy dataset inside {filepath}: {error_type.__name__} {e}')

        elif (extension == '.dat' and # qcodes++ files
                os.path.isfile(os.path.dirname(filepath)+'/snapshot.json')):
            metapath = os.path.dirname(filepath)+'/snapshot.json'
            try:
                item = DataItem(qcodesppData(filepath, self.canvas, metapath))
                return item
            except Exception as e:
                error_type = type(e)
                return error_type(f'Failed to add qcodes++ dataset {filepath}: {error_type.__name__} {e}')

        else: # bare column-based data file
            try:
                item = DataItem(BaseClassData(filepath, self.canvas))
                return item
            except Exception as e:
                error_type = type(e)
                return error_type(f'Failed to add .dat dataset {filepath}: {error_type.__name__} {e}')

    def open_files(self, filepaths=None, attr_dicts=None, overrideautocheck=False):
        self.file_list.itemClicked.disconnect(self.file_clicked)
        self.file_list.itemChanged.disconnect(self.file_checked)
        item_to_set_current=None
        minilog=[]
        if not filepaths:
            filepaths, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self, 'Open File', '', 'Data Files (*.dat *.npy *.csv)')
        if filepaths:
            for i,filepath in enumerate(filepaths):
                try:
                    if filepath == 'internal_data': # Should only happen when loading a session, therefore rely on attr_dicts
                        item=DataItem(InternalData(self.canvas, 
                                                    attr_dicts[i]['loaded_data'],
                                                    attr_dicts[i]['label'],
                                                    attr_dicts[i]['all_parameter_names'],
                                                    attr_dicts[i]['dim']))
                        
                    elif filepath == 'mixed_internal_data': # Should only happen when loading a session, therefore rely on attr_dicts
                        type_dictionary={'qcodesppData': qcodesppData,
                                            'BaseClassData': BaseClassData,
                                            'InternalData': InternalData}
                        for key in type_dictionary.keys():
                            if key in attr_dicts[i]['dataset1d_type']:
                                dataset1d_type = type_dictionary[key]
                            if key in attr_dicts[i]['dataset2d_type']:
                                dataset2d_type = type_dictionary[key]
                        label_name = attr_dicts[i]['label']
                        kwargs={}
                        if dataset1d_type in [qcodesppData,BaseClassData]:
                            kwargs['dataset1d_filepath'] = attr_dicts[i]['dataset1d_filepath']
                        elif dataset1d_type == InternalData:
                            kwargs['dataset1d_loaded_data'] = attr_dicts[i]['dataset1d_loaded_data']
                            kwargs['dataset1d_label'] = attr_dicts[i]['dataset1d_label']
                            kwargs['dataset1d_all_parameter_names'] = attr_dicts[i]['dataset1d_all_parameter_names']
                            kwargs['dataset1d_dim']= attr_dicts[i]['dataset1d_dim']
                        if dataset2d_type in [qcodesppData,BaseClassData]:
                            kwargs['dataset2d_filepath'] = attr_dicts[i]['dataset2d_filepath']
                        elif dataset2d_type == InternalData:
                            kwargs['dataset2d_loaded_data'] = attr_dicts[i]['dataset2d_loaded_data']
                            kwargs['dataset2d_label'] = attr_dicts[i]['dataset2d_label']
                            kwargs['dataset2d_all_parameter_names'] = attr_dicts[i]['dataset2d_all_parameter_names']
                            kwargs['dataset2d_dim']= attr_dicts[i]['dataset2d_dim']
                        item=DataItem(MixedInternalData(self.canvas,label_name,dataset2d_type,dataset1d_type,**kwargs))

                    else:
                        item=self.load_data_item(filepath)

                    if isinstance(item, Exception):
                        self.log_error(str(item))
                        minilog.append(str(item))
                        continue

                    item.filepath=filepath
                    self.file_list.addItem(item)
                    if attr_dicts: #then a previous session is being loaded
                        for attr,value in attr_dicts[i].items():
                            if attr not in ['filename','checkState','duplicate','is_current_item',
                                            'extra_cols','dataset1d_type','dataset2d_type',
                                            'dataset1d_plotted_lines','dataset2d_linecuts']:
                                setattr(item.data,attr,value)

                            elif attr=='is_current_item' and value:
                                item_to_set_current=item

                            elif attr=='extra_cols':
                                if not hasattr(item.data,'data_dict'):
                                    item.data.data_dict = {}
                                if not hasattr(item.data,'extra_cols'):
                                    item.data.extra_cols = []
                                if isinstance(item.data, qcodesppData) and not hasattr(item.data,'channels'):
                                    item.data.channels = {}

                                for colname in value:
                                    item.data.extra_cols.append(colname)
                                    item.data.data_dict[colname] = value[colname]['data']
                                    if isinstance(item.data, qcodesppData):
                                        item.data.channels[colname] = value[colname]['channel']
                                    elif isinstance(item.data,InternalData):
                                        item.data.all_parameter_names.append(colname)
                            
                            elif attr=='checkState':
                                item.setCheckState(value)
                                if value==2:
                                    self.file_checked(item)
                                    overrideautocheck=True #If any item is checked, override autochecking. 
                                    # But if NONE of them are checked, let autocheck do its thing.
                                    
                                    # The below is kind of dumb... but for anything at all to work, 1D data has to be inited by
                                    # actually plotting _something_ when file_checked is called, which makes a sidebar1D with the default params plotted.
                                    # If this sidebar1D exists, we need to delete it and make the proper one at reload_plotted_lines.
                                    if hasattr(item.data,'sidebar1D'):
                                        item.data.sidebar1D.hide()
                                        del item.data.sidebar1D
                            
                            elif attr=='duplicate':
                                item.duplicate = value
                                if item.duplicate and 'label' in attr_dicts[i]:
                                    item.setText(attr_dicts[i]['label'])

                            elif attr=='dataset1d_plotted_lines':
                                item.data.dataset1d.plotted_lines= value
                                self.reload_plotted_lines(item.data.dataset1d,item)

                            elif attr=='dataset2d_linecuts':
                                item.data.dataset2d.linecuts = value
                                self.reload_linecuts(item.data.dataset2d,item.checkState())

                            if attr=='linecuts':
                                self.reload_linecuts(item.data,item.checkState())

                            if attr=='plotted_lines':
                                self.reload_plotted_lines(item.data,item)

                        if 'processed_data' in attr_dicts[i]: # If the data had been plotted we need to force load it here
                                                                # otherwise the data will be in some weird state.
                            item.data.prepare_data_for_plot(reload_data=True,reload_from_file=True)

                    else:
                        for setting in ['titlesize','labelsize','ticksize']:
                            if hasattr(item.data,'settings'):
                                item.data.settings[setting]=self.global_text_size

                except Exception as e:
                    self.log_error(f'Failed to open {filepath}:\n{type(e).__name__}: {e}')
                    minilog.append(f'Failed to open {filepath}:\n{type(e).__name__}: {e}')

            if self.file_list.count() > 0:
                if item_to_set_current:
                    self.file_list.setCurrentItem(item_to_set_current)
                else:
                    last_item = self.file_list.item(self.file_list.count()-1)
                    self.file_list.setCurrentItem(last_item)
                if not overrideautocheck:
                    for item_index in range(self.file_list.count()-1):
                        self.file_list.item(item_index).setCheckState(QtCore.Qt.Unchecked)
                    last_item.setCheckState(QtCore.Qt.Checked)
                    self.file_checked(last_item)
        self.file_list.itemChanged.connect(self.file_checked)
        self.file_list.itemClicked.connect(self.file_clicked)
        if len(minilog) > 0:
            error_message = 'The following errors occurred while opening files:\n\n' + '\n\n'.join(minilog)
            self.ew = ErrorWindow(error_message)

    def reload_plotted_lines(self,data,item):
        if len(data.plotted_lines) > 0:
            item.data.sidebar1D = Sidebar1D(data,self)
            for line in data.plotted_lines.keys():
                if 'fit' in data.plotted_lines[line].keys():
                    data.plotted_lines[line]['fit']['fit_result'] = load_lmfit_modelresult_s(data.plotted_lines[line]['fit']['fit_result'])
                item.data.sidebar1D.append_trace_to_table(line)
            if item.checkState():
                item.data.sidebar1D.update()

    def reload_linecuts(self,data,item_checkState):
        for orientation in data.linecuts.keys():
            if len(data.linecuts[orientation]['lines']) > 0:
                for line in data.linecuts[orientation]['lines'].keys():
                    if 'fit' in data.linecuts[orientation]['lines'][line].keys():
                        data.linecuts[orientation]['lines'][line]['fit']['fit_result'] = load_lmfit_modelresult_s(data.linecuts[orientation]['lines'][line]['fit']['fit_result'])
                    if 'draggable_points' in data.linecuts[orientation]['lines'][line].keys():
                        points=data.linecuts[orientation]['lines'][line]['points']
                        data.linecuts[orientation]['lines'][line]['draggable_points'] = [DraggablePoint(data,points[0][0],points[0][1],line,orientation),
                        DraggablePoint(data,points[1][0],points[1][1],line,orientation,draw_line=True)]
            #Then make the linecut window
                data.linecuts[orientation]['linecut_window'] = LineCutWindow(data,orientation=orientation,init_cmap='plasma',editor_window=self)
                data.linecuts[orientation]['linecut_window'].running = True
                for line in data.linecuts[orientation]['lines']:
                    data.linecuts[orientation]['linecut_window'].append_cut_to_table(line)
                if item_checkState:
                    data.linecuts[orientation]['linecut_window'].activateWindow()
                    data.linecuts[orientation]['linecut_window'].update()
                    data.linecuts[orientation]['linecut_window'].show()

    def add_internal_data(self,item,check_item=True,uncheck_others=True):
        # Add internal data to the file list (from combined plots/files, fitting dependency, etc)
        #item.filepath='internal_data'
        self.file_list.itemChanged.disconnect(self.file_checked)
        self.file_list.addItem(item)
        self.file_list.setCurrentItem(item)
        if uncheck_others:
            for item_index in range(self.file_list.count()-1):
                self.file_list.item(item_index).setCheckState(QtCore.Qt.Unchecked)
        if check_item:
            self.clear_sidebar1D()
            item.setCheckState(QtCore.Qt.Checked)
            self.file_checked(item)
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
                if hasattr(item.data,'sidebar1D'):
                    item.data.sidebar1D.close()
                if hasattr(item.data, 'linecuts'):
                    for orientation in item.data.linecuts.keys():
                        if item.data.linecuts[orientation]['linecut_window']:
                            item.data.linecuts[orientation]['linecut_window'].close()
                if isinstance(item.data, MixedInternalData):
                    self.mixeddata_filter_box.hide()
                if (item.data.filepath in self.linked_files
                    and not hasattr(item, 'duplicate')):
                    self.linked_files.remove(item.data.filepath)
                index = self.file_list.row(item)
                self.file_list.takeItem(index)
                del item
        self.show_current_all()
        if update_plots:
            self.update_plots()

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

    def open_files_from_folder(self, rootdir=None):
        if not rootdir:
            rootdir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory to Open")
        if rootdir:
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
                                    self.log_error(f'Failed to get creation time for {filepath}:\n{type(e).__name__}: {e}')
                            filepaths.append((st_ctime,filepath,subdir))
            if not os.path.split(filepaths[0][2])[1].startswith('#'): #If it's qcodespp data, it's already sorted. If not, sort by time
                filepaths.sort(key=lambda tup: tup[0])
            self.open_files([file[1] for file in filepaths])
    
    def check_already_loaded(self, subdir, filepaths):
        loaded=False
        for filepath in filepaths:
            if subdir in filepath:
                loaded=True
        return loaded
        
    def update_link_to_folder(self, new_folder=True, folder=None):
        if folder is not None:
            self.linked_folder = folder
        elif new_folder:
            self.linked_folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory to Link")
        if self.linked_folder:
            self.set_window_title()
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
                                paths=[item.filepath for item in self.get_all_items() if 
                                       item.filepath not in ['internal_data','mixed_internal_data']]
                                for file in paths:
                                    if os.path.basename(subdir) in file:
                                        already_linked=True
                                        break
                                if not already_linked:
                                    try: # on Windows
                                        st_ctime = os.path.getctime(filepath)
                                    except Exception:
                                        try: # on Mac
                                            st_ctime = os.stat(filepath).st_birthtime
                                        except Exception as e:
                                            self.log_error(f'Failed to get creation time for {filepath}:\n{type(e).__name__}: {e}')
                                    new_files.append((st_ctime,filepath,subdir))

                            else:
                                if filepath not in self.linked_files:
                                    try: # on Windows
                                        st_ctime = os.path.getctime(filepath)
                                    except Exception:
                                        try: # on Mac
                                            st_ctime = os.stat(filepath).st_birthtime
                                        except Exception as e:
                                            self.log_error(f'Failed to get creation time for {filepath}:\n{type(e).__name__}: {e}')
                                    new_files.append((st_ctime,filepath,subdir))
            if new_files:
                if not os.path.split(new_files[0][2])[1].startswith('#'): #If it's qcodespp data, it's already sorted. If not, sort by time
                    new_files.sort(key=lambda tup: tup[0])
                new_filepaths = [new_file[1] for new_file in new_files]
                self.open_files(new_filepaths)
                for new_filepath in new_filepaths:
                    self.linked_files.append(new_filepath) 
                    
    def unlink_folder(self):
        if self.linked_folder:
            self.linked_folder = None
            self.set_window_title()
            
    def refresh_files(self):
        checked_items = self.get_checked_items()
        if self.linked_folder:
            old_number_of_items = self.file_list.count()
            self.update_link_to_folder(new_folder=False)
            if self.file_list.count() > old_number_of_items:
                last_item = self.file_list.item(self.file_list.count()-1)
                self.file_checked(last_item)
            elif checked_items:
                for item in checked_items:
                    if hasattr(item.data,'dim') and item.data.dim==2 and not isinstance(item.data, qcodesppData):
                        line=0
                    else:
                        line=None
                    item.data.prepare_data_for_plot(reload_data=True, reload_from_file=True, linefrompopup=line)
                self.update_plots()
                for item in checked_items:
                    item.data.reset_axlim_settings()
                    self.show_current_axlim_settings()
                    self.canvas.draw()
            
    def save_session(self, save_as=False):
        old_title = self.windowTitle()
        saved=False
        current_item = self.file_list.currentItem()
        if current_item:

            try:
                if save_as or not hasattr(self,'session_filepath'):
                    filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
                        self, 'Save Session As...', '', '*.igs')
                else:
                    filepath = self.session_filepath
        
                if filepath:
                    self.setWindowTitle(old_title + " - Saving session...")
                    items = [self.file_list.item(n) for n in range(self.file_list.count())]
                    save_error_log=[]
                    dirpath = os.path.dirname(filepath)

                    # Try to remove any temporary files from any failed loads or saves
                    if os.path.exists(dirpath+'/igtemp'):
                        error = self.remove_temp_files(dirpath)
                        if error:
                            self.log_error(f'Error removing temporary files before loading session:\n'
                                           f'{type(error).__name__}: {error}')

                    dictionary_list = []
                    os.makedirs(dirpath+'/igtemp', exist_ok=True)
                    for item in items:
                        try:
                            item_dictionary = {}
                            if hasattr(item,'filepath'):
                                item_dictionary['filepath']=item.filepath.replace('\\','/') # Replace backslashes with forward slashes for compatibility
                            if hasattr(item,'checkState'):
                                item_dictionary['checkState']=item.checkState()
                            if hasattr(item,'duplicate'):
                                item_dictionary['duplicate']=item.duplicate
                            if item == current_item:
                                item_dictionary['is_current_item'] = True
                            attributes=['label','settings','filters','view_settings','axlim_settings',
                                        'plot_type','dim','labels_changed','legend',
                                        'raw_data','processed_data']
                            if isinstance(item.data, InternalData):
                                attributes.extend(['loaded_data','all_parameter_names','dim'])
                            elif isinstance(item.data, MixedInternalData):
                                item_dictionary['dataset2d_type'] = str(item.data.dataset2d_type)
                                item_dictionary['dataset1d_type'] = str(item.data.dataset2d_type)
                                attributes.extend(['dataset1d_filepath','dataset2d_filepath',
                                        'dataset1d_loaded_data','dataset2d_loaded_data',
                                        'dataset1d_label','dataset2d_label',
                                        'dataset1d_all_parameter_names','dataset2d_all_parameter_names',
                                        'dataset1d_dim','dataset2d_dim','show_2d_data'])
                                if hasattr(item.data.dataset2d,'linecuts'):
                                    item_dictionary['dataset2d_linecuts'] = self.remove_linecutwindows_and_fits(item.data.dataset2d.linecuts)
                                if hasattr(item.data.dataset1d,'plotted_lines'):
                                    item_dictionary['dataset1d_plotted_lines'] = self.remove_linecutwindows_and_fits(item.data.dataset1d.plotted_lines)

                            for attribute in attributes:
                                if hasattr(item.data,attribute):
                                    item_dictionary[attribute]=getattr(item.data,attribute)

                            if hasattr(item.data,'extra_cols'):
                                item_dictionary['extra_cols'] = {}
                                for colname in item.data.extra_cols:
                                    item_dictionary['extra_cols'][colname] = {'data': item.data.data_dict[colname]}
                                    if isinstance(item.data, qcodesppData):
                                        item_dictionary['extra_cols'][colname]['channel'] = item.data.channels[colname]

                            if hasattr(item.data,'linecuts'):
                                item_dictionary['linecuts'] = self.remove_linecutwindows_and_fits(item.data.linecuts)

                            if hasattr(item.data,'plotted_lines'):
                                item_dictionary['plotted_lines'] = self.remove_linecutwindows_and_fits(item.data.plotted_lines)

                            dictionary_list.append(item_dictionary)
                        except Exception as e:
                            save_error_log.append(f'Error saving item {item.filepath}:\n{type(e).__name__}: {e}')
                            self.log_error(f'Error saving item {item.filepath}:\n{type(e).__name__}: {e}')

                    from qcodespp import __version__
                    # The last item is reserved for 'global' program information.
                    dictionary_list.append({
                        'qcodespp_version': __version__,
                        'show_linecut_markers': self.show_linecut_markers
                    })

                    # Save all needed files to a temperorary directory and add them to the tarball
                    np.save(dirpath+'/igtemp/numpyfile.npy', dictionary_list)
                    with tarfile.open(filepath, 'w:gz') as tar:
                        for filename in os.listdir(dirpath+'/igtemp'):
                            tar.add(dirpath+'/igtemp/'+filename, arcname='igtemp/'+filename, recursive=False)

                    saved=True
                    self.session_filepath = filepath

                    self.log_error(f'Session saved as {filepath}')

                    if len(save_error_log)>0:
                        error_message = ('The session was only partially saved; the following errors occurred:\n\n' 
                                              + '\n\n'.join(save_error_log))
                        self.ew = ErrorWindow(error_message)

                    error = self.remove_temp_files(dirpath)

                    if error:
                        message=(f'Error cleaning up temporary files after saving session: {error}\n\n'
                                'Do not panic! The session should have been saved successfully (unless you were warned of any '
                                'other errors). You can safely delete the igtemp folder in the session directory if you like, '
                                'or simply let InSpectra Gadget delete it next time you load or save a session.'
                                'This usually happens if a cloud service tries to sync the temporary files '
                                'exactly when InSpectra Gadget is trying to delete them.')
                        self.log_error(message, show_popup=True)
                    
                    del dictionary_list

            except Exception as e:
                self.log_error(f'Error saving session:\n{type(e).__name__}: {e}', show_popup=True)
        self.set_window_title()
        return saved

    def remove_linecutwindows_and_fits(self,d,exclude_key='linecut_window',exclude_key2='fit_result',
                                       exclude_key3='draggable_points'):
    # Remove linecut window object, lmfit results, and draggable points from the dictionary. None can be pickled. 
    # lmfit fit results are serialized as json strings and saved in place. Linecut windows are not special so are just removed, and 
    # draggable points are also removed and simply reinstated by knowing their co-ordinates, which are saved in the dictionary anyway.

        new_dict = {}
        for key, value in d.items():
            if isinstance(value, dict):
                # Recurse into nested dictionaries
                new_dict[key] = self.remove_linecutwindows_and_fits(value,exclude_key,exclude_key2,exclude_key3)
            else:
                # For non-dictionary values, just copy them
                new_dict[key] = value

        if exclude_key in new_dict:
            new_dict[exclude_key] = None  # Remove the linecut window object
        if exclude_key3 in new_dict:
            new_dict[exclude_key3] = None # Remove the draggable points object

        if exclude_key2 in new_dict:
            try:
                new_dict[exclude_key2] = new_dict[exclude_key2].dumps() # Save the lmfit object as a json string
            except Exception as e:
                self.save_error_log.append(f'Error saving fit result during session save: {e}')
                new_dict[exclude_key2] = None

        return new_dict
    
    def remove_temp_files(self,dirpath,attempts=5):
        # Remove the temporary files created during session save/load. Returns an error message, or False (i.e. no error) if successful.
        for attempt in range(attempts):
            error = self.single_remove_attempt(dirpath)
            if not error:
                break
            time.sleep(1)
        if error:
            return error
        else:
            return False

    def single_remove_attempt(self,dirpath):
        # Helper function to remove temporary files. Returns an error message, or False (i.e
        try:
            for filename in os.listdir(dirpath+'/igtemp'):
                file_path = os.path.join(dirpath+'/igtemp', filename)
                os.remove(file_path)
            os.rmdir(dirpath+'/igtemp')
            return False
        except Exception as e:
            return e

    def load_session(self,filepath=None):
        old_title = self.windowTitle()
        # First warn the user they will lose any unsaved work.
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle("Warning")
        msg_box.setText("Restoring a saved session will cause any unsaved work in the current session to be lost.")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        ret = msg_box.exec_()
        if ret != QtWidgets.QMessageBox.Ok:
            return

        # Then prompt to load the session
        if filepath is None:
            session_filepath, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Session', '', 'Inspectra Gadget session (*.igs)')
        else:
            session_filepath = filepath

        if session_filepath:
            dirpath = os.path.dirname(session_filepath)
            self.setWindowTitle(old_title + " - Loading session...")
            # Try to remove any temporary files from any failed loads or saves
            if os.path.exists(dirpath+'/igtemp'):
                error = self.remove_temp_files(dirpath)
                if error:
                    self.log_error(f'Error removing temporary files before loading session:\n{type(error).__name__}: {error}')

            if self.file_list.count() > 0:
                self.remove_files('all')
            
            try:
                # Extract the tarball to a temporary directory
                with tarfile.open(session_filepath, 'r') as tar:
                    tar.extractall(dirpath)
                # Load the numpy file containing the session data

                numpy_file=np.load(dirpath+'/igtemp/numpyfile.npy', allow_pickle=True)

                # Extract only the elements of the numpy array that are dictionaries representing data items
                data=[item for item in numpy_file if isinstance(item, dict) and 'filepath' in item.keys()]
                file_list=[attr_dict['filepath'] for attr_dict in data]

                # Use the resolve_missing_files function to check for missing files. Ask the user if they want to quit loading the session
                ret_mes = self.resolve_missing_files(file_list)
                if ret_mes == 'cancel':
                    self.log_error('Session loading cancelled.', show_popup=True)

                else:
                    file_list, unresolved_files = ret_mes
                    if len(unresolved_files) > 0:
                        msg_box = QtWidgets.QMessageBox(self)
                        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
                        msg_box.setWindowTitle("Warning")
                        msg_box.setText(f"{len(unresolved_files)} files could not be found. Click OK to continue "
                                        "loading the session without them, or cancel to stop loading the session.")
                        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
                        ret = msg_box.exec_()
                        if ret == QtWidgets.QMessageBox.Ok:
                            try:
                                data = [data[i] for i in range(len(data)) if data[i]['filepath'].replace('\\','/') not in unresolved_files]
                                for i, filepath in enumerate(file_list):
                                    data[i]['filepath'] = filepath
                                self.open_files(file_list,attr_dicts=data)

                            except Exception:
                                pass
                    else:
                        # most of the loading actually happens in the open_files function.
                        try:
                            for i, filepath in enumerate(file_list):
                                data[i]['filepath'] = filepath
                            self.open_files(file_list,attr_dicts=data)
                        except Exception: # If it fails, the messages should occur during open_files. And we need to keep going, to ensure temporary files are deleted
                            pass

                    try:
                        if 'show_linecut_markers' in numpy_file[-1]:
                            self.show_linecut_markers = numpy_file[-1]['show_linecut_markers']
                    except Exception as e:
                        self.log_error(f'Error loading show_linecut_markers from session:\n{type(e).__name__}: {e}')
                self.session_filepath = session_filepath
                self.log_error(f'Session loaded from {session_filepath}')
                del data
            except Exception as e:
                self.log_error(f'Error loading session:\n{type(e).__name__}: {e}',show_popup=True)

            error = self.remove_temp_files(dirpath)
            if error:
                message=(f'Error cleaning up temporary files after loading session:\n{type(error).__name__}: {error}\n'
                        'Do not panic! The session should have saved successfully (unless you were warned of any '
                        'other errors) and you can safely delete the igtemp folder in the session directory, or let '
                        'InSpectra Gadget do it next time you load or save a session.\n'
                        'This usually happens if a cloud service (e.g. OneDrive, Dropbox) tries to sync the temporary files '
                        'exactly when InSpectra Gadget tries to delete them. ')
                self.log_error(message, show_popup=True)

            self.update_plots() # Necessary to ensure some settings are applied to the final plot.
        self.set_window_title()

    def resolve_missing_files(self, filenames):
        resolved_files = []
        unresolved_files = []
        replacements = []
        for fname in filenames:
            fname = fname.replace('\\', '/')  # Ensure forward slashes
            if fname in ['internal_data', 'mixed_internal_data'] or os.path.exists(fname):
                resolved_files.append(fname)
                continue

            if len(replacements)>0:
                # Try to apply previous replacement patterns
                found=False
                for replacement in replacements:
                    try:
                        # Replace the differing part
                        candidate = fname.replace(*replacement)
                        if os.path.exists(candidate):
                            resolved_files.append(candidate)
                            found=True
                            break
                    except Exception:
                        pass
                if found:
                    continue
            
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Warning)
            msg_box.setWindowTitle("Warning")
            message = (f'File not found: {fname}\nClick OK to locate the file, '
                       'Ignore to skip this file or Cancel to abort session load.\n'
                       'If you locate the file, its location will be used to try to find other missing files.')
            msg_box.setText(message)
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Ignore | QtWidgets.QMessageBox.Cancel)
            ret = msg_box.exec_()
            if ret == QtWidgets.QMessageBox.Ignore:
                unresolved_files.append(fname)
                continue
            elif ret == QtWidgets.QMessageBox.Cancel:
                return 'cancel'

            new_fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Locate File", "", "All Files (*)")
            if new_fname and os.path.exists(new_fname):
                resolved_files.append(new_fname)
                # Find replacement pattern for subsequent files
                for i,(char1,char2) in enumerate(zip(fname[::-1], new_fname[::-1])):
                    if char1 != char2:
                        replacements.append((fname[:-i], new_fname[:-i]))
                        break
            else:
                unresolved_files.append(fname)
 
        return resolved_files, unresolved_files

    def export_processed_data(self, which='current'):
        current_item = self.file_list.currentItem()
        if current_item:
            if which == 'current':
                formats='JSON (*.json);;CSV (*.csv);;Numpy text (*.dat)'
            elif which == 'Z':
                formats='Numpy text (*.dat)'
            suggested_filename = current_item.data.label
            filepath, ext = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Export Data As', suggested_filename, formats)
            if which == 'current':
                if hasattr(current_item.data,'processed_data'):
                    if '.dat' in ext:
                        header=''
                        with open(filepath, "w") as dat_file:
                            try:
                                if current_item.data.dim==3:
                                    labels=['xlabel','ylabel','clabel']
                                    for label in labels:
                                        if current_item.data.settings[label] != '':
                                            header+=f'{current_item.data.settings[label]}\t'
                                    header=header.strip('\t')
                                    dat_file.write(f'# {header}\n')
                                    for j in range(np.shape(current_item.data.processed_data[2])[0]):
                                        for k in range(np.shape(current_item.data.processed_data[2])[1]):
                                            dat_file.write('{}\t{}\t{}\n'.format(current_item.data.processed_data[0][j,k],current_item.data.processed_data[1][j,k],current_item.data.processed_data[2][j,k]))
                                elif current_item.data.dim == 2:
                                    if current_item.data.plot_type == 'Histogram':
                                        self.log_error('Cannot save 1D histogram data as .dat. Use .json or .csv instead.', 
                                                       show_popup=True)
                                    else:
                                        processed_data=[]
                                        for line in current_item.data.plotted_lines.keys():
                                            if current_item.data.plotted_lines[line]['checkstate']:
                                                header+=f'{line}_{current_item.data.plotted_lines[line]["X data"]}\t{line}_{current_item.data.plotted_lines[line]["Y data"]}\t'
                                                processed_data.append(current_item.data.plotted_lines[line]['processed_data'][0])
                                                processed_data.append(current_item.data.plotted_lines[line]['processed_data'][1])
                                        np.savetxt(filepath, np.column_stack(processed_data),header=header)
                            except Exception as e:
                                self.log_error(f'Error saving processed data as .dat:\n{type(e).__name__}: {e}', show_popup=True)

                    else:
                        data={}
                        try:
                            if current_item.data.dim==3:
                                labels={'xlabel':'X',
                                        'ylabel':'Y',
                                        'clabel':'Z'}
                                for i,label in enumerate(labels.keys()):
                                    if current_item.data.settings[label] != '' and current_item.data.settings[label] not in data.keys():
                                        data[current_item.data.settings[label]]=current_item.data.processed_data[i].flatten().tolist()
                                    elif current_item.data.settings[label] == '':
                                        data[labels[label]]=current_item.data.processed_data[i].flatten().tolist()
                                    else:
                                        data[f'{current_item.data.settings[label]}_1']=current_item.data.processed_data[i].flatten().tolist()

                            elif current_item.data.dim == 2:
                                for line in current_item.data.plotted_lines.keys():
                                    if current_item.data.plotted_lines[line]['checkstate']:
                                        if current_item.data.plot_type == 'Histogram':
                                            headers=[f'{line}_{current_item.data.plotted_lines[line]['Y data']}_bins',
                                                    f'{line}_{current_item.data.plotted_lines[line]['Y data']}_counts',
                                                    f'{line}_{current_item.data.plotted_lines[line]['Y data']}_bins_fit']
                                        else:
                                            headers=[f'{line}_{current_item.data.plotted_lines[line]['X data']}',
                                                    f'{line}_{current_item.data.plotted_lines[line]['Y data']}',
                                                    f'{line}_{current_item.data.plotted_lines[line]['X data']}_fit']
                                        data[headers[0]]=current_item.data.plotted_lines[line]['processed_data'][0].tolist()
                                        data[headers[1]]=current_item.data.plotted_lines[line]['processed_data'][1].tolist()
                                        if 'fit' in current_item.data.plotted_lines[line].keys() and current_item.data.plotted_lines[line]['fit']['fit_checkstate']:
                                            data[headers[2]]=current_item.data.plotted_lines[line]['fit']['xdata'].tolist()
                                            fit_result=current_item.data.plotted_lines[line]['fit']['fit_result']
                                            data[f'{line}_{current_item.data.plotted_lines[line]['Y data']}'+'_fit']=fit_result.best_fit.tolist()
                                            data[f'{line}_{current_item.data.plotted_lines[line]['Y data']}'+'_fit_error']=fit_result.eval_uncertainty().tolist()
                                            fit_components=fit_result.eval_components()
                                            for component in fit_components:
                                                data[f'{line}_{current_item.data.plotted_lines[line]['Y data']}'+'_'+component]=fit_components[component].tolist()
                        except Exception as e:
                            self.log_error(f'Error processing data for export:\n{type(e).__name__}: {e}', show_popup=True)

                        if '.json' in ext:
                            try:
                                data['shape']=list(np.shape(current_item.data.processed_data[2]))
                                with open(filepath, 'w') as json_file:
                                    jsondump(data, json_file,ensure_ascii=False, indent=4)
                            except Exception as e:
                                self.log_error(f'Error exporting processed data as .json:\n{type(e).__name__}: {e}', show_popup=True)

                        elif '.csv' in ext:
                            try:
                                with open(filepath, 'w', newline='') as f:
                                    writer = csvwriter(f)
                                    if current_item.data.dim==3:
                                        header=[]
                                        for label in data.keys():
                                            header.append(f'#{label}')
                                        writer.writerow(header)
                                        for j in range(np.shape(current_item.data.processed_data[2])[0]):
                                            for k in range(np.shape(current_item.data.processed_data[2])[1]):
                                                writer.writerow([current_item.data.processed_data[0][j,k],current_item.data.processed_data[1][j,k],current_item.data.processed_data[2][j,k]])
                                    elif current_item.data.dim == 2:
                                        writer.writerow([key for key in data.keys()])
                                        lengths = [len(data[key]) for key in data.keys()]
                                        for i in range(np.max(lengths)):
                                            row = []
                                            for key in data.keys():
                                                try:
                                                    row.append(data[key][i])
                                                except IndexError:
                                                    row.append('')
                                            writer.writerow(row)
                            except Exception as e:
                                self.log_error(f'Error exporting processed data as .csv:\n{type(e).__name__}: {e}', show_popup=True)
                else:
                    self.log_error('No processed data to export', show_popup=True)

            elif which=='Z':
                if hasattr(current_item.data,'processed_data'):
                    if '.dat' in ext:
                        try:
                            with open(filepath,'w') as dat_file:
                                np.savetxt(filepath, current_item.data.processed_data[-1])
                        except Exception as e:
                            self.log_error(f'Error exporting processed Z data as .dat:\n{type(e).__name__}: {e}', show_popup=True)
                    else:
                        self.log_error('Exporting processed Z data as MxN array only possible to .dat files.')
                else:
                    self.log_error('No processed data to export', show_popup=True)
               
    def file_checked(self, item):
        if item.checkState() == 2:
            self.file_list.setCurrentItem(item)
            self.show_or_hide_mixeddata_widgets()
        self.update_plots()

    def file_double_clicked(self, item):
        self.file_list.itemChanged.disconnect(self.file_checked)
        for item_index in range(self.file_list.count()):
            self.file_list.item(item_index).setCheckState(QtCore.Qt.Unchecked)
        item.setCheckState(QtCore.Qt.Checked)
        self.file_list.itemChanged.connect(self.file_checked)
        self.update_plots()

    def file_clicked(self):
        current_item = self.file_list.currentItem()
        if hasattr(current_item,'data') and hasattr(current_item.data,'dim'):
            dim=current_item.data.dim
        else:
            dim=None
        self.reset_filters_combobox(dim)
        self.show_current_all()
        self.clear_sidebar1D()
        if hasattr(current_item.data,'sidebar1D'):
            self.oneD_layout.addWidget(current_item.data.sidebar1D)
        self.show_or_hide_mixeddata_widgets()

    def plot_type_changed(self):
        current_item = self.file_list.currentItem()
        plot_type = self.plot_type_box.currentText()
        current_item.data.plot_type=plot_type

        lineedits={'X':self.binsX_lineedit,
            'Y':self.binsY_lineedit}
        labels={'X':self.binsX_label,
            'Y':self.binsY_label}
        
        self.binsX_lineedit.hide()
        self.binsY_lineedit.hide()
        self.binsX_label.hide()
        self.binsY_label.hide()
        if hasattr(current_item.data,'sidebar1D'):
            # current_row = current_item.data.sidebar1D.trace_table.currentRow()
            # line = int(current_item.data.sidebar1D.trace_table.item(current_row,0).text())
            current_item.data.sidebar1D.plot_type_changed()
            self.update_plots(update_data=False)
        
        else:
            if 'Histogram' in plot_type:
                try:
                    which=plot_type.split(' ')[1]
                    
                    labels[which].show()
                    lineedits[which].show()

                    if f'bins{which}' not in current_item.data.settings.keys():
                        current_item.data.settings[f'bins{which}'] = 100
                
                    lineedits[which].setText(str(current_item.data.settings[f'bins{which}']))
                except Exception as e:
                    self.log_error(f'Could not change plot type:\n{type(e).__name__}: {e}', show_popup=True)

            self.update_plots(update_data=True,update_color_limits=True)

        self.reset_axlim_settings()

    def bins_changed(self,which='X'):
        lineedits={'X':self.binsX_lineedit,'Y':self.binsY_lineedit}
        current_item = self.file_list.currentItem()
        current_item.data.settings[f'bins{which}'] = int(lineedits[which].text())
        self.update_plots()

    def show_2d_data_checkbox_changed(self):
        current_item = self.file_list.currentItem()
        if isinstance(current_item.data, MixedInternalData):
            current_item.data.show_2d_data = self.show_2d_data_checkbox.isChecked()
            self.update_plots()
    
    def legend_checkbox_changed(self):
        current_item = self.file_list.currentItem()
        if hasattr(current_item,'data'):
            current_item.data.legend = self.legend_checkbox.isChecked()
            self.update_plots()

    def show_or_hide_view_settings(self):
        current_item = self.file_list.currentItem()
        if current_item:
            if (hasattr(current_item, 'data') and (hasattr(current_item.data, 'dim') and current_item.data.dim == 3 
                                                   or isinstance(current_item.data, MixedInternalData))):
                self.stats_button.show()
                self.legend_checkbox.hide()
                for i in range(self.view_layout.rowCount()):
                    for j in range(self.view_layout.columnCount()):
                        try:
                            self.view_layout.itemAtPosition(i,j).widget().show()
                        except:
                            pass
            else:
                if (hasattr(current_item, 'data') and (hasattr(current_item.data, 'dim') and current_item.data.dim == 2)):
                    self.legend_checkbox.clicked.disconnect()
                    self.legend_checkbox.setChecked(current_item.data.legend)
                    self.legend_checkbox.clicked.connect(self.legend_checkbox_changed)
                    self.legend_checkbox.show()
                else:
                    self.legend_checkbox.hide()
                self.stats_button.hide()
                for i in range(self.view_layout.rowCount()):
                    for j in range(self.view_layout.columnCount()):
                        try:
                            self.view_layout.itemAtPosition(i,j).widget().hide()
                        except:
                            pass

    def show_or_hide_mixeddata_widgets(self):
        current_item = self.file_list.currentItem()
        if isinstance(current_item.data,MixedInternalData):
            self.show_2d_data_checkbox.show()
            self.show_2d_data_checkbox.setChecked(current_item.data.show_2d_data)
            self.plot_type_box.hide()
            self.plot_type_label.hide()
            self.mixeddata_filter_box.clear()
            self.mixeddata_filter_box.show()
            self.mixeddata_filter_box.addItem(f'Applied to 2D data: {current_item.data.dataset2d.label}')
            self.mixeddata_filter_box.addItem(f'Applied to 1D data: {current_item.data.dataset1d.label}')
        else:
            self.plot_type_box.show()
            self.plot_type_label.show()
            self.show_2d_data_checkbox.hide()
            self.mixeddata_filter_box.clear()
            self.mixeddata_filter_box.hide()
    
    def clear_sidebar1D(self):
        # clear the sidebar1D
        for i in reversed(range(self.oneD_layout.count())):
            widgetToRemove = self.oneD_layout.itemAt(i).widget()
            # remove it from the layout list
            self.oneD_layout.removeWidget(widgetToRemove)
            # remove it from the gui
            widgetToRemove.setParent(None)

    def update_plots(self, item=None,update_data=True,update_color_limits=False):
        minilog=[]

        self.figure.clf()

        self.clear_sidebar1D()

        checked_items = self.get_checked_items()
        if checked_items:
            rows, cols = self.subplot_grid[len(checked_items)-1]
            for index, item in enumerate(checked_items):
                try:
                    if not hasattr(item.data, 'processed_data'):
                        error=item.data.prepare_data_for_plot(reload_data=True)
                        if error:
                            self.log_error(f'Error preparing data for plot:\n{type(error).__name__}: {error}', show_popup=True)
                            item.setCheckState(QtCore.Qt.Unchecked)
                            continue
                    elif hasattr(item.data, 'dim'):
                        if item.data.dim == 3 and update_data==True: 
                            # Should only be called when updating 2D data: updating 1D data is taken care of in the datatype and sidebar
                            error=item.data.prepare_data_for_plot(update_color_limits=update_color_limits)
                            if error:
                                # Most 'errors' that occur here are not deadly. Just log them.
                                self.log_error(f'Error preparing 2D data for plot:\n{type(error).__name__}: {error}')
                        elif item.data.dim == 'mixed' and update_data==True: #If MixedInternalData
                            error=item.data.dataset2d.prepare_data_for_plot(update_color_limits=update_color_limits)
                            if error:
                                # Most 'errors' that occur here are not deadly. Just log them.
                                self.log_error(f'Error preparing 2D data for plot:\n{type(error).__name__}: {error}')

                    item.data.figure = self.figure
                    item.data.axes = item.data.figure.add_subplot(rows, cols, index+1)
                    error=item.data.add_plot(editor_window=self)
                    if isinstance(error, list) and len(error)>0:
                        for w in error:
                            minilog.append(f'Warning while plotting {item.data.label}\n{w.category.__name__}: {w.message}')
                            self.log_error(f'Warning while plotting {item.data.label}\n{w.category.__name__}: {w.message}')
                    elif error:
                        minilog.append(str(error))
                        self.log_error(str(error))
                        continue

                    if self.show_linecut_markers and hasattr(item.data, 'linecuts'):
                        for orientation in ['horizontal', 'vertical', 'diagonal']:
                            if len(item.data.linecuts[orientation]['lines']) > 0:
                                self.reinstate_markers(item,orientation)
                            if item.data.linecuts[orientation]['linecut_window'] is not None and item==self.file_list.currentItem():
                                # This can be really heavy if there's lots of linecuts and fits. Only run if file actually in focus.
                                item.data.linecuts[orientation]['linecut_window'].update()
                    if hasattr(item.data, 'sidebar1D') and self.file_list.currentItem() == item:
                        self.oneD_layout.addWidget(item.data.sidebar1D)
                except Exception as e:
                    self.log_error(f'Could not plot {item.data.filepath}:\n{type(e).__name__}: {e}')
                    minilog.append(f'Could not plot {item.data.filepath}:\n{type(e).__name__}: {e}')
                    continue
        try:
            self.show_current_all()
            self.figure.tight_layout()
            self.canvas.draw()
        except Exception as e:
            self.log_error(f'Exception encountered updating plots:\n{type(e).__name__}: {e}')
            minilog.append(f'Exception encountered updating plots:\n{type(e).__name__}: {e}')

        if len(minilog) > 0:
            message = 'The following errors/warnings occurred while plotting:\n\n'+'\n\n'.join(minilog)
            self.ew = ErrorWindow(message)

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

    def set_refresh_intervals(self, from_dropdown=False):
        self.refwind = AutoRefreshPopup(self, from_dropdown=from_dropdown)
        ret = self.refwind.exec_()
        if ret != 1:
            return False
        return True
    
    def start_stop_tracking(self):
        current_item = self.file_list.currentItem()
        if (not self.live_tracking and
            current_item and current_item.checkState()) and not current_item.data.file_finished():
            if self.ask_autorefresh:
                cont=self.set_refresh_intervals()
                if not cont:
                    return
            self.live_track_item = current_item
            self.live_track_item.setText('[LIVE] '+self.live_track_item.data.label)
            self.refresh_files()
            if hasattr(self.live_track_item.data, 'raw_data') and self.live_track_item.data.raw_data is not None:
                if self.live_track_item.data.dim == 3:
                    self.start_auto_refresh(self.refresh_2d)
                elif self.live_track_item.data.dim == 2:
                    self.start_auto_refresh(self.refresh_1d)
            else:
                self.start_auto_refresh(self.refresh_1d, wait_for_file=True)
        elif self.live_tracking:
            self.stop_auto_refresh()
        
    def start_auto_refresh(self, time_interval, wait_for_file=False):
        self.live_tracking = True
        self.auto_refresh_timer = QtCore.QTimer()
        self.auto_refresh_timer.setInterval(time_interval*1000)
        if wait_for_file:
            self.auto_refresh_timer.timeout.connect(self.wait_for_file_call)
        else:
            self.auto_refresh_timer.timeout.connect(self.auto_refresh_call)
        self.action_refresh_stop.setEnabled(True)
        self.auto_refresh_timer.start()
        self.window_title_auto_refresh = ' - Auto-Refreshing Enabled'
        self.set_window_title()
        self.auto_refresh_call()
        
    def wait_for_file_call(self):
        if self.live_track_item and self.live_track_item.checkState():
            self.live_track_item.data.prepare_data_for_plot(reload_data=True)
            if self.live_track_item.data.raw_data:
                self.auto_refresh_timer.stop()
                self.live_tracking=False
                self.start_stop_tracking()            
            
    def auto_refresh_call(self):
        if self.live_track_item and self.live_track_item.checkState():
            if self.live_track_item.data.file_finished():
                self.log_error('Stopped auto refresh')
                self.stop_auto_refresh()
            else:
                self.window_title_auto_refresh = ' - Auto-Refreshing Enabled (Refreshing...)'
                self.set_window_title()
                self.refresh_files()
                self.window_title_auto_refresh = ' - Auto-Refreshing Enabled'
                self.set_window_title()
        
    def stop_auto_refresh(self):
        self.live_tracking=False
        self.auto_refresh_timer.stop()
        self.action_refresh_stop.setEnabled(False)
        self.window_title_auto_refresh = ''
        self.set_window_title()
        self.live_track_item.setText(self.live_track_item.data.label)
        
    def show_current_all(self):
        self.populate_new_plot_settings()
        self.show_current_plot_settings()
        self.show_current_view_settings()
        self.show_current_filters()
        self.show_current_axscale_settings()
        self.show_current_axlim_settings()
        self.show_or_hide_view_settings()
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
        self.plot_type_box.currentIndexChanged.disconnect(self.plot_type_changed)
        try:
            boxes= [self.new_plot_X_box, self.new_plot_Y_box, self.new_plot_Z_box, self.plot_type_box]
            for combobox in boxes:
                combobox.clear()

            current_item = self.file_list.currentItem()
            if current_item:
                if hasattr(current_item.data, 'all_parameter_names'):
                    dim = len(current_item.data.get_columns())
                    if dim == 2:
                        self.new_plot_Z_label.hide()
                        self.new_plot_Z_box.hide()
                        boxes= [self.new_plot_X_box, self.new_plot_Y_box]
                    else:
                        self.new_plot_Z_label.show()
                        self.new_plot_Z_box.show()
                        boxes= [self.new_plot_X_box, self.new_plot_Y_box, self.new_plot_Z_box]
                    for combobox in boxes:
                        combobox.addItems(current_item.data.all_parameter_names)
                    self.new_plot_X_box.setCurrentIndex(0)
                    self.new_plot_Y_box.setCurrentIndex(1)
                    if dim == 3:
                        self.new_plot_Z_box.setCurrentIndex(2)
                
                if hasattr(current_item.data,'dim') and current_item.data.dim == 2:
                    plot_types=['X,Y','Histogram','FFT']
                else:
                    plot_types=['X,Y,Z', 'Histogram Y', 'Histogram X', 'FFT Y', 'FFT X', 'FFT X/Y']
                self.plot_type_box.addItems(plot_types)
                if hasattr(current_item.data, 'plot_type'):
                    if current_item.data.plot_type in plot_types:
                        self.plot_type_box.setCurrentText(current_item.data.plot_type)

                lineedits={'X':[self.binsX_lineedit],
                    'Y':[self.binsY_lineedit],
                    'X/Y':[self.binsX_lineedit,self.binsY_lineedit]}
                labels={'X':[self.binsX_label],
                    'Y':[self.binsY_label],
                    'X/Y':[self.binsX_label,self.binsY_label]}
                
                # Have to first hide to make sure the only correct one(s) shown
                for label in labels['X/Y']:
                    label.hide()
                for lineedit in lineedits['X/Y']:
                    lineedit.hide()
                
                if self.plot_type_box.currentText() in ['Histogram X', 'Histogram Y', 'Histogram X/Y']:
                    which=self.plot_type_box.currentText().split(' ')[1]
                    for label in labels[which]:
                        label.show()
                    for lineedit in lineedits[which]:
                        lineedit.show()

                if isinstance(current_item.data, qcodesppData):
                    self.metadata_button.show()
                else:
                    self.metadata_button.hide()
                 
        except Exception as e:
            self.log_error(f'Error populating new plot settings:\n{type(e).__name__}: {e}', show_popup=True)
        self.plot_type_box.currentIndexChanged.connect(self.plot_type_changed)

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
            if settings['CBarHist']:
                self.cbar_hist_checkbox.setCheckState(QtCore.Qt.Checked)
            else:
                self.cbar_hist_checkbox.setCheckState(QtCore.Qt.Unchecked)
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
            for _ in self.which_filters(current_item):
                try:
                    self.append_filter_to_table()
                except Exception as e:
                    self.log_error(f'Error appending filter:\n{type(e).__name__}: {e}', show_popup=True)

    def global_text_changed(self):
        self.global_text_size=self.global_text_lineedit.text()
        for item in range(self.file_list.count()):
            if hasattr(self.file_list.item(item),'data') and hasattr(self.file_list.item(item).data,'settings'):
                for setting in ['titlesize','labelsize','ticksize']:
                    if setting in self.file_list.item(item).data.settings.keys():
                        self.file_list.item(item).data.settings[setting] = self.global_text_size
            if self.file_list.item(item).checkState():
                self.file_list.item(item).data.apply_plot_settings()
                self.show_current_plot_settings()
        self.canvas.draw()
    
    def plot_setting_edited(self,setting_item=None,setting_name=None):
        current_item = self.file_list.currentItem()
        if current_item:
            current_item.data.old_settings = current_item.data.settings.copy()
            if setting_name is None:
                setting_name = self.settings_table.item(setting_item.row(), 0).text()
            for row in range(self.settings_table.rowCount()):
                value = self.settings_table.item(row, 1).text()
                name = self.settings_table.item(row, 0).text()
                current_item.data.settings[name] = value
            self.settings_table.clearFocus()
            try:
                if setting_name in ['X data', 'Y data', 'Z data','columns']:
                    if isinstance(current_item.data,MixedInternalData):
                        current_item.data.dataset2d.prepare_data_for_plot(reload_data=True,reload_from_file=False)
                    else:
                        current_item.data.prepare_data_for_plot(reload_data=True,reload_from_file=False)
                    self.check_all_filters(signal=None,manual_signal='Uncheck all')
                    self.update_plots()
                    self.reset_axlim_settings()
                elif setting_name in ['transpose', 'delimiter']:
                    current_item.data.prepare_data_for_plot(reload_data=True,reload_from_file=True)
                    self.update_plots()
                elif 'label' in setting_name:
                    axis=setting_name.strip('label')
                    current_item.data.label_locks[axis] = True
                    self.update_plots()
                elif setting_name == 'maskcolor' or setting_name == 'cmap levels':
                    current_item.data.apply_colormap()
                elif setting_name in ['rasterized', 'colorbar', 'minorticks','shading']:
                    self.update_plots()
                current_item.data.extension_setting_edited(self, setting_name)
                current_item.data.apply_plot_settings()
                self.canvas.draw()
            except Exception as e: # if invalid value is typed: reset to previous settings
                self.log_error(f'Invalid value of plot setting:\n{type(e).__name__}: {e}', show_popup=True)
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
                self.log_error(f'Invalid axis limit:\n{type(e).__name__}: {e}', show_popup=True)
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
                elif edited_setting == 'CBarHist':
                    if self.cbar_hist_checkbox.isChecked():
                        view_settings[edited_setting] = True
                        if not hasattr(current_item.data,'hax'):
                            current_item.data.add_cbar_hist()
                            self.figure.tight_layout()
                    else:
                        view_settings[edited_setting] = False
                        if hasattr(current_item.data, 'hax'):
                            current_item.data.hax.clear()
                            try:
                                current_item.data.hax.remove()
                            except:
                                pass
                            del current_item.data.hax
                            self.figure.tight_layout()
                
                current_item.data.apply_view_settings()
                self.canvas.draw()
            except Exception as e:
                self.log_error(f'Invalid value of colourbar setting:\n{type(e).__name__}: {e}', show_popup=True)
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

    def reset_color_limits(self):
        current_item = self.file_list.currentItem()
        if current_item:
            current_item.data.reset_view_settings(overrule=True)
            self.show_current_view_settings()
            if current_item.checkState():
                current_item.data.apply_view_settings()
                self.canvas.draw()
    
    def copy_plot_settings(self):
        current_item = self.file_list.currentItem()
        if current_item:
            self.copied_settings = current_item.data.settings.copy()
    
    def copy_filters(self):
        current_item = self.file_list.currentItem()
        if current_item:
            self.copied_filters = copy.deepcopy(self.which_filters(current_item))
            
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
            if which == 'copied':
                if self.copied_filters:
                    filters = copy.deepcopy(self.copied_filters)
            elif which == 'old':
                filters = copy.deepcopy(self.old_filters)
            self.which_filters(current_item,filters=filters)

            #self.show_current_filters() Now show_current_all below
            #current_item.data.apply_all_filters() <<-- seems unnecessary; this will be done at update_plots on next call.

            if current_item.checkState():
                self.update_plots(update_color_limits=True)
            self.reset_axlim_settings()
            self.show_current_all()

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
            menu.addAction('Duplicate (Ctrl+D)')
            menu.addSeparator()
            actions = ['Remove file','Check all','Uncheck all','Clear list','Remove unchecked']
            for entry in actions:
                action = QtWidgets.QAction(entry, self)
                menu.addAction(action)
            if len(checked_items) > 1:
                menu.addSeparator()
                menu.addAction('Combine checked files')

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
            elif signal.text() == 'Combine checked files':
                try:
                    self.combine_plots()
                except Exception as e:
                    self.log_error(f'Could not combine files:\n{type(e).__name__}: {e}', show_popup=True)

    def duplicate_item(self, new_plot_button=False):
        original_item = self.file_list.currentItem()
        original_row = self.file_list.row(original_item)
        X = self.new_plot_X_box.currentText()
        Y = self.new_plot_Y_box.currentText()
        Z = self.new_plot_Z_box.currentText()
        if original_item:
            try:
                self.clear_sidebar1D()
                # Copy over data if internal data, or else reload it as new item. 
                # The advantage of reloading is that the new data gets the correct data class; it won't be InternalData.
                if isinstance(original_item.data, InternalData):
                    item=DataItem(InternalData(self.canvas,original_item.data.loaded_data,
                                            original_item.data.label,
                                            original_item.data.all_parameter_names,
                                            dimension=original_item.data.dim))
                    item.filepath = 'internal_data'
                    self.add_internal_data(item,check_item=False,uncheck_others=False)
                
                elif isinstance(original_item.data, MixedInternalData):
                    item=DataItem(MixedInternalData(self.canvas,original_item.data.label,
                                            original_item.data.dataset2d_type, original_item.data.dataset1d_type,
                                            original_item.data.dataset2d_filepath, original_item.data.dataset1d_filepath,
                                            original_item.data.dataset1d_loaded_data,original_item.data.dataset2d_loaded_data,
                                            original_item.data.dataset1d_label,original_item.data.dataset2d_label,
                                            original_item.data.dataset1d_all_parameter_names,original_item.data.dataset2d_all_parameter_names,
                                            original_item.data.dataset1d_dim,original_item.data.dataset2d_dim))
                    item.filepath = 'mixed_internal_data'
                    self.add_internal_data(item,check_item=False,uncheck_others=False)
                else:
                    self.open_files(filepaths=[original_item.data.filepath],overrideautocheck=True)

                new_item = self.file_list.currentItem()
                current_row = self.file_list.currentRow()
                self.file_list.takeItem(current_row)
                self.file_list.insertItem(original_row + 1, new_item)
                self.file_list.setCurrentRow(original_row + 1)
                new_item.duplicate = True

                # Copy over settings
                new_item.data.settings = original_item.data.settings.copy()
                new_item.data.view_settings = original_item.data.view_settings.copy()
                new_item.data.axlim_settings = original_item.data.axlim_settings.copy()
                # Copy filters to the correct location.
                self.which_filters(new_item,filters=copy.deepcopy(original_item.data.filters))
                #new_item.data.filters = copy.deepcopy(original_item.data.filters)
                if (hasattr(original_item.data, 'linecuts') and
                    any([len(original_item.data.linecuts[orientation]['lines'])>0 for orientation in ['horizontal','vertical','diagonal']])):
                    self.copy_linecuts(orientation='all',item=original_item)

                # Naming the new item in the file-list. qcpp gets special treatment, assuming the counter always comes first in the filename.
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
                        new_label=f'{original_label.split('_')[0]}-{duplicate_index}-{original_label.split("_")[1]}'
                    new_item.setText(new_label)
                    new_item.data.label = new_label
                    new_item.data.settings['title']=new_label

                else:
                    new_item.setText(f'Duplicate: {new_item.data.label}')
                    new_item.data.label = f'Duplicate: {new_item.data.label}'
                
                # Making new plot if 'Add new plot' button was pressed
                if new_plot_button:
                    if original_item.data.dim==3 or isinstance(original_item.data, MixedInternalData):
                        new_item.data.settings['X data'] = X
                        new_item.data.settings['Y data'] = Y
                        new_item.data.settings['Z data'] = Z
                    else:
                        # Next two lines basically fix a bug.
                        new_item.data.settings['X data'] = original_item.data.all_parameter_names[0]
                        new_item.data.settings['Y data'] = original_item.data.all_parameter_names[1]
                        new_item.data.prepare_data_for_plot()
                        new_item.data.sidebar1D = Sidebar1D(new_item.data,editor_window=self)
                        new_item.data.sidebar1D.running=True
                        new_item.data.plotted_lines = {0: {'checkstate': 2,
                                                'X data': X,
                                                'Y data': Y,
                                                'Bins': 100,
                                                'Xerr': 0,
                                                'Yerr': 0,
                                                'raw_data': new_item.data.raw_data,
                                                'processed_data': new_item.data.processed_data,
                                                'linecolor': (0.1, 0.5, 0.8, 1),
                                                'linewidth': 1.5,
                                                'linestyle': '-',
                                                'filters': []}}

                        new_item.data.sidebar1D.append_trace_to_table(0)
                        self.oneD_layout.addWidget(new_item.data.sidebar1D)

                elif original_item.data.dim==2:
                    # Next two lines basically fix a bug.
                    new_item.data.settings['X data'] = original_item.data.all_parameter_names[0]
                    new_item.data.settings['Y data'] = original_item.data.all_parameter_names[1]
                    new_item.data.prepare_data_for_plot()
                    # Populate trace table from original data. This doesn't work. It links the new item to the old one.
                    # if hasattr(original_item.data, 'plotted_lines'):
                    #     new_item.data.sidebar1D = Sidebar1D(new_item.data,self)
                    #     new_item.data.sidebar1D.running=True
                    #     new_item.data.plotted_lines = {}
                    #     for line in original_item.data.plotted_lines:
                    #         new_item.data.plotted_lines[line] = copy.deepcopy(original_item.data.plotted_lines[line])
                    #         new_item.data.sidebar1D.append_trace_to_table(line)
                    #     self.oneD_layout.addWidget(new_item.data.sidebar1D)
                    new_item.data.init_plotted_lines()

                new_item.setCheckState(QtCore.Qt.Checked)
                if new_plot_button and new_item.data.dim == 3:
                    self.plot_setting_edited(setting_name='X data')
                self.update_plots()
                if (hasattr(original_item.data, 'linecuts') and
                    any([len(original_item.data.linecuts[orientation]['lines'])>0 for orientation in ['horizontal','vertical','diagonal']])):
                    self.paste_linecuts(new_item)

            except Exception as e:
                self.log_error(f'Error duplicating item:\n{type(e).__name__}: {e}', show_popup=True)

    def combine_plots(self):
        checked_items = self.get_checked_items()
        if checked_items:
            try:
                data_list = []
                label_name=f'Combined: '
                for item in checked_items:
                    data_list.append(item.data)
                    label_name+=item.data.label[:15]+'..., '

                if any([isinstance(item,MixedInternalData) for item in data_list]):
                    # MixedInternalData cannot be combined any further.
                    self.log_error('Cannot combine mixed 1D and 2D datasets with other datasets.', show_popup=True)

                elif not all(hasattr(item, 'dim') for item in data_list):
                    # If any item doesn't have a dim, it's because the data is not loaded yet. 
                    self.log_error(f'Cannot combine items: data from one or more items not yet loaded.', show_popup=True)

                elif all([item.dim == 3 for item in data_list]):
                    # If sets of 2D datasets, stack them along the x-axis. Requires y axis has same dimension for all datasets
                    if not all(item.all_parameter_names == data_list[0].all_parameter_names for item in data_list):
                        self.log_error(f'Cannot combine 2D datasets with different parameters.', show_popup=True)
                        raise ValueError('Cannot combine 2D datasets with different parameters.')
                    elif not all(item.get_columns()[1] == data_list[0].get_columns()[1] for item in data_list):
                        self.log_error(f'Cannot combine 2D datasets with different y axes.', show_popup=True)
                        raise ValueError('Cannot combine 2D datasets with different y axes.')
                    combined_data=[]
                    combined_parameter_names=[]
                    for i,parameter_name in enumerate(data_list[0].all_parameter_names):
                        # The first parameter in qcodespp data is 1D, so we need to stack it differently.
                        if i == 0 and all(isinstance(data_list[j],qcodesppData) for j in range(len(data_list))):
                            xdata=np.hstack([data_list[j].dataset.arrays[parameter_name] for j in range(len(data_list))])
                            combined_data.append(xdata.T)
                            combined_parameter_names.append(parameter_name)
                        # For all other datatypes and all other parameters, try both stacking methods.
                        else:
                            try:
                                combined_data.append(np.vstack([data_list[j].data_dict[parameter_name] for j in range(len(data_list))]))
                                combined_parameter_names.append(parameter_name)
                            except ValueError:
                                try:
                                    combined_data.append(np.hstack([data_list[j].data_dict[parameter_name] for j in range(len(data_list))]))
                                    combined_parameter_names.append(parameter_name)
                                except ValueError as e:
                                    self.log_error(f'Error combining data for {parameter_name}:\n{type(e).__name__}: {e}\nCheck data dimesions', 
                                                show_popup=True)
                    if len(combined_data[0].shape) == 1: # Try to catch BaseClassData that also has a first independent param that is 1D, but this should never happen.
                        combined_data[0]=np.tile(combined_data[0],(combined_data[1].shape[1],1)).T
                    combined_item=DataItem(InternalData(self.canvas,combined_data,label_name,combined_parameter_names,dimension=3))
                    combined_item.filepath = 'internal_data'
                    self.add_internal_data(combined_item)

                elif all([item.dim == 2 for item in data_list]):
                    # For only 1D data, just pile all parameters into a new dataset.
                    combined_data=[]
                    combined_parameter_names=[]
                    for i, data in enumerate(data_list):
                        for parameter_name in data.all_parameter_names:
                            combined_data.append(data.data_dict[parameter_name])
                            new_name= f'{data.label[:4]}: {parameter_name}'
                            if new_name not in combined_parameter_names:
                                combined_parameter_names.append(new_name)
                            else:
                                # If the name already exists, append the index to make it unique.
                                combined_parameter_names.append(f'{new_name}_{i}')
                    combined_item=DataItem(InternalData(self.canvas,combined_data,label_name,combined_parameter_names,dimension=2))
                    combined_item.filepath = 'internal_data'
                    self.add_internal_data(combined_item)

                else:
                    finalerrormessage=('There are three possibilities when combining datasets: \n'
                          '1. Any number of 1D datasets with aribtrary dimension; all parameters available for plotting\n'
                          '2. Any number of 2D datasets with same sets of parameters and y-axis length. The datasets are stacked along the x-axis. \n'
                          '3. A single 2D dataset and a single 1D dataset. Pre-combine 1D and 2D datasets separately if necessary.')
                    if len(data_list) > 2:
                        self.log_error(f'Could not combine data. When combining 2D and 1D data, use only one dataset of each type.\n{finalerrormessage}',
                                       show_popup=True)
                        raise ValueError('Could not combine data. When combining 2D and 1D data, '
                                         f'use only one dataset of each type.\n{finalerrormessage}')
                    try:
                        if data_list[0].dim == 3:
                            dataset2d=data_list[0]
                            dataset1d=data_list[1]
                        else:
                            dataset2d=data_list[1]
                            dataset1d=data_list[0]
                        dataset1d_type=type(dataset1d)
                        dataset2d_type=type(dataset2d)
                        kwargs={}
                        if dataset1d_type in [qcodesppData,BaseClassData]:
                            kwargs['dataset1d_filepath'] = dataset1d.filepath
                        elif dataset1d_type == InternalData:
                            kwargs['dataset1d_loaded_data'] = dataset1d.loaded_data
                            kwargs['dataset1d_label'] = dataset1d.label
                            kwargs['dataset1d_all_parameter_names'] = dataset1d.all_parameter_names
                            kwargs['dataset1d_dim']= dataset1d.dim
                        if dataset2d_type in [qcodesppData,BaseClassData]:
                            kwargs['dataset2d_filepath'] = dataset2d.filepath
                        elif dataset2d_type == InternalData:
                            kwargs['dataset2d_loaded_data'] = dataset2d.loaded_data
                            kwargs['dataset2d_label'] = dataset2d.label
                            kwargs['dataset2d_all_parameter_names'] = dataset2d.all_parameter_names
                            kwargs['dataset2d_dim']= dataset2d.dim
                        combined_item=DataItem(MixedInternalData(self.canvas,label_name,dataset2d_type,dataset1d_type,**kwargs))
                        combined_item.filepath = 'mixed_internal_data'
                        self.add_internal_data(combined_item)

                    except Exception as e:
                        self.log_error(f'Could not combine data:\n{type(e).__name__}: {e}\n{finalerrormessage}', show_popup=True)

            except Exception as e:
                self.log_error(f'Could not combine data:\n{type(e).__name__}: {e}', show_popup=True)

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
                if setting_name in ['xlabel','ylabel','clabel']:
                    action = QtWidgets.QAction(current_item.data.settings[f'default_{setting_name}'], self)
                    menu.addAction(action)
                for entry in settings[setting_name]:
                    action = QtWidgets.QAction(entry, self)
                    menu.addAction(action)
                menu.triggered[QtWidgets.QAction].connect(self.replace_plot_setting)
                menu.popup(QtGui.QCursor.pos())

    def replace_plot_setting(self, signal):
        item = self.settings_table.currentItem()
        item.setText(signal.text())

    def which_filters(self,item,filters=None,filt=None):
        # This function works out which filters should be addressed based on the datatype (e.g. belonging to 1D line or 2D dataset)
        # and either returns them, sets them, or appends to them.
        if filters is None and filt is None:
            # Return the filters to operate on
            if isinstance(item.data,MixedInternalData) and self.mixeddata_filter_box.currentIndex() == 0:
                filters = item.data.dataset2d.filters
            elif hasattr(item.data, 'sidebar1D') and item.data.sidebar1D.trace_table.rowCount() > 0:
                current_1D_row = item.data.sidebar1D.trace_table.currentRow()
                current_line = int(item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                if isinstance(item.data,MixedInternalData):
                    filters= item.data.dataset1d.plotted_lines[current_line]['filters']
                else:
                    filters= item.data.plotted_lines[current_line]['filters']
            else:
                filters = item.data.filters
            return filters
        
        elif filt is None: # The filters are being set.
            if isinstance(item.data,MixedInternalData) and self.mixeddata_filter_box.currentIndex() == 0:
                item.data.dataset2d.filters=filters
            elif hasattr(item.data, 'sidebar1D') and item.data.sidebar1D.trace_table.rowCount() > 0:
                current_1D_row = item.data.sidebar1D.trace_table.currentRow()
                current_line = int(item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                if isinstance(item.data,MixedInternalData):
                    item.data.dataset1d.plotted_lines[current_line]['filters']=filters
                else:
                    item.data.plotted_lines[current_line]['filters']=filters
            else:
                item.data.filters = filters

        else: # A filter is being appended to the table
            if isinstance(item.data,MixedInternalData) and self.mixeddata_filter_box.currentIndex() == 0:
                item.data.dataset2d.filters.append(filt)
            elif hasattr(item.data, 'sidebar1D') and item.data.sidebar1D.trace_table.rowCount() > 0:
                current_1D_row = item.data.sidebar1D.trace_table.currentRow()
                current_line = int(item.data.sidebar1D.trace_table.item(current_1D_row,0).text())
                if hasattr(filt, 'method_list') and 'Z' in filt.method_list:
                    filt.method_list=copy.copy(filt.method_list)
                    filt.method_list.remove('Z')
                    if hasattr(filt, 'method') and filt.method == 'Z':
                        filt.method=filt.method_list[0]
                elif filt.name == 'Sort':
                    filt.method_list = ['']
                    filt.method= ''
                if isinstance(item.data,MixedInternalData):
                    item.data.dataset1d.plotted_lines[current_line]['filters'].append(filt)
                else:
                    item.data.plotted_lines[current_line]['filters'].append(filt)
            else:
                item.data.filters.append(filt)

    def filters_table_edited(self, item):
        current_item = self.file_list.currentItem()
        self.old_filters=copy.deepcopy(self.which_filters(current_item))
        if current_item:
            filters=self.which_filters(current_item)
            try:
                row = item.row()
                filt = filters[row]
                filter_item = self.filters_table.item(row, 0)
                filt.method = self.filters_table.cellWidget(row, 1).currentText()
                filt.settings = [self.filters_table.item(row, 2).text(),
                                 self.filters_table.item(row, 3).text()]
                filt.checkstate = filter_item.checkState()
                self.filters_table.clearFocus()
                current_item.data.apply_all_filters(filter_box_index=self.mixeddata_filter_box.currentIndex())
                if current_item.checkState():
                    self.update_plots(update_color_limits=True)
                    self.show_current_filters()
                    self.show_current_view_settings()
                    self.reset_axlim_settings()
            except Exception as e:
                self.log_error(f'Invalid value of filter:\n{type(e).__name__}: {e}', show_popup=True)
                self.paste_filters(which='old')

    def open_filter_settings_menu(self):
        row = self.filters_table.currentRow()
        column = self.filters_table.currentColumn()
        filter_name = self.filters_table.item(row, 0).text()
        if column == 0:
            menu = QtWidgets.QMenu(self)
            menu.addAction(QtWidgets.QAction('Check all', self))
            menu.addAction(QtWidgets.QAction('Uncheck all', self))
            menu.triggered[QtWidgets.QAction].connect(self.check_all_filters)
            menu.popup(QtGui.QCursor.pos())
        if filter_name in ['Multiply','Divide','Add/Subtract'] and column == 2:
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
        elif filter_name == 'Logarithm' and column ==2:
            menu = QtWidgets.QMenu(self)
            settings=['10','2','e']
            for entry in settings:
                action = QtWidgets.QAction(entry, self)
                menu.addAction(action)
            menu.triggered[QtWidgets.QAction].connect(self.replace_filter_setting)
            menu.popup(QtGui.QCursor.pos())

    def replace_filter_setting(self,signal):
        item = self.filters_table.currentItem()
        item.setText(signal.text())

    def check_all_filters(self, signal, manual_signal=None):
        if manual_signal:
            text=manual_signal
        else:
            text = signal.text()
        current_item = self.file_list.currentItem()
        self.filters_table.itemChanged.disconnect(self.filters_table_edited)
        checkstates = {'Check all': QtCore.Qt.Checked,
                       'Uncheck all': QtCore.Qt.Unchecked}
        filters = self.which_filters(current_item)
        for row in range(self.filters_table.rowCount()):
            self.filters_table.item(row, 0).setCheckState(checkstates[text])
            filters[row].checkstate = checkstates[text]
        self.filters_table.itemChanged.connect(self.filters_table_edited)
        if current_item.checkState():
            self.update_plots(update_color_limits=True)
            self.show_current_filters()
            self.show_current_view_settings()
            self.reset_axlim_settings()

    def filters_box_changed(self):
        current_item = self.file_list.currentItem()
        if current_item:
            filt = Filter(self.filters_combobox.currentText())
            try:
                self.which_filters(current_item,filt=filt)
            except Exception as e:
                self.log_error(f'Error adding filter:\n{type(e).__name__}: {e}', show_popup=True)
            if current_item.checkState() and filt.checkstate:
                self.update_plots(update_color_limits=True)
            else:
                self.append_filter_to_table()
        self.filters_combobox.currentIndexChanged.disconnect(self.filters_box_changed)
        self.filters_combobox.setCurrentIndex(0)
        self.filters_combobox.clearFocus()
        self.filters_combobox.currentIndexChanged.connect(self.filters_box_changed)

    def mixeddata_filterbox_changed(self):
        dim=3 if self.mixeddata_filter_box.currentIndex() == 0 else 2
        self.reset_filters_combobox(dim=dim)
        self.show_current_filters()

    def reset_filters_combobox(self, dim=None):
        self.filters_combobox.currentIndexChanged.disconnect(self.filters_box_changed)
        self.filters_combobox.clear()
        self.filters_combobox.addItem('<Add Filter>')
        try:
            if dim == 2:
                exclude=['Offset line by line', 'Subtract average line by line','Cut X','Cut Y','Roll X','Roll Y','Crop Y','Subtract trace']
                filterlist=[key for key in Filter.DEFAULT_SETTINGS.keys() if key not in exclude]
            else:
                filterlist = list(Filter.DEFAULT_SETTINGS.keys())
        except Exception as e:
            self.log_error(f'Error initializing filters:\n{type(e).__name__}: {e}')
            filterlist = list(Filter.DEFAULT_SETTINGS.keys())
        self.filters_combobox.addItems(filterlist)
        self.filters_combobox.clearFocus()
        self.filters_combobox.currentIndexChanged.connect(self.filters_box_changed)
    
    def append_filter_to_table(self):
        current_item = self.file_list.currentItem()
        if current_item:
            row = self.filters_table.rowCount()

            filt = self.which_filters(current_item)[row]
            try:
                self.filters_table.itemChanged.disconnect(self.filters_table_edited)
            except Exception as e:
                self.log_error(f'Error disconnecting itemChanged signal:\n{type(e).__name__}: {e}')
            self.filters_table.insertRow(row) 
            filter_item = QtWidgets.QTableWidgetItem(filt.name)
            filter_item.setFlags(QtCore.Qt.ItemIsSelectable | 
                                 QtCore.Qt.ItemIsEnabled | 
                                 QtCore.Qt.ItemIsUserCheckable)
            filter_item.setText(filt.name)
            filter_item.setCheckState(filt.checkstate)
            filter_item.setToolTip(filt.description)
            method_box = NoScrollQComboBox()
            method_box.addItems(filt.method_list)
            method_box.setCurrentIndex(filt.method_list.index(filt.method))
            setting_1 = QtWidgets.QTableWidgetItem(filt.settings[0])
            setting_2 = QtWidgets.QTableWidgetItem(filt.settings[1])
            if hasattr(filt, 'tooltips'):
                setting_1.setToolTip(filt.tooltips[0])
                if len(filt.tooltips) > 1:
                    setting_2.setToolTip(filt.tooltips[1])
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
            filters=self.which_filters(current_item)
            if which == 'current':
                filter_row = self.filters_table.currentRow()
                if filter_row != -1:
                    del filters[filter_row]
            elif which == 'all':
                filters.clear()
            self.show_current_filters()
            current_item.data.apply_all_filters()
            self.update_plots(update_color_limits=True)
            current_item.data.reset_view_settings()
            current_item.data.reset_axlim_settings()
            if current_item.checkState():
                current_item.data.apply_view_settings()
                current_item.data.apply_axlim_settings()
                self.show_current_view_settings()
                self.show_current_axlim_settings()
            self.canvas.draw()
     
    def move_filter(self, to):
        current_item = self.file_list.currentItem()
        if current_item:
            filters=self.which_filters(current_item)
            row = self.filters_table.currentRow()
            if ((row > 0 and to == -1) or
                (row < self.filters_table.rowCount()-1 and to == 1)):
                filters[row], filters[row+to] = filters[row+to], filters[row]
                if (self.filters_table.item(row,0).checkState() and 
                    self.filters_table.item(row+to,0).checkState()):
                    self.update_plots(update_color_limits=True)
                else:
                    self.show_current_filters()
                self.filters_table.setCurrentCell(row+to, 0)
           
    def save_filters(self):
        current_item = self.file_list.currentItem()
        if current_item:
            filters=self.which_filters(current_item)
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save Filters As...', '', '.npy')
            np.save(filename, filters)
            
    def load_filters(self):
        current_item = self.file_list.currentItem()
        if current_item:
            filters=self.which_filters(current_item)
            filename, _ = QtWidgets.QFileDialog.getOpenFileNames(
                    self, 'Open Filters File...', '', '*.npy')
            loaded_filters = list(np.load(filename[0], allow_pickle=True))
            filters += copy.deepcopy(loaded_filters)
            current_item.data.apply_all_filters()
            self.update_plots(update_color_limits=True)
            self.show_current_view_settings()

    def filttocol_clicked(self, axis):
        current_item = self.file_list.currentItem()
        if current_item:
            current_item.data.filttocol(axis=axis)

    def init_linecuts(self,data):
        data.linecuts={'horizontal':{'linecut_window':None,'lines':{},'linestyle':'-','linesize':1.5,
                                    'legend':False,'xscale':'linear','yscale':'linear'},
                        'vertical':{'linecut_window':None,'lines':{},'linestyle':'-','linesize':1.5,
                                    'legend':False,'xscale':'linear','yscale':'linear'},
                        'diagonal':{'linecut_window':None,'lines':{},'linestyle':'-','linesize':1.5,
                                    'legend':False,'xscale':'linear','yscale':'linear'},
                        'circular':{'linecut_window':None,'lines':{},'linestyle':'-','linesize':1.5,
                                    'legend':False,'xscale':'linear','yscale':'linear'},
                        }

    def make_linecut_window(self,orientation, data=None, show=True):
        if not data:
            item=self.file_list.currentItem()
            if item:
                data = item.data
        if data:
            if isinstance(data, MixedInternalData):
                data = data.dataset2d
            # Make dictionary if it doesn't exist
            if not hasattr(data,'linecuts'):
                self.init_linecuts(data)

            if data.linecuts[orientation]['linecut_window']==None:
                if self.colormap_box.currentText() == 'viridis':
                    selected_colormap = cm.get_cmap('plasma')
                else:
                    selected_colormap = cm.get_cmap('viridis')
                data.linecuts[orientation]['linecut_window'] = LineCutWindow(data,orientation=orientation,
                                                                                init_cmap=selected_colormap.name,
                                                                                editor_window=self)

        if show:
            self.show_linecut_window(orientation,data)

    def show_linecut_window(self, orientation,data):
        data.linecuts[orientation]['linecut_window'].running = True
        data.linecuts[orientation]['linecut_window'].activateWindow()
        if len(data.linecuts[orientation]['lines']) > 0:
            data.linecuts[orientation]['linecut_window'].update()
        data.linecuts[orientation]['linecut_window'].show()

    def copy_linecuts(self, orientation, item=None, lines=None):
        if not item:
            item = self.file_list.currentItem()
        if item:
            data = item.data
            if isinstance(data, MixedInternalData):
                data = data.dataset2d
            if hasattr(data,'linecuts'):
                try:
                    if orientation == 'all':
                        self.copied_linecuts = [orientation,self.remove_linecutwindows_and_fits(data.linecuts)]
                    elif lines is None:
                        self.copied_linecuts = [orientation,self.remove_linecutwindows_and_fits(data.linecuts[orientation])]
                    else:
                        linecut_dict={'lines':{}}
                        for line in lines:
                            linecut_dict['lines'][line] = self.remove_linecutwindows_and_fits(data.linecuts[orientation]['lines'][line])
                        self.copied_linecuts = [orientation,linecut_dict]
                except Exception as e:
                    self.log_error(f'Error copying linecuts:\n{type(e).__name__}: {e}', show_popup=True)
            else:
                self.log_error('No linecuts to copy in currently selected file', show_popup=True)

    def paste_single_linecut_orientation(self,orientation,data, lines):
        if data.linecuts[orientation]['linecut_window'] is None:
            self.make_linecut_window(orientation, data, show=False)
        if len(data.linecuts[orientation]['lines']) > 0:
            startindex=np.max(list(data.linecuts[orientation]['lines'].keys()))+1
        else:
            startindex=0

        out_of_range=[]

        for i,value in enumerate(lines.values()):
            line = int(i+startindex)
            shape=data.processed_data[-1].shape
            if orientation == 'horizontal' and value['data_index'] >= shape[1]:
                out_of_range.append(int(value['data_index']))
            elif orientation == 'vertical' and value['data_index'] >= shape[0]:
                out_of_range.append(int(value['data_index']))
            else:
                data.linecuts[orientation]['lines'][line] = copy.deepcopy(value)
                if 'draggable_points' in data.linecuts[orientation]['lines'][line].keys():
                    points=data.linecuts[orientation]['lines'][line]['points']
                    data.linecuts[orientation]['lines'][line]['draggable_points'] = [DraggablePoint(data,points[0][0],points[0][1],line,orientation),
                    DraggablePoint(data,points[1][0],points[1][1],line,orientation,draw_line=True)]
                elif 'fit' in data.linecuts[orientation]['lines'][line].keys():
                    data.linecuts[orientation]['lines'][line]['fit']['fit_result'] = load_lmfit_modelresult_s(data.linecuts[orientation]['lines'][line]['fit']['fit_result'])
                data.linecuts[orientation]['linecut_window'].append_cut_to_table(line)
        return out_of_range
    
    def paste_linecuts(self,item=None):
        if not item:
            item = self.file_list.currentItem()
        if item:
            if hasattr(item,'data') and (item.data.dim == 3 or isinstance(item.data, MixedInternalData)):
                data = item.data
                minilog=[]
                try:
                    if isinstance(data, MixedInternalData):
                        data = data.dataset2d
                    if not hasattr(data,'linecuts'):
                        self.init_linecuts(data)
                    if hasattr(self,'copied_linecuts') and self.copied_linecuts[0]=='all':
                        linecuts = copy.copy(self.copied_linecuts[1])
                        for orientation in linecuts.keys():
                            if len(list(linecuts[orientation]['lines'])) > 0:
                                out_of_range=self.paste_single_linecut_orientation(orientation,data, linecuts[orientation]['lines'])
                                self.show_linecut_window(orientation,data)
                                if len(out_of_range) > 0:
                                    for index in out_of_range:
                                        text=(f'Index {index} is out of range in the {orientation} direction for data '
                                         f'with shape {data.processed_data[-1].shape}.')
                                        minilog.append(text)
                                        self.log_error(text)
                    elif hasattr(self,'copied_linecuts'):
                        orientation= self.copied_linecuts[0]
                        lines= copy.copy(self.copied_linecuts[1]['lines'])
                        out_of_range=self.paste_single_linecut_orientation(orientation,data, lines)
                        self.show_linecut_window(orientation,data)
                        if len(out_of_range) > 0:
                            for index in out_of_range:
                                text=(f'Index {index} is out of range in the {orientation} direction for data '
                                    f'with shape {data.processed_data[-1].shape}.')
                                minilog.append(text)
                                self.log_error(text)
                    else:
                        self.log_error('No linecuts to paste', show_popup=True)
                except Exception as e:
                    message = f'Error pasting linecuts:\n{type(e).__name__}: {e}'
                    minilog.append(message)
                    self.log_error(message)

                self.update_plots()

                if len(minilog)>0:
                    error_message = 'The following errors occurred while pasting linecuts:\n\n' + '\n\n'.join(minilog)
                    self.ew = ErrorWindow(error_message)
            else:
                self.log_error('Cannot paste linecuts to this data type', show_popup=True)

    def show_hide_linecuts_changed(self):
        self.show_linecut_markers = not self.show_linecut_markers
        self.update_plots()

    def reinstate_markers(self, item, orientation):
        if orientation == 'horizontal':
            if hasattr(item.data,'horimarkers') and len(item.data.horimarkers)>0:
                for marker in item.data.horimarkers:
                    try:
                        marker.remove()
                        del marker
                    except NotImplementedError:
                        pass
            item.data.horimarkers=[]
            for line in item.data.linecuts['horizontal']['lines']:
                if item.data.linecuts[orientation]['lines'][line]['checkstate']:
                    z=item.data.linecuts[orientation]['lines'][line]['cut_axis_value']
                    item.data.horimarkers.append(item.data.axes.axhline(y=z, linestyle='dashed', linewidth=1, xmax=0.05,
                        color=item.data.linecuts[orientation]['lines'][line]['linecolor']))
                    item.data.horimarkers.append(item.data.axes.axhline(y=z, linestyle='dashed', linewidth=1, xmin=0.95,
                        color=item.data.linecuts[orientation]['lines'][line]['linecolor']))  

        elif orientation == 'vertical':
            if hasattr(item.data,'vertmarkers') and len(item.data.vertmarkers)>0:
                for marker in item.data.vertmarkers:
                    try:
                        marker.remove()
                        del marker
                    except NotImplementedError:
                        pass
            item.data.vertmarkers=[]
            for line in item.data.linecuts['vertical']['lines']:
                if item.data.linecuts[orientation]['lines'][line]['checkstate']:
                    z=item.data.linecuts[orientation]['lines'][line]['cut_axis_value']
                    item.data.vertmarkers.append(item.data.axes.axvline(x=z, linestyle='dashed', linewidth=1, ymax=0.05,
                        color=item.data.linecuts[orientation]['lines'][line]['linecolor']))
                    item.data.vertmarkers.append(item.data.axes.axvline(x=z, linestyle='dashed', linewidth=1, ymin=0.95,
                        color=item.data.linecuts[orientation]['lines'][line]['linecolor']))
                
        elif orientation == 'diagonal':
            for line in item.data.linecuts[orientation]['lines']:
                if item.data.linecuts[orientation]['lines'][line]['checkstate']:
                    points0= item.data.linecuts[orientation]['lines'][line]['points'][0]
                    points1= item.data.linecuts[orientation]['lines'][line]['points'][1]
                    item.data.linecuts[orientation]['lines'][line]['draggable_points']=[DraggablePoint(item.data, points0[0], points0[1],
                                                                                                line,orientation),
                                                DraggablePoint(item.data, points1[0], points1[1],line,orientation,draw_line=True)]

    def draggable_point_selected(self, x,y,data):
        selected=False
        if isinstance(data, MixedInternalData):
            data = data.dataset2d
        if hasattr(data,'linecuts'):
            # Define window the same size as the draggable points
            delta_x = np.abs(data.axes.get_xlim()[1]-data.axes.get_xlim()[0])*0.02
            delta_y = np.abs(data.axes.get_ylim()[1]-data.axes.get_ylim()[0])*0.02
            for orientation in ['diagonal','circular']:
                for line in data.linecuts[orientation]['lines'].keys():
                    for point in data.linecuts[orientation]['lines'][line]['points']:
                        if (np.abs(point[0]-x)<delta_x and np.abs(point[1]-y)<delta_y):
                            selected=True
        return selected
    
    def mouse_click_canvas(self, event):
        if self.navi_toolbar.mode == '': # If not using the navigation toolbar tools
            if event.inaxes:
                x, y = event.xdata, event.ydata
                checked_items = self.get_checked_items()
                self.plot_in_focus = [checked_item for checked_item in checked_items 
                                      if checked_item.data.axes == event.inaxes]
                if self.plot_in_focus:
                    if self.file_list.currentItem() != self.plot_in_focus[0]:
                        # If the clicked plot is not the current one, set it as current before doing anything else.
                        self.file_list.setCurrentItem(self.plot_in_focus[0])
                        self.file_clicked()
                    else:
                        self.file_list.setCurrentItem(self.plot_in_focus[0])
                        self.file_clicked()
                        data = self.plot_in_focus[0].data
                        data.selected_x, data.selected_y = x, y

                        # For 1D data left mouse click sets the fit limits.
                        if (event.button == 1  and 
                            data.dim == 2):
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

                        # For 2D data, left and middle mouse click generate horizontal or vertical linecut, UNLESS the
                        # mouse is in the vicinity of a pre-existing diagonal or circular linecut point.

                        elif ((event.button == 1 or event.button == 2) and 
                            (data.dim == 3 or isinstance(data,MixedInternalData)) and not self.draggable_point_selected(x,y,data)):
                            # Opening linecut/fitting window for 2D data
                            if isinstance(data, MixedInternalData):
                                data = data.dataset2d
                            index_x = np.argmin(np.abs(data.processed_data[0][:,0]-x))
                            index_y = np.argmin(np.abs(data.processed_data[1][0,:]-y))
                            data.selected_indices = [int(index_x), int(index_y)]
                            if self.colormap_box.currentText() == 'viridis':
                                selected_colormap = cm.get_cmap('plasma')
                            else:
                                selected_colormap = cm.get_cmap('viridis')
                            #Make entry to store linecuts in
                            if not hasattr(data,'linecuts'):
                                self.init_linecuts(data)
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
                                data.linecuts[orientation]['linecut_window'] = LineCutWindow(data,orientation=orientation,init_cmap=selected_colormap.name,editor_window=self)
                            data.linecuts[orientation]['linecut_window'].running = True
                            data.linecuts[orientation]['linecut_window'].append_cut_to_table(int(max_index+1))
                            data.linecuts[orientation]['linecut_window'].update()
                            data.linecuts[orientation]['linecut_window'].activateWindow()
                            self.canvas.draw()
                            
                        elif event.button == 3:
                            # Open right-click menu
                            rightclick_menu = QtWidgets.QMenu(self)

                            if isinstance(data, MixedInternalData):
                                index_x = np.argmin(np.abs(data.dataset2d.processed_data[0][:,0]-x))
                                index_y = np.argmin(np.abs(data.dataset2d.processed_data[1][0,:]-y))
                                z = data.dataset2d.processed_data[2][index_x,index_y]
                                coordinates = (f'x = {x:.4g}, y = {y:.4g}, z = {z:.4g}'
                                            f' ({index_x}, {index_y})')
                            elif data.dim == 2:
                                index_x = np.argmin(np.abs(data.processed_data[0]-x))
                                index_y = np.argmin(np.abs(data.processed_data[1]-y))
                                coordinates = (f'x = {x:.4g}, y = {y:.4g}'
                                            f' ({index_x}, {index_y})')
                            elif data.dim == 3:
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
                            if data.dim == 3:
                                actions.append(QtWidgets.QAction(f'Offset Z by {z:6g}', self))
                            actions.append(QtWidgets.QAction('Crop data to zoom', self))
                            for action in actions:
                                rightclick_menu.addAction(action)
                            # Add actions from extension modules
                            rightclick_menu.addSeparator()
                            data.add_extension_actions(self, rightclick_menu)
                            rightclick_menu.addSeparator()
                            actions=[]
                            if data.dim == 3 or isinstance(data, MixedInternalData):
                                actions.append(QtWidgets.QAction('Draw diagonal linecut', self))
                                #actions.append(QtWidgets.QAction('Draw circular linecut', self))
                                actions.append(QtWidgets.QAction('Plot vertical linecuts (middle click on plot)', self))
                                actions.append(QtWidgets.QAction('Plot horizontal linecuts (left click on plot)', self))
                            for action in actions:
                                rightclick_menu.addAction(action)
                            rightclick_menu.triggered[QtWidgets.QAction].connect(self.popup_canvas)
                            rightclick_menu.popup(QtGui.QCursor.pos())
                    
                # else: # if colorbar in focus
                #     self.cbar_in_focus = [checked_item for checked_item in checked_items
                #                           if (hasattr(checked_item.data,'cbar') and checked_item.data.cbar.ax == event.inaxes)]
                #     if self.cbar_in_focus:
                #         if self.file_list.currentItem() != self.cbar_in_focus[0]:
                #             # If the clicked plot is not the current one, set it as current before doing anything else.
                #             self.file_list.setCurrentItem(self.cbar_in_focus[0])
                #             self.file_clicked()

                #         else:
                #             self.press = event.ydata

    def on_motion(self, event):
        if hasattr(self,'press') and self.press != None:
            # if hasattr(self,'cbar_in_focus') and self.cbar_in_focus:
            #     try:
            #         ypress = self.press
            #         dy = event.ydata - ypress
            #         self.press=event.ydata
            #         map_min=self.cbar_in_focus[0].data.view_settings['Minimum']
            #         map_max=self.cbar_in_focus[0].data.view_settings['Maximum']
            #         self.cbar_in_focus[0].data.view_settings['Minimum']= map_min+dy
            #         self.cbar_in_focus[0].data.view_settings['Maximum']= map_max+dy
            #         self.cbar_in_focus[0].data.reset_midpoint()
            #         self.cbar_in_focus[0].data.apply_view_settings()
            #         self.canvas.draw()
            #     except: # sometimes can happen if the focus between plots changes weirdly. Not worth getting worried about, so no use filling up errors
            #         pass
            
            if self.press[0] in ['haxfill_top','haxfill_bottom','haxfill']:
                which=self.press[0]
                data=self.press[2]
                pixels_to_hax = data.hax.transData.inverted().transform
                ypress= self.press[1]
                dx,dy = pixels_to_hax((0,event.y)) - ypress
                self.press=[which,pixels_to_hax((0,event.y)),data]
                map_max=data.view_settings['Maximum']
                map_min=data.view_settings['Minimum']
                if which == 'haxfill_top':
                    data.view_settings['Maximum']= map_max+dy
                elif which == 'haxfill_bottom':
                    data.view_settings['Minimum']= map_min+dy
                elif which == 'haxfill':
                    data.view_settings['Minimum']= map_min+dy
                    data.view_settings['Maximum']= map_max+dy
                if hasattr(self,'hax_marker'):
                    if which=='haxfill_top':
                        self.hax_marker.set_ydata([data.view_settings['Maximum'],data.view_settings['Maximum']])
                    elif which=='haxfill_bottom':
                        self.hax_marker.set_ydata([data.view_settings['Minimum'],data.view_settings['Minimum']])

                data.reset_midpoint()
                data.apply_view_settings()
                self.show_current_view_settings()
                self.canvas.draw()
            
            elif self.press[0] == 'outside':
                data=self.press[2]
                pixels_to_hax = data.hax.transData.inverted().transform
                ypress= self.press[1]
                dx,dy = pixels_to_hax((0,event.y)) - ypress
                self.press=['outside',pixels_to_hax((0,event.y)),data]
                axmin=data.hax.get_ylim()[0]
                axmax=data.hax.get_ylim()[1]
                data.hax.set_ylim(axmin-dy,axmax-dy)
                self.canvas.draw()

        else:
            # Mouse is moving around without a press event (i.e. not clicked). Turn it into a move cursor if over a haxfill.
            histograms = [checked_item for checked_item in self.get_checked_items() if
                        hasattr(checked_item.data, 'hax')]
            box_mins = [checked_item.data.haxfill.get_window_extent().get_points()[0][1] for checked_item in histograms]
            box_maxs = [checked_item.data.haxfill.get_window_extent().get_points()[1][1] for checked_item in histograms]
            box_xmins = [checked_item.data.haxfill.get_window_extent().get_points()[0][0] for checked_item in histograms]
            box_xmaxs = [checked_item.data.haxfill.get_window_extent().get_points()[1][0] for checked_item in histograms]
            min_windows = [[box_min-(box_max-box_min)/50,box_min+(box_max-box_min)/50] for box_min, box_max in zip(box_mins, box_maxs)]
            max_windows = [[box_max-(box_max-box_min)/50,box_max+(box_max-box_min)/50] for box_min, box_max in zip(box_mins, box_maxs)]

            for i in range(len(min_windows)):
                if box_xmins[i] < event.x < box_xmaxs[i]:
                    if min_windows[i][0] < event.y < min_windows[i][1]:
                        self.canvas.setCursor(QtCore.Qt.SizeVerCursor)
                        break
                    elif max_windows[i][0] < event.y < max_windows[i][1]:
                        self.canvas.setCursor(QtCore.Qt.SizeVerCursor)
                        break
                    else:
                        self.canvas.setCursor(QtCore.Qt.ArrowCursor)
                else:
                    self.canvas.setCursor(QtCore.Qt.ArrowCursor)

    def on_release(self, event):
        self.press = None
        if hasattr(self,'hax_marker'):
            self.hax_marker.remove()
            del self.hax_marker
        self.canvas.draw()

    def on_pick(self,event):
        # Use this exclusively for the cbar's histogram, since it's not possible to access it in any other way.
        hist_in_focus = [checked_item for checked_item in self.get_checked_items() if
                        hasattr(checked_item.data, 'hax') and
                        checked_item.data.hax == event.artist]
        if hist_in_focus:
            data=hist_in_focus[0].data
            box=data.haxfill
            box_min=box.get_window_extent().get_points()[0][1]
            box_max=box.get_window_extent().get_points()[1][1]
            min_window=[box_min-(box_max-box_min)/50,box_min+(box_max-box_min)/50]
            max_window=[box_max-(box_max-box_min)/50,box_max+(box_max-box_min)/50]
            x, y = event.mouseevent.x, event.mouseevent.y
            pixels_to_hax = data.hax.transData.inverted().transform
            if self.file_list.currentItem() != hist_in_focus[0]:
                # If the clicked plot is not the current one, set it as current before doing anything else.
                self.file_list.setCurrentItem(hist_in_focus[0])
                self.file_clicked()
            
            if event.mouseevent.step != 0: #The user is scrolling.
                ydata= pixels_to_hax((x, y))[1]
                scale_factor = np.power(1.1, -event.mouseevent.step)
                y_top = ydata - data.hax.get_ylim()[0]
                y_bottom = data.hax.get_ylim()[1] - ydata
                newylims=[ydata - y_top * scale_factor, ydata + y_bottom * scale_factor]

                data.hax.set_ylim(newylims[0], newylims[1])
                data.hax.figure.canvas.draw()
            
            elif event.mouseevent.button == 1 and max_window[0]<y<max_window[1]: # Adjust upper limit of the haxfill box.
                self.hax_marker=data.hax.axhline(y=pixels_to_hax((0,box_max))[1], color='red', lw=1)
                self.press = ['haxfill_top', pixels_to_hax((x, y))[1], data]
            elif event.mouseevent.button == 1 and min_window[0]<y<min_window[1]:
                self.hax_marker=data.hax.axhline(y=pixels_to_hax((0,box_min))[1], color='red', lw=1)
                self.press = ['haxfill_bottom', pixels_to_hax((x, y))[1], data]
            elif event.mouseevent.button == 1 and min_window[1]<y<max_window[0]:
                self.press = ['haxfill', pixels_to_hax((x, y))[1], data]
            else:
                self.press = ['outside', pixels_to_hax((x, y))[1], data]
    
    def popup_canvas(self, signal):
        # Actions for right-click menu on the plot(s)
        current_item = self.plot_in_focus[0]
        data = self.plot_in_focus[0].data

        # Easy offset
        if 'Offset' in signal.text():
            axis=signal.text().split()[1]
            value=-float(signal.text().split()[3])
            if current_item:
                filt = Filter('Add/Subtract',method=axis, settings=[str(value),''], checkstate=2)
                self.which_filters(current_item,filt=filt)
            if current_item.checkState() and filt.checkstate:
                self.update_plots(update_color_limits=True)
                self.reset_axlim_settings()
                self.show_current_all()
        
        # Making linecuts
        elif 'linecut' in signal.text():
            orientation=signal.text().split()[1]
            
            self.make_linecut_window(orientation,data, show=False)

            # For diagonal/circular linecuts, need to make a new line each time. For hori/vert just open the window.
            if orientation == 'diagonal':
                x,y=data.selected_x, data.selected_y
                index_x = np.argmin(np.abs(data.processed_data[0][:,0]-x))
                index_y = np.argmin(np.abs(data.processed_data[1][0,:]-y))
                left,right= data.axes.get_xlim()
                bottom,top= data.axes.get_ylim()
                x_mid, y_mid = 0.5*(left+right), 0.5*(top+bottom)
                index_x_mid= np.argmin(np.abs(data.processed_data[0][:,0]-x_mid))
                index_y_mid= np.argmin(np.abs(data.processed_data[1][0,:]-y_mid))
                if self.colormap_box.currentText() == 'viridis':
                    selected_colormap = cm.get_cmap('plasma')
                else:
                    selected_colormap = cm.get_cmap('viridis')
                line_colors = selected_colormap(np.linspace(0.1,0.9,len(data.processed_data[1][0,:])))
                try:
                    max_index=np.max(list(data.linecuts[orientation]['lines'].keys()))
                except ValueError:
                    max_index=-1
                data.linecuts[orientation]['lines'][int(max_index+1)]={'points':[(x, y),(x_mid, y_mid)],
                                                            'indices':[(index_x, index_y),(index_x_mid, index_y_mid)],
                                                            'checkstate':2,
                                                            'offset':0,
                                                            'linecolor':line_colors[int(max_index+1)]}
                data.linecuts[orientation]['lines'][int(max_index+1)]['draggable_points']=[DraggablePoint(data, x, y,int(max_index+1),orientation),
                                            DraggablePoint(data, x_mid, y_mid,int(max_index+1),orientation,draw_line=True)]
                data.linecuts[orientation]['linecut_window'].append_cut_to_table(int(max_index+1))

            self.show_linecut_window(orientation,data)

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
                data.linecut_window = LineCutWindow(data,orientation='circular',editor_window=self)
            else:
                data.linecut_window.orientation='circular'
            data.linecut_window.running = True
            data.linecut_window.update()
            self.canvas.draw()
            data.linecut_window.activateWindow()

        elif signal.text() == 'Crop data to zoom':
            left, right = data.axes.get_xlim()
            if data.dim ==3:
                bottom, top = data.axes.get_ylim()
                x_min, x_max = np.argmin(np.abs(data.processed_data[0][:,0]-left)), np.argmin(np.abs(data.processed_data[0][:,0]-right))
                y_min, y_max = np.argmin(np.abs(data.processed_data[1][0,:]-bottom)), np.argmin(np.abs(data.processed_data[1][0,:]-top))

                filt = Filter('Crop X',method='Abs', settings=[str(data.processed_data[0][x_min,0]),
                                                                str(data.processed_data[0][x_max,0])], checkstate=2)
                self.which_filters(current_item,filt=filt)
                filt = Filter('Crop Y',method='Abs', settings=[str(data.processed_data[1][0,y_min]),
                                                            str(data.processed_data[1][0,y_max])], checkstate=2)
                self.which_filters(current_item,filt=filt)
            elif data.dim == 2:
                current_1D_row = data.sidebar1D.trace_table.currentRow()
                current_line = int(data.sidebar1D.trace_table.item(current_1D_row,0).text())
                try:
                    x_min,x_max=np.argmin(np.abs(data.plotted_lines[current_line]['processed_data'][0]-left)),np.argmin(np.abs(data.plotted_lines[current_line]['processed_data'][0]-right))
                    filt = Filter('Crop X',method='Abs', settings=[str(data.plotted_lines[current_line]['processed_data'][0][x_min]),
                                                                    str(data.plotted_lines[current_line]['processed_data'][0][x_max])], checkstate=2)
                    self.which_filters(current_item,filt=filt)
                except Exception as e:
                    self.log_error(f'Error cropping X:\n{type(e).__name__}: {e}', show_popup=True)
            if current_item.checkState() and filt.checkstate:
                self.update_plots(update_color_limits=True)
                self.reset_axlim_settings()
                self.show_current_all()
    
    def enter_move_tester(self,urls):
        for url in urls:
            if not (url.toLocalFile().endswith('.dat') or url.toLocalFile().endswith('.npy')
                    or url.toLocalFile().endswith('.txt') or url.toLocalFile().endswith('.igs')
                    or os.path.isdir(url.toLocalFile())):
                return False
            else:
                continue
        return True

    def drop_files_tester(self, urls):
        for url in urls:
            if not (url.toLocalFile().endswith('.dat') or url.toLocalFile().endswith('.npy') \
                    or url.toLocalFile().endswith('.txt')):
                return False
            else:
                continue
        return True
    
    def drop_folders_tester(self, urls):
        for url in urls:
            if not os.path.isdir(url.toLocalFile()):
                return False
            else:
                continue
        return True

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and self.enter_move_tester(urls):
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and self.enter_move_tester(urls):
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            # Accept single data files
            if urls and self.drop_files_tester(urls):
                file_paths = [url.toLocalFile() for url in urls]
                self.open_files(filepaths=file_paths)
                event.accept()
            # Accept session files
            elif urls and urls[0].toLocalFile().endswith('.igs'):
                file_path = urls[0].toLocalFile()
                self.load_session(filepath=file_path)
                event.accept()
            # Accept dropped folders
            elif urls and self.drop_folders_tester(urls):
                folder_paths = [url.toLocalFile() for url in urls]
                for path in folder_paths:
                    self.open_files_from_folder(rootdir=path)
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def show_metadata(self):
        item = self.file_list.currentItem()
        if item:
            if hasattr(item.data,'meta'):
                if not hasattr(item.data,'metapopup'):
                    item.data.metapopup=MetadataWindow(item.data)
                item.data.metapopup.show()

    def show_stats(self):
        item = self.file_list.currentItem()
        if item:
            if not hasattr(item.data,'statspopup'):
                item.data.statspopup=StatsWindow(item.data)
            item.data.statspopup.show()
            
    def mouse_scroll_canvas(self, event):
        if event.inaxes:
            checked_items = self.get_checked_items()
            self.plot_in_focus = [checked_item for checked_item in checked_items 
                                  if checked_item.data.axes == event.inaxes]
            self.cbar_in_focus = [checked_item for checked_item in checked_items
                        if hasattr(checked_item.data, 'cbar') and checked_item.data.cbar.ax == event.inaxes]
            
            # Scolling within plot bounds zooms
            if self.plot_in_focus:
                if self.file_list.currentItem() != self.plot_in_focus[0]:
                    # If the clicked plot is not the current one, set it as current before doing anything else.
                    self.file_list.setCurrentItem(self.plot_in_focus[0])
                    self.file_clicked()
                else:
                    scale=1.2
                    data = self.plot_in_focus[0].data
                    scale_factor = np.power(scale, -event.step)

                    if any(scale != 'linear' for scale in [data.axlim_settings['Xscale'],
                                                            data.axlim_settings['Yscale']]):
                        # This zoom method works well for non-linear plots, but is slightly slower since requires more calculation.
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
                            data.axlim_settings['Xmin']=new_xlim0
                            data.axlim_settings['Xmax']=new_xlim1
                        elif QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
                            data.axlim_settings['Ymin']=new_ylim0
                            data.axlim_settings['Ymax']=new_ylim1
                        else:
                            data.axlim_settings['Xmin']=new_xlim0
                            data.axlim_settings['Xmax']=new_xlim1
                            data.axlim_settings['Ymin']=new_ylim0
                            data.axlim_settings['Ymax']=new_ylim1
                    else:
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

            #Scrolling within colourbar changes limits
            # elif self.cbar_in_focus:
            #     if self.file_list.currentItem() != self.cbar_in_focus[0]:
            #         # If the clicked plot is not the current one, set it as current before doing anything else.
            #         self.file_list.setCurrentItem(self.cbar_in_focus[0])
            #         self.file_clicked()
            #     else:
            #         y = event.ydata
            #         data = self.cbar_in_focus[0].data
            #         min_map = data.view_settings['Minimum']
            #         max_map = data.view_settings['Maximum']
            #         range_map = max_map-min_map
            #         speed= np.abs(y-(min_map+0.5*range_map))*(0.25+0.01)/range_map # Scroll faster further away from the midpoint

            #         if y > min_map+0.5*range_map:
            #             new_max = max_map + event.step*range_map*speed
            #             data.view_settings['Maximum'] = new_max
            #         else:
            #             new_min = min_map + event.step*range_map*speed
            #             data.view_settings['Minimum'] = new_min
            #         data.reset_midpoint()
            #         data.apply_view_settings()
            #         self.canvas.draw()
            #         self.show_current_view_settings()

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
        # if event.key() == QtCore.Qt.Key_C and event.modifiers() == QtCore.Qt.ControlModifier:
        #     self.copy_canvas_to_clipboard()
        if event.key() == QtCore.Qt.Key_T and event.modifiers() == QtCore.Qt.ControlModifier:
            if not self.action_refresh_stop.isEnabled():
                self.start_auto_refresh(1)
                self.log_error('Started live tracking')
            else:
                self.stop_auto_refresh()
                self.log_error('Stopped live tracking')

    def save_preset(self):
        current_item = self.file_list.currentItem()
        if current_item:
            settings_to_save=['titlesize',
            'labelsize',
            'ticksize',
            'spinewidth',
            'colorbar',
            'minortick',
            'maskcolor',
            'cmap levels',
            'rasterized',
            'dpi',
            'transparent',
            'shading']
            view_settings_to_save=['Colormap Type','Colormap']

            presets={}
            for setting in settings_to_save:
                if setting in current_item.data.settings.keys():
                    presets[setting]=current_item.data.settings[setting]
            for setting in view_settings_to_save:
                if setting in current_item.data.view_settings.keys():
                    presets[setting]=current_item.data.view_settings[setting]

            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save Preset As...', '', 'IG preset (*.igp)')
            if filename:
                try:
                    with open(filename, 'w') as f:
                        jsondump(presets, f)
                except Exception as e:
                    self.log_error(f'Could not save preset:\n{type(e).__name__}: {e}', show_popup=True)

    def load_preset(self):
        checked_items = self.get_checked_items()
        if checked_items:
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Load Preset File...', '', '*.igp')
            if filename:
                try:
                    for item in checked_items:
                            with open(filename, 'r') as f:
                                presets = jsonload(f)
                            for setting in presets.keys():
                                if setting in item.data.settings.keys():
                                    item.data.settings[setting] = presets[setting]
                                elif setting in item.data.view_settings.keys():
                                    item.data.view_settings[setting] = presets[setting]
                            item.data.apply_view_settings()
                            self.update_plots()
                except Exception as e:
                    self.log_error(f'Could not load preset:\n{type(e).__name__}: {e}', show_popup=True)

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

    def save_image(self):
        current_item = self.file_list.currentItem()
        if current_item:
            data_name, _ = os.path.splitext(current_item.data.label)
            formats = 'Adobe Acrobat (*.pdf);;Portable Network Graphic (*.png)'
            filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save Figure As...', data_name.replace(':',''), formats)
            if filename:                
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
                self.log_error(f'Saved figure as {filename}')
        
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
                        item.data.add_plot(editor_window=self)
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
                        self.log_error(f'Could not plot {item.data.filepath} for saving:\n{type(e).__name__}: {e}', show_popup=True)
            if DARK_THEME and qdarkstyle_imported:
                rcParams_to_dark_theme()
                self.update_plots(update_data=False)

    def tight_layout(self):
        self.figure.tight_layout()
        self.canvas.draw()

    def log_error(self, error_message, show_popup=False):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.error_log[len(self.error_log)] = {'timestamp': timestamp,
                                               'message': error_message}
        if show_popup:
            self.ew = ErrorWindow(error_message)
    
    def open_error_log(self):
        self.elw = ErrorLogWindow(self.error_log)

    def closeEvent(self, event):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Save Session?",
            "Do you want to save your session before closing?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel
        )
        if reply == QtWidgets.QMessageBox.Yes:
            saved=self.save_session()
            if saved:
                event.accept()
            else:
                event.ignore()
        elif reply == QtWidgets.QMessageBox.No:
            event.accept()
        else:
            event.ignore()
        for window in QtWidgets.QApplication.instance().topLevelWidgets():
            window.close()