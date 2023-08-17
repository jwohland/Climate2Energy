import xarray as xr
from bias_correction_methods import *
from conversion_to_CF import *
from country_average import *
from utils import *
import numpy as np

print("open files")

data_path =  "/net/xenon/climphys/lbloin/energy_boost/"
ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_6h.nc")
ds_wind = zero_mean_longitudes(ds).sel(lon=slice(-15,50),lat=slice(30,75)).isel(lev=31)
ds_wind["s_hub"] = np.sqrt(ds_wind["U"]**2+ds_wind["V"]**2)

ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_daily_h2.nc")
ds_PV = zero_mean_longitudes(ds)
ds_t = zero_mean_longitudes(xr.open_dataset(data_path + "CESM2_r1i1p1_2015_daily_h1.nc"))
ds_PV["temperature"] = ds_t["TREFHT"]
ds_PV = ds_PV.sel(lon=slice(-15,50),lat=slice(30,75))

# Step 1: Bias correction 
for var in ["temperature", "FSDS"]:
    ds_PV[var] = bias_correct_dataset(ds_PV, var)

ds_wind = bias_correct_dataset(ds_wind, "s_hub")

# Step 2: Calculate capacity factors
ds_CF_PV = calculate_PV(ds)
ds_CF_wind = calculate_wind(ds)

# Step 3: subset countries
df_PV = cut_out_countries(ds_CF_PV)
df_wind = cut_out_countries(ds_CF_wind)