from typing import List
from pydantic import BaseModel, Field, field_validator


class Event(BaseModel):
    """
    事件模型：表示重大历史事件
    
    Event model representing significant historical events that are composed 
    of multiple actions and involve multiple entities.
    """
    
    is_retrospective: bool = Field(default=False, description="Whether this is a recalled earlier event")

    name: str = Field(
        description="事件名称，如'晋阳之战'、'三家分晋'等"
    )
    
    time: str | None = Field(
        default=None,
        description="事件发生的时间或时间段，如'前453年'、'周威烈王二十三年'"
    )
    
    location: str | None = Field(
        default=None,
        description="事件发生的主要地点，必须出现在locations列表中"
    )
    
    participants: List[str] = Field(
        default_factory=list,
        description="参与此事件的所有实体名称列表，必须出现在entities中"
    )
    
    description: str = Field(
        description="事件的详细描述，包括起因、经过、结果"
    )

    background: str = Field(
        default="",
        description="基于模型知识对该事件的背景补充"
    )
    
    significance: str = Field(
        default="",
        description="事件的历史意义和影响"
    )
    
    related_action_indices: List[int] = Field(
        default_factory=list,
        description="构成此事件的相关动作在relations列表中的索引"
    )
    
    source: str = Field(
        default="",
        description="事件在原文中的出处，如'卷1-段3'"
    )

    @field_validator('significance', 'source', 'background', mode='before')
    @classmethod
    def empty_string_if_none(cls, v):
        if v is None:
            return ""
        return v

    @field_validator('time', 'location', mode='before')
    @classmethod
    def normalize_unknown_optional(cls, value):
        return None if isinstance(value, str) and value.strip().lower() in {'none', 'null', ''} else value


    sentence_indexes_in_segment: List[int] = Field(
        default_factory=list,
        description="事件在文本段落中出现的句子索引列表"
    )

    juan_index: int = Field(
        default=0,
        description="The volume index of the book."
    )

    segment_index: int = Field(
        default=0,
        description="The segment index within the volume."
    )

