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
Comprehensive documentation, including examples is available at https://qcodespp.github.io

Installation
============

See https://qcodespp.github.io/installation.html

License
=======

See `License <https://github.com/QCoDeS/Qcodes/tree/master/LICENSE.rst>`__.

Contact and contributing
==================================================

This package is largely maintained by Damon Carrad. If you have a question, or want to contribute, please don't hesitate to contact me at damonc@dtu.dk. Note I'm mainly doing it in my spare time, but I will always try to help.