# APC PDU Control

This plugin for the [Indigo Domotics](http://www.indigodomo.com/) home automation platform that allows communication with a APC Power Distribution Unit (PDU) via Simple Network Management Protocol (SNMP)

This plugin has the ability to controls the On/Off/Reboot function of outlets on APC's MasterSwitch PDUs

Supported Operations

* Turn on
* Turn off
* Reboot
* Status Request
* Delayed Turn On
* Delayed Turn Off
* Delayed Reboot

You can also configured the On/Off/Reboot delays from the Plugin and the delay values configured on the PDU as Custom States.


## To-Do

The Plugin uses the snmpwalk and snmpset the comes installed on Macs. This plugin would benefit from incorporating the pysnmp module in a future release.