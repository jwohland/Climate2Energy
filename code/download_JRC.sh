# Download JRC data
for country in AT BE BG CZ DE DK EE EL ES FI FR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK UK
do
  wget -r -nd -P ../inputs/JRC http://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/JRC-IDEES/JRC-IDEES-2015_v1/JRC-IDEES-2015_All_xlsx_${country}.zip
  unzip ../inputs/JRC/JRC-IDEES-2015_All_xlsx_${country}.zip -d ../inputs/JRC/
done

# unzip
