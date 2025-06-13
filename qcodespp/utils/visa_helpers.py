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
        try:
            res=resman.open_resource(resource)
            print(f'Instrument IDN: {res.query('*IDN?')} VISA Address: {resource}\n')
        except:
            for baudrate in baudrates:
                connected=False
                try:
                    res=resman.open_resource(resource)
                    res.baud_rate=baudrate
                    print(f'Instrument IDN: {res.query('*IDN?')} VISA Address: {resource}\n')
                    connected=True
                    break
                except Exception as e:
                    pass
                finally:
                    res.baud_rate=9600
            if connected==False:
                print(f'Cannot access instrument with address {resource}. Likely the instrument '
                    'is already connected, possibly in another program or ipython kernel.\n')