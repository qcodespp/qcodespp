# Keithley_2700.py driver for Keithley 2700 DMM
#
# Pieter Eendebak <pieter.eendebak@gmail.com>, 2016 (adapt to Qcodes framework)
# Pieter de Groot <pieterdegroot@gmail.com>, 2008
# Martijn Schaafsma <qtlab@mcschaafsma.nl>, 2008
# Reinier Heeres <reinier@heeres.eu>, 2008
#
# Update december 2009:
# Michiel Jol <jelle@michieljol.nl>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging
from functools import partial

from qcodes import VisaInstrument
from qcodes.validators import Strings as StringValidator
from qcodes.validators import Ints as IntsValidator
from qcodes.validators import Numbers as NumbersValidator
from qcodes.validators import Enum


# %% Helper functions

class K2700Exception(Exception):
    pass

def bool_to_str(val):
    '''
    Function to convert boolean to 'ON' or 'OFF'
    '''
    if val:
        return "ON"
    else:
        return "OFF"


# %% Driver for Keithley_2700

def parseint(v):
    logging.debug('parseint: %s -> %d' % (v, int(v)))
    return int(v)


def parsebool(v):
    r = bool(int(v))
    logging.debug('parsetobool: %s -> %d' % (v, r))
    return r


def parsestr(v):
    return v.strip().strip('"')


class Keithley_2700(VisaInstrument):
    '''
    This is the qcodes driver for the Keithley_2700 Multimeter

    Usage: Initialize with::

        <name> =  = Keithley_2700(<name>, address='<GPIB address>', reset=<bool>,
            change_display=<bool>, change_autozero=<bool>)

    This driver does not yet contain all commands available, but supports reading
    voltage, current, resistance, temperature and frequency. Each of these parameters
    is only available when mode() is set to the corresponding value.

    '''
    def __init__(self, name, address, reset=False, use_defaults=False, **kwargs):
        super().__init__(name, address, **kwargs)

        self._modes = ['VOLT:AC', 'VOLT:DC', 'CURR:AC', 'CURR:DC', 'RES',
                       'FRES', 'TEMP', 'FREQ']
        # self._change_display = change_display
        # self._change_autozero = change_autozero
        self._averaging_types = ['MOV', 'REP']
        self._trigger_sent = False
        self._address=address

        # Force the K2700 to provide only the raw value rather than a complicated string
        self.write(':FORM:ELEM READ')

        # Add parameters to wrapper
        self.add_parameter('mode',
                           get_cmd=':CONF?',
                           get_parser=parsestr,
                           #set_cmd=':CONF:{}',
                           set_cmd=self._set_mode,
                           vals=Enum('VOLT:AC', 'VOLT:DC', 'CURR:AC', 'CURR:DC', 'RES', 'FRES', 'TEMP', 'FREQ'))

        self.add_parameter('trigger_count',
                           get_cmd=self._mode_par('INIT', 'CONT'),
                           get_parser=int,
                           set_cmd=self._mode_par_value('INIT', 'CONT', '{}'),
                           vals=IntsValidator(),
                           unit='#')
        self.add_parameter('trigger_delay',
                           get_cmd=self._mode_par('TRIG', 'DEL'),
                           get_parser=float,
                           set_cmd=self._mode_par_value('TRIG', 'DEL', '{}'),
                           vals=NumbersValidator(min_value=0,
                                                 max_value=999999.999),
                           unit='s')

        self.add_parameter('trigger_continuous',
                           get_cmd=self._mode_par('INIT', 'CONT'),
                           get_parser=parsebool,
                           set_cmd=self._mode_par_value('INIT', 'CONT', '{}'),
                           set_parser=bool_to_str)
        self.add_parameter('display',
                           get_cmd=self._mode_par('DISP', 'ENAB'),
                           get_parser=parsebool,
                           set_cmd=self._mode_par_value('DISP', 'ENAB', '{}'),
                           set_parser=bool_to_str)

        self.add_parameter('averaging',
                           get_cmd=partial(self._current_mode_get, 'AVER:STAT',
                                           parser=parsebool),
                           set_cmd=partial(self._current_mode_set,
                                           par='AVER:STAT'),
                           set_parser=bool_to_str)

        self.add_parameter('digits',
                           get_cmd=partial(self._current_mode_get, 'DIG',
                                           parser=int),
                           set_cmd=partial(self._current_mode_set, par='DIG'))

        self.add_parameter('nplc',
                           get_cmd=partial(self._current_mode_get, 'NPLC',
                                           parser=float),
                           set_cmd=partial(self._current_mode_set, par='NPLC',
                                           mode=None),
                           unit='APER',
                           docstring=('Get integration time in Number of '
                                      'PowerLine Cycles.\n'
                                      'To get the integrationtime in seconds, '
                                      'use get_integrationtime().'))

        self.add_parameter('range',
                           get_cmd=partial(self._current_mode_get, 'RANG',
                                           parser=float),
                           set_cmd=partial(self._current_mode_set, par='RANG'),
                           unit='RANG',
                           docstring=('Sets the measurement range.\n'
                                      'Note that not only a discrete set of '
                                      'ranges can be set (see the manual for '
                                      'details).'))

        self.add_parameter('integrationtime',
                           get_cmd=partial(self._current_mode_get, 'APER',
                                           parser=float),
                           set_cmd=partial(self._current_mode_set, par='APER',
                                           mode=None),
                           unit='s',
                           vals=NumbersValidator(min_value=2e-4, max_value=1.),
                           docstring=('Get integration time in seconds.\n'
                                      'To get the integrationtime as a Number '
                                      'of PowerLine Cycles, use get_nplc().'))

        if self.mode().startswith('VOLT'):
            self.add_parameter('volt',
                                unit='V',
                                label='Voltage',
                                get_cmd=':DATA:FRESH?',
                                get_parser=float)

        elif self.mode().startswith('CURR'):
            self.add_parameter('curr',
                                unit='A',
                                label='Current',
                                get_cmd=':DATA:FRESH?',
                                get_parser=float)

        elif self.mode()=='RES' or self.mode()=='FRES':
            self.add_parameter('res',
                                unit='Ohm',
                                label='Resistance',
                                get_cmd=':DATA:FRESH?',
                                get_parser=float)

        elif self.mode().startswith('FREQ'):
            self.add_parameter('freq',
                                unit='Hz',
                                label='Frequency',
                                get_cmd=':DATA:FRESH?',
                                get_parser=float)

        elif self.mode().startswith('TEMP'):
            self.add_parameter('temp',
                                unit='K',
                                label='Temperature',
                                get_cmd=':DATA:FRESH?',
                                get_parser=float)

        else:
            #I am pretty sure this should be impossible, but just in case.
            print('You are using the K2700 in a mode that is not one of\n'
                'VOLT:AC,VOLT:DC,CURR:AC,CURR:DC,RES,FRES,TEMP,FREQ.\n'
                'The parameter measurement() will return the measured value but units and labels will be generic')
            self.add_parameter('measurement',
                                unit='arb',
                                label=self.name,
                                get_cmd=':DATA:FRESH?',
                                get_parser=float)

        if reset:
            self.reset()
        else:
            self.get_all()
        if use_defaults:
            self.set_defaults()

        startupmode=self.mode()
        self.connect_message()

    def get_all(self):
        '''
        Reads all relevant parameters from instrument

        Input:
            None

        Output:
            None
        '''
        logging.info('Get all relevant data from device')

        for p in ['mode', 'trigger_count', 'trigger_continuous', 'averaging',
                  'digits', 'nplc', 'integrationtime', 'range', 'display']:
            logging.debug('get %s' % p)
            par = getattr(self, p)
            par.get()

        # self.get_trigger_delay()
        # self.get_trigger_source()
        # self.get_trigger_timer()
        # self.get_autozero()
        # self.get_averaging_window()
        # self.get_averaging_count()
        # self.get_averaging_type()
        # self.get_autorange()

    def _current_mode_get(self, par, mode=None, parser=None):
        cmd = self._mode_par(mode, par)
        r = self.ask(cmd)
        if parser is not None:
            r = parser(r)
        return r

    def _current_mode_set(self, value, par, mode=None):
        cmd = self._mode_par_value(mode, par, value)
        return self.write(cmd)

    # --------------------------------------
    #           functions
    # --------------------------------------

    def _set_mode_volt_dc(self):
        '''
        Set mode to DC Voltage

        Input:
            None

        Output:
            None
        '''
        logging.debug('Set mode to DC Voltage')
        self.mode.set('VOLT:DC')

    def set_defaults(self):
        '''
        Set to driver defaults:
        Output=data only
        Mode=Volt:DC
        Digits=7
        Trigger=Continous
        Range=10 V
        NPLC=1
        Averaging=off
        '''

        self.write('SYST:PRES')
        self.write(':FORM:ELEM READ')
        # Sets the format to only the read out, all options are:
        # READing = DMM reading, UNITs = Units,
        # TSTamp = Timestamp, RNUMber = Reading number,
        # CHANnel = Channel number, LIMits = Limits reading

        self._set_mode_volt_dc()
        self.digits.set(7)
        self.trigger_continuous.set(True)
        self.range.set(10)
        self.nplc.set(1)
        self.averaging.set(False)
        return

    def _determine_mode(self, mode):
        '''
        Return the mode string to use.
        If mode is None it will return the currently selected mode.
        '''
        logging.debug('Determine mode with mode=%s' % mode)
        if mode is None:
            mode = self.mode.get_latest()  # _mode(query=False)
        if mode not in self._modes and mode not in ('INIT', 'TRIG', 'SYST',
                                                    'DISP'):
            logging.warning('Invalid mode %s, assuming current' % mode)
            mode = self.mode.get_latest()
        logging.debug('Determine mode: mode=%s' % mode)
        return mode

    def _set_mode(self, mode):
        '''
        Set the mode to the specified value

        Input:
            mode (string) : mode to be set. Choose from self._modes

        Output:
            None
        '''

        logging.debug('Set mode to %s', mode)
        if mode in self._modes:
            string = ':CONF:%s' % mode
            self.write(string)

        else:
            logging.error('Invalid mode \'{}\'. Valid modes are {}'.format(mode,self._modes))

        # Get all values again because some parameters depend on mode
        self.get_all()
        self.trigger_continuous(True)
        self.remove_instance(self)
        self.__init__(self.name,self._address)

    def _mode_par_value(self, mode, par, val):
        '''
        For internal use only!!
        Create command string based on current mode

        Input:
            mode (string) : The mode to use
            par (string)  : Parameter
            val (depends) : Value

        Output:
            None
        '''
        mode = self._determine_mode(mode)
        string = ':%s:%s %s' % (mode, par, val)
        return string

    def _mode_par(self, mode, par):
        '''
        For internal use only!!
        Create command string based on current mode

        Input:
            mode (string) : The mode to use
            par (string)  : Parameter
            val (depends) : Value

        Output:
            None
        '''
        mode = self._determine_mode(mode)
        string = ':%s:%s?' % (mode, par, )
        return string

    def reset(self):
        '''
        Resets instrument to default values

        Input:
            None

        Output:
            None
        '''
        logging.debug('Resetting instrument')
        self.write('*RST')
        self.get_all()
