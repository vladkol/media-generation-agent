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
import os

# Set logging
logger = logging.getLogger(__name__)
PROMPTS_PATH = "../prompts/"


def load_prompt_from_file(
    filename: str
) -> str:
    try:
        # Construct path relative to the current script file (__file__)
        filepath = os.path.join(os.path.dirname(__file__), PROMPTS_PATH, filename)
        with open(filepath, encoding="utf-8") as f:
            instruction = f.read()
        logger.info(f"Successfully loaded instruction from {filename}")
    except Exception as e:
        logger.error(f"ERROR loading instruction file {filepath}: {e}")
    return instruction
