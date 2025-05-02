from PyQt5 import QtWidgets
import numpy as np
import os
import json
from matplotlib import cm
from matplotlib.widgets import Cursor
from qcodesplusplus.data.data_set import load_data
import qcodesplusplus.plotting.offline.main as main

from .helpers import MidpointNormalize
from .popupwindows import FFTWindow, Popup1D


class qcodesppData(main.BaseClassData):

    def __init__(self, filepath, canvas, metapath, load_the_data=True):
        super().__init__(filepath, canvas)
        # Open meta file and set label
        self.filepath = filepath
        with open(metapath) as f:
            self.meta = json.load(f)
        dirname = os.path.basename(os.path.dirname(metapath))
        # timestamp = self.meta['timestamp'].split(' ')[1]

        self.label = f'{dirname.split('#')[1]}'
        # self.raw_data = None
        

        self.independent_parameters = []
        self.independent_parameter_names = []
        self.dependent_parameters = []
        self.dependent_parameter_names = []
        self.all_parameters = []
        self.all_parameter_names = []
        
        
        
        self.channels = self.meta['arrays']

        if load_the_data:
            if '.dat' in filepath:
                self.dataset=load_data(os.path.dirname(filepath))
            else:
                self.dataset=load_data(filepath)

            self.identify_independent_vars()

            self.prepare_dataset()

            self.data_loaded=True
        
        else:
            self.data_loaded=False
            self.dataset=None

        self.index_x = 0
        self.index_y = 1

        #self.dataset_id = "#" + self.dataset.location.split("#", 1)[1].split("_", 1)[0]
        self.dataset_id = "#" + dirname.split("#", 1)[1].split("_", 1)[0]
        self.settings["title"] = self.dataset_id
        self.DEFAULT_PLOT_SETTINGS['title']= self.dataset_id
    


    def prepare_dataset(self):
        
        self.data_dict = self.dataset.arrays
        pars = list(self.data_dict.keys())
        self.dims = self.data_dict[pars[1]].shape


        if len(self.independent_parameters) > 1:
            pars = list(self.data_dict.keys())
            self.dims = self.data_dict[pars[1]].shape
            if len(self.data_dict[self.all_parameters[0]["array_id"]]) < self.dims[0]*self.dims[1]:
                self.data_dict[self.all_parameters[0]["array_id"]] = np.repeat(self.data_dict[self.all_parameters[0]["array_id"]], self.dims[1])


    def isFinished(self):
        self.set_x = self.data_dict[self.all_parameters[0]["array_id"]]
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

        self.prepare_dataset()
        # If user has selected X data, use that, otherwise use the first independent parameter
        # X data is the same no matter the data dimension
        if Xdataname != '':
            xdata = self.data_dict[Xdataname]
            self.settings['xlabel'] = f'{self.channels[Xdataname]['label']} ({self.channels[Xdataname]['unit']})'
        else:
            xdata = self.data_dict[self.all_parameters[self.index_x]["array_id"]]
            self.settings["xlabel"] = "{} ({})".format(self.independent_parameters[0]["label"], self.independent_parameters[0]["unit"])
        
        if len(self.independent_parameters) == 1: # data is 1D
            if Ydataname != '':
                ydata = self.data_dict[Ydataname]
                self.settings['ylabel'] = f'{self.channels[Ydataname]['label']} ({self.channels[Ydataname]['unit']})'
            else:
                ydata = self.data_dict[self.dependent_parameters[self.index_dependent_parameter]["array_id"]]
                self.settings["xlabel"] = "{} ({})".format(self.independent_parameters[0]["label"], self.independent_parameters[0]["unit"])

            if not self.isFinished():
                # Delete unfinished rows to enable plotting
                xdata = xdata[:len(self.set_x)-1]
                ydata = ydata[:len(self.set_x)-1]
            column_data = np.column_stack((xdata, ydata))

        elif len(self.independent_parameters) > 1: # data is 2D
            if self.settings['Y data'] != '':
                ydata = self.data_dict[self.settings['Y data']]
                self.settings['ylabel'] = f'{self.channels[self.settings['Y data']]['label']} ({self.channels[self.settings['Y data']]['unit']})'
            else:
                ydata = self.data_dict[self.all_parameters[self.index_y]["array_id"]]
                self.settings["ylabel"] = "{} ({})".format(self.all_parameters[self.index_y]["label"], self.independent_parameters[1]["unit"])

            if self.settings['Z data'] != '':
                zdata = self.data_dict[self.settings['Z data']]
                self.settings['clabel'] = f'{self.channels[self.settings['Z data']]['label']} ({self.channels[self.settings['Z data']]['unit']})'
            else:
                zdata = self.data_dict[self.dependent_parameters[self.index_dependent_parameter]["array_id"]]
                self.settings["clabel"] = "{} ({})".format(self.dependent_parameters[self.index_dependent_parameter]["label"], self.dependent_parameters[self.index_dependent_parameter]["unit"])
            
            column_data = np.column_stack((xdata.flatten(),
                                         ydata.flatten(),
                                        zdata.flatten()
                                        ))

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
    

    def load_and_reshape_data(self, reload_data=False,reload_from_file=True,linefrompopup=None):
        if not self.data_loaded or reload_data and reload_from_file:
            if '.dat' in self.filepath:
                self.dataset=load_data(os.path.dirname(self.filepath))
            else:
                self.dataset=load_data(self.filepath)

            self.identify_independent_vars()

            self.prepare_dataset()

            self.data_loaded=True

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
                # if len(unique_values) > 1: # if first sweep is finished -> set second x-column to second x-value
                #     self.raw_data[columns[0]][0,:] = unique_values[0]
                #     self.raw_data[columns[0]][1,:] = unique_values[1]
                # else: # if first sweep is not finished -> set duplicate x-columns to +1 and -1 of actual value
                self.raw_data[columns[0]][0,:] = columns[0]-1
                self.raw_data[columns[0]][1,:] = columns[0]+1
            else:
                self.raw_data = None
                
            self.settings['columns'] = ','.join([str(i) for i in columns])
    
    def copy_raw_to_processed_data(self,line=None):
        if line is not None:
            self.plotted_lines[line]['raw_data'] = self.raw_data
            self.plotted_lines[line]['processed_data'] = [np.array(np.copy(self.raw_data[x])) for x in self.get_columns()]
        else:
            self.processed_data = [np.array(np.copy(self.raw_data[x])) for x in self.get_columns()]

    def identify_independent_vars(self):        
        for chan in self.channels.keys():
            if self.channels[chan]["array_id"] not in self.all_parameter_names:
                if self.channels[chan]["is_setpoint"] and self.channels[chan]["array_id"] in list(self.dataset.arrays.keys()):
                    self.independent_parameters.append(self.channels[chan])
                    self.independent_parameter_names.append(self.channels[chan]["array_id"])
                elif self.channels[chan]["array_id"] in list(self.dataset.arrays.keys()):
                    self.dependent_parameters.append(self.channels[chan])
                    self.dependent_parameter_names.append(self.channels[chan]["array_id"])
        self.all_parameters = self.independent_parameters + self.dependent_parameters
        self.all_parameter_names = self.independent_parameter_names + self.dependent_parameter_names
        
        # Default to conductance as dependent variable if present.
        defnamefound=False
        for paramname in ['onductance','esistance', 'urr', 'olt']:
            for name in self.dependent_parameter_names:
                if not defnamefound:
                    if paramname in name:
                        self.index_dependent_parameter = self.dependent_parameter_names.index(name)
                        defnamefound=True
        if not defnamefound: 
            self.index_dependent_parameter = 0

        self.settings['X data'] = self.independent_parameter_names[0]

        if len(self.independent_parameters) > 1:
            self.settings['Y data'] = self.independent_parameter_names[1]
            self.settings['Z data'] = self.dependent_parameter_names[self.index_dependent_parameter]

        else:
            self.settings['Y data'] = self.dependent_parameter_names[self.index_dependent_parameter]

            self.settings.pop('Z data', None)

        self.settings_menu_options = {'X data': self.all_parameter_names,
                                      'Y data': self.all_parameter_names,
                                      'Z data': self.all_parameter_names}
        
        self.filter_menu_options = {'Multiply': self.all_parameter_names,
                                    'Divide': self.all_parameter_names,
                                    'Offset': self.all_parameter_names}
        
    # Redefine apply_all_filters so that data from other columns can be sent to the filters.
    def apply_all_filters(self, update_color_limits=True):
        if hasattr(self, 'popup1D'):
            current_1D_row = self.popup1D.cuts_table.currentRow()
            current_line = int(self.popup1D.cuts_table.item(current_1D_row,0).text())
            filters= self.plotted_lines[current_line]['filters']
            processed_data = self.plotted_lines[current_line]['processed_data']
        else:
            filters=self.filters
            processed_data = self.processed_data
        for filt in filters:
            if filt.checkstate:
                if filt.name in ['Multiply', 'Divide', 'Offset']:
                    if filt.settings[0][0]=='-':
                        arrayname=filt.settings[0][1:]
                        setting2='-'
                    else:
                        arrayname=filt.settings[0]
                        setting2='+'
                    if arrayname in self.all_parameter_names:
                        if len(self.independent_parameters) > 1:
                            array=self.data_dict[arrayname][:self.dims[0]][:self.dims[1]]
                        else:
                            array=self.data_dict[arrayname][:self.dims[0]]
                        if hasattr(self,'udflipped'): # If the calculated column data got flipped.
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
        if hasattr(self, 'popup1D'):
            self.plotted_lines[current_line]['processed_data'] = processed_data
        else:
            self.processed_data = processed_data
        if update_color_limits:
            self.reset_view_settings()
            # The below was the cause of the NotImplmentedError. Seems to work fine without it.
            # if hasattr(self, 'image'):
            #     self.apply_view_settings()

    def add_plot(self, dim, editor_window=None):
        if self.processed_data:
            cmap_str = self.view_settings['Colormap']
            if self.view_settings['Reverse']:
                cmap_str += '_r'
            cmap = cm.get_cmap(cmap_str, lut=int(self.settings['lut']))
            cmap.set_bad(self.settings['maskcolor'])
            if dim == 2:
                # self.image = self.axes.plot(self.processed_data[0], 
                #                             self.processed_data[1], color=cmap(0.5))
                
                if not hasattr(self, 'plotted_lines'):
                    self.plotted_lines = {0: {'checkstate': 2,
                                                'X data': self.independent_parameter_names[0],
                                                'Y data': self.dependent_parameter_names[self.index_dependent_parameter],
                                                'raw_data': self.raw_data,
                                                'processed_data': self.processed_data,
                                                'linecolor': (0.1, 0.5, 0.8, 1),
                                                'linewidth': 1.5,
                                                'linestyle': '-',
                                                'filters': []}}
                if not hasattr(self, 'popup1D'):
                    self.popup1D = Popup1D(self,editor_window=editor_window)
                    self.popup1D.running = True
                    self.popup1D.append_cut_to_table(0)
                    self.popup1D.activateWindow()

                self.popup1D.update()

                # This is horrible, but I need to get rid of these. Ideally I would re-write the extension so they're
                # not used at all in the 1D case. Will try later.
                if 'X data' in self.settings.keys():
                    self.settings.pop('X data')
                if 'Y data' in self.settings.keys():
                    self.settings.pop('Y data')

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
                    self.cbar = self.figure.colorbar(self.image,orientation='vertical')
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