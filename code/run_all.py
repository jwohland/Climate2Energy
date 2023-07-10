import xarray as xr
from bias_correction import *
from conversion_to_CF import *
from country_average import *
from utils import *


data_path = "/net/xenon/climphys/lbloin/energy_boost/"
ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_6h.nc")

# wind example claiming that one level is hub height
ds_wind = (
    ds.isel(lev=31, ilev=31)["U"].squeeze().drop(["lev", "ilev"]).sel(lat=slice(35, 75))
)
ds_wind = zero_mean_longitudes(ds_wind).sel(lon=slice(-12, 40))
ds_wind = ds_wind.to_dataset(name="s_hub")

# radiation example
# gsee expects dataset with variables "global_horizontal" and "temperature"
ds_PV = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_daily_h2.nc")
ds_PV = ds_PV["FSDS"].sel(lat=slice(35, 75), lon=slice(-12, 40))
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

# Step4: Save data
# wind
for i in range(3):
    ds = ds_wind.isel(turbine=i)
    turbine_name = str(ds.turbine.values)
    store_as_pandas_dataframe(ds["CF_wind"], name="CF_" + turbine_name)
# PV
store_as_pandas_dataframe(ds_PV["pv"], name="CF_PV")
