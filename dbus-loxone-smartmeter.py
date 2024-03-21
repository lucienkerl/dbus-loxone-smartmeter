#!/usr/bin/env python
# vim: ts=2 sw=2 et

# import normal packages
import platform
import logging
import logging.handlers
import sys
import base64
import os
import sys
import json

if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import requests  # for http GET
import configparser  # for config/ini file

# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService


class DbusLoxoneService:
    def __init__(self, paths, productname='Loxone', connection='Loxone HTTP API'):
        config = self._getConfig()
        deviceinstance = int(config['DEFAULT']['DeviceInstance'])
        customname = config['DEFAULT']['CustomName']
        role = config['DEFAULT']['Role']

        allowed_roles = ['pvinverter', 'grid']
        if role in allowed_roles:
            servicename = 'com.victronenergy.' + role
        else:
            logging.error("Configured Role: %s is not in the allowed list")
            exit()

        if role == 'pvinverter':
            productid = 0xA144
        else:
            productid = 45069

        self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
        self._paths = paths

        logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion',
                                   'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', productid)
        self._dbusservice.add_path('/DeviceType',
                                   345)  # found on https://www.sascha-curth.de/projekte/005_Color_Control_GX.html#experiment - should be an ET340 Engerie Meter
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', customname)
        self._dbusservice.add_path('/Latency', None)
        self._dbusservice.add_path('/FirmwareVersion', 0.3)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Role', role)
        self._dbusservice.add_path('/Position', self._getLoxonePosition())  # normaly only needed for pvinverter
        self._dbusservice.add_path('/Serial', self._getLoxoneSerial())
        self._dbusservice.add_path('/UpdateIndex', 0)

        # add path values to dbus
        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path, settings['initial'], gettextcallback=settings['textformat'], writeable=True,
                onchangecallback=self._handlechangedvalue)

        # last update
        self._lastUpdate = 0

        # add _update function 'timer'
        gobject.timeout_add(int(config['DEFAULT']['UpdateInterval']), self._update)  # pause 500ms before the next request

        # add _signOfLife 'timer' to get feedback in log every 5minutes
        gobject.timeout_add(self._getSignOfLifeInterval() * 60 * 1000, self._signOfLife)

    def _getLoxoneSerial(self):
        config = self._getConfig()
        url = "http://" + config['MS']['HOST'] + "/jdev/cfg/apiKey"
        payload = {}
        sample_string_bytes = (config['MS']['Username'] + ':' + config['MS']['Password']).encode("ascii")
        base64_bytes = base64.b64encode(sample_string_bytes)
        base64_string = base64_bytes.decode("ascii")
        headers = {
            'Authorization': 'Basic ' + base64_string
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        response_json = response.json()
        value = response_json['LL']['value']
        value = value.replace("\'", "\"")
        value_json = json.loads(value)
        logging.debug(value_json)

        return value_json['snr']

    def _getConfig(self):
        config = configparser.ConfigParser()
        config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
        return config

    def _getSignOfLifeInterval(self):
        config = self._getConfig()
        value = config['DEFAULT']['SignOfLifeLog']

        if not value:
            value = 0

        return int(value)

    def _getLoxonePosition(self):
        config = self._getConfig()
        value = config['DEFAULT']['Position']

        if not value:
            value = 0

        return int(value)

    def _getLoxoneData(self, uuid):
        if not uuid:
            return 0

        config = self._getConfig()
        url = "http://" + config['MS']['HOST'] + "/jdev/sps/io/" + uuid
        payload = {}
        sample_string_bytes = (config['MS']['Username'] + ':' + config['MS']['Password']).encode("ascii")
        base64_bytes = base64.b64encode(sample_string_bytes)
        base64_string = base64_bytes.decode("ascii")
        headers = {
            'Authorization': 'Basic ' + base64_string
        }
        meter_r = requests.request("GET", url, headers=headers, data=payload)

        # check for response
        if not meter_r:
            raise ConnectionError("No response from Loxone - %s" % (url))

        meter_data = meter_r.json()

        # check for Json
        if not meter_data:
            raise ValueError("Converting response to JSON failed")

        return float(meter_data['LL']['value'])*float(config['MS']['Power_Multiplicator'])

    def _signOfLife(self):
        logging.info("--- Start: sign of life ---")
        logging.info("Last _update() call: %s" % (self._lastUpdate))
        logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
        logging.info("--- End: sign of life ---")
        return True

    def _update(self):
        try:
            config = self._getConfig()
            # get data from Loxone
            l1_V = self._getLoxoneData(config['MS']['L1_V_UUID'])
            l1_P = self._getLoxoneData(config['MS']['L1_P_UUID'])
            l1_I = self._getLoxoneData(config['MS']['L1_I_UUID'])
            l1_Mrd = self._getLoxoneData(config['MS']['L1_Mrd_UUID'])
            l1_Mrc = self._getLoxoneData(config['MS']['L1_Mrc_UUID'])

            l2_V = self._getLoxoneData(config['MS']['L2_V_UUID'])
            l2_P = self._getLoxoneData(config['MS']['L2_P_UUID'])
            l2_I = self._getLoxoneData(config['MS']['L2_I_UUID'])
            l2_Mrd = self._getLoxoneData(config['MS']['L2_Mrd_UUID'])
            l2_Mrc = self._getLoxoneData(config['MS']['L2_Mrc_UUID'])

            l3_V = self._getLoxoneData(config['MS']['L3_V_UUID'])
            l3_P = self._getLoxoneData(config['MS']['L3_P_UUID'])
            l3_I = self._getLoxoneData(config['MS']['L3_I_UUID'])
            l3_Mrd = self._getLoxoneData(config['MS']['L3_Mrd_UUID'])
            l3_Mrc = self._getLoxoneData(config['MS']['L3_Mrc_UUID'])

            # send data to DBus
            self._dbusservice['/Ac/Power'] = l1_P+l2_P+l3_P
            self._dbusservice['/Ac/L1/Voltage'] = l1_V
            self._dbusservice['/Ac/L2/Voltage'] = l2_V
            self._dbusservice['/Ac/L3/Voltage'] = l3_V
            self._dbusservice['/Ac/L1/Current'] = l1_I
            self._dbusservice['/Ac/L2/Current'] = l2_I
            self._dbusservice['/Ac/L3/Current'] = l3_I
            self._dbusservice['/Ac/L1/Power'] = l1_P
            self._dbusservice['/Ac/L2/Power'] = l2_P
            self._dbusservice['/Ac/L3/Power'] = l3_P
            self._dbusservice['/Ac/L1/Energy/Forward'] = l1_Mrc
            self._dbusservice['/Ac/L2/Energy/Forward'] = l2_Mrc
            self._dbusservice['/Ac/L3/Energy/Forward'] = l3_Mrc
            self._dbusservice['/Ac/L1/Energy/Reverse'] = l1_Mrd
            self._dbusservice['/Ac/L2/Energy/Reverse'] = l2_Mrd
            self._dbusservice['/Ac/L3/Energy/Reverse'] = l3_Mrd

            # self._dbusservice['/Ac/Energy/Forward'] = meter_data['LL']['value']*1000
            # self._dbusservice['/Ac/Energy/Reverse'] = self._dbusservice['/Ac/L1/Energy/Reverse'] + self._dbusservice['/Ac/L2/Energy/Reverse'] + self._dbusservice['/Ac/L3/Energy/Reverse']

            # New Version - from xris99
            # Calc = 60min * 60 sec / 0.500 (refresh interval of 500ms) * 1000
            updateInterval = (float(config['DEFAULT']['UpdateInterval'])/1000)
            if (self._dbusservice['/Ac/Power'] > 0):
                self._dbusservice['/Ac/Energy/Forward'] = self._dbusservice['/Ac/Energy/Forward'] + (
                            self._dbusservice['/Ac/Power'] / (60 * 60 / updateInterval * 1000))
            if (self._dbusservice['/Ac/Power'] < 0):
                self._dbusservice['/Ac/Energy/Reverse'] = self._dbusservice['/Ac/Energy/Reverse'] + (
                            self._dbusservice['/Ac/Power'] * -1 / (60 * 60 / updateInterval * 1000))

            # logging
            logging.debug("House Consumption (/Ac/Power): %s" % (self._dbusservice['/Ac/Power']))
            logging.debug("House Forward (/Ac/Energy/Forward): %s" % (self._dbusservice['/Ac/Energy/Forward']))
            logging.debug("House Reverse (/Ac/Energy/Revers): %s" % (self._dbusservice['/Ac/Energy/Reverse']))
            logging.debug("---");

            # increment UpdateIndex - to show that new data is available an wrap
            self._dbusservice['/UpdateIndex'] = (self._dbusservice['/UpdateIndex'] + 1) % 256

            # update lastupdate vars
            self._lastUpdate = time.time()
        except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionError) as e:
            logging.critical(
                'Error getting data from Loxone - check network or Loxone status. Setting power values to 0. Details: %s',
                e, exc_info=e)
            self._dbusservice['/Ac/Power'] = 0
            self._dbusservice['/UpdateIndex'] = (self._dbusservice['/UpdateIndex'] + 1) % 256
        except Exception as e:
            logging.critical('Error at %s', '_update', exc_info=e)

        # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True  # accept the change


def getLogLevel():
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    logLevelString = config['DEFAULT']['LogLevel']

    if logLevelString:
        level = logging.getLevelName(logLevelString)
    else:
        level = logging.INFO

    return level


def main():
    # configure logging
    logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=getLogLevel(),
                        handlers=[
                            logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                            logging.StreamHandler()
                        ])

    try:
        logging.info("Start");

        from dbus.mainloop.glib import DBusGMainLoop
        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        # formatting
        _kwh = lambda p, v: (str(round(v, 2)) + ' kWh')
        _a = lambda p, v: (str(round(v, 1)) + ' A')
        _w = lambda p, v: (str(round(v, 1)) + ' W')
        _v = lambda p, v: (str(round(v, 1)) + ' V')

        # start our main-service
        pvac_output = DbusLoxoneService(
            paths={
                '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh},  # energy bought from the grid
                '/Ac/Energy/Reverse': {'initial': 0, 'textformat': _kwh},  # energy sold to the grid
                '/Ac/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L1/Energy/Forward': {'initial': 0, 'textformat': _kwh},
                '/Ac/L2/Energy/Forward': {'initial': 0, 'textformat': _kwh},
                '/Ac/L3/Energy/Forward': {'initial': 0, 'textformat': _kwh},
                '/Ac/L1/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
                '/Ac/L2/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
                '/Ac/L3/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
            })

        logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
        mainloop = gobject.MainLoop()
        mainloop.run()
    except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logging.critical('Error in main type %s', str(e))
    except Exception as e:
        logging.critical('Error at %s', 'main', exc_info=e)


if __name__ == "__main__":
    main()
