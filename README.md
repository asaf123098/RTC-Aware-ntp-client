This is an ntp client based on the NTPClient from "ntplib" that reads the time from RTC if no ntp pool is responding.

- It reads all the available pools from "/etc/ntp.conf" (requires installation of ntp "apt install ntp")
- Doesn't RTC interface implementation
- Takes in account possible time loss since response from the server until setting system time

Simply call NTPHandler().turn_on with the proper time zone to turn on, and NTPHandler.turn_off to turn off.