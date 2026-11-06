# ima-operator

让 Agent 用较少的上下文操作腾讯 ima：创建、搜索、查重、原位修订、迁移、删除与核验。

这是一套 **Agent Skill + MCP 操作手册 + Python 辅助脚本**。已有官方接口负责数据操作，宿主 Computer Use 补齐原位替换和删除。脚本保留完整结果，只向 Agent 返回短回执。

## 开始使用

```bash
git clone https://github.com/coding-with-yiqi/ima-operator.git ~/.codex/skills/ima-operator
```

或从 [Releases](https://github.com/coding-with-yiqi/ima-operator/releases) 下载 ZIP，解压到 Agent 的技能目录。已有同名目录时先核对本地修改，不覆盖自己的配置。

准备 [环境与官方凭证](references/setup.md)，然后向 Agent 说：

> 使用 $ima-operator 更新这篇 ima 笔记，保持同一文档，不重复上传。

也可说“检查这个知识库的重复文档”或“备份并清理我确认的旧版本”。删除会先准备具体清单，依宿主规则取得执行时确认。

## 操作手册

- [技能入口](SKILL.md)：按需加载的简短操作规则。
- [官方 MCP、OpenAPI 与 Computer Use](references/mcp.md)：14 个官方网关工具与实际能力边界。
- [20 个主要使用场景](references/scenarios.md)：周报、专栏、资料入库、原位修订、去重、备份与故障续跑。
- [原位编辑与删除](references/edit-delete.md)：同一 note_id 更新、备份、精确删除和回读。
- [增量同步与查重](references/dedup.md)：源映射、散列、候选筛选和删除差集。

## 如何减少 token

只加载当前任务需要的说明；先搜索和读元数据，正文按候选读取；脚本合并分页并保存完整结果。界面默认使用 AX 差异，能用 API 的操作走 API。未变化的文档跳过，修订沿用已有 ID。

开发时一个 81 文件、9 文件夹的目录样本，完整 JSON 约 9,050 tokens，短回执约 63 tokens（o200k_base 估算，仅比较目录输出）。该样本的私人目录、正文和回执不在仓库中；这是输出压缩示例，不代表总任务费用或通用性能保证。

```bash
python3 scripts/ima_ops.py --help
python3 scripts/ima_ops.py snapshot --name '团队知识库' --out ./receipts/catalog.json
python3 scripts/ima_ops.py candidates --snapshot ./receipts/catalog.json --out ./receipts/candidates.json
```

所有命令使用新的输出文件，避免覆盖备份。`call --write` 允许受限写接口调用；具体目标、用户授权、查重和回读仍由 Skill 流程落实。

## 验证与适用范围

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
```

9 项测试覆盖分页、重复游标、目标匹配、候选误判、散列类型、删除差集、写入边界、业务错误与备份。Computer Use 流程基于 macOS ima 客户端实操；其他平台需要按当前 UI 重新定位。场景手册分别标注“已实测”“官方支持”“待实测”。

官方 MCP 部分依据腾讯云 [Octop ima 适配器](https://github.com/TencentCloud/Octop/blob/main/src/octop/infra/connectors/gateway/adapters/tencent_ima.py)。本仓库为独立的社区技能，不是腾讯官方 MCP 服务；不分发官方技能源码，不包含凭证或私有业务资料。

本仓库原创代码与文档使用 [MIT License](LICENSE)。腾讯官方组件遵循其自身的许可与服务条款。
