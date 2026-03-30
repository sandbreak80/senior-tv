#!/bin/bash
# FLIRC Remote Setup Script for Senior TV
# Run this while physically at the device with the GE remote
#
# Prerequisites:
# 1. FLIRC USB receiver plugged into the NucBox
# 2. GE remote set to AUX mode
# 3. Point the GE remote at the FLIRC dongle (2-3 feet away)

echo "========================================="
echo "  FLIRC Remote Setup for Senior TV"
echo "========================================="
echo ""

# Check FLIRC is connected
if ! flirc_util settings > /dev/null 2>&1; then
    echo "ERROR: FLIRC not detected! Make sure it's plugged in."
    exit 1
fi

echo "FLIRC detected. Firmware: $(flirc_util version 2>/dev/null)"
echo ""
echo "Set your GE remote to AUX mode, then point it at the FLIRC."
echo ""
echo "You will record 6 buttons, one at a time."
echo "After each prompt, press the matching button on the GE remote."
echo ""
read -p "Ready? Press Enter to start..."
echo ""

BUTTONS=("up:UP (d-pad)" "down:DOWN (d-pad)" "left:LEFT (d-pad)" "right:RIGHT (d-pad)" "return:OK / Select (center of d-pad)" "escape:Back / Exit")

for entry in "${BUTTONS[@]}"; do
    key="${entry%%:*}"
    label="${entry##*:}"
    echo "-----------------------------------------"
    echo "  Recording: $label  -->  $key"
    echo "-----------------------------------------"
    echo "  Press the $label button on the GE remote now..."
    echo ""
    flirc_util record "$key"
    result=$?
    if [ $result -eq 0 ]; then
        echo "  OK - recorded!"
    else
        echo "  FAILED (error $result) - you can retry later with: flirc_util record $key"
    fi
    echo ""
    sleep 1
done

echo "========================================="
echo "  Setup Complete! Recorded buttons:"
echo "========================================="
flirc_util settings
echo ""
echo "Test it: open the Senior TV UI and try navigating with the remote."
echo "To redo a button: flirc_util delete  (then press the button to remove)"
echo "To start over:    flirc_util format  (erases all buttons)"
