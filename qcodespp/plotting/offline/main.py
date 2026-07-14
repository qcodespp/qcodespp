import queue
import threading
import sys
import numpy as np

DARK_THEME = True

try:
    import qdarkstyle # pip install qdarkstyle
    qdarkstyle_imported = True
except ModuleNotFoundError:
    qdarkstyle_imported = False


class PlotHandler:
    """Handle returned by offline_plotting() for sending data to the Editor.

    Usage::

        pw = offline_plotting()
        pw.plot1D(y_array)                          # y vs index
        pw.plot1D(x_array, y_array)                 # 1-D line plot
        pw.plot1D(x, y, label='My data', names=['Gate (V)', 'Current (A)'])
    """

    def __init__(self):
        self._queue = queue.Queue()

    def plot1D(self, *arrays, label='External data', names=None, plot_all=False):
        """Send arrays to the Editor to be plotted as a new 1D data item.

        Args:
            *arrays: Any number of 1D arrays (numpy or list-like)
            label (str): Name shown in the file list.
            names (list[str]): Axis/column names. Defaults to ``['x','y1','y2',...]``.
        """
        if len(arrays) == 0:
            raise ValueError("At least one array must be provided.")

        arrays = [np.asarray(a, dtype=float) for a in arrays]
        if len(arrays) == 1:
            arrays = [np.arange(len(arrays[0]), dtype=float), arrays[0]]

        dim = len(arrays)
        if names is None:
            names = ['x']
            for i in range(1, dim):
                names.append('y' + str(i))
        elif len(names) != dim:
            raise ValueError(f"Length of names ({len(names)}) must match number of arrays ({dim}).")

        self._queue.put(('plot1D', list(arrays), list(names), label, plot_all))

    def plot2D(self, x, y, z, label='External data', names=None):
        """Send arrays to the Editor to be plotted as a new 2D data item.

        Args:
            x (array-like): x-axis values.
            y (array-like): y-axis values.
            z (array-like): z-axis values.
            label (str): Name shown in the file list.
            names (list[str]): Axis/column names. Defaults to ``['x','y','z']``.
        """
        shape = np.shape(z)
        if len(shape) != 2:
            raise ValueError('z must be a 2D array-like')
        if np.shape(x) != shape and np.shape(x) != (shape[0],):
            raise ValueError('x must be a 1D array-like with length matching z\'s first dimension, '
                            'or a 2D array-like with shape matching z\'s')
        if np.shape(y) != shape and np.shape(y) != (shape[1],):
            raise ValueError('y must be a 1D array-like with length matching z\'s second dimension, '
                            'or a 2D array-like with shape matching z\'s')
        
        if len(np.shape(x)) == 1:
            x = np.tile(x[:, np.newaxis], (1, shape[1]))
        if len(np.shape(y)) == 1:
            y = np.tile(y[np.newaxis, :], (shape[0], 1))

        if names is None:
            names = ['x', 'y', 'z']
        elif len(names) != 3:
            raise ValueError(f"Length of names ({len(names)}) must be 3 for 2D data.")

        self._queue.put(('plot2D', [x, y, z], names, label))

def offline_plotting(folder=None, link_to_default=True, use_thread=True):
    """
    Entry point for qcodespp offline plotting. From CLI: qcodespp offline_plotting.
    From notebooks: ``pw = qcodespp.offline_plotting()``.

    Args:
        folder (str): Path (inc relative) to a folder containing the data files to be plotted.
        link_to_default (bool): Link to the qcodespp default folder specified by qc.set_data_folder().
            Ignored if another folder is specified by folder.
        use_thread (bool): Runs the application in a separate thread. Default True.
            Threading may cause problems on some systems, e.g. macOS.

    Returns:
        PlotHandler: Handle for sending data to the Editor. Call ``handle.plot(x, y)``
        from a notebook or script to add data dynamically. Only practically useful
        when use_thread=True (the default), since use_thread=False blocks until
        the window is closed.
    """
    handle = PlotHandler()

    if use_thread:
        try:
            plot_thread = threading.Thread(
                target=main, args=(folder, link_to_default, handle)
            )
            plot_thread.start()
        except Exception as e:
            print(f"Error running offline_plotting using threading: {e}\n"
                  "Try offline_plotting(use_thread=False)")
    else:
        main(folder=folder, link_to_default=link_to_default, handle=handle)

    return handle


def main(folder=None, link_to_default=True, handle=None):
    '''
    Initializes the offline_plotting Qt application and opens the editor window.
    '''

    from PyQt5 import QtWidgets
    from qcodespp.plotting.offline import Editor

    app = QtWidgets.QApplication(sys.argv)
    app.aboutToQuit.connect(app.deleteLater)
    app.lastWindowClosed.connect(app.quit)

    edit_window = Editor(folder=folder, link_to_default=link_to_default,
                         external_handle=handle)

    if DARK_THEME and qdarkstyle_imported:
        app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

    edit_window.show()
    app.exec_()

if __name__ == '__main__':
    main()
