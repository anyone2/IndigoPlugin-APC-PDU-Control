# APC PDU Control

This plugin for the [Indigo Domotics](http://www.indigodomo.com/) home automation platform allows communication with a APC Power Distribution Unit (PDU) via Simple Network Management Protocol (SNMP)

This plugin has the ability to control the On/Off/Reboot functions of the PDU and should work with any APC MasterSwitch device that supports SNMP.

## Supported Functions

* Turn On
* Turn Off
* Reboot
* Status Request
* Delayed Turn On
* Delayed Turn Off
* Delayed Reboot

You can also configured the On/Off/Reboot delays from the Plugin. All delays configured on the PDU, are shown as Custom States within the plugin.

## Configuration of your APC PDU

1) You <b>must</b> configure your APC PDU with appropriate Community Names. 

* Access Type read should be set to '  public  '
* Acces Type Write+ should be set to '  private  '

    Note: Write+ is preferred since it allows someone to be logged into the Web Portal and still allow Indigo to change an outlets state.


## Test Equipment

This plugin was tested and developed on the following APC hardware:

* APC MasterSwitch AP9211 
* APC AP9606 Web/SNMP Management SmartSlot Card


## To-Do

The Plugin uses the 'snmpwalk' and 'snmpset' commands that comes preinstalled on Macs. This plugin would benefit from incorporating the Python 'PySNMP' module in a future release.
