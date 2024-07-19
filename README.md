# CESM2energy

Code to translate output from the CESM2 climate model to country-level wind and solar photovoltaics capacity factors. 

![alt text](https://private-user-images.githubusercontent.com/20681098/281738802-a809291f-4021-414c-8bf1-2a4d6dd3a250.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTEiLCJleHAiOjE2OTk1MzUyMzYsIm5iZiI6MTY5OTUzNDkzNiwicGF0aCI6Ii8yMDY4MTA5OC8yODE3Mzg4MDItYTgwOTI5MWYtNDAyMS00MTRjLThiZjEtMmE0ZDZkZDNhMjUwLnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFJV05KWUFYNENTVkVINTNBJTJGMjAyMzExMDklMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjMxMTA5VDEzMDIxNlomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPWRkOThiYTljMTY3NmRlYTA2MTJhNDU5ZWQzYzY1OThjMDA1MTY5YzE0ZGFjOTkzMmZiNTRmNzRjNDE0NzBkY2YmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0JmFjdG9yX2lkPTAma2V5X2lkPTAmcmVwb19pZD0wIn0.iPuATjuuawkdBf5XrjO-djMmCIEutlHlI4e_OKnjx0o)
## Create environments

There are currently two seperate environment needed to run different parts of the tool. They can not be easily unified because they have incompatible version requirements of some other packages.

### Main environment

`mamba env create --file environment.yml  --name CESM2energy`

To run the jupyter notebooks, you might have to add `ipykernel` by (a) creating the environment above, (b) activating it (`conda activate CESMenergy`), 
and (c) running `conda install ipykernel`.

### Second environment (heating and cooling demand only)

`mamba env create --file environment_demandninja.yml  --name demand_ninja`

This environment is exclusively needed to run `code/conversion_to_demand.py`

## Download of additional input files

### Shapefiles of Exclusive Economic Zones for offshore wind computations

The offshore assessment relies on the shapes of EEZ, in particular the World EEZ v11 (2019-11-18) shapefile provided by the Flanders Marine Institute and available at https://www.marineregions.org/download_file.php?name=World_EEZ_v11_20191118.zip

Download and extract the data to `inputs/EEZ/`.

### Population data from NASA/Columbia Uni

After registration, data can be retrieved from the link below. We choose the highest resolution (2.5 minutes). Data must be unzipped and the file `gpw_v4_population_density_adjusted_rev11_2pt5_min.nc` must be moved into the `inputs` folder. 

https://sedac.ciesin.columbia.edu/data/set/gpw-v4-population-density-adjusted-to-2015-unwpp-country-totals-rev11/data-download

### Worldbank total population data
Lists of total populations in different countries need to be provided

  https://data.worldbank.org/indicator/SP.POP.TOTL

Download the file as csv, and upload it in inputs as World_bank_population.csv

### JRC-IDEES-2015_v1 data

We provide electrified heating demand using the currently electrified share (using demand-ninja and CESM2 climate information) as well as a scaled version. The scaled version assumes that all heating is fully electrified and can be used to create scenarios (e.g., division by 5 corresponds to a scenario where 20% of heating is met by electricity). The scaling needs input data from the Joint Research Center (JRC) Integrated Database of the European Energy System (IDEES) which must be downloaded by running 

`bash download_JRC.sh`

from the `code` folder, which downloads and unzipped the required inputs.https://github.com/energy-modelling-toolkit/hydro-power-database/

### Download JRC Hydropower Database
Download the file "jrc-hydro-power-plant-database.csv" from the GitHub repo: https://github.com/energy-modelling-toolkit/hydro-power-database/
Save the file into the `inputs` folder.
This file contains the location and the installed capacity (nominal power of the turbine) of hydropower plants (run-of-river, reservoir, pumped-hydro) in Europe.

### Download run-of-river generation from ENTSO-e Transparency platform
On ENTSO-e Transparency platform (https://transparency.entsoe.eu/), download run-of-river generation per each year per each country:
- Go to Generation>Actual generation per production type
- Select "Country" and in "Area" select the desired country.
- In "Production Type" select only "Hydro Run-of-river and poundage".
- Download the full year at Export Data>Actual Generation per Production Type (Year,CSV).
The file name should have this format: "Actual Generation per Production Type_201501010000-201601010000.csv".

### Download reservoir filling level and reservoir generation from ENTSO-e Transparency platform
#### Reservoir filling level
On ENTSO-e Transparency platform (https://transparency.entsoe.eu/), download run-of-river generation per each country:
- Go to Generation>Water Reservoirs and Hydro Storage Plants
- Select "Country" and in "Area" select the desired country.
- Download the csv at Export Data>Water Reservoirs and Hydro Storage Plants (CSV).
The file name should have this format: "Water Reservoirs and Hydro Storage Plants_201412290000-202412300000.csv".
#### Reservoir generation
On ENTSO-e Transparency platform (https://transparency.entsoe.eu/), download reservoir generation per each year per each country:
- Go to Generation>Actual generation per production type
- Select "Country" and in "Area" select the desired country.
- In "Production Type" select only "Hydro Water Reservoir".
- Download the full year at Export Data>Actual Generation per Production Type (Year,CSV).
The file name should have this format: "Actual Generation per Production Type_201501010000-201601010000.csv".

#### Save the downloaded file into the input folder
With Reservoir filling levels and Reservoir generation it will be possible to compute the historical energy inflow in reservoirs.

In the folder `inputs`, create the folder `entsoe_inflow`. In this folder, create one folder per country, named with the country code, e.g. `AT`.
Save the single reservoir filling level csv file downloaded (one file for all the years) and all the Reservoir generation files (one file per year, so multiple files) from ENTSO-e into the folder of the corresponding country.


### Code information
In the folder `inputs`, create the folder `entsoe_ror`. In this folder, create one folder per country, named with the country code, e.g. `AT`.
Save the csv file downloaded from ENTSO-e into the folder of the corresponding country.

### Download ENTSO-e power stats for scaling output to actual annual averages
Download Monthly Domestic Values aggregated by country for 2021, 2022 and 2023 as .csv files, and save into folder `inputs/entsoe/`

https://www.entsoe.eu/data/power-stats/

## Running CESM2Energy

After installation of the environments and download of the required additional inputs, you can run the tool from the `code` folder as

```
bash - l run_all.sh
```

## Climate model data (NEEDS UPDATING)
Necessary variables are: Wind Speed (U and V) at turbine level (~100m), surface short-wave downwelling radiation (RSDS), and surface temperature (TREFHT).
For implementing hydropower, we would additionally need run-off or precipitation.

We are currently using daily mean values for RSDS and TREFHT, while wind speed is in 6-hourly format.

#### Climate model grid
Information of the grid used by the climate model needs to be provided for the bias correction. 
The code reads grid information from `inputs/CESM_atm_grid.txt`.

#### Bias correction (NEEDS UPDATING)
Currently, the "ground truth" values used for bias correction comes from ERA5 data, regridded to CESM2 resolution (spatial + temporal). 

### Gaussian smoothed power curves from the windpowerlib

The conversion to wind capacity factors is based on power curves from the windpowerlib [1] that have been selected and smoothed following [2]. 

[1] https://github.com/wind-python/windpowerlib/blob/dev/windpowerlib/oedb/power_curves.csv
[2] Wohland, J., Brayshaw, D. & Pfenninger, S. Mitigating a century of European renewable variability with transmission and informed siting. Environ. Res. Lett. 16, 064026 (2021).
