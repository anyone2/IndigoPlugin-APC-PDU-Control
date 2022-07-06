#!/usr/bin/env python

import subprocess

#
def ExecuteGroup():
    # Run Applescript to execute Indigo Action Group "snmpTrapReceived"
    theCommand = "osascript 'ExecuteActionGroup.scpt'"    
    proc=subprocess.Popen(theCommand, shell=True, stdout=subprocess.PIPE, )
    theResponse=proc.communicate()[0]
    # Works but throws an error
    # osascript: OpenScripting.framework - initializer for scripting addition 
    # "/Library/ScriptingAdditions/ThaiTunes.osax" failed. [error -1]

#
def main():
    
    theAction = ""
    outlet = ""
    
    ProcessingTraps = True
    while ProcessingTraps:
        try:
            input = raw_input()
            
            if input[0:4] == "UDP:":
                theIP = input[input.find("[")+1:input.find("]")]
            
            if "mtrapargsInteger" in input:
                theOutlet = input[-1]

            if "outletOff" in input: 
                theAction = "Off"
                
            if "outletOn" in input: 
                theAction = "On"

        except EOFError:
            ProcessingTraps = False
            
    return theAction, theOutlet, theIP
#
if __name__ == '__main__':
    theAction, theOutlet, theIP = main()
    if theOutlet != "":        
        # From AppleScript Execute Indigo Action Group
        ExecuteGroup()


"""
ps aux | grep snmptrapd

sudo snmptrapd -m PowerNet-MIB -c snmptrapd.conf

"""


