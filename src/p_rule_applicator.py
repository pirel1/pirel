import asyncio
import copy
import difflib
import hashlib
import json
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

import d_grammar_expand
import p_code_runner
import p_consts
import p_ext_rule_chooser
import p_pirel
import p_subject
import p_utils
import p_visitor_js as pvjs
import p_visitor_py as pvpy


logger = p_utils.setup_logger(__name__)

class TarProgramRunError(RuntimeError): pass

_RUN_TESTS_CACHE_MAX_SIZE = 2048
_RUN_TESTS_CACHE_FPATH = p_consts.VALIDATION_CACHE_DIR / 'run-tests-cache.json'
_RUN_TESTS_CACHE: Dict[str, dict] = {}
_RUN_TESTS_CACHE_LOADED = False

# Cache successful main-code translations for repeated contexts.
_TAR_MAIN_TRANSLATE_CACHE_MAX_SIZE = 2048
_TAR_MAIN_TRANSLATE_CACHE: Dict[str, dict] = {}

# Cache previously successful choice combinations so we can start from a known
# good baseline even when subsequent learning changes rule ordering.
_SUCCESS_CHOICES_CACHE_MAX_SIZE = 512
_SUCCESS_CHOICES_PER_SRC_MAX = 6
_SUCCESS_CHOICES_EXACT: Dict[str, dict] = {}
_SUCCESS_CHOICES_BY_SRC: Dict[str, List[dict]] = {}

# Root cause:
# `choices_lists_error` only lived inside one apply_translation_rules() call, so
# a choice that already failed (e.g. ParserBase() branch degenerating to null)
# could be selected again in a later invocation for the same statement.
# Fix rationale:
# Keep a process-local "failed choices" cache keyed by exact validation context
# (subject + src_main + current ruleset), and feed it back into candidate
# selection on the next invocation.
_FAILED_CHOICES_CACHE_MAX_SIZE = 512
_FAILED_CHOICES_PER_EXACT_MAX = 64
_FAILED_CHOICES_EXACT: Dict[str, List[dict]] = {}

_PY_LIST_REPR_HELPER_JS = """function py_list_repr(arr) {
  return '[' + arr.map(x => String(x)).join(', ') + ']';
}
"""


def _inject_py_list_repr_helper_if_needed(program_js: str) -> str:
  if 'py_list_repr(' not in program_js:
    return program_js
  if re.search(r'\bfunction\s+py_list_repr\s*\(', program_js):
    return program_js
  if re.search(r'\b(?:const|let|var)\s+py_list_repr\s*=', program_js):
    return program_js
  return _PY_LIST_REPR_HELPER_JS + '\n' + program_js


def _extract_timing_ms(payload: object, key: str) -> int:
  if not isinstance(payload, dict):
    return 0
  timing = payload.get('timing', {})
  if not isinstance(timing, dict):
    return 0
  try:
    ms = int(timing.get(key, 0))
  except Exception:
    return 0
  return ms if ms > 0 else 0


def _accumulate_subject_cached_validation_ms(
  subject: Optional[p_subject.PirelSubject],
  delta_ms: object,
) -> None:
  if subject is None:
    return
  try:
    delta = int(delta_ms)
  except Exception:
    return
  if delta <= 0:
    return
  try:
    current = int(getattr(subject, '_cached_validation_ms', 0) or 0)
  except Exception:
    current = 0
  setattr(subject, '_cached_validation_ms', current + delta)


def _ensure_run_tests_cache_loaded() -> None:
  global _RUN_TESTS_CACHE_LOADED, _RUN_TESTS_CACHE
  if _RUN_TESTS_CACHE_LOADED:
    return
  _RUN_TESTS_CACHE_LOADED = True
  if not _RUN_TESTS_CACHE_FPATH.exists():
    _RUN_TESTS_CACHE = {}
    return
  try:
    payload = p_utils.read_json(_RUN_TESTS_CACHE_FPATH)
    entries = payload.get('entries', {})
    if not isinstance(entries, dict):
      logger.warning('Unexpected run_tests cache payload format; starting with empty cache.')
      _RUN_TESTS_CACHE = {}
      return
    _RUN_TESTS_CACHE = entries
    while len(_RUN_TESTS_CACHE) > _RUN_TESTS_CACHE_MAX_SIZE:
      _RUN_TESTS_CACHE.pop(next(iter(_RUN_TESTS_CACHE)))
  except Exception as err:
    logger.warning(f'Failed to load persistent run_tests cache: {err}')
    _RUN_TESTS_CACHE = {}


def _persist_run_tests_cache() -> None:
  payload = {
    'version': 1,
    'entries': _RUN_TESTS_CACHE,
  }
  try:
    _RUN_TESTS_CACHE_FPATH.parent.mkdir(parents=True, exist_ok=True)
    p_utils.write_json(_RUN_TESTS_CACHE_FPATH, payload)
  except Exception as err:
    logger.warning(f'Failed to persist run_tests cache: {err}')


def _make_run_tests_cache_key(
  subject: p_subject.PirelSubject,
  src_program_instr: str,
  tar_program_instr: str,
) -> str:
  key_payload = {
    'subject_name': subject.name,
    'src_lang': subject.src_lang,
    'tar_lang': subject.tar_lang,
    'src_program_instr': src_program_instr,
    'tar_program_instr': tar_program_instr,
  }
  key_json = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
  return hashlib.sha256(key_json.encode('utf-8')).hexdigest()


def _store_run_tests_cache(cache_key: str, payload: dict) -> None:
  _ensure_run_tests_cache_loaded()
  if cache_key in _RUN_TESTS_CACHE:
    _RUN_TESTS_CACHE.pop(cache_key)
  _RUN_TESTS_CACHE[cache_key] = payload
  while len(_RUN_TESTS_CACHE) > _RUN_TESTS_CACHE_MAX_SIZE:
    _RUN_TESTS_CACHE.pop(next(iter(_RUN_TESTS_CACHE)))
  _persist_run_tests_cache()


def _make_tar_main_translate_cache_key(
  src_main_code: str,
  choices: dict,
  subject: p_subject.PirelSubject,
) -> str:
  normalized_choices = _normalize_choices(choices)
  key_payload = {
    'subject_name': subject.name,
    'src_lang': subject.src_lang,
    'tar_lang': subject.tar_lang,
    'auto_backward': bool(subject.auto_backward),
    'src_main_code': src_main_code,
    'translation_rules_main_code': subject.translation_rules_main_code or '',
    'choices': normalized_choices,
  }
  key_json = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
  return hashlib.sha256(key_json.encode('utf-8')).hexdigest()


def _store_tar_main_translate_cache(cache_key: str, payload: dict) -> None:
  if cache_key in _TAR_MAIN_TRANSLATE_CACHE:
    _TAR_MAIN_TRANSLATE_CACHE.pop(cache_key, None)
  _TAR_MAIN_TRANSLATE_CACHE[cache_key] = payload
  while len(_TAR_MAIN_TRANSLATE_CACHE) > _TAR_MAIN_TRANSLATE_CACHE_MAX_SIZE:
    _TAR_MAIN_TRANSLATE_CACHE.pop(next(iter(_TAR_MAIN_TRANSLATE_CACHE)), None)


def _normalize_choices(choices: dict) -> dict:
  '''
  Normalize choices object into canonical ASTNODE format.
  '''
  if not isinstance(choices, dict) or choices.get('type') != 'ASTNODE':
    return {'type': 'ASTNODE', 'choices_list': []}

  normalized_choices_list: List[Tuple[Tuple[int, int, int], int]] = []
  for item in choices.get('choices_list', []):
    if not isinstance(item, (list, tuple)) or len(item) != 2:
      continue
    range_info, choice_idx = item
    if isinstance(range_info, list):
      range_info = tuple(range_info)
    if not isinstance(range_info, tuple) or len(range_info) != 3:
      continue
    try:
      normalized_range_info = (
        int(range_info[0]),
        int(range_info[1]),
        int(range_info[2]),
      )
      normalized_choice_idx = int(choice_idx)
    except Exception:
      continue
    normalized_choices_list.append((normalized_range_info, normalized_choice_idx))

  normalized_choices_list = p_ext_rule_chooser.choices_list_sorted(normalized_choices_list)
  return {
    'type': 'ASTNODE',
    'choices_list': normalized_choices_list,
  }


def _choices_signature(choices: dict) -> str:
  normalized = _normalize_choices(choices)
  payload = {
    'type': normalized['type'],
    'choices_list': normalized['choices_list'],
  }
  payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
  return hashlib.sha256(payload_json.encode('utf-8')).hexdigest()


def _make_success_choices_exact_key(
  subject: p_subject.PirelSubject,
  src_main_code_instr: str,
) -> str:
  # Exact key is ruleset-aware: safe reuse only when translation rules match.
  payload = {
    'subject_name': subject.name,
    'src_lang': subject.src_lang,
    'tar_lang': subject.tar_lang,
    'src_main_code_instr': src_main_code_instr,
    'translation_rules_main_code': subject.translation_rules_main_code or '',
  }
  payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
  return hashlib.sha256(payload_json.encode('utf-8')).hexdigest()


def _make_success_choices_src_key(
  subject: p_subject.PirelSubject,
  src_main_code_instr: str,
) -> str:
  # Source-only key enables relaxed fallback across ruleset revisions.
  payload = {
    'subject_name': subject.name,
    'src_lang': subject.src_lang,
    'tar_lang': subject.tar_lang,
    'src_main_code_instr': src_main_code_instr,
  }
  payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
  return hashlib.sha256(payload_json.encode('utf-8')).hexdigest()


def _evict_old_success_choices() -> None:
  while len(_SUCCESS_CHOICES_EXACT) > _SUCCESS_CHOICES_CACHE_MAX_SIZE:
    old_exact_key = next(iter(_SUCCESS_CHOICES_EXACT))
    _SUCCESS_CHOICES_EXACT.pop(old_exact_key, None)

  non_empty_keys = [k for k, v in _SUCCESS_CHOICES_BY_SRC.items() if len(v) > 0]
  while len(non_empty_keys) > _SUCCESS_CHOICES_CACHE_MAX_SIZE:
    old_src_key = non_empty_keys[0]
    _SUCCESS_CHOICES_BY_SRC.pop(old_src_key, None)
    non_empty_keys = [k for k, v in _SUCCESS_CHOICES_BY_SRC.items() if len(v) > 0]


def _evict_old_failed_choices() -> None:
  while len(_FAILED_CHOICES_EXACT) > _FAILED_CHOICES_CACHE_MAX_SIZE:
    _FAILED_CHOICES_EXACT.pop(next(iter(_FAILED_CHOICES_EXACT)), None)


def _store_success_choices_cache(
  subject: p_subject.PirelSubject,
  src_main_code_instr: str,
  choices: dict,
) -> None:
  normalized_choices = _normalize_choices(choices)
  exact_key = _make_success_choices_exact_key(subject, src_main_code_instr)
  src_key = _make_success_choices_src_key(subject, src_main_code_instr)
  choice_sig = _choices_signature(normalized_choices)

  exact_payload = {
    'choices': copy.deepcopy(normalized_choices),
    'choice_sig': choice_sig,
  }
  if exact_key in _SUCCESS_CHOICES_EXACT:
    _SUCCESS_CHOICES_EXACT.pop(exact_key, None)
  _SUCCESS_CHOICES_EXACT[exact_key] = exact_payload

  src_entries = _SUCCESS_CHOICES_BY_SRC.setdefault(src_key, [])
  src_entries = [entry for entry in src_entries if entry.get('choice_sig') != choice_sig]
  src_entries.insert(0, copy.deepcopy(exact_payload))
  _SUCCESS_CHOICES_BY_SRC[src_key] = src_entries[:_SUCCESS_CHOICES_PER_SRC_MAX]

  _evict_old_success_choices()


def _store_failed_choices_cache(
  subject: p_subject.PirelSubject,
  src_main_code_instr: str,
  choices: dict,
) -> None:
  normalized_choices = _normalize_choices(choices)
  exact_key = _make_success_choices_exact_key(subject, src_main_code_instr)
  choice_sig = _choices_signature(normalized_choices)

  entries = _FAILED_CHOICES_EXACT.setdefault(exact_key, [])
  entries = [entry for entry in entries if entry.get('choice_sig') != choice_sig]
  entries.insert(0, {
    'choices': copy.deepcopy(normalized_choices),
    'choice_sig': choice_sig,
  })
  _FAILED_CHOICES_EXACT[exact_key] = entries[:_FAILED_CHOICES_PER_EXACT_MAX]
  _evict_old_failed_choices()


def _remove_failed_choices_cache(
  subject: p_subject.PirelSubject,
  src_main_code_instr: str,
  choices: dict,
) -> None:
  exact_key = _make_success_choices_exact_key(subject, src_main_code_instr)
  entries = _FAILED_CHOICES_EXACT.get(exact_key)
  if not entries:
    return
  choice_sig = _choices_signature(choices)
  filtered = [entry for entry in entries if entry.get('choice_sig') != choice_sig]
  if len(filtered) == 0:
    _FAILED_CHOICES_EXACT.pop(exact_key, None)
  else:
    _FAILED_CHOICES_EXACT[exact_key] = filtered


def _is_failed_choices_cached(
  subject: p_subject.PirelSubject,
  src_main_code_instr: str,
  choices: dict,
) -> bool:
  exact_key = _make_success_choices_exact_key(subject, src_main_code_instr)
  entries = _FAILED_CHOICES_EXACT.get(exact_key, [])
  if len(entries) == 0:
    return False
  choice_sig = _choices_signature(choices)
  return any(entry.get('choice_sig') == choice_sig for entry in entries)


def _get_failed_choices_lists(
  subject: p_subject.PirelSubject,
  src_main_code_instr: str,
) -> List[list]:
  exact_key = _make_success_choices_exact_key(subject, src_main_code_instr)
  entries = _FAILED_CHOICES_EXACT.get(exact_key, [])
  choices_lists: List[list] = []
  for entry in entries:
    choices = entry.get('choices', {'type': 'ASTNODE', 'choices_list': []})
    normalized = _normalize_choices(choices)
    choices_lists.append(copy.deepcopy(normalized['choices_list']))
  return choices_lists


def _get_success_choices_candidates(
  subject: p_subject.PirelSubject,
  src_main_code_instr: str,
) -> List[Tuple[dict, str]]:
  candidates: List[Tuple[dict, str]] = []
  seen_choice_sigs: Set[str] = set()
  exact_key = _make_success_choices_exact_key(subject, src_main_code_instr)
  src_key = _make_success_choices_src_key(subject, src_main_code_instr)

  if exact_key in _SUCCESS_CHOICES_EXACT:
    payload = _SUCCESS_CHOICES_EXACT.pop(exact_key)
    _SUCCESS_CHOICES_EXACT[exact_key] = payload
    choice_sig = payload.get('choice_sig')
    if isinstance(choice_sig, str):
      seen_choice_sigs.add(choice_sig)
    candidates.append((copy.deepcopy(payload.get('choices', {'type': 'ASTNODE', 'choices_list': []})), 'exact'))

  for payload in _SUCCESS_CHOICES_BY_SRC.get(src_key, []):
    choice_sig = payload.get('choice_sig')
    if isinstance(choice_sig, str) and choice_sig in seen_choice_sigs:
      continue
    if isinstance(choice_sig, str):
      seen_choice_sigs.add(choice_sig)
    candidates.append((copy.deepcopy(payload.get('choices', {'type': 'ASTNODE', 'choices_list': []})), 'src'))

  return candidates


def _is_choices_translatable(
  src_main_code_instr: str,
  choices: dict,
  subject: p_subject.PirelSubject,
) -> bool:
  # Guard relaxed cache reuse: only keep candidates that still translate
  # under the current ruleset.
  try:
    _ = p_pirel.duoglot_translate_wrapper(
      src_code=src_main_code_instr,
      src_lang=subject.src_lang,
      tar_lang=subject.tar_lang,
      trans_rules=subject.translation_rules_main_code,
      auto_backward=subject.auto_backward,
      choices=choices,
      skip_template_extraction=True,
    )
    return True
  except Exception:
    return False


def _get_cached_or_initial_choices(
  src_main_code_instr: str,
  subject: p_subject.PirelSubject,
) -> dict:
  '''
  Prefer choices that were known to pass tests previously.
  Falls back to subject.choices if cached candidates are unusable.
  '''
  base_choices = _normalize_choices(subject.choices)
  candidates = _get_success_choices_candidates(subject, src_main_code_instr)
  if len(candidates) == 0:
    return base_choices

  for cand_choices, cache_scope in candidates:
    # Reason: a "successful cache" can become stale after rule-learning updates.
    # If that same choice is already known to fail in this exact context,
    # skip it early to avoid re-entering the bad branch.
    if _is_failed_choices_cached(subject, src_main_code_instr, cand_choices):
      logger.debug(
        f'Skipping cached successful choices (scope={cache_scope}) because '
        f'they are already marked as failing for subject="{subject.name}"'
      )
      continue
    if _is_choices_translatable(src_main_code_instr, cand_choices, subject):
      logger.debug(
        f'Using cached successful choices (scope={cache_scope}) '
        f'for subject="{subject.name}"'
      )
      return cand_choices

  if _is_failed_choices_cached(subject, src_main_code_instr, base_choices):
    logger.debug(
      f'Base choices are marked as failing for subject="{subject.name}". '
      f'Will still return base choices as a last resort if no alternative exists.'
    )

  logger.debug(
    f'Cached successful choices exist but are not usable for current ruleset; '
    f'falling back to subject.choices for subject="{subject.name}"'
  )
  return base_choices


class UnknownTypeInTracesError(RuntimeError): pass
class SrcTestScriptRunError(RuntimeError): pass


def _normalize_error_lines_keys(error_lines: dict) -> Dict[int, str]:
  '''
  Normalize error_lines keys to int.
  Reason: run_tests cache is persisted as JSON, so dict keys are restored as str.
  '''
  normalized: Dict[int, str] = {}
  for key, line_content in error_lines.items():
    if isinstance(key, int):
      line_idx = key
    else:
      try:
        line_idx = int(key)
      except (TypeError, ValueError):
        logger.debug(f'Ignoring semantic error line with non-numeric key: {key!r}')
        continue
    normalized[line_idx] = line_content
  return normalized


class TarTestScriptRunError(RuntimeError):
  def __init__(self, tar_error_dict: dict):
    super().__init__('Error running tar test script')
    self.tar_error_dict = tar_error_dict
  def __str__(self):
    return f'TarTestScriptRunError: {json.dumps(self.tar_error_dict, indent=2)}'
class TraceMismatchError(RuntimeError):
  def __init__(
    self,
    error_lines: dict,
    mismatched_log_stat_idxs: Optional[Tuple[int, int]] = None
  ):
    super().__init__('Trace mismatch between src and tar test scripts')
    self.error_lines = _normalize_error_lines_keys(error_lines)
    self.mismatched_log_stat_idxs = mismatched_log_stat_idxs
  def __str__(self):
    info = {
      'error_lines': self.error_lines,
      'mismatched_log_stat_idxs': self.mismatched_log_stat_idxs,
    }
    return f'TraceMismatchError: {json.dumps(info, indent=2)}'
class SrcTestScriptProblematicNodeError(RuntimeError):
  '''
  This error is raised when there is a translation error
  when translating src_main_code.
  '''
  def __init__(self, *args):
    super().__init__(*args)
    self.src_main_code : Optional[str] = None
    self.choices : Optional[dict] = None
    self.translation_rules_main_code : Optional[str] = None
    self.problematic_node_id : Optional[int] = None
    self.problematic_node_type : Optional[str] = None


class ValidationContextProblematicNodeError(RuntimeError):
  '''
  This error is raised when the validation-time src_main_code cannot be made
  translatable because a missing rule exists in the surrounding context code.
  '''
  def __init__(self, *args):
    super().__init__(*args)
    self.src_main_code : Optional[str] = None
    self.choices : Optional[dict] = None
    self.translation_rules_main_code : Optional[str] = None
    self.problematic_node_id : Optional[int] = None
    self.problematic_node_type : Optional[str] = None
    self.first_templates_dict : Optional[dict] = None


def _normalize_regex_trace_pattern(pattern: str) -> str:
  '''
  Normalize regex pattern text for cross-language trace comparison.
  Python and JS serializers can differ only in escape style for quote/slash.
  '''
  # quote/slash escaping is often a representation artifact, not semantics.
  # `\]` is also often emitted redundantly, but only safe to relax outside
  # character classes.
  out: List[str] = []
  in_char_class = False
  i = 0
  while i < len(pattern):
    ch = pattern[i]
    if ch == '\\' and i + 1 < len(pattern):
      nxt = pattern[i + 1]
      if nxt in ['\'', '"', '/']:
        out.append(nxt)
        i += 2
        continue
      if nxt == ']' and not in_char_class:
        out.append(']')
        i += 2
        continue
      out.append(ch)
      out.append(nxt)
      i += 2
      continue

    if ch == '[':
      in_char_class = True
    elif ch == ']' and in_char_class:
      in_char_class = False
    out.append(ch)
    i += 1
  return ''.join(out)


# INTERNAL API
def are_traces_equal_rec(
  src_trace: list,
  tar_trace: list
) -> bool:
  '''
  Compare the traces from the source and target programs.
  This is a recursive function.
  For more information, refer to
  1. run_src_test_script and run_tar_test_script in p_code_runner.py.
  2. myexactlog implementations for src and tar languages.
  '''

  def _any_of_matches(any_of_trace: list, other_trace: list) -> bool:
    assert any_of_trace[0] == 'any_of', 'expected any_of trace'
    for candidate in any_of_trace[1:]:
      if are_traces_equal_rec(candidate, other_trace):
        return True
    return False

  if src_trace[0] == 'any_of':
    return _any_of_matches(src_trace, tar_trace)
  if tar_trace[0] == 'any_of':
    return _any_of_matches(tar_trace, src_trace)

  # base case: lengths must be equal
  if len(src_trace) != len(tar_trace):
    return False

  # base case: types must be same
  type1, type2 = src_trace[0], tar_trace[0]
  if type1 != type2:
    return False

  assert type1 == type2, f'compare_traces: {type1} != {type2}'
  if len(src_trace) == 1:  # no content in case of null or function
    return True

  # base case: types are bool
  if type1 == 'bool':
    val1, val2 = src_trace[1], tar_trace[1]
    return val1 == val2

  # base case: types serialized as [type, length, payload]
  if type1 in ['string', 'hash', 'regex', 'unknown']:
    len1, len2 = src_trace[1], tar_trace[1]
    val1, val2 = src_trace[2], tar_trace[2]
    if type1 == 'regex':
      return _normalize_regex_trace_pattern(val1) == _normalize_regex_trace_pattern(val2)
    if type1 == 'unknown':
      logger.warning('are_traces_equal_rec: unknown type')
    return len1 == len2 and val1 == val2

  # base case: types are num
  if type1 == 'number':
    val1, val2 = src_trace[1], tar_trace[1]
    return p_utils.are_equal_numbers(val1, val2, eps_percentage=p_consts.EPS_PERCENTAGE)

  # base case: types are defined_in_main
  if type1 == 'defined_in_main':
    class_name1, class_name2 = src_trace[1], tar_trace[1]
    return class_name1 == class_name2

  # recurse
  if type1 in ['list', 'set', 'dict']:
    len1, len2 = src_trace[1], tar_trace[1]
    if len1 != len2:
      return False
    list1, list2 = src_trace[2], tar_trace[2]
    for ch1, ch2 in zip(list1, list2):
      child_res = are_traces_equal_rec(ch1, ch2)
      if not child_res:
        return False
    return True

  raise UnknownTypeInTracesError(f'Unknown type in are_traces_equal_rec: "{type1}"')


def is_valid_trace(
  trace: list
) -> bool:
  '''
  Check if the trace is valid.
  A valid trace is a list with exactly 3 elements:
  - type of the trace is a string "list"
  - length of the trace
  - list of trace entries
  '''
  if not isinstance(trace, list):
    return False
  if len(trace) != 3:
    return False

  trace_type = trace[0]
  trace_size = trace[1]
  trace_entries = trace[2]

  if not isinstance(trace_type, str):
    return False
  if trace_type != 'list':
    return False

  if not isinstance(trace_size, int):
    return False
  if trace_size < 0:
    return False

  if not isinstance(trace_entries, list):
    return False
  if len(trace_entries) != trace_size:
    return False

  return True


def is_valid_trace_entry(
  trace_entry: list
) -> bool:
  '''
  Check if the trace entry is valid.
  A valid trace entry is a list with exactly 3 elements:
  - type of the trace entry is a string "list"
  - length of the trace entry (corresponds to the number of arguments)
  - list of trace entry arguments
  '''
  if not isinstance(trace_entry, list):
    return False
  if len(trace_entry) != 3:
    return False

  te_type = trace_entry[0]
  te_size = trace_entry[1]
  te_args = trace_entry[2]

  if not isinstance(te_type, str):
    return False
  if te_type != 'list':
    return False

  '''
  Size of the trace entry must be at least 2:
  1. the first argument is the index of the log statement
  2. the second and subsequent arguments are the actual logged values
  '''
  if not isinstance(te_size, int):
    return False
  if te_size < 2:
    return False

  if not isinstance(te_args, list):
    return False
  if len(te_args) != te_size:
    return False

  return True


def is_trace_subsumed(
  shorter_trace: list,
  longer_trace: list
) -> bool:
  '''
  Check if the longer trace subsumes the shorter trace.
  '''
  assert is_valid_trace(shorter_trace), 'shorter_trace must be a valid trace'
  assert is_valid_trace(longer_trace), 'longer_trace must be a valid trace'

  shorter_tes = shorter_trace[2]
  longer_tes = longer_trace[2]
  assert len(longer_tes) > len(shorter_tes), 'longer_trace must be strictly longer than shorter_trace'

  # zip truncates the longer trace to the length of the shorter trace
  for idx, (shorter_te, longer_te) in enumerate(zip(shorter_tes, longer_tes)):
    assert is_valid_trace_entry(shorter_te), 'shorter_trace entry must be valid'
    assert is_valid_trace_entry(longer_te), 'longer_trace entry must be valid'
    trace_entries_identical = are_traces_equal_rec(shorter_te, longer_te)
    if not trace_entries_identical:
      return False

  return True


def does_trace_subsume_another(
  trace1: list,
  trace2: list
) -> bool:
  '''
  Check if one trace subsumes the second trace.
  '''
  assert is_valid_trace(trace1), 'trace1 must be a valid trace'
  assert is_valid_trace(trace2), 'trace2 must be a valid trace'
  trace1_len = trace1[1]
  trace2_len = trace2[1]
  if trace1_len < trace2_len:
    return is_trace_subsumed(trace1, trace2)
  elif trace2_len < trace1_len:
    return is_trace_subsumed(trace2, trace1)
  else:
    return are_traces_equal_rec(trace1, trace2)


def _get_trace_mismatch_idx(
  src_trace: list,
  tar_trace: list
) -> int:
  '''
  Given two traces, find the first index where they differ.
  If they are identical, return None. Index is 0-based.
  PRE: traces are not identical.
  RAISE: RuntimeError if traces are identical.
  '''
  def __get_trace_mismatch_idx_len_equal(src_trace_entries: list, tar_trace_entries: list) -> int:
    '''
    This function is used when the source trace and target trace are of the same length.
    '''
    for idx, (src_te, tar_te) in enumerate(zip(src_trace_entries, tar_trace_entries)):
      assert is_valid_trace_entry(src_te), 'source trace entry must be valid'
      assert is_valid_trace_entry(tar_te), 'target trace entry must be valid'
      trace_entries_identical = are_traces_equal_rec(src_te, tar_te)
      if not trace_entries_identical:
        return idx
    # if we reach here, it means that all entries are identical
    raise RuntimeError('Traces must be different')

  def __get_trace_mismatch_idx_tar_trace_larger(src_trace_entries: list, tar_trace_entries: list) -> int:
    '''
    This function is used when the source trace is shorter than the target trace.
    '''
    for idx, (src_te, tar_te) in enumerate(zip(src_trace_entries, tar_trace_entries)):
      assert is_valid_trace_entry(src_te), 'source trace entry must be valid'
      assert is_valid_trace_entry(tar_te), 'target trace entry must be valid'
      trace_entries_identical = are_traces_equal_rec(src_te, tar_te)
      if not trace_entries_identical:
        return idx
    # if we reach here, it means that src trace is subsumed by target trace
    raise RuntimeError('Source trace is subsumed by target trace. Target trace has more iterations?')

  def __get_trace_mismatch_idx_src_trace_larger(src_trace_entries: list, tar_trace_entries: list) -> int:
    '''
    This function is used when the source trace is longer than the target trace.
    '''
    for idx, (src_te, tar_te) in enumerate(zip(src_trace_entries, tar_trace_entries)):
      assert is_valid_trace_entry(src_te), 'source trace entry must be valid'
      assert is_valid_trace_entry(tar_te), 'target trace entry must be valid'
      trace_entries_identical = are_traces_equal_rec(src_te, tar_te)
      if not trace_entries_identical:
        return idx
    # if we reach here, it means that tar trace is subsumed by src trace
    raise RuntimeError('Target trace is subsumed by source trace. Target trace needs more iterations?')

  src_trace_type = src_trace[0]
  tar_trace_type = tar_trace[0]
  assert src_trace_type == 'list' and tar_trace_type == 'list', 'traces must be lists'
  src_trace_len = src_trace[1]
  tar_trace_len = tar_trace[1]
  src_trace_entries = src_trace[2]
  tar_trace_entries = tar_trace[2]

  # both traces are of the same length
  if src_trace_len == tar_trace_len:
    return __get_trace_mismatch_idx_len_equal(src_trace_entries, tar_trace_entries)

  # source trace is shorter than target trace
  elif src_trace_len < tar_trace_len:
    return __get_trace_mismatch_idx_tar_trace_larger(src_trace_entries, tar_trace_entries)

  # source trace is longer than target trace
  else:
    return __get_trace_mismatch_idx_src_trace_larger(src_trace_entries, tar_trace_entries)


def _get_log_statement_idxs(
  src_trace: list,
  tar_trace: list,
  trace_idx: int
) -> Tuple[int, int]:
  '''
  Given two traces and a trace index, find the log statement index under that trace index.
  Log statement indices are 1-based. trace_idx is 0-based.
  RETURN the log statement indices for both src and tar traces.

  Sample trace:
  ["list", 1,
    [
      [                                     | 1st trace entry
        "list", 2, [                        |
          ["number", 5],  | 1st logged arg  |
          ["number", 2]   | 2nd logged arg  |
        ]                                   |
      ]                                     |
    ]
  ]
  '''

  src_trace_entries = src_trace[2]
  tar_trace_entries = tar_trace[2]

  assert trace_idx < len(src_trace_entries), 'trace index must be less than src trace entries length'
  assert trace_idx < len(tar_trace_entries), 'trace index must be less than tar trace entries length'

  src_trace_entry = src_trace_entries[trace_idx]
  tar_trace_entry = tar_trace_entries[trace_idx]

  src_trace_entry_type = src_trace_entry[0]
  tar_trace_entry_type = tar_trace_entry[0]
  assert src_trace_entry_type == 'list' and tar_trace_entry_type == 'list', \
    'trace entries must be lists'

  src_trace_arg_len = src_trace_entry[1]
  tar_trace_arg_len = tar_trace_entry[1]
  assert src_trace_arg_len >= 2 and tar_trace_arg_len >= 2, \
    'trace entries must have at least 2 arguments logged'

  src_trace_args = src_trace_entry[2]
  tar_trace_args = tar_trace_entry[2]
  src_trace_arg1 = src_trace_args[0]  # contains src log statement index
  tar_trace_arg1 = tar_trace_args[0]  # contains tar log statement index
  src_trace_arg1_type = src_trace_arg1[0]
  tar_trace_arg1_type = tar_trace_arg1[0]
  assert src_trace_arg1_type == 'number' and tar_trace_arg1_type == 'number', \
    'trace entry first argument must be a number'

  src_trace_arg1_value = src_trace_arg1[1]  # src log statement index
  tar_trace_arg1_value = tar_trace_arg1[1]  # tar log statement index
  assert isinstance(src_trace_arg1_value, int) and isinstance(tar_trace_arg1_value, int), \
    'trace entry first argument must be an int'

  _src_trace_arg2 = src_trace_args[1]
  _tar_trace_arg2 = tar_trace_args[1]

  if src_trace_arg1_value != tar_trace_arg1_value:
    logger.warning(
      f'Expected log statement #{src_trace_arg1_value}, got #{tar_trace_arg1_value}.\n'
      f'src_trace_entry: {src_trace_entry}\n'
      f'tar_trace_entry: {tar_trace_entry}\n'
      f'trace_idx: {trace_idx} (condition for debugging: "_trace_idx == {trace_idx - 1}")')
  else:
    logger.warning(
      f'Expected "{_src_trace_arg2}" at log statement #{src_trace_arg1_value}, got "{_tar_trace_arg2}".\n'
      f'src_trace_entry: {src_trace_entry}\n'
      f'tar_trace_entry: {tar_trace_entry}\n'
      f'trace_idx: {trace_idx} (condition for debugging: "_trace_idx == {trace_idx - 1}")')

  return (src_trace_arg1_value, tar_trace_arg1_value)


def _get_log_statement_idx_subsumed(
  src_trace: list,
  tar_trace: list
) -> int:
  '''
  Return a log statement index that caused the trace mismatch
  given that one trace is subsumed by another.
  '''
  assert does_trace_subsume_another(src_trace, tar_trace), 'one trace must subsume another'
  assert is_valid_trace(src_trace), 'src_trace must be a valid trace'
  assert is_valid_trace(tar_trace), 'tar_trace must be a valid trace'

  src_trace_entries = src_trace[2]
  tar_trace_entries = tar_trace[2]

  assert len(src_trace_entries) != len(tar_trace_entries), 'traces must be of different lengths'
  shorter_trace_len = min(len(src_trace_entries), len(tar_trace_entries))
  longer_trace_entries = tar_trace_entries if len(tar_trace_entries) > len(src_trace_entries) else src_trace_entries

  trace_entry = longer_trace_entries[shorter_trace_len]
  assert is_valid_trace_entry(trace_entry), 'trace entry must be valid'

  trace_entry_type = trace_entry[0]
  assert trace_entry_type == 'list', 'trace entry must be a list'

  trace_entry_len = trace_entry[1]
  assert trace_entry_len >= 2, 'trace entry must have at least 2 arguments logged'

  trace_entry_args = trace_entry[2]
  trace_arg1 = trace_entry_args[0]
  trace_arg1_type = trace_arg1[0]
  assert trace_arg1_type == 'number', 'trace entry first argument must be a number'

  trace_arg1_value = trace_arg1[1]
  assert isinstance(trace_arg1_value, int), 'trace entry first argument must be an int'

  logger.warning(f'Looks like an extra or missing loop iteration caused by log statement #{trace_arg1_value}')
  return trace_arg1_value


def _get_mismatched_log_statement_idxs(
  src_trace: list,
  tar_trace: list
) -> Tuple[int, int]:
  '''
  RETURN the mismatched log statement indices for both src and tar traces.
  '''

  if not does_trace_subsume_another(src_trace, tar_trace):
    '''
    A trace mismatch index is a 0-based index in the traces where the entries differ.
    Using this index, we can find which log statement caused the trace mismatch.
    '''
    trace_mismatch_idx = _get_trace_mismatch_idx(src_trace, tar_trace)

    '''
    A mismatched log statement index is an index of the log statement that caused
    the trace mismatch. Log statement indices are 1-based.
    trace_mismatch_idx is 0-based.
    '''
    mismatched_log_stat_idxs = _get_log_statement_idxs(src_trace, tar_trace, trace_mismatch_idx)

    return mismatched_log_stat_idxs

  else:
    '''
    If one trace subsumes another, it means that there is a missing or extra loop iteration.
    '''
    mismatched_log_stat_idx = _get_log_statement_idx_subsumed(src_trace, tar_trace)
    return (mismatched_log_stat_idx, mismatched_log_stat_idx)


def _indentation(line: str) -> int:
    '''Return the indentation in character count of given line.'''
    return len(line.removesuffix(line.lstrip()))


def _build_line_map(original: str, modified: str) -> List[Optional[int]]:
  '''
  Map line indices in modified code to line indices in original code.
  '''
  original_lines = original.split('\n')
  modified_lines = modified.split('\n')
  mapping: List[Optional[int]] = [None] * len(modified_lines)
  matcher = difflib.SequenceMatcher(a=original_lines, b=modified_lines)
  for tag, i1, i2, j1, j2 in matcher.get_opcodes():
    if tag == 'equal':
      for orig_idx, mod_idx in zip(range(i1, i2), range(j1, j2)):
        mapping[mod_idx] = orig_idx
  return mapping


def _remap_error_lines(
  error_lines: Dict[int, str],
  line_map: Optional[List[Optional[int]]],
  original_program: str,
) -> Dict[int, str]:
  if not line_map:
    return error_lines
  original_lines = original_program.split('\n')
  remapped: Dict[int, str] = {}
  for mod_idx, line in error_lines.items():
    orig_idx = None
    if 0 <= mod_idx < len(line_map):
      orig_idx = line_map[mod_idx]
    if orig_idx is None:
      candidates = [i for i, l in enumerate(original_lines) if line in l]
      if len(candidates) == 1:
        orig_idx = candidates[0]
      else:
        stripped = line.strip()
        if stripped:
          candidates = [i for i, l in enumerate(original_lines) if stripped in l]
          if len(candidates) == 1:
            orig_idx = candidates[0]
    if orig_idx is not None and 0 <= orig_idx < len(original_lines):
      remapped[orig_idx] = original_lines[orig_idx]
  return remapped if remapped else error_lines


def _remap_tar_error_dict(
  tar_error_dict: dict,
  line_map: Optional[List[Optional[int]]],
  original_program: str,
) -> None:
  if not line_map:
    return
  line_num = tar_error_dict.get('line_num')
  if not line_num:
    return
  mod_idx = line_num - 1
  original_lines = original_program.split('\n')
  orig_idx = None
  if 0 <= mod_idx < len(line_map):
    orig_idx = line_map[mod_idx]
  if orig_idx is None:
    line_content = tar_error_dict.get('line_content')
    if line_content:
      candidates = [i for i, l in enumerate(original_lines) if line_content in l]
      if len(candidates) == 1:
        orig_idx = candidates[0]
      else:
        stripped = line_content.strip()
        if stripped:
          candidates = [i for i, l in enumerate(original_lines) if stripped in l]
          if len(candidates) == 1:
            orig_idx = candidates[0]
  if orig_idx is None or not (0 <= orig_idx < len(original_lines)):
    return
  tar_error_dict['line_num'] = orig_idx + 1
  tar_error_dict['line_content'] = original_lines[orig_idx]


def _adjust_line_nums_error_lines(
  error_lines: Dict[int, str],
  gt_line_map: Dict[int, int],
) -> Dict[int, str]:
  '''
  Adjust line numbers in error_lines according to gt_line_map:
  gt_line_map contains a mapping of line numbers in tar test script
  with ground truth translations to line numbers in tar test script
  without ground truth translations. We need this mapping because
  expansion ids from duoglot translation use line numbers in tar
  test script without ground truth translations (functions with ground
  truth translations are manually translated at the string level).
  NOTE gt_line_map is 1-based, error_lines is 0-based.
  RETURN a new error_lines dictionary with adjusted line numbers.
  '''
  assert gt_line_map is not None, 'expected gt_line_map to be not None'
  assert len(gt_line_map) > 0, 'expected gt_line_map to be non-empty'

  adjusted: Dict[int, str] = {}
  for line_num, line_content in error_lines.items():
    '''
    If (line_num + 1) is not in gt_line_map, it suggests that the error is at one of the following:
    1. function header
    2. function closing bracket
    3. function body that has a ground truth translation
    '''
    assert (line_num + 1) in gt_line_map, f'line number {line_num + 1} not found in gt_line_map'
    adjusted_line_num = gt_line_map[line_num + 1] - 1  # read 1-based, write 0-based
    adjusted[adjusted_line_num] = line_content
  return adjusted


def _adjust_line_nums_error_dict(
  tar_error_dict: dict,
  gt_line_map: Dict[int, int],
) -> dict:
  '''
  Adjust line numbers in tar_error_dict according to gt_line_map.
  Refer to _adjust_line_nums_error_lines for more details.
  NOTE gt_line_map is 1-based, tar_error_dict line_num is 1-based.
  RETURN modify tar_error_dict in-place with adjusted line number and return it.
  '''
  if not gt_line_map:
    return tar_error_dict
  assert gt_line_map is not None, 'expected gt_line_map to be not None'
  assert len(gt_line_map) > 0, 'expected gt_line_map to be non-empty'

  line_num = tar_error_dict['line_num']
  '''
  If line_num is not in gt_line_map, it suggests that the error is at one of the following:
  1. function header
  2. function closing bracket
  3. function body that has a ground truth translation
  '''
  assert line_num in gt_line_map, f'line number {line_num} not found in gt_line_map'
  adjusted_line_num = gt_line_map[line_num]
  tar_error_dict['line_num'] = adjusted_line_num
  return tar_error_dict


def _get_error_lines(
  tar_program_instr: str,
  mismatched_log_stat_idx: int
) -> Dict[int, str]:
  '''
  Return the line number and content
  in the given instrumented target program
  that can identify the nodes whose runtime value
  is traced by the mismatched log statement.

  Line numbers starts at 0 while log statement index starts at 1.
  '''
  assert mismatched_log_stat_idx >= 1, 'log index starts at 1'
  lines = tar_program_instr.split('\n')
  assert len(lines) > mismatched_log_stat_idx, 'no nonlog statement'
  for base, line in enumerate(lines):
    if line.lstrip().startswith(f'myexactlog({mismatched_log_stat_idx}'):
      break
  else:
    raise AssertionError(f'{mismatched_log_stat_idx=} not found')

  base_indentation = _indentation(lines[base])
  if base + 1 < len(lines) and lines[base+1].lstrip().startswith('return '):
    # The log statement for a return statement is after it.
    start = base + 1
    for stop, line in enumerate(lines[start+1:], start=start+1):
      if _indentation(line) <= base_indentation:
        break
    else:  # empty loop would not set stop
      stop = len(lines)
  else:
    stop = base
    for start, line in zip(reversed(range(stop)), lines[stop-1::-1]):
      if _indentation(line) <= base_indentation:
        break
    else:  # empty loop would not set start
      start == 0
    if lines[start].lstrip().startswith(f'myexactlog('):
      assert start + 1 == stop, 'expecting consecutive log statements'
      return {}
  return {i: lines[i] for i in range(start, stop)}


def _extract_err_lines_from_trace_mismatch(
  src_trace: list,
  tar_program_instr: str,
  tar_trace: list
) -> Tuple[dict, Tuple[int, int]]:
  '''
  This function assumes that there is a trace mismatch betwenn
  src and tar test scripts. Trace mismatch points to a semantic error
  in the tar test script since we assume that src test script is correct.
  This function returns line numbers (0-based) and line contents
  at which a semantic error might have occured. By having this information,
  we can choose alternative translation rules to fix the semantic error.
  '''

  '''
  Error lines is a dictionary where keys are line numbers (0-based) and values
  are the lines of the tar program that caused the trace mismatch.
  '''
  mismatched_log_stat_idxs = _get_mismatched_log_statement_idxs(src_trace, tar_trace)
  src_mmls_idx, tar_mmls_idx = mismatched_log_stat_idxs

  _CHOOSE_MIN_LOG_STAT_IDX = False
  if src_mmls_idx != tar_mmls_idx:
    if _CHOOSE_MIN_LOG_STAT_IDX:
      '''
      If src and tar scripts go to different log statements,
      then we need to choose the smallest log statement index.
      Consider the following example:
      ```                                 ```
      if Sum in mp.keys():                if (Array.from(Object.keys(mp)).includes(Sum)) {
          myexactlog(10, 2)                   myexactlog(10, 2);
          pass                            }
      mp[Sum] = mp.get(Sum, 0) + 1        mp[Sum] = (Object.prototype.hasOwnProperty.call(mp, Sum) ? mp[Sum] : 0) + 1;
      myexactlog(12, mp)                  myexactlog(12, mp);
      ```                                 ```
      If src enters 10, but tar goes to 12, then the issue at tar is at 10,
      i.e. it should have also entered 10.
      If src goes to 12, but tar enters 10, then the issue at tar is also at 10,
      i.e. it should not have entered 10.
      Thus we always select the smaller log statement index.
      '''
      error_lines = _get_error_lines(tar_program_instr, min(tar_mmls_idx, src_mmls_idx))
    else:
      '''
      The above statement is not always true. Consider the following example:
      ```
      def handle_comment():            function handle_comment() {
          i = j                            var i = j;
          myexactlog(3, i)                 myexactlog(3, i); }
      ...                              ...
      myexactlog(27, 5)                myexactlog(27, 5);
      act = handle_comment()           var act = null;
      myexactlog(28, act)              myexactlog(28, act);
      ```
      After 27, src goes to 3, but tar goes to 28. The issue at tar is at 28, not 3.
      '''
      error_lines_src_idx = _get_error_lines(tar_program_instr, src_mmls_idx)
      error_lines_tar_idx = _get_error_lines(tar_program_instr, tar_mmls_idx)
      error_lines = {**error_lines_src_idx, **error_lines_tar_idx}
  else:
    error_lines = _get_error_lines(tar_program_instr, src_mmls_idx)
  return error_lines, mismatched_log_stat_idxs


def _check_for_possible_loop_semantic_diff_gfg(
  src_program_instr: str,
  tar_program_instr: str,
  subject: p_subject.PirelSubject
) -> Tuple[str, str]:
  '''
  This function checks for possible loop semantic differences
  between src_program_instr and tar_program_instr.
  For example, iterating over a Python dictionary
  and a JavaScript object may lead to different
  order of iterations.
  '''

  _MPY = {
    'fiic':
    r'^(\s+)for {item_var} in {cont_var}:\s*$',
    'fiicv':
    r'^(\s+)for {item_var} in {cont_var}.values\(\):\s*$',
  }
  _MJS = {
    'fiookc':
    r'^(\s+)for \((\w+) {item_var} of Object.keys\({cont_var}\)\) {{\s*$',
    'fioovc':
    r'^(\s+)for \((\w+) {item_var} of Object.values\({cont_var}\)\) {{\s*$',
    'fioc':
    r'^(\s+)for \((\w+) {item_var} of {cont_var}\) {{\s*$',
  }
  _RPY = {
    'fiisc':
    r'\1for {item_var} in sorted({cont_var}):',
    'fiiscv':
    r'\1for {item_var} in sorted({cont_var}.values()):'
  }
  _RJS = {
    'fiookcsn':
    r'\1for (\2 {item_var} of Object.keys({cont_var}).sort((a, b) => Number(a) - Number(b))) {{',
    'fiookccnsn':
    r'\1for (\2 {item_var} of Object.keys({cont_var}).map(k => Number(k)).sort((a, b) => a - b)) {{',
    'fioovcsn':
    r'\1for (\2 {item_var} of Object.values({cont_var}).sort((a, b) => Number(a) - Number(b))) {{',
    'fioafcsn':
    r'\1for (\2 {item_var} of Array.from({cont_var}).sort((a, b) => Number(a) - Number(b))) {{'
  }

  repl_dict = p_utils.read_json(p_consts.TRANSLATION_RULES_DIR / 'text-based' / 'iter_collection_gfg.json')
  if subject.name not in repl_dict:
    return src_program_instr, tar_program_instr
  logger.debug('Checking for possible loop semantic differences in src and tar programs.')
  subject_conf = repl_dict[subject.name]
  repl_type = subject_conf['type']
  cont_var = subject_conf['cont_var']
  item_var = subject_conf['item_var']

  if repl_type == 'for_key_in_dict':
    src_pattern = re.compile(_MPY['fiic'].format(item_var=item_var, cont_var=cont_var), flags=re.MULTILINE)
    tar_pattern = re.compile(_MJS['fiookc'].format(item_var=item_var, cont_var=cont_var), flags=re.MULTILINE)
    src_repl = _RPY['fiisc'].format(item_var=item_var, cont_var=cont_var)
    tar_repl = _RJS['fiookcsn'].format(item_var=item_var, cont_var=cont_var)

  elif repl_type == 'for_key_in_dict_int_cast':
    src_pattern = re.compile(_MPY['fiic'].format(item_var=item_var, cont_var=cont_var), flags=re.MULTILINE)
    tar_pattern = re.compile(_MJS['fiookc'].format(item_var=item_var, cont_var=cont_var), flags=re.MULTILINE)
    src_repl = _RPY['fiisc'].format(item_var=item_var, cont_var=cont_var)
    tar_repl = _RJS['fiookccnsn'].format(item_var=item_var, cont_var=cont_var)

  elif repl_type == 'for_value_in_dict_values':
    src_pattern = re.compile(_MPY['fiicv'].format(item_var=item_var, cont_var=cont_var), flags=re.MULTILINE)
    tar_pattern = re.compile(_MJS['fioovc'].format(item_var=item_var, cont_var=cont_var), flags=re.MULTILINE)
    src_repl = _RPY['fiiscv'].format(item_var=item_var, cont_var=cont_var)
    tar_repl = _RJS['fioovcsn'].format(item_var=item_var, cont_var=cont_var)

  elif repl_type == 'for_item_in_set':
    src_pattern = re.compile(_MPY['fiic'].format(item_var=item_var, cont_var=cont_var), flags=re.MULTILINE)
    tar_pattern = re.compile(_MJS['fioc'].format(item_var=item_var, cont_var=cont_var), flags=re.MULTILINE)
    src_repl = _RPY['fiisc'].format(item_var=item_var, cont_var=cont_var)
    tar_repl = _RJS['fioafcsn'].format(item_var=item_var, cont_var=cont_var)

  else:
    raise NotImplementedError(f'Unknown repl_type: {repl_type}')

  after_src_program_instr, src_count = src_pattern.subn(src_repl, src_program_instr)
  after_tar_program_instr, tar_count = tar_pattern.subn(tar_repl, tar_program_instr)

  if src_count != tar_count:
    logger.debug(
      f'Number of replacements differ between src and tar programs. '
      f'Probably not found in tar_program_instr. Skipping replacement.')
    return src_program_instr, tar_program_instr

  logger.debug(f'Replaced {src_count} loop semantic difference(s) in src and tar programs.')
  p_utils.log_file_time(f'before_src_program_instr.py', src_program_instr)
  p_utils.log_file_time(f'before_tar_program_instr.js', tar_program_instr)
  p_utils.log_file_time(f'after_src_program_instr.py', after_src_program_instr)
  p_utils.log_file_time(f'after_tar_program_instr.js', after_tar_program_instr)
  return after_src_program_instr, after_tar_program_instr


def _check_for_instrumented_log_statements_gfg(
  src_program_instr: str,
  tar_program_instr: str,
  subject: p_subject.PirelSubject
) -> Tuple[str, str]:
  '''
  This function modifies log statements for certain subjects.
  The modification is done on a string level using regex.
  '''
  conf_data = {
    # In G0289, change the 2nd argument of myexactlog()
    # from 'res' to 'int(res)' in src program
    # and from 'res' to 'Number(res)' in tar program
    # because 'res' is string in tar program.
    'G0289': {
      'py': {
        'src': r'^(\s+)myexactlog\((\d+), res\)\s*$',
        'rpl': r'\1myexactlog(\2, int(res))'
      },
      'js': {
        'src': r'^(\s+)myexactlog\((\d+), res\);\s*$',
        'rpl': r'\1myexactlog(\2, Number(res));'
      }
    },
    # In G0326, change the 2nd argument of myexactlog()
    # from 'heapq' to 'Q' in both src and tar programs
    # because 'heapq' is a Python module name, while 'Q' is
    # an object on which a function of 'heapq' is called.
    # Alternatively, LogStatementInserter can be modified.
    'G0326': {
      'py': {
        'src': r'^(\s+)myexactlog\((\d+), heapq\)\s*$',
        'rpl': r'\1myexactlog(\2, Q)'
      },
      'js': {
        'src': r'^(\s+)myexactlog\((\d+), heapq\);\s*$',
        'rpl': r'\1myexactlog(\2, Q);'
      }
    }
  }

  if subject.name not in conf_data:
    return src_program_instr, tar_program_instr

  logger.debug('Post-processing instrumented log statements in src and tar programs.')

  subject_conf = conf_data[subject.name]
  assert subject.src_lang in subject_conf
  assert subject.tar_lang in subject_conf

  src_conf = subject_conf[subject.src_lang]
  tar_conf = subject_conf[subject.tar_lang]
  assert 'src' in src_conf and 'rpl' in src_conf, 'sanity check'
  assert 'src' in tar_conf and 'rpl' in tar_conf, 'sanity check'

  src_pattern = re.compile(src_conf['src'], flags=re.MULTILINE)
  tar_pattern = re.compile(tar_conf['src'], flags=re.MULTILINE)
  src_repl = src_conf['rpl']
  tar_repl = tar_conf['rpl']

  after_src_program_instr, src_count = src_pattern.subn(src_repl, src_program_instr)
  after_tar_program_instr, tar_count = tar_pattern.subn(tar_repl, tar_program_instr)

  if src_count != tar_count:
    logger.warning(
      f'Number of replacements differ between src and tar programs. '
      f'Should not normally happen. Skipping replacement.')
    return src_program_instr, tar_program_instr

  logger.debug(f'Replaced {src_count} instrumented log statements in src and tar programs.')
  p_utils.log_file_time(f'before_src_program_instr.py', src_program_instr)
  p_utils.log_file_time(f'before_tar_program_instr.js', tar_program_instr)
  p_utils.log_file_time(f'after_src_program_instr.py', after_src_program_instr)
  p_utils.log_file_time(f'after_tar_program_instr.js', after_tar_program_instr)
  return after_src_program_instr, after_tar_program_instr


def _check_for_rec_fn_calls_gfg(
  src_program_instr: str,
  tar_program_instr: str,
  subject: p_subject.PirelSubject
) -> Tuple[str, str]:
  '''
  This function replaces recursive function calls with literal values
  to avoid hitting recursion limits or type errors.
  Most common case that this function handles is
  when a recursive call is part of a larger expression, and the
  returned value is None, e.g. `x = rec_fn(...) + 1`.
  '''
  repl_dict = p_utils.read_json(p_consts.TRANSLATION_RULES_DIR / 'text-based' / 'rec_call_replacements_gfg.json')

  if subject.name not in repl_dict:
    return src_program_instr, tar_program_instr

  logger.debug('Replacing recursive function calls in src and tar programs.')
  p_utils.log_file_time(f'before_src_program_instr.py', src_program_instr)
  p_utils.log_file_time(f'before_tar_program_instr.js', tar_program_instr)

  subject_repl = repl_dict[subject.name]
  for defined_fn, invoked_fns_dict in subject_repl.items():
    for invoked_fn, lit_values_dict in invoked_fns_dict.items():
      assert subject.src_lang in lit_values_dict, 'sanity check'
      assert subject.tar_lang in lit_values_dict, 'sanity check'
      src_lit_value = lit_values_dict[subject.src_lang]
      tar_lit_value = lit_values_dict[subject.tar_lang]
      src_program_instr, src_repl_done = pvpy.FunctionInvocationReplacer.replace_function_invocations(
        src_program_instr, defined_fn, invoked_fn, src_lit_value)
      tar_program_instr, tar_repl_done = pvjs.FunctionInvocationReplacer.replace_function_invocations(
        tar_program_instr, defined_fn, invoked_fn, tar_lit_value)
      assert src_repl_done == tar_repl_done, 'sanity check'

  p_utils.log_file_time(f'after_src_program_instr.py', src_program_instr)
  p_utils.log_file_time(f'after_tar_program_instr.js', tar_program_instr)
  return src_program_instr, tar_program_instr



async def _run_tests(
  src_program_instr: str,
  tar_program_instr: str,
  subject: p_subject.PirelSubject
) -> None:
  '''
  RAISE `SrcTestScriptRunError` if there is an error when running src test script.
  RAISE `TarTestScriptRunError` if there is an error when running tar test script.
  RAISE `TraceMismatchError` if there is a trace mismatch between src and tar test scripts.

  NOTE `subject` must contain the following fields:
  - name
  - src_lang
  - tar_lang

  NOTE never modify `src_program_instr` and `tar_program_instr` directly.
  '''

  def _store_run_tests_cache_with_timing(payload: dict) -> None:
    nonlocal run_tests_stms, cache_key
    run_tests_etms = p_utils.current_time_msec()
    payload_w_time = copy.deepcopy(payload)
    timing = payload_w_time.get('timing', {})
    if not isinstance(timing, dict):
      timing = {}
    timing['run_tests_stms'] = run_tests_stms
    timing['run_tests_etms'] = run_tests_etms
    timing['run_tests_ms'] = run_tests_etms - run_tests_stms
    timing['cached_at_ms'] = run_tests_etms
    payload_w_time['timing'] = timing
    _store_run_tests_cache(cache_key, payload_w_time)

  p_utils.log_json_time(f'args-run_tests.json', locals())
  logger.debug('~~~ Starting to run source and target test scripts.')

  run_tests_stms = p_utils.current_time_msec()
  _ensure_run_tests_cache_loaded()

  # Pre-process `src_program_instr` and `tar_program_instr` to handle special cases in GFG benchmark.
  if subject.benchmark_name == 'gfg':
    src_program_instr, tar_program_instr = _check_for_rec_fn_calls_gfg(src_program_instr, tar_program_instr, subject)
    src_program_instr, tar_program_instr = _check_for_instrumented_log_statements_gfg(src_program_instr, tar_program_instr, subject)
    src_program_instr, tar_program_instr = _check_for_possible_loop_semantic_diff_gfg(src_program_instr, tar_program_instr, subject)

  '''
  Prepare final src and tar test scripts.
  NOTE These test scripts are the ones that are actually executed to obtain src and tar traces.
  '''
  # Previously, we replaced bodies of fns in src_program that have ground truth
  # translations with `pass`. Now, we need to revert that action.
  src_program_instr_gt = p_code_runner._replace_src_fns_with_pass_with_gt_translations(src_program_instr, subject.name)
  src_mylog_impl = p_code_runner.get_mylog_impl(subject.src_lang, subject_name=subject.name)
  src_program_run = src_mylog_impl + src_program_instr_gt

  # Replace bodies of fns in tar_program that have ground truth
  # translations with respective ground truth translations.
  tar_program_instr_gt, gt_line_map = p_code_runner._replace_tar_fns_with_gt_translations(tar_program_instr, subject)
  tar_mylog_impl = p_code_runner.get_mylog_impl(subject.tar_lang, subject_name=subject.name)
  tar_program_run_base = tar_mylog_impl + tar_program_instr_gt
  tar_program_run = _inject_py_list_repr_helper_if_needed(tar_program_run_base)
  injected_prefix_lines = tar_program_run.count('\n') - tar_program_run_base.count('\n')
  if injected_prefix_lines < 0:
    injected_prefix_lines = 0
  mylog_num_lines = tar_mylog_impl.count('\n') + injected_prefix_lines
  gt_line_map = {k + mylog_num_lines: v for k, v in gt_line_map.items()}  # shift by prelude lines before target program

  # uncomment if necessary for debugging
  # p_utils.write_text(p_consts.SRC_DIR / 'asrc_program_instr.py', src_program_instr)
  # p_utils.write_text(p_consts.SRC_DIR / 'atar_program_instr.js', tar_program_instr)
  # p_utils.write_text(p_consts.SRC_DIR / 'asrc_program_run.py', src_program_run)
  # p_utils.write_text(p_consts.SRC_DIR / 'atar_program_run.js', tar_program_run)
  # p_utils.write_text(p_consts.SRC_DIR / 'agt_line_map.json', json.dumps(gt_line_map, indent=2))

  '''
  Check cache for test results of the given src and tar test scripts.
  '''
  cache_key = _make_run_tests_cache_key(subject, src_program_run, tar_program_run)
  cached_result = _RUN_TESTS_CACHE.get(cache_key)
  if cached_result is not None:
    logger.debug('~~~ run_tests cache hit')
    _accumulate_subject_cached_validation_ms(
      subject,
      _extract_timing_ms(cached_result, 'run_tests_ms'),
    )
    if cached_result['ok']:
      return
    err_type = cached_result['err_type']
    if err_type == 'SrcTestScriptRunError':
      raise SrcTestScriptRunError(cached_result['msg'])
    if err_type == 'TarTestScriptRunError':
      raise TarTestScriptRunError(copy.deepcopy(cached_result['tar_error_dict']))
    if err_type == 'TraceMismatchError':
      error_lines = copy.deepcopy(cached_result['error_lines'])
      error_lines = {int(line_num): line_content for line_num, line_content in error_lines.items()}
      raise TraceMismatchError(
        error_lines,
        tuple(cached_result['mismatched_log_stat_idxs'])
        if cached_result['mismatched_log_stat_idxs'] is not None
        else None
      )
    raise RuntimeError(f'Unexpected cached run_tests error type: {err_type}')

  '''
  Run `src_program_run` and collect output trace.
  '''
  src_trace, src_stderr = await p_code_runner.run_src_test_script(src_program_run, subject)
  assert is_valid_trace(src_trace), 'src_trace must be a valid trace'

  # there is an error in running src test script
  if src_stderr != '':
    msg = f'SHOULD NOT HAPPEN! Error running src test script: {src_stderr}'
    logger.critical(msg)
    _store_run_tests_cache_with_timing({'ok': False, 'err_type': 'SrcTestScriptRunError', 'msg': msg})
    raise SrcTestScriptRunError(msg)
  else:
    logger.debug('GOOD No errors running src test script.')

  '''
  Run `tar_program_run` and collect output trace.
  '''
  tar_trace, tar_std_error = await p_code_runner.run_tar_test_script(tar_program_run, subject)
  assert is_valid_trace(tar_trace), 'tar_trace must be a valid trace'

  '''
  At this point, we have all the necessary data to decide whether to
  1. finish running tests without any errors
  2. raise TraceMismatchError if there is a trace mismatch
  3. raise TarTestScriptRunError if there is an error in running tar test script

  NOTE Trace categories (relative to each other)
  src and tar traces may fall into one of the following 6 categories:
  1. len(src_trace) < len(tar_trace) - src trace is shorter than tar trace
     a. is_trace_subsumed(src_trace, tar_trace)
        - there is a semantic error in tar test script due to
          possibly extra loop iterations
     b. not is_trace_subsumed(src_trace, tar_trace)
        - there is a semantic error due to trace mismatch
  2. len(src_trace) > len(tar_trace) - src trace is longer than tar trace
     a. is_trace_subsumed(tar_trace, src_trace)
        - there is a semantic error in tar test script due to
          possibly missing loop iterations
     b. not is_trace_subsumed(tar_trace, src_trace)
        - there is a semantic error due to trace mismatch
  3. len(src_trace) == len(tar_trace) - src trace and tar trace are of the same length
     a. are_traces_equal_rec(src_trace, tar_trace)
        - there is no semantic error
     b. not are_traces_equal_rec(src_trace, tar_trace)
        - there is a semantic error due to trace mismatch

  NOTE Error categories
  Regarding what error to raise:
  1. raise TarTestScriptRunError iff
     a. (tar_std_error != '') and is_trace_subsumed(tar_trace, src_trace)
        - case 2a
        - cases 1a, 3a are not supported yet
  2. raise TraceMismatchError iff
     a. (tar_std_error == '') and does_trace_subsume_another(src_trace, tar_trace)
        - cases 1b, 2b, 3b
        - cases 1a, 2a, 3a are not supported yet
     b. (tar_std_error != '') and does_trace_subsume_another(src_trace, tar_trace)
        - cases 1b, 2b, 3b
        - cases 1a, 2a, 3a are not supported yet
  '''

  # there is an error in running tar test script
  if tar_std_error != '':
    logger.debug(f'BAD Error running tar test script:\n{tar_std_error.strip()}')
    '''
    Sometimes, it might be the case that at the time an error occurs in tar test script,
    there already is a trace mismatch between src and tar traces. This suggests that the
    tar test script error occured due to an invalid rule chosen earlier. In this case,
    we should ensure that at the time of tar test script error, the src and tar traces
    are identical by choosing the correct translation rule.
    '''
    if not does_trace_subsume_another(src_trace, tar_trace):
      logger.debug('Trace mismatch between src and tar traces at the time of tar test script error.')
      error_lines, mismatched_log_stat_idxs = _extract_err_lines_from_trace_mismatch(src_trace, tar_program_instr, tar_trace)
      logger.debug(f'Trace mismatch error lines:\n{json.dumps(error_lines, indent=2)}')
      _store_run_tests_cache_with_timing({
        'ok': False, 'err_type': 'TraceMismatchError', 'error_lines': copy.deepcopy(error_lines),
        'mismatched_log_stat_idxs': copy.deepcopy(mismatched_log_stat_idxs)})
      raise TraceMismatchError(error_lines, mismatched_log_stat_idxs)

    '''
    At this point, we know that one of the traces subsumes the other.
    If the src trace subsumes the tar trace, it is ok, because up to the point of
    tar test script error, the src and tar traces match.
    If the tar trace subsumes the src trace, it is not ok, because this case is not
    considered yet.
    '''
    src_trace_size = src_trace[1]
    tar_trace_size = tar_trace[1]

    '''
    Special case: both traces are empty and tar test script fails.
    There is no trace signal to map to a log statement, so treat it as a
    target-script compile/runtime error and recover via compile-error chooser.
    '''
    if src_trace_size == tar_trace_size and src_trace_size == 0:
      logger.debug('Both src and tar traces are empty.')
      tar_error_dict = p_code_runner.extract_err_from_stderr_JS(tar_std_error, subject.tar_lang)
      tar_error_dict = _adjust_line_nums_error_dict(tar_error_dict, gt_line_map)
      _store_run_tests_cache_with_timing({
        'ok': False, 'err_type': 'TarTestScriptRunError',
        'tar_error_dict': copy.deepcopy(tar_error_dict)})
      raise TarTestScriptRunError(tar_error_dict)

    if src_trace_size <= tar_trace_size:
      logger.warning('src_trace is not longer than tar_trace')
    tar_error_dict = p_code_runner.extract_err_from_stderr_JS(tar_std_error, subject.tar_lang)
    tar_error_dict = _adjust_line_nums_error_dict(tar_error_dict, gt_line_map)
    _store_run_tests_cache_with_timing({
      'ok': False, 'err_type': 'TarTestScriptRunError',
      'tar_error_dict': copy.deepcopy(tar_error_dict)})
    raise TarTestScriptRunError(tar_error_dict)
  else:
    logger.debug('GOOD No errors running tar test script.')

  # 3. compare traces
  are_traces_identical = are_traces_equal_rec(src_trace, tar_trace)
  if not are_traces_identical:
    error_lines, mismatched_log_stat_idxs = _extract_err_lines_from_trace_mismatch(src_trace, tar_program_instr, tar_trace)
    logger.debug(
      f'Traces are not identical. There is a semantic error in translation.\n'
      f'error_lines:\n{json.dumps(error_lines, indent=2)}')
    _store_run_tests_cache_with_timing({
      'ok': False, 'err_type': 'TraceMismatchError', 'error_lines': copy.deepcopy(error_lines),
      'mismatched_log_stat_idxs': copy.deepcopy(mismatched_log_stat_idxs)})
    raise TraceMismatchError(error_lines, mismatched_log_stat_idxs)

  _store_run_tests_cache_with_timing({'ok': True})


_CACHE_get_tar_test_code = {}
def _get_tar_test_code(
  src_test_code: Optional[str],
  subject: p_subject.PirelSubject
) -> Optional[str]:
  '''
  Ideally, this function is run only once.
  '''
  if src_test_code in _CACHE_get_tar_test_code:
    return _CACHE_get_tar_test_code[src_test_code]

  if not subject.is_three_split:
    assert src_test_code is None, 'sanity check'
    return None

  # translate `src_test_code` using `translation_rules_test_code`
  duoglot_translate_result = p_pirel.duoglot_translate_wrapper(
    src_code=src_test_code,
    src_lang=subject.src_lang,
    tar_lang=subject.tar_lang,
    trans_rules=subject.translation_rules_test_code,
    auto_backward=subject.auto_backward,
    choices=subject.choices,
    skip_template_extraction=True
  )
  tar_test_code = duoglot_translate_result['tar_code']
  _CACHE_get_tar_test_code[src_test_code] = tar_test_code
  return tar_test_code


def _get_tar_test_call_code(
  src_test_call_code: str
) -> str:
  '''
  For the moment, just use `src_test_call_code` as `tar_test_call_code`,
  because Python and JavaScript function call syntax is the same.
  '''
  return src_test_call_code


def _replace_src_fns_with_gt_translations_with_pass(
  src_main_code: str,
  subject: p_subject.PirelSubject
) -> str:
  '''
  Return a modified src_main_code where the bodies of functions that
  have ground-truth translations are replaced with `pass` (for Python)
  '''
  logger.debug('Replacing bodies of src functions with ground-truth translations with empty bodies.')
  config_fpath = p_consts.SKEL_BENCHMARK_DIR / f'{subject.name}-config.json'
  if not config_fpath.exists():
    logger.warning(f'Config file {config_fpath} does not exist. Skipping emptying function bodies.')
    return src_main_code
  subject_config = p_utils.read_json(config_fpath)
  assert 'ground_truth_translations' in subject_config, 'expecting ground_truth_translations in subject config'
  gt_translations = subject_config['ground_truth_translations']
  fn_names = pvpy.DefinedFunctionNameExtractor.get_defined_function_names(src_main_code)
  modified_code = src_main_code
  for fn_name, gt_map in gt_translations.items():
    assert fn_name in fn_names, f'sanity check: function {fn_name} should be defined in src_main_code'
    assert fn_names.count(fn_name) == 1, f'sanity check: function {fn_name} should be defined only once in src_main_code'
    modified_code = pvpy.FunctionBodyReplacer.replace_function_body(
      modified_code,
      fn_name,
      'pass',
      dont_touch_inner_fn_defs=True,
      dont_insert_pass_if_inner_fns_exist=True,
    )
  return modified_code


def _get_tar_main_code_instr(
  src_main_code: str,
  choices: dict,
  subject: p_subject.PirelSubject
) -> Tuple[str, Dict[int, List[dict]], List[dict]]:
  '''
  Translate `src_main_code` using `translation_rules_main_code` and `choices`.
  RAISE SrcTestScriptProblematicNodeError
  '''
  logger.debug('Translating src_main_code_instr to get tar_main_code_instr.')

  assert subject.translation_rules_main_code is not None, \
    'translation rules for main code must be provided'

  translate_stms = p_utils.current_time_msec()
  cache_key = _make_tar_main_translate_cache_key(src_main_code, choices, subject)
  cached_result = _TAR_MAIN_TRANSLATE_CACHE.get(cache_key)
  if cached_result is not None:
    _TAR_MAIN_TRANSLATE_CACHE.pop(cache_key, None)
    _TAR_MAIN_TRANSLATE_CACHE[cache_key] = cached_result
    logger.debug('~~~ tar main translation cache hit')
    _accumulate_subject_cached_validation_ms(
      subject,
      _extract_timing_ms(cached_result, 'tar_main_translate_ms'),
    )
    return (
      cached_result['tar_main_code'],
      copy.deepcopy(cached_result['map_to_exid']),
      copy.deepcopy(cached_result['translate_dbg_history']),
    )

  try:
    duoglot_translate_result = p_pirel.duoglot_translate_wrapper(
      src_code=src_main_code,
      src_lang=subject.src_lang,
      tar_lang=subject.tar_lang,
      trans_rules=subject.translation_rules_main_code,
      auto_backward=subject.auto_backward,
      choices=choices,
      skip_template_extraction=True
    )
  except d_grammar_expand.TranslationRuleNotFoundException as exc:
    templates_dict = exc.get_templates_dict()
    problematic_node_type = templates_dict.get('problematic_node_type')
    ignore_prob_expr_stmt = bool(
      getattr(subject, 'ignore_problematic_expression_statement_in_main_translate', False))
    if ignore_prob_expr_stmt and problematic_node_type == 'expression_statement':
      logger.warning(
        'Recovery-assisted mode: keep TranslationRuleNotFoundException for '
        'problematic expression_statement in src_main_code translation.')
      raise
    logger.warning(f'Caught TranslationRuleNotFoundException when translating src_main_code: {exc}')
    err_obj = SrcTestScriptProblematicNodeError(
      f'There is a problematic node in src_main_code:\n'
      f'problematic_node_type = "{templates_dict["problematic_node_type"]}", '
      f'problematic_node_id = {templates_dict["problematic_node_id"]}')
    err_obj.src_main_code = src_main_code
    err_obj.choices = choices
    err_obj.translation_rules_main_code = subject.translation_rules_main_code
    err_obj.problematic_node_id = templates_dict['problematic_node_id']
    err_obj.problematic_node_type = templates_dict['problematic_node_type']
    raise err_obj

  tar_main_code = duoglot_translate_result['tar_code']
  map_to_exid = duoglot_translate_result['map_to_exid']
  translate_dbg_history = duoglot_translate_result['dbg_history']
  translate_etms = p_utils.current_time_msec()
  _store_tar_main_translate_cache(
    cache_key,
    {
      'tar_main_code': tar_main_code,
      'map_to_exid': copy.deepcopy(map_to_exid),
      'translate_dbg_history': copy.deepcopy(translate_dbg_history),
      'timing': {
        'tar_main_translate_stms': translate_stms,
        'tar_main_translate_etms': translate_etms,
        'tar_main_translate_ms': max(0, translate_etms - translate_stms),
        'cached_at_ms': translate_etms,
      },
    }
  )
  return tar_main_code, map_to_exid, translate_dbg_history


def _program_parts_concatenate(
  test_code: Optional[str],
  main_code: str,
  test_call_code: Optional[str],
  subject: p_subject.PirelSubject
) -> str:
  '''
  Combine `test_code`, `main_code`, and `test_call_code` into a single string.
  '''
  if not subject.is_three_split:
    assert test_code is None, 'sanity check'
    assert test_call_code is None, 'sanity check'
    return main_code
  assert test_code is not None, 'sanity check'
  assert test_call_code is not None, 'sanity check'
  return f'\n{p_consts.TEST_MAIN_CALL_DELIMITER}\n'.join([test_code, main_code, test_call_code])


def _program_parts_split(
  program: str,
  subject: p_subject.PirelSubject
) -> Tuple[Optional[str], str, Optional[str]]:
  '''
  Split `program` into test, main, and test call code snippets.
  If `subject.is_three_split` is False, return None for test and test call code snippets.
  '''
  if not subject.is_three_split:
    return None, program, None

  chunks = program.split(p_consts.TEST_MAIN_CALL_DELIMITER)
  assert len(chunks) == 3, 'sanity check: program should be split into 3 parts'
  src_test_code, src_main_code, src_test_call_code = chunks
  return src_test_code, src_main_code, src_test_call_code


# API
async def apply_translation_rules(
  subject: p_subject.PirelSubject,
  raise_on_missing_vrf_rule: bool = False,
) -> Tuple[str, List[dict]]:
  '''
  Apply the translation rules to the source program.
  Equivalent to index_bench.js::runBenchmarkHandler

  RETURN tuple:
  - plausible tar_program_instr (str)
  - translate_dbg_history (List[dict])

  Raised or propagated exceptions:
  - SrcTestScriptRunError
  - RuleCombinationsExhaustedError
  - SrcTestScriptProblematicNodeError

  NOTE subject.src_program must be instrumented with myexactlog() statements,
  since the rule applicator relies on traces generated by them to
  obtain a plausible translation.
  '''

  p_utils.log_json_time(f'args-apply_translation_rules.json', locals())
  logger.info('--rule-app--: starting rule applicator')

  src_program_instr = subject.src_program

  # The function `_program_parts_split()` is relevant only for three-split subjects (GFG).
  src_test_code, src_main_code_instr, src_test_call_code = \
    _program_parts_split(src_program_instr, subject)

  '''
  Since there are functions for which we have ground-truth translations,
  and therefore are translated directly bypassing the rule application process,
  we replace the bodies of such functions in src_main_code_instr with `pass`.
  '''
  src_main_code_instr = _replace_src_fns_with_gt_translations_with_pass(src_main_code_instr, subject)

  # Get corresponding instrumented test code and test call code.
  # These functions are relevant only for three-split subjects (GFG).
  tar_test_code = _get_tar_test_code(src_test_code, subject)
  tar_test_call_code = _get_tar_test_call_code(src_test_call_code)

  '''
  This is a list of choice options for each error line.
  '''
  choices_list_history = []

  '''
  This is a list of choice options that lead to NormalException
  with message "Automatic backwarding failed to find alternative choices".
  This exception is raised when translation with the given choices
  does not lead to a grammatically correct target program.
  '''
  choices_lists_ab_failed = []

  '''
  This is a list of choice options that lead to TarTestScriptRunError or TraceMismatchError.
  '''
  # Root cause/reason:
  # Without this seed, each new invocation starts with an empty error history,
  # so the same previously-failed choice combination can be tried again.
  # Seeding carries forward known-bad choices and prevents immediate re-selection.
  choices_lists_error = _get_failed_choices_lists(subject, src_main_code_instr)

  '''
  This is an object that is passed to the translator that tells it
  which rules to choose at given AST nodes.
  '''
  # Prefer historically successful choices to reduce first-iteration failures
  # caused by fresh rule-order combinations.
  current_choices = _get_cached_or_initial_choices(src_main_code_instr, subject)
  assert current_choices['type'] == 'ASTNODE', f'unsupported choices type "{current_choices["type"]}"'

  '''
  Rule applicator uses vanilla translator in _get_tar_main_code_instr().
  Vanilla translator is sensitive to the order of rules in translation_rules_main_code.
  This causes situations where the first iteration of the loop fails
  to just get "some" tar_main_code_instr, and therefore the entire rule
  application process fails. To mitigate this, we check the current_choices,
  and update it so that we get "some" translation src_main_code_instr.
  All the above works on the premise that the translation rules
  allow obtaining "some" translation of src_main_code_instr. If not,
  SrcTestScriptProblematicNodeError is raised as the last resort.
  '''
  # NOTE replaced by a new dedicated state TR_NOT_FOUND_ERROR in the loop below
  # commented temporarily, can be removed after the new state is verified to work well
  # current_choices = _check_and_update_choices(src_main_code_instr, current_choices, subject)

  # uncomment if necessary for debugging
  # p_utils.write_text(p_consts.SRC_DIR / 'atranslation_rules_main_code.snart', subject.translation_rules_main_code)

  # --- State machine implementation ---
  logger.debug('Starting state machine for translation rule application')

  state = 'INIT'
  context = {
    'current_choices': current_choices,
    'choices_list_history': choices_list_history,
    'choices_lists_ab_failed': choices_lists_ab_failed,
    'choices_lists_error': choices_lists_error,
    'tar_error_dict': None,
    'error_lines': None,
    'mismatched_log_stat_idxs': None,
    'map_to_exid': None,
    'translate_dbg_history': None,
    'tar_main_code_instr': None,
    'tar_program_instr': None,
    'last_error_type': None,  # 'compile' or 'semantic'
    'templates_dict': None,
    'dbg_history': None,
  }
  iteration = 0
  while True:
    iteration += 1
    logger.debug(f'--rule-app--: state={state}, iteration={iteration}')

    if state == 'INIT':
      try:
        tar_main_code_instr, map_to_exid, translate_dbg_history = _get_tar_main_code_instr(src_main_code_instr, context['current_choices'], subject)
        tar_program_instr = _program_parts_concatenate(tar_test_code, tar_main_code_instr, tar_test_call_code, subject)
        src_program_instr = _program_parts_concatenate(src_test_code, src_main_code_instr, src_test_call_code, subject)
        context['tar_main_code_instr'] = tar_main_code_instr
        context['map_to_exid'] = map_to_exid
        context['translate_dbg_history'] = translate_dbg_history
        context['tar_program_instr'] = tar_program_instr
        # try running tests
        await _run_tests(src_program_instr, tar_program_instr, subject)
        # success!
        # Keep failed cache self-healing: if a choice now succeeds, remove it
        # from failed history so future runs are not over-pruned.
        _remove_failed_choices_cache(subject, src_main_code_instr, context['current_choices'])
        _store_success_choices_cache(subject, src_main_code_instr, context['current_choices'])
        return tar_program_instr.strip(), translate_dbg_history
      except SrcTestScriptRunError as err:
        logger.critical('There is an error in running src test script. This normally should not happen')
        raise
      except TarTestScriptRunError as err:
        logger.warning('There is an error in running tar test script. Will attempt to find a new translation rules combination.')
        context['tar_error_dict'] = err.tar_error_dict
        context['last_error_type'] = 'compile'
        chs_list = context['current_choices']['choices_list']
        assert chs_list is not None, 'sanity check: choices_list should not be None for ASTNODE choices'
        context['choices_lists_error'].append(chs_list)
        # Persist compile-failing branch so subsequent invocations skip it.
        _store_failed_choices_cache(subject, src_main_code_instr, context['current_choices'])
        state = 'COMPILE_ERROR'
      except TraceMismatchError as err:
        logger.warning('There is a trace mismatch between src and tar test scripts.')
        context['error_lines'] = err.error_lines
        context['mismatched_log_stat_idxs'] = err.mismatched_log_stat_idxs
        context['last_error_type'] = 'semantic'
        chs_list = context['current_choices']['choices_list']
        assert chs_list is not None, 'sanity check: choices_list should not be None for ASTNODE choices'
        context['choices_lists_error'].append(chs_list)
        # Persist semantic-failing branch so subsequent invocations skip it.
        _store_failed_choices_cache(subject, src_main_code_instr, context['current_choices'])
        state = 'SEMANTIC_ERROR'
      except d_grammar_expand.TranslationRuleNotFoundException as err:
        logger.warning('TranslationRuleNotFoundException: failed to produce any translation of src_main_code_instr with current choices.')
        # save failed choices
        chs_list = context['current_choices']['choices_list']
        assert chs_list is not None, 'sanity check: choices_list should not be None for ASTNODE choices'
        context['choices_lists_error'].append(chs_list)
        # Persist "no translation produced" branch so it is not retried.
        _store_failed_choices_cache(subject, src_main_code_instr, context['current_choices'])
        context['templates_dict'] = err.get_templates_dict()
        context['dbg_history'] = err.dbg_history
        state = 'TR_NOT_FOUND_ERROR'
      except d_grammar_expand.NormalException as err:
        # catch NormalException from _get_tar_main_code_instr
        if not str(err).startswith('Automatic backwarding failed to find alternative choices'):
          raise
        logger.warning('NormalException: failed to produce grammatically valid target program.')
        # save failed choices
        chs_list = context['current_choices']['choices_list']
        assert chs_list is not None, 'sanity check: choices_list should not be None for ASTNODE choices'
        context['choices_lists_ab_failed'].append(chs_list)
        state = 'AB_FAILED'

    elif state == 'COMPILE_ERROR':
      proposed_choices = p_ext_rule_chooser.get_proposed_choices_compile_error(
        context['tar_program_instr'],
        context['tar_main_code_instr'],
        context['tar_error_dict'],
        context['choices_list_history'],
        context['map_to_exid'],
        context['translate_dbg_history'],
        subject.verified_choice_options,
        raise_on_missing_vrf_rule,
        src_main_code=src_main_code_instr,
        translation_rules_main_code=subject.translation_rules_main_code,
        choices_lists_ab_failed=context['choices_lists_ab_failed'],
        choices_lists_error=context['choices_lists_error'],
      )
      context['current_choices'] = proposed_choices
      state = 'INIT'

    elif state == 'SEMANTIC_ERROR':
      proposed_choices = p_ext_rule_chooser.get_proposed_choices_semantic_error(
        context['tar_program_instr'],
        context['tar_main_code_instr'],
        context['error_lines'],
        context['mismatched_log_stat_idxs'],
        context['choices_list_history'],
        context['map_to_exid'],
        context['translate_dbg_history'],
        subject.verified_choice_options,
        raise_on_missing_vrf_rule,
        src_main_code=src_main_code_instr,
        translation_rules_main_code=subject.translation_rules_main_code,
        choices_lists_ab_failed=context['choices_lists_ab_failed'],
        choices_lists_error=context['choices_lists_error'],
      )
      context['current_choices'] = proposed_choices
      state = 'INIT'

    elif state == 'AB_FAILED':
      # retry the last error context, but with updated excluded choices
      if context['last_error_type'] == 'compile':
        state = 'COMPILE_ERROR'
      elif context['last_error_type'] == 'semantic':
        state = 'SEMANTIC_ERROR'
      else:
        logger.error('Unknown last_error_type in AB_FAILED state.')
        raise RuntimeError('Unknown last_error_type in AB_FAILED state.')

    elif state == 'TR_NOT_FOUND_ERROR':
      dbg_history = context['dbg_history']
      templates_dict = context['templates_dict']
      assert dbg_history is not None, 'sanity check: dbg_history should not be None in TR_NOT_FOUND_ERROR state'
      assert templates_dict is not None, 'sanity check: templates_dict should not be None in TR_NOT_FOUND_ERROR state'
      rel_alt_step_infos : Dict[int, dict] = {}
      for i in range(2, len(dbg_history) + 1):
        prev_dbgh_elem = dbg_history[i - 2]
        dbgh_elem = dbg_history[i - 1]
        prev_alt_step = prev_dbgh_elem['alt_step']
        alt_step = dbgh_elem['alt_step']
        assert prev_alt_step == i - 1, 'sanity check'
        assert alt_step == i, 'sanity check'
        next_choices_count = prev_dbgh_elem['next_choices_status']['count']
        current_choose_idx = dbgh_elem['dbg_info']['notes']['choose_idx']
        current_rule_id = dbgh_elem['dbg_info']['notes']['rule_id']
        current_range_info = dbgh_elem['range_info']
        rel_alt_step_infos[alt_step] = {
          'next_choices_count': next_choices_count,
          'current_choose_idx': current_choose_idx,
          'current_rule_id': current_rule_id,
          'current_range_info': current_range_info
        }
      rel_alt_step_infos = p_ext_rule_chooser.rel_alt_step_info_remove_duplicates(rel_alt_step_infos)
      try:
        proposed_choices = p_ext_rule_chooser.get_next_unique_choices(
          rel_alt_step_infos,
          context['choices_list_history'],
          subject.verified_choice_options,
          raise_on_missing_vrf_rule=False,
          src_main_code=src_main_code_instr,
          translation_rules_main_code=subject.translation_rules_main_code,
          excluded_choice_options=[],
          choices_lists_ab_failed=context['choices_lists_ab_failed'],
          choices_lists_error=context['choices_lists_error'],
        )
        context['current_choices'] = proposed_choices
        state = 'INIT'
      except p_ext_rule_chooser.RuleCombinationsExhaustedError:
        msg = 'No rule to handle a node in source code.'
        logger.warning(msg)
        raise SrcTestScriptProblematicNodeError(msg)

    else:
      logger.error(f'Unknown state: {state}')
      raise RuntimeError(f'Unknown state: {state}')

