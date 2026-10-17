#!/bin/bash
# 以 root 运行一次:安装 /Library/netlab/netlab(root 所有、不可被普通用户改写),并加一条只允许该脚本免密的 sudoers 规则。
set -eu
SRC="$(cd "$(dirname "$0")" && pwd)/netlab"
mkdir -p /Library/netlab
install -o root -g wheel -m 755 "$SRC" /Library/netlab/netlab
chown root:wheel /Library/netlab; chmod 755 /Library/netlab
printf 'w ALL=(root) NOPASSWD: /Library/netlab/netlab\n' > /etc/sudoers.d/netlab
chown root:wheel /etc/sudoers.d/netlab; chmod 440 /etc/sudoers.d/netlab
visudo -cf /etc/sudoers.d/netlab
echo installed
