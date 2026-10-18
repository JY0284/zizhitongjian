from typing import List, Literal, Optional
from pydantic import AliasChoices, BaseModel, Field, field_validator


class Role(BaseModel):
    """
    实体模型：表示历史文本中的人物、组织、国家或文化产物
    
    Entity model representing influential figures, organizations, states, 
    and cultural artifacts in historical texts.
    """

    entity_type: Optional[Literal["person", "polity", "school", "organization"]] = Field(
        default=None,
        description="实体类型: person(人物), polity(政权/国家), school(学派), organization(组织/官职/群体). 若为None则由后处理推断."
    )
    
    name: str = Field(
        description="实体名称，使用最常见或官方的称呼"
    )
    
    alias: list[str] = Field(
        default_factory=list,
        description="文本中出现的所有别名和变称"
    )
    
    original_description_in_book: str = Field(
        default="",
        description="原文对该实体的描述，保持原文措辞"
    )

    description: str = Field(
        default="",
        validation_alias=AliasChoices("description", "llm_introduction"),
        description="基于模型知识对该实体的简要介绍，补充原文未提及的背景信息"
    )
    
    power: str | None = Field(
        default=None,
        description="此实体所属势力派别，如'秦国'、'儒家'等，若无则为None"
    )
    
    sentence_indexes_in_segment: List[int] = Field(
        default_factory=list,
        description="实体在文本段落中出现的句子索引列表"
    )

    juan_index: int = Field(
        default=0,
        description="The volume index of the book."
    )

    segment_index: int = Field(
        default=0,
        description="The segment index within the volume."
    )

    @field_validator('original_description_in_book', 'description', mode='before')
    @classmethod
    def empty_string_if_none(cls, v):
        if v is None:
            return ""
        return v

    @field_validator('power', mode='before')
    @classmethod
    def normalize_unknown_power(cls, value):
        return None if isinstance(value, str) and value.strip().lower() in {'none', 'null', ''} else value

