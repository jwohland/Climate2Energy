import xarray as xr
import pandas as pd
from utils import interpolate_wind_xr, zero_mean_longitudes, select_Europe
import numpy as np
import glob

def general_preproc(ds,datetime_index=False):
    ds = select_Europe(zero_mean_longitudes(ds))
    if datetime_index == True:
        ds["time"] = ds.indexes["time"].to_datetimeindex() 
    return ds.sel(time=slice("1991","2052"))

def match_time_steps_interpolate(
ds_data: xr.Dataset,
ds_reference: xr.Dataset,
skip_leap_days: bool = True,
) -> xr.Dataset:
    """
    Adjust the time steps of the reference dataset to match the time steps of the data dataset.

    Parameters
    ----------

    ds_data : xr.Dataset
    The dataset containing the desired time steps.
    ds_reference : xr.Dataset
    The reference dataset to be adjusted.
    skip_leap_days : bool, optional
    Whether to skip leap days when adjusting the time steps.
    Default is True.
    
    Returns
    -------
    xr.Dataset
    The reference dataset with adjusted time steps.
    """
    if not np.array_equal(
    np.unique(ds_data.time.dt.hour), np.unique(ds_reference.time.dt.hour)
    ):
        print("Adjusting time steps of the reference dataset")
    # Step 1: Create a new time index with hourly values spanning the time range of ds_data
    first_time_step = pd.to_datetime(ds_data.time.values[0])
    start_date = pd.to_datetime(ds_reference.time.values[0]).replace(
        hour=first_time_step.hour, minute=first_time_step.minute
    )
    time_range = pd.date_range(
        start=start_date,
        end=pd.to_datetime(ds_data.time.max().item()),
        freq="h",
    )
    if skip_leap_days:
        # Remove leap days from the time range
        time_range = time_range[~((time_range.month == 2) & (time_range.day == 29))]
    # Step 2: Interpolate ds_rsds_bc_subset to the new hourly time index
    # Step 3: Fill NaN values at the beginning and at the end of the time series
    ds_reference_hourly = (
        ds_reference.interp(time=time_range).bfill(dim="time").ffill(dim="time")
    )
    # Step 4: Extract the timesteps needed to match ds_tas_bc_subset
    ds_reference = ds_reference_hourly.sel(time=ds_data.time)
    del ds_reference_hourly
    
    return ds_reference


# Path to open files
for rcp in ["26","85"]:
    path = f"/net/exo/landclim/yhaddad/clim2energy-ch/cordex_processed/CNRM-ALADIN63_CNRM-CERFACS-CNRM-CM5_r1i1p1_rcp{26}/bias_corrected/"
    path_hydro = f"/net/argon/landclim2/pseubert/out_rcm/hist/CNRM-{rcp}/"
    out_path = "../output/CORDEX_data/atmospheric_variables/"

    # open, preprocess and save surface wind and specific humidity as one file
    others = general_preproc(xr.open_zarr(f"{path}3hr/sfcWind.zarr/").rename({"sfcWind":"U10"}))
    qrefht = general_preproc(xr.open_zarr(f"{path}3hr/huss_derived.zarr/")["huss"])
    others["QREFHT"] = qrefht
    others.to_netcdf(f"{out_path}other_CORDEX_{rcp}.nc")

    # open, preprocess and save radiation and temperature
    trefht = general_preproc(xr.open_zarr(f"{path}3hr/tas.zarr/").rename({"tas":"temperature"})) - 273.15 # conversion to celsius
    global_horizontal = general_preproc(xr.open_zarr(f"{path}3hr/rsds.zarr/").rename({"rsds":"global_horizontal"}))
    global_horizontal = match_time_steps_interpolate(trefht,global_horizontal,skip_leap_days=True)
    trefht.to_netcdf(f"{out_path}bced_temperature_CORDEX_{rcp}.nc")
    global_horizontal.to_netcdf(f"{out_path}bced_global-horizontal_CORDEX_{rcp}.nc")

    #open and preprocess hydro
    for time_range in ["1991-1995", "1996-2000", "2001-2005", "2006-2010", "2011-2015", "2016-2020", "2021-2025", "2026-2030", "2031-2035", "2036-2040", "2041-2045", "2046-2050", "2051-2055"]:
        file = glob.glob(f"{path_hydro}{time_range}/Qrouted_*_m3s.zarr/")[0]
        discharge = xr.open_zarr(file).rename({"Qrouted":"discharge"})
        discharge = discharge.reindex(lat=discharge.lat[::-1]) #make lat go from - to +
        discharge = general_preproc(discharge).convert_calendar("proleptic_gregorian")
        discharge.to_netcdf(f"{out_path}bced_discharge_CORDEX_{time_range}_{rcp}.nc")

