import xarray as xr
from bias_correction import BiasCorrection
import subprocess
import glob
from utils import *
import numpy as np
import pandas as pd
        
def bias_correct_per_loc(reference,model,da,method="basic_quantile"):
    """
    Computes bias correction using the model output during historical period (model)
    and the ground truth (reference) and applies  the correction to future model output (da).

    reference, model and da have to be xr.DataArrays at a single location

   
    """
    if np.isnan(da).all():
        return da
    else:
        bc = BiasCorrection(pd.Series(reference),pd.Series(model), pd.Series(da))
        return bc.correct(method=method)
        

def bias_correct_dataset(ds, var, method="basic_quantile"):
    """
    takes a data array da of a chosen variable var, and returns the
    bias corrected version (using package bias_correction).
    
    """
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
    # the reference dataset has slightly different values for the dimension "lat" (max 10E-14) due to different segmentation in cdo/python. this fixes it
    reference["lat"] = model.lat
    # bias_correction
    corrected = xr.apply_ufunc(
        bias_correct_per_loc, reference[var], model[var], ds[var], vectorize=True, 
        input_core_dims=[["time"], ["time"],["time"]], exclude_dims=set(("time",)), 
        output_core_dims = [["time"]], kwargs={"method": method}
    )

    return corrected
