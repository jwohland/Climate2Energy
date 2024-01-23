# CESM2energy

Code to translate output from the CESM2 climate model to country-level wind and solar photovoltaics capacity factors. 

![alt text](https://private-user-images.githubusercontent.com/20681098/281738802-a809291f-4021-414c-8bf1-2a4d6dd3a250.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTEiLCJleHAiOjE2OTk1MzUyMzYsIm5iZiI6MTY5OTUzNDkzNiwicGF0aCI6Ii8yMDY4MTA5OC8yODE3Mzg4MDItYTgwOTI5MWYtNDAyMS00MTRjLThiZjEtMmE0ZDZkZDNhMjUwLnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFJV05KWUFYNENTVkVINTNBJTJGMjAyMzExMDklMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjMxMTA5VDEzMDIxNlomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPWRkOThiYTljMTY3NmRlYTA2MTJhNDU5ZWQzYzY1OThjMDA1MTY5YzE0ZGFjOTkzMmZiNTRmNzRjNDE0NzBkY2YmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0JmFjdG9yX2lkPTAma2V5X2lkPTAmcmVwb19pZD0wIn0.iPuATjuuawkdBf5XrjO-djMmCIEutlHlI4e_OKnjx0o)
### Create environments

There are currently two seperate environment needed to run different parts of the tool. They can not be easily unified because they have incompatible version requirements of some other packages.

#### Main environment

`mamba env create --file environment.yml  --name CESM2energy`

To run the jupyter notebooks, you might have to add `ipykernel` by (a) creating the environment above, (b) activating it (`conda activate CESMenergy`), 
and (c) running `conda install ipykernel`.

#### Second environment (heating and cooling demand only)

`mamba env create --file environment_demandninja.yml  --name demand_ninja`

This environment is exclusively needed to run `code/conversion_to_demand.py`

### Download power curves from the windpowerlib

The conversion to wind capacity factors is based on the power curves from the windpowerlib. You need to download the following file to the 'input' folder

https://github.com/wind-python/windpowerlib/blob/dev/windpowerlib/oedb/power_curves.csv

### Download population data from NASA/Columbia Uni

After registration, data can be retrieved from the link below. We choose the highest resolution (2.5 minutes). Data must be unzipped and the file `gpw_v4_population_density_adjusted_rev11_2pt5_min.nc` must be moved into the `inputs` folder. 

https://sedac.ciesin.columbia.edu/data/set/gpw-v4-population-density-adjusted-to-2015-unwpp-country-totals-rev11/data-download

### Download JRC-IDEES-2015_v1 data

We provide electrified heating demand using the currently electrified share (using demand-ninja and CESM2 climate information) as well as a scaled version. The scaled version assumes that all heating is fully electrified and can be used to create scenarios (e.g., division by 5 corresponds to a scenario where 20% of heating is met by electricity). The scaling needs input data from the Joint Research Center (JRC) Integrated Database of the European Energy System (IDEES) which must be downloaded by running 

`bash download_JRC.sh`

from the `code` folder, which downloads and unzipped the required inputs.

### Code information

## Climate model data (NEEDS UPDATING)
Necessary variables are: Wind Speed (U and V) at turbine level (~100m), surface short-wave downwelling radiation (RSDS), and surface temperature (TREFHT).
For implementing hydropower, we would additionally need run-off or precipitation.

We are currently using daily mean values for RSDS and TREFHT, while wind speed is in 6-hourly format.

#### Bias correction (NEEDS UPDATING)
Currently, the "ground truth" values used for bias correction comes from ERA5 data, regridded to CESM2 resolution (spatial + temporal). 
