# 增量同步与去重

同一源文档只对应一个有效云端正文。标题相同仅是候选，内容相同也不自动意味着允许删除其他目录或人工文档。

## 最少读取

1. 用源路径稳定键查映射，比较源 SHA256。确认云端同一 ID 的正文摘要后，二者未变就跳过。只有时间戳变化不重写。
2. 无映射时，搜索精确标题和目标目录。未找到才创建；命中后读候选正文，确认来源、内容和归属。查重不全库下载正文。
3. 全库清理时，一次完整盘点保存本地，`candidates` 按标题、可选来源键／散列筛候选。只读候选与差异；不同标题的同源修订用映射补充来源键。
4. 候选逐份下载原文，保留原始字节 SHA256。笔记保存纯文本、富文本和链接。方案列明“保留谁、合入什么、删除谁、备份哪里”，不能按新日期直接丢旧内容。
5. 必要内容合进固定正文并验证，再按 [删除流程](edit-delete.md) 清理。保留人工资料与历史回执，活跃映射只保留唯一目标。

建议映射字段：`source_key, source_sha256, note_id, media_id, folder_id, logical_title, cloud_title, cloud_sha256, hash_type, checked_at`。保存写入阶段与回执，重试从缺失阶段续做。文件字节、笔记纯文本、富文本散列须标类型，不跨类型直接比较。

## 命令

```bash
python3 ~/.agents/skills/ima-operator/scripts/ima_ops.py snapshot \
  --name '目标库全名' --out /绝对路径/before.json
python3 ~/.agents/skills/ima-operator/scripts/ima_ops.py candidates \
  --snapshot /绝对路径/before.json --out /绝对路径/candidates.json
python3 ~/.agents/skills/ima-operator/scripts/ima_ops.py note \
  --id '真实note_id' --out /绝对路径/note-backup.json
```

`candidates` 可加 `--manifest /绝对路径/manifest.json`，数组每项 `media_id`，可选 `source_key`、`sha256`、`hash_type`。只传已核对证据；散列分组要求类型相同。始终输出候选，不发起删除。标题分组不去掉日期，避免合并不同周报。

删除授权清单：`{"knowledge_base_id":"真实ID","media_ids":["已批准ID"]}`。JSON 仅记录范围，不产生授权；须有用户对同一清单的执行时确认。

```bash
python3 ~/.agents/skills/ima-operator/scripts/ima_ops.py snapshot \
  --name '目标库全名' --out /绝对路径/after.json
python3 ~/.agents/skills/ima-operator/scripts/ima_ops.py audit \
  --before /绝对路径/before.json --after /绝对路径/after.json \
  --approved /绝对路径/approved.json --out /绝对路径/audit.json
```

`audit` 只验完整盘点的删除差集、意外新增和保留条目元数据；正文须用 `note` 或原件 SHA256 另验，不能宣称全库正文验证通过。清理期间有意修改正文或移目录应拆批验收。
