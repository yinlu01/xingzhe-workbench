#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 agent_study_plan.json — 内置学习计划 加速版 12 周冲刺备战计划
数据来源: 内置学习计划
用户画像: AI PM 背景，Agent 概念/Prompt 有基础，代码偏弱 → 理论压缩自测，动手全保留、跑通优先
Day 1 = 2026-08-23 (周日, 直接开课，环境准备并入 Day 1), Week 12 结束于 2026-11-14
v3: 由 16 周计划压缩而来，2026-08-23 应用户要求当天开课
"""
import json
from datetime import date, timedelta

START = date(2026, 8, 23)  # Week 1 Day 1（周日开课，周循环为 周日~周六，周六休息）
OUT = "agent_study_plan.json"
VERSION = 3

PHASES = [
    {"name": "基础快筛", "weeks": "1", "desc": "LLM/Transformer 核心概念自测查漏（有基础，快节奏过）"},
    {"name": "核心技能", "weeks": "2-6", "desc": "Prompt 快筛 + RAG 完整实战 + Agent 设计模式 + LangGraph/MCP"},
    {"name": "进阶深度", "weeks": "7-8", "desc": "微调/对齐（概念精+轻实战）+ 推理优化 + 安全评估"},
    {"name": "项目实战", "weeks": "9-11", "desc": "三大项目：RAG 问答 / 多 Agent 协作 / 生产级 Agent 应用"},
    {"name": "冲刺备战", "weeks": "12", "desc": "高频题 + 项目深挖 + 系统设计 + 模拟演练"},
]

# 每周: {week, phase(1-based index into PHASES), title, days: [周一..周六 共6天], sunday: "周日主题"}
WEEKS = [
    {"week": 1, "phase": 1, "title": "LLM 核心概念快筛", "days": [
        {"topic": "Self-Attention 快筛自测", "tasks": ["读 Jay Alammar《The Illustrated Transformer》快速过一遍", "自测清单：QKV 计算、softmax(QK^T/√d_k)V、MHA/MQA/GQA 区别，答不上的点记入查漏清单", "顺手搭好 Python 环境（今天开课，环境并进来）"], "deliv": "查漏清单 v1"},
        {"topic": "架构细节快筛", "tasks": ["概念过：RoPE 位置编码、SwiGLU、RMSNorm、Pre-Norm", "重点理解 KV Cache 与 Decoder-Only 架构（高频考点）"], "deliv": "笔记：架构要点 + 考点"},
        {"topic": "训练侧快筛", "tasks": ["看 Karpathy《Let's build the GPT Tokenizer》", "梳理：BPE 分词、预训练流程、Scaling Laws 结论（Chinchilla 配比）"], "deliv": "笔记：训练侧知识地图"},
        {"topic": "解码策略（轻实验）", "tasks": ["用 API/本地模型跑 Temperature/Top-k/Top-p 对比实验", "整理主流模型对比表：GPT/Claude/Qwen/DeepSeek（MoE/MLA/GQA）"], "deliv": "实验记录 + 模型对比表"},
        {"topic": "架构串讲", "tasks": ["看 Karpathy《Let's build GPT》（理解为主，不强制跟敲）", "把查漏清单 v1 逐条补齐"], "deliv": "查漏清单清零"},
        {"topic": "实战：跑通 mini-GPT（跑通优先）", "tasks": ["克隆 nanoGPT，配置 PyTorch 环境跑通训练/推理", "改一个超参观察行为变化（不用手写）"], "deliv": "✅ 代码：nanoGPT 跑通记录"},
    ], "sunday": "休息日 · 轻量复盘"},
    {"week": 2, "phase": 2, "title": "Prompt/Context 快筛 + 上手", "days": [
        {"topic": "Prompt 技巧自测", "tasks": ["自测：few-shot 示例选择、CoT 变体、Self-Consistency/ToT", "只补不熟的点，熟的直接过"], "deliv": "提示词速查表"},
        {"topic": "ReAct + Function Calling（重点）", "tasks": ["学 ReAct：Thought→Action→Observation 循环", "吃透 Function Calling 的 schema 定义与调用模式（新增高频考点）"], "deliv": "笔记：ReAct + FC 要点问答"},
        {"topic": "Context Engineering 上下文工程", "tasks": ["学上下文组装/压缩/排序（Lost in the Middle）、缓存", "读仓库《Context Engineering上下文工程》（你的 Harness 经验可对照）"], "deliv": "笔记：上下文工程"},
        {"topic": "System Prompt 实战", "tasks": ["为复杂场景设计完整提示系统（客服 Agent / Code Review Agent）", "结合你 SKILL 工程经验做对照笔记"], "deliv": "✅ 完整 System Prompt 设计"},
        {"topic": "LangChain/LCEL 热身", "tasks": ["Python 环境装 LangChain，跑通第一个 LLM 调用链", "为后面 RAG/LangGraph 打代码底子"], "deliv": "代码：LangChain 入门 demo"},
        {"topic": "实战：生产级 Prompt 系统", "tasks": ["给自己的工作场景（如行者工作台/产品分析）写一套生产级提示系统并实测迭代"], "deliv": "✅ 项目：Prompt 系统实测报告"},
    ], "sunday": "休息日"},
    {"week": 3, "phase": 2, "title": "RAG 基础", "days": [
        {"topic": "文档处理与分块", "tasks": ["学固定长度/递归/语义/结构化分块策略", "实现文档处理管道（256-1024 token、10-20% 重叠）"], "deliv": "代码：文档处理管道"},
        {"topic": "Embedding 模型", "tasks": ["对比 BGE 系列（中文最佳）/GTE/text-embedding-3", "了解 MTEB/C-MTEB 评测"], "deliv": "实验：Embedding 对比"},
        {"topic": "向量数据库", "tasks": ["Chroma 实操", "学 HNSW/IVF 索引原理；了解 Milvus/Qdrant 选型"], "deliv": "代码：向量检索 demo"},
        {"topic": "搭建 Naive RAG", "tasks": ["串起 加载→分块→向量化→检索→生成 完整链路"], "deliv": "✅ 代码：Naive RAG"},
        {"topic": "混合检索", "tasks": ["实现 BM25 + 向量 + RRF 融合检索"], "deliv": "代码：混合检索"},
        {"topic": "RAG 评估", "tasks": ["学 RAGAs 四指标：Faithfulness/Answer Relevance/Context Precision/Recall", "构建评估测试集"], "deliv": "评估报告"},
    ], "sunday": "休息日"},
    {"week": 4, "phase": 2, "title": "高级 RAG", "days": [
        {"topic": "查询改写", "tasks": ["实现 Multi-Query 分解、HyDE、Step-back Prompting"], "deliv": "代码：查询改写模块"},
        {"topic": "重排序 Rerank", "tasks": ["集成 BGE-Reranker-v2（Cross-Encoder）", "对比召回-重排前后效果"], "deliv": "实验：重排效果对比"},
        {"topic": "多轮 RAG + 幻觉检测", "tasks": ["实现对话历史管理与指代消解", "实现基于 NLI 的幻觉检测 + 引用溯源"], "deliv": "代码：多轮 RAG + 检测"},
        {"topic": "系统集成 Advanced RAG", "tasks": ["组装混合检索+重排+改写+检测完整系统"], "deliv": "✅ 代码：Advanced RAG"},
        {"topic": "对比分析", "tasks": ["Naive vs Advanced 全指标对比（Recall@5 提升目标 15%）", "写对比分析报告（沉淀为项目素材）"], "deliv": "对比分析报告"},
        {"topic": "缓冲日 / 查漏", "tasks": ["补本周未完成的代码任务（代码偏弱，留缓冲）", "或预习 LangGraph 概念"], "deliv": "本周交付物补齐"},
    ], "sunday": "休息日"},
    {"week": 5, "phase": 2, "title": "Agent 设计模式", "days": [
        {"topic": "Agent 核心概念快筛", "tasks": ["读 Lilian Weng《LLM Powered Autonomous Agents》", "自测：规划/记忆/工具/行动四组件、Agent vs Chain（你有底子，快过）"], "deliv": "查漏笔记"},
        {"topic": "纯 Python 实现 ReAct Agent", "tasks": ["不用框架，纯 Python 实现 ReAct Agent", "处理最大步数/循环检测/超时"], "deliv": "✅ 代码：ReAct Agent"},
        {"topic": "Plan-and-Execute + Reflection", "tasks": ["实现计划-执行分离模式", "实现 Reflexion（跨轮）与 Self-Refine（轮内）"], "deliv": "代码：两种模式"},
        {"topic": "Multi-Agent 模式", "tasks": ["学 Supervisor/层级/辩论/群体四种模式", "画架构图；理解通信：直接消息/共享黑板/事件驱动"], "deliv": "笔记 + 架构图"},
        {"topic": "记忆系统", "tasks": ["实现短期（上下文）+ 长期（向量库/摘要/实体）记忆"], "deliv": "代码：Agent 记忆模块"},
        {"topic": "实战：完整工具型 Agent", "tasks": ["组装一个带工具+记忆的完整 Agent（可用工作台场景）"], "deliv": "✅ 项目：完整 Agent"},
    ], "sunday": "休息日"},
    {"week": 6, "phase": 2, "title": "LangGraph + MCP", "days": [
        {"topic": "LangGraph 基础 + ReAct", "tasks": ["学 State/Node/Edge/Graph 概念与官方教程", "用 LangGraph 图编排实现 ReAct Agent（支持循环）"], "deliv": "代码：LangGraph ReAct"},
        {"topic": "Supervisor 多 Agent", "tasks": ["实现 Supervisor + Worker 多 Agent 图"], "deliv": "代码"},
        {"topic": "HITL + 持久化", "tasks": ["实现人工审核节点与中断恢复", "实现 Checkpointing 持久化与 Streaming 流式"], "deliv": "代码"},
        {"topic": "MCP 协议实战", "tasks": ["学 MCP 规范：工具集成标准化", "实现一个 MCP 工具服务器（结合你的 SKILL 工程经验）"], "deliv": "代码：MCP Server"},
        {"topic": "Dify 快速验证 + A2A 概览", "tasks": ["用 Dify 低代码搭 RAG 应用（快速验证故事）", "了解 A2A 协议与三家 Function Calling 差异"], "deliv": "应用：Dify RAG + 笔记"},
        {"topic": "阶段复盘", "tasks": ["复盘阶段一二：Prompt/RAG/Agent/LangGraph/MCP", "整理各模块要点问答（重点：FC vs MCP）"], "deliv": "✅ 阶段复盘笔记"},
    ], "sunday": "休息日"},
    {"week": 7, "phase": 3, "title": "微调 + 对齐", "days": [
        {"topic": "SFT 基础", "tasks": ["学 SFT 流程与指令数据格式（instruction-input-output）", "了解全量微调 vs PEFT"], "deliv": "笔记：SFT 流程"},
        {"topic": "LoRA/QLoRA 原理", "tasks": ["推导 LoRA：冻结 W₀、ΔW=BA、r<<min(d,k)", "学超参：r 8-64、alpha 1-2r、target_modules；QLoRA 4-bit NF4"], "deliv": "笔记：LoRA 推导"},
        {"topic": "微调实战（跑通优先）", "tasks": ["用 LLaMA-Factory 跑通 Qwen 微调（跑通即可，不强求调优）", "构建 100+ 条指令数据集"], "deliv": "代码：微调跑通 + 数据集"},
        {"topic": "RLHF 概念", "tasks": ["学 SFT→偏好数据→RM→PPO 完整流程", "理解 KL 约束与 4 模型开销、Reward Hacking"], "deliv": "笔记：RLHF 端到端"},
        {"topic": "DPO/GRPO 原理", "tasks": ["推导 DPO：跳过显式 RM 转分类问题", "学 DeepSeek-R1 的 GRPO：组相对排序奖励"], "deliv": "笔记：DPO/GRPO"},
        {"topic": "技术综述", "tasks": ["梳理 RLHF→DPO→GRPO 演进时间线与取舍", "整理要点问答（PM 背景讲清 trade-off 是优势项）"], "deliv": "✅ 综述 + 要点问答"},
    ], "sunday": "休息日"},
    {"week": 8, "phase": 3, "title": "推理优化 + 安全评估", "days": [
        {"topic": "KV Cache + vLLM", "tasks": ["学 KV Cache/PagedAttention/Continuous Batching 原理", "vLLM 部署模型实操"], "deliv": "代码：vLLM 部署"},
        {"topic": "量化 + 压测", "tasks": ["GPTQ/AWQ 概念 + 跑一次量化推理", "基准测试：吞吐/延迟/显存（参数量×2B FP16 估算）"], "deliv": "基准测试报告"},
        {"topic": "Prompt Injection 攻防", "tasks": ["学直接/间接注入与防御：检测过滤、指令层级隔离、输出校验", "实现基础 Guardrails（Guardrails AI / NeMo）"], "deliv": "笔记 + 代码：Guardrails"},
        {"topic": "Agent 评估", "tasks": ["设计评估框架：任务成功率/步效率/工具调用准确率（LangSmith/AgentBench/GAIA）"], "deliv": "评估方案文档"},
        {"topic": "GraphRAG 上手", "tasks": ["GraphRAG：实体抽取→知识图谱→社区检测→Local/Global 检索"], "deliv": "代码：GraphRAG demo"},
        {"topic": "进阶段复盘 + 项目预热", "tasks": ["复盘微调/对齐/推理优化/安全", "规划项目1的个人化选题（结合产品经验选垂直场景）"], "deliv": "✅ 复盘 + 项目选题"},
    ], "sunday": "休息日"},
    {"week": 9, "phase": 4, "title": "项目1：RAG 知识问答系统", "days": [
        {"topic": "项目1设计", "tasks": ["设计架构：查询理解→混合检索→重排→生成→幻觉检测", "技术选型：LangChain+Milvus/Chroma+BGE+Qwen", "选题结合你的垂直领域知识（差异化亮点）"], "deliv": "项目设计文档"},
        {"topic": "开发①：索引管道", "tasks": ["文档处理管道 + 索引构建（多格式、结构化+语义分块）"], "deliv": "代码"},
        {"topic": "开发②：检索系统", "tasks": ["向量+BM25+RRF+重排+查询改写"], "deliv": "代码"},
        {"topic": "开发③：生成系统", "tasks": ["System Prompt、Lost-in-the-Middle 优化、引用溯源、NLI 幻觉检测"], "deliv": "代码"},
        {"topic": "开发④：前端 + 优化", "tasks": ["多轮对话 + Streamlit/Gradio 前端", "RAGAs 评估 + 模块 A/B 测试"], "deliv": "代码 + 评估报告"},
        {"topic": "项目1收尾", "tasks": ["README、文档、部署", "沉淀项目数据点（Recall 提升/幻觉率下降）"], "deliv": "✅ 项目1完成"},
    ], "sunday": "休息日"},
    {"week": 10, "phase": 4, "title": "项目2：多 Agent 协作系统", "days": [
        {"topic": "项目2设计", "tasks": ["定义 5 角色：Supervisor/Researcher/Analyst/Writer/Reviewer", "技术选型：LangGraph + 工具 + Checkpointing"], "deliv": "项目设计文档"},
        {"topic": "开发①：编排图", "tasks": ["实现 Supervisor + Worker 编排图（条件边流转）"], "deliv": "代码"},
        {"topic": "开发②：工具集成", "tasks": ["搜索/Python REPL/文件读写工具集成"], "deliv": "代码"},
        {"topic": "开发③：HITL + 持久化", "tasks": ["关键决策人工审核 + 断点恢复", "错误处理与重试机制"], "deliv": "代码"},
        {"topic": "项目2收尾", "tasks": ["测试、文档、部署"], "deliv": "✅ 项目2完成"},
        {"topic": "项目3设计", "tasks": ["系统架构：多模型路由/工具系统/记忆/安全/可观测性", "技术选型：LangGraph+FastAPI+Redis+pgvector"], "deliv": "架构设计文档"},
    ], "sunday": "休息日"},
    {"week": 11, "phase": 4, "title": "项目3：生产级 Agent 应用", "days": [
        {"topic": "开发①：路由 + 工具", "tasks": ["智能路由（意图→模型→工具）+ MCP 工具系统"], "deliv": "代码"},
        {"topic": "开发②：记忆系统", "tasks": ["短期上下文 + 长期摘要/实体记忆（Redis+pgvector）"], "deliv": "代码"},
        {"topic": "开发③：安全 + 可观测", "tasks": ["注入防御、PII 脱敏、审计日志", "LangSmith 追踪、延迟/成本监控"], "deliv": "代码"},
        {"topic": "项目3收尾", "tasks": ["Docker 容器化部署 + 文档"], "deliv": "✅ 项目3完成"},
        {"topic": "亮点提炼 + 简历", "tasks": ["三项目亮点提炼（多模型路由降本、完整安全栈、长期记忆）", "STAR 结构写进简历 + 量化指标"], "deliv": "简历初稿"},
        {"topic": "项目深挖预演", "tasks": ["每项目准备 8 个追问：Why/What/How/指标/挑战/取舍/改进/规模化"], "deliv": "深挖文档"},
    ], "sunday": "休息日"},
    {"week": 12, "phase": 5, "title": "冲刺备战", "days": [
        {"topic": "知识体系复盘", "tasks": ["复盘 50 道高频题：基础 10 + RAG 10 + Agent 10 + 微调对齐 10 + 推理优化 5", "画知识脑图"], "deliv": "知识脑图"},
        {"topic": "刷题①", "tasks": ["刷《八股文完整答案集》69 题", "刷牛客高频拷打题"], "deliv": "整理答案"},
        {"topic": "刷题② + 系统设计", "tasks": ["练 4 道系统设计：企业 RAG/多 Agent 客服/代码生成 Agent/LLM 推理服务", "按 5-10-15-5 分钟框架答题"], "deliv": "设计方案"},
        {"topic": "模拟演练", "tasks": ["完整模拟一轮（录音复盘 / 找伙伴 / 牛客）", "练 STAR 讲项目 + 先结论后细节"], "deliv": "演练复盘"},
        {"topic": "目标公司研究", "tasks": ["研究目标公司 JD 与面经（字节重工程/阿里 Qwen/腾讯混元/小红书多模态等）"], "deliv": "投递清单"},
        {"topic": "简历定稿", "tasks": ["简历定稿 + 投递准备（PM 转 Agent 工程师的差异化故事线）"], "deliv": "✅ 开始投递！"},
    ], "sunday": "🎉 计划完成 — 开始投递！"},
]

schedule = []
d = START
for wk in WEEKS:
    for i, day in enumerate(wk["days"]):
        schedule.append({
            "date": d.isoformat(), "week": wk["week"], "phase": wk["phase"],
            "dow": ["周日", "周一", "周二", "周三", "周四", "周五"][i],
            "type": "study" if i < 5 else "practice",
            "topic": day["topic"], "title": wk["title"],
            "tasks": day["tasks"], "deliv": day["deliv"],
        })
        d += timedelta(days=1)
    schedule.append({
        "date": d.isoformat(), "week": wk["week"], "phase": wk["phase"],
        "dow": "周六", "type": "rest", "topic": wk["sunday"],
        "tasks": [], "deliv": "", "title": wk["title"],
    })
    d += timedelta(days=1)

plan = {
    "name": "AI Agent 冲刺备战 12 周计划（加速版）",
    "version": VERSION,
    "source": "内置学习计划",
    "startDate": START.isoformat(),
    "endDate": schedule[-1]["date"],
    "totalWeeks": 12,
    "totalDays": len(schedule),
    "phases": PHASES,
    "schedule": schedule,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(plan, f, ensure_ascii=False, indent=1)

print(f"✅ {OUT} v{VERSION}: {len(schedule)} days, {START} → {schedule[-1]['date']}")
for s in schedule[:3]: print(" ", s["date"], s["dow"], s["type"], s["topic"])
print("  ...")
for s in schedule[-2:]: print(" ", s["date"], s["dow"], s["type"], s["topic"])
