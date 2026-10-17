from django.core.management.base import BaseCommand
from django.utils import timezone

from zodiac.models import Article

CONTENT_HTML = """
<div class="tags"><span class="tag">秒回型人格</span><span class="tag">说干就干</span><span class="tag">输了也不认怂</span></div>

<h2>开场：那个总是第一个举手的人</h2>
<p>开会问"谁先来"，白羊座的手已经举起来了，脑子里其实还没想好要说什么。朋友问"要不要一起去"，白羊座答应的速度比问题问完还快。身边人总说他们"太冲动了"，但很少有人问一句：他们到底在急什么？</p>
<p class="punch">答案是：白羊座怕的不是做错，是"来不及"。</p>

<h2>火星给的第一把火：竞争心和不服输</h2>
<p>白羊座是黄道十二宫的第一位，守护星是火星——这不是凑巧，是设定好的剧本：永远想当第一个出发的人。别人还在纠结"要不要"，白羊座已经"做了再说"。这股劲头一半是天赋，一半是慌：他们害怕自己一旦停下来想，热情就会先熄灭。</p>
<p>所以你会发现，白羊座开新项目的兴奋感，永远比守成的耐心多得多——新鲜感一过，收尾往往是他们最不想面对的部分。</p>

<h2>被骂"冲动"的另一面：没人教过他们等</h2>
<p class="punch">白羊座不是不会等，是从来没人告诉过他们，"慢一点"也是一种答案。</p>
<p>他们的决策系统天生偏向直觉：感受到方向，行动就已经先于思考启动了。这种反应速度在需要果断的场合是优势——救场、破局、临时救火，白羊座永远冲在前面。但放进一段需要耐心陪伴的关系里，这股急劲儿反而会变成伤人的地方：还没等对方把话说完，"解决方案"已经脱口而出了。</p>

<h2>白羊座的雷区自查清单</h2>
<ul>
  <li><b>抢话解决</b> — 对方只是想被听见，不是想要一个立刻见效的方案，先憋住那句"我觉得你应该"。</li>
  <li><b>三分钟热度</b> — 新计划开始的第三天最危险，那是新鲜感掉下来的临界点，提前给自己设个"熬过去"的小目标。</li>
  <li><b>赢了才算数</b> — 不是所有场合都需要争出输赢，有些关系里，退一步不代表认输。</li>
</ul>

<div class="closing">
  <p>白羊座最不怕的是"开始"，最怕的是"半路上还要不要留下来"——这道题，才是他们真正要学的。</p>
</div>

<p class="share-hook">转发给那个话还没说完就已经在行动的白羊座朋友，看看Ta认不认。</p>
"""


class Command(BaseCommand):
    help = "写入一篇示例文章（白羊座·性格深度解析）用于本地预览"

    def handle(self, *args, **options):
        article, created = Article.objects.update_or_create(
            slug="aries-personality-2026-09-23",
            defaults=dict(
                sign="aries",
                dimension="personality",
                title="白羊座不是冲动，是没人教过Ta“等一等”",
                summary="别再说白羊座冲动了——他们只是太怕错过，把“现在就要”刻进了本能里。",
                content_html=CONTENT_HTML,
                status="published",
                published_at=timezone.now(),
            ),
        )
        verb = "创建" if created else "更新"
        self.stdout.write(self.style.SUCCESS(f"已{verb}文章：{article}"))
