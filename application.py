import argparse
import socket
import time
from struct import *
import sys
import ipaddress
from socket import AF_INET, SOCK_DGRAM
from os import path

# I integer (unsigned long) = 4bytes and H (unsigned short integer 2 bytes)
# see the struct official page for more info

header_format = '!IIHH'


# Taken from lecture
# The function creates a packet that we use to send from client to server and opposite
# Takes in the arguments seq, ack, flags, win, data
# Then returns the packet
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
    return packet


# Taken from lecture
# The function parses the header of the packet
# Takes the header as the argument
# Then returns the values of the parsed header
def parse_header(header):
    # taks a header of 12 bytes as an argument,
    # unpacks the value based on the specified header_format
    # and return a tuple with the values
    header_from_msg = unpack(header_format, header)
    # parse_flags(flags)
    return header_from_msg


# Taken from lecture
# The function parses the flags of the header
# Takes the flag value from the header as the argument
# Then returns the values of syn, ack and fin in the flag value
def parse_flags(flags):
    # we only parse the first 3 fields because we're not
    # using rst in our implementation
    syn = flags & (1 << 3)
    ack = flags & (1 << 2)
    fin = flags & (1 << 1)
    return syn, ack, fin


def client():  # Function for all client methods
    dropSequence = False  # Variable is used to drop the first sequence in the GBN and GBN-SR, used for testcase
    if args.testcase == "dropseq":
        dropSequence = True  # This is true if "dropseq" is used with the -t flag,
        # which means it is true that we are going to drop a sequence

    # Creates the socket for the client, uses the argument parser arguments to connect to server
    serverName = args.ipaddress
    serverPort = args.port
    clientSocket = socket.socket(AF_INET, SOCK_DGRAM)

    # Run the method that does the handshake method with the server
    handshake_client(serverName, serverPort, clientSocket)

    # If the chosen reliability method is Stop and Wait, then do this part of code
    if args.reliability == "SAW":  # Client SAW
        print("Using the Stop and Wait method....")
        print("----------------------------------")

        # Open the file that you want to send, read-binary
        f = open(args.file, "rb")
        data = f.read(1460)  # Read the first 1460 bytes of the file you want to send
        i = 1
        while data:  # While there is still data in (f.read())
            # Create a packet with the right sequence number, ack number, window and flag
            sequence_number = i
            acknowledgement_number = 0
            window = 0
            flags = 0

            # Create packet to send the data that you read
            msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
            print(f'Sending: seq={sequence_number}, ack={acknowledgement_number}, flags={flags}, receiver-window={window}')
            clientSocket.sendto(msg, (serverName, serverPort))  # Send the packet to server
            ack_wait = True
            while ack_wait:  # Wait for the ack for the packet you sent
                try:
                    clientSocket.settimeout(0.5)  # Wait for 0.5 seconds
                    ack = clientSocket.recv(12)  # Receive the ack with only the size of the header (12)
                    seq, ack, flags, win = parse_header(ack[:12])  # Parse the header
                    print(f'Receive: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}') # Printing out ack that is being received
                    if ack == sequence_number:  # If it is the right ack, stop waiting for acks, and send next packet
                        ack_wait = False  # Jump out of while ack_wait
                    elif ack != sequence_number:  # If you get wrong ack number
                        clientSocket.sendto(msg, (serverName, serverPort))  # Resend packet
                except socket.timeout:  # If timer runs out, resend (timeout resend)
                    ack_wait = True
                    clientSocket.sendto(msg, (serverName, serverPort))  # Resend packet

            data = f.read(1460)  # When the packet is sent, read the next 1460 bytes and send again.
            i += 1 # Received an ack for this packet, now update the next packet number
            # We repeat this loop until there is no more data left to read from the file

        # Creating a fin packet to close connection
        sequence_number = 0
        acknowledgement_number = 0
        window = 0
        flags = 2
        data = b''

        msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)

        # This part of the code sends the fin packet, and waits for the ack from server
        while True:
            clientSocket.sendto(msg, (serverName, serverPort))
            print(f'Sending: seq={sequence_number}, ack={acknowledgement_number}, flags={flags}, receiver-window={window}')
            # Wait for ack for the fin message
            try:
                clientSocket.settimeout(0.5)
                fin_ack = clientSocket.recv(12)
                seq, ack, flags, win = parse_header(fin_ack[:12])
                if ack == 0 and flags == 4:  # If right values for the ack:fin, then close connection and f
                    f.close()
                    clientSocket.close()
                    print("----------------------------")
                    print("Connection gracefully closed")
                    break
            except socket.timeout:
                continue  # If ack not received, resend (go through the while loop again)

    # If reliability is GBN, use this part of code
    elif args.reliability == "GBN": # Client GBN
        print("Using the Go Back N approach....")
        print("----------------------------------")

        # Open the file
        f = open(args.file, "rb")
        sender_window = []  # Sender window list, that we use to send all the packets at the same time
        counter = 1  # Value for the sequence number of the packets
        data = 0
        for i in range(int(args.window)):
            data = f.read(1460)  # Read 1460 bytes of file
            if not data:  # If there is no more data, break out of for-loop
                break
            # Create packet with these values
            sequence_number = counter
            acknowledgement_number = 0
            flags = 0
            window = 0
            counter += 1

            # Create packet and add it to the sender window
            msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
            sender_window.append(msg)
            seq, ack, flags, win = parse_header(msg[:12])  # it's an ack message with only the header

        while True:
            # If there is no more data left to read, or there is no more packets in the sender window
            if not data and not sender_window:
                break  # Break out of wile True loop

            #  Sends the whole sender window each time
            for i in range(len(sender_window)):
                if dropSequence:  # If we use dropseq with the -t flag, we will drop the first packet
                    dropSequence = False  # Make it false, so we dont drop any future packets
                    continue  # Hop over the first round in the for-loop, which means that we drop the first packet
                clientSocket.sendto(sender_window[i], (serverName, serverPort))  # Send packet to server
                seq, ack, flags, win = parse_header(sender_window[i][:12])
                print(f'Sending: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}') # Print paackets being sent

            #  Receives acks from server, puts in array
            ack_window = []  # Ack window for the received acks
            for i in range(len(sender_window)):
                try:
                    clientSocket.settimeout(0.5)  # If we dont recv a packet in 0.5seconds it will go to the except
                    ack = clientSocket.recv(12)
                    ack_window.append(ack)  # Add the received ack into the ack window
                    seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
                    print(f'Receive: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                except socket.timeout:
                    break  # If it times out we break

            #   Compares acks and seq and updates sender window
            i = 0
            while i < (len(ack_window)):  # Compare the ack window and the sender window in this loop
                # We compare each ack in the ack window, with the first packet in the sender window
                ack = ack_window[i]
                if not sender_window:  # If sender window is empty break out, and dont check anymore
                    break
                message = sender_window[0]  # First packet in the sender window

                ack_seq, ack_ack, ack_flags, ack_win = parse_header(ack[:12])  # Parse the header for the ack window
                seq, ack, flags, win = parse_header(message[:12])  # Parse the first packet in the sender window

                if seq == ack_ack:  # If we find the ack we are looking for in the ack window
                    del sender_window[0]  # We delete the packet in the sender window, that got the ack back
                    i = 0  # Make the loop go again by restarting the i value to 0
                    data = f.read(1460)  # Read the next 1460 bytes
                    if not data:  # If there is no more data, don't read and continue the "while i < (len(ack_window)):"
                        continue
                    # Create the next packet
                    sequence_number = counter
                    acknowledgement_number = 0
                    flags = 0
                    window = 0
                    counter += 1

                    # Create packet, add it to the sender window, that will be resent again later
                    msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
                    sender_window.append(msg)

                i += 1  # Increase the i value, if sender_window[0] did not match the previous one in ack_window[i]

        # Create fin
        sequence_number = 0
        acknowledgement_number = 0
        window = 0
        flags = 2
        data = b''

        msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)

        # Sends a fin message, and waits for the ack:fin from the server, if not it resends
        while True:
            clientSocket.sendto(msg, (serverName, serverPort))
            print(f'Sending: seq={sequence_number}, ack={acknowledgement_number}, flags={flags}, receiver-window={window}')
            # Wait for ack for the fin message
            try:
                clientSocket.settimeout(0.5)
                fin_ack = clientSocket.recv(12)
                seq, ack, flags, win = parse_header(fin_ack[:12])
                if ack == 0 and flags == 4:  # When ack is received for the fin, we close gracefully
                    f.close()
                    clientSocket.close()
                    print("----------------------------")
                    print("Connection gracefully closed")
                    break
            except socket.timeout:
                continue

    # If reliability is GBN-SR then do this part of the code
    elif args.reliability == "GBN-SR":  # Client GBN-SR
        print("Using the Go Back N approach with selective repeat....")
        print("----------------------------------")

        # Open the file
        f = open(args.file, "rb")
        sender_window = []  # Sender window is the window that we send
        rest_window = []  # Rest window is the rest of the packets,that didn't go through when we sent sender window
        new_window = []  # Contains the new packets that we are sending, after we have sent this sender window
        counter = 1  # Counter that counts the sequence number of the packets
        data = 0
        for i in range(int(args.window)):
            data = f.read(1460)  # Read 1460 bytes from file
            if not data:  # If there is no more data, we don't read or create anymore packets
                break  # Break out of this for loop
            # Creates packet with these values
            sequence_number = counter
            acknowledgement_number = 0
            flags = 0
            window = 0
            counter += 1  # Increase counter with 1 for the next packet

            # Create packet and add to the sender window
            msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
            sender_window.append(msg)

        while True:  # Go through this loop until we have received all acks for all the packets we have sent
            if not sender_window:  # If there are no more packets in the sender window, we are done
                break
            #  Sends the whole sender window
            for i in range(len(sender_window)):
                if dropSequence:  # If drop sequence, we drop the first packet but send the rest
                    dropSequence = False  # Make it false so we dont skio the rest of the packets
                    continue  # Continue on next loop
                clientSocket.sendto(sender_window[i], (serverName, serverPort))  # Send packet to server
                seq, ack, flags, win = parse_header(sender_window[i][:12])  # parsing packet header
                print(f'Sending: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

            #  Receives acks from server, puts in ack list
            ack_window = []
            for i in range(len(sender_window)):
                try:
                    clientSocket.settimeout(0.5)  # Set time out for the reception
                    ack = clientSocket.recv(12)
                    ack_window.append(ack)  # Add to the ack window, where we will compare with the sender window later
                    seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
                    print(f'Receive: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                except socket.timeout:  # If it times out, wait for recv again
                    continue
                except socket.error:  # If socket error, wait for recv again
                    continue

            sender_size = len(sender_window)  # Length of the sender window
            # For loops that compare the first value in the sender window, with each of the acks in the ack window
            for i in range(sender_size):
                for j in range(len(ack_window)):
                    ack = ack_window[j]
                    if not sender_window:
                        break
                    message = sender_window[0]

                    ack_seq, ack_ack, ack_flags, ack_win = parse_header(ack[:12])
                    seq, ack, flags, win = parse_header(message[:12])

                    # If we find the right ack for the sequence number
                    if seq == ack_ack:
                        del sender_window[0]  # Delete the packet that has gotten the ack
                        data = f.read(1460)  # Read 1460 more bytes from file
                        if not data:  # If no more data, don't do anything else
                            break
                        # If there is more data to read, add it to a packet, and put it in new window list
                        sequence_number = counter
                        acknowledgement_number = 0
                        flags = 0
                        window = 0
                        counter += 1
                        msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)
                        new_window.append(msg)

                    # Or if we cannot find the ack for the packet, put it in rest window
                    elif j == len(ack_window) - 1:
                        rest_window.append(sender_window[0])  # Put the packet in rest window
                        del sender_window[0]  # Deleted from sender window

            if rest_window:  # If there is still something in rest window
                # Copy the rest window to sender window, sender window is now the same as rest window
                sender_window = rest_window.copy()
                rest_window = []  # Empty rest window for later use

            # If there is no more in rest window and sender window, then turn sender window into new window
            elif new_window and not sender_window:
                sender_window = new_window.copy()
                new_window = []  # Then empty new dinwo for later use

            # Repeat until there is no more data left to read, and all the windows are empty

        # Create fin
        sequence_number = 0
        acknowledgement_number = 0
        window = 0
        flags = 2
        data = b''

        msg = create_packet(sequence_number, acknowledgement_number, flags, window, data)

        # Send a fin packet, waits for a response, if there is no response it will send again
        while True:
            clientSocket.sendto(msg, (serverName, serverPort))
            print(f'Sending: seq={sequence_number}, ack={acknowledgement_number}, flags={flags}, receiver-window={window}')
            # Wait for ack for the fin message
            try:
                clientSocket.settimeout(0.5)
                fin_ack = clientSocket.recv(12)
                seq, ack, flags, win = parse_header(fin_ack[:12])
                if ack == 0 and flags == 4:  # If we get the fin ack, we gracefully close
                    f.close()
                    clientSocket.close()
                    print("----------------------------")
                    print("Connection gracefully closed")
                    break
            except socket.timeout:
                continue  # If time out, redo the while loop


# Method that does the handshake from the client side
# Takes in the serverName, serverPort and clientSocket as arguments
# # Does not return anything, but prints the status of the connection
def handshake_client(serverName, serverPort, clientSocket):
    # Create a syn packet
    sequence_number = 0
    acknowledgment_number = 0
    window = 0
    flags = 8

    data = b''

    msg = create_packet(sequence_number, acknowledgment_number, flags, window, data)

    addr = (serverName, serverPort)

    clientSocket.sendto(msg, addr)  # Sends syn packet to server
    print(f'Sending: seq={sequence_number}, ack={acknowledgment_number}, flags={flags}, receiver-window={window}')

    try:
        clientSocket.settimeout(0.5)  # Waits for a response for 0.5 seconds
        ack = clientSocket.recv(12)  # Receives a syn ack from server
    except socket.timeout:  # If we do not get the syn ack, we close the socket and write error message
        print("Connection Error: Something went wrong when connecting to the server, please try again")
        clientSocket.close()
        sys.exit()  # Exit system as well

    header_from_ack = ack[:12]
    seq, ack, flags, win = parse_header(header_from_ack)
    print(f'Receive: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
    syn, ack, fin = parse_flags(flags)
    if syn == 8 and ack == 4:  # If it is the right value for the syn ack, we make an ack for the syn ack
        # Creating an ack packet for the syn ack we received
        sequence_number = 0
        acknowledgment_number = 0
        window = 0
        flags = 4

        data = b''

        msg = create_packet(sequence_number, acknowledgment_number, flags, window, data)

        addr = (serverName, serverPort)
        clientSocket.sendto(msg, addr)  # Send it to server
        print(f'Sending: seq={sequence_number}, ack={acknowledgment_number}, flags={flags}, receiver-window={window}')

        print("Connection established with server")  # Print connection established
        print("----------------------------------")  # And sent back an ack to receiver


def server():  # Function for all server methods
    dropAck = False  # Dropack is false, unless you use the "dropack" with the -t flag on the server side
    if args.testcase == "dropack":  # If you use the "dropack" with the -t flag on the server side, then dropack = True
        dropAck = True
    try:
        # Create a socket
        serverSocket = socket.socket(AF_INET, SOCK_DGRAM)
        serverPort = args.port
        # Bind with client
        handshake_server(serverSocket, serverPort)

        if args.reliability == "SAW":  # SAW server
            print("Using the Stop and Wait method....")
            print("----------------------------------")  # And sent back an ack to receiver
            # socket.recvfrom will have to wait until it receives a packet, otherwise it will time out with ack loss
            serverSocket.settimeout(None)

            data, addr = serverSocket.recvfrom(1472)  # Receive packet from client
            start_time = time.time()  # Start time when you receive the first packet
            f = open('new_file.jpg', 'wb')  # Open a new file, where the data we receive is supposed to be put
            counter = 1  # Tracking variable to check for the right sequence number for the packets
            while data:  # While there is data left to receive
                seq, ack, flags, win = parse_header(data[:12])  # Parse the header of the packet
                print(f'Receive: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                syn, ack, fin = parse_flags(flags)  # Parse the flags in the header
                if fin == 2:  # When we get the fin message, we break out of the data loop
                    break
                if seq == counter and not dropAck:  # When we get the right counter, and we don't need to drop an ack
                    # We create the ack for the packet and send it to client
                    sequence_number = 0
                    acknowledgment_number = seq
                    window = 0
                    flags = 4
                    f.write(data[12:])  # Write the data to the file
                    data = b''

                    ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
                    print(f'Sending: seq={sequence_number}, ack={acknowledgment_number}, flags={flags}, receiver-window={window}') # Printing out ack that is being sent

                    serverSocket.sendto(ack, addr)  # Send to client
                    counter += 1  # Increase counter for the next packets

                elif seq < counter and not dropAck:
                    # If we get old packets, send acks for them too, # because our previous ack packet could have been lost
                    sequence_number = 0
                    acknowledgment_number = seq
                    window = 0
                    flags = 4
                    data = b''

                    ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
                    print(f'Sending: seq={sequence_number}, ack={acknowledgment_number}, flags={flags}, receiver-window={window}')  # Printing out ack that is being sent
                    serverSocket.sendto(ack, addr)
                elif seq != counter:  # If the sequence number of the packet is not right, keep going
                    print("Not the right packet received")
                    print(str(counter))
                if dropAck:  # If dropack, drop the first ack, then make it false so we don't drop any other acks
                    dropAck = False

                data, addr = serverSocket.recvfrom(1472)  # Receive next packet from client

            # Create ack for fin
            sequence_number = 0
            acknowledgment_number = 0
            flags = 4
            window = 0
            data = b''
            ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
            serverSocket.sendto(ack, addr)  # Send ack
            seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
            print(f'Sending: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

            end_time = time.time()  # End time value

            duration = end_time - start_time  # Count the time duration

            print("----------------------------")
            print("Total duration of the transfer was " + str(round(duration, 2)))  # Print duration

            f.close()  # Close f
            serverSocket.close()
            print("----------------------------")
            print("Connection gracefully closed")

        elif args.reliability == "GBN":  # GBN server
            print("Using the Go Back N approach....")
            print("----------------------------------")  # And sent back an ack to receiver

            receiver_window = []
            ack_window = []
            f = open('new_file.jpg', 'wb')  # Open new file where we transfer the data to
            tracker = 1  # Tracker is used to count the sequence number
            addr = ()
            start_time = time.time()  # Track start time
            while True:
                try:
                    serverSocket.settimeout(0.5)  # Timeout for 0.5 seconds
                    data, addr = serverSocket.recvfrom(1472)  # Receive packet
                    seq, ack, flags, win = parse_header(data[:12])  # Parse header
                    print(f'Receive: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                    syn, ack, fin = parse_flags(flags)  # Parse flags
                    if fin == 2:  # If fin packet is received break out
                        break
                except socket.timeout:
                    continue

                if dropAck:  # If dropack, we go back to the top and receive again
                    dropAck = False  # Make it false so we dont drop further packets
                    continue

                seq, ack, flags, win = parse_header(data[:12])
                syn, ack, fin = parse_flags(flags)
                # If expected sequence number, write to file
                # If a packet is skipped, the next packet will not be used to write to file
                # Even if the packet is wrong, the server will still send an ack so that the client understands which
                # packet went missing
                if seq == tracker:  # If sequence number is the same as tracker
                    f.write(data[12:])  # Type to file
                    tracker += 1  # Increase tracker for next packet

                # Create ack and send ack
                sequence_number = 0
                acknowledgment_number = seq
                flags = 4
                window = 0
                data = b''
                ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
                serverSocket.sendto(ack, addr)  # Send ack to client for the packet
                seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
                print(f'Sending: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

            # Create ack for fin
            sequence_number = 0
            acknowledgment_number = 0
            flags = 4
            window = 0
            data = b''
            ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
            serverSocket.sendto(ack, addr)  # Send to ack for fin client
            seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
            print(f'Sending: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

            end_time = time.time()  # End time

            duration = end_time - start_time  # Calculate duration

            print("----------------------------")
            print("Total duration of the transfer was " + str(round(duration, 2)))  # Print duration

            f.close()  # Close f
            serverSocket.close()  # Gracefully close
            print("----------------------------")
            print("Connection gracefully closed")

        elif args.reliability == "GBN-SR":  # GBN-SR server
            print("Using the Go Back N approach with selective repeat....")
            print("----------------------------------")  # And sent back an ack to receiver

            storage = []  # This will be where we put the packets we receive
            f = open('new_file.jpg', 'wb')
            tracker = 1  # Counts the sequence number for us
            addr = ()
            global dataLeft
            dataLeft = True
            start_time = time.time()  # Start the start time
            while True:
                receiver_window = []
                try:
                    serverSocket.settimeout(0.5)  # Set timout to 0.5 seconds
                    data, addr = serverSocket.recvfrom(1472)  # Receive packet
                    seq, ack, flags, win = parse_header(data[:12])  # Parse header
                    print(f'Receive: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                    syn, ack, fin = parse_flags(flags)  # Parse flags
                    if fin == 2:  # If we get the fin packet, then break out of while True
                        break

                    if dropAck:  # If we dropack, then we continue and skip sending the first ack
                        dropAck = False  # Make it false so we dont skip any more than one
                        continue

                    # If expected sequence number, write to file
                    # If a packet is skipped, the next packet will not be used to write to file
                    # Even if the packet is wrong, the server will still send an ack so that the client understands which
                    # packet went missing
                    if seq == tracker:
                        f.write(data[12:])
                        tracker += 1

                    # If seq is not the expected value ( same as tracker )
                    elif seq != tracker:
                        storage.append(data)  # Put it in the storage/buffer

                    # Create ack and send it anyways
                    sequence_number = 0
                    acknowledgment_number = seq
                    flags = 4
                    window = 0
                    data = b''

                    ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
                    serverSocket.sendto(ack, addr)
                    seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
                    print(f'Sending: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
                except socket.timeout:  # If we do not receive in time, continue and receive again
                    continue

            lastCheck = 0
            # Finally we go through the storage/buffer to find the right sequence numbers
            # and right them in order to the file
            # We have all the packets we need to recreate the image in the storage, because of the acks we sent
            while lastCheck < len(storage):
                seq, ack, flags, win = parse_header(storage[lastCheck][:12])  # it's an ack message with only the header
                if tracker == seq:
                    f.write(storage[lastCheck][12:])  # Write to fike
                    del storage[lastCheck]  # Delete the one we wrote to file
                    tracker += 1  # Increase tracker for next packet
                    lastCheck = -1
                lastCheck += 1  # Increase each time. We go through the whole storage to find the right sequence number

            # Create ack for fin
            sequence_number = 0
            acknowledgment_number = 0
            flags = 4
            window = 0
            data = b''
            ack = create_packet(sequence_number, acknowledgment_number, flags, window, data)
            serverSocket.sendto(ack, addr)  # Send to client
            seq, ack, flags, win = parse_header(ack[:12])  # it's an ack message with only the header
            print(f'Sending: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')

            end_time = time.time()  # Set end time

            duration = end_time - start_time  # Calculate duration

            print("----------------------------")
            print("Total duration of the transfer was " + str(round(duration, 2)))

            f.close()  # Close f
            serverSocket.close()  # Gracefully close
            print("----------------------------")
            print("Connection gracefully closed")

    except ConnectionError:
        print("Connection error")


# Method that does the handshake from the server side
# Takes in the serverSocket and serverPort as arguments
# Does not return anything, but prints the status of the connection
def handshake_server(serverSocket, serverPort):
    serverSocket.bind(('', serverPort))
    try:
        receiveMessage, client_address = serverSocket.recvfrom(12)  # Receive syn first from client
        header_from_receive = receiveMessage[:12]
        seq, ack, flags, win = parse_header(header_from_receive)  # Parse the header
        print(f'Receive: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
        syn, ack, fin = parse_flags(flags)  # Parse the flags
    except socket.timeout:
        print("Connection Error: Something went wrong when connecting to the client, please try again")
        serverSocket.close()  # If not received in time, we close the socket
        sys.exit()  # And exit system

    if syn == 8:  # If we got the right packet that we expected
        # We create the syn ack packet and send it back
        sequence_number = 0
        acknowledgment_number = 0
        window = 0
        flags = 12
        data = b''

        msg = create_packet(sequence_number, acknowledgment_number, flags, window, data)
        serverSocket.sendto(msg, client_address)  # Send syn ack to client
        print(f'Sending: seq={sequence_number}, ack={acknowledgment_number}, flags={flags}, receiver-window={window}')
    else:
        print("Did not receive syn and ack") # If we did not receive the right values, we print an error message
        serverSocket.close()  # If not received in time, we close the socket
        sys.exit()  # And exit system

    try:
        serverSocket.settimeout(0.5) # Timeout for 0.5 seconds
        last_ack = serverSocket.recv(12) # Then we receive the ack for the syn ack
        seq, ack, flags, win = parse_header(last_ack) # Parse header
        print(f'Receive: seq={seq}, ack={ack}, flags={flags}, receiver-window={win}')
        syn, ack, fin = parse_flags(flags)  # Parse flags
    except socket.timeout:  # If timeout
        print("Connection Error: Something went wrong when connecting to the client, please try again")
        serverSocket.close()  # Close gracefully
        sys.exit()  # Exit system

    if ack == 4:  # If we got the right packet back, we print out the connection is established
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

# Function for checking if the right testcase is used, if not, the function returns a error message
# and explains how and when to use which test case
# Raises ArgumentTypeError if the test cases are typed incorrectly
def checkTestcase(test):
    valid_test = ("dropseq", "dropack")
    if test not in valid_test:
        raise argparse.ArgumentTypeError("Testcase must be 'dropack' for server and 'dropseq' for client")
    else:
        return test

# Function for checking if inputed file exists
# Raises ArgumentTypeError is file does not exist and stops client
def checkfile(val):
    file = str(val)
    if path.exists(file):
        return val
    else:
        raise argparse.ArgumentTypeError(f'File {file} does not excist')


# Method that takes in the arguments and parses them, so we can take out the values
parser = argparse.ArgumentParser(description='Application that transfers files by using packets and reliable protocols',
                                 epilog='End of help')

# Arguments for server and client
parser.add_argument('-s', '--server', help='Starts a server', action='store_true')
parser.add_argument('-c', '--client', help='Starts a client', action='store_true')
parser.add_argument('-p', '--port', help='Choose port number', type=valid_port, default=8088)
parser.add_argument('-i', '--ipaddress', help='Choose an IP address for connection', type=valid_ip, default='127.0.0.1')
parser.add_argument('-r', '--reliability', help='Choose a reliability function to use for connection', choices=['SAW', 'GBN', 'GBN-SR'])
parser.add_argument('-f', '--file', help='Choose a file to send', type=checkfile)
parser.add_argument('-w', '--window', help='Choose the window size 5, 10 or 15 (only for GBN or GBN-SR)', type=checkWindowSize, default=5)
parser.add_argument('-t', '--testcase', help='Choose test case', type=checkTestcase)

# Parsing the arguments that we just took in
args = parser.parse_args()

# Have to choose a reliability function, or else we get an error message
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

# Run client when -c or --client is used
elif args.client:
    client()

# Run server when -s or --server is used
elif args.server:
    server()

