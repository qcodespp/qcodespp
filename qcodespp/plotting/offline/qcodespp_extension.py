import numpy as np
import os
import json
import copy
from qcodespp.data.data_set import load_data
from qcodespp.plotting.offline.datatypes import BaseClassData

class qcodesppData(BaseClassData):

    def __init__(self, filepath, canvas, metapath, load_the_data=True):
        super().__init__(filepath, canvas)
        # Open meta file and set label
        self.filepath = filepath
        with open(metapath) as f:
            self.meta = json.load(f)
        dirname = os.path.basename(os.path.dirname(metapath))
        self.label = f'{dirname.split('#')[1]}'

        #self.dataset_id = "#" + self.dataset.location.split("#", 1)[1].split("_", 1)[0]
        self.dataset_id = "#" + dirname.split("#", 1)[1].split("_", 1)[0]
        self.settings["title"] = '#'+self.label#[:120]#self.dataset_id
        self.DEFAULT_PLOT_SETTINGS['title']= '#'+self.label#[:120]#self.dataset_id

        self.plot_type = None
        self.raw_data = None
        self.nans_removed = False

        # "Channels" is the meta info about the data arrays. Contains the label, unit and whether its a setpoint.
        if hasattr(self, 'extra_cols'):
            # Then we are loading from a saved session, and we need to preserve the extra columns that were generated
            old_chans = copy.deepcopy(self.channels)
        self.channels = self.meta['arrays']
        if hasattr(self, 'extra_cols'):
            for col in self.extra_cols:
                if col in old_chans.keys():
                    self.channels[col] = old_chans[col]
            del old_chans

        # Load the data itself. Will not be loaded if loading/linking from a folder.
        if load_the_data:
            self.load_data_from_file()
        else:
            self.data_loaded=False
            self.dataset=None

    def load_data_from_file(self):
        if '.dat' in self.filepath:
            self.dataset=load_data(os.path.dirname(self.filepath))
        else:
            self.dataset=load_data(self.filepath)

        if hasattr(self, 'extra_cols'):
        # Processed data that has been added to the data_dict. Need to preserve it!
            old_dict = copy.deepcopy(self.data_dict)

        self.data_dict = self.dataset.arrays.copy()

        if hasattr(self, 'extra_cols'):
            # Add the extra columns to the data_dict
            for col in self.extra_cols:
                if col in old_dict.keys():
                    self.data_dict[col] = old_dict[col]
            del old_dict

        self.prepare_dataset()

        self.data_loaded=True

    def prepare_dataset(self):
        # Run after loading data from file to populate various attributes, find data shape and massage data ready for IG plotting.

        # First, use metadata to identify independent and dependent parameters and populate all the names
        self.independent_parameter_names = [self.channels[chan]["array_id"] for chan in self.channels.keys() 
                                            if self.channels[chan]["is_setpoint"]
                                            and self.channels[chan]["array_id"] in list(self.data_dict.keys())]
        self.dependent_parameter_names = [self.channels[chan]["array_id"] for chan in self.channels.keys() 
                                            if not self.channels[chan]["is_setpoint"]
                                            and self.channels[chan]["array_id"] in list(self.data_dict.keys())]
        self.all_parameter_names = self.independent_parameter_names + self.dependent_parameter_names

        # We can tell the dimension of the data based on the number of independent parameters.
        if len(self.independent_parameter_names) > 1:
            self.dim=3
        else:
            self.dim=2

        columns = [i for i in range(self.dim)] # This only exists to be compatible with the BaseClassData.
        self.settings['columns'] = ','.join([str(i) for i in columns]) # And even then I will remove it entirely one day.

        # Default to commonly measured transport variables if present (staying capital letter agnostic)
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

        if self.dim == 3:
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
        allnames=[self.all_parameter_names+negparamnames]
        self.filter_menu_options = {'Multiply': allnames,
                                    'Divide': allnames,
                                    'Add/Subtract': allnames}
        
        self.dims = self.data_dict[self.dependent_parameter_names[0]].shape # The dimension of each array.
        # Remove NaNs from the data_dict if they are present from a prematurely stopped Loop
        if not self.nans_removed and not self.isFinished():
            for key in self.data_dict.keys():
                self.data_dict[key]= self.data_dict[key][:len(self.set_x)-1]
            self.nans_removed = True
            self.dims = self.data_dict[self.dependent_parameter_names[0]].shape

    def isFinished(self):
        self.set_x = self.data_dict[self.all_parameter_names[0]]
        self.set_x = np.unique(self.set_x[~np.isnan(self.set_x)])
        return len(self.set_x) == self.dims[0]
        
    def get_column_data(self, line=None):
        # Used at plotting time to find which parameters to plot, put the into the raw_data attribute and set the labels.

        if line is not None:
            Xdataname = self.plotted_lines[line]['X data']
            Ydataname = self.plotted_lines[line]['Y data']
        else:
            Xdataname = self.settings['X data']
            Ydataname = self.settings['Y data']

        # If user has selected X data, use that, otherwise use the first independent parameter
        # X data is the same no matter the data dimension
        xdata = self.data_dict[Xdataname]
        try:
            self.settings['xlabel'] = f'{self.channels[Xdataname]['label']} ({self.channels[Xdataname]['unit']})'
        except KeyError:
            self.settings['xlabel'] = Xdataname
        
        if self.dim == 2: # data is 1D
            ydata = self.data_dict[Ydataname]
            try:
                self.settings['ylabel'] = f'{self.channels[Ydataname]['label']} ({self.channels[Ydataname]['unit']})'
            except KeyError:
                self.settings['ylabel'] = Ydataname
            
            if len(xdata)==len(ydata):
                #column_data = np.column_stack((xdata, ydata))
                column_data = [xdata, ydata]
            else:
                column_data = [[0,0], [0,0]]
                # This can happen if the user has run statistics, and is trying to plot the result; if they change only
                # the X data, the length of the data won't match the Y data until they then select the correct thing.
                # So, just plot nothing until the user selects something sensible.

            self.settings['default_xlabel'] = self.settings['xlabel']
            self.settings['default_ylabel'] = self.settings['ylabel']
            self.settings['default_histlabel'] = self.settings['default_ylabel']
            self.settings['default_fftxlabel'] = f'1/{self.settings['default_xlabel']}'

        elif self.dim == 3: # data is 2D
            ydata = self.data_dict[self.settings['Y data']]
            zdata = self.data_dict[self.settings['Z data']]

            # Ensure shapes are correct, and account for situation where qcodespp X data is plotted on either the X or Y axis.
            # Assume no-one will ever plot it on the Z axis...
            if ydata.shape == zdata.shape:
                if xdata.shape == zdata.shape: # Then we are happy
                    column_data = [xdata, ydata, zdata]
                elif len(xdata.shape) == 1 and xdata.shape[0] == zdata.shape[0]: # If X data is 1D, we need to repeat it to match the Y and Z data
                    xdata = np.repeat(xdata, ydata.shape[1]).reshape(zdata.shape)
                    column_data = [xdata, ydata, zdata]
                else:
                    # If X data doesn't match, we can't plot it sensibly
                    column_data = None
            elif xdata.shape == zdata.shape:
                if len(ydata.shape) == 1 and ydata.shape[0] == zdata.shape[0]:
                    # If Y data is 1D, we need to repeat it to match the X and Z data
                    ydata = np.repeat(ydata, zdata.shape[1]).reshape(zdata.shape)
                    column_data = [xdata, ydata, zdata]
                else:
                    # If Y data doesn't match, we can't plot it sensibly
                    column_data = None
            else: # Neither X nor Y data match Z data, so there is no chance of plotting; can happen when multiple array
                # dimensions are present in the dataset. Pass until the user selects something sensible.
                column_data = None
            
            self.settings['ylabel'] = (f'{self.channels[self.settings['Y data']]['label']} '
                                    f'({self.channels[self.settings['Y data']]['unit']})')
            self.settings['clabel'] = (f'{self.channels[self.settings['Z data']]['label']} '
                                    f'({self.channels[self.settings['Z data']]['unit']})')
            
            self.settings['default_xlabel'] = self.settings['xlabel']
            self.settings['default_ylabel'] = self.settings['ylabel']
            self.settings['default_clabel'] = self.settings['clabel']
            self.settings['default_histlabel'] = self.settings['default_clabel']
            self.settings['default_fftxlabel'] = f'1/{self.settings['default_xlabel']}'
            self.settings['default_fftylabel'] = f'1/{self.settings['default_ylabel']}'

        else:
            column_data = None
        
        if column_data is not None:
            self.dims=column_data[0].shape # Update the dims to match the data shape
        
        return column_data

    def load_and_reshape_data(self, reload_data=False,reload_from_file=True,linefrompopup=None):
        # qcodespp data is _already_ in the correct shape for IG plotting, so we don't have to do much
        # Just load the data if necessary, and then choose the right columns/parameters to plot.

        if not self.data_loaded or (reload_data and reload_from_file):
            self.load_data_from_file()

        # qcodespp datasets can contain arrays of different shapes. If the user is trying to change them, they can't
        # change all of them at once. Instead of giving an error, just keep the old state.
        old_raw_data = copy.deepcopy(self.raw_data)
        self.raw_data = self.get_column_data(line=linefrompopup)
        if self.raw_data is None:
            self.raw_data = old_raw_data
            self.dimension_mismatch = True
        else:
            self.dimension_mismatch = False

        if self.dim == 3: # For 2D data, we do a couple of checks.
            if self.dims[0] > 1: # If two or more sweeps are finished
                # flip if first column is sorted from high to low
                if self.raw_data[0][0,0] > self.raw_data[0][-1,0]:
                    self.raw_data = [np.flipud(self.raw_data[i]) for i in range(len(self.raw_data))]
                    self.udflipped=True
                # flip if second column is sorted from high to low
                if self.raw_data[1][0,0] > self.raw_data[1][0,1]: 
                    self.raw_data = [np.fliplr(self.raw_data[i]) for i in range(len(self.raw_data))]
                    self.lrflipped=True
            elif self.dims[0] == 1: # if first two sweeps are not finished -> duplicate data of first sweep to enable 2D plotting
                self.raw_data = [np.tile(self.raw_data[i], (2, 1)) for i in range(len(self.raw_data))]

            else:
                self.raw_data = None

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
    
    def filttocol(self, axis):
        axes={'X': 0, 'Y': 1, 'Z': 2}
        if hasattr(self, 'sidebar1D'):
            current_1D_row = self.sidebar1D.trace_table.currentRow()
            current_line = int(self.sidebar1D.trace_table.item(current_1D_row,0).text())
            processed_data = self.plotted_lines[current_line]['processed_data'][axes[axis]]
            paramname = self.plotted_lines[current_line][f'{axis} data']
            colname= f'Filtered: {paramname}'
            self.dependent_parameter_names.append(colname)
            self.all_parameter_names.append(colname)
            self.data_dict[colname] = processed_data
            self.channels[colname] = {'label': colname,
                                        'unit': self.channels[paramname]['unit'],
                                        'array_id': colname,
                                        'is_setpoint': False}
        else:
            processed_data = self.processed_data[axes[axis]]
            paramname = self.settings[f'{axis} data']
            colname= f'Filtered: {paramname}'
            self.dependent_parameter_names.append(colname)
            self.all_parameter_names.append(colname)
            self.data_dict[colname] = processed_data
            self.channels[colname] = {'label': colname,
                                        'unit': self.channels[paramname]['unit'],
                                        'array_id': colname,
                                        'is_setpoint': False}
            
        if not hasattr(self, 'extra_cols'):
            self.extra_cols = []
        self.extra_cols.append(colname)

        for label in ['X data', 'Y data', 'Z data']:
            self.settings_menu_options[label]= self.all_parameter_names
        negparamnames=[f'-{name}' for name in self.all_parameter_names]
        allnames=np.hstack((self.all_parameter_names,negparamnames))
        for filtname in ['Multiply', 'Divide', 'Add/Subtract']:
            self.filter_menu_options[filtname]=allnames