from datetime import datetime
import numpy as np

from qcodespp.parameters import Parameter
from qcodespp.loops import Loop
from qcodespp.actions import _actions_snapshot
from qcodes.utils.helpers import full_class
from qcodes.metadatable import Metadatable
from qcodespp.station import Station
from qcodespp.dataset import new_data, DataSetPP
from qcodespp.dataarray import DataArray
from qcodespp.actions import _Measure
from qcodespp.actions import _QcodesBreak


class Measure(Metadatable):
    """
    Class to enable creation of a DataSetPP from a single (non-looped) set of actions.

    The class is initiated with a sequence of setpoints and actions, or simply
    the Station's default measure actions.
    Measure.run() will then execute the actions and return and save a DataSetPP

    Usage: 
        measure = Measure(setpoints, actions)
        data = measure.run()

    Args:
        setpoints (Optional, Parameter or Array): sequence of setpoints to
            use for the DataSetPP. Can be an array of values, or a Parameter, from which
            Measure will deduce the dimension. The latter is useful if you 
            have a parameter which you measure, but is considered the independent variable.
            e.g. time on an oscilloscope, or a voltage ramp on a source.
            If not provided, dummy setpoints are created
            for each dimension found in the actions.
        actions (any): sequence of actions to perform. Any action that is
            valid in a ``Loop`` can be used here. If an action is a gettable
            ``Parameter``, its output will be included in the DataSetPP.
            If no actions are provided, the default station.measure() is used.
            The typical use case is to store data from one or more ArrayParameter(s) 
            or ParameterWithSetpoints(s), i.e. non-scalar data, returned
            from an instrument buffer such as an oscilloscope, although scalars are also supported.
            Since the dataset forces us to include an array that acts as 'setpoints',
            a set of dummy setpoints is created for each dimension that is found in the actions.
    """
    dummy_parameter = Parameter(name='single',
                                label='Single Measurement',
                                set_cmd=None, get_cmd=None)

    def __init__(self, name=None,setpoints=None, actions=None, timer=False):
        super().__init__()
        if not actions:
            actions = Station.default.measure()
        if timer==False:
            actions=tuple(action for action in actions if action.name!='timer')
        
        #self._dummyLoop = Loop(self.dummy_parameter[0]).each(*actions)
        self.dataset=self.get_data_set(setpoints=setpoints, actions=actions, name=name)

    def run_temp(self, **kwargs):
        """
        Wrapper to run this measurement as a temporary data set
        """
        return self.run(quiet=True, location=False, **kwargs)
    
    def containers(self,setpoints,actions):
        """
        Finds the data arrays that will be created by the actions and setpoints
        """
        arrays=[]

        # Start with the setpoints
        if setpoints and isinstance(setpoints, Parameter):
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
            try:
                setpoint_array=DataArray(label='Setpoints',
                                        unit='',
                                        array_id='setpoints',
                                        name='setpoints',
                                        is_setpoint=True,
                                        preset_data=setpoints,
                                        shape=np.shape(setpoints))
                setpoint_array.init_data()
                arrays.append(setpoint_array)
            except TypeError:
                raise TypeError("setpoints must be a Parameter or an array-like object")
            
        # Then the actions
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
                                            preset_data=dummy_setpoints,
                                            shape=shape)
                    setpoint_array.init_data()
                    arrays.append(setpoint_array)
                action_array=DataArray(parameter=action, shape=shape, is_setpoint=False, set_array=setpoint_array)
                action_array.init_data()
                arrays.append(action_array)

        return arrays

    def get_data_set(self, setpoints, actions, name):
        #return self._dummyLoop.get_data_set(*args, **kwargs)
        # What this should actually do:
        # 1) Go through all actions, and if the action is a Parameter,
        #  find the dimension of the data it returns. check if dummy setpoints
        #  already exist, and if not, create them.
        # 2) Create a DataSetPP with the correct setpoints and actions
        self.data_set=new_data(arrays=self.containers(setpoints,actions),name=name)

    def _compile_actions(self, actions, action_indices=()):
        callables = []
        measurement_group = []
        for i, action in enumerate(actions):
            new_action_indices = action_indices + (i,)
            if hasattr(action, 'get'):
                measurement_group.append((action, new_action_indices))
                continue
            elif measurement_group:
                callables.append(_Measure(measurement_group, self.data_set,
                                          self.use_threads))
                measurement_group[:] = []

            callables.append(self._compile_one(action, new_action_indices))

        if measurement_group:
            callables.append(_Measure(measurement_group, self.data_set,
                                      self.use_threads))
            measurement_group[:] = []

        return callables


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

        data_set = self.data_set
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

        callables = self._compile_actions(actions=data_set.actions)
        n_callables = 0
        for item in callables:
            if hasattr(item, 'param_ids'):
                n_callables += len(item.param_ids)
            else:
                n_callables += 1
        
        if 'timer' in self.data_set.arrays:
            station.timer.reset_clock()

        try:
            for f in callables:
                # Callables are everything: the actual measurements, any tasks, etc.
                f(loop_indices='all')
                
        except _QcodesBreak:
            self.was_broken=True

        data_set.finalize()

        if not quiet:
            print(repr(data_set))
            print(datetime.now().strftime('acquired at %Y-%m-%d %H:%M:%S'))

        return data_set

    def snapshot_base(self, update=False):
        return {
            '__class__': full_class(self),
            'actions': _actions_snapshot(self.actions, update)
        }
