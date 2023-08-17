# CESM2energy

Code to translate output from the CESM2 climate model to country-level wind and solar photovoltaics capacity factors. 

### Create environment

`mamba env create --file environment.yml  --name CESM2energy`

To run the jupyter notebooks, you might have to add `ipykernel` by (a) creating the environment above, (b) activating it (`conda activate CESMenergy`), 
and (c) running `conda install ipykernel`.

### Download power curves from the windpowerlib

The conversion to wind capacity factors is based on the power curves from the windpowerlib. You need to download the following 
file to the 'input' folder

https://github.com/wind-python/windpowerlib/blob/dev/windpowerlib/oedb/power_curves.csv

### Code information

#### Climate model data
Necessary variables are: Wind Speed (U and V) at turbine level (~100m), surface short-wave downwelling radiation (RSDS), and surface temperature (TREFHT).
For implementing hydropower, we would additionally need run-off or precipitation.

We are currently using daily mean values for RSDS and TREFHT, while wind speed is in 6-hourly format.

#### Bias correction
Currently, the "ground truth" values used for bias correction comes from ERA5 data, regridded to CESM2 resolution (spatial + temporal). 
