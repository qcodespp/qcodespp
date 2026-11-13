from typing import Any

import numpy as np
from qcodes.instrument import VisaInstrument, InstrumentChannel
from qcodes.parameters import Parameter, create_on_off_val_mapping
from qcodes.validators import Enum, Numbers, Ints

_SOURCES=['CHAN1', 'CHAN2', 'CHAN3', 'CHAN4']
_WAVEMODES=['NORM','MAX','RAW']
_DATAFORMATS=['WORD','BYTE','ASC']
_MDEPTHS=['AUTO','1k','10k','100k','1M','10M','25M','50M','100M','200M']
_ACQTYPES=['NORM','AVER','PEAK','HRES']
_TRIGTYPES=['EDGE','PULS','SLOP','VID','PATT','DUR',
            'TIM','RUNT','WIND','DEL','SET','NEDG',
            'RS232','IIC','SPI','CAN','FLEX','LIN','IIS','M1553']
_TRIGCOUP=['AC','DC','LFR','HFR']
_TRIGMODES=['AUTO','NORM', 'SING']
_EDGESLOPES=['POS','NEG','RFALI']

# The number of points :WAV:DATA? returns is set by :WAV:STARt and :WAV:STOP, and STOP defaults to 1000. The
# programming guide says the largest range per read depends on the memory depth and format, but gives no numbers;
# these are the limits Rigol documents for the DS1000Z. Longer waveforms are read in chunks of these sizes.
_POINTS_PER_READ={'ASC':15625,'BYTE':250000}

def _parse_ascii_data(response: str) -> np.ndarray:
    """Converts a :WAV:DATA? response in ASCii format to an array, removing the TMC header (#N followed by N digits)."""
    response=response.strip()
    if response.startswith('#'):
        response=response[2+int(response[1]):]
    response=response.strip(',')
    if not response:
        return np.array([])
    return np.array(response.split(','),dtype=float)

class Rigol_MSO5354_Channel(InstrumentChannel):
    def __init__(self, parent: VisaInstrument, name: str, chan_num: int, **kwargs) -> None:
        super().__init__(parent, name, **kwargs)
        self.chan_num=chan_num

        self.bandwidth_limit: Parameter = self.add_parameter(
            'bandwidth_limit',
            label='Bandwidth Limit',
            set_cmd=f'CHAN{self.chan_num}:BWL {{}}',
            get_cmd=f'CHAN{self.chan_num}:BWL?',
            vals=Enum('20M','100M','200M','OFF')
        )

        self.coupling: Parameter = self.add_parameter(
            'coupling',
            label='Coupling',
            set_cmd=f'CHAN{self.chan_num}:COUP {{}}',
            get_cmd=f'CHAN{self.chan_num}:COUP?',
            vals=Enum('AC','DC','GND')
        )

        self.enabled: Parameter = self.add_parameter(
            'enabled',
            label='Enabled',
            set_cmd=f'CHAN{self.chan_num}:DISP {{}}',
            get_cmd=f'CHAN{self.chan_num}:DISP?',
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0)
        )

        self.invert: Parameter = self.add_parameter(
            'invert',
            label='Inverted',
            set_cmd=f'CHAN{self.chan_num}:INV {{}}',
            get_cmd=f'CHAN{self.chan_num}:INV?',
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0)
        )

        self.yoffset: Parameter = self.add_parameter(
            'yoffset',
            label='Y Offset',
            set_cmd=f'CHAN{self.chan_num}:OFF {{}}',
            get_cmd=f'CHAN{self.chan_num}:OFF?',
            get_parser=float,
            vals=Numbers()
        )

        self.yposition: Parameter = self.add_parameter(
            'yposition',
            label='Y Position',
            set_cmd=f'CHAN{self.chan_num}:POS {{}}',
            get_cmd=f'CHAN{self.chan_num}:POS?',
            get_parser=float,
            vals=Numbers(min_value=-100, max_value=100)
        )

        self.yscale: Parameter = self.add_parameter(
            'yscale',
            label = 'Y Scale',
            set_cmd=f'CHAN{self.chan_num}:SCAL {{}}',
            get_cmd=f'CHAN{self.chan_num}:SCAL?',
            get_parser=float,
            vals=Numbers()
        )

        self.ydata: Parameter = self.add_parameter(
            'ydata',
            label=f'Ch{self.chan_num} Data',
            unit='V',
            get_cmd=self._get_data
        )

        self.xdata: Parameter = self.add_parameter(
            'xdata',
            label='X Data',
            unit='s',
            get_cmd=self.parent._get_xdata
        )

    def _get_data(self):
        self.parent.source(f'CHAN{self.chan_num}')
        data_format=self.parent.data_format()
        if data_format not in _POINTS_PER_READ:
            raise RuntimeError(f'{self.full_name}: reading data in {data_format} format is not supported. Set '
                               f'{self.parent.data_format.full_name} to ASC or BYTE (WORD only carries the same '
                               f'8 bits as BYTE, in twice the number of bytes).')
        num_points=self.parent._num_points()
        chunks=[]
        start=1
        # STOP is set before STARt so that STARt is never past STOP, which the instrument might reject.
        self.parent.write(':WAV:STAR 1')
        while start<=num_points:
            self.parent.write(f':WAV:STOP {min(start+_POINTS_PER_READ[data_format]-1,num_points)}')
            self.parent.write(f':WAV:STAR {start}')
            if data_format=='ASC':
                chunk=_parse_ascii_data(self.parent.ask(':WAV:DATA?'))
            else:
                chunk=self.parent.visa_handle.query_binary_values(':WAV:DATA?',datatype='B',container=np.array)
            if len(chunk)==0:
                raise RuntimeError(f'{self.full_name}: no data returned for points {start} onwards '
                                   f'of {num_points}.')
            chunks.append(chunk)
            # Advance by the number of points actually returned, in case the instrument limits the range.
            start+=len(chunk)
        data=np.concatenate(chunks)
        if data_format=='BYTE':
            # Convert the 8-bit codes to volts with the formula Rigol gives for other series (e.g. DS1000Z);
            # the MSO5000 guide does not state it.
            preamble=self.parent.ask(':WAV:PRE?').split(',')
            yincrement,yorigin,yreference=(float(value) for value in preamble[7:10])
            data=(data-yorigin-yreference)*yincrement
        return data

class Rigol_MSO5354(VisaInstrument):
    def __init__(self, name: str, address: str, **kwargs: Any) -> None:
        super().__init__(name, address, terminator="\n", **kwargs)

        self.averages: Parameter = self.add_parameter(
            'averages',
            label='Averages',
            get_cmd='ACQ:AVER?',
            set_cmd='ACQ:AVER {}',
            set_parser=int,
            get_parser=int,
            vals=Ints(min_value=2, max_value=65536)
        )

        self.memory_depth: Parameter = self.add_parameter(
            'memory_depth',
            label='Memory Depth',
            get_cmd='ACQ:MDEP?',
            set_cmd='ACQ:MDEP {}',
            set_parser=int,
            vals=Enum(*_MDEPTHS)
        )

        self.aquisition_type: Parameter = self.add_parameter(
            'aquisition_type',
            label='Acquisition type',
            set_cmd = 'ACQ:TYPE {}',
            get_cmd = 'ACQ:TYPE?',
            vals=Enum(*_ACQTYPES)
        )

        self.sample_rate: Parameter = self.add_parameter(
            'sample_rate',
            label='Sample Rate',
            set_cmd='ACQ:SRAT {}',
            get_cmd='ACQ:SRAT?',
            set_parser=float,
            get_parser=float,
            vals=Numbers(min_value=0)
        )

        self.anti_aliasing: Parameter = self.add_parameter(
            'anti_aliasing',
            label='Anti-Aliasing',
            set_cmd='ACQ:AAL {}',
            get_cmd='ACQ:AAL?',
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0)
        )

        self.source: Parameter = self.add_parameter(
            'source',
            label='Source',
            get_cmd='WAV:SOUR?',
            set_cmd='WAV:SOUR {}',
            vals=Enum(*_SOURCES)
        )

        self.waveform_mode: Parameter = self.add_parameter(
            'waveform_mode',
            label='Waveform Mode',
            get_cmd='WAV:MODE?',
            set_cmd='WAV:MODE {}',
            vals=Enum(*_WAVEMODES)
        )

        self.data_format: Parameter = self.add_parameter(
            'data_format',
            label='Data format',
            get_cmd='WAV:FORM?',
            set_cmd='WAV:FORM {}',
            vals=Enum(*_DATAFORMATS)
        )

        self.xscale: Parameter = self.add_parameter(
            'xscale',
            label='X Scale',
            unit='s',
            set_cmd='TIM:SCAL {}',
            get_cmd='TIM:SCAL?',
            get_parser=float,
            vals=Numbers(min_value=1e-9,max_value=1000)
        )

        self.xoffset: Parameter = self.add_parameter(
            'xoffset',
            label='X offset',
            unit='s',
            set_cmd='TIM:OFFS {}',
            get_cmd='TIM:OFFS?',
            get_parser=float,
            vals=Numbers()
        )

        # self.samples_per_div: Parameter = self.add_parameter(
        #     'samples_per_div',
        #     label='Samples per div',
        #     unit='num samples',
        #     set_cmd=

        # )

        self.xpoints: Parameter = self.add_parameter(
            'xpoints',
            label='X Points',
            get_cmd='WAV:POINTS?',
            set_cmd='WAV:POINTS {}',
            get_parser=int,
            set_parser=int,
            vals=Ints()
            )

        self.xinc: Parameter = self.add_parameter(
            'xinc',
            label='X Increment',
            unit='s',
            get_cmd='WAV:XINC?',
            get_parser=float,
            vals=Numbers()
        )

        self.xorigin: Parameter = self.add_parameter(
            'xorigin',
            label='X Origin',
            unit='s',
            get_cmd='WAV:XOR?',
            get_parser=float,
            vals=Numbers()
        )

        self.xdata: Parameter = self.add_parameter(
            'xdata',
            label='X data',
            unit='s',
            get_cmd=self._get_xdata
        )

        self.autoscale_status: Parameter = self.add_parameter(
            'autoscale_status',
            label='Autoscale status',
            set_cmd='SYST:AUT {}',
            get_cmd='SYST:AUT?',
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0)
        )

        self.trigger_type: Parameter = self.add_parameter(
            'trigger_type',
            label='Trigger type',
            get_cmd='TRIG:MODE?',
            set_cmd='TRIG:MODE {}',
            vals=Enum(*_TRIGTYPES)
        )

        self.trigger_coupling: Parameter = self.add_parameter(
            'trigger_coupling',
            label='Trigger coupling',
            set_cmd='TRIG:COUP {}',
            get_cmd='TRIG:COUP?',
            vals = Enum(*_TRIGCOUP)
        )

        self.trigger_status: Parameter = self.add_parameter(
            'trigger_status',
            label='Trigger status',
            get_cmd='TRIG:STAT?')

        self.trigger_mode: Parameter = self.add_parameter(
            'trigger_mode',
            label='Trigger mode',
            get_cmd='TRIG:SWE?',
            set_cmd='TRIG:SWE {}',
            vals=Enum(*_TRIGMODES)
        )

        self.trigger_holdoff: Parameter = self.add_parameter(
            'trigger_holdoff',
            label='Trigger holdoff',
            unit='s',
            get_cmd = 'TRIG:HOLD?',
            set_cmd = 'TRIG:HOLD {}',
            vals = Numbers(min_value=8e-9, max_value = 10)
        )

        self.trigger_edge_source: Parameter = self.add_parameter(
            'trigger_edge_source',
            label='Trigger Edge Source',
            set_cmd='TRIG:EDGE:SOUR {}',
            get_cmd='TRIG:EDGE:SOUR?',
        )

        self.trigger_edge_slope: Parameter = self.add_parameter(
            'trigger_edge_slope',
            label='Trigger Edge Slope',
            set_cmd='TRIG:EDGE:SLOP {}',
            get_cmd='TRIG:EDGE:SLOP?',
            vals=Enum('POS','NEG','RFAL')
        )

        self.trigger_edge_level: Parameter = self.add_parameter(
            'trigger_edge_level',
            label='Trigger edge level',
            set_cmd='TRIG:EDGE:LEV {}',
            get_cmd='TRIG:EDGE:LEV?',
            vals=Numbers()
        )

        self.add_function('clear', call_cmd='CLE')

        self.add_function('autoscale', call_cmd='AUT')

        self.add_function('run', call_cmd='RUN')

        self.add_function('stop', call_cmd='STOP')

        self.add_function('single', call_cmd='SING')

        self.add_function('force', call_cmd='TFOR')

        self.add_function('cls', call_cmd = '*CLS')

        self.add_function('opc', call_cmd='*OPC')

        self.channels={}
        for i in range(4):
            chan=Rigol_MSO5354_Channel(self,f'ch{i+1}',i+1)
            self.channels[i+1]=chan
            self.add_submodule(f'ch{i+1}',chan)

        self.connect_message()

    def _get_xdata(self):
        preamble=self.ask('WAV:PRE?').split(',')
        origin=float(preamble[5])
        increment=float(preamble[4])
        return origin+np.arange(self._num_points())*increment

    def _memory_depth(self) -> int:
        """The number of points in the internal memory."""
        mdep=self.ask('ACQ:MDEP?').strip()
        if mdep.upper()=='AUTO':
            # memory depth = sample rate x waveform length, and the screen is 10 divisions wide.
            return int(round(float(self.ask('ACQ:SRAT?'))*float(self.ask('TIM:SCAL?'))*10))
        multiplier={'k':1e3,'K':1e3,'M':1e6}.get(mdep[-1],1)
        if multiplier!=1:
            mdep=mdep[:-1]
        return int(round(float(mdep)*multiplier))

    def _num_points(self) -> int:
        """The number of points to read for the current waveform mode."""
        mode=self.waveform_mode()
        stopped=self.trigger_status()=='STOP'
        if mode=='RAW':
            if not stopped:
                raise RuntimeError(f'{self.name}: in RAW mode the internal memory is read, which the instrument only '
                                   f'allows when stopped. Call {self.name}.stop() or {self.name}.single() first.')
            return self._memory_depth()
        if mode=='MAX' and stopped:
            # MAX reads the internal memory when stopped, and the screen when running.
            return self._memory_depth()
        return 1000
