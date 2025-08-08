import pyvisa

def listVISAinstruments(baudrates='qdac'):
    """
    List the VISA instruments connected to the computer. Deault baudrates checked are 9600 and 921600.

    Args:
        baudrates (int, str, list): The baudrate(s) to check for the instruments.
            - If an integer, it will check only that baudrate.
            - If a string, it can be 'qdac', 'standard', or 'all' to use predefined baudrate lists.
            - If a list, it should contain integers representing the baudrates to check.
    Returns:
        None: Prints the list of instruments and their identification strings.
    
    Details:
        If you are expecting instrument(s), e.g. QDAC, to communicate with a baudrate other than 9600,
        you can include the possible baudrates when calling the function. By default it also checks for the
        baudrate used by the qdac. If you want to check other baudrates, include them explicitly as a list,
        or use predefined lists 'standard' or 'all', with baudrates defined according the National Instruments standards.
    """
    baudrate_library={'qdac':[921600],
                'standard':[460800,230400,115200,57600,38400,19200,14400,4800,2400,1200,600,300],
                'all':[921600,256000,153600,128000,56000,28800,110,460800,230400,115200,57600,38400,19200,14400,4800,2400,1200,600,300]}

    if type(baudrates) is int:
        if baudrates not in baudrate_library['all']:
            print(f'{baudrates} is not usually a supported baudrate: Check for typo')
        baudrates=[baudrates]
    elif type(baudrates) is str:
        if baudrates in ['qdac','standard','all']:
            baudrates=baudrate_library[baudrates]
        else:
            raise ValueError('baudrates must be one of \'qdac\', \'standard\' or \'all\' if providing string')
    elif type(baudrates) is list:
        for baudrate in baudrates:
            if baudrate not in baudrate_library['all']:
                print(f'{baudrate} is not usually a supported baudrate: Check for typo')
    else:
        raise TypeError('baudrates must be either an integer, list of integers, or one of \'qdac\', \'standard\' or \'all\'')

    resman=pyvisa.ResourceManager()
    for resource in resman.list_resources():
        res=False
        connected=False
        e1=''
        e2=''
        try:
            res=resman.open_resource(resource)
            idn=res.query('*IDN?')
            print(f'Instrument IDN: {idn} VISA Address: {resource}\n')
        except Exception as e1:
            for baudrate in baudrates:
                try:
                    res=resman.open_resource(resource)
                    res.baud_rate=baudrate
                    print(f'Instrument IDN: {res.query('*IDN?')} VISA Address: {resource}\n')
                    connected=True
                    break
                except Exception as e:
                    e2=e
                    pass
                finally:
                    res.baud_rate=9600
            if connected==False:
                print(f'Instrument with address {resource} raised exceptions:\n {e1}\n{e2}\n'
                    'Possible causes: the instrument does not accept the \'IDN?\' command (e.g. it does not use SCPI, '
                    'it is a composite instrument), or it '
                    'is already connected, possibly in another program or ipython kernel.\n'
                    'Or, there is another problem with the instrument configuration, use the exceptions to guide you.')
        if res:
            res.close()