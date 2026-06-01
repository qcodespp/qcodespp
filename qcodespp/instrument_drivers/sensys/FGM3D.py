import logging
import time
from functools import partial
import serial

from qcodes import Instrument, MultiParameter

log = logging.getLogger(__name__)

class FGM3D(Instrument):
    '''
    QCoDeS driver to capture data stream from a Sensys FGM3D TD digitzer application

    The driver does not communicate directly with the instrument; it is only capable of reading 
    the data stream sent from the 'Live Streaming' section of the GUI. You must set up a virtual COM 
    port pair using e.g. https://freevirtualserialports.com/. Specify the first port in the GUI, and 
    the second port in this driver.

    The units cannot be read from the instrument; if using Gauss, specify this during init.

    Args:
        name (str): qcodes name for this instrument instance
        address (str): COM port identifier of the virtual COM port pair
    '''

    def __init__(self, name, address, baudrate=115200, unit='T', terminator='\r\n', timeout=5, **kwargs):

        self.ind_dict={'x':0,
            'y':1,
            'z':2,
            'r':3}
        
        super().__init__(name, **kwargs)
        self.terminator=terminator
        self.address=address
        self.unit=unit
        self.timeout=timeout
        self.ser=serial.Serial(address, baudrate=baudrate)

        for axis in ['x','y','z','r']:
            self.add_parameter(axis,
                                  label=f'B{axis}',
                                  unit=self.unit,
                                  get_cmd=partial(self._get_cmpt,axis))
            
        self.add_parameter(name='data',
                           unit=self.unit,
                           parameter_class=FGM3D_Parameter)

    def get_idn(self):
        return "Sensys FGM3D"
    
    def get_data(self):
        start=time.time()
        while time.time()-start<self.timeout:
            try:
                raw_data=self.ser.read_all().decode().split(self.terminator)[-2]
                t,x,y,z,r=raw_data.split(';')
                return (float(x),float(y),float(z),float(r))
            except:
                0
        return TimeoutError(f'Data could not be returned before timeout = {self.timeout}s')
    
    def _get_cmpt(self,axis):
        return self.get_data()[self.ind_dict[axis]]
        
class FGM3D_Parameter(MultiParameter):
    def __init__(self,name,unit,instrument):
        names=['Bx','By','Bz','Br']
        shapes=((),(),(),())
        units=[unit for i in range(4)]
        super().__init__(name=name,names=names,shapes=shapes,units=units,instrument=instrument)
    
    def get_raw(self):
        return self.instrument.get_data()
                        