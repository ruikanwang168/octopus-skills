#!/usr/bin/env bash
# Wait until the visual companion records a user choice, then print the latest event.
# Usage: wait-for-choice.sh <state_dir> [--timeout-seconds <n>] [--settle-seconds <n>] [--poll-interval <n>]

STATE_DIR="$1"
shift || true

TIMEOUT_SECONDS=900
SETTLE_SECONDS=1
POLL_INTERVAL=0.2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout-seconds)
      TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --settle-seconds)
      SETTLE_SECONDS="$2"
      shift 2
      ;;
    --poll-interval)
      POLL_INTERVAL="$2"
      shift 2
      ;;
    *)
      echo "{\"status\":\"error\",\"message\":\"Unknown argument: $1\"}"
      exit 2
      ;;
  esac
done

if [[ -z "$STATE_DIR" || ! -d "$STATE_DIR" ]]; then
  echo '{"status":"error","message":"Usage: wait-for-choice.sh <state_dir>"}'
  exit 2
fi

if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || [[ "$TIMEOUT_SECONDS" -lt 1 ]]; then
  echo '{"status":"error","message":"--timeout-seconds must be a positive integer"}'
  exit 2
fi

if ! [[ "$SETTLE_SECONDS" =~ ^[0-9]+$ ]]; then
  echo '{"status":"error","message":"--settle-seconds must be a non-negative integer"}'
  exit 2
fi

EVENTS_FILE="${STATE_DIR}/events"
DEADLINE=$(( $(date +%s) + TIMEOUT_SECONDS ))
LAST_EVENT=""
LAST_CHANGE=0

while true; do
  if [[ -s "$EVENTS_FILE" ]]; then
    CURRENT_EVENT="$(tail -n 1 "$EVENTS_FILE")"
    if [[ "$CURRENT_EVENT" != "$LAST_EVENT" ]]; then
      LAST_EVENT="$CURRENT_EVENT"
      LAST_CHANGE="$(date +%s)"
    fi

    if [[ -n "$LAST_EVENT" ]]; then
      NOW="$(date +%s)"
      if [[ "$SETTLE_SECONDS" -eq 0 || $(( NOW - LAST_CHANGE )) -ge "$SETTLE_SECONDS" ]]; then
        printf '%s\n' "$LAST_EVENT"
        exit 0
      fi
    fi
  fi

  if [[ "$(date +%s)" -ge "$DEADLINE" ]]; then
    printf '{"status":"timeout","events_file":"%s"}\n' "$EVENTS_FILE"
    exit 124
  fi

  sleep "$POLL_INTERVAL"
done
