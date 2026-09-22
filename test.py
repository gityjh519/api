from dataclasses import dataclass

from pydantic import BaseModel, Field


class BibleAddBody(BaseModel):
    volumIndex: int = Field(gt=0,description="卷，必须大于0")
    chapterIndex: int = Field(gt=0,description="章，必须大于0")
    sectionIndex: int = Field(gt=0,description="章，必须大于0")
    content: str = Field(min_length=1,description="经文内容不能为空")

