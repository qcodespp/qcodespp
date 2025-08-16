from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np
from collections import OrderedDict
from matplotlib import rcParams
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
import matplotlib.patches as patches
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar

# Colormaps
cmaps = OrderedDict()
cmaps['Uniform'] = ['viridis', 'plasma', 'inferno', 'magma', 'cividis']
cmaps['Sequential'] = ['Greys','Purples','Blues','Greens','Oranges','Reds',
                       'YlOrBr','YlOrRd','OrRd','PuRd','RdPu','BuPu','GnBu', 
                       'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn']
cmaps['Sequential (2)'] = ['binary','gist_yarg','gist_gray','gray','bone',
                           'pink','spring','summer','autumn','winter','cool',
                           'Wistia','hot','afmhot','gist_heat','copper']
cmaps['Diverging'] = ['PiYG','PRGn','BrBG','PuOr','RdGy','RdBu','RdYlBu',
                      'RdYlGn','Spectral','coolwarm','bwr','seismic']
cmaps['Cyclic'] = ['twilight', 'twilight_shifted', 'hsv']
cmaps['Qualitative'] = ['Pastel1','Pastel2','Paired','Accent','Dark2','Set1',
                        'Set2','Set3','tab10','tab20','tab20b','tab20c']
cmaps['Miscellaneous'] = ['flag','prism','ocean','gist_earth','terrain',
                          'gist_stern','gnuplot','gnuplot2','CMRmap',
                          'cubehelix','brg','gist_rainbow','rainbow','jet',
                          'nipy_spectral','gist_ncar']


class MidpointNormalize(Normalize):
    def __init__(self, vmin=None, vmax=None, midpoint=None, clip=False):
        self.midpoint = midpoint
        Normalize.__init__(self, vmin, vmax, clip)

    def __call__(self, value, clip=None):
        result, is_scalar = self.process_value(value)
        x, y = [self.vmin, self.midpoint, self.vmax], [0, 0.5, 1]
        return np.ma.array(np.interp(value, x, y), mask=result.mask, copy=False)


class NavigationToolbarMod(NavigationToolbar):
    #without save button
    NavigationToolbar.toolitems = (
        ('Home', 'Reset original view', 'home', 'home'),
        ('Back', 'Back to previous view', 'back', 'back'),
        ('Forward', 'Forward to next view', 'forward', 'forward'),
        (None, None, None, None),
        ('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
        ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
        ('Subplots', 'Configure subplots', 'subplots', 'configure_subplots'))

#Dark theme functions

DARK_COLOR = '#19232D'
GREY_COLOR = '#505F69'
LIGHT_COLOR = '#F0F0F0'
def rcParams_to_dark_theme():
    rcParams['text.color'] = LIGHT_COLOR
    rcParams['xtick.color'] = LIGHT_COLOR
    rcParams['ytick.color'] = LIGHT_COLOR
    rcParams['axes.facecolor'] = DARK_COLOR
    rcParams['axes.edgecolor'] = GREY_COLOR
    rcParams['axes.labelcolor'] = LIGHT_COLOR
    
def rcParams_to_light_theme():
    rcParams['text.color'] = 'black'
    rcParams['xtick.color'] = 'black'
    rcParams['ytick.color'] = 'black'
    rcParams['axes.facecolor'] = 'white'
    rcParams['axes.edgecolor'] = 'black'
    rcParams['axes.labelcolor'] = 'black'

class NoScrollQComboBox(QtWidgets.QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def wheelEvent(self, *args, **kwargs):
        if self.hasFocus():
            return QtWidgets.QComboBox.wheelEvent(self, *args, **kwargs)
        
class DraggablePoint:
    lock = None #  only one can be animated at a time
    def __init__(self, parent, x, y, linecut, orientation,draw_line=False, draw_circle=False):
        try:
            self.parent = parent
            self.orientation = orientation
            self.lc=linecut
            self.linecut = self.parent.linecuts[orientation]['lines'][linecut]
            self.color=self.linecut['linecolor']
            
            x_lb, x_ub = self.parent.axes.get_xlim()
            y_lb, y_ub = self.parent.axes.get_ylim()
            
            self.point = patches.Ellipse((x, y), (x_ub-x_lb)*0.02, 
                                        (y_ub-y_lb)*0.02, fc=self.color, 
                                        alpha=1, edgecolor=self.color)
            self.x = x
            self.y = y
            self.point_on_plot=self.parent.axes.add_patch(self.point)
            self.press = None
            self.background = None
            self.other_point = None
            self.connect()
            
            if draw_line:
                line_x = [self.linecut['points'][0][0], self.x]
                line_y = [self.linecut['points'][0][1], self.y]
                self.line = Line2D(line_x, line_y, 
                                color=self.color, 
                                alpha=1.0, linestyle='dashed', linewidth=1.5)
                self.line_on_plot=self.parent.axes.add_line(self.line)
        except Exception as e:
            print(f"Error in DraggablePoint: {e}")
        # if draw_circle:
        #     x0, y0 = self.parent.linecut_points[0].x, self.parent.linecut_points[0].y
        #     x1, y1 = self.parent.linecut_points[1].x, self.y
        #     self.circle = patches.Ellipse((x0, y0), 2*(x1-x0), 2*(y1-y0), 
        #                                   fc='none', alpha=None, linestyle='dashed', 
        #                                   linewidth=1, edgecolor='k')
        #     self.parent.axes.add_patch(self.circle)

    def connect(self):
        self.cidpress = self.point.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.cidrelease = self.point.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion = self.point.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self, event):
        if event.inaxes != self.point.axes: return
        if DraggablePoint.lock is not None: return
        contains, attrd = self.point.contains(event)
        if not contains: return
        self.parent.cursor.horizOn = False
        self.parent.cursor.vertOn = False 
        self.press = (self.point.center), event.xdata, event.ydata
        DraggablePoint.lock = self
        canvas = self.point.figure.canvas
        axes = self.point.axes
        self.point.set_animated(True)

        draggable_points = self.linecut['draggable_points']

        if QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
            if self == draggable_points[0]:
                self.other_point = draggable_points[1]
            else:
                self.other_point = draggable_points[0]

            self.other_point_zero = (self.other_point.x, self.other_point.y)
            self.other_point.point.set_animated(True)

        if hasattr(draggable_points[1], 'line'):
            if self == draggable_points[1]:
                self.line.set_animated(True)
            else:
                draggable_points[1].line.set_animated(True)

        # if (len(self.parent.linecut_points) > 2 and 
        #     hasattr(self.parent.linecut_points[2], 'circle')):
        #     if self == self.parent.linecut_points[2]:
        #         self.circle.set_animated(True)
        #     else:
        #         self.parent.linecut_points[2].circle.set_animated(True)
        
        # Draws over the old point. 
        canvas.draw()
        self.background = canvas.copy_from_bbox(self.point.axes.bbox)
        axes.draw_artist(self.point)
        if self.other_point is not None:
            axes.draw_artist(self.other_point.point)

        # below is faster than canvas.draw()
        canvas.blit(axes.bbox)

    def on_motion(self, event):
        if DraggablePoint.lock is not self:
            return
        if event.inaxes != self.point.axes: return
        self.point.center, xpress, ypress = self.press
        dx = event.xdata - xpress
        dy = event.ydata - ypress

        # if (len(self.parent.linecut_points) > 2 and 
        #     hasattr(self.parent.linecut_points[2], 'circle')):
        #     if self == self.parent.linecut_points[1]:
        #         dy = 0
        #     elif self == self.parent.linecut_points[2]:
        #         dx = 0

        self.point.center = (self.point.center[0]+dx, self.point.center[1]+dy)
        self.x = self.point.center[0]
        self.y = self.point.center[1]
        canvas = self.point.figure.canvas
        axes = self.point.axes
        canvas.restore_region(self.background)
        axes.draw_artist(self.point)

        draggable_points = self.linecut['draggable_points']

        if self.other_point is not None:
            if self == draggable_points[0]:
                other_point = draggable_points[1]
            else:
                other_point = draggable_points[0]
            other_point.x = self.other_point_zero[0]+dx
            other_point.y = self.other_point_zero[1]+dy
            other_point.point.center = (other_point.x, other_point.y)
            axes.draw_artist(other_point.point)

        if hasattr(draggable_points[1], 'line'):
            draggable_points[1].line.set_animated(True)
            axes.draw_artist(draggable_points[1].line)
            line_x = [draggable_points[0].x, draggable_points[1].x]
            line_y = [draggable_points[0].y, draggable_points[1].y]
            draggable_points[1].line.set_data(line_x, line_y)

        # if (len(self.parent.linecut_points) > 2 and 
        #     hasattr(self.parent.linecut_points[2], 'circle')):
        #     if self == self.parent.linecut_points[2]:
        #         self.circle.set_animated(True)
        #         axes.draw_artist(self.circle)
        #         self.circle.height = 2*(self.y-self.parent.linecut_points[0].y)
        #     elif self == self.parent.linecut_points[1]:
        #         self.parent.linecut_points[2].circle.set_animated(True)
        #         axes.draw_artist(self.parent.linecut_points[2].circle)
        #         self.parent.linecut_points[2].circle.width = 2*(self.x-self.parent.linecut_points[0].x)
        #     else:
        #         self.parent.linecut_points[2].circle.set_animated(True)
        #         axes.draw_artist(self.parent.linecut_points[2].circle)
        #         self.parent.linecut_points[2].circle.set_center((self.x, self.y))
        canvas.blit(axes.bbox)


    def on_release(self, event):
        if DraggablePoint.lock is not self:
            return
        self.parent.cursor.horizOn = True
        self.parent.cursor.vertOn = True
        self.press = None
        DraggablePoint.lock = None
        self.point.set_animated(False)
        draggable_points = self.linecut['draggable_points']

        # if (len(self.draggable_points) > 2 and 
        #     hasattr(self.draggable_points[2], 'circle')):
        #     if self == self.draggable_points[2]:
        #         self.circle.set_animated(False)
        #     elif self == self.draggable_points[1]:
        #         self.draggable_points[2].circle.set_animated(False) 
        #     else:
        #         self.draggable_points[2].circle.set_animated(False)
        #     if self == self.draggable_points[0]:
        #         circle = self.draggable_points[2].circle
        #         self.draggable_points[1].point.center = (circle.center[0]+0.5*circle.width, circle.center[1])
        #         self.draggable_points[2].point.center = (circle.center[0],circle.center[1]+0.5*circle.height)
        #         self.draggable_points[1].x = self.draggable_points[1].point.center[0]
        #         self.draggable_points[1].y = self.draggable_points[1].point.center[1]
        #         self.draggable_points[2].x = self.draggable_points[2].point.center[0]
        #         self.draggable_points[2].y = self.draggable_points[2].point.center[1]
        self.background = None

        # Snap to data.
        index_x=(np.abs(self.point.center[0]-self.parent.processed_data[0][:,0])).argmin()
        x_value = self.parent.processed_data[0][index_x,0]
        index_y=(np.abs(self.point.center[1]-self.parent.processed_data[1][0,:])).argmin()
        y_value = self.parent.processed_data[1][0,index_y]

        self.point.center = (x_value, y_value)

        self.x = self.point.center[0]
        self.y = self.point.center[1]

        if self.other_point is not None:
            index_x_1 = (np.abs(self.other_point.x - self.parent.processed_data[0][:,0])).argmin()
            x_value = self.parent.processed_data[0][index_x_1,0]
            index_y_1 = (np.abs(self.other_point.y - self.parent.processed_data[1][0,:])).argmin()
            y_value = self.parent.processed_data[1][0,index_y_1]
            self.other_point.point.center = (x_value, y_value)
            self.other_point.x = self.other_point.point.center[0]
            self.other_point.y = self.other_point.point.center[1]
            self.other_point.point.set_animated(False)
            if self.other_point == draggable_points[1]:
                self.linecut['points'][1] = (self.other_point.x, self.other_point.y)
                self.linecut['indices'][1] = (index_x_1, index_y_1)
            else:
                self.linecut['points'][0] = (self.other_point.x, self.other_point.y)
                self.linecut['indices'][0] = (index_x_1, index_y_1)
        self.other_point = None

        # Snap line to data
        if hasattr(draggable_points[1], 'line'):
            draggable_points[1].line.set_animated(True)
            self.point.axes.draw_artist(draggable_points[1].line)
            line_x = [draggable_points[0].x, draggable_points[1].x]
            line_y = [draggable_points[0].y, draggable_points[1].y]
            draggable_points[1].line.set_data(line_x, line_y)
            draggable_points[1].line.set_animated(False)

        self.point.figure.canvas.draw()

        if self == draggable_points[1]:
            self.linecut['points'][1] = (self.x, self.y)
            self.linecut['indices'][1] = (index_x, index_y)
        else:
            self.linecut['points'][0] = (self.x, self.y)
            self.linecut['indices'][0] = (index_x, index_y)
        self.parent.linecuts[self.orientation]['linecut_window'].points_dragged(self.lc)
        self.parent.linecuts[self.orientation]['linecut_window'].update()
        self.parent.linecuts[self.orientation]['linecut_window'].activateWindow()

    def disconnect(self):
        self.point.figure.canvas.mpl_disconnect(self.cidpress)
        self.point.figure.canvas.mpl_disconnect(self.cidrelease)
        self.point.figure.canvas.mpl_disconnect(self.cidmotion)
