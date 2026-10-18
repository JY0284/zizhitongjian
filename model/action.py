from typing import List
from pydantic import AliasChoices, BaseModel, Field, field_validator

from .role import Role


class Action(BaseModel):
    """
    关系/动作模型：表示实体间的互动关系
    
    Relation model representing interactions between entities, including
    military, political, and social actions.
    """
    
    time: str | None = Field(
        default=None,
        description="关系或动作发生的时间，使用纪年格式如'前453年'、'周威烈王二十三年'，若无明确时间则为None"
    )
    
    from_roles: List[str] = Field(
        validation_alias=AliasChoices("from_roles", "from"),
        description="所有主动方实体名称列表，表示动作的发起者，必须出现在entities中"
    )
    
    to_roles: List[str] = Field(
        validation_alias=AliasChoices("to_roles", "to"),
        description="所有接收方/被动方实体名称列表，表示动作的承受者，必须出现在entities中"
    )
    
    action: str = Field(
        description="具体动作或行为描述，如'围攻'、'背叛'、'册封'等"
    )
    
    context: str = Field(
        description="此关系（事件）产生的背景和原因，符合原文，详略得当"
    )
    
    result: str | None = Field(
        default=None,
        description="动作或事件的结果，若原文未明确说明则为None"
    )
    
    event_name: str | None = Field(
        default=None,
        description="如果属于某个有名称的历史事件，则记录事件名称如'晋阳之战'，否则为None"
    )
    
    location: str | None = Field(
        default=None,
        description="关系或动作发生的地点，如'晋阳'、'咸阳'等，必须出现在locations列表中，若无明确地点则为None"
    )

    is_commentary: bool = Field(
        default=False,
        description="是否为评论、议论或观点表达，而非客观历史事实"
    )
    is_retrospective: bool = Field(default=False, description="Whether this action is a recalled earlier event rather than current-year narration")

    sentence_indexes_in_segment: List[int] = Field(
        default_factory=list,
        description="关系或动作在文本段落中出现的句子索引列表"
    )

    juan_index: int = Field(
        default=0,
        description="The volume index of the book."
    )

    segment_index: int = Field(
        default=0,
        description="The segment index within the volume."
    )

    @field_validator('context', 'action', mode='before')
    @classmethod
    def empty_string_if_none(cls, v):
        if v is None:
            return ""
        return v

    @field_validator('time', 'result', 'event_name', 'location', mode='before')
    @classmethod
    def normalize_unknown_optional(cls, value):
        return None if isinstance(value, str) and value.strip().lower() in {'none', 'null', ''} else value
