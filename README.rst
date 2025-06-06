qcodes++
===================================

QCoDeS is a Python-based data acquisition framework developed by the
Copenhagen / Delft / Sydney / Microsoft quantum computing consortium.
It contains a huge range of drivers for communicating with instruments,
and a flexible - but complex - database-based method for collecting data
and running measurement loops.
See https://qcodes.github.io/ for more info.

This package, qcodes++ (aka qcodespp, qcpp, qc++), provides user-friendly
frontend to the solid backend of qcodes. If you have always wanted to run 
your measurements using python but found qcodes too daunting, qcodes++ is 
the package for you. Qcodes++ features

- Text-based data (i.e. readable by e.g. notepad, excel, origin pro, etc) (note 1)

- A simple yet powerful method for taking data and running measurements and loops (note 1)

- True live plotting and an integrated offline plotting/analysis tool

- Improvements to core qcodes functions (e.g. Station, Parameters) to streamline data acquisition, protect (meta)data integtrity and minimise user error

- Improved drivers for certain instruments

- and other user-friendliness improvements outlined in the documentation.

qcodes++ is installed alongside/around QCoDeS, meaning all features of both packages can be used 
seamlessly within the same notebook/environment. e.g. you could still use the mainline qcodes 
dataset and measurement process for some experiments while relying on qcodes++ in other instances.
In addition, all top level qcodes functions are available in qcodes++ with the same names, so if you
are used to doing 'import qcodes as qc', and then e.g. using qc.Station, you should simply replace the import with
'import qcodespp as qc', and continute to use qc.Station, qc.Parameter, etc. as before. For deeper-level
functions (most importantly instrument drivers), you can simply continue to use e.g. 
qcodes.instrument_drivers.tektronix.Keithley2400, or migrate to the qcodes++ version if one is available, and you prefer to.
TL;DR, you lose nothing by installing qcodes++ ontop of qcodes, but hopefully gain a bunch of user-friendly features.

QCoDeS and qcodes++ are compatible with Python 3.9+. They are primarily intended for use
from Jupyter notebooks and Jupyter lab, but can also be used from Spyder, traditional terminal-based
shells and in stand-alone scripts.

The name: In addition to being a really stupid pun on q(c++), it reflects the fact that really we just want 
to add some nice features to the main package, and also it makes me happy because totally 
coincidentally we have always named our plotting windows pp, e.g. pp = qcpp.live_plot().

Note 1: These features actually used to be part of QCoDeS but were replaced by the database-based dataset.
In some sense, this package is an 'OG' qcodes; it may be more limited on the backend, but those limitations 
mean we have instead been able to focus on things like user-friendliness and making cool plotting tools.

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


