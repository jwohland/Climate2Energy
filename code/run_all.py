import xarray as xr
from bias_correction_step import *
from conversion_to_CF import *
from country_average import *
from utils import *
import numpy as np

print("open files")

data_path = "/net/xenon/climphys/lbloin/energy_boost/"
ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_6h.nc")
ds_wind = zero_mean_longitudes(ds).sel(lon=slice(-15,50),lat=slice(30,75)).isel(lev=31)
ds_wind["s_hub"] = np.sqrt(ds_wind["U"]**2+ds_wind["V"]**2)

ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_daily_h2.nc")
ds_PV = zero_mean_longitudes(ds)
ds_t = zero_mean_longitudes(xr.open_dataset(data_path + "CESM2_r1i1p1_2015_daily_h1.nc"))
ds_PV["temperature"] = ds_t["TREFHT"]
ds_PV = ds_PV.sel(lon=slice(-15,50),lat=slice(30,75))
ds_PV["time"] = ds_PV.indexes[
    "time"
].to_datetimeindex()  # time index that GSEE understands

# Step 1: Bias correction 
for var in ["temperature", "FSDS"]:
    ds_PV[var] = bias_correct(ds_PV, var)


ds_wind = bias_correct(ds_wind, "s_hub")

# Step 2: Calculate capacity factors
ds_CF_PV = calculate_PV(ds_PV, params=None)
ds_CF_wind = convert_winds(
    ds_wind, "Wind_power_2015.nc"
)  # this expects that ds has variable called s_hub with hub height winds

# Step 3: subset countries
ds_CF_PV_countries = country_means(ds_CF_PV)
ds_CF_wind_countries = country_means(ds_CF_wind)

# Step4: Save data
# wind
for i in range(3):
    ds_tmp = ds_CF_wind_countries.isel(turbine=i)
    turbine_name = str(ds_tmp.turbine.values)
    store_as_pandas_dataframe(ds_tmp["CF_wind"], name="CF_" + turbine_name)
# PV
store_as_pandas_dataframe(ds_CF_PV_countries["pv"], name="CF_PV")
