qcodes++
===================================

qcodes++ (aka qcodespp, qcpp, qc++) is a python package to run scientific experiments. qcodes++ is built on top of `QCoDeS <https://qcodes.github.io/Qcodes/>`__, both extending capabilities and preserving older features.

QCoDeS is a Python-based data acquisition framework developed by the
Copenhagen / Delft / Sydney / Microsoft quantum computing consortium.
It contains a huge range of drivers for communicating with instruments,
and a flexible - but complex - database-based method for collecting data
and running measurement loops.

The qcodes++ package provides a user-friendly
frontend to the solid backend of QCoDeS. If you have always wanted to run 
your measurements using python but found QCoDeS too daunting, qcodes++ is 
the package for you. qcodes++ features

* Text-based data (i.e. readable by e.g. notepad, excel, origin pro, etc)
* A simple yet powerful method for taking data and running measurements and loops
* True live plotting and an integrated offline plotting/analysis tool
* Improvements to core qcodes functions (e.g. Station, Parameters) to streamline data acquisition, protect (meta)data integtrity and minimise user error
* Improved drivers for certain instruments
* and other user-friendliness improvements

`qcodes++ is installed alongside/around QCoDeS <https://qcodespp.github.io/differences_from_qcodes.html>`__, meaning all features of both packages can be used 
seamlessly within the same notebook/environment. e.g. you could still use the QCoDeS 
dataset and measurement process for some experiments while relying on qcodes++ in other instances.
In addition, all top level qcodes functions are available in qcodes++ with the same names.

The name: In addition to being a really stupid pun on q(c++), it reflects the fact that really we just want 
to add some nice features to the main package, and also it makes me happy because totally 
coincidentally we have always named our plotting windows pp, e.g. pp = qc.live_plot().

Documentation
=============
is available at https://qcodespp.github.io

Installation
============

See https://qcodespp.github.io/installation.html

QCoDeS and qcodes++ are compatible with Python 3.9+. They are primarily intended for use
from Jupyter notebooks and Jupyter lab, but can also be used from Spyder, traditional terminal-based
shells and in stand-alone scripts.

License
=======

See `License <https://github.com/QCoDeS/Qcodes/tree/master/LICENSE.rst>`__.

Contact and contributing
==================================================

This package is largely maintained by Damon Carrad. If you have a question, or want to contribute, please don't hesitate to contact me at damonc@dtu.dk. Note I'm mainly doing it in my spare time, but I will always try to help.