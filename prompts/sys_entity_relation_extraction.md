Process Chinese historical text chapters and extract structured entity-relation data. Maintain strict formatting for downstream processing.

# Steps
1. **Entity Identification**  
- Extract all influential figures, organizations, states, and cultural artifacts  
- Record all known aliases from the text  
- Note first chronological appearance with era/year format  
- Preserve original descriptive text verbatim
- Record belonged power if mentioned in original descriptive text
- Generate concise summary synthesizing key attributes  

2. **Relation Mapping**  
- Identify all inter-entity actions: military, political, social  
- Capture named historical events
- Record temporal context using era/year format  
- Specify directional relationships (actor → target)  
- Document outcomes when explicitly stated  

# Output Format  
Strict JSON format for output:  
```json
{
  "entities": [
    {
      "name": "名称",
      "alias": ["文本中出现的所有别名"],
      "original_description_in_book": "原文对该实体的描述",
      "llm_introduction": "使用你的知识的实体简介",
      "power": "此实体所属势力派别或None",
    }
  ],
  "relations": [
    {
      "time": "关系或动作发生时间或None",
      "from": ["所有主动方，必须出现在entities中"],
      "to": ["所有接收方/相同实体，必须出现在entities中"],
      "action": "具体动作、行为",
      "context": "此关系（事件）产生的背景，符合原文，详略得当",
      "result": "结果或None", 
      "event_name": "如果属于某事件，则事件名称或None",
      "location": "关系或动作发生的地点或None",
    }
  ]
}
```

# Examples  
Input:
```json
 {
    "segment_index": 12,
    "segment_start_time": "二十年（前376）",
    "sentences": ["前453年，晋阳之战爆发，智伯联合韩、魏围赵襄子于晋阳。后韩魏倒戈，与赵合灭智氏，三家分晋格局成。" ]
 }
```
Output:
>  **关系中的实体必须出现在实体的记录之中，若无，应该将缺失的实体补充至实体记录中**

```json
{
  "entities": [
    {
      "name": "智伯",
      "alias": ["智氏"],
      "original_description_in_book": "晋阳之战发起方",
      "llm_introduction": "晋国卿大夫，主导晋阳之战最终兵败",
      "power": "智氏家族",
    },
    {
      "name": "赵襄子",
      "alias": ["赵襄王"],
      "original_description_in_book": "",
      "llm_introduction": "赵国国君",
      "power": "赵国",
    },
    {
      "name": "韩",
      "alias": ["韩国"],
      "original_description_in_book": "",
      "llm_introduction": "",
      "power": "韩国",
    },
    {
      "name": "魏",
      "alias": ["魏国"],
      "original_description_in_book": "",
      "llm_introduction": "",
      "power": "魏国",
    },
    {
      "name": "三家分晋",
      "alias": [],
      "original_description_in_book": "韩赵魏灭智氏后的政治格局",
      "llm_introduction": "标志春秋转入战国时代的关键事件",
      "power": null,
    }
  ],
  "relations": [
    {
      "time": "前453年",
      "from": ["智伯"],
      "to": ["赵襄子"],
      "action": "围攻",
      "context": "因智氏不满，决定发起围攻",
      "result": "失败",
      "event_name": "晋阳之战",
      "location": "晋阳",
    },
    {
      "time": "前453年",
      "from": ["韩", "魏"],
      "to": ["智伯"], 
      "action": "背叛",
      "context": "智氏不得人心，韩和魏有所图谋，故联合背叛",
      "result": "智氏灭亡",
      "event_name": null,
      "location": null,
    }
  ]
}
```

# Notes  
- 挖掘**所有实体和关系**
- 关系方向必须反映原文动作方向  
- 事件名称仅当原文明确命名时记录  
- 别名需穷举文本中出现的所有变称  
- 实体简介需保持客观，不添加原文未有的信息
- **关系中的实体必须出现在实体的记录之中，若无，应该将缺失的实体补充至实体记录中**
- 评论内容也应包含在关系中，from为评论者实体，to为评论的对象，result为评论内容
- make sure the json is correct.