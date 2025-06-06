# coding=utf-8
# Copyright 2022 The HuggingFace Team. All rights reserved.
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
"""Utility functions related to both local files and files on the Hugging Face Hub."""

import os
import re
import warnings
from pathlib import Path
from typing import List, Optional, Union

from huggingface_hub import HfApi
from transformers.utils import http_user_agent


def validate_file_exists(
    model_name_or_path: Union[str, Path],
    filename: str,
    subfolder: str = "",
    revision: Optional[str] = None,
    token: Optional[Union[bool, str]] = None,
) -> bool:
    """
    Checks that the file called `filename` exists in the `model_name_or_path` directory or model repo.
    """

    if os.path.isdir(model_name_or_path):
        return os.path.isfile(os.path.join(model_name_or_path, subfolder, filename))
    else:
        return HfApi(user_agent=http_user_agent(), token=token).file_exists(
            filename=os.path.join(subfolder, filename),
            repo_id=model_name_or_path,
            revision=revision,
            token=token,
        )


def find_files_matching_pattern(
    model_name_or_path: Union[str, Path],
    pattern: str,
    glob_pattern: str = "**/*",
    subfolder: str = "",
    use_auth_token: Optional[Union[bool, str]] = None,
    token: Optional[Union[bool, str]] = None,
    revision: Optional[str] = None,
) -> List[Path]:
    """
    Scans either a model repo or a local directory to find filenames matching the pattern.

    Args:
        model_name_or_path (`Union[str, Path]`):
            The name of the model repo on the Hugging Face Hub or the path to a local directory.
        pattern (`str`):
            The pattern to use to look for files.
        glob_pattern (`str`, defaults to `"**/*"`):
            The pattern to use to list all the files that need to be checked.
        subfolder (`str`, defaults to `""`):
            In case the model files are located inside a subfolder of the model directory / repo on the Hugging
            Face Hub, you can specify the subfolder name here.
        use_auth_token (`Optional[Union[bool,str]]`, defaults to `None`):
            Deprecated. Please use the `token` argument instead.
        token (`Optional[Union[bool,str]]`, defaults to `None`):
            The token to use as HTTP bearer authorization for remote files. If `True`, will use the token generated
            when running `huggingface-cli login` (stored in `huggingface_hub.constants.HF_TOKEN_PATH`).
        token (`Optional[Union[bool, str]]`, *optional*):
            The token to use as HTTP bearer authorization for remote files. If `True`, will use the token generated
            when running `transformers-cli login` (stored in `~/.huggingface`).
        revision (`Optional[str]`, defaults to `None`):
            Revision is the specific model version to use. It can be a branch name, a tag name, or a commit id.

    Returns:
        `List[Path]`
    """

    if use_auth_token is not None:
        warnings.warn(
            "The `use_auth_token` argument is deprecated and will be removed soon. Please use the `token` argument instead.",
            FutureWarning,
        )
        if token is not None:
            raise ValueError("You cannot use both `use_auth_token` and `token` arguments at the same time.")
        token = use_auth_token

    model_path = str(model_name_or_path) if isinstance(model_name_or_path, Path) else model_name_or_path
    pattern = re.compile(subfolder + pattern)
    if os.path.isdir(model_path):
        files = Path(model_path).glob(glob_pattern)
        files = [p for p in files if re.search(pattern, str(p))]
    else:
        repo_files = HfApi(user_agent=http_user_agent(), token=token).list_repo_files(
            model_path, revision=revision, token=token
        )
        files = [Path(p) for p in repo_files if re.match(pattern, p)]

    return files
