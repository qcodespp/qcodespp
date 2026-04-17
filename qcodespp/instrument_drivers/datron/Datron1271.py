import logging
import time
from functools import partial
from numpy import average

from qcodes import VisaInstrument
from qcodes.validators import Enum, Bool, Arrays, Strings, Ints, Numbers
from qcodes.parameters import create_on_off_val_mapping

log = logging.getLogger(__name__)

class Datron1271(VisaInstrument):
    '''
    QCoDeS driver for the Datron 1271 8.5 digit multimeter

    The Datron 1271 is an old instrument with a few quirks: namely that many of the parameters are not readable. 
    Notable cases are the resolution, range, mode and delay. That means that if you don't set them through software, 
    QCoDeS will not know these values. This matters for the driver in that the parameters 'volt', 'curr' and 'resistance', 
    are only available if the mode is set to read them. You may therefore need to tell the software which mode you are 
    using with soft_mode(mode), where mode is one of 'DCI, ACI, ACV, OHMS, TRUE_OHMS, HI_OHMS'

    Not all functions are implemented or tested. Some functions do not work for unknown reasons.

    Args:
        name (str): qcodes name for this instrument instance
        address (str): VISA address
    '''

    def __init__(self, name, address, terminator='\n', **kwargs):
        super().__init__(name, address, terminator=terminator, **kwargs)

        self._unit='V'
        self._label='Voltage'

        self.volt=self.add_parameter('volt',
                                        unit='V',
                                        label='Voltage',
                                        get_cmd=partial(self._rdg,'volt'),
                                        get_parser=float,
                                        docstring=('Returns the voltage, if mode is DCV or ACV'))
        
        self.read=self.add_parameter('read',
                                     unit=self._unit,
                                     label=self._label,
                                     get_cmd='RDG?',
                                     get_parser=float,
                                     docstring='Returns a reading immediately')
        
        self.trig_read=self.add_parameter('trig_read',
                                                  unit=self._unit,
                                                  label=self._label,
                                                  get_cmd='X?',
                                                  get_parser=float,
                                                  docstring='Returns a reading after waiting for delay time to elapse')
        
        self.read_buffer=self.add_parameter('read_buffer',
                                    unit=self._unit,
                                    label=self._label,
                                    get_cmd=self._read_buffer,
                                    docstring='Returns a number of readings specified by buffer_size')
        
        self.buffer_size=self.add_parameter('buffer_size',
                                    unit='#',
                                    label='Buffer size',
                                    set_cmd='N {}',
                                    get_cmd='N?',
                                    vals=Ints(min_value=1))
        
        self.max=self.add_parameter('max',
                                    unit=self._unit,
                                    label=self._label,
                                    get_cmd='MAX?',
                                    get_parser=float)
        
        self.min=self.add_parameter('min',
                                    unit=self._unit,
                                    label=self._label,
                                    get_cmd='MIN?',
                                    get_parser=float)
        
        self.resolution=self.add_parameter('resolution',
                                           unit='num digits',
                                           label='Resolution',
                                           set_cmd=self._set_res,
                                           docstring='Set resolution by number of digits. Options are 5,6,7,8 (except for ACV and HI_OHMS, which is only 5,6)')

        self.mode=self.add_parameter('mode',
                                     set_cmd=self._set_mode,
                                     initial_value='DCV',
                                     docstring='Set measurement mode: ACI, ACV, DCI, DCV, OHMS, TRUE_OHMS, HI_OHMS',
                                     vals=Enum('ACI','ACV','DCI','DCV','OHMS','TRUE_OHMS', 'HI_OHMS'))
        
        self.range=self.add_parameter('range',
                                      set_cmd=self._set_range,
                                      label='Range',
                                      unit=self._unit,
                                      docstring='Set the range. Cannot be read')
        
        self.filter=self.add_parameter('filter',
                                   set_cmd=self._set_filter,
                                   label='Filter cut-off',
                                   unit='Hz',
                                   docstring='Set the low-pass filter cutoff. Cannot be read.')
        
        self.coupling=self.add_parameter('coupling',
                                         set_cmd='{}',
                                         docstring='Set coupling: DCCP, ACCP',
                                         vals=Enum('DCCP','ACCP'))
        
        self.offset=self.add_parameter('offset',
                                       unit=self._unit,
                                       label='Offset',
                                       set_cmd=self._set_offset,
                                       get_cmd='C?',
                                       vals=Numbers())
        
        self.multiplier=self.add_parameter('multiplier',
                                        unit=self._unit,
                                        label='Multiplier',
                                        initial_value=1,
                                        set_cmd=self._set_multiplier,
                                        get_cmd='M?',
                                        vals=Numbers(),
                                        docstring='Set the multiplier scaling readings. Setting 1 turns off multiplier')
        
        self.divisor=self.add_parameter('divisor',
                                        unit=self._unit,
                                        label='Divisor',
                                        initial_value=1,
                                        set_cmd=self._set_divisor,
                                        get_cmd='Z?',
                                        vals=Numbers(),
                                        docstring='Set the divisor, Z. Setting 1 turns off division')
        
        self.delay=self.add_parameter('delay',
                                      unit='s',
                                      label='Delay',
                                      set_cmd='DELAY {}',
                                      vals=Numbers(min_value=0))
        
        self.ave_rolling=self.add_parameter('ave_rolling',
                                            unit='#',
                                            label='Rolling average',
                                            set_cmd='AVG AV{}',
                                            vals=Enum(4,8,16,32,64))
        
        self.averaging=self.add_parameter('averaging',
                                          unit='#',
                                          label='Num Averaged Readings',
                                          set_cmd=self._set_averaging,
                                          vals=Ints(min_value=0),
                                          docstring='Number of readings to average over. Setting averaging(0) turns off averaging')
        
        self.line_freq=self.add_parameter('line_freq',
                                          unit='Hz',
                                          label='Line Frequency',
                                          set_cmd='LINEF {}',
                                          get_cmd='LINEF?',
                                          vals=Enum(50,60))

        self.protected_store=self.add_parameter('protected_store',
                                                get_cmd='*PUD',
                                                set_cmd='*PUD? {}',
                                                get_parser=str)
        
        self.option_config=self.add_parameter('option_config',
                                              get_cmd='*OPT?')
        
        self.connect_message()
        
    def reset(self):
        self.write('RST')

    def clear(self):
        self.write('*CLS')

    def zero(self):
        self.write('ZERO?')

    def self_test(self):
        ret=self.ask('*TST?')
        if ret=='0':
            return 'Test OK'
        elif ret==1:
            return 'Test not OK'
        else:
            raise ValueError('Self test returned unexpected value')
        
    def fast_test(self):
        ret=self.ask('*CNFTST?')
        if ret=='0':
            return 'Test OK'
        elif ret==1:
            return 'Test not OK'
        else:
            raise ValueError('Fast test returned unexpected value')
        
    def self_cal(self):
        ret=self.ask('*CAL?')
        if ret=='0':
            return 'Calibration OK'
        elif ret==1:
            return 'Calibration not OK'
        else:
            raise ValueError('Calibration returned unexpected value')
        
    def _set_mode(self,str):
        self.write(str)
        self.soft_mode(str)

    def soft_mode(self,str):
        for param in ['volt','curr','resistance','freq']:
            if param in self.parameters:
                self.remove_parameter(param)

        if 'V' in str:
            self._unit='V'
            self._label='Voltage'
            self.volt=self.add_parameter('volt',
                                        unit='V',
                                        label='Voltage',
                                        get_cmd=partial(self._rdg,'volt'),
                                        get_parser=float,
                                        docstring=('Returns the voltage, if mode is DCV or ACV'))

        elif 'I' in str:
            self._unit='A'
            self._label='Current'
            self.curr=self.add_parameter('curr',
                                     unit='A',
                                     label='Current',
                                     get_cmd=partial(self._rdg,'curr'),
                                     get_parser=float,
                                     docstring=('Returns the current, if mode is DCI or ACI'))

        else:
            self._unit='Ohm'
            self._label='Resistance'
            self.resistance=self.add_parameter('resistance',
                                           unit='Ohm',
                                           label='Resistance',
                                           get_cmd=partial(self._rdg,'resistance'),
                                           get_parser=float,
                                           docstring='Returns resistance, if mode is OHMS, TRUE_OHMS or HI_OHMS')
            
        if 'AC' in str:
            self.freq=self.add_parameter('freq',
                                         unit='Hz',
                                         label='Frequency',
                                         get_cmd='FREQ?',
                                         get_parser=float,
                                         docstring='Measured frequency of the AC signal')

    def _set_range(self,val):
        if 'V' in self.mode.cache():
            allowed=[1000,100,10,1,0.1,'auto']
            if val not in allowed:
                raise ValueError(f'{val} not in allowed ranges: '+', '.join([str(al) for al in allowed]))
            elif val == 'auto':
                self.write('AUTO')
            else:
                self.write(f'{self.mode.cache()} {val}')

    def _set_res(self,val):
        if self.mode.cache() in ['ACV','HI_OHMS']:
            if val not in [5,6]:
                raise ValueError('resolution must be 5 or 6')
            self.write(f'RESL{val}')
        else:
            if val not in [5,6,7,8]:
                raise ValueError('resolution must be one of 5, 6, 7, 8')
            self.write(f'RESL{val}')

    def _set_filter(self,val):
        if 'AC' in self.mode.cache():
            raise ValueError('Cannot use filter in AC mode')
        values=[1000,360,100,40,10,1,0]
        if val not in values:
            raise ValueError(f'Filter cannot be set to {val}. Use one of '+', '.join([str(value) for value in values]))
        elif val==0:
            self.write('FILT_OFF')
        else:
            self.write(f'FILT{val}HZ')
            self.write('FILT_ON')
    
    def _set_averaging(self,num):
        if num==0:
            self.write('AVE OFF')
        else:
            self.write(f'AVE BLOC_{num}')

    def _set_multiplier(self,val):
        self.write(f'M {val}')
        if val==1:
            self.write('MUL_M OFF')
        else:
            self.write('MUL_M ON')

    def _set_divisor(self,val):
        self.write(f'Z {val}')
        if val==1:
            self.write('DIV_Z OFF')
        else:
            self.write('DIV_Z ON')

    def _set_offset(self,val):
        self.write(f'C {val}')
        if val==0:
            self.write('SUB_C OFF')
        else:
            self.write('SUB_C ON')

    def _rdg(self,param_type=None):
        '''
        Perform an immediate reading, checking that the param_type conforms to the current instrument mode
        '''
        optiondict={'volt':['DCV','ACV'],
                    'curr':['DCI','ACI'],
                    'resistance':['OHMS','TRUE_OHMS','HI_OHMS']}
        if self.mode.cache() not in optiondict[param_type]:
            log.warning(f'Cannot use {param_type} in {self.mode.cache()} mode')
            return None
        
        return self.ask('RDG?')

    def _read_buffer(self):
        self.write(f'BLOCK {int(self.buffer_size.cache())}')
        return self.ask(f'BLOCK? 0,{int(self.buffer_size.cache())}')