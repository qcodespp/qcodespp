from qcodes.configuration import Config
config = Config() # type: Config

# Import all modules included in the qcodes namespace, except Parameter and Station
# as these need to go through qcodespp wrappers
from qcodes.dataset import (
    Measurement,
    ParamSpec,
    SQLiteSettings,
    experiments,
    get_guids_by_run_spec,
    initialise_database,
    initialise_or_create_database_at,
    initialised_database_at,
    load_by_counter,
    load_by_guid,
    load_by_id,
    load_by_run_spec,
    load_experiment,
    load_experiment_by_name,
    load_last_experiment,
    load_or_create_experiment,
    new_data_set,
    new_experiment,
)
from qcodes.instrument import (
    ChannelList,
    ChannelTuple,
    Instrument,
    InstrumentChannel,
    IPInstrument,
    VisaInstrument,
    find_or_create_instrument,
)
from qcodes.monitor import Monitor
from qcodes.parameters import (
    ArrayParameter,
    CombinedParameter,
    DelegateParameter,
    Function,
    ManualParameter,
    MultiParameter,
    #Parameter,
    ParameterWithSetpoints,
    ScaledParameter,
    SweepFixedValues,
    SweepValues,
    combine,
)

from qcodes.parameters import ElapsedTimeParameter

# modules from qcodes that have been extended/modified
from qcodespp.parameters import Parameter

from qcodespp.station import Station

# new modules not included in qcodes
from qcodespp.version import __version__

from qcodespp.loops import Loop, loop1d,loop2d,loop2dUD
from qcodespp.measure import Measure
from qcodespp.actions import Task, Wait, BreakIf

from qcodespp.plotting.RemotePlot import Plot, live_plot
from qcodespp.plotting.offline.main import offline_plotting
from qcodespp.plotting.analysis_tools import colorplot, colored_traces, load_2d_json

from qcodespp.data.data_set import new_data, load_data, load_data_num, load_data_nums, set_data_format, set_data_folder

from qcodespp.utils.visa_helpers import listVISAinstruments

from qcodespp.parameters import MultiParameterWrapper, ArrayParameterWrapper, stepper

# ensure to close all instruments when interpreter is closed
import atexit
atexit.register(Instrument.close_all)
