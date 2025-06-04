from datetime import datetime
import numpy as np

from qcodespp.parameters import Parameter
from qcodespp.loops import Loop
from qcodespp.actions import _actions_snapshot
from qcodes.utils.helpers import full_class
from qcodes.metadatable import Metadatable
from qcodespp.station import Station
from qcodespp.data.data_set import new_data
from qcodespp.data.data_array import DataArray
from qcodespp.actions import _Measure
from qcodespp.actions import _QcodesBreak
from qcodes.utils.threading import thread_map


class Measure(Metadatable):
    """
    Class to create a DataSetPP from a single (non-looped) set of measured parameters.

    This class is used exclusively to measure a set of parameters at a singple point in time.
    The typical use case is where the parameter(s)'s get function(s) return(s) an array, e.g. 
    an oscilloscope trace, or a spectrum analyser trace.
    The class is initiated with a sequence of setpoints and parameters. If no parameters are 
    provided, the default station.measure() is used.
    If no setpoints are provided, dummy setpoints are created for each dimension
    found in the parameters.
    Measure.run() will then execute the measurement and return and save a DataSetPP

    Usage:
        measure = Measure(name='Name for dataset filename',setpoints=Param_1)
        data = measure.run()

    Args:
        setpoints (Optional, Parameter or Array): sequence of setpoints to
            use for the DataSetPP. Can be an array of values, or a gettable Parameter, from which
            Measure will deduce the dimension. The latter is useful if you 
            have a parameter which you measure, but is considered the independent variable.
            e.g. time on an oscilloscope, or a voltage ramp on a source.
            If not provided, dummy setpoints are created for each dimension found in the actions.
        parameters (Opetional, Sequence[Parameter]): Sequence of gettable Parameters.
            If no actions are provided, the default station.measure() is used.
    """

    def __init__(self, name=None,setpoints=None, parameters=None,station=None, timer=False, use_threads=False):
        super().__init__()
        self.station = station or Station.default
        self.use_threads = use_threads
        self.setpoints = setpoints
        self.name=name
        self.timer=timer
        self.actions=parameters

    def each(self, *actions):
        """
        Set the actions to be performed in this measurement.

        Actions can be added during init, however this method is provided to make the Measure class 
        look like a Loop, where actions are added with .each(), and it makes somehow sense gramatically.

        Args:
            actions: a sequence of actions to perform. Any action that is
                valid in a ``Loop`` can be used here. If an action is a gettable
                ``Parameter``, its output will be included in the DataSetPP.
                If no actions are provided, the default station.measure() is used.
        """
        self.actions = actions
        return self
    
    def run_temp(self, **kwargs):
        """
        Wrapper to run this measurement as a temporary data set
        """
        return self.run(quiet=True, location=False, **kwargs)
    
    def _containers(self):
        """
        Finds the data arrays that will be created by the actions and setpoints
        """
        arrays=[]
        setpoints=self.setpoints
        # Start with the setpoints. If no setpoints are provided, they will be automatically created
        # when the actions are processed.

        if np.shape(setpoints): # Then the setpoints are a list or array of values
            setpoint_array=DataArray(label='Setpoints',
                                    unit='',
                                    array_id='setpoints',
                                    name='setpoints',
                                    is_setpoint=True,
                                    preset_data=setpoints)
            setpoint_array.init_data()
            arrays.append(setpoint_array)

        elif setpoints and isinstance(setpoints, Parameter):
            # arrays.append(DataArray(label=setpoints.label,unit=setpoints.unit,array_id=setpoints.full_name,
            #                         name=setpoints.name,is_setpoint=True))
            if hasattr(setpoints, 'shape'):
                shape = setpoints.shape
            else:
                shape = np.shape(setpoints.get_latest())
            setpoint_array= DataArray(parameter=setpoints, shape=shape, is_setpoint=True)
            setpoint_array.init_data()
            arrays.append(setpoint_array)

        elif setpoints:
            raise TypeError("setpoints must be a Parameter or an array-like object")
            
        # Then the actions
        if self.actions:
            actions= self.actions
        else:
            actions = self.station.measure()
        if self.timer==False:
            actions = [action for action in actions if action.name != 'timer']
        for action in actions:
            if isinstance(action, Parameter):
                if hasattr(action, 'shape'):
                    shape = action.shape
                else:
                    shape = np.shape(action.get_latest())

                # Try to find the appropriate setpoint array for this action
                setpoint_array=False
                for array in arrays:
                    if array.is_setpoint and array.shape == shape:
                        setpoint_array=array
                        break

                if not setpoint_array:
                    # If no setpoint array found, create a dummy setpoint array for this action
                    num_setpoint_arrays = len([array for array in arrays if array.is_setpoint])
                    init_array=np.arange(0,shape[0],1)
                    dummy_setpoints=np.tile(init_array,shape[1:]).reshape(shape[::-1])
                    setpoint_array=DataArray(label='Setpoints',
                                            unit='',
                                            array_id=f'setpoints_{num_setpoint_arrays}',
                                            name=f'setpoints_{num_setpoint_arrays}',
                                            is_setpoint=True,
                                            preset_data=dummy_setpoints)
                    setpoint_array.init_data()
                    arrays.append(setpoint_array)
                action_array=DataArray(parameter=action, shape=shape, is_setpoint=False, set_arrays=(setpoint_array,))
                action_array.init_data()
                arrays.append(action_array)
        return arrays

    def _get_data_set(self):
        """
        Construct the DataSetPP for this measurement.
        
        In contrast to Loop, this should not be called directly, but only
        when the user calls Measure.run()
        """
        #return self._dummyLoop.get_data_set(*args, **kwargs)
        # What this should actually do:
        # 1) Go through all actions, and if the action is a Parameter,
        #  find the dimension of the data it returns. check if dummy setpoints
        #  already exist, and if not, create them.
        # 2) Create a DataSetPP with the correct setpoints and actions
        self.data_set=new_data(name=self.name)
        for array in self._containers():
            if isinstance(array, DataArray):
                self.data_set.add_array(array)
            else:
                raise TypeError(f"Expected DataArray, got {type(array)}")
        return self.data_set

    def run(self, params_to_plot=None,use_threads=False, quiet=False, station=None, 
            publisher=None,**kwargs):
        """
        Run the actions in this measurement and return their data as a DataSetPP

        Args:
            params_to_plot: a list of parameters to plot once the measurement is done.
                Can either be the DataArray objects, or the parameters themselves.
            quiet (Optional[bool]): Set True to not print anything except
                errors. Default False.

            station (Optional[Station]): the ``Station`` this measurement
                pertains to. Defaults to ``Station.default`` if one is defined.
                Only used to supply metadata.

            use_threads (Optional[bool]): whether to parallelize ``get``
                operations using threads. Default False.

            Other kwargs are passed along to data_set.new_data. The key ones
            are:

            location (Optional[Union[str, False]]): the location of the
                DataSetPP, a string whose meaning depends on formatter and io,
                or False to only keep in memory. May be a callable to provide
                automatic locations. If omitted, will use the default
                DataSetPP.location_provider

            name (Optional[str]): if location is default or another provider
                function, name is a string to add to location to make it more
                readable/meaningful to users

            formatter (Optional[Formatter]): knows how to read and write the
                file format. Default can be set in DataSetPP.default_formatter

            io (Optional[io_manager]): knows how to connect to the storage
                (disk vs cloud etc)

        returns:
            a DataSetPP object containing the results of the measurement
        """

        data_set = self._get_data_set()
        if publisher:
            data_set.publisher = publisher

        station = station or self.station or Station.default
        if station:
            data_set.add_metadata({'station': station.snapshot()})

        data_set.add_metadata({'measurement': self.snapshot()})
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_set.add_metadata({'measurement': {
            'ts': ts,
            'use_threads': use_threads,
        }})

        data_set.save_metadata()

        if 'timer' in self.data_set.arrays:
            station.timer.reset_clock()

        try:
            self._measure()
                
        except _QcodesBreak:
            self.was_broken=True

        data_set.finalize()

        if not quiet:
            print(repr(data_set))
            print(datetime.now().strftime('acquired at %Y-%m-%d %H:%M:%S'))

        return data_set
    
    def _measure(self):
        """
        Actually perform the measurement.
        """
        out_dict = {}
        param_ids = [action.full_name for action in self.actions if isinstance(action, Parameter)]
        getters=[action.get for action in self.actions if isinstance(action, Parameter)]

        if self.use_threads:
            out = thread_map(self.getters)
        else:
            out = [g() for g in getters]

        for param_out, param_id in zip(out, param_ids):
            out_dict[param_id] = param_out

        self.data_set.store(loop_indices='all', ids_values=out_dict)

    def snapshot_base(self, update=False):
        return {
            '__class__': full_class(self),
            'actions': _actions_snapshot(self.actions, update)
        }
