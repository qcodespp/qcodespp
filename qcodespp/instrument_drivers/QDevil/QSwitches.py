from typing import Tuple, Sequence, List, Dict, Set, Union, Optional
import itertools
from qcodes import Instrument, DelegateParameter
from qcodes.validators import Enum

try:
    from qcodespp.instrument_drivers.QDevil.QSwitch import (QSwitch,
                                                        channel_list_to_state,
                                                        state_to_compressed_list,
                                                        state_to_expanded_list,
                                                        expand_channel_list,
                                                        compress_channel_list,
                                                        State)
except ImportError:
    try:
        from qcodes_contrib_drivers.drivers.QDevil.QSwitch import (QSwitch,
                                                            channel_list_to_state,
                                                            state_to_compressed_list,
                                                            state_to_expanded_list,
                                                            expand_channel_list,
                                                            compress_channel_list,
                                                            State)
    except ImportError:
        raise ImportError('Could not find QSwitch driver from either qcodespp or qcodes_contrib_drivers.\n'
                          'Please make sure one of these packages is installed in the current environment.')

relay_lines=24
relays_per_line=10

class QSwitches(Instrument):
    '''
    Class to treat multiple QSwitches as a single instrument.

    Lines are numbered 1 to N*24 where N is the number of QSwitches
    BNC taps are numbered 1-8, 11-18, 21-28, etc.
    Special taps 'ground'  and 'connect' remain marked as 0 and 9.

    linked_BNCs allows for the case where the front BNCs are externally linked such that e.g. a 
    single instrument input/output can be connected to any of the N*24 lines. The user can then
    use the lowest value of this link. e.g. if linked_BNCs=[[1,11],[2,12]] then
    qsws.close_relay(28,1) is equivalent to
    qsws.close_relay(28,11), and so on.
    It is assumed maximum one link per QSwitch, since otherwise links can be made internally.

    Args:
        qsws (sequence[QSwitches]): list of initialized/connected qswitches
        linked_BNCs (list[list]): list of linked BNCs, e.g. [1,11,21,31].
        name (str): QCodes name. Default = 'qsws'

    Not implemented: 
    Params: auto_save, error_indicator
    Methods: save_state, load_state, saved_states
    '''
    
    def __init__(self,qsws,linked_BNCs=None,name='qsws',**kwargs):
        super().__init__(name,**kwargs)
        if not isinstance(qsws,(list,tuple)):
            raise ValueError('Please provide a list or tuple of QSwitch instruments')
        for qsw in qsws:
            if not isinstance(qsw,QSwitch):
                raise ValueError('Please provide a list or tuple of QSwitch instruments')
                
        self._num_qsws=len(qsws)
        self.qsws=qsws
        self._serials=[qsw.IDN()["serial"] for qsw in self.qsws]
        self.linked_BNCs=linked_BNCs

        self.state=self.add_parameter('state',
                                    label='relays',
                                    get_cmd=self._get_state,
                                    set_cmd=self._set_state)

        self.closed_relays=self.add_parameter('closed_relays',
                                    source=self.state,
                                    set_parser=state_to_compressed_list,
                                    get_parser=channel_list_to_state,
                                    parameter_class=DelegateParameter,
                                    snapshot_value=False)

        self.overview=self.add_parameter('overview',
                                    label='overview',
                                    get_cmd=self._get_overview,
                                    snapshot_value=False)

        self.locked_relays=[]

        self._set_default_names()
        self.state_force_update()

        self._meta_attrs.extend(['serials','linked_BNCs'])

        self.connect_message()

    def connect_message(self):
        print(f'Initialised QSwitches meta-Instrument {self.name} containing QSwitches with serials '+' '.join(self._serials))
        self.log.info(f"Initialised QSwitches meta-Instrument: {self.name}")
        
    # -----------------------------------------------------------------------
    # Bring instrument-wide functions into this driver
    # -----------------------------------------------------------------------
    
    def reset(self):
        for qsw in self.qsws:
            qsw.reset()

    def soft_reset(self,force=False) -> None:
        if not self.locked_relays and not force:
            raise ValueError("No relays are locked. Use force=True to reset all relays anyway.")
        for i,qsw in enumerate(self.qsws):
            qsw.locked_relays=[line for line in self.locked_relays if int((line-1)/relay_lines)==i]
            qsw.soft_reset()

    def errors(self) -> str:
        errorlist=[]
        for qsw in self.qsws:
            errorlist.append(f'QSwitch {qsw.IDN()["serial"]} errors:')
            errorlist.append(qsw.errors())
        return ' '.join(errorlist)

    def error(self) -> str:
        errorlist=[]
        for qsw in self.qsws:
            errorlist.append(f'QSwitch {qsw.IDN()["serial"]} error:')
            errorlist.append(qsw.error())
        return ' '.join(errorlist)

    def state_force_update(self) -> None:
        for qsw in self.qsws:
            qsw.state_force_update()

    def abort(self) -> None:
        for qsw in self.qsws:
            qsw.abort()

    # -----------------------------------------------------------------------
    # Support functions to translate line and tap values to/from individual insts.
    # -----------------------------------------------------------------------            
    
    def _step_line_up(self, line: int, i: int) -> int:
        '''Used when returning the state

        Args:
            line (int): physical line of the qswitch
            i (int): index of the qswitch in self.qsws
        Returns:
            stepped up line number
        '''
        return line+relay_lines*i

    def _step_tap_up(self, tap: int, i: int) -> int:
        '''Used when returning the state

        Soft ground (0) and connect through (9) kept special.
        
        If no linked BNCs, returns 1-8, 11-18, 21-28, etc.
        If linked BNCs, returns the lowest BNC number.

        Args:
            tap (int): physical tap (BNC) of the qswitch
            i (int): index of the qswtich in self.qsws
        Returns:
            stepped up tap number
        '''
        if tap%relays_per_line==0:
            tap=0
        elif tap%relays_per_line==9:
            tap=9
        else:
            tap=self._step_link_down(tap+relays_per_line*i)
        return tap

    def _step_line_down(self, line:int, i:int) -> int:
        '''Used when setting the state'''
        return line-relay_lines*i

    def _step_tap_down(self, tap: int, i: int) -> int:
        '''Used when setting the state'''
        tap=self._step_link_up(tap,i)
        if tap%relays_per_line not in [0,9] and not i*relays_per_line<tap<(i+1)*relays_per_line:
            raise ValueError(f'Tap {tap} cannot be connected to the specified line since they are not on the same QSwitch.\n'
                             'If you have manually linked the BNC taps, you must explicitely declare this.')
        return tap%relays_per_line

    def _step_link_down(self,tap):
        '''If BNC links are used, report the lowest value in the link'''
        if self.linked_BNCs is not None:
            for link in self.linked_BNCs:
                if tap in link:
                    return min(link)
        return tap

    def _step_link_up(self,tap,i):
        '''If BNC links are used and the user provides the lowest value in the link, 
        work out which tap to send to the actual instrument'''
        if self.linked_BNCs is not None:
            for link in self.linked_BNCs:
                if tap in link:
                    tap=[num for num in link if i*relays_per_line<num<(i+1)*relays_per_line][0]
        return tap

    def _get_state(self) -> str:
        state=[]
        for i,qsw in enumerate(self.qsws):
            for line,tap in qsw.closed_relays():
                state.append((self._step_line_up(line,i),
                              self._step_tap_up(tap,i)))
        return state_to_compressed_list(state)

    def _set_state(self, state: str) -> None:
        states=[[] for _ in self.qsws]
        for line,tap in channel_list_to_state(state):
            idx=int((line-1)/relay_lines)
            states[idx-1].append((self._step_line_down(line,idx),
                                self._step_tap_down(tap,idx)))
        for i,qsw in enumerate(self.qsws):
            qsw.state(state_to_compressed_list(states[i]))

    def _get_overview(self) -> dict:
        overview={}
        for i,qsw in enumerate(self.qsws):
            for line,taps in qsw.overview().items():
                try:
                    line=self._step_line_up(int(line),i)
                except ValueError:
                    pass
                for j,tap in enumerate(taps):
                    if 'breakout' in tap:
                        tap_num=self._step_tap_up(int(tap.split()[-1]),i)
                        taps[j]=f'breakout {tap_num}'
                overview[str(line)]=taps
        return overview
        
    # -----------------------------------------------------------------------
    # Direct manipulation of the relays
    # -----------------------------------------------------------------------
  
    def open_relay(self, line: int, tap: int) -> None:
        idx=int((line-1)/relay_lines)
        qsw=self.qsws[idx]
        qsw.open_relay(self._step_line_down(line,idx),self._step_tap_down(tap,idx))
        
    def close_relay(self, line: int, tap: int) -> None:
        idx=int((line-1)/relay_lines)
        qsw=self.qsws[idx]
        qsw.close_relay(self._step_line_down(line,idx),self._step_tap_down(tap,idx))

    def close_relays(self, relays: State) -> None:
        states=[[] for _ in self.qsws]
        for line,tap in relays:
            idx=int((line-1)/relay_lines)
            states[idx].append((self._step_line_down(line,idx),
                                self._step_tap_down(tap,idx)))
        for i,qsw in enumerate(self.qsws):
            qsw.close_relays(states[i])

    def open_relays(self, relays: State) -> None:
        states=[[] for _ in self.qsws]
        for line,tap in relays:
            idx=int((line-1)/relay_lines)
            states[idx].append((self._step_line_down(line,idx),
                                self._step_tap_down(tap,idx)))
        for i,qsw in enumerate(self.qsws):
            qsw.open_relays(states[i])

    # -----------------------------------------------------------------------
    # Manipulation by name
    # -----------------------------------------------------------------------
    OneOrMore=QSwitch.OneOrMore
    
    def ground(self, lines: OneOrMore) -> None:
        connections: List[Tuple[int, int]] = []
        if isinstance(lines, (int,str)):
            line = self._to_line(lines)
            self.close_relay(line, 0)
            idx = int((line-1)/relay_lines)
            taps = range(1+idx*relays_per_line, (1+idx)*relays_per_line)
            connections = list(itertools.zip_longest([], taps, fillvalue=line))
            self.open_relays(connections)
        else:
            numbers = map(self._to_line, lines)
            grounds = list(itertools.zip_longest(numbers, [], fillvalue=0))
            self.close_relays(grounds)
            for tap in range(1, relays_per_line):
                connections += itertools.zip_longest(
                                    map(self._to_line, lines), [], fillvalue=tap)
            for i,connection in enumerate(connections):
                line=connection[0]
                idx = int((line-1)/relay_lines)
                connections[i]=(line,self._step_tap_up(tap,idx))
            self.open_relays(connections)
            
    def connect(self, lines: OneOrMore) -> None:
        if isinstance(lines, (str,int)):
            self.close_relay(self._to_line(lines), 9)
            self.open_relay(self._to_line(lines), 0)
        else:
            numbers = map(self._to_line, lines)
            pairs = list(itertools.zip_longest(numbers, [], fillvalue=9))
            self.close_relays(pairs)
            numbers = map(self._to_line, lines)
            connections = list(itertools.zip_longest(numbers, [], fillvalue=0))
            self.open_relays(connections)
            
    def connect_all(self) -> None:
        for qsw in self.qsws:
            qsw.connect_all()
    
    def breakout(self, line: Union[str,int], tap: Union[str,int]) -> None:
        self.close_relay(self._to_line(line), self._to_tap(tap))
        self.open_relay(self._to_line(line), 0)

    def line_float(self, lines: OneOrMore) -> None:
        if isinstance(lines, (int,str)):
            line = self._to_line(lines)
            idx = int((line-1)/relay_lines)
            taps = range(idx*relays_per_line, (1+idx)*relays_per_line-1)
            connections = list(itertools.zip_longest([], taps, fillvalue=line))
            self.open_relays(connections)
        else:
            for tap in range(relays_per_line+1):
                numbers = map(self._to_line, lines)
                pairs = list(itertools.zip_longest(numbers, [], fillvalue=tap))
                for i,connection in enumerate(pairs):
                    line=connection[0]
                    idx = int((line-1)/relay_lines)
                    pairs[i]=(line,self._step_tap_up(tap,idx))
                self.open_relays(pairs)
        
    def arrange(self, breakouts: Optional[Dict[str, int]] = None,
                lines: Optional[Dict[str, int]] = None) -> None:
        """An arrangement of names for lines and breakouts

        Args:
            breakouts (Dict[str, int]): Name/breakout pairs
            lines (Dict[str, int]): Name/line pairs
        """
        if lines:
            for name, line in lines.items():
                self._line_names[name] = line
        if breakouts:
            for name, tap in breakouts.items():
                self._tap_names[name] = tap
                
    # -----------------------------------------------------------------------
    # Support Functions for addressing by name.
    # -----------------------------------------------------------------------
    
    def _to_line(self, name: Union[str,int]) -> int:
        if isinstance(name,int):
            return name
        try:
            return self._line_names[name]
        except KeyError:
            raise ValueError(f'Unknown line "{name}"')

    def _to_tap(self, name: Union[str,int]) -> int:
        if isinstance(name,int):
            return name
        try:
            return self._tap_names[name]
        except KeyError:
            raise ValueError(f'Unknown tap "{name}"')
            
    def _set_default_names(self) -> None:
        lines = range(1, relay_lines*len(self.qsws)+1)
        taps = [i for i in range(relays_per_line*len(self.qsws)) if i%relays_per_line != 0]
        self._line_names = dict(zip(map(str, lines), lines))
        self._tap_names = dict(zip(map(str, taps), taps))