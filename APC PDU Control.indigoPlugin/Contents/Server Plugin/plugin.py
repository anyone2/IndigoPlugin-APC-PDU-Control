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

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

################################################################################
class Plugin(indigo.PluginBase):
    ########################################
    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)
        # self.debug = True
        self.debug = plugin_prefs.get("showDebugInfo", False)

    ########################################
    def startup(self):
        self.debugLog(u"startup called")
        self.versionCheck()

        # define the MIB file
        self.the_mib_file = "PowerNet-MIB.txt"


    def shutdown(self):
        self.logger.debug("shutdown called")

    # wasn't in the new but brought over
    def stopConcurrentThread(self):
        self.stopThread = True


    ########################################
    def versionCheck(self):
        self.debugLog(u"versionCheck() called")


    ########################################
    def deviceStartComm(self, dev):
        self.debugLog("Starting device: {0}".format(dev.name))

        # get IP, community name and outlet from props & add to opener
        community = dev.pluginProps["community"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        outlet = dev.pluginProps["outlet"]

        self.debugLog("Community Name: {0}".format(community))
        self.debugLog("IP address: {0}".format(pduIpAddr))
        self.debugLog("Outlet: {0}".format(outlet))

        # get the state of the outlets
        self.readAndUpdateState(dev)


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
            return True

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
            self.setPDUState(dev, "off")

        # TOGGLE ######
        elif action.deviceAction == indigo.kDimmerRelayAction.Toggle:
            newOnState = not dev.onState
            if newOnState:
                # Device is currently off, so turn it on
                self.setPDUState(dev, "on")
            else:
                # Device is currently on, so turn it off
                self.setPDUState(dev, "off")

        # STATUS REQUEST ######
        elif action.deviceAction == indigo.kDeviceGeneralAction.RequestStatus:
            self.readAndUpdateState(dev)

    ########################################
    def setPDUDelays(self, dev):

        # get IP, community name & outlet from props
        outlet = dev.pluginProps["outlet"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        community = dev.pluginProps["community"]

        # cycle thru delays settings
        for d in ["sPDUOutletPowerOnTime", "sPDUOutletPowerOffTime", "sPDUOutletRebootDuration"]:


            # if using the settings on the PDU
            if dev.pluginProps[d] == "Not configured":

                # skip all of this
                self.debugLog(f"Using PDUs configuration for: {d}")

            else:  # configure the delays on the PDU

                # determine where the plugin is running
                # use that to find the full path to the MIB file
                the_path = "'{0}/{1}'".format(os.getcwd(), self.the_mib_file)

                # put together the snmpwalk command to determine device status
                template = "snmpset -t 2 -m {0} -v 1 -c {1} {2} {3}.{4} i {5}"
                the_command = template.format(the_path, community,
                                              pduIpAddr, d, outlet, dev.pluginProps[d])

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

                    self.debugLog(f'send successful for "{dev.name} and delay "{d}"')


                else:

                    indigo.server.log(f'send failed "{dev.name}" unable to set delay for {d}', isError=True)

        else:  # at end of for loop

            sPDUOutletPowerOnTime = dev.pluginProps["sPDUOutletPowerOnTime"]
            sPDUOutletPowerOffTime = dev.pluginProps["sPDUOutletPowerOffTime"]
            sPDUOutletRebootDuration = dev.pluginProps["sPDUOutletRebootDuration"]

            self.debugLog("sPDUOutletPowerOnTime: {0}".format(sPDUOutletPowerOnTime))
            self.debugLog("sPDUOutletPowerOffTime: {0}".format(sPDUOutletPowerOffTime))
            self.debugLog("sPDUOutletRebootDuration: {0}".format(sPDUOutletRebootDuration))


            dev.updateStateOnServer("sPDUOutletPowerOnTime", sPDUOutletPowerOnTime)
            dev.updateStateOnServer("sPDUOutletPowerOffTime", sPDUOutletPowerOffTime)
            dev.updateStateOnServer("sPDUOutletRebootDuration", sPDUOutletRebootDuration)


    ########################################
    def getPDUDelays(self, dev):

        # my thought is to simply get the device settings and update them.

        self.debugLog("getPDUDelays")


    ########################################
    def setPDUState(self, dev, state):

        # get IP, community name & outlet from props
        outlet = dev.pluginProps["outlet"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        community = dev.pluginProps["community"]
        swapRebootForOff = dev.pluginProps["swapRebootForOff"]
        PowerOnTime = dev.pluginProps["sPDUOutletPowerOnTime"]
        PowerOffTime = dev.pluginProps["sPDUOutletPowerOffTime"]
        RebootDuration = dev.pluginProps["sPDUOutletRebootDuration"]

        # if user configured device's Off to be Reboot
        if swapRebootForOff and state == "off":
            state = "outletReboot"

        # send command to PDU to change state of an outlet
        # FYI: "4" is an error condition.

        # validate inputs
        if state == "on":
            theStateCode = " i 1"
            OnOffState = True

        elif state == "off":
            theStateCode = " i 2"
            OnOffState = False

        elif state == "outletReboot":
            theStateCode = " i 3"
            OnOffState = True

        elif state == "outletOnWithDelay":
            theStateCode = " i 5"
            OnOffState = True

        elif state == "outletOffWithDelay":
            theStateCode = " i 6"
            OnOffState = False

        elif state == "outletRebootWithDelay":
            theStateCode = " i 7"
            OnOffState = True


        else:
            self.errorLog(u"Error: State is not configured for use")
            return(False)

        # determine where the plugin is running
        # use that to find the full path to the MIB file
        the_path = "'{0}/{1}'".format(os.getcwd(), self.the_mib_file)

        # put together the snmpwalk command to determine device status
        template = "snmpset -t 2 -m {0} -v 1 -c {1} {2} sPDUOutletCtl.{3}{4}"
        the_command = template.format(the_path, community,
                                      pduIpAddr, outlet, theStateCode)

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

            dev.updateStateOnServer("onOffState", OnOffState)
            if state in ['on', 'off']:
                indigo.server.log(f'Turned "{dev.name}" {state}')
            elif state == 'outletReboot':
                indigo.server.log(f'Rebooting "{dev.name}" immediately')                
            elif state == 'outletOffWithDelay':
                indigo.server.log(f'Turning off "{dev.name}" after a {PowerOffTime} second delay')
            elif state == 'outletOnWithDelay':
                indigo.server.log(f'Turning on "{dev.name}" after a {PowerOnTime} second  delay')
            elif state == 'outletRebootWithDelay':
                indigo.server.log(f'Rebooting "{dev.name}" after a {RebootDuration} second delay')

            else:
                indigo.server.log(f"Undefined state encountered: {state}")

        else:
            the_template = u'send "%s" %s failed'
            indigo.server.log(the_template % (dev.name, state), isError=True)

    ########################################
    def getPDUState(self, dev):
        # request state of PDU
        # returns state of all outlets in a single string

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

                #
                self.debugLog("outlet_list: {0}".format(len(outlet_list)))
                if len(outlet_list) < int(outlet):
                    # self.debugLog("len(outlet_list) {0} > (int(outlet)) {1}".format(len(outlet_list), int(outlet)))
                    result_code = 2
                elif outlet_list[int(outlet) - 1] == "Off":
                    result_code = 0
                elif outlet_list[int(outlet) - 1] == "On":
                    result_code = 1
                else:
                    result_code = 2

                # since successful, exit loop
                break

        else:  # loop has exhausted iterating the list.

            # set result code to Unknown
            result_code = 2

        # everything worked - return resultCode = 2 if not
        self.debugLog(u"Result Code: {0}".format(result_code))

        return result_code

    ########################################
    def readAndUpdateState(self, dev):

        # request state from the PDU & update state variable accordingly
        result_code = self.getPDUState(dev)

        # also do if 0 or 1
        if result_code == 2:

            self.errorLog(u'Error: Device "%s" in unknown state' % dev.name)
            return False

        else:


            self.setPDUDelays(dev)

            swapRebootForOff = dev.pluginProps["swapRebootForOff"]
            self.debugLog("swapRebootForOff: {0}".format(swapRebootForOff))
            dev.updateStateOnServer("swapRebootForOff", swapRebootForOff)

            swapRebootForOff = dev.pluginProps["swapRebootForOff"]
            sPDUOutletPowerOnTime = dev.pluginProps["sPDUOutletPowerOnTime"]
            sPDUOutletPowerOffTime = dev.pluginProps["sPDUOutletPowerOffTime"]
            sPDUOutletRebootDuration = dev.pluginProps["sPDUOutletRebootDuration"]

            self.debugLog("swapRebootForOff: {0}".format(swapRebootForOff))
            self.debugLog("sPDUOutletPowerOnTime: {0}".format(sPDUOutletPowerOnTime))
            self.debugLog("sPDUOutletPowerOffTime: {0}".format(sPDUOutletPowerOffTime))
            self.debugLog("sPDUOutletRebootDuration: {0}".format(sPDUOutletRebootDuration))


            dev.updateStateOnServer("swapRebootForOff", swapRebootForOff)
            dev.updateStateOnServer("sPDUOutletPowerOnTime", sPDUOutletPowerOnTime)
            dev.updateStateOnServer("sPDUOutletPowerOffTime", sPDUOutletPowerOffTime)
            dev.updateStateOnServer("sPDUOutletRebootDuration", sPDUOutletRebootDuration)

            if result_code == 0:
                dev.updateStateOnServer("onOffState", False)
                indigo.server.log(u'Device "%s" is off' % (dev.name))
                return True
            elif result_code == 1:
                dev.updateStateOnServer("onOffState", True)
                indigo.server.log(u'Device "%s" is on' % dev.name)
                return True


    ########################################
    # Custom Plugin Action callbacks (defined in Actions.xml)
    ######################

    def outletOnImmediately(self, plugin_action, dev):
        self.setPDUState(dev, "on")

    def outletOnWithDelay(self, plugin_action, dev):
        self.setPDUState(dev, "outletOnWithDelay")

    def outletOffImmediately(self, plugin_action, dev):
        self.setPDUState(dev, "off")

    def outletOffWithDelay(self, plugin_action, dev):
        self.setPDUState(dev, "outletOffWithDelay")

    def outletReboot(self, plugin_action, dev):
        self.setPDUState(dev, "outletReboot")

    def outletRebootWithDelay(self, plugin_action, dev):
        self.setPDUState(dev, "outletRebootWithDelay")

