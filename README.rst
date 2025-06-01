qcodes++
===================================

QCoDeS is a Python-based data acquisition framework developed by the
Copenhagen / Delft / Sydney / Microsoft quantum computing consortium.
It contains a huge range of drivers for communicating with instruments,
and a flexible - but complex - database-based method for collecting data
and running measurement loops.
See https://qcodes.github.io/ for more info.

This package, qcodes++ (aka qcodespp), provides user-friendly
frontend to the solid backend of qcodes. If you have always wanted to run 
your measurements using python but found qcodes too daunting, qcodes++ is 
the package for you. Qcodes++ features

- Text-based data (i.e. readable by e.g. notepad, excel, origin pro, etc)

- A simple yet powerful method for taking data and running measurements and loops

- True live plotting and tightly integrated offline plotting

- Improvements to core qcodes functions (such as the Station) to streamline data acquisition, protect (meta)data integtrity and minimise user error

- Improved drivers for certain instruments

- and other user-friendliness improvements outlined in the documentation.

All features of qcodes are preserved in a qcodes++ installation. Even those
features that qcodes++ does not rely on can be used seamlessly within the same
notebook/environment. This means you lose nothing by installing qcodes++ ontop of qcodes.

QCoDeS and qcodes++ are compatible with Python 3.5+. It is primarily intended for use
from Jupyter notebooks and jupyter lab, but can also be used from Spyder, traditional terminal-based
shells and in stand-alone scripts.

Docs
====
Check out the wiki https://github.com/djcarrad/qcodesplusplus/wiki for an introduction. The 
accompanying jupyter notebooks are under 'tutorials'. As of yet, there is no separate, comprehensive
documentation; this is high on the to-do list. However, all the code is quite well self-documented and 
everything is open source. If you need to know which arguments a function takes, or which capabilities 
an instrument driver has, just open up the file! Or ask a friend

Install
=======

- Install anaconda from anaconda website: if you want to be able to call python from the command line, you should add the anaconda PATH to environment variables during install. Anaconda is a suite of software can be used to manage a python installation. 

- Install git: https://git-scm.com/download/win

Git is versioning software that allows multiple developers to contribute to pieces of software. It's used when software is likely to be changing quickly and flexibility and collaboration is key.

- We will then use the Anaconda prompt to install qcodes++. First, we will create a 'virtual environment' for qcodes++. This is a separate python installation that will not interfere with your base python installation. Then we will download (aka 'clone') the qcodes++ code and install it.

- Open the Anaconda prompt and type:

	conda create –n qcpp python
	
	activate qcpp

	cd C:/git

	git clone https://github.com/qcodespp/qcodespp
	
	pip install –e qcodespp

- Optionally install useful packages from the anaconda prompt:

	pip install scipy zhinst zhinst-qcodes

You can now run qcodes in jupyter lab by opening the anaconda prompt, and typing

	activate qcpp
	
	jupyter lab
	
Additionally...
---------------

- If you are going to use VISA instruments (e.g. ones that communicate via GPIB, USB, RS232) you should install the NI VISA and GPIB(488.2) backends from the National Instruments website

https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html

https://www.ni.com/en/support/downloads/drivers/download.ni-488-2.html

- If the qcodes install fails, you may need to install Visual Studio C++ build tools. https://visualstudio.microsoft.com/downloads/ --> Tools for Visual Studio --> Build Tools for Visual Studio.
	
	
Updating
--------
Open git bash, navigate to the install folder (usually cd C:/git/qcodespp), and use 

	git pull


Status
======
As of 24/6/2024, latest versions of all packages required by qcodes are working, except:
The current version of ipykernel closes all plot windows when the kernel is restarted. Will be difficult to fix given the lack of documentation for ipykernel.

On the to-do list is improving analysis functions, such as tighter integration with InspectraGadget
and incorporation of fitting tools.

If there is a feature that you desire, feel free to contact me, damonc@dtu.dk. We can try to make it happen together!

License
=======

See `License <https://github.com/QCoDeS/Qcodes/tree/master/LICENSE.rst>`__.

Differences from qcodes-elab
==================================================

Data_type cannot be declared to parameter on init. 
It has to be declared after by parameter.data_type=float or parameter.data_type=str


