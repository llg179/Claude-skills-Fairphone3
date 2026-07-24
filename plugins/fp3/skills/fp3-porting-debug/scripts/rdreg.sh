set +e
which devmem busybox 2>/dev/null
echo "--- NGD CFG @0x0c141000 ---"; devmem 0x0c141000 32 2>&1
echo "--- NGD STATUS @0x0c141004 ---"; devmem 0x0c141004 32 2>&1
echo "--- NGD RX_MSGQ_CFG @0x0c141008 (pipe_offset reg) ---"; devmem 0x0c141008 32 2>&1
