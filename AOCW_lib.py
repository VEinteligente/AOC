"""
    This is the library code for the Aggregation Ooni Command-line Watcher,
    this code will check for suspicious changes in the anomaly rate for some specific
    set of pages
"""

# Third party imports
import json
import sys
import os
from typing import List
from datetime import datetime, timedelta
# Local imports
import AOCBackend as aoc_bend

class PermaConfig:
    """
        An object defining the persistent configuration stored locally 
        to setup the program execution 
    """

    class ERROR:
        OK : str = 'ok'
        COULD_NOT_READ_LIST_FILE : str = "could_not_read_list_file"
        COULD_NOT_ACCESS_CONFIG_FILE : str = "could_not_access_config_file"

    # Variable to check if everything went fine configurating this file
    state : str = ERROR.OK

    # If the process is paused
    active : bool = False

    # The file with the url list
    list_file : str = None

    # File to print the log:
    log_file : str = None

    # number before now to consider 
    n_days_before : int = 1

    # An alarming change of rate between the last measurement and current
    # measurement
    critical_anomaly_rate : float = 0.1

    # Map from url to map of str to float indicating how much has changed 
    # every url. Map format:
    # url : {
    #           "previous_rate" : float 
    #           "current_rate"  : float
    #           "change"        : float
    #           "last_check"    : date in format YYYY-mm-dd HH:MM:SS | None
    #           "last_update"   : date in format YYYY-mm-dd HH:MM:SS | None
    #       }
    urls = {}
    def __init__(   self,
                    log_file : str = None,
                    list_file : str = None,
                    critical_anomaly_rate : float = 0.1,
                    active : bool = True,
                    n_days_before : int = 1,
                    urls : dict = {}
                ):

        # Some consistency checking:
        assert critical_anomaly_rate > 0, "a negative anomaly rate makes no sense"
        assert n_days_before > 0, "a negative number of dates makes no sense"

        # Store the changes 
        self.list_file = list_file
        self.log_file = log_file
        self.active = active
        self.critical_anomaly_rate = critical_anomaly_rate
        self.n_days_before = n_days_before
        self.urls = urls

    def to_json(self) -> str:
        """
            Parse this object to a valid json formated string
        """
        json_dict = {
            "active" : self.active,
            "list_file" : self.list_file,
            "log_file" : self.log_file,
            "n_days_before" : self.n_days_before,
            "critical_anomaly_rate" : self.critical_anomaly_rate,
            "urls" : self.urls
        }
        return json.dumps(json_dict, indent=2)

    def save(self):
        """
            Save this config to the corresponding file 
        """
        # Convert this config to a json string
        config_str : str = self.to_json()

        # get path to this file
        config_path = os.path.join(os.environ['HOME'], ".aocw/" + AOCW.DEFAULTS.CONFIG_FILE)

        # Open the config file for writing
        try:
            with open(config_path, 'w') as config_file:
                print(config_str, file=config_file)
        except:
            self.state = PermaConfig.ERROR.COULD_NOT_ACCESS_CONFIG_FILE
            return

    def load(self):
        """
            Set this objects values to those in the local storage
        """
        # get path to the config file
        config_path = os.path.join(os.environ['HOME'], ".aocw/" + AOCW.DEFAULTS.CONFIG_FILE)

        # Open the config file for writing
        try:
            with open(config_path, 'r') as config_file:
                data = json.load(config_file)
                self.active                 = data['active']
                self.list_file              = data['list_file']
                self.log_file               = data['log_file']
                self.n_days_before          = data['n_days_before']
                self.critical_anomaly_rate  = data['critical_anomaly_rate']
                self.urls                   = data['urls']
        except:
            self.state = PermaConfig.ERROR.COULD_NOT_ACCESS_CONFIG_FILE
            return
    def add_entry(self, url : str):
        """
            Add one url to the url dict, ignore it if it is already in the url dict
        """
        if self.urls.get(url) is None:
            self.urls[url] = {
               "previous_rate" : -1.0, 
               "current_rate"  : -1.0,
               "change"        : None,
               "last_check"    : None,
               "last_update"   : None
           }
        
    


class AOCW:
    """
        An object defining the configuration provided for the user with 
        every command, to drive the command line program execution.
        There is essentially 3 actions we can perform with the command line:
            1) init: set the list to get the inputs from
            2) set: to change the value of some configuration
            3) show: to show a list with the last anomaly rate for every input in the list
    """

    #Enums to identify actions to perform and errors to check
    class ACTIONS:
        INIT  : str = 'init'
        SET   : str = 'set'
        SHOW  : str = 'show'
        RUN   : str = 'run'

    class ERRORS:
        OK : str = 'ok'
        NOT_ENOUGH_ARGS : str = 'not_enough_arguments' 
        INVALID_ACTION :  str = 'invalid_action' # an unrecognized action as first argument
        COULD_NOT_CREATE_DIR : str = 'could_not_create_dir' # could not create the config dir
        COULD_NOT_ACCESS_CONFIG_FILE : str = 'could_not_access_config_file'
        COULD_NOT_ACCESS_LOG_FILE : str = 'could_not_access_log_file'
        COULD_NOT_ACCESS_LIST_FILE : str = 'could_not_access_LIST_file'
        INVALID_ARGUMENTS : str = 'invalid_arguments'
        COULD_NOT_CREATE_LOG : str = 'could_not_create_log_file'
        MISSING_REQUIRED_ARGUMENT : str = 'missing_required_argument'
        COULD_NOT_SETUP_CONFIG_FILE : str = 'COULD_NOT_SETUP_CONFIG_FILE'

    class FLAGS:
        INIT_FILE_FLAG : str = '-f'
        INIT_FILE_FLAG_LONG : str = '--file'
        INIT_RATE_FLAG : str = '-r'
        INIT_RATE_FLAG_LONG : str = '--critical-rate'
        INIT_ACTIVE_FLAG : str = '-a'
        INIT_ACTIVE_FLAG_LONG : str = '--active'
        INIT_N_DAYS_FLAG : str = '-n'
        INIT_N_DAYS_FLAG_LONG : str = '--n-days'

    class DEFAULTS:
        CONFIG_FILE : str = "config.json"
        LOG_FILE    : str = "aocw.log"
        CRITICAL_RATE : float = 0.1
        ACTIVE : bool = True
        N_DAYS_BEFORE : int = 1

    # Member variables
    action: str = ACTIONS.SHOW
    state : str = ERRORS.OK



    def __init__(self, argv : List[str]):
        """
            argv : Input from the terminal, first argument is the action to perform 
        """

        if len(argv) <= 1:
            self.state = AOCW.ERRORS.NOT_ENOUGH_ARGS
            self.action = None
            return
        # Check which action is to be performed
        action = argv[1]
        if action == AOCW.ACTIONS.INIT:
            self.action = AOCW.ACTIONS.INIT
        elif action == AOCW.ACTIONS.SHOW:
            self.action = AOCW.ACTIONS.SHOW
        elif action == AOCW.ACTIONS.SET:
            self.action = AOCW.ACTIONS.SET
        elif action == AOCW.ACTIONS.RUN:
            self.action = AOCW.ACTIONS.RUN
        else:
            self.action = None
            self.state = AOCW.ERRORS.INVALID_ACTION
            return

        # Perform actions as specified
        if action == AOCW.ACTIONS.INIT:
            self.init(argv)
        if action == AOCW.ACTIONS.RUN:
            self.run(argv)
        else:
            print("Not yet implemented 😿")
    

    def alert(self):
        """
            Notify the user that a suspicious change has been found
        """
        print("🙀 ALERT 🙀")

    def init(self, argv : List[str]):
        """
            Init the config for first time.
            Optional positional arguments:
                1) -f --file file : File with the list of urls to check [REQUIRED]
                2) -r --critical-rate : a float number
                3) -a --active true | false  : if the program should start running or not
                4) -n --n-days int : how many days before to this to take in consideration 
        """
        home = os.environ['HOME']
        aocw_dir : str = os.path.join(home, ".aocw")

        # Parse the provided arguments
        list_file : str = None
        #   set the file
        if AOCW.FLAGS.INIT_FILE_FLAG in argv or AOCW.FLAGS.INIT_FILE_FLAG_LONG in argv:
            for i in range(len(argv)):
                if argv[i] == AOCW.FLAGS.INIT_FILE_FLAG or argv[i] == AOCW.FLAGS.INIT_FILE_FLAG_LONG:
                    if i == len(argv) - 1:
                        self.state = AOCW.ERRORS.INVALID_ARGUMENTS
                        return
                    list_file = argv[i+1]
                    try:
                        list_file = os.path.abspath(list_file)
                    except:
                        self.state = AOCW.ERRORS.INVALID_ARGUMENTS
                        return

                    break 
        else:
            self.state = AOCW.ERRORS.MISSING_REQUIRED_ARGUMENT
            return

        #   set the critical rate value
        initial_rate = AOCW.DEFAULTS.CRITICAL_RATE
        if AOCW.FLAGS.INIT_RATE_FLAG in argv or AOCW.FLAGS.INIT_RATE_FLAG_LONG in argv:
            for i in range(len(argv)):
                if argv[i] == AOCW.FLAGS.INIT_RATE_FLAG or argv[i] == AOCW.FLAGS.INIT_RATE_FLAG_LONG:
                    if i == len(argv) - 1:
                        self.state = AOCW.ERRORS.INVALID_ARGUMENTS
                        return
                    try:
                        initial_rate = float(argv[i+1])
                        assert initial_rate > 0
                    except:
                        self.state = AOCW.ERRORS.INVALID_ARGUMENTS
                        return
                    break 

        #   set the n-days value
        n_days_before = AOCW.DEFAULTS.N_DAYS_BEFORE
        if AOCW.FLAGS.INIT_N_DAYS_FLAG in argv or AOCW.FLAGS.INIT_N_DAYS_FLAG_LONG in argv:
            for i in range(len(argv)):
                if argv[i] == AOCW.FLAGS.INIT_N_DAYS_FLAG or argv[i] == AOCW.FLAGS.INIT_N_DAYS_FLAG_LONG:
                    if i == len(argv) - 1:
                        self.state = AOCW.ERRORS.INVALID_ARGUMENTS
                        return
                    try:
                        n_days_before = int(argv[i+1])
                        assert n_days_before > 0
                    except:
                        self.state = AOCW.ERRORS.INVALID_ARGUMENTS
                        return
                    break 

        #   set if the app is performing measurements or not
        active : bool = AOCW.DEFAULTS.ACTIVE
        if AOCW.FLAGS.INIT_ACTIVE_FLAG in argv or AOCW.FLAGS.INIT_ACTIVE_FLAG_LONG in argv:
            for i in range(len(argv)):
                if argv[i] == AOCW.FLAGS.INIT_ACTIVE_FLAG or argv[i] == AOCW.FLAGS.INIT_ACTIVE_FLAG_LONG:
                    if i == len(argv) - 1:
                        self.state = AOCW.ERRORS.INVALID_ARGUMENTS
                        return
                    active = argv[i+1].lower()
                    if active == 'true':
                        active = True
                    elif active == 'false':
                        active = False
                    else:
                        self.state = AOCW.ERRORS.INVALID_ARGUMENTS
                        return
                    break 

        # Create data dir if not exists
        if not os.path.exists(aocw_dir):
            try:
                print(f"Creating local storage dir: {aocw_dir}")
                os.mkdir(aocw_dir)
            except:
                self.state = AOCW.ERRORS.COULD_NOT_CREATE_DIR
                return  

        # Create log file:
        log_file = os.path.join(aocw_dir, AOCW.DEFAULTS.LOG_FILE)
        try:
            print(f"Creating log file in: {log_file}")
            with open(log_file, 'w') as log:
                pass
        except:
            self.state = AOCW.ERRORS.COULD_NOT_CREATE_LOG
            return

        # search for our config json
        config_file = os.path.join(aocw_dir, self.DEFAULTS.CONFIG_FILE)

        # ask the user to override the current file
        if os.path.exists(config_file):
            should_override : str = input("AOCW file already exist. Override? [y/n]: ").lower()
            while should_override != 'y' and should_override != 'n':
                print("Urecognized input")
                should_override = input("AOCW file already exist. Override? [y/n]: ").lower()
            
            if should_override == 'n':
                print("No changes made.")
                self.state = AOCW.ERRORS.OK
                return

        # Create the config file
        try:
            with open(config_file, 'w') as f:
                pass
        except:
            self.state = AOCW.ERRORS.COULD_NOT_ACCESS_CONFIG_FILE
            return

        try:
            permaConfig : PermaConfig = PermaConfig(log_file, list_file, initial_rate, active, n_days_before)
        except:
            self.state = AOCW.ERRORS.COULD_NOT_SETUP_CONFIG_FILE
            return
    
        permaConfig.save()
        if (permaConfig.state != PermaConfig.ERROR.OK):
            print("Error: ", permaConfig.state)
            self.state = AOCW.ERRORS.COULD_NOT_SETUP_CONFIG_FILE
            return
    
    def run(self, argv : List[str]):
        """
            Run this program if it is set up to do so. Load urls from the 
            specified file and evaluate them in the ooni api, store their data
        """
        # Shortcut function 
        date2str = lambda d : d.strftime("%Y-%m-%d %H:%M:%S")
        # Load the config
        permaConfig : PermaConfig = PermaConfig()
        permaConfig.load()
        if permaConfig.state != PermaConfig.ERROR.OK:
            self.state = AOCW.ERRORS.COULD_NOT_ACCESS_CONFIG_FILE
            return 

        # Open the log file in append mode
        try:
            log_file = open(permaConfig.log_file, 'a')
        except:
            self.state = AOCW.ERRORS.COULD_NOT_ACCESS_LOG_FILE
            return

        print(f"[INFO] {date2str(datetime.now())} Running check:", file=log_file)

        # setup since date
        until : datetime = datetime.now()
        since : datetime = until - timedelta(days=permaConfig.n_days_before)

        # Open list file and measure every url
        try:
            with open(permaConfig.list_file, "r") as list_file:
                for line in list_file.readlines():

                    # Some lines have an endline, trim it so they won't mess up the ooni input
                    if line[-1] == '\n':
                        line = line[:len(line)-1]

                    # Get data for this url
                    print(f"Retrieving data for {line}...")
                    days = aoc_bend.get_measurements_list_api(since, until, line)
                    now : datetime = datetime.now()
                    if isinstance(days, str):
                        print(f"[ERROR] {date2str(now)} Could not retrieve data for url: {line}. Error: {days}", file=log_file)
                        continue

                    if permaConfig.urls.get(line) is None:
                        permaConfig.add_entry(line)

                    dayset = aoc_bend.MeasurementSet(days)
                    ratio = dayset.get_avg_anomalies()
                    # If there was no measurements (metrics == -1), update the check date and keep going
                    if ratio == -1:
                        permaConfig.urls[line]['last_check'] = date2str(now)
                        continue
                    
                    last = permaConfig.urls[line]['current_rate']
                    if last == -1:
                        change = 0
                    else:
                        change = ratio - permaConfig.urls[line]['current_rate']
                    permaConfig.urls[line]['previous_rate'] = permaConfig.urls[line]['current_rate']
                    permaConfig.urls[line]['current_rate']  = ratio
                    permaConfig.urls[line]['change']        = change
                    permaConfig.urls[line]['last_check']    = date2str(now)
                    permaConfig.urls[line]['last_update']   = date2str(now)
                    
                    if change > permaConfig.critical_anomaly_rate:
                        self.alert()
                        print(f"[ALERT] {date2str(now)} Change of {round(change, 3)} for url: {line}", file=log_file)


        except:
            self.state = AOCW.ERRORS.COULD_NOT_ACCESS_LIST_FILE
            return

        permaConfig.save()
        log_file.close()
