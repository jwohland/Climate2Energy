from windpowerlib import wind_turbine as wt
import numpy as np


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

1