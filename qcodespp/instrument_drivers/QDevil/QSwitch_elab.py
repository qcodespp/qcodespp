import re
import itertools
from time import sleep as sleep_s
from qcodes.parameters import DelegateParameter
from qcodes.instrument.visa import Instrument
from qcodes import validators
from pyvisa.errors import VisaIOError
from typing import (
    Tuple, Sequence, List, Dict, Set, Union, Optional)
from packaging.version import parse
import socket
import pyvisa as visa
import os
import json

# Version 1.1.0

State = Sequence[Tuple[int, int]]


def _line_tap_split(input: str) -> Tuple[int, int]:
    pair = input.split('!')
    if len(pair) != 2:
        raise ValueError(f'Expected channel pair, got {input}')
    if not pair[0].isdecimal():
        raise ValueError(f'Expected channel, got {pair[0]}')
    if not pair[1].isdecimal():
        raise ValueError(f'Expected channel, got {pair[1]}')
    return int(pair[0]), int(pair[1])


def channel_list_to_state(channel_list: str) -> State:
    outer = re.match(r'\(@([0-9,:! ]*)\)', channel_list)
    result: List[Tuple[int, int]] = []
    if len(channel_list)==0:
        return result
    elif not outer:
        raise ValueError(f'Expected channel list, got {channel_list}')
    sequences = outer[1].split(',')
    for sequence in sequences:
        limits = sequence.split(':')
        if limits == ['']:
            raise ValueError(f'Expected channel sequence, got {limits}')
        line_start, tap_start = _line_tap_split(limits[0])
        line_stop, tap_stop = line_start, tap_start
        if len(limits) == 2:
            line_stop, tap_stop = _line_tap_split(limits[1])
        if len(limits) > 2:
            raise ValueError(f'Expected channel sequence, got {limits}')
        if tap_start != tap_stop:
            raise ValueError(
                f'Expected same breakout in sequence, got {limits}')
        for line in range(line_start, line_stop+1):
            result.append((line, tap_start))
    return result


def state_to_expanded_list(state: State) -> str:
    return \
        '(@' + \
        ','.join([f'{line}!{tap}' for (line, tap) in state]) + \
        ')'


def state_to_compressed_list(state: State) -> str:
    tap_to_line: Dict[int, Set[int]] = dict()
    for line, tap in state:
        tap_to_line.setdefault(tap, set()).add(line)
    taps = list(tap_to_line.keys())
    taps.sort()
    intervals = []
    for tap in taps:
        start_line = None
        end_line = None
        lines = list(tap_to_line[tap])
        lines.sort()
        for line in lines:
            if not start_line:
                start_line = line
                end_line = line
                continue
            if line == end_line + 1:
                end_line = line
                continue
            if start_line == end_line:
                intervals.append(f'{start_line}!{tap}')
            else:
                intervals.append(f'{start_line}!{tap}:{end_line}!{tap}')
            start_line = line
            end_line = line
        if start_line == end_line:
            intervals.append(f'{start_line}!{tap}')
        else:
            intervals.append(f'{start_line}!{tap}:{end_line}!{tap}')
    return '(@' + ','.join(intervals) + ')'


def expand_channel_list(channel_list: str) -> str:
    return state_to_expanded_list(channel_list_to_state(channel_list))


def compress_channel_list(channel_list: str) -> str:
    return state_to_compressed_list(channel_list_to_state(channel_list))


relay_lines = 24
relays_per_line = 9


def _state_diff(before: State, after: State) -> Tuple[State, State, State]:
    initial = frozenset(before)
    target = frozenset(after)
    return list(target - initial), list(initial - target), list(target)


class QSwitch(Instrument):

    def __init__(self, name: str, address: str, **kwargs: "Unpack[InstrumentBaseKWArgs]") -> None:
        """Connect to a QSwitch

        Args:
            name (str): Name for instrument
            address (str): Address identification string, either a visa identification address (for USB or TCP/IP (fw<=1.3)) or IP address (for UDP (fw>=2.0))
        """
        visalib = kwargs.pop('visalib', '@py')
        super().__init__(name, **kwargs)
        self._check_instrument_name(name)
        if 'ASRL' in address:
            self._udp_mode = False
            self._switch = visa.ResourceManager(visalib).open_resource(address)
            self._set_up_visa()
        elif 'TCPIP' in address: #(TCP/IP connection for fw 1.3 and below)
            self._udp_mode = False
            self._switch = visa.ResourceManager(visalib).open_resource(address)
            self._set_up_visa()
        elif address.count(":") == 0: #(UDP connection for fw 2.0 and above)
            self._udp_mode = True
            self._max_udp_writes = 5
            self._max_udp_queries = 5
            self._udp_ip = address
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(2)  # time_out in seconds
        else:
            raise ValueError(f'Unknown connection type')
          
        self._set_up_debug_settings()
        self._set_up_simple_functions()
        self.connect_message()
        self._check_for_wrong_model()
        self._check_for_incompatiable_firmware()
        self._set_default_names()
        self.state_force_update()
        self.add_parameter(
            name='state',
            label='relays',
            set_cmd=self._set_state,
            get_cmd=self._get_state,
        )
        self.add_parameter(
            name='closed_relays',
            source=self.state,
            set_parser=state_to_compressed_list,
            get_parser=channel_list_to_state,
            parameter_class=DelegateParameter,
            snapshot_value=False,
        )
        self.add_parameter(
            name='auto_save',
            set_cmd='aut {0}'.format('{}'),
            get_cmd='aut?',
            get_parser=str,
            vals=validators.Enum('on', 'off'),
            snapshot_value=False,
        )
        self.add_parameter(
            name='error_indicator',
            set_cmd='beep:stat {0}'.format('{}'),
            get_cmd='beep:stat?',
            get_parser=str,
            vals=validators.Enum('on', 'off'),
            snapshot_value=False,
        )
        self._add_monitor_pseudo_parameters()

        self.locked_relays = []  # list of relays that are not reset when calling the soft_reset command

    # -----------------------------------------------------------------------
    # Instrument-wide functions
    # -----------------------------------------------------------------------

    def reset(self) -> None:
        self._write('*rst')
        sleep_s(0.6)
        self.state_force_update()

    def soft_reset(self, force=False) -> None:
        """ Resets the relays to the default state excluding the relays in self.lokced_relays
            The check for locked relays prevents accidentally reseting e.g. a gate in the case that the kernel is restarted but the locked_relays parameter is not updated.
        Args:
            force (bool): If True, all relays are reset to the default state. Bypasses the check for locked relays.
        """
        if not self.locked_relays and not force:
            raise ValueError("No relays are locked. Use force=True to reset all relays anyway.")
        else:
            for line in range(1, relay_lines+1):
                if line not in self.locked_relays:
                    for tap in range(1, relays_per_line+1):
                        self.open_relay(line, tap)
                    self.close_relay(line, 0)

            sleep_s(0.6)
            self.state_force_update()

    def errors(self) -> str:
        """Retrieve and clear all previous errors

        Returns:
            str: Comma separated list of errors or '0, "No error"'
        """
        return self.ask('all?')

    def error(self) -> str:
        """Retrieve next error

        Returns:
            str: The next error or '0, "No error"'
        """
        return self.ask('next?')

    def state_force_update(self) -> None:
        self._set_state_raw(self.ask('stat?'))


    def save_state(self, name: str, unique=False) -> None:
        """Save the current state of the relays

        Args:
            name (str): Name of the saved state
            unique (bool): If True, save the state in a file with the serial number of the qswitch as an identifier
        """
        try:
            # Determine the directory of the Jupyter Notebook
            notebook_dir = os.getcwd()
            if unique:
                savedstates_path = os.path.join(notebook_dir, 'savedstates_{}.json'.format(self.IDN()["serial"]))
            else:
                savedstates_path = os.path.join(notebook_dir, 'savedstates.json')

            # Load existing states if the file exists
            try:
                with open(savedstates_path, 'r') as f:
                    savedstates = json.load(f)
            except FileNotFoundError:
                savedstates = {}

            # Add the current state to the saved states
            savedstates[name] = self.state

            # Write the updated states back to the file
            with open(savedstates_path, 'w') as f:
                json.dump(savedstates, f, indent=4)

        except Exception as e:
            raise ValueError(f"Failed to save state: {e}")
        

    def load_state(self, name: str, unique = False) -> None:
        """Load a saved state of the relays

        Args:
            name (str): Name of the saved state
            unique (bool): If True, load the state from a file with the serial number of the qswitch as an identifier
        """
        try:
            notebook_dir = os.getcwd()
            if unique:
                savedstates_path = os.path.join(notebook_dir, 'savedstates_{}.json'.format(self.IDN()["serial"]))
            else:
                savedstates_path = os.path.join(notebook_dir, 'savedstates.json')


            with open(savedstates_path, 'r') as f:
                savedstates = json.load(f)

            if name in savedstates:
                self._set_state(savedstates[name])
            else:
                raise ValueError(f"State '{name}' not found.")

        except FileNotFoundError:
            raise ValueError("No saved states found.")
        except Exception as e:
            raise ValueError(f"Failed to load state: {e}")
        

    def saved_states(self, unique = False) -> Dict[str, str]:
        """Get a dictionary of saved states

        Args:
            unique (bool): If True, load the state from a file with the serial number of the qswitch as an identifier

        Returns:
            Dict[str, str]: Dictionary of saved states
        """
        try:
            notebook_dir = os.getcwd()
            if unique:
                savedstates_path = os.path.join(notebook_dir, 'savedstates_{}.json'.format(self.IDN()["serial"]))
            else:
                savedstates_path = os.path.join(notebook_dir, 'savedstates.json')

            with open(savedstates_path, 'r') as f:
                savedstates = json.load(f)

            return savedstates

        except FileNotFoundError:
            raise ValueError("No saved states found.")
        except Exception as e:
            raise ValueError(f"Failed to load saved states: {e}")

    # -----------------------------------------------------------------------
    # Direct manipulation of the relays
    # -----------------------------------------------------------------------

    def close_relays(self, relays: State) -> None:
        currently = channel_list_to_state(self._state)
        union = list(itertools.chain(currently, relays))
        self._effectuate(union)

    def close_relay(self, line: int, tap: int) -> None:
        self.close_relays([(line, tap)])

    def open_relays(self, relays: State) -> None:
        currently = frozenset(channel_list_to_state(self._state))
        subtraction = frozenset(relays)
        self._effectuate(list(currently - subtraction))

    def open_relay(self, line: int, tap: int) -> None:
        self.open_relays([(line, tap)])

    # -----------------------------------------------------------------------
    # Manipulation by name
    # -----------------------------------------------------------------------

    OneOrMore = Union[str, Sequence[str]]

    def ground(self, lines: OneOrMore) -> None:
        connections: List[Tuple[int, int]] = []
        if isinstance(lines, str):
            line = self._to_line(lines)
            self.close_relay(line, 0)
            taps = range(1, relays_per_line + 1)
            connections = list(itertools.zip_longest([], taps, fillvalue=line))
            self.open_relays(connections)
        else:
            numbers = map(self._to_line, lines)
            grounds = list(itertools.zip_longest(numbers, [], fillvalue=0))
            self.close_relays(grounds)
            for tap in range(1, relays_per_line + 1):
                connections += itertools.zip_longest(
                                    map(self._to_line, lines), [], fillvalue=tap)
            self.open_relays(connections)

    def connect(self, lines: OneOrMore) -> None:
        if isinstance(lines, str):
            self.close_relay(self._to_line(lines), 9)
            self.open_relay(self._to_line(lines), 0)
        else:
            numbers = map(self._to_line, lines)
            pairs = list(itertools.zip_longest(numbers, [], fillvalue=9))
            self.close_relays(pairs)
            numbers = map(self._to_line, lines)
            connections = list(itertools.zip_longest(numbers, [], fillvalue=0))
            self.open_relays(connections)

    def breakout(self, line: str, tap: str) -> None:
        self.close_relay(self._to_line(line), self._to_tap(tap))
        self.open_relay(self._to_line(line), 0)


    def lineFloat(self, lines: OneOrMore) -> None:
        if isinstance(lines, str):
            for tap in range(relays_per_line+1):
                self.open_relay(self._to_line(lines), tap)
        else:
            for tap in range(relays_per_line+1):
                numbers = map(self._to_line, lines)
                pairs = list(itertools.zip_longest(numbers, [], fillvalue=tap))
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
    # Debugging and testing

    def start_recording_scpi(self) -> None:
        """Record all SCPI commands sent to the instrument

        Any previous recordings are removed.  To inspect the SCPI commands sent
        to the instrument, call get_recorded_scpi_commands().
        """
        self._scpi_sent: List[str] = list()
        self._record_commands = True

    def get_recorded_scpi_commands(self) -> List[str]:
        """
        Returns:
            Sequence[str]: SCPI commands sent to the instrument
        """
        commands = self._scpi_sent
        self._scpi_sent = list()
        return commands

    def clear_read_queue(self) -> Sequence[str]:
        """Flush the VISA message queue of the instrument

        Takes at least _message_flush_timeout_ms to carry out.

        Returns:
            Sequence[str]: Messages lingering in queue
        """
        lingering = list()
        original_timeout = self.visa_handle.timeout
        self.visa_handle.timeout = self._message_flush_timeout_ms
        while True:
            try:
                message = self.visa_handle.read()
            except VisaIOError:
                break
            else:
                lingering.append(message)
        self.visa_handle.timeout = original_timeout
        return lingering

    # -----------------------------------------------------------------------
    # Override communication methods to make it possible to check for errors
    # and to record the communication with the instrument.

    def write(self, cmd: str) -> None:
        """Send SCPI command to instrument

        Args:
            cmd (str): SCPI command
        """
        if self._udp_mode: # UDP (ethernet) commands
            cmd_lower = cmd.lower()
            is_open_close_cmd = cmd_lower.find("clos ",0,12) != -1 or (cmd_lower.find("close ",0,12) != -1) or (cmd_lower.find("open ",0,12)  != -1) 
            is_rst_cmd = (cmd_lower == "*rst")
            counter = 0
            while True: 
                self._write(cmd)
                # Check that relay command was well received
                if (is_open_close_cmd or is_rst_cmd): 
                    if is_open_close_cmd:
                        splitcmd = cmd.split(" ") # split command name and channel representation
                        reply = self.ask(splitcmd[0]+"? "+splitcmd[1] if len(splitcmd)==2 else "") # use the written command as a query to verify state 
                        if (len(reply) > 0) and (reply.find("0") == -1):  # verify that the relays have switched
                            return
                    elif is_rst_cmd:
                        reply = self.ask("clos:stat?")  
                        if (reply == "(@1!0:24!0)"):  # verify that the relays are in the default state
                            return
                    counter += 1
                    if (counter >= self._max_udp_writes):  # throw error when max attempts is reached
                        raise ValueError(f'QSwitch {self._udp_ip} (UDP): Command check failure [{cmd_lower}] after {self._max_udp_writes} attempts')
                else:
                    self.ask('*opc?')
                    return
        else:
            try:
                self._write(cmd)
                self.ask('*opc?')
                errors = self._switch.query('all?')
            except Exception as error:
                raise ValueError(f'Error: {repr(error)} after executing {cmd}')
            if errors == '0,"No error"':
                return
            raise ValueError(f'Error: {errors} after executing {cmd}')

    def ask(self, cmd: str) -> str:
        """Send SCPI query to instrument

        Args:
            cmd (str): SCPI query

        Returns:
            str: SCPI answer
        """
        if self._record_commands:
                self._scpi_sent.append(cmd)
        if self._udp_mode: # UDP (ethernet) queries
            counter = 0
            time_before_next = 0.1
            while True:
                try:
                    # Clear input buffer
                    self._sock.settimeout(0.0001)
                    while True:
                        try:
                            data,_ = self._sock.recvfrom(1024)
                        except:
                            break
                    self._sock.settimeout(2)
                    # Send command
                    self._sock.sendto(f"{cmd}\n".encode(), (self._udp_ip, 5025))
                    sleep_s(0.5)
                    # Wait for response
                    data, _ = self._sock.recvfrom(1024)
                    answer = data.decode().strip()
                    return answer
                except Exception:
                    counter += 1
                    if (counter >= self._max_udp_queries):
                        raise ValueError(f'QSwitch {self._udp_ip} (UDP): Query timeout [{cmd}] after {self._max_udp_queries} attempts')
                    sleep_s(time_before_next)
                    time_before_next += 0.5
        else:
            answer = self._switch.query(cmd)
            return answer

    # -----------------------------------------------------------------------

    def _write(self, cmd: str) -> None:
        if self._record_commands:
            self._scpi_sent.append(cmd)
        if self._udp_mode:
            try:
                self._sock.sendto(f"{cmd}\n".encode(), (self._udp_ip, 5025))
            except Exception as e:
                raise ValueError(f'QSwitch {self._udp_ip} (UDP): Write Error [{cmd}]: {repr(e)}')
        else:
            self._switch.write(cmd)

    def _channel_list_to_overview(self, channel_list: str) -> dict[str, List[str]]:
        state = channel_list_to_state(channel_list)
        line_names: dict[int, str] = dict()
        for name, line in self._line_names.items():
            line_names[line] = name
        tap_names: dict[int, str] = dict()
        for name, tap in self._tap_names.items():
            tap_names[tap] = name
        result: dict[str, List[str]] = dict()
        for line, _ in state:
            line_name = line_names[line]
            result[line_name] = list()
        for line, tap in state:
            line_name = line_names[line]
            if tap == 0:
                result[line_name].append('grounded')
            elif tap == 9:
                result[line_name].append('connected')
            else:
                tap_name = f'breakout {tap_names[tap]}'
                result[line_name].append(tap_name)
        return result

    def _to_line(self, name: str) -> int:
        try:
            return self._line_names[name]
        except KeyError:
            raise ValueError(f'Unknown line "{name}"')

    def _to_tap(self, name: str) -> int:
        try:
            return self._tap_names[name]
        except KeyError:
            raise ValueError(f'Unknown tap "{name}"')

    def _get_state(self) -> str:
        self.state_force_update()
        return self._state

    def _set_state_raw(self, channel_list: str) -> None:
        self._state = channel_list

    def _set_state(self, channel_list: str) -> None:
        self._effectuate(channel_list_to_state(channel_list))

    def _effectuate(self, state: State) -> None:
        currently = channel_list_to_state(self._state)
        positive, negative, total = _state_diff(currently, state)
        if positive:
            self.write(f'clos {state_to_compressed_list(positive)}')
        if negative:
            self.write(f'open {state_to_compressed_list(negative)}')
        self._set_state_raw(state_to_compressed_list(total))

    def _set_up_debug_settings(self) -> None:
        self._record_commands = False
        self._scpi_sent = list()
        self._message_flush_timeout_ms = 1
        self._round_off = None

    def _set_up_visa(self) -> None:
        # No harm in setting the speed even if the connection is not serial.
        self._switch.write_termination = '\n'
        self._switch.read_termination = '\n'
        self._switch.timeout = 5000
        self._switch.query_delay = 0.01
        self._switch.baud_rate = 9600

    def _check_for_wrong_model(self) -> None:
        model = self.IDN()['model']
        if model.lower() != 'qswitch':
            raise ValueError(f'Unknown model {model}. Are you using the right'
                             ' driver for your instrument?')

    def _check_for_incompatiable_firmware(self) -> None:
        firmware = self.IDN()['firmware']
        least_compatible_fw = '0.178'
        if parse(firmware) < parse(least_compatible_fw):
            raise ValueError(f'Incompatible firmware {firmware}. You need at '
                             f'least {least_compatible_fw}')

    def _set_up_simple_functions(self) -> None:
        self.add_function('abort', call_cmd='abor')

    def _set_default_names(self) -> None:
        lines = range(1, relay_lines+1)
        taps = range(1, relays_per_line)
        self._line_names = dict(zip(map(str, lines), lines))
        self._tap_names = dict(zip(map(str, taps), taps))

    def _add_monitor_pseudo_parameters(self) -> None:
        self.add_parameter(
            name='overview',
            source=self.state,
            get_parser=self._channel_list_to_overview,
            parameter_class=DelegateParameter,
            snapshot_value=False,
        )

    def _check_instrument_name(self, name: str) -> None:
        if name.isidentifier():
            return
        raise ValueError(
            f'Instrument name "{name}" is incompatible with QCoDeS parameter '
            'generation (no spaces, punctuation, prepended numbers, etc)')
