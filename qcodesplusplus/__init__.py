from qcodes.configuration import Config
config = Config() # type: Config

# import all top-level modules from qcodes so that qcodespp operates exactly like qcodes if desired
from importlib import import_module
calibrations=import_module('qcodes.calibrations')
configuration=import_module('qcodes.configuration')
dataset=import_module('qcodes.dataset')
dist=import_module('qcodes.dist')
extensions=import_module('qcodes.extensions')
instrument=import_module('qcodes.instrument')
instrument_drivers=import_module('qcodes.instrument_drivers')
logger=import_module('qcodes.logger')
math_utils=import_module('qcodes.math_utils')
metadatable=import_module('qcodes.metadatable')
monitor=import_module('qcodes.monitor')
parameters=import_module('qcodes.parameters')
plotting=import_module('qcodes.plotting')
sphinx_extensions=import_module('qcodes.sphinx_extensions')
utils=import_module('qcodes.utils')
validators=import_module('qcodes.validators')
# import qcodes.configuration as configuration
# import qcodes.dataset as dataset
# import qcodes.dist as dist
# import qcodes.extensions as extensions
# import qcodes.instrument as instrument
# import qcodes.instrument_drivers as instrument_drivers
# import qcodes.logger as logger
# import qcodes.math_utils as math_utils
# import qcodes.metadatable as metadatable
# import qcodes.monitor as monitor
# import qcodes.parameters as parameters
# import qcodes.plotting as plotting
# import qcodes.sphinx_extensions as sphinx_extensions
# import qcodes.utils as utils
# import qcodes.validators as validators

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

from qcodes.utils import deprecate
from qcodes.parameters import ElapsedTimeParameter

# modules from qcodes that have been extended/modified
from .parameters import Parameter

from .station import Station

# new modules not included in qcodes
from .version import __version__

from .loops import Loop, active_loop, active_data_set
from .measure import Measure
from .actions import Task, Wait, BreakIf

from .qcpp_plotting.RemotePlot import Plot, live_plot
from .qcpp_plotting.offline.main import offline_plotting

from .qcpp_data.data_set import DataSet, new_data, load_data, load_data_num, load_data_nums, set_data_format, set_data_folder
from .qcpp_data.location import FormatLocation
from .qcpp_data.data_array import DataArray
from .qcpp_data.format import Formatter
from .qcpp_data.gnuplot_format import GNUPlotFormat
from .qcpp_data.hdf5_format import HDF5Format
from .qcpp_data.io import DiskIO

from .qcpp_utils.visa_helpers import listVISAinstruments

from .parameters import MultiParameterWrapper, ArrayParameterWrapper

# ensure to close all instruments when interpreter is closed
import atexit
atexit.register(Instrument.close_all)
