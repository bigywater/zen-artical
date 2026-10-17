"""用法: python3 shot.py <html文件名> <第几步(0=初始)> <输出png> [top]  —— 无头 Chrome 打开包装页,点到指定步骤后截图演示区(top 表示截页首)。"""
import sys, subprocess, os, signal, time
f, n, outp = sys.argv[1], sys.argv[2], sys.argv[3]
top = '&top=1' if len(sys.argv) > 4 else ''
chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
p = subprocess.Popen([chrome, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--window-size=1000,1000', '--virtual-time-budget=9000', f'--screenshot={outp}', f'http://localhost:9801/shot.html?f={f}&n={n}{top}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
t0 = time.time()
while time.time() - t0 < 40 and not (os.path.exists(outp) and time.time() - os.path.getmtime(outp) < 30 and p.poll() is not None):
    if os.path.exists(outp) and os.path.getsize(outp) > 0 and time.time() - os.path.getmtime(outp) < 3: break
    time.sleep(0.5)
try: os.killpg(p.pid, signal.SIGKILL)
except Exception: pass
print(outp, os.path.getsize(outp) if os.path.exists(outp) else 'missing')
