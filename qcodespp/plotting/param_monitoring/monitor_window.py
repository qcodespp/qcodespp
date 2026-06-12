import time
from collections import deque
from io import BytesIO
import numpy as np

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.cm import get_cmap

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QSpinBox, QDoubleSpinBox, QLabel,
                             QFileDialog, QTextEdit)
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QTimer

from qcodespp import Parameter, MultiParameter, Station, Measure
from qcodespp.data.data_set import set_data_folder, DataSetPP
from qcodespp.utils.helpers import convertExpToSI, pyplotconvertExpToSI


class MonitorWindow(QMainWindow):
    def __init__(self, *params, interval=0.2, maxlen=500, start=True, ylabel=None, yunit=None, station=None):
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
        self.ylabel = ylabel
        self.yunit = yunit
        self.times = [] #deque(maxlen=maxlen)
        self.param_dict = self._make_param_dict()
        self.data = {key: [] for key in self.param_dict.keys()} #{param.name: deque(maxlen=maxlen) for param in params}

        self.station = station
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

        self.copy_btn = QPushButton('Copy plot')
        self.copy_btn.clicked.connect(self._copy_canvas)
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(self.toolbar)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.copy_btn)

        layout.addLayout(toolbar_layout)
        layout.addWidget(self.canvas)

        colors= get_cmap('viridis')(np.linspace(0.1,0.9, len(self.param_dict.keys())))

        self.lines = {
            name: self.ax.plot([], [], '-o', markersize=3, label=f'{self.param_dict[name]["label"]} ({self.param_dict[name]["unit"]})', color=colors[i])[0]
            for i, name in enumerate(self.param_dict.keys())
        }
        self.ax.set_xlabel('Time (s)')
        if self.ylabel is not None:
            if self.yunit is not None:
                self.ax.set_ylabel(f'{self.ylabel} ({self.yunit})')
            else:
                self.ax.set_ylabel(self.ylabel)
        else:
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
        self.btn_save_stats = QPushButton('Save stats')
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)
        self.btn_restart.clicked.connect(self._restart)
        self.btn_clear.clicked.connect(self._clear)
        self.btn_save.clicked.connect(lambda: self._save_data(None))
        self.btn_save_stats.clicked.connect(self._save_stats_csv)
        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_restart)
        ctrl_layout.addWidget(self.btn_clear)
        ctrl_layout.addWidget(self.btn_save)
        ctrl_layout.addWidget(self.btn_save_stats)

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

        self.stats_label = QTextEdit('Right click and drag on the plot to show the average value of parameters in that region.')
        self.stats_label.setReadOnly(True)
        self.stats_label.setFixedHeight(int(self.stats_label.fontMetrics().height() * 
                                            (len(self.param_dict.keys())+1)))
        
        layout.addWidget(self.stats_label)
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
        if hasattr(self, '_average_band') and self._average_band is not None:
            self._average_band.remove()
            self._average_band = None

        self.stats_label.setText('Right click and drag on the plot to show the average value of parameters in that region.')
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def _stop(self):
        self.timer.stop()
        self.t0_cache=time.time()-self.t0
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _update(self,maxlen=None):
        try:
            for key, val in self._measure().items():
                self.data[key].append(val)
        except Exception as e:
            return
        
        if maxlen is not None:
            self.maxlen = maxlen
        self.times.append(time.time() - self.t0)

        if self.yunit is not None:
            maxs=[np.max(self.data[name]) for name in self.data]
            mins=[np.min(self.data[name]) for name in self.data]

            prefix,factor= pyplotconvertExpToSI([np.min(mins), np.max(maxs)])

            self.ax.set_ylabel(f'{self.ylabel} ({prefix}{self.yunit})')
        else:
            factor=1

        t = deque(self.times, maxlen=self.maxlen)
        for name, line in self.lines.items():
            line.set_data(t, deque(np.array(self.data[name])/factor, maxlen=self.maxlen))
            line.set_label(
                f'{self.param_dict[name]["label"]} = {convertExpToSI(self.data[name][-1])}{self.param_dict[name]["unit"]}'
            )

        self.ax.relim()
        self.ax.autoscale_view()
        self.ax.legend()
        self.canvas.draw()

    def _save_data(self, station):
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            'Save monitor data',
            '',
            'All Files (*)'
        )
        if not filepath:
            return

        try:

            old_provider = DataSetPP.location_provider or None
            old_default = DataSetPP.default_folder or None
            filename=filepath.split('/')[-1].split('.')[0]
            set_data_folder('/'.join(filepath.split('/')[:-1]))
            station = station or self.station or Station.default or None
            try:
                time_param = TimeCache(name="elapsed_time", window=self, label="Time", unit="s")
                data_param = ParamCache(name="data_param", window=self)
                measure = Measure(data_param, setpoints=[time_param],station=station)
                data_set=measure.run(name=filename,station=station,quiet=True)
                self.fig.savefig(data_set.location+".png", transparent=True,
                                    bbox_inches='tight')
            except Exception as exc:
                #QMessageBox.critical(self, "Save Error", f"Could not create qcodes++ file:\n{exc}")
                print(f"Error creating qcodes++ file: {exc.__class__.__name__}: {exc}")
            # Restore the old location provider and default folder if they existed.
            if old_provider is not None:
                DataSetPP.location_provider = old_provider
            if old_default is not None:
                DataSetPP.default_folder = old_default

        except Exception as e:
            print(f'Error while saving data: {e.__class__.__name__}: {e}')

    def _copy_canvas(self):
        buf = BytesIO()
        self.fig.savefig(buf, dpi=600, bbox_inches='tight')
        QApplication.clipboard().setImage(QImage.fromData(buf.getvalue()))
        buf.close()

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
        if event.button == 1: # left click: move stuff around
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
        if event.button == 3 and event.inaxes: # right click
            self.press = [event.xdata]

    def _on_motion(self, event):
        if hasattr(self,'press') and self.press is not None:
            if event.button == 1:
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
            if event.button == 3:
                limits=[self.press[0], event.xdata]
                if not any(l is None for l in limits):
                    self._show_averages(limits)

    def _on_release(self, event):
        if event.button == 3 and self.press is not None:
            limits=[self.press[0], event.xdata]
            if not any(l is None for l in limits):
                self._show_averages(limits)
        self.press = None
        self.canvas.draw()

    def _autoscale(self):
        self.ax.autoscale()
        self.canvas.draw()

    def _show_averages(self, limits):
        x0, x1 = min(limits), max(limits)
        mask = ((np.array(self.times) >= x0) & (np.array(self.times) <= x1))
        if not np.any(mask):
            return
        self.stats = {name: {'avg':np.mean(np.array(vals)[mask]),
                              'std':np.std(np.array(vals)[mask])}
                      for name, vals in self.data.items()}

        if hasattr(self, '_average_band') and self._average_band is not None:
            self._average_band.remove()
            self._average_band = None
        self._average_band = self.ax.axvspan(x0, x1, ymin=0, ymax=1, color='C0', alpha=0.2)
        self.canvas.draw()

        parts = []
        for name, s in self.stats.items():
            label = self.param_dict[name]['label']
            unit = self.param_dict[name]['unit']
            parts.append(f'{label}: avg = {convertExpToSI(s["avg"])}{unit},  std = {convertExpToSI(s["std"])}{unit}')
        self.stats_label.setText('\n'.join(parts))

    def _save_stats_csv(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            'Save stats data',
            '',
            'CSV Files (*.csv);;All Files (*)'
        )
        if not filepath:
            return
        try:
            with open(filepath, 'w') as f:
                f.write('Parameter,Average,Std Dev\n')
                for name, s in self.stats.items():
                    label = self.param_dict[name]['label']
                    unit = self.param_dict[name]['unit']
                    f.write(f'{label} ({unit}),{s["avg"]},{s["std"]}\n')
        except Exception as e:
            print(f'Error while saving stats data: {e.__class__.__name__}: {e}')
    
    def closeEvent(self, event):
        self._stop()
        event.accept()


class ParamCache(MultiParameter):
    '''MultiParameter to transfer the last mesaured data into a qcpp Measure'''
    def __init__(self, name, window, **kwargs):
        self.window=window
        self.names = list(self.window.param_dict.keys())
        self.labels = [self.window.param_dict[name]['label'] for name in self.names]
        self.units = [self.window.param_dict[name]['unit'] for name in self.names]
        self.shapes=tuple([() for _ in self.names])
        self.unit=''
        kwargs={
            'names': self.names,
            'labels': self.labels,
            'units': self.units,
            'shapes': self.shapes,
            **kwargs
        }
        super().__init__(name, **kwargs)

    def get_raw(self):
        return [self.window.data[name] for name in self.names]
    
class TimeCache(Parameter):
    '''Parameter to transfer the last measured times into a qcpp Measure'''
    def __init__(self, name, window, **kwargs):
        self.window=window
        super().__init__(name, **kwargs)

    def get_raw(self):
        return self.window.times