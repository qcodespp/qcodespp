from PyQt5 import QtWidgets, QtCore
import numpy as np
import os
from matplotlib.widgets import Cursor
from matplotlib import cm, rcParams
from .helpers import MidpointNormalize
from .popupwindows import FFTWindow
from .sidebars import Sidebar1D

class DataItem(QtWidgets.QListWidgetItem):
    def __init__(self, data):
        super().__init__()
        self.data = data
        
        self.setFlags(self.flags() | QtCore.Qt.ItemIsUserCheckable)
        self.setCheckState(QtCore.Qt.Unchecked)
        self.setText(self.data.label)

class BaseClassData:    
    # Set default plot settings
    DEFAULT_PLOT_SETTINGS = {}
    DEFAULT_PLOT_SETTINGS['title'] = '<label>'
    DEFAULT_PLOT_SETTINGS['xlabel'] = ''
    DEFAULT_PLOT_SETTINGS['ylabel'] = ''
    DEFAULT_PLOT_SETTINGS['clabel'] = ''
    DEFAULT_PLOT_SETTINGS['transpose'] = 'False'
    DEFAULT_PLOT_SETTINGS['titlesize'] = '14'
    DEFAULT_PLOT_SETTINGS['labelsize'] = '14' 
    DEFAULT_PLOT_SETTINGS['ticksize'] = '14'
    # DEFAULT_PLOT_SETTINGS['linewidth'] = '1.5'
    DEFAULT_PLOT_SETTINGS['spinewidth'] = '1'
    DEFAULT_PLOT_SETTINGS['columns'] = '0,1,2'
    DEFAULT_PLOT_SETTINGS['colorbar'] = 'True'
    DEFAULT_PLOT_SETTINGS['minorticks'] = 'False'
    DEFAULT_PLOT_SETTINGS['delimiter'] = ''
    DEFAULT_PLOT_SETTINGS['linecolor'] = 'black'
    DEFAULT_PLOT_SETTINGS['maskcolor'] = 'black'
    DEFAULT_PLOT_SETTINGS['lut'] = '512'
    DEFAULT_PLOT_SETTINGS['rasterized'] = 'True'
    DEFAULT_PLOT_SETTINGS['dpi'] = '300'
    DEFAULT_PLOT_SETTINGS['transparent'] = 'True'
    DEFAULT_PLOT_SETTINGS['shading'] = 'auto'
    
    # Set default view settings
    DEFAULT_VIEW_SETTINGS = {}
    DEFAULT_VIEW_SETTINGS['Minimum'] = 0
    DEFAULT_VIEW_SETTINGS['Maximum'] = 0
    DEFAULT_VIEW_SETTINGS['Midpoint'] = 0
    DEFAULT_VIEW_SETTINGS['Colormap'] = 'viridis'
    DEFAULT_VIEW_SETTINGS['Colormap Type'] = 'Uniform'
    DEFAULT_VIEW_SETTINGS['Locked'] = False
    DEFAULT_VIEW_SETTINGS['MidLock'] = False
    DEFAULT_VIEW_SETTINGS['Reverse'] = False

    # Set default axlim settings
    DEFAULT_AXLIM_SETTINGS = {}
    DEFAULT_AXLIM_SETTINGS['Xmin'] = None
    DEFAULT_AXLIM_SETTINGS['Xmax'] = None
    DEFAULT_AXLIM_SETTINGS['Ymin'] = None
    DEFAULT_AXLIM_SETTINGS['Ymax'] = None
    DEFAULT_AXLIM_SETTINGS['Xscale'] = 'linear'
    DEFAULT_AXLIM_SETTINGS['Yscale'] = 'linear'
    
    def __init__(self, filepath, canvas):
        self.filepath = filepath
        self.canvas = canvas
        self.label = os.path.basename(self.filepath)

        self.loaded_data=None
        
        self.settings = self.DEFAULT_PLOT_SETTINGS.copy()
        self.view_settings = self.DEFAULT_VIEW_SETTINGS.copy()
        self.axlim_settings = self.DEFAULT_AXLIM_SETTINGS.copy()
        self.filters = []

        try: # on Windows
            self.creation_time = os.path.getctime(filepath)
        except Exception:
            try: # on Mac
                self.creation_time = os.stat(filepath).st_birthtime
            except Exception:
                self.creation_time = None

    def prepare_dataset(self):
        try:
            self.loaded_data = np.genfromtxt(self.filepath, delimiter=self.settings['delimiter'])
        except ValueError: # Can occur if python doesn't recognise a header
            self.loaded_data = np.genfromtxt(self.filepath, delimiter=self.settings['delimiter'],skip_header=1)
        
        if self.settings['transpose'] == 'False':
            self.loaded_data = np.transpose(self.loaded_data)
        
        self.param_name_dict={}
        try: # to get column names if there is a header. Avoid using genfromtxt as it doesn't have enough options to work all the time.
            with open(self.filepath, 'r') as f:
                header = f.readline()
            if header.startswith('#'):
                header = header[1:]
                if self.settings['delimiter']:
                    self.all_parameter_names = header.split(self.settings['delimiter'])
                else:
                    self.all_parameter_names = header.split()
                for i,name in enumerate(self.all_parameter_names):
                    self.param_name_dict[name]=i
        except Exception as e:
            print(f'Could not read column names: {e}\n'
                'Using integers instead')
            pass

        if len(self.param_name_dict.keys()) == 0:
            self.all_parameter_names=[f"column_{i}" for i in range(self.loaded_data.shape[0])]
            self.param_name_dict={}
            for i,name in enumerate(self.all_parameter_names):
                self.param_name_dict[name]=i

        self.measured_data_points = self.loaded_data.shape[0]

        self.settings['X data'] = self.all_parameter_names[0]
        self.settings['Y data'] = self.all_parameter_names[1]
        self.settings['xlabel'] = self.all_parameter_names[0]
        self.settings['ylabel'] = self.all_parameter_names[1]

        if self.loaded_data[0,1] == self.loaded_data[0,0] and len(self.all_parameter_names) > 2:
            self.settings['Z data'] = self.all_parameter_names[2]
            self.settings['clabel'] = self.all_parameter_names[2]
            self.dim=3
        else:
            self.dim=2

        self.settings_menu_options = {'X data': self.all_parameter_names,
                                'Y data': self.all_parameter_names,
                                'Z data': self.all_parameter_names}
        negparamnames=[f'-{name}' for name in self.all_parameter_names]
        allnames=np.hstack((self.all_parameter_names,negparamnames))
        self.filter_menu_options = {'Multiply': allnames,
                                    'Divide': allnames,
                                    'Add/Subtract': allnames}

    def get_column_data(self,line=None):
        if line is not None:
            names = [self.plotted_lines[line]['X data'],
                     self.plotted_lines[line]['Y data']]
        else:
            names = [self.settings['X data'], self.settings['Y data']]

        x=self.loaded_data[self.param_name_dict[names[0]]]
        y=self.loaded_data[self.param_name_dict[names[1]]]
        if 'Z data' in self.settings.keys():
            z=self.loaded_data[self.param_name_dict[self.settings['Z data']]]
            column_data=np.column_stack((x,y,z))
        else:
            column_data=np.column_stack((x,y))
        return column_data
    
    def get_columns(self):
        return [int(col) for col in self.settings['columns'].split(',')]
    
    def load_and_reshape_data(self,reload=False,reload_from_file=False,linefrompopup=None):
        if reload_from_file or self.loaded_data is None:
            self.prepare_dataset()
        column_data = self.get_column_data(linefrompopup)
        if column_data.ndim == 1: # if empty array or single-row array
            self.raw_data = None
        else:
            # Determine the number of unique values in the first column to determine the shape of the data
            columns = self.get_columns()
            unique_values, unique_indices = np.unique(column_data[:,columns[0]], 
                                                      return_index=True)
            if len(unique_values) > 1:
                sorted_indices = sorted(unique_indices)
                if len(column_data[sorted_indices[-1]::,0]) < sorted_indices[1]:
                    data_shape = (len(unique_values)-1, sorted_indices[1])
                else:
                    data_shape = (len(unique_values), sorted_indices[1])
            else:
                data_shape = (1, column_data.shape[0])

            if data_shape[0] > 1: # If two or more sweeps are finished
        
                # Check if second column also has unique values at the same 
                # indices as the first column and if the first two values in 
                # the second column repeat ; if both True, skip that column.
                # Relevant for measurements where two parameters are swept simultaneously
                _, next_unique_indices = np.unique(column_data[:,columns[1]], 
                                                   return_index=True)
                if ((np.array_equal(unique_indices, next_unique_indices) or
                     np.array_equal(unique_indices, next_unique_indices[::-1])) and
                    (column_data[1,columns[1]] == column_data[0,columns[1]])):
                    columns[1] += 1
                    if len(columns) > 2 and columns[1] == columns[2]:
                        columns[2] += 1
                
                # Determine if file is 2D or 3D by checking if first two values in first column are repeated
                if column_data[1,columns[0]] != column_data[0,columns[0]] or len(columns) == 2:
                    self.raw_data = [column_data[:,x] for x in range(column_data.shape[1])]
                    columns = columns[:2]
                else: 
                    # flip if first column is sorted from high to low 
                    if unique_values[1] < unique_values[0]: 
                        column_data = np.flipud(column_data)
                        self.udflipped = True
                    self.raw_data = [np.reshape(column_data[:data_shape[0]*data_shape[1],x], data_shape) 
                                     for x in range(column_data.shape[1])]
                    # flip if second column is sorted from high to low
                    if self.raw_data[1][0,0] > self.raw_data[1][0,1]: 
                        self.raw_data = [np.fliplr(self.raw_data[x]) for x in range(column_data.shape[1])]
                        self.lrflipped = True
                        
            elif data_shape[0] == 1: # if first two sweeps are not finished -> duplicate data of first sweep to enable 3D plotting
                self.raw_data = [np.tile(column_data[:data_shape[1],x], (2,1)) for x in range(column_data.shape[1])]    
                if len(unique_values) > 1: # if first sweep is finished -> set second x-column to second x-value
                    self.raw_data[columns[0]][0,:] = unique_values[0]
                    self.raw_data[columns[0]][1,:] = unique_values[1]
                else: # if first sweep is not finished -> set duplicate x-columns to +1 and -1 of actual value
                    self.raw_data[columns[0]][0,:] = unique_values[0]-1
                    self.raw_data[columns[0]][1,:] = unique_values[0]+1
            self.settings['columns'] = ','.join([str(i) for i in columns])

    def shape_single_array(self,array): # Needed to reshape arrays of 2D data that do not get added to raw_data
        if self.dim == 2: # i.e. do nothing.
            return array
        elif self.dim == 3:
            data_shape = self.raw_data[-1].shape
            array = np.reshape(array, data_shape) 
            if hasattr(self,'udflipped'):
                array = np.flipud(array)
            if hasattr(self,'lrflipped'):
                array = np.fliplr(array)
            return array


    def copy_raw_to_processed_data(self,line=None):
        if line is not None:
            self.plotted_lines[line]['raw_data'] = self.raw_data
            self.plotted_lines[line]['processed_data'] = [np.array(np.copy(self.raw_data[x])) for x in self.get_columns()]
        else:
            self.processed_data = [np.array(np.copy(self.raw_data[x])) for x in self.get_columns()]

    def prepare_data_for_plot(self, reload_data=False, reload_from_file=False,
                              linefrompopup=None,update_color_limits=True):
        if not hasattr(self, 'raw_data') or reload_data:
            self.load_and_reshape_data(reload_data, reload_from_file, linefrompopup)
        if self.raw_data:
            self.copy_raw_to_processed_data(linefrompopup)
            self.apply_all_filters(update_color_limits=update_color_limits)
        else:
            self.processed_data = None
    def add_plot(self, editor_window=None):
        if self.processed_data:
            cmap_str = self.view_settings['Colormap']
            if self.view_settings['Reverse']:
                cmap_str += '_r'
            cmap = cm.get_cmap(cmap_str, lut=int(self.settings['lut']))
            cmap.set_bad(self.settings['maskcolor'])

            if self.dim == 2:
                if not hasattr(self, 'plotted_lines'):
                    self.plotted_lines = {0: {'checkstate': 2,
                                                'X data': self.all_parameter_names[0],
                                                'Y data': self.all_parameter_names[1],
                                                'Xerr': 0,
                                                'Yerr': 0,
                                                'raw_data': self.raw_data,
                                                'processed_data': self.processed_data,
                                                'linecolor': (0.1, 0.5, 0.8, 1),
                                                'linewidth': 1.5,
                                                'linestyle': '-',
                                                'filters': []}}
                if not hasattr(self, 'sidebar1D'):
                    self.sidebar1D = Sidebar1D(self,editor_window=editor_window)
                    self.sidebar1D.running = True
                    self.sidebar1D.append_trace_to_table(0)
                    editor_window.oneD_layout.addWidget(self.sidebar1D)

                self.sidebar1D.update()

                # This is horrible, but I need to get rid of these. Ideally I would re-write the extension so they're
                # not used at all in the 1D case. Will try later.
                if 'X data' in self.settings.keys():
                    self.settings.pop('X data')
                if 'Y data' in self.settings.keys():
                    self.settings.pop('Y data')

            elif self.dim == 3:
                norm = MidpointNormalize(vmin=self.view_settings['Minimum'], 
                                         vmax=self.view_settings['Maximum'], 
                                         midpoint=self.view_settings['Midpoint'])
                self.image = self.axes.pcolormesh(self.processed_data[0], 
                                                  self.processed_data[1], 
                                                  self.processed_data[2], 
                                                  shading=self.settings['shading'], 
                                                  norm=norm, cmap=cmap,
                                                  rasterized=self.settings['rasterized'])
                if self.settings['colorbar'] == 'True':
                    self.cbar = self.figure.colorbar(self.image, orientation='vertical')
                # Remove sidebar1D if it exists
                for i in reversed(range(editor_window.oneD_layout.count())): 
                    widgetToRemove = editor_window.oneD_layout.itemAt(i).widget()
                    # remove it from the layout list
                    editor_window.oneD_layout.removeWidget(widgetToRemove)
                    # remove it from the gui
                    widgetToRemove.setParent(None)
            self.cursor = Cursor(self.axes, useblit=True, 
                                 color=self.settings['linecolor'], linewidth=0.5)

            # Below removes data options for data types where selecting
            # axes data from the settings menu isn't implemented.
            # Remove if implemented for all data types one day.
            if 'X data' in self.settings.keys() and self.settings['X data'] == '':
                self.settings.pop('X data')
            if 'Y data' in self.settings.keys() and self.settings['Y data'] == '':
                self.settings.pop('Y data')
            if 'Z data' in self.settings.keys() and self.settings['Z data'] == '':
                self.settings.pop('Z data')

            self.apply_plot_settings()
            self.apply_axlim_settings()
            self.apply_axscale_settings()

    def reset_view_settings(self, overrule=False):
        if not self.view_settings['Locked'] or overrule:
            minimum = np.min(self.processed_data[-1])
            maximum = np.max(self.processed_data[-1])
            self.view_settings['Minimum'] = minimum
            self.view_settings['Maximum'] = maximum
            self.view_settings['Midpoint'] = 0.5*(minimum+maximum)
            self.view_settings['MidLock'] = False
            
    def reset_midpoint(self):
        if self.view_settings['MidLock'] == False:
            self.view_settings['Midpoint'] = 0.5*(self.view_settings['Minimum']+
                                                  self.view_settings['Maximum'])
                    
    def apply_plot_settings(self):
        self.axes.set_xlabel(self.settings['xlabel'], 
                             size=self.settings['labelsize'])
        self.axes.set_ylabel(self.settings['ylabel'], 
                             size=self.settings['labelsize'])
        # if isinstance(self.image, list):
        #     self.image[0].set_linewidth(float(self.settings['linewidth']))
        for axis in ['top','bottom','left','right']:
            self.axes.spines[axis].set_linewidth(float(self.settings['spinewidth']))
        self.axes.tick_params(labelsize=self.settings['ticksize'], 
                              width=float(self.settings['spinewidth']), 
                              color=rcParams['axes.edgecolor'])
        if self.settings['minorticks'] == 'True':
            self.axes.minorticks_on()
        if self.settings['title'] == '<label>':
            self.axes.set_title(self.label, size=self.settings['titlesize'])
        else:
            self.axes.set_title(self.settings['title'], 
                                size=self.settings['titlesize'])
        if self.settings['colorbar'] == 'True' and len(self.get_columns()) == 3:
            self.cbar.ax.set_title(self.settings['clabel'], 
                                   size=self.settings['labelsize'])
            self.cbar.ax.tick_params(labelsize=self.settings['ticksize'], 
                                     color=rcParams['axes.edgecolor']) 
            self.cbar.outline.set_linewidth(float(self.settings['spinewidth']))
        if ('Crop Y' in [filt.name for filt in self.filters] 
            and len(self.get_columns()) == 3):
            crop_filters = [filt for filt in self.filters 
                            if filt.name == 'Crop Y']
            for filt in crop_filters:
                if filt.method == 'Lim' and filt.checkstate:
                    self.axes.set_ylim(top=float(filt.settings[1]), 
                                       bottom=float(filt.settings[0]))
        if ('Crop X' in [filt.name for filt in self.filters]):
            crop_filters = [filt for filt in self.filters 
                            if filt.name == 'Crop X']
            for filt in crop_filters:
                if filt.method == 'Lim' and filt.checkstate:
                    self.axes.set_xlim(left=float(filt.settings[0]), 
                                       right=float(filt.settings[1]))

    def apply_view_settings(self):
        if len(self.get_columns()) == 3:
            norm = MidpointNormalize(vmin=self.view_settings['Minimum'], 
                                     vmax=self.view_settings['Maximum'], 
                                     midpoint=self.view_settings['Midpoint'])

            self.image.norm=norm

            if self.settings['colorbar'] == 'True' and hasattr(self, 'cbar'):
                #self.cbar.update_normal(self.image)
                self.cbar.ax.set_title(self.settings['clabel'],
                                       size=self.settings['labelsize'])
                self.cbar.ax.tick_params(labelsize=self.settings['ticksize'],
                                         color=rcParams['axes.edgecolor'])

    def apply_axlim_settings(self):
        self.axes.set_xlim(left=self.axlim_settings['Xmin'], 
                             right=self.axlim_settings['Xmax'])
        self.axes.set_ylim(bottom=self.axlim_settings['Ymin'],
                             top=self.axlim_settings['Ymax'])

    def apply_axscale_settings(self):
        self.axes.set_xscale(self.axlim_settings['Xscale'])
        self.axes.set_yscale(self.axlim_settings['Yscale'])
        
    def reset_axlim_settings(self):
        self.axes.autoscale()
        self.axlim_settings['Xmin'] = self.axes.get_xlim()[0]
        self.axlim_settings['Xmax'] = self.axes.get_xlim()[1]
        self.axlim_settings['Ymin'] = self.axes.get_ylim()[0]
        self.axlim_settings['Ymax'] = self.axes.get_ylim()[1]
    
    def apply_colormap(self):
        cmap_str = self.view_settings['Colormap']
        if self.view_settings['Reverse']:
            cmap_str += '_r'
        cmap = cm.get_cmap(cmap_str, lut=int(self.settings['lut']))
        cmap.set_bad(self.settings['maskcolor'])
        if len(self.get_columns()) == 3:
            self.image.set_cmap(cmap)
        else:
            self.image[0].set_color(cmap(0.5))            

    def apply_single_filter(self, processed_data, filt):
        if filt.name in ['Multiply', 'Divide', 'Add/Subtract']:
            if filt.settings[0][0]=='-':
                arrayname=filt.settings[0][1:]
                setting2='-'
            else:
                arrayname=filt.settings[0]
                setting2='+'
            if arrayname in self.all_parameter_names:
                array=self.shape_single_array(self.loaded_data[self.param_name_dict[arrayname]])

            else:
                array=None
            processed_data = filt.function(processed_data,
                                            filt.method,
                                            filt.settings[0], 
                                            setting2,
                                            array)
        else:
            processed_data = filt.function(processed_data,
                                            filt.method,
                                            filt.settings[0],
                                            filt.settings[1])
            
        return processed_data
        
    def apply_all_filters(self, update_color_limits=True):
        if hasattr(self, 'sidebar1D'):
            for line in self.plotted_lines.keys():
                filters = self.plotted_lines[line]['filters']
                processed_data = self.plotted_lines[line]['processed_data']
                for filt in filters:
                    if filt.checkstate:
                        processed_data = self.apply_single_filter(processed_data, filt)
                self.plotted_lines[line]['processed_data'] = processed_data

        else:
            filters=self.filters
            processed_data = self.processed_data
            for filt in filters:
                if filt.checkstate:
                    processed_data = self.apply_single_filter(processed_data, filt)
            self.processed_data = processed_data
            if update_color_limits:
                self.reset_view_settings()
       
    def extension_setting_edited(self, editor, setting_name):
        pass
        
    def add_extension_actions(self, editor, menu):
        pass
    
    def do_extension_actions(self, editor, menu):
        pass
        
    def file_finished(self):
        return False
    
    def hide_linecuts(self):  # Likely soon to be unused.
        if hasattr(self, 'linecut_window'):
            self.linecut_window.running = False
        for line in reversed(self.axes.get_lines()):
            line.remove()
            del line
        for patch in reversed(self.axes.patches):
            patch.remove()
            del patch
        if hasattr(self, 'linecut_points'):
            del self.linecut_points
        self.canvas.draw()
    
    def open_fft_window(self):
        if self.fft_orientation == 'vertical':
            self.fft = np.fft.rfft(self.processed_data[-1], axis=1)
        elif self.fft_orientation == 'horizontal':
            self.fft = np.fft.rfft(self.processed_data[-1], axis=0)
        self.fft_window = FFTWindow(self.fft)
        self.fft_window.show()


class NumpyData(BaseClassData):
    def __init__(self, filepath, canvas, dataset):
        super().__init__(filepath, canvas)
        self.dataset = dataset
        self.label = self.dataset['Label']
        for setting, value in self.dataset['Settings'].items():
            if setting in self.settings:
                self.settings[setting] = value        
        self.filters = self.dataset['Filters']
        self.view_settings = self.dataset['View Settings']
        self.axlim_settings = self.dataset['Axlim Settings']
        self.raw_data = self.dataset['Raw Data']

    def prepare_data_for_plot(self, reload_data=False):
        self.copy_raw_to_processed_data()
        self.apply_all_filters()



class InternalData(BaseClassData):
    # Class for datasets that are not saved to file, but are created in the program.
    # Combined files, fitting results....
    def __init__(self, canvas, dataset, label_name, all_parameter_names,dimension):
        super().__init__(filepath='internal_data', canvas=canvas)

        self.loaded_data = dataset
        self.canvas = canvas
        self.all_parameter_names = all_parameter_names
        self.param_name_dict={}
        for i,name in enumerate(self.all_parameter_names):
            self.param_name_dict[name]=i
        self.label = label_name
        self.dim = dimension

        self.prepare_dataset()

    def prepare_dataset(self):
        # prepare_dataset usually loads the data; here we have already loaded it, just need to set the names.

        self.settings['X data'] = self.all_parameter_names[0]
        self.settings['Y data'] = self.all_parameter_names[1]
        self.settings['xlabel'] = self.all_parameter_names[0]
        self.settings['ylabel'] = self.all_parameter_names[1]
        if self.dim==3:
            self.settings['Z data'] = self.all_parameter_names[2]
            self.settings['clabel'] = self.all_parameter_names[2]

        self.settings_menu_options = {'X data': self.all_parameter_names,
                                'Y data': self.all_parameter_names,
                                'Z data': self.all_parameter_names}
        negparamnames=[f'-{name}' for name in self.all_parameter_names]
        allnames=np.hstack((self.all_parameter_names,negparamnames))
        self.filter_menu_options = {'Multiply': allnames,
                                    'Divide': allnames,
                                    'Add/Subtract': allnames}
        
    def load_and_reshape_data(self,reload=False,reload_from_file=False,linefrompopup=None):
        # For combined files, the data is already loaded and reshaped.
        # Just need to set the raw_data
        self.raw_data = self.get_column_data(linefrompopup)
        self.settings['columns'] = ','.join([str(i) for i in range(self.dim)])
    
    def get_column_data(self,line=None):
        if line is not None:
            names = [self.plotted_lines[line]['X data'],
                     self.plotted_lines[line]['Y data']]
        else:
            names = [self.settings['X data'], self.settings['Y data']]

        x=self.loaded_data[self.param_name_dict[names[0]]]
        y=self.loaded_data[self.param_name_dict[names[1]]]

        if line is None and 'Z data' in self.settings.keys():
            z=self.loaded_data[self.param_name_dict[self.settings['Z data']]]
            column_data=[x,y,z]
        else:
            column_data=[x,y]
        return column_data
    
    def copy(self):
        # Copy the data to a new object.
        new_data = InternalData(self.canvas, self.loaded_data, self.label, self.all_parameter_names,self.dim)
        return new_data
    
class MixedInternalData(InternalData):
    # Class for combination of a single 2D dataset and various 1D datasets.
    def __init__(self, canvas, dataset2d, dataset1d, label_name):
        super().__init__(canvas, dataset1d.loaded_data, label_name, dataset1d.all_parameter_names,dimension=3)

        self.dataset2d = dataset2d
        self.dataset1d = dataset1d
        self.canvas = canvas
        # self.param_name_dict_2d={}
        # self.param_name_dict_1d={}
        # for i,name in enumerate(self.all_parameter_names_2d):
        #     self.param_name_dict_2d[name]=i
        # for i,name in enumerate(self.all_parameter_names_1d):
        #     self.param_name_dict_1d[name]=i
        self.label = label_name
        self.dim = 'mixed'

        #self.prepare_dataset()
        self.settings = self.dataset2d.settings
        self.axlim_settings = self.dataset2d.axlim_settings
        self.view_settings = self.dataset2d.view_settings
    
    def prepare_data_for_plot(self, *args, **kwargs):
        self.dataset2d.prepare_data_for_plot()
        self.dataset1d.prepare_data_for_plot()

    # def add_plot(self, editor_window=None):
    #     # Add the 2D plot first, then the 1D plots.
    #     self.dataset2d.axes=self.axes
    #     self.dataset2d.figure=self.figure
    #     self.dataset1d.axes=self.axes
    #     self.dataset1d.figure=self.figure
    #     self.figure.clf()
    #     self.dataset2d.add_plot(editor_window=editor_window,clear_fig=False)
    #     self.dataset1d.add_plot(editor_window=editor_window,clear_fig=False)

    def add_plot(self, editor_window=None):
        # Add the 2D plot first, then the 1D plots.
        self.dataset2d.axes=self.axes
        self.dataset2d.figure=self.figure
        self.dataset1d.axes=self.axes
        self.dataset1d.figure=self.figure

        cmap_str = self.view_settings['Colormap']
        if self.view_settings['Reverse']:
            cmap_str += '_r'
        cmap = cm.get_cmap(cmap_str, lut=int(self.settings['lut']))
        cmap.set_bad(self.settings['maskcolor'])

        norm = MidpointNormalize(vmin=self.dataset2d.view_settings['Minimum'], 
                                    vmax=self.dataset2d.view_settings['Maximum'], 
                                    midpoint=self.dataset2d.view_settings['Midpoint'])
        self.image = self.axes.pcolormesh(self.dataset2d.processed_data[0], 
                                            self.dataset2d.processed_data[1], 
                                            self.dataset2d.processed_data[2], 
                                            shading=self.settings['shading'], 
                                            norm=norm, cmap=cmap,
                                            rasterized=self.settings['rasterized'])
        if self.settings['colorbar'] == 'True':
            self.cbar = self.figure.colorbar(self.image, orientation='vertical')

        if not hasattr(self.dataset1d, 'plotted_lines'):
            self.dataset1d.plotted_lines = {0: {'checkstate': 2,
                                        'X data': self.dataset1d.all_parameter_names[0],
                                        'Y data': self.dataset1d.all_parameter_names[1],
                                        'Xerr': 0,
                                        'Yerr': 0,
                                        'raw_data': self.dataset1d.raw_data,
                                        'processed_data': self.dataset1d.processed_data,
                                        'linecolor': (0.1, 0.5, 0.8, 1),
                                        'linewidth': 1.5,
                                        'linestyle': '-',
                                        'filters': []}}
        if not hasattr(self.dataset1d, 'sidebar1D'):
            self.dataset1d.sidebar1D = Sidebar1D(self.dataset1d,editor_window=editor_window)
            self.dataset1d.sidebar1D.running = True
            self.dataset1d.sidebar1D.append_trace_to_table(0)
        editor_window.oneD_layout.addWidget(self.dataset1d.sidebar1D)

        self.dataset1d.sidebar1D.update(clearplot=False)

        self.cursor = Cursor(self.axes, useblit=True, 
                                color=self.settings['linecolor'], linewidth=0.5)

        self.dataset2d.apply_plot_settings()
        self.dataset2d.apply_axlim_settings()
        self.dataset2d.apply_axscale_settings()

    # def copy(self):
    #     # Copy the data to a new object.
    #     new_data = MixedInternalData(self.canvas, self.loaded_data_2d, self.loaded_data_1d, self.label, self.all_parameter_names_2d, self.all_parameter_names_1d)
    #     return new_data