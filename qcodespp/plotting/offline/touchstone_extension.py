import numpy as np
import os
import copy

from websockets.typing import Data

from qcodespp.plotting.offline.datatypes import BaseClassData

TOUCHSTONE_EXTENSIONS = ['.s1p', '.s2p', '.s3p', '.s4p', '.s5p', '.s6p', '.s7p', '.s8p']

PARAMETERS = ['S', 'Y', 'Z', 'H', 'G']

UNITS = ['Hz', 'kHz', 'MHz', 'GHz']

FORMATS = {'MA': ['Magnitude', 'Phase'],
           'DB': ['Decibels', 'Phase'],
           'RI': ['Real', 'Imaginary']}

KEYWORDS = ['Version',
            'Number of Ports',
            'Two-Port Data Order',
            'Number of Frequencies',
            'Number of Noise Frequencies',
            'Reference',
            'Matrix Format',
            'Mixed-Mode Order',
            'Begin Information',
            'End Information',
            'Network Data',
            'Noise Data',
            'End']

class TouchstoneData(BaseClassData):

    def __init__(self, filepath, canvas):
        super().__init__(filepath, canvas)

        _, ext = os.path.splitext(self.filepath)
        self.num_ports = int(ext[2:-1])

        self.parameter_type = 'S'
        self.frequency_unit = 'GHz'
        self.format_type = 'DB'
        self.impedance = 50

        self.meta={'comment_lines': [], 'keyword_lines': {}}
        
    def load_and_reshape_data(self,reload_data=False,reload_from_file=False,linefrompopup=None):
        if reload_from_file or self.loaded_data is None:
            error=self.prepare_dataset()
            if error:
                return error
        column_data = self.get_column_data(linefrompopup)
        self.raw_data = column_data.T

    def prepare_dataset(self):
        # Loads the data from file and prepares a data_dict, where the arrays are stored identified by 
        # either their header column names, or by their column number if no header is present.
        # These names are then sent to various parts of the GUI.

        success = self.load_touchstone_data()

        if success:
            self.dim=2 #always true for touchstone files
            self.set_names()

        else:
            return ValueError(f'Could not load data from {self.filepath}. File may be empty or not formatted correctly.')
        
    def load_touchstone_data(self):
        # Load Touchstone data from file and store it in self.data_dict.
        # Returns True if successful, False otherwise.

        try:
            with open(self.filepath, 'r') as f:
                lines = f.readlines()

            # Parse the Touchstone file format
            data_lines = []
            for i,line in enumerate(lines):
                line = line.strip()
                if line.startswith('!'):
                    self.meta['comment_lines'].append(line)
                elif line.startswith('#'):
                    self.decode_options(line)
                elif line.startswith('['):
                    self.decode_keyword(lines[i:])
                elif line:  # Non-empty line
                    data_lines.append(line)

            if not data_lines:
                return False  # No data found

            # Convert data lines to numpy array
            data_array = np.array([list(map(float, line.split())) for line in data_lines])

            # Store the data in self.data_dict
            self.all_parameter_names = self.create_labels()
            self.data_dict = {self.all_parameter_names[i]: data_array[:, i] for i in range(data_array.shape[1])}
            return True

        except Exception as e:
            return False
        
    def decode_options(self, line):
        # Decode the options line in the Touchstone file and set the corresponding attributes.
        parts = line[1:].strip().split()
        for part in parts:
            if part.upper() in PARAMETERS:
                self.parameter_type = part.upper()
            elif part.upper() in UNITS:
                self.frequency_unit = part.upper()
            elif part.upper() in FORMATS:
                self.format_type = FORMATS[part.upper()]
            else:
                try:
                    self.impedance = float(part)
                except ValueError:
                    pass  # Ignore unrecognized parts

    def decode_keyword(self, lines):
        line=lines[0].strip()
        keyword_end = line.find(']')
        keyword_name = line[1:keyword_end].strip() if keyword_end != -1 else ''
        keyword_data = line[keyword_end+1:].strip() if keyword_end != -1 else []
        if keyword_name == 'Network Data':
            return
        if keyword_name in KEYWORDS:
            for i in range(1, len(lines)):
                line = lines[i].strip()
                if line.startswith('['):
                    break
                keyword_data.append(line)
        self.meta['keyword_lines'][keyword_name] = keyword_data

        if keyword_name == 'Number of Ports':
            try:
                self.num_ports = int(keyword_data[0])
            except (ValueError, IndexError):
                pass  # Ignore if the data is not valid

    def create_labels(self):
        # Create labels for the data based on the parameter type, format, and number of ports.
        labels = [f'Frequency ({self.frequency_unit})'] #always present

        # Two possible locations the parameter order is specified in the Touchstone file: 
        # either in the keyword lines or in the comment lines.
        if 'Two-Port Data Order' in self.meta['keyword_lines'] and self.meta['keyword_lines']['Two-Port Data Order'][0] == '12_21': #otherwise it's the default 11_22 handled below
            for i in range(self.num_ports):
                for j in range(self.num_ports):
                    for k in range(2):
                        label = f'{self.parameter_type}{i+1}{j+1} ({self.format_type[k]})'
                        labels.append(label)
            return labels
        
        for line in self.meta['comment_lines']: #For Keysight instruments.
            if 'File: Measurements:' in line:
                params = line.split(':')[-1] if line.split(':')[-1]!= '' else line.split(':')[-2]
                param_order = params.strip().upper().replace(',', '').split()
                for param in param_order:
                    for k in range(2):
                        label = f'{param} ({self.format_type[k]})'
                        labels.append(label)
                return labels

        for i in range(self.num_ports): #default order
            for j in range(self.num_ports):
                for k in range(2):
                    label = f'{self.parameter_type}{j+1}{i+1} ({self.format_type[k]})'
                    labels.append(label)
        return labels