from bias_correction_methods import bias_correct_dataset
from utils import store_as_pandas_dataframe
from conversion_to_hydro import *
import sys
import xarray as xr
import pandas as pd
import numpy as np

# parameters
year = 2010
technologies = ["ror","inflow"]
rolling = {"ror":21,"inflow":3} # time to roll over - since inflow is weekly 3 weeks = 21 days

# =====================================================
# === Step 1: Open, bias correct and aggregate data ===
# =====================================================

# === CESM2 runoff === 
print("Open and bias correct CESM2 runoff")
runoff_full = open_runoff(year) # you can pass end_year to it to open several years in row
# Bias correction
runoff_full = bias_correct_dataset(runoff_full, "runoff").to_dataset(name="runoff")  
runoff_full = runoff_full.where(runoff_full.runoff > 0, other=0).convert_calendar("proleptic_gregorian") # to get numpy datetime (necessary for weekly resampling)
# aggregation
for tech in technologies:
    print(f"Aggregate CESM for tech {tech}")
    runoff = weighted_aggregation(runoff_full,tech)

    # === ERA5 runoff and ENTSO-e data (2017-2022) === 
    print(f"Open ERA5 runoff and ENTSO-e data for tech {tech}")
    # ENTSO-e
    calibration_ds = open_entsoe(tech) # conversion data set for inflows/ror
    [start_year,end_year] = calibration_ds.groupby("time.year").sum().year[[0,-1]].values
    # ERA5
    era_runoff = open_era().sel(time=slice(str(start_year),str(end_year)))
    if tech == "inflow":
        time_range = calibration_ds.time[[0,-1]].values # find values of start and end date, to open era5 weekly correctly
        era_runoff = open_weekly(era_runoff,time_range=time_range) # get era5 in weekly resolution
        runoff = open_weekly(runoff) # get cesm2 in weekly resolution
    #weighted aggregation, and making sure runoff and generation have same country list
    era_weighted = weighted_aggregation(era_runoff,tech)["runoff"].sel(country=calibration_ds.country)
    if tech =="ror":
        era_weighted["time"] = calibration_ds.time #ensuring same time stamp (runoff resamples to 11.30 every day and not 00.00)
    calibration_ds["runoff"] = era_weighted

    # rolling means
    runoff = runoff.rolling(time=rolling[tech],center=True).mean()
    calibration_ds = calibration_ds.rolling(time=rolling[tech],center=True).mean()

    print(f"All {tech} files opened and preprocessed. Conversion starting")

    # =====================================
    # === Step 2: Convert to hydropower ===
    # =====================================
    
    # get 75th percentile of runoff (use ERA5 to get multiple years of data), for each country regardless of season
    qu_75 = get_qu_75(calibration_ds)
    if tech == "inflow":
        qu_75 = qu_75*np.nan
    # Treat seasons separately
    season_transfer = []
    for season in runoff.groupby("time.season"):
        # get seasonal calibration data too
        calibration_season = calibration_ds.groupby("time.season")[season[0]]
        # apply by season over all grid cells
        season_transfer.append(lin_transfer_all_countries(season[1].runoff,
                                                          calibration_season,
                                                          tech,
                                                          qu_75 = qu_75
                                                         ).to_dataset(name=f"{tech}_GWh")
                              )
    total_transfer = xr.concat(season_transfer,dim="time").sortby("time") # add seasons together and sort chunks by time
    
    # Scale up to fit yearly avearge production values
    Scaled_total_transfer = scale_up(total_transfer,tech)
    
    print(f"Conversion for tech {tech} done. Now saving")
    # ===========================
    # === Step 3: Save output ===
    # ===========================
    store_as_pandas_dataframe(Scaled_total_transfer[f"{tech}_GWh"], f"hydro_{tech}_{year}")
    