#!/usr/bin/env bash
# Quick check of a running installation: ./deploy/smoke_test.sh http://127.0.0.1:8002/cards
set -euo pipefail
BASE="${1:-http://127.0.0.1:8002/cards}"
fail=0
check() {
  local path="$1" expect="$2" what="$3"
  local body code
  body="$(curl -s -w '\n%{http_code}' "$BASE$path")" || { echo "FAIL $path: no connection"; fail=1; return; }
  code="${body##*$'\n'}"; body="${body%$'\n'*}"
  if [ "$code" != "200" ]; then echo "FAIL $path: HTTP $code"; fail=1; return; fi
  if ! grep -q -- "$expect" <<<"$body"; then echo "FAIL $path: missing $what"; fail=1; return; fi
  echo "ok   $path"
}
check "/health" '"status":"ok"' "health status"
check "/" "app.css" "start page"
check "/demo" "demonav" "demonstration index"
check "/demo/board/arrow" "boards.js" "arrow board"
check "/demo/tap" "tap.js" "tap-order demonstration"
check "/static/app.css" "--paper" "stylesheet"
check "/account/login" "csrf_token" "login form"
headers="$(curl -s -D - -o /dev/null "$BASE/")"
for h in "Content-Security-Policy" "X-Content-Type-Options" "Referrer-Policy"; do
  if grep -qi "^$h:" <<<"$headers"; then echo "ok   header $h"; else echo "FAIL header $h"; fail=1; fi
done
[ "$fail" -eq 0 ] && echo "smoke test passed" || { echo "smoke test failed"; exit 1; }
