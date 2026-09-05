#!/usr/bin/env bash
# one `format` run, exactly as groups/format/workflows/format.yaml does it
id=$1
cur=$(/tmp/013/fmt/hash.sh)
stored=$(cat /tmp/013/fmt/.devman/.runs/.format.hash 2>/dev/null)
if [ "$cur" = "$stored" ]; then echo "$id SKIP $(date +%s.%N)"; exit 0; fi
echo "$id RUN   $(date +%s.%N)"
/tmp/013/fmt/fmt.sh
/tmp/013/fmt/hash.sh > /tmp/013/fmt/.devman/.runs/.format.hash
echo "$id DONE  $(date +%s.%N) hash=$(cut -c1-12 /tmp/013/fmt/.devman/.runs/.format.hash)"
