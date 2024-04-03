import numpy as np
import xarray as xr
import warnings
from os import makedirs


def select_Europe(ds):
    return ds.sel(lon=slice(-15, 50), lat=slice(30, 75))


def get_time_range(scenario):
    """
    Start and end years of the different scenarios covered in this analysis
    :param scenario:
    :return:
    """
    range_dict = {
        "historical": range(1995, 2015),
        "SSP370": range(2080, 2100),
        "SSP245": range(2080, 2100),
    }
    return range_dict[scenario]


def get_input_filename(scenario, realization, year):
    """
    Navigate to the input files
    :param scenario:
    :param realization:
    :param year:
    :return:
    """
    shared_path = f"/net/meso/climphys/cesm212/"
    tmp = "b.e212.B"
    if scenario == "historical":
        tmp += "HIST"
    else:
        tmp += scenario  # i.e., + SSP370 or SSP245
    tmp += "cmip6.f09_g17."
    if realization == "A":
        tmp += "1500"
    elif realization == "B":
        if scenario == "historical":
            tmp += "1000"
        elif scenario == "SSP370":
            tmp += "0600"
    elif realization == "C":
        if scenario == "historical":
            tmp += "1200"
        elif scenario == "SSP370":
            tmp += "0900"
    assembled_path = (
        f"{shared_path}{tmp}/archive/atm/hist/{tmp}.cam.h6.{year}-01-01-03600.nc"
    )
    return assembled_path


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


def get_hub_heights(turbine_name):
    """
    Lookup function to check turbine hub heights.
    Information is taken from windpowerlib, see link below.

    https://github.com/wind-python/windpowerlib/blob/dev/windpowerlib/data/default_turbine_data/turbine_data.csv
    :return:
    """
    hub_height_dict = {
        "SWT142_3150": 129,  # this turbine has 3 possible hub heights. We choose the one in the middle.
        "SWT120_3600": 90,
        "E-126_7580": 127,
    }
    return hub_height_dict[turbine_name]


def open_wind_solar(year, scenario, realization, test_data=False):
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
    chunks = {"lat": 10, "lon": 10, "lev": 5, "ilev": 5, "time": 1000}
    # Wind
    ds_atm = select_Europe(
        zero_mean_longitudes(
            xr.open_dataset(
                get_input_filename(scenario, realization, year), chunks=chunks
            )
        )
    )
    # Keep only few timesteps for test data
    if test_data:
        ds_atm = ds_atm.isel(time=slice(0, 10))
    ds_wind = ds_atm.isel(lev=slice(30, 32))  # lowermost 2 levels
    ds_wind = np.sqrt(ds_wind["U"] ** 2 + ds_wind["V"] ** 2)
    ds_wind = ds_wind.to_dataset(
        name="S"
    )  # call winds S here because they are still at model level
    ds_wind["Z3"] = ds_atm["Z3"]
    ds_wind = find_height(ds_wind)

    # air density
    ds_rho = ds_atm.sel(ilev=slice(900, 1200), lev=slice(900, 1200))[
        ["RHO_CLUBB", "Z3"]
    ]  # RHO_CLUBB and Z3  are provided on different sigma pressure coordinates called lev and ilev
    # we here select slices that contain hub height pressure on the GCM grid

    # Solar
    ds_PV = rad = ds_atm.rename({"FSDS": "global_horizontal"})[
        "global_horizontal"
    ].to_dataset()
    ds_PV["temperature"] = ds_atm["TREFHT"]
    ds_PV = temp_cel(ds_PV)  # temperature in celsius
    with warnings.catch_warnings():  # to_datetimeindex throws a warning because CESM uses non-leap year calendar. We verified that this is not a problem (see notebook 13) and catch the warning here.
        warnings.simplefilter("ignore")
        ds_PV["time"] = ds_PV.indexes[
            "time"
        ].to_datetimeindex()  # time index that GSEE understands

    return ds_wind, ds_rho, ds_PV


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


def create_directories():
    """
    Creates the directories that are needed to store the output in the desired structure
    :return:
    """
    required_directories = [
        f"../output/bias_correction/{bc_realization}/{scenario}/{realization}/{sub_folder}"
        for bc_realization in ["A", "B", "C"]
        for scenario in ["historical", "SSP370", "SSP245"]
        for realization in ["A", "B", "C"]
        for sub_folder in ["atmospheric_variables", "output_variables"]
    ]
    required_directories.append(
        "../plots/"
    )  # plots

    for directory in required_directories:
        makedirs(directory, exist_ok=True)  # only create them if they do not exist yet


# Air density correction
def add_target_pressure_level(ds, target_height):
    """
    Calculation of atmospheric pressure level that corresponds
    to target height. This pressure level "p_target" is a function
    of location and time as it varies with geopotential height and
    orography.

    Conversion assumes that target height sits between pressure
    levels 3 and 4, which roughly correspond to 195m and 60m above ground.

    :param ds:
    :param target_height:
    :return:
    """
    ds = find_height(ds)  # height above ground
    a = (target_height - ds.height.isel(lev=3)) / (
        ds.height.isel(lev=4) - ds.height.isel(lev=3)
    )
    ds["p_target"] = a * ds.lev.isel(lev=4) + (1 - a) * ds.lev.isel(lev=3)
    return ds


def compute_density_target(
    ds, target_height=120
):  # todo target height needs to be aligned with multiple hub heights
    """
    Interpolation of atmospheric density which is reported
    between model levels to the pressure level that corresponds
    to the target height (e.g., turbine hub height).

    Linear interpolation (air density vs. atmospheric pressure)
    because air density is approximately linear in pressure in the
    simulations. It even is perfectly linear when temperature is unchanged
    between 2 grid boxes (pV=NRT).

    :param ds: xr.Dataset with "Z3" and "RHO_CLUBB" as variables
    :param target_height:
    :return:
    """
    ds = add_target_pressure_level(ds, target_height=target_height)
    # interpolate ilev and lev (shifted by half a grid cell) to pressure at target height
    ds = ds.interp(lev=ds["p_target"], ilev=ds["p_target"])
    ds = ds.drop(["Z3", "height", "p_target"]).rename({"RHO_CLUBB": "RHO_target"})
    ds = ds.drop(["lev", "ilev"])
    return ds


def density_correct_winds(ds_wind, ds_rho, target_height):
    """
    Perform a wind correction that captures the effects of differing air density.
    Turbine power curves are reported at standard air density (rho_std) but
    air density at the wind park site is generally different from that.

    The computation below follows the IEC 61400-12 norm as explained in
    "WindPRO / Energy Power Curve Air Density Correction And Other Power
    Curve Options In WindPRO" by Lasse Svenningsen.

    It is based on two ideas.

    First, wind energy density is proportional to rho * u**3, where rho is air density
    and u is hub height wind speed.

    Second, real power curves deviate from this relationship. That is, a linear scaling of
    capacity factors with air density makes no sense as it would, for example, also modify
    the rated capacity. Therefore, we compute an alternative wind speed u' that captures
    the effects of air density changes and then compute CF(u').

    Basically, if we use the standard air density rho_std, which u' do we need
    to calculate the same energy density as when taking the real rho and u from the model?

    rho_std * u'**3 = rho * u**3

    Rearranging yields the equation implemented below.

    :param ds_wind:
    :param ds_rho:
    :return:
    """
    rho_std = 1.225  # kg/m3 according to IEC 61400-12
    ds_tmp = ds_wind["s_hub"] * (
        compute_density_target(ds_rho.copy(), target_height)["RHO_target"] / rho_std
    ) ** (1 / 3)
    ds_tmp = ds_tmp.to_dataset(name="s_hub")
    return ds_tmp
