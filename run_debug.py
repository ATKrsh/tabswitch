import sys
import traceback

print("Starting debug run...", flush=True)
try:
    with open('tabswitcher.py', 'r', encoding='utf-8') as f:
        code = f.read()
    exec(code, globals())
except BaseException as e:
    print(f"Exception type: {type(e).__name__}", flush=True)
    traceback.print_exc()
    with open("debug_err.txt", "w") as f:
        traceback.print_exc(file=f)
    sys.exit(1)
