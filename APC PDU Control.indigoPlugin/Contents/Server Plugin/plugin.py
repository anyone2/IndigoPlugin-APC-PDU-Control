#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import os
import indigo
import socket
import subprocess


########################################
class Plugin(indigo.PluginBase):
    
    def __init__(self, plugin_id, plugin_display_name, 
                 plugin_version, plugin_prefs):
        super().__init__(plugin_id, plugin_display_name, 
                         plugin_version, plugin_prefs)
        self.debug = plugin_prefs.get("showDebugInfo", False)

    ########################################
    def startup(self):
        self.debugLog(u"startup called")

        # determine where the plugin is running and path to MIB
        self.the_path = f"'{os.getcwd()}/PowerNet-MIB.txt'"

    def shutdown(self):
        self.logger.debug("shutdown called")

    ########################################
    def deviceStartComm(self, dev):
        self.debugLog("deviceStartComm called")

        # get IP, community name and outlet from props & add to opener
        community = dev.pluginProps["community"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        outlet = dev.pluginProps["outlet"]

        self.debugLog(f"Device: {dev.name}")
        self.debugLog(f"Community Name: {community}")
        self.debugLog(f"IP address: {pduIpAddr}")
        self.debugLog(f"Outlet: {outlet}")

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
            self.errorLog(f'Outlet "{outletNum}" must be between 1 & 16')
            errorDict = indigo.Dict()
            errorDict["outlet"] = ("The value of this field must "
                                   "be between 1 & 16")
            return False, valuesDict, errorDict

        else:

            try:

                # test for a valid IP Address
                addr = valuesDict["ipAddr"]
                socket.inet_aton(addr)
                return True

            except socket.error:  # invalid IP address

                self.errorLog(f'Error: IP Address "{addr}" is invalid')
                errorDict = indigo.Dict()
                errorDict["ipAddr"] = ("The value of this field must "
                                       "be a valid IP address")
                return False, valuesDict, errorDict

    ###################################################
    def shellCommand(self, the_command, shell_value):
        proc = subprocess.Popen(the_command,
                                shell=shell_value,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, 
                                encoding="utf-8")
        stdout_value, stderr_value = proc.communicate()
        return stdout_value.strip(), stderr_value

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

        # get and update the 'Use Off As Reboot' selection True/False
        UseOffAsReboot = dev.pluginProps["UseOffAsReboot"]
        dev.updateStateOnServer("UseOffAsReboot", f"{UseOffAsReboot}")
        
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

                # Do not set any delays
                self.debugLog(f'Using "{delay_name}" delay for '
                              f'{dev.name} {outlet}')

            else:  # configure the delays on the PDU

                # put together the snmpset command to set device parameters
                snmpset = "snmpset -t 2 -m {0} -v 1 -c {1} {2} sPDU{3}.{4} i {5}"
                the_command = snmpset.format(self.the_path, 
                                             community,
                                             pduIpAddr, 
                                             delay_name, 
                                             outlet, 
                                             dev.pluginProps[delay_name])

                ''' # noqa
                snmpset -t 2 s-m PowerNet-MIB -v 1 -c private -v 1 192.168.0.232 sPDUOutletPowerOnTime.5 i 15
                
                The full path to the MIB file is required
                '''
                
                # Execute command and capture the output
                stdout_value, stderr_value = self.shellCommand(the_command, True)

                self.debugLog(f"Sending to PDU: {the_command}")
                self.debugLog(f"stdout value: {stdout_value}")

                if stderr_value:
                    # some type of error
                    self.debugLog(f"stderr value: {stderr_value}")
                    indigo.server.log(f'send failed "{dev.name}", unable to '
                                      f'set delay for {delay_name}', 
                                      isError=True)

                else:   # no errors
                    
                    if stdout_value:
                        # everything work
                        dev.updateStateOnServer(f"{delay_name}", delay_name)
                        self.debugLog(f'send successful for "{dev.name} '
                                      f'and delay "{delay_name}"')
                    
                    else:  # stdout_value was blank, some error likely occurred

                        indigo.server.log(f'send failed "{dev.name}", unable '
                                          f'to set delay for {delay_name}', 
                                          isError=True)

    ########################################
    def getPDUDelays(self, dev):
        self.debugLog("getPDUDelays called")

        # get IP, community name & outlet from props
        outlet = dev.pluginProps["outlet"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        community = dev.pluginProps["community"]

        # cycle thru delays settings
        for delay_name in ["OutletPowerOnTime", 
                           "OutletPowerOffTime", 
                           "OutletRebootDuration"]:

            # put together the snmpwalk command to determine device status
            snmpwalk = "snmpwalk -t 2 -m {0} -v 1 -c {1} {2} sPDU{3}.{4}"
            the_command = snmpwalk.format(self.the_path, community, 
                                          pduIpAddr, delay_name, outlet)

            # Execute command and capture the output
            stdout_value, stderr_value = self.shellCommand(the_command, True)

            if stderr_value:

                # display error message
                self.errorLog(f"Unable to connect to Device {dev.name}")

                # if debuging is enabled, report the error
                self.debugLog(f"Error: {stderr_value}")

            else:

                if stdout_value:

                    # get the last time which is the configured delay 
                    the_delay = int(stdout_value.split()[-1])

                    # update delay on server
                    dev.updateStateOnServer(delay_name, the_delay)

                    self.debugLog(f'{outlet}-{dev.name} is configured '
                                  f'with a "{delay_name}" delay of '
                                  f'{the_delay} seconds')

                else:  # stdout_value was blank, likely a non-existing port

                    dev.updateStateOnServer(delay_name, 'unknown')
                    indigo.server.log(f'{outlet}-{dev.name} has an issue, '
                                      f'with the "{delay_name}" delay', 
                                      isError=True)

    ########################################
    def setPDUState(self, dev, state):
        self.debugLog("setPDUState called")

        # get IP, community name & outlet from props
        outlet = dev.pluginProps["outlet"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        community = dev.pluginProps["community"]
        # UseOffAsReboot = dev.pluginProps["UseOffAsReboot"]
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

            # put together the snmpset command to set device parameters
            snmpset = "snmpset -t 2 -m {0} -v 1 -c {1} {2} sPDUOutletCtl.{3}{4}"
            the_command = snmpset.format(self.the_path, community,
                                         pduIpAddr, outlet, 
                                         pdu_action[state]['theStateCode'])

            ''' # noqa
            snmpset -t 2 s-m PowerNet-MIB -v 1 -c private -v 1 192.168.0.232 sPDUOutletCtl.5 i 1

            The full path to the MIB file is required            
            '''

            # Execute command and capture the output
            stdout_value, stderr_value = self.shellCommand(the_command, True)

            self.debugLog(f"Sending to PDU: {the_command}")
            self.debugLog(f"stdout value: {stdout_value}")

            if stderr_value:
                # some type of error
                self.debugLog("Failed to send to PDU")
                self.debugLog(f"stderr value: {stderr_value}")
                indigo.server.log(f'send "{dev.name}" {state} failed', 
                                  isError=True)

            else:

                if stdout_value:
                    
                    if state in ['on', 'off']:
                        indigo.server.log(f'Turned "{dev.name}" {state}')
                        dev.updateStateOnServer("onOffState", 
                                                pdu_action[state]
                                                ['OnOffState'])

                    elif state == 'outletOffImmediately':
                        indigo.server.log(f'Turned "{dev.name}" off')
                        dev.updateStateOnServer("onOffState", 'off')
                    elif state == 'outletReboot':
                        indigo.server.log(f'Rebooted "{dev.name}"')                
                        dev.updateStateOnServer("onOffState", 'on')
                    elif state == 'outletOffWithDelay':
                        indigo.server.log(f'Turning off "{dev.name}" after'
                                          f'a {PowerOffTime} second delay')
                        dev.updateStateOnServer("onOffState", 'off')
                    elif state == 'outletOnWithDelay':
                        indigo.server.log(f'Turning on "{dev.name}" after '
                                          f'a {PowerOnTime} second  delay')
                        dev.updateStateOnServer("onOffState", 'on')
                    elif state == 'outletRebootWithDelay':
                        indigo.server.log(f'Rebooting "{dev.name}" after '
                                          f'a {RebootDuration} second delay')
                        dev.updateStateOnServer("onOffState", 'on')

                    else:  # not sure you'd ever get here
                        indigo.server.log(f"Unknown state: {state}")

                else:  # stdout_value was blank

                    self.errorLog("Error: some unknown error occurred")

        else:  # unknown state

            self.errorLog("Error: State is not configured for use")

    ########################################
    def getPDUState(self, dev):
        self.debugLog("getPDUState called")

        # get IP, community name & outlet from props
        outlet = dev.pluginProps["outlet"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        community = dev.pluginProps["community"]

        # put together the snmpwalk command to determine device status
        snmpwalk = "snmpwalk -t 2 -m {0} -v 1 -c {1} {2} sPDUMasterState"
        the_command = snmpwalk.format(self.the_path, community, pduIpAddr)

        # Execute command and capture the output
        stdout_value, stderr_value = self.shellCommand(the_command, True)

        if stderr_value:

            # display error message
            self.errorLog(f"Error: Attempting connection to Device {dev.name}")

            # if debuging is enabled, report the error
            self.debugLog(f"Error: {stderr_value}")

        else:

            if stdout_value:

                ''' # noqa 
                create list of Off/On states returned as 
                PowerNet-MIB::sPDUMasterState.0 = STRING: "Off Off Off Off Off Off Off Off "
                '''
                if len(stdout_value) > 43:
                    outlet_list = str(stdout_value[43:-2]).split()

                    self.debugLog(f"outlet_list: {outlet_list}")
                    self.debugLog(f"outlet: {outlet}")

                    # is outlet number higher than what is available on PDU
                    if len(outlet_list) < int(outlet):

                        # the PDU returned fewer outlets than the one requested
                        self.errorLog(f'"{dev.name}" might be misconfigured, '
                                      f'check the outlet number')

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
                        self.errorLog(f'"{dev.name}" is in an Unknown State')
                        self.debugLog(f"value: {outlet_list[int(outlet) - 1]}")                   
                        self.debugLog(f"stdout_value: {stdout_value}")

                else:  # stdout_value is not long enough to be valid

                    # some error occured
                    self.errorLog(f'"{dev.name}" is in an Unknown State')
                    self.debugLog(f"stdout_value: {stdout_value}")

            else:

                # some error occured
                self.errorLog(f'Error: Device "{dev.name}" in unknown state')

    ########################################
    def setAllState(self, plugin_action, state):
        self.debugLog("setAllState called")

        # get IP & community name from props
        ip_address = plugin_action.props.get("ipAddr")
        community = plugin_action.props.get("community")

        pdu_action = {
                      'AllOnImmediately': {'theStateCode': " i 1", 
                                           "OnOffState": True},
                      'AllOnSequence': {'theStateCode': " i 2", 
                                        "OnOffState": False},
                      'AllOffImmediately': {'theStateCode': " i 3", 
                                            "OnOffState": False},
                      'RebootAllImmediately': {'theStateCode': " i 4", 
                                               "OnOffState": True},
                      'RebootAllSequence': {'theStateCode': " i 5", 
                                            "OnOffState": True},
                      'AllOffSequence': {'theStateCode': " i 7", 
                                         "OnOffState": False},
                     }

        # if known state
        if pdu_action.get(state):

            # put together the snmpset command to set device parameters
            snmpset = (f"snmpset -t 2 -v 1 -c {community} {ip_address} "
                       f"1.3.6.1.4.1.318.1.1.4.2.1.0 "
                       f"{pdu_action[state]['theStateCode']}")

            '''# noqa
            snmpset -t 2 -v 1 -c private -v 1 192.168.0.232 1.3.6.1.4.1.318.1.1.4.2.1.0 i 1
            '''
            # Execute command and capture the output
            stdout_value, stderr_value = self.shellCommand(snmpset, True)

            self.debugLog(f"Sending to PDU: {snmpset}")
            self.debugLog(f"stdout value: {stdout_value}")

            if stderr_value:
                # some type of error
                self.debugLog("Failed to send to PDU")
                self.debugLog(f"stderr value: {stderr_value}")
                indigo.server.log(f'send "All" {state} failed', isError=True)
                self.errorLog(f'"Error:" {stderr_value}')

            else:

                if stdout_value:
                    
                    if state == 'AllOnImmediately':
                        indigo.server.log('Turned "All" On immediately')
                        self.updateAll(community, ip_address, state, 'on')

                    elif state == 'AllOffImmediately':
                        indigo.server.log('Turning "All" Off immediately')
                        self.updateAll(community, ip_address, state, 'off')

                    elif state == 'AllOnSequence':
                        indigo.server.log('Turning "All" On after the '
                                          '"Power On" Delay')
                        self.updateAll(community, ip_address, state, 'on')
                        self.errorLog('The outlet status may become out of '
                                      'sync because of the delay')                        

                    elif state == 'AllOffSequence':
                        indigo.server.log('Turning "All" Off after the '
                                          '"Power Off" Delay') 
                        self.updateAll(community, ip_address, state, 'off')
                        self.errorLog('The status of the outlets may become '
                                      'out of sync because of delays involved')                        

                    elif state == 'RebootAllSequence':
                        indigo.server.log('Rebooting "All" in after the '
                                          'configured delays')
                        self.updateAll(community, ip_address, state, 'on')
                        self.errorLog('The status of the outlets may become '
                                      'out of sync because of delays involved')                        

                    elif state == 'RebootAllImmediately':
                        # need to test if off becomes on when rebooted
                        indigo.server.log('Rebooting "All" immediately')
                        self.updateAll(community, ip_address, state, 'on')

                    else:  # not sure you'd ever get here
                        indigo.server.log("Undefined state: {state}")

                else:  # stdout_value was blank

                    self.errorLog("Error: some unknown error occurred")

        else:  # unknown state

            self.errorLog("Error: State is not configured for use")

    ########################################
    def updateAll(self, community, ip_address, state, on_off):

        # update the states of configured outlets with the same IP & community
        for dev in indigo.devices.iter("self"):
            if dev.configured:
                if (dev.pluginProps["ipAddr"] == ip_address):
                    if (dev.pluginProps["community"] == community):

                        OutletPowerOnTime = dev.states["OutletPowerOnTime"]
                        OutletPowerOffTime = dev.states["OutletPowerOffTime"]

                        if state == "AllOnSequence":
                            dev.updateStateOnServer("onOffState", on_off)
                            indigo.server.log(f'Turning ON "{dev.name}" after '
                                              f'a {OutletPowerOnTime} second '
                                              'delay')

                        elif (state == "RebootAllImmediately") and dev.onState:
                            dev.updateStateOnServer("onOffState", on_off)
                            indigo.server.log(f'Rebooting "{dev.name}", '
                                              f'powering OFF now, power ON '
                                              'after a "configured" delay')

                        elif state == "AllOffSequence":
                            dev.updateStateOnServer("onOffState", on_off)
                            indigo.server.log(f'Turning OFF "{dev.name}" after'
                                              f' a {OutletPowerOffTime} second'
                                              ' delay')

                        elif (state == "RebootAllSequence") and dev.onState:
                            dev.updateStateOnServer("onOffState", on_off)
                            indigo.server.log(f'Rebooting "{dev.name}" with '
                                              f'Off/On Delay of '
                                              f'{OutletPowerOffTime}/'
                                              f'{OutletPowerOnTime} seconds')

    ########################################
    # Menu callbacks defined in MenuItems.xml
    ########################################
    def toggleDebugging(self):
        if self.debug:
            self.logger.info("Turning off debug logging")
            self.pluginPrefs["showDebugInfo"] = False
        else:
            self.logger.info("Turning on debug logging")
            self.pluginPrefs["showDebugInfo"] = True
        self.debug = not self.debug

    ########################################
    # Custom Plugin Action callbacks 
    ########################################
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

    def TurnAllOnImmediately(self, plugin_action, dev):
        self.setAllState(plugin_action, "AllOnImmediately")

    def TurnAllOnSequence(self, plugin_action, dev):
        self.setAllState(plugin_action, "AllOnSequence")

    def TurnAllOffImmediately(self, plugin_action, dev):
        self.setAllState(plugin_action, "AllOffImmediately")

    def RebootAllImmediately(self, plugin_action, dev):
        self.setAllState(plugin_action, "RebootAllImmediately")

    def RebootAllSequence(self, plugin_action, dev):
        self.setAllState(plugin_action, "RebootAllSequence")

    def TurnAllOffSequence(self, plugin_action, dev):
        self.setAllState(plugin_action, "AllOffSequence")
