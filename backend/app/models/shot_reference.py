"""分镜关联表：Shot ↔ Character / Scene / Prop 多对多。"""

from sqlmodel import Field, SQLModel


class ShotCharacter(SQLModel, table=True):
    """分镜 ↔ 角色 关联表。"""
    __tablename__ = "shot_characters"
    shot_id: str = Field(primary_key=True, foreign_key="shots.id", max_length=36, ondelete="CASCADE")
    character_id: str = Field(primary_key=True, foreign_key="characters.id", max_length=36, ondelete="CASCADE")
    sort_order: int = Field(default=0)


class ShotScene(SQLModel, table=True):
    """分镜 ↔ 场景 关联表。"""
    __tablename__ = "shot_scenes"
    shot_id: str = Field(primary_key=True, foreign_key="shots.id", max_length=36, ondelete="CASCADE")
    scene_id: str = Field(primary_key=True, foreign_key="scenes.id", max_length=36, ondelete="CASCADE")
    sort_order: int = Field(default=0)


class ShotProp(SQLModel, table=True):
    """分镜 ↔ 道具 关联表。"""
    __tablename__ = "shot_props"
    shot_id: str = Field(primary_key=True, foreign_key="shots.id", max_length=36, ondelete="CASCADE")
    prop_id: str = Field(primary_key=True, foreign_key="props.id", max_length=36, ondelete="CASCADE")
    sort_order: int = Field(default=0)
