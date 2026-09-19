import json
from json import JSONDecodeError
from time import strftime

from datetime import datetime


import win32gui
import win32process
import psutil

import time

from psutil import NoSuchProcess
from pynput import keyboard, mouse
from pathlib import Path


def retrieve_configuration()->list:
    """Retrieves The users configuration info, AKA the json user_config. If it is not exist it creates it
    {'ide_to_track': ['exe_1','exe_2', ...]}
    """
    user = {"ide_to_track": ["pycharm64.exe", "Code.exe", "devenv.exe", "idea64.exe"]}
    try:
        with open("user_config.json", "r") as file:
            user = json.load(file)
    except FileNotFoundError:
        with open("user_config.json", "w") as file:
            json.dump(user, file, indent=4)
    return user["ide_to_track"]

def active_application() ->tuple[str,int,str]:
    """Returns the current running process/window that we are working on OR we have open"""

    #retrieving HWND number
    hwnd = win32gui.GetForegroundWindow()
    #print(hwnd)

    #It returns the window  we are currently in
    window_text = win32gui.GetWindowText(hwnd)
    window = window_text.split("|")[-1]
    window_format = window.replace(" ", "")
    window_format = "none" if len(window_format) == 0 else window_format

    #Retrieves the identifier of the thread and process that created the specified window(HWND)
    #we only care about PID
    thread_id,pid = win32process.GetWindowThreadProcessId(hwnd)
    #print(thread_id,pid)

    #psutil.Process returns Useful info about given pid->(pid=21132, name='pycharm64.exe', status='running', started='16:39:27')
    try:
        process = psutil.Process(pid) # App failure detected (1) Unexpected 'no process found with the given pid'
    except Exception as e:
        print(e)
        process_name = "None"
    else:
        process_name = process.name()

    return process_name,pid,window_format


def day_changed(data:dict)->bool:
    """Checks if somehow day changed while you were still working. if Yes, saves all the data to the
     previous day (locally and to Pixela)."""
    date_today = datetime.now().strftime("%Y:%m:%d")
    if date_today != data["date"]:
        console_print_save(f"Day Changed Detected-->{date_today}")

        #Log file is Updates every New day
        with open("log.txt", "a") as log:
            log.write(f"{data['date']} : {data['hours_coding']}\n")

        date_today = datetime.now().strftime("%Y:%m:%d")
        data["date"] = date_today
        data["hours_coding"] = 0.0
        return True
    return False

def retrieve_data()->dict:
    """Retrieves The Time if there is prior data, if not Creates the file"""
    date = datetime.now().strftime("%Y:%m:%d")
    try:
        with open("last_session.json", "r") as file:
            data = json.load(file)
    except (FileNotFoundError, JSONDecodeError):
        with open("last_session.json", "w") as file:
            data = {
                "date": date,
                "hours_coding": 0.0
            }
            json.dump(data,file,indent=4)

    return data

def write_to_file(data:dict):
    with open ("last_session.json", "w") as file:
        json.dump(data,file,indent=4)

def ide_closed(py_pid:int,data_save:dict):
    """This method checks if the Pycharm got closed while the .exe is running on the background.
    Checks if the pycharm's PID is changed. if it is, then that means that the program closed"""

    try:
        process = psutil.Process(py_pid)
    except NoSuchProcess:
        #that means Previous Pycharm process deleted/closed
        write_to_file(data_save)

def console_print_save(info:str):
    with open("console_log.txt", "a") as con:
        con.write(f"{info}\n")

#_________________________________MAIN_________________________________________________
class Main:
    def __init__(self):

        self.keyboard_listener = keyboard.Listener(on_press=self.keyboard_activity)

        self.mouse_listener = mouse.Listener(on_move=self.mouse_activity,on_click=self.mouse_click)

        self.date_today = datetime.now().strftime("%Y:%m:%d")

        self.data = retrieve_data()

        self.last_activity = time.monotonic()
        self.last_modified = CONFIG_FILE.stat().st_mtime_ns

        self.set_idle_time = 600  # in seconds --> 10 min max idle

        self.working_ides = retrieve_configuration()
        #self.counter_functionality()
        #self.run()

    def keyboard_activity(self,key):
        self.last_activity = time.monotonic()

    def mouse_activity(self,x, y):
        self.last_activity = time.monotonic()

    def mouse_click(self,x,y,button,pressed):
        self.last_activity = time.monotonic()

    #def run(self):
        #self.keyboard_listener.start()
        #self.mouse_listener.start()

    def load_if_changed(self):
        """Retrieves the  updated json IDE data to track . If json structure is messed up, or IDE list doesn't have .exe in it -> Default data will be used"""
        current_modified = CONFIG_FILE.stat().st_mtime_ns

        if current_modified != self.last_modified:
            try:
                with CONFIG_FILE.open("r") as file:
                    self.working_ides = json.load(file)["ide_to_track"]
            except JSONDecodeError:
                print("The JSON data file you changed is not structured as expected- DEFAULT DATA WILL BE USED INSTEAD")
                console_print_save(
                    "The JSON data file you changed is not structured as expected- DEFAULT DATA WILL BE USED INSTEAD")
                self.working_ides = DEFAULT_WORKING_IDES
            else:
                invalid_data = any(not item.endswith(".exe") for item in self.working_ides)
                if invalid_data:
                    print(
                        "Some of the values in json file changed and are not ending with '.exe' - DEFAULT DATA WILL BE USED INSTEAD")
                    console_print_save(
                        "Some of the values in json file changed and are not ending with '.exe' - DEFAULT DATA WILL BE USED INSTEAD")
                    self.working_ides = DEFAULT_WORKING_IDES
            self.last_modified = current_modified

    def counter_functionality(self):

        self.keyboard_listener.start()
        self.mouse_listener.start()

        #Check's if For the current day there is prior info
        if self.data["date"] == self.date_today and self.data["hours_coding"] != 0:
            #that means that for today's date there is a prior info
            run_time = self.data["hours_coding"]
        else:
            run_time = 0


        is_idle = 0
        ide_pid = None

        current_session = time.monotonic()
        start_session = time.monotonic()

        time_format = strftime("%H hrs: %M mins: %S sec",time.gmtime(self.data['hours_coding']))
        print(f"Previous Data for today's day ({self.data['date']}) time codding: {time_format}")
        console_print_save(f"Previous Data for today's day ({self.data['date']}) time codding: {time_format}")
        try:
            while True:
                self.load_if_changed()
                ide_closed(ide_pid,self.data)
                if day_changed(self.data):
                    run_time = 0
                    write_to_file(self.data)


                if time.monotonic() - current_session >= 2700:
                    #2700 seconds are 45 mins
                    #That mean, time to Send the Data locally
                    current_session = time.monotonic()

                    write_to_file(self.data)


                active_app,app_pid,win_tab = active_application()
                if active_app in self.working_ides:
                    ide_pid = app_pid
                    idle_time = time.monotonic() - self.last_activity
                    if idle_time > self.set_idle_time:
                        print(f"You Have been Idle for more than {idle_time/60} Mins!!")
                        is_idle = 1
                        #print(f"current programming run time:{(run_time - is_idle * set_idle_time) / 60}")
                    else:
                        run_time = (run_time + 1) - is_idle * self.set_idle_time
                        self.data["hours_coding"] = run_time
                        is_idle= 0

                time.sleep(1)

        except KeyboardInterrupt:
            print("Your IDE Closed")
            console_print_save("Your IDE Closed")
            time_format = strftime("%H hrs: %M mins: %S sec", time.gmtime(self.data['hours_coding']))
            current_time = strftime("%H hrs: %M mins: %S sec", time.gmtime(time.monotonic()-start_session))
            print(f"Total today's Runtime ->{time_format}, Current Runtime->{current_time}")
            console_print_save(f"Total today's Runtime ->{time_format}, Current Runtime->{current_time}")
            write_to_file(self.data)


if __name__ == "__main__":
    DEFAULT_WORKING_IDES = ["pycharm64.exe", "Code.exe", "devenv.exe", "idea64.exe"]
    retrieve_configuration()
    CONFIG_FILE = Path("user_config.json")
    main = Main()
    main.counter_functionality()