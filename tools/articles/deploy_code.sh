#!/bin/bash
# 只部署代码(tech/ zen/ zodiac/ manage.py),不动数据库。
# 用法(任意目录都行):bash /Users/w/Desktop/zen/tools/articles/deploy_code.sh
# 做的事:服务器上先把这几处代码打包留底 -> rsync 上传(服务器上多出来的文件不删)-> 属主改成 deploy
#         -> 用 deploy 用户跑 migrate / collectstatic / build_static(统计脚本是 build_static 时写进静态页的)
#         -> 重启 zen -> 验证。
# 运行前可以先看会传哪些文件(只读):rsync -rnic --exclude='__pycache__' --exclude='*.pyc' tech zen zodiac manage.py root@60.205.138.114:/srv/site/zen/
set -euo pipefail
S=root@60.205.138.114
STAMP=$(date +%Y%m%d-%H%M%S)
cd "$(dirname "$0")/../.."

ssh $S "mkdir -p /srv/site/db-backups && tar czf /srv/site/db-backups/zen-code-before-$STAMP.tgz -C /srv/site/zen tech zen zodiac manage.py && echo 已备份代码到 zen-code-before-$STAMP.tgz"

# macOS 自带的 rsync 没有 --chown,所以上传后在服务器上再改属主
rsync -rlptc --exclude='__pycache__' --exclude='*.pyc' tech zen zodiac manage.py $S:/srv/site/zen/

ssh $S 'bash -s' <<'REMOTE'
set -euo pipefail
cd /srv/site/zen && chown -R deploy:deploy tech zen zodiac manage.py
cat > /tmp/zen_run.sh <<"EOF"
set -e
while IFS== read -r k v; do case "$k" in ""|\#*) ;; *) export "$k=$v";; esac; done < /etc/zen.env
cd /srv/site/zen
/srv/site/venv-zen/bin/python manage.py migrate --noinput
/srv/site/venv-zen/bin/python manage.py collectstatic --noinput
/srv/site/venv-zen/bin/python manage.py build_static
EOF
chmod 755 /tmp/zen_run.sh
su -s /bin/bash deploy -c "bash /tmp/zen_run.sh"
rm -f /tmp/zen_run.sh
systemctl restart zen; sleep 3; systemctl is-active zen
c() { curl -s --resolve "$1:443:127.0.0.1" -k "https://$1$2"; }
echo "百度统计(tech ID 1a03f6d4...)出现次数,应为 1:"
for p in / /network-layered-model.html /series/network/; do printf "  bigywater.tech%s -> " "$p"; c bigywater.tech "$p" | grep -o '1a03f6d448b0ac97e0132d704c567484' | wc -l; done
echo "Umami 残留(应为 0):$(c bigywater.tech / | grep -ci umami)"
echo "星座站(统计 ID 5e83ba72...,应为 1):$(c myzodiac.fun / | grep -o '5e83ba7299810601116511b8779ba816' | wc -l)"
echo "星座站有没有串用 tech 的 ID(应为 0):$(c myzodiac.fun / | grep -c '1a03f6d448b0ac97e0132d704c567484')"
REMOTE
