#!/usr/bin/env bash
for f in /tmp/013/fmt/f*.py; do
  sed -i 's/^x=/x = /' "$f"
  sleep 0.02
done
