from PyQt5 import QtWidgets, QtCore, QtGui
import io
from json import load as jsonload
from json import dump as jsondump
from csv import writer as csvwriter
import qcodesplusplus.plotting.offline.fits as fits
from scipy.ndimage import map_coordinates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.colors import Normalize, LogNorm, ListedColormap
from matplotlib import cm
from matplotlib.widgets import Cursor
from matplotlib import rcParams
from matplotlib.lines import Line2D
import matplotlib.patches as patches
import numpy as np
try: # lmfit is used for fitting the evolution of the properties of multiple peaks 
    from lmfit.models import LorentzianModel, GaussianModel, ConstantModel
    from lmfit.model import save_modelresult
    lmfit_imported = True
except ModuleNotFoundError:
    lmfit_imported = False

try: # used for single peak fitting
    from scipy.signal import find_peaks
    find_peaks_imported = True
except ModuleNotFoundError:
    find_peaks_imported = False

try:
    import qdarkstyle # pip install qdarkstyle
    qdarkstyle_imported = True
except ModuleNotFoundError:
    qdarkstyle_imported = False

DARK_THEME = True

from .helpers import rcParams_to_dark_theme, rcParams_to_light_theme, cmaps

class LineCutWindow(QtWidgets.QWidget):
    def __init__(self, parent, orientation):
        super().__init__()
        self.parent = parent
        self.running = True
        self.orientation = orientation
        self.init_widgets()
        self.init_canvas()
        self.init_connections()
        self.init_layouts()
        self.set_main_layout()
        self.fit_type_changed()
        
    def init_widgets(self):
        self.setWindowTitle('Inspectra Gadget - Linecut and Fitting Window')
        self.resize(800, 800)
        self.save_button = QtWidgets.QPushButton('Save Data')
        self.save_image_button = QtWidgets.QPushButton('Save Image')
        self.copy_image_button = QtWidgets.QPushButton('Copy Image')
        self.clear_button = QtWidgets.QPushButton('Clear')
        self.fit_button = QtWidgets.QPushButton('Fit')
        self.save_preset_button = QtWidgets.QPushButton('Save preset')
        self.load_preset_button = QtWidgets.QPushButton('Load preset')
        self.save_result_button = QtWidgets.QPushButton('Save fit result')
        self.fit_functions_label = QtWidgets.QLabel('Select fit function:')
        self.input_label = QtWidgets.QLabel('Input info:')
        self.input_edit = QtWidgets.QLineEdit()
        self.guess_checkbox = QtWidgets.QCheckBox('Initial guess:')
        self.guess_edit = QtWidgets.QLineEdit()
        self.fit_class_box = QtWidgets.QComboBox()
        self.fit_class_box.addItems(fits.get_class_names())
        self.fit_class_box.setCurrentIndex(0)
        self.fit_class_box.SizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.fit_box = QtWidgets.QComboBox()
        self.fit_box.addItems(fits.get_names(fitclass=self.fit_class_box.currentText()))
        self.fit_box.setCurrentIndex(0)
        self.fit_box.SizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.output_window = QtWidgets.QTextEdit()
        self.output_window.setReadOnly(True)
        #self.output_window.setMaximumHeight(250)
        self.lims_label = QtWidgets.QLabel('Fit limits (left-click plot):')
        self.xmin_label = QtWidgets.QLabel('Xmin:')
        self.xmin_label.setStyleSheet("QLabel { color : blue; }")
        self.xmax_label = QtWidgets.QLabel('Xmax:')
        self.xmax_label.setStyleSheet("QLabel { color : red; }")
        self.xmin_box = QtWidgets.QLineEdit()
        self.xmax_box = QtWidgets.QLineEdit()
        self.reset_axes_button = QtWidgets.QPushButton('Reset')
        if self.orientation in ['horizontal','vertical']:
            self.orientation_button = QtWidgets.QPushButton('Hor./Vert.')
            self.up_button = QtWidgets.QPushButton('Up/Right')
            self.down_button = QtWidgets.QPushButton('Down/Left')

    def init_connections(self):
        self.save_button.clicked.connect(self.save_data)
        self.save_image_button.clicked.connect(self.save_image)
        self.copy_image_button.clicked.connect(self.copy_image)
        self.clear_button.clicked.connect(self.clear_lines)
        self.fit_class_box.currentIndexChanged.connect(self.fit_class_changed)
        self.fit_box.currentIndexChanged.connect(self.fit_type_changed)
        self.fit_button.clicked.connect(self.start_fitting)
        self.save_result_button.clicked.connect(self.save_fit_result)
        self.save_preset_button.clicked.connect(self.save_fit_preset)
        self.load_preset_button.clicked.connect(self.load_fit_preset)
        self.xmin_box.editingFinished.connect(self.limits_edited)
        self.xmax_box.editingFinished.connect(self.limits_edited)
        self.reset_axes_button.clicked.connect(self.reset_limits)
        if self.orientation in ['horizontal','vertical']:
            self.orientation_button.clicked.connect(self.change_orientation)
            self.up_button.clicked.connect(lambda: self.change_index('up'))
            self.down_button.clicked.connect(lambda: self.change_index('down'))
        
    def init_canvas(self):
        self.figure = Figure(tight_layout={'pad':2})
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        self.scroll_event_id = self.canvas.mpl_connect('scroll_event', 
                                                       self.mouse_scroll_canvas)
        self.canvas.mpl_connect('button_press_event', self.mouse_click_canvas)
        self.navi_toolbar = NavigationToolbar(self.canvas, self)
    
    def init_layouts(self):
        self.top_buttons_layout = QtWidgets.QHBoxLayout()
        self.lims_layout = QtWidgets.QHBoxLayout()
        self.fit_layout = QtWidgets.QHBoxLayout()
        self.inputs_layout = QtWidgets.QHBoxLayout()
        self.guess_layout = QtWidgets.QHBoxLayout()
        self.output_layout = QtWidgets.QVBoxLayout()
        self.fit_buttons_layout = QtWidgets.QHBoxLayout()

        self.top_buttons_layout.addWidget(self.save_button)
        self.top_buttons_layout.addWidget(self.save_image_button)
        self.top_buttons_layout.addWidget(self.copy_image_button)
        self.top_buttons_layout.addStretch()
        if self.orientation in ['horizontal','vertical']:
            self.top_buttons_layout.addWidget(self.orientation_button)
            self.top_buttons_layout.addWidget(self.down_button)
            self.top_buttons_layout.addWidget(self.up_button)

        self.lims_layout.addWidget(self.lims_label)
        self.lims_layout.addWidget(self.xmin_label)
        self.lims_layout.addWidget(self.xmin_box)
        self.lims_layout.addWidget(self.xmax_label)
        self.lims_layout.addWidget(self.xmax_box)
        self.lims_layout.addWidget(self.reset_axes_button)
        self.lims_layout.addStretch()

        self.fit_layout.addWidget(self.fit_functions_label)
        self.fit_layout.addWidget(self.fit_class_box)
        self.fit_layout.addWidget(self.fit_box)
        self.fit_layout.addStretch()

        self.inputs_layout.addWidget(self.input_label)
        self.inputs_layout.addWidget(self.input_edit)
        #self.inputs_layout.addStretch()

        self.guess_layout.addWidget(self.guess_checkbox)
        self.guess_layout.addWidget(self.guess_edit)
        #self.guess_layout.addStretch()

        self.output_layout.addWidget(self.output_window)

        self.fit_buttons_layout.addWidget(self.fit_button)
        self.fit_buttons_layout.addWidget(self.save_result_button)
        self.fit_buttons_layout.addWidget(self.clear_button)
        self.fit_buttons_layout.addStretch()
        self.fit_buttons_layout.addWidget(self.save_preset_button)
        self.fit_buttons_layout.addWidget(self.load_preset_button)

    def set_main_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout()
        self.plotbox=QtWidgets.QGroupBox('')
        self.plottinglayout = QtWidgets.QVBoxLayout()
        self.plottinglayout.addLayout(self.top_buttons_layout)
        self.plottinglayout.addWidget(self.navi_toolbar)
        self.plottinglayout.addWidget(self.canvas)
        self.plotbox.setLayout(self.plottinglayout)

        self.fittingbox=QtWidgets.QGroupBox('Curve Fitting')
        self.fittingbox.setMaximumHeight(450)
        self.fittinglayout = QtWidgets.QVBoxLayout()
        self.fittinglayout.addLayout(self.lims_layout)
        self.fittinglayout.addLayout(self.fit_layout)
        self.fittinglayout.addLayout(self.inputs_layout)
        self.fittinglayout.addLayout(self.guess_layout)
        self.fittinglayout.addLayout(self.output_layout)
        self.fittinglayout.addLayout(self.fit_buttons_layout)
        self.fittingbox.setLayout(self.fittinglayout)

        self.main_layout.addWidget(self.plotbox)
        self.main_layout.addWidget(self.fittingbox)
        self.setLayout(self.main_layout)
             
    def change_orientation(self):
        if self.orientation == 'horizontal':
            self.orientation = 'vertical'
        elif self.orientation == 'vertical':
            self.orientation = 'horizontal'
        self.xmin_box.clear()
        self.xmax_box.clear()
        self.output_window.clear()
        self.update()

    def limits_edited(self):
        try:
            if hasattr(self, 'minline'):
                self.minline.remove()
                del self.minline
            if hasattr(self, 'maxline'):
                self.maxline.remove()
                del self.maxline
        except:
            pass
        xmin=self.xmin_box.text()
        xmax=self.xmax_box.text()
        if xmin != '':
            xmin=float(xmin)
            self.minline=self.axes.axvline(xmin, 0,0.1, color='blue', linestyle='--')
        if xmax != '':
            xmax=float(xmax)
            self.maxline=self.axes.axvline(xmax, 0,0.1, color='red', linestyle='--')
        self.canvas.draw()
    
    def reset_limits(self):
        try:
            if hasattr(self, 'minline'):
                self.minline.remove()
                del self.minline
            if hasattr(self, 'maxline'):
                self.maxline.remove()
                del self.maxline
        except:
            pass
        self.xmin_box.clear()
        self.xmax_box.clear()

        self.canvas.draw()
  
    def update(self):
        if self.running:
            try:
                self.parent.linecut.remove()
                del self.parent.linecut
            except:
                pass
            if self.orientation == '1D':
                self.ylabel = self.parent.settings['ylabel']
            else:
                self.ylabel = self.parent.settings['clabel']
            self.draw_plot()
            self.parent.canvas.draw()
            self.show()
               
    def clear_lines(self):
        for line in reversed(self.axes.get_lines()):
            if line.get_linestyle() == '--':
                line.remove()
                del line
        if hasattr(self, 'peak_estimates'):
            self.peak_estimates = []
        self.update()
        self.output_window.clear()
        self.fit_type_changed(resetinputs=False)
        self.canvas.draw()
    
    def fit_class_changed(self):
        self.fit_box.clear()
        self.fit_box.addItems(fits.get_names(fitclass=self.fit_class_box.currentText()))
        self.fit_box.setCurrentIndex(0)
        self.fit_type_changed()
        #self.pars_label.setText(fits.get_names(parameters=self.fit_box.currentText()))
    
    def fit_type_changed(self,resetinputs=True):
        fit_function=fits.functions[self.fit_class_box.currentText()][self.fit_box.currentText()]
        if resetinputs:
            if 'default_inputs' in fit_function.keys():
                self.input_edit.setText(fit_function['default_inputs'])
            else:
                self.input_edit.setText('')
            if 'default_guess' in fit_function.keys():
                self.guess_edit.setText(fit_function['default_guess'])
            else:
                self.guess_edit.setText('')
        if 'inputs' in fit_function.keys():
            self.input_label.setText(f'Input info: {fit_function['inputs']}')
        else:
            self.input_label.setText(f'Input info:')
        if 'parameters' in fit_function.keys():
            self.guess_checkbox.setText(f'Initial guess: {fit_function['parameters']}')
        else:
            self.guess_checkbox.setText(f'Initial guess:')
        self.output_window.setText('Information about selected fit type:\n'+
                                   fit_function['description'])
    def collect_fit_data(self):
        # If diagonal or circular, setting limits doesn't work; however, one can easily change the range during linecut definition anyway
        if self.orientation in ['horizontal','vertical','1D']:
            if self.xmin_box.text() != '':
                xmin = float(self.xmin_box.text())
                min_ind=(np.abs(self.x - xmin)).argmin()
            else:
                min_ind = self.x.argmin()
            if self.xmax_box.text() != '':
                xmax = float(self.xmax_box.text())
                max_ind=(np.abs(self.x - xmax)).argmin()
            else:
                max_ind = self.x.argmax()
            # Need to check if indices in 'wrong' order; i.e. x data descending.
            if min_ind > max_ind:
                self.x_forfit=self.x[max_ind:min_ind]
                self.y_forfit=self.y[max_ind:min_ind]
            else:
                self.x_forfit=self.x[min_ind:max_ind]
                self.y_forfit=self.y[min_ind:max_ind]
        else:
            self.x_forfit = self.x
            self.y_forfit = self.y

        # if self.x_forfit[-1]<self.x_forfit[0]:
        #     self.x_forfit=self.x_forfit[::-1]
        #     self.y_forfit=self.y_forfit[::-1]

    def collect_fit_inputs(self,function_class,function_name):
        if function_name=='Expression':
            inputinfo=self.input_edit.text()
        elif 'inputs' in fits.functions[function_class][function_name].keys():
            try:
                inputinfo = [float(par) for par in self.input_edit.text().split(',')]
            except Exception as e:
                self.output_window.setText(f'Could not parse inputs: {e}\n'
                                            'Review information below:\n'
                                            f'{fits.functions[function_class][function_name]['description']}')
                inputinfo=None
        else:
            inputinfo=None
        return inputinfo
        

    def collect_init_guess(self,function_class, function_name):
        # Collect parameters/initial guess
        if self.guess_checkbox.checkState():
            try:
                p0 = self.guess_edit.text().split(',')
            except Exception as e:
                self.output_window.setText(f'Could not parse Initial guess: {e}\n'
                                            'Review information below:\n'
                                            f'{fits.functions[function_class][function_name]['description']}')
                p0 = None
        else:
            p0 = None
        return p0

    def start_fitting(self):
        self.collect_fit_data()
        function_class = self.fit_class_box.currentText()
        function_name = self.fit_box.currentText()
        inputinfo=self.collect_fit_inputs(function_class,function_name)
        p0=self.collect_init_guess(function_class,function_name)

        # Try to do the fit.
        try:
            self.fit_result = fits.fit_data(function_class=function_class, function_name=function_name,
                                                xdata=self.x_forfit,ydata=self.y_forfit, p0=p0, inputinfo=inputinfo)
            self.y_fit = self.fit_result.best_fit
        except Exception as e:
            self.output_window.setText(f'Curve could not be fitted: {e}')
            self.fit_parameters = [np.nan]*len(fits.get_names(function_name).split(','))
            self.y_fit = np.nan

        #self.draw_plot(parent_linecut=False)
        self.plot_parameters()
        self.draw_fits()
           
    def plot_parameters(self):
        self.output_window.clear()
        try:
            self.output_window.setText(self.fit_result.fit_report())

        except Exception as e:
            self.output_window.setText('Could not print fit parameters:', e)
         
    def draw_plot(self,parent_linecut=True):
        self.running = True
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)

        if self.orientation == '1D':
            self.x = self.parent.processed_data[0]
            self.y = self.parent.processed_data[1]
            self.xlabel = self.parent.settings['xlabel']
            self.ylabel = self.parent.settings['ylabel']
            self.title = self.parent.settings['title']
        
        elif self.orientation == 'horizontal':
            self.x = self.parent.processed_data[0][:,self.parent.selected_indices[1]]
            self.y = self.parent.processed_data[2][:,self.parent.selected_indices[1]]
            self.z = self.parent.processed_data[1][0,self.parent.selected_indices[1]]
            self.xlabel = self.parent.settings['xlabel']
            self.title = f'{self.parent.settings["ylabel"]} = {self.z}'
            if parent_linecut:
                self.parent.linecut = self.parent.axes.axhline(y=self.z, linestyle='dashed', linewidth=1, 
                                                           color=self.parent.settings['linecolor'])
            self.ylabel = self.parent.settings['clabel']
        elif self.orientation == 'vertical':
            self.x = self.parent.processed_data[1][self.parent.selected_indices[0],:]
            self.y = self.parent.processed_data[2][self.parent.selected_indices[0],:]
            self.z = self.parent.processed_data[0][self.parent.selected_indices[0],0]
            self.xlabel = self.parent.settings['ylabel']
            self.title = f'{self.parent.settings["xlabel"]} = {self.z}'
            if parent_linecut:
                self.parent.linecut = self.parent.axes.axvline(x=self.z, linestyle='dashed', linewidth=1, 
                                                           color=self.parent.settings['linecolor'])
            self.ylabel = self.parent.settings['clabel']
        elif self.orientation == 'diagonal' or self.orientation == 'circular':
            x0 = self.parent.linecut_points[0].x 
            y0 = self.parent.linecut_points[0].y
            x1 = self.parent.linecut_points[1].x 
            y1 = self.parent.linecut_points[1].y                
            l_x, l_y = self.parent.processed_data[0].shape
            x_min = np.amin(self.parent.processed_data[0][:,0])
            x_max = np.amax(self.parent.processed_data[0][:,0])
            y_min = np.amin(self.parent.processed_data[1][0,:])
            y_max = np.amax(self.parent.processed_data[1][0,:])
            i_x0 = (l_x-1)*(x0-x_min)/(x_max-x_min)
            i_y0 = (l_y-1)*(y0-y_min)/(y_max-y_min)
            i_x1 = (l_x-1)*(x1-x_min)/(x_max-x_min)
            i_y1 = (l_y-1)*(y1-y_min)/(y_max-y_min)
            if self.orientation == 'diagonal':
                n = int(np.sqrt((i_x1-i_x0)**2+(i_y1-i_y0)**2))
                x_diag = np.linspace(i_x0, i_x1, n), 
                y_diag = np.linspace(i_y0, i_y1, n)
                self.y = map_coordinates(self.parent.processed_data[-1], 
                                         np.vstack((x_diag, y_diag)))
                self.x = map_coordinates(self.parent.processed_data[0],
                                         np.vstack((x_diag, y_diag)))                
                self.xlabel = self.parent.settings['xlabel']
                self.title = f'({x0:5g},{y0:5g}) : ({x1:5g},{y1:5g})'
            elif self.orientation == 'circular':
                n = int(8*np.sqrt((i_x0-i_x1)**2+(i_y0-i_y1)**2))
                theta = np.linspace(0, 2*np.pi, n)
                i_x_circ = i_x0+(i_x1-i_x0)*np.cos(theta) 
                i_y_circ = i_y0+(i_y1-i_y0)*np.sin(theta)
                self.y = map_coordinates(self.parent.processed_data[-1], 
                                         np.vstack((i_x_circ, i_y_circ)))
                self.x = theta
                self.xlabel = 'Angle (rad)'
                self.title = ''
            self.ylabel = self.parent.settings['clabel']
        self.image = self.axes.plot(self.x, self.y, linewidth=self.parent.settings['linewidth'])
        self.cursor = Cursor(self.axes, useblit=True, color='grey', linewidth=0.5)
        self.axes.set_xlabel(self.xlabel, size='x-large')
        self.axes.set_ylabel(self.ylabel, size='x-large')
        self.axes.tick_params(labelsize='x-large', color=rcParams['axes.edgecolor'])
        self.axes.set_title(self.title, size='x-large')
        self.limits_edited()
        self.canvas.draw()
        self.parent.canvas.draw()
              
    def draw_fits(self):
        try:
            self.axes.plot(self.x_forfit, self.y_fit, 'k--',
                linewidth=self.parent.settings['linewidth'])
            self.fit_components=self.fit_result.eval_components()
            line_colors = cm.viridis(np.linspace(0.1,0.9,len(self.fit_components.keys())))
            for i,key in enumerate(self.fit_components.keys()):
                self.axes.plot(self.x_forfit, self.fit_components[key], '--', color=line_colors[i],alpha=0.75, linewidth=self.parent.settings['linewidth'])
        except Exception as e:
            self.output_window.setText(f'Could not plot fit components: {e}')
        self.canvas.draw()

    def closeEvent(self, event):
        self.parent.hide_linecuts()
        self.running = False
        
    def save_data(self):
        formats = 'JSON (*.json);;Comma Separated Value (*.csv)'
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Data As','',formats)
        try:
            data={}
            data['X']=list(self.x)
            data['Y']=list(self.y)
            if hasattr(self,'fit_result'):
                data['X_bestfit']=list(self.x_forfit)
                data['Y_bestfit']=list(self.y_fit)
            if hasattr(self,'fit_components'):
                for key in self.fit_components.keys():
                    data[key]=list(self.fit_components[key])
            if extension=='JSON (*.json)':
                with open(filename, 'w', encoding='utf-8') as f:
                    jsondump(data, f, ensure_ascii=False,indent=4)
            elif extension=='Comma Separated Value (*.csv)':
                with open(filename, 'w', newline='') as f:
                    writer = csvwriter(f)
                    writer.writerow([key for key in data])
                    for i in range(len(data['X'])):
                        row = []
                        for param in data:
                            try:
                                row.append(data[param][i])
                            except IndexError:
                                row.append('')
                        writer.writerow(row)
        except Exception as e:
            print(e)
    
    def save_fit_result(self):
        formats = 'lmfit Model Result (*.sav)'
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save Fit Result','', formats)
        save_modelresult(self.fit_result,filename)
        
    def save_image(self):
        formats = 'Portable Network Graphic (*.png);;Adobe Acrobat (*.pdf)'
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Figure As', '', formats)
        if filename:
            print('Save Figure as '+filename+' ...')
            if DARK_THEME and qdarkstyle_imported:
                rcParams_to_light_theme()
                self.update()
            self.figure.savefig(filename)
            if DARK_THEME and qdarkstyle_imported:
                rcParams_to_dark_theme()
                self.update()
            print('Saved!')
    
    def copy_image(self):
        self.cursor.horizOn = False
        self.cursor.vertOn = False            
        self.canvas.draw()
        if DARK_THEME and qdarkstyle_imported:
            rcParams_to_light_theme()
            self.parent.update()           
        buf = io.BytesIO()
        self.figure.savefig(buf, dpi=300, transparent=True, bbox_inches='tight')
        QtWidgets.QApplication.clipboard().setImage(QtGui.QImage.fromData(buf.getvalue()))
        buf.close()
        self.cursor.horizOn = True
        self.cursor.vertOn = True                       
        self.canvas.draw()
        if DARK_THEME and qdarkstyle_imported:
            rcParams_to_dark_theme()
            self.update() 

    def change_index(self, direction):
        if self.orientation == 'horizontal':
            if direction == 'up':
                new_index = self.parent.selected_indices[1]+1
                if new_index < self.parent.processed_data[0].shape[1]:
                    self.parent.selected_indices[1] = new_index
            elif direction == 'down':
                new_index = self.parent.selected_indices[1]-1
                if new_index >= 0:
                    self.parent.selected_indices[1] = new_index
        elif self.orientation == 'vertical':
            if direction == 'up':
                new_index = self.parent.selected_indices[0]+1
                if new_index < self.parent.processed_data[0].shape[0]:
                    self.parent.selected_indices[0] = new_index
            elif direction == 'down':
                new_index = self.parent.selected_indices[0]-1
                if new_index >= 0:
                    self.parent.selected_indices[0] = new_index
        self.update()
        self.output_window.clear()
        self.parent.canvas.draw()
            
    def mouse_scroll_canvas(self, event):
        if event.inaxes:
            data_shape = self.parent.processed_data[0].shape
            if self.orientation == 'horizontal':
                new_index = self.parent.selected_indices[1]+int(event.step)
                if new_index >= 0 and new_index < data_shape[1]:
                    self.parent.selected_indices[1] = new_index
            elif self.orientation == 'vertical':
                new_index = self.parent.selected_indices[0]+int(event.step)
                if new_index >= 0 and new_index < data_shape[0]:
                    self.parent.selected_indices[0] = new_index
            self.update()
            self.parent.canvas.draw()

    def mouse_click_canvas(self, event):
        if self.navi_toolbar.mode == '': # If not using the navigation toolbar tools
            if event.inaxes and event.button == 1:
                # Snap to data.
                index=(np.abs(self.x-event.xdata)).argmin()
                x_value = self.x[index]
                if self.xmin_box.text() == '':
                    self.xmin_box.setText(str(x_value))
                elif self.xmax_box.text() == '':
                    self.xmax_box.setText(str(x_value))
                else:
                    if np.abs(float(self.xmin_box.text())-float(x_value)) < np.abs(float(self.xmax_box.text())-float(x_value)):
                        self.xmin_box.setText(str(x_value))
                    else:
                        self.xmax_box.setText(str(x_value))
                self.limits_edited()

    def save_fit_preset(self):
        preset_dict={}
        preset_dict['xlims']=[self.xmin_box.text(),self.xmax_box.text()]
        preset_dict['function_class']=self.fit_class_box.currentText()
        preset_dict['function_name']=self.fit_box.currentText()
        preset_dict['inputinfo']=self.input_edit.text()
        preset_dict['initial_guess']=self.guess_edit.text()
        if self.guess_checkbox.isChecked():
            preset_dict['intial_checkbox']=True
                
        formats = 'JSON (*.json)'
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Figure As', '', formats)
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                jsondump(preset_dict, f, ensure_ascii=False)

    def load_fit_preset(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self, 'Open Fitting Preset', '', '*.json')
        if filename:
            with open(filename) as f:
                preset_dict=jsonload(f)
            self.xmin_box.setText(preset_dict['xlims'][0])
            self.xmax_box.setText(preset_dict['xlims'][1])
            self.fit_class_box.setEditText(preset_dict['function_class'])
            self.fit_box.setEditText(preset_dict['function_name'])
            self.input_edit.setText(preset_dict['inputinfo'])
            self.guess_edit.setText(preset_dict['initial_guess'])
            if preset_dict['intial_checkbox']:
                self.guess_checkbox.setCheckState(QtCore.Qt.Checked)
            else:
                self.guess_checkbox.setCheckState(QtCore.Qt.UnChecked)

    
    # Below doesn't work because arrow keys already function to move between items in the GUI.
    # Could try to override it one day.

    # def keyPressEvent(self,event):
    #     if self.orientation == 'horizontal' or self.orientation == 'vertical':
    #         data_shape = self.parent.processed_data[0].shape
    #         if self.orientation == 'horizontal':
    #             if event.key() == QtCore.Qt.Key_Up:
    #                 new_index = self.parent.selected_indices[1]+1
    #                 if new_index < data_shape[1]:
    #                     self.parent.selected_indices[1] = new_index
    #             elif event.key() == QtCore.Qt.Key_Down:
    #                 new_index = self.parent.selected_indices[1]-1
    #                 if new_index >= 0:
    #                     self.parent.selected_indices[1] = new_index
            
    #         elif self.orientation == 'vertical':
    #             if event.key() == QtCore.Qt.Key_Right:
    #                 new_index = self.parent.selected_indices[0]+1
    #                 if new_index < data_shape[0]:
    #                     self.parent.selected_indices[0] = new_index
    #             elif event.key() == QtCore.Qt.Key_Left:
    #                 new_index = self.parent.selected_indices[0]-1
    #                 if new_index >= 0:
    #                     self.parent.selected_indices[0] = new_index
    #         self.update()
    #         self.parent.canvas.draw()
  
            
class MultiPlotWindow(LineCutWindow):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Inspectra Gadget - Multiplot Window')
 
    def init_widgets(self):
        super().init_widgets()
        self.colormap_box = QtWidgets.QComboBox()
        self.colormap_box.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.colormap_type_box = QtWidgets.QComboBox()
        self.colormap_type_box.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)  
        for cmap_type in cmaps:    
            self.colormap_type_box.addItem(cmap_type)
        self.colormap_box.addItems(list(cmaps.values())[0])
        
        self.offset_label = QtWidgets.QLabel('Offset')
        self.offset_line_edit = QtWidgets.QLineEdit('0')
        self.offset_line_edit.setFixedSize(70,20)
        self.check_legend = QtWidgets.QCheckBox('Legend')

        self.reverse_checkbox = QtWidgets.QCheckBox('Reverse Fit Order')
        self.reverse_checkbox.setCheckState(QtCore.Qt.Checked)
        self.detect_peaks_button = QtWidgets.QPushButton('Detect Peaks')

    def init_connections(self):
        super().init_connections()
        self.colormap_type_box.currentIndexChanged.connect(self.colormap_type_edited)
        self.colormap_box.currentIndexChanged.connect(self.draw_plot)
        self.offset_line_edit.editingFinished.connect(self.draw_plot)
        self.check_legend.clicked.connect(self.draw_plot)
        self.detect_peaks_button.clicked.connect(self.detect_peaks)
        
    def init_canvas(self):
        super().init_canvas()
        self.canvas.mpl_disconnect(self.scroll_event_id) 
        self.canvas.mpl_connect('button_press_event', self.mouse_click_canvas)
               
    def init_layouts(self):
        super().init_layouts()
        
        self.top_buttons_layout.addWidget(self.colormap_type_box)
        self.top_buttons_layout.addWidget(self.colormap_box)
        
        self.lines_layout = QtWidgets.QHBoxLayout()
        self.lines_layout.addStretch()
        self.lines_layout.addWidget(self.offset_label)
        self.lines_layout.addWidget(self.offset_line_edit)
        self.lines_layout.addWidget(self.check_legend)
        
        self.bottom_buttons_layout.addWidget(self.detect_peaks_button)
        self.bottom_buttons_layout.addWidget(self.reverse_checkbox)
    
    def set_main_layout(self):
        self.main_layout.addLayout(self.top_buttons_layout)
        self.main_layout.addLayout(self.lines_layout)
        self.main_layout.addWidget(self.canvas)
        self.main_layout.addWidget(self.navi_toolbar)
        self.main_layout.addLayout(self.fit_layout)
        self.main_layout.addLayout(self.bottom_buttons_layout)
        self.setLayout(self.main_layout)
    
    def mouse_click_canvas(self, event):
        if self.navi_toolbar.mode == '':
            if event.inaxes and lmfit_imported:
                x = event.xdata                
                if event.button == 1:
                    if not hasattr(self, 'peak_estimates'):
                        self.peak_estimates = []
                    self.peak_estimates.append(self.axes.axvline(x, linestyle='dashed'))
                    self.canvas.draw()
                elif event.button == 3:
                    if hasattr(self, 'peak_estimates') and self.peak_estimates:
                        # Remove peak closest to right-click
                        peak_index = np.argmin(np.array([np.abs(p.get_xdata()[0]-x) for p in self.peak_estimates]))
                        self.peak_estimates[peak_index].remove()
                        del self.peak_estimates[peak_index]
                        self.canvas.draw()
    
    def update(self):
        self.draw_plot()
        self.show()
        
    def closeEvent(self, event):
        self.running = False
    
    def detect_peaks(self):
        self.clear_lines()
        if self.reverse_checkbox.checkState(): 
            index_trace = np.argmax(self.z)
        else:
            index_trace = np.argmin(self.z)
        peaks, _ = find_peaks(self.y[index_trace], width=5)
        if not hasattr(self, 'peak_estimates'):
            self.peak_estimates = []
        for peak in peaks:
            self.peak_estimates.append(self.axes.axvline(self.x[index_trace][peak], 
                                                         linestyle='dashed'))
        self.canvas.draw()
    
    def start_fitting(self):
        function_name = self.fit_box.currentText()
        if hasattr(self, 'peak_estimates') and len(self.peak_estimates) > 0:
            center_estimates = [p.get_xdata()[0] for p in self.peak_estimates]
            n_peaks = len(center_estimates)
            self.clear_lines()
            line_indices = list(range(len(self.z)))
            if np.argmin(self.z) == 0 and self.reverse_checkbox.checkState():  
                line_indices.reverse()
            elif np.argmax(self.z) == 0 and not self.reverse_checkbox.checkState(): 
                line_indices.reverse()
            
            # Initialize objects
            values = None
            self.peak_values = {}
            self.peak_values['background_constant'] = []
            self.peak_values['mean_height'] = []
            self.peak_values['mean_fwhm'] = []
            self.peak_values['coordinates'] = self.z[line_indices]
            for i in range(len(center_estimates)):
                self.peak_values[f'p{i}_center'] = [] 
                self.peak_values[f'p{i}_height'] = [] 
                self.peak_values[f'p{i}_fwhm'] = []

            # Fit routine for every trace
            for counter, line_index in enumerate(line_indices):
                x, y, z = self.x[line_index], self.y[line_index], self.z[line_index]
                print(f'Fitting peaks; index = {line_index}, value = {z}')
                if counter == 0:
                    background_estimate = np.amin(y)
                    height_estimate = np.amax(y) - np.amin(y)
                    fwhm_estimate = 0.1*(np.amax(x)-np.amin(x))
                    if function_name == 'Lorentzian':
                        sigma_estimate = fwhm_estimate/2
                        amplitude_estimate = height_estimate*sigma_estimate*np.pi
                    else: # Gaussian
                        sigma_estimate = fwhm_estimate/2.35482
                        amplitude_estimate = height_estimate*sigma_estimate*np.sqrt(2*np.pi)
                    peak_bounds = (np.amin(x)-0.5*(np.amax(x)-np.amin(x)), 
                                   np.amax(x)+0.5*(np.amax(x)-np.amin(x)))
                else:
                    background_estimate = values['bkg_c']
                    sigma_estimate = values['p0_sigma']
                    amplitude_estimate = values['p0_amplitude']
                    center_estimates = [values[f'p{i}_center'] for i 
                                        in range(len(center_estimates))]
                model = ConstantModel(prefix='bkg_')
                params = model.make_params()
                params['bkg_c'].set(background_estimate, min=-np.inf)
                for i, center_estimate in enumerate(center_estimates):
                    peak, pars = self.add_peak(f'p{i}_', function_name, 
                                               center_estimate, peak_bounds, 
                                               amplitude_estimate, sigma_estimate)
                    model = model + peak
                    params.update(pars)
                result = model.fit(y, params, x=x)
                values = result.best_values
                print('Fit finished')
                
                # Save fit values in dictionary
                self.peak_values['background_constant'].append(values['bkg_c'])
                for i in range(n_peaks):
                    self.peak_values[f'p{i}_center'].append(values[f'p{i}_center'])
                    if function_name == 'Lorentzian':    
                        best_fwhm = 2*values[f'p{i}_sigma']
                        best_height = (values[f'p{i}_amplitude']/
                                       (np.pi*values[f'p{i}_sigma']))
                    else:
                        best_fwhm = 2.35482*values[f'p{i}_sigma']
                        best_height = (values[f'p{i}_amplitude']/
                                       (np.sqrt(2*np.pi)*values[f'p{i}_sigma']))
                    self.peak_values[f'p{i}_height'].append(best_height)
                    self.peak_values[f'p{i}_fwhm'].append(best_fwhm)
                self.axes.plot(x, result.best_fit+line_index*self.offset, 'k--')
            self.canvas.draw()
            
            if not isinstance(self.parent, list):  
                # Plot peak center positions as dots in main canvas
                for i in range(n_peaks):
                    if self.orientation == 'vertical':
                        self.parent.axes.scatter(self.z[line_indices], 
                                                 self.peak_values[f'p{i}_center'], c='r')
                    elif self.orientation == 'horizontal':
                        self.parent.axes.scatter(self.peak_values[f'p{i}_center'], 
                                                 self.z[line_indices], c='r')
                self.parent.canvas.draw()
                
            # Calculate properties of peaks
            if len(self.peak_estimates) > 1:
                self.peak_values['mean_height'] = [np.mean([self.peak_values[f'p{i}_height'][j] 
                                                            for i in range(n_peaks)]) 
                                                   for j in range(len(line_indices))]
                self.peak_values['mean_fwhm'] = [np.mean([self.peak_values[f'p{i}_fwhm'][j] 
                                                          for i in range(n_peaks)]) 
                                                 for j in range(len(line_indices))]
                for index, parity in enumerate(['even','odd']):
                    self.peak_values['mean_spacing_'+parity] = [np.mean([np.abs(self.peak_values[f'p{i}_center'][j] - 
                                                                                self.peak_values[f'p{i+1}_center'][j]) 
                                                                         for i in range(index,n_peaks-1,2)]) 
                                                            for j in range(len(line_indices))]
                    self.peak_values['mean_height_'+parity] = [np.mean([self.peak_values[f'p{i}_height'][j] 
                                                                        for i in range(index,n_peaks,2)]) 
                                                               for j in range(len(line_indices))]
                    self.peak_values['mean_fwhm_'+parity] = [np.mean([self.peak_values[f'p{i}_fwhm'][j] 
                                                                      for i in range(index,n_peaks,2)]) 
                                                             for j in range(len(line_indices))]

            # Save dictionary with peak properties to file    
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save peak-fitting data as', 'fitdata', '*.npy')
            if filename:
                np.save(filename, self.peak_values)
                print('Peak fitting data saved!')
                
            
            self.parameter_windows = [] 
            for key in self.peak_values.keys():
                if len(self.z[line_indices]) == len(self.peak_values[key]):
                    self.parameter_windows.append(ParameterWindow(self.z[line_indices], 
                                                                  self.peak_values[key], 
                                                                  self.zlabel, key))
                    self.parameter_windows[-1].show()
        
    def add_peak(self, prefix, shape, center, bounds, amplitude, sigma):
        if shape == "Lorentzian":
            peak = LorentzianModel(prefix=prefix)
        else:
            peak = GaussianModel(prefix=prefix)
        pars = peak.make_params()
        pars[prefix + 'center'].set(center, min=bounds[0], max=bounds[1])
        pars[prefix + 'amplitude'].set(amplitude, min=0)
        pars[prefix + 'sigma'].set(sigma, min=0)
        return peak, pars
    
    def colormap_type_edited(self):
        self.colormap_box.currentIndexChanged.disconnect(self.draw_plot)
        self.colormap_box.clear()
        self.colormap_box.addItems(cmaps[self.colormap_type_box.currentText()])
        self.colormap_box.currentIndexChanged.connect(self.draw_plot)
        self.draw_plot()
         
    def draw_plot(self):
        self.running = True
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)

        try:
            self.offset = float(self.offset_line_edit.text())
        except Exception as e:
            print('Invalid offset value!', e)
            self.offset = 0
            self.offset_line_edit.setText('0')
        selected_colormap = cm.get_cmap(self.colormap_box.currentText())
        line_colors = selected_colormap(np.linspace(0.1,0.9,len(self.parent)))
        self.x, self.y = [], []
        self.z = np.arange(len(self.parent))
        for index, data in enumerate(self.parent):
            x, y = data.processed_data[0], data.processed_data[1]
            self.axes.plot(x, y+index*self.offset, 
                           color=line_colors[index], 
                           linewidth=data.settings['linewidth'], 
                           label=f'{data.label}')
            self.x.append(x)
            self.y.append(y)
        if self.check_legend.checkState():
            self.axes.legend()
        self.cursor = Cursor(self.axes, useblit=True, 
                             color='grey', linewidth=0.5)
        self.xlabel = data.settings['xlabel']
        self.ylabel = data.settings['ylabel']
        self.zlabel = ''
        self.axes.set_xlabel(self.xlabel, size='xx-large')
        self.axes.set_ylabel(self.ylabel, size='xx-large')
        self.axes.tick_params(labelsize='x-large', color=rcParams['axes.edgecolor'])
        self.canvas.draw()
           
    def draw_fits(self):
        for index in range(self.number):
            self.axes.plot(self.x[index], self.y_fit[index]+index*self.offset, 
                           'k--', linewidth=self.linewidth)         
        self.canvas.draw()
        
    def save_data(self):
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Data As')
        z = np.hstack([np.repeat(self.z[i], len(self.x[i])) 
                       for i in range(len(self.z))])
        x = np.hstack(self.x) 
        y = np.hstack(self.y)
        np.savetxt(filename, np.column_stack((z,x,y)))

            
class MultipleLineCutsWindow(MultiPlotWindow):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Inspectra Gadget - Multiple Linecuts Window')
 
    def init_widgets(self):
        super().init_widgets()        
        self.number_label = QtWidgets.QLabel('Number of lines:')
        self.number_line_edit = QtWidgets.QLineEdit('5')
        self.number_line_edit.setFixedSize(40,20)
        self.all_lines_button = QtWidgets.QPushButton('All')
        self.all_lines_button.setFixedSize(35,22)
        self.check_specify_lines = QtWidgets.QCheckBox('Specify lines:')
        self.check_specify_lines.clicked.connect(self.draw_plot)
        self.specify_lines_edit = QtWidgets.QLineEdit('')

    def init_connections(self):
        super().init_connections()
        self.number_line_edit.editingFinished.connect(self.draw_plot)
        self.all_lines_button.clicked.connect(self.clicked_all_lines)
        self.specify_lines_edit.editingFinished.connect(self.draw_plot)
               
    def init_layouts(self):
        super().init_layouts()
        self.lines_layout.addWidget(self.number_label)
        self.lines_layout.addWidget(self.number_line_edit)
        self.lines_layout.addWidget(self.all_lines_button)
        self.lines_layout.addWidget(self.check_specify_lines)
        self.lines_layout.addWidget(self.specify_lines_edit)
           
    def draw_plot(self):
        self.running = True
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)

        try:
            self.offset = float(self.offset_line_edit.text())
        except Exception as e:
            print('Invalid offset value!', e)
            self.offset = 0
            self.offset_line_edit.setText('0')
        selected_colormap = cm.get_cmap(self.colormap_box.currentText())
        
        rows, cols = self.parent.processed_data[0].shape
        self.number = int(self.number_line_edit.text())
        if self.orientation == 'horizontal':
            if not self.check_specify_lines.checkState():
                indices = np.linspace(0, cols-1, self.number, dtype=int)
            else:
                try:
                    if ':' in self.specify_lines_edit.text():
                        min_value = float(self.specify_lines_edit.text().split(':')[0])
                        max_value = float(self.specify_lines_edit.text().split(':')[-1])
                        min_index = np.argmin(np.abs(self.parent.processed_data[1][0,:]-min_value))
                        max_index = np.argmin(np.abs(self.parent.processed_data[1][0,:]-max_value))
                        indices = list(range(min_index,max_index+1))
                    else:
                        indices = [np.argmin(np.abs(self.parent.processed_data[1][0,:]-float(s))) 
                                   for s in self.specify_lines_edit.text().split(',')]
                    self.number = len(indices)
                except Exception as e:
                    print('Invalid lines specification!', e)
                    indices = []
                    self.number = 0
            self.x = self.parent.processed_data[0][:,indices].transpose()
            self.y = self.parent.processed_data[2][:,indices].transpose()
            self.z = self.parent.processed_data[1][0,indices]
            self.xlabel = self.parent.settings['xlabel']
            self.zlabel = self.parent.settings['ylabel']
        elif self.orientation == 'vertical':
            if not self.check_specify_lines.checkState():
                indices = np.linspace(0, rows-1, self.number, dtype=int)
            else:
                try:
                    if ':' in self.specify_lines_edit.text():
                        min_value = float(self.specify_lines_edit.text().split(':')[0])
                        max_value = float(self.specify_lines_edit.text().split(':')[-1])
                        min_index = np.argmin(np.abs(self.parent.processed_data[0][:,0]-min_value))
                        max_index = np.argmin(np.abs(self.parent.processed_data[0][:,0]-max_value))
                        indices = list(range(min_index,max_index+1))
                    else:
                        indices = [np.argmin(np.abs(self.parent.processed_data[0][:,0]-float(s))) 
                                   for s in self.specify_lines_edit.text().split(',')]
                    self.number = len(indices)
                except Exception as e:
                    print('Invalid lines specification!', e)
                    indices = []
                    self.number = 0

            self.x = self.parent.processed_data[1][indices,:]
            self.y = self.parent.processed_data[2][indices,:]
            self.z = self.parent.processed_data[0][indices,0]
            self.xlabel = self.parent.settings['ylabel']
            self.zlabel = self.parent.settings['xlabel']
        self.labels = [f'{self.z[i]:.5g}' for i in range(self.number)]            
        self.ylabel = self.parent.settings['clabel']
        self.title = ''
        line_colors = selected_colormap(np.linspace(0.1,0.9,self.number))
        for index in range(self.number):
            self.axes.plot(self.x[index], self.y[index]+index*self.offset, 
                           color=line_colors[index], 
                           linewidth=self.parent.settings['linewidth'], 
                           label=self.labels[index])
        if self.check_legend.checkState():
            self.axes.legend(title=self.zlabel)
        self.cursor = Cursor(self.axes, useblit=True, 
                             color='grey', linewidth=0.5)
        self.axes.set_xlabel(self.xlabel, size='xx-large')
        self.axes.set_ylabel(self.ylabel, size='xx-large')
        self.axes.tick_params(labelsize='x-large', color=rcParams['axes.edgecolor'])
        self.axes.set_title(self.title, size='x-large')
        self.canvas.draw()

    def clicked_all_lines(self):
        rows, cols = self.parent.processed_data[0].shape
        if self.orientation == 'horizontal':
            number = cols
        elif self.orientation == 'vertical':
            number = rows
        self.number_line_edit.setText(str(number))
        self.draw_plot()        
                
        
class ParameterWindow(QtWidgets.QWidget):
    def __init__(self, x, y, xlabel, ylabel):
        super().__init__()
        self.resize(600, 600)
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.button_layout = QtWidgets.QHBoxLayout()
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        self.navi_toolbar = NavigationToolbar(self.canvas, self)
        self.x = x
        self.y = y
        self.axes.plot(self.x, self.y,'.')
        self.axes.set_xlabel(xlabel, size='xx-large')
        self.axes.set_ylabel(ylabel, size='xx-large')
        self.axes.tick_params(labelsize='x-large', color=rcParams['axes.edgecolor'])
        self.figure.tight_layout(pad=2)
        self.canvas.draw()
        self.save_button = QtWidgets.QPushButton('Save')
        self.save_button.clicked.connect(self.save_data)
        self.save_image_button = QtWidgets.QPushButton('Save Image')
        self.save_image_button.clicked.connect(self.save_image)
        self.vertical_layout.addWidget(self.navi_toolbar)
        self.vertical_layout.addWidget(self.canvas)
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.save_image_button)
        self.vertical_layout.addLayout(self.button_layout)
        self.setLayout(self.vertical_layout)
        
    def save_data(self):
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Data As')
        data = np.array([self.x, self.y])
        np.savetxt(filename, data.T)

    def save_image(self):
        formats = 'Portable Network Graphic (*.png);;Adobe Acrobat (*.pdf)'
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Figure As', '', formats)
        if filename:
            print('Save Figure as '+filename+' ')
            self.figure.savefig(filename)
            print('Saved!')   
  
            
class FFTWindow(QtWidgets.QWidget):
    def __init__(self, fftdata):
        super().__init__()
        self.resize(600, 600)
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        #zoom_factory(self.axes)
        self.canvas = FigureCanvas(self.figure)
        self.navi_toolbar = NavigationToolbar(self.canvas, self)
        self.fft = np.absolute(fftdata).transpose()
        self.image = self.axes.pcolormesh(self.fft, shading='auto', norm=LogNorm(vmin=self.fft.min(), vmax=self.fft.max()))
        self.cbar = self.figure.colorbar(self.image, orientation='vertical')
        self.figure.tight_layout(pad=2)
        self.axes.tick_params(color=rcParams['axes.edgecolor'])
        self.canvas.draw()
        self.vertical_layout.addWidget(self.navi_toolbar)
        self.vertical_layout.addWidget(self.canvas)
        self.setLayout(self.vertical_layout)