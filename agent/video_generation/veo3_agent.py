
import asyncio
import json
import logging
import mimetypes
import time
from typing import Literal, Optional
import uuid

from google.adk.models.google_llm import Gemini
from google.adk.tools import ToolContext

from google.genai import types

from pydantic import BaseModel

from utils.storage_utils import ai_bucket_name
from tool_agent import ToolAgent

OPERATION_WAIT_TIME = 10.0 # 10 seconds between operation status check
AUTHORIZED_URI = "https://storage.mtls.cloud.google.com/"

# Set logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class MediaAsset(BaseModel):
    uri: str
    error: Optional[str] = None

async def generate_video(
    tool_context: ToolContext,
    prompt: str,
    start_frame_image_gsc_uri: Optional[str] = None,
    end_frame_image_gsc_uri: Optional[str] = None,
    video_duration_seconds: int = 8,
    aspect_ratio: Literal["16:9", "9:16"] = "16:9",
) -> MediaAsset:
    """Generates a video using Veo 3 model.
    Returns a MediaAsset object with the GCS URI of the generated video or an error text.

    Args:
        prompt (str): Video generation prompt.
            Required for text-to-video (t2v) and image-ti-video (i2v).
        start_frame_image_gsc_uri (Optional[str], optional): Optional GCS URI
            of the start frame image. Only used for image-to-video generation.
            Defaults to None.
        end_frame_image_gsc_uri (Optional[str], optional): Optional GCS URI
            of the end frame image. Only used for image-to-video generation.
            Only valid if start_frame_image_gsc_uri is specified as well.
            Defaults to None.
        video_duration_seconds (int, optional): Video duration in seconds.
            Supported values are 8,4,6.
            Defaults to 8.
        aspect_ratio (str, optional): Aspect ratio of the video.
            Supported values are "16:9" and "9:16". Defaults to "16:9".

    Returns:
        MediaAsset: object with the GCS URI of the generated image or an error text.
    """

    gemini_client = Gemini()
    genai_client = gemini_client.api_client
    if tool_context:
        agent_name = tool_context.agent_name
        invocation = tool_context.invocation_id
    else:
        agent_name = "agent"
        invocation = uuid.uuid4().hex

    config=types.GenerateVideosConfig(
        aspect_ratio=aspect_ratio,
        output_gcs_uri=f"gs://{ai_bucket_name}/{agent_name}",
        number_of_videos=1, # Only one video, otherwise cannot use seed.
        seed=1, # fix it here to make it _somewhat_ reproducible.
        duration_seconds=video_duration_seconds,
        person_generation="allow_adult",
        # enhance_prompt=True
    )
    source = types.GenerateVideosSource(prompt=prompt)
    if start_frame_image_gsc_uri:
        source.image = types.Image(
            gcs_uri=start_frame_image_gsc_uri,
            mime_type=mimetypes.guess_type(start_frame_image_gsc_uri)[0]
        )
    if end_frame_image_gsc_uri:
        config.last_frame = types.Image(
            gcs_uri=end_frame_image_gsc_uri,
            mime_type=mimetypes.guess_type(end_frame_image_gsc_uri)[0]
        )
    result_media = MediaAsset(uri="")
    logger.info(f"[{invocation}] Generating a video.")

    start = time.time()
    gen_video_op = await genai_client.aio.models.generate_videos(
        model="veo-3.1-generate-preview",
        source=source,
        config=config
    )
    while not gen_video_op.done:
        await asyncio.sleep(OPERATION_WAIT_TIME)
        gen_video_op = await genai_client.aio.operations.get(gen_video_op)
    if gen_video_op.error:
        result_media.error = json.dumps(gen_video_op.error, indent=2)
        logger.error(f"[{invocation}] {result_media.error}")
    elif not gen_video_op.result or not gen_video_op.result.generated_videos:
        result_media.error = f"[{invocation}] Empty generation result."
        logger.error(result_media.error)
    else:
        end = time.time()
        logger.info(
            f"[{invocation}] Video generation operation took {int(end - start)} seconds."
        )
        for video in gen_video_op.result.generated_videos:
            if not video.video or not video.video.uri:
                continue
            result_media.uri = video.video.uri
            logger.info(
                f"[{invocation}] Video URL: {result_media.uri.replace("gs://", AUTHORIZED_URI)}"
            )
            break
    logger.info(
        f"[{invocation}] Video Generation result:\n{result_media.model_dump_json(indent=2)}"
    )
    return result_media


veo3_agent = ToolAgent(
    name="veo3_agent",
    description="Generates a video based on a prompt and an optional starting frame image.",
    function=generate_video,
)

