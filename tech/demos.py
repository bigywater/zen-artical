"""
识别"有动画演示的文章"。

站里的动画演示是一个统一形态的交互组件:一个 class="demo" 的容器,加一段内联脚本驱动,
用「上一步 / 下一步 / 播放 / 重置」(或「重来 / 自动播放」)这类按钮控制。所以判据是:
有内联脚本,并且带步进控制按钮或 .demo 组件。

只有"有脚本"不够:代码块的 Python / Java / Go 语言切换标签也是按钮 + 脚本,但不是演示。
正文里提到"模拟""演示"字样也不算(常常是在说"用代码模拟某个场景")。
"""
import re

TAG = '动画演示'

_SCRIPT = re.compile(r'<script[^>]*>(?!\s*</script>)')
_STEP_BUTTON = re.compile(r'<button[^>]*>[^<]*?(?:上一步|下一步|自动播放|播放|暂停|重来|重置|单步|▶|⏮|⏭)[^<]*</button>')
_DEMO_BLOCK = re.compile(r'class="[^"]*\bdemo\b[^"]*"')


def has_animation_demo(html):
    return bool(_SCRIPT.search(html)) and bool(_STEP_BUTTON.search(html) or _DEMO_BLOCK.search(html))
