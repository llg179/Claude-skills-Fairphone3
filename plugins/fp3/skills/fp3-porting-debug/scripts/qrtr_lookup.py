#!/usr/bin/env python3
# Minimal qrtr-lookup replacement: enumerate QRTR services via kernel name service.
import socket, struct, sys

QRTR_TYPE_NEW_SERVER = 4
QRTR_TYPE_NEW_LOOKUP = 10
QRTR_PORT_CTRL = 0xfffffffe

s = socket.socket(socket.AF_QIPCRTR, socket.SOCK_DGRAM)
local_node = s.getsockname()[0]

# NEW_LOOKUP with service=0 instance=0 => enumerate everything
pkt = struct.pack('<IIIII', QRTR_TYPE_NEW_LOOKUP, 0, 0, 0, 0)
s.sendto(pkt, (local_node, QRTR_PORT_CTRL))
local_node = s.getsockname()[0]
s.settimeout(2.0)

print(f"# local node = {local_node}")
print("# service  instance(ver)  node  port")
seen = 0
while True:
    try:
        data, addr = s.recvfrom(1024)
    except socket.timeout:
        break
    if len(data) < 20:
        continue
    cmd, svc, inst, node, port = struct.unpack('<IIIII', data[:20])
    if cmd != QRTR_TYPE_NEW_SERVER:
        continue
    if svc == 0 and inst == 0 and node == 0 and port == 0:
        break  # end-of-list marker
    print(f"0x{svc:08x}  0x{inst:08x}  {node:4d}  {port:5d}")
    seen += 1
print(f"# total: {seen} services")
