#!/usr/bin/env python

import subprocess


# execute a Indigo Trigger. 
# Triggers can supress their execution in the log
def ExecuteIndigoTrigger(the_number):
    # indigo.trigger.execute(418792776)
    the_command = f"indigo-host -e 'indigo.trigger.execute({the_number})'" 
    shellCommand(the_command, True)


def shellCommand(the_command, shell_value):
    proc = subprocess.Popen(the_command,
                            shell=shell_value,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, 
                            encoding="utf-8")
    stdout_value, stderr_value = proc.communicate()
    return stdout_value.strip(), stderr_value


# for testing purposes capture what is received to file
def write_whatcha_got(share_this):
    the_file = "TrapHistory.txt"
    with open(the_file, 'a') as output:
        output.write(f'{share_this}\n')


def main():

    outlet = {}
    while True:
        try:
            the_input = input()
            
            write_whatcha_got(the_input)

            if the_input[0:4] == "UDP:":
                outlet['IP'] = the_input[the_input.find("[")+1:
                                         the_input.find("]")]

            if "mtrapargsInteger" in the_input:
                outlet['Outlet'] = the_input[-1]

            if "outletOff" in the_input: 
                outlet['State'] = "Off"
                
            if "outletOn" in the_input: 
                outlet['State'] = "On"

        except EOFError:
            break
            
    # if outlet info received
    if outlet:
        ExecuteIndigoTrigger(418792776)  


if __name__ == '__main__':

    main()
