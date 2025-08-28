import qcodespp as qc
import numpy as np

class ZISampleParam(qc.MultiParameter):
    """
    MultiParameter containing various parts of a ZI lockin sample reading.
    
    ZI lockins enable making a single reading for X, Y, R, phase, etc. 
    Leverage that to make a single reading and return as many pieces as the user wishes.
    The advantage is that the communication time scales linearly with the number of times 
    the lockin is called; i.e. individually reading X, Y, R, and phase would take four times 
    longer than using this approach.

    Should work for any ZI lockin, using either the zhinst-qcodes or qcodespp drivers.

    Args:
        name (str): The name of the parameter.
        sample (callable): The .sample method of the ZI lock-in amplifier.
        unit (Opt, str): The unit for the demodulator input. Default is 'V'.
        ai1unit (Opt, str): The unit for auxin0 readings (default is 'V').
        ai2unit (Opt, str): The unit for auxin1 readings (default is 'V').
        components (Opt, list of strings): The components to include in the reading. 
            Accepts any of the values returned by the sample (default is 'x', 'y', 'r', 'phase').
        gain (Opt, float): Scaling factor to apply to X, Y, R (default is 1).
        ai0gain (Opt, float): Scaling factor to apply to auxin0 (default is 1).
        ai1gain (Opt, float): Scaling factor to apply to auxin1 (default is 1).

    Usage:
        Current = ZISampleParam('Current', 
                                li_a.demod0_sample, 
                                unit='A', 
                                components=['r', 'phase'],
                                gain=1e-6
                                )
        station.set_measurement(Current)
    """
    def __init__(self, name, sample, unit='V', ai1unit='V', ai2unit='V', 
                 components=['x', 'y', 'r', 'phase'], gain=1.0, ai0gain=1.0, ai1gain=1.0):
        for comp in components:
            if comp not in ['x', 'y', 'r', 'phase', 'timestamp', 'frequency', 
                            'auxin0', 'auxin1', 'dio', 'trigger']:
                raise ValueError("components must be a list containing any of "
                                "'x', 'y', 'r', 'phase', 'timestamp', 'frequency', "
                                "'auxin0', 'auxin1', 'dio', 'trigger'")
        names=[f'{name}_{comp}' for comp in components]
        units=[]
        for nn in names:
            if nn.endswith('phase'):
                units.append('rad')
            elif nn.endswith('timestamp'):
                units.append('s')
            elif nn.endswith('frequency'):
                units.append('Hz')
            elif nn.endswith('auxin0'):
                units.append(ai1unit)
            elif nn.endswith('auxin1'):
                units.append(ai2unit)
            elif nn.endswith('dio') or nn.endswith('trigger'):
                units.append('')
            else:
                units.append(unit)

        super().__init__(
            name,
            names=tuple(names),
            shapes=tuple([() for _ in range(len(names))]),
            labels=tuple(names),
            units=tuple(units),
            docstring=("MultiParameter that returns specified components of a ZI lockin sample reading."),
        )

        self.gain = gain
        self.ai0gain = ai0gain
        self.ai1gain = ai1gain
        self._sample = sample
        self._meta_attrs.extend(['gain', 'ai0gain', 'ai1gain'])
        if sample.instrument is not None:
            self._inst_name = sample.instrument.name
            self._inst_class = sample.instrument.__class__
            self._meta_attrs.extend(['_inst_name', '_inst_class'])
            try:
                self._inst_serial = sample.instrument.serial
                self._meta_attrs.append('_inst_serial')
            except AttributeError:
                pass

    def get_raw(self):
        sam=self._sample()
        sam['r']=np.sqrt(sam['x']**2 + sam['y']**2)
        to_return=[]
        for nn in self.names:
            suffix=nn.split('_')[-1]
            if suffix in ['x', 'y', 'r']:
                to_return.append(sam[suffix][0]*self.gain)
            elif suffix=='auxin0':
                to_return.append(sam[suffix][0]*self.ai0gain)
            elif suffix=='auxin1':
                to_return.append(sam[suffix][0]*self.ai1gain)
            else:
                to_return.append(sam[suffix][0])
        return tuple(to_return)

class R4ptParam(qc.MultiParameter):
    """
    MultiParameter to return current, voltage and resistance based on two ZI lockin readings.
    
    ZI lockins enable making a single reading for X, Y, R, phase. 
    Leverage that to make a single reading for each of two lockins to return all relevant parameters: 
    Currents X Y R P, Voltages X Y R P, and computed resistances X Y R. 
    Basically requires only two communication instances instead of 14. 
    Phase not returned for resistance since it's not obvious what that means. 
    If currents are exactly zero, resistance returns NaN.

    Should work for any ZI lockin, using either the zhinst-qcodes or qcodespp drivers.

    Args:
        li_a_sample (callable): The .sample method of the current-reading lock-in amplifier.
        li_b_sample (callable): The .sample method of the voltage-reading lock-in amplifier.
        current_gain (float): Gain on the current preamplifier (default is 1e-6).
        voltage_gain (float): Gain on the voltage preamplifier (default is 1e-3).
        include_R (bool): Whether to include amplitude values in the output (default is True).
        include_phase (bool): Whether to include phase values in the output (default is True).
        name (str): The name of the parameter (default is 'R4pt').

    Usage:
        R4pt = R4ptParam(li_a.demod0_sample, li_b.demod0_sample,1e-6,1e-3)
        station.set_measurement(R4pt)
    """
    def __init__(self,li_a_sample,li_b_sample,
                current_gain=1e-6,voltage_gain=1e-3,
                include_R=True,include_phase=True,
                name='R4pt'):
        
        names=['CurrentX','CurrentY','CurrentR','CurrentP',
                    'VoltageX','VoltageY','VoltageR','VoltageP',
                    'ResistanceX','ResistanceY','ResistanceR']
        if not include_R:
            names.remove('CurrentR')
            names.remove('VoltageR')
            names.remove('ResistanceR')
        if not include_phase:
            names.remove('CurrentP')
            names.remove('VoltageP')
        units=[]
        for nn in names:
            if nn.endswith('P'):
                units.append('rad')
            elif 'Current' in nn:
                units.append('A')
            elif 'Voltage' in nn:
                units.append('V')
            elif 'Resistance' in nn:
                units.append('Ohm')

        super().__init__(
            name,
            names=tuple(names),
            shapes=tuple([() for _ in range(len(names))]),
            labels=tuple(names),
            units=tuple(units),
            docstring=("MultiParameter that reads all necessary values from two "
                        "ZI lockins to compute a 4 point resistance."),
        )

        self._current_gain = current_gain
        self._voltage_gain = voltage_gain
        self._li_a_sample=li_a_sample
        self._li_b_sample=li_b_sample
        self._include_R=include_R
        self._include_phase=include_phase
        self._meta_attrs.extend(['_current_gain','_voltage_gain'])
        for i,sample in zip(['a','b'],[li_a_sample, li_b_sample]):
            if sample.instrument is not None:
                setattr(self, f'_inst_{i}_name', sample.instrument.name)
                setattr(self, f'_inst_{i}_class', sample.instrument.__class__)
                self._meta_attrs.extend([f'_inst_{i}_name', f'_inst_{i}_class'])
                try:
                    setattr(self, f'_inst_{i}_serial', sample.instrument.serial)
                    self._meta_attrs.append(f'_inst_{i}_serial')
                except AttributeError:
                    pass

    def get_raw(self):
        Isam=self._li_a_sample()
        Vsam=self._li_b_sample()
        Ix=Isam['x'][0]*self._current_gain
        Iy=Isam['y'][0]*self._current_gain
        Ir=np.sqrt(Ix**2+Iy**2)
        Ip=Isam['phase'][0]
        Vx=Vsam['x'][0]*self._voltage_gain
        Vy=Vsam['y'][0]*self._voltage_gain
        Vr=np.sqrt(Vx**2+Vy**2)
        Vp=Vsam['phase'][0]
        if Ix!=0:
            Rx=Vx/Ix
        else:
            Rx=np.nan
        if Iy!=0:
            Ry=Vy/Iy
        else:
            Ry=np.nan
        if Ir!=0:
            Rr=Vr/Ir
        else:
            Rr=np.nan

        if self._include_R and self._include_phase:
            return(Ix,Iy,Ir,Ip,Vx,Vy,Vr,Vp,Rx,Ry,Rr)
        elif self._include_R:
            return(Ix,Iy,Ir,Vx,Vy,Vr,Rx,Ry,Rr)
        elif self._include_phase:
            return(Ix,Iy,Ip,Vx,Vy,Vp,Rx,Ry)
        else:
            return(Ix,Iy,Vx,Vy,Rx,Ry)