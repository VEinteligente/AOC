"""
    Driver code for the AOCW cli
"""

# Third party imports
import sys

# Local imports
import AOCW_lib

def main():
    config = AOCW_lib.AOCW(sys.argv)
    print(config.state)
    pass

if __name__ == "__main__":
    main()