# 其他 Agent：安装官方 ima Skill + ima-operator

适用于能读取 Skill、执行本机命令并允许受控联网的 Agent。官方包通过 OpenAPI 工作。核查日期：2026-11-06；安装目录依据对应官方文档，当前轮未逐个 Agent 端到端安装。

优先让 Agent 运行 `python3 <技能目录>/scripts/bootstrap.py --apply`，自动复用已有包、保存路径和验收；以下手动步骤仅作排查参考，不要求用户重复操作。详见 [自动接入流程](bootstrap.md)。

## 1. 选择技能目录

- **Codex**：当前官方用户级目录 `~/.agents/skills/`，项目级为 `.agents/skills/`。已有版本若从其他目录加载，先核对当前技能目录，避免安装同名两份。[官方目录说明](https://developers.openai.com/codex/skills/)
- **Claude Code**：个人目录 `~/.claude/skills/`；项目目录 `.claude/skills/`。本地目录不自动出现在 Cowork 或云端会话。[官方说明](https://code.claude.com/docs/en/skills)
- **OpenClaw**：共享目录默认 `~/.openclaw/skills/`，工作区目录为 `<workspace>/skills/`；自定义 state/profile 按当前配置。[官方说明](https://docs.openclaw.ai/tools/skills)
- **其他 Agent**：按该宿主的技能导入或目录规则安装，不复制上述路径冒充通用配置。

## 2. 安装腾讯官方 ima Skill

先到 [ima 官方接入页](https://ima.qq.com/agent-interface) 核对当前版本。以下固定为本项目核验过的 **1.1.10**，压缩包根目录是 `ima-skill/`。安装前检查已有同名技能，已有版本先核对而不覆盖。

macOS/Linux，以 Codex 为例；Claude Code、OpenClaw 替换第一行目录：

```bash
IMA_SKILLS_ROOT="$HOME/.agents/skills"
IMA_INSTALL_STAGE="$(mktemp -d)"
mkdir -p "$IMA_SKILLS_ROOT"
curl --fail --location 'https://app-dl.ima.qq.com/skills/ima-skills-1.1.10.zip' \
  --output "$IMA_INSTALL_STAGE/ima.zip" &&
unzip -q "$IMA_INSTALL_STAGE/ima.zip" 'ima-skill/*' \
  -x '*/.history/*' '*/.DS_Store' -d "$IMA_INSTALL_STAGE" &&
test ! -e "$IMA_SKILLS_ROOT/ima-skill" && \
  cp -R "$IMA_INSTALL_STAGE/ima-skill" "$IMA_SKILLS_ROOT/ima-skill"
```

若下载或解压失败，停止后续步骤；目标已存在时保留旧目录，先检查版本。Windows 可下载同一 ZIP，以资源管理器解压，将其中 `ima-skill` 整个文件夹放到当前 Agent 的技能目录。不要把 ZIP 或外层 `__MACOSX` 目录当成技能。

本次下载的 SHA256 为 `7e0d07cae0f98145dc5147e84b77bcc557e2fc4b256b08907922637952c20a7b`，可用于核对固定包；官方更新版本后重新核对，不将这个值套用到新版本。

确认目录中同时有 `SKILL.md`、`ima_api.cjs`、`meta.json`、`notes/`、`knowledge-base/`。

## 3. 安装本项目 Skill

```bash
git clone https://github.com/coding-with-yiqi/ima-operator.git "$IMA_SKILLS_ROOT/ima-operator"
export IMA_OFFICIAL_SKILL_DIR="$IMA_SKILLS_ROOT/ima-skill"
```

也可从 [Releases](https://github.com/coding-with-yiqi/ima-operator/releases) 下载 ZIP 解压到对应目录。`ima-skill` 与 `ima-operator` 是两份技能。自动流程会发现并保存官方路径，无需 export；手动模式下 `export` 只对当前终端生效，桌面 Agent 可运行一次 bootstrap 登记实际路径。

重新加载技能或新建会话；Codex 可用 `$ima-operator`，Claude Code 可用 `/ima-operator`，OpenClaw 检查当前技能列表。只加载当前任务所需模块。

## 4. 配置官方凭证并验收

按 [环境配置](setup.md) 安全保存 Client ID、API Key；Node.js 18+ 必需，本项目脚本另需 Python 3.9+。以 Codex 路径举例：

```bash
python3 "$IMA_SKILLS_ROOT/ima-operator/scripts/ima_ops.py" \
  --official-dir "$IMA_SKILLS_ROOT/ima-skill" snapshot \
  --name '目标知识库完整名称' --out ./receipts/first-catalog.json
```

出现 `complete:true` 并匹配目标库后，再读取一篇已知资料。看到文件夹或列出技能名称不等于接口已连通。第一次只读验收不创建测试文档、不产生重复资料。

## 只支持 MCP 的客户端

本次未核实可供任意 MCP 客户端直连的独立官方 ima MCP URL。WorkBuddy 官方连接器的授权也不能直接迁移到其他 Agent。腾讯官方项目 [Octop](https://github.com/TencentCloud/Octop/blob/main/src/octop/infra/connectors/gateway/adapters/tencent_ima.py) 有 ima 网关适配器，但它需要所在宿主配置，不是复制一个公开 URL 即可安装的远程服务。

如果宿主只支持 MCP、不能运行 Skill 或脚本，应先选定可用的网关或适配服务并核查来源、安装和凭证方式；不编造 MCP 配置。本仓库不把第三方封装标为官方，也不默认部署额外服务。

Computer Use 需要每个宿主独立提供。Codex 文档中的 `mcp__cua_repl.js` 不能复制成 Claude Code 或 OpenClaw 已安装的工具；读写 API 可独立使用，界面操作另做能力检查。
