#!/usr/bin/env bash
cd /tmp/013/fmt
find . -name '*.py' -not -path './.devenv/*' -not -path './.direnv/*' -not -path './.git/*' -print0 \
  | sort -z | xargs -0r sha256sum | sha256sum
