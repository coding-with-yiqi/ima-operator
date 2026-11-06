# ima MCP 操作手册

核查日期：2026-11-06。默认走已连接的官方能力；宿主未连接 ima MCP 时，可使用官方 OpenAPI。

## WorkBuddy 官方 ima 连接器

WorkBuddy 用户先按 [安装指引](install-workbuddy.md) 在客户端连接并扫码授权。官方当前文档支持检索、引用资料和把产物保存回知识库；不将其概括为“只有只读 MCP”，也不把连接授权等同于安装了官方笔记 Skill。[WorkBuddy 官方功能说明](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Knowledge-Base/IMA%20Knowledge%20Base/01-Workbuddy-IMA-Basic-Guide)

其他 Agent 的安装与凭证按 [独立安装指引](install-other-agents.md) 执行，不复制 WorkBuddy 的内部配置或登录态。

## 腾讯官方项目 Octop 的 MCP 网关

腾讯云官方 [Octop 连接器目录](https://github.com/TencentCloud/Octop/blob/main/src/octop/infra/connectors/catalog.json) 将 `tencent-ima` 标为 `gateway`。其 [ima 适配器源码](https://github.com/TencentCloud/Octop/blob/main/src/octop/infra/connectors/gateway/adapters/tencent_ima.py) 暴露以下 14 个工具。这里是官方项目内的网关适配器，尚未核实可直接粘贴到任意客户端的独立 MCP URL。不要编造 `/mcp` 地址；实际工具前缀由宿主决定。

笔记：

- `list_notebooks`：笔记本目录。
- `list_notes`：笔记列表。
- `search_notes`：按标题或内容搜索。
- `get_note`：按 ID 读纯文本。
- `create_note`：Markdown 创建笔记。
- `append_note`：追加到指定笔记。

知识库：

- `list_knowledge_bases`：搜索或列出库。
- `list_addable_knowledge_bases`：可添加内容的库。
- `get_knowledge_base`：库详情。
- `list_knowledge`：文件与文件夹。
- `search_knowledge`：库内搜索。
- `import_urls`：网页入库。
- `add_note_to_knowledge`：已有笔记关联入库。
- `get_media`：媒体原文入口。

工具名已按源码核查，尚未通过 Octop 端到端验收。底层 OpenAPI 的搜索、读写笔记、关联入库已在作者的维护流程实测。该适配器未列出删除、全文替换、建知识库、建知识库文件夹或文件移动工具；这些走 [客户端流程](edit-delete.md)。文件上传由官方 Skill 的 COS 流程补齐。

这 14 个工具属于 Octop 适配器，不能据此推断 WorkBuddy 连接器暴露了相同工具名或安装方式。

## 官方 OpenAPI／Skill

[官方授权入口](https://ima.qq.com/agent-interface)；[本机实测的官方技能包 1.1.10](https://app-dl.ima.qq.com/skills/ima-skills-1.1.10.zip)。首次调用读取官方根 `SKILL.md` 和当前模块 `SKILL.md`、API 文档；同一上下文已读且版本未变则复用。跨笔记与知识库操作读取两个模块。后续只定位用到的接口段落。

常用对应关系（路径前缀 `openapi/`）：

```text
list_knowledge_bases        wiki/v1/search_knowledge_base
get_knowledge_base          wiki/v1/get_knowledge_base
list_knowledge              wiki/v1/get_knowledge_list
search_knowledge            wiki/v1/search_knowledge
list_addable_knowledge_bases wiki/v1/get_addable_knowledge_base_list
get_media                   wiki/v1/get_media_info
create_note                 note/v1/import_doc
append_note                 note/v1/append_doc
get_note                    note/v1/get_doc_content
add_note_to_knowledge        wiki/v1/add_knowledge
import_urls                 wiki/v1/import_urls
```

最短创建流程：目标库和文件夹已验证 → 查源映射和同名候选 → `import_doc {content_format:1,content:<UTF-8 Markdown>}` → 保存 `note_id` → `add_knowledge {knowledge_base_id,media_type:11,title,note_info:{content_id:note_id},folder_id}` → 保存 `media_id` → 回读正文、关联和目录。笔记本 `folder_id` 与知识库文件夹 ID 不混用。创建已成功但关联失败时续做关联，不重新创建。

写入用本地请求文件，避免把长正文复制到工具调用文本：

```bash
python3 ~/.agents/skills/ima-operator/scripts/ima_ops.py call \
  --endpoint openapi/note/v1/import_doc \
  --request /绝对路径/request.json --out /绝对路径/receipt.json --write
```

`request.json` 由 UTF-8 源稿生成，含 `content_format:1` 和正文，不含凭证。`--write` 防误调用，不代表用户授权或已完成查重。返回仅代码、ID、回执路径，完整响应留本地。读取同样用 `call`，省略 `--write`。

文件原件入库：官方 `preflight-check.cjs` → `check_repeated_names` → `create_media` → `cos-upload.cjs` → `add_knowledge`。保持原始二进制；COS 只用响应里的临时凭证。持续修订的文字优先笔记，不靠改名上传堆积版本。

## 易错字段与失败处理

- 搜索库可返回 `kb_id/kb_name`，详情是 `id/name`。当前返回值优先，旧映射只作线索。
- `get_knowledge_list` 数据为 `knowledge_list`；搜索通常为 `info_list`。`media_type=99` 为文件夹。不能只读首页。
- 库搜索每页最多 20；目录最多 50；笔记搜索 `start/end` 每批不超过 20，可能模糊命中，须本地精确匹配。分页依 `is_end`，缺失或重复游标应失败，不能当作结束。
- `get_doc_content` 格式 0 是纯文本，2 是 JSON 富文本字符串；1 暂不支持。富文本可验证来源链接。
- 命令退出成功仍须检查业务 `code===0`。`-200` 是技能待更新且原请求未发送。
- `blocked_execution_network` 表示执行环境禁止联网；不判断为服务故障或密钥失效，不换通道绕过。权限恢复后继续。
- 鉴权/权限错误保留具体业务码；核对账号与可写范围，不自行重置密钥。没有已验证的账号身份查询端点，可写列表也不能证明角色或账号姓名。
- 写请求超时不能自动重发。先查标题、映射和正文，判断是否已成功，续接缺失步骤。

## Computer Use MCP

本机工具 `mcp__cua_repl.js` 通过 `cua.getApp("com.tencent.imamac")` 操作 ima。它是宿主的通用 Computer Use MCP，和腾讯接口分开。普通 shell 脚本不能凭空调用它，CLI 辅助器也不是 MCP 服务。

详细执行、删除确认与原位替换按需读 [界面操作](edit-delete.md)。
