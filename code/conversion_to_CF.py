import numpy as np
import pandas as pd
import glob
import xarray as xr
from gsee.climatedata_interface.interface import run_interface_from_dataset
from utils import get_hub_heights, extrapolate_wind_xr, density_correct_winds


class Power:
    """
    Wind power  conversion class. Based on pre-computed power curves taken from
    Wohland et al. (2021), this class provides functionality to translate hub
    height wind speeds into capacity factors.

    The powercurves initially come from the windpowerlib database (Haas et al., 2019)
    and are available from

    https://github.com/wind-python/windpowerlib/blob/dev/windpowerlib/oedb/power_curves.csv

    Power curves are smoothed to account for subgridscale turbulence using the
    approach detailed in Knorr (2016) and a turbulence intensity TI = 0.1246 (see
    figure B2 of Wohland et al., 2021).

    References

    1. Wohland, J., Brayshaw, D. & Pfenninger, S. Mitigating a century of European renewable
    variability with transmission and informed siting. Environ. Res. Lett. 16, 064026 (2021).

    2. Knorr K 2016 Modellierung von raumzeitlichen Eigenschaften der Windenergieeinspeisung
    für wetterdatenbasierte Windleistungssimulationen Dissertation (Fachbereich
    Elektrotechnik/Informatik der Universität Kassel)

    Haas S, Schachler B and Krien U 2019 Windpowerlib—a python library to model wind power—v.0.2.0
    """

    def __init__(self, turbine_index):
        power_curve = pd.read_pickle(
            sorted(glob.glob("../inputs/power_curves/*.p"))[turbine_index]
        )
        power_curve[
            power_curve < 0
        ] = 0  # cubic spline interpolation leads to unphysical negative values (order of 10**(-5)) when power curves increases from or drops to zero
        self.power_curve = power_curve
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
        if np.isnan(s):
            return np.nan
        elif s <= self.power_curve.index[0] or s >= self.power_curve.index[-1]:
            # below cut_in or above cut_out
            out = 0.0
        else:
            idx = self.power_curve[self.power_curve.index > s].iloc[
                0
            ]  # close index, power curve index monotonically increases
            out = idx.values[0]
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
    ds = ds.rename({var: varname})
    ds[varname].attrs["units"] = unitname
    ds[varname].attrs["long_name"] = long_varname
    return ds


def convert_winds(ds_wind, ds_rho, alpha, density_correct=True):
    """
    Convert 100m wind speeds to wind capacity factors for the three turbines.

    This involves scaling winds to hub height with the wind profile exponents alpha.
    Alpha varies in time and space.

    :param ds_wind: xr.dataset with 100m wind speeds available as "s_hub"
    :param ds_wind: xr.dataset with air density
    :param alpha: wind profile exponents
    :param filename:
    :param density_correct: Whether to apply the air density correction. Defaults to True.
    :return:
    """
    wind_power_list = []
    for turbine_index in range(3):
        # Open pre-computed smoothed power curves
        P = Power(turbine_index)
        print(P.turbine_name)
        # Extrapolate to hub height
        hub_height = get_hub_heights(P.turbine_name)
        ds_hub = extrapolate_wind_xr(ds_wind, 100, hub_height, alpha).to_dataset(
            name="s_hub"
        )
        # Density correction
        if density_correct:
            ds_hub = density_correct_winds(ds_hub, ds_rho, hub_height)
        # Apply power curve
        wind_power = xr.apply_ufunc(
            P.power_conversion, ds_hub["s_hub"], vectorize=True, dask="parallelized"
        ).to_dataset()
        wind_power = update_attrs(
            wind_power, "s_hub", "", "CF_wind", "normalized_wind_power_generation"
        )
        wind_power["turbine"] = P.turbine_name
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
        frequency="H",
        pdfs_file=None,
        num_cores=num_cores,
    )
    return ds_pv
