# -*- coding: utf-8 -*-
"""
Created on Wed Nov 29 21:56:57 2017

@author: Joeri de Bruijckere, Damon Carrad
"""

import numpy as np
from scipy.optimize import curve_fit
from lmfit.models import LorentzianModel, GaussianModel, ConstantModel, PowerLawModel

functions = {}
functions['Polynomials and powers'] = {'Linear': {'parameters':'no inputs'},
                        'Polynomial': {'parameters':'polynomial order'},
                        'Power law': {'parameters':'list of powers'}}
functions['Single peak'] = {'Lorentzian': {'parameters':'fwhm, height, middle'},
                'Gaussian': {'parameters':'fwhm, height, middle'},
                'Fano': {'parameters':'fwhm, height, middle, q'},
                'Frota': {'parameters':'fwhm, height, middle'}}

functions['Single peak w/background']={'Lorentzian_bg': {'parameters':'fwhm, height, middle, background'},
                'Gaussian_bg': {'parameters':'fwhm, height, middle, background'},
                'Fano_bg': {'parameters':'fwhm, height, middle, background, q'},
                'Frota_bg': {'parameters':'fwhm, height, middle, background'}} 

functions['MultiPeak'] = {'LorentzianMulti': {'parameters':'fwhm, height, # of peaks'},
                'GaussianMulti': {'parameters':'fwhm, height, # of peaks'}}

functions['MultiPeak w/background'] = {'LorentzianMulti_bg': {'parameters':'fwhm, height, # of peaks, background'},
                'GaussianMulti_bg': {'parameters':'fwhm, height, # of peaks, background'}}

def get_class_names():
    return functions.keys()

def get_function(function_class,function_name):
    return functions[function_class][function_name]['function']

def get_names(fitclass='Polynomials and powers'):
    return functions[fitclass].keys()
    
def get_parameters(function_class,function_name):
    return functions[function_class][function_name]['parameters']

def estimate_parameters(function_name, x, y):
    fwhm = 0.1*(np.amax(x)-np.amin(x))
    height = np.amax(y)-np.amin(y)
    middle = 0.5*(np.amax(x)+np.amin(x))
    if '_bg' in function_name:
        background = np.amin(y)
        estimated_parameters = [fwhm, height, middle, background]
    else:
        estimated_parameters = [fwhm, height, middle]
    if 'Fano' in function_name:
        q = 1
        estimated_parameters.append(q)
    return estimated_parameters

def fit_data(function_class,function_name, xdata, ydata, p0=None):
    f = functions[function_class][function_name]['function']
    if function_class in ['Single peak','Single peak w/background']:
        if not p0:
            p0 = estimate_parameters(function_name, xdata, ydata)
        popt, _ = curve_fit(f=f, xdata=xdata, ydata=ydata, p0=p0)
        return popt
    
    elif function_class == 'MultiPeak':
        result, components = f(xdata, ydata, numofpeaks=p0[2], amplitudes=p0[1], sigmas=p0[0])
        return result, components
    
    elif function_class == 'MultiPeak w/background':
        result, components = f(xdata, ydata, numofpeaks=p0[2], amplitudes=p0[1], sigmas=p0[0],background=p0[3])
        return result, components
    
    elif function_name == 'Linear':
        m,b = np.polyfit(xdata, ydata, 1)
        return m,b
    
    elif function_name == 'Polynomial':
        if not p0:
            order=2
        else:
            order = int(p0[0])
        coeffs = np.polyfit(xdata, ydata, order)
        return coeffs
    
    elif function_name == 'Power law':
        popt, _ = curve_fit(f=f(p0), xdata=xdata, ydata=ydata)


# Polynomials and powers
def linear(x, m, b):
    return m*x + b
functions['Polynomials and powers']['Linear']['function'] = linear

def polynomial(x, *coeffs):
    y = 0
    for i, coeff in enumerate(coeffs[::-1]):
        y += coeff*x**i
    return y
functions['Polynomials and powers']['Polynomial']['function'] = polynomial

# def fit_powerlaw(xdata,ydata, *powers):
#     power0=powers[0]
#     powers=powers[1:]
#     model=PowerLawModel(prefix='power0_')
#     params = model.make_params()
#     for i, power in enumerate(powers):
#         newmodel = PowerLawModel(prefix=f'power{i+1}_')
#         pars = newmodel.make_params()
#         model = model + newmodel
#         params.update(pars)

def lorentzian(x, fwhm, height, middle):
    y = height*(fwhm/2)**2/((x-middle)**2+(fwhm/2)**2)
    return y
functions['Single peak']['Lorentzian']['function'] = lorentzian

def gaussian(x, fwhm, height, middle):
    c = fwhm/(2*np.sqrt(2*np.log(2)))
    y = height*np.exp(-(x-middle)**2/(2*c**2))
    return y
functions['Single peak']['Gaussian']['function'] = gaussian

def fano(x, fwhm, height, middle, q):
    epsilon = 2*(x-middle)/fwhm
    y = height*(epsilon+q)**2/(1+epsilon**2)/(1+q**2)
    return y
functions['Single peak']['Fano']['function'] = fano

def frota(x, fwhm, height, middle):
    y = height*np.real(np.sqrt(1j*(fwhm/2)/((x-middle)+1j*(fwhm/2))))
    return y
functions['Single peak']['Frota']['function'] = frota

def lorentzian_bg(x, fwhm, height, middle, background):
    y = height*(fwhm/2)**2/((x-middle)**2+(fwhm/2)**2) + background
    return y
functions['Single peak w/background']['Lorentzian_bg']['function'] = lorentzian_bg

def gaussian_bg(x, fwhm, height, middle, background):
    c = fwhm/(2*np.sqrt(2*np.log(2)))
    y = height*np.exp(-(x-middle)**2/(2*c**2)) + background
    return y
functions['Single peak w/background']['Gaussian_bg']['function'] = gaussian_bg

def fano_bg(x, fwhm, height, middle, background, q):
    epsilon = 2*(x-middle)/fwhm
    y = height*(epsilon+q)**2/(1+epsilon**2)/(1+q**2) + background
    return y
functions['Single peak w/background']['Fano_bg']['function'] = fano_bg

def frota_bg(x, fwhm, height, middle, background):
    y = height*np.real(np.sqrt(1j*(fwhm/2)/((x-middle)+1j*(fwhm/2)))) + background
    return y
functions['Single peak w/background']['Frota_bg']['function'] = frota_bg


#MultiPeak fitting
def fit_lorentzians(xdata,ydata,numofpeaks=None,
                    amplitudes=None,sigmas=None,background=None):
    #Fits x,y data with lorentzian functions using 'rough_peak_positions' as initial guess positions.
    #One can instead provide the number of peaks, and the fitter will start with an initial guess of evenly spaced peaks.
    #numofpeaks is ignored if rough_peak_positions provided
    #If necessary, the range of the data can be limited, in units of the x data.
    #Custom starting amplitudes (proportional to height) and sigmas (proportional to width) may also be given
    #Returns parameters for each of the peaks fitted, 'peak0' to 'peakN' where N is the number of peaks in rough_peak_positions
    #If savefig set to True, saves the figure with plotname, which should include the filetype.

    if xdata[0]>xdata[-1]:
        xdata=xdata[::-1]
        ydata=ydata[::-1]
    
    peakspacing=(xdata.max()-xdata.min())/numofpeaks
    rough_peak_positions=[i*peakspacing+peakspacing/2+xdata.min() for i in range(int(numofpeaks))]
        #print(rough_peak_positions)

    if amplitudes==None or amplitudes==0: #Guess that the amplitudes will be close to the maximum value of the data
        amplitudes=np.max(ydata)
    if sigmas==None or sigmas==0: #Sigma = FWHM/2, so sigma should be roughly a fourth of the peak spacing. May be much less if peaks not overlapping
        sigmas=np.abs(xdata[-1]-xdata[0])/(4*numofpeaks)

    peakpos0=rough_peak_positions[0]
    peakpositions=rough_peak_positions[1:]
    
    def add_peak(prefix, center, amplitude=amplitudes, sigma=sigmas):
        peak = LorentzianModel(prefix=prefix)
        pars = peak.make_params()
        pars[prefix + 'center'].set(center)
        pars[prefix + 'amplitude'].set(amplitude, min=0)
        pars[prefix + 'sigma'].set(sigma, min=0)
        return peak, pars

    model = LorentzianModel(prefix='peak0_')
    params = model.make_params()
    params['peak0_center'].set(peakpos0)
    params['peak0_amplitude'].set(amplitudes, min=0)
    params['peak0_sigma'].set(sigmas, min=0)

    for i, cen in enumerate(peakpositions):
        peak, pars = add_peak('peak%d_' % (i+1), cen)
        model = model + peak
        params.update(pars)

    if background is not None:
        if background==0:
            background = ydata.min()
        bg = ConstantModel(prefix='bg_')
        pars = bg.make_params()
        pars['bg_c'].set(background)
        model = model + bg
        params.update(pars)

    init = model.eval(params, x=xdata)
    result = model.fit(ydata, params, x=xdata)
    components = result.eval_components()
    return(result, components)
functions['MultiPeak']['LorentzianMulti']['function'] = fit_lorentzians
functions['MultiPeak w/background']['LorentzianMulti_bg']['function'] = fit_lorentzians

def fit_gaussians(xdata,ydata,numofpeaks=None,
                    amplitudes=None,sigmas=None,background=None):
   
    #Fits x,y data with lorentzian functions using 'rough_peak_positions' as initial guess positions.
    #One can instead provide the number of peaks, and the fitter will start with an initial guess of evenly spaced peaks.
    #numofpeaks is ignored if rough_peak_positions provided
    #If necessary, the range of the data can be limited, in units of the x data.
    #Custom starting amplitudes (proportional to height) and sigmas (proportional to width) may also be given
    #Returns parameters for each of the peaks fitted, 'peak0' to 'peakN' where N is the number of peaks in rough_peak_positions
    #If savefig set to True, saves the figure with plotname, which should include the filetype.

    if xdata[0]>xdata[-1]:
        xdata=xdata[::-1]
        ydata=ydata[::-1]

    peakspacing=(xdata.max()-xdata.min())/numofpeaks
    rough_peak_positions=[i*peakspacing+peakspacing/2+xdata.min() for i in range(int(numofpeaks))]

    if amplitudes==None or amplitudes==0: #Guess that the amplitudes will be close to the maximum value of the data
        amplitudes=ydata.max()
    if sigmas==None or sigmas==0: #Sigma = FWHM/2, so sigma should be roughly a fourth of the peak spacing. May be much less if peaks not overlapping
        sigmas=np.abs(xdata[-1]-xdata[0])/(4*numofpeaks)
        
    peakpos0=rough_peak_positions[0]
    peakpositions=rough_peak_positions[1:]
    
    def add_peak(prefix, center, amplitude=amplitudes, sigma=sigmas):
        peak = GaussianModel(prefix=prefix)
        pars = peak.make_params()
        pars[prefix + 'center'].set(center)
        pars[prefix + 'amplitude'].set(amplitude, min=0)
        pars[prefix + 'sigma'].set(sigma, min=0)
        return peak, pars

    model = LorentzianModel(prefix='peak0_')
    params = model.make_params()
    params['peak0_center'].set(peakpos0)
    params['peak0_amplitude'].set(amplitudes, min=0)
    params['peak0_sigma'].set(sigmas, min=0)

    for i, cen in enumerate(peakpositions):
        peak, pars = add_peak('peak%d_' % (i+1), cen)
        model = model + peak
        params.update(pars)

    if background is not None:
        if background==0:
            background = ydata.min()
        bg = ConstantModel(prefix='bg_')
        pars = bg.make_params()
        pars['bg_c'].set(background)
        model = model + bg
        params.update(pars)

    init = model.eval(params, x=xdata)
    result = model.fit(ydata, params, x=xdata)
    components = result.eval_components()
    return(result, components)

functions['MultiPeak']['GaussianMulti']['function'] = fit_gaussians
functions['MultiPeak w/background']['GaussianMulti_bg']['function'] = fit_gaussians