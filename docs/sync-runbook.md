# Portal 完整同步手册

从 portal 根目录运行命令；自动生成物只通过源文件和生成器更新。只在同步门户或排查对应流程时读取。

## 同步流程

> 数据模块默认以 Hermes 云端 bridge 为 SSOT，通过 SSH 读取 `agentuser@43.132.146.234:127.0.0.1:8088`。
> 本地 `live-dashboard` / `bridge.py` 不需要启动；只有明确调试本地改动时才使用 `--source local`。

### Step 0: 日常收盘只跑统一入口

首页数据与每日市场手记是两条独立链路，且**顺序不能颠倒**（手记卡片与手记页都引用当日 PnL，先出手记会让卡片指向还没更新的首页）。日常收盘用统一入口一次跑完，顺序由脚本固定，不靠人记：

```bash
python3 tools/sync_portal.py --date YYYY-MM-DD --dry-run   # 预演，不写盘
python3 tools/sync_portal.py --date YYYY-MM-DD             # 依次执行 Step 1 与 Step 3.5
```

- 退出码：`0` 全成；`2` 首页数据失败（立即中断，不执行手记）；`3` 找不到当日 Vault ReviewNote；`4` 手记生成失败。另有 `--skip-reading`（只补首页）、`--allow-missing-reading`（当日复盘未写时只同步首页）、`--source local`（仅调试）。
- 首页数据写盘后会回读 `index.html` 内嵌 `PNL_DATA.summary.last_date`，与目标日期不符**只告警不阻断**：云端 PnL 未出数时首页就停在昨日，这条 WARN 是唯一信号。
- 定时入口 `~/Library/LaunchAgents/com.yimu.portal-sync.plist`（工作日 17:30 / 18:30，`--allow-missing-reading`）**需要在图形会话里装载**；非图形会话 `launchctl bootstrap` 会返回 `5: Input/output error`，此时手动跑 `sync_portal.py`，不要反复重试装载。

下面的 Step 1~Step 4.5 是逐步手册：排查单条链路、全量重建或新增生成器时按步执行。

### Step 1: 刷新数据模块（市场快照 + PnL 曲线）

```bash
python3 ~/Documents/YM_Capital/portal/tools/sync_pnl_data.py
```

从云端 bridge API 拉取 PnL 收益曲线 + 市场快照数据，嵌入 `index.html`。

**✔ 检查项**：确认输出显示同步来源与天数（如 "synced N PnL days + market snapshot from cloud:agentuser@43.132.146.234 → index.html"）。
若 SSH 或云端 bridge 不可用，会输出 `FAIL ... cloud bridge fetch failed`，此时先修云端或网络，不要改用旧数据。

脚本会更新：
- `PNL_DATA` 收益曲线数据
- 收益总览指标、日/周/月切换和指数对照数据
- `MARKET_SNAPSHOT_START/END` 内的今日市场状态卡片
- 市场更新时间和数据来源

本地调试模式：

```bash
python3 ~/Documents/YM_Capital/portal/tools/sync_pnl_data.py --source local
```

仅在本机已启动 `python3 scripts/bridge.py 8088` 且明确要看本地开发数据时使用。

### Step 2: 找差异

```bash
# Vault 中复盘笔记目录（按日期命名）
ls ~/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/复盘笔记/W*/ | grep "^[0-9].*_ReviewNote\.md$"

# portal 已同步的 HTML
ls ~/Documents/YM_Capital/portal/review-notes/ | grep "^[0-9].*\.html$"

# 对比：Vault 有 md 但 portal 无对应 html → 待同步
```

**✔ 检查项**：对比两列输出，确认待同步的笔记日期。若已有 HTML 但可能数据有误（如上次 5/20 误载 5/19 数据），需读 Vault md 验证内容一致性。

### Step 3: 转 HTML 并更新索引

对新笔记：

使用唯一生成入口 `convert_review.py` 自动转换
```bash
python3 ~/Documents/YM_Capital/portal/tools/convert_review.py <vault_md_path>
```

转换错误时修复生成器后重新生成；不提供手工转换并长期维护第二份页面的旁路。

`convert_review.py` 会同步更新：
- 首页“阅读最新复盘”按钮
- 常用入口“最新复盘”按钮
- 可审计交易链路的最新日期和记录跨度
- AI 复盘闭环的日报数量、最新复盘日期和近期 6 篇复盘卡片
- `review-notes/index.html` 的复盘归档、统计和最新日卡
- 复盘页 §二 心得与教训的认知卡样式（自动转成「可复用原则 / 当日证据 / 下次动作」）

同一天重复同步时，脚本应刷新详情页、首页卡片和归档页日卡，但不能重复增加统计数量。

§二 认知卡支持两种源格式：

```md
1. **[认知] 标题** — 内容
```

```md
### 今日认知

**1. 标题**

内容
```

**✔ 检查项**：
- 打开生成的 HTML 文件预览，核对顶部 chip 数据（情绪/涨跌停/持仓）与 Vault frontmatter 一致
- 大盘全景表、涨停结构表是否完整渲染
- 心得认知卡是否渲染为三层结构，卡片数量是否与 Vault §二 今日认知一致
- 规则教训、红方对抗轮次是否完整
- 首页近期复盘卡片显示上证、涨跌比、涨跌停、情绪值，且不截断
- 首页和详情页返回主页时能回到原进入位置

### Step 3.5: 生成每日市场手记

每日市场手记是公开阅读层，由 Vault ReviewNote 派生：

```bash
python3 ~/Documents/YM_Capital/portal/tools/convert_daily_note.py <vault_md_path>
```

可选地传入一句人工感受，作为「系统今天做了什么」的补充素材：

```bash
python3 ~/Documents/YM_Capital/portal/tools/convert_daily_note.py <vault_md_path> "今天真实感受..."
```

字段映射固定如下：

| Portal 字段 | ReviewNote 来源 | 说明 |
|---|---|---|
| 今日一句话 | §一 `### 一句话结论` | 首页摘要卡片和手记 hero 使用这句。 |
| 今日一个认知 | §二 `### 今日认知` 第一条 | 生成「今日一个认知 / 当日证据 / 下次动作」。 |
| 明日只看什么 | §三 `**总基调**` 或 `### 明日观察` | 只保留观察口径，不能变成公开买入号令。 |
| 今日市场状态 | frontmatter | 读取 `市场状态/赚钱效应/情绪值/上证涨幅/涨停家数/跌停家数/盘后持仓`。 |

`convert_daily_note.py` 会过滤 ticket、股数、成本、精确买卖指令、部分持仓标的。若 ReviewNote 缺 `一句话结论` 或 `今日认知`，先回到 ReviewNote 补源字段，不要在 Portal 里临时改 HTML 文案。

**✔ 检查项**：
- `daily-notes/YYYY-MM-DD.html` 已生成或刷新。
- `daily-notes/index.html` 归档只出现一次该日期。
- 首页 `#daily-notes` 最新卡片摘要来自 ReviewNote `一句话结论`。
- 页面无 ticket、股数、成本、精确买卖指令或未脱敏持仓细节。

### Step 4: 抽 insights

读 §二 心得中的认知条目，匹配 insights 9 主题的触发标签：
- 匹配成功 → 追加一句话摘要到 `insights/index.html` 对应卡片，计数 +1
- 匹配不上 → 保留原认知并列为待归类，继续其他同步；只有确需改变主题分类体系时才询问

当前 9 个主题为：资金合力、情绪与周期、选股与买点、建仓节奏、窗口节奏、尾盘与回勾、对手研究、对话与原则、操作评估。

新增认知写入时遵循新版阅读层：
- 列表第一层写「可复用原则」，不要把当日价格流水塞进标题
- 展开层写「证据与边界」，保留日期、个股、价格、资金等事实作为支撑
- 同步更新该卡片 footer 计数和首页对应认知卡计数

**✔ 检查项**：确认 insights 卡片计数已递增，新条目内容能在 portal 打开看到。

### Step 4.5: 发布前验证

同步和样式调整完成后，至少跑：

```bash
python3 tools/test_convert_review.py
python3 tools/test_convert_daily_note.py
python3 tools/test_sync_pnl_data.py
python3 tools/test_portal_pnl_kpi.py
python3 tools/portal_check.py --self-test
python3 tools/portal_check.py
git diff --check
```

前端视觉相关改动还必须用浏览器检查：
- 首页 `index.html#research`
- 最新复盘详情页 `review-notes/YYYY-MM-DD.html`
- 交易认知页 `insights/index.html`
- 桌面和约 390px 移动宽度都不能有横向溢出、文字重叠、空白卡片或计数不一致

### Step 5: 提交与推送

先展示 `git diff --stat` 与验证结果；没有提交/推送授权时询问，用户已明确授权则直接完成，不重复确认。
暂存本次明确文件，不使用全仓库暂存；已有无关改动保持原状。commit 与 push 按各自授权执行，push 后验证远端 SHA。

```bash
git diff --stat
git add -- <本次已核对文件路径>
git commit -m "sync: YYYY-MM-DD 复盘笔记 + insights 更新"
git push
```
