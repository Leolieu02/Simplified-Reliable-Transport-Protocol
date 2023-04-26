import argparse
from struct import *
import sys
import ipaddress
from socket import *

# I integer (unsigned long) = 4bytes and H (unsigned short integer 2 bytes)
# see the struct official page for more info

header_format = '!IIHH'


def create_packet(seq, ack, flags, win, data):
    # creates a packet with header information and application data
    # the input arguments are sequence number, acknowledgment number
    # flags (we only use 4 bits),  receiver window and application data
    # struct.pack returns a bytes object containing the header values
    # packed according to the header_format !IIHH
    header = pack(header_format, seq, ack, flags, win)

    # once we create a header, we add the application data to create a packet
    # of 1472 bytes
    packet = header + data
    print(f'packet containing header + data of size {len(packet)}')  # just to show the length of the packet
    return packet


def parse_header(header):
    # taks a header of 12 bytes as an argument,
    # unpacks the value based on the specified header_format
    # and return a tuple with the values
    header_from_msg = unpack(header_format, header)
    # parse_flags(flags)
    return header_from_msg


def parse_flags(flags):
    # we only parse the first 3 fields because we're not
    # using rst in our implementation
    syn = flags & (1 << 3)
    ack = flags & (1 << 2)
    fin = flags & (1 << 1)
    return syn, ack, fin


def client():
    serverName = args.ipaddress
    serverPort = args.port
    clientSocket = socket(AF_INET, SOCK_DGRAM)

    text = 'hello'.encode('utf-8')
    data = text + b'0' * (1460 - len(text))

    sequence_number = 1
    acknowledgment_number = 0
    window = 0  # window value should always be sent from the receiver-side
    flags = 0  # we are not going to set any flags when we send a data packet

    # msg now holds a packet, including our custom header and data
    msg = create_packet(sequence_number, acknowledgment_number, flags, window, data)

    addr = (serverName, serverPort)
    clientSocket.sendto(msg, addr)

    msg = clientSocket.recv(12)

    # let's parse the header
    seq, ack, flags, win = parse_header(msg)  # it's an ack message with only the header
    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

    # now let's parse the flag field
    syn, ack, fin = parse_flags(flags)
    print(f'syn_flag = {syn}, fin_flag={fin}, and ack_flag={ack}')

def server():
    try:
        # Create a socket
        serverSocket = socket(AF_INET, SOCK_DGRAM)
        serverPort = args.port
        # Bind with client
        serverSocket.bind(('', serverPort))
        print("Server ready for connection")

        try:
            # Try to receive packet
            receiveMessage, client_address = serverSocket.recvfrom(1472)
            header_from_msg = receiveMessage[:12]
            seq, ack, flags, win = parse_header(header_from_msg)
            print(f'seq={seq}, ack={ack}, flags={flags}, recevier-window={win}')
            message = receiveMessage.replace(b'0', b'').decode('utf-8')
            print("Packet size: " + str(len(message)))
            print("Data size: " + str(len(message[12:])))
            print("This is the message: " + message)
            print("")
            print("----------------------------------")
            print("")

            try:
                # Send ack back to client

                # Set the right values
                sequence_number = 0
                acknowledgment_number = 1  # an ack for the last sequence
                window = 0 # window value should always be sent from the receiver-side
                flags = 4
                data = b''

                # Create packet to send
                msg = create_packet(sequence_number, acknowledgment_number, flags, window, data)
                print (f'this is an acknowledgment packet of header size={len(msg)}')

                # Send ack back to client
                serverSocket.sendto(msg, client_address)
            except ChildProcessError:
                print("Error in sending back the ack")

        except ConnectionError:
            print("Cannot receive packet")

    except ConnectionError:
        print("Connection error")


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

# Arguments for server and client
parser.add_argument('-s', '--server', help='Starts a server', action='store_true')
parser.add_argument('-c', '--client', help='Starts a client', action='store_true')
parser.add_argument('-p', '--port', help='Choose port number', type=valid_port, default=8088)
parser.add_argument('-i', '--ipaddress', help='Choose an IP address for connection', type=valid_ip, default='127.0.0.1')

# Parsing the arguments that we just took in
args = parser.parse_args()

# Cannot start the program with these arguments at the same time
if args.server and args.client:
    print('Error message: Cannot start both client and server at the same time')
    sys.exit()

if not args.server and not args.client:
    print("You must run either in server or client mode")
    sys.exit()

elif args.client:
    client()

elif args.server:
    server()