set +e
busybox devmem 0x0c141000 32 2>&1 | sed 's/^/CFG=/'
busybox devmem 0x0c141004 32 2>&1 | sed 's/^/STATUS=/'
busybox devmem 0x0c141008 32 2>&1 | sed 's/^/RXMSGQ=/'
