from bias_correction_methods import *
from conversion_to_CF import *
from country_average import *
from utils import *


print("open files")
year = "2016"  # can be any year between 2016 and 2034


# Step 0: Open data
ds_wind, ds_PV = open_wind_solar(year, test_data=True)
ds_interpolated, alpha = interpolate_wind_xr(
    ds_wind, 100
)  # todo bias correct wants the output to be called s_hub


# Step 1: Bias correction
print("Files opened. Next: bias correction")
ds_corr_PV = xr.Dataset()
for var in ["temperature", "global_horizontal"]:
    print(var)
    ds_corr_PV[var] = bias_correct_dataset(ds_PV, var)


print("s_hub")
ds_corr_wind = bias_correct_dataset(
    ds_interpolated, "S"
)  # todo Luna had bias_correct_dataset(ds_wind, "s_hub").to_dataset(name="s_hub")
ds_corr_wind = extrapolate_wind_xr(
    ds_corr_wind, 100, 120, alpha
)  # todo this throws an error because ds_coorr_wind currently is a dataArray  but extrapolate_winds expects
# a dataset with a variable called S


# Step 2: Calculate capacity factors
print("Bias correction finished. Next: conversion to capacity factors")
ds_CF_PV = calculate_PV(ds_corr_PV, params=None)

ds_CF_wind = convert_winds(
    ds_corr_wind.to_dataset(
        name="s_hub"
    ),  # TODO: This to_dataset should not be needed.
    "Wind_power_2015.nc",  # TODO: fix hardcoded year
)  # this expects that ds has variable called s_hub with hub height winds

print("Capacity factors computed. Next: country subsets and saving data")
# Step 3: subset countries
ds_CF_PV_countries = country_means(ds_CF_PV)
ds_CF_wind_countries = country_means(ds_CF_wind)

# Step4: Save data

# wind
for i in range(3):
    ds_tmp = ds_CF_wind_countries.isel(
        turbine=i
    ).squeeze()  # TODO: squeeze just not be needed once interpolation is done
    turbine_name = str(ds_tmp.turbine.values)
    store_as_pandas_dataframe(ds_tmp["CF_wind"], name="CF_" + turbine_name)

# PV
store_as_pandas_dataframe(ds_CF_PV_countries["pv"], name="CF_PV")

print("Everything finished and saved")
