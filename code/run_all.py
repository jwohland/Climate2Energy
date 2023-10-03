import xarray as xr
from bias_correction_methods import *
from conversion_to_CF import *
from country_average import *
from utils import *
import numpy as np

print("open files")

data_path = "/net/xenon/climphys/lbloin/energy_boost/"
# Wind
ds = xr.open_dataset(data_path + "CESM2_r1i1p1_2015_6h.nc")
ds = (
    zero_mean_longitudes(ds)
    .sel(lon=slice(-15, 50), lat=slice(30, 75))  # choose Europe
    .isel(lev=slice(30, 32))  # lowermost 2 levels
)
ds_wind = np.sqrt(ds["U"] ** 2 + ds["V"] ** 2)
ds_geop = ds["Z3"]
ds_orog = xr.open_dataset(
    "/net/meso/climphys/cesm212/inputfiles/BSSP370cmip6/atm/cam/topo/fv_0.9x1.25_nc3000_Nsw042_Nrs008_Co060_Fi001_ZR_sgh30_24km_GRNL_c170103.nc"
)
ds_orog = zero_mean_longitudes(ds_orog).sel(lon=slice(-15, 50), lat=slice(30, 75))
ds_orog = (
    ds_orog["PHIS"] / 9.80665
)  # geopotential reported in m**2/s**2 and divided by earth acceleration according to https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html
ds_combined = ds_wind.to_dataset(name="S")
ds_combined["height"] = ds_geop - ds_orog
ds_interpolated, alpha = interpolate_wind_xr(ds_combined)

# Solar
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
for var in ["temperature", "global_horizontal"]:
    ds_PV[var] = bias_correct_dataset(ds_PV, var)

ds_wind = bias_correct_dataset(ds_interpolated, "S")
ds_wind = extrapolate_wind_xr(
    ds_wind, 100, 120, alpha
)

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
