# CESM2energy

Code to translate output from the CESM2 climate model to country-level wind and solar photovoltaics capacity factors. 

### Shapefile for country decomposition

Download country shapefiles from Natural Earth 

https://www.naturalearthdata.com/downloads/110m-cultural-vectors/

Then unpack and save the shp file (ne_110m_admin_0_countries.shp) in `inputs`.

### Create environment

`mamba env create --file environment.yml  --name CESM2energy`
