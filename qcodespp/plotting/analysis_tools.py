'''
Useful functions for plotting in Jupyter notebooks using matplotlib.
'''

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np


def colorplot(x,y,z,figsize=0,cmap=0,labels=0,xlim=0,ylim=0,zlim=0,xmajor=0,
              xminor=0,ymajor=0,yminor=0,font_size=0,label_size=0,check_shapes=False):
    """
    Make a nice colourplot from a three-dimensional data array using matplotlib. 
    
    Args:
        
        x: 1D or 2D array of x-coordinates
        
        y: 1D or 2D array of y-coordinates
        
        z: 2D array of z-values corresponding to the x and y coordinates.
        
        figsize (tuple, optional): Size of the figure in inches. Default is (8, 8).
        
        cmap (str, optional): Colormap to use for the plot. Default is 'hot'.
        
        labels (list, optional): Labels for the x, y, and z axes. Default is ['x', 'y', 'z'].
        
        xlim (tuple, optional): Limits for the x-axis. Default is None.
        
        ylim (tuple, optional): Limits for the y-axis. Default is None.
        
        zlim (tuple, optional): Limits for the z-axis (color scale). Default is None.
        
        xmajor (float, optional): Major tick interval for the x-axis. Default is None.
        
        xminor (float, optional): Minor tick interval for the x-axis. Default is None.
        
        ymajor (float, optional): Major tick interval for the y-axis. Default is None.
        
        yminor (float, optional): Minor tick interval for the y-axis. Default is None.
        
        font_size (int, optional): Font size for the axis labels. Default is 12.
        
        label_size (int, optional): Font size for the tick labels. Default is 12.

        check_shapes (bool, optional): If True, checks the shapes of x, y, and z arrays and transposes if necessary. Default is False.

    Returns:
        tuple: A tuple containing the figure, axis, and colorbar axis objects.

    """
    plt.rcParams["font.family"] = "Arial"
    plt.rcParams['axes.linewidth'] = 1.5
    if font_size==0:
        font_size=12
    if label_size==0:
        label_size=12

    if figsize==0:
        figsize=(8,8)
    if cmap==0:
        cmap='hot'
    if labels==0:
        labels=['x','y','z']
    
    fig, (ax1, cax)=plt.subplots(nrows=1,ncols=2,figsize=figsize,dpi=300,gridspec_kw={'width_ratios':[1,0.02]}) #This allows us better control over the colourbar. Note you can then 'easily' generalise this to more subplots (see below)
    fig.tight_layout(h_pad=None, w_pad=-2)

    if check_shapes:
        if np.shape(z)[1] != np.shape(x)[0] and np.shape(z)[0] == np.shape(x)[0]:
            z= z.T
        if np.shape(np.shape(y))==(2,) and np.shape(y)[1] != np.shape(x)[0] and np.shape(y)[0] == np.shape(x)[0]:
            y= y.T

    if zlim!=0:
        sdbs=ax1.pcolormesh(x,y,z,cmap=cmap,rasterized=True,linewidth=0,vmin=zlim[0],vmax=zlim[1])
    else:
        sdbs=ax1.pcolormesh(x,y,z,cmap=cmap,rasterized=True,linewidth=0)
    fig.colorbar(sdbs, cax=cax, orientation='vertical')

    cax.yaxis.set_ticks_position('right')
    cax.tick_params(which='major', length=4, width=1, labelsize=label_size)
    cax.set_ylabel(labels[2], fontsize=font_size, labelpad=20, rotation=270)

    ax1.set_xlabel(labels[0], fontsize=font_size, labelpad=10)
    ax1.set_ylabel(labels[1], fontsize=font_size, labelpad=10)
    if xmajor!=0:
        ax1.xaxis.set_major_locator(MultipleLocator(xmajor))
    if xminor!=0:
        ax1.xaxis.set_minor_locator(MultipleLocator(xminor))
    if ymajor!=0:
        ax1.yaxis.set_major_locator(MultipleLocator(ymajor))
    if yminor!=0:
        ax1.yaxis.set_minor_locator(MultipleLocator(yminor))
    ax1.tick_params(axis='both', which='major', direction='out', length=10, width=1, labelsize=label_size)
    ax1.tick_params(axis='both', which='minor', direction='out', length=5, width=1, labelsize=label_size)
    if xlim!=0:
        ax1.set_xlim(xlim)
    if ylim!=0:
        ax1.set_ylim(ylim)
    
    return (fig,ax1,cax)

def colored_traces(x,y, offset=0,figsize=0, cmap=0, labels=0, xlim=0, ylim=0,style='-',
                    xmajor=0, xminor=0, ymajor=0, yminor=0, font_size=0, label_size=0):
    """
    Plot a series of 1D traces where the lines are colored according to a matplotlib colormap.

    Args:
        
        x: 1D or 2D array of x-coordinates
        
        y: 2D array of y-coordinates
        
        figsize (tuple, optional): Size of the figure in inches. Default is (8, 8).
        
        cmap (str, optional): Colormap to use for the plot. Default is 'hot'.
        
        labels (list, optional): Labels for the x, y, and z axes. Default is ['x', 'y', 'z'].
        
        xlim (tuple, optional): Limits for the x-axis. Default is None.
        
        ylim (tuple, optional): Limits for the y-axis. Default is None.
        
        xmajor (float, optional): Major tick interval for the x-axis. Default is None.
        
        xminor (float, optional): Minor tick interval for the x-axis. Default is None.
        
        font_size (int, optional): Font size for the axis labels. Default is 12.
        
        label_size (int, optional): Font size for the tick labels. Default is 12.


    Returns:
        tuple: A tuple containing the figure and axis objects.

    """
    plt.rcParams["font.family"] = "Arial"
    plt.rcParams['axes.linewidth'] = 1.5
    if font_size==0:
        font_size=12
    if label_size==0:
        label_size=12

    if figsize==0:
        figsize=(8,8)
    if cmap==0:
        cmap='viridis'
    if labels==0:
        labels=['x','y']

    fig, ax1 = plt.subplots(figsize=figsize,dpi=300)
    fig.tight_layout(h_pad=None)

    if np.shape(np.shape(x)) == (2,) and np.shape(x) != np.shape(y):
        raise TypeError('x needs to be either a 1D array, or a 2D array with the same shape as y')
    elif np.shape(np.shape(x)) == (1,):
        x = np.tile(x, (np.shape(y)[0], 1))
    
    colors= plt.get_cmap(cmap)(np.linspace(0.1,0.9, np.shape(y)[0]))
    for i in range(np.shape(y)[0]):
        ax1.plot(x[i], y[i]+offset*i, style,color=colors[i])

    ax1.set_xlabel(labels[0], fontsize=font_size, labelpad=10)
    ax1.set_ylabel(labels[1], fontsize=font_size, labelpad=10)
    if xmajor!=0:
        ax1.xaxis.set_major_locator(MultipleLocator(xmajor))
    if xminor!=0:
        ax1.xaxis.set_minor_locator(MultipleLocator(xminor))
    if ymajor!=0:
        ax1.yaxis.set_major_locator(MultipleLocator(ymajor))
    if yminor!=0:
        ax1.yaxis.set_minor_locator(MultipleLocator(yminor))
    ax1.tick_params(axis='both', which='major', direction='out', length=10, width=1, labelsize=label_size)
    ax1.tick_params(axis='both', which='minor', direction='out', length=5, width=1, labelsize=label_size)
    if xlim!=0:
        ax1.set_xlim(xlim)
    if ylim!=0:
        ax1.set_ylim(ylim)
    
    return (fig,ax1)

def sort_lists(X,Y):
    '''
    Sort two lists according to the ascending order of the first list.

    Args:
        X: List whose elements will be sorted in ascending order
        Y: List whose elements will be sorted according to the new order of X

    Returns
        (X,Y): The sorted lists
    '''
    newlist=[(x,y) for x,y in zip(X,Y)]
    newlist=sorted(newlist,key=lambda element: element[0])
    X=[newlist[i][0] for i,val in enumerate(newlist)]
    Y=[newlist[i][1] for i,val in enumerate(newlist)]
    return X,Y

def load_2d_json(filename):
    """
    Load reshaped 2D data exported from offline_plotting as a JSON file.

    Args:
        filename (str): Path to the JSON file.

    Returns:
        dict: A dictionary containing the reshaped data.
    """
    import json
    with open(filename, 'r') as f:
        data = json.load(f)

    shape= data.get('shape', None)
    data.pop('shape', None)  # Remove 'shape' from the data dictionary if it exists
    if shape:
        for key in data.keys():
            data[key]=np.array(data[key]).reshape(shape)
        return data
    
    else:
        raise ValueError("Cannot reshape data: The JSON file does not contain a shape entry.")