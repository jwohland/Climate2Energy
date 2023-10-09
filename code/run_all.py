import xarray as xr
from bias_correction_methods import *
from conversion_to_CF import *
from country_average import *
from utils import *
import numpy as np

print("open files")

data_path = "/net/xenon/climphys/lbloin/energy_boost/"

ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_6h.nc")
ds_wind = (
    zero_mean_longitudes(ds).sel(lon=slice(-15, 50), lat=slice(30, 75)).isel(lev=31)
)
ds_wind["s_hub"] = np.sqrt(ds_wind["U"] ** 2 + ds_wind["V"] ** 2)
ds_wind = ds_wind.drop(
    "lev"
)  # temporary fix to avoid crash - will be fixed when interpolated (bias correction can't have empty lev)

ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_daily_h2.nc")
ds_PV = zero_mean_longitudes(ds).rename({"FSDS": "global_horizontal"})
ds_t = zero_mean_longitudes(
    xr.open_dataset(data_path + "CESM2_r1i1p1_2015_daily_h1.nc")
)
ds_PV["temperature"] = ds_t["TREFHT"]
ds_PV = ds_PV.sel(lon=slice(-15, 50), lat=slice(30, 75))
ds_PV["time"] = ds_PV.indexes[
    "time"
].to_datetimeindex()  # time index that GSEE understands


# Step 1: Bias correction
ds_corr_PV = xr.Dataset()
for var in ["temperature", "global_horizontal"]:
    print(var)
    ds_corr_PV[var] = bias_correct_dataset(ds_PV, var)

print("s_hub")
ds_corr_wind = bias_correct_dataset(ds_wind, "s_hub").to_dataset(name="s_hub")

# Step 2: Calculate capacity factors
ds_CF_PV = calculate_PV(ds_corr_PV, params=None)
ds_CF_wind = convert_winds(
    ds_corr_wind, "Wind_power_2015.nc"  # TODO: fix hardcoded year
)  # this expects that ds has variable called s_hub with hub height winds

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
