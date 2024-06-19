
from tqdm import tqdm
import numpy as np
import pandas as pd
import xarray as xr
from datetime import datetime, timedelta


## CREATE TIME DATAFRAME ##

year_0 = 2016
year_N = 2023

start_date = datetime(year_0, 1, 4)
end_date = datetime(year_N, 12, 25)

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
    current_date += timedelta(days=7)
    if (current_date+timedelta(days=2)).year > current_year:
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
        df_gen_y['time'] = df_gen_y['MTU'].apply(lambda x:  datetime.strptime(x[:15], date_format))
        df_gen_y['time_delta'] = (df_gen_y.time.shift(-1) - df_gen_y.time).dt.total_seconds()/3600
        df_gen_y['gen_GWh'] = df_gen_y['Hydro Water Reservoir  - Actual Aggregated [MW]'] * df_gen_y['time_delta']/1000 
        df_gen = pd.concat([df_gen, df_gen_y[['time', 'gen_GWh']]], axis=0)
    sum_gen = []
    for date in df_time.date:
        start_date = date
        end_date = date + timedelta(days=7)
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