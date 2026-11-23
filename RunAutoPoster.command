#!/bin/zsh
cd "/Users/samar/Youtube auto"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p logs

nohup /Library/Frameworks/Python.framework/Versions/3.9/bin/python3 autoposter.py \
  > "logs/autoposter.out.log" \
  2> "logs/autoposter.err.log" &

