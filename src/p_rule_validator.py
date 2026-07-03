import asyncio
import copy
import hashlib
import json
import os
import re
from typing import Dict, List, Optional, Tuple

import d_grammar_expand
import d_grammar_rules
import p_consts
import p_ext_rule_chooser
import p_pirel
import p_code_runner
from p_config import Config
import p_rule_applicator as prapp
import p_rule_postprocessor as prpp
import p_ruleset
import p_subject
import p_tree_log as ptlog
import p_utils


logger = p_utils.setup_logger(__name__)


class RulesExistNoneValid(RuntimeError): pass


_RUNTIME_HELPER_DEF_CACHE = {}
_CALLED_JS_FN_RE = re.compile(r'\("js\.call_expression"\s+\("js\.identifier"\s+\(val\s+"([^"]+)"\)\)')

_STAT_NODE_VALIDATE_EXPRS_CACHE_MAX_SIZE = 1024
# Root cause:
# stat_node_validate_exprs cache entries can become very large when they carry
# full serialized rule dicts, which inflates both RAM and on-disk JSON size.
# Fix rationale:
# keep compact hash payloads, cap total in-memory bytes, and load only recent
# entries to preserve hit-rate while avoiding runaway memory.
_STAT_NODE_VALIDATE_EXPRS_CACHE_MAX_TOTAL_BYTES = int(
  os.environ.get('PIREL_STAT_NODE_VALIDATE_CACHE_MAX_BYTES', str(32 * 1024 * 1024))
)
_STAT_NODE_VALIDATE_EXPRS_CACHE_LOAD_RECENT_MAX = int(
  os.environ.get('PIREL_STAT_NODE_VALIDATE_CACHE_LOAD_RECENT_MAX', '256')
)
_STAT_NODE_VALIDATE_EXPRS_CACHE_FPATH = p_consts.VALIDATION_CACHE_DIR / 'stat-node-validate-exprs-cache.json'
_STAT_NODE_VALIDATE_EXPRS_CACHE: Dict[str, dict] = {}
# relaxed_key -> ordered cache_key list
# Purpose: recover from cache misses caused only by ruleset-hash churn.
_STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX: Dict[str, List[str]] = {}
_STAT_NODE_VALIDATE_EXPRS_CACHE_LOADED = False
_STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES = 0


def _safe_int_ms(value: object) -> int:
  try:
    ms = int(value)
  except Exception:
    return 0
  return ms if ms > 0 else 0


def _accumulate_cached_validation_ms(
  lstat_node_val: Optional[ptlog.StatNodeVal],
  delta_ms: object,
  bucket_attr: str = 'cached_validation_ms',
) -> None:
  if lstat_node_val is None:
    return
  delta = _safe_int_ms(delta_ms)
  if delta <= 0:
    return

  current_bucket = _safe_int_ms(getattr(lstat_node_val, bucket_attr, 0))
  setattr(lstat_node_val, bucket_attr, current_bucket + delta)

  if bucket_attr != 'cached_validation_ms':
    current_total = _safe_int_ms(getattr(lstat_node_val, 'cached_validation_ms', 0))
    lstat_node_val.cached_validation_ms = current_total + delta


def _rule_hash_from_rule_str(rule_str: str) -> str:
  return hashlib.sha256(rule_str.encode('utf-8')).hexdigest()


def _normalize_rule_hashes_map(
  encoded_to_rule_hashes: object
) -> Optional[Dict[str, List[str]]]:
  if not isinstance(encoded_to_rule_hashes, dict):
    return None
  normalized: Dict[str, List[str]] = {}
  for encoded_ast, rule_hashes in encoded_to_rule_hashes.items():
    if not isinstance(encoded_ast, str) or not isinstance(rule_hashes, list):
      continue
    clean_hashes: List[str] = []
    for rule_hash in rule_hashes:
      if not isinstance(rule_hash, str) or len(rule_hash) == 0:
        continue
      if rule_hash in clean_hashes:
        continue
      clean_hashes.append(rule_hash)
    if len(clean_hashes) > 0:
      normalized[encoded_ast] = clean_hashes
  return normalized


def _legacy_serialized_rules_to_hashes(
  encoded_to_rules: object
) -> Dict[str, List[str]]:
  '''
  Convert legacy v2 payload (full serialized rules) into compact rule hashes.
  '''
  if not isinstance(encoded_to_rules, dict):
    return {}
  converted: Dict[str, List[str]] = {}
  for encoded_ast, serialized_trules in encoded_to_rules.items():
    if not isinstance(encoded_ast, str) or not isinstance(serialized_trules, list):
      continue
    rule_hashes: List[str] = []
    for serialized_trule in serialized_trules:
      if not isinstance(serialized_trule, dict):
        continue
      rule_str = serialized_trule.get('rule_str')
      if not isinstance(rule_str, str) or len(rule_str) == 0:
        continue
      rule_hash = _rule_hash_from_rule_str(rule_str)
      if rule_hash in rule_hashes:
        continue
      rule_hashes.append(rule_hash)
    if len(rule_hashes) > 0:
      converted[encoded_ast] = rule_hashes
  return converted


def _compute_stat_node_cache_entry_bytes(cache_payload: dict) -> int:
  try:
    return len(json.dumps(
      cache_payload,
      ensure_ascii=False,
      sort_keys=True,
      separators=(',', ':')
    ).encode('utf-8'))
  except Exception:
    return 0


def _normalize_stat_node_validate_exprs_cache_entry(
  cached: object
) -> Optional[dict]:
  if not isinstance(cached, dict):
    return None

  verified_choice_options = cached.get('verified_choice_options')
  if verified_choice_options is not None and not isinstance(verified_choice_options, list):
    verified_choice_options = None

  cache_meta = cached.get('cache_meta', {})
  if not isinstance(cache_meta, dict):
    cache_meta = {}
  else:
    cache_meta = copy.deepcopy(cache_meta)

  verified_rule_hashes = _normalize_rule_hashes_map(cached.get('verified_rule_hashes'))
  if verified_rule_hashes is None:
    verified_rule_hashes = _legacy_serialized_rules_to_hashes(cached.get('verified_rules', {}))

  unverifiable_rule_hashes = _normalize_rule_hashes_map(cached.get('unverifiable_rule_hashes'))
  if unverifiable_rule_hashes is None:
    unverifiable_rule_hashes = _legacy_serialized_rules_to_hashes(cached.get('unverifiable_rules', {}))

  payload = {
    'verified_rule_hashes': verified_rule_hashes,
    'unverifiable_rule_hashes': unverifiable_rule_hashes,
    'verified_choice_options': verified_choice_options,
    'cache_meta': cache_meta,
  }
  entry_bytes = _compute_stat_node_cache_entry_bytes(payload)
  cache_meta['entry_bytes'] = entry_bytes
  payload['cache_meta'] = cache_meta
  return payload


def _cache_entry_bytes(cache_payload: dict) -> int:
  cache_meta = cache_payload.get('cache_meta', {})
  if isinstance(cache_meta, dict):
    entry_bytes = cache_meta.get('entry_bytes')
    if isinstance(entry_bytes, int) and entry_bytes >= 0:
      return entry_bytes
  entry_bytes = _compute_stat_node_cache_entry_bytes(cache_payload)
  if not isinstance(cache_meta, dict):
    cache_meta = {}
    cache_payload['cache_meta'] = cache_meta
  cache_meta['entry_bytes'] = entry_bytes
  return entry_bytes


def _ensure_stat_node_validate_exprs_cache_loaded() -> None:
  global _STAT_NODE_VALIDATE_EXPRS_CACHE_LOADED
  global _STAT_NODE_VALIDATE_EXPRS_CACHE
  global _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX
  global _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES
  if _STAT_NODE_VALIDATE_EXPRS_CACHE_LOADED:
    return
  _STAT_NODE_VALIDATE_EXPRS_CACHE_LOADED = True
  _STAT_NODE_VALIDATE_EXPRS_CACHE = {}
  _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX = {}
  _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES = 0
  if not _STAT_NODE_VALIDATE_EXPRS_CACHE_FPATH.exists():
    return
  try:
    payload = p_utils.read_json(_STAT_NODE_VALIDATE_EXPRS_CACHE_FPATH)
    entries = payload.get('entries', {})
    relaxed_index = payload.get('relaxed_index', {})
    if not isinstance(entries, dict):
      logger.warning('Unexpected stat_node_validate_exprs cache payload format; starting with empty cache.')
      return
    if not isinstance(relaxed_index, dict):
      relaxed_index = {}

    entry_items = list(entries.items())
    if (
      _STAT_NODE_VALIDATE_EXPRS_CACHE_LOAD_RECENT_MAX > 0
      and len(entry_items) > _STAT_NODE_VALIDATE_EXPRS_CACHE_LOAD_RECENT_MAX
    ):
      dropped = len(entry_items) - _STAT_NODE_VALIDATE_EXPRS_CACHE_LOAD_RECENT_MAX
      entry_items = entry_items[-_STAT_NODE_VALIDATE_EXPRS_CACHE_LOAD_RECENT_MAX:]
      logger.info(
        'Trimmed loaded stat_node_validate_exprs cache entries '
        f'to most recent {_STAT_NODE_VALIDATE_EXPRS_CACHE_LOAD_RECENT_MAX} '
        f'(dropped={dropped}).'
      )

    for cache_key, cached in entry_items:
      if not isinstance(cache_key, str):
        continue
      normalized_payload = _normalize_stat_node_validate_exprs_cache_entry(cached)
      if normalized_payload is None:
        continue
      _STAT_NODE_VALIDATE_EXPRS_CACHE[cache_key] = normalized_payload
      _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES += _cache_entry_bytes(normalized_payload)
      cache_meta = normalized_payload.get('cache_meta', {})
      relaxed_key = cache_meta.get('relaxed_key') if isinstance(cache_meta, dict) else None
      if isinstance(relaxed_key, str) and len(relaxed_key) > 0:
        _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX.setdefault(relaxed_key, []).append(cache_key)

    for relaxed_key, cache_keys in relaxed_index.items():
      if not isinstance(relaxed_key, str):
        continue
      if not isinstance(cache_keys, list):
        continue
      for cache_key in cache_keys:
        if not isinstance(cache_key, str):
          continue
        if cache_key not in _STAT_NODE_VALIDATE_EXPRS_CACHE:
          continue
        _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX.setdefault(relaxed_key, [])
        if cache_key in _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX[relaxed_key]:
          continue
        _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX[relaxed_key].append(cache_key)
    for relaxed_key in list(_STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX):
      filtered = [
        cache_key for cache_key in _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX[relaxed_key]
        if cache_key in _STAT_NODE_VALIDATE_EXPRS_CACHE
      ]
      if len(filtered) == 0:
        _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX.pop(relaxed_key, None)
      else:
        _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX[relaxed_key] = filtered

    while len(_STAT_NODE_VALIDATE_EXPRS_CACHE) > _STAT_NODE_VALIDATE_EXPRS_CACHE_MAX_SIZE:
      _evict_oldest_stat_node_validate_exprs_cache_entry()
    while (
      _STAT_NODE_VALIDATE_EXPRS_CACHE_MAX_TOTAL_BYTES > 0
      and len(_STAT_NODE_VALIDATE_EXPRS_CACHE) > 1
      and _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES > _STAT_NODE_VALIDATE_EXPRS_CACHE_MAX_TOTAL_BYTES
    ):
      _evict_oldest_stat_node_validate_exprs_cache_entry()
  except Exception as err:
    logger.warning(f'Failed to load stat_node_validate_exprs cache: {err}')
    _STAT_NODE_VALIDATE_EXPRS_CACHE = {}
    _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX = {}
    _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES = 0


def _persist_stat_node_validate_exprs_cache() -> None:
  payload = {
    # v3 stores compact rule-hash payloads and explicit relaxed index.
    # across nearby ruleset variants.
    'version': 3,
    'entries': _STAT_NODE_VALIDATE_EXPRS_CACHE,
    'relaxed_index': _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX,
  }
  try:
    _STAT_NODE_VALIDATE_EXPRS_CACHE_FPATH.parent.mkdir(parents=True, exist_ok=True)
    p_utils.write_json(_STAT_NODE_VALIDATE_EXPRS_CACHE_FPATH, payload)
  except Exception as err:
    logger.warning(f'Failed to persist stat_node_validate_exprs cache: {err}')


def _remove_cache_key_from_relaxed_index(cache_key: str) -> None:
  for relaxed_key in list(_STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX):
    cache_keys = _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX.get(relaxed_key, [])
    if cache_key not in cache_keys:
      continue
    _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX[relaxed_key] = [
      key for key in cache_keys if key != cache_key
    ]
    if len(_STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX[relaxed_key]) == 0:
      _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX.pop(relaxed_key, None)


def _remove_stat_node_validate_exprs_cache_entry(cache_key: str) -> None:
  global _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES
  cached_payload = _STAT_NODE_VALIDATE_EXPRS_CACHE.pop(cache_key, None)
  if isinstance(cached_payload, dict):
    _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES = max(
      0,
      _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES - _cache_entry_bytes(cached_payload)
    )
  _remove_cache_key_from_relaxed_index(cache_key)


def _evict_oldest_stat_node_validate_exprs_cache_entry() -> None:
  if len(_STAT_NODE_VALIDATE_EXPRS_CACHE) == 0:
    return
  oldest_cache_key = next(iter(_STAT_NODE_VALIDATE_EXPRS_CACHE))
  _remove_stat_node_validate_exprs_cache_entry(oldest_cache_key)


def _store_stat_node_validate_exprs_cache(
  cache_key: str,
  relaxed_key: str,
  ruleset_side_effect_rule_hashes: dict,
  verified_choice_options: Optional[List[Tuple[Tuple[int, int, int], List[int]]]] = None,
  cache_meta: Optional[dict] = None,
) -> None:
  global _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES
  _ensure_stat_node_validate_exprs_cache_loaded()
  cache_meta_payload = copy.deepcopy(cache_meta) if isinstance(cache_meta, dict) else {}
  # Keep relaxed key in entry metadata so index can be rebuilt from entries.
  cache_meta_payload['relaxed_key'] = relaxed_key
  cache_meta_payload['cached_at_ms'] = p_utils.current_time_msec()
  payload = {
    'verified_rule_hashes': copy.deepcopy(ruleset_side_effect_rule_hashes.get('verified_rule_hashes', {})),
    'unverifiable_rule_hashes': copy.deepcopy(ruleset_side_effect_rule_hashes.get('unverifiable_rule_hashes', {})),
    'verified_choice_options': copy.deepcopy(verified_choice_options),
    'cache_meta': cache_meta_payload,
  }
  cache_meta_payload['entry_bytes'] = _compute_stat_node_cache_entry_bytes(payload)
  payload['cache_meta'] = cache_meta_payload
  if cache_key in _STAT_NODE_VALIDATE_EXPRS_CACHE:
    _remove_stat_node_validate_exprs_cache_entry(cache_key)
  _STAT_NODE_VALIDATE_EXPRS_CACHE[cache_key] = payload
  _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES += _cache_entry_bytes(payload)
  _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX.setdefault(relaxed_key, [])
  _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX[relaxed_key].append(cache_key)
  while len(_STAT_NODE_VALIDATE_EXPRS_CACHE) > _STAT_NODE_VALIDATE_EXPRS_CACHE_MAX_SIZE:
    _evict_oldest_stat_node_validate_exprs_cache_entry()
  while (
    _STAT_NODE_VALIDATE_EXPRS_CACHE_MAX_TOTAL_BYTES > 0
    and len(_STAT_NODE_VALIDATE_EXPRS_CACHE) > 1
    and _STAT_NODE_VALIDATE_EXPRS_CACHE_TOTAL_BYTES > _STAT_NODE_VALIDATE_EXPRS_CACHE_MAX_TOTAL_BYTES
  ):
    _evict_oldest_stat_node_validate_exprs_cache_entry()
  _persist_stat_node_validate_exprs_cache()


def _make_stat_node_validate_exprs_cache_key(
  src_main_code: str,
  ruleset_hash: str,
  simple_ntext: str,
  subject_name: str,
) -> str:
  key_payload = {
    'src_main_code': src_main_code,
    'ruleset_hash': ruleset_hash,
    'simple_ntext': simple_ntext,
    'subject_name': subject_name,
  }
  key_json = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
  return hashlib.sha256(key_json.encode('utf-8')).hexdigest()


def _make_stat_node_validate_exprs_relaxed_cache_key(
  src_main_code: str,
  simple_ntext: str,
  subject_name: str,
) -> str:
  # Deliberately excludes ruleset hash: same statement/source can reuse
  # compatible validated rules even if global ruleset composition changed.
  key_payload = {
    'src_main_code': src_main_code,
    'simple_ntext': simple_ntext,
    'subject_name': subject_name,
  }
  key_json = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
  return hashlib.sha256(key_json.encode('utf-8')).hexdigest()


def _make_ruleset_hash(current_ruleset: p_ruleset.Ruleset) -> str:
  ruleset_str = current_ruleset.to_str_ruleset()
  return hashlib.sha256(ruleset_str.encode('utf-8')).hexdigest()


def _snapshot_ruleset_side_effects(current_ruleset: p_ruleset.Ruleset) -> dict:
  # Root cause:
  # Serializing full rule dicts into cache payloads makes each entry very large.
  # Fix rationale:
  # Persist only stable rule hashes and recover refs through ruleset hash index.
  return {
    'verified_rule_hashes': current_ruleset.get_verified_rule_hashes(),
    'unverifiable_rule_hashes': current_ruleset.get_unverifiable_rule_hashes(),
  }


def _normalize_verified_choice_options(
  verified_choice_options: object
) -> Optional[List[Tuple[Tuple[int, int, int], List[int]]]]:
  if not isinstance(verified_choice_options, list):
    return None
  normalized: List[Tuple[Tuple[int, int, int], List[int]]] = []
  for option in verified_choice_options:
    if not isinstance(option, (list, tuple)) or len(option) != 2:
      return None
    choice_ident, choice_idxs = option
    if not isinstance(choice_ident, (list, tuple)) or len(choice_ident) != 3:
      return None
    if not isinstance(choice_idxs, list):
      return None
    if not all(isinstance(v, int) for v in choice_ident):
      return None
    if not all(isinstance(v, int) for v in choice_idxs):
      return None
    normalized.append((tuple(choice_ident), choice_idxs))
  return normalized


def _apply_stat_node_validate_exprs_cache_entry(
  current_ruleset: p_ruleset.Ruleset,
  cache_payload: dict,
) -> Optional[List[Tuple[Tuple[int, int, int], List[int]]]]:
  verified_rule_hashes = _normalize_rule_hashes_map(cache_payload.get('verified_rule_hashes'))
  if verified_rule_hashes is None:
    verified_rule_hashes = _legacy_serialized_rules_to_hashes(
      cache_payload.get('verified_rules', {}))
  unverifiable_rule_hashes = _normalize_rule_hashes_map(cache_payload.get('unverifiable_rule_hashes'))
  if unverifiable_rule_hashes is None:
    unverifiable_rule_hashes = _legacy_serialized_rules_to_hashes(
      cache_payload.get('unverifiable_rules', {}))

  for encoded_ast, rule_hashes in verified_rule_hashes.items():
    for rule_hash in rule_hashes:
      rule_ref = current_ruleset.get_rule_ref_by_hash(rule_hash)
      if rule_ref is None:
        logger.warning(
          f'Ignoring cached verified rule hash for "{encoded_ast}" '
          'because it is not in current ruleset.')
        continue
      current_ruleset.update_verified_rules(encoded_ast, rule_ref)

  for encoded_ast, rule_hashes in unverifiable_rule_hashes.items():
    for rule_hash in rule_hashes:
      rule_ref = current_ruleset.get_rule_ref_by_hash(rule_hash)
      if rule_ref is None:
        logger.warning(
          f'Ignoring cached unverifiable rule hash for "{encoded_ast}" '
          'because it is not in current ruleset.')
        continue
      if current_ruleset.unverifiable_rules_exist(encoded_ast):
        existing_unverifiable_rules = current_ruleset.get_unverifiable_rules(encoded_ast)
        if rule_ref in existing_unverifiable_rules:
          continue
      current_ruleset.update_unverifiable_rules(encoded_ast, rule_ref)

  return _normalize_verified_choice_options(
    cache_payload.get('verified_choice_options'))


def _cache_payload_has_compatible_rule(
  current_ruleset: p_ruleset.Ruleset,
  cache_payload: dict,
) -> bool:
  # Safety filter for relaxed fallback: apply cache only when at least one
  # cached rule is still present in current ruleset.
  for payload_key in ('verified_rule_hashes', 'unverifiable_rule_hashes'):
    encoded_to_rule_hashes = _normalize_rule_hashes_map(cache_payload.get(payload_key, {}))
    if encoded_to_rule_hashes is None:
      continue
    for rule_hashes in encoded_to_rule_hashes.values():
      for rule_hash in rule_hashes:
        if current_ruleset.get_rule_ref_by_hash(rule_hash) is not None:
          return True

  # Backward compatibility for legacy cache payload that stores full rules.
  for payload_key in ('verified_rules', 'unverifiable_rules'):
    converted_hashes = _legacy_serialized_rules_to_hashes(cache_payload.get(payload_key, {}))
    for rule_hashes in converted_hashes.values():
      for rule_hash in rule_hashes:
        if current_ruleset.get_rule_ref_by_hash(rule_hash) is not None:
          return True
  return False


def _get_stat_node_validate_exprs_cache_payload(
  current_ruleset: p_ruleset.Ruleset,
  exact_cache_key: str,
  relaxed_cache_key: str,
) -> Tuple[Optional[dict], str]:
  # 1) Prefer exact cache hit.
  # 2) If exact miss, try relaxed hits that are rule-compatible.
  cache_payload = _STAT_NODE_VALIDATE_EXPRS_CACHE.get(exact_cache_key)
  if cache_payload is not None:
    # LRU touch: keep recently reused entries from being evicted first.
    _STAT_NODE_VALIDATE_EXPRS_CACHE.pop(exact_cache_key, None)
    _STAT_NODE_VALIDATE_EXPRS_CACHE[exact_cache_key] = cache_payload
    return cache_payload, 'exact'

  fallback_cache_keys = _STAT_NODE_VALIDATE_EXPRS_CACHE_RELAXED_IDX.get(relaxed_cache_key, [])
  for fallback_cache_key in reversed(fallback_cache_keys):
    fallback_payload = _STAT_NODE_VALIDATE_EXPRS_CACHE.get(fallback_cache_key)
    if fallback_payload is None:
      continue
    if not _cache_payload_has_compatible_rule(current_ruleset, fallback_payload):
      continue
    # LRU touch for relaxed reuse as well.
    _STAT_NODE_VALIDATE_EXPRS_CACHE.pop(fallback_cache_key, None)
    _STAT_NODE_VALIDATE_EXPRS_CACHE[fallback_cache_key] = fallback_payload
    return fallback_payload, f'relaxed({fallback_cache_key})'

  return None, 'miss'

def _runtime_helper_is_defined(lang: str, helper_name: str) -> bool:
  cache_key = (lang, helper_name)
  if cache_key in _RUNTIME_HELPER_DEF_CACHE:
    return _RUNTIME_HELPER_DEF_CACHE[cache_key]

  runtime_code = p_code_runner.get_mylog_impl(lang)
  # Simple definition checks for typical JS declaration styles.
  patterns = [
    rf'\bfunction\s+{re.escape(helper_name)}\b',
    rf'\b(?:const|let|var)\s+{re.escape(helper_name)}\b',
    rf'\b{re.escape(helper_name)}\s*=\s*function\b',
    rf'\bclass\s+{re.escape(helper_name)}\b',
  ]
  is_defined = any(re.search(pat, runtime_code) for pat in patterns)
  _RUNTIME_HELPER_DEF_CACHE[cache_key] = is_defined
  return is_defined


def _get_called_identifiers_in_js_expand(trule_str: str) -> List[str]:
  '''
  Extract identifiers used as direct JS function calls in the expand pattern.
  '''
  return _CALLED_JS_FN_RE.findall(trule_str)


def get_used_translation_rule_ids(
  dbg_history: List[dict]
) -> List[int]:
  used_rule_ids : List[int] = []
  for history_elem in dbg_history:
    dbg_info : dict = history_elem['dbg_info']
    notes : dict = dbg_info['notes']
    rule_id = notes['rule_id']
    used_rule_ids.append(rule_id)
  return used_rule_ids


def _process_used_rules(
  rule_ids_before: List[int],
  rule_ids_after: List[int],
  current_ruleset: str,
  ltrule_syntax_val_res: Optional[ptlog.TRuleSyntaxValRes] = None
) -> bool:

  ltrule_syntax_val_res = ltrule_syntax_val_res or ptlog.TRuleSyntaxValRes()

  # number of rules used after must be strictly greater than the number of rules used before
  if not (len(rule_ids_after) > len(rule_ids_before)):
    msg = (
      f'Translation rule is BAD:\n'
      f'number of rules used after ({len(rule_ids_after)}) {str(rule_ids_after)}\n'
      f'must be strictly greater than the\n'
      f'number of rules used before ({len(rule_ids_before)}) {str(rule_ids_before)}')
    logger.debug(msg)
    ltrule_syntax_val_res.is_valid = False
    ltrule_syntax_val_res.reason = msg
    return False

  # used rule id's before must be identical to the first rule id's after
  for i in range(len(rule_ids_before)):
    if rule_ids_before[i] != rule_ids_after[i]:
      msg = (
        'Translation rule is BAD:\n'
        f'used rule ids at index {i} are different.\n'
        'Should not happen under normal circumstances.\n'
        'More debugging needed.'
      )
      logger.debug(msg)
      ltrule_syntax_val_res.is_valid = False
      ltrule_syntax_val_res.reason = msg
      return False

  # id of the first rule used must be of rule under test
  # `rule_ids_before = [3, 10, 4, 5, 6, 0]`
  # `rule_ids_after  = [3, 10, 4, 5, 6, 0, 17, 8, 7]`
  # as in the example above, `17` must be id of the rule under test
  existing_rules_list = d_grammar_rules.parse_analyze_rules_optim(current_ruleset)
  num_rules_in_before_ruleset = len(existing_rules_list)
  # this will be id of the rule under test
  rule_under_test_idx_in_after_ruleset = num_rules_in_before_ruleset
  num_rules_used_in_before_rule_ids = len(rule_ids_before)
  rule_under_test_idx_in_after_rule_ids = num_rules_used_in_before_rule_ids
  if rule_under_test_idx_in_after_ruleset != rule_ids_after[rule_under_test_idx_in_after_rule_ids]:
    msg = (
      'Translation rule is BAD:\n'
      'The last used rule id is not of the rule under test.\n'
      'Should not happen under normal circumstances.\n'
      'More debugging needed.'
    )
    logger.debug(msg)
    ltrule_syntax_val_res.is_valid = False
    ltrule_syntax_val_res.reason = msg
    return False

  logger.debug('translation rule is syntactically valid')
  ltrule_syntax_val_res.is_valid = True
  return True


def is_valid_translation_rule_syntactic(
  subject: p_subject.PirelSubject,
  translation_rule: str,
  current_ruleset: str,
  ltrule: Optional[ptlog.TRule] = None,
  allow_existing_ruleset_translation: bool = False,
) -> bool:
  '''
  Check if the provided translation rule:
  1. Has its placeholder mappings correct.
  2. Can translate the problematic node.
  PRE: exising ruleset fails to translate the code
  '''

  p_utils.log_json_time(f'args-is_valid_translation_rule_syntactic.json', locals())
  ltrule = ltrule or ptlog.TRule.from_str(translation_rule)
  ltrule_syntax_val_res = ptlog.TRuleSyntaxValRes()
  ltrule.syntax_val_res = ltrule_syntax_val_res
  logger.debug(
    f'~~ Checking if translation rule is syntactically valid:\n'
    f'Rule hash value: {ltrule.hash}\n{translation_rule}')

  # ~~~ FIRST, CHECK IF THE MAPPINGS IN THE TRANSLATION RULE ARE CORRECT
  expansion_programs = d_grammar_rules.parse_analyze_rules_optim(translation_rule)
  assert len(expansion_programs) == 1, 'should not happen: there must be exactly one translation rule'
  match_pattern, expand_pattern = expansion_programs[0]['match'], expansion_programs[0]['expand']
  try:
    _ = prpp.TranslationRule(match_pattern, expand_pattern)
  except prpp.RuleMappingError as err:
    msg = (
      f'Translation rule is BAD:\n'
      f'is invalid due to rule mapping error:\n'
      f'{p_utils.exception_to_str(err)}'
    )
    logger.debug(msg)
    ltrule_syntax_val_res.is_valid = False
    ltrule_syntax_val_res.reason = msg
    return False

  # ~~~ SECOND, EARLY-REJECT RULES THAT REQUIRE UNAVAILABLE RUNTIME HELPERS
  # If a rule calls a helper that isn't defined in the JS runtime prelude,
  # it will always fail at execution time.
  src_main_code = subject.get_src_main_code()
  for fn_name in _get_called_identifiers_in_js_expand(translation_rule):
    if fn_name in Config.js_global_fn_whitelist:
      continue
    if fn_name in src_main_code:
      continue
    if _runtime_helper_is_defined(subject.tar_lang, fn_name):
      continue
    msg = (
      'Translation rule is BAD:\n'
      f'uses runtime helper `{fn_name}` which is not available in JS prelude.'
    )
    logger.debug(msg)
    ltrule_syntax_val_res.is_valid = False
    ltrule_syntax_val_res.reason = msg
    return False

  # ~~~ SECOND, CHECK IF THE TRANSLATION RULE REALLY TRANSLATES THE PROBLEMATIC NODE
  # ~~ get the translation result with the existing ruleset
  dbg_history_before = None
  try:
    _ = p_pirel.duoglot_translate_wrapper(
      subject.get_src_main_code(),
      subject.src_lang,
      subject.tar_lang,
      current_ruleset,
      subject.auto_backward,
      subject.choices,
      skip_template_extraction=True
    )
  except d_grammar_expand.TranslationRuleNotFoundException as exc:
    # NOTE dbg_history should have been set in duoglot_translate_wrapper
    dbg_history_before = exc.dbg_history
  except:
    msg = 'Translation failed with the existing ruleset. Should not happen.'
    logger.error(msg)
    ltrule_syntax_val_res.is_valid = False
    ltrule_syntax_val_res.reason = msg
    raise RuntimeError('Only TranslationRuleNotFoundException is expected')
  else:
    msg = (
      '[unexpected] existing ruleset translated the code\n'
      'This case needs to be debugged.'
    )
    if allow_existing_ruleset_translation:
      logger.warning(
        msg + '\n'
        'Skipping necessity check and treating the rule as syntactically valid.'
      )
      ltrule_syntax_val_res.is_valid = True
      ltrule_syntax_val_res.reason = msg
      return True
    logger.error(msg)
    ltrule_syntax_val_res.is_valid = False
    ltrule_syntax_val_res.reason = msg
    return False

  # ~~ get the translation result with the (existing ruleset + rule under test)
  dbg_history_after = None
  try:
    _ = p_pirel.duoglot_translate_wrapper(
      subject.get_src_main_code(),
      subject.src_lang,
      subject.tar_lang,
      current_ruleset + '\n\n' + translation_rule,
      subject.auto_backward,
      subject.choices,
      skip_template_extraction=True
    )
    # translation rule translated the remaining nodes
    msg = (
      'Translation rule is GOOD:\n'
      'It translated the last problematic node(s).'
    )
    logger.debug(msg)
    ltrule_syntax_val_res.is_valid = True
    return True
  except d_grammar_expand.TranslationRuleNotFoundException as exc:
    # expected: will further check the rule ids used before and after the translation
    # NOTE dbg_history should have been set in duoglot_translate_wrapper
    dbg_history_after = exc.dbg_history
  except Exception as exc:
    msg = (
      'Translation rule is BAD:\n'
      'Exception other than TranslationRuleNotFoundException occurred.\n'
      'Translation rule under test is bad.\n'
      'If the rule looks good to the eye, it might be a good idea to debug this case.\n'
      f'Exception: {p_utils.exception_to_str(exc)}'
    )
    logger.debug(msg)
    ltrule_syntax_val_res.is_valid = False
    ltrule_syntax_val_res.reason = msg
    return False

  # there still is a problematic node
  rule_ids_before = get_used_translation_rule_ids(dbg_history_before)
  rule_ids_after = get_used_translation_rule_ids(dbg_history_after)

  return _process_used_rules(
    rule_ids_before,
    rule_ids_after,
    current_ruleset,
    ltrule_syntax_val_res
  )


def find_pirel_keyword_in_trule(
  trule: str
) -> Optional[str]:
  '''
  Very simple check for PiREL keywords in the translation rule.
  RETURN the first matching keyword or None if no match is found.
  '''
  pirel_keywords = [
    p_consts.GENERIC_SECRET_FN,
    p_consts.PAR_PROG_PROB_NODE_REPLACE,
    p_consts.PAR_PROG_DUMMY_IDENTIFIER,
    p_consts.PIREL_LOG_OBJ_FN_NAME,
    p_consts.PRE_CTX_SPEC_IDENT
  ]
  for keyword in pirel_keywords:
    if keyword in trule:
      return keyword
  return None


def is_invalid_pattern_detected(
  trule_str: str
) -> bool:
  '''
  Check if the translation rule contains some invalid patterns.
  RETURN True if an invalid pattern is detected, False otherwise.

  NOTE This is a temporary hacky solution. It does not solve the
  root cause of the problem. Solving the root cause will lift the
  need for this function.
  '''

  def _pattern1_par_expr_to_number(trule: prpp.TranslationRule) -> bool:
    '''
    Check for the patterns like this:
      (match_expand
        (fragment ("py.parenthesized_expression" (str "(") "." (str ")")) "*")
        (fragment ("js.number" (val "2")) "*2")
      )
    where a parenthesized expression is translated to anything
    other than a parenthesized expression.
    '''
    mroot_node = trule.src_root_node.children[0]
    if mroot_node.is_terminal():
      return False
    if mroot_node.get_type() != '"py.parenthesized_expression"':
      return False
    # number of placeholders in match pattern must be 2
    if len(trule.S) != 2:
      return False
    eroot_node = trule.tar_root_node.children[0]
    if eroot_node.is_terminal():
      return False
    if eroot_node.get_type() != '"js.parenthesized_expression"':
      return True
    # number of placeholders in expand pattern must be 2
    if len(trule.T) != 2:
      return True
    return False

  def _pattern2_py_call_to_js_dunder_call(trule_str: str) -> bool:
    '''
    Reject rules that emulate Python callable dispatch via `.__call__` in JS.
    Example to reject:
      py.call(...)  -> js.call_expression(js.member_expression(... "__call__"), ...)
    '''
    return '"py.call"' in trule_str and '(val "__call__")' in trule_str

  def _pattern3_py_call_to_js_new_or_call(trule_str: str) -> bool:
    '''
    Reject generic py.call rewrites that force constructor/new semantics
    or JS Function.call(...) indirection.
    '''
    if '"py.call"' not in trule_str:
      return False
    is_suspicious = 'js.new_expression' in trule_str or '(val "call")' in trule_str
    if not is_suspicious:
      return False

    # Root cause:
    # the old guard blocked all suspicious py.call rules, including
    # deterministic callee-specific mappings (e.g., range(...)) that may
    # legitimately include nested `new Error(...)` in generated helpers.
    # Fix rationale:
    # keep blocking generic py.call rewrites, but allow specific-callee rules.
    # Generic matcher shape example:
    #   ("py.call" "." ("py.argument_list" ...))
    is_generic_py_call = '("py.call" "."' in trule_str
    if not is_generic_py_call:
      return False

    # Allow deterministic and semantically aligned runtime mapping:
    # re.compile(<pattern>) -> new RegExp(<pattern>)
    # This case appears in parser benchmarks and is not the unsafe generic
    # constructor coercion pattern that this guard targets.
    is_re_compile_to_regexp = (
      '("py.attribute" ("py.identifier" (val "re")) (str ".") ("py.identifier" (val "compile")))' in trule_str
      and '(val "RegExp")' in trule_str
    )
    if is_re_compile_to_regexp:
      return False

    return True

  def _pattern4_py_not_operator_truthiness_overfit(trule_str: str) -> bool:
    '''
    Reject overfitted `not` rules that hard-code container/object truthiness
    with Array/Object/Set/Number-specific checks.
    '''
    if '"py.not_operator"' not in trule_str:
      return False
    # Root cause:
    # this guard previously treated `(val "Object")` itself as suspicious.
    # That over-blocked valid recovery rules using
    # `Object.prototype.hasOwnProperty.call(...)` for membership semantics,
    # e.g. Python `not hasattr(...) and x in obj`.
    # Fix rationale:
    # keep rejecting explicit truthiness-probe shapes
    # (Array.isArray/Object.keys/instanceof/isNaN and container+length/size combos),
    # but do not reject `length`/`size` usage by itself.
    # NOTE:
    # Do not reject by ternary-expression alone. Valid Python `not` rewrites
    # often require ternary in JS (e.g., boolean-to-int normalization).
    # Instead, reject only when explicit truthiness-probe artifacts appear.
    suspicious_tokens_direct = [
      '(val "isArray")',
      '(val "keys")',
      '(val "instanceof")',
      '(val "isNaN")',
    ]
    if any(tok in trule_str for tok in suspicious_tokens_direct):
      return True

    # `length`/`size` alone can be legitimate (e.g., string slicing in sibling
    # branches). Treat them as suspicious only when coupled with known
    # container-constructor probes used in overfitted truthiness rewrites.
    container_tokens = [
      '(val "Array")',
      '(val "Set")',
      '(val "Map")',
      '(val "WeakMap")',
      '(val "WeakSet")',
      '(val "Number")',
    ]
    has_container_probe = any(tok in trule_str for tok in container_tokens)
    has_size_probe = '(val "length")' in trule_str or '(val "size")' in trule_str
    return has_container_probe and has_size_probe

  def _pattern5_generic_if_truthiness_overfit(trule_str: str) -> bool:
    '''
    Reject generic `if <expr>:` rewrites that inject list/object length probes.
    Keep direct condition mapping and explicit user-authored conditions.
    '''
    is_generic_if = (
      '"py.if_statement" (str "if") "." (str ":") ("py.block" "*")' in trule_str
    )
    if not is_generic_if:
      return False
    suspicious_tokens = [
      '(val "Array")',
      '(val "isArray")',
      '(val "Object")',
      '(val "keys")',
      '(val "length")',
      '(val "size")',
      'js.ternary_expression',
    ]
    return any(tok in trule_str for tok in suspicious_tokens)

  def _pattern6_boolean_operator_truthiness_overfit(trule_str: str) -> bool:
    '''
    Reject `and/or` rewrites that replace short-circuit operators with
    container-specific truthiness branches.
    '''
    if '"py.boolean_operator"' not in trule_str:
      return False
    if 'js.ternary_expression' not in trule_str:
      return False
    suspicious_tokens = [
      '(val "Array")',
      '(val "Object")',
      '(val "Set")',
      '(val "keys")',
      '(val "length")',
      '(val "size")',
      '(val "isNaN")',
    ]
    return any(tok in trule_str for tok in suspicious_tokens)

  def _pattern7_compound_statement_to_iife_expression_statement(trule: prpp.TranslationRule) -> bool:
    '''
    Reject rules that translate Python compound statements into
    JS expression statements containing IIFEs.
    This shape frequently leaks variable scope across adjacent statements.
    Example failure: `k` assigned in the IIFE branch and used after it
    in the outer function, resulting in repeated `ReferenceError: k is not defined`.
    We keep this at rule-filter stage as a second guard, because legacy/cached
    rules can bypass candidate-level validation.
    '''
    src_root_node = trule.src_root_node.children[0]
    if src_root_node.is_terminal():
      return False
    if src_root_node.get_type() not in [
      '"py.if_statement"',
      '"py.for_statement"',
      '"py.while_statement"',
      '"py.try_statement"',
      '"py.with_statement"',
    ]:
      return False

    tar_root_node = trule.tar_root_node.children[0]
    if tar_root_node.is_terminal():
      return False
    if tar_root_node.get_type() != '"js.expression_statement"':
      return False

    tar_root_nt_children = [child for child in tar_root_node.children if not child.is_terminal()]
    if len(tar_root_nt_children) == 0:
      return False
    call_node = tar_root_nt_children[0]
    if call_node.get_type() != '"js.call_expression"':
      return False

    call_nt_children = [child for child in call_node.children if not child.is_terminal()]
    if len(call_nt_children) == 0:
      return False
    callee_node = call_nt_children[0]
    if callee_node.get_type() != '"js.parenthesized_expression"':
      return False

    callee_nt_children = [child for child in callee_node.children if not child.is_terminal()]
    if len(callee_nt_children) == 0:
      return False
    fn_like_node = callee_nt_children[0]
    return fn_like_node.get_type() in [
      '"js.function"',
      '"js.arrow_function"',
      '"js.generator_function"',
    ]

  def _pattern8_py_call_to_js_null(trule: prpp.TranslationRule) -> bool:
    '''
    Reject direct mappings that erase Python calls:
      py.call(...) -> js.null
    This removes call side effects and usually breaks semantics.
    '''
    src_root_node = trule.src_root_node.children[0]
    if src_root_node.is_terminal():
      return False
    if src_root_node.get_type() != '"py.call"':
      return False

    tar_root_node = trule.tar_root_node.children[0]
    if tar_root_node.is_terminal():
      return False
    return tar_root_node.get_type() == '"js.null"'

  def _pattern9_generic_while_truthiness_overfit(trule_str: str) -> bool:
    '''
    Accept generic `while <expr>:` rewrites that directly map to JS `while` with the same condition
    '''
    generic_while_py = '(fragment ("py.while_statement" (str "while") "." (str ":") ("py.block" "*")) "*")'
    generic_while_js = '(fragment ("js.while_statement" (str "while") ("js.parenthesized_expression" (str "(") ".1" (str ")")) ("js.statement_block" (str "{") "*2" (str "}"))) "*3")'
    if generic_while_py not in trule_str:
      return False
    if generic_while_js not in trule_str:
      return True
    return False

  parsed_rules = d_grammar_rules.parse_analyze_rules_optim(trule_str)
  assert len(parsed_rules) == 1, 'should not happen: there must be exactly one translation rule'
  match_pattern, expand_pattern = parsed_rules[0]['match'], parsed_rules[0]['expand']
  trule = prpp.TranslationRule(match_pattern, expand_pattern)

  all_pattern_checks_trule = [
    _pattern1_par_expr_to_number,
    _pattern7_compound_statement_to_iife_expression_statement,
    _pattern8_py_call_to_js_null,
  ]
  for pattern_check in all_pattern_checks_trule:
    if pattern_check(trule):
      logger.warning(f'Invalid pattern detected by {pattern_check.__name__} in translation rule:\n{trule_str}')
      return True
  all_pattern_checks_trule_str = [
    _pattern2_py_call_to_js_dunder_call,
    _pattern3_py_call_to_js_new_or_call,
    _pattern4_py_not_operator_truthiness_overfit,
    _pattern5_generic_if_truthiness_overfit,
    _pattern6_boolean_operator_truthiness_overfit,
    _pattern9_generic_while_truthiness_overfit,
  ]
  for pattern_check in all_pattern_checks_trule_str:
    if pattern_check(trule_str):
      logger.warning(f'Invalid pattern detected by {pattern_check.__name__} in translation rule:\n{trule_str}')
      return True
  return False


def filter_translation_rules(
  trules_list: List[str],
  subject: p_subject.PirelSubject,
  current_ruleset: str,
  lprule_filter_log: Optional[ptlog.PRuleFilterLog] = None,
  allow_existing_ruleset_translation: bool = False,
) -> List[str]:
  '''
  Filter out translation rules that are not syntactically correct.

  subject must contain the following attributes:
  - get_src_main_code()
  - src_lang
  - tar_lang
  - auto_backward
  - choices
  '''
  logger.debug(
    f'rule-filter: ~~~ Starting p_rule_validator.filter_translation_rules. '
    f'Number of rules before: {len(trules_list)}')
  lprule_filter_log = lprule_filter_log or ptlog.PRuleFilterLog()

  syn_cor_trules = []
  for idx, trule in enumerate(trules_list, start=1):
    logger.debug(f'Checking translation rule {idx}/{len(trules_list)}')
    ltrule = ptlog.TRule.from_str(trule)
    lprule_filter_log.trules_all.append(ltrule)

    is_syntax_valid = is_valid_translation_rule_syntactic(
      subject,
      trule,
      current_ruleset,
      ltrule,
      allow_existing_ruleset_translation=allow_existing_ruleset_translation,
    )
    if not is_syntax_valid:
      logger.debug(f'rule-filter: translation rule is not syntactically valid:\n{trule}')
      continue

    pirel_keyword = find_pirel_keyword_in_trule(trule)
    if pirel_keyword is not None:
      logger.debug(f'rule-filter: found PiREL keyword "{pirel_keyword}" in translation rule:\n{trule}')
      continue

    is_inv_pat = is_invalid_pattern_detected(trule)
    if is_inv_pat:
      logger.debug(f'rule-filter: found invalid pattern in translation rule:\n{trule}')
      continue

    lprule_filter_log.trules_syn_valid.append(ltrule)
    syn_cor_trules.append(trule)

  logger.debug(
    f'rule-filter: ~~~ Finished filtering translation rules. '
    f'Number of rules after: {len(syn_cor_trules)}')
  return syn_cor_trules


async def stat_node_validate_trules_test_based(
  stat_val_subject: p_subject.PirelSubject,
  current_ruleset: p_ruleset.Ruleset,
  simple_ntext: str,
  lstat_node_val: Optional[ptlog.StatNodeVal] = None
) -> Tuple[str, List[dict]]:
  '''
  A valid ruleset is one that can translate the source program
  plausibly, i.e. both source and target programs behave
  the same on the tests.
  NOTE it is assumed that stat_val_subject.src_main_code is instrumented.
  '''

  p_utils.log_json_time(f'args-stat_node_validate_trules_test_based.json', locals())
  logger.debug('~~ Starting test-based validation of translation rules')

  lstat_node_val = lstat_node_val or ptlog.StatNodeVal()
  lstat_node_val.v2_expr_valid_stms = p_utils.current_time_msec()

  '''
  1. Raises AllRulesInMatcherGroupImplausibleError
  2. ruleset_serialized contains verified rules that can be copied
     to current_ruleset
  '''
  src_main_code = stat_val_subject.get_src_main_code()
  ruleset_hash = _make_ruleset_hash(current_ruleset)
  # Cache-scope override:
  # keep subject.name as the real benchmark subject (used by config lookups
  # in downstream validation), but allow callers to isolate cache namespace.
  cache_subject_name = getattr(stat_val_subject, 'cache_subject_name', stat_val_subject.name)
  # exact: fastest path when both source and ruleset hash match
  exact_cache_key = _make_stat_node_validate_exprs_cache_key(
    src_main_code,
    ruleset_hash,
    simple_ntext,
    cache_subject_name,
  )
  # relaxed: fallback path when ruleset hash changed but statement context stayed
  # the same; helps avoid recomputing from scratch every learning step.
  relaxed_cache_key = _make_stat_node_validate_exprs_relaxed_cache_key(
    src_main_code,
    simple_ntext,
    cache_subject_name,
  )
  _ensure_stat_node_validate_exprs_cache_loaded()

  logger.debug('--stat-val--: getting readonly choices list before applying translation rules')
  verified_choice_options: List[Tuple[Tuple[int, int, int], List[int]]] = []
  cached_verified_choice_options: Optional[List[Tuple[Tuple[int, int, int], List[int]]]] = None
  cache_payload, cache_hit_kind = _get_stat_node_validate_exprs_cache_payload(
    current_ruleset,
    exact_cache_key,
    relaxed_cache_key,
  )
  if cache_payload is not None:
    if cache_hit_kind == 'exact':
      logger.debug('--stat-val--: stat_node_validate_exprs cache hit (exact)')
    else:
      logger.debug(f'--stat-val--: stat_node_validate_exprs cache hit ({cache_hit_kind})')
    cached_verified_choice_options = _apply_stat_node_validate_exprs_cache_entry(
      current_ruleset, cache_payload)
    cache_meta = cache_payload.get('cache_meta', {})
    if isinstance(cache_meta, dict):
      _accumulate_cached_validation_ms(
        lstat_node_val,
        cache_meta.get('expr_validate_ms', 0),
        bucket_attr='cached_expr_validation_ms',
      )
    cached_ruleset_hash = (
      cache_meta.get('ruleset_hash') if isinstance(cache_meta, dict) else None
    )
    # Safe reuse condition:
    # choice indexes are matcher-group-position based, so they are stable only
    # when the ruleset hash is identical.
    if (
      cached_verified_choice_options is not None
      and cached_ruleset_hash == ruleset_hash
    ):
      verified_choice_options = cached_verified_choice_options
      logger.debug('--stat-val--: reused cached verified choice options')
    else:
      verified_choice_options = current_ruleset.get_choice_options_from_verified_rules(
        src_main_code)
  else:
    logger.debug('--stat-val--: stat_node_validate_exprs cache miss')
    expr_val_stms = p_utils.current_time_msec()
    await p_ext_rule_chooser.stat_node_validate_exprs(
      src_main_code,
      stat_val_subject.get_src_test_code(),
      stat_val_subject.translation_rules_test_code,
      current_ruleset,
      simple_ntext,
      stat_val_subject.name,
      eot_probe_src_main_code=getattr(stat_val_subject, 'origin_src_main_code_for_eot', None),
      eot_probe_stat_nid=getattr(stat_val_subject, 'origin_stat_nid_for_eot', None),
    )
    expr_val_etms = p_utils.current_time_msec()
    verified_choice_options = current_ruleset.get_choice_options_from_verified_rules(
      src_main_code)
    ruleset_side_effects = _snapshot_ruleset_side_effects(current_ruleset)
    _store_stat_node_validate_exprs_cache(
      exact_cache_key,
      relaxed_cache_key,
      ruleset_side_effects,
      verified_choice_options=verified_choice_options,
      cache_meta={
        'expr_validate_stms': expr_val_stms,
        'expr_validate_etms': expr_val_etms,
        'expr_validate_ms': expr_val_etms - expr_val_stms,
        'ruleset_hash': ruleset_hash,
      },
    )

  stat_val_subject.verified_choice_options = verified_choice_options
  logger.debug('--stat-val--: saved readonly choices list')

  lstat_node_val.v2_expr_valid_ok = True
  lstat_node_val.v2_expr_valid_etms = p_utils.current_time_msec()
  lstat_node_val.v3_rule_apply_stms = p_utils.current_time_msec()

  logger.debug('--stat-val--: applying translation rules to get the target program')
  tar_program_plausible, translate_dbg_history = None, None
  setattr(stat_val_subject, '_cached_validation_ms', 0)
  try:
    tar_program_plausible, translate_dbg_history = \
      await prapp.apply_translation_rules(stat_val_subject)
  except d_grammar_expand.NormalException as exc:
    msg = str(exc)
    if msg == 'Automatic backwarding failed to find alternative choices. (back limit)':
      raise RulesExistNoneValid from exc
    raise exc
  finally:
    _accumulate_cached_validation_ms(
      lstat_node_val,
      getattr(stat_val_subject, '_cached_validation_ms', 0),
      bucket_attr='cached_translation_ms',
    )
    setattr(stat_val_subject, '_cached_validation_ms', 0)
  stat_val_subject.verified_choice_options = []  # reset
  logger.debug('--stat-val--: finished applying translation rules')

  lstat_node_val.v3_rule_apply_ok = True
  lstat_node_val.v3_rule_apply_etms = p_utils.current_time_msec()
  return tar_program_plausible, translate_dbg_history
