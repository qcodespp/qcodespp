from PyQt5 import QtWidgets, QtCore
import numpy as np
import os
import copy
import warnings
from matplotlib.widgets import Cursor
from matplotlib import cm, rcParams
from qcodespp.plotting.offline.helpers import MidpointNormalize
from qcodespp.plotting.offline.sidebars import Sidebar1D

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
    DEFAULT_PLOT_SETTINGS['delimiter'] = ''
    DEFAULT_PLOT_SETTINGS['titlesize'] = '12'
    DEFAULT_PLOT_SETTINGS['labelsize'] = '12' 
    DEFAULT_PLOT_SETTINGS['ticksize'] = '12'
    # The above three now get overridden by global_text_size
    DEFAULT_PLOT_SETTINGS['spinewidth'] = '1'
    DEFAULT_PLOT_SETTINGS['colorbar'] = 'True'
    DEFAULT_PLOT_SETTINGS['minorticks'] = 'False'
    DEFAULT_PLOT_SETTINGS['maskcolor'] = 'black'
    DEFAULT_PLOT_SETTINGS['cmap levels'] = '128'
    DEFAULT_PLOT_SETTINGS['rasterized'] = 'True'
    DEFAULT_PLOT_SETTINGS['dpi'] = '300'
    DEFAULT_PLOT_SETTINGS['transparent'] = 'True'
    DEFAULT_PLOT_SETTINGS['shading'] = 'auto'
    DEFAULT_PLOT_SETTINGS['columns'] = '0,1,2'
    
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
    DEFAULT_VIEW_SETTINGS['CBarHist'] = True

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
        self.plot_type=None
        
        self.settings = self.DEFAULT_PLOT_SETTINGS.copy()
        self.settings['title'] = self.label
        self.view_settings = self.DEFAULT_VIEW_SETTINGS.copy()
        self.axlim_settings = self.DEFAULT_AXLIM_SETTINGS.copy()
        self.filters = []
        self.legend=False

        self.label_locks={'x':False,'y':False,'c':False}

        try: # on Windows
            self.creation_time = os.path.getctime(filepath)
        except Exception:
            try: # on Mac
                self.creation_time = os.stat(filepath).st_birthtime
            except Exception:
                self.creation_time = None

    def prepare_dataset(self):
        # Loads the data from file and prepares a data_dict, where the arrays are stored identified by 
        # either their header column names, or by their column number if no header is present.
        # These names are then sent to various parts of the GUI.
        try:
            self.loaded_data = np.genfromtxt(self.filepath, delimiter=self.settings['delimiter'])
        except ValueError: # Can occur if python doesn't recognise a header
            self.loaded_data = np.genfromtxt(self.filepath, delimiter=self.settings['delimiter'],skip_header=1)

        if self.loaded_data.shape[0] > 0 and self.loaded_data.shape[1] > 0:
            # Only do stuff if data has actually been loaded.
            if self.settings['transpose'] == 'False':
                self.loaded_data = np.transpose(self.loaded_data)

            if hasattr(self, 'extra_cols'):
                # Processed data that has been added to the data_dict. Need to preserve it!
                old_dict = copy.deepcopy(self.data_dict)
            
            self.data_dict={}
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
                        self.data_dict[name]=self.loaded_data[i]
            except Exception as e:
                pass

            if hasattr(self, 'extra_cols'):
                # Add the extra columns to the data_dict
                for col in self.extra_cols:
                    if col in old_dict.keys():
                        self.data_dict[col] = old_dict[col]
                        self.all_parameter_names.append(col)
                del old_dict

            if len(self.data_dict.keys()) == 0:
                self.all_parameter_names=[f"column_{i}" for i in range(self.loaded_data.shape[0])]
                for i,name in enumerate(self.all_parameter_names):
                    self.data_dict[name]=self.loaded_data[i]

            self.settings['X data'] = self.all_parameter_names[0]
            self.settings['Y data'] = self.all_parameter_names[1]
            self.settings['xlabel'] = self.all_parameter_names[0]
            self.settings['ylabel'] = self.all_parameter_names[1]
            self.settings['default_xlabel'] = self.all_parameter_names[0]
            self.settings['default_ylabel'] = self.all_parameter_names[1]
            self.settings['default_fftxlabel'] = f'1/{self.all_parameter_names[0]}'

            if self.loaded_data[0,1] == self.loaded_data[0,0] and len(self.all_parameter_names) > 2:
                self.settings['Z data'] = self.all_parameter_names[2]
                self.settings['clabel'] = self.all_parameter_names[2]
                self.settings['default_clabel'] = self.all_parameter_names[2]
                self.settings['default_histlabel'] = self.all_parameter_names[2]
                self.settings['default_fftylabel'] = f'1/{self.all_parameter_names[1]}'
                self.dim=3
            else:
                self.dim=2
                self.settings['default_histlabel'] = self.all_parameter_names[1]

            self.settings_menu_options = {'X data': self.all_parameter_names,
                                    'Y data': self.all_parameter_names,
                                    'Z data': self.all_parameter_names}
            negparamnames=[f'-{name}' for name in self.all_parameter_names]
            allnames=np.hstack((self.all_parameter_names,negparamnames))
            self.filter_menu_options = {'Multiply': allnames,
                                        'Divide': allnames,
                                        'Add/Subtract': allnames}

        else:
            return ValueError(f'Could not load data from {self.filepath}. File may be empty or not formatted correctly.')
        
    def get_column_data(self,line=None):
        if line is not None:
            names = [self.plotted_lines[line]['X data'],
                     self.plotted_lines[line]['Y data']]
        else:
            names = [self.settings['X data'], self.settings['Y data']]
        x=self.data_dict[names[0]]
        y=self.data_dict[names[1]]
        self.settings['default_xlabel'] = names[0]
        self.settings['default_ylabel'] = names[1]
        if 'Z data' in self.settings.keys():
            z=self.data_dict[self.settings['Z data']]
            self.settings['default_clabel'] = self.settings['Z data']
            column_data=np.column_stack((x,y,z))
        else:
            if len(x)==len(y):
                column_data = np.column_stack((x, y))
            else:
                column_data = np.zeros((2,2))
                # This can happen if the user has run statistics, and is trying to plot the result; if they change only
                # the X data, the length of the data won't match the Y data until they then select the correct thing.
                # So, just plot nothing until the user selects something sensible.
        return column_data
    
    def get_columns(self):
        return [int(col) for col in self.settings['columns'].split(',')]
    
    def load_and_reshape_data(self,reload_data=False,reload_from_file=False,linefrompopup=None):
        if reload_from_file or self.loaded_data is None:
            error=self.prepare_dataset()
            if error:
                return error
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
        
    def add_array_to_data_dict(self, array, name):
        self.data_dict[name] = array
        self.all_parameter_names=list(self.data_dict.keys())

        for label in ['X data', 'Y data', 'Z data']:
            self.settings_menu_options[label]= self.all_parameter_names
        negparamnames=[f'-{name}' for name in self.all_parameter_names]
        allnames=np.hstack((self.all_parameter_names,negparamnames))
        for filtname in ['Multiply', 'Divide', 'Add/Subtract']:
            self.filter_menu_options[filtname]=allnames

        if not hasattr(self, 'extra_cols'):
            self.extra_cols = []
        self.extra_cols.append(name)

    def filttocol(self, axis):
        axes={'X': 0, 'Y': 1, 'Z': 2}
        if hasattr(self, 'sidebar1D'):
            current_1D_row = self.sidebar1D.trace_table.currentRow()
            current_line = int(self.sidebar1D.trace_table.item(current_1D_row,0).text())
            data_to_send = self.plotted_lines[current_line]['processed_data'][axes[axis]]
            colname=f'Filtered: {self.plotted_lines[current_line][f'{axis} data']}'
        else:
            data_to_send = self.processed_data[axes[axis]]
            colname= f'Filtered: {self.settings[f'{axis} data']}'
        self.add_array_to_data_dict(data_to_send, colname)

    def copy_raw_to_processed_data(self,line=None):
        if line is not None:
            self.plotted_lines[line]['raw_data'] = self.raw_data
            self.plotted_lines[line]['processed_data'] = [np.array(np.copy(self.raw_data[x])) for x in self.get_columns()]
        else:
            self.processed_data = [np.array(np.copy(self.raw_data[x])) for x in self.get_columns()]

    # After the data has been reshaped into raw_data and copied to processed_data,
    # first again reshape the data if it should be plotted as a histogram or FFT.
    # After this step, it goes through the filters.
    def reshape_for_plot_type(self, line=None):
        type_dict={'Histogram': lambda: self.plot_type_histogram(line),
                   'FFT': lambda: self.plot_type_fft(line),
                   'Histogram Y': self.plot_type_histogram_y,
                   'Histogram X': self.plot_type_histogram_x,
                   'FFT Y': self.plot_type_ffty,
                   'FFT X': self.plot_type_fftx,
                   'FFT X/Y': self.plot_type_fftxy}
        type_dict[self.plot_type]()

    def plot_type_histogram(self,line):
        y,x=np.histogram(self.plotted_lines[line]['processed_data'][1], bins=int(self.plotted_lines[line]['Bins']))
        x=(x[:-1]+x[1:])/2
        self.plotted_lines[line]['processed_data']=[x,y]

    def plot_type_fft(self,line):
        y=np.abs(np.fft.rfft(self.plotted_lines[line]['processed_data'][1],norm='ortho'))
        x=np.fft.rfftfreq(self.plotted_lines[line]['processed_data'][1].shape[0], d=np.abs(self.plotted_lines[line]['processed_data'][0][1]-self.plotted_lines[line]['processed_data'][0][0]))
        self.plotted_lines[line]['processed_data']=[x,y]

    def plot_type_histogram_y(self):
        bins=self.settings['binsY']
        new_zdata=np.zeros((self.processed_data[-1].shape[0],bins))
        new_ydata=np.zeros((self.processed_data[-1].shape[0],bins))
        new_xdata=np.zeros((self.processed_data[-1].shape[0],bins))

        for i in range(self.processed_data[-1].shape[0]):
            new_zdata[i,:],y=np.histogram(self.processed_data[-1][i,:], bins=bins)
            new_ydata[i,:]=(y[:-1]+y[1:])/2
            new_indices=np.linspace(0,bins-1,bins)
            old_indices=np.linspace(0,self.processed_data[0].shape[1]-1,self.processed_data[0].shape[1])
            new_xdata[i,:]=np.interp(new_indices,old_indices,self.processed_data[0][i,:])
        self.processed_data=[new_xdata,new_ydata,new_zdata]

    def plot_type_histogram_x(self):
        bins=self.settings['binsX']
        new_zdata=np.zeros((bins,self.processed_data[-1].shape[1]))
        new_ydata=np.zeros((bins,self.processed_data[-1].shape[1]))
        new_xdata=np.zeros((bins,self.processed_data[-1].shape[1]))

        for i in range(self.processed_data[-1].shape[1]):
            new_zdata[:,i],x=np.histogram(self.processed_data[-1][:,i], bins=bins)
            new_xdata[:,i]=(x[:-1]+x[1:])/2
            new_indices=np.linspace(0,bins-1,bins)
            old_indices=np.linspace(0,self.processed_data[1].shape[0]-1,self.processed_data[1].shape[0])
            new_ydata[:,i]=np.interp(new_indices,old_indices,self.processed_data[1][:,i])
        self.processed_data=[new_xdata,new_ydata,new_zdata]

    def plot_type_ffty(self):
        zdata=np.abs(np.fft.rfft(self.processed_data[-1],norm='ortho',axis=1))
        ydata=np.zeros_like(zdata)
        for i in range(ydata.shape[0]):
            ydata[i,:]=np.linspace(0,1/(2*np.abs(self.processed_data[1][i,1]-self.processed_data[1][i,0])),zdata.shape[1])
        xdata=np.zeros_like(zdata)
        for i in range(xdata.shape[0]):
            xdata[i,:]=np.interp(np.arange(np.shape(xdata)[1]),np.arange(np.shape(self.processed_data[0])[1]),self.processed_data[0][i,:])
        self.processed_data=[xdata,ydata,zdata]

    def plot_type_fftx(self):
        zdata=np.abs(np.fft.rfft(self.processed_data[-1],norm='ortho',axis=0))
        xdata=np.zeros_like(zdata)
        for i in range(xdata.shape[1]):
            xdata[:,i]=np.linspace(0,1/(2*np.abs(self.processed_data[0][1,i]-self.processed_data[0][0,i])),zdata.shape[0])
        ydata=np.zeros_like(zdata)
        for i in range(ydata.shape[1]):
            ydata[:,i]=np.interp(np.arange(np.shape(ydata)[0]),np.arange(np.shape(self.processed_data[1])[0]),self.processed_data[1][:,i])
        self.processed_data=[xdata,ydata,zdata]

    def plot_type_fftxy(self):
        xdata = self.processed_data[0]
        ydata = self.processed_data[1]
        zdata = self.processed_data[-1]
        zdata=np.abs(np.fft.rfft2(zdata,norm='ortho'))
        # It's actually simple... x and y data are the frequencies, which go between zero and Nyquist, i.e. 1/2 the sampling rate.
        xdata=np.tile(np.linspace(0,1/(2*np.abs(xdata[:,0][1]-xdata[:,0][0])),zdata.shape[0]),(zdata.shape[1],1)).T
        ydata=np.tile(np.linspace(0,1/(2*np.abs(ydata[0][1]-ydata[0][0])),zdata.shape[1]),(zdata.shape[0],1))
        self.processed_data=[xdata,ydata,zdata]

    def prepare_data_for_plot(self, reload_data=False, reload_from_file=False,
                              linefrompopup=None,update_color_limits=False,plot_type=None):
        if not hasattr(self, 'raw_data') or reload_data:
            error=self.load_and_reshape_data(reload_data, reload_from_file, linefrompopup)
            if error:
                return error
            update_color_limits = True
        if self.raw_data:
            self.copy_raw_to_processed_data(linefrompopup)
            if hasattr(self,'plot_type') and self.plot_type not in ['X,Y','X,Y,Z',None]:
                self.reshape_for_plot_type(linefrompopup)
            self.apply_all_filters(update_color_limits=update_color_limits)
        else:
            self.processed_data = None

    def init_plotted_lines(self):
        self.plotted_lines = {0: {'checkstate': 2,
                        'X data': self.all_parameter_names[0],
                        'Y data': self.all_parameter_names[1],
                        'Bins': 100,
                        'Xerr': 0,
                        'Yerr': 0,
                        'raw_data': self.raw_data,
                        'processed_data': self.processed_data,
                        'linecolor': (0.1, 0.5, 0.8, 1),
                        'linewidth': 1.5,
                        'linestyle': '-',
                        'filters': []}}
        
    def add_cbar_hist(self):
        self.hax=self.cbar.ax.inset_axes([-1.05, 0, 1, 1],picker=True)
        counts, self.cbar_hist_bins = np.histogram(self.processed_data[-1],bins=int(self.settings['cmap levels']),
                                                   range=(np.nanmin(self.processed_data[-1]), np.nanmax(self.processed_data[-1])))
        midpoints = self.cbar_hist_bins[:-1] + np.diff(self.cbar_hist_bins)/2
        self.hax.fill_between(-counts, midpoints,0,color='mediumslateblue')
        self.haxfill=self.hax.fill_betweenx(np.linspace(self.view_settings['Minimum'], self.view_settings['Maximum'], 100), 
                                                        self.hax.get_xlim()[0], 
                                                        color='blue', alpha=0.2)

        self.hax.margins(0)
        self.hax.spines[:].set_linewidth(0.5)
        self.hax.get_xaxis().set_visible(False)
        self.hax.get_yaxis().set_visible(False)

    def add_plot(self, editor_window):
        if hasattr(self, 'columns_bad') and isinstance(self.columns_bad, Exception):
            self.axes.text(
                    0.5, 0.5, str(self.columns_bad),
                    ha='center', va='center', fontsize=18, color='k',
                    transform=self.axes.transAxes
                )
        elif self.processed_data:
            try:
                with warnings.catch_warnings(record=True) as recorded_warnings:
                    if self.dim == 2:
                        if not hasattr(self, 'plotted_lines'):
                            self.init_plotted_lines()
                        if not hasattr(self, 'sidebar1D'):
                            self.sidebar1D = Sidebar1D(self,editor_window=editor_window)
                            self.sidebar1D.running = True
                            self.sidebar1D.append_trace_to_table(0)
                        self.sidebar1D.update()

                        # This is horrible, but I need to get rid of these. Ideally I would re-write the extension so they're
                        # not used at all in the 1D case. Will try later.
                        if 'X data' in self.settings.keys():
                            self.settings.pop('X data')
                        if 'Y data' in self.settings.keys():
                            self.settings.pop('Y data')

                    elif self.dim == 3:
                        cmap_str = self.view_settings['Colormap']
                        if self.view_settings['Reverse']:
                            cmap_str += '_r'
                        cmap = cm.get_cmap(cmap_str, lut=int(self.settings['cmap levels']))
                        cmap.set_bad(self.settings['maskcolor'])

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
                            self.cbar = self.figure.colorbar(self.image)
                            if self.view_settings['CBarHist'] == True:
                                self.add_cbar_hist()

                    if (any([not locked for locked in self.label_locks.values()]) or
                        (self.plot_type and ('Histogram' in self.plot_type or 'FFT' in self.plot_type))):
                        self.apply_default_labels()

                    self.cursor = Cursor(self.axes, useblit=True,
                                        color='black', linewidth=0.5)

                    # Below removes data options for data types where selecting
                    # axes data from the settings menu isn't implemented.
                    # Should now be implemented for all data types. Marked for deletion 26/08/2025
                    # if 'X data' in self.settings.keys() and self.settings['X data'] == '':
                    #     self.settings.pop('X data')
                    # if 'Y data' in self.settings.keys() and self.settings['Y data'] == '':
                    #     self.settings.pop('Y data')
                    # if 'Z data' in self.settings.keys() and self.settings['Z data'] == '':
                    #     self.settings.pop('Z data')

                    self.apply_plot_settings()
                    self.apply_axlim_settings()
                    self.apply_axscale_settings()

                if len(recorded_warnings) > 0:
                    return recorded_warnings
            except Exception as e:
                return type(e)(f"Error while plotting {self.label}:\n{type(e).__name__}: {e}")

    def apply_default_labels(self):
        if not self.label_locks['x'] and 'default_xlabel' in self.settings.keys():
            self.settings['xlabel'] = self.settings['default_xlabel']
        if not self.label_locks['y'] and 'default_ylabel' in self.settings.keys():
            self.settings['ylabel'] = self.settings['default_ylabel']
        if not self.label_locks['c'] and 'default_clabel' in self.settings.keys():
            self.settings['clabel'] = self.settings['default_clabel']

        if self.dim == 3:
            if self.plot_type and 'Histogram' in self.plot_type:
                self.settings['clabel'] = 'Counts'
                if self.plot_type == 'Histogram Y' and 'default_histlabel' in self.settings.keys():
                    self.settings['ylabel'] = self.settings['default_histlabel']
                elif self.plot_type == 'Histogram X' and 'default_histlabel' in self.settings.keys():
                    self.settings['xlabel'] = self.settings['default_histlabel']
            elif self.plot_type and 'FFT' in self.plot_type:
                self.settings['clabel'] = 'FFT Amplitude'
                if self.plot_type=='FFT Y' and 'default_fftylabel' in self.settings.keys():
                    self.settings['ylabel'] = self.settings['default_fftylabel']
                elif self.plot_type=='FFT X' and 'default_fftxlabel' in self.settings.keys():
                    self.settings['xlabel'] = self.settings['default_fftxlabel']
                elif self.plot_type=='FFT X/Y':
                    if 'default_fftxlabel' in self.settings.keys():
                        self.settings['xlabel'] = self.settings['default_fftxlabel']
                    if 'default_fftylabel' in self.settings.keys():
                        self.settings['ylabel'] = self.settings['default_fftylabel']
        else:
            if self.plot_type == 'Histogram':
                self.settings['ylabel'] = 'Counts'
                self.settings['xlabel'] = self.settings['default_histlabel']
            elif self.plot_type == 'FFT':
                self.settings['ylabel'] = 'FFT Amplitude'
                self.settings['xlabel'] = self.settings['default_fftxlabel']

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
        for axis in ['top','bottom','left','right']:
            self.axes.spines[axis].set_linewidth(float(self.settings['spinewidth']))
        self.axes.tick_params(labelsize=self.settings['ticksize'], 
                              width=float(self.settings['spinewidth']), 
                              color=rcParams['axes.edgecolor'])
        if self.settings['minorticks'] == 'True':
            self.axes.minorticks_on()
        if self.settings['title'] == '<label>':
            self.axes.set_title(self.label, size=self.settings['titlesize'],wrap=True)
        else:
            self.axes.set_title(self.settings['title'], 
                                size=self.settings['titlesize'],wrap=True)
        if self.settings['colorbar'] == 'True' and len(self.get_columns()) == 3:
            self.cbar.ax.set_ylabel(self.settings['clabel'], fontsize=self.settings['labelsize'], 
                                 labelpad=10, rotation=270)
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
            # Update main plot and cbar
            self.image.norm=norm

            # # Update histogram
            if hasattr(self,'hax'):
                self.haxfill.set_data(np.linspace(self.view_settings['Minimum'], self.view_settings['Maximum'], 100),
                                      self.hax.get_xlim()[0], 0)
                if self.view_settings['Minimum']<self.hax.get_ylim()[0] or self.view_settings['Maximum']>self.hax.get_ylim()[1]:
                    self.hax.set_ylim([np.min([self.view_settings['Minimum'],np.min(self.cbar_hist_bins)]),
                                np.max([self.view_settings['Maximum'],np.max(self.cbar_hist_bins)])])

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
        cmap = cm.get_cmap(cmap_str, lut=int(self.settings['cmap levels']))
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
            if arrayname in self.data_dict.keys():
                array=self.shape_single_array(self.data_dict[arrayname])

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
        
    def apply_all_filters(self, update_color_limits=True,filter_box_index=None):
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

        self.loaded_data = dataset.copy()
        self.canvas = canvas
        self.all_parameter_names = all_parameter_names.copy()
        self.data_dict={}
        for i,name in enumerate(self.all_parameter_names):
            self.data_dict[name]=self.loaded_data[i]
        self.label = label_name
        self.dim = dimension
        self.settings['title'] = self.label

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

        x=self.data_dict[names[0]]
        y=self.data_dict[names[1]]

        if line is None and 'Z data' in self.settings.keys():
            z=self.data_dict[self.settings['Z data']]
            column_data=[x,y,z]
        else:
            column_data=[x,y]
        return column_data
    
class MixedInternalData(BaseClassData):
    # Class for combination of a single 2D dataset and various 1D datasets.
    # The type of each dataset needs to be provided by e.g. type(dataset).
    # For BaseClassData or qcodesppData, all that is then needed is the filepath.
    # For internal data, more info is needed.
    
    def __init__(self, canvas, label_name, dataset2d_type, dataset1d_type,
                 dataset2d_filepath=None, dataset1d_filepath=None,
                 dataset1d_loaded_data=None,dataset2d_loaded_data=None,
                 dataset1d_label=None,dataset2d_label=None,
                 dataset1d_all_parameter_names=None,dataset2d_all_parameter_names=None,
                 dataset1d_dim=None,dataset2d_dim=None):
        super().__init__(filepath='mixed_internal_data', canvas=canvas)

        # The following block is necessary for saving and loading.
        self.dataset2d_type = dataset2d_type
        self.dataset1d_type = dataset1d_type
        self.dataset1d_filepath = dataset1d_filepath
        self.dataset2d_filepath = dataset2d_filepath
        self.dataset1d_loaded_data = dataset1d_loaded_data
        self.dataset2d_loaded_data = dataset2d_loaded_data
        self.dataset1d_label = dataset1d_label
        self.dataset2d_label = dataset2d_label
        self.dataset1d_all_parameter_names = dataset1d_all_parameter_names
        self.dataset2d_all_parameter_names = dataset2d_all_parameter_names
        self.dataset1d_dim = dataset1d_dim
        self.dataset2d_dim = dataset2d_dim

        self.filepath = 'mixed_internal_data'
        self.canvas = canvas
        self.label = label_name
        self.dim = 'mixed'
        self.settings['title'] = self.label

        self.show_2d_data = True

        # Reload both datasets to ensure completely distinct objects.
        from qcodespp.plotting.offline.qcodespp_extension import qcodesppData

        if dataset2d_type == qcodesppData:
            self.dataset2d = qcodesppData(dataset2d_filepath,canvas,os.path.dirname(dataset2d_filepath)+'/snapshot.json',load_the_data=True)
        elif dataset2d_type == BaseClassData:
            self.dataset2d = BaseClassData(dataset2d_filepath,canvas)
        elif dataset2d_type == InternalData:
            self.dataset2d = InternalData(canvas,dataset2d_loaded_data,dataset2d_label,dataset2d_all_parameter_names,dataset2d_dim)
        
        if dataset1d_type == qcodesppData:
            self.dataset1d = qcodesppData(dataset1d_filepath,canvas,os.path.dirname(dataset1d_filepath)+'/snapshot.json',load_the_data=True)
        elif dataset1d_type == BaseClassData:
            self.dataset1d = BaseClassData(dataset1d_filepath,canvas)
        elif dataset1d_type == InternalData:
            self.dataset1d = InternalData(canvas,dataset1d_loaded_data,dataset1d_label,dataset1d_all_parameter_names,dataset1d_dim)

        self.plot_type=None
        
        self.all_parameter_names = self.dataset2d.all_parameter_names.copy()
        self.dataset2d.settings=self.settings
        self.dataset2d.axlim_settings=self.axlim_settings
        self.dataset2d.view_settings=self.view_settings

        self.settings['X data'] = self.all_parameter_names[0]
        self.settings['Y data'] = self.all_parameter_names[1]
        self.settings['xlabel'] = self.all_parameter_names[0]
        self.settings['ylabel'] = self.all_parameter_names[1]
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
        
        # if hasattr(dataset2d, 'linecuts'):
        #     self.dataset2d.linecuts=copy_linecuts(dataset2d,editor_window=editor_window)

        # if hasattr(dataset1d,'plotted_lines'):
        #     self.dataset1d.plotted_lines=copy_plotted_lines(dataset1d.plotted_lines)

        self.prepare_data_for_plot(reload_data=True,reload_from_file=True)
        self.dataset1d.init_plotted_lines()

    def prepare_data_for_plot(self, *args, **kwargs):
        self.dataset2d.prepare_data_for_plot(*args, **kwargs)
        self.dataset1d.prepare_data_for_plot(*args, **kwargs)

    def reset_view_settings(self):
        self.dataset2d.reset_view_settings()

    def add_plot(self, editor_window):
        try:
            self.dataset2d.axes=self.axes
            self.dataset2d.figure=self.figure
            self.dataset1d.axes=self.axes
            self.dataset1d.figure=self.figure

            if self.show_2d_data:
                cmap_str = self.dataset2d.view_settings['Colormap']
                if self.dataset2d.view_settings['Reverse']:
                    cmap_str += '_r'
                cmap = cm.get_cmap(cmap_str, lut=int(self.dataset2d.settings['cmap levels']))
                cmap.set_bad(self.dataset2d.settings['maskcolor'])

                norm = MidpointNormalize(vmin=self.dataset2d.view_settings['Minimum'], 
                                            vmax=self.dataset2d.view_settings['Maximum'], 
                                            midpoint=self.dataset2d.view_settings['Midpoint'])
                self.image = self.axes.pcolormesh(self.dataset2d.processed_data[0], 
                                                    self.dataset2d.processed_data[1], 
                                                    self.dataset2d.processed_data[2], 
                                                    shading=self.dataset2d.settings['shading'], 
                                                    norm=norm, cmap=cmap,
                                                    rasterized=self.dataset2d.settings['rasterized'])
                if self.dataset2d.settings['colorbar'] == 'True':
                    self.cbar = self.figure.colorbar(self.image)
                    if self.view_settings['CBarHist'] == True:
                        self.add_cbar_hist()

            # Now plot 1D data on top
            if not hasattr(self, 'sidebar1D'):
                self.sidebar1D = Sidebar1D(self.dataset1d,editor_window=editor_window)
                self.sidebar1D.running = True
                if hasattr(self.dataset1d, 'plotted_lines'):
                    for line in self.dataset1d.plotted_lines.keys():
                        self.sidebar1D.append_trace_to_table(line)
            
            if not hasattr(self.dataset1d, 'plotted_lines'):
                # Should basically never happen; user should always have created a plot before since it's 'combine _checked_ files'
                self.dataset1d.init_plotted_lines()
                self.sidebar1D.append_trace_to_table(0)

            self.sidebar1D.lims_label.setText('Fit limits')
                
            self.sidebar1D.update(clearplot=False)

            self.cursor = Cursor(self.axes, useblit=True, 
                                    color='black', linewidth=0.5)
            self.apply_plot_settings()
            self.apply_axlim_settings()
            self.apply_axscale_settings()
        except Exception as e:
            editor_window.log_error(f"Error while plotting {self.label}: {e}")

    def apply_all_filters(self, update_color_limits=True,filter_box_index=None):
        if filter_box_index ==1:
            for line in self.dataset1d.plotted_lines.keys():
                filters = self.dataset1d.plotted_lines[line]['filters']
                processed_data = self.dataset1d.plotted_lines[line]['processed_data']
                for filt in filters:
                    if filt.checkstate:
                        processed_data = self.dataset1d.apply_single_filter(processed_data, filt)
                self.dataset1d.plotted_lines[line]['processed_data'] = processed_data

        else:
            filters=self.dataset2d.filters
            processed_data = self.dataset2d.processed_data
            for filt in filters:
                if filt.checkstate:
                    processed_data = self.dataset2d.apply_single_filter(processed_data, filt)
            self.dataset2d.processed_data = processed_data
            if update_color_limits:
                self.reset_view_settings()

    def add_cbar_hist(self):
        self.hax=self.cbar.ax.inset_axes([-1.05, 0, 1, 1],picker=True)
        counts, self.cbar_hist_bins = np.histogram(self.dataset2d.processed_data[-1],bins=int(self.settings['cmap levels']),
                                                   range=(np.nanmin(self.dataset2d.processed_data[-1]), 
                                                          np.nanmax(self.dataset2d.processed_data[-1])))
        midpoints = self.cbar_hist_bins[:-1] + np.diff(self.cbar_hist_bins)/2
        self.hax.fill_between(-counts, midpoints,0,color='mediumslateblue')
        self.haxfill=self.hax.fill_betweenx(np.linspace(self.view_settings['Minimum'], self.view_settings['Maximum'], 100), 
                                                        self.hax.get_xlim()[0], 
                                                        color='blue', alpha=0.2)

        self.hax.margins(0)
        self.hax.spines[:].set_linewidth(0.5)
        self.hax.get_xaxis().set_visible(False)
        self.hax.get_yaxis().set_visible(False)