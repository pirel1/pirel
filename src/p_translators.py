import os
from collections import OrderedDict

import d_ast_parse
import d_grammar_expand
import d_utils
import p_consts
import p_utils


logger = p_utils.setup_logger(__name__)
# Root cause:
# Keeping many TransSession objects alive causes high RSS because each session
# may accumulate large parser/alt-slot state after heavy translations.
# Fix rationale:
# Keep a small LRU of "hot" translators for speed, and evict old/heavy entries
# proactively instead of retaining up to 1000 sessions and clearing all at once.
_TRANSLATORS_CACHE = OrderedDict()
_MAX_CACHE_SIZE = int(os.environ.get('PIREL_TRANSLATOR_CACHE_SIZE', '24'))
_MAX_TOTAL_WEIGHT = int(os.environ.get('PIREL_TRANSLATOR_CACHE_MAX_WEIGHT', '50000'))
_SRC_PARSE_CACHE = {}
_SRC_PARSE_CACHE_MAX_SIZE = 2000


def _estimate_translator_weight(translator: d_grammar_expand.TransSession) -> int:
  '''
  Approximate memory weight of a translator using internal state sizes.
  '''
  parser_results = len(getattr(translator, '_alt_parser_result_dict', {}))
  slot_expand_info = len(getattr(translator, '_slot_expand_info_dict', {}))
  alt_tree = len(getattr(translator, '_alt_tree_dict', {}))
  return parser_results + slot_expand_info + alt_tree


def _translators_cache_total_weight() -> int:
  total = 0
  for translator_info in _TRANSLATORS_CACHE.values():
    translator = translator_info.get('translator')
    if translator is None:
      continue
    total += _estimate_translator_weight(translator)
  return total


def _evict_translators_cache_if_needed() -> None:
  evicted_by_count = 0
  while len(_TRANSLATORS_CACHE) > _MAX_CACHE_SIZE:
    _TRANSLATORS_CACHE.popitem(last=False)
    evicted_by_count += 1

  evicted_by_weight = 0
  if _MAX_TOTAL_WEIGHT > 0:
    current_weight = _translators_cache_total_weight()
    # Keep at least one entry to preserve fast-path behavior for immediate retries.
    while len(_TRANSLATORS_CACHE) > 1 and current_weight > _MAX_TOTAL_WEIGHT:
      _TRANSLATORS_CACHE.popitem(last=False)
      evicted_by_weight += 1
      current_weight = _translators_cache_total_weight()

  if evicted_by_count > 0 or evicted_by_weight > 0:
    logger.debug(
      'translator cache eviction: '
      f'count_evicted={evicted_by_count}, '
      f'weight_evicted={evicted_by_weight}, '
      f'remaining_entries={len(_TRANSLATORS_CACHE)}, '
      f'remaining_weight={_translators_cache_total_weight()}')


def _get_src_parse_cached(src_code: str, src_lang: str):
  cache_key = d_utils.strings_sha256([src_lang, src_code])
  if cache_key in _SRC_PARSE_CACHE:
    return _SRC_PARSE_CACHE[cache_key]

  src_ast, src_ann = d_ast_parse.parse_text_dbg(src_code, src_lang)
  if len(_SRC_PARSE_CACHE) > _SRC_PARSE_CACHE_MAX_SIZE:
    _SRC_PARSE_CACHE.clear()
  _SRC_PARSE_CACHE[cache_key] = (src_ast, src_ann)
  return src_ast, src_ann


def get_translator_cached(
  src_code: str,
  src_lang: str,
  tar_lang: str,
  translation_rules: str,
  slot_dedup_enabled: bool,
) -> d_grammar_expand.TransSession:

  translator_key = d_utils.strings_sha256(
    [src_code, translation_rules, src_lang, tar_lang, str(slot_dedup_enabled)])
  logger.debug(
    f'translators cache size: {len(_TRANSLATORS_CACHE)} '
    f'(weight={_translators_cache_total_weight()}, '
    f'max_size={_MAX_CACHE_SIZE}, max_weight={_MAX_TOTAL_WEIGHT})')

  translator_info = None
  translator = None

  if translator_key in _TRANSLATORS_CACHE:
    logger.debug('cache hit: translator found in cache')
    translator_info = _TRANSLATORS_CACHE.pop(translator_key)
    _TRANSLATORS_CACHE[translator_key] = translator_info
    assert translator_info['src_code'] == src_code
    assert translator_info['translation_rules'] == translation_rules
    assert translator_info['src_lang'] == src_lang
    assert translator_info['tar_lang'] == tar_lang
    translator = translator_info['translator']

  else:
    logger.debug('cache miss: translator not found in cache')
    src_ast, src_ann = _get_src_parse_cached(src_code, src_lang)
    target_grammar = p_consts.GRAMMAR_DICT[tar_lang]
    _optional_dbg_info_save_func = lambda *args, **kwargs: None

    translator = d_grammar_expand.TransSession(
      src_code,
      src_ast,
      src_ann,
      src_lang,
      tar_lang,
      target_grammar,
      translation_rules,
      _optional_dbg_info_save_func,
      slot_dedup_enabled
    )

    translator_info = {
      'src_code': src_code,
      'src_lang': src_lang,
      'tar_lang': tar_lang,
      'translation_rules': translation_rules,
      'translator': translator
    }
    _TRANSLATORS_CACHE[translator_key] = translator_info
    _evict_translators_cache_if_needed()

  assert translator is not None and translator_info is not None
  return translator
