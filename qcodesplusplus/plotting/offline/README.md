# Inspectra-Gadget
Inspectra-Gadget is a GUI for inspecting and post-processing quantum transport data (e.g. differential conductance spectra) originally made by Joeri De Bruijckere. You can find the original version here: https://github.com/joeridebruijckere/Inspectra-Gadget

The elab version adds compatibility with datasets generated from qcodes-elab (https://github.com/djcarrad/qcodes-elab) and adds additional functionality.


# Packaging as .exe
It is useful to pack InspectraGadget into an .exe to distribute it and make it indpendent from the installed python version and packages on the machine. I would like to upload an .exe here, but it is larger than 25 MB. Maybe I will manage to get the file size down in the future.

To package as .exe with pyinstaller:

1. In command prompt activate the qcodes environment
> activate qcodes

2. Install pyinstaller if you haven't already
> pip install -U pyinstaller

3. Navigate to the Inpsectra gadget directory
> cd [Your-directory]\Inpectra-Gadget-master

4. Run the following pyinstaller command, make sure the qcodes installation directory is correct
>pyinstaller --onefile --add-data design.ui:. --add-data C:\git\qcodes-elab\qcodes:qcodes --name InspectraGadget --icon iconGadget.png main.py

# Known issues
* Only unknown ones for now.

# Planned updates
* Add a settings menu to change some hardcoded settings like darkmode/lightmode, auto refresh interval, etc,
* Fitting of line graphs. Currently fits are only avaialble for linecuts from colorplots



