from pydantic import BaseModel, Field


class MemorySettings(BaseModel):
    default_max_token_limit: int = Field(default=4000)
    default_sliding_window_size: int = Field(default=6)
    default_tool_output_limit: int = Field(default=150)

    default_recent_zone_size: int = Field(default=6)
    default_middle_zone_size: int = Field(default=6)
    default_summary_zone_size: int = Field(default=10)

    enable_auto_compression_on_overflow: bool = Field(default=True)


settings = MemorySettings()