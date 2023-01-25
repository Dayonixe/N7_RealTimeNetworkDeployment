# Project - Real Time Network Deployment

Team : Nouhaila A. & Théo Pirouelle

<img src="https://img.shields.io/badge/language-C-666666?style=flat-square" alt="laguage-C" /><a href="https://www.python.org/">
  <img src="https://img.shields.io/badge/language-python-blue?style=flat-square" alt="laguage-python" />
</a>

---

The AFDX switch is a software switch and is made with FPGA cards in airplanes.

## A first attempt

### Machine without DPDK

We modify the file `send.py` by thinking to modify the port of sending in the file :

```Python
#!/usr/bin/env python
from socket import *
import time

# opening a raw socket on eth0
socket= socket(AF_PACKET, SOCK_RAW)
socket.bind(("eth3", 0))                    # Sending port

# src and dest addr configuration
# ici src=dst=00:01:02:03:04:05
src_addr="\x00\x01\x02\x03\x04\x05"
dst_addr="\x00\x01\x02\x03\x04\x05"

# payload = chaine of 1000 characteres *
payload=("*"*1000)

# checksum non calcule = 0x00000000
checksum="\x00\x00\x00\x00"

# 0x0800 = IPv4
ethertype="\x08\x00"

socket.send(dst_addr+src_addr+ethertype+payload+checksum)

socket.close()
```

### Machine with DPDK

After sending the machine without DPDK a packet to port number 1.

Result obtained:

```
> ./build/l2fwd -- -p 0x3

Port statistics ====================================
Statistics for port 0 ------------------------------
Packets sent:                        1
Packets received:                    0
Packets dropped:                     0
Statistics for port 1 ------------------------------
Packets sent:                        0
Packets received:                    1
Packets dropped:                     0
Aggregate statistics ===============================
Total packets sent:                  1
Total packets received:              1
Total packets dropped:               0
====================================================
```

We put the `0x3` to say that we use port 0 and port 1.

Switching table used:

| src | dst |
| --- | --- |
| 0 | 1 |
| 1 | 0 |

The switch table is in the file `l2fwd`.

## Implementation of AFDX switching

In this PW, we have chosen to make a direct access data structure. That is to say, we made a table in the first part when we did not manage the multicast VLs. In the second part, we made a list. This allows to reduce the execution time of the code. 

We also chose a static allocation because we have to take into account all the VLs we have (65536). Even if we don't use all the VLs. 

### Machine without DPDK

To test, we modify the destination address:

```Python
#!/usr/bin/env python
from socket import *
import time

# opening a raw socket on eth0
socket= socket(AF_PACKET, SOCK_RAW)
socket.bind(("eth3", 0))

# src and dest addr configuration
# ici src=dst=00:01:02:03:04:05
src_addr="\x00\x01\x02\x03\x04\x05"
dst_addr="\x00\x01\x02\x03\x00\x01"  # The last two bytes to modify for the VL_ID

# payload = chaine of 1000 characteres *
payload=("*"*1000)

# checksum non calcule = 0x00000000
checksum="\x00\x00\x00\x00"

# 0x0800 = IPv4
ethertype="\x08\x00"

socket.send(dst_addr+src_addr+ethertype+payload+checksum)

socket.close()
```

### Machine with DPDK

In a first step, we set up a switching table using lists, and for each VL number we associate a random port between 0 and 1 of dimension 65536. For example:

| VL number | Port number |
| --- | --- |
| 0 | 0 |
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 0 |
| 5 | 1 |
| 6 | 0 |
| 7 | 0 |
| ... | ... |
| 65536 | 1 |

The switching table is filled with a random number between 0 and 1 as follows:

```C
for (i=0 ; i<65536 ; i++) {
	dest_VL[i]=(int)(rand()/(double)(RAND_MAX+1)*2);
}
```

We retrieve the VL number from the destination address and retrieve the destination port from the VL number and the switch table and initialize `t` to calculate the execution time, as follows:

```C
eth = rte_pktmbuf_mtod(m, struct ether_hdr *);
tmp1 = eth->d_addr/addr_bytes[4];
tmp2 = eth->d_addr/addr_bytes[5];
vl = (tmp1 << 8) + tmp2; 
dst_port = l2fwd_dst_ports[dest_VL[VL]];
t = rte_get_timer_cycles();
```

and we add this line just after sending the packet to recover the execution time which corresponds to the memory reading time of the destination port of the switching table:

```C
t = (1000000*(rte_get_timer_cycles()-t)/rte_get_timer_hz());
```

The execution time is $1µs$, and we obtain the following result:

```
> ./build/l2fwd -- -p 0x3

Port statistics ====================================
Statistics for port 0 ------------------------------
Packets sent:                        3
Packets received:                    0
Packets dropped:                     0
Statistics for port 1 ------------------------------
Packets sent:                        2
Packets received:                    5
Packets dropped:                     0
Aggregate statistics ===============================
Total packets sent:                  5
Total packets received:              5
Total packets dropped:               0
====================================================
```

As you can see the program uses the switching table to send the packets that correspond to each VL to the right port.

# The VLs are multicast

For the multicast VLs, we have chosen to modify the data structure we used for the first configuration. We created a list of list of dimension $65536*2$. As follows:

```C
// We initialize the VL 0 for the test              
dest_VL[0][0]=1;
dest_VL[0][1]=1;
for (i=1;i<65536;i++) {
	// We initialize the rest with a random value between 0 and 1
	dest_VL[i][0]=(int)(rand()/(double)(RAND_MAX+1)*2);
	dest_VL[i][1]=(int)(rand()/(double)(RAND_MAX+1)*2);
}
```

Each VL will have a list of two dimensions. For example, for VL number `i`: if `dest_VL[i][0]=1` and `dest_VL[i][1]=1` then the VL is multicast and we send on both ports. Otherwise, we send on port number `dest_VL[i][0]`. 

The execution time is $1µs$.

We use the following code:

```C
// If the VL is multicast
if (dest_VL[VL][0]==1 && dest_VL[VL][1]==1) {
	buffer = tx_buffer[1];
	sent = rte_eth_tx_buffer(1, 0, buffer, m);
	if (sent)
		port_statistics[1].tx += sent;
	buffer = tx_buffer[0];
 	sent = rte_eth_tx_buffer(0, 0, buffer, m);
	if (sent)
		port_statistics[0].tx += sent;
} else {
	dst_port = l2fwd_dst_ports[dest_VL[VL][0]];
	buffer = tx_buffer[dst_port];
	sent = rte_eth_tx_buffer(dst_port, 0, buffer, m);
	if (sent)
		port_statistics[dst_port].tx += sent;
}
```

We can see that the machine without DPDK received 14 packets and sent 17 so there are 3 packets that were multicast.

```
> ./build/l2fwd -- -p 0x3

Port statistics ====================================
Statistics for port 0 ------------------------------
Packets sent:                        8
Packets received:                    0
Packets dropped:                     0
Statistics for port 1 ------------------------------
Packets sent:                        9
Packets received:                    14
Packets dropped:                     0
Aggregate statistics ===============================
Total packets sent:                  17
Total packets received:              14
Total packets dropped:               0
====================================================
```

# VL control at the input

### Machine without DPDK

We modify the `send.py` file to be able to loop without sending to the same recipient :

```Python
#!/usr/bin/env python
from socket import *
import time
import sys
import binascii

# Checking the parameter
if len(sys.argv) == 1:
	print("Ca marche pas, il y a un probleme !!!")
	print(sys.argv)
	exit()

# opening a raw socket on eth0
socket= socket(AF_PACKET, SOCK_RAW)
socket.bind(("eth3", 0))

# src and dest addr configuration
src_addr="\x00\x01\x02\x03\x04\x05"      # ici src=00:01:02:03:04:05
dst_addr="\x00\x01\x02\x03\x00" + binascii.unhexlify("0"+sys.argv[1])

# payload = chaine if 1000 characteres *
payload=("*"*1000)

# checksum non calcule = 0x00000000
checksum="\x00\x00\x00\x00"

# 0x0800 = IPv4
ethertype="\x08\x00"

socket.send(dst_addr+src_addr+ethertype+payload+checksum)

socket.close()
```

```Bash
#!/bin/bash

while :
do
	randNumber=$((RANDOM % 9))
	echo "VL numero : ${randNumber}"
	./sendv2.py $randNumber
	sleep 1
done
```

When we run the `end_system.sh` script, we get the following display:

```
VL numero : 5

VL numero : 1

VL numero : 7

VL numero : 0

VL numero : 3

VL numero : 0

VL numero : 1

VL numero : 7

VL numero : 2

VL numero : 5

VL numero : 7

VL numero : 8

VL numero : 8
```

### Machine with DPDK

After executing the `end_system.sh` script, we get the following display:

```
> ./build/l2fwd -- -p 0x3

Port statistics ====================================
Statistics for port 0 ------------------------------
Packets sent:                        7
Packets received:                    0
Packets dropped:                     0
Statistics for port 1 ------------------------------
Packets sent:                        9
Packets received:                    11
Packets dropped:                     0
Aggregate statistics ===============================
Total packets sent:                  16
Total packets received:              13
Total packets dropped:               0
====================================================

numero de VL : 5
le temps d'execution : 1 µs

numero de VL : 1
le temps d'execution : 1 µs

numero de VL : 7
le temps d'execution : 1 µs

numero de VL : 0
le temps d'execution : 1 µs

numero de VL : 3
le temps d'execution : 1 µs

numero de VL : 0
le temps d'execution : 1 µs

numero de VL : 1
le temps d'execution : 1 µs

numero de VL : 7
le temps d'execution : 1 µs

numero de VL : 2
le temps d'execution : 1 µs

numero de VL : 5
le temps d'execution : 1 µs

numero de VL : 7
le temps d'execution : 1 µs

numero de VL : 8
le temps d'execution : 1 µs

numero de VL : 8
le temps d'execution : 1 µs
```
