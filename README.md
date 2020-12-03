This is an ntp client that reads the time from RTC if no ntp pool is responding.

- It reads all the available pools from "/etc/ntp.conf" (requires installation of ntp "apt install ntp")
- Doesn't RTC interface implementation
