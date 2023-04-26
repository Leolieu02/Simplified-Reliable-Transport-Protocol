import argparse
import math
import sys
import ipaddress
from socket import *
import time


# Description:
# Function that checks ip address number is valid, returns ip address
# Arguments:
# ip: ip address that needs to be checked
# Returns: Ip address variable
def valid_ip(ip):
    global ip_object
    try:
        ip_object = ipaddress.ip_address(ip)
    except ValueError:
        raise argparse.ArgumentTypeError('The IP address is NOT valid.')
    return ip


# Description:
# Function that checks if port number is valid, returns port number in integer
# Arguments:
# port: port number of the server
# Returns: port value as an integer if possible
def valid_port(port):
    try:
        value = int(port)
    except ValueError:
        raise argparse.ArgumentTypeError('Expecting integer from port')
    if value < 1024 or value >= 65535:
        raise argparse.ArgumentTypeError('Invalid port')
    return value

# Method that takes in the arguments and parses them, so we can take out the values
parser = argparse.ArgumentParser(description='Simplified version of Iperf method in Mininet', epilog='End of help')

# Arguments for server
parser.add_argument('-s', '--server', help='Starts a server', action='store_true')
parser.add_argument('-b', '--bind', help='Choose IP address', type=valid_ip, default='0.0.0.0')
parser.add_argument('-p', '--port', help='Choose port number', type=valid_port, default=8088)


# Arguments for client
parser.add_argument('-c', '--client', help='Starts a client', action='store_true')
parser.add_argument('-I', '--serverip', help='Choose IP address for client', type=valid_ip, default='0.0.0.0')