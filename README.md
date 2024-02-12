# dbus-loxone-smartmeter

Integrate data points from Loxone into [Victron Energies Venus OS](https://github.com/victronenergy/venus)

> [!NOTE]  
> Readme is not completed yet.

## Purpose

With the scripts in this repo it should be easy possible to install, uninstall, restart a service that connects the Loxone Miniserver to the VenusOS and GX devices from Victron.
Idea is pasend on @RalfZim project linked below.

## How it works

### Details / Process

As mentioned above the script is inspired by @RalfZim fronius smartmeter implementation.
So what is the script doing:

- Running as a service
- connecting to DBus of the Venus OS `com.victronenergy.grid.http_40` or `com.victronenergy.pvinverter.http_40`
- After successful DBus connection the Loxone Outputs are accessed via REST-API
- Paths are added to the DBus with default value 0 - including some settings like name, etc
- After that a "loop" is started which pulls the Loxone data every 500ms from the REST-API and updates the values in the DBus

Thats it 😄

### Pictures

![Tile Overview](img/venus-os-tile-overview.PNG)
![Remote Console - Overview](img/venus-os-remote-console-overview.PNG)
![SmartMeter - Values](img/venus-os-shelly3em-smartmeter.PNG)
![SmartMeter - Device Details](img/venus-os-shelly3em-smartmeter-devicedetails.PNG)

## Install & Configuration

### Get the code

Just grap a copy of the main branche and copy them to `/data/dbus-shelly-3em-smartmeter`.
After that call the install.sh script.

The following script should do everything for you:

```
wget https://github.com/lucienkerl/dbus-loxone-smartmeter/archive/refs/heads/main.zip
unzip main.zip "dbus-loxone-smartmeter-main/*" -d /data
mv /data/dbus-loxone-smartmeter-main /data/dbus-loxone-smartmeter
chmod a+x /data/dbus-loxone-smartmeter/install.sh
/data/dbus-loxone-smartmeter/install.sh
rm main.zip
```

⚠️ Check configuration after that - because service is already installed an running and with wrong connection data (host, username, pwd) you will spam the log-file

### Change config.ini

Within the project there is a file `/data/dbus-loxone-smartmeter/config.ini` - just change the values - most important is the host, username and password in section "MS". More details below:

| Section   | Config vlaue   | Explanation                                                                                   |
| --------- | -------------- | --------------------------------------------------------------------------------------------- |
| DEFAULT   | AccessType     | Fixed value 'OnPremise'                                                                       |
| DEFAULT   | SignOfLifeLog  | Time in minutes how often a status is added to the log-file `current.log` with log-level INFO |
| DEFAULT   | CustomName     | Name of your device - usefull if you want to run multiple versions of the script              |
| DEFAULT   | DeviceInstance | DeviceInstanceNumber e.g. 40                                                                  |
| DEFAULT   | Role           | use 'GRID' or 'PVINVERTER' to set the type of the shelly 3EM                                  |
| DEFAULT   | Position       | Available Postions: 0 = AC, 1 = AC-Out 1, AC-Out 2                                            |
| DEFAULT   | LogLevel       | Define the level of logging - lookup: https://docs.python.org/3/library/logging.html#levels   |
| ONPREMISE | Host           | IP or hostname of on-premise Shelly 3EM web-interface                                         |
| ONPREMISE | Username       | Username for htaccess login - leave blank if no username/password required                    |
| ONPREMISE | Password       | Password for htaccess login - leave blank if no username/password required                    |
| ONPREMISE | L1Position     | Which input on the Shelly in 3-phase grid is supplying a single Multi                         |

### Remapping L1

In a 3-phase grid with a single Multi, Venus OS expects L1 to be supplying the only Multi. This is not always the case. If for example your Multi is supplied by L3 (Input `C` on the Shelly) your GX device will show AC Loads as consuming from both L1 and L3. Setting `L1Position` to the appropriate Shelly input allows for remapping the phases and showing correct data on the GX device.

If your single Multi is connected to the Input `A` on the Shelly you don't need to change this setting. Setting `L1Position` to `2` would swap the `B` CT & Voltage sensors data on the Shelly with the `A` CT & Voltage sensors data on the Shelly. Respectively, setting `L1Position` to `3` would swap `A` and `C` inputs.

## Used documentation

- https://github.com/victronenergy/venus/wiki/dbus#grid DBus paths for Victron namespace GRID
- https://github.com/victronenergy/venus/wiki/dbus#pv-inverters DBus paths for Victron namespace PVINVERTER
- https://github.com/victronenergy/venus/wiki/dbus-api DBus API from Victron
- https://www.victronenergy.com/live/ccgx:root_access How to get root access on GX device/Venus OS

## Discussions on the web

This module/repository has been posted on the following threads:

- https://community.victronenergy.com/questions/125793/shelly-3em-smartmeter-with-venusos-cerbo-gx.html
