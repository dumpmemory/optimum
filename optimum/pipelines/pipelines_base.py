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
"""Pipelines running different backends."""

from typing import Any, Dict, Optional, Union

from transformers import (
    AudioClassificationPipeline,
    AutoConfig,
    AutoFeatureExtractor,
    AutoImageProcessor,
    AutomaticSpeechRecognitionPipeline,
    AutoTokenizer,
    FeatureExtractionPipeline,
    FillMaskPipeline,
    ImageClassificationPipeline,
    ImageSegmentationPipeline,
    ImageToImagePipeline,
    ImageToTextPipeline,
    Pipeline,
    PreTrainedTokenizer,
    PreTrainedTokenizerFast,
    QuestionAnsweringPipeline,
    SequenceFeatureExtractor,
    SummarizationPipeline,
    Text2TextGenerationPipeline,
    TextClassificationPipeline,
    TextGenerationPipeline,
    TokenClassificationPipeline,
    TranslationPipeline,
    ZeroShotClassificationPipeline,
)
from transformers import pipeline as transformers_pipeline
from transformers.feature_extraction_utils import PreTrainedFeatureExtractor
from transformers.image_processing_utils import BaseImageProcessor
from transformers.pipelines import (
    FEATURE_EXTRACTOR_MAPPING,
    IMAGE_PROCESSOR_MAPPING,
    TOKENIZER_MAPPING,
    check_task,
    get_default_model_and_revision,
    infer_framework_load_model,
)
from transformers.pipelines import SUPPORTED_TASKS as TRANSFORMERS_SUPPORTED_TASKS

from ..utils import is_onnxruntime_available, is_transformers_version


if is_onnxruntime_available():
    from ..onnxruntime import (
        ORTModelForAudioClassification,
        ORTModelForCausalLM,
        ORTModelForFeatureExtraction,
        ORTModelForImageClassification,
        ORTModelForImageToImage,
        ORTModelForMaskedLM,
        ORTModelForQuestionAnswering,
        ORTModelForSemanticSegmentation,
        ORTModelForSeq2SeqLM,
        ORTModelForSequenceClassification,
        ORTModelForSpeechSeq2Seq,
        ORTModelForTokenClassification,
        ORTModelForVision2Seq,
    )
    from ..onnxruntime.modeling_ort import ORTModel

    ORT_SUPPORTED_TASKS = {
        "feature-extraction": {
            "impl": FeatureExtractionPipeline,
            "class": (ORTModelForFeatureExtraction,),
            "default": "distilbert-base-cased",
            "type": "text",  # feature extraction is only supported for text at the moment
        },
        "fill-mask": {
            "impl": FillMaskPipeline,
            "class": (ORTModelForMaskedLM,),
            "default": "bert-base-cased",
            "type": "text",
        },
        "image-classification": {
            "impl": ImageClassificationPipeline,
            "class": (ORTModelForImageClassification,),
            "default": "google/vit-base-patch16-224",
            "type": "image",
        },
        "image-segmentation": {
            "impl": ImageSegmentationPipeline,
            "class": (ORTModelForSemanticSegmentation,),
            "default": "nvidia/segformer-b0-finetuned-ade-512-512",
            "type": "image",
        },
        "question-answering": {
            "impl": QuestionAnsweringPipeline,
            "class": (ORTModelForQuestionAnswering,),
            "default": "distilbert-base-cased-distilled-squad",
            "type": "text",
        },
        "text-classification": {
            "impl": TextClassificationPipeline,
            "class": (ORTModelForSequenceClassification,),
            "default": "distilbert-base-uncased-finetuned-sst-2-english",
            "type": "text",
        },
        "text-generation": {
            "impl": TextGenerationPipeline,
            "class": (ORTModelForCausalLM,),
            "default": "distilgpt2",
            "type": "text",
        },
        "token-classification": {
            "impl": TokenClassificationPipeline,
            "class": (ORTModelForTokenClassification,),
            "default": "dbmdz/bert-large-cased-finetuned-conll03-english",
            "type": "text",
        },
        "zero-shot-classification": {
            "impl": ZeroShotClassificationPipeline,
            "class": (ORTModelForSequenceClassification,),
            "default": "facebook/bart-large-mnli",
            "type": "text",
        },
        "summarization": {
            "impl": SummarizationPipeline,
            "class": (ORTModelForSeq2SeqLM,),
            "default": "t5-base",
            "type": "text",
        },
        "translation": {
            "impl": TranslationPipeline,
            "class": (ORTModelForSeq2SeqLM,),
            "default": "t5-small",
            "type": "text",
        },
        "text2text-generation": {
            "impl": Text2TextGenerationPipeline,
            "class": (ORTModelForSeq2SeqLM,),
            "default": "t5-small",
            "type": "text",
        },
        "automatic-speech-recognition": {
            "impl": AutomaticSpeechRecognitionPipeline,
            "class": (ORTModelForSpeechSeq2Seq,),
            "default": "openai/whisper-tiny.en",
            "type": "multimodal",
        },
        "image-to-text": {
            "impl": ImageToTextPipeline,
            "class": (ORTModelForVision2Seq,),
            "default": "nlpconnect/vit-gpt2-image-captioning",
            "type": "multimodal",
        },
        "audio-classification": {
            "impl": AudioClassificationPipeline,
            "class": (ORTModelForAudioClassification,),
            "default": "superb/hubert-base-superb-ks",
            "type": "audio",
        },
        "image-to-image": {
            "impl": ImageToImagePipeline,
            "class": (ORTModelForImageToImage,),
            "default": "caidas/swin2SR-classical-sr-x2-64",
            "type": "image",
        },
    }
else:
    ORT_SUPPORTED_TASKS = {}


def load_bettertransformer(
    model,
    targeted_task,
    load_tokenizer=None,
    tokenizer=None,
    feature_extractor=None,
    load_feature_extractor=None,
    image_processor=None,
    load_image_processor=None,
    SUPPORTED_TASKS=None,
    subfolder: str = "",
    token: Optional[Union[bool, str]] = None,
    revision: str = "main",
    model_kwargs: Optional[Dict[str, Any]] = None,
    config: AutoConfig = None,
    hub_kwargs: Optional[Dict] = None,
    **kwargs,
):
    from ..bettertransformer import BetterTransformer

    if model_kwargs is None:
        # the argument was first introduced in 4.36.0 but most models didn't have an sdpa implementation then
        # see https://github.com/huggingface/transformers/blob/v4.36.0/src/transformers/modeling_utils.py#L1258
        if is_transformers_version(">=", "4.36.0"):
            model_kwargs = {"attn_implementation": "eager"}
        else:
            model_kwargs = {}

    if isinstance(model, str):
        model_id = model
    else:
        model_id = None

    model_classes = {"pt": SUPPORTED_TASKS[targeted_task]["pt"]}
    framework, model = infer_framework_load_model(
        model,
        model_classes=model_classes,
        config=config,
        framework="pt",
        task=targeted_task,
        **hub_kwargs,
        **model_kwargs,
    )

    if framework == "tf":
        raise NotImplementedError(
            "BetterTransormer is PyTorch-specific. It will not work with the provided TensorFlow model."
        )

    model = BetterTransformer.transform(model, **kwargs)

    return model, model_id, tokenizer, feature_extractor, image_processor


def load_ort_pipeline(
    model,
    targeted_task,
    load_tokenizer,
    tokenizer,
    feature_extractor,
    load_feature_extractor,
    image_processor,
    load_image_processor,
    SUPPORTED_TASKS,
    subfolder: str = "",
    token: Optional[Union[bool, str]] = None,
    revision: str = "main",
    model_kwargs: Optional[Dict[str, Any]] = None,
    config: AutoConfig = None,
    **kwargs,
):
    if model_kwargs is None:
        model_kwargs = {}

    if isinstance(model, str):
        model_id = model
        model = SUPPORTED_TASKS[targeted_task]["class"][0].from_pretrained(
            model, revision=revision, subfolder=subfolder, token=token, **model_kwargs
        )
    elif isinstance(model, ORTModel):
        if tokenizer is None and load_tokenizer:
            for preprocessor in model.preprocessors:
                if isinstance(preprocessor, (PreTrainedTokenizer, PreTrainedTokenizerFast)):
                    tokenizer = preprocessor
                    break
            if tokenizer is None:
                raise ValueError(
                    "Could not automatically find a tokenizer for the ORTModel, you must pass a tokenizer explictly"
                )
        if feature_extractor is None and load_feature_extractor:
            for preprocessor in model.preprocessors:
                if isinstance(preprocessor, SequenceFeatureExtractor):
                    feature_extractor = preprocessor
                    break
            if feature_extractor is None:
                raise ValueError(
                    "Could not automatically find a feature extractor for the ORTModel, you must pass a "
                    "feature_extractor explictly"
                )
        if image_processor is None and load_image_processor:
            for preprocessor in model.preprocessors:
                if isinstance(preprocessor, BaseImageProcessor):
                    image_processor = preprocessor
                    break
            if image_processor is None:
                raise ValueError(
                    "Could not automatically find a feature extractor for the ORTModel, you must pass a "
                    "image_processor explictly"
                )

        model_id = None
    else:
        raise ValueError(
            f"""Model {model} is not supported. Please provide a valid model either as string or ORTModel.
            You can also provide non model then a default one will be used"""
        )
    return model, model_id, tokenizer, feature_extractor, image_processor


MAPPING_LOADING_FUNC = {
    "ort": load_ort_pipeline,
    "bettertransformer": load_bettertransformer,
}


def pipeline(
    task: str = None,
    model: Optional[Any] = None,
    tokenizer: Optional[Union[str, PreTrainedTokenizer]] = None,
    feature_extractor: Optional[Union[str, PreTrainedFeatureExtractor]] = None,
    image_processor: Optional[Union[str, BaseImageProcessor]] = None,
    use_fast: bool = True,
    token: Optional[Union[str, bool]] = None,
    accelerator: Optional[str] = "ort",
    revision: Optional[str] = None,
    trust_remote_code: Optional[bool] = None,
    *model_kwargs,
    **kwargs,
) -> Pipeline:
    targeted_task = "translation" if task.startswith("translation") else task

    if accelerator == "ort":
        if targeted_task not in list(ORT_SUPPORTED_TASKS.keys()):
            raise ValueError(
                f"Task {targeted_task} is not supported for the ONNX Runtime pipeline. Supported tasks are { list(ORT_SUPPORTED_TASKS.keys())}"
            )

    if accelerator not in MAPPING_LOADING_FUNC:
        raise ValueError(
            f'Accelerator {accelerator} is not supported. Supported accelerators are "ort" and "bettertransformer".'
        )

    supported_tasks = ORT_SUPPORTED_TASKS if accelerator == "ort" else TRANSFORMERS_SUPPORTED_TASKS

    if model is None:
        if accelerator != "ort":
            _, target_task, task_options = check_task(task)
            model, default_revision = get_default_model_and_revision(target_task, "pt", task_options)
            revision = revision or default_revision
        else:
            model = supported_tasks[targeted_task]["default"]

    hub_kwargs = {
        "revision": revision,
        "token": token,
        "trust_remote_code": trust_remote_code,
        "_commit_hash": None,
    }

    config = kwargs.get("config", None)
    if config is None and isinstance(model, str):
        config = AutoConfig.from_pretrained(model, _from_pipeline=task, **hub_kwargs, **kwargs)
        hub_kwargs["_commit_hash"] = config._commit_hash

    no_feature_extractor_tasks = set()
    no_tokenizer_tasks = set()
    no_image_processor_tasks = set()
    for _task, values in supported_tasks.items():
        if values["type"] == "text":
            no_feature_extractor_tasks.add(_task)
            no_image_processor_tasks.add(_task)
        elif values["type"] in {"image", "video"}:
            no_tokenizer_tasks.add(_task)
        elif values["type"] in {"audio"}:
            no_tokenizer_tasks.add(_task)
            no_image_processor_tasks.add(_task)
        elif values["type"] not in ["multimodal", "audio", "video"]:
            raise ValueError(f"SUPPORTED_TASK {_task} contains invalid type {values['type']}")

    model_config = config or model.config
    load_tokenizer = type(model_config) in TOKENIZER_MAPPING or model_config.tokenizer_class is not None
    load_feature_extractor = type(model_config) in FEATURE_EXTRACTOR_MAPPING or feature_extractor is not None
    load_image_processor = type(model_config) in IMAGE_PROCESSOR_MAPPING or image_processor is not None

    # copied from transformers.pipelines.__init__.py l.609
    if targeted_task in no_tokenizer_tasks:
        # These will never require a tokenizer.
        # the model on the other hand might have a tokenizer, but
        # the files could be missing from the hub, instead of failing
        # on such repos, we just force to not load it.
        load_tokenizer = False

    if targeted_task in no_feature_extractor_tasks:
        load_feature_extractor = False

    if targeted_task in no_image_processor_tasks:
        load_image_processor = False

    if load_image_processor and load_feature_extractor:
        load_feature_extractor = False

    model, model_id, tokenizer, feature_extractor, image_processor = MAPPING_LOADING_FUNC[accelerator](
        model,
        targeted_task,
        load_tokenizer,
        tokenizer,
        feature_extractor,
        load_feature_extractor,
        image_processor,
        load_image_processor,
        SUPPORTED_TASKS=supported_tasks,
        config=config,
        hub_kwargs=hub_kwargs,
        token=token,
        *model_kwargs,
        **kwargs,
    )

    use_fast = kwargs.get(use_fast, "True")
    if tokenizer is None and load_tokenizer:
        tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=use_fast, **hub_kwargs)
    if feature_extractor is None and load_feature_extractor:
        feature_extractor = AutoFeatureExtractor.from_pretrained(model_id, use_fast=use_fast, **hub_kwargs)
    if image_processor is None and load_image_processor:
        image_processor = AutoImageProcessor.from_pretrained(model_id, **hub_kwargs)

    return transformers_pipeline(
        task,
        model=model,
        tokenizer=tokenizer,
        feature_extractor=feature_extractor,
        image_processor=image_processor,
        use_fast=use_fast,
        **kwargs,
    )
