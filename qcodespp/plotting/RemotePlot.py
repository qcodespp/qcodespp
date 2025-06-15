import subprocess
import threading
import os

import numpy as np
import zmq
import json
from uuid import uuid4

from qcodespp.data.data_set import DataSetPP
from qcodespp.data.data_array import DataArray
from qcodespp.utils.helpers import NumpyJSONEncoder
from qcodespp.parameters import Parameter

def live_plot(*args,data_set=None, data_items=None):
    """
    Entry point for live plotting of qcodespp data.

    Args:
        *args (DataSetPP, DataArray, Parameter, list, tuple): Positional arguments can be:
            - ``DataSetPP``: The dataset to link to the live plot.
            - ``DataArray`` or ``Parameter``: The data items to plot.
            - A list or tuple of ``DataArray`` or ``Parameter`` objects to plot.
        data_set (``DataSetPP``, optional): The ``DataSetPP`` to link to the live plot.
            If not provided, it will try to use the default dataset.
            If no data_set, one can add items to the plot, but the data will not be tracked.
        data_items (Sequence[``DataArray``, ``Parameter``], optional): List of ``DataArray``
            or ``Parameter`` objects to plot. If not provided, nothing will be plotted initially,
            the user can use ``Plot.add()`` later.

    Returns:
        The ``Plot`` instance.
    """

    if data_items is None:
        data_items = []

    for arg in args:
        if isinstance(arg, DataSetPP):
            data_set = arg
        elif isinstance(arg, (DataArray, Parameter)):
            data_items.append(arg)
        elif isinstance(arg, (list, tuple)):
            data_items.extend(arg)

    plot = Plot()
    if data_set is None and DataSetPP.default_dataset is not None:
        data_set = DataSetPP.default_dataset
    if data_set:
        data_set.publisher=plot
    if data_items:
        new_items=[]
        for item in data_items:
            if isinstance(item, Parameter) and not data_set:
                raise ValueError('Parameters only accepted to data_items if a data_set is also provided.')
            elif isinstance(item, Parameter):
                for array in data_set.arrays:
                    if item.full_name in array:
                        new_items.append(data_set.arrays[array])
            elif isinstance(item, DataArray):
                new_items.append(item)
                if not data_set:
                    try: # Try ONE more time to link some kind of data set to the plot.
                        item.data_set.publisher = plot
                    except:
                        pass
            else:
                raise TypeError('data_items must be either DataArray or Parameter objects, not %s.' % type(item))
        plot.add_multiple(*new_items)

    return plot

class ControlListener(threading.Thread):
    """
    ListenToClientTask
    """
    def __init__(self, client_ready_event=None, port=8876):
        self.client_ready_event = client_ready_event
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)

        self.port = self.socket.bind_to_random_port('tcp://*',
                                                    min_port=port,
                                                    max_port=port+500,
                                                    max_tries=500)

        self.socket.setsockopt(zmq.SUBSCRIBE, b'')

        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

        threading.Thread.__init__(self)

        self.running = True

    def run(self):
        while self.running:
            socks = dict(self.poller.poll(1000))
            if socks.get(self.socket) == zmq.POLLIN:
                try:
                    msg = self.socket.recv_json()
                    ready = msg.get('client_ready', None)
                    if ready is True:
                        self.client_ready_event.set()
                    else:
                        pass
                        # print(msg)
                except Exception:
                    print('ups ups ups')

        self.socket.close()
        self.context.term()


class Plot():
    """
    Class to create live plot instances.

    Most methods of this class should not be called directly; only add(), add_multiple(), clear() and close()
    should be used by the user.

    Args:
        title (str, optional): Title of the plot window.
        name (str, optional): Name of the plot instance. If not provided, a random UUID will be used.
    """

    context = zmq.Context()
    socket = context.socket(zmq.PUB)

    port = 8876
    port = socket.bind_to_random_port('tcp://*',
                                      min_port=port,
                                      max_port=port+20,
                                      max_tries=100)
    encoding = 'utf-8'

    def __init__(self, title=None, name=None):
        name = name or uuid4().hex
        topic = 'qcodes.plot.'+name
        self.topic = topic
        self.metadata = {}
        self.data_uuid = uuid4().hex

        self.client_ready_event = threading.Event()
        self.client_ready_event.clear()

        self.control_task = ControlListener(self.client_ready_event)
        self.control_task.start()
        self.control_port = self.control_task.port

        self.new_client()

        ret = self.client_ready_event.wait(30)
        if ret == False:
            print('timeout for plot window.')
        self.client_ready_event.clear()

        self.set_title(title)

    def publish(self, data, uuid=None):
        jdata = json.dumps(data, cls=NumpyJSONEncoder)
        uuid = uuid or ''
        self.socket.send_multipart([self.topic.encode(self.encoding),
                                    uuid.encode(self.encoding),
                                    jdata.encode(self.encoding)])

    def publish_data(self, data, uuid, meta, arrays):
        jdata = json.dumps(data)
        uuid = uuid or ''
        jmeta = json.dumps(meta)
        self.socket.send_multipart([self.topic.encode(self.encoding),
                                    uuid.encode(self.encoding),
                                    jdata.encode(self.encoding),
                                    jmeta.encode(self.encoding),
                                    *arrays])

    def add_metadata(self, new_metadata, uuid=None):
        data = {'metadata': new_metadata}
        self.publish(data, uuid)

    def store(self, loop_indices, ids_values, uuid):
        data = {'data': {'values': ids_values,
                         'indices': loop_indices}}
        self.publish(data, uuid)

    def save_metadata(self, metadata, uuid=None):
        self.add_metadata(metadata, uuid)

    def finalize(self, uuid=None):
        self.publish({'finalize': True}, uuid)

    def new_client(self, name=None):
        this_dir, this_filename = os.path.split(__file__)
        client = os.path.join(this_dir, 'RemotePlotClient.py')
        args = ['python',
                client,
                self.topic,
                str(self.port),
                str(self.control_port)]

        print(' '.join(args))

        DETACHED_PROCESS = 0x00000008

        subprocess.Popen(args, creationflags=DETACHED_PROCESS)

    def clear(self):
        self.publish({'clear_plot': True})

    def add_multiple(self,*z_params):
        """Add multiple ``DataArray`` s to the ``Plot``.
        
        Args:
            *z_params (Sequence [DataArray]): DataArrays to be added to the Plot.
                Each DataArray is added to a separate subplot.
        """
        for i,z_param in enumerate(z_params):
            self.add(z_param,subplot=i) #title=z_param.full_name,name=z_param.name,

    def add(self, *args, x=None, y=None, z=None,
            subplot=0, name=None, title=None, position=None,
            relativeto=None, xlabel=None, ylabel=None, zlabel=None,
            xunit=None, yunit=None, zunit=None, silent=True,linecuts=False,
            symbol=None,#color=None, width=None, pen=False, brush=None,
            size=None,# antialias=None,
            **kwargs):
        """
        Add a trace to the plot.

        Args:
            *args (DataArray): positional arguments, can be:
                - ``y`` or ``z``: specify just the 1D or 2D data independent parameter, with the setpoint
                    axis or axes implied from the DataSetPP setpoints.
                - ``x, y`` or ``x, y, z``: specify all axes of the data.
            x (DataArray, optional): x-axis data.
            y (DataArray, optional): y-axis data.
            z (DataArray, optional): z-axis data.
            subplot (int, optional): Subplot index to add the trace to. Defaults to 0.
            name (str, optional): Name of the trace. If not provided, the name of the DataArray will be used.
            title (str, optional): Title of the trace. If not provided, the name of the DataArray will be used.
            position (str): Position of the subplot in the plot window. Options are 'bottom', 'top', 'left', 'right', 'above', or 'below'.
            relativeto (str, optional): Position relative to which the subplot should be placed.
            xlabel (str, optional): Label for the x-axis. If not provided, the label of the DataArray will be used.
            ylabel (str, optional): Label for the y-axis. If not provided, the label of the DataArray will be used.
            zlabel (str, optional): Label for the z-axis. If not provided, the label of the DataArray will be used.
            xunit (str, optional): Unit for the x-axis. If not provided, the unit of the DataArray will be used.
            yunit (str, optional): Unit for the y-axis. If not provided, the unit of the DataArray will be used.
            zunit (str, optional): Unit for the z-axis. If not provided, the unit of the DataArray will be used.
            silent (bool, optional): If True, do not wait for the client to be ready. Defaults to True.
            linecuts (bool, optional): If True, plot line cuts instead of a 2D image. Defaults to False.
            symbol (str, optional): Symbol to use for the trace. Defaults to None.
            size (int, optional): Size of the symbol. Defaults to None.
        """

        if x is not None:
            kwargs['x'] = x
        if y is not None:
            kwargs['y'] = y
        if z is not None:
            kwargs['z'] = z

        kwargs['xlabel'] = xlabel
        kwargs['ylabel'] = ylabel
        kwargs['zlabel'] = zlabel
        kwargs['xunit'] = xunit
        kwargs['yunit'] = yunit
        kwargs['zunit'] = zunit
        kwargs['name'] = name

        self.expand_trace(args, kwargs)

        x = kwargs.get('x', None)
        y = kwargs.get('y', None)
        z = kwargs.get('z', None)

        uuid = None

        arguments = {'subplot': subplot,
                     'title': title,
                     'position': position,
                     'relativeto': relativeto,
                     'linecuts':linecuts,
                     'symbol': symbol,
                     'size': size}#,
                     # 'color': color,
                     # 'width': width,
                     # 'pen': pen,
                     # 'brush': brush,
                     # 'size': size,
                     # 'antialias': antialias}

        meta = []
        arrays = []

        uuid = self.data_uuid

        snap_name = None

        for arr_name, arr in zip(['x', 'y', 'z'], [x, y, z]):


            shape = None
            location = None
            array_id = None
            unit = None
            label = None

            if arr is not None:
                if isinstance(arr, DataArray):
                    snap = arr.snapshot()
                    uuid = arr.data_set.uuid

                    location = getattr(arr.data_set, 'location', None)
                    label = snap.get('label', None)
                    if snap.get('unit',None) is not None:
                        unit = snap.get('unit', None)
                    elif snap.get('units', None) is not None:
                        unit = snap.get('units',None)
                    snap_name = snap.get('name', None)
                    shape = snap.get('shape', None)
                    array_id = arr.array_id
                else:
                    array_id = uuid4().hex


            unit = kwargs.get('%sunit'%arr_name, None) or unit
            label = kwargs.get('%slabel'%arr_name, None) or label

            arguments['%s_info'%arr_name] = {}
            arguments['%s_info'%arr_name]['location'] = location
            arguments['%s_info'%arr_name]['label'] = label
            arguments['%s_info'%arr_name]['unit'] = unit
            arguments['%s_info'%arr_name]['shape'] = shape
            arguments['%s_info'%arr_name]['name'] = snap_name or name
            arguments['%s_info'%arr_name]['array_id'] = array_id
            arguments['name'] = name or snap_name

        for arr_name, arr in zip(['x', 'y', 'z'], [x, y, z]):
            if arr is not None:
                if isinstance(arr, DataArray):
                    ndarr = arr.ndarray
                if isinstance(arr, np.ndarray):
                    ndarr = arr
                else:
                    try:
                        ndarr = np.array(arr)
                    except:
                        continue

                if (~np.isnan(ndarr)).any():
                    arrays.append(ndarr)
                    arguments['%s_info'%arr_name]['shape'] = ndarr.shape
                    arguments['%s_info'%arr_name]['name']

                    meta.append({'array_id': arguments['%s_info'%arr_name]['array_id'],
                                 'shape': ndarr.shape,
                                 'dtype': str(ndarr.dtype)})

        if len(arrays) > 0:
            self.publish_data({'add_plot': arguments},
                              uuid, meta, arrays)
        else:
            self.publish({'add_plot': arguments}, uuid)

        if not silent:
            # self.client_ready_event.clear()
            # return
            ret = self.client_ready_event.wait(30)
            if ret == False:
                print('plot timed out!')
            self.client_ready_event.clear()

    def expand_trace(self, args, kwargs):
        """
        Complete the x, y (and possibly z) data definition for a trace.

        Also modifies kwargs in place so that all the data needed to fully specify the
        trace is present (ie either x and y or x and y and z)

        Both ``__init__`` (for the first trace) and the ``add`` method support multiple
        ways to specify the data in the trace:

        As args:
            - ``add(y)`` or ``add(z)`` specify just the main 1D or 2D data, with the setpoint
              axis or axes implied.
            - ``add(x, y)`` or ``add(x, y, z)`` specify all axes of the data.
        And as kwargs:
            - ``add(x=x, y=y, z=z)`` you specify exactly the data you want on each axis.
              Any but the last (y or z) can be omitted, which allows for all of the same
              forms as with args, plus x and z or y and z, with just one axis implied from
              the setpoints of the z data.

        This method takes any of those forms and converts them into a complete set of
        kwargs, containing all of the explicit or implied data to be used in plotting this trace.

        Args:
            args (Tuple[DataArray]): positional args, as passed to either ``__init__`` or ``add``
            kwargs (Dict(DataArray]): keyword args, as passed to either ``__init__`` or ``add``.
                kwargs may contain non-data items in keys other than x, y, and z.

        Raises:
           ValueError: if the shape of the data does not match that of args
           ValueError: if the data is provided twice
        """
        # TODO(giulioungaretti): replace with an explicit version:
        # return the new kwargs  instead of modifying in place
        # TODO this should really be a static method
        if args:
            if hasattr(args[-1][0], '__len__'):
                # 2D (or higher... but ignore this for now)
                # this test works for both numpy arrays and bare sequences
                axletters = 'xyz'
                ndim = 2
            else:
                axletters = 'xy'
                ndim = 1

            if len(args) not in (1, len(axletters)):
                raise ValueError('{}D data needs 1 or {} unnamed args'.format(
                    ndim, len(axletters)))

            arg_axletters = axletters[-len(args):]

            for arg, arg_axletters in zip(args, arg_axletters):
                # if arg_axletters in kwargs:
                #     raise ValueError(arg_axletters + ' data provided twice')
                kwargs[arg_axletters] = arg

        # reset axletters, we may or may not have found them above
        axletters = 'xyz' if 'z' in kwargs else 'xy'
        main_data = kwargs.get(axletters[-1], None)

        if hasattr(main_data, 'set_arrays'):
            num_axes = len(axletters) - 1
            # things will probably fail if we try to plot arrays of the
            # wrong dimension... but we'll give it a shot anyway.
            set_arrays = main_data.set_arrays[-num_axes:]
            # for 2D: y is outer loop, which is earlier in set_arrays,
            # and x is the inner loop... is this the right convention?
            # Merlin: Not in my view, I step on x-axis and do many
            #         y-sweeps, thus removed this reversing here.
            set_axletters = axletters[:-1]
            for axletter, set_array in zip(set_axletters, set_arrays):
                if axletter not in kwargs:
                    kwargs[axletter] = set_array

    def set_title(self, title):
        self.publish({'set_title': title})

    def set_cmap(self, cmap):
        self.publish({'set_cmap': cmap})

    def save(self, filename=None, subplot=None):
        self.publish({'save_screenshot': {'filename': str(filename), 'subplot': subplot}})
        # print('Should save a screenshot of the plot now')

    def set_xlabel(self, label, subplot=0):
        print('Should set the x-label of a subplot now')

    def set_ylabel(self, label, subplot=0):
        print('Should set the y-label of a subplot now')

    def set_geometry(self, height, width, x0, y0):
        # like other qt takes it:
        print('Should set the geometry of the window now')

    def close(self):
        self.publish({'close_client': True})
        print('Should close the plot window now')
