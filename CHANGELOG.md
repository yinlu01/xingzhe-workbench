# 行者工作台更新日志

## [2026-08-27] fix(reading): 在读书目接入微信读书在读

### 修复
- 「在读书目」模块之前只读手动书目（`wb_life_books`，仅一条旧的"AI产品经理实战"），未反映真实在读。改为**优先显示微信读书 `inProgressBooks`**（含进度百分比 + 最近读日期），无微信读书数据时 fallback 手动书目。

---

## [2026-08-27] fix(plan): 计划章节与游标一致性自愈

### 修复
- 新增 `ensurePlanForDate` 的**章节一致性自愈**：今天的读书/学习任务若与游标指向章节不一致（游标回退但计划仍是旧章节），自动失效重算，避免「游标和计划割裂」。
- 根因：之前 `ensurePlanForDate` 看到今天计划已是新 schema（v=3）就直接返回，游标变化后计划不跟着重算，导致首页今日概览等展示旧章节。

---

## [2026-08-27] fix(plan): 修复游标迁移误判 + 学习任务游标化

### 修复
- **游标迁移误判**：`migrateReadingCursor` 之前会把「今天的 done=True」也计入（多为微信读书自动打卡，不代表真正读完当前章节），导致游标跳到第 7 讲。修复：迁移时**跳过今天**，只统计历史真实完成的章节（→ 正确指向第 4 讲）。
- **学习任务游标化**：`ensurePlanForDate` 的 study 生成之前仍用旧顺延 `roll.study`（与 agent 游标矛盾），现改为直接用 agent 游标（`getTodayAgentInfo` 返回的当前学习日）。`planRolloverFrom` 已无调用（保留为死代码）。

---

## [2026-08-27] refactor(plan): 读书/学习计划改为「进度驱动」（整体平移）

### 背景
昨天的「顺延」只是单天顺延前一天，且读书章节仍由 `update_today.py` 按日历推进 `todaySchedule`——导致没读的章节被跳过、进度跳号（如今天跳到第 6 讲，实际应补第 4 讲）。用户要求的正确逻辑是：**未打卡就停留，后续整体往后平移**。

### 核心改动（进度游标）
- 读书、学习各维护一个「进度游标」（`reading_cursor` / `agent_cursor`）：**只有打卡完成才前进，未打卡停留** → 整体平移。
- 读书：新增 `buildReadingSequence()`（展平 67 周章节、跳过复习/休息）、`getTodayReadingChapter()`、`advance/rewindReadingCursor()`。`getTodayPlanInfo` / `ensurePlanForDate` / 读书页 hero / 首页 mini 卡**统一读游标章节**，废除 `todaySchedule` 割裂数据源。
- 学习（agent）：新增 `agent_cursor`（rest 日自动跳过）、`advance/rewindAgentCursor()`；`getTodayAgentInfo` 改为读游标（不再按日期匹配）。
- 打卡联动：规划页勾选 / 读书卡标记 / 微信读书自动打卡 / Agent 卡打卡，都会让游标前进；取消则回退。
- 迁移：首次运行自动初始化游标（读书游标从历史「最后完成章节」推断 → 第 4 讲；学习游标从打卡记录推断）。
- `PLAN_SCHEMA` 2→3，旧缓存自动失效重算。

---

## [2026-08-27] fix: 微信读书数据清零 + 读书章节错位

### Bug 1：微信读书数据清零
- **现象**：本月/本周/累计阅读时长、书架、笔记全部变为 0/空。
- **根因**：`weread_sync.py` 的 `call_api` 失败时返回空 dict，且无失败防御；8/27 08:44 定时同步时 API 瞬时返回空，脚本用空数据 `--save` 覆盖了 `weread_data.json`。
- **修复**：书架返回空（API 异常 / Key 失效 / 网络抖动）时 `sys.exit(1)` 中止，不再覆盖本地数据。数据已重新同步恢复（累计 137h58m / 本月 6h45m）。

### Bug 2：读书章节错位（今天显示第 5 讲，应为第 6 讲）
- **现象**：8/27（周四）读书显示「第 5 讲」（周三内容）。
- **根因**：`update_today.py` 由「行者创业系统每日读书提醒」在每天 21:00 才调用，导致当天白天 `todaySchedule` 还是昨天的，`ensurePlanForDate` 用昨天章节生成了今日计划。
- **修复**：新增「读书计划每日推进（凌晨）」自动化（每天 00:05 运行 `update_today.py`），确保当天一开始章节即正确；已手动推进 `todaySchedule` 到「第 6 讲 · 资本市场与直接融资」，App 自动刷新机制（`planRefreshToday`）已同步修正今日计划。

---

## [2026-08-26] feat(reading): 最近读书笔记接入微信读书 + AI 每日总结

### 问题
首页「最近读书笔记」模块只读 `wb_life_notes`（手动笔记，仅 2 条、停在 8/12），近期在微信读书的笔记/划线从未同步进来，导致模块「压根不更新」。

### 改动
- **数据层（`weread_sync.py`）**：新增 `fetch_recent_notes()`，拉取最近 8 本有笔记的书的划线（`/book/bookmarklist`）与想法（`/review/list/mine`）正文，过滤近 14 天，产出 `recentNotes` 字段（含 bookId/title/chapter/text/time/type）到 `weread_data.json`。
- **前端（`mac-dashboard.html`）**：首页「最近读书笔记」改为 `renderHomeNotes()`，优先展示微信读书近期笔记（划线/想法带标签），无数据时 fallback 手动笔记；新增「AI 读书笔记总结」区块（`homeNotesSummary`）。`autoLoadWeReadData` 与 `autoRefreshData` 同步后联动刷新首页。
- **AI 每日总结**：新增 `weread_summary.json`（结构 `{date, generatedAt, summary, highlights}`），前端轮询加载；新建 WorkBuddy 自动化「每日读书笔记总结」（每日 22:30），扫描近 3 天笔记生成总结写回。
- `weread_summary.json` 已加入 `.gitignore`（个人数据）。

---

## [2026-08-26] fix(reading): 读书页 hero 接入顺延逻辑（全站扫描收尾）

### 修复
- **读书页 hero（`renderReadingPlan`）此前仍直接读 reading_plan.json 的今日章节，未体现顺延**——这是全站最后一处残留的旧数据源展示。修复：hero 顺延优先，今日有 rolled 读书任务时显示「⏳ 顺延 · 阶段 · 第X周」+ 顺延书目/章节，无欠账时正常显示计划新章节。
- `planRefreshToday()` 增加 `renderReadingPlan()` 联动，使读书页 hero 在数据就绪重算后即时更新。

### 全站扫描结论（「今日读书/学习任务」展示入口统一收敛）
| 展示入口 | 状态 |
|---|---|
| 首页 · 今日概览 banner | 已接入每日计划 |
| 首页 · 读书卡 | 已接入 |
| 首页 · Agent 学习卡 | 已接入 |
| 首页 · mini 计划卡 | 已接入 |
| 任务页 · 读书卡 | 已接入 |
| 读书页 · hero | 本次接入 |
| 规划页 · 日/周月/待办 | 本就读每日计划 |

至此，所有「今日该做什么」的展示统一由 `getTodayDailyTasks()`（每日计划，含顺延）驱动，`getTodayPlanInfo()`/`getTodayAgentInfo()` 仅保留为数据源与 fallback。

---

## [2026-08-26] fix(plan): 休息日不再误生成学习任务 + 顺延机制梳理加固

### 修复
- **休息日边界**：agent 计划含 12 个周六 `rest` 日，此前 `ensurePlanForDate` 的 study 分支只判断 `ag.today` 存在、未排除 `type==='rest'`，导致休息日误生成「学习」任务。修复：`else if(ag&&ag.today&&ag.today.type!=='rest')`。顺延欠账仍会补（rest 日若有前一天未完成的学习任务仍顺延），但休息日不再凭空生成新学习任务。
- 读书位边界此前已正确（周日 `rest` 不生成读书、周六 `review` 生成复习），本次仅补齐 study 位，使两个位在「顺延优先 + 休息日不新增」上完全对称。

### 梳理结论（顺延机制完整性）
- 数据流闭环：`renderAll → renderPlan/首页 → ensurePlanForDate → planRolloverFrom(前一天) → 生成今日晚间`；`loadReadingPlan/loadAgentPlan → planRefreshToday` 兜底数据未就绪；`PLAN_SCHEMA` 版本号兜底代码升级；`planSyncTodayFromCheckins` 保证打卡与每日计划双向一致。
- 一致性入口：首页今日概览 / 读书卡 / Agent 卡 / mini 计划卡 / 规划页，均收敛到 `getTodayDailyTasks()` 单一数据源。

---

## [2026-08-26] fix(plan+home): 首页今日概览同步顺延 + 修复计划被永久缓存

### 新增（首页统一读取每日计划）
- 首页「今日概览」、读书卡、Agent 学习卡、读书计划 mini 卡统一改为**优先读取每日计划（含顺延任务）**，不再各自独立读 reading_plan.json / agent_study_plan.json 的「日期推进式」数据，顺延后首页与规划页完全一致。
- 顺延任务在首页以 `（⏳ 延期）` 标记呈现；mini 计划卡在读书顺延时显示「昨日未完成 · 顺延至今日，先补旧账」。
- 新增 `getTodayDailyTasks()`（首页统一入口）、`planDetailBrief()`（清洗任务 detail 前缀后缀）、`planSyncTodayFromCheckins()`（打卡与每日计划双向同步）。
- 打卡入口（`checkPlanToday` / `togglePlanCheckIn` / 微信读书自动打卡）在标记后触发 `renderHome()`，首页概览即时刷新。

### 修复（关键：计划被永久缓存导致更新不生效）
- **根因**：`ensurePlanForDate` 在初始化时于 reading_plan.json / agent_study_plan.json 异步加载完成前就生成了「今天」计划，并被 `generated:true` 永久缓存；之后代码升级（含顺延逻辑）也**不会触发重算**，所以首页始终显示旧章节、顺延从未真正计算。
- **方案 1（schema 版本）**：给计划数据加 `PLAN_SCHEMA` 版本号（当前=2），`ensurePlanForDate` 检测到 `v` 不符即视为旧缓存强制重算——**单纯重启 App 也能让代码更新生效**。
- **方案 2（数据就绪后刷新）**：reading_plan.json / agent_study_plan.json 加载成功后调用 `planRefreshToday()` 主动让今日计划失效并重算，确保顺延与章节基于最新数据。
- **方案 3（保留上午/下午）**：重算时仅重建晚间例行，保留用户已添加的上午/下午任务（修复上一版 `delete` 整条导致自定义任务丢失的回归）。

---

## [2026-08-26] feat(plan): 任务滚动顺延机制

### 新增
- **滚动顺延（Rollover）**：前一天晚间「读书/学习」任务若未完成，将自动顺延到今日晚间计划中，**不会再被跳过**。做完旧的才能推进新内容。
- 顺延任务标记：卡片显示 ⏳ 延期标签，detail 注明「未完成 · 自 X/X 顺延」，卡片带有浅橙底色提示。
- 新增辅助函数 `planPrevDate()`（跨月/跨年安全）和 `planRolloverFrom()`（提取欠账任务）。

### 修复
- `ensurePlanForDate` 从「每日重置」改为「顺延优先」：有欠账时不生成今日同类型新任务，仅补充顺延旧任务；无欠账时正常生成今日计划。

### 技术改动
- `ensurePlanForDate` 结构重构：先生成 `roll`（欠账），再按「读书位/学习位」判断顺延或今日新任务。
- `renderPlanSlot` 增加 `rolled` 标记渲染（`.plan-roll-tag` + `.plan-task.rolled`）。
- CSS 新增 `.plan-roll-tag`（橙色虚线芯片）和 `.plan-task.rolled`（浅橙渐变底色）。

---

## [2026-08-25] fix(plan): 修复添加任务数据丢失 + IME 回车误触

### 修复
- **Bug 1（数据丢失）**：`planEnsureDay` 内部重新读取 localStorage 导致返回新对象，`planConfirmAdd` 保存的却是旧对象，任务从未持久化。修复：给 `planEnsureDay` 增加可选 `daily` 参数，让写入方传入同一对象。`planApplySuggestion` 一并修复。
- **Bug 2（IME 回车误触）**：中文输入法选字时按回车被误判为「提交」。修复：输入框 `onkeydown` 增加 `isComposing || keyCode === 229` 守卫，仅真正编辑完才提交。

### 体验优化
- 添加成功后自动滚动到新任务并播放 `plan-flash` 高亮动画，解决「加完看不到」的体验问题。

---

## [2026-08-25] feat(plan): 美化规划页视觉

### 设计改动
- **Hero 渐变横幅**：橙→紫→蓝微渐变背景，大号完成百分比（如 20%）+ 完成计数 + 进度条缓动动画。
- **三段时段身份色**：上午（太阳图标·橙色）、下午（时钟图标·蓝色）、晚上（月亮图标·紫色），每段实时显示 `完成数/总数`。
- **任务卡片**：左侧 3px 分类色轨（读书蓝/学习紫/运动绿/复盘橙），hover 微抬升。
- **AI 建议卡片**：加装饰性光晕。
- **周月视图**：卡片标题加上身份色图标芯片，日历今日日期改为实心橙色圆点。

---

## [2026-08-25] refactor(plan): 合并规划与待办 Tab + 日历密度优化

### 优化
- **日历密度**：日历格从正方形改为紧凑行式（38px 高，日期左/圆点右），月历+双卡片可一屏内放下；去噪音（精简图例提示）。
- **Tab 合并**：侧栏去掉独立「待办」入口（badge 移至规划），规划页新增「待办」子 Tab（日度/周月/待办三视图），原核心目标+待办清单完整移入。

---

## [2026-08-24] feat(plan): 时间规划模块 V1

### 新增
- 规划页面：支持日度（上午/下午/晚上分段）、周月（合并视图）、待办三子视图。
- 自动生成晚间例行计划：读书（来自 reading_plan.json）、学习（来自 agent_study_plan.json）、运动、复盘、昨日 AI 建议。
- 支持任务添加/删除/完成/时间修改，打卡状态自动回填。
- 日历视图：周高亮、今日高亮、任务圆点标记。
