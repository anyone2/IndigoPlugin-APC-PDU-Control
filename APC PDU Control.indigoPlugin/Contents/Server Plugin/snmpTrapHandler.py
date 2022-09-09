#!/usr/bin/env python

import shlex
import subprocess


def main():

    outlet = {}
    while True:

        try:
            the_input = input()
            
            if the_input[0:4] == "UDP:":
                outlet['IP'] = the_input[the_input.find("[")+1:
                                         the_input.find("]")]

            elif "mtrapargsInteger" in the_input:
                outlet['Outlet'] = the_input[-1]

            elif "outletOff" in the_input: 
                outlet['State'] = "Off"
                
            elif "outletOn" in the_input: 
                outlet['State'] = "On"

        except EOFError:
            break
            
    # if outlet info received
    if outlet:
        # execute a Indigo Trigger. Triggers allow log suppression 
        cmd = shlex.split("indigo-host -e 'indigo.trigger.execute("
                          "\"snmpTrapd Trigger\")'")
        subprocess.run(cmd) 


if __name__ == '__main__':

    main()
