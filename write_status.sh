#!/bin/sh
# Status writer - updates STATUS.md every 30 seconds
while true; do
    echo "Updated: $(date -u)" > STATUS.md
    for bot in snap eddy bolt storm medic; do
        if pgrep -f "${bot}.py" > /dev/null; then
            echo "${bot}: RUNNING" >> STATUS.md
        else
            echo "${bot}: DOWN" >> STATUS.md
        fi
    done
    sleep 30
done
