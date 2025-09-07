"""A collection of functions that get added to the QCoDeS Parameter class.

In addition, two wrapper classes are provided to easily create ArrayParameters and MultiParameters.
MultiParameters created with this method become settable, sweepable and movable.
"""

import time

import numpy

from qcodes.parameters import (
    ArrayParameter,
    MultiParameter,
    Parameter,
    ParameterBase,
    SweepFixedValues
)

from typing import Any

from qcodes.parameters.sequence_helpers import is_sequence

def move(self,end_value,steps=101,step_time=0.03):
    """
    Move the parameter to a new value in a number of steps without taking data.
    
    Args:
        end_value (float): The value to move to.

        steps (int, optional): Number of steps to take. Defaults to 101.

        step_time (float, optional): Time in seconds between each step. Defaults to 0.03.
    """
    start_value = self.get()
    for i in range(0,steps):
        self.set(start_value + (end_value - start_value)/(steps-1) * i)
        time.sleep(step_time)
    self.set(end_value)
    
def sweep(self, start, stop, step=None, num=None, print_warning=True):
    """
    Create a collection of parameter values to be iterated over.

    Requires `start` and `stop` and (`step` or `num`)
    The sign of `step` is not relevant.

    Args:
        start (Union[int, float]): The starting value of the sequence.

        stop (Union[int, float]): The end value of the sequence.

        step (Optional[Union[int, float]]):  Spacing between values.

        num (Optional[int]): Number of values to generate.

    Returns:
        SweepFixedValues: collection of parameter values to be iterated over

    Examples:
        >>> sweep(0, 10, num=5)
         [0.0, 2.5, 5.0, 7.5, 10.0]
        >>> sweep(5, 10, step=1)
        [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        >>> sweep(15, 10.5, step=1.5)
        >[15.0, 13.5, 12.0, 10.5]
    """
    sweeprange= numpy.abs(stop - start)
    try:
        if numpy.abs(self.get()-start)>sweeprange*1e-3 and print_warning:
            print('Are you sure? Start value for {}.sweep is {} {} but {}()={} {}'.format(self.name,start,self.unit,self.name,self.get(),self.unit))
    except TypeError: #Sometimes a parameter (especially a dummy parameter) will return None if it has not been set yet.
        pass
    return SweepFixedValues(self, start=start, stop=stop,
                            step=step, num=num)

def logsweep(self, start, stop, num=None, print_warning=True):
    """
    Create a collection of parameter values to be iterated over in a log scale
    
    Requires `start` and `stop` and or `num`. Note that `step` cannot be used here.

    Args:
        start (Union[int, float]): The starting value of the sequence.

        stop (Union[int, float]): The end value of the sequence.

        num (Optional[int]): Number of values to generate.

    Returns:
        SweepFixedValues: collection of parameter values to be iterated over
    """
    try:
        if numpy.abs(self.get()-start)>start*1e-3 and print_warning:
            print('Are you sure? Start value for {}.logsweep is {} {} but {}()={} {}'.format(self.name,start,self.unit,self.name,self.get(),self.unit))
    except TypeError:
        pass
    setpoints=numpy.geomspace(start,stop,num=num)
    return SweepFixedValues(self, setpoints)

def arbsweep(self, setpoints, print_warning=True):
    """
    Create a collection of parameter values to be iterated over from a list of arbitrary values.

    Args:
        setpoints (list or array): The setpoints to sweep over.

    Returns:
        SweepFixedValues: collection of parameter values to be iterated over

    Example:
        >>> values = [0.0, 2.5, 5.0, 7.5, 10.0]
        >>> loop=qc.Loop(parameter.arbsweep(values),delay=0.1).each(*station.measure())
    """
    sweeprange=numpy.abs(numpy.max(setpoints) - numpy.min(setpoints))
    try:
        if numpy.abs(self.get()-setpoints[0])>sweeprange*1e-3 and print_warning:
            print('Are you sure? Start value for {}.arbsweep is {} {} but {}()={} {}'.format(self.name,setpoints[0],self.unit,self.name,self.get(),self.unit))
    except TypeError:
        pass
    return SweepFixedValues(self, setpoints)

def returnsweep(self, start, stop, step=None, num=None, print_warning=True):
    """
    Create a collection of parameter values to be iterated over,
    where the parameter sweeps from `start` to `stop` and then back up to `start`.

    The total number of points will be `2*num-1` if `num` is provided,
    or `2*(stop-start)/step+1` if `step` is provided.

    Args:
        start (Union[int, float]): The starting value of the sequence.

        stop (Union[int, float]): The end value of the sequence.

        step (Optional[Union[int, float]]):  Spacing between values.

        num (Optional[int]): Number of values to generate.

    Returns:
        SweepFixedValues: collection of parameter values to be iterated over
    """
    if step is not None:
        if num is not None:
            raise AttributeError('Sweeps cannot accept step AND num.')
        else:
            num=numpy.int(numpy.abs((stop-start)/step)+1)
    elif num is not None:
        if step is not None:
            raise AttributeError('Sweeps cannot accept step AND num.')
        else:
            step=numpy.abs((stop-start)/(num-1))
            num=num
    setpointsdown=numpy.linspace(start,stop,num)
    if stop>start:
        step=-step
    setpointsup=numpy.linspace(stop+step,start,num-1)
    setpoints=numpy.hstack((setpointsdown,setpointsup))
    sweeprange= numpy.abs(stop - start)
    try:
        if numpy.abs(self.get()-start)>sweeprange*1e-3 and print_warning:
            print('Are you sure? Start value for {}.returnsweep is {} {} but {}()={} {}'.format(self.name,start,self.unit,self.name,self.get(),self.unit))
    except TypeError:
        pass
    return SweepFixedValues(self, setpoints)

def set_data_type(self,data_type=float):
    """
    Should no longer be necessary: marked for deprecation.

    Set the data type of the parameter. Gets passed to DataArray and the underlying numpy ndarray.

    Args:
        data_type : The data type of the parameter. Can be 'float' or 'str'.
    """
    if data_type not in [float,str]:
        raise ValueError('Parameter data_type must be either float or str')
    else:
        self.data_type=data_type

Parameter.move=move
Parameter.sweep=sweep
Parameter.logsweep=logsweep
Parameter.arbsweep=arbsweep
Parameter.returnsweep=returnsweep

def _set_step(val):
    pass
stepper=Parameter(name='stepper',label='Step Number',unit='#',set_cmd=_set_step)

class ArrayParameterWrapper(ArrayParameter):
    """
    Wrapper to easily declare ArrayParameters.

    Args:
        name (str, optional): Name of the ArrayParameter. Defaults to None.

        label (str, optional): Label for the ArrayParameter. Defaults to None.

        unit (str, optional): Unit for the ArrayParameter. Defaults to None.

        instrument (Instrument, optional): Instrument this ArrayParameter belongs to. Defaults to None.

        shape (tuple, optional): Shape of the array. If not provided, it will be inferred from the get_cmd.

        get_cmd (callable, optional): Function that returns the array data. If provided, shape will be inferred from its output.

    Usage:
        Example usage where an instrument has a get_buffer() function which returns an array

        VoltageBuffer=qc.ArrayParameterWrapper(name='VoltageBuffer',
                                            label='Voltage',
                                            unit='V',
                                            get_cmd=VoltageInstrument.get_buffer)
    """

    def __init__(self, name=None, label=None,unit=None, instrument=None, shape=None, get_cmd=None):

        if get_cmd is not None:
            self.get_raw=get_cmd
        if shape is None and get_cmd is not None:
            array=get_cmd()
            if isinstance(array,list):
                array=numpy.array(array)
            shape=array.shape
        else:
            raise AttributeError('Provide either a shape or a get_cmd')

        super().__init__(name=name, shape=shape,instrument=instrument,label=label,unit=unit)

class SweepMultiValues(SweepFixedValues):
    '''
    Class to enable sweeping MultiParameters with different values for each parameter.

    Simply a subclass of SweepFixedValues with a restricted set of options to ensure that the
    setpoints are constructed correctly.
    
    Args:
        parameter (MultiParameter): The MultiParameter to sweep.
        keys (list): A list of lists, where each inner list contains the setpoints for each 
        parameter at that sweep index.
    '''
    def __init__(
        self,
        parameter: ParameterBase,
        keys: Any | None = None):

        super().__init__(parameter,keys)
        # Initialising the parent class constructs the setpoints incorrectly, 
        # so reset self._values to an empty list.
        self._values: list[Any] = []
        self._snapshot: dict[str, Any] = {}
        self._value_snapshot: list[dict[str, Any]] = []

        if isinstance(keys, slice):
            self._add_slice(keys)
            self._add_linear_snapshot(self._values)

        elif is_sequence(keys):
            for key in keys:
                if isinstance(key, slice):
                    self._add_slice(key)
                else:
                    # assume a single value
                    self._values.append(key)
            # we dont want the snapshot to go crazy on big data
            if self._values:
                self._add_sequence_snapshot(self._values)

        else:
            # assume a single value
            self._values.append(keys)
            self._value_snapshot.append({"item": keys})

        self.validate(self._values)

class MultiParameterWrapper(MultiParameter):
    """
    Class to wrap multiple pre-existing parameters into MultiParameter. Enables getting, setting, sweeping and moving.

    Args:
        parameters (list or tuple): List of Parameters to wrap.

        name (str, optional): Name of the MultiParameter.

        instrument (Instrument, optional): Instrument this MultiParameter belongs to, if any.

    Examples:
        multi_param = MultiParameterWrapper((param1, param2, param3), name='multi_param', instrument=my_instrument)

        Get values
        >>> values = multi_param()

        Set all constituent parameters to the same value
        >>> multi_param(value)

        Set each parameter to different values
        >>> multi_param([1.0, 2.0, 3.0])

        Move to new values
        >>> multi_param.move([new_value1, new_value2, new_value3])

        Sweeping all parameters with the same start and stop values
        >>> multi_param.sweep(start_val, stop_val, num=num)

        Sweeping each parameter with different start and stop values
        >>> multi_param.sweep([start_val1, start_val2], [stop_val1, stop_val2], num=num)

        When used in a qcodespp Loop, if all parameters are swept with the same values, 
        the setpoint array will be the setpoints.
        If the parameters are swept with different values, the setpoints will be indices, 
        and the constituent parameters will be automatically added to the measurement, so that 
        each parameter gets measured at each setpoint.
    """
    def __init__(self,parameters,name=None, instrument=None):

        self.parameters=parameters
        names=[]
        shapes=[]
        labels=[]
        units=[]
        for param in self.parameters:
            names.append(param.full_name)
            shapes.append(())
            labels.append(param.label)
            units.append(param.unit)

        super().__init__(name=name, names=tuple(names),shapes=tuple(shapes))

        self.labels=tuple(labels)
        self.units=tuple(units)
        self.unit='' # Mainly to be compatible with automatic naming in loop1d,loop2d, etc.

    def get_raw(self):
        '''
        Method to get the values of all parameters in the MultiParameter.

        Returns:
            tuple: A tuple containing the values of all parameters in the MultiParameter.
        '''
        return tuple([param.get() for param in self.parameters])

    def set_raw(self, values):
        """
        Method to set the values of all parameters in the MultiParameter.

        Args:
            values (list, tuple, int, float): The values to set for the parameters.
                If a single value is provided, it will be set for all parameters.
                If a list or tuple is provided, it must match the number of parameters.
        """

        if type(values) in [int, float]:
            for parameter in self.parameters:
                parameter.set(values)
        elif numpy.array(values).shape != numpy.array(self.parameters).shape:
            raise ValueError('Number of values to set must match number of parameters')
        else:
            for i,value in enumerate(values):
                self.parameters[i].set(value)

    def move(self,end_values,steps=101,step_time=0.03):
        """
        Move all parameters to new values in a number of steps without taking data.

        Args:
            end_values (list, tuple, int, float): The values to move to.
                If a single value is provided, it will be moved for all parameters.
                If a list or tuple is provided, it must match the number of parameters.
            steps (int, optional): Number of steps to take. Defaults to 101.
            step_time (float, optional): Time in seconds between each step. Defaults to 0.03.
        """

        if isinstance(end_values, (int, float)):
            setpoints=[numpy.linspace(self.parameters[i](),end_values,steps) for i in range(len(self.parameters))]
        elif numpy.array(end_values).shape != numpy.array(self.parameters).shape:
            raise ValueError('Number of end values must match number of parameters')
        else:
            setpoints=[numpy.linspace(self.parameters[i](),end_values[i],steps) for i in range(len(self.parameters))]
        
        for j in range(steps):
            for i,param in enumerate(self.parameters):
                param(setpoints[i][j])

    def sweep(self, start_vals,stop_vals,num,print_warning=True):
        """
        Create a collection of parameter values to be iterated over for all parameters in the MultiParameter.

        Args:
            start_vals (list, tuple, int, float): The starting values of the sequence.
                If a single value is provided, it will be used for all parameters.
                If a list or tuple is provided, it must match the number of parameters.

            stop_vals (list, tuple, int, float): The end values of the sequence.
                If a single value is provided, it will be used for all parameters.
                If a list or tuple is provided, it must match the number of parameters.

            num (int): Number of values to generate.

            print_warning (bool): Whether to print a warning if the start value is different from the 
                current value. Defaults to True.

        Returns:
            SweepFixedValues or SweepMultiValues: A collection of parameter values to be iterated over which can be passed to a Loop.

        Raises:
            ValueError: If the number of start_vals or stop_vals does not match the number of parameters, 
            or if they are not a single value.
        """

        #If the user is sweeping all params with the same values, the case is the same as Parameter.sweep
        if type(start_vals) in [int, float]:
            # Check that the start and stop values are the same shape
            if numpy.array(start_vals).shape != numpy.array(stop_vals).shape:
                raise ValueError('Number of start values must match number of stop values')
            
            # Warn the user if the start value is different from any of the current values
            sweeprange= numpy.abs(stop_vals - start_vals)
            for i,parameter in enumerate(self.parameters):
                try:
                    if print_warning and numpy.abs(parameter.get()-start_vals)>sweeprange*1e-3:
                        print(f'Are you sure? Start value for {parameter.name} sweep is '
                            f'{start_vals} {parameter.unit} but '
                            f'{parameter.name}()={parameter.get()} {parameter.unit}')
                except TypeError: #Sometimes a parameter (especially a dummy parameter) will return None if it has not been set yet.
                    pass
            
            # return SweepFixedValues as for a Parameter
            return SweepFixedValues(self, start=start_vals, stop=stop_vals,num=num)
        
        # Otherwise, check that the shapes are correct, and make a setpointarray of the appropriate size 
        # for SweepMultiValues, after checking the start values are close to the current values.
        elif numpy.array(start_vals).shape != numpy.array(self.parameters).shape:
            raise ValueError('Number of start_vals must match number of parameters, or be a signle value')
        elif numpy.array(stop_vals).shape != numpy.array(self.parameters).shape:
            raise ValueError('Number of stop_vals must match number of parameters, or be a signle value')
        
        else:
            for i,parameter in enumerate(self.parameters):
                sweeprange= numpy.abs(stop_vals[i] - start_vals[i])
                try:
                    if print_warning and numpy.abs(parameter.get()-start_vals[i])>sweeprange*1e-3:
                        print(f'Are you sure? Start value for {parameter.name} sweep is '
                                f'{start_vals[i]} {parameter.unit} but '
                                f'{parameter.name}()={parameter.get()} {parameter.unit}')
                except TypeError: #Sometimes a parameter (especially a dummy parameter) will return None if it has not been set yet.
                    pass

            setpointarray=[]
            for j in range(num):
                setpointarray.append([start_vals[i] + (stop_vals[i] - start_vals[i])/(num-1) * j for i in range(numpy.array(self.parameters).shape[0])])
            return SweepMultiValues(self,setpointarray)

