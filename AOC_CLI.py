"""
    This is the library code for the AOC cli
"""
# Third party imports
from typing import List
import sys
# Internal imports
import AOCBackend as AOC
from datetime import datetime

class Config:
    """
        The data needed to reason about the user input
    """
    DATE_FORMAT = "%Y-%m-%d"
    DATE_FORMAT_ERROR = "invalid_date_format"
    NOT_ENOUGH_ARGS_ERROR = "not_enough_args"
    FILE_ERROR = "file_error"
    OK = "ok"
    INCONSISTENT_DATES = "inconsistent_dates"

    def __init__(self, args : List[str]):
        # Check for arguments matching
        if len(args) < 3:
            self.since = None
            self.until = None
            self.file  = None
            self.error = self.NOT_ENOUGH_ARGS_ERROR
            return

        # Try to parse since date:
        try:
            self.since = datetime.strptime(args[1], self.DATE_FORMAT)
        except ValueError:
            self.since = None
            self.until = None
            self.file  = None
            self.error = self.DATE_FORMAT_ERROR
            return

        # Try to parse until date
        try:
            self.until = datetime.strptime(args[2], self.DATE_FORMAT)
        except ValueError:
            self.since = None
            self.until = None
            self.file  = None
            self.error = self.DATE_FORMAT_ERROR
            return

        if self.since > self.until:
            self.since = None
            self.until = None
            self.file  = None
            self.error = self.DATE_FORMAT_ERROR
            return 

        # try to parse file with urls if their exists
        if len(args) >= 4 and args[3][0] != '-':
            try:
                with open(args[3], 'r') as file:
                    self.inputs = [ line if line[-1] != '\n' else line[:len(line) -1] for line in file.readlines()]
                    
            except:
                self.since = None
                self.until = None
                self.file  = None
                self.error = self.FILE_ERROR
                return

            self.file = args[3]
        else:
            self.file = None
            self.inputs = []

        # Especify a critical error rate
        self.critical_weird_rate = 0.1

        self.error = self.OK

class StrColors:
    """
        Some colors to use while printing stuff
    """
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def days_from_config(config : Config) -> List[AOC.MeasurementSet]:
    """
        Get a set of rows from the provided input
        such that each row has the same ammount of days 

    """
    if config.error != Config.OK:
        return None
    
    rows = []
    if len(config.inputs) == 0:
        print("Getting general measurements...")
        row = AOC.get_measurements(config.since, config.until, None)
        if isinstance(row, str):
            print(f"Error retrieving general measurements, error: {row}", file=sys.stderr)
        else:
            rows.append(AOC.MeasurementSet(row))

    else:
        for dom in config.inputs:
            print(f"Getting measurements for {dom} since {config.since} until {config.until}...")
            row = AOC.get_measurements_list_api(config.since, config.until, dom)
            if isinstance(row, str):
                print(f"Error retrieving measurements for input {dom[:len(dom)-1]}, error: {row}", file=sys.stderr)
            else:
                rows.append(AOC.MeasurementSet(row))
    return rows
    
