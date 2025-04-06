"""Station objects - collect all the equipment you use to do an experiment."""
from typing import List, Sequence, Any

import time

from qcodes.metadatable import MetadatableWithName

from qcodesplusplus import Instrument, Parameter
from qcodes.parameters import ParameterBase , ElapsedTimeParameter

from qcodes import Station as QStation

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
    Same as QCoDeS station, but we add automatic addition of instruments and parameters,
    and the measurement capabilities.
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
        Automatically add instruments to the station.
        Usually, variables=globals()
        """
        if add_instruments==True:
            if 'instruments' in self.snapshot_base():
                for variable in variables:
                    if isinstance(variables[variable],Instrument):
                        if variables[variable].name not in self.snapshot_base()['instruments']:
                            self.add_component(variables[variable],update_snapshot=update_snapshot)
            else:
                for variable in variables:
                    if isinstance(variables[variable],Instrument):
                        self.add_component(variables[variable],update_snapshot=update_snapshot)

            if 'instruments' not in self.snapshot_base():
                raise KeyError('No instruments found in variable list!')
            else:
                names=[]
                for variable in self.snapshot_base()['instruments']:
                    names.append(variable)
                print('Instruments in station: '+str(names))
        if add_parameters==True:
            if 'parameters' in self.snapshot_base():
                for variable in variables:
                    if isinstance(variables[variable],ParameterBase):
                        if variables[variable].name not in self.snapshot_base()['parameters']:
                            self.add_component(variables[variable],update_snapshot=update_snapshot)
            else:
                for variable in variables:
                    if isinstance(variables[variable],ParameterBase):
                        self.add_component(variables[variable],update_snapshot=update_snapshot)

            if 'parameters' not in self.snapshot_base():
                raise KeyError('No parameters found in variable list!')
            else:
                names=[]
                for variable in self.snapshot_base()['parameters']:
                    names.append(variable)
                print('Parameters in station: '+str(names))

    def set_measurement(self, *actions):
        """
        Save a set ``*actions``` as the default measurement for this Station.

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

        self.default_measurement = actions

        if 'timer' in self.components:
            self.default_measurement = self.default_measurement + (self.components['timer'],)

    def communication_time(self,measurement_num=1):
        commtimes=[]
        for i in range(measurement_num):
            starttime=time.time()
            self.measurement()
            endtime=time.time()
            commtimes.append(endtime-starttime)
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
        Pass the default measurement or parameters in actions to a loop.
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
