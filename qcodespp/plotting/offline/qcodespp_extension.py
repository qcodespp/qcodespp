import numpy as np
import os
import json
import copy
from qcodespp.data.data_set import load_data
from qcodespp.plotting.offline.datatypes import BaseClassData

class qcodesppData(BaseClassData):

    def __init__(self, filepath, canvas, metapath):
        super().__init__(filepath, canvas)
        # Open meta file and set label
        with open(metapath) as f:
            self.meta = json.load(f)
        dirname = os.path.basename(os.path.dirname(metapath))

        self.label = f'{dirname.split('#')[1]}'
        self.settings["title"] = '#'+self.label
        self.DEFAULT_PLOT_SETTINGS['title']= '#'+self.label

        self.independent_parameter_names = []
        self.dependent_parameter_names = []
        self.all_parameter_names = []

        if hasattr(self, 'extra_cols'):
            old_chans = copy.deepcopy(self.channels)
        
        self.channels = self.meta['arrays']

        if hasattr(self, 'extra_cols'):
            for col in self.extra_cols:
                if col in old_chans.keys():
                    self.channels[col] = old_chans[col]
            del old_chans

    def load_from_file(self):
        if '.dat' in self.filepath:
            self.loaded_data=load_data(os.path.dirname(self.filepath))
        else:
            self.loaded_data=load_data(self.filepath)

        if hasattr(self, 'extra_cols'):
        # Processed data that has been added to the data_dict. Need to preserve it!
            old_dict = copy.deepcopy(self.data_dict)

        self.data_dict = self.loaded_data.arrays.copy()

        if hasattr(self, 'extra_cols'):
            # Add the extra columns to the data_dict
            for col in self.extra_cols:
                if col in old_dict.keys():
                    self.data_dict[col] = old_dict[col]
            del old_dict

    def load_and_reshape_data(self, reload_data=False,reload_from_file=True,linefrompopup=None):
        if self.loaded_data is None or reload_data and reload_from_file:
            self.load_from_file()

            self.prepare_dataset()

            if len(self.independent_parameter_names) > 1:
                self.dim = 3
            else:
                self.dim = 2

            self.fix_x_dimension()

        column_data = self.get_column_data(line=linefrompopup)
        if column_data.ndim == 1: # if empty array or single-row array
            self.raw_data = None
        else:
            # # Determine the number of unique values in the first column to determine the shape of the data
            columns = self.get_columns()
            data_shape = self.dims

            if data_shape[0] > 1: # If two or more sweeps are finished
                
                # Determine if file is 1D or 2D by checking if first two values in first column are repeated
                if len(data_shape) == 1:
                    self.raw_data = [column_data[:,x] for x in range(column_data.shape[1])]            
                    columns = columns[:2]
                else: 
                    # flip if first column is sorted from high to low 
                    if column_data[:,columns[0]][-1] < column_data[:,columns[0]][0]: 
                        column_data = np.flipud(column_data)
                        self.udflipped=True
                    self.raw_data = [np.reshape(column_data[:,x], data_shape) 
                                     for x in range(column_data.shape[1])]
                    # flip if second column is sorted from high to low
                    if self.raw_data[1][0,0] > self.raw_data[1][0,1]: 
                        self.raw_data = [np.fliplr(self.raw_data[x]) for x in range(column_data.shape[1])]
                        self.lrflipped=True
                        
            elif data_shape[0] == 1: # if first two sweeps are not finished -> duplicate data of first sweep to enable 3D plotting
                self.raw_data = [np.tile(column_data[:data_shape[1],x], (2,1)) for x in range(column_data.shape[1])]    

                self.raw_data[columns[0]][0,:] = columns[0]-1
                self.raw_data[columns[0]][1,:] = columns[0]+1
            else:
                self.raw_data = None
                
            self.settings['columns'] = ','.join([str(i) for i in columns])

    def fix_x_dimension(self):
        self.dims = np.shape(self.data_dict[self.independent_parameter_names[self.dim-2]])

        if self.dim==3 and len(self.data_dict[self.all_parameter_names[0]]) < self.dims[0]*self.dims[1]:
            self.data_dict[self.all_parameter_names[0]] = np.repeat(self.data_dict[self.all_parameter_names[0]], self.dims[1])

    def isFinished(self):
        self.set_x = self.data_dict[self.all_parameter_names[0]]
        self.set_x = np.unique(self.set_x[~np.isnan(self.set_x)])
        return len(self.set_x) == self.dims[0]
    
    def finished_dimensions(self):
        self.dims = [len(self.set_x)-1, self.dims[1]]
        
    def get_column_data(self, line=None):
        if line is not None:
            Xdataname = self.plotted_lines[line]['X data']
            Ydataname = self.plotted_lines[line]['Y data']
        else:
            Xdataname = self.settings['X data']
            Ydataname = self.settings['Y data']

        self.fix_x_dimension()
        # If user has selected X data, use that, otherwise use the first independent parameter
        # X data is the same no matter the data dimension
        xdata = self.data_dict[Xdataname]
        try:
            self.settings['xlabel'] = f'{self.channels[Xdataname]['label']} ({self.channels[Xdataname]['unit']})'
        except KeyError:
            self.settings['xlabel'] = Xdataname
        
        if len(self.independent_parameter_names) == 1: # data is 1D
            ydata = self.data_dict[Ydataname]
            try:
                self.settings['ylabel'] = f'{self.channels[Ydataname]['label']} ({self.channels[Ydataname]['unit']})'
            except KeyError:
                self.settings['ylabel'] = Ydataname
            
            if not self.isFinished():
                # Delete unfinished rows to enable plotting
                xdata = xdata[:len(self.set_x)-1]
                ydata = ydata[:len(self.set_x)-1]
            if len(xdata)==len(ydata):
                column_data = np.column_stack((xdata, ydata))
            else:
                column_data = np.zeros((2,2))
                # This can happen if the user has run statistics, and is trying to plot the result; if they change only
                # the X data, the length of the data won't match the Y data until they then select the correct thing.
                # So, just plot nothing until the user selects something sensible.

            self.settings['default_xlabel'] = self.settings['xlabel']
            self.settings['default_ylabel'] = self.settings['ylabel']
            self.settings['default_histlabel'] = self.settings['default_ylabel']
            self.settings['default_fftxlabel'] = f'1/{self.settings['default_xlabel']}'

        elif len(self.independent_parameter_names) > 1: # data is 2D
            xdata = self.data_dict[Xdataname].flatten()
            ydata = self.data_dict[self.settings['Y data']].flatten()
            self.settings['ylabel'] = (f'{self.channels[self.settings['Y data']]['label']} '
                                        f'({self.channels[self.settings['Y data']]['unit']})')
            zdata = self.data_dict[self.settings['Z data']].flatten()
            self.settings['clabel'] = (f'{self.channels[self.settings['Z data']]['label']} '
                                        f'({self.channels[self.settings['Z data']]['unit']})')

            lengths = [len(xdata), len(ydata), len(zdata)]
            maxlen = max(lengths)
            if len(xdata) < maxlen:
                xdata = np.pad(xdata, (0, maxlen - len(xdata)), 'constant', constant_values=np.nan)
            if len(ydata) < maxlen:
                ydata = np.pad(ydata, (0, maxlen - len(ydata)), 'constant', constant_values=np.nan)
            if len(zdata) < maxlen:
                zdata = np.pad(zdata, (0, maxlen - len(zdata)), 'constant', constant_values=np.nan)

            column_data = np.column_stack((xdata,
                                         ydata,
                                        zdata
                                        ))

            self.settings['default_xlabel'] = self.settings['xlabel']
            self.settings['default_ylabel'] = self.settings['ylabel']
            self.settings['default_clabel'] = self.settings['clabel']
            self.settings['default_histlabel'] = self.settings['default_clabel']
            self.settings['default_fftxlabel'] = f'1/{self.settings['default_xlabel']}'
            self.settings['default_fftylabel'] = f'1/{self.settings['default_ylabel']}'

            # # Delete unfinished rows to enable plotting
            if not self.isFinished():
                self.finished_dimensions()

                column_data = column_data[~np.isnan(column_data).any(axis=1)]
                column_data = column_data[~np.isnan(column_data[:,0])]
                column_data = column_data[:self.dims[0]*self.dims[1]]

        else:
            return np.empty((1,1))
          
        self.measured_data_points = column_data.shape[0]

        return column_data
    
    def prepare_dataset(self):
        for chan in self.channels.keys():
            if self.channels[chan]["array_id"] not in self.all_parameter_names:
                if self.channels[chan]["is_setpoint"] and self.channels[chan]["array_id"] in list(self.data_dict.keys()):
                    self.independent_parameter_names.append(self.channels[chan]["array_id"])
                elif self.channels[chan]["array_id"] in list(self.data_dict.keys()):
                    self.dependent_parameter_names.append(self.channels[chan]["array_id"])
        self.all_parameter_names = self.independent_parameter_names + self.dependent_parameter_names
        
        # Default to conductance as dependent variable if present.
        defnamefound=False
        for paramname in ['onductance','esistance', 'urr', 'olt']:
            for name in self.dependent_parameter_names:
                if not defnamefound and paramname in name:
                    self.index_dependent_parameter = self.dependent_parameter_names.index(name)
                    defnamefound=True
        if not defnamefound: 
            self.index_dependent_parameter = 0

        if 'X data' not in self.settings.keys() or self.settings['X data'] == '':
            self.settings['X data'] = self.independent_parameter_names[0]

        if len(self.independent_parameter_names) > 1:
            if 'Y data' not in self.settings.keys() or self.settings['Y data'] == '':
                self.settings['Y data'] = self.independent_parameter_names[1]
            if 'Z data' not in self.settings.keys() or self.settings['Z data'] == '':
                self.settings['Z data'] = self.dependent_parameter_names[self.index_dependent_parameter]

        else:
            if 'Y data' not in self.settings.keys() or self.settings['Y data'] == '':
                self.settings['Y data'] = self.dependent_parameter_names[self.index_dependent_parameter]

            self.settings.pop('Z data', None)
            
        self.settings_menu_options = {'X data': self.all_parameter_names,
                                      'Y data': self.all_parameter_names,
                                      'Z data': self.all_parameter_names}
        
        negparamnames=[f'-{name}' for name in self.all_parameter_names]
        allnames=np.hstack((self.all_parameter_names,negparamnames))
        self.filter_menu_options = {'Multiply': allnames,
                                    'Divide': allnames,
                                    'Add/Subtract': allnames}
        
    def init_plotted_lines(self):
        self.plotted_lines = {0: {'checkstate': 2,
                        'X data': self.independent_parameter_names[0],
                        'Y data': self.dependent_parameter_names[1],
                        'Bins': 100,
                        'Xerr': 0,
                        'Yerr': 0,
                        'raw_data': self.raw_data,
                        'processed_data': self.processed_data,
                        'linecolor': (0.1, 0.5, 0.8, 1),
                        'linewidth': 1.5,
                        'linestyle': '-',
                        'filters': []}}
        

    def apply_single_filter(self, processed_data, filt):
        if filt.name in ['Multiply', 'Divide', 'Add/Subtract']:
            if filt.settings[0][0]=='-':
                arrayname=filt.settings[0][1:]
                setting2='-'
            else:
                arrayname=filt.settings[0]
                setting2='+'
            if arrayname in self.all_parameter_names:
                if self.dim==3:
                    array=self.data_dict[arrayname][:self.dims[0]][:self.dims[1]]
                else:
                    array=self.data_dict[arrayname][:self.dims[0]]
                if hasattr(self,'udflipped'):
                    array=np.flipud(array)
                if hasattr(self,'lrflipped'):
                    array=np.fliplr(array)
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
    
    def add_array_to_data_dict(self, array, name):
        self.data_dict[name] = array
        self.all_parameter_names=list(self.data_dict.keys())
        self.dependent_parameter_names.append(name)

        for label in ['X data', 'Y data', 'Z data']:
            self.settings_menu_options[label]= self.all_parameter_names
        negparamnames=[f'-{name}' for name in self.all_parameter_names]
        allnames=np.hstack((self.all_parameter_names,negparamnames))
        for filtname in ['Multiply', 'Divide', 'Add/Subtract']:
            self.filter_menu_options[filtname]=allnames

        self.channels[name] = {'label': name,
                                        'unit': '',
                                        'array_id': name,
                                        'is_setpoint': False}

        if not hasattr(self, 'extra_cols'):
            self.extra_cols = []
        self.extra_cols.append(name)
        
    def filttocol(self, axis):
        axes={'X': 0, 'Y': 1, 'Z': 2}
        if hasattr(self, 'sidebar1D'):
            current_1D_row = self.sidebar1D.trace_table.currentRow()
            current_line = int(self.sidebar1D.trace_table.item(current_1D_row,0).text())
            data_to_send = self.plotted_lines[current_line]['processed_data'][axes[axis]]
            paramname = self.plotted_lines[current_line][f'{axis} data']

        else:
            data_to_send = self.processed_data[axes[axis]]
            paramname = self.settings[f'{axis} data']

        colname= f'Filtered: {paramname}'

        self.add_array_to_data_dict(data_to_send, colname)

        self.channels[colname] = {'label': colname,
                                        'unit': self.channels[paramname]['unit'],
                                        'array_id': colname,
                                        'is_setpoint': False}

