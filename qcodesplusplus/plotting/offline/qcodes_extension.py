# -*- coding: utf-8 -*-
"""
Inspectra-Gadget - QCoDes functionality

Author: Joeri de Bruijckere

Last updated on Nov 11 2020

"""

from PyQt5 import QtWidgets
import numpy as np
import qcodesplusplus.plotting.offline.main as main

class QCodesData(main.BaseClassData):
    def __init__(self, filepath, canvas, dataset):
        super().__init__(filepath, canvas)
        self.dataset = dataset
        self.label = (f'Run #{dataset.captured_run_id} {dataset.exp_name}' 
                      f'({dataset.sample_name}) {dataset.run_timestamp()}')
        
    def get_column_data(self):
        dependent_par = self.dataset.dependent_parameters[0]
        data_dict = self.dataset.get_parameter_data(dependent_par)[dependent_par]
        pars = list(data_dict.keys())
        if len(pars) == 2: # file is 2D
            column_data = np.column_stack((data_dict[pars[1]], 
                                           data_dict[pars[0]]))
        else: # file is 3D
            column_data = np.column_stack((data_dict[pars[1]], 
                                           data_dict[pars[2]], 
                                           data_dict[pars[0]]))
        return column_data

    def add_extension_actions(self, editor, menu):
        channel_menu = menu.addMenu('Select channel...')
        for par in self.dependent_parameters:
            action = QtWidgets.QAction(par, editor)
            channel_menu.addAction(action) 
        menu.addSeparator()
        
    def do_extension_actions(self, editor, signal):
        if signal.text() in self.dependent_parameters:
            self.index_dependent_parameter = self.dependent_parameters.index(signal.text())
            self.refresh_data()
            editor.update_plots()
            editor.show_current_all()