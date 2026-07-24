set +e
export XDG_RUNTIME_DIR=/run/user/$(id -u)
echo "uid=$(id -u) XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
echo "=== wpctl status (sinks) ==="
wpctl status 2>&1 | sed -n '/Audio/,/Video/p' | head -25
echo "=== pactl sinks ==="
pactl list short sinks 2>&1 | head
