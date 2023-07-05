import xarray as xr
from bias_correction import *
from conversion_to_CF import *
from country_average import *
from utils import *

data_path = "/net/xenon/climphys/lbloin/energy_boost/"
ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_6h.nc")
ds = zero_mean_longitudes(ds)

# wind example over limited domain and just claiming that one level is hub height
# todo this is just temporary
ds_wind = (
    ds.isel(lev=31, ilev=31)["U"]
    .squeeze()
    .drop(["lev", "ilev"])
    .sel(lat=slice(50, 60), lon=slice(10, 20))
)
ds_wind = ds_wind.to_dataset(name="s_hub")

# Step 1: Bias correction
ds = bias_correct(ds)

# Step 2: Calculate capacity factors
ds_CF_PV = calculate_PV(ds)
ds_CF_wind = convert_winds(
    ds_wind, "Wind_power_2015.nc"
)  # this expects that ds has variable called s_hub with hub height winds

# Step 3: subset countries
df_PV = cut_out_countries(ds_CF_PV)
df_wind = cut_out_countries(ds_CF_wind)