# literature-rag

给 AI 关键词 → 拿到真实文献 DOI → 导入 Zotero 指定分类。

```
关键词 ──检索──> 真实 DOI 列表 ──筛选──> 选中的 DOI ──入库──> Zotero（指定分类）
              ↑ 多源去重排序          ↑ 精筛 or 粗筛          ↑ 本地写插件 / Web API
```

- **检索**：并发查 Crossref / Semantic Scholar / OpenAlex / arXiv，按 DOI 去重、按「引用数 + 相关度」排序，返回真实 DOI（AI 不编造）。
- **筛选**：两种方式任选 —— **精筛**（AI 读摘要帮你判断）或 **粗筛**（AI 不读摘要，省 token，人工筛）。
- **入库**：默认本地写入插件（全本地、无需账号/API key），备选 Zotero Web API。

---

## 推荐：`litrag run`（一站式，最省 token）

DeepSeek 代读摘要，Claude 只看 verdict + 连续 DOI 列表，不再把摘要灌进上下文。

```bash
litrag run "planarian regeneration toxicity" --collection 涡虫毒理学
# 内部：search(4源去重) → dedup(剔库里已有) → DeepSeek 筛选 → 输出连续 DOI

litrag run "planarian regeneration toxicity" --collection 涡虫毒理学 --write   # 直接入库 include 的 DOI
```

需要 `DEEPSEEK_API_KEY`（或复用 Claude Code 的 `ANTHROPIC_AUTH_TOKEN`）。

---

## 先选筛选方式

### 方式 A：精筛（AI 读摘要）— `litrag search`

适合**条数少、要 AI 帮你精读摘要挑选**。AI 会把摘要读进上下文，帮你对比、推荐，你再勾选。

```bash
litrag search "planarian regeneration" --json          # AI 读摘要 → 展示排序列表
litrag import "10.xxx/..." --collection "涡虫毒理学"    # 你勾选后入库
```

### 方式 B：粗筛（AI 不读摘要）— `litrag coarse`

适合**条数多、要省 token、自己看摘要决定**。AI 只抓摘要+机翻写进一个 md 文件，**完全不读摘要**，人工筛选。

```bash
litrag coarse "planarian regeneration" --top 30              # 默认写到 ./litrag_coarse/
litrag coarse "planarian regeneration" --top 30 --no-translate   # 国内跳过机翻（更快，翻译列留空）
# → 你打开 md，看标题/年份/引用/摘要/机翻，在序号列打 √
# → 告诉 AI「筛好了」，AI 用 Grep 提取打勾序号 → 入库
```

### 对比

| | 精筛 `search` | 粗筛 `coarse` |
|---|---|---|
| AI 读摘要 | ✅ | ❌（只抓取不读） |
| token 消耗 | 高 | 低 |
| 谁筛选 | AI 辅助 + 你 | 纯人工 |
| 结果形式 | 终端列表 | md 文件（摘要 + 中文机翻） |

> ⚠️ **用英文关键词**：学术库主要索引英文，中文关键词效果差（「涡虫再生」会搜成农药残留；`planarian regeneration` 才命中真文献）。

---

## 安装（一次性）

### 1. 前置：让 Zotero 能写入

Zotero 7 的本地 API 是**只读**的，写入必须装插件（或用 Web API）。

1. Zotero 桌面版运行中 → **设置 → 高级** → 勾选 **「允许本机其他应用与 Zotero 通信」**（端口 `23119`）。
2. 装写入插件 `zotero-write-endpoint`（`.xpi` 已在本项目根目录，v1.0.5）：
   **Zotero → 工具 → 插件 → ⚙ → Install Plugin From File…** → 选 `.xpi` → **重启**。
   - 需重新下载：`https://github.com/Ayanya-0628/zotero-mcp/releases/download/plugin-latest/zotero-write-endpoint.xpi`（GitHub 不通可加 `https://ghfast.top/` 镜像前缀）。

### 2. 安装本工具

```bash
pip install -e .            # 本地检索 + 本地入库
pip install -e ".[web]"     # 额外装 pyzotero（Web API 后端）
```

### 3. 验证

```bash
litrag health   # 本地 API / 写插件 / 各检索源 全 OK 即可用
```

---

## 命令速查

```bash
litrag health                          # 自检
litrag run     "关键词" [选项]          # ★ 一站式：检索→去重→DeepSeek筛选→连续DOI（省token）
litrag search  "关键词" [选项]          # 精筛：检索，AI 读摘要
litrag coarse  "关键词" [选项]          # 粗筛：生成 md 表格，AI 不读摘要
litrag collections                     # 列出库内分类（key + 名称 + 父级）
litrag import  "DOI..." [选项]          # 按 DOI 入库
```

### `search` / `coarse` 共同选项

| 选项 | 默认 | 说明 |
|---|---|---|
| `--top N` | 20 / 30 | 返回条数 |
| `--min-citations N` | 0 | 只保留引用数 ≥ N |
| `--sources` | 全部 | 子集，如 `crossref,openalex` |
| `--json` | 关 | JSON 输出 |

`coarse` 额外有 `--out DIR`（md 输出目录，默认 `./litrag_coarse`）和 `--no-translate`（跳过机翻）。

### `import` 选项

| 选项 | 默认 | 说明 |
|---|---|---|
| `--collection` | 无 | 目标分类，**接受名字或 key** |
| `--backend` | `local` | `local`（写插件）/ `web`（Web API） |
| `--timeout` | 120 | 等待 Zotero 拉取元数据的秒数 |
| `--json` | 关 | JSON 输出 |

```bash
litrag import "10.1038/s41586-021-03819-2"                    # 入「我的文库」根目录
litrag import "10.1038/s41586-021-03819-2" --collection "涡虫毒理学"   # 按名字归类
litrag import "10.1038/s41586-021-03819-2" --collection "6YB2ZS5Y"     # 或直接给 key
```

导入结果每行一个状态：`added`（成功，附标题+条目 key）/ `duplicate`（库里已有）/ `error`（原因）。

---

## 端到端示例（精筛）

```bash
litrag health                                              # 1. 自检
litrag search "planarian regeneration" --min-citations 5 --top 10 --json   # 2. 检索
litrag collections                                        # 3. 看分类
litrag import "10.1146/annurev.cellbio.20.010403.095114" --collection "涡虫毒理学"   # 4. 入库
```

```
added      10.1146/annurev.cellbio.20.010403.095114  FUNDAMENTALS OF PLANARIAN REGENERATION [ABC12345]
duplicate  10.1126/science.1203983                    already in library (no new item)
```

---

## 粗筛流程详解（AI 不读摘要）

1. `litrag coarse "planarian regeneration" --top 30`（默认输出到 `./litrag_coarse/`）
   - 命令行打印**精简表**（序号/年份/引用/标题/DOI），**无摘要**。
   - 磁盘生成 md：`序号 / 文献名称 / DOI / 年份 / 引用数 / 摘要 / 摘要翻译`（摘要+机翻供人看）。
2. 你打开 md，在**序号列**打勾：`| 1 |` → `| √1 |`。
3. 告诉 AI「筛好了」。AI 用 `Grep -o "√\d+"` 提取勾选序号（**不读摘要、不读全文**），映射回 DOI 入库。

> 打勾不会导致缓存失效：AI 从不回读 md 全文，只用 Grep 提取序号。若不想改文档，也可直接说「第 3、7、15 行」。

摘要翻译后端可选（免费 SiliconFlow / DeepSeek / translatepy），见「模型与翻译切换」；配好免费 key 后中文机翻自动填，不进 AI、不花 token。

---

## Web API 后端（备选，需 Zotero 账号）

不想装插件、或希望 Zotero 未运行时也能写入（下次打开自动同步）时用：

1. 到 <https://www.zotero.org/settings/keys> 生成 API key（勾选读写权限），记下 library ID。
2. ```bash
   export ZOTERO_LIBRARY_ID=1234567
   export ZOTERO_API_KEY=xxxxxxxxxxxxxxxx
   litrag import "10.xxx/..." --backend web --collection "分类名"
   ```

> 限制：Web API 不支持 arXiv id；`--collection` 只能匹配**顶层**分类。

---

## 分享给朋友（在另一台电脑部署）

打包分享时先**排除**这几个目录（非代码，且含你的检索数据）：

- `archives/` — 检索结果缓存（含摘要）
- `literature_rag.egg-info/` — pip 安装产物
- `__pycache__/` — 字节码缓存

朋友拿到后，按上面「安装（一次性）」走一遍（装 Zotero + 开本地 API + 装 `.xpi` 插件 + `pip install -e .`），只多一步——**配自己的 API key**：

```bash
export DEEPSEEK_API_KEY="sk-你的key"
litrag health    # 看到 `DeepSeek key: OK` 即可用
```

> ⚠️ **模型名要对上**：本项目默认 `deepseek-v4-flash`（走 `api.deepseek.com/anthropic` 兼容端点），这是为原作者的后端调的。若朋友的账号没有这个模型名，筛选会报「模型不存在」，需再设：
>
> ```bash
> export DEEPSEEK_MODEL="你账号实际提供的模型名"   # 例如标准账号的 deepseek-chat
> ```
>
> 若朋友用的是**别的服务**（原生 Anthropic / OpenAI 等），请求协议与本项目的 DeepSeek 兼容格式不同，无法只换 key 就用，需改 `literature_rag/screen.py`。
>
> `.claude/` 目录（Claude Code 技能）只有朋友也用 Claude Code 时才需要，可留可删。

---

## 模型与翻译切换（可选）

本项目有两处调用外部模型，都用环境变量控制，默认值已调好。

### 1. 筛选模型（`run` 里 DeepSeek 读摘要）

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 复用 `ANTHROPIC_AUTH_TOKEN` | 筛选 key（设了优先用） |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 模型名，换账号/服务时改 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/anthropic` | 兼容端点 |

> 换**原生 Anthropic / OpenAI** 等协议不能只换 key，要改 `screen.py`。

### 2. 翻译后端（`coarse` 的摘要机翻）

按「**有 key 走免费 API，无 key 回退 translatepy**」自动选：

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `SILICONFLOW_API_KEY` 或 `LITRAG_TRANSLATE_KEY` | 无 | 设了就走 OpenAI 兼容端点 |
| `LITRAG_TRANSLATE_BASE_URL` | `https://api.siliconflow.cn/v1` | 换服务时改 |
| `LITRAG_TRANSLATE_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | 免费模型；换 DeepSeek 等时改 |

- **真免费（推荐）**：硅基流动免费模型 `Qwen/Qwen2.5-7B-Instruct`。注册 <https://cloud.siliconflow.cn> 拿 key，`setx SILICONFLOW_API_KEY "sk-xxx"` 即可。
- **更准（便宜）**：换 DeepSeek —— 设 `LITRAG_TRANSLATE_KEY` + `LITRAG_TRANSLATE_BASE_URL=https://api.deepseek.com/v1` + `LITRAG_TRANSLATE_MODEL=deepseek-chat`。
- **都不设**：回退 translatepy（爬 Google，国内基本超时留空）。

> **怎么判断免费还是付费**：模型广场看「免费」标签 / 账单页看是否 ¥0；免费模型在 ¥0 余额账号上能成功，付费模型会报「余额不足」。

---

## Claude Code 技能：怎么触发

`.claude/skills/literature-search/SKILL.md` 是给 Claude Code 用的技能。装到全局（`~/.claude/skills/`）后任何目录都能触发。

- **自动触发**：Claude 根据技能的 `description` 字段匹配你的意图，自然语言说出下面这类话就会自动加载：
  - 「帮我找一下 **X 方面** 的文献 / 论文」
  - 「查 **X** 主题，导进 Zotero」
  - 「搜一下 **planarian regeneration** 的文献并入库」
  - 「帮我做个 **X** 方向的文献粗筛 / 精筛」
- **手动触发**：输入 `/literature-search`。
- **触发后**：Claude 把你的主题压成 3-5 个英文词 → 跑 `litrag run` → 只转述 DOI 列表 + include/uncertain 数量，不读摘要。

> 不用 Claude Code 的朋友可删 `.claude/` 目录，不影响 CLI 本身。

---

## 常见问题

- **`Read timed out`？** Zotero 拉 CrossRef 元数据走代理较慢，默认 120s，用 `--timeout 180` 调大。超时不代表失败，条目可能已写入，先去 Zotero 里看一眼再重试。
- **Semantic Scholar 报 429？** 未认证限速 ~1 rps，已内置重试；想稳定可加免费 API key。
- **检索返回 0 篇、或大量 SSL / 超时 / 502？** 学术 API（Crossref / OpenAlex / Semantic Scholar / DeepSeek）在国内可**直连**，本地代理（Clash）抽风时反而会 SSL 断 / 502 / 超时。已内置「直连优先、代理回退」，通常自动恢复；arXiv 需走代理，也由回退兜住，**无需手动配 `NO_PROXY`**。
- **DeepSeek 筛选全标 uncertain 且 reason 为空？** `deepseek-v4-flash` 是推理模型，已用 `thinking: disabled` 关推理并提高 max_tokens；若仍出现，多为网络波动导致响应截断，代码会自动重试一次。
- **重复导入？** Zotero 会检测重复并跳过，返回 `duplicate`。
- **没归类成功？** `--collection` 接受名字或 key，先用 `litrag collections` 确认分类存在。
- **中文关键词搜不到对的？** 用英文关键词（见「先选筛选方式」）。
- **粗筛翻译列是空的？** 国内没配免费 key 时 translatepy 会超时。设 `SILICONFLOW_API_KEY`（免费）或加 `--no-translate` 跳过。见「模型与翻译切换」。
- **想换筛选/翻译模型？** 见「模型与翻译切换」的环境变量表。

---

## 项目结构

```
literature_rag/
  search.py          # 多源检索、去重、排序
  screen.py          # DeepSeek 摘要筛选（Claude 不读摘要，省 token 核心）
  run.py             # 一站式：search→dedup→screen→连续DOI→入库
  _http.py           # 直连优先、代理回退的请求封装（绕开抽风代理）
  coarse.py          # 粗筛：生成 md 表格 + 精简表
  translate.py       # 摘要机翻（translatepy 或免费 SiliconFlow，不进 AI）
  import_zotero.py   # local(写插件) / web(pyzotero) 双后端
  zotero_api.py      # 列分类、名字→key 解析、库内已有 DOI
  sources/           # crossref / semantic_scholar / openalex / arxiv
  cli.py             # run / search / coarse / import / collections / health
.claude/skills/literature-search/SKILL.md   # Claude Code 技能（编排 run 流程）
```

---

## 已知限制

- 检索靠学术 API，关键词匹配有噪声（如 "Attention Is All You Need" 会命中大量标题党/假 DOI）——这正是「先审后入」的意义。
- 排序为「log 引用数 + 相关度」简单加权；语义重排由 Claude 在 Skill 层把关。
- arXiv 结果无 DOI 时用 `arxiv:<id>` 作 key，仅本地后端支持导入。
