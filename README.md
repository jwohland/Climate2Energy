# CESM2energy

Code to translate output from the CESM2 climate model to country-level wind and solar photovoltaics capacity factors. 

![alt text](https://private-user-images.githubusercontent.com/20681098/281738802-a809291f-4021-414c-8bf1-2a4d6dd3a250.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTEiLCJleHAiOjE2OTk1MzUyMzYsIm5iZiI6MTY5OTUzNDkzNiwicGF0aCI6Ii8yMDY4MTA5OC8yODE3Mzg4MDItYTgwOTI5MWYtNDAyMS00MTRjLThiZjEtMmE0ZDZkZDNhMjUwLnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFJV05KWUFYNENTVkVINTNBJTJGMjAyMzExMDklMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjMxMTA5VDEzMDIxNlomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPWRkOThiYTljMTY3NmRlYTA2MTJhNDU5ZWQzYzY1OThjMDA1MTY5YzE0ZGFjOTkzMmZiNTRmNzRjNDE0NzBkY2YmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0JmFjdG9yX2lkPTAma2V5X2lkPTAmcmVwb19pZD0wIn0.iPuATjuuawkdBf5XrjO-djMmCIEutlHlI4e_OKnjx0o)
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
