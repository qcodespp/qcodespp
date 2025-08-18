import logging
import time
from functools import partial
from numpy import average

from qcodes import VisaInstrument
from qcodes.validators import Strings as StringValidator
from qcodes.validators import Ints as IntsValidator
from qcodes.validators import Numbers as NumbersValidator
from qcodes.validators import Enum, Bool
from qcodes.parameters import create_on_off_val_mapping

class HiokiDM7275(VisaInstrument):
    '''
    QCoDeS driver for the Hioki DC7275 Precision DC voltmeter

    At present only voltage measurements are available.

    Args:
        name (str): qcodes name for this instrument instance
        address (str): VISA address
    '''
    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)


        self.trigger_count=self.add_parameter('trigger_count',
                                        get_cmd=':SAMP:COUN?',
                                        get_parser=int,
                                        set_cmd='SAMP:CONT {}',
                                        vals=IntsValidator(),
                                        unit='#')
        
        self.trigger_delay=self.add_parameter('trigger_delay',
                                        get_cmd='TRIG:DEL?',
                                        get_parser=float,
                                        set_cmd='TRIG:DEL {}',
                                        vals=NumbersValidator(min_value=0,
                                                                 max_value=999999.999),
                                        unit='s')

        self.trigger_continuous=self.add_parameter('trigger_continuous',
                                        get_cmd='INIT:CONT?',
                                        set_cmd='INIT:CONT {}',
                                        val_mapping=create_on_off_val_mapping(1,0),
                                        docstring=('Trigger measurements continuously or not')
                                        )
        

        # self.add_parameter('averaging',
        #                    get_cmd=partial(self._current_mode_get, 'AVER:STAT',
        #                                    parser=parsebool),
        #                    set_cmd=partial(self._current_mode_set,
        #                                    par='AVER:STAT'),
        #                    set_parser=bool_to_str)

        self.offset=self.add_parameter('offset',
                                        get_cmd='SENS:VOLT:DC:NULL:VAL?',
                                        get_parser=float,
                                        set_cmd='SENS:VOLT:DC:NULL:VAL {}',
                                        vals=NumbersValidator(min_value=-1000,max_value=1000),
                                        docstring=('Constant value subtracted from measurement.')
                                        )

        self.offset_enabled=self.add_parameter('offset_enabled',
                                        get_cmd='SENS:VOLT:DC:NULL?',
                                        set_cmd='SENS:VOLT:DC:NULL {}',
                                        val_mapping=create_on_off_val_mapping(1,0),
                                        docstring=('Constant offset subtraction enabled (True or False).')
                                        )

        self.digits=self.add_parameter('digits',
                                        get_cmd=':SENS:VOLT:DIG?',
                                        get_parser=int,
                                        set_cmd=':SENS:VOLT:DIG {}',
                                        unit='',
                                        docstring=('Number of digits precision from 4 to 8'),
                                        vals=IntsValidator(min_value=4,max_value=8))

        self.nplc=self.add_parameter('nplc',
                                        get_cmd=':SENS:VOLT:DC:NPLC?',
                                        set_cmd=':SENS:VOLT:DC:NPLC {}',
                                        get_parser=float,
                                        unit='#',
                                        docstring=('Get integration time in Number of '
                                                  'PowerLine Cycles.\n'
                                                  'To get the integrationtime in seconds, '
                                                  'use integrationtime().'),
                                        vals=IntsValidator(1,499))

        self.integrationtime=self.add_parameter('integrationtime',
                                        get_cmd=':SENS:VOLT:DC:APER?',
                                        get_parser=float,
                                        set_cmd=':SENS:VOLT:DC:APER {}',
                                        unit='s',
                                        vals=NumbersValidator(0.001,9.999),
                                        docstring=('Get integration time in seconds.\n'
                                                    'To get the integrationtime as a Number '
                                                    'of Power Line Cycles, use nplc().'))

        self.autorange=self.add_parameter('autorange',
                                        get_cmd=':SENS:VOLT:DC:RANG:AUTO?',
                                        set_cmd=':SENS:VOLT:DC:RANG:AUTO {}',
                                        unit='',
                                        docstring=('Turn autorange on or off.'),
                                        val_mapping=create_on_off_val_mapping(1,0)
                                         )

        self.range=self.add_parameter('range',
                                        get_cmd=':SENS:VOLT:DC:RANG?',
                                        set_cmd=':SENS:VOLT:DC:RANG {}',
                                        unit='RANG',
                                        docstring=('Sets the measurement range.\n'
                                                   'Note that not only a discrete set of '
                                                   'ranges can be set (see the manual for '
                                                   'details).'),
                                        vals = Enum(0.1,1,10,100,1000)
                                        )

        self.volt=self.add_parameter('volt',
                                        unit='V',
                                        label='Voltage',
                                        get_cmd=':FETC?',
                                        get_parser=float)

        self.connect_message()


    # --------------------------------------
    #           functions
    # --------------------------------------

    def auto_offset(self,meas_num=10):
        '''
        Measure the current input voltage and apply this as the offset

        Args:
            meas_num: Number of measurements to average over to obtain the offset value.
        '''
        self.offset_enabled(False)
        voltages=[]
        time.sleep(2)
        for i in range(meas_num):
            time.sleep(self.integrationtime())
            voltages.append(self.volt())
        self.offset(average(voltages))
        self.offset_enabled(True)
        print(f'Auto offset completed. Offset value = {self.offset()} V')

    def reset(self):
        '''
        Resets instrument
        '''
        logging.debug('Resetting instrument')
        self.write('*RST')
