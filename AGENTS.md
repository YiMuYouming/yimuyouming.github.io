# Portal — 公开阅读层工作入口

## 任务路由

- 日常复盘衔接先回 `../Market_Watch/docs/runbooks/daily-flow.md`；阅读、计划确认、展示发布分别恢复，不在 Portal 复制复盘顺序。

- “同步门户/同步今天门户/根据流程同步门户”：执行 `docs/sync-runbook.md` 完整流程：云端数据 → Vault 差异 → convert_review → convert_daily_note → insights → 验证与桌面/移动 QA → 摘要 → 按授权提交推送。
- **日常收盘的站内同步只跑统一入口 `tools/sync_portal.py`**（顺序固定：① 首页数据 → ② 复盘详情页 → ③ 每日市场手记；任一步失败即中断，见 sync-runbook Step 0）。上面的完整流程仍是排查与全量重建时的手册。
- 页面和样式调整：读 README、DESIGN.md 与相关实现；只改本次需要的生成器/源内容，不默认触发全量同步。
- 公开内容来源与 Portal 2.0 结构：`docs/PORTAL_2.0.md`；历史方案按需查阅。

## 内容与授权边界

- Vault ReviewNote 是每日复盘和市场手记的 SSOT；Portal 不直接从 Market Watch 过程笔记发布，不在 HTML 发明结论或改写事实。
- 显式 `daily_bundle_ref` 的阅读稿通过 shared review reader 校验包内机器输入，公开正文仍取当前阅读稿。无效包不得回退正文猜事实；机器包、封存原件和精确账户信息不进入公开文件。
- `tools/convert_review.py` 与 `tools/convert_daily_note.py` 是生成入口；先修源或生成器，再重新生成，不手工维护第二套转换结果。
- 公开页必须脱敏 ticket、股数、成本、精确买卖指令和未公开持仓细节；数据 freshness 与日期必须可核对。
- 数据同步默认从 Hermes 读取；本地开发数据仅用于明确调试，不用旧数据冒充今日云端事实。
- 既有完整提交/推送授权沿用，不重复确认；没有授权先完成可审阅结果再询问。明确暂存本次文件，不混入其他改动。
- insights 优先归入既有主题；不能合理归类时保留待归类项并继续其余工作，主题体系变化再确认。

## 验证与交付

- 同步任务完整验证清单见 runbook，包括转换、PnL、portal_check 和 git diff --check。
- 视觉/发布任务检查首页、最新复盘、insights，桌面与约 390px 移动端；检查溢出、重叠、空白、日期和计数。
- 纯文档改动只做适用的链接、契约及差异检查，不刷新线上数据或生成无关页面。
- 输出变更摘要、验证与未解决项；推送后回读远端 SHA。设计细节统一以 DESIGN.md 为准。
