# -*- coding: utf-8 -*-
"""
Created on Wed Nov 29 21:56:57 2017

@author: Joeri de Bruijckere
"""

import numpy as np
from scipy.optimize import curve_fit

def get_names(parameters=None):
    functions = {'Lorentzian': 'fwhm, height, middle, background', 
                 'Gaussian': 'fwhm, height, middle, background',
                 'Fano': 'fwhm, height, middle, background, q',
                 'Frota': 'fwhm, height, middle, background'}
    if parameters:
        return functions[parameters]
    else:
        return functions.keys()

def get_function(function_name):
    functions = {'Lorentzian': lorentzian, 'Gaussian': gaussian,
                 'Fano': fano, 'Frota': frota}
    return functions[function_name]

def estimate_parameters(function_name, x, y):
    fwhm = 0.1*(np.amax(x)-np.amin(x))
    height = np.amax(y)-np.amin(y)
    middle = 0.5*(np.amax(x)+np.amin(x))
    background = np.amin(y)
    estimated_parameters = [fwhm, height, middle, background]
    if function_name == 'Fano':
        q = 1
        estimated_parameters.append(q)
    return estimated_parameters

def fit_data(function_name, xdata, ydata, p0=None):
    f = get_function(function_name)
    if not p0:
        p0 = estimate_parameters(function_name, xdata, ydata)
    popt, _ = curve_fit(f=f, xdata=xdata, ydata=ydata, p0=p0)
    return popt
    
def lorentzian(x, fwhm, height, middle, background):
    y = height*(fwhm/2)**2/((x-middle)**2+(fwhm/2)**2) + background
    return y

def gaussian(x, fwhm, height, middle, background):
    c = fwhm/(2*np.sqrt(2*np.log(2)))
    y = height*np.exp(-(x-middle)**2/(2*c**2)) + background
    return y

def fano(x, fwhm, height, middle, background, q):
    epsilon = 2*(x-middle)/fwhm
    y = height*(epsilon+q)**2/(1+epsilon**2)/(1+q**2) + background
    return y

def frota(x, fwhm, height, middle, background):
    y = height*np.real(np.sqrt(1j*(fwhm/2)/((x-middle)+1j*(fwhm/2)))) + background
    return y
    