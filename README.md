# 资治通鉴-文白对照数据-人工智能辅助理解-交互式史书

> 🚀 **强烈推荐先点这里在线体验：<https://zztj.wawuyu.cn>**
>
> 建议从「关系网络」「地图」开始探索，交互体验最佳。

## 更新记录

- **2026.1.17**
    - **前端可视化（visualization）**
        - URL 全局状态同步与历史语义（更稳定的跳转/回退体验）
        - 范围驱动视图（按卷/年份范围过滤事件、地点等），详情交互增强
        - 新增“地图”Tab（Leaflet + OpenStreetMap），地点可一键在地图中查看并高亮定位；地点列表支持搜索
        - 时间轴重构为“时间点列表 + 右侧事件列表”，更适配事件密集年份
        - 关系网络详情增强：人物详情/关系详情中展示“相关事件”，点击可直接打开事件卡片
        - 顶部增加 GitHub 入口与 Star 数展示（更方便关注/收藏）
        - 构建验证步骤补充（任务完成后可复现验证）
    - **数据与流水线**
        - 统一知识库与类型定义完善（canonical artifact / unified KB types）
        - 地点地理编码：高德(Amap)缓存与回填坐标流程
    - **工程化与文档**
        - 多处结构/可读性重构与健壮 JSON 解析复用
        - 任务地图与 UX 规范补充与更新；README 增加地图 Demo 截图

## 效果预览（阶段性成果）

| 主界面（时间轴） | 核心能力：人物关系网 |
| --- | --- |
| ![主界面与时间轴](https://github.com/JY0284/zizhitongjian/blob/main/demo/main_page_and_events_timeline.png) | ![关系网络](https://github.com/JY0284/zizhitongjian/blob/main/demo/relation_network_1.png) |

- **时间轴**：事件密集时自动聚类；支持缩放/平移/搜索
- **人物关系网**：点击人物/关系查看详情与交互事件（体现结构化的核心成果）
- **地点**：地点列表与详情，串起相关人物与事件

## 文白对照阅读
[阅读书籍点击](https://jy0284.github.io/zizhitongjian/chapters/001_资治通鉴第一卷(周纪).html)

## 简介
项目地址：[zizhitongjian](https://github.com/JY0284/zizhitongjian)

这个仓库是有关**资治通鉴-文白对照**的可供**人类和机器阅读阅读**并进行**相关数据研究**的项目。

本项目中的文本格式按照原书的`卷`进行整理，`chapters`目录下按照`[0-9]+_资治通鉴卷名.md`进行分别存储：

```shell
chapters
├── 001_资治通鉴第一卷(周纪).md
├── 002_资治通鉴第二卷(周纪).md
├── 003_资治通鉴第三卷(周纪).md
...
```

每一卷的内容格式如下（`*`表示在部分卷中可能不存在的内容）：

```python
[卷名]*

[时间原文]
[时间译文]

[空白][空白][原文]
[空白][空白][译文]

[空白][空白][原文]
[空白][空白][译文]

[时间原文]
[时间译文]

[空白][空白][原文]
[空白][空白][译文]
```

## 结构化数据
结构化数据已由`model.py`生成，其中的数据结构及生成过程可见于`model.py`。结构化数据保存于`data.json`（[结构化数据文件](https://github.com/JY0284/zizhitongjian/blob/main/data.json)）。数据读取和使用样例请见`data_usage_demo_visualization.ipynb`（[结构化数据使用样例](https://github.com/JY0284/zizhitongjian/blob/main/data_usage_demo_visualization.ipynb)）。

## 资治通鉴数据应用样例：交互式历史可视化系统

本项目新增了基于 React + D3.js 的现代化交互式可视化系统，位于 `visualization` 目录下。该系统提供了更加流畅、直观的历史数据探索体验，帮助读者从时间、空间、人物关系等多个维度深入理解《资治通鉴》。

### 主要功能展示

#### 1. 交互式历史事件时间轴 (Interactive Timeline)
全新的时间轴组件支持智能聚类、缩放平移、全局概览及实时搜索。
- **主界面与时间轴概览**：
![主界面与时间轴](https://github.com/JY0284/zizhitongjian/blob/main/demo/main_page_and_events_timeline.png)
- **时间轴细节交互**：
![时间轴细节](https://github.com/JY0284/zizhitongjian/blob/main/demo/time_line.png)

#### 2. 复杂人物关系网络 (Relation Network)
通过力导向图展示人物之间的复杂关系，支持点击节点查看人物详情，点击连线查看具体交互事件。
- **关系网络全景**：
![关系网络](https://github.com/JY0284/zizhitongjian/blob/main/demo/relation_network_1.png)
- **人物详情查看**：
![人物详情](https://github.com/JY0284/zizhitongjian/blob/main/demo/relation_network_node_detail.png)
- **关系细节查看**：
![关系细节](https://github.com/JY0284/zizhitongjian/blob/main/demo/relation_network_edge_detail.png)

#### 3. 历史地理与地点 (Historical Locations)
展示历史地名及其相关事件，支持查看地点详情。
- **地点列表**：
![地点列表](https://github.com/JY0284/zizhitongjian/blob/main/demo/location_list.png)
- **地点详情**：
![地点详情](https://github.com/JY0284/zizhitongjian/blob/main/demo/location_list_node_detail.png)
- **地图模式（OpenStreetMap）**：
![地图模式](https://github.com/JY0284/zizhitongjian/blob/main/demo/map_view.png)

### 本地启动方法

如果您想在本地运行该系统：

```bash
cd visualization
npm install
npm run dev
```

## Local Development

This repository has two layers:

1. Corpus and pipeline: Markdown chapters, structured book JSON, extraction models, and artifact builders.
2. Visualization: a React app that reads generated runtime JSON from `visualization/public/data/`.

### Python checks

```bash
uv run pytest -q
uv run python scripts/validate_segment_year_index.py --fail
```

### Frontend checks

```bash
cd visualization
npm install
npm run build
```

### Runtime data

The visualization expects:

- `visualization/public/data/unified_knowledge.json`
- `visualization/public/data/juan_year_index.json`

These files are generated artifacts and may be absent in a clean checkout. If they are not present, build or copy them from the pipeline output before starting the frontend.

### Local API keys

Local secrets live in ignored `.env`. Copy `.env.example` to `.env` for local-only configuration:

```bash
cp .env.example .env
```

Set `DEEPSEEK_API_KEY` only when running LLM extraction. `knowledge_extraction.py` reads process environment variables, so export the file before running extraction:

```bash
set -a
source .env
set +a
```

Set `AMAP_KEY` only when running geocoding. The geocoding script loads `.env` automatically. Never commit `.env`.

The default extraction model is `deepseek-v4-flash`. Set `DEEPSEEK_MODEL=deepseek-v4-pro` for reasoning-heavy extraction passes.

## 技术实现简述

为了支撑上述可视化系统，本项目构建了一套完整的知识提取与融合流程：

1.  **AI 知识提取 (Knowledge Extraction)**
    *   利用大语言模型对《资治通鉴》原文进行深度语义分析。
    *   自动提取**人物 (Roles)**、**地点 (Locations)**、**事件 (Events)** 及**人物关系 (Relations)**。

2.  **实体消歧与融合 (Entity Resolution)**
    *   **智能合并**：通过 Union-Find 算法，将同一人物的不同称呼（如“赵籍”、“赵侯”）自动合并为统一实体。
    *   **防误触机制**：内置黑名单机制，防止“王”、“臣”、“公子”等通用称谓导致错误合并。
    *   **人地分离**：特殊处理逻辑区分人名与国名（如区分“赵籍”与“赵国”），确保关系网络准确性。

3.  **统一知识库 (Unified Knowledge Base)**
    *   将分散在各卷的碎片化信息重组为时空连贯的结构化数据，支持跨卷检索与分析。

4.  **地点地理编码 (Geocoding)**
    *   使用高德(Amap)为 `data/unified_knowledge.json` 的地点补全 WGS84 坐标（`coordinates: [lng, lat]`）。
    *   配置：复制 `.env.example` 为 `.env`，填入 `AMAP_KEY`。
    *   运行：`python scripts/geocode_locations_amap.py` 生成缓存，然后 `python scripts/merge_geocoding_into_unified_kb.py` 回填坐标。
    *   速率控制：默认每次请求间隔 `0.25s`（可用 `--sleep` 调整），避免触发限流。
    *   无密钥也可预跑：不设置 `AMAP_KEY` 时会自动进入 `--simulate`（只写入 query/needs_review，不调用 API）。

## 项目进展

项目在持续更新，目前任务列表完成情况如下：
- [x] 文本内容获取
- [x] 格式化卷名，便于排序及查询
- [x] 时间数据的译文格式保持和原文格式统一
- [x] 去除不符合文白对照格式的空行、空格，使用统一的换行格式
- [x] 文本内容程序化校对，定位残缺和错误内容
- [x] 文本数据结构化，便于利用数据分析工具和可视化工具进行处理
- [x] 结构化数据使用样例
- [x] AI辅助理解及可视化样例
- [x] AI辅助获取全书知识图谱（人物、事件及其关系，以及在格式化数据中的精确定位）
- [ ] 对话交互式资治通鉴
- [ ] ...

数据预处理的部分源码及说明在本项目的`*.ipynb`中存档及更新。

如果有任何感兴趣的、想要这个项目做的，请随时、尽情建议！

## 参与贡献

1. 请随时、尽情在issue中提供任何意见建议，不限于文本内容、文本格式、数据结构、数据分析、数据可视化等任何主题；
2. 文本中有`[todo]`的地方为分析过程中发现的内容残缺的部分，可以参与校对和修复:D

## 相关资源
1. http://www.ziyexing.com/files-5/zizhitongjian/zizhitongjian_index.htm
2. https://ctext.org/wiki.pl?if=gb&res=548761&remap=gb
3. 卷28译文可参考：http://www.ziyexing.com/files-4/yywj-157.htm


## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JY0284/zizhitongjian&type=Date)](https://star-history.com/#JY0284/zizhitongjian&Date)
