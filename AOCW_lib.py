"""
    This is the library code for the Aggregation Ooni Command-line Watcher,
    this code will check for suspicious changes in the anomaly rate for some specific
    set of pages
"""

# Third party imports
from    typing      import List
from    datetime    import datetime, timedelta
from    tabulate    import tabulate

import json
import sys
import os
import getpass
import ssl, smtplib

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

    # address to send notifications
    mail_to_notify = "your@email.com"

    # mail address used to send notifications
    sender_mail = "my@email.com"

    # sender mail password
    sender_mail_pswd = "supersecurepasssword"

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
                    log_file                : str = None,
                    list_file               : str = None,
                    critical_anomaly_rate   : float = 0.1,
                    active                  : bool = True,
                    n_days_before           : int = 1,
                    mail_to_notify          : str = '',
                    sender_mail             : str = None,
                    sender_password         : str = None,
                    urls                    : dict = {},
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
        self.mail_to_notify = mail_to_notify
        self.sender_mail = sender_mail
        self.sender_mail_pswd = sender_password

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
            "urls" : self.urls,
            "mail_to_notify" : self.mail_to_notify,
            "sender_mail" : self.sender_mail,
            "sender_mail_pswd" : self.sender_mail_pswd

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
                self.sender_mail_pswd       = data['sender_mail_pswd']
                self.sender_mail            = data['sender_mail']
                self.mail_to_notify         = data['mail_to_notify']
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
            4) run: to request data from ooni
    """

    #Enums to identify actions to perform and errors to check
    class ACTIONS:
        INIT        : str = 'init'
        INIT_HELP   : str = "Initalize the aocw, creating its local files and setting up initial parameters."
        SET         : str = 'set'
        SET_HELP    : str = 'Change customization parameters'
        SHOW        : str = 'show'
        SHOW_HELP   : str = 'Show currently collected data'
        RUN         : str = 'run'
        RUN_HELP    : str = 'Run computations over the specified list'
        info = [
            {
                'action' : INIT,
                'help'   : INIT_HELP
            },
            {
                'action' : RUN,
                'help'   : RUN_HELP
            },
            {
                'action' : SET,
                'help'   : SET_HELP
            },
            {
                'action' : SHOW,
                'help'   : SHOW_HELP
            }
        ]

    class ERRORS:
        OK : str = 'ok'
        NOT_ENOUGH_ARGS : str = 'not_enough_arguments' 
        INVALID_ACTION :  str = 'invalid_action' # an unrecognized action as first argument
        COULD_NOT_CREATE_DIR : str = 'could_not_create_dir' # could not create the config dir
        COULD_NOT_ACCESS_CONFIG_FILE : str = 'could_not_access_config_file'
        COULD_NOT_ACCESS_LOG_FILE : str = 'could_not_access_log_file'
        COULD_NOT_ACCESS_LIST_FILE : str = 'could_not_access_list_file'
        INVALID_ARGUMENTS : str = 'invalid_arguments'
        COULD_NOT_CREATE_LOG : str = 'could_not_create_log_file'
        MISSING_REQUIRED_ARGUMENT : str = 'missing_required_argument'
        COULD_NOT_SETUP_CONFIG_FILE : str = 'could_not_setup_config_file'

    class DEFAULTS:
        CONFIG_FILE : str = "config.json"
        LOG_FILE    : str = "aocw.log"
        CRITICAL_RATE : float = 0.1
        ACTIVE : bool = True
        N_DAYS_BEFORE : int = 1

    class INIT_FLAGS:
        INIT_FILE_FLAG      : str = '-f'
        INIT_FILE_FLAG_LONG : str = '--file'
        INIT_FILE_HELP      : str = "[REQUIRED] path to the file that contains the URL list to check when running"
        INIT_RATE_FLAG      : str = '-r'
        INIT_RATE_FLAG_LONG : str = '--critical-rate'
        INIT_RATE_HELP      : str = "Specify the default anomaly rate. Defaults to 0.1"
        INIT_ACTIVE_FLAG        : str = '-a'
        INIT_ACTIVE_FLAG_LONG   : str = '--active'
        INIT_ACTIVE_HELP        : str = "Specify if the program should keep asking for data (true or false). Defaults to true."
        INIT_N_DAYS_FLAG        : str = '-n'
        INIT_N_DAYS_FLAG_LONG   : str = '--n-days'
        INIT_N_DAYS_HELP        : str = "specify the ammount of days before to consider"
        INIT_EMAIL_FLAG         : str = "-e"
        INIT_EMAIL_FLAG_LONG    : str = "-email-to-notify"
        INIT_EMAIL_HELP         : str = "[REQUIRED] The email address to be notified when some weird event is happening"
        info = [
            {
                "short" : INIT_FILE_FLAG,
                "long"  : INIT_FILE_FLAG_LONG,
                "help"  : INIT_FILE_HELP
            },
            {
                "short" : INIT_RATE_FLAG,
                "long"  : INIT_RATE_FLAG_LONG,
                "help"  : INIT_RATE_HELP
            },
            {
                "short" : INIT_ACTIVE_FLAG,
                "long"  : INIT_ACTIVE_FLAG_LONG,
                "help"  : INIT_ACTIVE_HELP
            },
            {
                "short" : INIT_N_DAYS_FLAG,
                "long"  : INIT_N_DAYS_FLAG_LONG,
                "help"  : INIT_N_DAYS_HELP
            },
            {
                "short" : INIT_EMAIL_FLAG,
                "long"  : INIT_EMAIL_FLAG_LONG,
                "help"  : INIT_EMAIL_HELP
            },
        ]


    # Member variables
    action: str = ACTIONS.SHOW
    state : str = ERRORS.OK

    def __init__(self, argv : List[str]):
        """
            argv : Input from the terminal, first argument is the action to perform 
        """

        if len(argv) == 1:
            self.state = AOCW.ERRORS.OK
            # Print some help
            self.help()
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
        elif action == AOCW.ACTIONS.RUN:
            self.run(argv)
        elif action == AOCW.ACTIONS.SHOW:
            self.show(argv)
        else:
            print("Not yet implemented 😿")
    

    def alert(self, permaConfig : PermaConfig, change : float, url : str, datestr : str, logfile = None):
        """
            Notify the user that a suspicious change has been found

            permaConfig: The config object currently in use
            change: The actual change delta found 
            url: The url with anomalies
            datestr: Date when this anomaly was found (in string)
            logfile: A file object containing the logfile used to log for errors.

        """
        print("🙀 ALERT 🙀")
        # Set up email data
        sender = permaConfig.sender_mail
        reciever = permaConfig.mail_to_notify
        psswd = permaConfig.sender_mail_pswd
        message = f"Subject: [ALERT] url {url}\n\nUrl {url} registered an alarming change of {round(change,4)} at {datestr}"

        # set up email server config
        port = 465
        context = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
                server.login(sender, psswd)   
                server.sendmail(sender, reciever, message)
        except:
            if logfile:
                print(f"[ERROR] {datestr} Could not send email to {permaConfig.mail_to_notify} from {permaConfig.sender_mail} of anomaly with change {round(change,4)} \
                        with url {url}", file=logfile)

    def help(self):
        """
            Print help message
        """
        print("Usage:\n   AOCW.py ACTION [ACTION OPTIONS]")
        print(f"     Where ACTION = {AOCW.ACTIONS.INIT} | {AOCW.ACTIONS.RUN} | {AOCW.ACTIONS.SET} | {AOCW.ACTIONS.SHOW}")
        for d in AOCW.ACTIONS.info:
            print(f"        {d['action']} : {d['help']}")

        print("Try --help option with any action to get more details")

    def init(self, argv : List[str]):
        """
            Init the config for first time.
            Optional positional arguments:
                1) -f --file file : File with the list of urls to check [REQUIRED]
                2) -r --critical-rate : a float number
                3) -a --active true | false  : if the program should start running or not
                4) -n --n-days int : how many days before to this to take in consideration
                5) -e --email-to-notify str : the email address to send notifications to 
        """
        home = os.environ['HOME']
        aocw_dir : str = os.path.join(home, ".aocw")

        if "-h" in argv or "--help" in argv or len(argv) == 2:
            AOCW.init_help()
            self.state = AOCW.ERRORS.OK
            return

        # Parse the provided arguments
        list_file : str = None
        #   set the file
        if AOCW.INIT_FLAGS.INIT_FILE_FLAG in argv or AOCW.INIT_FLAGS.INIT_FILE_FLAG_LONG in argv:
            for i in range(len(argv)):
                if argv[i] == AOCW.INIT_FLAGS.INIT_FILE_FLAG or argv[i] == AOCW.INIT_FLAGS.INIT_FILE_FLAG_LONG:
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
        if AOCW.INIT_FLAGS.INIT_RATE_FLAG in argv or AOCW.INIT_FLAGS.INIT_RATE_FLAG_LONG in argv:
            for i in range(len(argv)):
                if argv[i] == AOCW.INIT_FLAGS.INIT_RATE_FLAG or argv[i] == AOCW.INIT_FLAGS.INIT_RATE_FLAG_LONG:
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
        if AOCW.INIT_FLAGS.INIT_N_DAYS_FLAG in argv or AOCW.INIT_FLAGS.INIT_N_DAYS_FLAG_LONG in argv:
            for i in range(len(argv)):
                if argv[i] == AOCW.INIT_FLAGS.INIT_N_DAYS_FLAG or argv[i] == AOCW.INIT_FLAGS.INIT_N_DAYS_FLAG_LONG:
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
        if AOCW.INIT_FLAGS.INIT_ACTIVE_FLAG in argv or AOCW.INIT_FLAGS.INIT_ACTIVE_FLAG_LONG in argv:
            for i in range(len(argv)):
                if argv[i] == AOCW.INIT_FLAGS.INIT_ACTIVE_FLAG or argv[i] == AOCW.INIT_FLAGS.INIT_ACTIVE_FLAG_LONG:
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

        #   parse the email to notify
        email : str = None
        if AOCW.INIT_FLAGS.INIT_EMAIL_FLAG in argv or AOCW.INIT_FLAGS.INIT_EMAIL_FLAG_LONG in argv:
            for i in range(len(argv)):
                if argv[i] == AOCW.INIT_FLAGS.INIT_EMAIL_FLAG or argv[i] == AOCW.INIT_FLAGS.INIT_EMAIL_FLAG_LONG:
                    if i == len(argv) - 1:
                        self.state = AOCW.ERRORS.INVALID_ARGUMENTS
                        return
                    email = argv[i+1]
                    break 
        else:
            self.state = AOCW.ERRORS.MISSING_REQUIRED_ARGUMENT
            return

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

        YELLOW = "\u001b[33m"
        ENDC = '\033[0m'
        # Get sender mail
        confirm = False
        print("We need a gmail email address that will send notifications in case of some anomaly.")
        print(f"{YELLOW}WARNING: We highly recommend you to create a dummy email account for this purpose since we can ensure{ENDC}")
        print(f"{YELLOW}your security for now.{ENDC}")
        sender_mail = ''
        while not confirm:
            sender_mail : str = input("Sender mail: ")
            print(f"Your sender account will be: {sender_mail}")
            yn = input("Are you agree?[y/n]: ").lower()
            while yn != 'y' and yn != 'n':
                print("unrecognized input")
                yn = input("Are you agree?[y/n]: ").lower()

            if yn == 'y':
                confirm = True

        # Get sender password
        sender_pswd = ''
        confirm = False
        while not confirm:
            sender_pswd = getpass.getpass(f"Password for {sender_mail}: ")
            confirmation_pswd = getpass.getpass("Confirm password: ")
            confirm = sender_pswd == confirmation_pswd
            if not confirm:
                print("Password not matching, retry")

        try:
            permaConfig : PermaConfig = PermaConfig(log_file, 
                                                    list_file, 
                                                    initial_rate, 
                                                    active, 
                                                    n_days_before,
                                                    email,
                                                    sender_mail,
                                                    sender_pswd)
        except:
            self.state = AOCW.ERRORS.COULD_NOT_SETUP_CONFIG_FILE
            return

        permaConfig.save()
        if (permaConfig.state != PermaConfig.ERROR.OK):
            print("Error: ", permaConfig.state)
            self.state = AOCW.ERRORS.COULD_NOT_SETUP_CONFIG_FILE
            return
    
    def init_help():
        print(" Initialize local files to store logic and data retrieved from ooni.")
        print(" Possible arguments to setup the installation:")
        for f in AOCW.INIT_FLAGS.info:
            print(f"    {f['short']}, {f['long']}:   {f['help']}\n")

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

        # Check if the program is currently active
        if not permaConfig.active:
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
                        self.alert(permaConfig, change, line, date2str(now))
                        print(f"[ALERT] {date2str(now)} Change of {round(change, 3)} for url: {line}", file=log_file)


        except:
            self.state = AOCW.ERRORS.COULD_NOT_ACCESS_LIST_FILE
            return

        permaConfig.save()
        log_file.close()

    def show(self, argv : List[str]):
        """
            Print the current config and the currently stored data
        """
        # Load local data
        permaConfig : PermaConfig = PermaConfig()
        permaConfig.load()
        if permaConfig.state != PermaConfig.ERROR.OK:
            self.state = AOCW.ERRORS.COULD_NOT_ACCESS_CONFIG_FILE
            return


        # For string coloring:
        RED  = '\033[91m'
        YELLOW = "\u001b[33m"
        GREEN  = "\u001b[32m" 
        BLUE   = "\u001b[36m"
        ENDC = '\033[0m'
        critical_rate : float = permaConfig.critical_anomaly_rate
        alert = lambda f : f"{RED if f > critical_rate else ''}{f}{ENDC if f > critical_rate else ''}"

        # Build the table
        header : List[str] = ["input", "last check", "last update", "previous rate", "current rate", "change"]
        header = map(lambda s : f"{BLUE}{s}{ENDC}",header)

        body = [
            [  
                inpt, details["last_check"], details["last_update"], 
                f"{round(details['previous_rate'], 3)}", 
                f"{round(details['current_rate'], 3)}",
                f"{alert(round(details['change'], 3)) if details['change'] is not None else 'No change to show'}", 
            ]
            for (inpt, details) in permaConfig.urls.items()
        ]

        # If there's no rows to show:
        if len(body) == 0:
            body.append(
                ["-- No sites to show --"]
            )

        table = [header] + body


        print(f"List file: {YELLOW}{permaConfig.list_file}{ENDC}")
        print(f"Specified critical rate: {RED}{permaConfig.critical_anomaly_rate}{ENDC}")
        print(f"Checking {GREEN}{permaConfig.n_days_before}{ENDC} days before the current day to request for measurements")
        print(f"Sending notifications from: {YELLOW}{permaConfig.sender_mail}{ENDC}")
        print(f"Notifying: {YELLOW}{permaConfig.mail_to_notify}{ENDC}")
        if permaConfig.active:
            print(f"Active: {GREEN} true {ENDC}")
        else:
            print(f"Active: {RED} false {ENDC}")
        print(tabulate(table))
        
        
        
