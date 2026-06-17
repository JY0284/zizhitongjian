# 任务地图（V1）

> 用来串联 `design.md` 与 `data_pipeline.md` 的实现清单。
> 创建时间：2026/01/17

## 当前代码锚点

- 抽取：`knowledge_extraction.py`，通过 `knowledge_store.py` 写入 `data/store/juan_*.json`
- 融合：`entity_resolution.py`，写入 `data/unified_knowledge.json`
- 前端入口：`visualization/src/App.tsx`
- 筛选控件：`visualization/src/components/FilterControls.tsx`
- 类型定义：`visualization/src/types/unified.ts`

## 阶段 0：冻结数据契约

- [x] 1. 明确定义核心 JSON 结构
  - 输出：
    - `data/segment_year_index.json`
    - `data/juan_year_index.json`
    - `data/location_geocoding.json`
    - `data/unified_knowledge.json` 的关系年份字段和事件补全年份字段
  - 成功标准：后端脚本与前端类型引用同一套字段约定。
  - 触点：`data_pipeline.md`、`visualization/src/types/unified.ts`、`model/*`

- [x] 2. 明确全局时间策略
  - 输出：
    - 公元/公元前处理规则
    - `segment_start_time` 支持的正则格式
    - 解析失败时的“未知年份”行为
  - 触点：`data_pipeline.md`

## 阶段 1：时间基础

- [x] 3. 实现确定性的段落年份解析
  - 输出：从 `adapted_book.json` 生成 `data/segment_year_index.json`
  - 成功标准：
    - 大部分含 `前NNN` 或 `公元前NNN` 的段落能得到数值年份
    - 记录 `parse_method` 与 `confidence`
  - 触点：`scripts/build_segment_year_index.py`

- [x] 4. 增加年份顺序校验
  - 输出：校验器能发现同卷内年份倒退、跨卷起始年份异常等问题
  - 成功标准：异常时退出码非零，并打印可操作的案例
  - 触点：`scripts/validate_year_index.py`

- [x] 5. 构建卷起始年份索引
  - 输出：从 `data/segment_year_index.json` 生成 `data/juan_year_index.json`
  - 成功标准：每卷都有 `juan_start_year`，缺失时能被明确标出
  - 触点：`scripts/build_juan_year_index.py`

## 阶段 2：统一知识库时间增强

- [x] 6. 为统一关系增加数值年份
  - 输出：
    - `relations[*].first_interaction_year`
    - `relations[*].last_interaction_year`
  - 成功标准：前端关系网络不需要解析字符串即可按年份筛选
  - 触点：`entity_resolution.py`、`visualization/src/utils/unifiedDataProcessing.ts`

- [x] 7. 关系缺少年份时从段落索引补全
  - 输出：根据每个动作的 `(juan_index, segment_index)` 查找段落年份，并聚合到统一关系
  - 成功标准：相比只解析文本时间，年份覆盖率提升
  - 触点：`entity_resolution.py`、`data/segment_year_index.json`

- [x] 8. 增加事件补全年份字段

## 关键插入项：拆分非人物实体

- [x] 从 `Role` 中拆出政权/国家类实体
  - 输出：`data/unified_knowledge.json` 增加 `polities`，秦、魏、赵等不再混入人物
  - 触点：`model/polity.py`、`model/unified.py`、`entity_resolution.py`

- [x] 扩展学派和组织分类
  - 输出：
    - `schools`，如儒家、法家、道家、墨家
    - `organizations`，如丞相府、太尉、秦军
  - LLM 提示词增加 `entity_type`
  - 兜底规则按名称模式分类
  - 测试：`tests/test_entity_resolution.py`
  - 触点：
    - `model/role.py`
    - `model/school.py`
    - `model/organization.py`
    - `model/unified.py`
    - `prompts/sys_entity_relation_extraction.md`
    - `entity_resolution.py`

## 阶段 3：地点地理编码缓存

- [x] 9. 定义高德地理编码配置与密钥处理
  - 输出：明确 `AMAP_KEY` 等环境变量和限流策略
  - 成功标准：本地可运行，密钥不会被提交
  - 触点：`README.md`、`data_pipeline.md`

- [x] 10. 实现统一地点地理编码缓存
  - 输出：生成或更新 `data/location_geocoding.json`
  - 成功标准：
    - 不擦除已有条目
    - 坐标写为 WGS84 `[lng, lat]`
    - 多候选或低置信度时标记 `needs_review`
  - 触点：`scripts/geocode_locations_amap.py`

- [x] 11. 将地理编码结果回填统一知识库
  - 输出：`data/unified_knowledge.json` 中的 `locations[*].coordinates` 被填充
  - 成功标准：前端只读取统一知识库中的坐标
  - 触点：`scripts/merge_geocoding_into_unified_kb.py`

## 阶段 4：前端全局上下文与导航语义

- [x] 12. 让全局上下文进入 URL
  - 输出：`tab`、`juanRange`、`yearRange`、聚焦/选中对象进入 URL
  - 成功标准：
    - 刷新后恢复上下文
    - 分享链接能复现同一视图
  - 触点：`visualization/src/App.tsx`

- [x] 13. 实现浏览器历史策略
  - 输出：
    - 高频中间更新使用 `replace`
    - 用户提交后使用 `push`
  - 成功标准：浏览器前进/后退像上下文导航，而不是被拖拽过程污染
  - 触点：`FilterControls.tsx`、`Timeline.tsx`

- [x] 14. 关系网络支持 `yearRange` 筛选
  - 输出：边按数值年份筛选，节点由剩余边推导
  - 成功标准：关系网络与全局上下文一致
  - 验证：`cd visualization && npm run build`

- [x] 15. 增加卷范围与年份范围联动
  - 输出：修改其中一个范围时，同步或提示同步另一个范围
  - 成功标准：用户可以按卷或按年份导航，不产生明显困惑
  - 验证：`cd visualization && npm run build`

## 阶段 5：地点列表、地图与轨迹

- [x] 16. 地点列表完全受全局上下文驱动
  - 输出：地点列表和详情随 `juanRange`、`yearRange` 变化
  - 成功标准：只展示当前范围内相关地点
  - 验证：`cd visualization && npm run build`

- [x] 17. 增加地图模式，并处理坐标缺失
  - 输出：基于 Leaflet + OpenStreetMap 的地图 tab
  - 成功标准：没有坐标时不出现空白页，有坐标的地点可正常绘制
  - 实现：
    - 新组件：`visualization/src/components/MapView.tsx`
    - 地点列表保留为列表模式
    - 已将地理编码坐标回填到统一知识库样例数据
  - 验证：`cd visualization && npm run build`

- [ ] 18. 完成人物/事件/势力轨迹体验
  - 当前状态：`MapView` 中已有部分轨迹实现
  - 剩余输出：在人物、事件、势力详情中增加入口；有年份和坐标时展示有序路径
  - 成功标准：数据支持时显示轨迹，不支持时明确说明原因
  - 触点：详情面板、地图视图、`unifiedDataProcessing.ts`

## 阶段 6：构建编排与可重复性

- [x] 19. 增加统一的数据构建入口
  - 输出：一个命令按顺序运行年份索引、融合、地理编码、校验和发布
  - 实现：`scripts/build_data.py`
  - 验证：`uv run python scripts/build_data.py --skip-resolve`

- [x] 20. 增加产物冒烟校验
  - 输出：校验 JSON 结构、坐标顺序/范围、关系年份合理性
  - 实现：`scripts/validate_artifacts.py`
  - 验证：`uv run pytest tests/test_validate_artifacts.py -q`

## 阶段 7：数据到界面的发布闭环

- [ ] 21. 发布更新后的运行时数据到前端
  - 输出：前端能读取新的 `unified_knowledge.json` 和 `juan_year_index.json`
  - 成功标准：可视化无运行时错误，筛选和地图行为符合设计
  - 触点：
    - `visualization/public/data/*`
    - `visualization/src/hooks/useUnifiedData.ts`
