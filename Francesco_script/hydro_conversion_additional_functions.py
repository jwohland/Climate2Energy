## import libraries
import xarray as xr
import numpy as np
from scipy.optimize import minimize
from tqdm import tqdm

## use aggregate to get the calibration dataset

def aggregate(technologies):
    calibs = {}

    for tech in tqdm(technologies,desc="Aggregate ERA5 discharge and ENTSO-e data for r-o-r and inflow"):

        calibration_ds = open_entsoe(tech)
        [start_year,end_year] = calibration_ds.groupby("time.year").sum().year[[0,-1]].values

        era_discharge = open_era().sel(time=slice(str(start_year),str(end_year)))

        if tech == "inflow":
            time_range = calibration_ds.time[[0,-1]].values
            era_discharge = open_weekly(era_discharge,time_range=time_range)       
        era_weighted = weighted_aggregation(era_discharge,tech)["discharge"].sel(country=calibration_ds.country)
        if tech =="ror":
            era_weighted["time"] = calibration_ds.time

        calibration_ds["discharge"] = era_weighted
        calibs[tech] = calibration_ds.rolling(time=rolling[tech],center=True).mean()

    return calibs


## use convert to convert ds_discharge_input into ror/inflow, using the calibration dataset

def convert(calibs,ds_discahrge_input,technologies):
    final_hydro = {}
    def piecewise_linear(x, a1, b2, c2,q):
        return np.piecewise(x, [x <= q, x > q], [lambda x: a1 * x, lambda x: b2 * x + c2])

    for tech in tqdm(technologies):

        print(f"Converting {tech}")

        ds_final = xr.Dataset(
            coords={
                'country': calibs[tech].country,
                'time': calibs[tech].time
            },
            data_vars={
                'discharge': (['country', 'time'], ds_discahrge_input[tech].discharge.values.copy()),
                f'{tech}_GWh': (['country', 'time'], calibs[tech][f'{tech}_GWh'].values.copy()),
            }   
        ) 
        
        for country in calibs[tech].country.values:
            [a1_opt, b2_opt, c2_opt],q =  get_pwlf(calibs,tech,country)
            ds_final[f'{tech}_GWh'].loc[dict(country=country)] =  piecewise_linear(ds_discahrge_input[tech].sel(country=country).discharge.values, a1_opt, b2_opt, c2_opt,q)

        final_hydro[tech] = ds_final
    return final_hydro




def get_pwlf(calibs,tech,country):
    q = get_qu_75(calibs[tech]).sel(country=country).values
    calib = calibs[tech].sel(country=country).dropna(dim="time")
    x = calib.discharge
    

    x = calib.discharge.values
    y = calib[f"{tech}_GWh"].values

    def piecewise_linear(x, a1, b2, c2,q):
        return np.piecewise(x, [x <= q, x > q], [lambda x: a1 * x, lambda x: b2 * x + c2])
    
    def objective(params, x, y,q=q):
        a1, b2, c2 = params
        c2 = a1 * q - b2 * q  # Ensure continuity at x = 10
        y_fit = piecewise_linear(x, a1, b2, c2,q)
        return np.sum((y - y_fit) ** 2)

    initial_guess = [1, 1, 0]
    bounds = [(0, None), (0, None), (None, None)]
    result = minimize(objective, initial_guess, args=(x, y), bounds=bounds)

    a1_opt, b2_opt, _ = result.x
    c2_opt = a1_opt * q - b2_opt * q 

    return [a1_opt, b2_opt, c2_opt], q




## this is to plot
def plot_kinked_lin_regression(calibs,tech,country,ax):

    calib = calibs[tech].sel(country=country).dropna(dim="time")
    [a1_opt, b2_opt, c2_opt],q =  get_pwlf(calibs,tech,country)

    def piecewise_linear(x, a1, b2, c2,q):
        return np.piecewise(x, [x <= q, x > q], [lambda x: a1 * x, lambda x: b2 * x + c2])

    x = calib.discharge.values
    y = calib[f"{tech}_GWh"].values

    ax.scatter(x, y,s=3, label='Data')
    ax.plot(x, piecewise_linear(x, a1_opt, b2_opt, c2_opt,q), 'r',label=f'Fitted piecewise linear function')
    
    ax.set_title(f"country = {country}")
    ax.set_ylabel("ENTSO-e values [GWh]")
    ax.legend(["a1 = {:.3f}, b2 = {:.3f}, c2 = {:.3f}".format(a1_opt, b2_opt, c2_opt)])
    #ax.set_xlabel("Daily country-aggregated river discharge (capacity weighted) [m3 s-1]")	
    ax.set_xlabel("discharge (m3 s-1)")
    #plt.savefig(f"../output/figs/{tech}_lin_fit_{country}.png",dpi =1200,bbox_inches="tight")