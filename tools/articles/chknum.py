"""核对 art/cN.py 的 step 文本里出现的数字(含小数,至少 3 个字符)是否都在 out/cN.txt 里出现过。用法:python3 chknum.py c48"""
import re, sys, importlib
sys.path.insert(0, '.')
n = sys.argv[1]
m = importlib.import_module(f'art.{n}')
out = open(f'out/{n}.txt').read()
missing = []
for i, st in enumerate(m.steps, 1):
    for num in set(re.findall(r'(?<![\w.])\d[\d.,]*\d(?![\d.,])', st['note'])):
        if len(num) >= 3 and num not in out and num.replace(',', '') not in out:
            missing.append((i, num))
print(n, '缺失的数字(不在 out 里,可能是推算值):', missing if missing else '无')
