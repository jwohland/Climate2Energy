from bias_correction_methods import prepare_bias_correction
import sys
from utils import create_directories


if __name__ == "__main__":
    # Create directory structure
    create_directories()
    bc_realization = str(sys.argv[1])
    prepare_bias_correction(bc_realization)
