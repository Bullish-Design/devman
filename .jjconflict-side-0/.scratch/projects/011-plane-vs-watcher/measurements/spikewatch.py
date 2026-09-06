"""One watchfiles daemon with dspike's exact watch parameters (dspike/watcher.py)."""
import sys, threading
from pathlib import Path
from watchfiles import DefaultFilter, watch as file_watch

class SpikeFilter(DefaultFilter):
    ignore_dirs = (*DefaultFilter.ignore_dirs, ".devenv", ".direnv", ".devman")

root = Path(sys.argv[1]).resolve()
stop = threading.Event()
print("ready", flush=True)
for changes in file_watch(root, watch_filter=SpikeFilter(), step=100,
                          debounce=1_600, rust_timeout=1_000, stop_event=stop,
                          raise_interrupt=False, yield_on_timeout=True):
    pass
