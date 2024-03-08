from bias_correction_methods import *
from conversion_to_CF import *
from country_average import *
from utils import *
import sys


print("open files")
try:
    year = str(sys.argv[1])  # can be any year between 2016 and 2034
except IndexError:
    year = "2016"
print(year)
####################
# Step 0: Open data
####################
ds_wind, ds_PV = open_wind_solar(
    year, test_data=False
)  # test_data=True allows for quick test with only 10 timesteps
print("Files opened. Next: bias correction")

####################
# Step 1: Bias correction
####################
ds_corr_PV = xr.Dataset()
for var in ["temperature", "global_horizontal"]:
    print(var)
    ds_corr_PV[var] = bias_correct_dataset(ds_PV, var)

print("s_hub")
# Extrapolate model to 100m (i.e., ERA5 height), then bias correct, then extrapolate to 120m
ds_interpolated, alpha = interpolate_wind_xr(
    ds_wind, 100
)  # careful: this outputs s_hub even though these are 100m winds
ds_corr_wind = bias_correct_dataset(ds_interpolated, "s_hub")
print("Bias correction finished. Next: conversion to capacity factors")

####################
# Step 2: Calculate capacity factors
####################
ds_CF_PV = calculate_PV(ds_corr_PV, params=None)
ds_CF_wind = convert_winds(
    ds_corr_wind,
    alpha,
    "Wind_power_"
    + str(year)
    + ".nc",  # TODO: either remove completely or store intermediate PV output as well before computing country averages
)  # this expects that ds has variable called s_hub with hub height winds
print("Capacity factors computed. Next: country subsets and saving data")

# Step 3: subset countries
ds_CF_PV_countries = country_means(ds_CF_PV)
ds_CF_wind_countries = country_means(ds_CF_wind)
ds_CF_wind_countries_offshore = country_means(ds_CF_wind, onshore=False)


# Step4: Save data
# wind
for onshore in [True, False]:
    if onshore:
        ds_tmp_full = ds_CF_wind_countries
    else:
        ds_tmp_full = ds_CF_wind_countries_offshore
    for i in range(3):
        ds_tmp = ds_tmp_full.isel(turbine=i)
        turbine_name = str(ds_tmp.turbine.values)
        store_as_pandas_dataframe(
            ds_tmp["CF_wind"], name=f"CF_{turbine_name}_{year}_onshore_{onshore}"
        )
# PV
store_as_pandas_dataframe(ds_CF_PV_countries["pv"], name=f"CF_PV_{year}")
print("Everything finished and saved")
