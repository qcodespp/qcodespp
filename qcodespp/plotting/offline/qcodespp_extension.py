import numpy as np
import os
import json
import copy
from qcodespp.data.data_set import load_data
from qcodespp.plotting.offline.datatypes import BaseClassData

class qcodesppData(BaseClassData):

    def __init__(self, filepath, canvas, metapath,load_the_data=False):
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
            for key,val in old_chans.items():
                self.channels[key] = val
            del old_chans

        if load_the_data:               # Should only need to happen for (Mixed)InternalData.
            self.prepare_dataset()       # Otherwise, data is loaded when first plotted.

    def prepare_dataset(self):
        # Loads the data from file, and prepares a data_dict. This is significantly easier than in the BaseClassData,
        # since qcodespp data is already in a dictionary. We can also use the metadata to easily work out if the data
        # is 1D or 2D purely based on how many independent parameters there are.
        if '.dat' in self.filepath:
            self.loaded_data=load_data(os.path.dirname(self.filepath), remove_incomplete=False)
        else:
            self.loaded_data=load_data(self.filepath, remove_incomplete=False)

        if hasattr(self, 'extra_cols'):
        # Processed data that has been added to the data_dict. Need to preserve it!
            old_dict = copy.deepcopy(self.data_dict)

        #self.data_dict = self.loaded_data.arrays.copy()

        self.data_dict = self.remove_string_arrays(self.loaded_data.arrays.copy())

        if hasattr(self, 'extra_cols'):
            # Add the extra columns to the data_dict
            for key,val in old_dict.items():
                self.data_dict[key] = val
            del old_dict

        # Identify the independent and dependent parameters, put various labels in the right place
        self.identify_variables()

        # Assign dimension based on number of independent parameters
        if len(self.independent_parameter_names) > 1:
            self.dim = 3
        else:
            self.dim = 2

        # Check if the data is finished, and if not, remove NaNs from the _end_ of the data.
        if not self.loaded_data.fraction_complete()==1:
            set_x = self.data_dict[self.all_parameter_names[0]]
            non_nan_len = len(np.unique(set_x[~np.isnan(set_x)]))-1
            if non_nan_len > 0:
                for arrayname, array in self.data_dict.items():
                    if array.shape[0] > non_nan_len:
                        self.data_dict[arrayname] = array[:non_nan_len]

        # There was a time where NaNs could occur in the middle of the data. 
        # This should never happen anymore, but for old datasets,
        # we can deal with them here.
        if self.dim == 3:
            for arrayname, array in self.data_dict.items():
                if np.isnan(array).any():
                    for i,j in np.argwhere(np.isnan(array)):
                        if i > 0:
                            array[i,j] = array[i-1,j]
                        else:
                            array[i,j] = array[i+1,j]

        # self.dims is the shape of each data array. It's not necessarily true that all arrays will have the same shape,
        # but if self.identify_variables() worked, then the Y data array will have the correct shape for the first set of
        # variables to be plotted for both 1D and 2D data. self.dims gets updated every time the user chooses a new 
        # (set of) variable(s) to plot.
        self.dims = np.shape(self.data_dict[self.settings['Y data']])

    def remove_string_arrays(self, data_dict):
        """
        Removes arrays that have str as data_type, since these cannot be plotted.
        """
        for key in list(data_dict.keys()):
            if hasattr(data_dict[key],'data_type') and data_dict[key].data_type == str:
                del data_dict[key]
        return data_dict

    def load_and_reshape_data(self, reload_data=False,reload_from_file=True,linefrompopup=None):
        if self.loaded_data is None or reload_data and reload_from_file:
            self.prepare_dataset()

        # Get the required X, Y (and Z) data from the data_dict.
        column_data = self.get_column_data(line=linefrompopup)

        if isinstance(column_data, Exception):
            self.columns_bad=column_data
            return column_data
        
        else:
            self.columns_bad=False
            columns = [i for i in range(self.dim)]
            if self.dims[0] > 1: # If two or more sweeps are finished
                
                if self.dim == 2: # if data is 1D
                    self.raw_data = column_data#[column_data[:,x] for x in range(column_data.shape[1])]            

                else: # data is 2D. We make sure X and Y are ascending so that the filters can behave predictably.
                    self.raw_data = column_data
                    if self.raw_data[0][0,0] > self.raw_data[0][0,1]: 
                        self.raw_data = [np.fliplr(array) for array in self.raw_data]
                        self.lrflipped=True
                    if self.raw_data[1][0,0] > self.raw_data[1][1,0]:
                        self.raw_data = [np.flipud(array) for array in self.raw_data]
                        self.udflipped=True

            elif self.dims[0] == 1: # if first two sweeps are not finished -> duplicate data of first sweep to enable 3D plotting
                column_data = np.column_stack((column_data[0].flatten(),
                                                 column_data[1].flatten(),
                                                 column_data[2].flatten()))
                self.raw_data = [np.tile(column_data[:self.dims[1],x], (2,1)) for x in range(column_data.shape[1])]    

                self.raw_data[columns[0]][0,:] = columns[0]-1
                self.raw_data[columns[0]][1,:] = columns[0]+1
            else:
                self.raw_data = None
                
            self.settings['columns'] = ','.join([str(i) for i in columns]) # Legacy. Don't want to yet remove for fear of breaking. Will one day.

    def get_column_data(self, line=None):
        if line is not None:
            Xdataname = self.plotted_lines[line]['X data']
            Ydataname = self.plotted_lines[line]['Y data']
        else:
            Xdataname = self.settings['X data']
            Ydataname = self.settings['Y data']

        #self.fix_x_dimension()
        # If user has selected X data, use that, otherwise use the first independent parameter
        # X data is the same no matter the data dimension
        xdata = self.data_dict[Xdataname]

        try:
            self.settings['default_xlabel'] = f'{self.channels[Xdataname]['label']} ({self.channels[Xdataname]['unit']})'
        except KeyError:
            self.settings['default_xlabel'] = Xdataname
        
        if len(self.independent_parameter_names) == 1: # data is 1D
            ydata = self.data_dict[Ydataname]
            try:
                self.settings['default_ylabel'] = f'{self.channels[Ydataname]['label']} ({self.channels[Ydataname]['unit']})'
            except KeyError:
                self.settings['default_ylabel'] = Ydataname
            
            if len(xdata)==len(ydata):
                column_data = [xdata, ydata]
            else:
                return ValueError(f'Cannot plot {Ydataname} vs {Xdataname}:\n'
                                  f"number of data points\n"
                                  f"{len(xdata)} and {len(ydata)}\n"
                                  "do not match.")

                # This can happen if the user has run statistics, and is trying to plot the result; if they change only
                # the X data, the length of the data won't match the Y data until they then select the correct thing.
                # So, just plot nothing until the user selects something sensible.

            self.settings['default_histlabel'] = self.settings['default_ylabel']
            self.settings['default_fftxlabel'] = f'1/{self.settings['default_xlabel']}'

        elif len(self.independent_parameter_names) > 1: # data is 2D
            ydata = self.data_dict[Ydataname]
            self.settings['default_ylabel'] = (f'{self.channels[self.settings['Y data']]['label']} '
                                        f'({self.channels[self.settings['Y data']]['unit']})')
            Zdataname = self.settings['Z data']
            zdata = self.data_dict[Zdataname]
            self.settings['default_clabel'] = (f'{self.channels[self.settings['Z data']]['label']} '
                                        f'({self.channels[self.settings['Z data']]['unit']})')

            column_data = [xdata, ydata, zdata]
            # Update dims, which may change if e.g. up sweeps have different dimension to down sweeps.
            self.dims = zdata.shape

            # Check two things: if any of the arrays are the zero-th indep param from qcodespp data, the shape will be
            # 1D, so we need to reshape them to 2D.
            # Secondly, if any of the dimensions don't match, we just return an error. This can happen if the user is
            # underway with changing multiple columns, and have not yet selected all the correct data types.
            arraynames=[Xdataname, Ydataname, Zdataname]
            for i,name in enumerate(arraynames):
                if name == self.all_parameter_names[0]:
                    column_data[i] = np.repeat(column_data[i], self.dims[1]).reshape(self.dims)
                if column_data[i].shape != self.dims:
                    return ValueError("Cannot plot data: shapes of\n"
                                     f"{column_data[0].shape}, {column_data[1].shape}, {column_data[2].shape}\n"
                                     f"do not match.")

            self.settings['default_histlabel'] = self.settings['default_clabel']
            self.settings['default_fftxlabel'] = f'1/{self.settings['default_xlabel']}'
            self.settings['default_fftylabel'] = f'1/{self.settings['default_ylabel']}'

        else:
            return ValueError("No data found in this dataset.")

        return column_data

    def identify_variables(self):
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
        
    def file_finished(self):
        if not self.loaded_data.fraction_complete()==1:
            return False
        return True


# class qcodesppData(BaseClassData):

#     def __init__(self, filepath, canvas, metapath):
#         super().__init__(filepath, canvas)
#         # Open meta file and set label
#         with open(metapath) as f:
#             self.meta = json.load(f)
#         dirname = os.path.basename(os.path.dirname(metapath))

#         self.label = f'{dirname.split('#')[1]}'
#         self.settings["title"] = '#'+self.label
#         self.DEFAULT_PLOT_SETTINGS['title']= '#'+self.label

#         self.independent_parameter_names = []
#         self.dependent_parameter_names = []
#         self.all_parameter_names = []

#         if hasattr(self, 'extra_cols'):
#             old_chans = copy.deepcopy(self.channels)
        
#         self.channels = self.meta['arrays']

#         if hasattr(self, 'extra_cols'):
#             for col in self.extra_cols:
#                 if col in old_chans.keys():
#                     self.channels[col] = old_chans[col]
#             del old_chans

#     def load_from_file(self):
#         if '.dat' in self.filepath:
#             self.loaded_data=load_data(os.path.dirname(self.filepath))
#         else:
#             self.loaded_data=load_data(self.filepath)

#         if hasattr(self, 'extra_cols'):
#         # Processed data that has been added to the data_dict. Need to preserve it!
#             old_dict = copy.deepcopy(self.data_dict)

#         self.data_dict = self.loaded_data.arrays.copy()

#         if hasattr(self, 'extra_cols'):
#             # Add the extra columns to the data_dict
#             for col in self.extra_cols:
#                 if col in old_dict.keys():
#                     self.data_dict[col] = old_dict[col]
#             del old_dict

#     def load_and_reshape_data(self, reload_data=False,reload_from_file=True,linefrompopup=None):
#         if self.loaded_data is None or reload_data and reload_from_file:
#             self.load_from_file()

#             self.prepare_dataset()

#             if len(self.independent_parameter_names) > 1:
#                 self.dim = 3
#             else:
#                 self.dim = 2

#             self.fix_x_dimension()

#         column_data = self.get_column_data(line=linefrompopup)

#         if column_data.ndim == 1: # if empty array or single-row array
#             self.raw_data = None
#         else:
#             columns = [i for i in range(self.dim)]
#             if self.dims[0] > 1: # If two or more sweeps are finished
                
#                 if self.dim == 2: # if data is 1D
#                     self.raw_data = [column_data[:,x] for x in range(column_data.shape[1])]            
#                     columns = columns[:2]
#                 else: 
#                     # flip if first column is sorted from high to low 
#                     if column_data[:,columns[0]][-1] < column_data[:,columns[0]][0]: 
#                         column_data = np.flipud(column_data)
#                         self.udflipped=True
#                     self.raw_data = [np.reshape(column_data[:,x], self.dims) 
#                                      for x in range(column_data.shape[1])]
#                     # flip if second column is sorted from high to low
#                     if self.raw_data[1][0,0] > self.raw_data[1][0,1]: 
#                         self.raw_data = [np.fliplr(self.raw_data[x]) for x in range(column_data.shape[1])]
#                         self.lrflipped=True
                        
#             elif self.dims[0] == 1: # if first two sweeps are not finished -> duplicate data of first sweep to enable 3D plotting
#                 self.raw_data = [np.tile(column_data[:self.dims[1],x], (2,1)) for x in range(column_data.shape[1])]    

#                 self.raw_data[columns[0]][0,:] = columns[0]-1
#                 self.raw_data[columns[0]][1,:] = columns[0]+1
#             else:
#                 self.raw_data = None
                
#             self.settings['columns'] = ','.join([str(i) for i in columns])

#     def fix_x_dimension(self):
#         self.dims = np.shape(self.data_dict[self.independent_parameter_names[self.dim-2]])

#         if self.dim==3 and len(self.data_dict[self.all_parameter_names[0]]) < self.dims[0]*self.dims[1]:
#             self.data_dict[self.all_parameter_names[0]] = np.repeat(self.data_dict[self.all_parameter_names[0]], self.dims[1])

#     def isFinished(self):
#         self.set_x = self.data_dict[self.all_parameter_names[0]]
#         self.set_x = np.unique(self.set_x[~np.isnan(self.set_x)])
#         return len(self.set_x) == self.dims[0]
    
#     def finished_dimensions(self):
#         self.dims = [len(self.set_x)-1, self.dims[1]]
        
#     def get_column_data(self, line=None):
#         if line is not None:
#             Xdataname = self.plotted_lines[line]['X data']
#             Ydataname = self.plotted_lines[line]['Y data']
#         else:
#             Xdataname = self.settings['X data']
#             Ydataname = self.settings['Y data']

#         self.fix_x_dimension()
#         # If user has selected X data, use that, otherwise use the first independent parameter
#         # X data is the same no matter the data dimension
#         xdata = self.data_dict[Xdataname]
#         try:
#             self.settings['xlabel'] = f'{self.channels[Xdataname]['label']} ({self.channels[Xdataname]['unit']})'
#         except KeyError:
#             self.settings['xlabel'] = Xdataname
        
#         if len(self.independent_parameter_names) == 1: # data is 1D
#             ydata = self.data_dict[Ydataname]
#             try:
#                 self.settings['ylabel'] = f'{self.channels[Ydataname]['label']} ({self.channels[Ydataname]['unit']})'
#             except KeyError:
#                 self.settings['ylabel'] = Ydataname
            
#             if not self.isFinished():
#                 # Delete unfinished rows to enable plotting
#                 xdata = xdata[:len(self.set_x)-1]
#                 ydata = ydata[:len(self.set_x)-1]
#             if len(xdata)==len(ydata):
#                 column_data = np.column_stack((xdata, ydata))
#             else:
#                 column_data = np.zeros((2,2))
#                 # This can happen if the user has run statistics, and is trying to plot the result; if they change only
#                 # the X data, the length of the data won't match the Y data until they then select the correct thing.
#                 # So, just plot nothing until the user selects something sensible.

#             self.settings['default_xlabel'] = self.settings['xlabel']
#             self.settings['default_ylabel'] = self.settings['ylabel']
#             self.settings['default_histlabel'] = self.settings['default_ylabel']
#             self.settings['default_fftxlabel'] = f'1/{self.settings['default_xlabel']}'

#         elif len(self.independent_parameter_names) > 1: # data is 2D
#             xdata = self.data_dict[Xdataname].flatten()
#             ydata = self.data_dict[self.settings['Y data']].flatten()
#             self.settings['ylabel'] = (f'{self.channels[self.settings['Y data']]['label']} '
#                                         f'({self.channels[self.settings['Y data']]['unit']})')
#             zdata = self.data_dict[self.settings['Z data']].flatten()
#             self.settings['clabel'] = (f'{self.channels[self.settings['Z data']]['label']} '
#                                         f'({self.channels[self.settings['Z data']]['unit']})')

#             lengths = [len(xdata), len(ydata), len(zdata)]
#             maxlen = max(lengths)
#             if len(xdata) < maxlen:
#                 xdata = np.pad(xdata, (0, maxlen - len(xdata)), 'constant', constant_values=np.nan)
#             if len(ydata) < maxlen:
#                 ydata = np.pad(ydata, (0, maxlen - len(ydata)), 'constant', constant_values=np.nan)
#             if len(zdata) < maxlen:
#                 zdata = np.pad(zdata, (0, maxlen - len(zdata)), 'constant', constant_values=np.nan)

#             column_data = np.column_stack((xdata,
#                                          ydata,
#                                         zdata
#                                         ))

#             self.settings['default_xlabel'] = self.settings['xlabel']
#             self.settings['default_ylabel'] = self.settings['ylabel']
#             self.settings['default_clabel'] = self.settings['clabel']
#             self.settings['default_histlabel'] = self.settings['default_clabel']
#             self.settings['default_fftxlabel'] = f'1/{self.settings['default_xlabel']}'
#             self.settings['default_fftylabel'] = f'1/{self.settings['default_ylabel']}'

#             # # Delete unfinished rows to enable plotting
#             if not self.isFinished():
#                 self.finished_dimensions()

#                 column_data = column_data[~np.isnan(column_data).any(axis=1)]
#                 column_data = column_data[~np.isnan(column_data[:,0])]
#                 column_data = column_data[:self.dims[0]*self.dims[1]]

#         else:
#             return np.empty((1,1))

#         return column_data
    
#     def prepare_dataset(self):
#         for chan in self.channels.keys():
#             if self.channels[chan]["array_id"] not in self.all_parameter_names:
#                 if self.channels[chan]["is_setpoint"] and self.channels[chan]["array_id"] in list(self.data_dict.keys()):
#                     self.independent_parameter_names.append(self.channels[chan]["array_id"])
#                 elif self.channels[chan]["array_id"] in list(self.data_dict.keys()):
#                     self.dependent_parameter_names.append(self.channels[chan]["array_id"])
#         self.all_parameter_names = self.independent_parameter_names + self.dependent_parameter_names
        
#         # Default to conductance as dependent variable if present.
#         defnamefound=False
#         for paramname in ['onductance','esistance', 'urr', 'olt']:
#             for name in self.dependent_parameter_names:
#                 if not defnamefound and paramname in name:
#                     self.index_dependent_parameter = self.dependent_parameter_names.index(name)
#                     defnamefound=True
#         if not defnamefound: 
#             self.index_dependent_parameter = 0

#         if 'X data' not in self.settings.keys() or self.settings['X data'] == '':
#             self.settings['X data'] = self.independent_parameter_names[0]

#         if len(self.independent_parameter_names) > 1:
#             if 'Y data' not in self.settings.keys() or self.settings['Y data'] == '':
#                 self.settings['Y data'] = self.independent_parameter_names[1]
#             if 'Z data' not in self.settings.keys() or self.settings['Z data'] == '':
#                 self.settings['Z data'] = self.dependent_parameter_names[self.index_dependent_parameter]

#         else:
#             if 'Y data' not in self.settings.keys() or self.settings['Y data'] == '':
#                 self.settings['Y data'] = self.dependent_parameter_names[self.index_dependent_parameter]

#             self.settings.pop('Z data', None)
            
#         self.settings_menu_options = {'X data': self.all_parameter_names,
#                                       'Y data': self.all_parameter_names,
#                                       'Z data': self.all_parameter_names}
        
#         negparamnames=[f'-{name}' for name in self.all_parameter_names]
#         allnames=np.hstack((self.all_parameter_names,negparamnames))
#         self.filter_menu_options = {'Multiply': allnames,
#                                     'Divide': allnames,
#                                     'Add/Subtract': allnames}
        
#     def init_plotted_lines(self):
#         self.plotted_lines = {0: {'checkstate': 2,
#                         'X data': self.independent_parameter_names[0],
#                         'Y data': self.dependent_parameter_names[1],
#                         'Bins': 100,
#                         'Xerr': 0,
#                         'Yerr': 0,
#                         'raw_data': self.raw_data,
#                         'processed_data': self.processed_data,
#                         'linecolor': (0.1, 0.5, 0.8, 1),
#                         'linewidth': 1.5,
#                         'linestyle': '-',
#                         'filters': []}}
        

#     def apply_single_filter(self, processed_data, filt):
#         if filt.name in ['Multiply', 'Divide', 'Add/Subtract']:
#             if filt.settings[0][0]=='-':
#                 arrayname=filt.settings[0][1:]
#                 setting2='-'
#             else:
#                 arrayname=filt.settings[0]
#                 setting2='+'
#             if arrayname in self.all_parameter_names:
#                 if self.dim==3:
#                     array=self.data_dict[arrayname][:self.dims[0]][:self.dims[1]]
#                 else:
#                     array=self.data_dict[arrayname][:self.dims[0]]
#                 if hasattr(self,'udflipped'):
#                     array=np.flipud(array)
#                 if hasattr(self,'lrflipped'):
#                     array=np.fliplr(array)
#             else:
#                 array=None
#             processed_data = filt.function(processed_data,
#                                             filt.method,
#                                             filt.settings[0], 
#                                             setting2,
#                                             array)
#         else:
#             processed_data = filt.function(processed_data,
#                                             filt.method,
#                                             filt.settings[0],
#                                             filt.settings[1])
            
#         return processed_data
    
#     def add_array_to_data_dict(self, array, name):
#         self.data_dict[name] = array
#         self.all_parameter_names=list(self.data_dict.keys())
#         self.dependent_parameter_names.append(name)

#         for label in ['X data', 'Y data', 'Z data']:
#             self.settings_menu_options[label]= self.all_parameter_names
#         negparamnames=[f'-{name}' for name in self.all_parameter_names]
#         allnames=np.hstack((self.all_parameter_names,negparamnames))
#         for filtname in ['Multiply', 'Divide', 'Add/Subtract']:
#             self.filter_menu_options[filtname]=allnames

#         self.channels[name] = {'label': name,
#                                         'unit': '',
#                                         'array_id': name,
#                                         'is_setpoint': False}

#         if not hasattr(self, 'extra_cols'):
#             self.extra_cols = []
#         self.extra_cols.append(name)
        
#     def filttocol(self, axis):
#         axes={'X': 0, 'Y': 1, 'Z': 2}
#         if hasattr(self, 'sidebar1D'):
#             current_1D_row = self.sidebar1D.trace_table.currentRow()
#             current_line = int(self.sidebar1D.trace_table.item(current_1D_row,0).text())
#             data_to_send = self.plotted_lines[current_line]['processed_data'][axes[axis]]
#             paramname = self.plotted_lines[current_line][f'{axis} data']

#         else:
#             data_to_send = self.processed_data[axes[axis]]
#             paramname = self.settings[f'{axis} data']

#         colname= f'Filtered: {paramname}'

#         self.add_array_to_data_dict(data_to_send, colname)

#         self.channels[colname] = {'label': colname,
#                                         'unit': self.channels[paramname]['unit'],
#                                         'array_id': colname,
#                                         'is_setpoint': False}

