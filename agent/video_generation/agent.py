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

import os

import google.auth
from google.genai import types

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.models.llm_request import LlmRequest

_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id) # type: ignore
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

from subagents import story_agent, storyboard_agent, video_agent
from utils.storage_utils import upload_data_to_gcs

async def before_model_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest
) -> LlmResponse | None:
    """The callback that ensures uploading user's images to GCS."""
    last_user_content = llm_request.contents[-1]
    parts_to_replace = {}
    if last_user_content.parts:
        for index, part in enumerate(last_user_content.parts):
            inline_data = part.inline_data
            if (
                not inline_data
                or not inline_data.data
                or not inline_data.mime_type
            ):
                continue
            if inline_data.mime_type.startswith("image/"):
                image_name = upload_data_to_gcs(
                    callback_context.agent_name,
                    inline_data.data,
                    inline_data.mime_type
                )
                image_text = f"IMAGE_URI: {image_name}"
                parts_to_replace[index] = types.Part.from_text(text=image_text)
    for index, part in parts_to_replace.items():
        last_user_content.parts[index] = part # type: ignore


root_agent = LlmAgent(
    name="root_agent",
    model="gemini-2.5-pro",
    instruction="""
    You are video director agent. You orchestrate other tools and agents through the process.
    1. First, work on the story. Use story agent to craft the story.
    2. Second, you use storyboard agent to iterate over each shot.
    3. Once storyboard agent gave you the shot's prompt, first frame and last frame, you use video agent to create a video.

    You iterate over steps 2 and 3 for each shot.

    You must preserve and pass all details between agents. Do not try to summarize or shorten them.
    Show that output to me as well.
    Each video shot must be 8 seconds long.

    """.strip(),
    global_instruction="""
        When output "gs://" URIs to the user, replace "gs://" with "https://storage.mtls.cloud.google.com/".
        When calling any functions/tools, keep "gs://" URIs as they are.
    """.strip(),
    sub_agents=[story_agent, storyboard_agent, video_agent],
    before_model_callback=before_model_callback,
)
