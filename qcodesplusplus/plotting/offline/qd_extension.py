# -*- coding: utf-8 -*-
"""
Inspectra-Gadget - Matlab qd functionality

Author: Joeri de Bruijckere

Last updated on Nov 11 2020

"""

from PyQt5 import QtWidgets
import numpy as np
import os
import json
from datetime import timedelta, datetime
from textwrap import wrap

import qcodesplusplus.plotting.offline.main as main

# Default settings Matlab qd data
DEFAULT_CHANNEL = 'lockin_curr/X' # Channel shown by default
CONVERT_MICROSIEMENS_TO_ESQUAREDH = True # Whether or not to convert dI/dV from uS to e^2/h by default
DEFAULT_RC_FILTER_CORRECT = True # Whether or not to apply RC-filter correction by default
DEFAULT_RC_FILTER_VALUE = 8240 # Default value of the total RC-filer resistance (Ohm)
DEFAULT_SHOW_FULL_RANGE = False # Adjust limits of plot to its final size by default
DEFAULT_SHOW_SETTINGS_LIST = False # Show a list of the values of the other channels as specified by CHANNELS_TO_SHOW
CHANNELS_TO_SHOW = ['source', 'pg1', 'pg2', 'cg1', 'cg2', 'bg', 'sg', 'Bx', 'Bz', 'T']

# These channels will have their corresponding axis label automatically replaced by the name and unit in this dictionary
LABEL_DICT = {'source': ('Bias voltage', '(mV)'), 
              'dc_curr': ('Current', '(nA)'), 
              'lockin_curr/X': ('d$I$/d$V$', '($e^2/h$)'),
              'lockin_bias/X': ('d$V$/d$I$', '($\Omega$)'),
              'bg': ('Backgate voltage', '(V)'), 
              'sg': ('Sidegate voltage', '(V)'),
              'GATE': ('Gate voltage', '(V)')}

class QdData(main.BaseClassData):
    
    def __init__(self, filepath, canvas, metapath):
        super().__init__(filepath, canvas)
        # Open meta file and set label
        with open(metapath) as f:
            self.meta = json.load(f) 
        dirname = os.path.basename(os.path.dirname(metapath))
        timestamp = self.meta['timestamp'].split(' ')[1]
        name = self.meta['name']
        self.label = f'{dirname} {timestamp} {name}'
        
        # Initialize default settings
        self.settings['showsettings'] = f'{DEFAULT_SHOW_SETTINGS_LIST}'
        self.settings['rc-filter'] = f'{DEFAULT_RC_FILTER_VALUE}'
        self.settings_menu_options = {'rc_filter': ['0', '4120', '8420'],
                                      'showsettings': ['True', 'False']}
        self.rc_filter_correct = DEFAULT_RC_FILTER_CORRECT
        self.show_full_range = DEFAULT_SHOW_FULL_RANGE
        
        self.channels = [channel['name'] for channel in self.meta['columns']]
        self.construct_settings_list()
        self.set_measurement_bounds()
        self.determine_total_data_points()
        
    def set_default_channel(self):
        try:
            new_index = self.channels.index(DEFAULT_CHANNEL)
            columns = self.settings['columns'].split(',')
            columns[-1] = str(new_index)
            self.settings['columns'] = ','.join([str(col) for col in columns])
        except Exception as e:
            print(f'Default channel {DEFAULT_CHANNEL} not found...', e)
        
    def construct_settings_list(self):
        self.settings_string = '' 
        meta_channels = self.meta['setup']['channels']
        for instrument in self.meta['register']['instruments']:
            if instrument['name'] == 'dac':
                dac = instrument
                break
        for channel in CHANNELS_TO_SHOW:
            try:
                if channel in meta_channels:
                    for register_channel in self.meta['register']['channels']:
                        if register_channel['name'] == channel: 
                            if register_channel['instrument'] == 'dac':  
                                value = dac['current_values'][register_channel['channel_id']]
                                self.settings_string += f'{channel}: {value:.3g} \n'
                                break
                            elif register_channel['instrument'] == 'smua':
                                for instrument in self.meta['register']['instruments']:
                                    if instrument['name'] == 'smua' and 'current_values' in instrument.keys():
                                        value = instrument['current_values']['v']
                                        self.settings_string += f'{channel}: {value:.3g} \n'
                                        break
                            elif register_channel['instrument'] == 'smub':
                                for instrument in self.meta['register']['instruments']:
                                    if instrument['name'] == 'smub' and 'current_values' in instrument.keys():
                                        value = instrument['current_values']['v']
                                        self.settings_string += f'{channel}: {value:.3g} \n'
                                        break
                            elif register_channel['instrument'] == 'smua2':
                                for instrument in self.meta['register']['instruments']:
                                    if instrument['name'] == 'smua2' and 'current_values' in instrument.keys():
                                        value = instrument['current_values']['v']
                                        self.settings_string += f'{channel}: {value:.3g} \n'
                                        break
                            elif register_channel['instrument'] == 'smub2':
                                for instrument in self.meta['register']['instruments']:
                                    if instrument['name'] == 'smub2' and 'current_values' in instrument.keys():
                                        value = instrument['current_values']['v']
                                        self.settings_string += f'{channel}: {value:.3g} \n'
                                        break
                    else:
                        if channel == 'Bx' or channel == 'Bz':
                            for instrument in self.meta['register']['instruments']:
                                if instrument['name'] == 'magnet':
                                    value = instrument['field'][channel[1:]]
                                    self.settings_string += f'{channel}: {value:.3g} \n'
                                    break
                elif channel == 'T':
                    for instrument in self.meta['register']['instruments']:
                        if instrument['name'] == 'triton':
                            value = instrument['temperatures']['MC']*1000
                            self.settings_string += f'{channel}: {value:.3g} \n'
                            break
            except:
                print(f'Could not add channel {channel}...')      
    
    def prepare_data_for_plot(self, reload_data=False, refresh_unit_conversion=False):
        if not hasattr(self, 'raw_data') or not self.raw_data:
            self.load_and_reshape_data()
            self.set_default_channel()
            refresh_unit_conversion = True
        elif reload_data:
            self.load_and_reshape_data()
        if self.raw_data:
            self.copy_raw_to_processed_data()
            self.process_four_terminal_data()
            if self.rc_filter_correct:
                self.correct_for_rcfilters()
            if refresh_unit_conversion:
                self.filters = []
                self.reset_labels()
                self.unit_conversion()
            self.apply_all_filters()
            self.update_progress()
        else:
            self.processed_data = None
        
    def set_measurement_bounds(self, rescale=1, offset=0):
        # Get bounds to be able to show full range during measurement
        if 'from' in self.meta['job'] and 'to' in self.meta['job']:
            self.measurement_bounds = [self.meta['job']['from'],
                                       self.meta['job']['to']]
        elif ('job' in self.meta['job'] and 'from' in self.meta['job']['job']
              and 'to' in self.meta['job']['job']):
            self.measurement_bounds = [self.meta['job']['job']['from'],
                                       self.meta['job']['job']['to']]
        
        # If x-parameter is combination of channels (list), 
        # take bounds that belongs to the displayed channel    
        if isinstance(self.measurement_bounds[0], list):
            x_channel = self.channels[self.get_columns()[0]]
            meta_channels = self.meta['job']['chans']
            if x_channel in meta_channels:
                self.measurement_bounds = [bound[meta_channels.index(x_channel)]
                                           for bound in self.measurement_bounds]
        if hasattr(self, 'measurement_bounds'):
            self.measurement_bounds = [bound/rescale+offset for bound 
                                       in self.measurement_bounds]

    def determine_total_data_points(self):
        # Get total number of (to be) measured data points
        self.total_data_points = 1 
        if 'points' in self.meta['job']:
            self.total_data_points *= self.meta['job']['points']
        if 'points' in self.meta['job']['job']:
            self.total_data_points *= self.meta['job']['job']['points']
    
    def correct_for_rcfilters(self):
        columns = self.get_columns()
        if 'source' in self.channels and 'dc_curr' in self.channels:
            try:
                source_index = self.channels.index('source')
                if source_index in columns:
                    source_divider = self.meta['setup']['meta']['source_divider']
                    curr_index = self.channels.index('dc_curr')                    
                    curr_amp = self.meta['setup']['meta']['current_amp']
                    source_data = self.raw_data[source_index] / source_divider
                    curr_data = self.raw_data[curr_index] / curr_amp
                    source_corrected = (source_data - float(self.settings['rc-filter'])*curr_data)*source_divider
                    self.processed_data[columns.index(source_index)] = np.copy(source_corrected)
            except Exception as e:
                print('Could not perform rc-filter correction for source...', e)
        
        if 'lockin_curr/X' in self.channels:
            try:
                lockin_index = self.channels.index('lockin_curr/X')
                if lockin_index in columns:
                    for instrument in self.meta['register']['instruments']:
                        if instrument['name'] == 'lockin_curr':
                            break
                    sine_amplitude = float(instrument['config']['SLVL'])
                    lockin_divider = self.meta['setup']['meta']['lock_sig_divider']
                    curr_amp = self.meta['setup']['meta']['current_amp']
                    conversion = curr_amp*sine_amplitude/lockin_divider # divide by this to convert lockin-signal to Siemens (1/Ohm)
                    lockin_data = self.raw_data[lockin_index]/conversion # in Siemens
                    series_resistance = float(self.settings['rc-filter']) # in Ohm
                    lockin_corrected = lockin_data/(1.-series_resistance*lockin_data)*conversion
                    self.processed_data[columns.index(lockin_index)] = np.copy(lockin_corrected)
            except Exception as e:
                print('Could not perform rc-filter correction for lockin_curr/X...', e)

    def unit_conversion(self):
        columns = self.get_columns()
        if 'source' in self.channels:
            source_index = self.channels.index('source')
            if source_index in columns:
                source_divider = self.meta['setup']['meta']['source_divider']
                SOURCE_UNIT = 1e-3 # Convert V to mV  
                if source_divider*SOURCE_UNIT != 1.0:
                    divide = f'{source_divider*SOURCE_UNIT:.3g}'
                    axis = ['X','Y','Z'][columns.index(source_index)] 
                    self.filters.append({'Name': 'Divide', 'Method': axis, 
                                         'Setting 1': divide, 'Setting 2': '', 'Checked': 2})
                if source_index == 0:
                    self.set_measurement_bounds(rescale=source_divider*SOURCE_UNIT)
        
        # Gate voltages are combinations of a coarse channel and a fine channel
        fine_gates = [channel for channel in self.channels 
                      if channel[0] == 'g' and channel[-1] == 'f']
        for gate in fine_gates:
            gate_index = self.channels.index(gate)
            if gate_index in columns:                              
                DAC_FINE_DIVIDER = 200
                DAC_FINE_OFFSET = 0.05
                divide = f'{DAC_FINE_DIVIDER:.3g}'
                gate_axis = ['X','Y','Z'][columns.index(gate_index)]
                self.filters.append(main.Filter(name='Divide', method=gate_axis,
                                                settings=[divide,''], checkstate=2))
                if DAC_FINE_OFFSET != 0.0:
                    fine_offset = f'{DAC_FINE_OFFSET:.3g}'
                    self.filters.append(main.Filter(name='Offset', method=gate_axis,
                                                    settings=[fine_offset,''], checkstate=2))
                coarse_gate = gate[:-1]
                for instrument in self.meta['register']['instruments']:
                    if instrument['name'] == 'dac':
                        dac = instrument
                        break
                for dac_channel in self.meta['register']['channels']:
                    if dac_channel['name'] == coarse_gate:
                        dac_channel_coarse_gate = dac_channel['channel_id']
                        break
                coarse_offset_dac = dac['current_values'][dac_channel_coarse_gate]
                coarse_offset = f'{coarse_offset_dac:.3g}'
                self.filters.append(main.Filter(name='Offset', method=gate_axis,
                                                settings=[coarse_offset,''], checkstate=2))
                if gate_index == 0:   
                    self.set_measurement_bounds(rescale=DAC_FINE_DIVIDER, 
                                                offset=DAC_FINE_OFFSET+coarse_offset_dac)
             
        if 'dc_curr' in self.channels:
            curr_index = self.channels.index('dc_curr')
            if curr_index in columns:
                curr_amp = self.meta['setup']['meta']['current_amp']
                CURR_UNIT = 1e-9 # Ampere to nano-ampere
                if curr_amp*CURR_UNIT != 1.0:
                    divide = f'{curr_amp*CURR_UNIT:.3g}'
                    axis = ['X','Y','Z'][columns.index(curr_index)]                    
                    self.filters.append(main.Filter(name='Divide', method=axis,
                                                    settings=[divide,''], checkstate=2))
        
        if 'lockin_curr/X' in self.channels:
            lockin_index = self.channels.index('lockin_curr/X')
            if lockin_index in columns:
                for instrument in self.meta['register']['instruments']:
                    if instrument['name'] == 'lockin_curr':
                        break
                sine_amplitude = float(instrument['config']['SLVL'])
                lockin_divider = self.meta['setup']['meta']['lock_sig_divider']
                curr_amp = self.meta['setup']['meta']['current_amp']
                LOCKIN_UNIT = 1e-6 # Siemens to microsiemens
                conversion_factor = curr_amp*sine_amplitude/lockin_divider*LOCKIN_UNIT
                if conversion_factor != 1.0:
                    divide = f'{conversion_factor:.3g}'
                    axis = ['X','Y','Z'][columns.index(lockin_index)] 
                    self.filters.append(main.Filter(name='Divide', method=axis,
                                                    settings=[divide,''], checkstate=2))
                    multiply_e2h = 'e^2/h'
                    axis = ['X','Y','Z'][columns.index(lockin_index)] 
                    self.filters.append(main.Filter(name='Multiply', method=axis,
                                                    settings=[multiply_e2h,''], checkstate=2))

        if 'lockin_bias/X' in self.channels and 'lockin_curr/X' in self.channels: # assume 4-terminal, current-biased
            lockin_bias_index = self.channels.index('lockin_bias/X')
            if lockin_bias_index in columns:
                curr_amp = self.meta['setup']['meta']['current_amp']
                bias_amp = self.meta['setup']['meta']['bias_amp']
                conversion_factor = curr_amp/bias_amp
                if conversion_factor != 1.0:
                    factor = f'{conversion_factor:.3g}'
                    axis = ['X','Y','Z'][columns.index(lockin_bias_index)]                    
                    self.filters.append(main.Filter(name='Multiply', method=axis,
                                                    settings=[factor,''], checkstate=2))
        
    def reset_labels(self):
        columns = self.get_columns()
        self.settings['xlabel'] = self.channels[columns[0]]
        self.settings['ylabel'] = self.channels[columns[1]]
        self.settings['clabel'] = self.channels[columns[-1]]         
    
        for index, channel in enumerate([self.channels[x] for x in columns]):
            label = ['xlabel', 'ylabel', 'clabel'][index]
            if channel in LABEL_DICT:
                self.settings[label] = (f'{LABEL_DICT[channel][0]} '
                                        f'{LABEL_DICT[channel][1]}')
            elif channel[0] == 'g' and channel[1].isdigit() and len(channel) < 4:
                self.settings[label] = (f'{LABEL_DICT["GATE"][0]} {channel[1]} '
                                        f'{LABEL_DICT["GATE"][1]}')
    
    def process_four_terminal_data(self):
        if ('lockin_bias/X' in self.channels and 
            'lockin_curr/X' in self.channels):
            bias_index = self.channels.index('lockin_bias/X')
            if bias_index in self.columns:
                curr_index = self.channels.index('lockin_curr/X')
                data_index = self.columns.index(bias_index) 
                self.processed_data[data_index] = (self.raw_data[bias_index] / 
                                                   self.raw_data[curr_index])
    
    def add_plot(self, dim):
        super().add_plot(dim)
        if dim == 2:
            if self.settings['showsettings'] == 'True':
                self.axes.text(1.02, 0, self.settings_string, 
                               fontsize=self.settings['ticksize'], 
                               transform=self.axes.transAxes) 
        elif dim == 3:
            if hasattr(self, 'measurement_bounds') and self.show_full_range:        
                self.axes.set_xlim(left=min(self.measurement_bounds), 
                                   right=max(self.measurement_bounds))
            if self.settings['showsettings'] == 'True':
                self.axes.text(1.2, 0, self.settings_string, 
                               fontsize=self.settings['ticksize'], 
                               transform=self.axes.transAxes)
    
    def apply_plot_settings(self):
        super().apply_plot_settings()
        if self.settings['title'] == '<label>':
            self.axes.set_title("\n".join(wrap(self.label,80)), 
                                size=self.settings['titlesize'])
     
    def file_finished(self):
        if (hasattr(self, 'last_modified_time') and
            hasattr(self, 'progress_fraction')):
            return ((datetime.now().timestamp() - 
                     self.last_modified_time > 600) or 
                    self.progress_fraction == 1)
        else:
            return False
        
    def update_progress(self):
        self.progress_fraction = (self.measured_data_points /
                                  self.total_data_points)
        self.last_modified_time = os.path.getmtime(self.filepath)
        spent_time = self.last_modified_time - self.creation_time
                     
        total_time = spent_time / self.progress_fraction
        remaining_seconds = total_time - spent_time
        remaining_datetime = timedelta(seconds=remaining_seconds)
        
        percentage = int(self.progress_fraction*100)
        remaining_time = str(remaining_datetime).split('.')[0]
        finish_time = str(datetime.now()+remaining_datetime).split('.')[0]
        self.remaining_time_string = (f'  {percentage}% Completed  -  Remaining time: '
                                      f'{remaining_time}  -  Finishes at: {finish_time}')

    def extension_setting_edited(self, editor, setting_name):
        if setting_name == 'rc-filter':
            self.prepare_data_for_plot(reload_data=True)
            editor.update_plots()
        elif setting_name == 'showsettings':
            editor.update_plots()

    def add_extension_actions(self, editor, menu):
        channel_menu = menu.addMenu('Change channel to...')
        for channel in self.channels[len(self.get_columns())-1:]:
            action = QtWidgets.QAction(channel, editor)
            channel_menu.addAction(action)
            
        if self.rc_filter_correct:
            action = QtWidgets.QAction('Disable RC-filter correction...', editor)                            
        else:
            action = QtWidgets.QAction('Enable RC-filter correction...', editor)
        menu.addAction(action)  
        
        if hasattr(self, 'show_full_range') and self.show_full_range:
            action = QtWidgets.QAction('Show measured range...', editor)
        else:
            action = QtWidgets.QAction('Show full range...', editor)                                
        menu.addAction(action)
        menu.addSeparator()

    def do_extension_actions(self, editor, signal):
        if signal.text() == 'Enable RC-filter correction...':
            self.rc_filter_correct = True
            self.prepare_data_for_plot(reload_data=True, refresh_unit_conversion=False)
            editor.update_plots()
        elif signal.text() == 'Disable RC-filter correction...':
            self.rc_filter_correct = False
            self.prepare_data_for_plot(reload_data=True, refresh_unit_conversion=False)
            editor.update_plots()
        elif signal.text() in self.channels:
            channel_index = self.channels.index(signal.text())
            self.settings['columns'] = self.settings['columns'][:-1]+str(channel_index)
            if len(self.get_columns()) == 2:
                self.settings['ylabel'] = signal.text()
            else:                
                self.settings['clabel'] = signal.text()
            self.prepare_data_for_plot(reload_data=True, refresh_unit_conversion=True)
            editor.update_plots()
            editor.show_current_all()
        elif signal.text() == 'Show full range...':
            self.show_full_range = True
            self.axes.set_xlim(left=min(self.measurement_bounds), 
                               right=max(self.measurement_bounds))
            editor.canvas.draw()
        elif signal.text() == 'Show measured range...':
            self.show_full_range = False
            self.axes.set_xlim(left=np.amin(self.processed_data[0]), 
                               right=np.amax(self.processed_data[0]))
            editor.canvas.draw()