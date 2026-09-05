#!/usr/bin/env bash
# proposed: format to a FIXPOINT, and store only a hash the tree still has
id=$1
cur=$(/tmp/013/fmt/hash.sh); stored=$(cat /tmp/013/fmt/.devman/.runs/.format.hash 2>/dev/null)
[ "$cur" = "$stored" ] && { echo "$id SKIP"; exit 0; }
echo "$id RUN   $(date +%s.%N)"
for i in 1 2 3; do
  /tmp/013/fmt/fmt.sh
  h1=$(/tmp/013/fmt/hash.sh)
  /tmp/013/fmt/fmt.sh
  h2=$(/tmp/013/fmt/hash.sh)
  [ "$h1" = "$h2" ] && { echo "$h2" > /tmp/013/fmt/.devman/.runs/.format.hash; echo "$id DONE pass=$i"; exit 0; }
  echo "$id RETRY pass=$i (tree moved under the formatter)"
done
echo "$id GAVE UP" >&2; exit 1
