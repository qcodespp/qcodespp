from qcodes import Instrument
import pandas as pd
import numpy as np

from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
import requests


class BlueFors(Instrument):
    """
    This is a QCoDeS python driver to extract the temperature and pressure,
    as well as control these parameters through the REST API provided by a BlueFors
    fridge. Adapted from https://gitlab.com/squad-lab/bfutils to avoid needing 
    to specify a folder path for the log files.

    TODO: This was done in a rush. A better implemetation would be to make the 
    log file reading optional, instead of avoiding it completely.
    """

    def __init__(
        self,
        name: str,
        bftc_ip: str,
        bftc_port: int,
        fse_ip: str,
        fse_port: int,
        bftc_channels: dict = {1: "50k", 2: "4k", 3: "magnet", 5: "still", 6: "mxc"},
        heater_channels: dict = {3: "still", 4: "mxc"},
        fse_heater_channels: dict = {4: "fse"},
        timeout: float = 10.0,
        controller_timeout: float = 10.0,
        **kwargs,
    ) -> None:
        """
        ✨Better✨ QCoDeS driver for BlueFors fridges.

        Args:
        name (str): Name of the instrument.
        folder_path (str): Location of the BlueFors fridge log files.
        bftc_ip (str): IP address of the BlueFors temperature controller.
        bftc_port (int): Port of the BlueFors temperature controller.
        fse_ip (str): IP address of the BlueFors flow controller.
        fse_port (int): Port of the BlueFors FSE temperature controller.
        bftc_channels (dict): Dictionary of the BlueFors temperature controller channels.
            Example: {1: "50k", 2: "4k", 3: "magnet", 5: "still", 6: "mxc"}
        heater_channels (dict): Dictionary of the BlueFors heater channels.
            Example: {3: "still", 4: "mxc"}
        fse_heater_channels (dict): Dictionary of the BlueFors FSE heater channels.
            Example: {4: "fse"}
        timeout: Timeout for the HTTP requests.
        controller_timeout: Timeout for the controller requests.
        """
        super().__init__(name=name, **kwargs)

        date = datetime.today().strftime("%y-%m-%d")

        self.bftc_ip = bftc_ip
        self.fse_ip = fse_ip
        self.bftc_port = bftc_port
        self.fse_port = fse_port
        self.bftc_channels = bftc_channels
        self.heater_channels = heater_channels
        self.timeout = timeout
        self.controller_timeout = controller_timeout

        for (
            temperature_sensor_nr,
            temperature_sensor_name,
        ) in self.bftc_channels.items():
            setter = None
            if temperature_sensor_name in self.heater_channels.values():
                heater_nr = list(self.heater_channels.keys())[
                    list(self.heater_channels.values()).index(temperature_sensor_name)
                ]
                setter = partial(
                    self.set_temperature, self.bftc_ip, self.bftc_port, heater_nr
                )

            self.add_parameter(
                name=f"t_{temperature_sensor_name}",
                unit="K",
                get_parser=float,
                get_cmd=partial(
                    self.get_temperature,
                    self.bftc_ip,
                    self.bftc_port,
                    temperature_sensor_nr,
                ),
                set_cmd=setter,
                docstring=f"Temperature at {temperature_sensor_name} stage",
            )

        self.add_parameter(
            name="temperature",
            unit="K",
            get_parser=dict,
            get_cmd=self.get_temperatures_bftc,
            docstring="Temperature dictionary for all channels",
        )

        self.add_parameter(
            name="t_fse",
            unit="K",
            get_parser=float,
            set_cmd=partial(self.set_temperature, self.fse_ip, self.fse_port, 4),
            get_cmd=partial(self.get_temperature, self.fse_ip, self.fse_port, 1),
            docstring="Temperature inside the FSE",
        )

        for heater_nr, heater_name in heater_channels.items():
            self.add_parameter(
                name=f"h_{heater_name}",
                get_cmd=partial(
                    self.get_heater, self.bftc_ip, self.bftc_port, heater_nr
                ),
                set_cmd=partial(
                    self.set_heater, self.bftc_ip, self.bftc_port, heater_nr
                ),
                docstring=f"Control for the {heater_name} heater",
            )

            self.add_parameter(
                name=f"pid_{heater_name}",
                get_cmd=partial(self.get_pid, self.bftc_ip, self.bftc_port, heater_nr),
                set_cmd=partial(self.set_pid, self.bftc_ip, self.bftc_port, heater_nr),
                docstring=f"Control for the PID of the {heater_name} heater",
            )

        for heater_nr, heater_name in fse_heater_channels.items():
            self.add_parameter(
                name=f"h_{heater_name}",
                get_cmd=partial(self.get_heater, self.fse_ip, self.fse_port, heater_nr),
                set_cmd=partial(self.set_heater, self.fse_ip, self.fse_port, heater_nr),
                docstring=f"Control for the {heater_name} heater",
            )

            self.add_parameter(
                name=f"pid_{heater_name}",
                get_cmd=partial(self.get_pid, self.fse_ip, self.fse_port, heater_nr),
                set_cmd=partial(self.set_pid, self.fse_ip, self.fse_port, heater_nr),
                docstring=f"Control for the PID of the {heater_name} heater",
            )

    def get_historical_temperature(
        self,
        ip: str,
        port: int,
        channel_nr: int,
        minutes,
    ) -> float:
        """Reads the current temperature from the fridge.

        Args:
            ip (str): IP address of the channel.
            port (int): Port number of the channel.
            channel_nr (int): Channel index number from which the temperature is extracted.
            minutes (float): Duration in minutes over which the temperatures are returned.

        Returns:
            dict: Dictionary of temperatures in Kelvin.
        """
        data = {
            "channel_nr": channel_nr,
            "start_time": (datetime.now() - timedelta(minutes=minutes)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "stop_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fields": ["temperature"],
        }
        try:
            req = requests.post(
                f"http://{ip}:{port}/channel/historical-data",
                json=data,
                timeout=self.timeout,
            ).json()
            latest_time = req["measurements"]["timestamp"][-1]
            time_diff = datetime.now() - datetime.fromtimestamp(latest_time)
            if time_diff.total_seconds() / 60 > self.controller_timeout:
                raise TimeoutError(
                    f"Temperature controller offline since more than {self.controller_timeout} minutes"
                )

            return req["measurements"]["temperature"]

        except IndexError:
            raise IndexError("Cannot find temperature data for the channel")

    def get_temperature(self, ip: str, port: str, channel_nr: int) -> float:
        temp = self.get_historical_temperature(ip, port, channel_nr, minutes=150)[-1]
        if temp != None:
            return temp
        return np.nan

    def set_temperature(
        self, ip: str, port: str, heater_nr: int, temperature: float
    ) -> None:
        data = {
            "heater_nr": heater_nr,
            "active": True,
            "pid_mode": 1,
            "control_algorithm": 1,
            "setpoint": temperature,
        }

        requests.post(
            f"http://{ip}:{port}/heater/update",
            json=data,
            timeout=self.timeout,
        )

    def get_temperatures_bftc(self) -> float:
        temperature_dict = {}
        for key in self.bftc_channels:
            temperature_dict[key] = self.get_temperature(
                ip=self.bftc_ip, port=self.bftc_port, channel_nr=key
            )
        return temperature_dict

    def get_heater(self, ip: str, port: str, heater_nr: int):
        data = {
            "heater_nr": heater_nr,
        }
        req = requests.post(
            f"http://{ip}:{port}/heater",
            json=data,
            timeout=self.timeout,
        ).json()

        return {
            "active": req["active"],
            "mode": ["manual", "pid"][req["pid_mode"]],
            "power": req["power"],
            "setpoint": req["setpoint"],
        }

    def set_heater(
        self, ip: str, port: int, heater_nr: int, power: float = 0.0
    ) -> None:
        data = {
            "heater_nr": heater_nr,
        }

        req = requests.post(
            f"http://{ip}:{port}/heater",
            json=data,
            timeout=self.timeout,
        )

        if req.json()["max_power"] < power:
            raise ValueError("Power exceeds maximum power")

        if not power:
            data["active"] = False

        else:
            data_add = {
                "active": True,
                "pid_mode": 0,
                "power": power,
            }
            data.update(data_add)

        requests.post(
            f"http://{ip}:{port}/heater/update",
            json=data,
            timeout=self.timeout,
        )

    def get_pid(self, ip: str, port: int, heater_nr: int):
        data = {
            "heater_nr": heater_nr,
        }

        req = requests.post(
            f"http://{ip}:{port}/heater",
            json=data,
            timeout=self.timeout,
        ).json()

        return {
            "p": req["control_algorithm_settings"]["proportional"],
            "i": req["control_algorithm_settings"]["integral"],
            "d": req["control_algorithm_settings"]["derivative"],
        }

    def set_pid(self, ip: str, port: int, heater_nr: int, pid: tuple) -> None:
        p, i, d = pid
        data = {
            "heater_nr": heater_nr,
            "pid_mode": 1,
            "control_algorithm": 1,
            "control_algorithm_settings": {
                "proportional": p,
                "integral": i,
                "derivative": d,
            },
        }

        requests.post(
            f"http://{ip}:{port}/heater/update",
            json=data,
            timeout=self.timeout,
        )