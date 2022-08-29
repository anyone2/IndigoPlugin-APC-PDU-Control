# APC PDU Control

This plugin for the [Indigo Domotics](http://www.indigodomo.com/) home automation platform allows communication with a APC Power Distribution Unit (PDU) via Simple Network Management Protocol (SNMP)

This plugin has the ability to control the On/Off/Reboot functions of the PDU and should work with any APC MasterSwitch device that supports SNMP.

## Supported Functions

* Turn On
* Turn Off
* Reboot
* Status Request

* Turn All Outlets On
* Turn All Outlets Off
* Reboot All Outlets Immediately

You can also configured the On/Off/Reboot delays from within the Plugin. All delays configured on the PDU, are shown as Custom States. The configured delays effect the behavior of the delayed On/Off/Reboot.

## Configuration of your APC PDU

1) You <b>must</b> configure your APC PDU with appropriate Community Names. 

* Access Type read should be set to '  public  '
* Acces Type Write+ should be set to '  private  '

    Note: Write+ is preferred since it allows someone to be logged into the Web Portal and still allow Indigo to change an outlets state.

## Test Equipment

This plugin was tested and developed on the following APC hardware:

* APC MasterSwitch AP9211 
* APC AP9606 Web/SNMP Management SmartSlot Card
* running APC OS(AOS) v3.0.9.a and Application module v2.2.5.a


## To-Do

The Plugin uses the 'snmpwalk' and 'snmpset' commands that comes preinstalled on Macs. This plugin would benefit from incorporating the Python 'PySNMP' module in a future release. As well, the very first version of this plugin had a work-around to handle SMNP traps received from the APC PDU, adding that back in is a To-Do.
