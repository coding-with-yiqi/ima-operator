# 环境配置

## 依赖

- Python 3.9+、Node.js 18+（需要内置 fetch）。
- 官方 ima Skill：开发时验证版本 1.1.10，含 `ima_api.cjs` 与 `meta.json`。
- 对于原位编辑、删除等 UI 操作，宿主需提供 Computer Use 工具。文档中的 `mcp__cua_repl.js` 是 Codex 宿主工具；其他 Agent 需使用各自已授权的 UI 工具和当前操作文档。

## 官方技能与凭证

从 [ima 官方入口](https://ima.qq.com/agent-interface) 获取技能和 Client ID、API Key；已验证的 [1.1.10 官方包](https://app-dl.ima.qq.com/skills/ima-skills-1.1.10.zip) 可作为版本参考。优先遵循官方当前版本说明。

辅助脚本默认查找 `~/.local/share/ima-skills/ima_api.cjs`。解压后确保该文件与 `meta.json` 在同一目录，也可指定已有目录：

```bash
export IMA_OFFICIAL_SKILL_DIR='/path/to/official-ima-skill'
python3 scripts/ima_ops.py --official-dir '/path/to/official-ima-skill' snapshot \
  --name '团队知识库' --out ./receipts/catalog.json
```

凭证保存到本机 `~/.config/ima/client_id` 和 `~/.config/ima/api_key`，限制为本人可读；不要提交 Git、粘贴到聊天或放进命令参数。本辅助器让官方工具从这两个文件加载，并移除凭证环境变量覆盖，避免用错账号。密钥只发到 `https://ima.qq.com`。

## 第一轮

先读官方对应模块的技能和 API 文档。用目标库全名做只读盘点，核对库详情与已知文件，再进入写入任务。不同库不能仅凭相似名称选定。需要写入时查可添加库列表；身份或权限有疑问再核对客户端，不将可写列表等同于账号身份。

每个项目自建本地源映射，保存源路径与散列、note_id、media_id、folder_id 和回执。不要复用别人的库 ID。原始聊天、完整备份和项目配置保持本地；共享库只上传用户授权的整理内容。

## 状态与限制

脚本不提供独立 MCP server，也不能从 Python 调用宿主 CUA。已连接官方网关时可以直接使用其工具；未连接时使用官方 OpenAPI。缺少 UI 工具时，仍可完成 API 范围内的操作，不把删除计划报告成已删除。

若环境明确禁止联网，停止依赖网络的步骤并保留本地成果，不切换通道绕过。遇到新官方版本、接口字段变化或客户端行为变化，重新核对文档和小范围验证后继续。
