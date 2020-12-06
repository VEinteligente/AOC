"""
    Driver program for the AOC CLI
"""
# Third party imports
import sys
from tabulate import tabulate
# local imports
from AOC_CLI import Config, days_from_config, StrColors

USAGE = "Usage: \naoc since until file\n    For more details, aoc --help" 


def main():
    c = Config(sys.argv)
    
    # 
    if c.error == Config.DATE_FORMAT_ERROR:
        print("Provided date format is not valid. Expected: YYYY-mm-dd", file=sys.stderr)
        exit(1)
    elif c.error == Config.FILE_ERROR:
        print("Could not open provided file", file=sys.stderr)
        exit(1)
    elif c.error == Config.NOT_ENOUGH_ARGS_ERROR:
        print(USAGE)
        exit(1)
    elif c.error == Config.INCONSISTENT_DATES:
        print("Since date can't  be after until date", file=sys.stderr)
        exit(1)
    elif c.error != Config.OK:
        print(f"Error: {c.error}", file=sys.stderr)
        exit(1)

    format_date = lambda d : d.strftime("%Y-%m-%d")
    # Generate table
    rows = days_from_config(c)
    if len(rows) == 0:
        print("Could not retrieve any data")
        exit(0)

    # Print requested data description
    print(f"Showing weird behavior rate since {format_date(c.since)}, until {format_date(c.until)} from list {c.file}")
    # Add the header to the table
    table = [['input'] + [format_date(x.start_day) for x in rows[0].days] + ["total measurements", "total anomalies", "total weird behavior rate"]]
    # Add every row to the table
    for dayset in rows:
        table += [
                    # Input row
                    [dayset.days[0].input[:30] if dayset.days[0].input else "(no input)"] + 
                    # weird behavior rate per day
                    [   
                        f"{StrColors.FAIL if day.weird_behavior_ratio >= c.critical_weird_rate else ''}{round(day.weird_behavior_ratio,3)}{StrColors.ENDC if day.weird_behavior_ratio >= c.critical_weird_rate else ''}" 
                            if day.weird_behavior_ratio else "NA" 
                        for day in dayset.days
                    ] + 
                    # total ammount of measurements, anomalies, and total weird rate
                    [
                        dayset.total_measurements, 
                        dayset.total_anomalies, 
                        f"{StrColors.FAIL if dayset.get_avg_weirds() >= c.critical_weird_rate else ''}{round(dayset.get_avg_weirds(),3)}{StrColors.ENDC if dayset.get_avg_weirds() >= c.critical_weird_rate else ''}"
                    ]
                ]
    
    print(tabulate(table))

if __name__ == '__main__':
    main()