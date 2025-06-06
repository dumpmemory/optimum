# coding=utf-8
# Copyright 2023 The HuggingFace Team. All rights reserved.
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

import copy
import random
import string
from typing import Any, Dict, Tuple, Union
from unittest import TestCase

import pytest
from transformers import AutoConfig, AutoFeatureExtractor, AutoTokenizer, PretrainedConfig, PreTrainedTokenizerBase
from transformers.image_processing_utils import BaseImageProcessor
from transformers.utils import http_user_agent

from optimum.utils.import_utils import is_datasets_available
from optimum.utils.preprocessing import TaskProcessorsManager
from optimum.utils.testing_utils import require_datasets


if is_datasets_available():
    from datasets import DatasetDict, DownloadConfig


TEXT_MODEL_NAME = "bert-base-uncased"
CONFIG = AutoConfig.from_pretrained(TEXT_MODEL_NAME)
TOKENIZER = AutoTokenizer.from_pretrained(TEXT_MODEL_NAME)
IMAGE_MODEL_NAME = "google/vit-base-patch16-224"
IMAGE_PROCESSOR = AutoFeatureExtractor.from_pretrained(IMAGE_MODEL_NAME)

TASK_TO_NON_DEFAULT_DATASET = {
    "text-classification": {
        "dataset_args": {"path": "glue", "name": "mnli"},
        "dataset_data_keys": {"primary": "premise", "secondary": "hypothesis"},
    },
    "token-classification": {
        "dataset_args": {"path": "wino_bias", "name": "type1_pro"},
        "dataset_data_keys": {"primary": "tokens"},
    },
    "question-answering": {
        "dataset_args": "wiki_qa",
        "dataset_data_keys": {"question": "question", "context": "answer"},
    },
    "image-classification": {
        "dataset_args": "sasha/dog-food",
        "dataset_data_keys": {"image": "image"},
    },
}

LOAD_SMALLEST_SPLIT = True
NUM_SAMPLES = 10


# Taken from https://pynative.com/python-generate-random-string/
def get_random_string(length: int) -> str:
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


def get_random_dict_of_strings() -> Dict[str, str]:
    random_num_items = random.randint(2, 8)
    random_lengths = ((random.randint(1, 16), random.randint(1, 16)) for _ in range(random_num_items))
    return {get_random_string(x[0]): get_random_string(x[1]) for x in random_lengths}


class TaskProcessorTestBase:
    TASK_NAME: str
    CONFIG: "PretrainedConfig"
    PREPROCESSOR: Union["PreTrainedTokenizerBase", "BaseImageProcessor"]
    WRONG_PREPROCESSOR: Union["PreTrainedTokenizerBase", "BaseImageProcessor"]

    def get_dataset_path_and_kwargs(self) -> Tuple[str, Dict[str, Any]]:
        not_default_dataset_args = TASK_TO_NON_DEFAULT_DATASET[self.TASK_NAME]["dataset_args"]
        if isinstance(not_default_dataset_args, dict):
            path = not_default_dataset_args.get("path", None)
            if path is None:
                raise ValueError(
                    'When not_default_dataset_args is a dictionary, it must contain a key called "path" corresponding to '
                    "the path or name of the dataset."
                )
            load_dataset_kwargs = {k: v for k, v in not_default_dataset_args.items() if k != "path"}
        else:
            path = not_default_dataset_args
            load_dataset_kwargs = {}

        return path, load_dataset_kwargs

    def test_accepted_preprocessor_classes_do_not_raise_exception(self):
        try:
            cls = TaskProcessorsManager.get_task_processor_class_for_task(self.TASK_NAME)
            cls(self.CONFIG, self.PREPROCESSOR)
        except ValueError as e:
            if str(e).startswith("Preprocessor is incorrect"):
                self.fail(
                    f"{cls} should be able to take preprocessors of type {type(self.PREPROCESSOR)}, but it failed here."
                )

    def test_wrong_preprocessor_classes_raise_exception(self):
        with self.assertRaises(ValueError) as cm:
            TaskProcessorsManager.get_task_processor_class_for_task(self.TASK_NAME)(
                self.CONFIG, self.WRONG_PREPROCESSOR
            )
            msg = str(cm.exception)
            self.assertTrue(
                msg.startswith("Preprocessor is incorrect"),
                "The message specifying that the type of preprocessor provided is not allowed for the TaskProcessor class "
                "was wrong.",
            )

    def test_create_defaults_and_kwargs_from_preprocessor_kwargs_does_not_mutate_preprecessor_kwargs(self):
        preprocessor_kwargs = get_random_dict_of_strings()
        clone = copy.deepcopy(preprocessor_kwargs)
        TaskProcessorsManager.get_task_processor_class_for_task(self.TASK_NAME)(
            self.CONFIG, self.PREPROCESSOR, preprocessor_kwargs
        )
        self.assertDictEqual(preprocessor_kwargs, clone)

    @require_datasets
    @pytest.mark.datasets_test
    def test_load_dataset_unallowed_data_keys(self):
        task_processor = TaskProcessorsManager.get_task_processor_class_for_task(self.TASK_NAME)(
            self.CONFIG, self.PREPROCESSOR
        )
        random_data_keys = get_random_dict_of_strings()
        with self.assertRaises(ValueError) as cm:
            path, load_dataset_kwargs = self.get_dataset_path_and_kwargs()
            task_processor.load_dataset(path, data_keys=random_data_keys, **load_dataset_kwargs)
            msg = str(cm.exception)
            self.assertTrue(
                msg.startswith("data_keys contains unallowed keys"),
                "The message specifying that the data keys keys are wrong is not the expected one.",
            )

    def _test_load_dataset(
        self,
        default_dataset: bool,
        try_to_guess_data_keys: bool,
        only_keep_necessary_columns: bool,
        **preprocessor_kwargs,
    ):
        download_config = DownloadConfig(user_agent=http_user_agent())
        task_processor = TaskProcessorsManager.get_task_processor_class_for_task(self.TASK_NAME)(
            self.CONFIG, self.PREPROCESSOR, preprocessor_kwargs
        )
        data_keys = (
            TASK_TO_NON_DEFAULT_DATASET[self.TASK_NAME]["dataset_data_keys"] if not try_to_guess_data_keys else None
        )
        dataset_with_all_columns = None
        if default_dataset:
            dataset = task_processor.load_default_dataset(
                only_keep_necessary_columns=only_keep_necessary_columns,
                load_smallest_split=LOAD_SMALLEST_SPLIT,
                num_samples=NUM_SAMPLES,
                download_config=download_config,
            )
            if only_keep_necessary_columns:
                dataset_with_all_columns = task_processor.load_default_dataset(download_config=download_config)
        else:
            path, load_dataset_kwargs = self.get_dataset_path_and_kwargs()
            dataset = task_processor.load_dataset(
                path,
                data_keys=data_keys,
                only_keep_necessary_columns=only_keep_necessary_columns,
                load_smallest_split=LOAD_SMALLEST_SPLIT,
                num_samples=NUM_SAMPLES,
                **load_dataset_kwargs,
                download_config=download_config,
            )
            if only_keep_necessary_columns:
                dataset_with_all_columns = task_processor.load_dataset(
                    path,
                    data_keys=data_keys,
                    load_smallest_split=LOAD_SMALLEST_SPLIT,
                    num_samples=NUM_SAMPLES,
                    **load_dataset_kwargs,
                    download_config=download_config,
                )

        # We only check if the column names of the dataset with the not necessary columns removed are a strict subset
        # of the dataset with all the columns.
        if dataset_with_all_columns is not None:
            if isinstance(dataset, DatasetDict):
                for split_name, split in dataset.items():
                    self.assertLess(set(split.column_names), set(dataset_with_all_columns[split_name].column_names))
            else:
                self.assertLess(set(dataset.column_names), set(dataset_with_all_columns.column_names))

        return dataset

    @require_datasets
    @pytest.mark.datasets_test
    def test_load_dataset(self):
        return self._test_load_dataset(False, False, False)

    @require_datasets
    @pytest.mark.datasets_test
    def test_load_dataset_by_guessing_data_keys(self):
        return self._test_load_dataset(False, True, False)

    @require_datasets
    @pytest.mark.datasets_test
    def test_load_dataset_and_only_keep_necessary_columns(self):
        return self._test_load_dataset(False, False, True)

    @require_datasets
    @pytest.mark.datasets_test
    def test_load_default_dataset(self):
        return self._test_load_dataset(True, False, False)


class TextClassificationProcessorTest(TestCase, TaskProcessorTestBase):
    TASK_NAME = "text-classification"
    CONFIG = CONFIG
    PREPROCESSOR = TOKENIZER
    WRONG_PREPROCESSOR = IMAGE_PROCESSOR

    @require_datasets
    @pytest.mark.datasets_test
    def test_load_dataset_with_max_length(self):
        max_length = random.randint(4, 16)
        dataset = self._test_load_dataset(False, False, True, max_length=max_length)
        if isinstance(dataset, DatasetDict):
            first_split = list(dataset.keys())[0]
            dataset = dataset[first_split]
        input_ids = dataset[0]["input_ids"]
        self.assertEqual(len(input_ids), max_length)


class TokenClassificationProcessorTest(TestCase, TaskProcessorTestBase):
    TASK_NAME = "token-classification"
    CONFIG = CONFIG
    PREPROCESSOR = TOKENIZER
    WRONG_PREPROCESSOR = IMAGE_PROCESSOR

    @require_datasets
    @pytest.mark.datasets_test
    def test_load_dataset_with_max_length(self):
        max_length = random.randint(4, 16)
        dataset = self._test_load_dataset(False, False, True, max_length=max_length)
        if isinstance(dataset, DatasetDict):
            first_split = list(dataset.keys())[0]
            dataset = dataset[first_split]
        input_ids = dataset[0]["input_ids"]
        self.assertEqual(len(input_ids), max_length)

    @require_datasets
    @pytest.mark.datasets_test
    def test_load_default_dataset(self):
        self.skipTest(
            "Skipping so as not to execute conll2003 remote code (test would require trust_remote_code=True)"
        )


class QuestionAnsweringProcessorTest(TestCase, TaskProcessorTestBase):
    TASK_NAME = "question-answering"
    CONFIG = CONFIG
    PREPROCESSOR = TOKENIZER
    WRONG_PREPROCESSOR = IMAGE_PROCESSOR

    @require_datasets
    @pytest.mark.datasets_test
    def test_load_dataset_with_max_length(self):
        max_length = 384
        dataset = self._test_load_dataset(False, False, True, max_length=max_length)
        if isinstance(dataset, DatasetDict):
            first_split = list(dataset.keys())[0]
            dataset = dataset[first_split]
        input_ids = dataset[0]["input_ids"]
        self.assertEqual(len(input_ids), max_length)


class ImageClassificationProcessorTest(TestCase, TaskProcessorTestBase):
    TASK_NAME = "image-classification"
    CONFIG = CONFIG
    PREPROCESSOR = IMAGE_PROCESSOR
    WRONG_PREPROCESSOR = TOKENIZER
