#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2022, Perceptive Automation, LLC. All rights reserved.
# https://www.indigodomo.com

import indigo

import os
import sys
import time
import socket
import urllib # different, was urllib2
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

        # start snmptrapd if it's enabled
        if self.plugin_prefs["processTraps"]:
            # self.snmptrapdStart()
            self.debugLog(u"commented out: self.snmptrapdStart()")

    def shutdown(self):
        self.logger.debug("shutdown called")

    # wasn't in the new but brought over
    def stopConcurrentThread(self):
        self.stopThread = True
        if self.plugin_prefs["processTraps"]:
            self.snmptrapdKill()

    ########################################
    # again brought over not sure I need this...plus who the hell is 159.122.4.194?
    def versionCheck(self):
        self.debugLog(u"versionCheck() called")
        '''
        # determine address of html document with latest version info
        plugin_name = self.plugin_id.split(".")[2]
        current_version = str(self.pluginVersion)
        the_site = r'http://159.122.4.194/~nick'
        the_url = the_site + "/plugins/%s.html" % plugin_name
        socket.setdefaulttimeout(3)

        try:
            # grab version info of the html document
            latest_version = urllib.urlopen(the_url).read().split('\n')[0]

            # compare version information to current version
            if current_version < latest_version:

                template = (u"You are running {0}. "
                            "A newer version, {1}, is available.")
                self.errorLog(template.format(current_version, latest_version))

        except urllib.error.URLError:
            # self.debugLog("Error: {0}".format(e))
            self.errorLog(u"Unable to determine if the plugin is up-to-date.")

        except urllib.error.HTTPError:
            # self.debugLog("Error: {0}".format(e))
            self.errorLog(u"Unable to determine if the plugin is up-to-date.")

        # except (Exception, e):
        #     self.debugLog("Error: {0}".format(e))
        #     self.errorLog(u"Unable to determine if the plugin is up-to-date.")
        '''

    '''
    ########################################
    # deviceStartComm() is called on application launch for all of our plugin defined
    # devices, and it is called when a new device is created immediately after its
    # UI settings dialog has been validated. This is a good place to force any properties
    # we need the device to have, and to cleanup old properties.
    def deviceStartComm(self, dev):
        # self.logger.debug(f"deviceStartComm: {dev.name}")

        props = dev.pluginProps
        if dev.deviceTypeId == 'myColorType':
            # Set SupportsColor property so Indigo knows device accepts color actions and should use color UI.
            props["SupportsColor"] = True

            # Cleanup properties used by other device types. These can exist if user switches the device type.
            if "IsLockSubType" in props:
                del props["IsLockSubType"]

            dev.replacePluginPropsOnServer(props)
        elif dev.deviceTypeId == 'myLockType':
            # Set IsLockSubType property so Indigo knows device accepts lock actions and should use lock UI.
            props["IsLockSubType"] = True

            # Cleanup properties used by other device types. These can exist if user switches the device type.
            if "SupportsColor" in props:
                del props["SupportsColor"]

            dev.replacePluginPropsOnServer(props)
    '''


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
    # def validateDeviceConfigUi(self, values_dict, type_id, dev_id):
    #     return (True, values_dict)

    # passed in variable names are different....look at this section

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

    ###################################################
    # revisit this
    def check_snmptrapd_config(self, the_path, the_config_file):
        '''
        This function confirms the contents of the file "snmptrapd.conf"
        which is in the plugin bundle, contains the correct entries and
        paths to the programs referenced
        '''

        # read the "snmptrapd.conf" file
        filename = "{0}{1}".format(the_path.strip("'"), the_config_file)
        with open(filename, 'r') as f:
            lines = f.readlines()

        # format the trap handler entry in the "snmptrapd.conf" file
        the_traphandler = 'snmpTrapHandler.py'
        template = "traphandle default /usr/bin/python {0}{1}'\n"
        trap_handler_command = template.format(the_path, the_traphandler)

        # if the correct path to the traphandler file
        # is not used in the "snmptrapd.conf" file
        if trap_handler_command not in lines:

            # rewrite "snmptrapd.conf" using the correct path
            with open(filename, 'w') as f:
                f.write("authCommunity log,execute, public\n")
                f.write(trap_handler_command)
                f.write("disableAuthorization yes\n")


    ###################################################
    def snmptrapdStart(self):

        if not self.is_snmptrapd_running():

            # determine path were the plugin is executing
            the_path = "'{0}/".format(os.getcwd())

            # define the snmptrapd configuration file
            the_conf_file = "snmptrapd.conf"

            # confirm config has correct file paths
            self.check_snmptrapd_config(the_path, the_conf_file)

            # format the snmptrapd command with full paths
            template = "sudo /usr/sbin/snmptrapd -m {0}{1}' -Lo -c {0}{2}'"
            the_command = template.format(the_path,
                                          self.the_mib_file,
                                          the_conf_file)

            # launch snmptrapd as a dameon
            stdout_value, stderr_value = self.shellCommand(the_command, True)

            time.sleep(0.5)

            if self.is_snmptrapd_running():
                indigo.server.log(u"snmptrapd was successfully started.")
                return True
            else:
                indigo.server.log(u"snmptrapd failed to start.")
                indigo.server.log(u"Unable to Process SNMP Traps. "
                                  "Please review the README.")
                if stderr_value:
                    self.debugLog(u"%s" % stderr_value)
                return False

        else:  # snmptrapd is already running
            indigo.server.log(u"snmptrapd was already running!")
            return True

    ###################################################
    def is_snmptrapd_running(self):

        the_command = ['ps', '-U', 'root']
        stdout_value, stderr_value = self.shellCommand(the_command, False)

        for line in stdout_value.splitlines():

            if 'snmptrapd -m' in line:
                # snmptrapd IS running
                return True

        else:

            # snmptrapd IS NOT running
            return False

    ###################################################
    def snmptrapdKill(self):

        the_command = ['ps', '-U', 'root']
        stdout_value, stderr_value = self.shellCommand(the_command, False)

        for line in stdout_value.splitlines():

            if 'snmptrapd -m' in line:
                pid = int(line.split(None, 1)[0])

                the_command = "sudo /bin/kill -TERM {0}".format(pid)
                self.shellCommand(the_command, True)

                time.sleep(0.5)

                if not self.is_snmptrapd_running():
                    indigo.server.log(u"snmptrapd has been stopped "
                                      "(pid %s)." % pid)
                    return True
                else:
                    indigo.server.log(u"snmptrapd failed to stop.")
                    return False
        else:

            # snmptrapd was NOT running!
            return True


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

    '''
    def actionControlDevice(self, action, dev):
        ###### TURN ON ######
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            # Command hardware module (dev) to turn ON here:
            # ** IMPLEMENT ME **
            send_success = True        # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" on")

                # And then tell the Indigo Server to update the state.
                dev.updateStateOnServer("onOffState", True)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" on failed")

        ###### TURN OFF ######
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            # Command hardware module (dev) to turn OFF here:
            # ** IMPLEMENT ME **
            send_success = True        # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" off")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("onOffState", False)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" off failed")

        ###### LOCK ######
        if action.deviceAction == indigo.kDeviceAction.Lock:
            # Command hardware module (dev) to LOCK here:
            # ** IMPLEMENT ME **
            send_success = True        # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" lock")

                # And then tell the Indigo Server to update the state.
                dev.updateStateOnServer("onOffState", True)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" lock failed")

        ###### UNLOCK ######
        elif action.deviceAction == indigo.kDeviceAction.Unlock:
            # Command hardware module (dev) to turn UNLOCK here:
            # ** IMPLEMENT ME **
            send_success = True        # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" unlock")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("onOffState", False)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" unlock failed")

        ###### TOGGLE ######
        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            # Command hardware module (dev) to toggle here:
            # ** IMPLEMENT ME **
            new_on_state = not dev.onState
            send_success = True        # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" toggle")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("onOffState", new_on_state)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" toggle failed")

        ###### SET BRIGHTNESS ######
        elif action.deviceAction == indigo.kDeviceAction.SetBrightness:
            # Command hardware module (dev) to set brightness here:
            # ** IMPLEMENT ME **
            new_brightness = action.actionValue
            send_success = True        # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" set brightness to {new_brightness}")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("brightnessLevel", new_brightness)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" set brightness to {new_brightness} failed")

        ###### BRIGHTEN BY ######
        elif action.deviceAction == indigo.kDeviceAction.BrightenBy:
            # Command hardware module (dev) to do a relative brighten here:
            # ** IMPLEMENT ME **
            new_brightness = min(dev.brightness + action.actionValue, 100)
            send_success = True        # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" brighten to {new_brightness}")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("brightnessLevel", new_brightness)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" brighten to {new_brightness} failed")

        ###### DIM BY ######
        elif action.deviceAction == indigo.kDeviceAction.DimBy:
            # Command hardware module (dev) to do a relative dim here:
            # ** IMPLEMENT ME **
            new_brightness = max(dev.brightness - action.actionValue, 0)
            send_success = True        # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" dim to {new_brightness}")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("brightnessLevel", new_brightness)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" dim to {new_brightness} failed")

        ###### SET COLOR LEVELS ######
        elif action.deviceAction == indigo.kDeviceAction.SetColorLevels:
            # action.actionValue is a dict containing the color channel key/value
            # pairs. All color channel keys (redLevel, greenLevel, etc.) are optional
            # so plugin should handle cases where some color values are not specified
            # in the action.
            action_color_vals = action.actionValue

            # Construct a list of channel keys that are possible for what this device
            # supports. It may not support RGB or may not support white levels, for
            # example, depending on how the device's properties (SupportsColor, SupportsRGB,
            # SupportsWhite, SupportsTwoWhiteLevels, SupportsWhiteTemperature) have
            # been specified.
            channel_keys = []
            using_white_channels = False
            if dev.supportsRGB:
                channel_keys.extend(['redLevel', 'greenLevel', 'blueLevel'])
            if dev.supportsWhite:
                channel_keys.extend(['whiteLevel'])
                using_white_channels = True
            if dev.supportsTwoWhiteLevels:
                channel_keys.extend(['whiteLevel2'])
            elif dev.supportsWhiteTemperature:
                channel_keys.extend(['whiteTemperature'])
            # Note having 2 white levels (cold and warm) takes precedence over
            # the use of a white temperature value. You cannot have both, although
            # you can have a single white level and a white temperature value.

            # Next enumerate through the possible color channels and extract that
            # value from the actionValue (action_color_vals).
            kv_list = []
            result_vals = []
            for channel in channel_keys:
                if channel in action_color_vals:
                    brightness = float(action_color_vals[channel])
                    brightness_byte = int(round(255.0 * (brightness / 100.0)))

                    # Command hardware module (dev) to change its color level here:
                    # ** IMPLEMENT ME **

                    if channel in dev.states:
                        kv_list.append({'key':channel, 'value':brightness})
                    result = str(int(round(brightness)))
                elif channel in dev.states:
                    # If the action doesn't specify a level that is needed (say the
                    # hardware API requires a full RGB triplet to be specified, but
                    # the action only contains green level), then the plugin could
                    # extract the currently cached red and blue values from the
                    # dev.states[] dictionary:
                    cached_brightness = float(dev.states[channel])
                    cached_brightness_byte = int(round(255.0 * (cached_brightness / 100.0)))
                    # Could show in the Event Log '--' to indicate this level wasn't
                    # passed in by the action:
                    result = '--'
                    # Or could show the current device state's cached level:
                    #    result = str(int(round(cached_brightness)))

                # Add a comma to separate the RGB values from the white values for logging.
                if channel == 'blueLevel' and using_white_channels:
                    result += ","
                elif channel == 'whiteTemperature' and result != '--':
                    result += " K"
                result_vals.append(result)
            # Set to False if it failed.
            send_success = True

            result_vals_str = ' '.join(result_vals)
            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" set color to {result_vals_str}")

                # And then tell the Indigo Server to update the color level states:
                if len(kv_list) > 0:
                    dev.updateStatesOnServer(kv_list)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" set color to {result_vals_str} failed")
    '''

    ########################################
    def setPDUDelays(self, dev):

        # get IP, community name & outlet from props
        outlet = dev.pluginProps["outlet"]
        pduIpAddr = dev.pluginProps["ipAddr"]
        community = dev.pluginProps["community"]
        # swapRebootForOff = dev.pluginProps["swapRebootForOff"]
        # PowerOnTime = dev.pluginProps["sPDUOutletPowerOnTime"]
        # PowerOffTime = dev.pluginProps["sPDUOutletPowerOffTime"]
        # RebootDuration = dev.pluginProps["sPDUOutletRebootDuration"]

        # if len(outlet_list) > (int(outlet) - 1):

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

                # i.e. snmpset -t 2 s-m PowerNet-MIB -v 1 -c private -v 1 192.168.0.232 sPDUOutletPowerOnTime.5 i 15
                # full path the the MIB file is needed

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
        # state argument is either "on" or "off"
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
            self.errorLog(u"Error: State must be on or off")
            return(False)

        # determine where the plugin is running
        # use that to find the full path to the MIB file
        the_path = "'{0}/{1}'".format(os.getcwd(), self.the_mib_file)

        # put together the snmpwalk command to determine device status
        template = "snmpset -t 2 -m {0} -v 1 -c {1} {2} sPDUOutletCtl.{3}{4}"
        the_command = template.format(the_path, community,
                                      pduIpAddr, outlet, theStateCode)

        # i.e. snmpset -t 2 s-m PowerNet-MIB -v 1 -c private -v 1 192.168.0.232 sPDUOutletCtl.5 i 1
        # full path the the MIB file is needed

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

        # if result_code == 0:
        #     dev.updateStateOnServer("onOffState", False)
        #     indigo.server.log(u'Device "%s" is off' % (dev.name))
        #     return True
        # elif result_code == 1:
        #     dev.updateStateOnServer("onOffState", True)
        #     indigo.server.log(u'Device "%s" is on' % dev.name)
        #     return True
        # else:
        #     self.errorLog(u'Error: Device "%s" in unknown state' % dev.name)
        #     return False


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





    '''
    ########################################
    def confirmStatusAll(self, pluginAction):

            # This function is meant to be executed as a Action Group,
            # called from an external SNMP trap handler.

            # It verifies that all outlet states in Indigo are correctly
            # displayed an corrects them if not. Needed if states are change
            # from PDU web portal directly.

        ipList = []
        the_devices = []

        # make a list of all the APC PDU devices which are configured
        for dev in indigo.devices.iter("com.anyone.apcpdu"):

            if dev.configured:
                the_id = dev.id
                ip = dev.globalProps['com.anyone.apcpdu']['ipAddr']
                outlet = dev.globalProps['com.anyone.apcpdu']['outlet']
                community = dev.globalProps['com.anyone.apcpdu']['community']

                # append to device list
                the_devices.append([ip, the_id, outlet,
                                    dev.onState, community])

                # if ip & community combo are unique append to list
                if [ip, community] not in ipList:
                    ipList.append([ip, community])

        # Just in case there is more than one PDU
        # check all configured IP and community combinations
        for the_ip, the_community in ipList:

            # determine where the plugin is running
            # use that to find the full path to the MIB file
            the_path = "'{0}/{1}'".format(os.getcwd(), self.the_mib_file)

            # put together the snmpwalk command to determine device status
            template = "snmpwalk -t 2 -m {0} -v 1 -c {1} {2} sPDUMasterState"
            the_command = template.format(the_path, the_community, the_ip)
            # i.e. snmpwalk -t 2 -m PowerNet-MIB -v 1 -c private 192.168.0.232 sPDUMasterState

            proc = subprocess.Popen(the_command,
                                    shell=True,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, )
            stdout_value, stderr_value = proc.communicate()

            if not stderr_value:

                # create a list of outlet On/Off states
                outlet_list = stdout_value[43:-2].split()

                # cycle thru configured devices
                for device in the_devices:

                    # extract device values
                    ip, the_id, outlet, on_state, community = device

                    # if device ip/community matches entry in ip/community list
                    if (the_ip, the_community) == (ip, community):

                        # if the device state is On in Indigo
                        if on_state:
                            # if device showed via snmpWalk as Off
                            if outlet_list[int(outlet) - 1] == "Off":
                                # Change the Indigo device state to Off
                                target = indigo.devices[the_id]
                                target.updateStateOnServer("onOffState", False)
                                template = u'Device "%s" was turned off'
                                indigo.server.log(template % target.name)

                        else:  # the device state is Off in Indigo

                            # if device showed via snmpWalk as On
                            if outlet_list[int(outlet) - 1] == "On":
                                # Change the Indigo device state to On
                                target = indigo.devices[the_id]
                                target.updateStateOnServer("onOffState", True)
                                template = u'Device "%s" was turned on'
                                indigo.server.log(template % target.name)

    

    ########################################
    # General Action callback
    ######################
    def actionControlUniversal(self, action, dev):
        ###### BEEP ######
        if action.deviceAction == indigo.kUniversalAction.Beep:
            # Beep the hardware module (dev) here:
            # ** IMPLEMENT ME **
            self.logger.info(f"sent \"{dev.name}\" beep request")

        ###### ENERGY UPDATE ######
        elif action.deviceAction == indigo.kUniversalAction.EnergyUpdate:
            # Request hardware module (dev) for its most recent meter data here:
            # ** IMPLEMENT ME **
            self.logger.info(f"sent \"{dev.name}\" energy update request")

        ###### ENERGY RESET ######
        elif action.deviceAction == indigo.kUniversalAction.EnergyReset:
            # Request that the hardware module (dev) reset its accumulative energy usage data here:
            # ** IMPLEMENT ME **
            self.logger.info(f"sent \"{dev.name}\" energy reset request")

        ###### STATUS REQUEST ######
        elif action.deviceAction == indigo.kUniversalAction.RequestStatus:
            # Query hardware module (dev) for its current status here:
            # ** IMPLEMENT ME **
            self.logger.info(f"sent \"{dev.name}\" status request")

    ########################################
    # Custom Plugin Action callbacks (defined in Actions.xml)
    ######################
    def set_backlight_brightness(self, plugin_action, dev):
        try:
            new_brightness = int(plugin_action.props.get("brightness", 100))
        except ValueError:
            # The int() cast above might fail if the user didn't enter a number:
            self.logger.error(f"set backlight brightness action to device \"{dev.name}\" -- invalid brightness value")
            return
        # Command hardware module (dev) to set backlight brightness here:
        # FIXME: add implementation here
        send_success = True     # Set to False if it failed.
        if send_success:
            # If success then log that the command was successfully sent.
            self.logger.info(f"sent \"{dev.name}\" set backlight brightness to {new_brightness}")
            # And then tell the Indigo Server to update the state:
            dev.updateStateOnServer("backlightBrightness", new_brightness)
        else:
            # Else log failure but do NOT update state on Indigo Server.
            self.logger.error(f"send \"{dev.name}\" set backlight brightness to {new_brightness} failed")
    '''

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


