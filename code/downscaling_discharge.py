#imports
import xarray as xr
import cftime
from datetime import timedelta

def downscale(ds_discharge,ds_runoff,save_info):
    ## Open discharge, monthly values
    
    
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
    ds_discharge_daily['time'] = ds_discharge_daily.time + timedelta(days=-31)  #shift one month back
    
    ## Match time coordinates of the two datasets: discharge_daily and runoff_mean
    ds_runoff_mean = ds_runoff_mean.sel(time=ds_discharge_daily.time)
    
    ## Expand runoff_mean, to include latitude and longitude
    ds_runoff_mean = ds_runoff_mean.broadcast_like(ds_discharge_daily)
    
    ## Calculate daily values of river discharge
    ds_discharge_daily['discharge'] =  ds_discharge_daily.discharge_monthly_ave * ds_runoff_mean.runoff_normalized
    
    ds_discharge_daily.sel(bnds=0).to_netcdf(f"../output/{save_info}.nc")
    
    return None