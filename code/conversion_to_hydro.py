from utils import zero_mean_longitudes, select_Europe
import glob
import xarray as xr
import pandas as pd
import numpy as np
import scipy
import os
import datetime as dt
from scipy.optimize import minimize
from historical_inflow import create_historical_inflow
from bias_correction_methods import bias_correct_hydro


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
    qu = xr.apply_ufunc(quantile_75,ds.discharge,
            vectorize=True,
            input_core_dims=[["time"]],
            exclude_dims=set(("time",))    
            )
    return qu

def open_discharge(year, end_year=np.nan,realization=1500,period="HIST"):
    """
    Opens and preprocesses discharge data (see function preprocess_cesm_discharge) for a certain year. If end year is passed as an int, it opens all years between year and end_year (included)
    :param year: string
    :kwarg end_year: string or nan (if only one year is needed)
    """
    if np.isnan(end_year) == False: 
        time_range = range(year,end_year+1)
    else:
        time_range = [year]
    dss = []
    for year in time_range:
        dss.append(xr.open_dataset(f"/net/xenon/climphys/lbloin/CESM2energy_data/CESM2_discharge/{period}_{realization}_{year}_discharge.nc"))
    
    return xr.concat(dss,dim="time").load().convert_calendar("proleptic_gregorian") # new calendar to get numpy datetime (necessary for weekly resampling)

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
    file = glob.glob(f"../output/discharge_ERA5.nc")
    def preprocess_era_here(ds):
        return preprocess_era(ds,cesm_lat,cesm_lon)
    if file == []:
        files = [f"/net/xenon/climphys/lbloin/CESM2energy_data/ERA5_discharge/discharge_{year}.nc" for year in range(1995,2023)] #historical+calbration ERA5 data
        era5 = xr.open_mfdataset(files,preprocess=preprocess_era_here,combine="nested")
        era5.to_netcdf(f"../output/discharge_ERA5.nc")
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

def open_entsoe_inflow():
    file = glob.glob("../inputs/entsoe_historic_inflow/historic_inflow.nc")
    if file == []:
        create_historical_inflow()
    ds_inflow = xr.open_dataset(file[0])

    return ds_inflow

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