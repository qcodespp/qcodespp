import time
from typing import Any

import numpy as np
from qcodes import validators as vals
from qcodes.instrument import VisaInstrument, InstrumentChannel
from qcodes.parameters import Parameter, MultiParameter, create_on_off_val_mapping
from qcodes.validators import Enum, Numbers

# Setting frequency range
MIN_FREQ = 100e3
MAX_FREQ = 18e9

DATA_FORMATS = {"MLOG": {"names": ["mag", "null"], 
                         "labels": ["Log Magnitude", ""], 
                         "units": ["dB", "deg"]},
                "PHAS": {"names": ["phase", "null"],
                         "labels": ["Phase",""],
                         "units": ["deg",""]},
                "GDEL": {"names": ["group_delay", "null"],
                        "labels": ["Group Delay",""],
                        "units": ["s",""]},
                "SLIN": {"names": ["mag", "phase"],
                        "labels": ["Linear Magnitude", "Phase"], 
                        "units": ["", "deg"]},
                "SLOG": {"names": ["mag", "phase"],
                         "labels": ["Log Magnitude", "Phase"], 
                         "units": ["dB", "deg"]},
                "SCOM": {"names": ["real", "imag"],
                         "labels": ["Real Part", "Imaginary Part"], 
                         "units": ["", ""]},
                "SMIT": {"names": ["smith_real", "smith_imag"],
                         "labels": ["Smith Chart Real Part", "Smith Chart Imaginary Part"], 
                          "units": ["", ""]},
                "SADM": {"names": ["admittance_real", "admittance_imag"],
                         "labels": ["Admittance Real Part", "Admittance Imaginary Part"], 
                          "units": ["S", "S"]},
                "PLIN": {"names": ["mag", "phase"],
                         "labels": ["Linear Magnitude", "Phase"], 
                          "units": ["", "deg"]},
                "PLOG": {"names": ["mag", "phase"],
                         "labels": ["Log Magnitude", "Phase"], 
                          "units": ["dB", "deg"]},
                "POL": {"names": ["mag", "phase"],
                        "labels": ["Polar Magnitude", "Polar Phase"], 
                        "units": ["", "deg"]},
                "MLIN": {"names": ["mag", "phase"],
                         "labels": ["Linear Magnitude", "Phase"], 
                         "units": ["", "deg"]},
                "SWR": {"names": ["swr", "null"],
                        "labels": ["Standing Wave Ratio",""],
                        "units": ["",""]},
                "REAL": {"names": ["real", "null"],
                         "labels": ["Real Part",""],
                         "units": ["",""]},
                "IMAG": {"names": ["imag", "null"],
                         "labels": ["Imaginary Part",""],
                         "units": ["",""]},
                "UPH": {"names": ["unwrapped_phase", "null"],
                        "labels": ["Unwrapped Phase",""],
                        "units": ["deg",""]},
                "PPH": {"names": ["phase", "null"],
                        "labels": ["Phase",""],
                        "units": ["deg",""]}}

class Keysight_E5063A_Data(MultiParameter):
    """
    Return two column trace data from the Keysight E5063A Vector Network Analyzer.

    sdata: Returns the corrected S-parameter data for the trace.
    smem: Returns the corrected S-parameter data for the trace from memory.
    fdata: Returns the corrected and formatted S-parameter data for the trace.
    fmem: Returns the corrected and formatted S-parameter data for the trace from memory.

    See https://helpfiles.keysight.com/csg/e5063a/programming/remote_control/reading-writing_measurement_data/internal_data_processing.htm
    """

    def __init__(self, 
                name: str,
                trace: Keysight_E5063A_Trace,
                data_type: str,
                **kwargs) -> None:

        self.trace = trace
        self.data_type = data_type
        self.shapes = ((),())
        self.unit=''

        self.set_names_labels_units()

        kwargs={
            'names': self.names,
            'labels': self.labels,
            'units': self.units,
            'shapes': self.shapes,
            **kwargs
        }
        super().__init__(name, **kwargs)

    def get_raw(self):
        """Retrieve the complex measurement data for this trace."""
        chan = self.trace.channel_number
        trace = self.trace.trace_number
        raw= np.array(self.trace.ask(f"CALC{chan}:TRAC{trace}:DATA:{self.data_type}?").split(','), dtype=float)
        return [raw[::2],raw[1::2]]

    def set_names_labels_units(self):
        param_type=self.trace.param_type()
        if self.data_type in ["SDAT","SMEM"]:
            self.names = [f"{param_type}_real", f"{param_type}_imag"]
            self.labels = [f"{param_type} Real Part", f"{param_type} Imaginary Part"]
            self.units = ["", ""]
        else:
            data_format = self.trace.data_format()
            self.labels = [f"{param_type} {label}" for label in DATA_FORMATS[data_format]["labels"]]
            self.names = [f"{param_type}_{name}" for name in DATA_FORMATS[data_format]["names"]]
            self.units = DATA_FORMATS[data_format]["units"]

class Keysight_E5063A_Trace(InstrumentChannel):
    """
    A trace in a channel of the Keysight E5063A Vector Network Analyzer.
    """

    def __init__(self, parent: VisaInstrument, name: str, channel_number: int, trace_number: int) -> None:
        super().__init__(parent, name)
        self.channel_number = channel_number
        self.trace_number = trace_number

        self.data_format: Parameter = self.add_parameter(
            "data_format",
            label="Data Format",
            get_cmd=f"CALC{channel_number}:TRAC{trace_number}:FORM?",
            set_cmd=self._set_data_format,
            vals=Enum(*list(DATA_FORMATS.keys())),
        )
        """Parameter data_format"""

        self.param_type: Parameter = self.add_parameter(
            "param_type",
            label="Parameter Type",
            get_cmd=f"CALC{channel_number}:PAR{trace_number}:DEF?",
            set_cmd=self._set_param_type,
            vals=Enum("S11", "S12", "S21", "S22"),
        )

        self.sdata: Parameter = self.add_parameter(
            "sdata",
            parameter_class=Keysight_E5063A_Data,
            trace=self,
            data_type="SDAT",
        )

        self.smem: Parameter = self.add_parameter(
            "smem",
            parameter_class=Keysight_E5063A_Data,
            trace=self,
            data_type="SMEM",
        )

        self.fdata: Parameter = self.add_parameter(
            "fdata",
            parameter_class=Keysight_E5063A_Data,
            trace=self,
            data_type="FDAT",
        )

        self.fmem: Parameter = self.add_parameter(
            "fmem",
            parameter_class=Keysight_E5063A_Data,
            trace=self,
            data_type="FMEM",
        )

    def _set_data_format(self, value):
        """Set the data format for this trace."""
        self.write(f"CALC{self.channel_number}:TRAC{self.trace_number}:FORM {value}")
        for param in [self.sdata, self.smem, self.fdata, self.fmem]:
            param.set_names_labels_units()

    def _set_param_type(self, value):
        """Set the parameter type for this trace."""
        self.write(f"CALC{self.channel_number}:PAR{self.trace_number}:DEF {value}")
        for param in [self.sdata, self.smem, self.fdata, self.fmem]:
            param.set_names_labels_units()
    
class Keysight_E5063A_Channel(InstrumentChannel):
    """
    A channel of the Keysight E5063A Vector Network Analyzer.
    """

    def __init__(self, parent: VisaInstrument, name: str, channel_number: int) -> None:
        super().__init__(parent, name)
        self.channel_number = channel_number


        # Sets the start frequency of the analyzer.
        self.start_freq: Parameter = self.add_parameter(
            "start_freq",
            label="Start Frequency",
            get_cmd=f"SENS{channel_number}:FREQ:STAR?",
            get_parser=float,
            set_cmd=f"SENS{channel_number}:FREQ:STAR {{}}",
            unit="Hz",
            vals=Numbers(min_value=MIN_FREQ, max_value=MAX_FREQ),
        )
        """Parameter start_freq"""

        # Sets the stop frequency of the analyzer.
        self.stop_freq: Parameter = self.add_parameter(
            "stop_freq",
            label="Stop Frequency",
            get_cmd=f"SENS{channel_number}:FREQ:STOP?",
            get_parser=float,
            set_cmd=f"SENS{channel_number}:FREQ:STOP {{}}",
            unit="Hz",
            vals=Numbers(min_value=MIN_FREQ, max_value=MAX_FREQ),
        )
        """Parameter stop_freq"""

        # Sets the center frequency of the analyzer.
        self.center_freq: Parameter = self.add_parameter(
            "center_freq",
            label="Center Frequency",
            get_cmd=f"SENS{channel_number}:FREQ:CENT?",
            get_parser=float,
            set_cmd=f"SENS{channel_number}:FREQ:CENT {{}}",
            unit="Hz",
            vals=Numbers(min_value=MIN_FREQ, max_value=MAX_FREQ),
        )
        """Parameter center_freq"""

        # Sets the frequency span of the analyzer.
        self.span: Parameter = self.add_parameter(
            "span",
            label="Frequency Span",
            get_cmd=f"SENS{channel_number}:FREQ:SPAN?",
            get_parser=float,
            set_cmd=f"SENS{channel_number}:FREQ:SPAN {{}}",
            unit="Hz",
        )
        """Parameter span"""

        # Sets the number of data points for the measurement.
        self.points: Parameter = self.add_parameter(
            "points",
            label="Points",
            get_cmd=f"SENS{channel_number}:SWE:POIN?",
            get_parser=int,
            set_cmd=f"SENS{channel_number}:SWE:POIN {{}}",
            unit="",
            vals=Numbers(min_value=1, max_value=100003),
        )
        """Parameter points"""

        self.x: Parameter = self.add_parameter(
            "x",
            get_cmd=self._get_x,
            label="X Data",
            unit="",
        )

        self.freq: Parameter = self.add_parameter(
            "freq",
            get_cmd=self._get_freq,
            label="Frequency",
            unit="Hz",
        )

        # Set the units for returning S-parameters
        self.snp_format: Parameter = self.add_parameter(
            "snp_format",
            label="SNP Format",
            get_cmd=self._get_snp_format,
            set_cmd=self._set_snp_format,
            vals=Enum("RI", "MA", "DB", "AUTO"),
        )
        """Parameter snp_format"""

        self.data_format: Parameter = self.add_parameter(
            "data_format",
            label="Data Format",
            get_cmd=f"CALC{channel_number}:FORM?",
            set_cmd=self._set_data_format,
            vals=Enum(*list(DATA_FORMATS.keys())),
        )
        """Parameter data_format"""

        # Sets the RF power output level.
        self.source_power: Parameter = self.add_parameter(
            "source_power",
            label="source_power",
            unit="dBm",
            get_cmd=f"SOUR{channel_number}:POW?",
            set_cmd=f"SOUR{channel_number}:POW {{}}",
            get_parser=float,
            vals=Numbers(min_value=-100, max_value=20),
        )
        """Parameter source_power"""

        # Sets the bandwidth of the digital IF filter to be used in the measurement.
        self.if_bandwidth: Parameter = self.add_parameter(
            "if_bandwidth",
            label="if_bandwidth",
            unit="Hz",
            get_cmd=f"SENS{channel_number}:BWID?",
            set_cmd=f"SENS{channel_number}:BWID {{}}",
            get_parser=float,
            vals=Numbers(min_value=1, max_value=15e6),
        )
        """Parameter if_bandwidth"""

        # Sets the type of analyzer sweep mode. First set sweep type, then set sweep parameters such as frequency or power settings. Default is LIN
        self.sweep_type: Parameter = self.add_parameter(
            "sweep_type",
            label="Type",
            get_cmd=f"SENS{channel_number}:SWE:TYPE?",
            set_cmd=f"SENS{channel_number}:SWE:TYPE {{}}",
            vals=Enum("LIN", "LOG", "SEGM"),
        )
        """Parameter sweep_type"""

        # Sets the time the analyzer takes to complete one sweep.
        self.sweep_time: Parameter = self.add_parameter(
            "sweep_time",
            label="sweep_time",
            unit="s",
            get_parser=float,
            get_cmd=f"SENS{channel_number}:SWE:TIME?",
            set_cmd=f"SENS{channel_number}:SWE:TIME {{}}",
        )
        """Parameter sweep_time"""

        # Turns the automatic sweep time function ON or OFF.
        self.sweep_time_auto: Parameter = self.add_parameter(
            "sweep_time_auto",
            label="sweep_time_auto",
            get_parser=float,
            get_cmd=f"SENS{channel_number}:SWE:TIME:AUTO?",
            set_cmd=f"SENS{channel_number}:SWE:TIME:AUTO {{}}",
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0),
        )
        """Parameter sweep_time_auto"""

        # Turns trace averaging ON or OFF. Default OFF
        self.averages_enabled: Parameter = self.add_parameter(
            "averages_enabled",
            label="Averages Enabled",
            get_cmd=f"SENS{channel_number}:AVER?",
            set_cmd=f"SENS{channel_number}:AVER {{}}",
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0"),
        )
        """Parameter averages_enabled"""

        # Sets the number of measurements to combine for an average. Must also set SENS:AVER[:STATe] ON
        self.averages_count: Parameter = self.add_parameter(
            "averages_count",
            label="Averages Count",
            get_cmd=f"SENS{channel_number}:AVER:COUN?",
            get_parser=int,
            set_cmd=f"SENS{channel_number}:AVER:COUN {{}}",
            vals=Numbers(min_value=1, max_value=999),
        )
        """Parameter averages count"""

        # Clear averages
        # Clears and restarts averaging of the measurement data. Does NOT apply to point averaging.
        self.add_function("clear_averages", call_cmd="SENS:AVER:CLE")

        self.cal_kit: Parameter = self.add_parameter(
            "cal_kit",
            get_cmd=f'SENS{channel_number}:CORR:COLL:CKIT?',
            set_cmd=f'SENS{channel_number}:CORR:COLL:CKIT {{}}',
            label="Calibration Kit",
            vals=vals.Ints(1, 30),
        )

        self.cal_type: Parameter = self.add_parameter(
            "cal_type",
            get_cmd=f'SENS{channel_number}:CORR:COLL:METH:TYPE?',
            set_cmd=f'SENS{channel_number}:CORR:COLL:METH:TYPE {{}}',
            label="Calibration Type",
            vals=vals.Enum("ERES", "OPEN", "SHOR", "SOLT1", "SOLT2", "THRU", "TRL2"),
        )

        self.applied_cal_type: Parameter = self.add_parameter(
            "applied_cal_type",
            get_cmd=f'SENS{channel_number}:CORR:TYPE?',
            label="Applied Calibration Type",
        )

        self.cal_status: Parameter = self.add_parameter(
            "cal_status",
            get_cmd=f'SENS{channel_number}:CORR:STAT?',
            label="Calibration Status",
            set_cmd=f'SENS{channel_number}:CORR:STAT {{}}',
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0"),
        )

        self.traces={}
        for trace_number in range(1, 5):  # 4 traces per channel
            trace_name = f"tr{trace_number}"
            trace = Keysight_E5063A_Trace(self, trace_name, channel_number, trace_number)
            self.add_submodule(trace_name, trace)
            self.traces[trace_number] = trace

    def coll_cal_data(self,cal_type,*port):
        """Perform a calibration on the specified port."""
        chan = self.channel_number
        if cal_type in ["THRU", "ISOL"]:
            self.write(f'SENS{chan}:CORR:COLL:{cal_type} {port[0]},{port[1]}')
        else:
            self.write(f'SENS{chan}:CORR:COLL:{cal_type} {port[0]}')
        # while self.ask('*OPC?') != '+1':
        #     time.sleep(0.1)

    def save_cal(self):
        self.write(f'SENS{self.channel_number}:CORR:COLL:SAVE')

    def _set_cal_type(self, value):
        """Set the calibration type."""
        chan = self.channel_number
        self.write(f'SENS{chan}:CORR:COLL:METH:TYPE {value}')

    def _get_x(self):
        """return x axis values"""
        chan = self.channel_number
        return np.array(self.ask(f"CALC{chan}:DATA:XAX?").split(','), dtype=float)

    def _get_freq(self):
        """Get the frequency values."""
        chan = self.channel_number
        return np.array(self.ask(f"SENS{chan}:FREQ:DATA?").split(','), dtype=float)

    def _get_snp_format(self):
        """Get the S-parameter format."""
        self.parent.set_active_channel(self.channel_number)
        return self.ask("MMEM:STOR:SNP:FORM?")

    def _set_snp_format(self, value):
        """Set the S-parameter format."""
        if value not in ["RI", "MA", "DB", "AUTO"]:
            raise ValueError("S-parameter format must be one of: RI, MA, DB, AUTO.")
        self.parent.set_active_channel(self.channel_number)
        self.write(f"MMEM:STOR:SNP:FORM {value}")

    def _set_data_format(self, value):
        """Set the data format for this channel."""
        self.write(f"CALC{self.channel_number}:FORM {value}")
        for trace_number in range(1, 5):
            trace = getattr(self, f"tr{trace_number}")
            for param in [trace.sdata, trace.smem, trace.fdata, trace.fmem]:
                param.set_names_labels_units()

class Keysight_E5063A(VisaInstrument):
    """
    Qcodes driver for the Keysight E5063A Vector Network Analyzer.
    Not tested 14/09/2026. Simply constructed from the manual.
    """

    def __init__(self, name: str, address: str, **kwargs: Any) -> None:
        time.sleep(5)  # Required sleep to ensure the instruments can start being queried
        super().__init__(name, address, terminator="\n", **kwargs)

                    # Sets the source of the sweep trigger signal. Default is IMMediate.
        self.trigger_source: Parameter = self.add_parameter(
            "trigger_source",
            label="Trigger Source",
            get_cmd="TRIG:SOUR?",
            set_cmd="TRIG:SOUR {}",
            vals=Enum("INT", "EXT", "MAN", "BUS"),
        )
        """Trigger Source"""

        # Specifies the polarity expected by the external trigger input circuitry. Also specify TRIG:TYPE (Level |Edge).
        self.trigger_slope: Parameter = self.add_parameter(
            "trigger_slope",
            label="Trigger Slope",
            get_cmd="TRIG:EXT:SLOP?",
            set_cmd="TRIG:EXT:SLOP {}",
            vals=Enum("POS", "NEG"),
        )
        """Trigger Slope"""

        # Sets the data format for transferring measurement data and frequency data. Default is ASCii,0.
        self.format_data: Parameter = self.add_parameter(
            "format_data",
            label="Format Data",
            get_cmd="FORM:DATA?",
            set_cmd="FORM:DATA {}",
            vals=Enum("REAL32", "REAL", "ASCii"),
        )
        """Parameter format data"""

        # Turns RF power from the source ON or OFF.
        self.rf_on: Parameter = self.add_parameter(
            "rf_on",
            label="RF ON",
            get_cmd="OUTP?",
            set_cmd="OUTP {}",
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0"),
        )
        """Parameter RF Power Source"""

        # Set the byte order used for GPIB data transfer.
        # Some computers read data from the analyzer in the reverse order. This command is only implemented if FORMAT:DATA is set to :REAL.
        # Default is NORM
        self.format_border: Parameter = self.add_parameter(
            "format_border",
            label="Format Border",
            get_cmd="FORM:BORD?",
            set_cmd="FORM:BORD {}",
            vals=Enum("NORM", "SWAP"),
        )
        """Parameter Format Border"""

        # Status Operation
        # Summarizes conditions in the Averaging and Operation:Define:User<1|2|3> event registers.
        self.operation_status: Parameter = self.add_parameter(
            "operation_status",
            label="Operation Status",
            get_cmd="STAT:OPER:COND?",
            get_parser=int,
        )
        """Status Operation"""

        self.channels={}
        for channel_number in range(1, 5):  # 4 channels
            channel_name = f"ch{channel_number}"
            channel = Keysight_E5063A_Channel(self, channel_name, channel_number)
            self.add_submodule(channel_name, channel)
            self.channels[channel_number] = channel

        # Clear Status
        # Clears the instrument status byte by emptying the error queue and clearing all event registers. Also cancels any preceding *OPC command or query.
        self.add_function("cls", call_cmd="*CLS")

        # Operation complete command
        # Generates the OPC message in the standard event status register when all pending overlapped operations have been completed (for example, a sweep, or a Default).
        self.add_function("opc", call_cmd="*OPC")

        # System Reset
        # Deletes all traces, measurements, and windows.
        self.add_function("system_reset", call_cmd="SYST:PRES")

        self.connect_message()

    def set_active_channel(self, channel_number: int):
        """Set the active channel for the instrument."""
        if channel_number not in [1, 2, 3, 4]:
            raise ValueError("Channel number must be between 1 and 4.")
        self.write(f"DISP:WIND{channel_number}:ACT")

    def get_data(self, chan=1, trace=1):
        """Retrieve the complex measurement data for a specified channel and trace."""
        self.format_data("ASCii,0")  # recommended to avoid binary data parsing errors
        raw= np.array(self.ask(f"CALC{chan}:TRAC{trace}:DATA:SDAT?").split(','), dtype=float)
        return [raw[::2],raw[1::2]]

    def get_x(self,chan=1):
        """return x axis values from specified trace"""
        #self.format_data("REAL,64")  # recommended to avoid frequency rounding errors
        self.format_data("ASCii,0")
        return np.array(self.ask(f"CALC{chan}:DATA:XAX?").split(','), dtype=float)
    
    def get_y(self,chan=1, trace=1):
        """Retrieve y data from specified trace"""
        self.format_data("ASCii")  # recommended to avoid binary data parsing errors
        return np.array(self.ask(f'CALC{chan}:TRAC{trace}:DATA:FDATA?').split(','), dtype=float)

    # def get_snp(self,n=2):
    #     """return all S-parameters for n ports"""
    #     self.format_data("ASCii,0")  # recommended to avoid binary data parsing errors
    #     raw=np.array(self.ask(f"CALC:MEAS:DATA:SNP? {n}").split(','), dtype=float)
    #     dat_len=self.points()
    #     return raw.reshape(len(raw)//dat_len, dat_len)
