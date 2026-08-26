#!/bin/zsh
# 同 tab 打开 URL：set URL of active tab，避免 open -a 每次新开标签。
# 用法: macos_chrome_nav.sh "https://..."
# 无窗口时才新建；osascript 失败时才回退 open -a。
set -u
URL="${1:-}"
if [[ -z "$URL" ]]; then
  echo "用法: macos_chrome_nav.sh <url>" >&2
  exit 64
fi
osascript -e 'tell application "Google Chrome"
  activate
  if (count of windows) = 0 then make new window
  try
    execute active tab of front window javascript "window.stop()"
  end try
end tell' >/dev/null 2>&1
osascript -e 'on run argv
  tell application "Google Chrome"
    if (count of windows) = 0 then make new window
    set URL of active tab of front window to (item 1 of argv)
  end tell
end run' "$URL" >/dev/null 2>&1 || open -a "Google Chrome" "$URL"
