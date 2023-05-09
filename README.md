# Portfolio2: Data2410 Reliable Transport Protocol (DRTP)
This will be a *simplified* version of the tcp protocol. The program uses the udp
protocol, and by adding new features on top will make it a more reliable solution for file
transfer. Our program will be able to send an image from one client to a server, and take
into account packet loss, duplicates and delays so to make the file stay the same when 
arriving as it was when sent. 

# Running the application
Running this consists of writing the application name followed by the arguments to
dictate the programs behaviour. An example of this may be; `python3 application.py
-s -r SAW -i 10.0.0.1`. You need to run the program in either client 
mode with the `-c` option or in server mode with the `-s` option. Failing to do so 
will leave you with an appropriate error message. When running the program in server
mode, you may choose an ip address to bind to with the `-i` option. Choosing to leave
this out when running the application will make it fall back to the default ip address,
which is **127.0.0.1**. The same can be said for the client side, in which using the
`-i` tag gives you the ability to connect to a server with a specific ip address. 
You will also be able to choose a port for both client and server with the `-p` tag. 
This too will have a default port of **8088** should you choose to not specify port. 

When running the application, you will need to pick a reliability option that
will be used when sending the image. This will have to be done with the `-r` option
followed by one of the reliability functions. Here you will be able to choose between
*Stop-And-Wait*, *Go-Back-N* and *Selective repeat*. Down below will be a list of 
how to run each of them and a small description of what they do

## How to use the reliability functions

- **Stop-And-Wait**. For this you will need to write `-r SAW` when running the application. 
Here the client will wait for each ack from the server before sending a new packet.
- **Go-Back-N**. Here you can use `-r GBN`. Here the client will send multiple
packets and if they arrive out-of-order, the server will discard the new packets and the
clients will send them again. 
- **Selective repeat**. You will need to write `-r GBN-SR` to run this function. This is
almost the same as the Go-Back-N method, but the server will instead save the
out-of-order packets in a buffer for later use.

Both the Go-Back-N and Selective repeat methods will use windows of packets when
transferring. The size of this window can be chosen. Simply use the `-w` tag 
accompanied by the size of the window. **Note that you can only choose the sizes 
5, 10 and 15**.

## Sending file
In this application you will only be able to send **images** to the server. 
When choosing an image to transfer, you will have to use the `-f` option and the name
of the image you want to send. The Portfolio-2 folder will be equipped with a minion.jpg
image to use should you not have one to use. 

## Using testcase
You can run tests on the reliability functions to stimulate packet losses. The `-t`
tag on the server side will drop the first ack one time before continuing to trigger
retransmission. On the server side you will need to write `-t dropack`. Using
it on the client side will drop a packet to trigger retransmission. Using it on the
client side needs to be done by `-t dropseq`. **You will not be able to use the 
dropseq option with the Stop-And-Wait**.

## Arguments
    -h, --help            show this help message and exit
    -s, --server          Starts a server
    -c, --client          Starts a client
    -p PORT, --port PORT  Choose port number
    -i IPADDRESS, --ipaddress IPADDRESS
    Choose an IP address for connection
    -r {SAW,GBN,GBN-SR}, --reliability {SAW,GBN,GBN-SR}
    Choose a reliability function to use for connection
    -f FILE, --file FILE  Choose a file to send
    -w WINDOW, --window WINDOW
    Choose the window size 5, 10 or 15 (only for GBN or GBN-SR)
    -t TESTCASE, --testcase TESTCASE
    Choose test case

## Running the application with examples
- `python3 application.py -s -r SAW` - This will run the program in server mode with
the Stop-And-Wait function
- `python3 application.py -c -i 10.0.0.1 -r GBN -f minion.jpg` - This will run
the application on client mode. It will connect to the server with ip address
10.0.0.1 and use the Go-Back-N method when transferring the file. The image chosen
for sending is minion.jpg. 
- `python3 application.py -s -r GBN-SR -t dropack` - this will run the server with
Selective repeat. In addition to this, it will run a test to make it drop an ack, 
which triggers a retransmission. 

### You can run the program using this format
For server: `python3 application.py -s -i <ip_address> -p <port_number> -r 
<reliable method> -t <test_case>`

For client: `python3 application.py -c -i <server_ip_address> -p <server_port> -f 
<file_to_transfer.jpg> -r <reliable method> -t <test_case>`
