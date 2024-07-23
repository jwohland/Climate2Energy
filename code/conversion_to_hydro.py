from utils import zero_mean_longitudes, select_Europe, get_time_range,quantile_75, get_qu_75, get_cesm_dict
import glob
import xarray as xr
import pandas as pd
import numpy as np
import scipy
import os
import datetime as dt
from scipy.optimize import minimize
from tqdm import tqdm
import cftime

# =================================
# === PREPROCESSING AND OPENING ===
# =================================

def downscale(ds_discharge,ds_runoff,save_info):
    ## Do mean of runoff over latitude and longitude (One value per day, spatially aggregated)
    ds_runoff_mean = ds_runoff.mean(dim=["lon", "lat"])
    ## Get the monthly average of runoff, and then the normlized profiles of runoff
    ds_runoff_mean.coords['year_month'] = ('time', ds_runoff_mean.time.dt.strftime('%Y-%m').data)
    
    monthly_ave = ds_runoff_mean.groupby('year_month').mean(dim='time')
    year_month_str = ds_runoff_mean.time.dt.strftime('%Y-%m').data
    monthly_ave_data = monthly_ave.sel(year_month=year_month_str).runoff.data
    runoff_monthly_ave = xr.DataArray(
        data=monthly_ave_data,
        dims='time',
        coords={'time': ds_runoff_mean.time}
    )
    ds_runoff_mean['runoff_normalized'] = ds_runoff_mean.runoff / runoff_monthly_ave
    ds_runoff_mean = ds_runoff_mean.drop_vars('year_month')
    ## Sincronyze all time stamps to midnight
    def normalize_to_midnight(time_array):
        return [cftime.DatetimeNoLeap(t.year, t.month, t.day, 0, 0, 0, 0, has_year_zero=t.has_year_zero) for t in time_array]
    ds_runoff_mean['time'] = normalize_to_midnight(ds_runoff_mean.time.values)
    ## Expand monthly discharge to daily discharge
    ds_discharge_daily = ds_discharge.resample(time='1D').ffill().rename({'discharge': 'discharge_monthly_ave'})
    ds_discharge_daily['time'] = ds_discharge_daily.time + dt.timedelta(days=-31)  #shift one month back
    ## Match time coordinates of the two datasets: discharge_daily and runoff_mean
    ds_runoff_mean = ds_runoff_mean.sel(time=ds_discharge_daily.time)
    ## Expand runoff_mean, to include latitude and longitude
    ds_runoff_mean = ds_runoff_mean.broadcast_like(ds_discharge_daily)
    ## Calculate daily values of river discharge
    ds_discharge_daily['discharge'] =  ds_discharge_daily.discharge_monthly_ave * ds_runoff_mean.runoff_normalized
    
    ds_discharge_daily.to_netcdf(save_info)
    return None


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



def create_discharge(scenario,realization):
    out_path = f"/net/xenon/climphys/lbloin/CESM2energy_data/CESM2_discharge/"
    # translate parameters for file paths
    if scenario == "historical":
        period = "HIST"
    else:
        period = scenario
    file_real = get_cesm_dict()[scenario][realization]
    time_range = get_time_range(scenario)
    # === open preprocess downscale ===
    path  = f"/net/meso/climphys/cesm212/b.e212.B{period}cmip6.f09_g17.{file_real}/archive/"
    files_dis = []	
    files_run = []
    for year in time_range:
        for month in ["01","02","03","04","05","06","07","08","09","10","11","12"]:	
            files_dis.append(f"{path}rof/hist/b.e212.B{period}cmip6.f09_g17.{file_real}.mosart.h0.{year}-{month}.nc")	
        files_run.append(f"{path}lnd/hist/b.e212.B{period}cmip6.f09_g17.{file_real}.clm2.h6.{year}-01-01-03600.nc")
    # get monthly discharge
    discharge = xr.open_mfdataset(files_dis,preprocess=preprocess_cesm,combine="nested").load()
    # get daily runoff
    def preprocess(ds):
        return preprocess_cesm(ds,var="runoff")
    runoff = xr.open_mfdataset(files_run,preprocess=preprocess,combine="nested").load().resample(time="1D").mean()
    # downscale and save
    downscale(discharge,runoff,f"{out_path}{scenario}_{realization}_discharge.nc")
    return None

def open_discharge(scenario, realization):
    """
    Opens and preprocesses discharge data (see function preprocess_cesm_discharge) for a certain year. If end year is passed as an int, it opens all years between year and end_year (included)
    :param scenario, realization: str
    """
    f = f"/net/xenon/climphys/lbloin/CESM2energy_data/CESM2_discharge/{scenario}_{realization}_discharge.nc"
    file = glob.glob(f)
    if file == []:
        print("River discharge files not found. Creating them.")
        create_discharge(scenario,realization)
        file = glob.glob(f)
    ds = xr.open_dataset(file[0])
    return ds.convert_calendar("proleptic_gregorian") # new calendar to get numpy datetime (necessary for weekly resampling)

def preprocess_era(ds,cesm_lat,cesm_lon):
    """
    changes variable names to fit CESM2 standard, and changes lat order to go from 90->-90 to -90->90
    :param ds: dataset
    :param cesm_lat: latitude grid of CESM2, 
    """
    ds = ds.rename({"latitude":"lat","longitude":"lon","dis24":"discharge"})
    ds=ds.reindex(lat=ds.lat[::-1])
    ds_co = ds.coarsen(lat=10,lon=10, boundary="trim").sum()
    #ds_co = select_Europe(ds_co)
    # since the ERA5 grid is exactly 10 higher resolution than CESM2, the two grids should have the same length after selecting Europe. However, there might be slight differences in the absolute values of the grids (lat = 30.2 instead of 30.25) due to the coarsening. That is why we assign the lat and lon values of CESM2 here.
    if len(ds_co.lat) == len(cesm_lat) and len(ds_co.lon) == len(cesm_lon):
        ds_co["lat"] = cesm_lat
        ds_co["lon"] = cesm_lon
    else:
        print("Error: CESM2 and ERA5 grid are not same length")
    return ds_co

def open_era(cesm_lat,cesm_lon):
    """
    Opens ERA5 discharge, and preprocesses it to fit the naming conventions 
    If the file doesn't exist, the function executes a bash script that creates the necessary file
    """
    # ERA5 discharge for the ENTSO-e time range
    file = glob.glob(f"../output/bias_correction/Raw_ERA5_discharge.nc")
    def preprocess_era_here(ds):
        return preprocess_era(ds,cesm_lat,cesm_lon)
    if file == []:
        files = [f"/net/xenon/climphys/lbloin/CESM2energy_data/ERA5_discharge/discharge_{year}.nc" for year in range(1995,2023)] #historical+calbration ERA5 data
        era5 = xr.open_mfdataset(files,preprocess=preprocess_era_here,combine="nested")
        era5.to_netcdf(f"../output/bias_correction/Raw_ERA5_discharge.nc")
    else:
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

def create_historical_inflow():

    ## CREATE TIME DATAFRAME ##
    
    year_0 = 2016
    year_N = 2023
    
    start_date = dt.datetime(year_0, 1, 4)
    end_date = dt.datetime(year_N, 12, 25)
    
    dates = []
    weeks = []
    years = []
    current_date = start_date
    current_year = year_0
    week = 1
    while current_date <= end_date:
        dates.append(current_date)
        weeks.append(week)
        years.append(current_year)
        current_date += dt.timedelta(days=7)
        if (current_date+dt.timedelta(days=2)).year > current_year:
            current_year += 1
            week = 1
        else:
            week += 1
    
    df_time = pd.DataFrame({'date': dates, 'week': weeks, 'year': years})
    
    ## COUNTRY LIST ##
    country_list = ['AT','BG','FR','IT','ME','NO','PT','RO','ES','SE','CH'] 
    
    
    ## CREATE DATASET ##
    ds_old = xr.Dataset(
        coords={
            'country': country_list,'time': df_time.date
            },
        data_vars={
            'V': (['country', 'time'], np.full((len(country_list), len(df_time)), np.nan)),
            'gen': (['country', 'time'], np.full((len(country_list), len(df_time)), np.nan)),
            'delta_V': (['country', 'time'], np.full((len(country_list), len(df_time)), np.nan)),
            'inflow_GWh': (['country', 'time'], np.full((len(country_list), len(df_time)), np.nan)),
        }
    )
    
    
    ## READ FILLING LEVELS ##
    for country in tqdm(country_list, desc='Reading filling levels per country'):
        filename = f'../inputs/entsoe_historic_inflow/{country}/Water Reservoirs and Hydro Storage Plants_201412290000-202412300000.csv'
        df_V = pd.read_csv(filename)
        V = []
        for year in range(year_0,year_N+1):
            mask = df_V.columns.str.contains(str(year))
            V.extend(df_V.loc[:len(df_time[df_time.year==year])-1, mask].interpolate().copy().values.flatten()/1000)
        ds_old['V'].loc[{'country':country}] = xr.DataArray(V, dims=('time'))
    
    
    ## CALCULATE DELTA V ##
    ds_old['delta_V'] = ds_old['V'].diff('time')
    ds_old['delta_V'] = ds_old['delta_V'].shift(time=-1)
    
    
    ## READ GENERATION ##
    date_format = "%d.%m.%Y %H:%M"
    
    for country in tqdm(country_list, desc='Reading reservoir generation per country'):
        df_gen = pd.DataFrame(columns=['time','gen_GWh'])
        for year in range(year_0,year_N+1):
            filename = f'../inputs/entsoe_historic_inflow/{country}/Actual Generation per Production Type_{str(year)}01010000-{str(year+1)}01010000.csv'
            df_gen_y = pd.read_csv(filename)
            df_gen_y = df_gen_y.interpolate()
            df_gen_y['time'] = df_gen_y['MTU'].apply(lambda x:  dt.datetime.strptime(x[:15], date_format))
            df_gen_y['time_delta'] = (df_gen_y.time.shift(-1) - df_gen_y.time).dt.total_seconds()/3600
            df_gen_y['gen_GWh'] = df_gen_y['Hydro Water Reservoir  - Actual Aggregated [MW]'] * df_gen_y['time_delta']/1000 
            df_gen = pd.concat([df_gen, df_gen_y[['time', 'gen_GWh']]], axis=0)
        sum_gen = []
        for date in df_time.date:
            start_date = date
            end_date = date + dt.timedelta(days=7)
            sum_gen.append(df_gen[(df_gen.time >= start_date) & (df_gen.time < end_date)].gen_GWh.sum())
        ds_old['gen'].loc[{'country':country}] = xr.DataArray(sum_gen, dims=('time'))
    
    
    ## CALCULATE INFLOW ##
    eff = 0.9**0.5
    for country in country_list:
        ds_old['inflow_GWh'].loc[{'country':country}] = ds_old['gen'].loc[{'country':country}]/eff + ds_old['delta_V'].loc[{'country':country}]
    
    
    ## ADJUST INFLOW LEVELS ##
    
    ## 1. IDENTIFY WRONG FILLING LEVEL VALUES ##
    ds_old['ratio_dV_maxGen'] = ds_old['delta_V']/ ds_old['gen'].max('time')
    ds_new = ds_old.copy()
    
    ratio_threshold = 1
    
    ds_old['ratio_dV_maxGen'] = ds_old['ratio_dV_maxGen'].shift(time=1)
    ds_new['V'] = ds_new['V'].where(ds_old['ratio_dV_maxGen'] > -ratio_threshold)
    ds_old['ratio_dV_maxGen'] = ds_old['ratio_dV_maxGen'].shift(time=-1) 
    ds_new['V'] = ds_new.V.interpolate_na(dim='time',method='linear')
    ds_new['delta_V'] = ds_new['V'].shift(time=-1) - ds_new['V']
    ds_new['inflow_GWh'] = ds_new['gen']/eff + ds_new['delta_V']
    ds_new['ratio_dV_maxGen'] = ds_new['delta_V']/ ds_new['gen'].max('time')
    
    ## 2. REMOVE NEGATIVE INFLOW VALUES ##
    ds_new['inflow_GWh'] = ds_new['inflow_GWh'].where(ds_new['inflow_GWh'] >= 0, 0)
    
    
    ## OUTPUT DATASET AND REVOME UNNECESSARY VARIABLES ##
    ds = ds_new.copy()
    variables_to_delete = ['V', 'gen', 'delta_V', 'ratio_dV_maxGen']
    for var in (variables_to_delete):
        ds = ds.drop_vars(var)
    
    ds.to_netcdf('../inputs/entsoe_historic_inflow/historic_inflow.nc')
    return None

def open_entsoe_inflow():
    file = glob.glob("../inputs/entsoe_historic_inflow/historic_inflow.nc")
    if file == []:
        create_historical_inflow()
    ds_inflow = xr.open_dataset(file[0])

    return ds_inflow

# ==================================
# === AGGREGATION AND CONVERSION ===
# ==================================


def weighted_aggregation(ds_discharge,tech):
    """
    Aggregates the discharge data to country level, using the JRC dataset as a reference for the weighting coefficients.
    """

    # Create a dataset with the normalized installed capacity of ror power plants per country
    lat = ds_discharge.lat.values
    lon = ds_discharge.lon.values
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

    file_normalized_capacity = glob.glob(f"../inputs/normalized_capacity_{tech}.nc")

    if file_normalized_capacity != []:
        print("Loading normalized capacity "+ tech +" dataset")
        ds_C = xr.open_dataset(file_normalized_capacity[0])
    else:
        # Define the type of power plants to consider
        if tech == "ror":
            type_code = ["HROR"]
        elif tech == "inflow":
            type_code = ["HDAM","HPHS"]

        # Create the dataset
        print("Creating normalized capacity "+ tech +" dataset")
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

        # Fill the dataset  
        for country_code in country_list:
            C = np.zeros((len(lat),len(lon)))
            for ii in range(len(lon)): 
                for jj in range(len(lat)):
                    C[jj,ii] = df_jrc["installed_capacity_MW"][(df_jrc["type"].isin(type_code)) & (df_jrc["country_code"]==country_code) & (lon_edge[ii]<df_jrc["lon"]) & (df_jrc["lon"]<lon_edge[ii+1]) & (lat_edge[jj]<df_jrc["lat"]) & (df_jrc["lat"]<lat_edge[jj+1])].sum()

            ds_C.normalized_capacity.loc[{'country':country_code}] = C[:,:] / df_jrc["installed_capacity_MW"][(df_jrc["type"].isin(type_code)) & (df_jrc["country_code"]==country_code)].sum()
            
        ds_C.to_netcdf(f"../inputs/normalized_capacity_{tech}.nc")
        print("Normalized capacity "+ tech +" dataset saved")

    # Calculate the discharge per country
    ds_w = []
    for country in country_list:
        ds = (ds_C.normalized_capacity.sel(country=country) * ds_discharge.discharge).sum(('lat','lon'))
        ds_w.append(ds)
    ds_w = xr.concat(ds_w, dim='country')
    ds_w = ds_w.to_dataset(name='discharge')

    return ds_w

def piecewise_linear(x, a1, b1, a2, b2,q):
    return np.piecewise(x, [x <= q, x > q], [lambda x: a1 * x + b1, lambda x: a2 * x + b2])
    
def objective(params, x, y,q):
    a1, b1, a2,  = params
    b2 = a1 * q + b1 - a2 * q  # Ensure continuity at x = 10
    y_fit = piecewise_linear(x, a1, b1, a2, b2,q)
    return np.sum((y - y_fit) ** 2)

def get_pwlf(calibration_ds,tech):
    # get 75th percentile
    q = get_qu_75(calibration_ds).values
    #calibration parameters
    calib = calibration_ds.dropna(dim="time")
    x = calib.discharge.values
    y = calib[f"{tech}_GWh"].values
    #piece-wise linear fit 
    initial_guess = [1, 0, 1]  # [a1, b1, a2]
    bounds = [(0, None), (None, 0), (0, None)]
    result = minimize(objective, initial_guess, args=(x, y, q), bounds=bounds)
    # linear fit parameters
    a1_opt, b1_opt, a2_opt = result.x
    b2_opt = a1_opt * q + b1_opt - a2_opt * q 

    return [a1_opt, b1_opt, a2_opt, b2_opt], q

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
        annual_prod = pd.read_csv(f"../inputs/entsoe_scaling/monthly_domestic_values_{year}.csv",delimiter=delim[j])
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
    :param ds: DataArray of transformed discharge-to-hydro, per country
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
