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
from typing import Any, AsyncGenerator, Callable, Dict, Optional, Union

from google.adk.agents import (
    BaseAgent,
    InvocationContext,
    LlmAgent
)
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools import FunctionTool

from google.genai import types

from pydantic import BaseModel


class ToolAgent(BaseAgent):
    """Agent that acts as a prompt parser for a function-tool.
    It infers tool parameters from the prompt.
    This agent is useful when you need to use a function-tool
    where you are required to use a sub-agent.
    """
    function: Callable[..., Any]
    model: Union[str, BaseLlm] = "gemini-2.5-flash"

    def _clean_base_models(
        self,
        callback_context: CallbackContext,
        llm_request: LlmRequest
    ) -> Optional[LlmResponse]:
        """
        Callback for cleaning up response schema for LLM requests
        in case if the response schema uses `additionalProperties`
        which causes an exception.
        """

        def _clean(data: Dict[str, Any]) -> Dict[str, Any]:
            for key, value in data.copy().items():
                if key == "additionalProperties":
                    data.pop(key)
                if isinstance(value, dict):
                    data[key] = _clean(value)
            return data

        if llm_request.config and llm_request.config.response_schema:
            schema = llm_request.config.response_schema
            if isinstance(schema, types.Schema):
                schema = schema.model_dump()
            elif hasattr(schema, "model_json_schema"):
                schema = schema.model_json_schema()  # type: ignore
            elif not isinstance(schema, dict):
                schema = json.loads(str(schema))
            llm_request.config.response_schema = _clean(schema)
        else:
            return None


    async def _run_async_impl(
            self,
            ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        tool = FunctionTool(self.function)
        tool_agent = LlmAgent(
            name=f"{tool.name}_tool_agent",
            instruction=f"""
                You are a helpful Tool agent. You parse user's request and call {tool.name} function with parameters inferred from the user's request.
                You don't make a decision whether to make a call or not. You parse arguments, then make a call.
                You are allowed to make a single function call.
                YOU ARE NOT ALLOWED TO REFUSE TO CALL THE TOOL.
            """,
            description=tool.description,
            model=self.model,
            tools=[tool],
            before_model_callback=self._clean_base_models,
        )
        result_event_text = ""
        run_generator = tool_agent.run_async(ctx)
        async for event in run_generator:
            frs = event.get_function_responses()
            for fr in frs:
                if not fr.response:
                    continue
                response = fr.response
                if len(response) == 1 and "result" in response:
                    response = response["result"]
                if isinstance(response, BaseModel):
                    result_event_text = response.model_dump_json(
                        indent=2,
                        exclude_none=True
                    )
                else:
                    result_event_text = json.dumps(response, indent=2)
                break
            if result_event_text:
                break
        await run_generator.aclose()
        if not result_event_text:
            result_event_text = "The tool returned no result."
        yield Event(
            content=types.Content(
                parts=[types.Part.from_text(
                    text=result_event_text
                )],
                role="model"
            ),
            turn_complete=True,
            author=self.name
        )
