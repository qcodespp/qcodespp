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
                        'for three peaks with a constant offset of 5.\n')

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
                        'for three peaks with a constant offset of 5.\n')

for peaktype in ['Voigt','PseudoVoigt','BreitWigner/Fano','SplitLorentzian','ExpGaussian','SkewedGaussian','Moffat','Pearson7','DampedHarmOsc','Doniach']:
    functions['Peaks: 4 param'][peaktype] = {}
    functions['Peaks: 4 param'][peaktype]['inputs']='# of peaks, use offset'
    functions['Peaks: 4 param'][peaktype]['default_inputs']='1,0'
    functions['Peaks: 4 param'][peaktype]['parameters']='fwhm(s), height(s), position(s), gammas(s), y_offset'
    functions['Peaks: 4 param'][peaktype]['description'] = multipeak_description.format(peaktype,fourparamform)

functions['Peaks: skewed']={}
fiveparamform=('w1 ... wn, a1 ... an, x1 ... xn, g1 ... gn, s1 ... sn, c where w = peak fwhm, a = peak height, '
                        'x = peak position, g = gamma (see lmfit documentation for meaning in each case), '
                        's = skew and c = constant offset value (if used). For example:\n'
                        '0.01 0.014 0.005, 1.1 1.05 1.2, -0.1 0 0.1, 0.001 0.001 0.001, 0.1 0.12 0.14\n'
                        'for three peaks with no constant offset, and\n'
                        '0.01 0.014 0.005, 1.1 1.05 1.2, -0.1 0 0.1, 0.001 0.001 0.001, 0.1 0.12 0.14, 5\n'
                        'for three peaks with a constant offset of 5.\n')
for peaktype in ['Pearson4','SkewedVoigt']:
    functions['Peaks: skewed'][peaktype] = {}
    functions['Peaks: skewed'][peaktype]['inputs']='# of peaks, use offset'
    functions['Peaks: skewed'][peaktype]['default_inputs']='1,0'
    functions['Peaks: skewed'][peaktype]['parameters']='fwhm(s), height(s), position(s), gammas(s), skews(s), y_offset'
    functions['Peaks: skewed'][peaktype]['description'] = multipeak_description.format(peaktype,fiveparamform)

# Oscillating
functions['Oscillating']={'Sine':{}
                        # 'Sine w/exp decay':{},
                        # 'Sine w/power decay':{}
                        }
functions['Oscillating']['Sine']['inputs']='# of waves, use offset'
functions['Oscillating']['Sine']['default_inputs']='1,0'
functions['Oscillating']['Sine']['parameters']='Amplitude(s), frequency(ies), phase(s), offset'
functions['Oscillating']['Sine']['description']=('Fit a sine wave A*sin(f*x+phase) with optional + c if use offset == 1.\n'
                                                'Specify # of waves > 1 to fit A_1*sin(f_1*x+ph_1) + ... + A_n*sin(f_n*x+ph_n) + c.\n'
                                                'Initial guesses for more than one wave take the form\n'
                                                'A_1 ... A_n, f_1 ... f_n, ph_1 ... ph_n, c\n'
                                                'e.g., for three waves:\n'
                                                '0.01 0.014 0.005, 1.1 1.05 1.2, -0.1 0 0.1, 0.001 0.001 0.001,5\n')


# Thermal distributions
functions['Thermal']={'Maxwell':{'fullname':'Maxwell-Boltzmann', 'equation':'1/A*exp((x-x0)/kT)'},
                    'Fermi':{'fullname':'Fermi-Dirac', 'equation':'1/[A*exp((x-x0)/kT)+1]'},
                    'Bose':{'fullname':'Bose-Einstein', 'equation':'1/[A*exp((x-x0)/kT)-1]'},
                    }

thermaldescription=('Fit to a {} distribution: y = {}. kT is considered a single fit parameter. Initial guesses '
                    'for kT should be in units of x, usually either eV or J.')
for key in functions['Thermal'].keys():
    functions['Thermal'][key]['parameters']=['A, x0, kT']
    functions['Thermal'][key]['description']=thermaldescription.format(functions['Thermal'][key]['fullname'], functions['Thermal'][key]['equation'])

#Step functions
functions['Step']={'Linear':{},'Arctan':{},'ErrorFunction':{},'Logistic':{}}
stepdescription=('Fit a single step function of type {} (see lmfit documentation for information). \n'
                'The step function starts at 0 and ends with value +/- A. '
                'The x-value where y=A/2 is given by x0, and sigma is the characteristic width of the step.\n'
                'Use an offset filter on the data in the main panel to ensure your data starts at y=0.')
for key in functions['Step'].keys():
    functions['Step'][key]['parameters']=['A, x0, sigma']
    functions['Step'][key]['description']=stepdescription.format(key)

#Rectangle functions
functions['Rectangle']={'Linear':{},'Arctan':{},'ErrorFunction':{},'Logistic':{}}
rectdescription=('Fit a rectangle function of type {} (see lmfit documentation for information). \n'
                'A rectangle function steps from 0 to +/- A, then back to 0. '
                'The x-values where y=A/2 are given by x0_1, x0_2, and sigma_1 and sigma_2 are the characteristic widths of the steps.\n'
                'Use an offset filter on the data in the main panel to ensure your data starts at y=0.')
for key in functions['Rectangle'].keys():
    functions['Rectangle'][key]['parameters']=['A, x0_1, x0_2, sigma_1, sigma_2']
    functions['Rectangle'][key]['description']=rectdescription.format(key)

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

    if p0:
        for i,key in enumerate(params.keys()):
            params[key].set(float(p0[i]))
    else:
        for key in params.keys():
            if 'amplitude' in key:
                params[key].set(ydata.max()-ydata.min())
            elif 'expo' in key:
                params[key].set(1)

    result = model.fit(ydata, params, x=xdata)
    #components = result.eval_components()
    return result
functions['Polynomials and powers']['Power law']['function'] = fit_powerlaw

def fit_exponentials(xdata,ydata, p0,inputinfo):
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

    if p0:
        for i,key in enumerate(params.keys()):
            params[key].set(float(p0[i]))

    else:
        amplitudes=ydata.max()-ydata.min()
        decays=xdata.max()-xdata.min()
        #more or less. Beats negative infinity.
        for key in params.keys():
            if 'amplitude' in key:
                params[key].set(amplitudes)
            elif 'decay' in key:
                params[key].set(decays)

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
                'Pearson7Model':'expon',
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

# Function for lmfit peaks with five parameters.
def fit_skewedpeaks(modeltype,xdata,ydata,p0,inputinfo):
    #Fits x,y data with peaks characterised by amplitude, fwhm and position.
    #Custom starting amplitudes (proportional to height) and sigmas (proportional to width) may also be given
    #Returns the entire lmfit result.
    fourthparamdict={'Pearson4Model':'expon'}
    if modeltype.__name__ in fourthparamdict.keys():
        fourthparam=fourthparamdict[modeltype.__name__]
    else:
        fourthparam='gamma'
    #Fifth parameter is always 'skew'

    numofpeaks=inputinfo[0]
    usebackground=inputinfo[1]
    sigmas=None
    amplitudes=None
    gammas=None
    skews=None

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
        skews=[float(par) for par in p0[4].split()]
    if usebackground==1:
        try:
            background=p0[5]
        except:
            background=0
    else:
        background=None

    if amplitudes ==None: #Guess that the amplitudes will be close to the maximum value of the data
        amplitudes=[ydata.max()-ydata.min() for i in range(int(numofpeaks))]
    if sigmas==None: #Sigma will be much smaller than the peak spacing unless peaks are overlapping. However, starting with a low value seems to work even if overlapping, but not the other way around.
        sigmas=[np.abs(xdata[-1]-xdata[0])/(12*numofpeaks) for i in range(int(numofpeaks))]
    if gammas==None:
        gammas=[0 for i in range(int(numofpeaks))]
    if skews==None:
        skews=[1 for i in range(int(numofpeaks))]

    peakpos0=rough_peak_positions[0]
    peakpositions=rough_peak_positions[1:]
    
    def add_peak(prefix, center, amplitude, sigma,gamma,skew):
        peak = modeltype(prefix=prefix)
        pars = peak.make_params()
        pars[prefix + 'center'].set(center)
        pars[prefix + 'amplitude'].set(amplitude)
        pars[prefix + 'sigma'].set(sigma, min=0)
        pars[prefix + fourthparam].set(gamma)
        pars[prefix + 'skew'].set(skew)
        return peak, pars

    model = modeltype(prefix='peak0_')
    params = model.make_params()
    params['peak0_center'].set(peakpos0)
    params['peak0_amplitude'].set(amplitudes[0])
    params['peak0_sigma'].set(sigmas[0], min=0)
    params['peak0_'+fourthparam].set(gammas[0])
    params['peak0_skew'].set(skews[0])

    for i, cen in enumerate(peakpositions):
        peak, pars = add_peak('peak%d_' % (i+1), cen, amplitudes[i+1], sigmas[i+1], gammas[i+1],skews[i+1])
        model = model + peak
        params.update(pars)

    if background is not None:
        bg = lmm.ConstantModel(prefix='bg_')
        pars = bg.make_params()
        pars['bg_c'].set(background)
        model = model + bg
        params.update(pars)

    result = model.fit(ydata, params, x=xdata)
    return result

functions['Peaks: skewed']['Pearson4']['function'] = partial(fit_skewedpeaks, lmm.Pearson4Model)
functions['Peaks: skewed']['SkewedVoigt']['function'] = partial(fit_skewedpeaks,lmm.SkewedVoigtModel)

#Multiple sine wave fitting
def fit_sines(xdata,ydata,p0,inputinfo):
    modeltype=lmm.SineModel
    #Fits x,y data with peaks characterised by amplitude, fwhm and position.
    #Custom starting amplitudes (proportional to height) and sigmas (proportional to width) may also be given
    #Returns the entire lmfit result.
    numofwaves=inputinfo[0]
    usebackground=inputinfo[1]
    amps=None
    freqs=None
    phases=None

    if xdata[0]>xdata[-1]:
        xdata=xdata[::-1]
        ydata=ydata[::-1]

    if p0: #Format should be list of strings: ['A A ... A','f f ... f','ph ph ... ph','c']
        amps=[float(par) for par in p0[0].split()]
        freqs=[float(par) for par in p0[1].split()]
        phases=[float(par) for par in p0[2].split()]
    if usebackground==1:
        try:
            background=p0[3]
        except:
            background=0
    else:
        background=None

    if amps ==None: #Guess that the amplitudes will be close to the maximum minus minimum
        amps=[ydata.max()-ydata.min() for i in range(int(numofwaves))]
    if freqs==None: #Guess that the user probably provides somewhere between 1 and 20 periods for fitting.
        freqs=[10/np.abs(xdata[-1]-xdata[0]) for i in range(int(numofwaves))]
    if phases==None: # The phases (surely?!) just have to be something sensible in units of radians
        phases=[0.1 for i in range(int(numofwaves))]
    
    def add_wave(prefix, amplitude, frequency, phase):
        wave = modeltype(prefix=prefix)
        pars = wave.make_params()
        pars[prefix + 'amplitude'].set(amplitude)
        pars[prefix + 'frequency'].set(frequency)
        pars[prefix + 'shift'].set(phase)
        return wave, pars

    model = modeltype(prefix='wave0_')
    params = model.make_params()
    params['wave0_amplitude'].set(amps[0])
    params['wave0_frequency'].set(freqs[0])
    params['wave0_shift'].set(phases[0])

    new_amps=amps[1:]

    for i, amp in enumerate(new_amps):
        wave, pars = add_wave('wave%d_' % (i+1), amp, freqs[i+1], phases[i+1])
        model = model + wave
        params.update(pars)

    if background is not None:
        bg = lmm.ConstantModel(prefix='bg_')
        pars = bg.make_params()
        pars['bg_c'].set(background)
        model = model + bg
        params.update(pars)

    result = model.fit(ydata, params, x=xdata)
    return result
functions['Oscillating']['Sine']['function']=fit_sines

#Fit a thermal distribution of MB, FD or BE type.
def thermal_fit(modeltype,xdata,ydata,p0,inputinfo):
    model=lmm.ThermalDistributionModel(form=modeltype)
    
    if p0:
        params=model.make_params()
        for i,key in enumerate(params.keys()):
            params[key]=float(p0[i])
    else:
        params=model.guess(ydata,x=xdata)
    result=model.fit(ydata,params,x=xdata)
    return result

functions['Thermal']['Maxwell']['function'] = partial(thermal_fit, 'maxwell')
functions['Thermal']['Bose']['function'] = partial(thermal_fit, 'bose')
functions['Thermal']['Fermi']['function'] = partial(thermal_fit, 'fermi')

#Fit a step function.
def step_fit(modeltype,xdata,ydata,p0,inputinfo):
    if xdata[0]>xdata[-1]:
        xdata=xdata[::-1]
        ydata=ydata[::-1]
    model=lmm.StepModel(form=modeltype)
    params=model.make_params()
    if p0:
        for i,key in enumerate(params.keys()):
            params[key]=float(p0[i])
    else:
        if ydata[-1]>ydata[0]:
            params['amplitude'].set(ydata.max())
        else:
            params['amplitude'].set(ydata.min())
        params['center'].set((xdata[0]+xdata[-1])/2)
        params['sigma'].set((xdata[-1]-xdata[0])/10)

    result=model.fit(ydata,params,x=xdata)
    return result

functions['Step']['Linear']['function'] = partial(step_fit, 'linear')
functions['Step']['Arctan']['function'] = partial(step_fit, 'arctan')
functions['Step']['ErrorFunction']['function'] = partial(step_fit, 'erf')
functions['Step']['Logistic']['function'] = partial(step_fit, 'logistic')

#Fit a rectangle function.
def rectangle_fit(modeltype,xdata,ydata,p0,inputinfo):
    if xdata[0]>xdata[-1]:
        xdata=xdata[::-1]
        ydata=ydata[::-1]
    model=lmm.RectangleModel(form=modeltype)
    params=model.make_params()
    if p0:
        for i,key in enumerate(params.keys()):
            params[key]=float(p0[i])
    else:
        if ydata[-1]>ydata[0]:
            params['amplitude'].set(ydata.max())
        else:
            params['amplitude'].set(ydata.min())
        params['center1'].set((3*xdata[0]+xdata[-1])/4)
        params['center2'].set((xdata[0]+3*xdata[-1])/4)
        params['sigma1'].set((xdata[-1]-xdata[0])/20)
        params['sigma2'].set((xdata[-1]-xdata[0])/20)

    result=model.fit(ydata,params,x=xdata)
    return result

functions['Rectangle']['Linear']['function'] = partial(rectangle_fit, 'linear')
functions['Rectangle']['Arctan']['function'] = partial(rectangle_fit, 'arctan')
functions['Rectangle']['ErrorFunction']['function'] = partial(rectangle_fit, 'erf')
functions['Rectangle']['Logistic']['function'] = partial(rectangle_fit, 'logistic')

# Arbitrary expressions get fitted using the below:
def expression_fit(xdata,ydata,p0,inputinfo):
    #Fit an arbitrary function given in inputinfo. 
    #Initial guesses for parameters are given in p0 in a string form.
    model=lmm.ExpressionModel(inputinfo)
    params=model.make_params()
    for i,whatever in enumerate(p0):
        params[whatever.split('=')[0].strip()].set(value=float(whatever.split('=')[1]))

    result=model.fit(ydata,params,x=xdata)
    return result

functions['User input']['Expression']['function']=expression_fit