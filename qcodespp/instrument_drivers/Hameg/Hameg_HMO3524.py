"""
QCoDeS driver for the Hameg HMO3524 (and HMO3522) digital oscilloscope.

Constructed from the HAMEG "SCPI Programmers Manual HMO3522 / 3524" (firmware 01.020 and later).

Example:
    scope = Hameg_HMO3524("scope", "TCPIP0::192.168.1.10::INSTR")
    scope.ch1.state(True)
    scope.ch1.scale(0.1)            # 100 mV/div
    scope.timebase_scale(1e-6)      # 1 us/div
    time, voltage = scope.ch1.waveform()

    # Automatic measurement
    scope.meas1.source("CH1")
    scope.meas1.measurement_type("VPP")
    scope.meas1.value()
"""
import warnings
from typing import Any

import numpy as np
from qcodes.instrument import VisaInstrument, InstrumentChannel
from qcodes.parameters import Parameter, MultiParameter, create_on_off_val_mapping
from qcodes.validators import Enum, Ints, MultiType, Numbers, Strings

NUM_LOGIC_CHANNELS = 16
NUM_PODS = 2
NUM_MEASUREMENTS = 4
NUM_REFERENCES = 4

# Automatic measurement functions (:MEASure:TRACe<n>:TYPE), keyed by the short form the
# instrument returns. Values are (label, unit) for the measured value.
MEASUREMENT_TYPES = {
    "FREQ": ("Frequency", "Hz"),
    "PER": ("Period", "s"),
    "VPP": ("Peak-to-peak Voltage", "V"),
    "VMAX": ("Maximum Voltage", "V"),
    "VMIN": ("Minimum Voltage", "V"),
    "VAV": ("Average Voltage", "V"),
    "VRMS": ("RMS Voltage", "V"),
    "HPC": ("Positive Pulse Count", ""),
    "LPC": ("Negative Pulse Count", ""),
    "REC": ("Rising Edge Count", ""),
    "FEC": ("Falling Edge Count", ""),
    "TRIS": ("Rise Time", "s"),
    "TFAL": ("Fall Time", "s"),
    "AMPL": ("Amplitude", "V"),
    "NONE": ("Value", ""),
}

# Trigger signal measurement functions (:MEASure:TRIGger<n>:TYPE)
TRIGGER_MEASUREMENT_TYPES = {
    "FREQ": ("Trigger Frequency", "Hz"),
    "PER": ("Trigger Period", "s"),
    "NONE": ("Trigger Value", ""),
}

# Status codes returned alongside every measurement value
MEASUREMENT_STATUS = {
    2000: "the value is valid",
    2001: "no valid data were available at the time of measurement",
    2002: "the measurement is not possible with the current oscilloscope settings",
    2007: "the input signal exceeds the upper limit of the converter range",
    2008: "the input signal is below the lower limit of the converter range",
    2009: "the input signal exceeds both the upper and lower limits of the converter range",
}
MEASUREMENT_VALID = 2000

# Floats used by the instrument to represent infinity and 'not a number'
SCPI_INF = 9.9e37
SCPI_NAN = 9.91e37


def _parse_float(response: str) -> float:
    """Parse a float, converting the instrument's INF, NINF and NAN representations."""
    value = float(response)
    if np.isclose(value, SCPI_NAN, rtol=1e-4):
        return np.nan
    if np.isclose(abs(value), SCPI_INF, rtol=1e-4):
        return float(np.copysign(np.inf, value))
    return value


def _parse_int(response: str) -> int:
    """Parse integers that the instrument returns in floating point notation, e.g. '2.0E+00'."""
    return int(round(float(response)))


def _strip_quotes(response: str) -> str:
    return response.strip().strip('"')


def _normalize_source(response: str) -> str:
    """
    Normalize a waveform source name as reported by the instrument.

    The instrument may drop the index 1 from paths in its responses (e.g. 'CH' for 'CH1', see
    the :TRACe? and :CHANnel examples in the manual), so it is added back here.
    """
    source = response.strip().strip('"').upper()
    if source in ("CH", "ZCH", "RE"):
        source += "1"
    return source


def _parse_measurement(response: str, name: str) -> float:
    """
    Parse a '<value>,<status>' measurement response, e.g. '1.027749E+03,2000'.

    Returns the value, and warns if the status code indicates that the value is not valid.
    """
    value_str, _, status_str = response.partition(",")
    value = _parse_float(value_str)
    if status_str.strip():
        status = _parse_int(status_str)
        if status != MEASUREMENT_VALID:
            description = MEASUREMENT_STATUS.get(status, "unknown status")
            warnings.warn(f"{name}: {description} (status {status}).", stacklevel=2)
    return value


class HMO3524_Waveform(MultiParameter):
    """
    Time axis and voltage of an analog channel's waveform, from a single read of the waveform.
    """

    def __init__(self, name: str, instrument: "HMO3524_Channel", **kwargs: Any) -> None:
        n = instrument.channel_number
        # Names include the channel, since Measure stores the data of a MultiParameter by name.
        super().__init__(
            name,
            names=(f"ch{n}_time", f"ch{n}_voltage"),
            shapes=((), ()),
            labels=(f"Channel {n} Time", f"Channel {n} Voltage"),
            units=("s", "V"),
            instrument=instrument,
            **kwargs,
        )
        self.unit = ""

    def get_raw(self):
        channel = self.instrument
        voltage = channel._get_voltage()
        return [channel._time_axis(len(voltage)), voltage]


class HMO3524_Channel(InstrumentChannel):
    """
    An analog input channel of the Hameg HMO3524 oscilloscope.

    The waveform can be read as `waveform` (time and voltage together, e.g. for Measure), or as
    `time` and `voltage` separately (e.g. inside a Loop, or Measure(ch.voltage, setpoints=[ch.time])).
    Only displayed waveforms can be read, so the channel must be switched on.
    """

    def __init__(self, parent: VisaInstrument, name: str, channel_number: int) -> None:
        super().__init__(parent, name)
        self.channel_number = channel_number
        cmd = f":CHAN{channel_number}"

        # Switches the channel on or off. Only displayed channels can be read out.
        self.state: Parameter = self.add_parameter(
            "state",
            label="State",
            get_cmd=f"{cmd}:STAT?",
            set_cmd=f"{cmd}:STAT {{}}",
            val_mapping=create_on_off_val_mapping(on_val="ON", off_val="OFF"),
        )
        """Channel on/off"""

        # Sets the vertical sensitivity. Includes the probe attenuation.
        self.scale: Parameter = self.add_parameter(
            "scale",
            label="Vertical Scale",
            unit="V/div",
            get_cmd=f"{cmd}:SCAL?",
            set_cmd=f"{cmd}:SCAL {{}}",
            get_parser=float,
            vals=Numbers(min_value=0),
        )
        """Vertical scale"""

        # Positions the trace on the screen, in divisions from the centre.
        self.position: Parameter = self.add_parameter(
            "position",
            label="Vertical Position",
            unit="div",
            get_cmd=f"{cmd}:POS?",
            set_cmd=f"{cmd}:POS {{}}",
            get_parser=float,
            vals=Numbers(),
        )
        """Vertical position"""

        # Compensates for a DC offset at the probe tip.
        self.offset: Parameter = self.add_parameter(
            "offset",
            label="Offset",
            unit="V",
            get_cmd=f"{cmd}:OFFS?",
            set_cmd=f"{cmd}:OFFS {{}}",
            get_parser=float,
            vals=Numbers(),
        )
        """DC offset"""

        # Sets the input coupling.
        self.coupling: Parameter = self.add_parameter(
            "coupling",
            label="Coupling",
            get_cmd=f"{cmd}:COUP?",
            set_cmd=f"{cmd}:COUP {{}}",
            vals=Enum("AC", "DC", "GND"),
        )
        """Input coupling"""

        # Switches the 50 Ohm termination in (50) or out (1e6).
        self.impedance: Parameter = self.add_parameter(
            "impedance",
            label="Input Impedance",
            unit="Ohm",
            get_cmd=f"{cmd}:IMP?",
            set_cmd=f"{cmd}:IMP {{}}",
            get_parser=float,
            vals=Enum(50, 1e6),
        )
        """Input impedance"""

        # Inserts a bandwidth limiting filter in the input circuitry.
        self.bandwidth_limit: Parameter = self.add_parameter(
            "bandwidth_limit",
            label="Bandwidth Limit",
            get_cmd=f"{cmd}:BWL?",
            set_cmd=f"{cmd}:BWL {{}}",
            val_mapping=create_on_off_val_mapping(on_val="ON", off_val="OFF"),
        )
        """Bandwidth limit filter on/off"""

        # Sets the probe attenuation factor, between 0.001 and 1000.
        # Per the manual, 0.1 corresponds to a x10 probe. Writes are ignored if a probe with
        # attenuation read-out is connected.
        self.probe: Parameter = self.add_parameter(
            "probe",
            label="Probe Attenuation",
            get_cmd=f"{cmd}:PROB?",
            set_cmd=f"{cmd}:PROB {{}}",
            get_parser=float,
            vals=Numbers(min_value=1e-3, max_value=1e3),
        )
        """Probe attenuation"""

        # Sets the polarity of the input signal.
        self.polarity: Parameter = self.add_parameter(
            "polarity",
            label="Polarity",
            get_cmd=f"{cmd}:POL?",
            set_cmd=f"{cmd}:POL {{}}",
            vals=Enum("NORM", "INV"),
        )
        """Polarity"""

        # Sets a time offset for the channel, to compensate for cable or probe delays.
        self.deskew: Parameter = self.add_parameter(
            "deskew",
            label="Deskew",
            unit="s",
            get_cmd=f"{cmd}:DESK?",
            set_cmd=f"{cmd}:DESK {{}}",
            get_parser=float,
            vals=Numbers(),
        )
        """Deskew"""

        # Waveform data are not stored in the snapshot (like MultiParameter, which excludes them by default).
        self.time: Parameter = self.add_parameter(
            "time",
            label=f"Channel {channel_number} Time",
            unit="s",
            get_cmd=self._get_time,
            snapshot_value=False,
        )
        """Time axis of the channel's waveform"""

        self.voltage: Parameter = self.add_parameter(
            "voltage",
            label=f"Channel {channel_number} Voltage",
            unit="V",
            get_cmd=self._get_voltage,
            snapshot_value=False,
        )
        """Voltage of the channel's waveform"""

        self.waveform: HMO3524_Waveform = self.add_parameter(
            "waveform",
            parameter_class=HMO3524_Waveform,
        )
        """Time and voltage of the channel's waveform"""

    def _select_for_readout(self) -> None:
        """
        Select this channel's waveform for read out, in ASCII format (voltages as text).

        Only displayed waveforms can be selected, and the instrument ignores the request otherwise,
        so the selection is read back to avoid returning the data of another channel.
        """
        source = f"CH{self.channel_number}"
        self.write(f":TRAC:SOUR {source}")
        selected = _normalize_source(self.ask(":TRAC:SOUR?"))
        if selected != source:
            raise RuntimeError(
                f"{self.full_name}: the instrument did not select {source} for read out (the selected "
                f"source is {selected}). Only displayed waveforms can be read out; switch on the channel "
                f"with {self.state.full_name}(True)."
            )
        self.write(":TRAC:FORM ASC")

    def _get_voltage(self) -> np.ndarray:
        self._select_for_readout()
        return np.array(self.ask(":TRAC:DATA?").strip().strip(",").split(","), dtype=float)

    def _get_time(self) -> np.ndarray:
        self._select_for_readout()
        return self._time_axis(_parse_int(self.ask(":TRAC:POIN?")))

    def _time_axis(self, num_points: int) -> np.ndarray:
        """Time axis of the waveform selected for read out."""
        x_increment = float(self.ask(":TRAC:XINC?"))
        x_origin = float(self.ask(":TRAC:XOR?"))
        # The manual gives t = n * XINC - XOR, but defines XOR as the time of the first point
        # (e.g. -3 ms), so XOR is added here. The reference index XREF is always 0.
        return x_origin + np.arange(num_points) * x_increment


class HMO3524_LogicChannel(InstrumentChannel):
    """
    A logic (digital) channel D0..D15 of the Hameg HMO3524, available with the optional logic probes.
    """

    def __init__(self, parent: VisaInstrument, name: str, channel_number: int) -> None:
        super().__init__(parent, name)
        self.channel_number = channel_number
        cmd = f":LOG{channel_number}"

        # Switches the logic channel on or off.
        self.state: Parameter = self.add_parameter(
            "state",
            label="State",
            get_cmd=f"{cmd}:STAT?",
            set_cmd=f"{cmd}:STAT {{}}",
            val_mapping=create_on_off_val_mapping(on_val="ON", off_val="OFF"),
        )
        """Logic channel on/off"""

        # Sets the position of the logic channel on the display.
        self.position: Parameter = self.add_parameter(
            "position",
            label="Position",
            unit="div",
            get_cmd=f"{cmd}:POS?",
            set_cmd=f"{cmd}:POS {{}}",
            get_parser=float,
            vals=Numbers(),
        )
        """Display position"""

        # Sets the display height of the logic signal.
        self.size: Parameter = self.add_parameter(
            "size",
            label="Display Size",
            get_cmd=f"{cmd}:SIZE?",
            set_cmd=f"{cmd}:SIZE {{}}",
            vals=Enum("SMAL", "MED", "LARG"),
        )
        """Display size"""


class HMO3524_Pod(InstrumentChannel):
    """
    A logic pod of the Hameg HMO3524. POD1 contains D0..D7 and POD2 contains D8..D15.
    """

    def __init__(self, parent: VisaInstrument, name: str, pod_number: int) -> None:
        super().__init__(parent, name)
        self.pod_number = pod_number
        cmd = f":POD{pod_number}"

        # Switches the pod on or off.
        self.state: Parameter = self.add_parameter(
            "state",
            label="State",
            get_cmd=f"{cmd}:STAT?",
            set_cmd=f"{cmd}:STAT {{}}",
            val_mapping=create_on_off_val_mapping(on_val="ON", off_val="OFF"),
        )
        """Pod on/off"""

        # Sets the threshold of the logic comparator. USER (or USER1) and USER2 select the
        # user-defined levels. The manual uses both USER and USER1 for user level 1.
        self.threshold: Parameter = self.add_parameter(
            "threshold",
            label="Threshold",
            get_cmd=f"{cmd}:THR?",
            set_cmd=f"{cmd}:THR {{}}",
            vals=Enum("CMOS", "ECL", "TTL", "USER", "USER1", "USER2"),
        )
        """Logic threshold"""

        self.user_level1: Parameter = self.add_parameter(
            "user_level1",
            label="User Level 1",
            unit="V",
            get_cmd=f"{cmd}:THR:UDL1?",
            set_cmd=f"{cmd}:THR:UDL1 {{}}",
            get_parser=float,
            vals=Numbers(),
        )
        """User-defined threshold level 1"""

        self.user_level2: Parameter = self.add_parameter(
            "user_level2",
            label="User Level 2",
            unit="V",
            get_cmd=f"{cmd}:THR:UDL2?",
            set_cmd=f"{cmd}:THR:UDL2 {{}}",
            get_parser=float,
            vals=Numbers(),
        )
        """User-defined threshold level 2"""


class HMO3524_Measurement(InstrumentChannel):
    """
    One of the four automatic measurements of the Hameg HMO3524.

    Each measurement has a waveform measurement (measurement_type, source, value) and a trigger
    signal measurement (trigger_type, trigger_value). The label and unit of value and
    trigger_value follow the selected type. A warning is issued if the instrument reports that
    a value is not valid, e.g. because the signal exceeds the converter range.
    """

    def __init__(self, parent: VisaInstrument, name: str, measurement_number: int, sources: list[str]) -> None:
        super().__init__(parent, name)
        self.measurement_number = measurement_number
        trac = f":MEAS:TRAC{measurement_number}"
        trig = f":MEAS:TRIG{measurement_number}"

        # Measured values are not queried when taking a snapshot, since unused measurements
        # (type NONE) would each give a warning.
        self.value: Parameter = self.add_parameter(
            "value",
            label=f"Measurement {measurement_number}",
            get_cmd=f"{trac}:VAL?",
            get_parser=lambda response: _parse_measurement(response, self.value.full_name),
            snapshot_get=False,
        )
        """Measured value. NaN if no valid value is available."""

        # Sets the measurement function, see MEASUREMENT_TYPES.
        self.measurement_type: Parameter = self.add_parameter(
            "measurement_type",
            label="Measurement Type",
            get_cmd=self._get_measurement_type,
            set_cmd=self._set_measurement_type,
            vals=Enum(*MEASUREMENT_TYPES),
        )
        """Measurement function"""

        # Sets the waveform to be measured.
        self.source: Parameter = self.add_parameter(
            "source",
            label="Source",
            get_cmd=f"{trac}:SOUR?",
            set_cmd=f"{trac}:SOUR {{}}",
            get_parser=_normalize_source,
            vals=Enum(*sources),
        )
        """Measurement source"""

        self.trigger_value: Parameter = self.add_parameter(
            "trigger_value",
            label=f"Measurement {measurement_number} Trigger",
            get_cmd=f"{trig}:VAL?",
            get_parser=lambda response: _parse_measurement(response, self.trigger_value.full_name),
            snapshot_get=False,
        )
        """Measured value of the trigger signal. NaN if no valid value is available."""

        # Sets the measurement function for the trigger signal (not the waveform).
        self.trigger_type: Parameter = self.add_parameter(
            "trigger_type",
            label="Trigger Measurement Type",
            get_cmd=self._get_trigger_type,
            set_cmd=self._set_trigger_type,
            vals=Enum(*TRIGGER_MEASUREMENT_TYPES),
        )
        """Trigger signal measurement function"""

        # Query the types so that value and trigger_value get the right labels and units.
        self.measurement_type()
        self.trigger_type()

    def _get_measurement_type(self) -> str:
        value = self.ask(f":MEAS:TRAC{self.measurement_number}:TYPE?").strip().upper()
        self._update_label_unit(self.value, MEASUREMENT_TYPES, value)
        return value

    def _set_measurement_type(self, value: str) -> None:
        self.write(f":MEAS:TRAC{self.measurement_number}:TYPE {value}")
        self._update_label_unit(self.value, MEASUREMENT_TYPES, value)

    def _get_trigger_type(self) -> str:
        value = self.ask(f":MEAS:TRIG{self.measurement_number}:TYPE?").strip().upper()
        self._update_label_unit(self.trigger_value, TRIGGER_MEASUREMENT_TYPES, value)
        return value

    def _set_trigger_type(self, value: str) -> None:
        self.write(f":MEAS:TRIG{self.measurement_number}:TYPE {value}")
        self._update_label_unit(self.trigger_value, TRIGGER_MEASUREMENT_TYPES, value)

    def _update_label_unit(self, param: Parameter, types: dict, value: str) -> None:
        label, unit = types.get(value, ("Value", ""))
        param.label = f"Measurement {self.measurement_number} {label}"
        param.unit = unit


class Hameg_HMO3524(VisaInstrument):
    """
    QCoDeS driver for the Hameg HMO3524 digital oscilloscope. Also supports the 2-channel HMO3522.

    Not tested on hardware 12/11/2026. Constructed from the SCPI Programmers Manual
    (firmware 01.020 and later).

    Submodules:
        ch1..ch4:      analog channels (ch1 and ch2 only on the HMO3522)
        d0..d15:       logic channels
        pod1, pod2:    logic pods
        meas1..meas4:  automatic measurements

    Args:
        name: Instrument name.
        address: VISA resource address.
        num_channels: Number of analog channels. If None, it is set from the model in *IDN?
            (2 for the HMO3522, otherwise 4).
    """

    def __init__(self, name: str, address: str, num_channels: int | None = None, **kwargs: Any) -> None:
        super().__init__(name, address, terminator="\n", **kwargs)

        if num_channels is None:
            num_channels = 2 if "3522" in str(self.IDN().get("model")) else 4
        self.num_channels = num_channels

        analog_sources = [f"CH{n}" for n in range(1, num_channels + 1)]
        reference_sources = [f"RE{n}" for n in range(1, NUM_REFERENCES + 1)]
        logic_sources = [f"D{n}" for n in range(NUM_LOGIC_CHANNELS)]

        # ACQUISITION

        # Starts or stops signal capturing. Reading also returns COMP (all captures completed)
        # or BRE (last capture stopped before completion).
        self.acquisition_state: Parameter = self.add_parameter(
            "acquisition_state",
            label="Acquisition State",
            get_cmd=":ACQ:STAT?",
            set_cmd=":ACQ:STAT {}",
            vals=Enum("RUN", "STOP"),
        )
        """Acquisition state"""

        # Sets the acquisition type: refresh, roll, envelope or average.
        self.acquisition_type: Parameter = self.add_parameter(
            "acquisition_type",
            label="Acquisition Type",
            get_cmd=":ACQ:TYPE?",
            set_cmd=":ACQ:TYPE {}",
            vals=Enum("REFR", "ROLL", "ENV", "AVER"),
        )
        """Acquisition type"""

        # Sets the number of acquisitions to average. Used when acquisition_type is AVER.
        self.average_count: Parameter = self.add_parameter(
            "average_count",
            label="Average Count",
            get_cmd=":ACQ:AVER:COUN?",
            set_cmd=":ACQ:AVER:COUN {}",
            get_parser=_parse_int,
            vals=Enum(*[2**n for n in range(1, 10)]),
        )
        """Number of averages"""

        # Activates the optional high resolution acquisition mode.
        self.high_resolution: Parameter = self.add_parameter(
            "high_resolution",
            label="High Resolution",
            get_cmd=":ACQ:HRES?",
            set_cmd=":ACQ:HRES {}",
            val_mapping=create_on_off_val_mapping(on_val="ON", off_val="OFF"),
        )
        """High resolution mode on/off"""

        # Enables automatic peak detection (True = AUTO). This does not by itself mean peak
        # detection is active.
        self.peak_detect: Parameter = self.add_parameter(
            "peak_detect",
            label="Automatic Peak Detect",
            get_cmd=":ACQ:PEAK?",
            set_cmd=":ACQ:PEAK {}",
            val_mapping=create_on_off_val_mapping(on_val="AUTO", off_val="OFF"),
        )
        """Automatic peak detection on/off"""

        # Activates automatic real time sampling (as opposed to random sampling).
        self.realtime: Parameter = self.add_parameter(
            "realtime",
            label="Real Time Sampling",
            get_cmd=":ACQ:REAL?",
            set_cmd=":ACQ:REAL {}",
            val_mapping=create_on_off_val_mapping(on_val="ON", off_val="OFF"),
        )
        """Real time sampling on/off"""

        # Prioritises the waveform update rate (MWAV), the sampling rate (MSAM) or neither (AUTO).
        self.waveform_rate: Parameter = self.add_parameter(
            "waveform_rate",
            label="Waveform Rate",
            get_cmd=":ACQ:WRAT?",
            set_cmd=":ACQ:WRAT {}",
            vals=Enum("MWAV", "MSAM", "AUTO"),
        )
        """Waveform/sampling rate mode"""

        # HORIZONTAL

        # Sets the main time base. Limits depend on the acquisition mode, e.g. ROLL requires > 50 ms/div.
        self.timebase_scale: Parameter = self.add_parameter(
            "timebase_scale",
            label="Time Base",
            unit="s/div",
            get_cmd=":HOR:MAIN:SCAL?",
            set_cmd=":HOR:MAIN:SCAL {}",
            get_parser=float,
            vals=Numbers(min_value=0),
        )
        """Horizontal scale"""

        # Sets the trigger delay.
        self.timebase_delay: Parameter = self.add_parameter(
            "timebase_delay",
            label="Trigger Delay",
            unit="s",
            get_cmd=":HOR:DEL:TIME?",
            set_cmd=":HOR:DEL:TIME {}",
            get_parser=float,
            vals=Numbers(),
        )
        """Trigger delay"""

        # TRIGGER A

        self.trigger_mode: Parameter = self.add_parameter(
            "trigger_mode",
            label="Trigger Mode",
            get_cmd=":TRIG:A:MODE?",
            set_cmd=":TRIG:A:MODE {}",
            vals=Enum("AUTO", "NORM", "SING"),
        )
        """Trigger mode"""

        self.trigger_type: Parameter = self.add_parameter(
            "trigger_type",
            label="Trigger Type",
            get_cmd=":TRIG:A:TYPE?",
            set_cmd=":TRIG:A:TYPE {}",
            vals=Enum("EDGE", "VID", "PULS", "LOG"),
        )
        """Trigger type"""

        # Edge (slope) trigger settings
        self.trigger_source: Parameter = self.add_parameter(
            "trigger_source",
            label="Trigger Source",
            get_cmd=":TRIG:A:EDGE:SOUR?",
            set_cmd=":TRIG:A:EDGE:SOUR {}",
            vals=Enum(*analog_sources, *logic_sources, "EXT", "LINE"),
        )
        """Edge trigger source"""

        self.trigger_slope: Parameter = self.add_parameter(
            "trigger_slope",
            label="Trigger Slope",
            get_cmd=":TRIG:A:EDGE:SLOP?",
            set_cmd=":TRIG:A:EDGE:SLOP {}",
            vals=Enum("POS", "NEG", "EITH"),
        )
        """Edge trigger slope"""

        self.trigger_coupling: Parameter = self.add_parameter(
            "trigger_coupling",
            label="Trigger Coupling",
            get_cmd=":TRIG:A:EDGE:COUP?",
            set_cmd=":TRIG:A:EDGE:COUP {}",
            vals=Enum("AC", "DC", "HF"),
        )
        """Edge trigger coupling"""

        self.trigger_level: Parameter = self.add_parameter(
            "trigger_level",
            label="Trigger Level",
            unit="V",
            get_cmd=":TRIG:A:EDGE:LEV?",
            set_cmd=":TRIG:A:EDGE:LEV {}",
            get_parser=float,
            vals=Numbers(),
        )
        """Edge trigger level"""

        self.trigger_lowpass: Parameter = self.add_parameter(
            "trigger_lowpass",
            label="Trigger Low-pass Filter",
            get_cmd=":TRIG:A:EDGE:FILT:LPAS?",
            set_cmd=":TRIG:A:EDGE:FILT:LPAS {}",
            val_mapping=create_on_off_val_mapping(on_val="ON", off_val="OFF"),
        )
        """Trigger low-pass filter on/off"""

        # Switched on automatically by the instrument at sensitivities < 2 mV/div.
        self.trigger_noise_reject: Parameter = self.add_parameter(
            "trigger_noise_reject",
            label="Trigger Noise Reject",
            get_cmd=":TRIG:A:EDGE:FILT:NREJ?",
            set_cmd=":TRIG:A:EDGE:FILT:NREJ {}",
            val_mapping=create_on_off_val_mapping(on_val="ON", off_val="OFF"),
        )
        """Trigger noise reject filter on/off"""

        # Video trigger settings
        self.trigger_video_field: Parameter = self.add_parameter(
            "trigger_video_field",
            label="Video Trigger Field",
            get_cmd=":TRIG:A:VID:FIEL?",
            set_cmd=":TRIG:A:VID:FIEL {}",
            vals=Enum("ODD", "EVEN", "ALL", "LINE", "ALLL"),
        )
        """Video trigger field"""

        self.trigger_video_line: Parameter = self.add_parameter(
            "trigger_video_line",
            label="Video Trigger Line",
            get_cmd=":TRIG:A:VID:LINE?",
            set_cmd=":TRIG:A:VID:LINE {}",
            get_parser=_parse_int,
            vals=Ints(min_value=0),
        )
        """Video trigger line number"""

        self.trigger_video_polarity: Parameter = self.add_parameter(
            "trigger_video_polarity",
            label="Video Trigger Polarity",
            get_cmd=":TRIG:A:VID:POL?",
            set_cmd=":TRIG:A:VID:POL {}",
            vals=Enum("POS", "NEG"),
        )
        """Video trigger sync pulse polarity"""

        self.trigger_video_standard: Parameter = self.add_parameter(
            "trigger_video_standard",
            label="Video Trigger Standard",
            get_cmd=":TRIG:A:VID:STAN?",
            set_cmd=":TRIG:A:VID:STAN {}",
            vals=Enum("PAL", "NTSC"),
        )
        """Video standard"""

        self.trigger_video_source: Parameter = self.add_parameter(
            "trigger_video_source",
            label="Video Trigger Source",
            get_cmd=":TRIG:A:VID:SOUR?",
            set_cmd=":TRIG:A:VID:SOUR {}",
            vals=Enum(*analog_sources, "EXT"),
        )
        """Video trigger source"""

        # TRIGGER B

        # The B trigger is an additional edge trigger, only available if the A trigger is an edge trigger.
        self.trigger_b_state: Parameter = self.add_parameter(
            "trigger_b_state",
            label="B Trigger State",
            get_cmd=":TRIG:B:STAT?",
            set_cmd=":TRIG:B:STAT {}",
            val_mapping=create_on_off_val_mapping(on_val="ON", off_val="OFF"),
        )
        """B trigger on/off"""

        self.trigger_b_level: Parameter = self.add_parameter(
            "trigger_b_level",
            label="B Trigger Level",
            unit="V",
            get_cmd=":TRIG:B:LEV?",
            set_cmd=":TRIG:B:LEV {}",
            get_parser=float,
            vals=Numbers(),
        )
        """B trigger level"""

        # DISPLAY

        self.display_backlight: Parameter = self.add_parameter(
            "display_backlight",
            label="Backlight Intensity",
            unit="%",
            get_cmd=":DISP:BACK:INT?",
            set_cmd=":DISP:BACK:INT {}",
            get_parser=float,
            vals=Numbers(min_value=0, max_value=100),
        )
        """Display backlight intensity"""

        self.display_trace_intensity: Parameter = self.add_parameter(
            "display_trace_intensity",
            label="Trace Intensity",
            unit="%",
            get_cmd=":DISP:TRAC:INT?",
            set_cmd=":DISP:TRAC:INT {}",
            get_parser=float,
            vals=Numbers(min_value=0, max_value=100),
        )
        """Display trace intensity"""

        # Normal colours (NORM) or false colour display (FCOL) for the analog channels.
        self.display_palette: Parameter = self.add_parameter(
            "display_palette",
            label="Display Palette",
            get_cmd=":DISP:PAL?",
            set_cmd=":DISP:PAL {}",
            vals=Enum("NORM", "FCOL"),
        )
        """Display palette"""

        # Display samples as dots or connected by lines (vectors).
        self.display_style: Parameter = self.add_parameter(
            "display_style",
            label="Display Style",
            get_cmd=":DISP:STYL?",
            set_cmd=":DISP:STYL {}",
            vals=Enum("DOTS", "VECT"),
        )
        """Display style"""

        # HARDCOPY

        self.hardcopy_format: Parameter = self.add_parameter(
            "hardcopy_format",
            label="Screenshot Format",
            get_cmd=":HCOP:FORM?",
            set_cmd=":HCOP:FORM {}",
            vals=Enum("BMP", "GIF", "PNG"),
        )
        """Screenshot file format"""

        self.hardcopy_width: Parameter = self.add_parameter(
            "hardcopy_width",
            label="Screenshot Width",
            unit="px",
            get_cmd=":HCOP:SIZE:X?",
            get_parser=_parse_int,
        )
        """Screenshot width"""

        self.hardcopy_height: Parameter = self.add_parameter(
            "hardcopy_height",
            label="Screenshot Height",
            unit="px",
            get_cmd=":HCOP:SIZE:Y?",
            get_parser=_parse_int,
        )
        """Screenshot height"""

        # SYSTEM

        self.system_name: Parameter = self.add_parameter(
            "system_name",
            label="Instrument Name",
            get_cmd=":SYST:NAME?",
            set_cmd=':SYST:NAME "{}"',
            get_parser=_strip_quotes,
            vals=Strings(),
        )
        """User-defined instrument name"""

        # Date as 'year,month,day', e.g. '2009,5,1'
        self.system_date: Parameter = self.add_parameter(
            "system_date",
            label="Date",
            get_cmd=":SYST:DATE?",
            set_cmd=":SYST:DATE {}",
            vals=Strings(),
        )
        """Instrument date"""

        # Time as 'hour,minute,second', e.g. '12,5,0'
        self.system_time: Parameter = self.add_parameter(
            "system_time",
            label="Time",
            get_cmd=":SYST:TIME?",
            set_cmd=":SYST:TIME {}",
            vals=Strings(),
        )
        """Instrument time"""

        # WAVEFORM READOUT

        # Sets the number of points read out per waveform, for all channels: DMAX (all sampled data
        # shown on the display), MAX, DEF, or a number of points. Reading returns the number of points.
        # Large numbers of points may need a longer VISA timeout.
        self.waveform_points: Parameter = self.add_parameter(
            "waveform_points",
            label="Waveform Points",
            get_cmd=":TRAC:POIN?",
            set_cmd=":TRAC:POIN {}",
            get_parser=_parse_int,
            vals=MultiType(Enum("DMAX", "MAX", "DEF"), Ints(min_value=1)),
        )
        """Number of points read out per waveform"""

        # SUBMODULES

        self.channels = {}
        for channel_number in range(1, num_channels + 1):
            channel_name = f"ch{channel_number}"
            channel = HMO3524_Channel(self, channel_name, channel_number)
            self.add_submodule(channel_name, channel)
            self.channels[channel_number] = channel

        self.logic_channels = {}
        for channel_number in range(NUM_LOGIC_CHANNELS):
            channel_name = f"d{channel_number}"
            channel = HMO3524_LogicChannel(self, channel_name, channel_number)
            self.add_submodule(channel_name, channel)
            self.logic_channels[channel_number] = channel

        self.pods = {}
        for pod_number in range(1, NUM_PODS + 1):
            pod_name = f"pod{pod_number}"
            pod = HMO3524_Pod(self, pod_name, pod_number)
            self.add_submodule(pod_name, pod)
            self.pods[pod_number] = pod

        self.measurements = {}
        measurement_sources = analog_sources + reference_sources + logic_sources
        for measurement_number in range(1, NUM_MEASUREMENTS + 1):
            measurement_name = f"meas{measurement_number}"
            measurement = HMO3524_Measurement(self, measurement_name, measurement_number, measurement_sources)
            self.add_submodule(measurement_name, measurement)
            self.measurements[measurement_number] = measurement

        # Start continuous signal capturing
        self.add_function("run", call_cmd=":ACQ:STAT RUN")

        # Stop signal capturing
        self.add_function("stop", call_cmd=":ACQ:STAT STOP")

        # Clear Status
        # Resets the status registers and error list, and deletes the OPC state.
        self.add_function("cls", call_cmd="*CLS")

        # Reset
        # Restarts the instrument with factory default settings.
        self.add_function("reset", call_cmd="*RST")

        self.connect_message()

    def save_screenshot(self, filename: str) -> None:
        """Save the screen content to a file, in the format set by hardcopy_format (BMP, GIF or PNG)."""
        data = self.visa_handle.query_binary_values(":HCOP:DATA?", datatype="s", container=bytes)
        with open(filename, "wb") as file:
            file.write(data)
