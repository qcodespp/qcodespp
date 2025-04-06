from qcodes.configuration import Config
config = Config() # type: Config

from qcodes import *
from qcodes.parameters import ElapsedTimeParameter

from .version import __version__

from .loops import Loop, active_loop, active_data_set
from .measure import Measure
from .actions import Task, Wait, BreakIf

from .plotting.RemotePlot import Plot
from .data.data_set import DataSet, new_data, load_data, load_data_num, load_data_nums, set_data_format, set_data_folder
from .data.location import FormatLocation
from .data.data_array import DataArray
from .data.format import Formatter
from .data.gnuplot_format import GNUPlotFormat
from .data.hdf5_format import HDF5Format
from .data.io import DiskIO

from .parameters import Parameter,MultiParameterWrapper, ArrayParameterWrapper

from .utils.visa_helpers import listVISAinstruments

from .station import Station

# ensure to close all instruments when interpreter is closed
import atexit
atexit.register(Instrument.close_all)
