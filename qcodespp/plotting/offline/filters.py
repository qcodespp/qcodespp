# -*- coding: utf-8 -*-
"""
Created on Thu Nov 9 20:05:23 2017

@author: Joeri de Bruijckere, Damon Carrad
"""

import numpy as np
from scipy import ndimage, signal
from scipy.interpolate import interp1d, interp2d


# Filter definitions

def derivative(data, method, times_x, times_y):
    times_x, times_y = int(times_x), int(times_y)
    if len(data) == 3:
        for _ in range(times_x):
            data[-1] = np.gradient(data[-1], data[0][:,0], axis=0)
        for _ in range(times_y):
            data[-1] = np.gradient(data[-1], data[1][0,:], axis=1)
    elif len(data) == 2:
        for _ in range(times_y):
            data[-1] = np.gradient(data[-1], data[0])        
    return data

def integrate(data, method, times_x, times_y):
    times_x, times_y = int(times_x), int(times_y)
    if len(data) == 3:
        if method=='Z':
            for _ in range(times_x):
                data[-1] = np.cumsum(data[-1], axis=0)
            for _ in range(times_y):
                data[-1] = np.cumsum(data[-1], axis=1)
        elif method=='Y':
            for _ in range(times_y):
                data[1] = np.cumsum(data[1], axis=1)
        elif method=='X':
            for _ in range(times_x):
                data[0] = np.cumsum(data[0], axis=0)
    elif len(data) == 2:
        if method in ['Y','Z']:
            for _ in range(times_y):
                data[-1] = np.cumsum(data[-1])
        elif method == 'X':
            for _ in range(times_x):
                data[0] = np.cumsum(data[0])
    
    return data    
        
def smooth(data, method, width_x, width_y):
    filters = {'Gauss': ndimage.gaussian_filter, 
               'Median': ndimage.median_filter}
    filters1d = {'Gauss': ndimage.gaussian_filter1d}

    if method == 'Gauss':
        width_x, width_y = float(width_x), float(width_y)
    elif method == 'Median':
        width_x, width_y = int(np.ceil(float(width_x)))+1, int(np.ceil(float(width_y)))+1
    if len(data) == 3:
        if width_x:
            if width_y:
                data[-1] = filters[method](data[-1], [width_x, width_y])
            else:
                data[-1] = filters1d[method](data[-1], width_x, axis=0)
        else:
            if width_y:
                data[-1] = filters1d[method](data[-1], width_y, axis=1)
    elif len(data) == 2:
        if width_y:
            data[-1] = filters1d[method](data[-1], width_y)
    return data

def sav_gol(data, method, window_length, polyorder):
    polyorder = int(polyorder)
    window_length = int(window_length)
    if window_length < polyorder:
        window_length = polyorder + 1
    if window_length % 2 == 0:
        window_length += 1
    if 'Y' in method:
        axis = 1
    elif 'X' in method:
        axis = 0
    deriv = method.count('d')
    if len(data) == 3:
        data[-1] = signal.savgol_filter(data[-1], window_length, polyorder, 
                                        deriv=deriv, axis=axis)       
        for _ in range(deriv):
            data[-1] /= np.gradient(data[axis], axis=axis)
    elif len(data) == 2:
        data[-1] = signal.savgol_filter(data[-1], window_length, polyorder, 
                                        deriv=deriv)
        for _ in range(deriv): 
            data[-1] /= np.gradient(data[0])
    return data

def crop_x(data, method, left, right):
    if method != 'Lim':
        min_data = np.min(data[0])
        max_data = np.max(data[0])
        left, right = float(left), float(right)
        if (left < right and max_data > left and min_data < right):
            if method == 'Abs':
                mask = ((data[0] < left) | (data[0] > right))
            elif method == 'Rel':
                mask = (((data[0] >= min_data) & (data[0] <= min_data + abs(left))) |
                        ((data[0] <= max_data) & (data[0] >= max_data - abs(right))))
            if len(data) == 3:
                for i in [1,2,0]:
                    data[i] = np.ma.compress_rowcols(np.ma.masked_array(data[i], mask=mask), axis=0)
            elif len(data) == 2:
                for i in [1,0]:
                    data[i] = np.ma.masked_array(data[i], mask=mask)
    return data
  
def crop_y(data, method, bottom, top):
    if len(data) == 3 and method != 'Lim':
        min_data = np.min(data[1])
        max_data = np.max(data[1])
        bottom, top = float(bottom), float(top)
        if (bottom < top and max_data > bottom and min_data < top):
            for i in [0,2,1]:
                if method == 'Abs':
                    mask = ((data[1] < bottom) | (data[1] > top))
                elif method == 'Rel':
                    mask = (((data[1] >= min_data) & (data[1] <= min_data + abs(bottom))) |
                            ((data[1] <= max_data) & (data[1] >= max_data - abs(top))))   
                data[i] = np.ma.compress_rowcols(
                        np.ma.masked_array(data[i], mask=mask), axis=1)
    return data

def roll_x(data, method, position, amount):
    if len(data) == 3:
        amount = int(amount)
        position = int(position)
        data[2][:,position:] = np.roll(data[2][:,position:], shift=amount, axis=0)
    return data

def roll_y(data, method, position, amount):
    if len(data) == 3:
        amount = int(amount)
        position = int(position)
        data[2][position:,:] = np.roll(data[2][position:,:], shift=amount, axis=1)
    return data

def cut_x(data, method, left, width):
    if len(data) == 3:
        left, width = int(left), int(width)
        part1 = data[-1][:left,:]
        part2 = data[-1][left:left+width,:]
        part3 = data[-1][left+width:,:]
        data[-1] = np.vstack((part1,part3,part2))
    return data

def cut_y(data, method, bottom, width):
    if len(data) == 3:
        bottom, width = int(bottom), int(width)
        part1 = data[-1][:,:bottom]
        part2 = data[-1][:,bottom:bottom+width]
        part3 = data[-1][:,bottom+width:]
        data[-1] = np.hstack((part1,part3,part2))
    return data 

def swap_xy(data, method, setting1, setting2):
    data[0], data[1] = data[1], data[0]
    return data

def flip(data, method, setting1, setting2):
    if method == 'U-D':
        data[-1] = np.fliplr(data[-1])
    elif method == 'L-R':
        data[-1] = np.flipud(data[-1])
    return data

def normalize(data, method, point_x, point_y):
    if method == 'Max': 
        norm_value = np.max(data[-1])
    elif method == 'Min':
        norm_value = np.min(data[-1])    
    elif method == 'Point' and len(data) == 3:
        x_index = np.argmin(np.abs(data[0][:,0] - float(point_x)))
        y_index = np.argmin(np.abs(data[1][0,:] - float(point_y)))
        norm_value = data[-1][x_index,y_index]
    elif method == 'Point' and len(data) == 2:
        x_index = np.argmin(np.abs(data[0] - float(point_x)))
        norm_value = data[-1][x_index]
    elif method == 'Min to Max':
        norm_value = np.max(data[-1]) - np.min(data[-1])
        data[-1] = data[-1]-np.min(data[-1])
    data[-1] = data[-1] / norm_value
    return data

def subtract_average(data, method, setting1, setting2):
    shape=np.shape(data[-1])
    if method == 'Z':
        average=np.average(data[-1])
        for i in range(shape[0]):
            data[-1][i] = data[-1][i]-average
    elif method == 'Y':
        average=np.average(data[1])
        for i in range(shape[0]):
            data[1][i] = data[1][i]-average
    elif method == 'X':
        average=np.average(data[0])
        for i in range(shape[0]):
            data[0][i] = data[0][i]-average
    return data

def offset_line_by_line(data,method,index,setting2):
    index=int(index)
    if len(data) == 3:
        shape=np.shape(data[-1])
        if method=='Z':
            newdata=np.zeros_like(data[-1])
            for i in range(shape[0]):
                for j in range(shape[1]):
                    newdata[i][j]=data[-1][i][j]-data[-1][i][index]
            data[-1]=newdata
        elif method=='Y':
            newdata=np.zeros_like(data[-1])
            for i in range(shape[0]):
                for j in range(shape[1]):
                    newdata[i][j]=data[1][i][j]-data[1][i][index]
            data[1]=newdata
    else:
        print('Cannot offset 1D data line by line. Use regular offset')

    return data

def subtract_ave_line_by_line(data,method,setting1,setting2):
    if len(data) == 3:
        shape=np.shape(data[-1])
        if method=='Z':
            newdata=np.zeros_like(data[-1])
            for i in range(shape[0]):
                average=np.average(data[-1][i])
                for j in range(shape[1]):
                    newdata[i][j]=data[-1][i][j]-average
            data[-1]=newdata
        elif method=='Y':
            newdata=np.zeros_like(data[-1])
            for i in range(shape[0]):
                average=np.average(data[1][i])
                for j in range(shape[1]):
                    newdata[i][j]=data[1][i][j]
            data[1]=newdata
    else:
        print('Cannot subtract average from 1D data line by line. Use subract average')

    return data

def offset(data, method, setting1, setting2, array=None):
    axis = {'X': 0, 'Y': 1, 'Z': 2}
    if array is not None:
        if len(data) == 3:
            if setting2=='+':
                data[axis[method]] += array
            else:
                data[axis[method]] = np.subtract(data[axis[method]],array) 
        elif len(data) == 2 and axis[method] < 2:
            if setting2=='+':
                data[axis[method]] += array
            else:
                data[axis[method]] = np.subtract(data[axis[method]],array)
    else:
        value=float(setting1)
        if len(data) == 3:
            for i,row in enumerate(data[axis[method]]):
                for j,val in enumerate(row):
                    data[axis[method]][i][j] += value
        elif len(data) == 2 and axis[method] < 2:
            for j,val in enumerate(data[axis[method]]):
                data[axis[method]][j] += value
    return data
    
def absolute(data, method, setting1, setting2):
    data[-1] = np.absolute(data[-1])
    return data
    
# def multiply(data, method, setting1, setting2):
#     if setting1 == 'e^2/h':
#         value = 0.025974
#     else:
#         value = float(setting1)
    
#     axis = {'X': 0, 'Y': 1, 'Z': 2}
#     if len(data) == 3:
#         data[axis[method]] *= value
#     elif len(data) == 2 and axis[method] < 2:
#         data[axis[method]] *= value
#     return data

def multiply(data, method, setting1, setting2, array=None):
    axis = {'X': 0, 'Y': 1, 'Z': 2}
    if array is not None:
        if len(data) == 3:
            data[axis[method]] *= array
        elif len(data) == 2 and axis[method] < 2:
            data[axis[method]] *= array

    else:
        if setting1 == 'e^2/h':
            value = 0.025974
        else:
            value = float(setting1)
    
        if len(data) == 3:
            for i,row in enumerate(data[axis[method]]):
                for j,val in enumerate(row):
                    data[axis[method]][i][j] *= value
        elif len(data) == 2 and axis[method] < 2:
            for j,val in enumerate(data[axis[method]]):
                data[axis[method]][j] *= value
    return data

# def divide(data, method, setting1, setting2):
#     axis = {'X': 0, 'Y': 1, 'Z': 2}
#     if len(data) == 3:
#         data[axis[method]] /= float(setting1)
#     elif len(data) == 2 and axis[method] < 2:
#         data[axis[method]] /= float(setting1)
#     return data

def divide(data, method, setting1, setting2, array=None):
    axis = {'X': 0, 'Y': 1, 'Z': 2}
    if array is not None:
        if len(data) == 3:
            data[axis[method]] /= array
        elif len(data) == 2 and axis[method] < 2:
            data[axis[method]] /= array

    else:
        value=float(setting1)
        if len(data) == 3:
            for i,row in enumerate(data[axis[method]]):
                for j,val in enumerate(row):
                    data[axis[method]][i][j] /= value
        elif len(data) == 2 and axis[method] < 2:
            for j,val in enumerate(data[axis[method]]):
                data[axis[method]][j] /= value
    return data


def logarithm(data, method, setting1=10, setting2=None):
    if setting1 == 'e':
        function = np.ma.log
    elif setting1 == '10':
        function = np.ma.log10
    elif setting1 == '2':
        function = np.ma.log2
    else:
        print('Setting 1 is not a valid base. Use e, 10 or 2')
    if method == 'Mask':
        data[-1] = function(data[-1])        
    elif method == 'Shift':
        min_value = np.amin(data[-1])
        if min_value <= 0.0:
            data[-1] = function(data[-1]-min_value)
        else:
            data[-1] = function(data[-1])
    elif method == 'Abs':
        data[-1] = function(np.abs(data[-1]))
    return data

def power(data, method, setting1, setting2):
    axis = {'X': 0, 'Y': 1, 'Z': 2}
    value=float(setting1)
    if len(data) == 3:
        for i,row in enumerate(data[axis[method]]):
            for j,val in enumerate(row):
                data[axis[method]][i][j] = data[axis[method]][i][j]**value
    elif len(data) == 2 and axis[method] < 2:
        for j,val in enumerate(data[axis[method]]):
            data[axis[method]][j] = data[axis[method]][j]**value
    return data

def root(data, method, setting1, setting2):
    root = float(setting1)
    axis = {'X': 0, 'Y': 1, 'Z': 2}
    if root > 0:
        if len(data) == 3:
            for i,row in enumerate(data[axis[method]]):
                for j,val in enumerate(row):
                    data[axis[method]][i][j] = np.abs(data[axis[method]][i][j])**(1/root)
        elif len(data) == 2 and axis[method] < 2:
            for j,val in enumerate(data[axis[method]]):
                data[axis[method]][j] = np.abs(data[axis[method]][j])**(1/float(setting1))
    return data

def interpolate(data, method, n_x, n_y):
    if len(data) == 3:
        x, y = data[0][:,0], data[1][0,:]
        f_z = interp2d(y, x, data[2], kind=method)
        n_x, n_y = int(n_x), int(n_y)
        min_x, max_x = np.amin(data[0]), np.amax(data[0]) 
        min_y, max_y = np.amin(data[1]), np.amax(data[1])
        yp, xp = np.linspace(min_y, max_y, n_y), np.linspace(min_x, max_x, n_x)
        data[1], data[0] = np.meshgrid(yp, xp)
        data[2] = f_z(yp, xp)
    elif len(data) == 2:
        f = interp1d(data[0], data[1], kind=method)
        n_x = int(n_x)
        min_x, max_x = np.amin(data[0]), np.amax(data[0]) 
        data[0] = np.linspace(min_x, max_x, n_x)
        data[1] = f(data[0])
    return data
    
def add_slope(data, method, a_x, a_y):
    if len(data) == 3:
        a_x, a_y = float(a_x), float(a_y)
        data[-1] += a_x*data[0] + a_y*data[1]
    elif len(data) == 2:
        a_y = float(a_y)
        data[-1] += a_y*data[0]
    return data    
                
def subtract_trace(data, method, index, setting2):
    if len(data) == 3:
        index = int(float(index))
        if method == 'Hor':
            data[-1] -= np.tile(data[-1][:,index], (len(data[-1][0,:]),1)).T
        elif method == 'Ver':
            data[-1] -= np.tile(data[-1][index,:], (len(data[-1][:,0]),1))
    return data

def invert(data, method, setting1, setting2):
    axis = {'X': 0, 'Y': 1, 'Z': -1}
    data[axis[method]] = 1./data[axis[method]]
    return data
        
        
class Filter:   
    DEFAULT_SETTINGS = {'Derivative': {'Method': ['Mid'],
                                       'Settings': ['0', '1'],
                                       'Function': derivative,
                                       'Checkstate': 2},
                        'Integrate': {'Method': ['Z','Y','X'],
                                       'Settings': ['0', '1'],
                                       'Function': integrate,
                                       'Checkstate': 2},
                        'Smoothen': {'Method': ['Gauss', 'Median'],
                                     'Settings': ['0', '2'],
                                     'Function': smooth,
                                     'Checkstate': 2},
                        'Savitzy-Golay smoothing': {'Method': ['Y','X','dY','dX','ddY','ddX'],
                                    'Settings': ['7', '2'],
                                    'Function': sav_gol,
                                    'Checkstate': 2},                               
                        'Add/Subtract': {'Method': ['X','Y','Z'],
                                   'Settings': ['0', ''],
                                   'Function': offset,
                                   'Checkstate': 2},
                        'Multiply': {'Method': ['X','Y','Z'],
                                     'Settings': ['1', ''],
                                     'Function': multiply,
                                     'Checkstate': 2}, 
                        'Divide': {'Method': ['X','Y','Z'],
                                   'Settings': ['1', ''],
                                   'Function': divide,
                                   'Checkstate': 0},
                        'Add Slope': {'Method': [''],
                                  'Settings': ['0', '-1'],
                                  'Function': add_slope,
                                  'Checkstate': 2},
                        'Invert': {'Method': ['X','Y','Z'],
                                   'Settings': ['', ''],
                                   'Function': invert,
                                   'Checkstate': 0},
                        'Normalize': {'Method': ['Max', 'Min', 'Min to Max','Point'],
                                      'Settings': ['', ''],
                                      'Function': normalize,
                                      'Checkstate': 2},
                        'Subtract average': {'Method': ['Z', 'Y', 'X'],
                                      'Settings': ['', ''],
                                        'Function': subtract_average,
                                        'Checkstate': 2},
                        'Offset line by line': {'Method': ['Z', 'Y'],
                                      'Settings': ['', ''],
                                      'Function': offset_line_by_line,
                                      'Checkstate': 2},
                        'Subtract average line by line': {'Method': ['Z', 'Y'],
                                      'Settings': ['', ''],
                                        'Function': subtract_ave_line_by_line,
                                        'Checkstate': 2},
                        'Subtract trace': {'Method': ['Ver', 'Hor'],
                                     'Settings': ['0', ''],
                                     'Function': subtract_trace,
                                     'Checkstate': 0},
                        'Logarithm': {'Method': ['Mask','Shift','Abs'],
                                      'Settings': ['10', ''],
                                      'Function': logarithm,
                                      'Checkstate': 2}, 
                        'Power': {'Method': ['X','Y','Z'],
                                 'Settings': ['2', ''],
                                 'Function': power,
                                 'Checkstate': 2}, 
                        'Root': {'Method': ['X','Y','Z'],
                                 'Settings': ['2', ''],
                                 'Function': root,
                                 'Checkstate': 2}, 
                        'Absolute': {'Method': [''],
                                     'Settings': ['', ''],
                                     'Function': absolute,
                                     'Checkstate': 2}, 
                        'Flip': {'Method': ['L-R','U-D'],
                                 'Settings': ['', ''],
                                 'Function': flip,
                                 'Checkstate': 2}, 
                        'Interp': {'Method': ['linear','cubic','quintic'],
                                   'Settings': ['800', '600'],
                                   'Function': interpolate,
                                   'Checkstate': 0},
                        'Roll X': {'Method': ['Index'],
                                   'Settings': ['0', '0'],
                                   'Function': roll_x,
                                   'Checkstate': 0},                             
                        'Roll Y': {'Method': ['Index'],
                                   'Settings': ['0', '0'],
                                   'Function': roll_y,
                                   'Checkstate': 0},
                        'Crop X': {'Method': ['Abs', 'Rel', 'Lim'],
                                   'Settings': ['-1', '1'],
                                   'Function': crop_x,
                                   'Checkstate': 0},                              
                        'Crop Y': {'Method': ['Abs', 'Rel', 'Lim'],
                                   'Settings': ['-2', '2'],
                                   'Function': crop_y,
                                   'Checkstate': 0},
                        'Cut X': {'Method': ['Index'],
                                  'Settings': ['0', '0'],
                                  'Function': cut_x,
                                  'Checkstate': 0},                               
                        'Cut Y': {'Method': ['Index'],
                                  'Settings': ['0', '0'],
                                  'Function': cut_y,
                                  'Checkstate': 0},                                
                        'Swap X/Y': {'Method': [''],
                                    'Settings': ['', ''],
                                    'Function': swap_xy,
                                    'Checkstate': 2}, 
                                   } 
    
    def __init__(self, name, method=None, settings=None, checkstate=None):
        self.name = name
        default_settings = self.DEFAULT_SETTINGS.copy()
        self.method_list = default_settings[name]['Method']
        if method:
            self.method = method
        else:
            self.method = self.method_list[0]
        if settings:
            self.settings = settings
        else:
            self.settings = default_settings[name]['Settings']
        if checkstate:
            self.checkstate = checkstate
        else:
            self.checkstate = default_settings[name]['Checkstate']
        self.function = default_settings[name]['Function']
        