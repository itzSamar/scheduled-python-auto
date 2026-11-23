#!/bin/zsh
cd "/Users/samar/Youtube auto"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
nohup /Library/Frameworks/Python.framework/Versions/3.9/bin/python3 main.py \
  > "logs/manual_upload.out.log" \
  2> "logs/manual_upload.err.log" &
