import threading
import sys

def param_monitor(*params, interval=0.2, maxlen=500, use_thread=True):
    """	
    Entry point for qcodespp parameter monitoring. 
    Args:
        params (list): List of QCoDeS parameters to monitor.
        interval (int): Update interval in seconds.
        maxlen (int): Number of points to keep in the rolling window.
        use_thread (bool): Runs the application in a separate thread or not. Default is False.
            Threading may cause problems on some systems, e.g. macOS.
    """

    if use_thread:# and sys.platform != 'darwin': #This way of threading may not work on macOS.
        try:
            plot_thread = threading.Thread(target = main, args=(*params,), kwargs={'interval': interval, 'maxlen': maxlen})
            plot_thread.start()
        except Exception as e:
            print(f"Error running monitor_window using threading: {e}\n"
                  "Try monitor_window(use_thread=False)")
    else:
        main(*params, interval=interval, maxlen=maxlen)

def main(*params, interval=0.2, maxlen=500):
    '''
    Initializes the monitor_window Qt application and opens the monitor window.
    '''

    from PyQt5 import QtWidgets
    from .monitor_window import MonitorWindow

    app = QtWidgets.QApplication(sys.argv)
    app.aboutToQuit.connect(app.deleteLater)
    app.lastWindowClosed.connect(app.quit)
    
    monitor_window = MonitorWindow(*params, interval=interval, maxlen=maxlen)
    monitor_window.show()
    app.exec_()

if __name__ == '__main__':
    main()