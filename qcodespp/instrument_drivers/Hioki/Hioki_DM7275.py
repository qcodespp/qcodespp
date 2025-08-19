import logging
import time
from functools import partial
from numpy import average

from qcodes import VisaInstrument
from qcodes.validators import Enum, Bool, Arrays, Strings, Ints, Numbers
from qcodes.parameters import create_on_off_val_mapping

class HiokiDM7275(VisaInstrument):
    '''
    QCoDeS driver for the Hioki DC7275 Precision DC voltmeter

    Args:
        name (str): qcodes name for this instrument instance
        address (str): VISA address
    '''

    # Dictionary used by self._trig_source_parser to translate between readable words and machine commands.
    _trigdict={'immediate':'IMM',
                'external':'EXT',
                'bus':'BUS'}

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        self.volt=self.add_parameter('volt',
                                        unit='V',
                                        label='Voltage',
                                        get_cmd=':FETC?',
                                        get_parser=float,
                                        docstring=('Returns the most recent reading immediately\n'
                                                'Be sure to set an appropriate delay time for the '
                                                'integrationtime value. Use volt_triggered to '
                                                'return a triggered voltage reading.'))

        self.volt_triggered=self.add_parameter('volt_triggered',
                                        unit='V',
                                        label='Voltage',
                                        get_cmd=self._get_volt_triggered,
                                        docstring=('Returns a reading after the trigger is triggered.\n'
                                                'Only enabled if self.triggered_continuous == False'
                                                'Use volt to return the latest reading without triggering.'))

        self.read_buffer=self.add_parameter('read_buffer',
                                        unit='V',
                                        label='Voltage',
                                        get_cmd=self._get_buffer,
                                        docstring='Read all values in the buffer.',
                                        vals=Arrays())

        self.num_buffer_readings=self.add_parameter('num_buffer_readings',
                                        unit='#',
                                        label='Number of readings currently in buffer',
                                        get_cmd='DATA:POIN?',
                                        get_parser=int)

        self.nplc=self.add_parameter('nplc',
                                        get_cmd=':SENS:VOLT:DC:NPLC?',
                                        set_cmd=':SENS:VOLT:DC:NPLC {}',
                                        get_parser=float,
                                        unit='#',
                                        docstring=('Get integration time in Number of '
                                                  'PowerLine Cycles.\n'
                                                  'To get the integrationtime in seconds, '
                                                  'use integrationtime().'),
                                        vals=Ints(1,499))

        self.integrationtime=self.add_parameter('integrationtime',
                                        get_cmd=':SENS:VOLT:DC:APER?',
                                        get_parser=float,
                                        set_cmd=':SENS:VOLT:DC:APER {}',
                                        unit='s',
                                        vals=Numbers(0.001,9.999),
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


        self.digits=self.add_parameter('digits',
                                        get_cmd=':SENS:VOLT:DIG?',
                                        get_parser=int,
                                        set_cmd=':SENS:VOLT:DIG {}',
                                        unit='',
                                        docstring=('Number of digits precision from 4 to 8'),
                                        vals=Ints(min_value=4,max_value=8))


        self.offset=self.add_parameter('offset',
                                        get_cmd='SENS:VOLT:DC:NULL:VAL?',
                                        get_parser=float,
                                        set_cmd='SENS:VOLT:DC:NULL:VAL {}',
                                        vals=Numbers(min_value=-1000,max_value=1000),
                                        docstring=('Constant value subtracted from measurement.')
                                        )

        self.offset_enabled=self.add_parameter('offset_enabled',
                                        get_cmd='SENS:VOLT:DC:NULL?',
                                        set_cmd='SENS:VOLT:DC:NULL {}',
                                        val_mapping=create_on_off_val_mapping(1,0),
                                        docstring=('Constant offset subtraction enabled (True or False).')
                                        )

        self.trigger_source=self.add_parameter('trigger_source',
                                        get_cmd='TRIG:SOUR?',
                                        get_parser=self._trig_source_parser,
                                        set_cmd='TRIG:SOUR {}',
                                        set_parser=self._trig_source_parser,
                                        vals=Enum(*self._trigdict))

        self.trigger_continuous=self.add_parameter('trigger_continuous',
                                        get_cmd='INIT:CONT?',
                                        set_cmd='INIT:CONT {}',
                                        val_mapping=create_on_off_val_mapping(1,0),
                                        docstring=('Trigger measurements continuously or not')
                                        )

        self.trigger_count=self.add_parameter('trigger_count',
                                        get_cmd=':SAMP:COUN?',
                                        get_parser=int,
                                        set_cmd='SAMP:COUN {}',
                                        vals=Ints(),
                                        unit='#')
        
        self.trigger_delay=self.add_parameter('trigger_delay',
                                        get_cmd='TRIG:DEL?',
                                        get_parser=float,
                                        set_cmd='TRIG:DEL {}',
                                        vals=Numbers(min_value=0,
                                                    max_value=999999.999),
                                        unit='s')

        self.trigger_autodelay=self.add_parameter('trigger_autodelay',
                                        get_cmd='TRIG:DEL:AUTO?',
                                        set_cmd='TRIG:DEL:AUTO {}',
                                        val_mapping=create_on_off_val_mapping(1,0)
                                        )

        # self.add_parameter('averaging',
        #                    get_cmd=partial(self._current_mode_get, 'AVER:STAT',
        #                                    parser=parsebool),
        #                    set_cmd=partial(self._current_mode_set,
        #                                    par='AVER:STAT'),
        #                    set_parser=bool_to_str)



        self.connect_message()


    # --------------------------------------
    #           functions
    # --------------------------------------

    def auto_offset(self,meas_num=10):
        '''
        Measure the input voltage and apply this value as the offset (null)

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

    def trigger_now(self,trigger_count=None,wait=True,return_buffer=False):
        '''
        Manually trigger measurement(s). 

        Clears the buffer and stores the number of measurements specified by trigger_count, spaced by integrationtime.
        
        Args:
            trigger_count (int): Number of measurements to perform. If None, self.trigger_count used
            wait (bool): Whether to sleep until all measurements stored in buffer
            return_buffer (bool): Whether to return the buffer values after measurement.
                                Default False since reading the buffer clears it.
        '''

        if trigger_count is not None:
            self.trigger_count(trigger_count)

        self.write('INIT:IMM')
        
        if wait:
            while self.num_buffer_readings()<self.trigger_count():
                time.sleep(self.integrationtime())
        
        if return_buffer:
            return self.read_buffer()

    def _trig_source_parser(self,val):
        for key,value in self._trigdict.items():
            if val==value:
                return key
            elif val==key:
                return value

    def _get_volt_triggered(self):
        if self.trigger_continuous():
            return None
        return float(self.ask('READ?'))

    def _get_buffer(self):
        if self.num_buffer_readings()>0:
            buffer=self.ask(':R?')
            array=buffer.split(',')
            for i,char in enumerate(array[0]):
                if char in ['+','-']:
                    array[0]=array[0][i:]
                    break
            array=[float(element) for element in array]
            return array
        else:
            time.sleep(self.integrationtime())
            return [self.volt()]

    def clear_buffer(self):
        self.write(':DATA:CLE')

    def reset(self):
        '''
        Resets instrument
        '''
        logging.debug('Resetting instrument')
        self.write('*RST')

