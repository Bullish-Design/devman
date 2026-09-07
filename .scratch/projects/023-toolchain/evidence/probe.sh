set +e
echo "### label=${LABEL:-?}"
echo "-- PATH --"; echo "$PATH" | tr ':' '\n' | head -12
echo "-- vars --"; for v in VIRTUAL_ENV PYTHONPATH REPOMAN_TOOLCHAIN_VENV DEVENV_ROOT DEVENV_STATE GPU_LLM_BASE_URL GPU_LLM_MODEL UV_FIND_LINKS; do eval "echo \"$v=\${$v-<unset>}\""; done
echo "-- which --"; for c in python python3 uv gitman repoman templateer dagu jj git ruff; do printf "%-10s %s\n" "$c" "$(command -v $c || echo MISSING)"; done
echo "-- imports --"
python3 - <<'PY'
import sys
print("sys.executable", sys.executable)
print("sys.version", sys.version.split()[0])
for m in ("pyjutsu","gitman","templateer","repoman","yaml","pydantic"):
    try:
        mod=__import__(m); print(f"{m:12} OK {str(getattr(mod,'__version__','?')):10} {getattr(mod,'__file__',None)}")
    except Exception as e:
        print(f"{m:12} FAIL {type(e).__name__}: {e}")
PY
