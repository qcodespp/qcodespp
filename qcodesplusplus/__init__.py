from qcodes.configuration import Config
config = Config() # type: Config

# import all top-level modules from qcodes so that qcodespp operates exactly like qcodes if desired
from qcodes import (calibrations,configuration,dataset,dist,extensions,instrument,instrument_drivers,
                    logger,math_utils,metadatable,monitor,parameters,plotting,sphinx_extensions,
                    utils,validators)
# Then import all modules included in the qcodes namespace, except Parameter and Station
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
#from qcodes.station import Station
from qcodes.utils import deprecate
from qcodes.parameters import ElapsedTimeParameter

# modules that will be overwritten.
from .parameters import Parameter

from .station import Station

# new modules not included in qcodes
from .version import __version__

from .loops import Loop, active_loop, active_data_set
from .measure import Measure
from .actions import Task, Wait, BreakIf

from .plotting.RemotePlot import Plot
from .plotting.offline.main import offline_plotting

from .data.data_set import DataSet, new_data, load_data, load_data_num, load_data_nums, set_data_format, set_data_folder
from .data.location import FormatLocation
from .data.data_array import DataArray
from .data.format import Formatter
from .data.gnuplot_format import GNUPlotFormat
from .data.hdf5_format import HDF5Format
from .data.io import DiskIO

from .utils.visa_helpers import listVISAinstruments

from .parameters import MultiParameterWrapper, ArrayParameterWrapper

# ensure to close all instruments when interpreter is closed
import atexit
atexit.register(Instrument.close_all)
