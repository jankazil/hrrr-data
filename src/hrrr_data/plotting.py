'''
Tools for plotting High Resolution Rapid Refresh (HRRR) data.
'''

import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter
from cartopy.mpl.ticker import LongitudeLocator, LatitudeLocator

from datetime import datetime,timedelta,timezone

from pathlib import Path

import matplotlib.pyplot as plt

import xarray as xr

def plot_geographic(
    hrrr_ds : xr.Dataset,
    hrrr_var : str,
    title: str = None,
    cbar_label: str = None,
    plot_path: Path = None,
    lon_min: float = None,
    lon_max: float = None,
    lat_min: float = None,
    lat_max: float = None,
    location_legends: list[str] = None,
    location_colors: list[str] = None,
    location_sizes: list[float] = None,
    location_lons: list[list[float]] = None,
    location_lats: list[list[float]] = None,
    cmap=None,
) -> None:
    
    '''
    Plot the geographic distribution of a High Resolution Rapid Refresh
    HRRR variable over the contiguous United States (CONUS) using a
    Lambert Conformal Conic projection.
    
    Optionally plots one or more group of locations given by their
    longitudes and latitudes, using a given color, location marker,
    and label per location group.
    
    Args:
        hrrr_ds : xarray.Dataset
            HRRR dataset containing:
            
                • The gridded variable `hrrr_var` with attributes:
                  
                  - 'initial_time' as '%m/%d/%Y (%H:%M)'
                  - 'forecast_time_units' equal to 'hours'
                  - 'forecast_time' as an integer-like hours offset
                  - 'long_name' and 'units' for labeling
                • 2D coordinate fields 'gridlat_0' (latitudes) and 'gridlon_0' (longitudes).
            
        hrrr_var : str
            Name of the HRRR variable in `hrrr_ds` to plot.
            
        title : str, optional
            Figure title. If omitted, a title will be constructed from the HRRR
            initialization time and forecast lead.
            
        cbar_label : str, optional
            Colorbar label text. If omitted, will use '<long_name> (<units>)' from
            the variable attributes.
            
        plot_path : pathlib.Path, optional
            If provided, the figure will be saved to this path (parent directories
            will be created as needed). No file is saved if `plot_path` is None.
    
        lon_min : float, optional
            Western longitude bound (degrees) for the map extent. Used only if all four
            of lon_min, lon_max, lat_min, and lat_max are provided.
            
        lon_max : float, optional
            Eastern longitude bound (degrees) for the map extent.
            
        lat_min : float, optional
            Southern latitude bound (degrees) for the map extent.
            
        lat_max : float, optional
            Northern latitude bound (degrees) for the map extent.
            
        location_legends : sequence type[str], optional
            One legend label per location group. Must align with the lengths of
            `location_colors`, `location_sizes`, `location_lons`, and `location_lats`.
            
        location_colors : sequence type[str], optional
            One color specification per location group (for example, 'k', '#1f77b4').
            
        location_sizes : sequence type[float], optional
            One marker size (points) per location group.
            
        location_lons : sequence type[sequence type[float]], optional
            Longitudes for each location group. The outer sequence indexes groups; the
            inner sequences hold the group members.
            
        location_lats : sequence type[sequence type[float]], optional
            Latitudes for each location group. Shapes must mirror `location_lons`.
            
    cmap : str, matplotlib.colors.Colormap, or None, optional
            Colormap to use for mapping data values to colors. Can be the name of a
            Matplotlib colormap (e.g. 'viridis', 'plasma', 'coolwarm'), or a
            `matplotlib.colors.Colormap` object. If None (default), the current
            Matplotlib default colormap (`viridis`) is used.            
    
    Returns:
        None
        
    Notes:
        location plotting expects all of the following to be provided together:
        `location_legends`, `location_colors`, `location_sizes`, `location_lons`, and
        `location_lats`. Each position i across these sequences defines one location
        group that will be plotted and labeled in the legend.
    '''
    
    #
    # Data and coordinates
    #
    
    data = hrrr_ds[hrrr_var]
    lat = hrrr_ds['gridlat_0']
    lon = hrrr_ds['gridlon_0']
    
    # Identify initialization time, forecast lead time, and forecast valid time
    
    forecast_init_time = datetime.strptime(hrrr_ds[hrrr_var].attrs['initial_time'], "%m/%d/%Y (%H:%M)")
    forecast_init_time = forecast_init_time.replace(tzinfo=timezone.utc)
    
    assert hrrr_ds[hrrr_var].attrs['forecast_time_units'] == 'hours', 'Forecast period units must be hours'
    forecast_lead_time_hours = int(hrrr_ds[hrrr_var].attrs['forecast_time'])
    
    forecast_time = forecast_init_time + timedelta(hours = forecast_lead_time_hours)
    
    #
    # Plot
    #
    
    # Title
    
    if title is None:
      title = 'HRRR, ' + 'initialization time = ' + forecast_init_time.isoformat() + ', forecast time (+' + str(forecast_lead_time_hours) + ' h) = ' + forecast_time.isoformat()
    
    # Colorbar title
    
    if cbar_label is None:
        cbar_label = data.attrs['long_name'] + ' (' + data.attrs['units'] + ')'
    
    # Use Lambert Conformal Conic projection with HRRR parameters
    
    hrrr_proj = ccrs.LambertConformal(
        central_longitude=-97.5,
        central_latitude=38.5,
        standard_parallels=(38.5, 38.5)
    )
    
    # Create figure
    
    fig, ax = plt.subplots(figsize = (11.15,8),subplot_kw={'projection': hrrr_proj})
    
    # Create plot area
    
    ax.set_title(title, fontsize=11.15)
    
    # Plot the data - the meaning of "PlateCarree" here is only that the coordinates are latitude and longitude
    
    mesh = ax.pcolormesh(lon, lat, data, transform=ccrs.PlateCarree(),shading='auto',cmap=cmap)
    
    # Plot boundaries
    if (lon_min is not None and
        lon_max is not None and
        lat_min is not None and
        lat_max is not None
        ):
        ax.set_extent([lon_min,lon_max,lat_min,lat_max], crs=ccrs.PlateCarree())
    
    #
    # Color bar
    #
    
    # Get the position of the map axes
    
    pos = ax.get_position()
    
    # Create a new axes for the colorbar next to the map, matching its vertical extent
    
    cbar_ax = fig.add_axes([pos.x1 + 0.015, pos.y0, 0.02, pos.height])
    
    # Create colorbar
    
    cbar = fig.colorbar(mesh, cax=cbar_ax)
    cbar.set_label(cbar_label, fontsize=12)
    cbar.ax.tick_params(labelsize=12)
    
    #
    # Add coastlines or other geographic features
    #
    
    ax.coastlines(linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.25)
    ax.add_feature(cfeature.STATES, linewidth=0.25)
    
    #
    # Gridlines
    #
    
    gl = ax.gridlines(
        draw_labels=True,
        linewidth=0.5,
        color='black',
        alpha=1.0,
        linestyle='--'
    )
    
    # Grid labels on the axes (not inline on the map)
    
    gl.x_inline = False
    gl.y_inline = False
    gl.bottom_labels = True
    gl.left_labels = True
    gl.top_labels = False
    gl.right_labels = False
    
    # Choose where lines go
    
    gl.xlocator = LongitudeLocator(nbins=6)
    gl.ylocator = LatitudeLocator(nbins=6)
    
    # Nice degree formatting
    
    gl.xformatter = LongitudeFormatter(number_format='.0f', degree_symbol='°')
    gl.yformatter = LatitudeFormatter(number_format='.0f', degree_symbol='°')
    
    # Force horizontal labels
    
    gl.xlabel_style = {'rotation': 0, 'ha': 'center', 'va': 'top', 'size': 12}
    gl.ylabel_style = {'rotation': 0, 'ha': 'right', 'va': 'center', 'size': 12}
    
    #
    # Add location markers
    #
    
    legend_handles = []
    
    if (location_legends is not None and
        location_lons is not None and
        location_lats is not None and
        location_colors is not None and
        location_sizes is not None):
        
        for location_legend, lons, lats, location_color, location_size in zip(location_legends, location_lons,location_lats,location_colors,location_sizes):
            
            for lon, lat in zip(lons,lats):
                
                dot = ax.plot(
                    lon, lat,
                    marker='o',
                    color=location_color,
                    markersize=location_size,
                    transform=ccrs.PlateCarree()
                )
            
            # Legend handle
            
            legend_handle = plt.Line2D(
                [], [],
                marker='o',
                color=location_color,
                linestyle='None',
                markersize=location_size,
                label=location_legend
            )
            
            legend_handles.append(legend_handle)
    
    # Add location legends
    
    if legend_handles:
        legend = ax.legend(
        handles=legend_handles,
        loc='lower left', # Do not use 'best' - this may cause execution to continue for too long when too many items are plotted
        fontsize=10,
        frameon=True
        )
    
    #
    # Save plot
    #
    
    if (plot_path is not None):
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        path = fig.savefig(plot_path,bbox_inches="tight",dpi=300)
    
    return
