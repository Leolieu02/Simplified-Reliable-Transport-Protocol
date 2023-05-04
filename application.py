import argparse
import socket
from struct import *
import sys
import ipaddress
from socket import AF_INET, SOCK_DGRAM

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
    clientSocket = socket.socket(AF_INET, SOCK_DGRAM)

    handshake_client(serverName, serverPort, clientSocket)

    if args.reliability == "SAW":
        print("Using the Stop and Wait method....")
        print("----------------------------------")

        f = open(args.file, "rb")
        data = f.read(1460)
        i = 1
        while data:
            sequence_number = i
            acknowledgement_number = 0
            window = 0
            flags = 0

            msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
            print(f'seq={sequence_number}, ack={acknowledgement_number}, flags={flags}, receiver-window={window}')
            clientSocket.sendto(msg, (serverName, serverPort))
            ack_wait = True
            while ack_wait:
                try:
                    clientSocket.settimeout(0.5)
                    ack = clientSocket.recv(12)
                    seq, ack, flags, win = parse_header(ack[:12])
                    print("ACK " + str(ack))
                    if ack == sequence_number:
                        ack_wait = False
                    elif ack != sequence_number:  # If you get wrong ack number
                        clientSocket.sendto(msg, (serverName, serverPort))  # Resend packet
                except socket.timeout:  # If timer runs out, resend (timeout resend)
                    ack_wait = True
                    clientSocket.sendto(msg, (serverName, serverPort))  # Resend packet

            data = f.read(1460)
            i += 1

        sequence_number = 0
        acknowledgement_number = 0
        window = 0
        flags = 2
        data = b''

        msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
        clientSocket.sendto(msg, (serverName, serverPort))

        f.close()
        clientSocket.close()
        print("----------------------------")
        print("Connection gracefully closed")

    elif args.reliability == "GBN":
        print("Using the Go Back N approach....")
        print("----------------------------------")

        f = open(args.file, "rb")
        sender_window = []
        counter = 1
        data = 0
        for i in range(int(args.window)):
            data = f.read(1460)
            if not data:
                break
            sequence_number = counter
            acknowledgement_number = 0
            flags = 0
            window = 0
            counter += 1

            msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
            sender_window.append(msg)
            seq, ack, flags, win = parse_header(msg[:12])  # it's an ack message with only the header
            print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

        while True:
            if not data and not sender_window:
                break

            #  Sends the whole sender window
            for i in range(len(sender_window)):
                clientSocket.sendto(sender_window[i], (serverName, serverPort))

            #  Receives acks from server, puts in array
            ack_window = []
            for i in range(len(sender_window)):
                try:
                    clientSocket.settimeout(0.5)
                    ack = clientSocket.recv(12)
                    ack_window.append(ack)
                    seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
                    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                except socket.timeout:
                    break

            #   Compares acks and seq and updates sender window
            i = 0
            while i < (len(ack_window)):
                ack = ack_window[i]
                message = sender_window[0]
                print("length_ack: " + str(len(ack_window)))
                print("length_sender: " + str(len(sender_window)))

                ack_seq, ack_ack, ack_flags, ack_win = parse_header(ack[:12])
                seq, ack, flags, win = parse_header(message[:12])

                if seq == ack_ack:
                    del sender_window[0]
                    i = 0
                    data = f.read(1460)
                    if not data:
                        break
                    sequence_number = counter
                    acknowledgement_number = 0
                    flags = 0
                    window = 0
                    counter += 1

                    msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
                    sender_window.append(msg)
                    seq, ack, flags, win = parse_header(msg[:12])  # it's an ack message with only the header
                    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

                i += 1
        # Create fin
        sequence_number = 0
        acknowledgement_number = 0
        window = 0
        flags = 2
        data = b''

        msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
        clientSocket.sendto(msg, (serverName, serverPort))

        f.close()
        clientSocket.close()
        print("----------------------------")
        print("Connection gracefully closed")

    elif args.reliability == "GBN-SR":
        print("Using the Go Back N approach with selective repeat....")
        print("----------------------------------")

        f = open(args.file, "rb")
        sender_window = []
        rest_window = []
        new_window = []
        counter = 1
        data = 0
        for i in range(int(args.window)):
            data = f.read(1460)
            if not data:
                break
            sequence_number = counter
            acknowledgement_number = 0
            flags = 0
            window = 0
            counter += 1

            msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
            sender_window.append(msg)
            seq, ack, flags, win = parse_header(msg[:12])  # it's an ack message with only the header
            print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

        while True:
            if not sender_window:
                break
            #  Sends the whole sender window
            for i in range(len(sender_window)):
                clientSocket.sendto(sender_window[i], (serverName, serverPort))

            #  Receives acks from server, puts in array
            ack_window = []
            for i in range(len(sender_window)):
                try:
                    clientSocket.settimeout(0.5)
                    ack = clientSocket.recv(12)
                    ack_window.append(ack)
                    seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
                    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                except socket.timeout:
                    continue
                except socket.error:
                    continue

            sender_size = len(sender_window)
            for i in range(sender_size):
                for j in range(len(ack_window)):
                    ack = ack_window[j]
                    if not sender_window:
                        break
                    message = sender_window[0]

                    print("length_ack: " + str(len(ack_window)))
                    print("length_sender: " + str(len(sender_window)))

                    ack_seq, ack_ack, ack_flags, ack_win = parse_header(ack[:12])
                    seq, ack, flags, win = parse_header(message[:12])

                    if seq == ack_ack:
                        del sender_window[0]
                        data = f.read(1460)
                        if not data:
                            print("No more data")
                            break
                        sequence_number = counter
                        acknowledgement_number = 0
                        flags = 0
                        window = 0
                        counter += 1
                        msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
                        new_window.append(msg)
                        print("Ny vindu er " + str(len(new_window)))
                        seq, ack, flags, win = parse_header(msg[:12])  # it's an ack message with only the header
                        print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

                    elif j == len(ack_window) - 1:
                        rest_window.append(sender_window[0])
                        print("Seq ikke sendt " + str(seq))
                        del sender_window[0]

            if rest_window:
                sender_window = rest_window.copy()
                print("Kopierer rest")
                rest_window = []
            # So that if client does not get any acks it will not copy new window yet
            elif new_window and not sender_window:
                sender_window = new_window.copy()
                print("Kopierer new")
                new_window = []

            print("Sender vindu er " + str(len(sender_window)))

        # Create fin
        sequence_number = 0
        acknowledgement_number = 0
        window = 0
        flags = 2
        data = b''

        msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
        clientSocket.sendto(msg, (serverName, serverPort))

        f.close()
        clientSocket.close()
        print("----------------------------")
        print("Connection gracefully closed")


def handshake_client(serverName, serverPort, clientSocket):
    sequence_number = 0
    acknowledgment_number = 0
    window = 0
    flags = 8

    data = b''

    msg = create_packet(sequence_number, acknowledgment_number, flags, window, data)

    addr = (serverName, serverPort)

    clientSocket.sendto(msg, addr)

    ack = clientSocket.recv(12)

    header_from_ack = ack[:12]

    seq, ack, flags, win = parse_header(header_from_ack)
    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
    syn, ack, fin = parse_flags(flags)
    print(f'syn_flag = {syn}, fin_flag={fin}, and ack_flag={ack}')
    if syn == 8 and ack == 4:
        sequence_number = 0
        acknowledgment_number = 0
        window = 0
        flags = 4

        data = b''

        msg = create_packet(sequence_number, acknowledgment_number, flags, window, data)

        addr = (serverName, serverPort)
        clientSocket.sendto(msg, addr)

        print("Connection established with server")
        print("----------------------------------")  # And sent back an ack to receiver


def server():
    dropAck = False
    if args.testcase == "dropack":
        dropAck = True
    try:
        # Create a socket
        serverSocket = socket.socket(AF_INET, SOCK_DGRAM)
        serverPort = args.port
        # Bind with client
        handshake_server(serverSocket, serverPort)

        if args.reliability == "SAW":
            print("Using the Stop and Wait method....")
            print("----------------------------------")  # And sent back an ack to receiver

            data, addr = serverSocket.recvfrom(1472)
            f = open('new_file.jpg', 'wb')
            counter = 1
            while data:
                seq, ack, flags, win = parse_header(data[:12])
                syn, ack, fin = parse_flags(flags)
                if fin == 2:
                    break
                if seq == counter:
                    if dropAck:
                        return
                    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                    sequence_number = 0
                    acknowledgment_number = seq
                    window = 0
                    flags = 4
                    f.write(data[12:])
                    data = b''

                    ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
                    serverSocket.sendto(ack, addr)
                    counter += 1

                elif seq < counter:
                    if dropAck:
                        return
                    sequence_number = 0
                    acknowledgment_number = seq
                    window = 0
                    flags = 4
                    f.write(data[12:])
                    data = b''

                    ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
                    serverSocket.sendto(ack, addr)
                elif seq != counter:
                    print("Not the right packet received")
                    print(str(counter))
                if dropAck:
                    dropAck = False
                data, addr = serverSocket.recvfrom(1472)

            print("----------------------------")
            print("Connection gracefully closed")
            f.close()

        elif args.reliability == "GBN":
            print("Using the Go Back N approach....")
            print("----------------------------------")  # And sent back an ack to receiver

            receiver_window = []
            ack_window = []
            f = open('new_file.jpg', 'wb')
            tracker = 1
            addr = ()
            dataCheck = True

            while dataCheck:
                receiver_window = []
                for i in range(int(args.window)):
                    try:
                        serverSocket.settimeout(0.5)
                        data, addr = serverSocket.recvfrom(1472)
                        seq, ack, flags, win = parse_header(data[:12])  # it's an ack message with only the header
                        print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                        syn, ack, fin = parse_flags(flags)
                        if fin == 2:
                            dataCheck = False
                            break
                        receiver_window.append(data)
                    except socket.timeout:
                        break

                for i in range(len(receiver_window)):
                    if dropAck:
                        dropAck = False
                        continue

                    data = receiver_window[i]
                    seq, ack, flags, win = parse_header(data[:12])
                    syn, ack, fin = parse_flags(flags)
                    print(fin)

                    # If expected sequence number, write to file
                    # If a packet is skipped, the next packet will not be used to write to file
                    # Even if the packet is wrong, the server will still send an ack so that the client understands which
                    # packet went missing
                    if seq == tracker:
                        f.write(data[12:])
                        tracker += 1

                    # Create ack
                    sequence_number = 0
                    acknowledgment_number = seq
                    flags = 4
                    window = 0
                    data = b''

                    ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
                    serverSocket.sendto(ack, addr)
                    seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
                    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

            f.close()
            serverSocket.close()
            print("----------------------------")
            print("Connection gracefully closed")

        elif args.reliability == "GBN-SR":
            print("Using the Go Back N approach with selective repeat....")
            print("----------------------------------")  # And sent back an ack to receiver

            storage = []
            f = open('new_file.jpg', 'wb')
            tracker = 1
            addr = ()
            global dataLeft
            dataLeft = True
            while True:
                receiver_window = []
                try:
                    serverSocket.settimeout(0.5)
                    data, addr = serverSocket.recvfrom(1472)
                    seq, ack, flags, win = parse_header(data[:12])  # it's an ack message with only the header
                    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                    syn, ack, fin = parse_flags(flags)
                    if fin == 2:
                        break

                    if dropAck:
                        dropAck = False
                        continue
                    # If expected sequence number, write to file
                    # If a packet is skipped, the next packet will not be used to write to file
                    # Even if the packet is wrong, the server will still send an ack so that the client understands which
                    # packet went missing
                    if seq == tracker:
                        f.write(data[12:])
                        tracker += 1
                        print("Tracker lik " + str(tracker))

                    elif seq != tracker:
                        for j in range(len(storage)):
                            tmp_data = storage[j]
                            tmp_seq, tmp_ack, tmp_flags, tmp_win = parse_header(tmp_data[:12])
                            print("Temp seq " + str(tmp_seq))
                            if tracker == tmp_seq:
                                f.write(data[12:])
                                del storage[j]
                                tracker += 1
                                print("Tracker storage " + str(tracker))
                                break  # Found in storage
                        storage.append(data)

                    # Create ack
                    sequence_number = 0
                    acknowledgment_number = seq
                    flags = 4
                    window = 0
                    data = b''

                    ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
                    serverSocket.sendto(ack, addr)
                    seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
                    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                except socket.timeout:
                    continue

            f.close()
            serverSocket.close()
            print("----------------------------")
            print("Connection gracefully closed")

    except ConnectionError:
        print("Connection error")


def handshake_server(serverSocket, serverPort):
    serverSocket.bind(('', serverPort))
    receiveMessage, client_address = serverSocket.recvfrom(12)
    header_from_receive = receiveMessage[:12]
    seq, ack, flags, win = parse_header(header_from_receive)
    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
    syn, ack, fin = parse_flags(flags)
    print(f'syn_flag = {syn}, fin_flag={fin}, and ack_flag={ack}')
    if syn == 8:
        sequence_number = 0
        acknowledgment_number = 0
        window = 0
        flags = 12
        data = b''

        msg = create_packet(sequence_number, acknowledgment_number, flags, window, data)
        serverSocket.sendto(msg, client_address)
    else:
        print("Did not receive syn and ack")
        sys.exit()

    last_ack = serverSocket.recv(12)
    seq, ack, flags, win = parse_header(last_ack)
    print(f'seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
    syn, ack, fin = parse_flags(flags)
    print(f'syn_flag = {syn}, fin_flag={fin}, and ack_flag={ack}')
    if ack == 4:
        print("Connection established with client")
        print("-----------------------------------")


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

# Function for checking valid window-sizes
# Checks if input is integer and if input is one of the valid values, raises ArgumentTypeError if not
def checkWindowSize(val):
    try:
        size = int(val)
    except ValueError:
        raise argparse.ArgumentTypeError('Window-size must be an integer')
    valid_size = (5, 10, 15)
    if size not in valid_size:
        raise argparse.ArgumentTypeError('Window-size must be 5, 10 or 15')
    else:
        return size


# Method that takes in the arguments and parses them, so we can take out the values
parser = argparse.ArgumentParser(description='Simplified version of Iperf method in Mininet', epilog='End of help')

# Arguments for server and client
parser.add_argument('-s', '--server', help='Starts a server', action='store_true')
parser.add_argument('-c', '--client', help='Starts a client', action='store_true')
parser.add_argument('-p', '--port', help='Choose port number', type=valid_port, default=8088)
parser.add_argument('-i', '--ipaddress', help='Choose an IP address for connection', type=valid_ip, default='127.0.0.1')
parser.add_argument('-r', '--reliability', help='Choose a reliability function to use for connection')
parser.add_argument('-f', '--file', help='Choose a file to send')
parser.add_argument('-w', '--window', help='Choose the window size 5, 10 or 15 (only for GBN or GBN-SR)', type=checkWindowSize, default=5)
parser.add_argument('-t', '--testcase', help='Choose test case')

# Parsing the arguments that we just took in
args = parser.parse_args()

if not args.reliability:
    print("Choose a reliability function to use")
    sys.exit()

# Cannot start the program with these arguments at the same time
if args.server and args.client:
    print('Error message: Cannot start both client and server at the same time')
    sys.exit()

# Must start program in either server or client-mode
if not args.server and not args.client:
    print("You must run either in server or client mode")
    sys.exit()

elif args.client:
    client()

elif args.server:
    server()


# Window size
# Handshake
# SR alone?
# CheckWindowSizeN
# Hjelp!
# Ferdig