from utils import zero_mean_longitudes, select_Europe
import glob
import subprocess
import xarray as xr
import pandas as pd
import numpy as np
import scipy
import os
import statsmodels.api as sm
import datetime as dt
import pwlf

path = "/net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.1500/archive/lnd/hist/"

def preprocess_cesm_runoff(ds):
    """
    Returns a dataset of runoff for Europe with daily values
    :param ds: 
    """
    ds = select_Europe(zero_mean_longitudes(ds)) # selecting area and settin long to -180,180
    ds = ds.resample(time="D").sum() #resample to daily values
    ds = ds.rename({"QRUNOFF":"runoff"})["runoff"].to_dataset() #renaming and selecting only runoff
    ds = ds*3600 # to get output in mm/d
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
    runoff = xr.open_mfdataset(files,preprocess=preprocess_cesm_runoff,combine="nested")
    return runoff.load()

def open_era():
    """
    Opens ERA5 runoff for 2017-2022, to use for the transfer function between inflow/ror and runoff.

    If the file doesn't exist, the function executes a bash script that creates the necessary file
    """
    # ERA5 runoff for the ENTSO-e time range
    file = glob.glob("../output/runoff_ERA5_2016_2022.nc")
    if file == []:
        subprocess.run(["bash", f"preprocess/preprocess_runoff_ERA5_for_transfer.sh"])
        file = glob.glob("../output/runoff_ERA5_2016_2022.nc")
    era5 = xr.open_dataset(file[0])
    return era5

def open_weekly(ds,time_range=[]):
    if len(time_range) == 2:
        ds.sel(time=slice(time_range[0]+pd.Timedelta(days=0),time_range[1]+pd.Timedelta(days=7))) # open the right time range
    ds_weekly = ds.resample(time='1W',origin="start").sum()
    ds_weekly['time'] = (ds_weekly.time - pd.Timedelta(days=6)) # set labels t0 match inflow
    ds_weekly["time"] = ds_weekly.indexes['time'].normalize() # remove time component (sub-daily) of datetime
    return ds_weekly

def open_entsoe(tech):
    """
    Opens the ENTSO-e data for the technology specified (either inflow or ror)
    :param tech: string
    """
    if tech == "inflow":
        return open_entsoe_inflow()
    elif tech == "ror":
        return open_entsoe_ror()
    else:
        print("Technology not recognized. Please choose 'inflow' or 'ror'")

def open_entsoe_ror():
    """
    Opens the ENTSO-e data for the ror technology.
    """
    year_0 = 2017
    year_N = 2022

    folder_path = "../inputs/entsoe_ror/"
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
            df_ror_full['time'] = df_ror_full['MTU'].apply(lambda x: dt.datetime(year=int(x[6:10]), month=int(x[3:5]), day=int(x[0:2])))
            df_ror_full['delta_time'] = df_ror_full['MTU'].apply(lambda x: (dt.datetime.strptime(x.split(" - ")[1].split(" ")[0] +' '+x.split(" - ")[1].split(" ")[1], "%d.%m.%Y %H:%M") - dt.datetime.strptime(x.split(" - ")[0], "%d.%m.%Y %H:%M")).total_seconds() / 3600)

            # Calculate GWh per each time step
            df_ror_full['ror_GWh'] = df_ror_full['Hydro Run-of-river and poundage  - Actual Aggregated [MW]']*df_ror_full['delta_time']/1000

            # Group ror production by date
            ds_time.append(df_ror_full[['ror_GWh','time']].groupby('time').sum().to_xarray())
        ds_ror.append(xr.concat(ds_time, dim='time'))
    ds_ror = xr.concat(ds_ror, dim='country') 
    ds_ror['country'] = country_list

    return ds_ror

def open_entsoe_inflow():
    year_0 = 2016
    year_N = 2019

    folder_path = "../inputs/entsoe_inflow/"

    #read all files, each file corresponds to a country
    files = glob.glob(folder_path + "*.csv")
    file_names = [f.split("/")[-1] for f in files]
    country_list = [f.split("_")[1] for f in file_names]

    start_date = dt.datetime(year_0, 1, 4)
    end_date = dt.datetime(year_N, 12, 26)

    # Generate the weekly timeseries
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date)
        current_date += dt.timedelta(days=7)

    # Create the dataset
    ds_inflow = xr.Dataset(coords={'time': dates,'country': country_list}, data_vars={'inflow_GWh': (('time', 'country'), np.full((len(dates), len(country_list)),np.nan))})

    # Fill the dataset
    for country in country_list:
        df_inflow = pd.read_csv(folder_path + 'Inflow_' +country +"_2016-2019.csv")
        df_inflow['ind'] = pd.to_datetime(df_inflow['ind'])
        df_inflow = df_inflow.drop_duplicates(subset='ind', keep='first')

        # Add the country inflow in the dataset
        ds_inflow['inflow_GWh'].loc[dict(time=df_inflow['ind'].values,country=country)] = df_inflow['0'].values

    return ds_inflow

def weighted_aggregation(ds_runoff,tech):
    """
    Aggregates the runoff data to country level, using the JRC dataset as a reference for the weighting coefficients.
    """

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
    file_path = "../inputs/jrc-hydro-power-plant-database.csv"
    df_jrc = pd.read_csv(file_path)
    country_list=df_jrc['country_code'].unique().tolist()

    # Create the dataset
    ds_C = xr.Dataset(
        data_vars=dict(
            normalized_capacity=(["lat", "lon", "country"],  np.zeros((len(lat),len(lon),len(country_list)))),
        ),
        coords=dict(
            country=country_list,
            lat=lat,
            lon=lon
        ),
        attrs=dict(description="Installed hydro capacity (normalized per country)"),
    )

    # Define the type of power plants to consider
    if tech == "ror":
        type_code = ["HROR"]
    elif tech == "inflow":
        type_code = ["HDAM","HPHS"]

    # Fill the dataset  
    for country_code in country_list:
        C = np.zeros((len(lat),len(lon)))
        for ii in range(len(lon)): 
            for jj in range(len(lat)):
                C[jj,ii] = df_jrc["installed_capacity_MW"][(df_jrc["type"].isin(type_code)) & (df_jrc["country_code"]==country_code) & (lon_edge[ii]<df_jrc["lon"]) & (df_jrc["lon"]<lon_edge[ii+1]) & (lat_edge[jj]<df_jrc["lat"]) & (df_jrc["lat"]<lat_edge[jj+1])].sum()

        ds_C.normalized_capacity.loc[{'country':country_code}] = C[:,:] / df_jrc["installed_capacity_MW"][(df_jrc["type"].isin(type_code)) & (df_jrc["country_code"]==country_code)].sum()
        
    # Calculate the runoff per country
    ds_w = []
    for country in country_list:
        ds = (ds_C.normalized_capacity.sel(country=country) * ds_runoff.runoff).sum(('lat','lon'))
        ds_w.append(ds)
    ds_w = xr.concat(ds_w, dim='country')
    ds_w = ds_w.to_dataset(name='runoff')

    return ds_w

def lin_transfer(runoff_cesm2, calibration,tech):
    """ 
    Creates a linear transfer function between entsoe inflow/ror and ERA5 runoff as f(x) = ax + b.

    Applies this function to CESM2 runoff, to get its inflow/ror.
    
    :param runoff_cesm: runoff to be transferred to inflow/ror
    ::param calibration: ds including era5 runoff and entsoe inflow/ror to create linear transfer function
    :param tech:  string
    """
    slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(calibration.runoff,calibration[f"{tech}_GWh"]) 
    return slope*runoff_cesm2 + intercept

def lin_transfer_no_b(runoff_cesm2, calibration,tech):
    """ 
    Creates a linear transfer function between ENTSO-e inflow/ror and ERA5 runoff as f(x) = ax (no b).

    Applies this function to CESM2 runoff, to get its inflow/ror.
    
    :param runoff_cesm: runoff to be transferred to inflow/ror
    :param calibration: ds including era5 runoff and entsoe inflow/ror to create linear transfer function
    :param tech:  string
    """
    model = sm.OLS(calibration[f"{tech}_GWh"].values,calibration.runoff.values)
    slope = model.fit().params 
    return slope*runoff_cesm2

def condition_75th(ds, q, over_under):
    if over_under == "over":
        return ds > q
    elif over_under == "under":
        return ds < q

def lin_transfer_all_countries(runoff_cesm2, calibration,tech,qu_75=np.nan):
    """ 
    Applies a linear transfer function across countries. If qu_75 is nan, it applies f(x) = ax + b for all values. Else, qu_75 is the value at which you differentiate: f(x) = ax for runoff < qu_75 (normal values), and f(x) = ax + b for runoff > qu_75 (spillover)
    
    :param runoff_cesm: runoff to be transferred to inflow/ror
    :param calibration: ds including era5 runoff and entsoe inflow/ror to create linear transfer function
    :param tech:  string
    :kwarg qu_75: if not nan, 75th percentile of CESM2 runoff values, to separate between linear transfer types
    """
    transferred = []
    for country in calibration.country:
        calib_country = calibration.sel(country=country).dropna(dim="time") #linear regressions can't handle nans
        runoff_country = runoff_cesm2.sel(country=country)
        qu_75_country = qu_75.sel(country=country)
        if len(calib_country.runoff) > 0:
            if np.isnan(qu_75_country) == False: #linear transfer differentiated based on 75th percentile value 
                # fit a linear regression with a kink at 75th percentile (under 75th percentile, intercept = 0)
                if qu_75_country.values > max(calib_country.runoff):
                    # if entire sample is under total 75th percentile, just do regular linear regression with no intercept
                    predicted = lin_transfer_no_b(runoff_country, calib_country,tech).values
                elif min(calib_country.runoff) > qu_75_country.values: 
                    # if entire sample is under total 75th percentile, just do regular linear regression with no intercept
                    predicted = lin_transfer(runoff_country, calib_country,tech).values
                else:
                    x_kink = np.array([min(calib_country.runoff), qu_75_country.values, max(calib_country.runoff)])
                    # initialize piecewise linear fit
                    my_pwlf = pwlf.PiecewiseLinFit(calib_country.runoff,calib_country[f"{tech}_GWh"])
                    # fit the data with the specified break point and force to go through 0
                    my_pwlf.fit_with_breaks_force_points(x_kink,[0],[0])
                    predicted = my_pwlf.predict(runoff_country)
                cesm2_transferred = xr.DataArray(predicted,dims=["time"],coords ={"time":runoff_country.time})
            else: # no differentiating based on 75th percentile
                # f(x) = ax + b                                     
                cesm2_transferred = lin_transfer(runoff_country,calib_country,tech)
            transferred.append(cesm2_transferred)
        else:
            transferred.append(runoff_country*0) #return dataarray of zeros
    transferred = xr.concat(transferred,dim="country")
    transferred["country"] = list(calibration.country.values)
    return transferred

def read_annual_prod(countries, tech):
    """
    Reads the annual production of hydropower for each country of interest, for the hydropower technology specified
    :param countries: list of country codes
    :param tech: string
    """
    prod_per_country = np.zeros(len(countries))
    delim = [";","\t",","] # different years have different delimiters for their .csv file
    time_range = range(2021,2024) #time range considered
    for j,year in enumerate(time_range):
        annual_prod = pd.read_csv(f"../inputs/entsoe/monthly_domestic_values_{year}.csv",delimiter=delim[j])
        for i,country in enumerate(countries):
            annual_prod_country = annual_prod[annual_prod['Country'] == country] #choosing country
            if tech == "ror":
                # select technology and sum over months
                annual_prod_country = annual_prod_country[annual_prod_country["Category"] == "Hydro Run-of-river and poundage"]["ProvidedValue"].sum()
                prod_per_country[i] += annual_prod_country #adding annual sum for each year
            elif tech == "inflow":
                for sub_tech in["Hydro Water Reservoir", "Hydro Pumped Storage"]:
                    # select sub-technology and sum over months
                    annual_prod_sub_tech = annual_prod_country[annual_prod_country["Category"] == sub_tech]["ProvidedValue"].sum()
                    prod_per_country[i] += annual_prod_sub_tech # adding annual sum for each year, for both subtechnologies together
                    
    prod_per_country=prod_per_country/len(time_range) #average to annual mean production
    #create output xarray dataarray
    prod_per_country = xr.DataArray(prod_per_country,dims=["country"],coords ={"country":list(countries)})
    return prod_per_country

def scale_up(ds,tech):
    """
    Scales output to fit average annual hydropower production values for each country
    :param ds: DataArray of transformed runoff-to-hydro, per country
    :param tech: string
    """
    prod_per_country = read_annual_prod(ds.country.values, tech)
    scaled_output = []
    for country in ds.country:
        ann_prod = prod_per_country.sel(country=country)
        day_by_day = ds.sel(country=country)
        nb_years = len(day_by_day.groupby("time.year").sum().year) #number of years in total
        ann_prod_non_scaled = day_by_day[f"{tech}_GWh"].sum()/nb_years #average yearly values for this dataset
        scaled = day_by_day * (ann_prod.values/ann_prod_non_scaled.values) 
        scaled_output.append(scaled)
    scaled_output = xr.concat(scaled_output,dim="country")
    scaled_output["country"] = list(ds.country.values)
    return scaled_output
