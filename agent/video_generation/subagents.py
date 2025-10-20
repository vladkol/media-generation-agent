# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel

from google.adk.agents import Agent
from google.adk.tools import AgentTool, BaseTool, ToolContext
from google.genai import types

from nano_banana_tool import generate_image
from veo3_agent import veo3_agent
from utils.utils import load_prompt_from_file
from utils.storage_utils import download_data_from_gcs


async def extract_media_callback(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Dict
) -> Optional[Dict]:
    """The callback that ensures uploading all media assets to the Artifact Store"""
    if not tool_response:
        return
    if not isinstance(tool_response, BaseModel):
        if isinstance(tool_response, dict) and len(tool_response) == "1" and "result" in tool_response:
            response = tool_response["result"]
        else:
            response = tool_response
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                return
    elif isinstance(tool_response, BaseModel):
        response = tool_response.model_dump(exclude_none=False)
    if isinstance(response, dict):
        uri = response.get("uri", "")
        if uri and uri.startswith("gs://"):
            await tool_context.save_artifact(
                filename=uuid.uuid4().hex,
                artifact=types.Part(inline_data=download_data_from_gcs(uri))
            )

story_agent = Agent(
    model="gemini-2.5-pro",
    name="story_agent",
    description="Story Agent",
    instruction=load_prompt_from_file("story_agent.md"),
    output_key="story",
)
storyboard_agent = Agent(
    model="gemini-2.5-pro",
    name="storyboard_agent",
    description="""Storyboard Agent.

    Input:
        1. The story.
        2. Characters with their detailed descriptions.
        3. Video shot script.
        4. Optional last frame of the **previous** shot.
    """,
    instruction=load_prompt_from_file("storyboard_agent.md"),
    tools=[generate_image],
    after_tool_callback=extract_media_callback,
    output_key="storyboard",
)
video_agent = Agent(
    model="gemini-2.5-pro",
    name="video_agent",
    description="""Video Agent.

    Input:

    1. Video generation prompt.
    2. First frame.
    3. Last frame.

    """,
    instruction=load_prompt_from_file("video_agent.md"),
    tools=[AgentTool(veo3_agent)],
    after_tool_callback=extract_media_callback,
    output_key="video",
)
