import xarray as xr
from bias_correction import *
from conversion_to_CF import *

data_path =  "/net/xenon/climphys/lbloin/energy_boost/"
ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_6h.nc")

# Step 1: Bias correction
ds = bias_correct(ds)

# Step 2: Calculate capacity factors
ds_CF_PV = calculate_PV(ds)
ds_CF_wind = calculate_wind(ds)

# Step 3: subset countries
df_PV = subset_countries(ds_CF_PV)
df_wind = subset_countries(ds_CF_wind)