# 数据流水线设计（V1）

> 支撑第一版交互体验：全局上下文、时间筛选、地图模式。
> 创建时间：2026/01/17

## 目标

- 生成确定、可版本化的知识库，供可视化和检索使用。
- 即使抽取文本里的时间不完整，也能用数值年份支持全局时间导航。
- 为统一地点补全 WGS84 坐标，坐标统一保存为 `[lng, lat]`。
- 支持增量构建：只重跑变化部分，缓存自动保留，人工修正可覆盖自动结果。

## 范围（V1）

- 时间粒度只做到“年”。
- 公元前年份使用负数表示。
- 地理编码只对统一后的地点运行，主服务商为高德（Amap）。

## 输入

- `adapted_book.json`
  - 已分段的标准书籍文本。
  - 每个段落包含 `segment_start_time`，通常带有明确年份，例如 `（...、前295）`。
- `data/store/juan_*.json`
  - LLM 按卷/分块抽取后的缓存结果，由 `KnowledgeStore` 写入。

## 核心产物

### 1. 段落年份索引

- 文件：`data/segment_year_index.json`
- 键：`(juan_index, segment_index)`，实际写作 `${juan_index}-${segment_index}`
- 用途：
  - 为每个段落提供标准数值年份，支持时间筛选和缺失时间补全。
  - 稳定推导每卷起始年份。

示例结构：

```json
{
  "version": "v1",
  "cutoff_year": -1,
  "generated_at": "...",
  "segments": {
    "1-1": {
      "juan_index": 1,
      "segment_index": 1,
      "segment_start_time_raw": "威烈王二十三年（戊寅、前403）",
      "year": -403,
      "parse_method": "regex:前(\\d+)",
      "confidence": 1.0
    }
  }
}
```

规则：

- 解析失败时 `year` 为 `null`，`parse_method` 为 `null`，`confidence` 为 `0.0`。
- 人工修正放在 `data/segment_year_overrides.json`，由 `scripts/build_segment_year_index.py --overrides ...` 应用。

人工修正示例：

```json
{
  "version": "v1",
  "notes": "...",
  "overrides": {
    "252-2": {
      "year": 871,
      "reason": "..."
    }
  }
}
```

### 2. 卷起始年份索引

- 文件：`data/juan_year_index.json`
- 用途：让前端能在卷范围 `juanRange` 与年份范围 `yearRange` 之间做联动。

示例结构：

```json
{
  "version": "v1",
  "generated_at": "...",
  "juan_start_year": {
    "1": -403,
    "2": -402
  }
}
```

### 3. 统一知识库

- 文件：`data/unified_knowledge.json`
- V1 需要补充的字段：
  - 关系年份：
    - `first_interaction_year: number | null`
    - `last_interaction_year: number | null`
  - 事件缺失时间时的补全年份：
    - `imputed_time_start: number | null`
    - `imputed_time_end: number | null`

### 4. 地理编码缓存

- 文件：`data/location_geocoding.json`
- 键：统一地点的 `id` 或 `canonical_name`
- 坐标标准：
  - WGS84
  - JSON 中统一写作 `[lng, lat]`

示例结构：

```json
{
  "version": "v1",
  "provider": "amap",
  "generated_at": "...",
  "locations": {
    "晋阳": {
      "location_id": "晋阳",
      "canonical_name": "晋阳",
      "modern_name": "太原",
      "query": "太原",
      "coordinates": [112.5489, 37.8706],
      "confidence": 0.9,
      "source": "amap",
      "evidence": "amap geocode match",
      "needs_review": false,
      "updated_at": "..."
    }
  },
  "overrides": {
    "晋阳": {
      "coordinates": [112.5489, 37.8706],
      "notes": "manual override"
    }
  }
}
```

规则：

- `coordinates` 永远是 WGS84，顺序永远是 `[lng, lat]`。
- 当 `needs_review=true` 时，`coordinates` 应保持为 `null`，避免把不确定坐标当成权威结果。可选记录：
  - `candidate_coordinates`
  - `candidate_count`
  - `info`
  - `infocode`
  - `attempts`

## 本地构建顺序

1. `uv run python scripts/build_segment_year_index.py --overrides data/segment_year_overrides.json`
2. `uv run python scripts/build_juan_year_index.py`
3. `uv run python entity_resolution.py --store-dir data/store --output data/unified_knowledge.json`
4. 可选：`uv run python scripts/geocode_locations_amap.py`
5. 可选：`uv run python scripts/merge_geocoding_into_unified_kb.py`
6. `uv run python scripts/validate_artifacts.py`
7. 把前端需要的运行时数据发布到 `visualization/public/data/`

第 3 步依赖 `data/store/juan_*.json`。这些文件由 LLM 抽取阶段生成，干净检出仓库后可能不存在。

## 阶段说明

### A. LLM 抽取

- 脚本：`knowledge_extraction.py`
- 读取：`adapted_book.json`
- 写入：`data/store/juan_*.json`

说明：抽取提示词不负责输出坐标，坐标统一交给地理编码阶段处理。

### B. 构建段落年份索引

- 输入：优先使用 `adapted_book.json`，也可以从 `data/store/juan_*.json` 读取 `segment_start_time`
- 输出：`data/segment_year_index.json`

解析规则：

1. `公元前(\d+)` -> `year = -N`
2. `前(\d+)` -> `year = -N`
3. `公元(\d+)` -> `year = +N`
4. `（...、(\d{1,4})）` 或 ASCII 括号形式 -> 默认 `year = +N`

质量约束：

- 同一卷内，年份应随段落索引非递减。
- 跨卷时，卷起始年份应符合《资治通鉴》的整体时间顺序。
- 违反约束的案例进入人工修正文件，而不是在代码中写死。

### C. 构建卷起始年份索引

- 输入：`data/segment_year_index.json`
- 输出：`data/juan_year_index.json`

规则：

- 优先取 `(juan, segment=1)` 的年份。
- 若首段年份缺失，则退回取该卷所有段落中的最小可用年份。

### D. 实体融合与统一知识库

- 脚本：`entity_resolution.py`
- 读取：`data/store/juan_*.json`
- 写入：`data/unified_knowledge.json`

补全规则：

- 事件：
  - 能从 `event.time` 解析出年份时，保留为 `time_start`。
  - 无法解析时，根据事件出现的卷/段，从段落年份索引补出候选年份。
- 关系：
  - 优先解析 `action.time`。
  - 解析失败时，通过每个动作的 `(juan_index, segment_index)` 查段落年份。
  - 统一关系上聚合出 `first_interaction_year` 与 `last_interaction_year`。

### E. 地点地理编码

- 输入：`data/unified_knowledge.json` 中的地点
- 输出：`data/location_geocoding.json`

配置：

- 从 `.env.sample` 复制 `.env`，填入 `AMAP_KEY`。

脚本：

- 生成或更新缓存：`uv run python scripts/geocode_locations_amap.py`
- 回填统一知识库：`uv run python scripts/merge_geocoding_into_unified_kb.py`

流程：

- 每个统一地点生成查询词，优先使用 `modern_name`，否则使用 `canonical_name`。
- 调用高德地理编码接口。
- 归一化为 `[lng, lat]`。
- 多候选、低置信度或位置明显不合理时标记 `needs_review`。
- 人工覆盖始终在最后应用。

前端只读取回填后的统一知识库，不直接调用 LLM 或地理编码服务。

## 版本与增量构建

- 每个产物包含：
  - `version`
  - `generated_at`
  - 输入哈希（V1 可选）
- 增量策略：
  - LLM 抽取已通过 `KnowledgeStore` 按分块缓存。
  - 段落年份索引是确定性产物，可以低成本重算。
  - 地理编码缓存只追加或更新，不应清空已有人工修正。

## V2 待决问题

- 更稳健地处理公元/公元前混合记法。
- 历史地名消歧：结合朝代、区域约束和多候选排序。
- 坐标准确性：现代坐标与古地理位置之间需要明确标注差异。
