from datetime import datetime

from qcodespp.parameters import Parameter
from qcodespp.loops import Loop
from qcodespp.actions import _actions_snapshot
from qcodes.utils.helpers import full_class
from qcodes.metadatable import Metadatable


class Measure(Metadatable):
    """
    Create a DataSetPP from a single (non-looped) set of actions.

    Args:
        *actions (any): sequence of actions to perform. Any action that is
            valid in a ``Loop`` can be used here. If an action is a gettable
            ``Parameter``, its output will be included in the DataSetPP.
            The typical use case is to store data from one or more ArrayParameter(s) 
            or ParameterWithSetpoints(s), i.e. non-scalar data, returned
            from an instrument buffer such as an oscilloscope, although scalars are also supported.
            Since the dataset forces us to include an array that acts as 'setpoints',
            a set of dummy setpoints is created for each dimension that is found in the actions.
    """
    dummy_parameter = Parameter(name='single',
                                label='Single Measurement',
                                set_cmd=None, get_cmd=None)

    def __init__(self, *actions, timer=False):
        super().__init__()
        if timer==False:
            actions=tuple(action for action in actions if action.name!='timer')
        self._dummyLoop = Loop(self.dummy_parameter[0]).each(*actions)

    def run_temp(self, **kwargs):
        """
        Wrapper to run this measurement as a temporary data set
        """
        return self.run(quiet=True, location=False, **kwargs)

    def get_data_set(self, *args, **kwargs):
        return self._dummyLoop.get_data_set(*args, **kwargs)
        # What this should actually do:
        # 1) Go through all actions, and if the action is a Parameter,
        #  find the dimension of the data it returns. check if dummy setpoints
        #  already exist, and if not, create them.
        # 2) Create a DataSetPP with the correct setpoints and actions

    def run(self, use_threads=False, quiet=False, station=None, **kwargs):
        """
        Run the actions in this measurement and return their data as a DataSetPP

        Args:
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

        data_set = self._dummyLoop.get_data_set(**kwargs)

        # set the DataSetPP to local for now so we don't save it, since
        # we're going to massage it afterward
        original_location = data_set.location
        data_set.location = False

        # run the measurement as if it were a Loop
        self._dummyLoop.run(use_threads=use_threads,
                            station=station, quiet=True, check_written_data=False, progress_bar=False)

        # look for arrays that are unnecessarily nested, and un-nest them
        all_unnested = True
        for array in data_set.arrays.values():
            if array.ndim == 1:
                if array.is_setpoint:
                    dummy_setpoint = array
                else:
                    # we've found a scalar - so keep the dummy setpoint
                    all_unnested = False
            else:
                # The original return was an array, so take off the extra dim.
                # (This ensures the outer dim length was 1, otherwise this
                # will raise a ValueError.)
                array.ndarray.shape = array.ndarray.shape[1:]

                # TODO: DataArray.shape masks ndarray.shape, and a user *could*
                # change it, thinking they were reshaping the underlying array,
                # but this would a) not actually reach the ndarray right now,
                # and b) if it *did* and the array was reshaped, this array
                # would be out of sync with its setpoint arrays, so bad things
                # would happen. So we probably want some safeguards in place
                # against this
                array.shape = array.ndarray.shape

                array.set_arrays = array.set_arrays[1:]

                array.init_data()

        # Do we still need the dummy setpoint array at all?
        if all_unnested:
            del data_set.arrays[dummy_setpoint.array_id]
            if hasattr(data_set, 'action_id_map'):
                del data_set.action_id_map[dummy_setpoint.action_indices]

        # now put back in the DataSetPP location and save it
        data_set.location = original_location
        data_set.write()

        # metadata: ActiveLoop already provides station snapshot, but also
        # puts in a 'loop' section that we need to replace with 'measurement'
        # but we use the info from 'loop' to ensure consistency and avoid
        # duplication.
        LOOP_SNAPSHOT_KEYS = ['ts_start', 'ts_end', 'use_threads']
        data_set.add_metadata({'measurement': {
            k: data_set.metadata['loop'][k] for k in LOOP_SNAPSHOT_KEYS
        }})
        del data_set.metadata['loop']

        # actions are included in self.snapshot() rather than in
        # LOOP_SNAPSHOT_KEYS because they are useful if someone just
        # wants a local snapshot of the Measure object
        data_set.add_metadata({'measurement': self.snapshot()})

        data_set.save_metadata()

        data_set.finalize()

        if not quiet:
            print(repr(data_set))
            print(datetime.now().strftime('acquired at %Y-%m-%d %H:%M:%S'))

        return data_set

    def snapshot_base(self, update=False):
        return {
            '__class__': full_class(self),
            'actions': _actions_snapshot(self._dummyLoop.actions, update)
        }
