from bias_correction_methods import prepare_bias_correction
import sys


if __name__ == "__main__":
    bc_realization = str(sys.argv[1])
    prepare_bias_correction(bc_realization)
