"""
    Driver code for the AOCW cli
"""

# Third party imports
import sys

# Local imports
import AOCW_lib

def main():
    aocw = AOCW_lib.AOCW(sys.argv)

    if aocw.state != AOCW_lib.AOCW.ERRORS.OK:
        print(f"Error: {aocw.state}", file=sys.stderr)
        exit(1)    

if __name__ == "__main__":
    main()