# 安装与环境配置

默认由 Agent 按 [自动接入流程](bootstrap.md) 执行 `scripts/bootstrap.py --apply`：自动识别、检查现状、补齐缺项并验证。用户无需先选平台或填写路径。以下是按需排查的详细指引，已有可用配置直接复用：

- [WorkBuddy：官方 ima 连接器、官方 Skill、本项目技能](install-workbuddy.md)
- [其他 Agent：Codex、Claude Code、OpenClaw 与 MCP-only 客户端](install-other-agents.md)

官方连接器提供宿主内接入；官方 `ima-skill` 提供 OpenAPI 技能；本项目 `ima-operator` 提供操作编排。这三者分开识别，不把导入本项目当成已经装好官方能力。

## 依赖和路径

官方 Skill 需要 Node.js 18+；本项目辅助脚本需要 Python 3.9+。原位编辑、删除还需要当前宿主的 Computer Use。只使用 WorkBuddy 内置连接器时，按客户端提供的能力和授权使用，无需为了只读查询配置本项目脚本。

辅助脚本自动使用 bootstrap 保存的路径并发现标准技能目录；也支持现有 `IMA_OFFICIAL_SKILL_DIR` 或一次性的 `--official-dir`。无需每轮手动 export，不搬运或覆盖已有安装。通用安装落在 `~/.local/share/ima-skills`。

## Client ID 与 API Key

从 [ima 官方接入页](https://ima.qq.com/agent-interface) 获取，保存到该执行环境的 `~/.config/ima/client_id` 和 `~/.config/ima/api_key`，仅本人可读。用本地编辑器或宿主提供的凭证设置填写，不把值放到普通对话、Git、日志或命令参数。本辅助器让官方工具从文件读取，移除凭证环境变量覆盖；只向 `https://ima.qq.com` 发送。

WorkBuddy 扫码授权与 OpenAPI 凭证分开，需要 Skill/API 功能时才配置后者。文件缺少且当前环境已有完整、不冲突的 ima 凭证时，bootstrap 自动复用并安全保存；不需要用户再次提供。云端 Agent 按自身执行环境配置，不能假定可读取本机文件。

## 验收和续跑

先读官方相应模块说明，再只读确认唯一目标库和一篇已知资料。写入前核对可写范围；身份不明确时核对客户端，不把可添加列表当作账号身份。

每个项目保存自己的源映射、ID、散列和回执，不能复用别人的目标 ID。完整备份与项目配置保持本地，只上传授权内容。

环境明确禁止联网时保留本地成果，不切换通道绕过。官方版本或客户端变化时重新核对；写请求超时先回读，不能重复创建。
