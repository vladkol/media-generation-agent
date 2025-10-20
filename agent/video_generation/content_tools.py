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

from pathlib import Path
import httpx
import mimetypes
import uuid

from google.adk.tools import ToolContext
from google.genai import types

def file_exists(file_path: str) -> bool:
    """Checks if a local file exists"""
    return Path(file_path).exists()

def read_text_file(file_path: str) -> str:
    """Reads text file"""
    return Path(file_path).read_text(encoding="utf-8")

def write_text_file(file_path: str, text: str):
    """Writes text file"""
    path = Path(file_path)
    parent_path = path.parent.absolute()
    parent_path.mkdir(parents=True, exist_ok=True)
    Path(file_path).write_text(text, encoding="utf-8")

async def read_web_page(url: str) -> str:
    """Loads a web page by its URL"""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.text

async def read_web_image(image_url: str, tool_context: ToolContext) -> dict:
    """Loads a web image by its URL, and save it to artifacts"""
    async with httpx.AsyncClient() as client:
        response = await client.get(image_url, follow_redirects=True)
        response.raise_for_status()
        image_data = response.content
        content_type = response.headers.get(
            "Content-Type",
            "application/x-binary"
        )
        mime_type = content_type.split(';')[0].strip()
        ext = mimetypes.guess_extension(mime_type)
        if not ext:
            ext = ".bin"
        file_name = f"{uuid.uuid4().hex}{ext}"
        await tool_context.save_artifact(
            filename=file_name,
            artifact=types.Part.from_bytes(data=image_data, mime_type=mime_type)
        )
        return {
            "status": "success",
            "details": "Image was retrieved and saved to artifacts.",
            "original_url": image_url,
            "filename": file_name
        }