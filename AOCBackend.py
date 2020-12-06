"""
    This is the library backend code for the Aggregation Ooni Command-line (AOC).
    This file exports functions needed to process and compute the ratio for blocking change,
    those data may be useful both to the CLI and the watcher server 
"""

# Third party imports
from datetime import datetime
from typing import List
import requests

class MeasurementDay:
    """
        This class represents the statistical data for a single 
        day
    """
    def __init__(   self, 
                    measurement_count : int, 
                    anomaly_count : int, 
                    failure_count : int, 
                    start_day : datetime,
                    inpt     : str,
                    confirmed_count : int = 0):

        # Consistency checking
        assert measurement_count >= 0, "Negative measurement ammount does not makes sense"
        assert anomaly_count >= 0   , "Negative measurement ammount does not makes sense"
        assert failure_count >= 0   , "Negative measurement ammount does not makes sense"
        assert confirmed_count >= 0 , "Negative measurement ammount does not makes sense"

        # Ooni data:
        self.measurement_count   = measurement_count
        self.anomaly_count      = anomaly_count
        self.failure_count      = failure_count
        self.confirmed_count    = confirmed_count
        self.start_day          = start_day
        self.input              = inpt

        # Our data
        self.anomaly_ratio = anomaly_count / measurement_count if measurement_count != 0 else None
        self.failure_ratio = failure_count / measurement_count if measurement_count != 0 else None
        self.confirmed_ratio = confirmed_count / measurement_count if measurement_count != 0 else None
        self.weird_behavior_ratio = (confirmed_count + anomaly_count + failure_count) / measurement_count if measurement_count != 0 else None
        
    def __str__(self):
        return "<Day: {day}, domain: {domain}, ammount: {ammount}>".format(day=self.start_day, domain=self.input, ammount=self.measurement_count)
    
    def __repr__(self):
        return "<Day: {day}, domain: {domain}, ammount: {ammount}>".format(day=self.start_day, domain=self.input, ammount=self.measurement_count)
    
class MeasurementSet:
    """
        This class represents the statistical data for a set of days
    """
    def __init__(self, days : List[MeasurementDay]):

        # Some type checking:
        assert all(isinstance(x, MeasurementDay) for x in days), "This is not a measurement list"

        self.days = days

        # Keep the days list sorted so we can keep them sorted in the tables
        self.days.sort(key=lambda x: x.start_day)

        # Keep the total for every measurement type
        self.total_measurements   = sum(x.measurement_count for x in days)
        self.total_anomalies      = sum(x.anomaly_count for x in days)
        self.total_failures       = sum(x.failure_count for x in days)
        self.total_confirmed      = sum(x.confirmed_count for x in days)
        self.total_weird_behavior = self.total_confirmed + self.total_anomalies + self.total_failures

    def get_avg_anomalies(self) -> float:
        """
            return the anomaly rate for all these measurements
        """
        return self.total_anomalies / self.total_measurements
    
    def get_avg_failures(self) -> float:
        """
            return the failure rate for all these measurements
        """
        return self.total_failures / self.total_measurements
    
    def get_avg_confirmed(self) -> float:
        """
            return the confirmed rate for all these measurements
        """
        return self.total_confirmed / self.total_measurements

    def get_avg_weirds(self) -> float:
        """
            return the weirds rate for all these measurements
        """
        return self.total_weird_behavior / self.total_measurements

    def add_day(self, day : MeasurementDay):
        """
            Add a day to the stored day list
        """
        self.days.append(day)
        self.days.sort(key=lambda x: x.start_day)

        self.total_measurements += day.measurement_count
        self.total_anomalies    += day.anomaly_count
        self.total_confirmed    += day.confirmed_count
        self.total_failures     += day.failure_count
        
    def get_days_by_domain(self, domain : str) -> List[MeasurementDay]:
        """
            Search a set of days by its domain
        """
        return [x for x in self.days if x.domain == domain]


def get_measurements(   since : datetime, 
                        until : datetime, 
                        domain : str, 
                        probe_cc : str = 'VE', 
                    test_name : str = None) -> List[MeasurementDay]:
    """
        Get a list of aggregated measurements 
            since: lower bound for the start time for those measurements
            until: upper bound for the start time for those measurements
            domain: domain which should be shared for every measurement
            probe_cc: contry code for the country the measurements should come from
        
        It may return a list of measurements on succesful execution, or a string
        with the possible error:
            - network_error : Error requesting data from ooni (status code != 200)
            - bad_arguments : Succesful request, but unvalid arguments
            - unknown       : unknown error 
    """
    assert since <= until, "since date should be before until date"

    # The error types
    NETWORK_ERROR = "network_error"
    BAD_ARGUMENTS = "bad_arguments"
    UNKOWN        = "unknown"  

    # Set the request arguments
    url = "https://api.ooni.io/api/v1/aggregation"
    params = {
        'since' : since.strftime("%Y-%m-%d"),
        'until' : until.strftime("%Y-%m-%d"),
        'probe_cc' : probe_cc,
        'axis_x' : 'measurement_start_day',
    }

    if domain:
        # params['domain'] = domain
        pass

    # filter by test name only if provided
    if test_name:
        params['test_name'] = test_name

    # perform the request
    req = requests.get(url, params=params)

    # Check request status
    if req.status_code != 200:
        return NETWORK_ERROR

    data = req.json()   

    # Check for errors
    if data.get('error'):
        return BAD_ARGUMENTS 

    result = data.get('result')
    if not result:
        return UNKOWN

    # process input data
    return [
        MeasurementDay( r['measurement_count'], 
                        r['anomaly_count'], 
                        r['failure_count'], 
                        datetime.strptime(r['measurement_start_day'], "%Y-%m-%d"), 
                        domain, 
                        r['confirmed_count'])
        for r in result
    ]

     

