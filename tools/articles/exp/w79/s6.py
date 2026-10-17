import atexit, os
@atexit.register
def h(): print("  atexit 执行 (sys.exit(3) 已经调用过)")
import sys
print("调用 sys.exit(3)"); sys.exit(3)
