import threading
import sys

DARK_THEME = True

try:
    import qdarkstyle # pip install qdarkstyle
    qdarkstyle_imported = True
except ModuleNotFoundError:
    qdarkstyle_imported = False

def offline_plotting(folder=None,link_to_default=True,use_thread=True):
    """	
    Entry point for qcodespp offline plotting. From CLI: qcodespp offline_plotting. From notebooks: qcodespp.offline_plotting().

    Args:
        folder (str): Path (inc relative) to a folder containing the data files to be plotted.
        link_to_default (bool): Link to the qcodespp default folder specified by qc.set_data_folder().
            Ignored if another folder is specified by folder.
        use_thread (bool): Runs the application in a separate thread or not. Default is True.
            Threading may cause problems on some systems, e.g. macOS.
    """

    if use_thread:# and sys.platform != 'darwin': #This way of threading may not work on macOS.
        try:
            plot_thread = threading.Thread(target = main, args=(folder,link_to_default,))
            plot_thread.start()
        except Exception as e:
            print(f"Error running offline_plotting using threading: {e}\n"
                  "Try offline_plotting(use_thread=False)")
    else:
        main(folder=folder,link_to_default=link_to_default)

def main(folder=None,link_to_default=True):
    '''
    Initializes the offline_plotting Qt application and opens the editor window.
    '''

    from PyQt5 import QtWidgets
    from qcodespp.plotting.offline.editor import Editor

    app = QtWidgets.QApplication(sys.argv)
    app.aboutToQuit.connect(app.deleteLater)
    app.lastWindowClosed.connect(app.quit)
    
    edit_window = Editor(folder=folder,link_to_default=link_to_default)
    
    if DARK_THEME and qdarkstyle_imported:
        app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    
    edit_window.show()
    app.exec_()

if __name__ == '__main__':
    main()