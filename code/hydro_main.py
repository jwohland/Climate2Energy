from bias_correction_methods import bias_correct_dataset
from country_average import country_means, get_country_list
from utils import store_as_pandas_dataframe, zero_mean_longitudes, select_Europe, create_directories
from conversion_to_hydro import *
import glob
import sys
import subprocess
import xarray as xr
import pandas as pd
import numpy as np
import scipy
import os
import statsmodels.api as sm
import datetime as datetime

# create necessary directories (for pecd and entso-e data)
create_directories()
year = 2010

# =====================================================
# === Step 1: Open, bias correct and aggregate data ===
# =====================================================

# === CESM2 runoff === 
print("Open and bias correct CESM2 runoff")
runoff = open_runoff(year) # you can pass end_year to it to open several years in row
# Bias correction

# runoff = bias_correct_dataset(runoff, "runoff").to_dataset(name="runoff")  

# === ERA5 runoff (2017-2022) === 
print("Open ERA5 runoff")
runoff_era5 = open_era()

# === ENTSO-E inflow (2017-2022) ===
print("Open ENTSO-e inflow data")
inflow_entsoe = open_entsoe_ror() # conversion data set for inflows 

# === Smart aggregation over country for CESM2 and ERA5 ===
print("Aggregate runoff over countries")
runoff = weighted_aggregation_ror(runoff)
runoff_era5 = weighted_aggregation_ror(runoff_era5)

print("All files opened and preprocessed. Conversion starting")

# ================================================
# === Step 2: Convert to hydropower generation ===
# ================================================
# TODO: concat era5 entsoe into one xarray
# === Run-of-river ===
# get 75th percentile of CESM2 runoff, for each country
qu_75 = get_qu_75(runoff)
# Treat seasons separately
season_transfer = []
for season in runoff.groupby("time.season"):
    # get seasonal era5 and entsoe values too
    runoff_era5_season = dict(runoff_era5.groupby("time.season"))[season[0]]
    inflow_entsoe_season = dict(inflow_entsoe.groupby("time.season"))[season[0]]
    # apply by season over all grid cells
    season_transfer.append(lin_transfer_all_countries(season[1].runoff,
                                                      runoff_era5_season.runoff,
                                                      inflow_entsoe_season.inflow,
                                                      qu_75 = qu_75
                                                     ).to_dataset(name="inflow_cesm2")
                          )
ror = xr.concat(season_transfer,dim="time").sortby("time") # add seasons together and sort chunks by time
# Rolling mean
ror = ror.rolling(time=7,center=True).mean() #TODO rolling mean before
# TODO: change implementation to fit your needs

# TODO: Scale up

# === Reservoir/pumped hydro ===
# TODO: implement your setup (potentially streamline with r-o-r setup
reservoir = xr.DataArray()
# TODO: scale up
# Save both hydro types in one dictionary
output = {
    "ror":ror.inflow_cesm2,
    "inflow":reservoir
}

print("Conversion done. Now saving")
# ===========================
# === Step 4: Save output ===
# ===========================
for i,type in enumerate(output):
    store_as_pandas_dataframe(output[type], f"hydro_{type}_{year}")