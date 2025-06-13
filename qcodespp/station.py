"""Station objects - collect all the equipment you use to do an experiment."""
from typing import List, Sequence, Any

import time

from qcodes.metadatable import MetadatableWithName

from qcodespp.parameters import Parameter
from qcodes.parameters import ParameterBase , ElapsedTimeParameter

from qcodes import Station as QStation
from qcodes import Instrument
from qcodespp.actions import _actions_snapshot
from numpy import mean

'''
This code wraps the QCoDeS Station class and adds some functionality to it.
It allows for the automatic addition of instruments and parameters to the station,
and underlies the data acquisition. In qcodesplusplus there is no separate measurement
context, since all measurements should be done in the context of a station anyway.
Doing it like this forces the user to only measure parameters in the station,
without the need for a separate measurement context.
'''

class Station(QStation):
    """
    A representation of the physical measurement setup/station.

    This class is a wrapper around the QCoDeS Station class, adding functionality
    for automatic addition of instruments and parameters, and providing a
    measurement method that can be used to measure parameters in the station.

    Args:
        components: List of Instruments, Parameters, or other components to add to the station.

        add_variables: Automatically adds previously defined Instruments and Parameters to the station.
        Typically, add_variables=globals() to look through all previously defined variables.

        config_file: Path to YAML files to load the station config from.
            - If only one yaml file needed to be loaded, it should be passed
              as a string, e.g., '~/station.yaml'
            - If more than one yaml file needed, they should be supplied as
              a sequence of strings, e.g. ['~/station1.yaml', '~/station2.yaml']

        use_monitor: Should the QCoDeS monitor be activated for this station.

        default: Is this station the default?

        update_snapshot: Immediately update the snapshot of each component as it is added to the Station.

        inc_timer: Include a timer parameter in the station and the default measurement.

    """

    def __init__(
        self,
        *components: MetadatableWithName,
        add_variables: Any=None,
        config_file: str | Sequence[str] | None = None,
        use_monitor: bool | None = None,
        default: bool = True,
        update_snapshot: bool = True,
        inc_timer: bool = True,
        **kwargs: Any,
    ) -> None:
        
        super().__init__(*components, config_file,use_monitor,default,update_snapshot,**kwargs)

        # when a new station is defined, store it in a class variable
        # so it becomes the globally accessible default station.
        # You can still have multiple stations defined, but to use
        # other than the default one you must specify it explicitly.
        # If for some reason you want this new Station NOT to be the
        # default, just specify default=False
        if default:
            Station.default = self

        self.components: dict[str, MetadatableWithName] = {}
        for item in components:
            self.add_component(item, update_snapshot=update_snapshot)

        self.use_monitor = use_monitor

        self._added_methods: list[str] = []
        self._monitor_parameters: list[Parameter] = []

        if config_file is None:
            self.config_file = []
        elif isinstance(config_file, str):
            self.config_file = [
                config_file,
            ]
        else:
            self.config_file = list(config_file)

        self.load_config_files(*self.config_file)

        if inc_timer==True:
            timer=ElapsedTimeParameter(name='timer')
            self.add_component(timer, update_snapshot=update_snapshot)

        self.default_measurement = [] # type: List

        if add_variables is not None:
            self.auto_add(add_variables)

    def auto_add(self,variables,add_instruments: bool=True,add_parameters: bool=True,update_snapshot: bool=True):
        """
        Automatically add previously defined instruments and parameters to the station. Usually, auto_add=globals().

        Args:
            variables: Dictionary of variables to check for Instruments and Parameters. e.g. globals(), locals(), etc.
            
            add_instruments: If True, add Instruments to the station.
            
            add_parameters: If True, add Parameters to the station.
            
            update_snapshot: If True, update the snapshot of each component as it is added to the Station.
        """
        print('Automatically adding components to Station...')
        for variable in variables:
            if add_instruments and isinstance(variables[variable],Instrument):
                if 'instruments' not in self.snapshot_base():
                    self.add_component(variables[variable],update_snapshot=update_snapshot)
                elif variables[variable].name not in self.snapshot_base()['instruments']:
                    self.add_component(variables[variable],update_snapshot=update_snapshot)
            elif add_parameters and isinstance(variables[variable],ParameterBase):
                if 'parameters' not in self.snapshot_base():
                    self.add_component(variables[variable],update_snapshot=update_snapshot)
                elif variables[variable].name not in self.snapshot_base()['parameters']:
                    self.add_component(variables[variable],update_snapshot=update_snapshot)
        if add_instruments and 'instruments' in self.snapshot_base():
            names=[name for name in self.snapshot_base()['instruments']]
            print('Instruments in station: '+str(names))
        if add_parameters and 'parameters' in self.snapshot_base():
            names=[name for name in self.snapshot_base()['parameters']]
            print('Parameters in station: '+str(names))

    def snapshot_base(self, update: bool=False,
                      params_to_skip_update: Sequence[str]=None) -> dict:
        """
        State of the station as a JSON-compatible dict.

        Note: in the station contains an instrument that has already been
        closed, not only will it not be snapshotted, it will also be removed
        from the station during the execution of this function.

        Args:
            update (bool): If True, update the state by querying the
             all the children: f.ex. instruments, parameters, components, etc.
             If False, just use the latest values in memory.

        Returns:
            dict: base snapshot
        """
        snap = {
            'instruments': {},
            'parameters': {},
            'components': {},
            'default_measurement': _actions_snapshot(
                self.default_measurement, update)
        }

        components_to_remove = []

        for name, itm in self.components.items():
            if isinstance(itm, Instrument):
                # instruments can be closed during the lifetime of the
                # station object, hence this 'if' allows to avoid
                # snapshotting instruments that are already closed
                if Instrument.is_valid(itm):
                    snap['instruments'][name] = itm.snapshot(update=update)
                else:
                    components_to_remove.append(name)
            elif isinstance(itm, (Parameter
                                  )):
                snap['parameters'][name] = itm.snapshot(update=update)
            else:
                snap['components'][name] = itm.snapshot(update=update)

        for c in components_to_remove:
            self.remove_component(c)

        return snap

    def set_measurement(self, *actions):
        """
        Save a set of ``*actions``` as the default measurement for this Station.

        These actions will be executed by default by a Loop if this is the
        default Station, and any measurements among them can be done once
        by .measure

        Args:
            *actions: parameters to set as default  measurement
        """
        # Validate now so the user gets an error message ASAP
        # and so we don't accept `Loop` as an action here, where
        # it would cause infinite recursion.
        # We need to import Loop inside here to avoid circular import
        from .loops import Loop
        Loop.validate_actions(*actions)

        for action in actions:
            if hasattr(action,'get') and action not in self.components.values():
                if hasattr(action, 'instrument') and action.instrument not in self.components.values():
                    raise ValueError(f'Could not find {action.full_name} nor a possible parent instrument in the specified Station. '
                        'Please add the parameter and/or instrument to the Station before measuring to avoid loss of metadata.')
            elif hasattr(action, 'instrument') and action.instrument and action.instrument not in self.components.values():
                    raise ValueError(f'{action.full_name} belongs to the instrument {action.instrument.name}, but this instrument '
                        'is not in the specified Station. '
                        'Please add this instrument to the Station before measuring to avoid loss of metadata.')

        self.default_measurement = actions

        if 'timer' in self.components:
            self.default_measurement = self.default_measurement + (self.components['timer'],)

    def communication_time(self,measurement_num=5, return_average=True):
        """
        Estimate how long it takes to communicate with the instruments in the station.

        Args:
            measurement_num: Number of measurements to take to estimate the communication time.
                Default is 1, but can be set to a higher number for more accurate estimates.
            return_average: Whether to return the average of the measurements or the entire list.
        Returns:
            Either the average communication time or the list of communication times for each measurement.
        """
        commtimes=[]
        for i in range(measurement_num):
            starttime=time.time()
            self.measurement()
            endtime=time.time()
            commtimes.append(endtime-starttime)
        if return_average:
            return mean(commtimes)
        else:
            return commtimes

    def measurement(self, *actions):
        """
        Measure the default measurement, or parameters in actions.

        Args:
            *actions: parameters to mesure
        """
        if not actions:
            actions = self.default_measurement

        out = []

        # this is a stripped down, uncompiled version of how
        # ActiveLoop handles a set of actions
        # callables (including Wait) return nothing, but can
        # change system state.
        for action in actions:
            if hasattr(action, 'get'):
                out.append(action.get())
            elif callable(action):
                action()

        return out

    def measure(self,*actions,timer=None):
        """
        Pass the default measurement to a loop after previously setting it with set_measurement.

        Example:
            station.set_measurement(param1, param2)
            loop = Loop(instrument.parameter.sweep(1, 10, 1),delay=0.1).each(*station.measure())
        """

        if not actions:
            actions = self.default_measurement
        if timer==False:
            actions=tuple(action for action in actions if action.name!='timer')
        return actions

    # station['someitem'] and station.someitem are both
    # shortcuts to station.components['someitem']
    # (assuming 'someitem' doesn't have another meaning in Station)
    def __getitem__(self, key):
        """Shortcut to components dict."""
        return self.components[key]

    delegate_attr_dicts = ['components']
