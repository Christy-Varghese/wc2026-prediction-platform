#!/bin/bash
# Daily WC2026 goalscorer refresh — scrapes ESPN into data/raw/match_events.json.
# Installed as a cron job (tag: wc2026-events). Remove with:
#   crontab -l | grep -v wc2026-events | crontab -
cd "/Users/christyvarghese/Documents/ObsidianVault/SecondBrain/wc2026-prediction-platform/backend" || exit 1
../.venv/bin/python -m app.events >> /tmp/wc2026_events_refresh.log 2>&1
