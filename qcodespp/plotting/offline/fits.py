import numpy as np
from lmfit import models as lmm
from lmfit import Model
from functools import partial

# Fit functions

# Polynomials and powers
def linear(xdata,ydata,p0,inputinfo):
    model=lmm.LinearModel()
    params=model.guess(ydata, x=xdata)
    result = model.fit(ydata, params, x=xdata)
    return result

def polynomial(xdata,ydata,p0,inputinfo):
    degree = int(inputinfo[0]) or int(inputinfo)
    model=lmm.PolynomialModel(degree=degree)
    params=model.guess(ydata, x=xdata)
    result = model.fit(ydata, params, x=xdata)
    return result

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
    return result

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
    return result


#Peak fitting
def fit_lorgausstype(modeltype,xdata,ydata,p0,inputinfo):
    #Fits x,y data with peaks characterised by amplitude, fwhm and position.
    #Custom starting amplitudes (proportional to height) and sigmas (proportional to width) may also be given
    #Returns the entire lmfit result.
    numofpeaks=inputinfo[0]
    usebackground=inputinfo[1]
    sigmas=None
    amplitudes=None

    # if xdata[0]>xdata[-1]:
    #     xdata=xdata[::-1]
    #     ydata=ydata[::-1]
    
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

    if sigmas==None: #Sigma will be much smaller than the peak spacing unless peaks are overlapping. However, starting with a low value seems to work even if overlapping, but not the other way around.
        sigmas=[np.abs(xdata[-1]-xdata[0])/(12*numofpeaks) for i in range(int(numofpeaks))]
    if amplitudes ==None: #Guess that the height will be close to the maximum value of the data: calculate amplitude based on gaussian.
        height=ydata.max()-ydata.min()
        amp=height*sigmas[0]*np.sqrt(2*np.pi)
        # but to be honest i get better results just using the height...doesn't make sense but whatever
        amplitudes=[height for i in range(int(numofpeaks))]

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

    # if xdata[0]>xdata[-1]:
    #     xdata=xdata[::-1]
    #     ydata=ydata[::-1]
    #     flipped=True
    # else:
    #     flipped=False
    
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

    # if xdata[0]>xdata[-1]:
    #     xdata=xdata[::-1]
    #     ydata=ydata[::-1]
    
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

    # if xdata[0]>xdata[-1]:
    #     xdata=xdata[::-1]
    #     ydata=ydata[::-1]

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


#Fit a step function.
def step_fit(modeltype,xdata,ydata,p0,inputinfo):
    # if xdata[0]>xdata[-1]:
    #     xdata=xdata[::-1]
    #     ydata=ydata[::-1]
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

#Fit a rectangle function.
def rectangle_fit(modeltype,xdata,ydata,p0,inputinfo):
    # if xdata[0]>xdata[-1]:
    #     xdata=xdata[::-1]
    #     ydata=ydata[::-1]
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

#Custom fits
def QD_fit(xdata,ydata,p0,inputinfo):
    numofpeaks=inputinfo[0]
    alpha=inputinfo[1]
    G0s=None
    
    if p0: #Format should be list of strings: ['x0 x0 ... x0','G0 G0 ... G0','T']
        rough_peak_positions=[float(par) for par in p0[0].split()]
        G0s=[float(par) for par in p0[1].split()]
        T=[float(p0[2])]
    else:
        peakspacing=(xdata.max()-xdata.min())/numofpeaks
        rough_peak_positions=[i*peakspacing+peakspacing/2+xdata.min() for i in range(int(numofpeaks))]
        G0s=[ydata.max()-ydata.min() for i in range(int(numofpeaks))]
        T=0.01
    
    boltzmann = 1.38064852e-23  # J/K
    def QD_model(x, x0, G0, T):
        return G0 * np.cosh(1.60217663e-19*alpha * (x - x0) / (2 * boltzmann * T))**(-2)
    model=Model(QD_model,prefix='peak0_')
    params=model.make_params()

    params['peak0_G0'].set(value=G0s[0])
    params['peak0_T'].set(value=T)
    params['peak0_x0'].set(value=rough_peak_positions[0])

    def add_peak(prefix, x0, G0, T):
        peak = Model(QD_model,prefix=prefix)
        pars = peak.make_params()
        pars[prefix + 'x0'].set(x0)
        pars[prefix + 'G0'].set(G0)
        pars[prefix + 'T'].set(T)
        return peak, pars
    
    for i, cen in enumerate(rough_peak_positions[1:]):
        peak, pars = add_peak('peak%d_' % (i+1), cen, G0s[i+1], T)
        model = model + peak
        params.update(pars)

    result=model.fit(ydata,params,x=xdata)
    return result

def FET_mobility(xdata,ydata,p0,inputinfo):
    C=float(inputinfo[0])
    L=float(inputinfo[1])
    def FET_model(x, mu, V_th, R_s):
        return 1/(R_s + L**2/(C*mu*(x-V_th)))
    model=Model(FET_model)
    params=model.make_params()
    if p0:
        params['mu'].set(value=float(p0[0]))
        params['V_th'].set(value=float(p0[1]))
        params['R_s'].set(value=float(p0[2]))
    else:
        params['mu'].set(L**2*(ydata.max()-ydata.min())/(C*(xdata.max()-xdata.min())))
        params['V_th'].set(xdata.min())
        params['R_s'].set(1/ydata.max())

    result=model.fit(ydata,params,x=xdata)
    return result

def dynes_fit(xdata,ydata,p0,inputinfo):
    electron=1.60217663e-19
    def dynes_model(x, G_N, gamma, delta):
        return np.abs(G_N*((electron*x-1j*gamma*electron)/np.sqrt((electron*x-1j*gamma*electron)**2-(delta*electron)**2)).real)
    model=Model(dynes_model)
    params=model.make_params()
    if p0:
        params['G_N'].set(value=float(p0[0]))
        params['gamma'].set(value=float(p0[1]))
        params['delta'].set(value=float(p0[2]))
    else:
        params['G_N'].set(value=(ydata.max()-ydata.min())/2)
        params['gamma'].set(value=(xdata.max()-xdata.min())/200)
        params['delta'].set(value=(xdata.max()-xdata.min())/2)
    result=model.fit(ydata,params,x=xdata)
    return result

def ramsey_fit(xdata,ydata,p0,inputinfo):
    def ramsey_model(x, A, B, C, f, phi, T2):
        return A*np.cos(2*np.pi*f*x + phi)*np.exp(-x/T2)+B+C*x
    
    model=Model(ramsey_model)
    params=model.make_params()
    if p0:
        params['A'].set(value=float(p0[0]))
        params['B'].set(value=float(p0[1]))
        params['C'].set(value=float(p0[2]))
        params['f'].set(value=float(p0[3]))
        params['phi'].set(value=float(p0[4]))
        params['T2'].set(value=float(p0[5]))
    else:
        params['A'].set(value=(ydata.max()-ydata.min())/2)
        params['B'].set(value=ydata.min())
        params['C'].set(value=(ydata.max()-ydata.min())/100)
        params['f'].set(value=1/(xdata.max()-xdata.min()))
        params['phi'].set(value=0)
        params['T2'].set(value=(xdata.max()-xdata.min())/10)

    result=model.fit(ydata,params,x=xdata)
    return result

def statistics(xdata,ydata,p0,inputinfo):
    # Not really fitting; just returns the statistical information specified in inputinfo.
    if 'percentile' in inputinfo:
        percentiles=[float(p0[i]) for i in range(len(p0))] if p0 else [1,5,10,25,50,75,90,95,99]
    elif 'average' in inputinfo:
        weights=[float(p0[i]) for i in range(len(p0))] if p0 else None
    elif inputinfo == 'all':
        percentiles=[1,5,10,25,50,75,90,95,99]
        weights=None
    
    function_dict={
        'mean':np.mean,
        'average':lambda x: np.average(x,weights=weights),
        'std':np.std,
        'var':np.var,
        'median':np.median,
        'min':np.min,
        'max':np.max,
        'range':lambda x: np.max(x)-np.min(x),
        'sum':np.sum,
        'skew':lambda x: np.mean((x-np.mean(x))**3)/np.std(x)**3,
        'percentile':lambda x: np.percentile(x,percentiles),
        'autocorrelation': lambda x: np.correlate(x,x,mode='full')[len(x)-1:],
        'autocorrelation_norm': lambda x: np.correlate(x,x,mode='full')[len(x)-1:]/np.max(np.correlate(x,x,mode='full'))
    }

    result={}
    if inputinfo == 'all':
        functions=function_dict.keys()
    elif inputinfo == 'all1d':
        functions=['mean','std','var','median','min','max','range','sum','skew']
    else:
        functions=inputinfo.split(',')
    for function in functions:
        if function not in ['percentile','autocorrelation','autocorrelation_norm']:
            result[function]=float(function_dict[function](ydata))
        else:
            if function == 'percentile':
                result[function]=function_dict[function](ydata)
                result['percentiles']=percentiles
            else:
                result[function]=function_dict[function](ydata)
    result['xdata']=xdata
    result['ydata']=ydata
    return result


# Dictionary for storing info about the fit functions used in this module.
functions = {}
functions['Polynomials and powers'] = {'Linear': {'function': linear},
                                    'Polynomial': {'inputs':'order', 
                                                'default_inputs' : '2',
                                                'function': polynomial},
                                    'Power law': {'inputs':'# of terms, use offset',
                                                'default_inputs': '1,0',
                                                'parameters': 'a_0,b_0,...,a_n,b_n,c',
                                                'function': fit_powerlaw},
                                    'Exponentials': {'inputs':'# of terms, use offset',
                                                'default_inputs': '1,0',
                                                'parameters': 'a_0,b_0,...,a_n,b_n,c',
                                                'function': fit_exponentials}
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
lorgaussform=('w1 ... wn, a1 ... an, x1 ... xn, c where w = peak sigma a = peak amplitude, '
                        'x = peak position and c = constant offset value (if used). For example:\n'
                        '0.01 0.014 0.005, 1.1 1.05 1.2, -0.1 0 0.1\n'
                        'for three peaks with no constant offset, and\n'
                        '0.01 0.014 0.005, 1.1 1.05 1.2, -0.1 0 0.1,5\n'
                        'for three peaks with a constant offset of 5.\n')

for peaktype in ['Lorentzian','Gaussian','Lognormal','StudentsT','DampedOscillator']:
    functions['Peaks: 3 param'][peaktype] = {}
    functions['Peaks: 3 param'][peaktype]['inputs']='# of peaks, use offset'
    functions['Peaks: 3 param'][peaktype]['default_inputs']='1,0'
    functions['Peaks: 3 param'][peaktype]['parameters']='sigma(s), amplitudes(s), position(s), y_offset'
    functions['Peaks: 3 param'][peaktype]['description'] = multipeak_description.format(peaktype,lorgaussform)
functions['Peaks: 3 param']['Lorentzian']['function'] = partial(fit_lorgausstype, lmm.LorentzianModel)
functions['Peaks: 3 param']['Gaussian']['function'] = partial(fit_lorgausstype,lmm.GaussianModel)
functions['Peaks: 3 param']['StudentsT']['function'] = partial(fit_lorgausstype,lmm.StudentsTModel)
functions['Peaks: 3 param']['Lognormal']['function'] = partial(fit_lorgausstype,lmm.LognormalModel)
functions['Peaks: 3 param']['DampedOscillator']['function'] = partial(fit_lorgausstype,lmm.DampedOscillatorModel)


functions['Peaks: 4 param']={}
fourparamform=('w1 ... wn, a1 ... an, x1 ... xn, g1 ... gn, c where w = peak sigma, a = peak amplitude, '
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
    functions['Peaks: 4 param'][peaktype]['parameters']='sigmas(s), amplitudes(s), position(s), gammas(s), y_offset'
    functions['Peaks: 4 param'][peaktype]['description'] = multipeak_description.format(peaktype,fourparamform)
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

functions['Peaks: skewed']={}
fiveparamform=('w1 ... wn, a1 ... an, x1 ... xn, g1 ... gn, s1 ... sn, c where w = peak sigma, a = peak amplitude, '
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
    functions['Peaks: skewed'][peaktype]['parameters']='sigma(s), amplitude(s), position(s), gammas(s), skews(s), y_offset'
    functions['Peaks: skewed'][peaktype]['description'] = multipeak_description.format(peaktype,fiveparamform)
functions['Peaks: skewed']['Pearson4']['function'] = partial(fit_skewedpeaks, lmm.Pearson4Model)
functions['Peaks: skewed']['SkewedVoigt']['function'] = partial(fit_skewedpeaks,lmm.SkewedVoigtModel)

# Oscillating
functions['Oscillating']={'Sine':{'function':fit_sines}
                          #'Ramsey':{'function':ramsey_fit},
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
functions['Thermal']={'Maxwell':{'fullname':'Maxwell-Boltzmann', 'equation':'1/A*exp((x-x0)/kT)','function':partial(thermal_fit, 'maxwell')},
                    'Fermi':{'fullname':'Fermi-Dirac', 'equation':'1/[A*exp((x-x0)/kT)+1]','function':partial(thermal_fit, 'fermi')},
                    'Bose':{'fullname':'Bose-Einstein', 'equation':'1/[A*exp((x-x0)/kT)-1]','function':partial(thermal_fit, 'bose')},
                    }

thermaldescription=('Fit to a {} distribution: y = {}. kT is considered a single fit parameter. Initial guesses '
                    'for kT should be in units of x, usually either eV or J.')
for key in functions['Thermal'].keys():
    functions['Thermal'][key]['parameters']='A, x0, kT'
    functions['Thermal'][key]['description']=thermaldescription.format(functions['Thermal'][key]['fullname'], functions['Thermal'][key]['equation'])



#Step functions
functions['Step']={'Linear':{},'Arctan':{},'ErrorFunction':{},'Logistic':{}}
stepdescription=('Fit a single step function of type {} (see lmfit documentation for information). \n'
                'The step function starts at 0 and ends with value +/- A. '
                'The x-value where y=A/2 is given by x0, and sigma is the characteristic width of the step.\n'
                'Use an offset filter on the data in the main panel to ensure your data starts at y=0.\n'
                'In addition, the x-data must be ascending; use a filter to multiply by -1, and possibly an add/subtract offset, if necessary.\n')
for key in functions['Step'].keys():
    functions['Step'][key]['parameters']='A, x0, sigma'
    functions['Step'][key]['description']=stepdescription.format(key)
functions['Step']['Linear']['function'] = partial(step_fit, 'linear')
functions['Step']['Arctan']['function'] = partial(step_fit, 'arctan')
functions['Step']['ErrorFunction']['function'] = partial(step_fit, 'erf')
functions['Step']['Logistic']['function'] = partial(step_fit, 'logistic')

#Rectangle functions
functions['Rectangle']={'Linear':{},'Arctan':{},'ErrorFunction':{},'Logistic':{}}
rectdescription=('Fit a rectangle function of type {} (see lmfit documentation for information). \n'
                'A rectangle function steps from 0 to +/- A, then back to 0. '
                'The x-values where y=A/2 are given by x0_1, x0_2, and sigma_1 and sigma_2 are the characteristic widths of the steps.\n'
                'Use an offset filter on the data in the main panel to ensure your data starts at y=0.\n'
                'In addition, the x-data must be ascending; use a filter to multiply by -1, and possibly an add/subtract offset, if necessary.\n')
for key in functions['Rectangle'].keys():
    functions['Rectangle'][key]['parameters']=['A, x0_1, x0_2, sigma_1, sigma_2']
    functions['Rectangle'][key]['description']=rectdescription.format(key)

functions['Rectangle']['Linear']['function'] = partial(rectangle_fit, 'linear')
functions['Rectangle']['Arctan']['function'] = partial(rectangle_fit, 'arctan')
functions['Rectangle']['ErrorFunction']['function'] = partial(rectangle_fit, 'erf')
functions['Rectangle']['Logistic']['function'] = partial(rectangle_fit, 'logistic')

# Custom fits based on expression fit
functions['Custom']={'Coulomb blockade':{'function':QD_fit},
                    'FET mobility':{'function':FET_mobility},
                    'BCS/Dynes':{'function':dynes_fit},
                    'Ramsey':{'function':ramsey_fit},
                     }

functions['Custom']['Coulomb blockade']['inputs']='# of peaks, alpha'
functions['Custom']['Coulomb blockade']['default_inputs']='1,0.1'
functions['Custom']['Coulomb blockade']['parameters']='V_0s, G_0s, T'
functions['Custom']['Coulomb blockade']['description']=('Fit one or more Coulomb blockade peaks in the limit of low tunnel coupling:\n'
                                                'G = G_0 * cosh(e*alpha*(Vg - V_0)/(2*k_B*T))**(-2)\n'
                                                'where G is the conductance, G_0 the peak conductance, Vg is the gate voltage, '
                                                'V_0 the gate voltage at the peak, k_B is the Boltzmann constant, '
                                                'T is the temperature, e is electron charge and alpha is the lever arm.\n'
                                                'Alpha must be provided as an input, e.g. 0.02, and should be measured from '
                                                'Coulomb diamonds.\n'
                                                'Initial guesses for V_0s, G_s0s and T are given in the form:\n'
                                                'V_0_1 V_0_2 ... V_0_n, G_0_1 G_0_2 ... G_0_n, T\n'
                                                'e.g., -0.1 0 0.1, 1.1 1.05 1.2, 0.01\n'
                                                'note: give only a single value for T, as it _should_ be the same for all peaks.\n'
                                                'However, each peak will return its own T.\n'
                                                'See e.g. page 396 of the Thomas Ihn book "Semiconductor Nanostructures: Quantum States and Electronic Transport" '
                                                )

functions['Custom']['FET mobility']['inputs']='C,L'
functions['Custom']['FET mobility']['default_inputs']='5e-15,5e-6'
functions['Custom']['FET mobility']['parameters']='mu, V_th, R_s'
functions['Custom']['FET mobility']['description']=('Fit a FET mobility curve of the form:\n'
                                                'G = 1/(R_s+L^2/(C*mu*(Vg-V_th)))\n'
                                                'where R_s is the series resistance, L is the channel length, C is the capacitance, '
                                                'mu is the mobility and V_th is the threshold voltage.\n'
                                                'The data should be G, conductance, vs Vg, gate voltage.\n'
                                                'You must provide calculated/measured values for C and L; these are not fitted.\n'
                                                'If necessary, provide initial guesses for mu, x_0 and R_s in the form:\n'
                                                '0.1,0.5,1e3\n'
                                                'Note; all units in SI! i.e. S and m, not e2/h and cm.\n'
                                                'See doi.org/10.1088/0957-4484/26/21/215202')

functions['Custom']['BCS/Dynes']['parameters']='G_N, gamma, delta'
functions['Custom']['BCS/Dynes']['description']=('Fit the BCS/Dynes model to a tunnel spectrum of a superconducting gap. '
                                                 'The Dynes model is given by:\n'
                                                 'dI/dV(V) = G_N*Re[(e*V-i*gamma)/sqrt((e*V-i*gamma)^2-(delta)^2)]\n'
                                                 'where G_N is the normal state conductance, gamma is broadening and '
                                                 'delta is the superconducting gap. Delta and gamma are in electronvolts\n'
                                                 'see doi.org/10.1103/PhysRevLett.41.1509\n or doi.org/10.1038/s41467-021-25100-w')

functions['Custom']['Ramsey']['parameters']='A, B, C, f, phi, T2'
functions['Custom']['Ramsey']['description']=('Fit a Ramsey oscillation of the form A*cos(2*pi*f*x + phi)*exp(-x/T2) + B + C*x.\n'
                                                'Initial guesses for the parameters are given in the form:\n'
                                                'A, B, C, f, phi, T2\n'
                                                'e.g., 0.01, -50, -4e6, 40e6, 0, 50e-9\n')

#Wrap the ExpressionModel to allow arbitrary input.
functions['User input']={'Expression':{}}
functions['User input']['Expression']['inputs'] = 'Expression'
functions['User input']['Expression']['parameters'] = 'all fit parameters'
functions['User input']['Expression']['description'] =('Fit an arbitrary expression. Input any function you like. '
                                            'x must be the independent variable. e.g.\n'
                                            'C + A * exp(-x/x0) * sin(x*freq+phase)\n'
                                            'You must also provide initial guesses for each parameter in the form:\n'
                                            'C=0.25, A=1.0, x0=2.0, freq=0.04, phase=0')
functions['User input']['Expression']['function']=expression_fit

functions['Statistics']={'Statistics':{}}
functions['Statistics']['Statistics']['inputs'] = 'Function names'
functions['Statistics']['Statistics']['parameters'] = 'weights or percentiles (opt)'
functions['Statistics']['Statistics']['description'] =('Calculate statistical information about the data. Available numpy functions are:\n'
                                            'mean, average, std, var, median, min, max, range, sum, skew, percentile, autocorrelation and autocorrelation_norm.\n'
                                            'See: https://numpy.org/doc/stable/reference/routines.statistics.html.\n'
                                            'Input a comma-separated list of functions to calculate, e.g.\n'
                                            'mean,std,var,median,min,max.\n'
                                            'The average can be weighted by providing a list of weights in the "Initial guess" box.\n'
                                            'The default percentiles to calculate are 1,5,10,25,50,75,90,95 and 99. '
                                            'To change this, provide a list of percentiles in the "Initial guess" box.\n'
                                            'User-defined weights and percentiles cannot be used together; calculate the average and percentiles separately in this case.\n'
                                            'Use "all" to calculate all functions, or use the keyword "all1d" to calculate everything except the percentiles and autocorrelation.\n'
                                            'Linecuts only: A parameter dependency can be generated, but only if the functions return the same number of values.\n'
                                            'This means you can generate a dependency that includes everything except the percentiles and autocorrelation; '
                                            'these can be generated separately, resulting in a 2D dataset.\n'
                                            'The difference between autocorrelation and autocorrelation_norm is that the latter is normalised to the zero-th index value.\n')
functions['Statistics']['Statistics']['function']=statistics
functions['Statistics']['Statistics']['default_inputs'] = 'all'


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