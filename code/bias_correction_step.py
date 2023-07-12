import xarray as xr
from bias_correction import BiasCorrection
import subprocess
import glob
from utils import *
import numpy as np
import pandas as pd
        
def bias_correction(reference,model,da,method="basic_quantile"):
    if np.isnan(da).all():
        return da
    else:
        bc = BiasCorrection(pd.Series(reference),pd.Series(model), pd.Series(da))
        return bc.correct(method=method)
        

def bias_correct(ds, var, method="basic_quantile"):
    """takes a data array da of a chosen variable var, and returns the
    bias corrected version (using package bias_correction)."""
    ref_file = f"../output/{var}_ERA5.nc"
    mod_file = f"../output/hist_{var}.nc"
    # making sure that the reference and model data is available
    if (
        glob.glob(ref_file) == []
        or glob.glob(mod_file) == []
    ):
        print("missing files")
        subprocess.run("./preprocess_bias_correction.sh")
    # open reference and model data
    reference = zero_mean_longitudes(xr.open_dataset(ref_file))
    if var == "temperature":
        reference = temp_cel(reference)
    model = zero_mean_longitudes(xr.open_dataset(mod_file))
    
    reference = reference.reindex(lat=ds[var].coords['lat'], lon=ds[var].coords['lon'])
    model = model.reindex(lat=ds[var].coords['lat'], lon=ds[var].coords['lon'])
    # bias_correction
    #print(reference[var].coords['lat'], model[var].coords['lat'], ds[var].coords['lat'])
    corrected = xr.apply_ufunc(
        bias_correction, reference[var], model[var], ds[var], vectorize=True, 
        input_core_dims=[["time"], ["time"],["time"]], exclude_dims=set(("time",)), 
        output_core_dims = [["time"]], kwargs={"method": method}
    )

    return corrected
