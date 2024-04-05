from bias_correction_methods import bias_correct_dataset
from country_average import country_means, get_country_list
from utils import store_as_pandas_dataframe, zero_mean_longitudes, select_Europe, create_directories
import glob
import sys
import subprocess
import xarray as xr
import pandas as pd
import scipy
from sklearn.metrics import mean_squared_error

path = "/net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.1500/archive/lnd/hist/"

def open_runoff(year):
    """
    Returns an xarray data set of runoff in Europe for selected year. 
    :param year: int
    """
    year =int(year) #make sure to have year in int
    runoffs = []
    # opening the wanted year + one year before and after, so that even after rolling means we have a full calendar year
    for y in [year-1,year,year+1]:
        ds = xr.open_dataset(f"{path}b.e212.BHISTcmip6.f09_g17.1500.clm2.h6.{y}-01-01-03600.nc")
        runoff = ds.rename({"QRUNOFF":"runoff"})["runoff"].to_dataset()
        runoffs.append(zero_mean_longitudes(select_Europe(runoff)))
    #  only keeping one month before and after our calendar year
    runoff = xr.concat(runoffs,dim="time").sel(time=slice(f"{year-1}-12",f"{year+1}-01")) 
    # aggregate to daily values
    runoff = runoff.resample(time="D").sum()
    return runoff

def read_pecd_excel(file,sheet):
    """
    returns a pandas dataframe with the pecd information from a certain file in a certain sheet
    :param file:
    :param sheet:
    """
    df = pd.read_excel(file, 
                      sheet_name=sheet,
                      header=1,
                      usecols="D:AM", engine='openpyxl') # because we are forcing an old version of pandas
    return df

def open_pecd_generation():
    """
    Returns a data set of run-of-river energy generation per country for 1982-2017. 

    The countries are taken from the country list needed to run AnyMod on the European grid.
    
    Leap days are not included, as they are documented differently across pecd country input excel sheets.
    """
    countries = get_country_list() #countries to open
    pecd_countries = {}
    not_used = []
    for country in countries:
        #checking if file exists
        file = glob.glob(f"../inputs/pecd/PEMMDB_{countries[country]}00_Hydro_Inflows_2030.xlsx")
        if file != []: 
            # open excel as dataframe
            ror = read_pecd_excel(file[0],"Run of River - Year Dependent")
            pondage = read_pecd_excel(file[0],"Pondage - Year Dependent")
            pecd_df = ror.add(pondage,fill_value=0) # add one to the other
    
        else: # if country has several bidding zones, it will be treated here
            files = glob.glob(f"../inputs/pecd/PEMMDB_{countries[country]}*_Hydro_Inflows_2030.xlsx")
            if files != []: 
                dfs = []
                for file in files:
                    ror = read_pecd_excel(file,"Run of River - Year Dependent")
                    pondage = read_pecd_excel(file,"Pondage - Year Dependent")
                    dfs.append(ror.add(pondage,fill_value=0)) # add one to the other
                pecd_df = dfs[0]
                for d in dfs[1:]:
                    pecd_df = pecd_df.add(d,fill_value=0)
            else:
                not_used.append(country) #if it's empty, we have no data on this country, and it simply won't be part of our database
        pecd_df = pecd_df[0:365] # remove leap years (they are differently documented in different countries)
        if pecd_df.isna().all().all() == False: #if all values are nan, we skip this country
            df_values = pecd_df.transpose().stack().values #extract values in date format (not dayofyear-year)
            # date range for data (excel stores values as dayofyear+year)
            dates = xr.cftime_range(start="1982", end="2017-12-31", freq="D",calendar="noleap")
            pecd_countries[country] = xr.DataArray(df_values, 
                                                   dims=["time"],
                                                   coords ={"time":dates})
    # create dataset
    pecd = xr.concat([pecd_countries[country] for country in pecd_countries], dim = "country").to_dataset(name="generation")
    pecd["country"] = list(pecd_countries.keys()) 
    
    print(f"countries with no or empty data: {not_used}")
    return pecd

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
    # remove leap days
    era5 = era5.sel(time=~((era5.time.dt.month == 2) & (era5.time.dt.day == 29)))
    return era5

def open_entso_e_generation():
    # TODO: write up how to open entso e data
    return None

def weighted_aggregation(ds):
    # TODO: write up weighted average code
    return ds.mean(("lat","lon"))

def lin_transfer(runoff_cesm2, runoff_era,generation):
    """ 
    Creates a linear transfer function between PECD generation and ERA5 runoff.

    Applies this function to CESM2 runoff, to get its generation.
    
    :param runoff_cesm: runoff to be transferred to generation
    :param runoff_era: runoff input to create linear transfer function
    :param generation: generation input to create linear transfer function
    """
    slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(runoff_era,generation)
    return slope*runoff_cesm2 + intercept

def lin_transfer_all_countries(runoff_cesm2, runoff_era, generation):
    """ 
    Applies the function lin_transfer across countries.
    
    :param runoff_cesm: runoff to be transferred to generation
    :param runoff_era: runoff input to create linear transfer function
    :param generation: generation input to create linear transfer function
    """
    cesm2_generation = xr.apply_ufunc(
        lin_transfer, 
        runoff_cesm2, 
        runoff_era, 
        generation, 
        vectorize=True,
        input_core_dims=[["time"],["time"],["time"]],
        exclude_dims=set(("time",)),
        output_core_dims=[["time"]]
    )
    return cesm2_generation



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
    
    hydro = xr.Dataset()
    # === CESM2 runoff === 
    runoff = open_runoff(year)
    # Bias correction
    #runoff = bias_correct_dataset(runoff, "runoff").to_dataset("runoff")  TODO: fix bug
    
    # === ERA5 runoff (2017-2022) === 
    runoff_era5 = open_era()
    
    # === Smart aggregation over country for CESM2 and ERA5 ===
    runoff = weighted_aggregation(runoff)
    runoff_era5 = weighted_aggregation(runoff_era5)
    
    # === PECD generation (1982-2017) ===
    # conversion data set for run-or-river, already 1 value per country
    generation_pecd = open_pecd_generation()
    
    # === ENTSO-E generation (2016-2019) ===
    entso_e = open_entso_e_generation() # conversion data set for inflows 
    
    print("All files opened. Conversion starting")
    
    # ================================================
    # === Step 2: Convert to hydropower generation ===
    # ================================================
    
    # === Run-of-river ===
    # Treat seasons separately
    season_transfer = []
    for season in runoff.groupby("time.season"):
        runoff_era5_season = dict(runoff_era5.groupby("time.season"))[season[0]]
        generation_pecd_season = dict(generation_pecd.groupby("time.season"))[season[0]]
        season_transfer.append(lin_transfer_all_countries(season[1].runoff,
                                                          runoff_era5_season.runoff,
                                                          generation_pecd_season.generation
                                                         ).to_dataset(name="generation_cesm2")
                              )
    ror = xr.concat(season_transfer,dim="time").sortby("time") # add seasons together and sort chunks by time
    # Rolling mean
    ror = ror.rolling(time=7,center=True).mean()
    # TODO: change implementation to fit your needs
    
    # === Reservoir/pumped hydro ===
    # TODO: implement your setup (potentially streamline with r-o-r setup
    inflow = xr.DataArray()
    # Save both hydro types in one dictionary
    output = {
        "ror":ror.generation_cesm2,
        "inflow":inflow
    }
    
    # ===========================
    # === Step 4: Save output ===
    # ===========================
    for i,type in enumerate(output):
        store_as_pandas_dataframe(output[type], f"hydro_{type}_{year}")
    
    return None


if __name__ == "__main__":
    hydro_conversion()
