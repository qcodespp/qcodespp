import sys
import time
import threading
from collections import deque
import numpy as np

from datetime import datetime

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.cm import get_cmap

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QSpinBox, QDoubleSpinBox, QLabel,
                             QFileDialog)
from PyQt5.QtCore import QTimer

from qcodes import MultiParameter, Station
from qcodespp.data.data_set import new_data, set_data_folder, DataSetPP
from qcodespp.data.data_array import DataArray


class MonitorWindow(QMainWindow):
    def __init__(self, params, interval=200, maxlen=500, start=True):
        """
        params:   list of QCoDeS parameters to monitor
        interval: update interval in ms
        maxlen:   number of points to keep in the rolling window
        start:    if True, begin plotting immediately on open
        """
        super().__init__()
        self.params = params
        self._interval = interval
        self.t0 = time.time()
        self.t0_cache=0
        self.maxlen = maxlen
        self.times = [] #deque(maxlen=maxlen)
        self.param_dict = self._make_param_dict()
        self.data = {key: [] for key in self.param_dict.keys()} #{param.name: deque(maxlen=maxlen) for param in params}

        self._build_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self._update)
        if start:
            self._start()

    def _make_param_dict(self):
        out_dict = {}
        self.getters = [param.get for param in self.params]
        for param in self.params:
            if isinstance(param, MultiParameter):
                for i, name in enumerate(param.names):
                    if param.labels is not None:
                        label = param.labels[i]
                    else:
                        label = name
                    out_dict[f'{param.full_name}_{name}'] = {'unit':param.units[i],
                                    'label':label}
            else:
                out_dict[param.full_name] = {'unit':param.unit,
                                    'label':param.label}

        return out_dict

    def _measure(self):
        # TODO: At the moment there is none of the optimisations that (allegedly) exist in Loop,
        # such as trying to group gettable parameters that have the same source.
        out_dict = {}

        out = [g() for g in self.getters]

        for param_out, param in zip(out, self.params):
            if isinstance(param, MultiParameter):
                for i, name in enumerate(param.names):
                    if param.labels is not None:
                        label = param.labels[i]
                    else:
                        label = name
                    out_dict[f'{param.full_name}_{name}'] = param_out[i]
            else:
                out_dict[param.full_name] = param_out

        return out_dict

    def _build_ui(self):
        self.setWindowTitle('Parameter Monitor')
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.fig = Figure(tight_layout=True)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

        colors= get_cmap('viridis')(np.linspace(0.1,0.9, len(self.param_dict.keys())))

        self.lines = {
            name: self.ax.plot([], [], '-o', markersize=3, label=f'{self.param_dict[name]["label"]} ({self.param_dict[name]["unit"]})', color=colors[i])[0]
            for i, name in enumerate(self.param_dict.keys())
        }
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Param value(s) (arb units)')
        self.ax.set_title('Real-time Parameter Monitor')
        self.ax.legend()

        ctrl_layout = QHBoxLayout()

        self.btn_start = QPushButton('Start')
        self.btn_stop = QPushButton('Stop')
        self.btn_restart = QPushButton('Restart')
        self.btn_clear = QPushButton('Clear')
        self.btn_save = QPushButton('Save data')
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)
        self.btn_restart.clicked.connect(self._restart)
        self.btn_clear.clicked.connect(self._clear)
        self.btn_save.clicked.connect(lambda: self._save_data(None))
        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_restart)
        ctrl_layout.addWidget(self.btn_clear)
        ctrl_layout.addWidget(self.btn_save)

        ctrl_layout.addStretch()

        ctrl_layout.addWidget(QLabel('Interval (s):'))
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.001, 3600)
        self.spin_interval.setDecimals(1)
        self.spin_interval.setValue(self._interval / 1000)
        self.spin_interval.valueChanged.connect(self._on_interval_changed)
        ctrl_layout.addWidget(self.spin_interval)

        ctrl_layout.addWidget(QLabel('Max points:'))
        self.spin_maxlen = QSpinBox()
        self.spin_maxlen.setRange(10, 100000)
        self.spin_maxlen.setValue(self.maxlen)
        self.spin_maxlen.valueChanged.connect(self._on_maxlen_changed)
        ctrl_layout.addWidget(self.spin_maxlen)

        layout.addLayout(ctrl_layout)

    def _on_interval_changed(self, value):
        self._interval = int(value * 1000)
        if self.timer.isActive():
            self.timer.start(self._interval)

    def _on_maxlen_changed(self, value):
        self._update(maxlen=value)
        # self.times = deque(self.times, maxlen=value)
        # self.data = {name: deque(vals, maxlen=value) for name, vals in self.data.items()}

    def _start(self):
        self.t0 = time.time() - self.t0_cache
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.timer.start(self._interval)

    def _restart(self):
        self.t0 = time.time()
        self.t0_cache = 0
        if not self.timer.isActive():
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.timer.start(self._interval)

    def _clear(self):
        self.t0 = time.time()
        self.t0_cache = 0
        self.times = []#deque(maxlen=maxlen)
        self.data = {key: [] for key in self.param_dict.keys()} #{name: deque(maxlen=maxlen) for name in self.data}
        for line in self.lines.values():
            line.set_data([], [])
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def _stop(self):
        self.timer.stop()
        self.t0_cache=time.time()-self.t0
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _update(self,maxlen=None):
        if maxlen is not None:
            self.maxlen = maxlen
        self.times.append(time.time() - self.t0)

        for key, val in self._measure().items():
            self.data[key].append(val)

        t = deque(self.times, maxlen=self.maxlen)
        for name, line in self.lines.items():
            line.set_data(t, deque(self.data[name], maxlen=self.maxlen))

        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def _save_data(self, station):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            'Save monitor data',
            '',
            'All Files (*)'
        )
        if not file_path:
            return

        station = station or Station.default or None

        data_set = self._make_data_set(location=file_path)

        if station is not None:
            data_set.add_metadata({'station': station.snapshot()})

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_set.add_metadata({'measurement': {
            'ts': ts,
        }})

        data_set.save_metadata()

        data_set.finalize()

    def _make_data_set(self,location,**kwargs):
        """
        Construct the DataSetPP for this measurement.
        """
        old_provider = DataSetPP.location_provider or None
        old_default = DataSetPP.default_folder or None

        name=location.split('/')[-1].split('.')[0]

        data_folder=location.split(name)[0].strip('/')

        set_data_folder(data_folder)

        data_set=new_data(name=name,**kwargs)
        time_array = DataArray(label = 'Time',
                        unit = 's',
                        array_id = 'time',
                        name = 'time',
                        is_setpoint = True,
                        preset_data = self.times)
        time_array.init_data()
        data_set.add_array(time_array)
        for name,value in self.data.items():
            # Make and add the array to the dataset.
            data_array = DataArray(name = name,
                                label = self.param_dict[name]['label'],
                                unit = self.param_dict[name]['unit'],
                                preset_data = value,
                                is_setpoint = False,
                                set_arrays = (time_array,))
            data_array.init_data()
            data_set.add_array(data_array)

        # Restore the old location provider and default folder if they existed.
        if old_provider is not None:
            DataSetPP.location_provider = old_provider
        if old_default is not None:
            DataSetPP.default_folder = old_default

        return data_set
