import numpy as np
from PyQt5 import QtGui, QtCore

def zoom_factory(ax, base_scale=1.1):
    """
    Add ability to zoom with the scroll wheel.

    Parameters
    ----------
    ax : matplotlib axes object
        axis on which to implement scroll to zoom
    base_scale : float
        how much zoom on each tick of scroll wheel

    Returns
    -------
    disconnect_zoom : function
        call this to disconnect the scroll listener
    """

    def limits_to_range(lim):
        return lim[1] - lim[0]

    fig = ax.get_figure()  # get the figure of interest
    fig.canvas.capture_scroll = True
    has_toolbar = hasattr(fig.canvas, "toolbar") and fig.canvas.toolbar is not None
    if has_toolbar:
        # it might be possible to have an interactive backend without
        # a toolbar. I'm not sure so being safe here
        toolbar = fig.canvas.toolbar
        toolbar.push_current()
    orig_xlim = ax.get_xlim()
    orig_ylim = ax.get_ylim()
    orig_yrange = limits_to_range(orig_ylim)
    orig_xrange = limits_to_range(orig_xlim)
    orig_center = ((orig_xlim[0] + orig_xlim[1]) / 2, (orig_ylim[0] + orig_ylim[1]) / 2)

    def zoom_fun(event):
        if event.inaxes is not ax:
            return
        # get the current x and y limits
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        # set the range
        (cur_xlim[1] - cur_xlim[0]) * 0.5
        (cur_ylim[1] - cur_ylim[0]) * 0.5
        xdata = event.xdata  # get event x location
        ydata = event.ydata  # get event y location
        if event.button == "up":
            # deal with zoom in
            scale_factor = base_scale
        elif event.button == "down":
            # deal with zoom out
            scale_factor = 1 / base_scale
        else:
            # deal with something that should never happen
            scale_factor = 1
        # set new limits
        new_xlim = [
            xdata - (xdata - cur_xlim[0]) / scale_factor,
            xdata + (cur_xlim[1] - xdata) / scale_factor,
        ]
        new_ylim = [
            ydata - (ydata - cur_ylim[0]) / scale_factor,
            ydata + (cur_ylim[1] - ydata) / scale_factor,
        ]
        new_yrange = limits_to_range(new_ylim)
        new_xrange = limits_to_range(new_xlim)

        if abs(new_yrange) > abs(orig_yrange):
            new_ylim = orig_center[1] - new_yrange / 2, orig_center[1] + new_yrange / 2
        if abs(new_xrange) > abs(orig_xrange):
            new_xlim = orig_center[0] - new_xrange / 2, orig_center[0] + new_xrange / 2
        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)

        if has_toolbar:
            toolbar.push_current()
        ax.figure.canvas.draw_idle()  # force re-draw

    # attach the call back
    cid = fig.canvas.mpl_connect("scroll_event", zoom_fun)

    def disconnect_zoom():
        fig.canvas.mpl_disconnect(cid)

    # return the disconnect function
    return disconnect_zoom


def zoom_factory_alt(axis, scale_factor=1.2):
    """returns zooming functionality to axis.
    From https://gist.github.com/tacaswell/3144287"""

    def zoom_fun(event, ax, scale):
        """zoom when scrolling"""
        if event.inaxes == axis and QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
            scale_factor = np.power(scale, -event.step)
            xdata = event.xdata
            ydata = event.ydata
            x_left = xdata - ax.get_xlim()[0]
            x_right = ax.get_xlim()[1] - xdata

            ax.set_xlim([xdata - x_left * scale_factor, xdata + x_right * scale_factor])
            ax.figure.canvas.draw()
            # Update toolbar so back/forward buttons work
            fig.canvas.toolbar.push_current()


        elif event.inaxes == axis and QtGui.QGuiApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
            scale_factor = np.power(scale, -event.step)
            xdata = event.xdata
            ydata = event.ydata
            y_top = ydata - ax.get_ylim()[0]
            y_bottom = ax.get_ylim()[1] - ydata

            ax.set_ylim([ydata - y_top * scale_factor, ydata + y_bottom * scale_factor])
            ax.figure.canvas.draw()
            # Update toolbar so back/forward buttons work
            fig.canvas.toolbar.push_current()

        elif event.inaxes == axis:
            scale_factor = np.power(scale, -event.step)
            xdata = event.xdata
            ydata = event.ydata
            x_left = xdata - ax.get_xlim()[0]
            x_right = ax.get_xlim()[1] - xdata
            y_top = ydata - ax.get_ylim()[0]
            y_bottom = ax.get_ylim()[1] - ydata

            ax.set_xlim([xdata - x_left * scale_factor, xdata + x_right * scale_factor])
            ax.set_ylim([ydata - y_top * scale_factor, ydata + y_bottom * scale_factor])
            ax.figure.canvas.draw()
            # Update toolbar so back/forward buttons work
            fig.canvas.toolbar.push_current()

    fig = axis.get_figure()
    fig.canvas.mpl_connect(
        "scroll_event", lambda event: zoom_fun(event, axis, scale_factor)
    )