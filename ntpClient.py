# RTC-Aware-ntp-client
import time
import ntplib
import socket
import subprocess
from pytz import timezone
from datetime import datetime
from threading import Thread


MAX_ALLOWED_STRATUM = 15
TIME_FORMAT_STAMP = "%Y-%m-%d %H:%M:%S"
SAMPLE_THRESHOLD = 0.128

ONE_MINUTE = 60
TEN_MINUTES = ONE_MINUTE * 10
SEVENTEEN_MINUTES = ONE_MINUTE * 17


class NTPHandler:

    def __init__(self):
        self.rtc_clock = Clock()
        self.client = ntplib.NTPClient()
        self.possible_pools = self.get_ntp_conf_pools()
        self.keep_running = True
        self.__thread = None

    @staticmethod
    def get_ntp_conf_pools():
        with open("/etc/ntp.conf", "r") as conf_file:
            pools = [row for row in conf_file if row.startswith("pool")]

        return list(map(lambda row: row.split()[1], pools))

    def turn_on(self, time_zone):
        """
        :param time_zone: Should be in a "Asia/Jerusalem format same as the output of
        "timedatectl list-timezones" command
        """
        self.keep_running = True
        self.__thread = Thread(target=self.__turn_on, args=(timezone(time_zone),))
        self.__thread.setDaemon(True)
        self.__thread.start()

    def __turn_on(self, time_zone):
        self.set_timedatectl_ntp(False)
        while self.keep_running:
            time_from_ntp_server, local_time_when_received = self.get_current_time_from_server()

            if time_from_ntp_server:
                local_time_diff_from_server = abs(time_from_ntp_server - local_time_when_received)
                self.update_system_time_with_ntp_time(time_from_ntp_server, local_time_when_received, time_zone)

                if local_time_diff_from_server.total_seconds() > SAMPLE_THRESHOLD:
                    print(f"Diff between local and server ({local_time_diff_from_server}) is higher "
                          f"than {SAMPLE_THRESHOLD}, waiting just 1 minute")
                    self.__sleep_and_check_exit_request(ONE_MINUTE)
                else:
                    print(f"Diff between local and server ({local_time_diff_from_server}) is lower "
                          f"than {SAMPLE_THRESHOLD}, waiting 17 minutes")
                    self.__sleep_and_check_exit_request(SEVENTEEN_MINUTES)

            elif not self.rtc_clock.is_reset():
                print("Ntp pools unavailable, setting time from RTC, and trying again in 10 minutes")
                current_time = self.rtc_clock.get()
                current_time = current_time.astimezone(time_zone)
                self.set_system_time(current_time)
                self.__sleep_and_check_exit_request(TEN_MINUTES)

            else:
                print("Ntp pools unavailable, RTC is reset, setting RTC to now and trying again in 10 minutes")
                self.rtc_clock.set()
                self.__sleep_and_check_exit_request(TEN_MINUTES)

    @staticmethod
    def set_timedatectl_ntp(state: bool):
        ShellCommand(["timedatectl", "set-ntp", str(state)])

    def get_current_time_from_server(self):
        response, local_time_when_received = self.__get_available_pool()
        time_from_ntp_server = None

        if response:
            time_from_ntp_server = datetime.utcfromtimestamp(response.tx_time)
            time_from_ntp_server = time_from_ntp_server.replace(tzinfo=timezone("UTC"))

        return time_from_ntp_server, local_time_when_received

    def __get_available_pool(self) -> (ntplib.NTPStats, datetime):
        for pool in self.possible_pools:
            try:
                response = self.client.request(pool, timeout=3)
                if response.stratum <= MAX_ALLOWED_STRATUM:
                    return response, self.__get_utc_now()
            except socket.gaierror:
                print(f"Failed connecting to {pool}")
                continue

        return None, None

    def update_system_time_with_ntp_time(self, time_from_ntp_server, local_time_when_received, time_zone):
        self.__get_utc_now()
        time_since_received = self.__get_utc_now() - local_time_when_received
        time_to_set = time_from_ntp_server + time_since_received
        time_to_set = time_to_set.astimezone(time_zone)

        self.set_system_time(time_to_set)
        self.rtc_clock.set()

    @staticmethod
    def __get_utc_now():
        utcnow = datetime.utcnow()
        return utcnow.replace(tzinfo=timezone("UTC"))

    @staticmethod
    def set_system_time(time_to_set: datetime):
        ShellCommand(["timedatectl", "set-time", time_to_set.strftime("%Y-%m-%d %H:%M:%S")])

    def __sleep_and_check_exit_request(self, sleep_time):
        start_time = time.time()

        while time.time() - start_time < sleep_time and self.keep_running:
            time.sleep(1)

    def turn_off(self):
        self.keep_running = False
        if self.__thread and self.__thread.is_alive():
            print("Turning NTP Handler off..")
            self.__thread.join(SEVENTEEN_MINUTES)
            print("NTP Handler is off")


class ShellCommand:

    def __init__(self, args):
        self.proc = subprocess.Popen(args=args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, _ = self.proc.communicate()

        assert self.proc.returncode == 0, f"Failed '{' '.join(args)}' ({stdout.decode()})"
