#!/bin/bash
# Restart Senior TV - kills server and lets systemd or manual restart take over
fuser -k 5000/tcp 2>/dev/null
sleep 2
cd /home/media/code_projectsd/senior_tv
source venv/bin/activate
nohup python3 server.py > /tmp/senior_tv.log 2>&1 &
sleep 3
echo "Server restarted on port 5000"
