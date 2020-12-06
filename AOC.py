"""
    Driver program for the AOC CLI
"""
# Third party imports
import sys
from tabulate import tabulate
# local imports
from AOC_CLI import Config, days_from_config

USAGE = "Usage: \naoc since until file\n    For more details, aoc --help" 


def main():
    c = Config(sys.argv)
    
    # 
    if c.error == Config.DATE_FORMAT_ERROR:
        print("Provided date format is not valid. Expected: YYYY-mm-dd")
        exit(1)
    elif c.error == Config.FILE_ERROR:
        print("Could not open provided file")
        exit(1)
    elif c.error == Config.NOT_ENOUGH_ARGS_ERROR:
        print(USAGE)
        exit(1)
    elif c.error == Config.INCONSISTENT_DATES:
        print("Since date can't  be after until date")
        exit(1)
    elif c.error != Config.OK:
        print(f"Error: {c.error}")
        exit(1)

    format_date = lambda d : d.strftime("%Y-%m-%d")
    # Generate table
    rows = days_from_config(c)
    print(f"Showing weird behavior rate since {format_date(c.since)}, until {format_date(c.until)} from list {c.file}")
    table = [['input'] + [format_date(x.start_day) for x in rows[0].days]]
    table += [[dayset.days[0].input[:20]] + [round(day.weird_behavior_ratio,2) for day in dayset.days] + [] for dayset in rows]
    
    print(tabulate(table))

if __name__ == '__main__':
    main()