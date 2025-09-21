from datetime import datetime
import numpy as np

from qcodes.utils import full_class, thread_map
from qcodes.metadatable import Metadatable

from qcodespp.parameters import Parameter, MultiParameter
from qcodespp.actions import _actions_snapshot
from qcodespp.station import Station
from qcodespp.data.data_set import new_data
from qcodespp.data.data_array import DataArray
from qcodespp.actions import _QcodesBreak
from qcodespp.plotting.RemotePlot import live_plot


class Measure(Metadatable):
    """
    Create a ``DataSetPP`` from a single (non-looped) set of measured parameters.

    ``Measure`` is used to measure a set of parameters at a single point in time.
    The typical use case is where the parameter(s)'s get function(s) return(s) an array, e.g. 
    an oscilloscope trace, or a spectrum analyser trace. 
    The array shape(s) do not need to be known and can change between measurements.
    The parameters to be measured are provided at init or through station.set_measurement().
    Optionally, setpoints may be provided, but this is usually not required nor recommended.
    If no setpoints are provided, dummy setpoints are created for each dimension found in the 
    measured parameters (recommended, see Args documentation below).

    ``Measure.run()`` executes the measurement, and returns and saves a ``DataSetPP``

    Examples:
        Measure two parameters:

        >>> station.set_measurement(array_param1, array_param2)
        >>> data = Measure(name='Name for dataset filename').run()

        Measure two parameters twice, changing some value in between:

        >>> station.set_measurement(array_param1, array_param2)
        >>> measure = Measure()
        >>> data=measure.run(name='instrument parameter value = 0')
        >>> instrument.some_parameter(1.0)  # Set some parameter to a value
        >>> data=measure.run(name='instrument parameter value = 1')

        Iteratively:

        >>> station.set_measurement(array_param1, array_param2)
        >>> measure = Measure()
        >>> for i in range(10):
        >>>     instrument.some_parameter(i)  # Set some parameter to a value
        >>>     data=measure.run(name=f'iteration {i}')

    Args:
        *measure (Optional, Sequence[Parameter]): Sequence of gettable Parameters.
            If no actions are provided, the default station.measure() is used.

        name (Optional, str): String to send to the filename of the DataSet.

        setpoints (Optional, Sequence[Parameter or Array]): sequence of setpoint arrays
            use for the DataSetPP. Can be array(s) of values, or gettable Parameter(s). 
            If not provided, dummy setpoints are created for each dimension found in the parameters.
            Providing a setpoint parameter may be useful if you measure a parameter that is considered the 
            independent variable. e.g. time on an oscilloscope, or a voltage ramp on a source. live_plot 
            and offline_plotting will then be able to plot the correct dependencies automatically. However; 
            it can be tricky to get all the dimensions right, so in most instances it's better to just pass 
            all measured parameters to the parameters argument, and then plot whatever parameter against 
            whatever other parameter manually.

        station (Optional, Station): The ``Station`` to use if not the default.

        use_threads (Optional, bool): Use threading to parallelize getting parameters from instruments.
    
        use_timer (Optional, bool, default False): The default station.measure() includes a timer parameter, 
            which is useful for Loops but essentially useless here. If you really want it, set use_timer=True.
    """

    def __init__(self, *measure, setpoints=None, use_threads=False, station=None, name=None, use_timer=False):
        super().__init__()
        self.station = station or Station.default
        self.use_threads = use_threads
        self.setpoints = setpoints
        self.name = name
        self.use_timer = use_timer
        self.actions = measure

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
    
    def run(self, plot=None, name=None, use_threads=None, quiet=False, station=None,**kwargs):
        """
        Run the actions in this measurement and return their data as a DataSetPP

        Args:
            plot (Optional[Sequence[Parameter,str]]): a list of parameters to plot. 
                Provide the parameter, or parameter full_name as a string.

            name (Optional[str]): Filename, minus counter, date and time.
                Overwrites any name provided at init.

            quiet (Optional[bool]): Set True to not print anything except
                errors. Default False.

            station (Optional[Station]): the ``Station`` this measurement
                pertains to. Defaults to ``Station.default`` if one is defined.
                Only used to supply metadata.

            use_threads (Optional[bool]): whether to parallelize ``get``
                operations using threads. Default False.

            kwargs are passed to data_set.new_data. The key ones are:

            location (Optional[Union[str, False]]): the location of the
                DataSetPP, a string whose meaning depends on formatter and io,
                or False to only keep in memory. May be a callable to provide
                automatic locations. If omitted, will use the default
                DataSetPP.location_provider

            formatter (Optional[Formatter]): For writing to file. Default 
                is GnuplotFormat, can be set in DataSetPP.default_formatter

            io (Optional[io_manager]): io manager for DataSetPP object.

        returns:
            a DataSetPP object containing the results of the measurement
        """
        if name:
            self.name = name
        station = station or self.station or Station.default

        if self.use_timer==True:
            station.timer.reset_clock()

        if use_threads is not None:
            self.use_threads = use_threads

        try:
            self._raw_data=self._measure()
                
        except _QcodesBreak:
            self.was_broken=True

        data_set = self._make_data_set(**kwargs)

        if plot is not None:
            pp=live_plot()
            data_set.publisher = pp
            pp.add_subplots(*plot)

        if station:
            data_set.add_metadata({'station': station.snapshot()})

        data_set.add_metadata({'measurement': self.snapshot()})
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_set.add_metadata({'measurement': {
            'ts': ts,
            'use_threads': use_threads,
        }})

        data_set.save_metadata()

        data_set.finalize()

        if not quiet:
            print(repr(data_set))
            print(datetime.now().strftime('Acquired at %Y-%m-%d %H:%M:%S'))

        return data_set
    
    def _construct_measure_dict(self):
        """
        Work out which meassurements need to be made, including the gettable setpoints, if provided.
        """
        params_to_measure={}
        if not self.actions:
            self.actions = self.station.measure()
        if self.use_timer==False: # Useful in the Loop, so is included in station.measure() by default. Less useful here.
            self.actions = [action for action in self.actions if action.name != 'timer']
        if self.setpoints:
            for action in self.setpoints:
                if hasattr(action, '_gettable') and action._gettable: # don't try to measure a parameter without a get method.
                    params_to_measure[action.full_name] = {'action': action, 'is_setpoint': True}
        for action in self.actions:
            if hasattr(action, '_gettable') and action._gettable: # don't try to measure a parameter without a get method.
                params_to_measure[action.full_name] = {'action': action, 'is_setpoint': False}
        return params_to_measure
    
    def _measure(self):
        """
        Perform the measurement: get all the parameters and store in a dict which will be used to fill the DataSetPP.
        """
        # TODO: At the moment there is none of the optimisations that (allegedly) exist in Loop,
        # such as trying to group gettable parameters that have the same source.
        out_dict = {}
        params_to_measure=self._construct_measure_dict()

        getters = [param['action'].get for param in params_to_measure.values()]

        if self.use_threads: # Not tested
            out = thread_map(getters)
        else:
            out = [g() for g in getters]

        for param_out, param in zip(out, params_to_measure):
            action=params_to_measure[param]['action']
            if isinstance(action, MultiParameter):
                for i, name in enumerate(action.names):
                    if action.labels is not None:
                        label = action.labels[i]
                    else:
                        label = name
                    out_dict[name] = {'values':param_out[i],
                                    'unit':action.units[i],
                                    'label':label,
                                    'is_setpoint': params_to_measure[param]['is_setpoint']}
            else:
                out_dict[param] = {'values':param_out,
                                    'unit':action.unit,
                                    'label':action.label,
                                    'is_setpoint': params_to_measure[param]['is_setpoint']}

        return out_dict

    def _make_data_set(self,**kwargs):
        """
        Construct the DataSetPP for this measurement.
        """

        self.data_set=new_data(name=self.name,**kwargs)
        setpoint_arrays=[]

        if self.setpoints:
            for i,sp in enumerate(self.setpoints):
                if np.shape(sp): # If sp has a shape, it is an array-like object
                    setpoint_array = DataArray(label='Setpoints',
                                            unit='',
                                            array_id=f'setpoints_{i}',
                                            name=f'setpoints_{i}',
                                            is_setpoint=True,
                                            preset_data=sp)
                elif isinstance(sp, Parameter):
                    vals=self._raw_data[sp.full_name]['values']
                    setpoint_array = DataArray(parameter=sp, preset_data=vals, is_setpoint=True)
                else:
                    raise TypeError("Setpoints element must be a Parameter or an array-like object")
                setpoint_array.init_data()
                setpoint_arrays.append(setpoint_array)
                self.data_set.add_array(setpoint_array)
            
        for name,value in self._raw_data.items():
            if value['is_setpoint']:
                continue # Setpoints are already added above

            array_shape=np.shape(value['values'])

            if array_shape==(): # if shape is (), make it (1,) to make a setpoint array also.
                array_shape=(1,)
                value['values']=(value['values'],)

            # Try to find the appropriate setpoint arrays for this param
            param_setpoint_arrays=()
            for i in range(np.shape(array_shape)[0]):
                # Find arrays with appropriate shape for each dimension
                # e.g. (10, 20, 30) -> (10,), (10, 20), (10, 20, 30)
                sub_shape = array_shape[:i+1] 
                setpoint_array = False
                for array in setpoint_arrays:
                    if array.shape == sub_shape:
                        setpoint_array = array
                        break

                if not setpoint_array:
                    # If no setpoint array found, create a dummy setpoint array for this 
                    # param with the approrpriate dimension/shape.
                    init_array = np.arange(0, sub_shape[-1], 1)
                    dummy_setpoints = np.tile(init_array, sub_shape[:-1]).reshape(sub_shape)
                    setpoint_array = DataArray(label = 'Setpoints',
                                            unit = '',
                                            array_id = f'setpoints_{len(setpoint_arrays)}',
                                            name = f'setpoints_{len(setpoint_arrays)}',
                                            is_setpoint = True,
                                            preset_data = dummy_setpoints)
                    setpoint_array.init_data()
                    setpoint_arrays.append(setpoint_array)
                    self.data_set.add_array(setpoint_array)

                param_setpoint_arrays = param_setpoint_arrays + (setpoint_array,)

            # Make and add the array to the dataset.
            data_array = DataArray(name = name,
                                label = value['label'],
                                unit = value['unit'],
                                preset_data = value['values'],
                                is_setpoint = False,
                                set_arrays = param_setpoint_arrays)
            data_array.init_data()
            self.data_set.add_array(data_array)

        return self.data_set

    def snapshot_base(self, update=False):
        return {
            '__class__': full_class(self),
            'actions': _actions_snapshot(self.actions, update)
        }

