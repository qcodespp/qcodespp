import sys
import time
import threading
from collections import deque
import numpy as np

from datetime import datetime

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.cm import get_cmap

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QSpinBox, QDoubleSpinBox, QLabel,
                             QFileDialog)
from PyQt5.QtCore import QTimer

from qcodes import MultiParameter, Station
from qcodespp.data.data_set import new_data, set_data_folder, DataSetPP
from qcodespp.data.data_array import DataArray
from qcodespp.utils.helpers import convertExpToSI


class MonitorWindow(QMainWindow):
    def __init__(self, *params, interval=0.2, maxlen=500, start=True):
        """
        params:   list of QCoDeS parameters to monitor
        interval: update interval in s
        maxlen:   number of points to keep in the rolling window
        start:    if True, begin plotting immediately on open
        """
        super().__init__()
        self.params = list(params)
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
        self.toolbar = NavigationToolbar(self.canvas, self)
        

        self.canvas.mpl_connect('scroll_event', self._mouse_scroll_canvas)
        self.canvas.mpl_connect('button_press_event', self._mouse_click_canvas)
        self.canvas.mpl_connect('button_release_event', self._on_release)
        self.canvas.mpl_connect('motion_notify_event', self._on_motion)
        self.press=None
        # self.canvas.mpl_connect('pick_event', self.on_pick)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        colors= get_cmap('viridis')(np.linspace(0.1,0.9, len(self.param_dict.keys())))

        self.lines = {
            name: self.ax.plot([], [], '-o', markersize=3, label=f'{self.param_dict[name]["label"]} ({self.param_dict[name]["unit"]})', color=colors[i])[0]
            for i, name in enumerate(self.param_dict.keys())
        }
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Param value(s) (arb units)')
        self.ax.legend()

        bottom_layout = QVBoxLayout()
        input_layout = QHBoxLayout()
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

        input_layout.addWidget(QLabel('Interval (s):'))
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.001, 3600)
        self.spin_interval.setDecimals(3)
        self.spin_interval.setValue(self._interval)
        self.spin_interval.valueChanged.connect(self._on_interval_changed)
        input_layout.addWidget(self.spin_interval)

        input_layout.addWidget(QLabel('Max points:'))
        self.spin_maxlen = QSpinBox()
        self.spin_maxlen.setRange(10, 100000)
        self.spin_maxlen.setValue(self.maxlen)
        self.spin_maxlen.valueChanged.connect(self._on_maxlen_changed)
        input_layout.addWidget(self.spin_maxlen)

        input_layout.addStretch()
        self.btn_autoscale = QPushButton('Autoscale')
        self.btn_autoscale.clicked.connect(self._autoscale)
        input_layout.addWidget(self.btn_autoscale)

        layout.addLayout(bottom_layout)
        bottom_layout.addLayout(input_layout)
        bottom_layout.addLayout(ctrl_layout)

    def _on_interval_changed(self, value):
        self._interval = float(value)
        if self.timer.isActive():
            self.timer.start(int(value * 1000))

    def _on_maxlen_changed(self, value):
        self._update(maxlen=value)
        # self.times = deque(self.times, maxlen=value)
        # self.data = {name: deque(vals, maxlen=value) for name, vals in self.data.items()}

    def _start(self):
        self.t0 = time.time() - self.t0_cache
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.timer.start(int(self._interval * 1000))

    def _restart(self):
        self.t0 = time.time()
        self.t0_cache = 0
        if not self.timer.isActive():
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.timer.start(int(self._interval * 1000))

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
            line.set_label(
                f'{self.param_dict[name]["label"]} = {convertExpToSI(self.data[name][-1])}{self.param_dict[name]["unit"]}'
            )

        self.ax.relim()
        self.ax.autoscale_view()
        self.ax.legend()
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
    

    def _zoom_plot(self, event, axis='both'):
        scale=1.2
        axes = self.ax
        scale_factor = np.power(scale, -event.step)

        #convert pixels to axes
        tranP2A = axes.transAxes.inverted().transform
        xdata, ydata = tranP2A((event.x,event.y))
        #convert axes to data limits
        tranA2D= axes.transLimits.inverted().transform
        #convert the scale (for log plots)
        tranSclA2D = axes.transScale.inverted().transform
        #x,y position of the mouse in range (0,1)
        newxlims=[xdata - xdata*scale_factor, xdata + (1-xdata)*scale_factor]
        newylims=[ydata - ydata*scale_factor, ydata + (1-ydata)*scale_factor]
        new_xlim0,new_ylim0 = tranSclA2D(tranA2D((newxlims[0],newxlims[0])))
        new_xlim1,new_ylim1 = tranSclA2D(tranA2D((newylims[1],newylims[1])))

        if axis in ['x','both']:
            axes.set_xlim(new_xlim0, new_xlim1)
        if axis in ['y','both']:
            axes.set_ylim(new_ylim0, new_ylim1)

        self.canvas.draw()
    
    def _mouse_scroll_canvas(self, event):
        axes=self.ax
        if (axes.xaxis.contains(event)[0] and
            event.y < axes.get_window_extent().y1):
            self._zoom_plot(event,axis = 'x')
        elif (axes.yaxis.contains(event)[0] and
                event.x < axes.get_window_extent().x1):
            self._zoom_plot(event, axis = 'y')
        elif event.inaxes == axes:
            self._zoom_plot(event)

    def _mouse_click_canvas(self, event):
        if event.inaxes:
            axis='both'
        elif (self.ax.xaxis.contains(event)[0] and
            event.y < self.ax.get_window_extent().y1):
            axis = 'x'
        elif (self.ax.yaxis.contains(event)[0] and
            event.x < self.ax.get_window_extent().x1):
            axis = 'y'
        else:
            return
        width, height = self.canvas.get_width_height()
        bbox=self.ax.get_position().get_points()
        x0, x1 = bbox[0][0]*width, bbox[1][0]*width
        y0, y1 = bbox[0][1]*height, bbox[1][1]*height
        pixels_per_unit=[None,None]
        bounds=[None,None]
        if axis in ['x','both']:
            bounds[0] = self.ax.get_xbound()
            pixels_per_unit[0] = (x1 - x0) / (bounds[0][1] - bounds[0][0])
        if axis in ['y','both']:
            bounds[1] = self.ax.get_ybound()
            pixels_per_unit[1] = (y1 - y0) / (bounds[1][1] - bounds[1][0])
        self.press = [axis,[event.x,event.y],pixels_per_unit,bounds[0],bounds[1]]

    def _on_motion(self, event):
        if hasattr(self,'press') and self.press is not None:
            axpress = self.press[1]
            pixels_per_unit = self.press[2]
            xbound = self.press[3]
            ybound = self.press[4]
            if self.press[0] in ['x','both']:
                dx = (event.x - axpress[0]) / pixels_per_unit[0]
                self.ax.set_xlim(xbound[0] - dx, xbound[1] - dx)
            if self.press[0] in ['y','both']:
                dy = (event.y - axpress[1]) / pixels_per_unit[1]
                self.ax.set_ylim(ybound[0] - dy, ybound[1] - dy)

            self.canvas.draw()


    def _on_release(self, event):
        self.press = None
        self.canvas.draw()

    def _autoscale(self):
        self.ax.autoscale()
        self.canvas.draw()