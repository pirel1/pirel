import p_consts
from pathlib import Path
from typing import List, Optional


class Config:
  benchmark_name: str = None
  subject_names: List[str] = None

  src_lang: str = None
  tar_lang: str = None
  is_three_split: bool = None
  translation_order: str = p_consts.TranslationOrder.EOT

  overriding_rulesets: List[Path] = None

  max_concurrent_subjects: int = None
  reuse_translation_rules: bool = None

  is_email_report: bool = None

  model_params: dict = {
    'model_name': p_consts.OpenAIModelNames.GPT5_NANO,
    'temperature': 1.0,
    'max_completion_tokens': 16384,
    'request_timeout': None,
    'max_retries': 2,
  }
  use_reduced_prompts: bool = False
  is_enable_llm_cache: bool = True

  generator: str = 'lightweight'

  prefer_shorter_rules: bool = True  # NOTE not configured through CLI
  js_global_fn_whitelist: List[str] = [
    'parseInt', 'parseFloat', 'isNaN', 'isFinite',
    'Number', 'String', 'Boolean', 'BigInt',
    'Array', 'Object', 'Math', 'JSON',
  ]


def load_configs(args):
  Config.benchmark_name = args.benchmark_name
  Config.subject_names = args.arg_subject_names

  Config.src_lang = args.src_lang
  Config.tar_lang = args.tar_lang
  Config.is_three_split = args.is_three_split
  Config.translation_order = args.translation_order

  Config.overriding_rulesets = args.overriding_rulesets

  Config.max_concurrent_subjects = args.max_concurrent_subjects
  Config.reuse_translation_rules = args.reuse_translation_rules

  Config.is_email_report = args.is_email_report

  Config.model_params['model_name'] = args.openai_model_name
  Config.use_reduced_prompts = args.use_reduced_prompts

  Config.generator = args.generator
