import time

import numpy

# To make the modules work within qcodespp
from qcodes.parameters import *

# Specific modules used below, for traceability.
from qcodes.parameters import (
    ArrayParameter,
    MultiParameter,
    Parameter,
    SweepFixedValues,
)

def move(self,end_value,steps=101,step_time=0.03):
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
        SweepFixedValues: collection of parameter values to be
            iterated over
    Examples:
        >>> sweep(0, 10, num=5)
         [0.0, 2.5, 5.0, 7.5, 10.0]
        >>> sweep(5, 10, step=1)
        [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        >>> sweep(15, 10.5, step=1.5)
        >[15.0, 13.5, 12.0, 10.5]
    """
    if self.get()!=start:
        if print_warning==True:
            print('Are you sure? Start value for {}.sweep is {} {} but {}()={} {}'.format(self.name,start,self.unit,self.name,self.get(),self.unit))
    return SweepFixedValues(self, start=start, stop=stop,
                            step=step, num=num)
def logsweep(self, start, stop, num=None):
    """
    Create a collection of parameter values to be iterated over in a log scale
    
    """
    if self.get()!=start:
        print('Are you sure? Start value for {}.sweep is {} {} but {}()={} {}'.format(self.name,start,self.unit,self.name,self.get(),self.unit))
    setpoints=numpy.geomspace(start,stop,num=num)
    return SweepFixedValues(self, setpoints)
def arbsweep(self, setpoints):
    """
    Create a collection of parameter values to be iterated over from a list of arbitrary values.

    Args:
        setpoints (list or array): The setpoints to sweep over.

    Returns:
        SweepFixedValues: collection of parameter values to be
            iterated over

    Example:
        values = [0.0, 2.5, 5.0, 7.5, 10.0]
        loop=qc.Loop(parameter.arbsweep(values),delay=0.1).each(*station.measure())
    """
    if self.get()!=setpoints[0]:
        print('Are you sure? Start value for {}.sweep is {} {} but {}()={} {}'.format(self.name,setpoints[0],self.unit,self.name,self.get(),self.unit))
    return SweepFixedValues(self, setpoints)
def returnsweep(self, start, stop, step=None, num=None):
    """
    Create a collection of parameter values to be iterated over.
    Must be an array or list of values
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
    if self.get()!=start:
        print('Are you sure? Start value for {}.sweep is {} {} but {}()={} {}'.format(self.name,start,self.unit,self.name,self.get(),self.unit))
    return SweepFixedValues(self, setpoints)

def set_data_type(self,data_type=float):
    """
    Set the data type of the parameter.

    Args:
        data_type : The data type of the parameter. Can be 'float' or 'str'.
    """
    if data_type != float:
        if data_type != str:
            raise ValueError('Parameter data_type must be either float or str')
    else:
        self.data_type=data_type

Parameter.move=move
Parameter.sweep=sweep
Parameter.logsweep=logsweep
Parameter.arbsweep=arbsweep
Parameter.returnsweep=returnsweep

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

class MultiParameterWrapper(MultiParameter):
    """
    Class to wrap multiple pre-existing parameters into MultiParameter. Enables getting, setting, sweeping and moving.

    Args:
        parameters (list): List of Parameter objects to wrap.
        name (str, optional): Name of the MultiParameter. Defaults to None.
        instrument (Instrument, optional): Instrument this MultiParameter belongs to. Defaults to None.

    Usage:
        parameters = [param1, param2, param3]  # List of Parameter objects
        multi_param = MultiParameterWrapper(parameters, name='MyMultiParam', instrument=my_instrument)

        # Get values
        values = multi_param()

        # Set all constituent parameters to the same value
        multi_param(value)

        # Set each parameter to different values
        multi_param([1.0, 2.0, 3.0])

        # Move to new values
        multi_param.move([new_value1, new_value2, new_value3])

        # Sweeping all parameters with the same start and stop values
        multi_param.sweep(start_val, stop_val, num=num)

        # Sweeping each parameter with different start and stop values
        multi_param.sweep([start_val1, start_val2], [stop_val1, stop_val2], num=num)

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

    def get_raw(self):
        return tuple([param.get() for param in self.parameters])

    def set_raw(self, values):
        if type(values) is int or type(values) is float:
            for parameter in self.parameters:
                parameter.set(values)
        elif numpy.array(values).shape != numpy.array(self.parameters).shape:
            raise ValueError('Number of values to set must match number of parameters')
        else:
            for i,value in enumerate(values):
                self.parameters[i].set(value)

    def move(self,end_values,steps=101,step_time=0.03):
        if type(end_values) is int or type(end_values) is float:
            for i,param in enumerate(self.parameters):
                param.move(end_values,steps,step_time)       
        else:
            for i,param in enumerate(self.parameters):
                param.move(list(end_values)[i],steps,step_time)

    def sweep(self, start_vals,stop_vals,num):
        #If the user is sweeping all params with the same values, the case is the same as Parameter.sweep
        if numpy.array(start_vals).shape == ():
            if numpy.array(start_vals).shape != numpy.array(stop_vals).shape:
                raise ValueError('Number of start values must match number of stop values')
            return SweepFixedValues(self, start=start_vals, stop=stop_vals,num=num)
        
        #Otherwise, check that the shapes are correct, and make a setpointarray of the appropriate size for SweepFixedValues
        elif numpy.array(start_vals).shape != numpy.array(self.parameters).shape:
            raise ValueError('Number of start_vals must match number of parameters')
        elif numpy.array(stop_vals).shape != numpy.array(self.parameters).shape:
            raise ValueError('Number of stop_vals must match number of parameters')
        setpointarray=[]
        for j in range(num):
            setpointarray.append([start_vals[i] + (stop_vals[i] - start_vals[i])/(num-1) * j for i in range(numpy.array(self.parameters).shape[0])])
        return SweepFixedValues(self,setpointarray)
