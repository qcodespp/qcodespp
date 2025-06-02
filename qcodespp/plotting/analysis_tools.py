#Useful functions developed over the years to speed up various analysis tasks

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


def colourplot(data,figsize=0,cmap=0,labels=0,xlim=0,ylim=0,zlim=0,xmajor=0,xminor=0,ymajor=0,yminor=0,font_size=0,label_size=0):
    """
    Make a nice colourplot from a three-dimensional data array using matplotlib. 
    
    Args:
        data (list or array): A list or array containing three elements: [x, y, z], where:
            - x: 1D or 2D array of x-coordinates
            - y: 1D or 2D array of y-coordinates
            - z: 2D array of z-values corresponding to the x and y coordinates.

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

    if zlim!=0:
        sdbs=ax1.pcolormesh(data[0],data[1],data[2],cmap=cmap,rasterized=True,linewidth=0,vmin=zlim[0],vmax=zlim[1])
    else:
        sdbs=ax1.pcolormesh(data[0],data[1],data[2],cmap=cmap,rasterized=True,linewidth=0)
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
