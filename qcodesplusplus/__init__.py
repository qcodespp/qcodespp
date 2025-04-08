from qcodes.configuration import Config
config = Config() # type: Config

# import all top-level modules from qcodes. We will add new modules, and overwrite a handful.
from qcodes import *
from qcodes.parameters import ElapsedTimeParameter

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

# modules that will be overwritten.
from .parameters import Parameter

from .station import Station

# ensure to close all instruments when interpreter is closed
import atexit
atexit.register(Instrument.close_all)
