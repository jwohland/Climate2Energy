import numpy as np


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
    ds_hub = y_hub.to_dataset(name="S_hub")
    ds_hub["S_hub"].attrs = {"long_name": "Wind speed at hub height [m/s]"}
    ds_hub.drop(vertical_dim)
    return ds_hub, alpha


def extrapolate_wind_xr(ds, input_height, output_height, alpha):
    """
    Extrapolate wind speeds in ds from the input height to the output height using
    the power law and precomputed alpha values (per timestep and location)
    :param ds:
    :param input_height:
    :param output_height:
    :param alpha:
    :return:
    """
    return ds["S"]*(output_height / input_height) ** alpha