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

import logging
import mimetypes
from typing import Literal, Optional

from google.adk.models.google_llm import Gemini
from google.adk.tools import ToolContext

from google.genai import types

from pydantic import BaseModel

from utils.storage_utils import upload_data_to_gcs

# Set logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MediaAsset(BaseModel):
    uri: str
    error: Optional[str] = None

async def generate_image(
    tool_context: ToolContext,
    prompt: str,
    source_image_gsc_uri: Optional[str] = None,
    aspect_ratio: Literal["16:9", "9:16"] = "16:9",
) -> MediaAsset:
    """Generates an image using Gemini 2.5 Flash Image model (aka Nano Banana).
    Returns a MediaAsset object with the GCS URI of the generated image or an error text.

    Args:
        prompt (str): Image generation prompt (may refer to the source image if it's provided).
        source_image_gsc_uri (Optional[str], optional): Optional GCS URI
            of source image.
            Defaults to None.
        aspect_ratio (str, optional): Aspect ratio of the video.
            Supported values are "16:9" and "9:16". Defaults to "16:9".

    Returns:
        MediaAsset: object with the GCS URI of the generated image or an error text.
    """

    gemini_client = Gemini()
    genai_client = gemini_client.api_client
    content = types.Content(
        parts=[types.Part.from_text(text=prompt)],
        role="user"
    )
    if source_image_gsc_uri:
        content.parts.insert( # type: ignore
            0,
            types.Part(
                file_data=types.FileData(
                    file_uri=source_image_gsc_uri,
                    mime_type=mimetypes.guess_type(source_image_gsc_uri)[0]
                )
            )
        )

    for _ in range (0, 5):
        response = genai_client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[content],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                )
            )
        )
        response_text = ""
        if response and response.parts:
            for part in response.parts:
                if part.text and not part.thought:
                    response_text += part.text
                if part.file_data and part.file_data.file_uri:
                    return MediaAsset(uri=part.file_data.file_uri)
                if part.inline_data and part.inline_data.data:
                    gcs_uri = await upload_data_to_gcs(
                        tool_context.agent_name,
                        part.inline_data.data,
                        part.inline_data.mime_type # type: ignore
                    )
                    return MediaAsset(uri=gcs_uri)
        if response_text:
            logger.warning(f"MODEL RESPONSE: \n{response_text}")

    return MediaAsset(uri="", error="Empty generation result.")
