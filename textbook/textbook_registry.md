# 教材注册表

> AI 在开始教学或切换教材时读取此文件，了解可用的教材池。

## 教材列表

| 教材名称 | 路径 | 来源 | 状态 |
|----------|------|------|------|
| Building Effective Agents | textbook/building-effective-agents.md | URL: https://www.anthropic.com/engineering/building-effective-agents | active |

## 操作说明

- **状态**：`active`（正在学习）/ `inactive`（暂停）/ `completed`（已学完）
- **添加教材**：用户在对话中说"添加教材 + URL 或本地路径"，AI 将内容保存到 `textbook/` 并注册到此表
- **切换教材**：用户在对话中说"切换到 X 教材"，AI 更新此表状态列
- **开始学习**：AI 读取此表，若有多个可选教材则让用户选择
