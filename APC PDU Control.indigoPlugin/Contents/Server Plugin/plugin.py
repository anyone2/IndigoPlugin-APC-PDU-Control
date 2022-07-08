#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import os
import sys
import time
import socket
import urllib
import subprocess
import urllib.error


################################################################################
class Plugin(indigo.PluginBase):
    ########################################
    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)
        self.debug = plugin_prefs.get("showDebugInfo", False)

    ########################################
    def startup(self):
        self.debugLog(u"startup called")

        # define the MIB file
        self.the_mib_file = "PowerNet-MIB.txt"


    def shutdown(self):
        self.logger.debug("shutdown called")


    ########################################
    def deviceStartComm(self, dev):
        self.debugLog("deviceStartComm called")

        # get IP, community name and outlet from props & add to opener
        community = dev.pluginProps["community"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        outlet = dev.pluginProps["outlet"]

        self.debugLog("Device: {0}".format(dev.name))
        self.debugLog("Community Name: {0}".format(community))
        self.debugLog("IP address: {0}".format(pduIpAddr))
        self.debugLog("Outlet: {0}".format(outlet))

        # get the state of the outlets
        self.getPDUState(dev)

        # set the PDU delays configured in the Plugin
        self.setPDUDelays(dev)

        # get the delays configured on each outlet on the PDU
        self.getPDUDelays(dev)


    ########################################

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        # validate supplied values
        outletNum = int(valuesDict["outlet"])
        if outletNum < 1 or outletNum > 16:
            template = u'Error: Outlet "{0}" must be between 1 & 16'
            self.errorLog(template.format(outletNum))
            errorDict = indigo.Dict()
            errorDict["outlet"] = ("The value of this field must "
                                   "be between 1 & 16")
            return False, valuesDict, errorDict

        else:

            addr = valuesDict["ipAddr"]

            try:

                # test for valid IP Address
                socket.inet_aton(addr)
                return True

            except socket.error:
                # the IP Address is Invalid
                self.errorLog(f'Error: IP Address "{addr}" is invalid')
                errorDict = indigo.Dict()
                errorDict["ipAddr"] = ("The value of this field must "
                                       "be a valid IP address")
                return False, valuesDict, errorDict


    ###################################################

    def shellCommand(self, the_command, shellValue):
        proc = subprocess.Popen(the_command,
                                shell=shellValue,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, )
        stdout_value, stderr_value = proc.communicate()
        return stdout_value, stderr_value


    ########################################
    # Relay / Dimmer Action callback
    ########################################

    def actionControlDimmerRelay(self, action, dev):

        # TURN ON ######
        if action.deviceAction == indigo.kDimmerRelayAction.TurnOn:
            self.setPDUState(dev, "on")

        # TURN OFF ######
        elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
            if dev.pluginProps["UseOffAsReboot"]:
                self.setPDUState(dev, "outletReboot")
            else:
                self.setPDUState(dev, "off")

        # TOGGLE ######
        elif action.deviceAction == indigo.kDimmerRelayAction.Toggle:
            
            # If device is currently on, turn it off
            if dev.onState:
                # if 'Use Off as Reboot' checked in Configuration
                if dev.pluginProps["UseOffAsReboot"]:
                    # reboot the outlet
                    self.setPDUState(dev, "outletReboot")
                else:
                    # turn the device off
                    self.setPDUState(dev, "off")
            else:
                # Device is currently off, so turn it on
                self.setPDUState(dev, "on")

        # STATUS REQUEST ######
        elif action.deviceAction == indigo.kDeviceGeneralAction.RequestStatus:

            # get the state configured on the PDU
            self.getPDUState(dev)

            # get the three(3) delays on the PDU
            self.getPDUDelays(dev)


    ########################################
    def setPDUDelays(self, dev):
        self.debugLog("setPDUDelays called")
        
        # get IP, community name & outlet from props
        outlet = dev.pluginProps["outlet"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        community = dev.pluginProps["community"]

        # cycle thru delays settings
        for delay_name in ["OutletPowerOnTime", 
                           "OutletPowerOffTime", 
                           "OutletRebootDuration"]:

            # if using the settings on the PDU
            if dev.pluginProps[delay_name] == "Not configured":

                # skip all of this
                self.debugLog(f"Using PDUs {delay_name} delay for: outlet: {outlet}")

            else:  # configure the delays on the PDU

                # determine where the plugin is running
                # use that to find the full path to the MIB file
                the_path = "'{0}/{1}'".format(os.getcwd(), self.the_mib_file)

                # put together the snmpwalk command to determine device status
                template = "snmpset -t 2 -m {0} -v 1 -c {1} {2} sPDU{3}.{4} i {5}"
                the_command = template.format(the_path, 
                                              community,
                                              pduIpAddr, 
                                              delay_name, 
                                              outlet, 
                                              dev.pluginProps[delay_name])

                '''
                snmpset -t 2 s-m PowerNet-MIB -v 1 -c private -v 1 192.168.0.232 sPDUOutletPowerOnTime.5 i 15
                
                The full path the the MIB file is required
                '''
                
                # Try a max of three (3) times
                # pausing for 2 seconds between attempts
                for r in range(1, 4):

                    stdout_value, stderr_value = self.shellCommand(the_command, True)

                    self.debugLog(u"Sending to PDU: {0}".format(the_command))
                    self.debugLog(u"stdout value: {0}".format(stdout_value))

                    if stderr_value:
                        # some type of error
                        self.debugLog(u"Failed to send to PDU")
                        self.debugLog(u"stderr value: {0}".format(stderr_value))
                        Successful = False
                        time.sleep(2)
                    else:
                        # everything worked
                        self.debugLog(u"Sent to PDU")
                        Successful = True
                        break

                # everything worked return True, else return False
                if Successful:

                    self.debugLog(f'send successful for "{dev.name} '
                                   'and delay "{delay_name}"')


                else:

                    indigo.server.log(f'send failed "{dev.name}" '
                                       'unable to set delay for {d}', 
                                       isError=True)

        else:  # at end of for loop

            OutletPowerOnTime = dev.pluginProps["OutletPowerOnTime"]
            OutletPowerOffTime = dev.pluginProps["OutletPowerOffTime"]
            OutletRebootDuration = dev.pluginProps["OutletRebootDuration"]

            dev.updateStateOnServer("OutletPowerOnTime", OutletPowerOnTime)
            dev.updateStateOnServer("OutletPowerOffTime", OutletPowerOffTime)
            dev.updateStateOnServer("OutletRebootDuration", OutletRebootDuration)


    ########################################
    # request the PDU On, Off and reboot delays
    def getPDUDelays(self, dev):
        self.debugLog("getPDUDelays called")

        # get IP, community name & outlet from props
        outlet = dev.pluginProps["outlet"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        community = dev.pluginProps["community"]

        # determine where the plugin is running
        # use that to find the full path to the MIB file
        the_path = "'{0}/{1}'".format(os.getcwd(), self.the_mib_file)

        # cycle thru delays settings
        for delay_name in ["OutletPowerOnTime", 
                           "OutletPowerOffTime", 
                           "OutletRebootDuration"]:

            # put together the snmpwalk command to determine device status
            template = "snmpwalk -t 2 -m {0} -v 1 -c {1} {2} sPDU{3}.{4}"
            the_command = template.format(the_path, community, 
                                          pduIpAddr, delay_name, outlet)

            # try to do this a max of three (3) times
            # pausing 5 seconds between unsuccessful attempts
            for r in range(1, 4):

                # Execute command and capture the output
                stdout_value, stderr_value = self.shellCommand(the_command, True)

                if stderr_value:

                    # display error message
                    template = u"Error: Retrying connection to Device {0}"
                    self.debugLog(template.format(dev.name))

                    # if debuging is enabled, report the error
                    self.debugLog(u"Error: {0}".format(stderr_value))

                    # pause for 5 seconds
                    time.sleep(5)

                else:

                    if stdout_value:

                        # get the last time which is the configured delay 
                        the_delay = int(stdout_value.split()[-1])

                        # update delay on server
                        dev.updateStateOnServer(delay_name, the_delay)
                        self.debugLog('{0}-{1} is configured with a "{2}" delay '
                                      'of {3} seconds'.format(outlet, 
                                                              dev.name, 
                                                              delay_name, 
                                                              the_delay))

                        # since successful, exit loop
                        break

                    else:  # likely a non-existing port

                        dev.updateStateOnServer(delay_name, 'unknown')
                        indigo.server.log('{0}-{1} has an issue, the "{2}" delay '
                                          'is "Unknown"'.format(outlet, 
                                                                dev.name, 
                                                                delay_name),
                                          isError=True)
                        break

            else:  # loop has exhausted iterating the list.

                # set delay Unknown
                dev.updateStateOnServer(delay_name, 'unknown')
                indigo.server.log('{0}-{1} has an issue, the "{2}" delay '
                                  'is "Unknown"'.format(outlet, 
                                                        dev.name, 
                                                        delay_name),
                                  isError=True)


    ########################################
    def setPDUState(self, dev, state):
        self.debugLog("setPDUState called")

        # get IP, community name & outlet from props
        outlet = dev.pluginProps["outlet"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        community = dev.pluginProps["community"]
        UseOffAsReboot = dev.pluginProps["UseOffAsReboot"]
        PowerOnTime = dev.pluginProps["OutletPowerOnTime"]
        PowerOffTime = dev.pluginProps["OutletPowerOffTime"]
        RebootDuration = dev.pluginProps["OutletRebootDuration"]

        # send command to PDU to change state of an outlet
        # FYI: "4" is an error condition.

        pdu_action = {
                      'on': {'theStateCode': " i 1", 
                             "OnOffState": True},
                      'off': {'theStateCode': " i 2", 
                              "OnOffState": False},
                      'outletReboot': {'theStateCode': " i 3", 
                                       "OnOffState": True},
                      'outletOnWithDelay': {'theStateCode': " i 5", 
                                            "OnOffState": True},
                      'outletOffWithDelay': {'theStateCode': " i 6", 
                                             "OnOffState": False},
                      'outletRebootWithDelay': {'theStateCode': " i 7", 
                                                "OnOffState": True},
                      'outletOffImmediately': {'theStateCode': " i 2", 
                                               "OnOffState": False},
                     }

        # if known state
        if pdu_action.get(state):

            # determine where the plugin is running
            # use that to find the full path to the MIB file
            the_path = "'{0}/{1}'".format(os.getcwd(), self.the_mib_file)

            # put together the snmpwalk command to determine device status
            template = "snmpset -t 2 -m {0} -v 1 -c {1} {2} sPDUOutletCtl.{3}{4}"
            the_command = template.format(the_path, community,
                                          pduIpAddr, outlet, 
                                          pdu_action[state]['theStateCode'])

            '''
            snmpset -t 2 s-m PowerNet-MIB -v 1 -c private -v 1 192.168.0.232 sPDUOutletCtl.5 i 1
            
            The full path the the MIB file is required
            '''

            # Try a max of three (3) times
            # pausing for 5 seconds between attempts
            for r in range(1, 4):

                stdout_value, stderr_value = self.shellCommand(the_command, True)

                self.debugLog(u"Sending to PDU: {0}".format(the_command))
                self.debugLog(u"stdout value: {0}".format(stdout_value))

                if stderr_value:
                    # some type of error
                    self.debugLog(u"Failed to send to PDU")
                    self.debugLog(u"stderr value: {0}".format(stderr_value))
                    Successful = False
                    time.sleep(5)
                else:
                    # everything worked
                    self.debugLog(u"Sent to PDU")
                    Successful = True
                    break

            # everything worked return True, else return False
            if Successful:

                dev.updateStateOnServer("onOffState", 
                                        pdu_action[state]['OnOffState'])

                if state in ['on', 'off']:
                    indigo.server.log(f'Turned "{dev.name}" {state}')
                elif state == 'outletOffImmediately':
                    indigo.server.log(f'Turned "{dev.name}" off immediately')
                elif state == 'outletReboot':
                    indigo.server.log(f'Rebooted "{dev.name}"')                
                elif state == 'outletOffWithDelay':
                    indigo.server.log(f'Turning off "{dev.name}" '
                                      f'after a {PowerOffTime} second delay')
                elif state == 'outletOnWithDelay':
                    indigo.server.log(f'Turning on "{dev.name}" '
                                      f'after a {PowerOnTime} second  delay')
                elif state == 'outletRebootWithDelay':
                    indigo.server.log(f'Rebooting "{dev.name}" '
                                      f'after a {RebootDuration} second delay')

                else:  # not sure you'd ever get here
                    indigo.server.log(f"Undefined state encountered: {state}")

            else:  # when unsuccessful

                indigo.server.log(f'send "{dev.name}" {state} failed', 
                                  isError=True)

        else:
            self.errorLog(u"Error: State is not configured for use")
            return(False)


    ########################################
    def getPDUState(self, dev):
        self.debugLog("getPDUState called")

        # get IP, community name & outlet from props
        outlet = dev.pluginProps["outlet"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        community = dev.pluginProps["community"]

        # determine where the plugin is running
        # use that to find the full path to the MIB file
        the_path = "'{0}/{1}'".format(os.getcwd(), self.the_mib_file)

        # put together the snmpwalk command to determine device status
        template = "snmpwalk -t 2 -m {0} -v 1 -c {1} {2} sPDUMasterState"
        the_command = template.format(the_path, community, pduIpAddr)

        # try to do this a max of three (3) times
        # pausing 5 seconds between unsuccessful attempts
        for r in range(1, 4):

            # Execute command and capture the output
            stdout_value, stderr_value = self.shellCommand(the_command, True)

            if stderr_value:

                # display error message
                template = u"Error: Retrying connection to Device {0}"
                self.debugLog(template.format(dev.name))

                # if debuging is enabled, report the error
                self.debugLog(u"Error: {0}".format(stderr_value))

                # pause for 5 seconds
                time.sleep(5)

            else:

                # create list of Off/On states returned
                # stdout_value is PowerNet-MIB::sPDUMasterState.0 = STRING: "Off Off Off Off Off Off Off Off "
                outlet_list = str(stdout_value[43:-2]).split()
                self.debugLog("outlet_list: {0}".format(outlet_list))
                self.debugLog("outlet: {0}".format(outlet))

                # is outlet number higher than what is available on PDU
                if len(outlet_list) < int(outlet):

                    # the PDU returned fewer outlets than the one requested
                    self.errorLog(f'Error: "{dev.name}" might be misconfigured, '
                                   'check the outlet number')

                elif outlet_list[int(outlet) - 1] == "Off":
                    
                    # Outlet is OFF, update server and display to log
                    dev.updateStateOnServer("onOffState", False)
                    indigo.server.log(f'Device "{dev.name}" is off')
                
                elif outlet_list[int(outlet) - 1] == "On":
                
                    # Outlet is ON, update server and display to log
                    dev.updateStateOnServer("onOffState", True)
                    indigo.server.log(f'Device "{dev.name}" is on')

                else:  # unknown value encountered

                    # some error occured
                    self.errorLog(f'Error: Device "{dev.name}" in unknown state')

                # since successful, exit loop
                break

        else:  # loop has exhausted iterating the list.

            # some error occured
            self.errorLog(f'Error: Device "{dev.name}" in unknown state')


    ########################################
    # Custom Plugin Action callbacks (defined in Actions.xml)
    ######################

    def outletOnImmediately(self, plugin_action, dev):
        self.setPDUState(dev, "on")

    def outletOnWithDelay(self, plugin_action, dev):
        self.setPDUState(dev, "outletOnWithDelay")

    def outletOffImmediately(self, plugin_action, dev):
        self.setPDUState(dev, "outletOffImmediately")

    def outletOffWithDelay(self, plugin_action, dev):
        self.setPDUState(dev, "outletOffWithDelay")

    def outletReboot(self, plugin_action, dev):
        self.setPDUState(dev, "outletReboot")

    def outletRebootWithDelay(self, plugin_action, dev):
        self.setPDUState(dev, "outletRebootWithDelay")
