"""DataSetPP class and factory functions."""

import time
from datetime import datetime, date
import logging
import glob
import numpy as np
from traceback import format_exc
from copy import deepcopy
from collections import OrderedDict
from typing import Dict, Callable

from qcodespp.data.gnuplot_format import GNUPlotFormat
from qcodespp.data.io import DiskIO
from qcodespp.data.location import FormatLocation
from qcodes.utils import DelegateAttributes, full_class, deep_update
from qcodes import config
import os
import platform

from uuid import uuid4
log = logging.getLogger(__name__)

def new_data(location=None, loc_record=None, name=None, overwrite=False,
             io=None, backup_location=None, force_write=False, **kwargs):
    """
    Create a new DataSetPP, the text-based data set of qcodespp.

    Args:
        location (str or callable or False, optional): If you provide a string,
            it must be an unused location in the io manager. Can also be:

            - a callable ``location provider`` with one required parameter
              (the io manager), and one optional (``record`` dict),
              which returns a location string when called
            - ``False`` - denotes an only-in-memory temporary DataSetPP.

            Note that the full path to or physical location of the data is a
            combination of io + location. the default ``DiskIO`` sets the base
            directory, which this location is a relative path inside.
            Default ``DataSetPP.location_provider`` which is initially
            ``FormatLocation()``

        loc_record (dict, optional): If location is a callable, this will be
            passed to it as ``record``

        name (str, optional): overrides the ``name`` key in the ``loc_record``.

        overwrite (bool): Are we allowed to overwrite an existing location?
            Default False.

        io (io_manager, optional): base physical location of the ``DataSetPP``.
            Default ``DataSetPP.default_io`` is initially ``DiskIO('.')`` which
            says the root data directory is the current working directory, ie
            where you started the python session.

        arrays (Optional[List[qcodes.DataArray]): arrays to add to the DataSetPP.
                Can be added later with ``self.add_array(array)``.

        formatter (Formatter, optional): sets the file format/structure to
            write (and read) with. Default ``DataSetPP.default_formatter`` which
            is initially ``GNUPlotFormat()``.

        write_period (float or None, optional):seconds
            between saves to disk.
    Returns:
        A new ``DataSetPP`` object ready for storing new data in.
    """
    if io is None:
        io = DataSetPP.default_io

    if location is None:
        location = DataSetPP.location_provider

    if name is not None:
        if not loc_record:
            loc_record = {}
        loc_record['name'] = name

    if callable(location):
        location = location(io, record=loc_record)

    if location and (not overwrite) and io.list(location):
        raise FileExistsError('"' + location + '" already has data')

    return DataSetPP(location=location, io=io, backup_location=backup_location, force_write=force_write, name=name, **kwargs)

def load_data(location=None, formatter=None, io=None, include_metadata=True,remove_incomplete=True):
    """
    Load an existing DataSetPP.

    Args:
        location (str, optional): the location to load from. Default is the
            current live DataSetPP.
            Note that the full path to or physical location of the data is a
            combination of io + location. the default ``DiskIO`` sets the base
            directory, which this location is a relative path inside.

        formatter (Formatter, optional): sets the file format/structure to
            read with. Default ``DataSetPP.default_formatter`` which
            is initially ``GNUPlotFormat()``.

        io (io_manager, optional): base physical location of the ``DataSetPP``.
            Default ``DataSetPP.default_io`` is initially ``DiskIO('.')`` which
            says the root data directory is the current working directory, ie
            where you started the python session.

    Returns:
        A new ``DataSetPP`` object loaded with pre-existing data.
    """
    if location is False:
        raise ValueError('location=False means a temporary DataSetPP, '
                         'which is incompatible with load_data')

    data = DataSetPP(location=location, formatter=formatter, io=io)
    if include_metadata==True:
        data.read_metadata()
        data.read()
    else:
        data.read(include_metadata=False)
    if remove_incomplete:
        if data.fraction_complete() != 1:
            data = data.remove_incomplete()
            log.warning('Data was loaded with incomplete columns removed.\n'
            'If this is not desired, use remove_incomplete=False in load_data, '
            'load_data_num, or load_data_nums.')
    return data

def load_data_num(number, datafolder="data", delimiter='_',leadingzeros=3,include_metadata=True,remove_incomplete=True):
    """
    Load a qcodespp DataSetPP using the counter as identifier.

    Typically qcodespp DataSetPPs are forced to use the format counter_name_date_time,
    where the counter is a zero-padded integer. This function will search for
    a folder with the given counter number, and load the data from it.

    Args:
        number (str or int): the dataset's counter number
        datafolder (str, optional): the folder to load from. Default is the
            current live DataSetPP.
            Note that the full path to or physical location of the data is a
            combination of io + location. the default ``DiskIO`` sets the base
            directory, which this location is a relative path inside.
        delimiter (str, optional): The character after the number. Almost always
            underscore but may be specified if necessary.

    Returns:
        A new ``DataSetPP`` object loaded with pre-existing data.
    """
    number=str(number).split('_')[0].zfill(leadingzeros) #Split included here to account for a potential fail point in backwards compatibility. 
                                                #There were cases where the user had to explicitly include the delimiter.
    datapaths = [glob.glob('{}/#{}{}*/'.format(datafolder,number,delimiter))]
    if np.shape(datapaths[0])[0]>1:
        raise ValueError('Multiple data sets found! Check numbering or delimiter.')
    elif np.shape(datapaths[0])[0]==0:
        raise ValueError('No dataset found!')
    else:
        data = load_data(datapaths[0][0],include_metadata=include_metadata,remove_incomplete=remove_incomplete)
        return data

def load_data_nums(listofnumbers, datafolder="data",delimiter='_',leadingzeros=3,include_metadata=True,remove_incomplete=True):
    """
    Loads numerous DataSetPPs from the specified folder by counter number.

    Args:
        litsofnumbers (list of strings or ints): list of desired dataset numbers.
        datafolder (str, optional): the folder to load from. Default is the
            current live DataSetPP.
            Note that the full path to or physical location of the data is a
            combination of io + location. the default ``DiskIO`` sets the base
            directory, which this location is a relative path inside.
        delimiter (str, optional): The character after the number. Almost always
            underscore but may be specified if necessary.

    Returns:
        An array containing ``DataSetPP`` objects loaded with pre-existing data.
    """

    data=[]
    for i,number in enumerate(listofnumbers):
        number=str(number).split('_')[0].zfill(leadingzeros) #Split included here to account for a potential fail point in backwards compatibility. 
                                                    #There were cases where the user had to explicitly include the delimiter.
        datapaths = [glob.glob('{}/#{}{}*/'.format(datafolder,number,delimiter))]
        if np.shape(datapaths[0])[0]>1:
            raise ValueError('Multiple data sets with number {} found! check numbering or choice of delimiter.'.format(number))
        elif np.shape(datapaths[0])[0]==0:
            raise ValueError('No dataset with number {} found! check numbering. '.format(number))
        else:
            data.append(load_data(datapaths[0][0],include_metadata=include_metadata,remove_incomplete=remove_incomplete))

    return data

def set_data_format(fmt='data/#{counter}_{name}_{date}_{time}'):
    """
    Set the default format for storing DataSetPPs. See qcodespp.data.location for more information.

    Args:
        fmt (str): A format string for the location of the data, with wildcards determined by the FormatLocation class.
            Another useful format may be 'data/{date}/#{counter}_{name}_{time}'.
    """

    DataSetPP.location_provider=FormatLocation(fmt=fmt)

def set_data_folder(folder='data'):
    """
    Set the default folder for storing DataSetPPs.

    Args:
        folder (str): Folder name relative to the current working directory, e.g. location of the current
            Jupyter notebook. The folder will be created if it does not exist.
    """
    
    fmt=folder+'/#{counter}_{name}_{date}_{time}'
    DataSetPP.default_folder=folder
    DataSetPP.location_provider=FormatLocation(fmt=fmt)

class DataSetPP(DelegateAttributes):

    """
    A container for one complete measurement from qcodespp.Measure or qcodespp.Loop.

    A DataSetPP consists of multiple DataArrays with potentially different 
    sizes and dimensionalities. It is accompanied by metadata containing snapshots 
    of different qcodespp classes, e.g. Instruments and Parameters in the Station.

    A DataSetPP should not be instantiated directly, but constructed by qcodespp.Measure 
    or qcodespp.Loop. A pre-existing DataSetPP can be loaded with qcodespp.load_data, 
    load_data_num, or load_data_nums.

    The default format for storage is (a) text file(s) with GNUPlotFormat, where the 
    DataArrays are converted to numpy arrays. This means that each DataArray must be 
    rectangular, and all elements must be of the same type. Currently, types are limited 
    to float or str; however, almost any type other than str can be converted to a float, 
    and this is done automatically; e.g. boolean --> (0,1). 
    DataArrays which are also Setpoints can only be of type float.

    Args:
        location (str or False): A location in the io manager, or ``False`` for
            an only-in-memory temporary DataSetPP.
            Note that the full path to or physical location of the data is a
            combination of io + location. the default ``DiskIO`` sets the base
            directory, which this location is a relative path inside.

        io (io_manager, optional): base physical location of the ``DataSetPP``.
            Default ``DataSetPP.default_io`` is initially ``DiskIO('.')`` which
            says the root data directory is the current working directory, ie
            where you started the python session.

        arrays (Optional[List[qcodes.DataArray]): arrays to add to the DataSetPP.
                Can be added later with ``self.add_array(array)``.

        formatter (Formatter, optional): sets the file format/structure to
            write (and read) with. Default ``DataSetPP.default_formatter`` which
            is initially ``GNUPlotFormat()``.

        write_period (float or None, optional): Only if ``mode=LOCAL``, seconds
            between saves to disk. If not ``LOCAL``, the ``DataServer`` handles
            this and generally writes more often. Use None to disable writing
            from calls to ``self.store``. Default 5.

    Attributes:
        background_functions (OrderedDict[callable]): Class attribute,
            ``{key: fn}``: ``fn`` is a callable accepting no arguments, and
            ``key`` is a name to identify the function and help you attach and
            remove it.

            In ``DataSetPP.complete`` we call each of these periodically, in the
            order that they were attached.

            Note that because this is a class attribute, the functions will
            apply to every DataSetPP. If you want specific functions for one
            DataSetPP you can override this with an instance attribute.
    """

    # ie data_set.arrays['vsd'] === data_set.vsd
    delegate_attr_dicts = ['arrays']

    default_io = DiskIO('.')
    default_formatter = GNUPlotFormat()
    location_provider = FormatLocation()

    default_folder=None

    background_functions: Dict[str, Callable] = OrderedDict()

    def __init__(self, location=None, arrays=None, formatter=None, io=None,
                 write_period=5, backup_location=None,force_write=False,name=None):
        if location is False or isinstance(location, str):
            self.location = location
        else:
            raise ValueError('unrecognized location ' + repr(location))

        if isinstance(backup_location,str):
            self.backup_location=backup_location
        elif 'backup_location' in config['core'].keys():
            self.backup_location=config['core']['backup_location']
            if os.access(self.backup_location, os.W_OK) is False and os.path.exists(self.backup_location) is False:
                try:
                    os.makedirs(self.backup_location)
                except Exception as e:
                    log.warning(f'Backup location specified in qcodespp.config["core"]["backup_location"] '
                        'could not be created. Try another location \n {e}')
            if os.access(self.backup_location, os.W_OK) is False:
                log.warning('Backup location specified in qcodespp.config["core"]["backup_location"] is not writable. '
                    'Try another location')
        elif backup_location is None:
            if platform.system()=='Windows':
                self.backup_location='C:/Users/'+os.getlogin()+'/AppData/Local/qcodespp/data_backup'
            else:
                self.backup_location='~/.qcodespp/data_backup'
            if os.access(self.backup_location, os.W_OK) is False and os.path.exists(self.backup_location) is False:
                try:
                    os.makedirs(self.backup_location)
                except Exception as e:
                    log.warning(f'Default backup location {self.backup_location} '
                        'could not be created. \n {e} '
                        'This usually is not a problem but you may like to specify/create one. '
                        'Specify it globally for this session using qcodespp.config["core"]["backup_location"]="*your backup location*",'
                        'or specify it for this DataSet by specifying backup_location="*your backup location*" in e.g. new_data() or get_data_set()')
                    
            if os.access(self.backup_location, os.W_OK) is False:
                log.warning(f'Default backup_location, ~/.qcodespp/data_backup cannot be used. '
                        'This usually is not a problem but you may like to specify one. '
                        'Specify it globally for this session using qcodespp.config["core"]["backup_location"]="*your backup location*",'
                        'or specify it for this DataSet by specifying backup_location="*your backup location*" in e.g. new_data() or get_data_set()')
        else:
            self.backup_location=self.location
            log.warning('No backup_location specified for saving data. This usually is not a problem but you may like to specify one. '
                'Specify it globally for this session using qcodespp.config["core"]["backup_location"]="*your backup location*",'
                'or specify it for this DataSet by specifying backup_location="*your backup location*" in e.g. new_data() or get_data_set()')

        self.backup_used=False
        self.writing_skipped=False
        self._backup_warning=False
        self._skipped_warning=False

        self.finalized=False

        self.publisher = None

        self.name=name

        if self.name is not None:
            forbiddenchars=['[',']','<','>',':','\"','/','\\','|','?','*']
            for char in forbiddenchars:
                if char in self.name:
                    raise ValueError(f'{char} cannot be used in a filename on Windows')

        # TODO: when you change formatter or io (and there's data present)
        # make it all look unsaved
        self.formatter = formatter or self.default_formatter
        self.io = io or self.default_io

        self.write_period = write_period
        self.last_write = 0
        self.last_store = -1
        self.force_write=force_write

        self.metadata = {}
        self.uuid = uuid4().hex

        self.arrays = _PrettyPrintDict()
        if arrays:
            self.action_id_map = self._clean_array_ids(arrays)
            for array in arrays:
                self.add_array(array)

        if self.arrays:
            for array in self.arrays.values():
                array.init_data()

        if self.name is not None and isinstance(self.formatter,GNUPlotFormat):
            for group in self.formatter.group_arrays(self.arrays):
                pathlength=len(self.io.base_location+'/'+self.location+'/'+group.name+self.formatter.extension)
                if pathlength>246:
                    loc_record={}
                    loc_record['name'] = self.name[:-(pathlength-246)]
                    self.location = self.location_provider(io, record=loc_record)
                    log.warning('DataSetPP filename has been automatically shortened to avoid Windows maximum character limit')

        # Make this dataset a class attribute so that it can be accessed by other functions, 
        # most notably to set its publisher in live plotting.
        DataSetPP.default_dataset = self

    def sync(self):
        """
        Synchronize this DataSetPP with the DataServer or storage.

        If this DataSetPP is on the server, asks the server for changes.
        If not, reads the entire DataSetPP from disk.

        Returns:
            bool: True if this DataSetPP is live on the server
        """
        # TODO: sync implies bidirectional... and it could be!
        # we should keep track of last sync timestamp and last modification
        # so we can tell whether this one, the other one, or both copies have
        # changed (and I guess throw an error if both did? Would be cool if we
        # could find a robust and intuitive way to make modifications to the
        # version on the DataServer from the main copy)

        # LOCAL DataSetPP - no need to sync just use local data
        return False

    def fraction_complete(self):
        """
        Get the fraction of this DataSetPP which has data in it.

        Returns:
            float: the average of all measured (not setpoint) arrays'
                ``fraction_complete()`` values, independent of the individual
                array sizes. If there are no measured arrays, returns zero.
        """
        array_count, total = 0, 0

        for array in self.arrays.values():
            if not array.is_setpoint:
                array_count += 1
                total += array.fraction_complete()

        return total / (array_count or 1)
    
    def remove_incomplete(self):
        """"
        Returns a DataSetPP minus any incomplete columns.

        DataArrays are initialized with a set shape and filled with NaNs. 
        The NaNs get replaced during the measurements, but if the measurement is
        stopped prematurely, the existence of NaNs can cause problems when plotting.

        Returns:
            DataSetPP: a new DataSetPP with all incomplete columns removed.
        """
        if self.fraction_complete() != 1:
            try:
                set_x = self.arrays[list(self.arrays.keys())[0]]
            except (IndexError, KeyError):
                set_x = None
            if set_x is not None:
                new_dataset = new_data(location=False)
                new_dataset.metadata=self.metadata
                non_nan_len = len(np.unique(set_x[~np.isnan(set_x)])) - 1
                for array in self.arrays.values():
                    if array.shape[0] > non_nan_len:
                        new_dataset.add_array(array.subset(slice(None, non_nan_len)))
                return new_dataset
            else:
                log.warning('DataSetPP has no setpoint arrays, cannot remove incomplete columns')
                return self
        else:
            log.warning('DataSetPP is already complete, no incomplete columns to remove')
            return self

    def complete(self, delay=1.5):
        """
        Periodically sync the DataSetPP and display percent complete status.

        Also, each period, execute functions stored in (class attribute)
        ``self.background_functions``. If a function fails, we log its
        traceback and continue on. If any one function fails twice in
        a row, it gets removed.

        Args:
            delay (float): seconds between iterations. Default 1.5
        """
        log.info(
            'waiting for DataSetPP <{}> to complete'.format(self.location))

        failing = {key: False for key in self.background_functions}

        completed = False
        while True:
            log.info('DataSetPP: {:.0f}% complete'.format(
                self.fraction_complete() * 100))

            # first check if we're done
            if self.sync() is False:
                completed = True

            # then even if we *are* done, execute the background functions
            # because we want things like live plotting to get the final data
            for key, fn in list(self.background_functions.items()):
                try:
                    log.debug('calling {}: {}'.format(key, repr(fn)))
                    fn()
                    failing[key] = False
                except Exception:
                    log.info(format_exc())
                    if failing[key]:
                        log.warning(
                            'background function {} failed twice in a row, '
                            'removing it'.format(key))
                        del self.background_functions[key]
                    failing[key] = True

            if completed:
                break

            # but only sleep if we're not already finished
            time.sleep(delay)

        log.info('DataSetPP <{}> is complete'.format(self.location))

    def get_changes(self, synced_indices):
        """
        Find changes since the last sync of this DataSetPP.

        Args:
            synced_indices (dict): ``{array_id: synced_index}`` where
                synced_index is the last flat index which has already
                been synced, for any (usually all) arrays in the DataSetPP.

        Returns:
            Dict[dict]: keys are ``array_id`` for each array with changes,
                values are dicts as returned by ``DataArray.get_changes``
                and required as kwargs to ``DataArray.apply_changes``.
                Note that not all arrays in ``synced_indices`` need be
                present in the return, only those with changes.
        """
        changes = {}

        for array_id, synced_index in synced_indices.items():
            array_changes = self.arrays[array_id].get_changes(synced_index)
            if array_changes:
                changes[array_id] = array_changes

        return changes

    def add_array(self, data_array):
        """
        Add one DataArray to this DataSetPP, and mark it as part of this DataSetPP.

        Note: DO NOT just set ``data_set.arrays[id] = data_array``, because
        this will not check if we are overwriting another array, nor set the
        reference back to this DataSetPP, nor that the ``array_id`` in the array
        matches how you're storing it here.

        Args:
            data_array (DataArray): the new array to add

        Raises:
            ValueError: if there is already an array with this id here.
        """

        if data_array.array_id in self.arrays:
            raise ValueError('array_id {} already exists in this '
                             'DataSetPP'.format(data_array.array_id))
        self.arrays[data_array.array_id] = data_array

        # back-reference to the DataSetPP
        data_array.data_set = self

    def remove_array(self, array_id):
        """ Remove an array from a dataset

        Throws an exception when the array specified is refereced by other
        arrays in the dataset.

        Args:
            array_id (str): array_id of array to be removed
        """
        for a in self.arrays:
            sa = self.arrays[a].set_arrays
            if array_id in [a.array_id for a in sa]:
                raise Exception(
                    'cannot remove array %s as it is referenced by a' % array_id)
        _ = self.arrays.pop(array_id)
        self.action_id_map = self._clean_array_ids(self.arrays.values())

    def _clean_array_ids(self, arrays):
        """
        replace action_indices tuple with compact string array_ids
        stripping off as much extraneous info as possible
        """
        action_indices = [array.action_indices for array in arrays]
        for array in arrays:
            name = array.full_name
            if array.is_setpoint and name and not name.endswith('_set'):
                name += '_set'

            array.array_id = name
        array_ids = set([array.array_id for array in arrays])
        for name in array_ids:
            param_arrays = [array for array in arrays
                            if array.array_id == name]
            self._clean_param_ids(param_arrays, name)

        array_ids = [array.array_id for array in arrays]

        return dict(zip(action_indices, array_ids))

    def _clean_param_ids(self, arrays, name):
        # strip off as many leading equal indices as possible
        # and append the rest to the back of the name with underscores
        param_action_indices = [list(array.action_indices) for array in arrays]
        while all(len(ai) for ai in param_action_indices):
            if len(set(ai[0] for ai in param_action_indices)) == 1:
                for ai in param_action_indices:
                    ai[:1] = []
            else:
                break
        
        # For ND loops, N>1, we need to add an index to ensure a unique name.
        array_ids = [array.array_id for array in arrays]
        if len(array_ids) != len(set(array_ids)):
            for array, ai in zip(arrays, param_action_indices):
                array.array_id = name + ''.join('_' + str(ai[0]))

        # Complex loops without well-defined dimension need the full set of action indices to be unique.
        array_ids = [array.array_id for array in arrays]
        if len(array_ids) != len(set(array_ids)):
            for array, ai in zip(arrays, param_action_indices):
                array.array_id = name + ''.join('_' + str(i) for i in ai)

    def store(self, loop_indices, ids_values):
        """
        Insert data into one or more of our DataArrays.

        Args:
            loop_indices (tuple): the indices within whatever loops we are
                inside. May have fewer dimensions than some of the arrays
                we are inserting into, if the corresponding value makes up
                the remaining dimensionality.
            values (Dict[Union[float, sequence]]): a dict whose keys are
                array_ids, and values are single numbers or entire slices
                to insert into that array.
         """
        for array_id, value in ids_values.items():
            if type(loop_indices) is tuple:
                self.arrays[array_id][loop_indices] = value
            elif loop_indices=='all': # from Measure
                self.arrays[array_id][:] = value
        self.last_store = time.time()

        if self.publisher is not None:
            self.publisher.store(loop_indices, ids_values, uuid=self.uuid)
            
        if (self.write_period is not None and
                time.time() > self.last_write + self.write_period):
            log.debug('Attempting to write')
            self.write()
            self.last_write = time.time()
        # The below could be useful but as it writes at every single
        # step of the loop its too verbose even at debug
        # else:
        #     log.debug('.store method: This is not the right time to write')

    def default_parameter_name(self, paramname='amplitude'):
        """ Return name of default parameter for plotting

        The default parameter is determined by looking into
        metdata['default_parameter_name'].  If this variable is not present,
        then the closest match to the argument paramname is tried.

        Args:
            paramname (str): Name to match to parameter name

        Returns:
            name ( Union[str, None] ): name of the default parameter
        """

        arraynames = self.arrays.keys()

        # overrule parameter name from the metadata
        if self.metadata.get('default_parameter_name', False):
            paramname = self.metadata['default_parameter_name']

        # try to return the exact name
        if paramname in arraynames:
            return paramname

        # try find something similar
        vv = [v for v in arraynames if v.endswith(paramname)]
        if (len(vv) > 0):
            return vv[0]
        vv = [v for v in arraynames if v.startswith(paramname)]
        if (len(vv) > 0):
            return vv[0]

        # try to get the first non-setpoint array
        vv = [v for v in arraynames if not self.arrays[v].is_setpoint]
        if (len(vv) > 0):
            return sorted(vv)[0]

        # fallback: any array found
        try:
            name = sorted((list(arraynames)))[0]
            return name
        except IndexError:
            pass
        return None

    def default_parameter_array(self, paramname='amplitude'):
        """ Return default parameter array

        Args:
            paramname (str): Name to match to parameter name.
                 Defaults to 'amplitude'

        Returns:
            array (DataArray): array corresponding to the default parameter

        See also:
            default_parameter_name

        """
        paramname = self.default_parameter_name(paramname=paramname)
        return getattr(self, paramname, None)

    def read(self,include_metadata=True):
        """Read the whole DataSetPP from storage, overwriting the local data."""
        if self.location is False:
            return
        self.formatter.read(self,include_metadata)

    def read_metadata(self):
        """Read the metadata from storage, overwriting the local data."""
        if self.location is False:
            return
        self.formatter.read_metadata(self)

    def write(self, write_metadata=False, only_complete=True, filename=None, force_rewrite=False):
        """
        Writes updates to the DataSetPP to storage.

        N.B. it is recommended to call data_set.finalize() when a DataSetPP is
        no longer expected to change to ensure files get closed

        Args:
            write_metadata (bool): write the metadata to disk
            only_complete (bool): passed on to the match_save_range inside
                self.formatter.write. Used to ensure that all new data gets
                saved even when some columns are strange.
            filename (Optional[str]): The filename (minus extension) to use.
                The file gets saved in the usual location.
        """
        if self.location is False:
            return
        # Only the gnuplot formatter has a "filename" kwarg
        try:
            if force_rewrite or self._backup_warning or self._skipped_warning:
                force_rewrite=True
            else:
                force_rewrite=False
            if isinstance(self.formatter, GNUPlotFormat):
                self.formatter.write(self,
                                     self.io,
                                     self.location,
                                     write_metadata=write_metadata,
                                     only_complete=only_complete,
                                     filename=filename,
                                     force_write=self.force_write,
                                     force_rewrite=force_rewrite)
            else:
                self.formatter.write(self,
                                     self.io,
                                     self.location,
                                     write_metadata=write_metadata,
                                     only_complete=only_complete)
            if self._skipped_warning==True or self._backup_warning==True:
                log.warning(f'{datetime.now().replace(microsecond=0)}: Writing data to primary location resumed')
                self._skipped_warning=False
                self._backup_warning=False
        except Exception as e:
            log.warning(f'{datetime.now().replace(microsecond=0)}: Data could not be written to primary location: '+str(e))
            try:
                if isinstance(self.formatter, GNUPlotFormat):
                    self.formatter.write(self,
                                        self.io,
                                        self.backup_location+f'/{date.today()} #{self.location_provider.counter}/',
                                        write_metadata=write_metadata,
                                        only_complete=only_complete,
                                        filename=filename,
                                        force_write=self.force_write)
                else:
                    self.formatter.write(self,
                                        self.io,
                                        self.backup_location+f'/{date.today()} #{self.location_provider.counter}/',
                                        write_metadata=write_metadata,
                                        only_complete=only_complete)
                    
                self.backup_used=True
                self._backup_warning=True
                log.warning(f'{datetime.now().replace(microsecond=0)}: Data written to backup location: {self.backup_location}')

            except Exception as e:
                log.warning(f'{datetime.now().replace(microsecond=0)}: Data could not be written to backup location: '+str(e))
                self.writing_skipped=True
                self._skipped_warning=True

    def write_copy(self, path=None, io_manager=None, location=None):
        """
        Write a new complete copy of this DataSetPP to storage.

        Args:
            path (str, optional): An absolute path on this system to write to.
                If you specify this, you may not include either ``io_manager``
                or ``location``.

            io_manager (io_manager, optional): A new ``io_manager`` to use with
                either the ``DataSetPP``'s same or a new ``location``.

            location (str, optional): A new ``location`` to write to, using
                either this ``DataSetPP``'s same or a new ``io_manager``.
        """
        if io_manager is not None or location is not None:
            if path is not None:
                raise TypeError('If you provide io_manager or location '
                                'to write_copy, you may not provide path.')
            if io_manager is None:
                io_manager = self.io
            elif location is None:
                location = self.location
        elif path is not None:
            io_manager = DiskIO(None)
            location = path
        else:
            raise TypeError('You must provide at least one argument '
                            'to write_copy')

        if location is False:
            raise ValueError('write_copy needs a location, not False')

        lsi_cache = {}
        mr_cache = {}
        for array_id, array in self.arrays.items():
            lsi_cache[array_id] = array.last_saved_index
            mr_cache[array_id] = array.modified_range
            # array.clear_save() is not enough, we _need_ to set modified_range
            # TODO - identify *when* clear_save is not enough, and fix it
            # so we *can* use it. That said, maybe we will *still* want to
            # use the full array here no matter what, or strip trailing NaNs
            # separately, either here or in formatter.write?
            array.last_saved_index = None
            array.modified_range = (0, array.ndarray.size - 1)

        try:
            self.formatter.write(self, io_manager, location, force_write=True)
            self.snapshot()
            self.formatter.write_metadata(self, io_manager, location,
                                          read_first=False)
        finally:
            for array_id, array in self.arrays.items():
                array.last_saved_index = lsi_cache[array_id]
                array.modified_range = mr_cache[array_id]

    def add_metadata(self, new_metadata):
        """
        Update DataSetPP.metadata with additional data.

        Args:
            new_metadata (dict): new data to be deep updated into
                the existing metadata
        """
        deep_update(self.metadata, new_metadata)

        if self.publisher is not None:
            self.publisher.add_metadata(new_metadata, uuid=self.uuid)

    def save_metadata(self):
        """Evaluate and save the DataSetPP's metadata."""
        if self.publisher is not None:
            self.publisher.add_metadata(self.metadata, uuid=self.uuid)

        if self.location is not False:
            self.snapshot()
            self.formatter.write_metadata(self, self.io, self.location)

    def finalize(self, filename=None, write_metadata=True, force_rewrite=False):
        """
        Mark the DataSetPP complete and write any remaining modifications.

        Also closes the data file(s), if the ``Formatter`` we're using
        supports that.

        Args:
            filename (Optional[str]): The file name (minus extension) to
                write to. The location of the file is the usual one.
            write_metadata (bool): Whether to save a snapshot. For e.g. dumping
                raw data inside a loop, a snapshot is not wanted.
        """
        log.debug('Finalising the DataSetPP. Writing.')
        # write all new data, not only (to?) complete columns
        self.write(only_complete=False, filename=filename, force_rewrite=force_rewrite)

        if hasattr(self.formatter, 'close_file'):
            self.formatter.close_file(self)

        if write_metadata:
            self.save_metadata()

        if self.publisher is not None:
            self.publisher.finalize(uuid=self.uuid)

        self.finalized=True

    def snapshot(self, update=False):
        """JSON state of the DataSetPP."""
        array_snaps = {}
        for array_id, array in self.arrays.items():
            array_snaps[array_id] = array.snapshot(update=update)

        self.metadata.update({
            '__class__': full_class(self),
            'location': self.location,
            'arrays': array_snaps,
            'formatter': full_class(self.formatter),
            'io': repr(self.io),
            'uuid': self.uuid
        })
        return deepcopy(self.metadata)

    def get_array_metadata(self, array_id):
        """
        Get the metadata for a single contained DataArray.

        Args:
            array_id (str): the array to get metadata for.

        Returns:
            dict: metadata for this array.
        """
        try:
            return self.metadata['arrays'][array_id]
        except (AttributeError, KeyError):
            return None
        
    def __repr__(self):
        """Rich information about the DataSetPP and contained arrays."""
        out = type(self).__name__ + ':'

        attrs = [['location', repr(self.location)]]
        attr_template = '\n   {:8} = {}'
        for var, val in attrs:
            out += attr_template.format(var, val)

        arr_info = [['<Type>', '<array_id>', '<array.shape>']]

        if hasattr(self, 'action_id_map'):
            id_items = [
                item for index, item in sorted(self.action_id_map.items())]
        else:
            id_items = self.arrays.keys()

        for array_id in id_items:
            array = self.arrays[array_id]
            setp = 'Setpoint' if array.is_setpoint else 'Measured'
            array_id = array_id or 'None'
            arr_info.append([setp, array_id, repr(array.shape)])

        column_lengths = [max(len(row[i]) for row in arr_info)
                          for i in range(len(arr_info[0]))]
        out_template = ('\n   '
                        '{info[0]:{lens[0]}} | {info[1]:{lens[1]}} | '
                        '{info[2]}')

        for arr_info_i in arr_info:
            out += out_template.format(info=arr_info_i, lens=column_lengths)

        return out

class _PrettyPrintDict(dict):
    """
    simple wrapper for a dict to repr its items on separate lines
    with a bit of indentation
    """

    def __repr__(self):
        body = '\n  '.join([repr(k) + ': ' + self._indent(repr(v))
                            for k, v in self.items()])
        return '{\n  ' + body + '\n}'

    def _indent(self, s):
        lines = s.split('\n')
        return '\n    '.join(lines)
