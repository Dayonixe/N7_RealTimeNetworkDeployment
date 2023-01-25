#!/usr/bin/env python
from socket import *
import time

# ouverture d'un socket raw sur eth0
socket= socket(AF_PACKET, SOCK_RAW)
socket.bind(("eth3", 0))

# configuration des addr src et dest
# ici src=dst=00:01:02:03:04:05
src_addr="\x00\x01\x02\x03\x04\x05"
dst_addr="\x00\x01\x02\x03\x00\x00"

# payload = chaine de 1000 caracteres *
payload=("*"*1000)

# checksum non calcule = 0x00000000
checksum="\x00\x00\x00\x00"

# 0x0800 = IPv4
ethertype="\x08\x00"

socket.send(dst_addr+src_addr+ethertype+payload+checksum)

socket.close()
