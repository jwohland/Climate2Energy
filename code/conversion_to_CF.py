from windpowerlib import wind_turbine as wt
import numpy as np
import pandas as pd
import glob
import time
import xarray as xr


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
    rep_turbines = ['E-126/7580', 'SWT120/3600', 'SWT142/3150']
    for i, turbine_name in enumerate(rep_turbines):
        power_curve = wt.get_turbine_data_from_file(turbine_name, powercurve_data)
        power_curve.value /= power_curve.value.max()  # normalization
        power_curve = power_curve.set_index("wind_speed").rename(columns={'value': turbine_name})
        power_curve = interpol(power_curve)
        # save
        power_curve.to_pickle(out_path + 'final_power_curve_' + str(i) + '.p')

class Power:
    """
    Wind power  conversion class. Based on pre-computed power curves, this
    class provides functionality to translate hub height wind speeds into
    capacity factors.
    """
    def __init__(self, turbine_index):
        self.power_curve = pd.read_pickle(sorted(glob.glob('../output/*.p'))[turbine_index])
        self.turbine_name = self.power_curve.keys()[0].replace('/', '_')  # / leads to issues when saving

    def power_conversion(self, s):
        """
        translate wind speed s into capacity factors via the power curves that
        are provided as a lookup table.
        :param s:
        :return:
        """
        s = np.round(s, 2)  # only two decimal accuracy in power curve
        if s < self.power_curve.index[0] or s > self.power_curve.index[-1]:
            # below cut_in or above cut_out
            out = 0.
        else:
            out = self.power_curve.loc[s].values[0]
        return out


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
    ds[varname].attrs['units'] = unitname
    ds[varname].attrs['long_name'] = long_varname
    return ds

def convert_winds(ds, filename):
    """
    Convert wind speeds to wind capacity factors for the three turbines
    :param ds: xr.dataset with hub height wind speeds availablee as "s_hub"
    :param filename:
    :return:
    """
    for turbine_index in range(3):
        # Open power curves if they exists, otherwise compute them
        try:
            P = Power(turbine_index)
        except:
            compute_powercurves()
            P = Power(turbine_index)
        print(P.turbine_name)

        #Check if this particular output already exists, otherwise compute
        try:
            xr.open_dataset(out_path + P.turbine_name + '/' + filename)
            print(" already exists")
        except FileNotFoundError:
            t_0 = time.time()
            wind_power = xr.apply_ufunc(P.power_conversion,
                                        ds["s_hub"],
                                        vectorize=True,
                                        dask='allowed').to_dataset()
            wind_power = update_attrs(wind_power,
                                      's_hub',
                                      '',
                                      'CF_wind',
                                      'normalized_wind_power_generation')
            print('wind power conversion took ' + str(time.time() - t_0))
            t_0 = time.time()
            wind_power.to_netcdf(out_path + P.turbine_name + '/' + filename)
            print('saving took ' + str(int(time.time() - t_0)) + ' s')


