# -*- coding: utf-8 -*-
"""
Created on Wed Nov 29 21:56:57 2017

@author: Joeri de Bruijckere, Damon Carrad
"""

import numpy as np
from lmfit import models as lmm
from functools import partial

# Dictionary for storing info about the fit functions used in this module.
functions = {}
functions['Polynomials and powers'] = {'Linear': {},
                                    'Polynomial': {'inputs':'order', 
                                                'default_inputs' : '2'
                                                },
                                    'Power law': {'inputs':'# of terms, use offset',
                                                'default_inputs': '1,0',
                                                'parameters': 'a_0,b_0,...,a_n,b_n,c'
                                                },
                                    'Exponentials': {'inputs':'# of terms, use offset',
                                                'default_inputs': '1,0',
                                                'parameters': 'a_0,b_0,...,a_n,b_n,c'
                                                }
                                    }

# Give descriptions to help the user.
functions['Polynomials and powers']['Linear']['description'] = 'Simple linear y = mx + b fit'
functions['Polynomials and powers']['Polynomial']['description'] = ('Polynomial fit of order n, y = a_n*x^n + ... + a_1*x + a_0.\n'
                                                                    'Provide n, the polynomial order.')
functions['Polynomials and powers']['Power law']['description'] = ('Power law fit of the form y = a_0*x^b_0 + ... + a_n*x^b_n + c.\n'
                                                                    'Provide inputs n,c, where n is the number of terms to include '
                                                                    'and c is whether to include a constant offset; c=0: no offset, c=1: offset')
functions['Polynomials and powers']['Exponentials']['description'] = ('Exponential fit of the form y = a_0*exp(-x/b_0) + ... + a_n*exp(-x/b_n) + c.\n'
                                                                    'Provide inputs n,c, where n is the number of terms to include '
                                                                    'and c is whether to include a constant offset; c=0: no offset, c=1: offset')

# Add simple peaks that take amplitude, width and position as only arguments.
functions['Peaks: 3 param']={}
multipeak_description= ('Fit one or more {} peaks. The inputs are n,c, where n is the number of peaks and c is whether to '
                        'include a constant offset in the fit. c=0 --> no offset, c=1 --> Offset.\n'
                        'For exmaple, inputs of 4,0 will fit four peaks without a constant offset.\n'
                        'By default, the fit assumes equally spaced peaks with heights approximately the max value of the data.\n'
                        'To change this, provide an initial guess of the form {}\n'
                        'If providing an intial guess, you must provide '
                        'all parameters for all peaks.')
lorgaussform=('w1 ... wn, a1 ... an, x1 ... xn, c where w = peak fwhm, a = peak height, '
                        'x = peak position and c = constant offset value (if used). For example:\n'
                        '0.01 0.014 0.005, 1.1 1.05 1.2, -0.1 0 0.1\n'
                        'for three peaks with no constant offset, and\n'
                        '0.01 0.014 0.005, 1.1 1.05 1.2, -0.1 0 0.1,5\n'
                        'for three peaks with a large constant offset of 5.\n')

for peaktype in ['Lorentzian','Gaussian','Lognormal','StudentsT','DampedOscillator']:
    functions['Peaks: 3 param'][peaktype] = {}
    functions['Peaks: 3 param'][peaktype]['inputs']='# of peaks, use offset'
    functions['Peaks: 3 param'][peaktype]['default_inputs']='1,0'
    functions['Peaks: 3 param'][peaktype]['parameters']='fwhm(s), height(s), position(s), y_offset'
    functions['Peaks: 3 param'][peaktype]['description'] = multipeak_description.format(peaktype,lorgaussform)

functions['Peaks: 4 param']={}
fourparamform=('w1 ... wn, a1 ... an, x1 ... xn, g1 ... gn, c where w = peak fwhm, a = peak height, '
                        'x = peak position, g = gamma (see lmfit documentation for meaning in each case) '
                        'and c = constant offset value (if used). For example:\n'
                        '0.01 0.014 0.005, 1.1 1.05 1.2, -0.1 0 0.1, 0.001 0.001 0.001\n'
                        'for three peaks with no constant offset, and\n'
                        '0.01 0.014 0.005, 1.1 1.05 1.2, -0.1 0 0.1, 0.001 0.001 0.001,5\n'
                        'for three peaks with a large constant offset of 5.\n')

for peaktype in ['Voigt','PseudoVoigt','BreitWigner/Fano','SplitLorentzian','ExpGaussian','SkewedGaussian','Moffat','Pearson7','DampedHarmOsc','Doniach']:
    functions['Peaks: 4 param'][peaktype] = {}
    functions['Peaks: 4 param'][peaktype]['inputs']='# of peaks, use offset'
    functions['Peaks: 4 param'][peaktype]['default_inputs']='1,0'
    functions['Peaks: 4 param'][peaktype]['parameters']='fwhm(s), height(s), position(s), gammas(s), y_offset'
    functions['Peaks: 4 param'][peaktype]['description'] = multipeak_description.format(peaktype,fourparamform)

#Wrap the ExpressionModel to allow arbitrary input.
functions['User input']={'Expression':{}}
functions['User input']['Expression']['inputs'] = 'Expression'
functions['User input']['Expression']['parameters'] = 'all fit parameters'
functions['User input']['Expression']['description'] =('Fit an arbitrary expression. Input any function you like. '
                                            'x must be the independent variable. e.g.\n'
                                            'C + A * exp(-x/x0) * sin(x*phase)\n'
                                            'You must also provide initial guesses for each parameter in the form:\n'
                                            'C=0.25, A=1.0, x0=2.0, phase=0.04')

# functions to return different parts of the functions dictionary. Makes it easier to call in main
def get_class_names():
    return functions.keys()

def get_function(function_class,function_name):
    return functions[function_class][function_name]['function']

def get_names(fitclass='Polynomials and powers'):
    return functions[fitclass].keys()
    
def get_parameters(function_class,function_name):
    return functions[function_class][function_name]['parameters']

def get_description(function_class,function_name):
    return functions[function_class][function_name]['description']

# Entry point for fitting the data. Passes info along to relevant functions and returns the fit result
def fit_data(function_class,function_name, xdata, ydata, p0=None, inputinfo=None):

    # all fit functions get called through the dictionary
    f = functions[function_class][function_name]['function']
    result = f(xdata,ydata,p0,inputinfo)
    return result


# The rest of this code is the definition of the actual fit functions, and referencing them from the functions dictionary

# Polynomials and powers
def linear(xdata,ydata,p0,inputinfo):
    model=lmm.LinearModel()
    params=model.guess(ydata, x=xdata)
    result = model.fit(ydata, params, x=xdata)
    return result
functions['Polynomials and powers']['Linear']['function'] = linear

def polynomial(xdata,ydata,p0,inputinfo):
    degree = int(inputinfo[0]) or int(inputinfo)
    model=lmm.PolynomialModel(degree=degree)
    params=model.guess(ydata, x=xdata)
    result = model.fit(ydata, params, x=xdata)
    return result
functions['Polynomials and powers']['Polynomial']['function'] = polynomial

def fit_powerlaw(xdata,ydata, p0,inputinfo):
    if p0:
        p0 = [float(par) for par in p0]
    order=inputinfo[0]
    constant=inputinfo[1]

    model= lmm.PowerLawModel(prefix='power0_')
    params = model.make_params()
    for i in range(int(order-1)):
        newmodel = lmm.PowerLawModel(prefix=f'power{i+1}_')
        pars = newmodel.make_params()
        model = model + newmodel
        params.update(pars)
    if constant !=0:
        bg = lmm.ConstantModel(prefix='bg_')
        pars = bg.make_params()
        pars['bg_c'].set(constant)
        model = model + bg
        params.update(pars)

    init = model.eval(params, x=xdata)
    result = model.fit(ydata, params, x=xdata)
    #components = result.eval_components()
    return result
functions['Polynomials and powers']['Power law']['function'] = fit_powerlaw

def fit_exponentials(xdata,ydata, p0,inputinfo):
    if p0:
        p0 = [float(par) for par in p0]
    order=inputinfo[0]
    constant=inputinfo[1]

    model= lmm.ExponentialModel(prefix='term0_')
    params = model.make_params()
    for i in range(int(order-1)):
        newmodel = lmm.ExponentialModel(prefix=f'term{i+1}_')
        pars = newmodel.make_params()
        model = model + newmodel
        params.update(pars)
    if constant !=0:
        bg = lmm.ConstantModel(prefix='bg_')
        pars = bg.make_params()
        pars['bg_c'].set(constant)
        model = model + bg
        params.update(pars)

    init = model.eval(params, x=xdata)
    result = model.fit(ydata, params, x=xdata)
    #components = result.eval_components()
    return result
functions['Polynomials and powers']['Exponentials']['function'] = fit_exponentials

#Peak fitting
def fit_lorgausstype(modeltype,xdata,ydata,p0,inputinfo):
    #Fits x,y data with peaks characterised by amplitude, fwhm and position.
    #Custom starting amplitudes (proportional to height) and sigmas (proportional to width) may also be given
    #Returns the entire lmfit result.
    numofpeaks=inputinfo[0]
    usebackground=inputinfo[1]
    sigmas=None
    amplitudes=None

    if xdata[0]>xdata[-1]:
        xdata=xdata[::-1]
        ydata=ydata[::-1]
    
    peakspacing=(xdata.max()-xdata.min())/numofpeaks
    rough_peak_positions=[i*peakspacing+peakspacing/2+xdata.min() for i in range(int(numofpeaks))]

    if p0: #Format should be list of strings: ['w w ... w','a a ... a','x x ... x','c']
        sigmas=[float(par) for par in p0[0].split()]
        amplitudes=[float(par) for par in p0[1].split()]
        rough_peak_positions=[float(par) for par in p0[2].split()]
    if usebackground==1:
        try:
            background=p0[3]
        except:
            background=0
    else:
        background=None

    if amplitudes ==None: #Guess that the amplitudes will be close to the maximum value of the data
        amplitudes=[ydata.max()-ydata.min() for i in range(int(numofpeaks))]
    if sigmas==None: #Sigma will be much smaller than the peak spacing unless peaks are overlapping. However, starting with a low value seems to work even if overlapping, but not the other way around.
        sigmas=[np.abs(xdata[-1]-xdata[0])/(12*numofpeaks) for i in range(int(numofpeaks))]

    peakpos0=rough_peak_positions[0]
    peakpositions=rough_peak_positions[1:]
    
    def add_peak(prefix, center, amplitude, sigma):
        peak = modeltype(prefix=prefix)
        pars = peak.make_params()
        pars[prefix + 'center'].set(center)
        pars[prefix + 'amplitude'].set(amplitude)
        pars[prefix + 'sigma'].set(sigma, min=0)
        return peak, pars

    model = modeltype(prefix='peak0_')
    params = model.make_params()
    params['peak0_center'].set(peakpos0)
    params['peak0_amplitude'].set(amplitudes[0])
    params['peak0_sigma'].set(sigmas[0], min=0)

    for i, cen in enumerate(peakpositions):
        peak, pars = add_peak('peak%d_' % (i+1), cen, amplitudes[i+1], sigmas[i+1])
        model = model + peak
        params.update(pars)

    if background is not None:
        bg = lmm.ConstantModel(prefix='bg_')
        pars = bg.make_params()
        pars['bg_c'].set(background)
        model = model + bg
        params.update(pars)

    init = model.eval(params, x=xdata)
    result = model.fit(ydata, params, x=xdata)
    return result

# Any lmfit built-in function taking only amplitude, sigma and position can use the above function.
functions['Peaks: 3 param']['Lorentzian']['function'] = partial(fit_lorgausstype, lmm.LorentzianModel)
functions['Peaks: 3 param']['Gaussian']['function'] = partial(fit_lorgausstype,lmm.GaussianModel)
functions['Peaks: 3 param']['StudentsT']['function'] = partial(fit_lorgausstype,lmm.StudentsTModel)
functions['Peaks: 3 param']['Lognormal']['function'] = partial(fit_lorgausstype,lmm.LognormalModel)
functions['Peaks: 3 param']['DampedOscillator']['function'] = partial(fit_lorgausstype,lmm.DampedOscillatorModel)

# Function for lmfit peaks with four parameters.
def fit_voigttype(modeltype,xdata,ydata,p0,inputinfo):
    #Fits x,y data with peaks characterised by amplitude, fwhm and position.
    #Custom starting amplitudes (proportional to height) and sigmas (proportional to width) may also be given
    #Returns the entire lmfit result.
    fourthparamdict={'SplitLorentzianModel':'sigma_r',
                'PseudoVoigtModel':'fraction',
                'MoffatModel':'beta',
                'Pearson7Model':'exponent',
                'BreitWignerModel':'q'}
    if modeltype.__name__ in fourthparamdict.keys():
        fourthparam=fourthparamdict[modeltype.__name__]
    else:
        fourthparam='gamma'

    numofpeaks=inputinfo[0]
    usebackground=inputinfo[1]
    sigmas=None
    amplitudes=None
    gammas=None

    if xdata[0]>xdata[-1]:
        xdata=xdata[::-1]
        ydata=ydata[::-1]
    
    peakspacing=(xdata.max()-xdata.min())/numofpeaks
    rough_peak_positions=[i*peakspacing+peakspacing/2+xdata.min() for i in range(int(numofpeaks))]

    if p0: #Format should be list of strings: ['w w ... w','a a ... a','x x ... x','c']
        sigmas=[float(par) for par in p0[0].split()]
        amplitudes=[float(par) for par in p0[1].split()]
        rough_peak_positions=[float(par) for par in p0[2].split()]
        gammas=[float(par) for par in p0[3].split()]
    if usebackground==1:
        try:
            background=p0[4]
        except:
            background=0
    else:
        background=None

    if amplitudes ==None: #Guess that the amplitudes will be close to the maximum value of the data
        amplitudes=[ydata.max()-ydata.min() for i in range(int(numofpeaks))]
    if sigmas==None: #Sigma will be much smaller than the peak spacing unless peaks are overlapping. However, starting with a low value seems to work even if overlapping, but not the other way around.
        sigmas=[np.abs(xdata[-1]-xdata[0])/(12*numofpeaks) for i in range(int(numofpeaks))]
    if gammas==None: #God I have no idea
        gammas=[0 for i in range(int(numofpeaks))]

    peakpos0=rough_peak_positions[0]
    peakpositions=rough_peak_positions[1:]
    
    def add_peak(prefix, center, amplitude, sigma,gamma):
        peak = modeltype(prefix=prefix)
        pars = peak.make_params()
        pars[prefix + 'center'].set(center)
        pars[prefix + 'amplitude'].set(amplitude)
        pars[prefix + 'sigma'].set(sigma, min=0)
        pars[prefix + fourthparam].set(gamma)
        return peak, pars

    model = modeltype(prefix='peak0_')
    params = model.make_params()
    params['peak0_center'].set(peakpos0)
    params['peak0_amplitude'].set(amplitudes[0])
    params['peak0_sigma'].set(sigmas[0], min=0)
    params['peak0_'+fourthparam].set(gammas[0])

    for i, cen in enumerate(peakpositions):
        peak, pars = add_peak('peak%d_' % (i+1), cen, amplitudes[i+1], sigmas[i+1], gammas[i+1])
        model = model + peak
        params.update(pars)

    if background is not None:
        bg = lmm.ConstantModel(prefix='bg_')
        pars = bg.make_params()
        pars['bg_c'].set(background)
        model = model + bg
        params.update(pars)

    init = model.eval(params, x=xdata)
    result = model.fit(ydata, params, x=xdata)
    return result

functions['Peaks: 4 param']['Voigt']['function'] = partial(fit_voigttype, lmm.VoigtModel)
functions['Peaks: 4 param']['PseudoVoigt']['function'] = partial(fit_voigttype, lmm.PseudoVoigtModel)
functions['Peaks: 4 param']['BreitWigner/Fano']['function'] = partial(fit_voigttype, lmm.BreitWignerModel)
functions['Peaks: 4 param']['SplitLorentzian']['function'] = partial(fit_voigttype, lmm.SplitLorentzianModel)
functions['Peaks: 4 param']['ExpGaussian']['function'] = partial(fit_voigttype, lmm.ExponentialGaussianModel)
functions['Peaks: 4 param']['SkewedGaussian']['function'] = partial(fit_voigttype, lmm.SkewedGaussianModel)
functions['Peaks: 4 param']['Moffat']['function'] = partial(fit_voigttype, lmm.MoffatModel)
functions['Peaks: 4 param']['Pearson7']['function'] = partial(fit_voigttype, lmm.Pearson7Model)
functions['Peaks: 4 param']['DampedHarmOsc']['function'] = partial(fit_voigttype, lmm.DampedHarmonicOscillatorModel)
functions['Peaks: 4 param']['Doniach']['function'] = partial(fit_voigttype, lmm.DoniachModel)

def expression_fit(xdata,ydata,p0,inputinfo):
    #Fit an arbitrary function given in inputinfo. 
    #Initial guesses for parameters are given in p0 in a string form. This needs to be decoded.
    model=lmm.ExpressionModel(inputinfo)
    params=model.make_params()
    for i,whatever in enumerate(p0):
        params[whatever.split('=')[0].strip()].set(value=float(whatever.split('=')[1]))
    init=model.eval(params,x=xdata)
    result=model.fit(ydata,params,x=xdata)
    return result

functions['User input']['Expression']['function']=expression_fit