# 资治通鉴-文白对照数据-人工智能辅助理解

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

## 抛砖引玉——资治通鉴数据应用样例（壹）：AI辅助理解可视化
> 正在进行中。
> [结构化数据使用样例](https://github.com/JY0284/zizhitongjian/blob/main/data_usage_demo_visualization.ipynb)
> [AI辅助资治通鉴知识图谱挖掘&构建](https://github.com/JY0284/zizhitongjian/blob/main/extract_and_build_knowledge_graph.ipynb)

### 可视化脚本 plot_er.py 使用指南（ER 关系 Sankey 图）
本仓库新增了 **`plot_er.py`**（由之前的示例脚本改名而来），可把实体-关系结构化数据渲染成一张 **“权力/影响力流向 Sankey 图”**。  
图中每一条带状流代表一次或多次 **分封 / 背叛 / 代 / 立** 等“权力流转”事件，鼠标悬停即可看到对应的事件标签及计数。

#### 1. 准备数据

真实示例结构化数据存放在 data/demo_er.json，构建过程可参考[AI辅助资治通鉴知识图谱挖掘&构建](https://github.com/JY0284/zizhitongjian/blob/main/extract_and_build_knowledge_graph.ipynb)

#### 2. 一条命令生成并保存 HTML

```bash
python plot_er.py data/demo_er.json --keep-loops --all-actions -o demo/demo_er.html
```

| 主要参数            | 作用                                                                             |
| --------------- | ------------------------------------------------------------------------------ |
| `--keep-loops`  | **保留自循环**（同一势力内部的事件）。若不加该参数，脚本默认去掉这些往往难以辨识的细线。                                 |
| `--all-actions` | 不仅统计“分封 / 背叛 / 代 / 立”四类动作，而是 **把所有关系事件都画进图里**。如果只想看“权力流转”四类动作，可省略此参数。          |
| `-o <HTML>`     | 把结果保存为指定文件，同时自动在浏览器中打开。若不加 `-o`，脚本会直接弹出 Plotly 交互窗口（部分终端/远程环境可能无法弹窗，建议加 `-o`）。 |

更多用法示例请运行：

```bash
python plot_er.py -h
```

#### 3. 线上示例

仓库已经用 `data/demo_er.json` 运行了一次脚本，生成的静态文件放在：

```
demo/demo_er.html
```

> ⚠️ 该文件约 5 MB，Plotly 脚本已内嵌，可直接在浏览器离线查看。

👇 **互动示例**
![历史人物/势力关系交互图静态截图](https://github.com/JY0284/zizhitongjian/blob/main/demo/demo_er.png)


[历史人物/势力关系交互图HTML，下载至本地使用浏览器打开](https://github.com/JY0284/zizhitongjian/blob/main/demo/demo_er.html)

#### 4. 这张 Sankey 图能看出什么？

1. **势力间的权力走向一目了然**
   例如，可以直观看到 **周朝 → 魏国 / 赵国 / 韩国** 的分封流，以及 **智氏家族 → 赵国** 的大带状流，背后对应“晋阳之战”等关键事件。
2. **鼠标悬停即得事件详情**
   悬浮在某条带上会显示如 “三家分晋 (1)；立为继承人 (2)” 等列表，快速了解该流包含哪些事件、各发生几次。
3. **参数化过滤，探索更深**

   * 通过 `-s` / `-e`（开始/结束年份）只观察特定时代；
   * 加或减 `--keep-loops` 查看内部权力更迭；
   * 去掉 `--all-actions` 聚焦“权力流转”四大动词。
     这样既能俯瞰宏观格局，也能精查局部细节。

### 其他demo
正在进行中的可视化Demo（使用GPT-O1与Deepseek-R1完成）：
![demo_1](https://github.com/JY0284/zizhitongjian/blob/main/周纪关系图.png)
![demo_2](https://github.com/JY0284/zizhitongjian/blob/main/history_relations.gv.png)
![demo_3](https://github.com/JY0284/zizhitongjian/blob/main/资治通鉴卷1-Seg1-实体关系图.png)


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
- [ ] AI辅助获取全书知识图谱（人物、事件及其关系，以及在格式化数据中的精确定位）
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
