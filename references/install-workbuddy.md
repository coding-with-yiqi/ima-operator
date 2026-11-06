# WorkBuddy：安装 ima 官方连接器与技能

核查日期：2026-11-06。以下按官方文档整理，当前轮未在 WorkBuddy 客户端端到端操作；菜单以当前版本为准。

默认让 Agent 按 [自动接入流程](bootstrap.md) 检查并办理以下步骤。已授权可用的连接器直接复用；用户只在确实需要时参与扫码或账号授权。

## 1. 连接官方 ima

在 WorkBuddy 左侧打开“资料库”→“ima 知识库”→“立即前往授权”，用个人微信扫码登录 ima，核对申请权限并确认。返回后检查已连接状态。也可从“专家·技能·连接器”的连接器页签找到 ima 卡片，按提示接入。

个人版走个人授权；企业版可能由企业统一身份和管理员管理，和个人版连接状态独立。日常任务引用已有资料及把文件存回 ima，可先使用这个官方连接器。[官方 ima 功能指引](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Knowledge-Base/IMA%20Knowledge%20Base/01-Workbuddy-IMA-Basic-Guide)

连接后在任务的连接器选择中启用 ima；只保持本次需要的连接器开启。[官方连接器说明](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Connector)

这是 WorkBuddy 内置的官方接入入口。公开文档称其为连接器；无需自行猜 MCP URL，也不从 WorkBuddy 提取内部 token 给其他 Agent。

## 2. 需要官方笔记/API 能力时，安装 ima Skill

1. 从 [ima 官方接入页](https://ima.qq.com/agent-interface) 获取当前安装包。已核对包为 [ima-skills-1.1.10.zip](https://app-dl.ima.qq.com/skills/ima-skills-1.1.10.zip)。
2. WorkBuddy →“专家·技能·连接器”→“技能”→“添加技能”→“上传技能”，选择官方 ZIP；到“已安装”确认启用。如果市场已有相同官方技能，可按市场提示安装，先检查已有版本。
3. 在 ima 官方接入页取得 Client ID、API Key，按官方技能的凭证说明配置本机。授权给连接器不代表已经配置 Skill 的这组凭证；不要将密钥贴到普通对话。

官方当前说明：对话安装仅支持市场里的技能，自备 ZIP 使用“上传技能”。因此不把“发一个下载链接”写成所有 WorkBuddy 版本都保证成功的安装方式。[官方技能安装说明](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)

## 3. 安装本项目的操作流程

从 [Releases](https://github.com/coding-with-yiqi/ima-operator/releases) 下载 `ima-operator` ZIP，同样用“上传技能”导入并启用。官方 `ima-skill` 提供接口，本项目 `ima-operator` 负责省 token 的操作编排、查重和验收，两个名称应同时区分。

若使用本项目 Python 辅助器，将 `IMA_OFFICIAL_SKILL_DIR` 指向实际安装的官方技能目录（包含 `ima_api.cjs`、`meta.json`），不要猜 WorkBuddy 的内部目录。[凭证与依赖](setup.md)

## 4. 最小验收

先发：“使用 ima 官方连接器，列出我可访问的知识库，并读取指定库的一篇已知资料；只回报标题和来源。”若还安装了 Skill，再要求通过官方 API 只读确认同一库。只有授权、目标和读取均成功，才进入创建或修改任务。

安装图标、已启用状态和扫码完成都不代替真实读取。原位编辑和不可恢复删除还需要当前宿主具备并授权 Computer Use，按 [对应流程](edit-delete.md) 执行。
