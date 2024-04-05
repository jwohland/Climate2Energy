from bias_correction_methods import bias_correct_dataset
from country_average import country_means, get_country_list
from utils import store_as_pandas_dataframe, zero_mean_longitudes, select_Europe, create_directories
import glob
import sys
import subprocess
import xarray as xr
import pandas as pd
import numpy as np
import scipy
import os
import statsmodels.api as sm

path = "/net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.1500/archive/lnd/hist/"

def preprocess_cesm_runoff(ds):
    """
    Returns a dataset of runoff for Europe with daily values
    :param ds: 
    """
    ds = zero_mean_longitudes(select_Europe(ds)) # selecting area and settin long to -180,180
    ds = ds.resample(time="D").sum() #resample to daily values
    ds = ds.rename({"QRUNOFF":"runoff"})["runoff"].to_dataset() #renaming and selecting only runoff
    return ds

def quantile_75(ds):
    """
    returns the value of the 75th percentile of dataset ds
    :param ds: 
    """
    return np.nanquantile(ds,0.75)
    
def get_qu_75(ds):
    """
    returns the value of the 75th percentile of dataset ds for all countries
    :param ds: 
    """
    qu = xr.apply_ufunc(quantile_75,ds.runoff,
            vectorize=True,
            input_core_dims=[["time"]],
            exclude_dims=set(("time",))    
            )
    return qu

def open_runoff(year, end_year=np.nan):
    """
    Opens and preprocesses runoff data (see function preprocess_cesm_runoff) for a certain year. If end year is passed as an int, it opens all years between year and end_year (included)
    :param year: int
    :kwarg end_year: int
    """
    year =int(year) #make sure to have year in int
    if np.isnan(end_year) == False: 
        end_year = int(end_year) #make sure to have year in int
        time_range = range(year,end_year+1)
    else:
        time_range = [year]
    # opening all wanted files
    files = [f"{path}b.e212.BHISTcmip6.f09_g17.1500.clm2.h6.{y}-01-01-03600.nc" for y in time_range]
    runoff = xr.open_mfdataset(files,preprocess=preprocess_cesm_runoff)
    return runoff

def open_era():
    """
    Opens ERA5 runoff for 2017-2022, to use for the transfer function between generation and runoff.

    If the file doesn't exist, the function executes a bash script that creates the necessary file
    """
    file = glob.glob("../output/runoff_ERA5_2017_2022.nc")
    # TODO: avoid running this twice (also done for bias correction, but not exactly the same time frame)
    if file == []:
        subprocess.run(["bash", f"preprocess/preprocess_runoff_ERA5_for_transfer.sh"])
        file = glob.glob("../output/runoff_ERA5_2017_2022.nc")
    era5 = xr.open_dataset(file[0])
    # remove leap days TODO: remove this
    era5 = era5.sel(time=~((era5.time.dt.month == 2) & (era5.time.dt.day == 29)))
    return era5

def open_entsoe_ror():
    year_0 = 2017
    year_N = 2022

    folder_path = "inputs/entsoe_ror/"
    # read all the folders in the path. Each folder corresponds to a country
    country_list = [folder for folder in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, folder))]

    years = range(year_0, year_N+1)

    ds_ror =[]

    for country in country_list:
        ds_time = []
        for year in years:
            # Load data
            df_ror_full = pd.read_csv(folder_path+country+'/Actual Generation per Production Type_'+str(year)+'01010000-'+str(year+1)+'01010000.csv')

            # Convert date to datetime and delta_time (the MTU column has this format:"01.01.2022 00:00 - 01.01.2022 01:00 (CET/CEST)")
            df_ror_full['time'] = df_ror_full['MTU'].apply(lambda x: datetime.datetime(year=int(x[6:10]), month=int(x[3:5]), day=int(x[0:2])))
            df_ror_full['delta_time'] = df_ror_full['MTU'].apply(lambda x: (datetime.datetime.strptime(x.split(" - ")[1].split(" ")[0] +' '+x.split(" - ")[1].split(" ")[1], "%d.%m.%Y %H:%M") - datetime.datetime.strptime(x.split(" - ")[0], "%d.%m.%Y %H:%M")).total_seconds() / 3600)

            # Calculate GWh per each time step
            df_ror_full['ror_GWh'] = df_ror_full['Hydro Run-of-river and poundage  - Actual Aggregated [MW]']*df_ror_full['delta_time']/1000

            # Group ror production by date
            ds_time.append(df_ror_full[['ror_GWh','time']].groupby('time').sum().to_xarray())
        ds_ror.append(xr.concat(ds_time, dim='time'))
    ds_ror = xr.concat(ds_ror, dim='country') 
    ds_ror['country'] = country_list

    return ds_ror

def open_entsoe_reservoir():
    # TODO: write up how to open entso e data
    return None

def weighted_aggregation_ror(ds_runoff):
    """
    Aggregates the runoff data to country level, using the JRC dataset as a reference for the weighting coefficients.
    """
    year_0 = 2017
    year_N = 2022

    # Create a dataset with the normalized installed capacity of ror power plants per country
    lat = ds_runoff.lat.values
    lon = ds_runoff.lon.values
    lat_edge = (lat[:-1]+lat[1:])/2
    lon_edge = (lon[:-1] + lon[1:])/2
    lon_edge = np.insert(lon_edge,0,-1000)
    lon_edge = np.append(lon_edge,1000)
    lat_edge = np.insert(lat_edge,0,0)
    lat_edge = np.append(lat_edge,1000)

    # Load the JRC dataset
    file_path = "inputs/jrc-hydro-power-plant-database.csv"
    df_jrc = pd.read_csv(file_path)
    country_list=df_jrc['country_code'].unique().tolist()

    # Create the dataset
    ds_C_ror = xr.Dataset(
        data_vars=dict(
            C_ror=(["lat", "lon", "country"],  np.zeros((48,53,30))),
        ),
        coords=dict(
            country=country_list,
            lat=lat,
            lon=lon
        ),
        attrs=dict(description="Installed ror capacity (normalized per country)"),
    )

    # Fill the dataset  
    for country_code in country_list:
        C_ror = np.zeros((48,53))
        for ii in range(len(lon)): 
            for jj in range(len(lat)):
                C_ror[jj,ii] = df_jrc["installed_capacity_MW"][(df_jrc["type"]=='HROR') & (df_jrc["country_code"]==country_code) & (lon_edge[ii]<df_jrc["lon"]) & (df_jrc["lon"]<lon_edge[ii+1]) & (lat_edge[jj]<df_jrc["lat"]) & (df_jrc["lat"]<lat_edge[jj+1])].sum()

        ds_C_ror.C_ror.loc[{'country':country_code}] = C_ror[:,:] / df_jrc["installed_capacity_MW"][(df_jrc["type"]=='HROR') & (df_jrc["country_code"]==country_code)].sum()
        
    # Calculate the runoff per country
    ds_w = []
    for country in country_list:
        ds = (ds_C_ror.C_ror.sel(country=country) * ds_runoff.runoff.sel(time=slice(str(year_0)+"-01-01T11:30:00.000000000",str(year_N)+"-12-31T11:30:00.000000000"))).sum(dim=['lat','lon'])
        ds_w.append(ds)
    ds_w = xr.concat(ds_w, dim='country')
    ds_w = ds_w.to_dataset(name='runoff')

    return ds_w

def weighted_aggregation_reservoir(ds):
    # TODO: write up weighted average code
    return ds.mean(("lat","lon"))

def lin_transfer(runoff_cesm2, runoff_era,inflow_entsoe):
    """ 
    Creates a linear transfer function between PECD generation and ERA5 runoff as f(x) = ax + b.

    Applies this function to CESM2 runoff, to get its inflow.
    
    :param runoff_cesm: runoff to be transferred to generation
    :param runoff_era: runoff input to create linear transfer function
    :param inflow_entsoe: inflow input to create linear transfer function
    """
    slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(runoff_era,inflow_entsoe) #TODO: make sure it works for Nans (ignore them)
    return slope*runoff_cesm2 + intercept

def lin_transfer_no_b(runoff_cesm2, runoff_era,inflow_entsoe):
    """ 
    Creates a linear transfer function between PECD generation and ERA5 runoff as f(x) = ax (no b).

    Applies this function to CESM2 runoff, to get its inflow.
    
    :param runoff_cesm: runoff to be transferred to generation
    :param runoff_era: runoff input to create linear transfer function
    :param inflow_entsoe: inflow input to create linear transfer function
    """
    model = sm.OLS(inflow_entsoe,runoff_era)
    slope = model.fit().params #TODO: make sure it works for Nans (ignore them)
    return slope*runoff_cesm2

def lin_transfer_all_countries(runoff_cesm2, runoff_era, inflow_entsoe,qu_75=np.nan):
    """ 
    TODO: update description
    Applies a linear transfer function across countries. If qu_75 is nan, it applies f(x) = ax + b for all values. Else, qu_75 is the value at which you differentiate: f(x) = ax for runoff < qu_75 (normal values), and f(x) = ax + b for runoff > qu_75 (spillover)
    
    :param runoff_cesm: runoff to be transferred to generation
    :param runoff_era: runoff input to create linear transfer function
    :param inflow_entsoe: inflow input to create linear transfer function
    :kwarg qu_75: if not nan, 75th percentile of CESM2 runoff values, to separate between linear transfer types
    """
    runoffs_inflow = [runoff_cesm2, runoff_era, inflow_entsoe]
    inflows = []
    for country in runoff_cesm2.countries:
        qu_75_country = qu_75.sel(country=country)
        if np.isnan(qu_75_country) == False: #linear transfer differentiated based on 75th percentile value 
            # f(x) = ax for values under qu_75 
            args_for_lin_transfer_no_b = []
            for ds in runoffs_inflow:
                args_for_lin_transfer_no_b.append(ds.where(ds < qu_75_country,drop=True))
            # apply function over all grid cells
            cesm2_inflow_no_b = lin_transfer_no_b(*args_for_lins_transfer)
            # f(x) = ax + b for values above qu_75
            args_for_lin_transfer = []
            for ds in runoffs_inflow:
                args_for_lin_transfer.append(ds.where(ds > qu_75_country,drop=True))
        else: # no differentiating based on 75th percentile
            args_for_lin_transfer = runoffs_inflow
        # f(x) = ax + b                                     
        cesm2_inflow = lin_transfer(*args_for_lin_transfer)
        if np.isnan(qu_75) == False:
            cesm2_inflow = xr.concat([cesm2_inflow_no_b,cesm2_inflow],dim="time").sortby("time")
        inflows.append(cesm2_inflow)
    inflows = xr.concat(inflows,dim="country")
    inflows["country"] = list(runoff_cesm2.countries)
        
    return inflows



def hydro_conversion():
    """
    Execute conversion from CESM2 output to hydropower over a chosen year.

    :return:
    """
    try:
        year = str(sys.argv[1])  # can be any year between 1990 and 2010
    except IndexError:
        year = "2010"
    print(year)
    
    # create necessary directories (for pecd and entso-e data)
    create_directories()
    
    # =====================================================
    # === Step 1: Open, bias correct and aggregate data ===
    # =====================================================
    
    # === CESM2 runoff === 
    print("Open and bias correct CESM2 runoff")
    runoff = open_runoff(year) # you can pass end_year to it to open several years in row
    # Bias correction
    #runoff = bias_correct_dataset(runoff, "runoff").to_dataset("runoff")  TODO: fix bug
    
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
    
    # === Reservoir/pumped hydro ===
    # TODO: implement your setup (potentially streamline with r-o-r setup
    reservoir = xr.DataArray()
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
    
    return None


if __name__ == "__main__":
    hydro_conversion()
