import xarray as xr
from utils import select_Europe, zero_mean_longitudes
from downscaling_discharge import downscale
from tqdm import tqdm

def preprocess_cesm(ds,var="discharge"):
    """
    Returns a dataset of river discharge or runoff (param var) for Europe
    :param ds: 
    :param var: str
    """
    ds = select_Europe(zero_mean_longitudes(ds)) # selecting area and settin long to -180,180
    if var == "discharge":
        land_dis = xr.where(ds.RIVER_DISCHARGE_OVER_LAND_LIQ > 0, ds.RIVER_DISCHARGE_OVER_LAND_LIQ, 0)
        ocean_dis = xr.where(ds.TOTAL_DISCHARGE_TO_OCEAN_LIQ > 0, ds.TOTAL_DISCHARGE_TO_OCEAN_LIQ, 0)
        ds = (land_dis+ocean_dis)
        ds = ds.where(ds > 0).to_dataset(name="discharge") #renaming and selecting only river discharge
    elif var == "runoff":
        ds = ds.rename({"QRUNOFF":"runoff"})["runoff"].to_dataset() #renaming and selecting only runoff
    else:
        print("variable unknown")
        return None
    return ds


periods = {"HIST":{"time_range":range(1995,2015),
                   "realizations":["1500","1000","1200"],
                  }, 
           "SSP370": {"time_range": range(2080,2100),
                      "realizations":["1500","0600","0900"],
                     },
           # "SSP245": {"time_range": range(2080,2100),
           #            "realizations":["1500"],
           #           },
          }
out_path = f"/net/xenon/climphys/lbloin/CESM2energy_data/CESM2_discharge/"

# === open preprocess downscale ===
for period in periods:
    print(period)
    for realization in periods[period]["realizations"]:
        print(realization)
        path  = f"/net/meso/climphys/cesm212/b.e212.B{period}cmip6.f09_g17.{realization}/archive/"
        files_dis = []	
        files_run = []
        for year in (periods[period]["time_range"]):
            for month in ["01","02","03","04","05","06","07","08","09","10","11","12"]:	
                files_dis.append(f"{path}rof/hist/b.e212.B{period}cmip6.f09_g17.{realization}.mosart.h0.{year}-{month}.nc")	
            files_run.append(f"{path}lnd/hist/b.e212.B{period}cmip6.f09_g17.{realization}.clm2.h6.{year}-01-01-03600.nc")
        # get monthly discharge
        discharge = xr.open_mfdataset(files_dis,preprocess=preprocess_cesm,combine="nested").load()
        # get daily runoff
        def preprocess(ds):
            return preprocess_cesm(ds,var="runoff")
        runoff = xr.open_mfdataset(files_run,preprocess=preprocess,combine="nested").load().resample(time="1D").mean()
        # downscale and save
        downscale(discharge,runoff,f"{out_path}{period}_{realization}_discharge.nc")
        # saving individual years
        downscaled = xr.open_dataset(f"{out_path}{period}_{realization}_discharge.nc")
        for year in tqdm(periods[period]["time_range"]):
            downscaled.sel(time=str(year)).to_netcdf(f"{out_path}{period}_{realization}_{year}_discharge_tot.nc")