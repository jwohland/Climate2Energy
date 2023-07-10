import xarray as xr
from bias_correction import *
from conversion_to_CF import *
from country_average import *
from utils import *


data_path = "/net/xenon/climphys/lbloin/energy_boost/"
ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_6h.nc")

# wind example over limited domain and just claiming that one level is hub height
# todo this is just temporary and needs to be generalized to full domain and correct heights
ds_wind = (
    ds.isel(lev=31, ilev=31)["U"]
    .squeeze()
    .drop(["lev", "ilev"])
    .isel(time=slice(0, 3))
    .sel(lat=slice(35, 75), lon=slice(-12, 40))
)
ds_wind = zero_mean_longitudes(ds_wind)
ds_wind = ds_wind.to_dataset(name="s_hub")

# radiation example over limited domain and just claiming that one level is hub height
# todo this is just temporary and needs to be expanded to full domain
# gsee expects dataset with variables "global_horizontal" and "temperature"
ds_PV = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_daily_h2.nc")
ds_PV = ds_PV["FSDS"].isel(time=slice(0, 3)).sel(lat=slice(35, 75), lon=slice(-12, 40))
ds_PV = ds_PV.to_dataset(name="global_horizontal")
ds_temp = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_daily_h1.nc")
ds_PV["temperature"] = ds_temp["TREFHT"]
ds_PV["time"] = ds_PV.indexes[
    "time"
].to_datetimeindex()  # time index that GSEE understands


# Step 1: Bias correction
ds = bias_correct(ds)

# Step 2: Calculate capacity factors
ds_CF_PV = calculate_PV(ds_PV, params=None)
ds_CF_wind = convert_winds(
    ds_wind, "Wind_power_2015.nc"
)  # this expects that ds has variable called s_hub with hub height winds

# Step 3: subset countries
df_PV = cut_out_countries(ds_CF_PV)
df_wind = cut_out_countries(ds_CF_wind)
