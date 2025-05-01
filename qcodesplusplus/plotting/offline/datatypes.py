from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np
import os
from matplotlib.widgets import Cursor
from matplotlib import cm, rcParams
from .helpers import MidpointNormalize
from .popupwindows import FFTWindow, Popup1D

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
        
    def get_column_data(self):
        try:
            column_data = np.genfromtxt(self.filepath, delimiter=self.settings['delimiter'])
        except ValueError: # Can occur if python doesn't recognise a header
            column_data = np.genfromtxt(self.filepath, delimiter=self.settings['delimiter'],skip_header=1)

        # if column_data.shape[0]<column_data.shape[1]: # Should be getting three columns and many more rows. If not the case, try to transpose.
        #     column_data=column_data.transpose()
        
        try: # to get column names if there is a header. Importing like this completely screws the data formatting for some reason, so use this to just load the header
            namedata=np.genfromtxt(self.filepath, delimiter=self.settings['delimiter'],names=True)
            if namedata.dtype.names:
                self.column_array=namedata.dtype.names
                self.column_dict={}
                for i,name in enumerate(namedata.dtype.names):
                    self.column_dict[name]=i
        except:
            pass

        # This whole column names thing is incomplete... Will finish at some point, just not priority.
        # The way that data is loaded is completely opaque to me. I have no idea where the columns are first defined.

        if not hasattr(self,'column_dict'):
            self.column_array=[i for i in range(column_data.shape[1])]
            self.column_dict={}
            for i in self.column_array:
                self.column_dict[f'{i}']=i

        self.settings_menu_options = {'X data': self.column_array,
                                      'Y data': self.column_array,
                                      'Z data': self.column_array}

        self.measured_data_points = column_data.shape[0]
        return column_data
    
    def get_columns(self):
        return [int(col) for col in self.settings['columns'].split(',')]
    
    def load_and_reshape_data(self,reload=False,reload_from_file=False, fromPopup1D=False):
        column_data = self.get_column_data()
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
                    self.raw_data = [np.reshape(column_data[:data_shape[0]*data_shape[1],x], data_shape) 
                                     for x in range(column_data.shape[1])]
                    # flip if second column is sorted from high to low
                    if self.raw_data[1][0,0] > self.raw_data[1][0,1]: 
                        self.raw_data = [np.fliplr(self.raw_data[x]) for x in range(column_data.shape[1])]
                        
            elif data_shape[0] == 1: # if first two sweeps are not finished -> duplicate data of first sweep to enable 3D plotting
                self.raw_data = [np.tile(column_data[:data_shape[1],x], (2,1)) for x in range(column_data.shape[1])]    
                if len(unique_values) > 1: # if first sweep is finished -> set second x-column to second x-value
                    self.raw_data[columns[0]][0,:] = unique_values[0]
                    self.raw_data[columns[0]][1,:] = unique_values[1]
                else: # if first sweep is not finished -> set duplicate x-columns to +1 and -1 of actual value
                    self.raw_data[columns[0]][0,:] = unique_values[0]-1
                    self.raw_data[columns[0]][1,:] = unique_values[0]+1
            self.settings['columns'] = ','.join([str(i) for i in columns])

            # self.settings['X data']=self.column_array[columns[0]]
            # self.settings['Y data']=self.column_array[columns[1]]
            # if len(self.get_columns())>2:
            #     self.settings['Z data']=self.column_array[columns[2]]
            # else:
            #     self.settings.pop('Z data', None)
                   
    def copy_raw_to_processed_data(self):
        self.processed_data = [np.array(np.copy(self.raw_data[x])) for x in self.get_columns()]

    def prepare_data_for_plot(self, reload_data=False, refresh_filters=False, reload_from_file=False,linefrompopup=None):
        if not hasattr(self, 'raw_data') or reload_data:
            self.load_and_reshape_data(reload_data, reload_from_file, linefrompopup)
        if self.raw_data:
            self.copy_raw_to_processed_data()
            self.apply_all_filters()
        else:
            self.processed_data = None

    def add_plot(self, dim):
        if self.processed_data:
            cmap_str = self.view_settings['Colormap']
            if self.view_settings['Reverse']:
                cmap_str += '_r'
            cmap = cm.get_cmap(cmap_str, lut=int(self.settings['lut']))
            cmap.set_bad(self.settings['maskcolor'])
            if dim == 2:
                self.image = self.axes.plot(self.processed_data[0], 
                                            self.processed_data[1], color=cmap(0.5))

            elif dim == 3:
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
            self.image.set_norm(norm)
            if self.settings['colorbar'] == 'True':
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

    # The below function seems to NOT be used by anything!!
    def apply_filter(self, filt, update_color_limits=True):
        if filt.checkstate:
            self.processed_data = filt.function(self.processed_data, 
                                                filt.method,
                                                filt.settings[0], 
                                                filt.settings[1]) 
            if update_color_limits:
                self.reset_view_settings()
                self.apply_view_settings()
                
    def apply_all_filters(self, update_color_limits=True):
        # Note to Damon (i.e. self): Don't forget this is redefined in the qcpp wrapper.
        for filt in self.filters:
            if filt.checkstate:
                self.processed_data = filt.function(self.processed_data, 
                                                    filt.method,
                                                    filt.settings[0], 
                                                    filt.settings[1])
        if update_color_limits:
            self.reset_view_settings()
            if hasattr(self, 'image'):
                self.apply_view_settings()
       
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