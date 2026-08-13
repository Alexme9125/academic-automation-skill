#!/bin/zsh
# 把本地 JS 注入 Google Chrome 当前前置窗口的活动标签，打印返回值。
# 用法: macos_chrome_js.sh /path/to/file.js
# 前提: Chrome 已开；View → Developer → Allow JavaScript from Apple Events
set -u
JSFILE="${1:-}"
if [[ -z "$JSFILE" || ! -f "$JSFILE" ]]; then
  echo "用法: macos_chrome_js.sh <file.js>" >&2
  exit 64
fi
JSFILE="$(cd "$(dirname "$JSFILE")" && pwd)/$(basename "$JSFILE")"
osascript -e "set js to do shell script \"cat '$JSFILE'\"" \
          -e 'tell application "Google Chrome" to execute active tab of front window javascript js' 2>&1
