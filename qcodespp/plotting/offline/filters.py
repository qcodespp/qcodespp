# -*- coding: utf-8 -*-
"""
Created on Thu Nov 9 20:05:23 2017

@author: Joeri de Bruijckere, Damon Carrad
"""

import numpy as np
from scipy import ndimage, signal
from scipy.interpolate import LinearNDInterpolator, CloughTocher2DInterpolator, make_interp_spline

from qcodespp.plotting.analysis_tools import sort_lists

# Filter definitions

def derivative(data, method, times_x, times_y):
    times_x, times_y = int(times_x), int(times_y)
    if len(data) == 3:
        for _ in range(times_y):
            data[-1]= np.array([np.gradient(data[-1][i,:], data[1][i,:]) for i in range(data[-1].shape[0])])
        for _ in range(times_x):
            data[-1]= np.array([np.gradient(data[-1][:,i], data[0][:,i]) for i in range(data[-1].shape[1])]).T
    elif len(data) == 2:
        for _ in range(times_y):
            data[-1] = np.gradient(data[-1], data[0])
    return data

def cumulative_sum(data, method, times_x, times_y):
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

def integrate_rectangle(x, y):
    """
    Numerically integrate y with respect to x. Should be the same as cumulative sum for regularly spaced x.
    """
    integrated_y = np.zeros_like(y)
    for i in range(1, len(y)):
        integrated_y[i] = integrated_y[i-1] + y[i] * (x[i] - x[i-1])
    return integrated_y

def integrate_trapezoid(x,y):
    """
    Numerically integrate y with respect to x using the trapezoidal rule.
    """
    integrated_y = np.zeros_like(y)
    for i in range(1,len(y)):
        integrated_y[i] = integrated_y[i-1] + (y[i] + y[i-1]) * (x[i] - x[i-1]) / 2.0
    return integrated_y

def integrate_simpson(x, y):
    """
    Numerically integrate y with respect to x using Simpson's rule.
    """
    integrated_y = np.zeros_like(y)
    for i in range(1,len(y) - 1):
        integrated_y[i] = integrated_y[i-1] + (y[i-1] + 4 * y[i] + y[i+1]) * (x[i+1] - x[i-1])/6
    # Use trapezoidal rule for the last segment
    integrated_y[-1] = integrated_y[-2] + (y[-1] + y[-2]) * (x[-1] - x[-2]) / 2.0
    
    return integrated_y


def integrate(data, method, times_x, times_y):
    times_x, times_y = int(times_x), int(times_y)
    functions={'Trapezoid': integrate_trapezoid, 'Simpson': integrate_simpson, 'Rectangle': integrate_rectangle}
    if len(data) == 3:
        for _ in range(times_x):
            data[-1] = np.array([functions[method](data[-1][:,i], data[0][:,i]) for i in range(data[-1].shape[1])]).T
        for _ in range(times_y):
            data[-1] = np.array([functions[method](data[-1][i,:], data[1][i,:]) for i in range(data[-1].shape[0])])

    elif len(data) == 2:
        for _ in range(times_y):
            data[-1] = functions[method](data[0], data[1])

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
    if len(data) == 3:
        data[0], data[1], data[-1] = data[1].T, data[0].T, data[-1].T
    elif len(data) == 2:
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
        raise ValueError(f'{setting1} is not a valid base. Use e, 10 or 2')
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

def interp2d(x, y, z, kind='linear'):
    """
    Re-do the job that scipy used to do
    """
    if kind == 'linear':
        interpolator = LinearNDInterpolator(list(zip(x,y)), z)
    elif kind == 'cubic':
        interpolator = CloughTocher2DInterpolator(list(zip(x,y)), z)
    return interpolator

def interpolate(data, method, n_x, n_y):
    n_x, n_y = int(n_x), int(n_y)
    if len(data) == 3:
        x=data[0].flatten()
        y=data[1].flatten()
        z=data[2].flatten()
        f_z = interp2d(x,y,z, kind=method)
        X, Y = np.linspace(min(x), max(x), n_x), np.linspace(min(y), max(y), n_y)
        X, Y = np.meshgrid(X, Y)
        data[2] = np.ma.masked_invalid(f_z(X,Y).T)
        data[0] = X.T
        data[1] = Y.T
    elif len(data) == 2:
        kind={'linear': 1, 'cubic': 3}
        x,y=sort_lists(data[0], data[1])
        f = make_interp_spline(x, y, kind[method])
        data[0] = np.linspace(np.min(x), np.max(x), n_x)
        data[1] = f(data[0])
    return data

def sort(data, method, setting1, setting2):
    if len(data) == 3:
        if method == 'X':
            xsort,zsort=np.zeros_like(data[-1]),np.zeros_like(data[-1])
            for i in range(data[-1].shape[1]):
                xsort[:,i],zsort[:,i]=sort_lists(data[0][:,i],data[-1][:,i])
            data=[xsort, data[1], zsort]
        elif method == 'Y':
            ysort,zsort=np.zeros_like(data[-1]),np.zeros_like(data[-1])
            for i in range(data[-1].shape[0]):
                ysort[i,:],zsort[i,:]=sort_lists(data[1][i],data[-1][i])
            data=[data[0], ysort, zsort]
    elif len(data) == 2:
        data[0], data[1] = sort_lists(data[0], data[1])
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
    DEFAULT_SETTINGS = {'Derivative': {'Method': [''],
                                       'Settings': ['0', '1'],
                                       'tooltips': ['Order in X', 'Order in Y'],
                                       'Function': derivative,
                                       'Checkstate': 2,
                                       'description': 'n-th derivative in x and/or y'},
                        'Integrate': {'Method': ['Trapezoid','Simpson','Rectangle'],
                                       'Settings': ['0', '1'],
                                       'tooltips': ['Order in X', 'Order in Y'],
                                       'Function': integrate,
                                       'Checkstate': 2,
                                       'description': 'Numerically integrate the z data (for 2D) or y data (for 1D) n times along the x or y axis.'},
                        'Cumulative sum': {'Method': ['Z','Y','X'],
                                       'Settings': ['0', '1'],
                                       'tooltips': ['Order in zero-th index', 'Order in first index'],
                                        'Function': cumulative_sum,
                                        'Checkstate': 2,
                                        'description': 'Perform the cumulative sum n times along the array axis. Similar to integrating if the grid is regular.'},
                        'Smoothen': {'Method': ['Gauss', 'Median'],
                                     'Settings': ['0', '2'],
                                     'tooltips': ['Smoothing window in X', 'Smoothing window in Y'],
                                     'Function': smooth,
                                     'Checkstate': 2,
                                     'description': 'Smoothing from scipy.ndimage.'},
                        'Savitzy-Golay smoothing': {'Method': ['Y','X','dY','dX','ddY','ddX'],
                                    'Settings': ['7', '2'],
                                    'tooltips': ['Smoothing window', 'Polynomial order'],
                                    'Function': sav_gol,
                                    'Checkstate': 2,
                                    'description': 'Savitzy-Golay smoothing/filtering applied along the selected axis'},
                        'Add/Subtract': {'Method': ['X','Y','Z'],
                                   'Settings': ['0', ''],
                                   'tooltips': ['Value'],
                                   'Function': offset,
                                   'Checkstate': 2,
                                   'description': 'Add/subtract a fixed value to any axis. To add/subtract another parameter from the same dataset, right click on the offset value. To subtract, place a \'-\' in front of the parameter name.'},
                        'Multiply': {'Method': ['X','Y','Z'],
                                     'Settings': ['1', ''],
                                     'tooltips': ['Value'],
                                     'Function': multiply,
                                     'Checkstate': 2,
                                     'description': 'X*factor. To multiply by another parameter from the same dataset, right click on the value to choose.'}, 
                        'Divide': {'Method': ['X','Y','Z'],
                                   'Settings': ['1', ''],
                                   'tooltips': ['Value'],
                                   'Function': divide,
                                   'Checkstate': 0,
                                   'description': 'X/factor. To divide by another parameter from the same dataset, right click on the value to choose.'},
                        'Add Slope': {'Method': [''],
                                  'Settings': ['0', '-1'],
                                  'tooltips': ['Slope value in X', 'Slope value in Y'],
                                  'Function': add_slope,
                                  'Checkstate': 2,
                                  'description': 'Slope is multiplied to x and/or y. Useful to e.g. subtract series resistance'},
                        'Invert': {'Method': ['X','Y','Z'],
                                   'Settings': ['', ''],
                                   'Function': invert,
                                   'Checkstate': 0,
                                   'description': 'perform 1/x, 1/y or 1/z '},
                        'Normalize': {'Method': ['Max', 'Min', 'Min to Max','Point'],
                                      'Settings': ['', ''],
                                      'tooltips': ['X coordinate', 'Y coordinate'],
                                      'Function': normalize,
                                      'Checkstate': 2,
                                      'description': 'Normalise z-data (or y-data if 1D) to min, max, or specified point'},
                        'Subtract average': {'Method': ['Z', 'Y', 'X'],
                                      'Settings': ['', ''],
                                        'Function': subtract_average,
                                        'Checkstate': 2,
                                        'description': 'Subtract average of data from data'},
                        'Offset line by line': {'Method': ['Z', 'Y'],
                                      'Settings': ['0', ''],
                                      'tooltips': ['Index'],
                                      'Function': offset_line_by_line,
                                      'Checkstate': 2,
                                      'description': 'For each line in a 2D dataset, subtract the value at the given index, within that line. Used if you know that the n-th index of each line should be zero.'},
                        'Subtract average line by line': {'Method': ['Z', 'Y'],
                                      'Settings': ['', ''],
                                        'Function': subtract_ave_line_by_line,
                                        'Checkstate': 2,
                                        'description': 'For each line in a 2D dataset, subtract the average of values in that line.'},
                        'Subtract trace': {'Method': ['Ver', 'Hor'],
                                     'Settings': ['0', ''],
                                     'tooltips': ['Index'],
                                     'Function': subtract_trace,
                                     'Checkstate': 0,
                                     'description': 'Subtract the linetrace at the given index from all other lines in the data.'},
                        'Logarithm': {'Method': ['Mask','Shift','Abs'],
                                      'Settings': ['10', ''],
                                      'tooltips': ['Base; 10, 2 or e'],
                                      'Function': logarithm,
                                      'Checkstate': 2,
                                      'description': 'logarithm to base 10, 2 or e (default 10). The Mask, Offset and Abs options deals with negative values. Mask ignores them, Offset offsets all data by the minimum value in the data, and Abs takes the absolute value of the data. Only for z data; for x,y use axis scaling below plot window'}, 
                        'Power': {'Method': ['X','Y','Z'],
                                 'Settings': ['2', ''],
                                 'tooltips': ['Exponent'],
                                 'Function': power,
                                 'Checkstate': 2,
                                 'description': 'performs x^exponent'}, 
                        'Root': {'Method': ['X','Y','Z'],
                                 'Settings': ['2', ''],
                                 'tooltips': ['Exponent'],
                                 'Function': root,
                                 'Checkstate': 2,
                                 'description': 'performs abs(x)^(1/exponent) if exponent>0'}, 
                        'Absolute': {'Method': [''],
                                     'Settings': ['', ''],
                                     'Function': absolute,
                                     'Checkstate': 2,
                                     'description': 'Absolute value of data '}, 
                        'Flip': {'Method': ['L-R','U-D'],
                                 'Settings': ['', ''],
                                 'Function': flip,
                                 'Checkstate': 2,
                                 'description': 'Flips the data along the x-axis (1D) or y-axis (2D)'}, 
                        'Interpolate': {'Method': ['linear','cubic'],
                                   'Settings': ['800', '600'],
                                   'tooltips': ['Number of points in X', 'Number of points in Y'],
                                   'Function': interpolate,
                                   'Checkstate': 0,
                                   'description': 'Interpolate onto a regular grid with the given number of points'},
                        'Sort': {'Method': ['X','Y'],
                                   'Settings': ['', ''],
                                   'Function': sort,
                                   'Checkstate': 2,
                                   'description': 'Rearranges the data such that X or Y is sorted in ascending order.'},
                        'Roll X': {'Method': ['Index'],
                                   'Settings': ['0', '0'],
                                    'tooltips': ['Position', 'Amount'],
                                   'Function': roll_x,
                                   'Checkstate': 0,
                                   'description': 'Uses numpy.roll to roll the data in x by the given amount, starting at the given position'},                             
                        'Roll Y': {'Method': ['Index'],
                                   'Settings': ['0', '0'],
                                    'tooltips': ['Position', 'Amount'],
                                   'Function': roll_y,
                                   'Checkstate': 0,
                                   'description': 'Uses numpy.roll to roll the data in y by the given amount, starting at the given position'},
                        'Crop X': {'Method': ['Abs', 'Rel', 'Lim'],
                                   'Settings': ['-1', '1'],
                                   'tooltips': ['Min', 'Max'],
                                   'Function': crop_x,
                                   'Checkstate': 0,
                                   'description': 'Not just zooming; relevant if e.g. you want to apply a filter only to a section of the data. Available also by right-clicking on the plot window'},                              
                        'Crop Y': {'Method': ['Abs', 'Rel', 'Lim'],
                                   'Settings': ['-1', '1'],
                                   'tooltips': ['Min', 'Max'],
                                   'Function': crop_y,
                                   'Checkstate': 0,
                                   'description': 'Not just zooming; relevant if e.g. you want to apply a filter only to a section of the data. Available also by right-clicking on the plot window'},
                        'Cut X': {'Method': ['Index'],
                                  'Settings': ['0', '0'],
                                    'tooltips': ['Left index', 'Width'],
                                  'Function': cut_x,
                                  'Checkstate': 0,
                                  'description': 'Crop, but uses array index, and uses min and width rather than min and max.'},                               
                        'Cut Y': {'Method': ['Index'],
                                  'Settings': ['0', '0'],
                                    'tooltips': ['Bottom index', 'Width'],
                                  'Function': cut_y,
                                  'Checkstate': 0,
                                  'description': 'Crop, but uses array index, and uses min and width rather than min and max.'},                                
                        'Swap X/Y': {'Method': [''],
                                    'Settings': ['', ''],
                                    'Function': swap_xy,
                                    'Checkstate': 2,
                                    'description': 'Swaps the x and y axes of the data, i.e. plots y as a function of x and vice versa'}, 
                                   } 
    
    def __init__(self, name, method=None, settings=None, checkstate=None, dimension=2):
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
        self.description = default_settings[name]['description']
        if 'tooltips' in default_settings[name]:
            self.tooltips = default_settings[name]['tooltips']
        