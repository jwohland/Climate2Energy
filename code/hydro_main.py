from bias_correction_methods import bias_correct_dataset
from utils import store_as_pandas_dataframe
from conversion_to_hydro import *
import sys
import xarray as xr
import pandas as pd
import numpy as np

# create necessary directories (for pecd and entso-e data)
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
# aggregation
for tech in technologies:
    print(f"Aggregate CESM for tech {tech}")
    runoff = weighted_aggregation(runoff_full,tech)
    # rolling means
    runoff = runoff.rolling(time=rolling[tech],center=True).mean()

    # === ERA5 runoff and ENTSO-e data (2017-2022) === 
    print(f"Open ERA5 runoff and ENTSO-e data for tech {tech}")
    # ERA5
    era_runoff = open_era()
    calibration_ds = weighted_aggregation(era_runoff,tech)
    # ENTSO-e
    calibration_ds[f"{tech}_GWh"] = open_entsoe(tech)[f"{tech}_GWh"] # conversion data set for inflows 
    # rolling means
    calibration_ds = calibration_ds.rolling(time=rolling[tech],center=True).mean()

    print(f"All {tech} files opened and preprocessed. Conversion starting")

    # =====================================
    # === Step 2: Convert to hydropower ===
    # =====================================
    
    # get 75th percentile of runoff (use ERA5 to get multiple years of data), for each country regardless of season
    qu_75 = get_qu_75(calibration_ds)
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
    