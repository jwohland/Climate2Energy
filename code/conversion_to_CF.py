from windpowerlib import wind_turbine as wt
import numpy as np
import pandas as pd
import glob
import time
import xarray as xr
from gsee.climatedata_interface.interface import run_interface_from_dataset


out_path = "../output/"
powercurve_data = "../inputs/power_curves.csv"  #'/data/wind-python-windpowerlib-v0.2.0/windpowerlib/oedb/power_curves.csv'


def interpol(power):
    """
    Linear interpolation of power curve to a resoltion of 0.01 m/s
    :param power: DataFrame with index wind speed and value power generation
    :return:
    """
    start, end = power.first_valid_index(), power.last_valid_index()
    power = power.reindex(
        np.arange(start, end + 0.01, 0.01), tolerance=10 ** (-7), method="nearest"
    )
    power = power.interpolate(method="linear")
    power.index = np.round(power.index, decimals=2)
    return power


def compute_powercurves():
    """
    Compute the powercurves using the three turbines considered representative in
    Wohland et al. (2021) and save them as pickled files for later use
    :return:
    """
    rep_turbines = ["E-126/7580", "SWT120/3600", "SWT142/3150"]
    for i, turbine_name in enumerate(rep_turbines):
        power_curve = wt.get_turbine_data_from_file(turbine_name, powercurve_data)
        power_curve.value /= power_curve.value.max()  # normalization
        power_curve = power_curve.set_index("wind_speed").rename(
            columns={"value": turbine_name}
        )
        power_curve = interpol(power_curve)
        # save
        power_curve.to_pickle(out_path + "final_power_curve_" + str(i) + ".p")


class Power:
    """
    Wind power  conversion class. Based on pre-computed power curves, this
    class provides functionality to translate hub height wind speeds into
    capacity factors.
    """

    def __init__(self, turbine_index):
        self.power_curve = pd.read_pickle(
            sorted(glob.glob("../output/*.p"))[turbine_index]
        )
        self.turbine_name = self.power_curve.keys()[0].replace(
            "/", "_"
        )  # / leads to issues when saving

    def power_conversion(self, s):
        """
        translate wind speed s into capacity factors via the power curves that
        are provided as a lookup table.
        :param s:
        :return:
        """
        if s < self.power_curve.index[0] or s > self.power_curve.index[-1]:
            # below cut_in or above cut_out
            out = 0.0
        else:
            idx = self.power_curve[self.power_curve.index > s].iloc[0]  # close index, power curve index monotonically increases
            out = self.power_curve.iloc[idx].values[0]
        return float(out)


def update_attrs(ds, var, unitname, varname, long_varname):
    """
    Updates metadata of an xarray dataset, for example after trend calculation
    :param ds: input dataset
    :param var; variable in ds that is to be updated
    :param unitname: new units
    :param varname: new name of the variable
    :param long_varname: new long name of the variable
    :return:
    """
    ds = ds.rename_vars({var: varname})
    ds[varname].attrs["units"] = unitname
    ds[varname].attrs["long_name"] = long_varname
    return ds


def convert_winds(ds, filename):
    """
    Convert wind speeds to wind capacity factors for the three turbines
    :param ds: xr.dataset with hub height wind speeds available as "s_hub"
    :param filename:
    :return:
    """
    wind_power_list = []
    for turbine_index in range(3):
        # Open power curves if they exists, otherwise compute them
        try:
            P = Power(turbine_index)
        except:
            compute_powercurves()
            P = Power(turbine_index)
        print(P.turbine_name)

        # Check if this particular output already exists, otherwise compute
        try:
            wind_power = xr.open_dataset(out_path + P.turbine_name + "/" + filename)
            print(" already exists")
        except FileNotFoundError:
            t_0 = time.time()
            wind_power = xr.apply_ufunc(
                P.power_conversion, ds["s_hub"], vectorize=True, dask="allowed"
            ).to_dataset()
            wind_power = update_attrs(
                wind_power, "s_hub", "", "CF_wind", "normalized_wind_power_generation"
            )
            wind_power["turbine"] = P.turbine_name
            print("wind power conversion took " + str(time.time() - t_0))
            t_0 = time.time()
            wind_power.to_netcdf(out_path + P.turbine_name + "/" + filename)
            print("saving took " + str(int(time.time() - t_0)) + " s")
        wind_power_list.append(wind_power)
    wind_power = xr.concat(
        wind_power_list,
        dim=pd.Index(
            [Power(turbine_index).turbine_name for turbine_index in range(3)],
            name="turbine",
        ),
    )
    return wind_power


def calculate_PV(ds, params=None, num_cores=1):
    """
    Convert temperature and radiation to PV generation capacity factors
    :param ds: xr.Dataset that contains variables "global_horizontal" and "temperature"
    :param params: panel parameters
    :param num_cores: number of cores to be used
    :return:
    """
    if not params:
        params = dict(
            tilt=35, azim=180, tracking=0, capacity=1
        )  # capacity set to 1 Watt, that is output are capacity factors
    ds_pv = run_interface_from_dataset(
        data=ds,
        params=params,
        frequency="D",
        pdfs_file=None,
        num_cores=num_cores,
    )
    return ds_pv
