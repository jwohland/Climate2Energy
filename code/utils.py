import numpy as np
import xarray as xr
import warnings


def select_Europe(ds):
    return ds.sel(lon=slice(-15, 50), lat=slice(30, 75))


def find_height(ds):
    """
    Calculates the height of dataset model levels
    :param ds:
    :return:
        ds:
        - same dataset as input, with added data array ds["height"]
    """
    if "Z3" not in ds.data_vars:
        raise ValueError(
            "Error: dataset does not have variable 'Z3', necessary for height calculation."
        )
    ds_orog = xr.open_dataset(
        "/net/meso/climphys/cesm212/inputfiles/BSSP370cmip6/atm/cam/topo/fv_0.9x1.25_nc3000_Nsw042_Nrs008_Co060_Fi001_ZR_sgh30_24km_GRNL_c170103.nc"
    )
    ds_orog = select_Europe(zero_mean_longitudes(ds_orog))
    ds_orog = (
        ds_orog["PHIS"] / 9.80665
    )  # geopotential reported in m**2/s**2 and divided by earth acceleration according to https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html

    ds["height"] = ds["Z3"] - ds_orog
    return ds


def open_wind_solar(year, test_data=False):
    """
    Open the data needed for wind and solar energy calculation and output
    as xr.Datasets.

    :param year:
    :param test_data: if set to True, only first 10 time steps are kept for testing
    :return:
        ds_wind:
            - wind speeds at 2 adjacent levels
            - height above ground
        ds_solar:
            - global horizontal radiation
            - temperature
    """
    data_path = "/net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.1500/archive/atm/hist/b.e212.BHISTcmip6.f09_g17.1500.cam"
    # Wind
    ds = xr.open_dataset(data_path + f".h6.{year}-01-01-03600.nc")
    ds = select_Europe(
        zero_mean_longitudes(ds).isel(lev=slice(30, 32))  # lowermost 2 levels
    )
    ds_wind = np.sqrt(ds["U"] ** 2 + ds["V"] ** 2)
    ds_wind = ds_wind.to_dataset(
        name="S"
    )  # call winds S here because they are still at model level
    ds_wind["Z3"] = ds["Z3"]
    ds_wind = find_height(ds_wind)

    # Solar
    ds = xr.open_dataset(data_path + f".h6.{year}-01-01-03600.nc")
    ds_PV = zero_mean_longitudes(ds).rename({"FSDS": "global_horizontal"})
    ds_t = zero_mean_longitudes(
        xr.open_dataset(data_path + f".h6.{year}-01-01-03600.nc")
    )
    ds_PV["temperature"] = ds_t["TREFHT"]
    ds_PV = ds_PV.sel(lon=slice(-15, 50), lat=slice(30, 75))
    with warnings.catch_warnings():  # to_datetimeindex throws a warning because CESM uses non-leap year calendar. We verified that this is not a problem (see notebook 13) and catch the warning here.
        warnings.simplefilter("ignore")
        ds_PV["time"] = ds_PV.indexes[
            "time"
        ].to_datetimeindex()  # time index that GSEE understands

    # Keep only few timesteps for test data
    if test_data:
        ds_wind = ds_wind.isel(time=slice(0, 10))
        ds_PV = ds_PV.isel(time=slice(0, 10))
    return ds_wind, ds_PV


def zero_mean_longitudes(ds):
    """
    resort a dataset with longitudes from
        0 to 360
    to one that has longitudes from
        -180 to 180
    :param ds:
    :return:
    """
    ds.coords["lon"] = (ds.coords["lon"] + 180) % 360 - 180
    ds = ds.sortby("lon")
    return ds


def temp_cel(ds):
    """
    returns the temperature dataset ds in celsius
    """
    if "temperature" in ds.data_vars:
        ds["temperature"] = ds["temperature"] - 273.15
        ds["temperature"].attrs["units"] = "degrees C"
        return ds
    else:
        "temperature is not in this dataset"
        return None


def store_as_pandas_dataframe(ds, name):
    """

    :param ds:
    :param name:
    :return:
    """
    ds.to_pandas().to_csv("../output/" + name + ".csv")


#
def interpolate_wind_xr(ds, output_height=120):
    """
    Calculates wind speeds at output height using data at evolving heights and
    the power law. Execution is done for one timestep here.

    The power law exponent is fitted per time step and location, thereby accounting
    for the fact that wind profiles do not always look the same

    It is assumed that the Dataset ds only contains two levels that are close to the
    hub height.

    This function is taken and modified from lucas_3dwinds
    """
    vertical_dim = "lev"
    # Identify index of upper and lower level to be used here
    height_max = 0
    height_min = 1
    # Calculate power law exponent alpha
    alpha = np.log(
        ds["S"].isel(lev=height_max) / ds["S"].isel(lev=height_min)
    ) / np.log(ds["height"].isel(lev=height_max) / ds["height"].isel(lev=height_min))
    # Interpolate to output height
    y_hub = (
        ds["S"].isel(lev=height_min)
        * (output_height / ds["height"].isel(lev=height_min)) ** alpha
    )
    ds_hub = y_hub.to_dataset(name="s_hub")
    ds_hub["s_hub"].attrs = {"long_name": "Wind speed at hub height [m/s]"}
    ds_hub = ds_hub.drop(vertical_dim)
    return ds_hub, alpha


def extrapolate_wind_xr(da, input_height, output_height, alpha):
    """
    Extrapolate wind speeds in ds from the input height to the output height using
    the power law and precomputed alpha values (per timestep and location)
    :param da: DataArray of wind speeds at input height
    :param input_height:
    :param output_height:
    :param alpha:
    :return:
    """
    return da * (output_height / input_height) ** alpha
