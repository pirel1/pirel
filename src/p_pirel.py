import asyncio
import ast
import csv
import copy
import hashlib
import inspect
import json
import os
import re
import textwrap
from collections import Counter, OrderedDict
from os import fspath
from sys import executable
from typing import Dict, Iterator, List, Optional, Set, Tuple, Union

import d_ast_parse
import d_ast_pretty
import d_grammar_expand
import d_grammar_rules
import p_code_runner
import p_consts
import p_data_structures as pds
import p_generator
import p_generator_lw
import p_grammar
import p_llm_gen
import p_rule_applicator as prapp
import p_ext_rule_chooser
import p_rule_inferencer
import p_rule_validator
import p_ruleset
import p_subject
import p_translators
import p_tree_log as ptlog
import p_utils
import p_visitor as pvis
import p_visitor_js as pvjs
import p_visitor_py as pvpy
from p_config import Config


_EOT_MODULE_TEMPLATE = '''from os import chdir
import inspect
def myexactlog(*args, **kwargs): pass
def _pirel_stack_str():
    names = []
    for frame_info in inspect.stack():
        fn_name = frame_info.function
        if fn_name in ('_pirel_stack_str', '<module>'):
            continue
        names.append(fn_name)
    if not names:
        return '__MODULE__'
    return '|'.join(reversed(names))
chdir({!r})
{}
'''

# Root cause:
# EoT statement-node extraction rebuilt and executed an instrumented module
# on every call, even when src/subject/lang were identical.
# Fix rationale:
# Keep a bounded LRU cache of extracted node-id order and reuse it on
# repeated calls to avoid expensive regeneration/re-execution.
_EOT_STAT_NODE_IDS_CACHE_MAX_ENTRIES = int(os.environ.get(
  'PIREL_EOT_STAT_NODE_IDS_CACHE_MAX_ENTRIES', '32'))
_EOT_STAT_NODE_IDS_CACHE: OrderedDict[Tuple[str, str, str, bool], List[int]] = OrderedDict()


def _make_eot_stat_node_ids_cache_key(
  src_program: str,
  lang: str,
  subject_name: Optional[str],
  deduplicate: bool,
) -> Tuple[str, str, str, bool]:
  subject_key = subject_name if isinstance(subject_name, str) else ''
  digest = hashlib.sha256(src_program.encode('utf-8')).hexdigest()
  return (lang, subject_key, digest, deduplicate)


def _get_cached_eot_stat_node_ids(
  cache_key: Tuple[str, str, str, bool]
) -> Optional[List[int]]:
  cached = _EOT_STAT_NODE_IDS_CACHE.get(cache_key)
  if cached is None:
    return None
  _EOT_STAT_NODE_IDS_CACHE.move_to_end(cache_key)
  return list(cached)


def _set_cached_eot_stat_node_ids(
  cache_key: Tuple[str, str, str, bool],
  node_ids: List[int],
) -> None:
  _EOT_STAT_NODE_IDS_CACHE[cache_key] = list(node_ids)
  _EOT_STAT_NODE_IDS_CACHE.move_to_end(cache_key)
  while len(_EOT_STAT_NODE_IDS_CACHE) > _EOT_STAT_NODE_IDS_CACHE_MAX_ENTRIES:
    _EOT_STAT_NODE_IDS_CACHE.popitem(last=False)

logger = p_utils.setup_logger(__name__)


class ProbNode_NoTRule_AllTSPsExhaustedError(RuntimeError): pass
class TSP_NoTRuleLearnedError(RuntimeError): pass
class CouldNotGenRefTranslationsError(RuntimeError): pass
class _ValidationError_ProblematicNodeExists(RuntimeError):
  def __init__(self, templates_dict: Optional[dict] = None):
    super().__init__('_ValidationError_ProblematicNodeExists')
    self.templates_dict = templates_dict or {}

  @property
  def problematic_node_type(self) -> Optional[str]:
    node_type = self.templates_dict.get('problematic_node_type')
    return node_type if isinstance(node_type, str) else None
class TestFunctionGenerationError(RuntimeError): pass
class NoTSPsGeneratedError(RuntimeError): pass
class PartialProgramGenerationError(RuntimeError): pass
class BypassStaRuleLearningError(RuntimeError): pass


_STAT_NODE_VALIDATION_MODE_QUICK = 'quick'
_STAT_NODE_VALIDATION_MODE_FULL = 'full'
_RULESET_CHECKPOINT_INTERVAL = 1
_EXP_RESULT_CSV_DIR = p_consts.ROOT_DIR / 'exp-result-csv'


# Root cause:
# These process-global AST caches were unbounded, so long runs with many
# distinct src_main_code contexts could keep growing memory usage.
# Fix rationale:
# Convert them to bounded LRU caches so hot entries are preserved for speed
# while old entries are evicted to prevent runaway RSS growth.
_CACHE_PIREL_ROOT_NODE: "OrderedDict[Tuple[str, str], pds.PirelNode]" = OrderedDict()
_CACHE_PIREL_NID_NODE_MAP: "OrderedDict[Tuple[str, str], Dict[int, pds.PirelNode]]" = OrderedDict()
_CACHE_PIREL_NID_NPATH_MAP: "OrderedDict[Tuple[str, str], Dict[int, List[int]]]" = OrderedDict()
_CACHE_PVPY_ROOT_NODE: "OrderedDict[str, pvis.AbstractNode]" = OrderedDict()
_CACHE_PVPY_NID_NODE_MAP: "OrderedDict[str, Dict[int, pvis.AbstractNode]]" = OrderedDict()

_CACHE_PIREL_ROOT_NODE_MAX = int(os.environ.get('PIREL_CACHE_PIREL_ROOT_NODE_MAX', '128'))
_CACHE_PIREL_NID_NODE_MAP_MAX = int(os.environ.get('PIREL_CACHE_PIREL_NID_NODE_MAP_MAX', '128'))
_CACHE_PIREL_NID_NPATH_MAP_MAX = int(os.environ.get('PIREL_CACHE_PIREL_NID_NPATH_MAP_MAX', '128'))
_CACHE_PVPY_ROOT_NODE_MAX = int(os.environ.get('PIREL_CACHE_PVPY_ROOT_NODE_MAX', '256'))
_CACHE_PVPY_NID_NODE_MAP_MAX = int(os.environ.get('PIREL_CACHE_PVPY_NID_NODE_MAP_MAX', '256'))


def _lru_get(cache: OrderedDict, key):
  cached = cache.get(key)
  if cached is None:
    return None
  cache.move_to_end(key)
  return cached


def _lru_put(cache: OrderedDict, key, value, max_size: int, cache_name: str) -> None:
  if key in cache:
    cache.pop(key, None)
  cache[key] = value
  if max_size <= 0:
    return
  evicted = 0
  while len(cache) > max_size:
    cache.popitem(last=False)
    evicted += 1
  if evicted > 0:
    logger.debug(
      f'Evicted {evicted} old entries from {cache_name} '
      f'(size={len(cache)}, max={max_size})'
    )


def _sanitize_checkpoint_subject_name(subject_name: str) -> str:
  return ''.join(ch if (ch.isalnum() or ch in ('-', '_')) else '_' for ch in subject_name)


def _save_ruleset_checkpoint(
  subject_name: str,
  statement_idx: int,
  ruleset: p_ruleset.Ruleset,
) -> None:
  subject_safe = _sanitize_checkpoint_subject_name(subject_name)
  timestamp = p_utils.current_time()
  subject_ruleset_dir = p_consts.RULESET_CHECKPOINTS_DIR / f'{subject_safe}_ruleset'
  ckpt_fname = (
    f'ruleset-checkpoint-{subject_safe}-stmt-{statement_idx}-at-{timestamp}.json'
  )
  ckpt_fpath = subject_ruleset_dir / ckpt_fname
  subject_ruleset_dir.mkdir(parents=True, exist_ok=True)
  p_utils.write_json(ckpt_fpath, ruleset.to_dict())
  logger.info(
    f'Saved ruleset checkpoint for subject="{subject_name}" '
    f'at statement {statement_idx}: {ckpt_fpath}'
  )


def _duration_ms(stms: Optional[int], etms: Optional[int]) -> int:
  if stms is None or etms is None:
    return 0
  try:
    return max(0, int(etms) - int(stms))
  except Exception:
    return 0


def _safe_positive_int(value: object) -> int:
  try:
    val = int(value)
  except Exception:
    return 0
  return val if val > 0 else 0


def _llm_query_ms_pair(llm_query_stat: ptlog.LLMQueryStat) -> Tuple[int, int]:
  '''
  Return (llm_query_ms, cached_extra_ms).
  cached_extra_ms is the portion missing from wall-clock due to cache hit.
  '''
  cached_query_ms = _safe_positive_int(getattr(llm_query_stat, 'cached_query_ms', 0))
  is_cache_hit = bool(getattr(llm_query_stat, 'is_cache_hit', False))
  runtime_query_ms = _duration_ms(
    getattr(llm_query_stat, 'stms', None),
    getattr(llm_query_stat, 'etms', None),
  )

  if cached_query_ms > 0:
    return cached_query_ms, cached_query_ms if is_cache_hit else 0
  if is_cache_hit:
    return runtime_query_ms, runtime_query_ms
  return runtime_query_ms, 0


def _llm_query_ms_from_pllm_gen_log(pllm_gen_log: Optional[ptlog.PLLMGenLog]) -> Tuple[int, int]:
  if pllm_gen_log is None:
    return 0, 0

  total_ms = 0
  cached_extra_ms = 0
  trans_sp1 = pllm_gen_log.trans_sp1
  if trans_sp1 is not None:
    for stat in trans_sp1.llm_query_stats:
      qms, cms = _llm_query_ms_pair(stat)
      total_ms += qms
      cached_extra_ms += cms

  for trans_sp2 in pllm_gen_log.trans_sp2s:
    for stat in trans_sp2.llm_query_stats:
      qms, cms = _llm_query_ms_pair(stat)
      total_ms += qms
      cached_extra_ms += cms

  return total_ms, cached_extra_ms


def _llm_query_ms_from_tsp(tsp: ptlog.TSP) -> Tuple[int, int]:
  total_ms = 0
  cached_extra_ms = 0
  for trule_learn_attempt in tsp.trule_learn_attempts:
    qms, cms = _llm_query_ms_from_pllm_gen_log(trule_learn_attempt.p_llm_gen_log)
    total_ms += qms
    cached_extra_ms += cms
  return total_ms, cached_extra_ms


def _llm_query_ms_from_rule_learn_elem(
  elem: Union[ptlog.RuleLearnStd, ptlog.RuleLearnRec, ptlog.RuleLearnSnp]
) -> Tuple[int, int]:
  if isinstance(elem, ptlog.RuleLearnRec):
    if elem.get_ref_trans is None:
      return 0, 0
    total_ms = 0
    cached_extra_ms = 0
    for stat in elem.get_ref_trans.llm_query_stats:
      qms, cms = _llm_query_ms_pair(stat)
      total_ms += qms
      cached_extra_ms += cms
    return total_ms, cached_extra_ms

  if isinstance(elem, ptlog.RuleLearnStd):
    total_ms = 0
    cached_extra_ms = 0
    for node_trans_iter in elem.node_trans_iters:
      for tsp in node_trans_iter.tsps:
        qms, cms = _llm_query_ms_from_tsp(tsp)
        total_ms += qms
        cached_extra_ms += cms
    return total_ms, cached_extra_ms

  if isinstance(elem, ptlog.RuleLearnSnp):
    total_ms = 0
    cached_extra_ms = 0
    for tsp in elem.tsps:
      qms, cms = _llm_query_ms_from_tsp(tsp)
      total_ms += qms
      cached_extra_ms += cms
    return total_ms, cached_extra_ms

  return 0, 0


def _collect_statement_metrics(lstat_node: ptlog.StatNode) -> Tuple[int, int, int, int, int, int]:
  '''
  Return (e2e_ms, learning_ms, translation_ms, validation_ms, llm_query_ms, llm_tokens_total).
  '''
  learning_runtime_ms = 0
  translation_ms = 0
  validation_ms = 0
  llm_query_ms = 0

  cached_validation_extra_ms = 0
  cached_translation_extra_ms = 0
  llm_cached_extra_ms = 0

  for elem in lstat_node.val_learn_iters:
    if isinstance(elem, ptlog.StatNodeVal):
      stat_val_runtime_ms = _duration_ms(elem.stms, elem.etms)
      translation_runtime_ms = _duration_ms(elem.v3_rule_apply_stms, elem.v3_rule_apply_etms)
      validation_runtime_ms = max(0, stat_val_runtime_ms - translation_runtime_ms)
      translation_ms += translation_runtime_ms
      validation_ms += validation_runtime_ms

      cached_expr_ms = _safe_positive_int(getattr(elem, 'cached_expr_validation_ms', 0))
      cached_translation_ms = _safe_positive_int(getattr(elem, 'cached_translation_ms', 0))
      if cached_expr_ms > 0 or cached_translation_ms > 0:
        if cached_expr_ms > 0:
          validation_ms += cached_expr_ms
          cached_validation_extra_ms += cached_expr_ms
        if cached_translation_ms > 0:
          translation_ms += cached_translation_ms
          cached_translation_extra_ms += cached_translation_ms
      else:
        # Backward compatibility for rows/logs created before bucket split.
        legacy_cached_val_ms = _safe_positive_int(getattr(elem, 'cached_validation_ms', 0))
        if legacy_cached_val_ms > 0:
          validation_ms += legacy_cached_val_ms
          cached_validation_extra_ms += legacy_cached_val_ms

    elif isinstance(elem, (ptlog.RuleLearnStd, ptlog.RuleLearnRec, ptlog.RuleLearnSnp)):
      learning_runtime_ms += _duration_ms(elem.stms, elem.etms)
      elem_llm_query_ms, elem_llm_cached_extra_ms = _llm_query_ms_from_rule_learn_elem(elem)
      llm_query_ms += elem_llm_query_ms
      llm_cached_extra_ms += elem_llm_cached_extra_ms

  learning_ms = learning_runtime_ms + llm_cached_extra_ms
  llm_tokens_total = int(lstat_node.get_num_input_tokens()) + int(lstat_node.get_num_output_tokens())
  e2e_ms = (
    _duration_ms(lstat_node.stms, lstat_node.etms)
    + cached_validation_extra_ms
    + cached_translation_extra_ms
    + llm_cached_extra_ms
  )
  return e2e_ms, learning_ms, translation_ms, validation_ms, llm_query_ms, llm_tokens_total


def _append_statement_result_csv(
  subject_name: str,
  statement_idx: int,
  statement_nid: int,
  e2e_ms: int,
  learning_ms: int,
  translation_ms: int,
  validation_ms: int,
  llm_query_ms: int,
  llm_tokens_total: int,
  status: str,
  error_type: str,
) -> None:
  _EXP_RESULT_CSV_DIR.mkdir(parents=True, exist_ok=True)
  csv_fpath = _EXP_RESULT_CSV_DIR / f'{subject_name}_result.csv'
  header = [
    'statement_idx',
    'statement_nid',
    'e2e_ms',
    'learning_ms',
    'translation_ms',
    'validation_ms',
    'llm_query_ms',
    'llm_tokens_total',
    'status',
    'error_type',
  ]
  new_row = {
    'statement_idx': str(statement_idx),
    'statement_nid': str(statement_nid),
    'e2e_ms': str(e2e_ms),
    'learning_ms': str(learning_ms),
    'translation_ms': str(translation_ms),
    'validation_ms': str(validation_ms),
    'llm_query_ms': str(llm_query_ms),
    'llm_tokens_total': str(llm_tokens_total),
    'status': status,
    'error_type': error_type,
  }

  rows: List[dict] = []
  replaced = False
  if csv_fpath.exists():
    with open(csv_fpath, 'r', newline='') as fin:
      reader = csv.DictReader(fin)
      if reader.fieldnames is not None and 'statement_nid' in reader.fieldnames:
        for row in reader:
          normalized_row = {k: row.get(k, '') for k in header}
          if normalized_row.get('statement_nid') == new_row['statement_nid']:
            rows.append(new_row)
            replaced = True
          else:
            rows.append(normalized_row)
      else:
        # Unexpected format: start a clean table with the latest row.
        rows = []

  if not replaced:
    rows.append(new_row)

  with open(csv_fpath, 'w', newline='') as fout:
    writer = csv.DictWriter(fout, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)


def _get_cached_pirel_root_node(src_main_code: str, lang: str) -> pds.PirelNode:
  key = (src_main_code, lang)
  cached = _lru_get(_CACHE_PIREL_ROOT_NODE, key)
  if cached is not None:
    return cached
  root_node = pds.PirelTree.from_code_str(src_main_code, lang).get_root_node()
  _lru_put(
    _CACHE_PIREL_ROOT_NODE,
    key,
    root_node,
    _CACHE_PIREL_ROOT_NODE_MAX,
    '_CACHE_PIREL_ROOT_NODE'
  )
  return root_node


def _get_cached_pirel_nid_node_map(src_main_code: str, lang: str) -> Dict[int, pds.PirelNode]:
  key = (src_main_code, lang)
  cached = _lru_get(_CACHE_PIREL_NID_NODE_MAP, key)
  if cached is not None:
    return cached
  root_node = _get_cached_pirel_root_node(src_main_code, lang)
  nid_node_map = {}
  stack = [root_node]
  while stack:
    node = stack.pop()
    if node.is_terminal():
      continue
    nid_node_map[node.get_id()] = node
    stack.extend(node.get_children())
  _lru_put(
    _CACHE_PIREL_NID_NODE_MAP,
    key,
    nid_node_map,
    _CACHE_PIREL_NID_NODE_MAP_MAX,
    '_CACHE_PIREL_NID_NODE_MAP'
  )
  return nid_node_map


def _get_cached_pirel_nid_npath_map(src_main_code: str, lang: str) -> Dict[int, List[int]]:
  key = (src_main_code, lang)
  cached = _lru_get(_CACHE_PIREL_NID_NPATH_MAP, key)
  if cached is not None:
    return cached
  root_node = _get_cached_pirel_root_node(src_main_code, lang)
  nid_npath_map: Dict[int, List[int]] = {}
  stack: List[Tuple[pds.PirelNode, List[int]]] = [(root_node, [])]
  while stack:
    node, npath = stack.pop()
    if node.is_terminal():
      continue
    nid_npath_map[node.get_id()] = npath
    children = node.get_children()
    for idx in range(len(children) - 1, -1, -1):
      child = children[idx]
      stack.append((child, npath + [idx]))
  _lru_put(
    _CACHE_PIREL_NID_NPATH_MAP,
    key,
    nid_npath_map,
    _CACHE_PIREL_NID_NPATH_MAP_MAX,
    '_CACHE_PIREL_NID_NPATH_MAP'
  )
  return nid_npath_map


def _get_cached_pvpy_root_node(src_main_code: str) -> pvis.AbstractNode:
  cached = _lru_get(_CACHE_PVPY_ROOT_NODE, src_main_code)
  if cached is not None:
    return cached
  root_node = pvpy.Tree.from_str(src_main_code).root_node
  _lru_put(
    _CACHE_PVPY_ROOT_NODE,
    src_main_code,
    root_node,
    _CACHE_PVPY_ROOT_NODE_MAX,
    '_CACHE_PVPY_ROOT_NODE'
  )
  return root_node


def _get_pvpy_root_copy(src_main_code: str) -> pvis.AbstractNode:
  return copy.deepcopy(_get_cached_pvpy_root_node(src_main_code))


def _get_cached_pvpy_nid_node_map(src_main_code: str) -> Dict[int, pvis.AbstractNode]:
  cached = _lru_get(_CACHE_PVPY_NID_NODE_MAP, src_main_code)
  if cached is not None:
    return cached
  nid_node_map = _get_cached_pvpy_root_node(src_main_code).get_nid_node_map()
  _lru_put(
    _CACHE_PVPY_NID_NODE_MAP,
    src_main_code,
    nid_node_map,
    _CACHE_PVPY_NID_NODE_MAP_MAX,
    '_CACHE_PVPY_NID_NODE_MAP'
  )
  return nid_node_map


def _get_direct_ref_translations_re_compile_assignment(
  simple_ntext: str,
  tar_lang: str
) -> List[str]:
  '''
  Build deterministic JS reference translations for a direct assignment:
  `<name> = re.compile(<pattern>)`.

  This avoids LLM drift on regex payload (e.g. dropping `\\s`) and
  avoids declaration-less assignment in strict-mode JS.
  '''
  if tar_lang != 'js':
    return []

  try:
    module = ast.parse(simple_ntext)
  except SyntaxError:
    return []
  if len(module.body) != 1:
    return []

  stmt = module.body[0]
  if not isinstance(stmt, ast.Assign):
    return []
  if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
    return []
  lhs_name = stmt.targets[0].id

  rhs = stmt.value
  if not isinstance(rhs, ast.Call):
    return []
  if rhs.keywords:
    return []
  if len(rhs.args) != 1:
    return []

  fn = rhs.func
  if not (isinstance(fn, ast.Attribute)
          and isinstance(fn.value, ast.Name)
          and fn.value.id == 're'
          and fn.attr == 'compile'):
    return []

  try:
    pattern = ast.literal_eval(rhs.args[0])
  except Exception:
    return []
  if not isinstance(pattern, str):
    return []

  # Use new RegExp(<json-string>) so slash/quote escaping is stable.
  rhs_js = f'new RegExp({json.dumps(pattern)})'
  return [f'var {lhs_name} = {rhs_js};']


def _extract_defer_candidate_call_only_statement(
  simple_ntext: str,
  src_lang: str,
  allowed_callee_names: Optional[Set[str]] = None,
) -> Optional[Tuple[str, List[str]]]:
  '''
  Return `(call_only_statement, callee_names)` when a statement
  immediately consumes a call's return value in the same statement.

  Examples:
  - `a, b = obj.f(x)` -> (`obj.f(x)`, ['f'])
  - `if is_ready(x):` -> (`is_ready(x)`, ['is_ready'])
  - `return parse(x)` -> (`parse(x)`, ['parse'])
  - `z = f(g(x))` -> (`pirel_tmp_var = g(x)\nf(pirel_tmp_var)`, ['g', 'f'])
  - `y = f(a) * g(b)` -> (`f(a)\ng(b)`, ['f', 'g'])

  Return `None` if not applicable.

  If `allowed_callee_names` is provided, only calls to those callee names
  are considered defer candidates (for example, local function calls only).
  '''
  if src_lang != 'py':
    return None

  try:
    module = ast.parse(simple_ntext)
  except SyntaxError:
    return None
  if len(module.body) != 1:
    return None

  stmt = module.body[0]
  parent_map: Dict[ast.AST, ast.AST] = {}
  for node in ast.walk(stmt):
    for child in ast.iter_child_nodes(node):
      parent_map[child] = node

  def _is_value_consumed_in_same_statement(call_node: ast.Call) -> bool:
    nonlocal parent_map, stmt
    parent = parent_map.get(call_node)
    if parent is None:
      return False
    # Pure call statement (`foo()`) does not consume the return value.
    if isinstance(parent, ast.Expr) and parent.value is call_node and parent is stmt:
      return False
    return True

  def _get_callee_name(call_node: ast.Call) -> Optional[str]:
    fn_node = call_node.func
    if isinstance(fn_node, ast.Name):
      return fn_node.id
    if isinstance(fn_node, ast.Attribute):
      return fn_node.attr
    return None

  def _ast_depth(node: ast.AST) -> int:
    nonlocal parent_map
    depth = 0
    cursor = parent_map.get(node)
    while cursor is not None:
      depth += 1
      cursor = parent_map.get(cursor)
    return depth

  consumed_calls: List[ast.Call] = [
    node for node in ast.walk(stmt)
    if isinstance(node, ast.Call) and _is_value_consumed_in_same_statement(node)
  ]
  if allowed_callee_names is not None:
    consumed_calls = [
      node for node in consumed_calls
      if (_get_callee_name(node) in allowed_callee_names)
    ]
  if not consumed_calls:
    return None

  consumed_call_set = set(consumed_calls)
  outermost_consumed_calls: List[ast.Call] = []
  for call_node in consumed_calls:
    cursor = parent_map.get(call_node)
    has_consumed_ancestor = False
    while cursor is not None:
      if cursor in consumed_call_set:
        has_consumed_ancestor = True
        break
      cursor = parent_map.get(cursor)
    if not has_consumed_ancestor:
      outermost_consumed_calls.append(call_node)

  if not outermost_consumed_calls:
    return None

  def _call_pos_key(call_node: ast.Call) -> Tuple[int, int]:
    return (
      getattr(call_node, 'lineno', 10**9),
      getattr(call_node, 'col_offset', 10**9),
    )

  def _node_span(node: ast.AST) -> Tuple[int, int, int, int]:
    return (
      getattr(node, 'lineno', -1),
      getattr(node, 'col_offset', -1),
      getattr(node, 'end_lineno', -1),
      getattr(node, 'end_col_offset', -1),
    )

  consumed_call_spans: Set[Tuple[int, int, int, int]] = {
    _node_span(node) for node in consumed_calls
  }
  tmp_var_counter = 0

  def _next_tmp_var_name() -> str:
    nonlocal tmp_var_counter
    tmp_var_counter += 1
    if tmp_var_counter == 1:
      return 'pirel_tmp_var'
    return f'pirel_tmp_var_{tmp_var_counter}'

  def _linearize_outer_call(call_node: ast.Call) -> Optional[List[str]]:
    root_span = _node_span(call_node)
    linearized_lines: List[str] = []

    class _NestedConsumedCallRewriter(ast.NodeTransformer):
      def visit_Call(self, node: ast.Call) -> ast.AST:  # type: ignore[override]
        node = self.generic_visit(node)
        span = _node_span(node)
        if span in consumed_call_spans and span != root_span:
          tmp_var_name = _next_tmp_var_name()
          rhs_expr = ast.unparse(ast.fix_missing_locations(copy.deepcopy(node))).strip()
          linearized_lines.append(f'{tmp_var_name} = {rhs_expr}')
          return ast.copy_location(ast.Name(id=tmp_var_name, ctx=ast.Load()), node)
        return node

    try:
      rewritten_root = _NestedConsumedCallRewriter().visit(copy.deepcopy(call_node))
      rewritten_root = ast.fix_missing_locations(rewritten_root)
      root_line = ast.unparse(rewritten_root).strip()
    except Exception:
      return None
    if root_line == '':
      return None
    return linearized_lines + [root_line]

  call_only_lines: List[str] = []
  for call_node in sorted(outermost_consumed_calls, key=_call_pos_key):
    linearized_lines = _linearize_outer_call(call_node)
    if linearized_lines is None:
      return None
    for call_line in linearized_lines:
      if call_line == '':
        continue
      if len(call_only_lines) == 0 or call_only_lines[-1] != call_line:
        call_only_lines.append(call_line)

  if len(call_only_lines) == 0:
    return None
  call_only_stmt = '\n'.join(call_only_lines)
  if call_only_stmt == simple_ntext.strip():
    return None

  callee_names: List[str] = []
  seen_callee_names: Set[str] = set()
  for call_node in sorted(
    consumed_calls,
    key=lambda node: (
      -_ast_depth(node),  # inner call first (e.g. g before f in f(g(x)))
      getattr(node, 'lineno', 10**9),
      getattr(node, 'col_offset', 10**9),
    )
  ):
    callee_name = _get_callee_name(call_node)
    if callee_name is None or callee_name in seen_callee_names:
      continue
    seen_callee_names.add(callee_name)
    callee_names.append(callee_name)

  return call_only_stmt, callee_names


def _get_enclosing_function_name(
  node: pvis.AbstractNode
) -> Optional[str]:
  cursor = node
  while cursor is not None:
    if isinstance(cursor, pvpy.FunctionDefinitionNode):
      assert isinstance(cursor.name, pvpy.IdentifierNode), \
        'function name must be an IdentifierNode'
      return cursor.name.val()
    cursor = cursor.get_parent()
  return None


def _build_local_function_call_graph(
  src_main_code: str,
) -> Tuple[Set[str], Dict[str, Set[str]]]:
  '''
  Build a local call graph among function definitions in `src_main_code`.
  Edges are `caller_fn_name -> callee_fn_name`.
  '''
  root_node = _get_cached_pvpy_root_node(src_main_code)
  defined_fn_names: Set[str] = set()

  def _collect_fn_defs(node: pvis.AbstractNode) -> None:
    nonlocal defined_fn_names
    if isinstance(node, pvpy.FunctionDefinitionNode):
      assert isinstance(node.name, pvpy.IdentifierNode), \
        'function name must be an IdentifierNode'
      defined_fn_names.add(node.name.val())
    for child in node.get_nt_children():
      _collect_fn_defs(child)

  _collect_fn_defs(root_node)
  call_graph: Dict[str, Set[str]] = {fn_name: set() for fn_name in defined_fn_names}

  def _get_callee_name_from_call(call_node: pvpy.CallNode) -> Optional[str]:
    fn_node = call_node.function
    if isinstance(fn_node, pvpy.IdentifierNode):
      return fn_node.val()
    if isinstance(fn_node, pvpy.AttributeNode):
      if isinstance(fn_node.attribute, pvpy.IdentifierNode):
        return fn_node.attribute.val()
    return None

  def _collect_calls(node: pvis.AbstractNode, current_fn_name: Optional[str]) -> None:
    next_fn_name = current_fn_name
    if isinstance(node, pvpy.FunctionDefinitionNode):
      assert isinstance(node.name, pvpy.IdentifierNode), \
        'function name must be an IdentifierNode'
      next_fn_name = node.name.val()

    if isinstance(node, pvpy.CallNode):
      callee_name = _get_callee_name_from_call(node)
      if (
        next_fn_name is not None
        and callee_name is not None
        and callee_name in defined_fn_names
      ):
        call_graph[next_fn_name].add(callee_name)

    for child in node.get_nt_children():
      _collect_calls(child, next_fn_name)

  _collect_calls(root_node, None)
  return defined_fn_names, call_graph


def _compute_transitive_callee_closure(
  seed_fn_names: Set[str],
  call_graph: Dict[str, Set[str]],
) -> Set[str]:
  closure: Set[str] = set()
  queue: List[str] = list(seed_fn_names)
  while queue:
    fn_name = queue.pop(0)
    if fn_name in closure:
      continue
    closure.add(fn_name)
    for callee_name in call_graph.get(fn_name, set()):
      if callee_name not in closure:
        queue.append(callee_name)
  return closure


def _map_statement_nids_to_enclosing_fn_names(
  src_main_code: str,
  statement_nids: List[int],
) -> Dict[int, Optional[str]]:
  nid_node_map = _get_cached_pvpy_nid_node_map(src_main_code)
  nid_to_fn_name: Dict[int, Optional[str]] = {}
  for stat_nid in statement_nids:
    stat_node = nid_node_map.get(stat_nid)
    if stat_node is None:
      continue
    nid_to_fn_name[stat_nid] = _get_enclosing_function_name(stat_node)
  return nid_to_fn_name


def _compute_deferred_boundary_idx(
  start_idx: int,
  stat_nodes: List[pds.PirelNode],
  nid_to_fn_name: Dict[int, Optional[str]],
  callee_closure: Set[str],
) -> int:
  '''
  Compute boundary index for deferred statement finalization.
  Boundary is the last contiguous statement-index that still belongs to
  the callee closure in execution order.
  '''
  boundary_idx = start_idx
  if not callee_closure:
    return boundary_idx

  for idx in range(start_idx + 1, len(stat_nodes) + 1):
    stat_nid = stat_nodes[idx - 1].get_id()
    fn_name = nid_to_fn_name.get(stat_nid)
    if fn_name in callee_closure:
      boundary_idx = idx
      continue
    break

  return boundary_idx


def _get_pre_context_global(
  src_main_code: str,
  stat_npath: List[int]
) -> str:
  '''
  A pre-context is part of the code that appears before the context node
  of the problematic node inside a function body.

  The goal of this function is to extract pre-context for the snippet
  that is used to validate the translation rule. The idea of extraction
  algorithm is to find the enclosing `function_definition`s `block` node,
  and remove all nodes that appear after the context node. What is left
  is the pre-context that we need. After that, we replace the context
  node with a special identifier, that is later string-replaced by the
  actual snippet.
  '''
  def _process_elif_clauses(else_clause_node: pvpy.ElifClauseNode) -> None:
    '''
    Replace all children of `elif` clause's body with a pass statement.
    '''
    pass_statement_node = pvpy.PassStatementNode.build()
    else_clause_node.consequence.children = [pass_statement_node]
    pass_statement_node.set_parent(else_clause_node.consequence)

  def _process_else_clauses(else_clause_node: pvpy.ElseClauseNode) -> None:
    '''
    Replace all children of `else` clause's body with a pass statement.
    '''
    pass_statement_node = pvpy.PassStatementNode.build()
    else_clause_node.body.children = [pass_statement_node]
    pass_statement_node.set_parent(else_clause_node.body)

  def _process_except_clause(except_clause_node: pvpy.ExceptClauseNode) -> None:
    '''
    Replace all children of `except` clause's body with a pass statement.
    '''
    pass_statement_node = pvpy.PassStatementNode.build()
    except_clause_body = except_clause_node.get_nt_children()[-1]
    except_clause_body.children = [pass_statement_node]
    pass_statement_node.set_parent(except_clause_body)

  root_node = _get_pvpy_root_copy(src_main_code)
  statement_node = root_node.get_child_by_path(stat_npath)

  # 1. find the enclosing function_definition node's block
  cursor_node = statement_node
  while cursor_node.get_parent() is not None:

    # remove siblings to the right of cursor_node as we are moving up
    next_sibling = cursor_node.next_sibling()

    while next_sibling is not None:
      # need to get the pointer to the next_sibling++
      # before removing next_sibling itself
      next_next_sibling = next_sibling.next_sibling()

      # keep elif and else clauses because they are part of the translation rule
      # they are part of the translation rule due to the fact that
      # they are not simplified. Refer to p_grammar.simplify_template() for more information.
      if isinstance(next_sibling, pvpy.ElifClauseNode):
        _process_elif_clauses(next_sibling)
        next_sibling = next_next_sibling
        continue
      if isinstance(next_sibling, pvpy.ElseClauseNode):
        _process_else_clauses(next_sibling)
        next_sibling = next_next_sibling
        continue
      if isinstance(next_sibling, pvpy.ExceptClauseNode):
        _process_except_clause(next_sibling)
        next_sibling = next_next_sibling
        continue

      next_sibling.get_parent().get_children().remove(next_sibling)
      next_sibling.parent = None
      next_sibling = next_next_sibling

    # move up the tree
    cursor_node = cursor_node.get_parent()
    if isinstance(cursor_node, pvpy.BlockNode):
      if isinstance(cursor_node.get_parent(), pvpy.FunctionDefinitionNode):
        break

  # 2. replace the context node with a special identifier
  spec_id_stat = pvpy.ExpressionStatementNode.build(
    pvpy.IdentifierNode.build(p_consts.PRE_CTX_SPEC_IDENT))
  spec_id_stat.set_parent(statement_node.get_parent())
  context_node_idx_as_child = statement_node.parent.children.index(statement_node)
  statement_node.parent.children[context_node_idx_as_child] = spec_id_stat

  # 3. pretty print the block
  pp = pvpy.PrettyPrinter(indent_with='    ')
  pp.visit(cursor_node)
  pre_context = '\n'.join(pp.lines)
  return pre_context


def _get_pre_context_eot(
  src_program: str,
  stat_npath: list[int],
  npath_blacklist: list[list[int]],
  npath_text_overrides: Optional[Dict[Tuple[int, ...], str]] = None,
) -> str:
  '''Return the context of the statement to be translated.

  Nodes blacklisted are to be translated after this statement
  in execution-order translation, so that only the pre-context is left.
  '''
  root_node = _get_pvpy_root_copy(src_program)
  statement_node = root_node.get_child_by_path(stat_npath)
  assert statement_node is not None

  stat_npath_tuple = tuple(stat_npath)
  blacklist_tuples: Set[Tuple[int, ...]] = set()
  for npath in npath_blacklist:
    npath_tuple = tuple(npath)
    if npath_tuple[:len(stat_npath_tuple)] == stat_npath_tuple:
      continue  # keep descendants of the statement to be translated
    blacklist_tuples.add(npath_tuple)

  # Prune blacklisted nodes in one traversal, instead of repeated path lookup/removal.
  def _prune_blacklisted(
    node: pvis.AbstractNode,
    npath_prefix: Tuple[int, ...],
  ) -> None:
    children_snapshot = list(node.children)
    kept_children = []
    for idx, child in enumerate(children_snapshot):
      child_path = npath_prefix + (idx,)
      if child_path in blacklist_tuples:
        if isinstance(child, pvpy.ElseClauseNode):
          child.body.children = []
        elif isinstance(child, pvpy.ElifClauseNode):
          child.consequence.children = []
        else:
          child.parent = None
          continue
      _prune_blacklisted(child, child_path)
      kept_children.append(child)
    if kept_children != children_snapshot:
      node.children = kept_children

  _prune_blacklisted(root_node, ())

  if npath_text_overrides:
    for override_npath, override_text in sorted(
      npath_text_overrides.items(),
      key=lambda item: (len(item[0]), item[0]),
      reverse=True,
    ):
      if override_npath == stat_npath_tuple:
        continue
      if override_npath in blacklist_tuples:
        continue

      try:
        target_node = root_node.get_child_by_path(list(override_npath))
      except Exception:
        continue
      if target_node is None:
        continue
      target_parent = target_node.get_parent()
      if target_parent is None:
        continue

      try:
        repl_root_nt_children = pvpy.Tree.from_str(override_text).root_node.get_nt_children()
      except Exception:
        logger.debug(
          f'Skipping pre-context override due to parse error '
          f'(npath={override_npath}):\n{override_text}')
        continue
      if len(repl_root_nt_children) != 1:
        logger.debug(
          f'Skipping pre-context override that is not a single statement '
          f'(npath={override_npath}, num_stmts={len(repl_root_nt_children)}):\n'
          f'{override_text}')
        continue

      repl_stat_node = repl_root_nt_children[0]
      try:
        idx_in_parent = target_parent.children.index(target_node)
      except ValueError:
        continue
      repl_stat_node.set_parent(target_parent)
      target_parent.children[idx_in_parent] = repl_stat_node

  stack = [root_node]
  while stack:
    node = stack.pop()
    if isinstance(node, pvpy.BlockNode) and not node.children:
      pass_statement_node = pvpy.PassStatementNode.build()
      node.children = [pass_statement_node]
      pass_statement_node.set_parent(node)
    stack.extend(node.children)

  spec_id_stat = pvpy.ExpressionStatementNode.build(
    pvpy.IdentifierNode.build(p_consts.PRE_CTX_SPEC_IDENT))
  spec_id_stat.set_parent(statement_node.get_parent())
  context_node_idx_as_child = statement_node.parent.children.index(statement_node)
  statement_node.parent.children[context_node_idx_as_child] = spec_id_stat
  return pvpy.PrettyPrinter(indent_with='    ').visit(root_node)


def get_pre_context(
  src_main_code: str,
  lang: str,
  is_three_split: bool,
  stat_nid: int,
  nid_blacklist: list[int],
  nid_text_overrides: Optional[Dict[int, str]] = None,
) -> str:
  '''
  Get pre-context for the statement node.
  The pre-context is the code that appears before the statement node
  in the source code up to the closest enclosing function definition.
  '''
  # p_utils.log_json_time(f'args-get_pre_context.json', locals())
  nid_npath_map = _get_cached_pirel_nid_npath_map(src_main_code, lang)
  if stat_nid not in nid_npath_map:
    raise ValueError(f'statement node id {stat_nid} not found in source AST')
  stat_npath = nid_npath_map[stat_nid]
  if is_three_split:
    return _get_pre_context_global(src_main_code, stat_npath)
  else:
    blacklist = sorted(
      [nid_npath_map[nid] for nid in nid_blacklist if nid in nid_npath_map],
      reverse=True
    )
    npath_text_overrides: Dict[Tuple[int, ...], str] = {}
    if nid_text_overrides:
      for nid, replacement_text in nid_text_overrides.items():
        npath = nid_npath_map.get(nid)
        if npath is None:
          continue
        npath_text_overrides[tuple(npath)] = replacement_text
    return _get_pre_context_eot(
      src_main_code,
      stat_npath,
      blacklist,
      npath_text_overrides or None,
    )


def _can_be_context_node(
  node: pds.PirelNode,
  lang: str
) -> bool:
  '''
  A node is a context node if AST of its text,
  when parsed on its own, is isomorphic to itself.
  Refer to p_templates._validate_template() for more information.
  TODO can be optimized by hard-coding the actual context node types
  '''
  # must be non-terminal
  if node.is_terminal():
    return False
  # node text must not have errors when parsed as it is
  if p_utils.does_have_parse_error(node.get_text(), lang):
    return False
  # parse the node text as a program on its own
  ast_text, ast_ann = d_ast_parse.parse_text_dbg(node.get_text(), lang, keep_text=True)
  tree = pds.PirelTree(ast_text, ast_ann)
  # there should be exactly one context node
  if len(tree.get_root_node().get_children()) != 1:
    return False
  context_node = tree.get_root_node().get_children()[0]
  # context node must be isomorphic to the original node
  if not node.is_type_isomorphic_to(context_node):
    return False
  return True


def _check_needs_rec_rule_learning_directly(
  templates_dict: dict
) -> bool:
  '''
  Check template_origin to see if we need to bypass standard rule learning
  and go directly to recovery rule learning.
  '''

  def __pattern_1_type_fn_three_args(template_origin: str) -> bool:
    '''
    Assignment statements of the form:
    Clz = type(class_name, (super_class,), {...})
    '''
    ts_query_str = '(module (expression_statement (assignment left: (identifier) right: (call function: (identifier) @name arguments: (argument_list "(" (_) "," (_) "," (_) ")" ) ) ) ) )'
    tree = p_consts._py_parser.parse(bytes(template_origin, 'utf8'))
    ts_query = p_consts._py_language.query(ts_query_str)
    captures = ts_query.captures(tree.root_node)
    if len(captures) != 1:
      return False
    capture, _ = captures[0]
    fn_name = template_origin[capture.start_byte:capture.end_byte]
    if fn_name != 'type':
      return False
    logger.debug('Matched direct recovery learning pattern: type() with three arguments')
    return True

  def __pattern_2_assignment_re_compile(template_origin: str) -> bool:
    '''
    Assignment statements of the form:
    <var> = re.compile(<regex>)
    '''
    ts_query_str = '(assignment left: (identifier) right: (call function: (attribute) @attr ) )'
    tree = p_consts._py_parser.parse(bytes(template_origin, 'utf8'))
    ts_query = p_consts._py_language.query(ts_query_str)
    captures = ts_query.captures(tree.root_node)
    if len(captures) != 1:
      return False
    capture, _ = captures[0]
    fn_name = template_origin[capture.start_byte:capture.end_byte]
    if fn_name != 're.compile':
      return False
    logger.debug('Matched direct recovery learning pattern: re.compile()')
    return True

  # in cases when templates_dict is loaded from str, keys are strings
  _valid_template_idx = p_utils.to_int(templates_dict['num_templates']) - 1
  template_dict = templates_dict.get(_valid_template_idx) or templates_dict.get(str(_valid_template_idx))

  patterns = [
    __pattern_1_type_fn_three_args,
    __pattern_2_assignment_re_compile,
  ]
  for pattern in patterns:
    if pattern(template_dict['template_origin']):
      logger.debug('Bypassing standard rule learning: matched a direct recovery learning pattern')
      return True
  return False


def _visitor_nodes_with_pirel_id_instrumentation(
  visitor_nodes: list[pvis.AbstractNode],
  pirel_nodes: list[pds.PirelNode],
  lang: str,
) -> Iterator[pvis.AbstractNode]:
  assert len(visitor_nodes) == len(pirel_nodes), breakpoint()
  for visitor_node, pirel_node in zip(visitor_nodes, pirel_nodes):
    pirel_parent = pirel_node.get_parent()
    parent_type = pirel_parent.get_ts_node_type() if pirel_parent is not None else None
    is_statement_level_node = parent_type in ('module', 'block')
    if (is_statement_level_node
        and _can_be_context_node(pirel_node, lang)
        and pirel_node.get_ts_node_type() != 'function_definition'):
      print_stmt = f"print('PiREL', {pirel_node.get_id()}, _pirel_stack_str(), flush=True)"
      print_node, = pvpy.Tree.from_str(print_stmt).root_node.children
      yield print_node
    yield visitor_node


def _parse_eot_trace_line(
  line: str,
) -> Optional[Tuple[int, Tuple[str, ...]]]:
  if not line.startswith('PiREL '):
    return None

  parts = line.split(' ', 2)
  if len(parts) < 2:
    return None

  node_id = int(parts[1])
  if len(parts) < 3:
    return node_id, tuple()

  stack_raw = parts[2].strip()
  if stack_raw == '' or stack_raw == '__MODULE__':
    return node_id, tuple()

  stack = tuple(fn_name for fn_name in stack_raw.split('|') if fn_name != '')
  return node_id, stack


def _instrument_visitor_node_with_pirel_node_id(
  visitor_node: pvis.AbstractNode,
  pirel_node: pds.PirelNode,
  lang: str,
  gt_translations: dict,
) -> None:
  '''
  Instrument visitor node with pirel node id by adding a print statement.
  '''
  if isinstance(visitor_node, pvpy.StringNode):
    return  # FIXME: handle f-strings (short circuit here can be kept though)

  visitor_children = visitor_node.children
  pirel_children = pirel_node.get_children()

  assert len(visitor_children) == len(pirel_children), 'expected the same number of children'
  for visitor_child, pirel_child in zip(visitor_children, pirel_children):
    if isinstance(visitor_child, pvis.TerminalNode):
      assert visitor_child.get_type() == pirel_child.get_type(), 'expected terminal node texts to be the same'
      assert pirel_child.is_terminal(), 'expected pirel child to be terminal'
    else:
      assert visitor_child.get_type() == pirel_child.get_ts_node_type(), 'expected corresponding node types to be same'

  if isinstance(visitor_node, pvpy.FunctionDefinitionNode):
    assert isinstance(visitor_node.name, pvpy.IdentifierNode), 'expected function name to be an identifier node'
    fn_name = visitor_node.name.val()
    if fn_name in gt_translations:
      # find block node of the function definition
      visitor_block_node, pirel_block_node = None, None
      for visitor_child, pirel_child in zip(visitor_children, pirel_children):
        if isinstance(visitor_child, pvpy.BlockNode):
          visitor_block_node = visitor_child
          pirel_block_node = pirel_child
          break

      assert visitor_block_node is not None and pirel_block_node is not None, 'expected to find block node in function definition'
      assert visitor_block_node.get_type() == pirel_block_node.get_ts_node_type() == 'block', 'expected block node types to be block'
      for visitor_child, pirel_child in zip(visitor_block_node.children, pirel_block_node.get_children()):
        # children of block node are nonterminals by grammar
        assert visitor_child.get_type() == pirel_child.get_ts_node_type(), 'expected corresponding node types to be same'

      # collect function definition node inside block node
      # skip non-function-definition statements inside the function body
      visitor_block_fn_defs = [visitor_child for visitor_child in visitor_block_node.children if isinstance(visitor_child, pvpy.FunctionDefinitionNode)]
      pirel_block_fn_defs = [pirel_child for pirel_child in pirel_block_node.get_children() if pirel_child.get_ts_node_type() == 'function_definition']
      for visitor_child, pirel_child in zip(visitor_block_fn_defs, pirel_block_fn_defs):
        _instrument_visitor_node_with_pirel_node_id(visitor_child, pirel_child, lang, gt_translations)
      return

  children = list(_visitor_nodes_with_pirel_id_instrumentation(visitor_children, pirel_children, lang))
  for visitor_child, pirel_child in zip(visitor_children, pirel_children):
    _instrument_visitor_node_with_pirel_node_id(visitor_child, pirel_child, lang, gt_translations)
  visitor_node.children = children


async def get_statement_nodes_eot(
  src_program: str,
  lang: str,
  subject_name: Optional[str],
  return_node_ids: bool = False,
  deduplicate: bool = True,
) -> list[pds.PirelNode|int]:
  '''
  Return a list of statement nodes for execution-order translation.

  If node identifiers are requested, skip finding the PiREL nodes
  from their ID, which is costly.

  PARAM deduplicate:
  - True: return each statement node id once (first visit order)
  - False: keep full execution trace order including repeated visits
  '''
  cache_key = _make_eot_stat_node_ids_cache_key(
    src_program, lang, subject_name, deduplicate)
  cached_node_ids = _get_cached_eot_stat_node_ids(cache_key)
  if cached_node_ids is not None:
    logger.debug(
      'Reusing cached EoT statement node IDs '
      f'(count={len(cached_node_ids)}, deduplicate={deduplicate}, '
      f'lang={lang}, subject={subject_name!r}).'
    )
    if return_node_ids:
      return cached_node_ids
    pirel_root_node = pds.PirelTree.from_code_str(src_program, lang).get_root_node()
    return [pirel_root_node.get_node_by_id(node_id) for node_id in cached_node_ids]

  workdir = fspath(p_consts.BENCHMARK_CONFIGS['skel']['benchmark_dir'])  # FIXME
  pirel_root_node = pds.PirelTree.from_code_str(src_program,
                                                lang).get_root_node()
  visitor_root_node = pvpy.Tree.from_str(src_program).root_node
  if subject_name is None:
    gt_translations = {}
  else:
    subject_config = p_utils.read_json(p_consts.SKEL_BENCHMARK_DIR / f'{subject_name}-config.json')
    gt_translations = subject_config['ground_truth_translations']
  _instrument_visitor_node_with_pirel_node_id(visitor_root_node,
                                              pirel_root_node, lang,
                                              gt_translations)
  module = pvpy.PrettyPrinter(indent_with='    ').visit(visitor_root_node)
  module = _EOT_MODULE_TEMPLATE.format(workdir, module)

  logger.debug('Prepared instrumented module for EoT statement node extraction.')
  p_utils.log_file_time('src_instrumented_eot.py', module)

  # OPTION 1: run with "-c" option
  # NOTE no timeout here, can run indefinitely
  # proc = await asyncio.create_subprocess_exec(
  #   executable, '-c', module,
  #   stdout=asyncio.subprocess.PIPE,
  #   stderr=asyncio.subprocess.PIPE
  # )
  # stdout = (await proc._read_stream(1)).decode()
  # stderr = (await proc._read_stream(2)).decode()
  # await proc.wait()
  # assert proc.returncode == 0, f'Error executing instrumented module:\n{stderr}'

  # OPTION 2: run using p_code_runner._run_code()
  stdout, stderr = await p_code_runner._run_code(module, 'py', timeout_sec=1000)
  assert stderr == '', f'Error executing instrumented module:\n{stderr}'

  node_ids: List[int] = []
  visited: Set[int] = set()
  for line in stdout.splitlines():
    parsed = _parse_eot_trace_line(line)
    if parsed is None:
      continue
    node_id, _ = parsed
    if deduplicate:
      if node_id in visited:
        continue
      visited.add(node_id)
    node_ids.append(node_id)
  _set_cached_eot_stat_node_ids(cache_key, node_ids)
  if return_node_ids:
    return node_ids
  return [pirel_root_node.get_node_by_id(node_id) for node_id in node_ids]


async def get_statement_exec_events_eot(
  src_program: str,
  lang: str,
  subject_name: Optional[str],
  deduplicate: bool = False,
) -> List[Tuple[int, Tuple[str, ...]]]:
  '''
  Return execution-order statement events as `(statement_nid, call_stack_tuple)`.

  `call_stack_tuple` is the dynamic function stack (outermost -> innermost)
  at the point the statement executed.
  '''
  workdir = fspath(p_consts.BENCHMARK_CONFIGS['skel']['benchmark_dir'])  # FIXME
  pirel_root_node = pds.PirelTree.from_code_str(src_program, lang).get_root_node()
  visitor_root_node = pvpy.Tree.from_str(src_program).root_node
  if subject_name is None:
    gt_translations = {}
  else:
    subject_config = p_utils.read_json(p_consts.SKEL_BENCHMARK_DIR / f'{subject_name}-config.json')
    gt_translations = subject_config['ground_truth_translations']
  _instrument_visitor_node_with_pirel_node_id(
    visitor_root_node,
    pirel_root_node,
    lang,
    gt_translations,
  )
  module = pvpy.PrettyPrinter(indent_with='    ').visit(visitor_root_node)
  module = _EOT_MODULE_TEMPLATE.format(workdir, module)

  logger.debug('Prepared instrumented module for EoT statement exec-event extraction.')
  p_utils.log_file_time('src_instrumented_eot.py', module)

  # OPTION 1: run with "-c" option
  # NOTE no timeout here, can run indefinitely
  # proc = await asyncio.create_subprocess_exec(
  #   executable, '-c', module,
  #   stdout=asyncio.subprocess.PIPE,
  #   stderr=asyncio.subprocess.PIPE
  # )
  # stdout = (await proc._read_stream(1)).decode()
  # stderr = (await proc._read_stream(2)).decode()
  # await proc.wait()
  # assert proc.returncode == 0, f'Error executing instrumented module:\n{stderr}'

  # OPTION 2: run using p_code_runner._run_code()
  stdout, stderr = await p_code_runner._run_code(module, 'py', timeout_sec=1000)
  assert stderr == '', f'Error executing instrumented module:\n{stderr}'

  events: List[Tuple[int, Tuple[str, ...]]] = []
  visited: Set[int] = set()
  for line in stdout.splitlines():
    parsed = _parse_eot_trace_line(line)
    if parsed is None:
      continue
    node_id, stack = parsed
    if deduplicate:
      if node_id in visited:
        continue
      visited.add(node_id)
    events.append((node_id, stack))
  return events


async def _get_statement_nodes(
  src_main_code: str,
  lang: str,
  is_three_split: bool,
  subject_name: Optional[str],
  return_node_ids: bool = False,
) -> List[Union[pds.PirelNode, int]]:
  '''
  Statement nodes are primary units of code in the source code.
  In other words, a source code is a sequence of statement nodes.
  '''
  if not is_three_split:
    return await get_statement_nodes_eot(src_main_code, lang, subject_name, return_node_ids)

  def __rec_pre_order(node: pds.PirelNode, lang: str) -> None:
    nonlocal nodes
    if _can_be_context_node(node, lang):
      nodes.append(node)
    for child in node.get_children():
      __rec_pre_order(child, lang)

  tree = pds.PirelTree.from_code_str(src_main_code, lang)
  nodes : List[pds.PirelNode] = []
  __rec_pre_order(tree.get_root_node(), lang)

  # hacky: remove function definitions as we have rules to translate their headers
  nodes = [n.get_id() if return_node_ids else n
           for n in nodes if n.get_ts_node_type() != 'function_definition']
  return nodes


def _init_tsps(
  template_dict: dict
) -> List[Tuple[str, str]]:
  '''
  Generate TSPs using a new algorithm.
  '''
  tsps = p_generator.generate_tsps_with_generator(template_dict)
  if len(tsps) == 0:
    raise NoTSPsGeneratedError('Could not generate any TSPs')
  p_utils.log_json_time(f'TSPs-generated.json', tsps)
  return tsps


def _get_partial_program(
  subject: p_subject.PirelSubject,
  current_ruleset_str: str,
  template_dict: dict
) -> str:
  '''
  A partial program (TODO is it a good name?) is a partially translated
  program in target language. Partial programs are used in LLM prompts
  to show the context of the code to be translated in the target program.

  IDEA
  Since translation is done in pre-order traversal, the sequence of nodes
  to be translated is:
  1. Nodes for which we have a translation rule
  2. Problematic node, for which we are attempting to learn a translation rule
  3. Nodes that are not translated yet.
  The algorithm is:
  a. Create a hacky rule for problematic node, that translates it into an
     identifier with a special name. This identifier will be the location
     of the translation. Everything around it will be the context.
  b. For each node in (3) create a hacky rule as in (a) with a different
     identifier with a special name, then just remove it from the code later.
     This way we get a partially translated program.
  '''

  def _append_hacky_rules(
    current_ruleset_str: str,
    problematic_node_type: str,
    secret_identifier: str
  ) -> str:
    '''
    Update `trans_rules` by appending all possible hacky rules
    to get a partial program.

    TODO HACKY this function is language dependent
    '''

    # contains possible ways to translate a node in the source language
    # into a node in the target language.
    HACKY_EXPANSIONS_PY_JS = {
      'pair': [
        # replacement for `pair` in `object`
        f'("js.shorthand_property_identifier" (val "{secret_identifier}"))',
      ],
      'default': [
        # convert a node into an identifier directly
        f'("js.identifier" (val "{secret_identifier}"))',

        # convert a node into an identifier under expression statement node
        f'("js.expression_statement" ("js.identifier" (val "{secret_identifier}")))',

        # ignore a node (do not translate)
        f''
      ]
    }

    matcher = f'"py.{problematic_node_type}" "*"'
    for hacky_expansion in HACKY_EXPANSIONS_PY_JS.get(problematic_node_type, HACKY_EXPANSIONS_PY_JS['default']):
      hacky_rule = f'(match_expand (fragment ({matcher}) "*") (fragment {hacky_expansion} "*2"))'
      current_ruleset_str = current_ruleset_str + f'\n\n{hacky_rule}'
    return current_ruleset_str

  def _post_process_partial_program_remove_excess_replace_vars(partial_program: str) -> str:
    '''
    Problem: if a problematic node appears multiple times consecutively in the AST,
    what ends up happening is that partial program contains several consecutive
    replace_var's. This is not good for using with LLMs.
    This function solves this problem by str.replace() by replacing all occurences of
    replace_var's to dummy_var's except the first one.
    The solution is somewhat hacky and not complete, but it's much easier than
    intervening translation process where we require translate() to use different
    rules for the same consecutive node types.
    '''
    li = partial_program.rsplit(
      p_consts.PAR_PROG_PROB_NODE_REPLACE,
      partial_program.count(p_consts.PAR_PROG_PROB_NODE_REPLACE) - 1
    )
    return p_consts.PAR_PROG_DUMMY_IDENTIFIER.join(li)

  # NOTE if the first translation was successful, it means we have all necessary translation rules.
  # If it wasn't successful, then we run a loop in which we introduce `problematic_node -> identifier` rules
  # until we translate the program. This way we generate a partial program.
  logger.debug(f'~~~ Preparing partially translated target code')

  # 1 ADD HACKY RULES FOR THE MAIN PROBLEMATIC NODE
  prob_ntype_main = template_dict['problematic_node_type']
  new_trans_rules = _append_hacky_rules(current_ruleset_str, prob_ntype_main, p_consts.PAR_PROG_PROB_NODE_REPLACE)
  new_src_code = template_dict['template_origin']

  logger.debug(
    f'problematic_node_type_main = "{prob_ntype_main}"\n'
    f'Appended hacky rules for the main problematic node to the ruleset\n'
    f'new_src_code = \n{new_src_code}')

  templates_dict = None
  try:
    duoglot_result_dict = duoglot_translate_wrapper(
      new_src_code,
      subject.src_lang,
      subject.tar_lang,
      new_trans_rules,
      subject.auto_backward,
      subject.choices,
      skip_template_extraction=True
    )
    logger.debug(f'SUCCESS Partial program generation is complete. num_loops=0')
    tar_code = duoglot_result_dict['tar_code']
    partial_program = _post_process_partial_program_remove_excess_replace_vars(tar_code)
    return partial_program
  except d_grammar_expand.TranslationRuleNotFoundException as exc:
    templates_dict = exc.get_templates_dict()

  # 2 ADD HACKY RULES FOR THE SUBSEQUENT PROBLEMATIC NODES
  logger.debug(f'Translation is not over yet: there are still nodes to translate in a hacky way')
  loop_counter = 1

  while True:
    logger.debug(f'Entering partial program generation loop #{loop_counter}')
    assert templates_dict is not None, 'should not happen: templates_dict is None'
    prob_ntype_remaining = templates_dict['problematic_node_type']
    new_trans_rules = _append_hacky_rules(new_trans_rules, prob_ntype_remaining, p_consts.PAR_PROG_DUMMY_IDENTIFIER)

    logger.debug(
      f'prob_ntype_remaining = "{prob_ntype_remaining}". '
      f'Appended hacky rules to the ruleset')

    templates_dict = None
    try:
      duoglot_result_dict = duoglot_translate_wrapper(
        new_src_code,
        subject.src_lang,
        subject.tar_lang,
        new_trans_rules,
        subject.auto_backward,
        subject.choices,
        skip_template_extraction=True
      )
      tar_code = duoglot_result_dict['tar_code']
      partial_program = _post_process_partial_program_remove_excess_replace_vars(tar_code)
      logger.debug(f'SUCCESS Partial program generation is complete. num_loops={loop_counter}')
      logger.debug(f'Partial program is:\n{partial_program}')
      return partial_program
    except d_grammar_expand.TranslationRuleNotFoundException as exc:
      templates_dict = exc.get_templates_dict()

    logger.debug(f'Partial program generation loop #{loop_counter} ended')
    loop_counter += 1


def _artificial_context_if_possible(template_dict: dict) -> Optional[dict]:
  '''
  ["py.module", 0,
    [
      "py.return_statement",
      1,
      "\"return\"", <node>
    ]
  ]
  '''
  logger.debug('Checking if artificial context for expressions can be used')

  context_ntype = template_dict['context_node_type']
  prob_ntype = template_dict['problematic_node_type']
  prob_nid = template_dict['problematic_node_id']
  prob_npath = template_dict['problematic_node_path']
  template_origin = template_dict['template_origin']
  src_lang = template_dict['src_lang']

  if context_ntype == prob_ntype:
    logger.debug(
      f'Artificial context cannot be used: context_node_type == '
      f'problematic_node_type == {context_ntype}')
    return None

  prob_nstr = d_ast_parse.node_id_pretty_print(template_origin, src_lang, prob_nid)
  artif_template_origin = f'return {prob_nstr}'
  artif_prob_npath = [1]

  # check if `artif_template_origin` can be parsed
  if p_utils.does_have_parse_error(artif_template_origin, src_lang):
    logger.debug(
      f'Artificial context cannot be used: could not parse '
      f'artificial template_origin == {artif_template_origin!r}')
    return None

  # check if the problematic node in `artif_template_origin`
  # is the same tree as the original problematic node
  tree1 = pds.DuoGlotTree.from_code_str(template_origin, src_lang)
  tree2 = pds.DuoGlotTree.from_code_str(artif_template_origin, src_lang)
  assert len(tree1.root_node.get_children()) == 1
  assert len(tree2.root_node.get_children()) == 1
  ctx_node1 = tree1.root_node.get_children()[0]
  ctx_node2 = tree2.root_node.get_children()[0]
  prob_node1 = ctx_node1.get_child_by_path(prob_npath)
  prob_node2 = ctx_node2.get_child_by_path(artif_prob_npath)
  assert prob_node1.get_ts_node_type() == prob_ntype == prob_node2.get_ts_node_type(), 'sanity check'
  if not prob_node1.is_similar_to_rec(prob_node2):
    logger.debug(
      f'Artificial context cannot be used: problematic node is parsed '
      f'differently in the artificial template_origin:\n'
      f'template_origin:\n{template_origin}\n'
      f'artificial_template_origin:\n{artif_template_origin}\n')
    return None

  artif_context_ntype = 'return_statement'
  artif_prob_nid = prob_node2.get_id()
  artif_contexts = [
    {
      'source_context': [
        [
          prob_node2.get_type()
        ],
        [
          'py.return_statement'
        ]
      ],
      'target_context': [
        [
          'unknown'
        ],
        [
          'js.return_statement'
        ]
      ]
    }
  ]
  artif_partial_program = f'return {p_consts.PAR_PROG_PROB_NODE_REPLACE};'

  artif_template_dict = {
    'template_id': template_dict['template_id'],
    'src_lang': template_dict['src_lang'],
    'tar_lang': template_dict['tar_lang'],
    'template_origin': artif_template_origin,
    'context_node_type': artif_context_ntype,
    'context_node_id': 1,
    'problematic_node_type': template_dict['problematic_node_type'],
    'problematic_node_id': artif_prob_nid,
    'problematic_node_path': artif_prob_npath,
    'is_valid_template': template_dict['is_valid_template'],
    'is_insert_secret_fn': template_dict['is_insert_secret_fn'],
    'contexts': artif_contexts,
    'partial_program': artif_partial_program,
  }

  return artif_template_dict


def _init_template_dict(
  subject: p_subject.PirelSubject,
  current_ruleset_str: str,
  templates_dict: dict
) -> dict:
  '''
  subject must contain:
  - src_lang
  - tar_lang
  - auto_backward
  - choices
  - get_src_main_code()
  '''

  def _rerun_translation_for_context(
    subject: p_subject.PirelSubject,
    current_ruleset_str: str,
    template_origin: str
  ) -> dict:
    '''
    Why do we need this function?
    We need this function to update certain values in `template_dict`:
    1. context_node_id
    2. problematic_node_id
    3. contexts (mainly)

    NOTE returns a new `template_dict`
    TODO optimize: context extraction is needed only at this step
    RETURN updated `template_dict`
    '''
    try:
      _ = duoglot_translate_wrapper(
        template_origin,
        subject.src_lang,
        subject.tar_lang,
        current_ruleset_str,
        subject.auto_backward,
        subject.choices,
      )
    except d_grammar_expand.TranslationRuleNotFoundException as exc:
      templates_dict = exc.get_templates_dict()
      template_idx = templates_dict['num_templates'] - 1
      return templates_dict[template_idx]
    raise RuntimeError('DuoGlot should have failed to translate the context code')

  logger.debug('Starting template_dict initialization')

  # in cases when templates_dict is loaded from str, keys are strings
  _valid_template_idx = p_utils.to_int(templates_dict['num_templates']) - 1
  template_dict = templates_dict.get(_valid_template_idx) or templates_dict.get(str(_valid_template_idx))

  result = _artificial_context_if_possible(template_dict)
  if result is not None:
    logger.debug(
      'Finished template_dict initialization. Using artificial context.\n'
      f'template_dict:\n{json.dumps(result, indent=2)}')
    p_utils.log_json_time(f'template_dict.json', result)
    return result

  # Rerun DuoGlot translation to obtain `template_dict`
  # for the context code snippet, not the entire program.
  # This is done to get the updated values for
  # `context_node_id`, `problematic_node_id`, and `problematic_node_path`
  template_dict = _rerun_translation_for_context(subject, current_ruleset_str, template_dict['template_origin'])

  # simplify the context
  template_dict = p_grammar.simplify_template(template_dict)

  # simplify the template using the generator
  template_dict = p_generator.simplify_template_with_generator(template_dict)

  # Rerun DuoGlot translation to obtain `template_dict`
  # for the context code snippet, not the entire program.
  # This is done to get the updated values for
  # `context_node_id`, `problematic_node_id`, and `problematic_node_path`
  template_dict = _rerun_translation_for_context(subject, current_ruleset_str, template_dict['template_origin'])

  # prepare partial program
  try:
    partial_program = _get_partial_program(subject, current_ruleset_str, template_dict)
  except Exception as e:
    logger.warning(f'Failed to generate partial program: {e}')
    raise PartialProgramGenerationError(f'Failed to generate partial program: {e}')
  template_dict['partial_program'] = partial_program

  logger.debug(
    'Finished template_dict initialization\n'
    f'template_dict:\n{json.dumps(template_dict, indent=2)}')
  p_utils.log_json_time(f'template_dict.json', template_dict)
  return template_dict


def _append_break_to_loop_body(loop_node: pvis.AbstractNode) -> None:
  assert isinstance(loop_node, (pvpy.ForStatementNode, pvpy.WhileStatementNode))
  # Keep insertion idempotent for repeated instrumentation passes.
  nt_children = loop_node.body.get_nt_children()
  if nt_children and isinstance(nt_children[-1], pvpy.BreakStatementNode):
    return
  break_statement = pvpy.BreakStatementNode('break_statement')
  loop_node.body.children.append(break_statement)
  break_statement.set_parent(loop_node.body)


def _prepend_terminate_to_loop_body(loop_node: pvis.AbstractNode) -> None:
  assert isinstance(loop_node, (pvpy.ForStatementNode, pvpy.WhileStatementNode))
  nt_children = loop_node.body.get_nt_children()

  # Keep insertion idempotent for repeated instrumentation passes.
  if nt_children and __is_os_exit_call_statement_node(nt_children[0]):
    return

  terminate_tree = pvpy.Tree.from_str(p_consts.PY_TERMINATION_STATEMENT)
  terminate_nodes = terminate_tree.root_node.get_nt_children()
  assert len(terminate_nodes) == 1, 'expected one terminate statement'
  terminate_node = terminate_nodes[0]
  terminate_node.set_parent(loop_node.body)

  insert_idx = 0
  while (
    insert_idx < len(loop_node.body.children)
    and isinstance(loop_node.body.children[insert_idx], pvis.TerminalNode)
  ):
    insert_idx += 1
  loop_node.body.children = (
    loop_node.body.children[:insert_idx]
    + [terminate_node]
    + loop_node.body.children[insert_idx:]
  )


def __is_os_exit_call_statement_node(node: pvis.AbstractNode) -> bool:
  '''
  Return True if the node is an expression statement that calls os._exit(0)
  NOTE argument check is not performed, i.e. `0` in _exit().
  '''
  if not isinstance(node, pvpy.ExpressionStatementNode):
    return False
  assert len(node.get_nt_children()) == 1, 'expected one child of expression statement'
  call_node = node.get_nt_children()[0]
  if not isinstance(call_node, pvpy.CallNode):
    return False
  function = call_node.function
  if not isinstance(function, pvpy.AttributeNode):
    return False
  _object = function.object
  _attribute = function.attribute
  assert isinstance(_attribute, pvpy.IdentifierNode), 'expected attribute to be an identifier node'
  assert isinstance(_object, pvpy.IdentifierNode), 'expected object to be an identifier node'
  if _object.val() != 'os':
    return False
  if _attribute.val() != '_exit':
    return False
  return True


def _combine_prectx_and_simple_ntext(
  pre_context: str,
  snippet_under_test: str,
  append_break_for_loop_stmt: bool = False,
  append_terminate_after_stmt: bool = False,
) -> str:

  def __rec_find_special_identifier(node: pvis.AbstractNode) -> Optional[pvpy.IdentifierNode]:
    if isinstance(node, pvpy.IdentifierNode):
      if node.val() == p_consts.PRE_CTX_SPEC_IDENT:
        return node
    for child in node.children:
      res = __rec_find_special_identifier(child)
      if res is not None:
        return res
    return None

  def __get_enclosing_function(node: pvis.AbstractNode) -> Optional[pvpy.FunctionDefinitionNode]:
    cursor = node
    while cursor is not None:
      if isinstance(cursor, pvpy.FunctionDefinitionNode):
        return cursor
      cursor = cursor.get_parent()
    return None

  def __get_enclosing_statement(node: pvis.AbstractNode) -> Optional[pvis.AbstractNode]:
    cursor = node
    while cursor is not None:
      parent = cursor.get_parent()
      if isinstance(parent, (pvpy.BlockNode, pvpy.ModuleNode)):
        return cursor
      cursor = parent
    return None

  def __get_callee_name(call_node: pvpy.CallNode) -> Optional[str]:
    fn_node = call_node.function
    if isinstance(fn_node, pvpy.IdentifierNode):
      return fn_node.val()
    if isinstance(fn_node, pvpy.AttributeNode):
      if isinstance(fn_node.attribute, pvpy.IdentifierNode):
        return fn_node.attribute.val()
    return None

  def __find_caller_statement_for_return(
    return_node: pvpy.ReturnStatementNode
  ) -> Optional[pvis.AbstractNode]:
    target_fn = __get_enclosing_function(return_node)
    if target_fn is None or not isinstance(target_fn.name, pvpy.IdentifierNode):
      return None
    target_fn_name = target_fn.name.val()

    candidates: List[pvis.AbstractNode] = []
    seen_stmt_objids: Set[int] = set()
    stack = [pc_tree.root_node]
    while stack:
      node = stack.pop()
      if isinstance(node, pvpy.CallNode):
        callee_name = __get_callee_name(node)
        if callee_name == target_fn_name:
          enclosing_fn = __get_enclosing_function(node)
          if enclosing_fn is target_fn:
            pass
          else:
            enclosing_stmt = __get_enclosing_statement(node)
            if enclosing_stmt is not None and id(enclosing_stmt) not in seen_stmt_objids:
              seen_stmt_objids.add(id(enclosing_stmt))
              candidates.append(enclosing_stmt)
      for child in reversed(node.get_nt_children()):
        stack.append(child)

    if not candidates:
      return None
    candidates.sort(key=lambda nd: nd.get_node_id())
    return candidates[-1]

  def __is_raise_system_exit_node(node: pvis.AbstractNode) -> bool:
    if not isinstance(node, pvpy.RaiseStatementNode):
      return False
    raise_children = node.get_nt_children()
    return (
      len(raise_children) == 1
      and isinstance(raise_children[0], pvpy.IdentifierNode)
      and raise_children[0].val() == 'SystemExit'
    )

  def __insert_terminate_after_statement(statement_node: pvis.AbstractNode) -> bool:
    parent = statement_node.get_parent()
    if parent is None:
      return False
    siblings = parent.get_children()
    try:
      stmt_idx = siblings.index(statement_node)
    except ValueError:
      return False

    for sib in siblings[stmt_idx + 1:]:
      if isinstance(sib, pvis.TerminalNode):
        continue
      if __is_os_exit_call_statement_node(sib):
        return True
      break

    terminate_tree = pvpy.Tree.from_str(p_consts.PY_TERMINATION_STATEMENT)
    terminate_nodes = terminate_tree.root_node.get_nt_children()
    assert len(terminate_nodes) == 1, 'expected one terminate statement'
    terminate_node = terminate_nodes[0]
    terminate_node.set_parent(parent)
    insert_idx = stmt_idx + 1
    while insert_idx < len(siblings) and isinstance(siblings[insert_idx], pvis.TerminalNode):
      insert_idx += 1
    parent.children = (
      siblings[:insert_idx]
      + [terminate_node]
      + siblings[insert_idx:]
    )
    return True

  assert pre_context.count(p_consts.PRE_CTX_SPEC_IDENT) == 1, \
    'should not happen: pre_context must contain exactly one line with special identifier'
  pc_tree = pvpy.Tree.from_str(pre_context)
  sut_tree = pvpy.Tree.from_str(snippet_under_test)

  spec_id_node = __rec_find_special_identifier(pc_tree.root_node)
  assert spec_id_node is not None, 'should not happen: could not find special identifier node'
  repl_expr_stat_node = spec_id_node.get_parent()  # will replace expression statement node
  idx_in_parent = repl_expr_stat_node.parent.children.index(repl_expr_stat_node)

  # Root cause:
  # expression-validation snippet may contain multiple statements (e.g.
  # "lhs = rhs" + "myexactlog(rhs)"). Replacing PRE_CTX marker with the
  # wrapper module node breaks parent/child expectations.
  # Patch reason:
  # splice the snippet's non-terminal top-level statements directly into
  # parent children so both single- and multi-statement snippets are valid.
  sut_root_nt_children = sut_tree.root_node.get_nt_children()
  assert len(sut_root_nt_children) > 0, \
    'should not happen: snippet_under_test must contain at least one statement'
  repl_parent = repl_expr_stat_node.parent
  if len(sut_root_nt_children) == 1:
    sut_stat_node = sut_root_nt_children[0]
    sut_stat_node.set_parent(repl_parent)
    repl_parent.children[idx_in_parent] = sut_stat_node
    inserted_nodes = [sut_stat_node]
  else:
    for node in sut_root_nt_children:
      node.set_parent(repl_parent)
    repl_parent.children = (
      repl_parent.children[:idx_in_parent]
      + sut_root_nt_children
      + repl_parent.children[idx_in_parent + 1:]
    )
    inserted_nodes = sut_root_nt_children

  # Root cause:
  # When the current statement itself is a loop statement in EOT validation,
  # marker-anchored break instrumentation runs before replacement and therefore
  # cannot attach a break to that loop's body.
  # Fix rationale:
  # After replacing the marker with the concrete statement, enforce a
  # single-iteration guard by appending `break` to the loop statement itself.
  if (
    append_break_for_loop_stmt
    and len(inserted_nodes) == 1
    and isinstance(inserted_nodes[0], (pvpy.ForStatementNode, pvpy.WhileStatementNode))
  ):
    _append_break_to_loop_body(inserted_nodes[0])

  if append_terminate_after_stmt:
    # Stop validation snippet immediately after the validated statement path runs.
    if len(inserted_nodes) == 1 and isinstance(inserted_nodes[0], pvpy.ReturnStatementNode):
      # For return-target validation, terminate after the concrete caller call-site statement.
      caller_stmt = __find_caller_statement_for_return(inserted_nodes[0])
      if caller_stmt is not None and __insert_terminate_after_statement(caller_stmt):
        pp = pvpy.PrettyPrinter(indent_with='    ')
        pp.visit(pc_tree.root_node)
        return '\n'.join(pp.lines)

    if (
      len(inserted_nodes) == 1
      and isinstance(inserted_nodes[0], (pvpy.ForStatementNode, pvpy.WhileStatementNode))
    ):
      # Loop target can run forever before reaching a sibling statement-level
      # terminator. Put terminate at the top of the loop body instead.
      _prepend_terminate_to_loop_body(inserted_nodes[0])
    else:
      terminate_tree = pvpy.Tree.from_str(p_consts.PY_TERMINATION_STATEMENT)
      terminate_nodes = terminate_tree.root_node.get_nt_children()
      assert len(terminate_nodes) == 1, 'expected one terminate statement'
      terminate_node = terminate_nodes[0]
      terminate_node.set_parent(repl_parent)
      idx_last_inserted = repl_parent.children.index(inserted_nodes[-1])
      insert_before_target = (
        len(inserted_nodes) == 1
        and isinstance(
          inserted_nodes[0],
          (
            pvpy.BreakStatementNode,
            pvpy.ContinueStatementNode,
            pvpy.ReturnStatementNode,
            pvpy.RaiseStatementNode,
          ),
        )
      )
      insert_idx = idx_last_inserted if insert_before_target else idx_last_inserted + 1
      repl_parent.children = (
        repl_parent.children[:insert_idx]
        + [terminate_node]
        + repl_parent.children[insert_idx:]
      )

  pp = pvpy.PrettyPrinter(indent_with='    ')
  pp.visit(pc_tree.root_node)
  return '\n'.join(pp.lines)


def _create_subject_for_snippet_learn(
  artif_template_origin: str,
  src_lang: str,
  tar_lang: str,
  subject_name: str,
) -> p_subject.PirelSubject:
  '''
  Create a subject used during snippet-based rule learning
  phase: learn_trans_rules_from_snippet()
  '''

  # all attributes of PirelSubject instance set explicitly
  benchmark_name = 'snippet-learn'
  name = subject_name
  src_program = artif_template_origin
  src_lang = src_lang
  tar_lang = tar_lang
  translation_rules_main_code = None
  translation_rules_test_code = None
  is_three_split = False
  auto_backward = True
  choices = {'type': 'ASTNODE', 'choices_list': []}
  verified_choice_options = []

  # create a subject instance
  snippet_learn_subject = p_subject.PirelSubject(
    benchmark_name, name, src_program, src_lang, tar_lang, is_three_split)
  snippet_learn_subject.translation_rules_main_code = translation_rules_main_code
  snippet_learn_subject.translation_rules_test_code = translation_rules_test_code
  snippet_learn_subject.auto_backward = auto_backward
  snippet_learn_subject.choices = choices
  snippet_learn_subject.verified_choice_options = verified_choice_options

  return snippet_learn_subject


def _create_subject_for_stat_learn(
  main_subject: p_subject.PirelSubject,
  simple_ntext: str,
  current_ruleset: p_ruleset.Ruleset,
  simple_nchoices: dict,
) -> p_subject.PirelSubject:
  '''
  Create a subject used during rule learning phase.
  '''

  # all attributes of PirelSubject instance set explicitly
  benchmark_name = 'stat-learn'
  name = main_subject.name
  src_program = simple_ntext
  src_lang = main_subject.src_lang
  tar_lang = main_subject.tar_lang
  translation_rules_main_code = current_ruleset.to_str_ruleset()
  translation_rules_test_code = None
  is_three_split = False
  auto_backward = True
  choices = simple_nchoices
  verified_choice_options = []

  # create a subject instance
  stat_learn_subject = p_subject.PirelSubject(
    benchmark_name, name, src_program, src_lang, tar_lang, is_three_split)
  stat_learn_subject.translation_rules_main_code = translation_rules_main_code
  stat_learn_subject.translation_rules_test_code = translation_rules_test_code
  stat_learn_subject.auto_backward = auto_backward
  stat_learn_subject.choices = choices
  stat_learn_subject.verified_choice_options = verified_choice_options

  return stat_learn_subject


def _rfind_statement_nid_by_text(
  src_main_code: str,
  statement: str
) -> int:
  '''
  Return the node_id in the AST of src_main_code whose text is statement.
  If there are multiple such nodes, return the rightmost one.
  If there multiple nodes with the same text, return the furthest one
  from the root.
  PRE: statement is not empty and appears in src_main_code.
  '''

  def _rec_rfind(node: pvis.AbstractNode) -> Optional[pvis.AbstractNode]:
    nonlocal statement
    pp = pvpy.PrettyPrinter(indent_with='    ')
    node_text = pp.visit(node)
    node_text = node_text if node_text is not None else '\n'.join(pp.lines)
    if node_text == statement:
      # found matching node, but its child may have the same text
      # e.g. block -> expression_statement
      # need to return the smallest matching node
      all_children_result = [_rec_rfind(child) for child in node.get_nt_children()]
      if all(c is None for c in all_children_result):
        return node
      child_res = [c for c in all_children_result if c is not None]
      assert len(child_res) == 1, 'should not happen: multiple children with the same text'
      return child_res[0]
    for child in reversed(node.get_nt_children()):
      res = _rec_rfind(child)
      if res is not None:
        return res
    return None

  assert statement.strip() != '', 'should not happen: statement is empty'
  assert src_main_code.strip() != '', 'should not happen: src_main_code is empty'

  tree = pvpy.Tree.from_str(src_main_code)
  stat_node = _rec_rfind(tree.root_node)
  assert stat_node is not None, 'should not happen: could not find statement node'

  return stat_node.get_node_id()


def _find_pre_ctx_spec_statement_nid(src_main_code: str) -> int:
  '''
  Return the statement node id for the unique pre-context marker statement:
  `pirel_pre_ctx_spec_identifier`.

  Root cause:
  break instrumentation previously located the target statement by text.
  For common snippets like `pass`, this can match a wrong statement node.
  Fix rationale:
  use the unique pre-context marker statement to anchor loop instrumentation.
  '''
  tree = pvpy.Tree.from_str(src_main_code)
  root_node = tree.root_node
  matches: List[pvis.AbstractNode] = []

  stack = [root_node]
  while stack:
    node = stack.pop()
    if isinstance(node, pvpy.ExpressionStatementNode):
      nt_children = node.get_nt_children()
      if (
        len(nt_children) == 1
        and isinstance(nt_children[0], pvpy.IdentifierNode)
        and nt_children[0].val() == p_consts.PRE_CTX_SPEC_IDENT
      ):
        matches.append(node)
    stack.extend(node.get_nt_children())

  assert len(matches) == 1, \
    f'expected exactly one PRE_CTX marker statement, got {len(matches)}'
  return matches[0].get_node_id()


def _instrument_with_break_statements(
  src_main_code: str,
  statement: str,
  loop_scope: str = 'ancestors',
  statement_nid: Optional[int] = None,
) -> str:
  '''
  Insert break statements in loops to avoid infinite loops.
  - loop_scope='ancestors': insert breaks only in loops that are ancestors
    of the statement node (legacy behavior).
  - loop_scope='ancestors_and_callers': insert breaks in loops that are
    ancestors of the statement and in loops that enclose call sites from the
    caller chain to the statement's enclosing function.
  - loop_scope='all_loops': insert breaks in every for/while loop in the
    snippet (broad fallback mode).
  PRE: statement is not empty and appears in src_main_code,
  unless statement_nid is provided.
  '''
  tree = pvpy.Tree.from_str(src_main_code)
  root_node = tree.root_node

  def _collect_ancestor_loops(node: pvis.AbstractNode) -> list[pvis.AbstractNode]:
    loops: list[pvis.AbstractNode] = []
    cursor_node = node
    while cursor_node is not None:
      if isinstance(cursor_node, (pvpy.ForStatementNode, pvpy.WhileStatementNode)):
        loops.append(cursor_node)
      cursor_node = cursor_node.get_parent()
    return loops

  def _dedup_nodes(nodes: list[pvis.AbstractNode]) -> list[pvis.AbstractNode]:
    seen_objids: Set[int] = set()
    deduped: list[pvis.AbstractNode] = []
    for node in nodes:
      objid = id(node)
      if objid in seen_objids:
        continue
      seen_objids.add(objid)
      deduped.append(node)
    return deduped

  def _collect_caller_chain_loops(
    stat_node: pvis.AbstractNode,
  ) -> list[pvis.AbstractNode]:
    '''
    Return loops that can execute the statement indirectly via caller chain.
    We track calls among locally defined functions:
    caller_fn -> callee_fn.

    Root cause:
    The previous ancestors-only strategy cannot see loops in callers
    when the validated statement is nested in a callee function.
    Patch reason:
    Recover those caller-side loops by traversing reverse call edges
    from the statement's enclosing function to its transitive callers.
    '''

    def _get_enclosing_fn_name(node: pvis.AbstractNode) -> Optional[str]:
      cursor = node
      while cursor is not None:
        if isinstance(cursor, pvpy.FunctionDefinitionNode):
          assert isinstance(cursor.name, pvpy.IdentifierNode), \
            'function name must be an IdentifierNode'
          return cursor.name.val()
        cursor = cursor.get_parent()
      return None

    defined_fn_names: Set[str] = set()

    def _collect_fn_defs(node: pvis.AbstractNode) -> None:
      if isinstance(node, pvpy.FunctionDefinitionNode):
        assert isinstance(node.name, pvpy.IdentifierNode), \
          'function name must be an IdentifierNode'
        defined_fn_names.add(node.name.val())
      for child in node.get_nt_children():
        _collect_fn_defs(child)

    _collect_fn_defs(root_node)
    target_fn_name = _get_enclosing_fn_name(stat_node)
    if target_fn_name is None or target_fn_name not in defined_fn_names:
      return []

    # Reverse call index: callee_fn -> list[(caller_fn_name_or_none, call_node)]
    callee_to_callsites: Dict[str, list[Tuple[Optional[str], pvis.AbstractNode]]] = {}

    def _get_callee_name_from_call(call_node: pvpy.CallNode) -> Optional[str]:
      fn_node = call_node.function
      if isinstance(fn_node, pvpy.IdentifierNode):
        return fn_node.val()
      if isinstance(fn_node, pvpy.AttributeNode):
        # Root cause:
        # Caller-chain loop recovery only tracked identifier calls, so calls like
        # `class_var.updatepos(...)` were ignored and caller loops were missed.
        # Fix rationale:
        # Treat attribute calls by their attribute identifier name as potential
        # local callee names when they match locally defined functions.
        if isinstance(fn_node.attribute, pvpy.IdentifierNode):
          return fn_node.attribute.val()
      return None

    def _collect_calls(node: pvis.AbstractNode, current_fn_name: Optional[str]) -> None:
      next_fn_name = current_fn_name
      if isinstance(node, pvpy.FunctionDefinitionNode):
        assert isinstance(node.name, pvpy.IdentifierNode), \
          'function name must be an IdentifierNode'
        next_fn_name = node.name.val()

      if isinstance(node, pvpy.CallNode):
        callee_name = _get_callee_name_from_call(node)
        if callee_name in defined_fn_names:
          callee_to_callsites.setdefault(callee_name, []).append((next_fn_name, node))

      for child in node.get_nt_children():
        _collect_calls(child, next_fn_name)

    _collect_calls(root_node, None)

    caller_chain_loops: list[pvis.AbstractNode] = []
    visited_fns: Set[str] = {target_fn_name}
    queue: List[str] = [target_fn_name]
    while queue:
      callee_name = queue.pop(0)
      for caller_name, call_node in callee_to_callsites.get(callee_name, []):
        # Add loops surrounding the concrete call site (runtime-relevant),
        # instead of all loops in the file.
        caller_chain_loops.extend(_collect_ancestor_loops(call_node))
        if caller_name is None:
          continue
        if caller_name in visited_fns:
          continue
        visited_fns.add(caller_name)
        queue.append(caller_name)

    return _dedup_nodes(caller_chain_loops)

  nid_node_map = root_node.get_nid_node_map()
  if statement_nid is None:
    stat_nid = _rfind_statement_nid_by_text(src_main_code, statement)
  else:
    stat_nid = statement_nid
  assert stat_nid in nid_node_map, 'should not happen: stat_nid not in nid_node_map'
  stat_node = nid_node_map[stat_nid]

  loop_nodes_to_break: list[pvis.AbstractNode] = []
  if loop_scope == 'all_loops':
    stack = [root_node]
    while stack:
      node = stack.pop()
      if isinstance(node, (pvpy.ForStatementNode, pvpy.WhileStatementNode)):
        loop_nodes_to_break.append(node)
      stack.extend(node.children)
  elif loop_scope == 'ancestors':
    loop_nodes_to_break.extend(_collect_ancestor_loops(stat_node))
  elif loop_scope == 'ancestors_and_callers':
    # Root cause:
    # ancestors-only misses caller-side loops when the statement resides in a
    # callee function; all-loops overcorrects and can truncate unrelated loops.
    # Patch reason:
    # Limit break insertion to loops that can execute the statement: direct
    # ancestor loops + caller-chain callsite loops.
    loop_nodes_to_break.extend(_collect_ancestor_loops(stat_node))
    loop_nodes_to_break.extend(_collect_caller_chain_loops(stat_node))
  else:
    raise ValueError(f'Unknown loop_scope: {loop_scope}')

  # Apply in source order for deterministic instrumentation.
  nid_by_objid = {id(node): nid for nid, node in nid_node_map.items()}
  loop_nodes_to_break = _dedup_nodes(loop_nodes_to_break)
  loop_nodes_to_break.sort(key=lambda node: nid_by_objid.get(id(node), 10**12))
  for loop_node in loop_nodes_to_break:
    _append_break_to_loop_body(loop_node)

  pp = pvpy.PrettyPrinter(indent_with='    ')
  pp.visit(root_node)
  return '\n'.join(pp.lines)


def _create_src_main_code_for_val(
  src_main_code: str,
  pre_context: str,
  statement: str,
  is_three_split: bool,
) -> str:
  '''
  Return log-instrumented main code for statement node validation.

  This snippet contains the given statement wrapped in its pre-context,
  and if the subject program is in the three-split format,
  wrapped again in the function header if src_main_code.
  '''
  # Keep the unique pre-context marker first, so break instrumentation can
  # anchor on an unambiguous statement node (instead of text like `pass`).
  stmt_in_ctx = pre_context
  if is_three_split: # wrap in f_gold
    function_headers = [line for line in src_main_code.splitlines()
                        if line.startswith('def f_gold(')]
    assert len(function_headers) == 1
    fn_header = function_headers[0].strip()
    assert fn_header.endswith('):')
    stmt_in_ctx = f'{fn_header}\n{p_utils.indent(stmt_in_ctx, 4)}'
    # Root cause:
    # Ancestor-only break insertion can miss caller-side loops when the
    # validated statement is inside a callee function (e.g., updatepos()),
    # which allowed None to flow into loop guards during EOT validation.
    # Patch reason:
    # Keep loop instrumentation focused on execution-relevant loops:
    # statement ancestors + caller-chain callsite loops.
    spec_stmt_nid = _find_pre_ctx_spec_statement_nid(stmt_in_ctx)
    stmt_in_ctx = _instrument_with_break_statements(
      stmt_in_ctx,
      p_consts.PRE_CTX_SPEC_IDENT,
      loop_scope='ancestors_and_callers',
      statement_nid=spec_stmt_nid,
    )
    stmt_in_ctx = _combine_prectx_and_simple_ntext(
      stmt_in_ctx,
      statement,
      append_break_for_loop_stmt=True,
    )
    stmt_in_ctx = pvpy.LogStatementInserter.insert_log_statements(stmt_in_ctx)
    stmt_in_ctx = pvpy.LogStatementsIndexer.index_log_statements(stmt_in_ctx)
  else:
    # For EOT validation, terminate immediately after the current
    # translated statement path executes.
    stmt_in_ctx = _combine_prectx_and_simple_ntext(
      stmt_in_ctx,
      statement,
      append_break_for_loop_stmt=False,
      append_terminate_after_stmt=True,
    )
    stmt_in_ctx = pvpy.LogInserterNo3Split.insert_log_statements(stmt_in_ctx)
    stmt_in_ctx = pvpy.LogIndexerNo3Split.index_log_statements(stmt_in_ctx)

  return stmt_in_ctx


def _create_src_program_for_stat_val(
  main_subject: p_subject.PirelSubject,
  pre_context: str,
  simple_ntext: str
) -> str:
  '''
  Test code for statement node validation
  is the same as the main subject's test code.
  '''
  snv_src_test_code = main_subject.get_src_test_code()
  snv_src_main_code = _create_src_main_code_for_val(
    main_subject.get_src_main_code(),
    pre_context,
    simple_ntext,
    main_subject.is_three_split)
  if not main_subject.is_three_split:
    return snv_src_main_code

  '''
  Test call code is a simple hard-coded `test()` string
  '''
  snv_test_call_code = 'test()'

  snv_src_program = p_consts.TEST_SCRIPT_TEMPLATE.format(
    test_code=snv_src_test_code, main_code=snv_src_main_code, test_call_code=snv_test_call_code)
  return snv_src_program


def _create_subject_for_stat_val(
  main_subject: p_subject.PirelSubject,
  pre_context: str,
  simple_ntext: str,
  current_ruleset: p_ruleset.Ruleset,
  origin_stat_nid_for_eot: Optional[int] = None,
) -> p_subject.PirelSubject:
  '''
  Create a subject used during validation phase.
  '''
  # all attributes of PirelSubject instance set explicitly
  benchmark_name = 'stat-val'
  name = main_subject.name
  src_program = _create_src_program_for_stat_val(main_subject, pre_context, simple_ntext)
  src_lang = main_subject.src_lang
  tar_lang = main_subject.tar_lang
  translation_rules_main_code = \
    p_utils.read_text(p_consts.RULE_VAL_PRIORITY_RULES_FPATH) + '\n\n' + \
    p_utils.read_text(p_consts.LOG_STAT_RULE_FPATH) + '\n\n' + \
    current_ruleset.to_str_ruleset() + '\n\n' + \
    p_utils.read_text(p_consts.RULE_VAL_EXTRA_RULES_FPATH)
  translation_rules_test_code = main_subject.translation_rules_test_code
  is_three_split = main_subject.is_three_split
  auto_backward = True
  choices = {'type': 'ASTNODE', 'choices_list': []}  # default
  verified_choice_options = []  # default, will be set later

  # create a subject instance
  stat_val_subject = p_subject.PirelSubject(
    benchmark_name, name, src_program, src_lang, tar_lang, is_three_split)
  stat_val_subject.translation_rules_main_code = translation_rules_main_code
  stat_val_subject.translation_rules_test_code = translation_rules_test_code
  stat_val_subject.is_three_split = is_three_split
  stat_val_subject.auto_backward = auto_backward
  stat_val_subject.choices = choices
  stat_val_subject.verified_choice_options = verified_choice_options
  # Keep original (unpruned) context so downstream readonly-choice init can
  # resolve execution order before blacklist/pruning effects from pre-context.
  stat_val_subject.origin_src_main_code_for_eot = main_subject.get_src_main_code()
  stat_val_subject.origin_stat_nid_for_eot = origin_stat_nid_for_eot

  return stat_val_subject


def _get_first_lang_nonterminal_child(node: object, lang_prefix: str) -> Optional[list]:
  if not isinstance(node, list):
    return None
  for child in node[1:]:
    if not isinstance(child, list) or len(child) == 0:
      continue
    child_type = child[0]
    if not isinstance(child_type, str):
      continue
    if child_type.startswith(f'"{lang_prefix}.'):
      return child
  return None


def _extract_return_expr_companion_rule(rule_str: str) -> Optional[str]:
  '''
  For a recovery rule that maps `py.return_statement` -> `js.return_statement`,
  derive a companion expression-level rule from the return payload.
  This helps validation paths where the same expression appears under
  instrumentation wrappers (e.g., myexactlog(...)) rather than `return`.
  '''
  parsed_rules = d_grammar_rules.parse_analyze_rules_optim(rule_str)
  if len(parsed_rules) != 1:
    return None
  rule_parsed = parsed_rules[0]
  if rule_parsed.get('type') != 'match_expand':
    return None

  match_frag = rule_parsed.get('match')
  expand_frag = rule_parsed.get('expand')
  if (
    not isinstance(match_frag, list) or len(match_frag) < 2 or match_frag[0] != 'fragment'
    or not isinstance(expand_frag, list) or len(expand_frag) < 2 or expand_frag[0] != 'fragment'
  ):
    return None

  match_root = match_frag[1]
  expand_root = expand_frag[1]
  if (
    not isinstance(match_root, list) or len(match_root) == 0 or match_root[0] != '"py.return_statement"'
    or not isinstance(expand_root, list) or len(expand_root) == 0 or expand_root[0] != '"js.return_statement"'
  ):
    return None

  py_expr = _get_first_lang_nonterminal_child(match_root, 'py')
  js_expr = _get_first_lang_nonterminal_child(expand_root, 'js')
  if py_expr is None or js_expr is None:
    return None

  companion_rule = {
    'type': 'match_expand',
    'match': ['fragment', copy.deepcopy(py_expr), '"*"'],
    'expand': ['fragment', copy.deepcopy(js_expr), '"*1"'],
  }
  companion_rule_str = d_grammar_rules.pretty_rule(companion_rule)
  if companion_rule_str == rule_str:
    return None
  return companion_rule_str


def _rule_source_fragment_contains_node_type(
  rule_str: str,
  src_lang: str,
  node_type: str,
) -> bool:
  '''
  Return True if match-side fragment of a rule contains the given source
  node type anywhere in its subtree.
  '''
  parsed_rules = d_grammar_rules.parse_analyze_rules_optim(rule_str)
  target_types = {
    node_type,
    f'{src_lang}.{node_type}',
    f'"{src_lang}.{node_type}"',
  }
  if node_type.startswith(f'{src_lang}.'):
    target_types.add(node_type.split('.', 1)[1])

  def _rec_contains(node: object) -> bool:
    if not isinstance(node, list):
      return False
    if len(node) > 0 and isinstance(node[0], str) and node[0] in target_types:
      return True
    for child in node[1:]:
      if _rec_contains(child):
        return True
    return False

  for rule_parsed in parsed_rules:
    if rule_parsed.get('type') != 'match_expand':
      continue
    match_frag = rule_parsed.get('match')
    if not isinstance(match_frag, list) or len(match_frag) < 2 or match_frag[0] != 'fragment':
      continue
    match_root = match_frag[1]
    if _rec_contains(match_root):
      return True
  return False


def _is_problematic_node_covered_by_overfitted_rules(
  problematic_node_type: Optional[str],
  added_rule_strs: List[str],
  src_lang: str,
) -> bool:
  if not problematic_node_type:
    return False
  for added_rule_str in added_rule_strs:
    if _rule_source_fragment_contains_node_type(
      added_rule_str,
      src_lang,
      problematic_node_type,
    ):
      return True
  return False


async def _filter_overfitted_trules_by_validation(
  learned_trules: List[str],
  main_subject: p_subject.PirelSubject,
  current_ruleset: p_ruleset.Ruleset,
  simple_ntext: str,
  simple_nchoices: dict,
  pre_context: str,
  stat_nid: int,
) -> List[str]:
  '''
  Validate overfitted statement rules by running the full statement-level
  validation pipeline with each rule applied in isolation. Only rules that
  pass validation are returned.
  '''
  logger.debug(f'--stat-filter--: Starting p_pirel._filter_overfitted_trules_by_validation()')

  valid_trules: List[str] = []
  total = len(learned_trules)
  for idx, rule_str in enumerate(learned_trules, start=1):
    logger.debug(f'--stat-filter--: filtering overfitted rule by validation (idx={idx}/{total})\n{rule_str}')

    # Root cause: a recovery overfitted rule can wrap a Python compound statement
    # into a JS IIFE expression statement. Local validation for the current node
    # may pass, but later statements can fail due to leaked scope
    # (e.g., `ReferenceError: k is not defined`).
    # Fix rationale: reject known-invalid structural patterns early so they are
    # never injected into the shared ruleset, even before test-based validation.
    if p_rule_validator.is_invalid_pattern_detected(rule_str):
      logger.warning(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'discarding overfitted rule by invalid-pattern guard '
        f'({idx}/{total})')
      continue

    rule_parsed = p_ruleset.TRuleBase.parse_rule_str(rule_str)
    rule = p_ruleset.StatementOverfittedTRule(rule_parsed, stat_nid, simple_ntext)
    if current_ruleset.get_rule_ref(rule) is not None:
      logger.debug(f'--stat-filter--: statement node (nid={stat_nid}): skipping duplicate rule:\n{rule}')
      candidate_rule_strs: List[str] = []
    else:
      candidate_rule_strs = [rule_str]

    companion_rule_str = _extract_return_expr_companion_rule(rule_str)
    if companion_rule_str is not None:
      # Root cause:
      # return-level overfitted rules can fail in full validation when the same
      # expression appears inside log instrumentation calls, where the root is
      # expression_statement/call rather than return_statement.
      # Fix rationale:
      # auto-add a companion expression rule extracted from the return payload.
      if p_rule_validator.is_invalid_pattern_detected(companion_rule_str):
        logger.debug(
          f'--stat-main--: statement node (nid={stat_nid}): '
          f'skipping derived companion rule due to invalid-pattern guard\n'
          f'{companion_rule_str}')
      else:
        candidate_rule_strs.append(companion_rule_str)
        logger.debug(
          f'--stat-main--: statement node (nid={stat_nid}): '
          f'derived companion expression rule from return overfitted rule\n'
          f'{companion_rule_str}')

    tmp_ruleset = p_ruleset.Ruleset.from_dict(current_ruleset.to_dict())
    added_rule_strs: List[str] = []
    for candidate_rule_str in candidate_rule_strs:
      candidate_rule_parsed = p_ruleset.TRuleBase.parse_rule_str(candidate_rule_str)
      candidate_rule = p_ruleset.StatementOverfittedTRule(
        candidate_rule_parsed,
        stat_nid,
        simple_ntext,
      )
      if tmp_ruleset.get_rule_ref(candidate_rule) is not None:
        logger.debug(
          f'--stat-main--: statement node (nid={stat_nid}): '
          f'skipping duplicate rule during overfitted validation\n{candidate_rule}')
        continue
      tmp_ruleset.prepend_rule(candidate_rule)
      added_rule_strs.append(candidate_rule_str)

    if len(added_rule_strs) == 0:
      continue

    tmp_stat_learn_subject = _create_subject_for_stat_learn(
      main_subject, simple_ntext, tmp_ruleset, simple_nchoices)
    tmp_stat_val_subject = _create_subject_for_stat_val(
      main_subject,
      pre_context,
      simple_ntext,
      tmp_ruleset,
      origin_stat_nid_for_eot=stat_nid,
    )
    # Root cause:
    # overfitted-rule filtering reused stat-val caches keyed by subject name.
    # That allowed stale readonly choices / successful-choice seeds from prior
    # iterations to steer translation away from the newly prepended candidate
    # overfitted rule (falling back to generic paths, e.g., unresolved py.slice).
    # Fix rationale:
    # isolate each candidate validation run with a cache-only namespace, while
    # preserving subject.name for benchmark config lookups during EOT validation.
    tmp_stat_val_subject.cache_subject_name = (
      f'{main_subject.name}__ovfilt_nid{stat_nid}_cand{idx}'
    )
    tmp_stat_val_subject.choices = copy.deepcopy(simple_nchoices)

    try:
      await stat_node_validate_trules(
        simple_nchoices,
        simple_ntext,
        tmp_stat_learn_subject,
        tmp_stat_val_subject,
        tmp_ruleset,
        ptlog.StatNodeVal(),
      )
    except _ValidationError_ProblematicNodeExists as exc:
      if not _is_problematic_node_covered_by_overfitted_rules(
        exc.problematic_node_type,
        added_rule_strs,
        main_subject.src_lang,
      ):
        logger.warning(
          f'--stat-filter--: statement node (nid={stat_nid}): '
          f'discarding overfitted rule that failed validation '
          f'({idx}/{total}): {type(exc).__name__}')
        continue
      logger.info(
        f'--stat-filter--: statement node (nid={stat_nid}): '
        f'bypassing problematic-node precheck for overfitted candidate '
        f'({idx}/{total}); problematic_node_type={exc.problematic_node_type}')
      try:
        await stat_node_validate_trules(
          simple_nchoices,
          simple_ntext,
          tmp_stat_learn_subject,
          tmp_stat_val_subject,
          tmp_ruleset,
          ptlog.StatNodeVal(),
          skip_problematic_node_precheck=True,
        )
      except Exception as bypass_exc:
        logger.warning(
          f'--stat-filter--: statement node (nid={stat_nid}): '
          f'discarding overfitted rule that failed validation '
          f'({idx}/{total}): {type(bypass_exc).__name__}')
        continue
    except Exception as exc:
      logger.warning(
        f'--stat-filter--: statement node (nid={stat_nid}): '
        f'discarding overfitted rule that failed validation '
        f'({idx}/{total}): {type(exc).__name__}')
      continue

    for added_rule_str in added_rule_strs:
      if added_rule_str not in valid_trules:
        valid_trules.append(added_rule_str)
    logger.debug(
      f'--stat-filter--: rule set passed validation (idx={idx}/{total}) '
      f'added={len(added_rule_strs)}')
    for added_rule_str in added_rule_strs:
      logger.debug(f'--stat-filter--: validated rule\n{added_rule_str}')

  return valid_trules


def _get_statement_node_text(
  node: pds.PirelNode,
  src_main_code: str,
) -> str:
  '''
  RETURN text of the statement node.
  '''
  nid_node_map = _get_cached_pvpy_nid_node_map(src_main_code)
  assert node.get_id() in nid_node_map, 'should not happen: node id not in nid_node_map'
  node = nid_node_map[node.get_id()]
  pp = pvpy.PrettyPrinter(indent_with='    ')
  pp.visit(node)
  text = '\n'.join(pp.lines)
  return text


def _simplify_comp_stat_node_text(
  node: pds.PirelNode,
  src_main_code: str,
) -> str:
  '''
  Replaces children of `block` nodes with a pass statement.
  Has no effect on non-compound statement nodes.
  RETURN simplified text of the statement node.
  '''
  text = _get_statement_node_text(node, src_main_code)
  tree = pvpy.Tree.from_str(text)
  sn_simplifier = pvpy.CompStatNodeSimplifier()
  sn_simplifier.visit(tree.root_node)
  pp = pvpy.PrettyPrinter(indent_with='    ')
  simplified_text = pp.visit(tree.root_node)
  return simplified_text


def _get_statement_node_by_id(
  src_main_code: str,
  lang: str,
  node_id: int
) -> pds.PirelNode:
  '''
  Given an id of the statement node, return the node from the source code.
  '''
  nid_node_map = _get_cached_pirel_nid_node_map(src_main_code, lang)
  if node_id not in nid_node_map:
    raise ValueError(f'statement node id {node_id} not found in source AST')
  node = nid_node_map[node_id]
  return node


def _append_standard_rules_to_ruleset(
  current_ruleset: p_ruleset.Ruleset,
  learned_rule_strs: List[str],
  stat_nid: int,
  simple_ntext: str,
) -> int:
  '''
  Add learned standard rules to the end of the ruleset.
  RETURN number of rules actually added.
  '''
  added = 0
  for rule_str in learned_rule_strs:
    rule_parsed = p_ruleset.TRuleBase.parse_rule_str(rule_str)
    rule = p_ruleset.StandardTRule(rule_parsed, stat_nid, simple_ntext)
    if current_ruleset.get_rule_ref(rule) is not None:
      logger.debug(f'skipping duplicate rule:\n{rule}')
      continue
    current_ruleset.append_rule(rule)
    added += 1
  return added


def _can_translate(
  src_code: str,
  src_lang: str,
  tar_lang: str,
  translation_rules: str,
  auto_backward: bool,
  choices: dict
) -> Optional[dict]:
  '''
  Check if we can get a translation for the given source code.
  RETURN None if translation is successful, otherwise return templates_dict.
  RAISE BypassStaRuleLearningError when translation search exhausts alternatives
  (NormalException), so caller can enter recovery flow directly.
  '''
  try:
    _ = duoglot_translate_wrapper(
      src_code, src_lang, tar_lang, translation_rules, auto_backward, choices)
    return None
  except d_grammar_expand.TranslationRuleNotFoundException as exc:
    templates_dict = exc.get_templates_dict()
    return templates_dict
  except d_grammar_expand.NormalException as exc:
    logger.warning(
      '_can_translate: NormalException during precheck '
      f'(auto_backward exhausted): {exc}. '
      'Bypassing standard learning and entering recovery flow.')
    raise BypassStaRuleLearningError from exc


def duoglot_translate_wrapper(
  src_code: str,
  src_lang: str,
  tar_lang: str,
  trans_rules: str,
  auto_backward: bool = True,
  choices: dict = {'type': 'ASTNODE', 'choices_list': []},
  **kwargs
) -> dict:
  '''
  Wrapper around DuoGlot's `grammar_expand.TransSession.get_translation()`.
  RAISE Propagate all exceptions to the caller.
  RETURN a dict containing all the relevant information about the target program.

  kwargs:
  - skip_template_extraction: bool, optional, default is False
  '''

  p_utils.log_json_time(f'args-duoglot_translate_wrapper.json', locals())

  assert src_code.isascii()
  assert choices['type'] in ['STEP', 'ASTNODE'], 'Unknown choices type'
  slot_dedup_enabled = choices['type'] == 'ASTNODE'

  tms_begin = p_utils.current_time_msec()
  translator = p_translators.get_translator_cached(
    src_code,
    src_lang,
    tar_lang,
    trans_rules,
    slot_dedup_enabled
  )
  tms_after_get_translator = p_utils.current_time_msec()

  # uncomment when necessary
  # p_utils.write_json(p_consts.SRC_DIR / 'asrc_ast.json', translator.source_ast)
  # p_utils.write_text(p_consts.SRC_DIR / 'atrans_rules.snart', trans_rules)
  # p_utils.write_json(p_consts.SRC_DIR / 'achoices.json', choices)

  # NOTE raises all sorts of exceptions (check docs)
  # If there are no raised exceptions, it means that the translation was successful.
  tar_ast, dbg_history = translator.get_translation(choices, auto_backward, **kwargs)
  tms_after_translate = p_utils.current_time_msec()

  logger.debug(f'SUCCESS DuoGlot translation is successful!')
  tar_code, map_to_exid = d_ast_pretty.ast_to_code(tar_ast, tar_lang)
  tms_after_codegen = p_utils.current_time_msec()
  logger.debug(
    'duoglot timings: '
    f'get_translator={tms_after_get_translator - tms_begin}ms, '
    f'translate={tms_after_translate - tms_after_get_translator}ms, '
    f'ast_to_code={tms_after_codegen - tms_after_translate}ms, '
    f'total={tms_after_codegen - tms_begin}ms')
  return {
    'src_ast': translator.source_ast,
    'src_ann': translator.source_ann,
    'tar_ast': tar_ast,
    'tar_code': tar_code,
    'map_to_exid': map_to_exid,
    'dbg_history': dbg_history,
  }


async def learn_trans_rules_from_snippet(
  snippet: str,
  src_lang: str,
  tar_lang: str,
  ruleset_str: str,
  subject_name: str,
  lrule_learn_snp: Optional[ptlog.RuleLearnSnp] = None,
  allow_existing_ruleset_translation: bool = False,
) -> List[str]:
  '''
  Learn translation rules from a code snippet.
  PARAM ruleset_str: ruleset that cannot translate the snippet.

  NOTE This function is almost identical to learn_trans_rules_for_prob_node
  TODO refactor to reduce code duplication?
  '''
  p_utils.log_json_time(f'args-learn_trans_rules_from_snippet.json', locals())
  assert Config.generator == 'lightweight', 'only lightweight generator is supported here'

  lrule_learn_snp = lrule_learn_snp or ptlog.RuleLearnSnp()
  lrule_learn_snp.snippet = snippet
  lrule_learn_snp.stms = p_utils.current_time_msec()

  # Keep original intent for expression snippets: learn under artificial return context.
  # Reason: expression-level snippets produce tighter problematic-node patterns than
  # statement-level learning, which was the original design.
  # For non-expression snippets (e.g. assignments), fall back to statement-level learning.
  # Reason: wrapping a statement with `return {}` changes semantics and can generate
  # mismatched TSPs such as `return var1.var2`.
  if not p_utils.does_have_parse_error(snippet, src_lang):
    tree = pds.DuoGlotTree.from_code_str(snippet, src_lang)
    root_node = tree.get_root_node()
    assert len(root_node.get_children()) == 1, 'snippet must contain exactly one context node'
    context_node = root_node.get_children()[0]

    if context_node.get_ts_node_type() == 'expression_statement' and len(context_node.get_children()) == 1:
      prob_node = context_node.get_children()[0]
      artif_template_origin = p_generator_lw.ARTIF_CTX_TEMPLATE.format(snippet)
      if p_utils.does_have_parse_error(artif_template_origin, src_lang):
        artif_template_origin = snippet
        artif_tree = pds.DuoGlotTree.from_code_str(artif_template_origin, src_lang)
        assert len(artif_tree.root_node.get_children()) == 1
        artif_ctx_node = artif_tree.root_node.get_children()[0]
        artif_prob_path = context_node.get_path_to_child(prob_node)
      else:
        artif_tree = pds.DuoGlotTree.from_code_str(artif_template_origin, src_lang)
        assert len(artif_tree.root_node.get_children()) == 1
        artif_ctx_node = artif_tree.root_node.get_children()[0]
        artif_prob_node = artif_ctx_node.get_child_by_path(p_generator_lw.ARTIF_PROB_NPATH)
        assert prob_node.is_similar_to_rec(artif_prob_node), \
          'PRE broken: problematic node under artificial context is not similar to source problematic node'
        artif_prob_path = p_generator_lw.ARTIF_PROB_NPATH
    else:
      artif_template_origin = snippet
      artif_tree = pds.DuoGlotTree.from_code_str(artif_template_origin, src_lang)
      assert len(artif_tree.root_node.get_children()) == 1
      artif_ctx_node = artif_tree.root_node.get_children()[0]
      artif_prob_path = []
  else:
    # Parse-failure snippets are likely expression fragments; try artificial return context.
    artif_template_origin = p_generator_lw.ARTIF_CTX_TEMPLATE.format(snippet)
    if p_utils.does_have_parse_error(artif_template_origin, src_lang):
      raise NoTSPsGeneratedError(
        'Could not parse snippet both as-is and under artificial return context')
    artif_tree = pds.DuoGlotTree.from_code_str(artif_template_origin, src_lang)
    assert len(artif_tree.root_node.get_children()) == 1
    artif_ctx_node = artif_tree.root_node.get_children()[0]
    artif_prob_path = p_generator_lw.ARTIF_PROB_NPATH

  template_dict = {
    'template_id': 1,
    'template_origin': artif_template_origin,
    'src_lang': src_lang,
    'tar_lang': tar_lang,
    'context_node_type': artif_ctx_node.get_ts_node_type(),
    'context_node_id': artif_ctx_node.get_id(),
    'problematic_node_path': artif_prob_path,
    'is_valid_template': True,
    'is_insert_secret_fn': False,
  }

  # generate TSPs
  tsps, template_dict = p_generator_lw.generate_tsps_lightweight(template_dict)
  if len(tsps) == 0:
    lrule_learn_snp.success = False
    lrule_learn_snp.reason = 'Could not generate any TSPs'
    lrule_learn_snp.etms = p_utils.current_time_msec()
    raise NoTSPsGeneratedError('Could not generate any TSPs')
  p_utils.log_json_time(f'TSPs-generated.json', tsps)

  # create subject for snippet-based learning
  subject = _create_subject_for_snippet_learn(
    artif_template_origin, src_lang, tar_lang, subject_name)

  # iterate over TSPs
  num_useful_tsps = 0
  num_skipped_tsps = 0
  all_trules_list : List[str] = []

  for tsp_idx, tsp in enumerate(tsps, start=1):
    logger.debug(
      f'learn-prob: learning translation rules using TSP ({tsp_idx}/{len(tsps)}):\n'
      f'tsp.id = {tsp_idx}\n{json.dumps(tsp, indent=2)}')

    ltsp = ptlog.TSP()
    ltsp.id = tsp_idx
    ltsp.sp1 = tsp[0]
    ltsp.sp2 = tsp[1]
    lrule_learn_snp.tsps.append(ltsp)

    trules_list = await learn_trans_rules_from_tsp_with_retries(
      tsp,
      template_dict,
      subject,
      ruleset_str,
      ltsp,
      allow_existing_ruleset_translation=allow_existing_ruleset_translation,
    )
    all_trules_list.extend(trules_list)

    if len(trules_list) == 0:
      logger.warning(
        f'learn-prob: no translation rules were learnt from TSP '
        f'(tsp.id = {tsp_idx}):\n{json.dumps(tsp, indent=2)}')
      num_skipped_tsps += 1
    else:
      num_useful_tsps += 1

    if num_skipped_tsps >= p_consts.MAX_NUM_SKIPPED_TSPS:
      logger.debug('learn-prob: too many skipped TSPs, stopping.')
      break
    if num_useful_tsps >= p_consts.MAX_NUM_USEFUL_TSPS:
      logger.debug('learn-prob: enough useful TSPs, stopping.')
      break

  if len(all_trules_list) > 0:
    lrule_learn_snp.success = True
    lrule_learn_snp.etms = p_utils.current_time_msec()
    logger.debug(f'learn-prob: learned {len(all_trules_list)} translation rules.')
    return all_trules_list

  msg = (
    f'Could not learn any translation rules to translate '
    f'the problematic node with any of the {len(tsps)} TSPs. '
    f'problematic_node_type = "{template_dict["problematic_node_type"]}". '
    f'len(tsps) = {len(tsps)}')
  logger.warning(msg)
  lrule_learn_snp.success = False
  lrule_learn_snp.reason = msg
  lrule_learn_snp.etms = p_utils.current_time_msec()
  raise ProbNode_NoTRule_AllTSPsExhaustedError(msg)


async def learn_trans_rules_from_tsp(
  tsp: Tuple[str, str],
  template_dict: dict,
  subject: p_subject.PirelSubject,
  current_ruleset_str: str,
  ltrule_learn_attempt: Optional[ptlog.TRuleLearnAttempt] = None,
  allow_existing_ruleset_translation: bool = False,
) -> List[str]:
  '''
  RETURN All possible valid translation rules inferred from all possible translations of `tsp`.
  RAISE `TSP_NoTRuleLearnedError` if no translation rules were learned from TSP.

  NOTE subject must contain the following attributes:
  - name
  - src_lang
  - tar_lang
  - get_src_main_code()
  - auto_backward
  - choices
  '''

  p_utils.log_json_time(f'args-learn_trans_rules_from_tsp.json', locals())
  logger.debug(
    f'learn-tsp: starting p.pirel.learn_trans_rules_from_tsp:\n'
    f'{json.dumps({"tsp": tsp}, indent=2)}')

  ltrule_learn_attempt = ltrule_learn_attempt or ptlog.TRuleLearnAttempt()
  ltrule_learn_attempt.stms = p_utils.current_time_msec()

  # TRANSLATE TSP TO GET {SP1-TP1, SP2-TP2} (TRANSLATION PAIR)
  lpllm_gen_log = ptlog.PLLMGenLog()
  ltrule_learn_attempt.p_llm_gen_log = lpllm_gen_log
  translation_pairs = await p_llm_gen.get_translation_pairs_from_tsp_less_llm(subject, tsp, template_dict, lpllm_gen_log)
  assert len(translation_pairs) > 0, 'sanity check: translation_pairs must not be empty'

  # INFER TRANSLATION RULES FROM TRANSLATION PAIRS
  lprule_inf_log = ptlog.PRuleInfLog()
  ltrule_learn_attempt.p_rule_inferencer_log = lprule_inf_log
  trules_list = p_rule_inferencer.infer_translation_rules(template_dict, translation_pairs, lprule_inf_log)

  # CHECK TRANSLATION RULES
  lprule_filter_log = ptlog.PRuleFilterLog()
  ltrule_learn_attempt.p_rule_filter_log = lprule_filter_log
  checked_trules_list = p_rule_validator.filter_translation_rules(
    trules_list,
    subject,
    current_ruleset_str,
    lprule_filter_log,
    allow_existing_ruleset_translation=allow_existing_ruleset_translation,
  )

  if len(checked_trules_list) == 0:
    logger.warning('learn-tsp: no translation rules were learned from TSP.')
    ltrule_learn_attempt.success = False
    ltrule_learn_attempt.reason = 'No translation rules were learned from TSP.'
    ltrule_learn_attempt.etms = p_utils.current_time_msec()
    raise TSP_NoTRuleLearnedError('No translation rules were learned from TSP.')

  ltrule_learn_attempt.success = True
  ltrule_learn_attempt.etms = p_utils.current_time_msec()
  logger.debug(f'learn-tsp: learned {len(checked_trules_list)} translation rules from TSP.')
  return checked_trules_list


async def learn_trans_rules_from_tsp_with_retries(
  tsp: Tuple[str, str],
  template_dict: dict,
  subject: p_subject.PirelSubject,
  current_ruleset_str: str,
  ltsp: Optional[ptlog.TSP] = None,
  allow_existing_ruleset_translation: bool = False,
) -> List[str]:
  '''
  RETURN All possible translation rules inferred from all possible translations of `tsp`.
  NOTE may return zero translation rules

  subject must contain the following attributes:
  - name
  - src_lang
  - tar_lang
  - get_src_main_code()
  - auto_backward
  - choices
  '''

  ltsp = ltsp or ptlog.TSP()
  ltsp.stms = p_utils.current_time_msec()

  attempt_count = 0
  while attempt_count < p_consts.TSP_NUM_ATTEMPTS:
    attempt_count += 1

    logger.debug(f'learn-tsp: attempting to learn some translation rules from a TSP #{attempt_count}')
    ltrule_learn_attempt = ptlog.TRuleLearnAttempt()
    ltrule_learn_attempt.id = attempt_count
    ltsp.trule_learn_attempts.append(ltrule_learn_attempt)

    try:
      trules_list = await learn_trans_rules_from_tsp(
        tsp,
        template_dict,
        subject,
        current_ruleset_str,
        ltrule_learn_attempt,
        allow_existing_ruleset_translation=allow_existing_ruleset_translation,
      )
      ltsp.success = True
      ltsp.etms = p_utils.current_time_msec()
      return trules_list

    except p_llm_gen.NoTransPairsFromTSPError as err:
      logger.warning('Attempt to learn translation rules from TSP failed')

    except TSP_NoTRuleLearnedError as err:
      logger.warning('Attempt to learn translation rules from TSP failed')

  msg = f'No trans rules learned from TSP after {p_consts.TSP_NUM_ATTEMPTS} attempts.'
  logger.warning(msg)
  ltsp.success = False
  ltsp.reason = msg
  ltsp.etms = p_utils.current_time_msec()
  return []


async def learn_trans_rules_for_prob_node(
  subject: p_subject.PirelSubject,
  current_ruleset_str: str,
  templates_dict: dict,
  lnode_trans_iter: Optional[ptlog.NodeTransIter] = None
) -> List[str]:
  '''
  Run PiREL translation rule learning module for a problematic node.
  PRE There is a translation error.
  RETURN [translation_rules]
  RAISE `ProbNode_NoTRule_AllTSPsExhaustedError` if couldn't learn a translation rule.
  Our goal is to never raise this error

  NOTE subject must contain the following attributes:
  - name
  - src_lang
  - tar_lang
  - get_src_main_code()
  - auto_backward
  - choices
  '''

  logger.debug(f'learn-prob: starting rule learning for a problematic node.')
  p_utils.log_json_time(f'args-learn_trans_rules_for_prob_node.json', locals())

  lnode_trans_iter = lnode_trans_iter or ptlog.NodeTransIter()
  lnode_trans_iter.stms = p_utils.current_time_msec()

  # ~~~ initialize template_dict and TSPs
  if Config.generator == 'default':
    template_dict = _init_template_dict(subject, current_ruleset_str, templates_dict)
    tsps = _init_tsps(template_dict)
  elif Config.generator == 'lightweight':
    _valid_template_idx = p_utils.to_int(templates_dict['num_templates']) - 1
    template_dict = templates_dict.get(_valid_template_idx) or templates_dict.get(str(_valid_template_idx))
    tsps, template_dict = p_generator_lw.generate_tsps_lightweight(template_dict)
    if len(tsps) == 0:
      lnode_trans_iter.success = False
      lnode_trans_iter.reason = 'Could not generate any TSPs'
      lnode_trans_iter.etms = p_utils.current_time_msec()
      raise NoTSPsGeneratedError('Could not generate any TSPs')
    p_utils.log_json_time(f'TSPs-generated.json', tsps)
  else:
    raise ValueError(f'Unknown generator: {Config.generator}')

  lnode_trans_iter.node_id = template_dict['problematic_node_id']
  lnode_trans_iter.node_type = template_dict['problematic_node_type']
  lnode_trans_iter.template_origin = template_dict['template_origin']

  # ~~~ iterate over TSPs (from abstract to concrete)
  num_useful_tsps = 0
  num_skipped_tsps = 0
  all_trules_list : List[str] = []

  for tsp_idx, tsp in enumerate(tsps, start=1):
    logger.debug(
      f'learn-prob: learning translation rules using TSP ({tsp_idx}/{len(tsps)}):\n'
      f'tsp.id = {tsp_idx}\n{json.dumps(tsp, indent=2)}')

    ltsp = ptlog.TSP()
    ltsp.id = tsp_idx
    ltsp.sp1 = tsp[0]
    ltsp.sp2 = tsp[1]
    lnode_trans_iter.tsps.append(ltsp)

    trules_list = await learn_trans_rules_from_tsp_with_retries(
      tsp, template_dict, subject, current_ruleset_str, ltsp)
    all_trules_list.extend(trules_list)

    if len(trules_list) == 0:
      logger.warning(
        f'learn-prob: no translation rules were learnt from TSP '
        f'(tsp.id = {tsp_idx}):\n{json.dumps(tsp, indent=2)}')
      num_skipped_tsps += 1
    else:
      num_useful_tsps += 1

    if num_skipped_tsps >= p_consts.MAX_NUM_SKIPPED_TSPS:
      logger.debug('learn-prob: too many skipped TSPs, stopping.')
      break
    if num_useful_tsps >= p_consts.MAX_NUM_USEFUL_TSPS:
      logger.debug('learn-prob: enough useful TSPs, stopping.')
      break

  if len(all_trules_list) > 0:
    lnode_trans_iter.success = True
    lnode_trans_iter.etms = p_utils.current_time_msec()
    logger.debug(f'learn-prob: learned {len(all_trules_list)} translation rules.')
    return all_trules_list

  msg = (
    f'Could not learn any translation rules to translate '
    f'the problematic node with any of the {len(tsps)} TSPs. '
    f'problematic_node_type = "{template_dict["problematic_node_type"]}". '
    f'len(tsps) = {len(tsps)}')
  logger.warning(msg)
  lnode_trans_iter.success = False
  lnode_trans_iter.reason = msg
  lnode_trans_iter.etms = p_utils.current_time_msec()
  raise ProbNode_NoTRule_AllTSPsExhaustedError(msg)


async def stat_node_learn_trules_recovery(
  simple_ntext: str,
  src_lang: str,
  tar_lang: str,
  lrule_learn_rec: Optional[ptlog.RuleLearnRec] = None,
) -> List[str]:
  '''
  Learn an overfitted rule to translate the statement node as a
  measure to recover from the internal validation failure.
  '''
  p_utils.log_json_time(f'args-stat_node_learn_trules_recovery.json', locals())
  logger.info('Starting statement node translation rule learning (RECOVERY)')
  logger.debug(
    f'--stat-learn-rec--: will learn an overfitted rule '
    f'to translate the statement:\n{simple_ntext}')
  lrule_learn_rec = lrule_learn_rec or ptlog.RuleLearnRec()
  lrule_learn_rec.stms = p_utils.current_time_msec()

  def _synthesize_context(simple_ntext: str, src_lang: str) -> dict:
    tree = pds.DuoGlotTree.from_code_str(simple_ntext, src_lang)
    root_node = tree.get_root_node()
    assert len(root_node.get_children()) == 1, 'root node should have a single child'
    context_node = root_node.get_children()[0]
    return {
      'source_context': [[context_node.get_type()]],
      'target_context': [['unknown']]
    }

  simple_ntext_wsec = pvpy.BlockSecretFunInserter.insert_secret_functions(simple_ntext)
  if simple_ntext != simple_ntext_wsec:
    simple_ntext = simple_ntext_wsec
    logger.debug(f'Inserted secret function invocation:\n{simple_ntext}')

  reference_translations = _get_direct_ref_translations_re_compile_assignment(
    simple_ntext, tar_lang)
  if reference_translations:
    now = p_utils.current_time_msec()
    lget_ref_trans = ptlog.GetRefTrans(
      statement_str=simple_ntext,
      ref_translations=reference_translations,
      stms=now,
      etms=now,
      success=True)
    logger.info(
      'Using direct deterministic recovery reference translation '
      'for re.compile() assignment.')
  else:
    reference_translations, lget_ref_trans = \
      await p_llm_gen.get_reference_translations(
        simple_ntext,
        src_lang,
        tar_lang,
      )

  lrule_learn_rec.get_ref_trans = lget_ref_trans

  def _remove_js_comments_best_effort(js_code: str, label: str) -> str:
    try:
      return pvjs.CommentsRemover.remove_comments(js_code)
    except Exception as err:
      logger.debug(
        '--stat-learn-rec--: failed to remove comments for '
        f'{label}; using raw snippet. reason={repr(err)}'
      )
      return js_code

  def _is_incomplete_js_header_snippet(js_code: str) -> bool:
    snippet = js_code.strip()
    if snippet == '':
      return False
    if snippet.startswith('}'):
      snippet = snippet[1:].lstrip()
    return bool(
      snippet.endswith('{') and
      re.match(r'^(?:if|else\s+if|else|for|while|try|catch|finally|with|switch)\b', snippet)
    )


  if len(reference_translations) == 0:
    msg = 'No reference translations were generated for the statement node'
    logger.error(msg)
    lrule_learn_rec.success = False
    lrule_learn_rec.reason = msg
    lrule_learn_rec.etms = p_utils.current_time_msec()
    raise CouldNotGenRefTranslationsError(msg)

  normalized_reference_translations: List[str] = []
  for idx, ref_trans in enumerate(reference_translations, start=1):
    cleaned_ref_trans = _remove_js_comments_best_effort(
      ref_trans,
      label=f'reference_translations[{idx}]',
    ).strip()
    if cleaned_ref_trans == '':
      continue
    if _is_incomplete_js_header_snippet(cleaned_ref_trans):
      logger.debug(
        '--stat-learn-rec--: skipped incomplete recovery reference translation: '
        f'{repr(cleaned_ref_trans)}'
      )
      continue
    normalized_reference_translations.append(cleaned_ref_trans)

  if len(normalized_reference_translations) == 0:
    msg = 'No valid reference translations remain after recovery normalization'
    logger.error(msg)
    lrule_learn_rec.success = False
    lrule_learn_rec.reason = msg
    lrule_learn_rec.etms = p_utils.current_time_msec()
    raise CouldNotGenRefTranslationsError(msg)

  context = _synthesize_context(simple_ntext, src_lang)
  overfitted_trules : List[str] = []
  for idx, ref_trans in enumerate(normalized_reference_translations, start=1):
    try:
      trule = p_rule_inferencer.infer_translation_rule_wrapper(
        translation_pair=[{'source': simple_ntext, 'target': ref_trans}],
        src_lang=src_lang,
        tar_lang=tar_lang,
        context=context,
        is_insert_secret_fn=(p_consts.GENERIC_SECRET_FN in simple_ntext),
        choose_largest_node=True,
        is_ignore_semicolon=False
      )
    except Exception as err:
      logger.warning(
        f'Failed to infer a translation rule from reference translation #{idx} '
        f'during recovery. reason={repr(err)}. reference translation:\n{ref_trans}\n'
        'This reference translation will be skipped for recovery.'
      )
      continue
    logger.debug(
      f'--stat-learn-rec--: Learned translation rule '
      f'{idx}/{len(normalized_reference_translations)}:\n{trule}')
    overfitted_trules.append(trule)

  if len(overfitted_trules) == 0:
    msg = 'Could not infer any translation rules from the reference translations for recovery'
    logger.error(msg)
    lrule_learn_rec.success = False
    lrule_learn_rec.reason = msg
    lrule_learn_rec.etms = p_utils.current_time_msec()
    raise CouldNotGenRefTranslationsError(msg)

  lrule_learn_rec.success = True
  lrule_learn_rec.etms = p_utils.current_time_msec()

  return overfitted_trules


async def stat_node_learn_trules_standard(
  simple_ntext: str,
  simple_nchoices: dict,
  stat_learn_subject: p_subject.PirelSubject,
  current_ruleset: p_ruleset.Ruleset,
  lrule_learn_std: Optional[ptlog.RuleLearnStd] = None
) -> List[str]:
  '''
  A standard way of learning translation rules, where we
  stumble upon a problematic node given some choices,
  and learn translation rule(s) that translate that node.
  The rules returned by this function are validated only
  for syntactic correctness, not for semantic correctness.

  NOTE subject must contain the following attributes:
  - name
  - src_lang
  - tar_lang
  - get_src_main_code()
  - auto_backward
  - choices
  '''

  logger.info('~~ Starting statement node translation rule learning (STANDARD)')
  lrule_learn_std = lrule_learn_std or ptlog.RuleLearnStd()
  lrule_learn_std.stms = p_utils.current_time_msec()

  _MAX_NUM_ITERS = 50
  new_learned_trules : List[str] = []
  iter_counter = 0

  while iter_counter < _MAX_NUM_ITERS:
    iter_counter += 1
    logger.debug(f'--stat-learn-sta--: rule learn loop (STANDARD) iteration #{iter_counter}')

    lnode_trans_iter = ptlog.NodeTransIter()
    lnode_trans_iter.id = iter_counter
    lrule_learn_std.node_trans_iters.append(lnode_trans_iter)

    templates_dict = _can_translate(
      simple_ntext,
      stat_learn_subject.src_lang,
      stat_learn_subject.tar_lang,
      '\n\n'.join(new_learned_trules) + '\n\n' + current_ruleset.to_str_ruleset(),
      stat_learn_subject.auto_backward,
      simple_nchoices
    )
    if templates_dict is None:
      logger.info('SUCCESS Learned rules to translate statement node (translation successful)')
      logger.debug(f'--stat-learn-sta--: Learned translation rules:\n' + '\n'.join(new_learned_trules))

      lrule_learn_std.success = True
      lrule_learn_std.etms = p_utils.current_time_msec()

      return new_learned_trules

    '''
    At this point we have a problematic node that we cannot translate.
    We need to learn translation rules for this node.
    '''
    trules_list = await learn_trans_rules_for_prob_node(
      stat_learn_subject,
      '\n\n'.join(new_learned_trules) + '\n\n' + current_ruleset.to_str_ruleset(),
      templates_dict,
      lnode_trans_iter
    )

    logger.debug(f'--stat-learn-sta--: appending {len(trules_list)} new translation rules.')
    for trule in trules_list:
      logger.debug(trule)
      new_learned_trules.append(trule)

  lrule_learn_std.success = False
  lrule_learn_std.reason = f'Hit max iterations: {_MAX_NUM_ITERS}'
  lrule_learn_std.etms = p_utils.current_time_msec()

  raise RuntimeError('stat_node_learn_trules_standard: hit max iterations')


async def stat_node_validate_trules(
  simple_nchoices: dict,
  simple_ntext: str,
  stat_learn_subject: p_subject.PirelSubject,
  stat_val_subject: p_subject.PirelSubject,
  current_ruleset: p_ruleset.Ruleset,
  lstat_node_val: Optional[ptlog.StatNodeVal] = None,
  validation_mode: str = _STAT_NODE_VALIDATION_MODE_FULL,
  skip_problematic_node_precheck: bool = False,
) -> Tuple[str, List[dict]]:
  '''
  Return silently if
  1. there are enough rules to translate the statement node
  2. the learned rules pass internal validation

  Raise or propagate exceptions otherwise.
  '''

  p_utils.log_json_time(f'args-stat_node_validate_trules.json', locals())
  logger.info('Starting statement node translation rule validation')
  lstat_node_val = lstat_node_val or ptlog.StatNodeVal()
  lstat_node_val.stms = p_utils.current_time_msec()

  # 1. check for problematic nodes in the statement node
  if skip_problematic_node_precheck:
    logger.debug('--stat-val--: skipping problematic-node precheck (forced)')
    lstat_node_val.v1_enough_rules = True
  else:
    templates_dict = _can_translate(
      simple_ntext,
      stat_learn_subject.src_lang,
      stat_learn_subject.tar_lang,
      current_ruleset.to_str_ruleset(),
      stat_learn_subject.auto_backward,
      simple_nchoices
    )
    if templates_dict is not None:
      lstat_node_val.v1_enough_rules = False
      if _check_needs_rec_rule_learning_directly(templates_dict):
        raise BypassStaRuleLearningError
      raise _ValidationError_ProblematicNodeExists(templates_dict)
    logger.debug('GOOD Statement node has no problematic nodes with current choices.')
    lstat_node_val.v1_enough_rules = True

  if validation_mode == _STAT_NODE_VALIDATION_MODE_QUICK:
    # Fast path for iterative search: only ensure the statement is translatable.
    lstat_node_val.success = True
    lstat_node_val.etms = p_utils.current_time_msec()
    logger.debug('--stat-val--: quick validation succeeded (translation coverage only)')
    return '', []
  if validation_mode != _STAT_NODE_VALIDATION_MODE_FULL:
    raise ValueError(f'Unsupported validation mode: {validation_mode}')

  # 2. perform internal validation
  '''
  Run test-based rule validation to validate the learned translation rules
  that translate the statement node. This invocation has a call to
  p_rule_applicator.apply_translation_rules() that checks all possible
  translation rule combinations that result in a plausible translation
  of the source test script using the learned translation rules.
  '''
  tar_program_plausible, translate_dbg_history = await p_rule_validator.stat_node_validate_trules_test_based(
    stat_val_subject,
    current_ruleset,
    simple_ntext,
    lstat_node_val,
  )

  lstat_node_val.success = True
  lstat_node_val.etms = p_utils.current_time_msec()
  logger.debug('--stat-val--: finished internal validation successfully')
  return tar_program_plausible, translate_dbg_history


def should_learn_overfitted_rule(simple_ntext: str, stat_nid: int, subject_name: str) -> bool:
  '''
  Check subject config and return whether we should learn an overfitted rule directly without validation.
  '''
  config_fpath = p_consts.SKEL_BENCHMARK_DIR / f'{subject_name}-config.json'
  if not config_fpath.exists():
    logger.warning(f'Config file {config_fpath} does not exist. Will not learn overfitted rules directly.')
    return False
  subject_config = p_utils.read_json(config_fpath)

  # these assertions may be removed later
  # forcing them now to not forget that they exist
  assert 'learn_overfitted_rules_simple_ntexts' in subject_config, 'Config file must contain "learn_overfitted_rules_simple_ntexts".'
  assert 'learn_overfitted_rules_stat_nids' in subject_config, 'Config file must contain "learn_overfitted_rules_stat_nids".'

  # first, check simple_ntext match
  if 'learn_overfitted_rules_simple_ntexts' in subject_config:
    learn_overfitted_rules_simple_ntexts = subject_config['learn_overfitted_rules_simple_ntexts']
    first_line = simple_ntext.strip().splitlines()[0] if simple_ntext.strip() != '' else ''
    if first_line in learn_overfitted_rules_simple_ntexts:
      logger.debug(f'Statement node with simple_ntext {repr(simple_ntext)} is configured for learning overfitted rules directly without validation.')
      return True
  else:
    logger.warning(f'Config file {config_fpath} does not contain "learn_overfitted_rules_simple_ntexts". Will not learn overfitted rules directly based on simple_ntext match.')

  # second, check stat_nid match
  if 'learn_overfitted_rules_stat_nids' in subject_config:
    learn_overfitted_rules_stat_nids = subject_config['learn_overfitted_rules_stat_nids']
    if stat_nid in learn_overfitted_rules_stat_nids:
      logger.debug(f'Statement node {stat_nid} is configured for learning overfitted rules directly without validation.')
      return True
  else:
    logger.warning(f'Config file {config_fpath} does not contain "learn_overfitted_rules_stat_nids". Will not learn overfitted rules directly based on stat_nid match.')

  return False


async def stat_node_main_learn_validate_trules(
  main_subject: p_subject.PirelSubject,
  current_ruleset: p_ruleset.Ruleset,  # starting ruleset + learned rules so far
  stat_nid: int,
  nid_blacklist: list[int],
  lstat_node: Optional[ptlog.StatNode] = None,
  simple_ntext_override: Optional[str] = None,
  nid_text_overrides: Optional[Dict[int, str]] = None,
):
  '''
  Validate current translation rules for the statement node,
  and learn new translation rules based on validation errors.
  NOTE adds new translation rules to the current_ruleset.
  '''
  p_utils.log_json_time(f'args-stat_node_main_learn_validate_trules.json', locals())
  src_main_code = main_subject.get_src_main_code()
  src_lang = main_subject.src_lang

  stat_node = _get_statement_node_by_id(src_main_code, src_lang, stat_nid)
  simple_ntext = simple_ntext_override
  if simple_ntext is None:
    simple_ntext = _simplify_comp_stat_node_text(stat_node, src_main_code)
  pre_context = get_pre_context(src_main_code, src_lang,
                                main_subject.is_three_split,
                                stat_nid, nid_blacklist,
                                nid_text_overrides=nid_text_overrides)
  simple_nchoices = {'type': 'ASTNODE', 'choices_list': []}
  snippet_learn_counter = {}

  lstat_node = lstat_node or ptlog.StatNode()
  lstat_node.stms = p_utils.current_time_msec()
  lstat_node.node_id = stat_nid
  lstat_node.node_text = _get_statement_node_text(stat_node, src_main_code)
  lstat_node.pre_context = pre_context
  lstat_node.simple_ntext = simple_ntext

  logger.debug(
    f'--stat-main--: statement node (nid={stat_nid}): '
    f'Starting rule learning and validation for statement node:\n{simple_ntext}')
  p_utils.log_file_time(f'pre_context.{src_lang}', pre_context)

  _MAX_NUM_ITERS = 4
  iter_counter = 0
  should_run_final_validation = False
  while iter_counter < _MAX_NUM_ITERS:
    iter_counter += 1
    logger.debug(
      f'--stat-main--: statement node (nid={stat_nid}): '
      f'main validate-learn loop iteration #{iter_counter}')

    lstat_node_val = ptlog.StatNodeVal()
    lstat_node.val_learn_iters.append(lstat_node_val)

    stat_learn_subject = _create_subject_for_stat_learn(
      main_subject, simple_ntext, current_ruleset, simple_nchoices)
    iter_learned_sta_trules : List[str] = []
    iter_learned_rec_trules : List[str] = []

    if should_learn_overfitted_rule(simple_ntext, stat_nid, main_subject.name):
      logger.debug(f'--stat-main--: statement node (nid={stat_nid}): learning overfitted rules directly')
      lstat_node_val.success = None
      lstat_node_val.reason = 'Learning overfitted rules directly (without validation)'
      lstat_node_val.etms = p_utils.current_time_msec()
      lrule_learn_rec = ptlog.RuleLearnRec()
      lstat_node.val_learn_iters.append(lrule_learn_rec)
      iter_learned_rec_trules = await stat_node_learn_trules_recovery(
        simple_ntext,
        stat_learn_subject.src_lang,
        stat_learn_subject.tar_lang,
        lrule_learn_rec,
      )
      for rule_str in reversed(iter_learned_rec_trules):
        if _is_invalid_recovery_rule_for_statement(simple_ntext, rule_str):
          logger.warning(
            '--stat-main--: dropping recovery rule due to invalid assignment->declaration '
            f'pattern for statement nid={stat_nid}, simple_ntext={repr(simple_ntext)}'
          )
          continue
        rule_parsed = p_ruleset.TRuleBase.parse_rule_str(rule_str)
        rule = p_ruleset.StatementOverfittedTRule(rule_parsed, stat_nid, simple_ntext)
        if current_ruleset.get_rule_ref(rule) is not None:
          logger.debug(f'skipping duplicate rule:\n{rule}')
          continue
        current_ruleset.prepend_rule(rule)

    # Learn from matcher fragment first (original behavior), then fall back to
    # full statement only if snippet learning fails.
    # Reason: preserve existing snippet-learning intent while recovering from
    # fragment-only dead ends observed in attribute/member mismatch failures.
    async def _learn_snippet_with_statement_fallback(
      snippet_for_retry: str,
      not_matching_rules_str: str,
      lrule_log: ptlog.RuleLearnSnp,
    ) -> List[str]:
      try:
        return await learn_trans_rules_from_snippet(
          snippet_for_retry,
          stat_learn_subject.src_lang,
          stat_learn_subject.tar_lang,
          not_matching_rules_str,
          stat_learn_subject.name,
          lrule_log,
        )
      except (NoTSPsGeneratedError, ProbNode_NoTRule_AllTSPsExhaustedError):
        if simple_ntext == snippet_for_retry:
          raise
        logger.debug(
          f'--stat-main--: statement node (nid={stat_nid}): '
          f'snippet learning failed on matcher fragment, retrying with full statement:\n'
          f'matcher_fragment={snippet_for_retry}\n'
          f'statement={simple_ntext}')
        return await learn_trans_rules_from_snippet(
          simple_ntext,
          stat_learn_subject.src_lang,
          stat_learn_subject.tar_lang,
          not_matching_rules_str,
          stat_learn_subject.name,
          lrule_log,
        )

    try:
      logger.debug(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'about to start validation of learned rules')
      p_utils.log_file_time(f'learned_rules_so_far.snart', current_ruleset.to_str_ruleset())
      p_utils.log_json_time(f'learned_rules_so_far.json', current_ruleset.to_dict())
      _ = await stat_node_validate_trules(
        simple_nchoices,
        simple_ntext,
        stat_learn_subject,
        stat_learn_subject,
        current_ruleset,
        lstat_node_val,
        validation_mode=_STAT_NODE_VALIDATION_MODE_QUICK,
      )
      logger.debug(
        f'--stat-main--: statement node (nid={stat_nid}): '
        'quick validation succeeded; running final full pre-context validation gate')
      stat_val_subject = _create_subject_for_stat_val(
        main_subject,
        pre_context,
        simple_ntext,
        current_ruleset,
        origin_stat_nid_for_eot=stat_nid,
      )
      tar_program_plausible, translate_dbg_history = await stat_node_validate_trules(
        simple_nchoices,
        simple_ntext,
        stat_learn_subject,
        stat_val_subject,
        current_ruleset,
        lstat_node_val,
        validation_mode=_STAT_NODE_VALIDATION_MODE_FULL,
      )
      logger.info(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'SUCCESS Statement node translation rules validated successfully')
      lstat_node.success = True
      lstat_node.etms = p_utils.current_time_msec()
      _total_stat_ms = lstat_node.etms - lstat_node.stms
      _MAX_MINS = 4
      if _total_stat_ms > _MAX_MINS * 60 * 1000:
        p_utils.email_safely(
          subject=f'{main_subject.name}: statement node {stat_nid} took too long to translate',
          message=(
            f'Statement node {stat_nid} took {_total_stat_ms / 1000:.2f} seconds to validate, '
            f'which exceeds the threshold of {_MAX_MINS} minutes. '
            f'Please check the logs for details.')
        )
      return

    except p_rule_validator.RulesExistNoneValid as err:
      logger.warning(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'RulesExistNoneValid:\n'
        f'Most likely missing a valid rule')

      lstat_node_val.success = False
      lstat_node_val.reason = 'Most likely missing a valid rule'
      lstat_node_val.etms = p_utils.current_time_msec()

      lrule_learn_rec = ptlog.RuleLearnRec()
      lstat_node.val_learn_iters.append(lrule_learn_rec)

      iter_learned_rec_trules = await stat_node_learn_trules_recovery(
        simple_ntext,
        stat_learn_subject.src_lang,
        stat_learn_subject.tar_lang,
        lrule_learn_rec,
      )

    except _ValidationError_ProblematicNodeExists:
      logger.info(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'_ValidationError_ProblematicNodeExists:\n'
        f'There is a node with no translation rules to handle it. '
        f'Will start the STANDARD rule learning procedure.')

      lstat_node_val.success = False
      lstat_node_val.reason = 'There is a node with no translation rules to handle it.'
      lstat_node_val.etms = p_utils.current_time_msec()

      lrule_learn_std = ptlog.RuleLearnStd()
      lstat_node.val_learn_iters.append(lrule_learn_std)

      try:
        iter_learned_sta_trules = await stat_node_learn_trules_standard(
          simple_ntext,
          simple_nchoices,
          stat_learn_subject,
          current_ruleset,
          lrule_learn_std,
        )

      except NoTSPsGeneratedError as err:
        logger.warning(
          f'--stat-main--: statement node (nid={stat_nid}): '
          f'NoTSPsGeneratedError:\n'
          f'No TSPs (two generated snippets in src lang) were generated. '
          f'Will start the RECOVERY rule learning procedure.')

        lrule_learn_std.success = False
        lrule_learn_std.reason = 'No TSPs were generated.'
        lrule_learn_std.etms = p_utils.current_time_msec()

        lrule_learn_rec = ptlog.RuleLearnRec()
        lstat_node.val_learn_iters.append(lrule_learn_rec)

        iter_learned_rec_trules = await stat_node_learn_trules_recovery(
          simple_ntext,
          stat_learn_subject.src_lang,
          stat_learn_subject.tar_lang,
          lrule_learn_rec,
        )

      except ProbNode_NoTRule_AllTSPsExhaustedError as err:
        logger.warning(
          f'--stat-main--: statement node (nid={stat_nid}): '
          f'ProbNode_NoTRule_AllTSPsExhaustedError:\n'
          f'Could not learn any translation rules to translate the problematic node '
          f'with any of the TSPs. Will start the RECOVERY rule learning procedure.')

        lrule_learn_std.success = False
        lrule_learn_std.reason = 'All TSPs used but no translation rules were learned.'
        lrule_learn_std.etms = p_utils.current_time_msec()

        lrule_learn_rec = ptlog.RuleLearnRec()
        lstat_node.val_learn_iters.append(lrule_learn_rec)

        iter_learned_rec_trules = await stat_node_learn_trules_recovery(
          simple_ntext,
          stat_learn_subject.src_lang,
          stat_learn_subject.tar_lang,
          lrule_learn_rec,
        )

      except PartialProgramGenerationError as err:
        logger.warning(
          f'--stat-main--: statement node (nid={stat_nid}): '
          f'PartialProgramGenerationError:\n'
          f'Could not generate a partial program for the statement node. '
          f'Will start the RECOVERY rule learning procedure.')

        lrule_learn_std.success = False
        lrule_learn_std.reason = 'Could not generate a partial program for a node.'
        lrule_learn_std.etms = p_utils.current_time_msec()

        lrule_learn_rec = ptlog.RuleLearnRec()
        lstat_node.val_learn_iters.append(lrule_learn_rec)

        iter_learned_rec_trules = await stat_node_learn_trules_recovery(
          simple_ntext,
          stat_learn_subject.src_lang,
          stat_learn_subject.tar_lang,
          lrule_learn_rec,
        )

    except p_ext_rule_chooser.RuleCombinationsExhaustedError as err:
      logger.warning(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'p_ext_rule_chooser.RuleCombinationsExhaustedError:\n'
        f'No combination of rules leads to a plausible translation. '
        f'Will start the RECOVERY rule learning procedure.')

      lstat_node_val.success = False
      lstat_node_val.reason = 'No combination of rules leads to a plausible translation.'
      lstat_node_val.etms = p_utils.current_time_msec()

      lrule_learn_rec = ptlog.RuleLearnRec()
      lstat_node.val_learn_iters.append(lrule_learn_rec)

      iter_learned_rec_trules = await stat_node_learn_trules_recovery(
        simple_ntext,
        stat_learn_subject.src_lang,
        stat_learn_subject.tar_lang,
        lrule_learn_rec,
      )

    except p_ext_rule_chooser.QueueInfiniteLoopError as err:
      logger.warning(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'p_ext_rule_chooser.QueueInfiniteLoopError:\n'
        f'Cannot obtain a plausible translation of a choicable expression '
        f'due to an infinite loop in the matcher queue. '
        f'Will start the RECOVERY rule learning procedure.')

      lstat_node_val.success = False
      lstat_node_val.reason = 'Infinite loop in the matcher queue.'
      lstat_node_val.etms = p_utils.current_time_msec()

      lrule_learn_rec = ptlog.RuleLearnRec()
      lstat_node.val_learn_iters.append(lrule_learn_rec)

      iter_learned_rec_trules = await stat_node_learn_trules_recovery(
        simple_ntext,
        stat_learn_subject.src_lang,
        stat_learn_subject.tar_lang,
        lrule_learn_rec,
      )

    except p_ext_rule_chooser.AllRulesInMatcherGroupImplausibleError as err:
      logger.warning(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'p_ext_rule_chooser.AllRulesInMatcherGroupImplausibleError:\n'
        f'No rule to plausibly translate a sub-expression. '
        f'Will learn an additional rule by the STANDARD procedure.')

      lstat_node_val.success = False
      lstat_node_val.reason = 'No rule to plausibly translate a sub-expression.'
      lstat_node_val.etms = p_utils.current_time_msec()

      lrule_learn_snp = ptlog.RuleLearnSnp()
      lstat_node.val_learn_iters.append(lrule_learn_snp)

      snippet = err.snippet
      # Keep threshold budget keyed by the original matcher fragment.
      # Reason: fallback retries with full statements should not consume budget
      # as if they were different snippets.
      snippet_counter_key = err.snippet
      snippet_learn_counter[snippet_counter_key] = snippet_learn_counter.get(snippet_counter_key, 0) + 1

      if snippet_learn_counter[snippet_counter_key] < p_consts.SNIPPET_LEARN_THRESHOLD:

        try:
          iter_learned_sta_trules = await _learn_snippet_with_statement_fallback(
            snippet_for_retry=snippet,
            not_matching_rules_str=err.not_matching_rules_str,
            lrule_log=lrule_learn_snp,
          )

        except NoTSPsGeneratedError as err:
          logger.warning(
            f'--stat-main--: statement node (nid={stat_nid}): '
            f'NoTSPsGeneratedError from learn_trans_rules_from_snippet():\n'
            f'No TSPs were generated from snippet learning. '
            f'Will start the RECOVERY rule learning procedure.')

          lrule_learn_snp.success = False
          lrule_learn_snp.reason = 'No TSPs were generated.'
          lrule_learn_snp.etms = p_utils.current_time_sec()

          lrule_learn_rec = ptlog.RuleLearnRec()
          lstat_node.val_learn_iters.append(lrule_learn_rec)

          iter_learned_rec_trules = await stat_node_learn_trules_recovery(
            simple_ntext,
            stat_learn_subject.src_lang,
            stat_learn_subject.tar_lang,
            lrule_learn_rec,
          )

        except ProbNode_NoTRule_AllTSPsExhaustedError as err:
          logger.warning(
            f'--stat-main--: statement node (nid={stat_nid}): '
            f'ProbNode_NoTRule_AllTSPsExhaustedError from learn_trans_rules_from_snippet():\n'
            f'Could not learn any translation rules to translate the problematic node '
            f'with any of the TSPs. Will start the RECOVERY rule learning procedure.')

          lrule_learn_snp.success = False
          lrule_learn_snp.reason = 'All TSPs used but no translation rules were learned.'
          lrule_learn_snp.etms = p_utils.current_time_sec()

          lrule_learn_rec = ptlog.RuleLearnRec()
          lstat_node.val_learn_iters.append(lrule_learn_rec)

          iter_learned_rec_trules = await stat_node_learn_trules_recovery(
            simple_ntext,
            stat_learn_subject.src_lang,
            stat_learn_subject.tar_lang,
            lrule_learn_rec,
          )

      else:
        logger.warning(
          f'--stat-main--: statement node (nid={stat_nid}): '
          f'snippet rule learning hit threshold ({p_consts.SNIPPET_LEARN_THRESHOLD}), '
          f'will start RECOVERY procedure instead:\n{snippet}')

        lrule_learn_snp.success = False
        lrule_learn_snp.reason = 'Budget exhausted for snippet rule learning.'
        lrule_learn_snp.etms = p_utils.current_time_sec()

        lrule_learn_rec = ptlog.RuleLearnRec()
        lstat_node.val_learn_iters.append(lrule_learn_rec)

        iter_learned_rec_trules = await stat_node_learn_trules_recovery(
          simple_ntext,
          stat_learn_subject.src_lang,
          stat_learn_subject.tar_lang,
          lrule_learn_rec,
        )

    except p_ext_rule_chooser.VerifiedRulesExhaustedError as err:
      logger.warning(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'p_ext_rule_chooser.VerifiedRulesExhaustedError:\n'
        'All verified rules were exhausted and no plausible translation found. '
        'Will learn an additional rule by the STANDARD procedure.')

      lstat_node_val.success = False
      lstat_node_val.reason = 'All verified rules were exhausted and no plausible translation found.'
      lstat_node_val.etms = p_utils.current_time_sec()

      lrule_learn_snp = ptlog.RuleLearnSnp()
      lstat_node.val_learn_iters.append(lrule_learn_snp)

      snippet = err.no_choices_snippet
      # Keep threshold budget keyed by the original matcher fragment.
      # Reason: fallback retries with full statements should not consume budget
      # as if they were different snippets.
      snippet_counter_key = err.no_choices_snippet
      snippet_learn_counter[snippet_counter_key] = snippet_learn_counter.get(snippet_counter_key, 0) + 1

      if snippet_learn_counter[snippet_counter_key] < p_consts.SNIPPET_LEARN_THRESHOLD:
        try:
          iter_learned_sta_trules = await _learn_snippet_with_statement_fallback(
            snippet_for_retry=snippet,
            not_matching_rules_str=err.not_matching_rules_str,
            lrule_log=lrule_learn_snp,
          )

        except NoTSPsGeneratedError as err:
          logger.warning(
            f'--stat-main--: statement node (nid={stat_nid}): '
            f'NoTSPsGeneratedError from learn_trans_rules_from_snippet():\n'
            f'No TSPs were generated from snippet learning. '
            f'Will start the RECOVERY rule learning procedure.')

          lrule_learn_snp.success = False
          lrule_learn_snp.reason = 'No TSPs were generated.'
          lrule_learn_snp.etms = p_utils.current_time_sec()

          lrule_learn_rec = ptlog.RuleLearnRec()
          lstat_node.val_learn_iters.append(lrule_learn_rec)

          iter_learned_rec_trules = await stat_node_learn_trules_recovery(
            simple_ntext,
            stat_learn_subject.src_lang,
            stat_learn_subject.tar_lang,
            lrule_learn_rec,
          )

        except ProbNode_NoTRule_AllTSPsExhaustedError as err:
          logger.warning(
            f'--stat-main--: statement node (nid={stat_nid}): '
            f'ProbNode_NoTRule_AllTSPsExhaustedError from learn_trans_rules_from_snippet():\n'
            f'Could not learn any translation rules to translate the problematic node '
            f'with any of the TSPs. Will start the RECOVERY rule learning procedure.')

          lrule_learn_snp.success = False
          lrule_learn_snp.reason = 'All TSPs used but no translation rules were learned.'
          lrule_learn_snp.etms = p_utils.current_time_sec()

          lrule_learn_rec = ptlog.RuleLearnRec()
          lstat_node.val_learn_iters.append(lrule_learn_rec)

          iter_learned_rec_trules = await stat_node_learn_trules_recovery(
            simple_ntext,
            stat_learn_subject.src_lang,
            stat_learn_subject.tar_lang,
            lrule_learn_rec,
          )
      else:
        logger.warning(
          f'--stat-main--: statement node (nid={stat_nid}): '
          f'snippet rule learning hit threshold ({p_consts.SNIPPET_LEARN_THRESHOLD}), '
          f'will start RECOVERY procedure instead:\n{snippet}')

        lrule_learn_rec = ptlog.RuleLearnRec()
        lstat_node.val_learn_iters.append(lrule_learn_rec)

        iter_learned_rec_trules = await stat_node_learn_trules_recovery(
          simple_ntext,
          stat_learn_subject.src_lang,
          stat_learn_subject.tar_lang,
          lrule_learn_rec,
        )

    except prapp.ValidationContextProblematicNodeError as err:
      logger.warning(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'prapp.ValidationContextProblematicNodeError:\n'
        'Validation failed because context code outside the current statement '
        'needs additional translation rules. '
        'Auxiliary context learning is disabled, re-raising.')

      lstat_node_val.success = False
      lstat_node_val.reason = 'Validation context contains a node with no translation rules.'
      lstat_node_val.etms = p_utils.current_time_msec()
      raise err

    except prapp.SrcTestScriptProblematicNodeError as err:
      logger.warning(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'prapp.SrcTestScriptProblematicNodeError:\n'
        f'The source test script has a problematic node. '
        f'Will start the RECOVERY rule learning procedure.')

      lstat_node_val.success = False
      lstat_node_val.reason = 'The source test script has a problematic node.'
      lstat_node_val.etms = p_utils.current_time_msec()

      lrule_learn_rec = ptlog.RuleLearnRec()
      lstat_node.val_learn_iters.append(lrule_learn_rec)

      iter_learned_rec_trules = await stat_node_learn_trules_recovery(
        simple_ntext,
        stat_learn_subject.src_lang,
        stat_learn_subject.tar_lang,
        lrule_learn_rec,
      )

    except BypassStaRuleLearningError as err:
      logger.info(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'BypassStaRuleLearningError:\n'
        f'Directly learning a recovery rule for statement:\n{simple_ntext}')

      lstat_node_val.success = False
      lstat_node_val.reason = 'Directly learning a recovery rule (bypass standard rule learning).'
      lstat_node_val.etms = p_utils.current_time_msec()

      lrule_learn_rec = ptlog.RuleLearnRec()
      lstat_node.val_learn_iters.append(lrule_learn_rec)

      iter_learned_rec_trules = await stat_node_learn_trules_recovery(
        simple_ntext,
        stat_learn_subject.src_lang,
        stat_learn_subject.tar_lang,
        lrule_learn_rec,
      )

    # ADD LEARNED RULES TO THE CURRENT RULESET
    ruleset_size_before_update = len(current_ruleset.rules)
    if len(iter_learned_sta_trules) > 0:
      joined_iter_learned_sta_trules = '\n'.join(iter_learned_sta_trules)
      logger.debug(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'simple_ntext:\n{simple_ntext}\n'
        f'learned {len(iter_learned_sta_trules)} new translation rules by STANDARD procedure:\n'
        f'{joined_iter_learned_sta_trules}\n'
        f'Appending learned standard translation rules to the current ruleset')
      _append_standard_rules_to_ruleset(
        current_ruleset,
        iter_learned_sta_trules,
        stat_nid,
        simple_ntext,
      )
    elif len(iter_learned_rec_trules) > 0:
      valid_rec_trules = await _filter_overfitted_trules_by_validation(
        iter_learned_rec_trules,
        main_subject,
        current_ruleset,
        simple_ntext,
        simple_nchoices,
        pre_context,
        stat_nid,
      )
      if len(valid_rec_trules) == 0:
        logger.warning(
          f'--stat-main--: statement node (nid={stat_nid}): '
          f'No overfitted rules passed validation; skipping recovery rules.')
        lstat_node_val.success = False
        lstat_node_val.reason = 'No overfitted rules passed validation'
        lstat_node_val.etms = p_utils.current_time_msec()
        continue

      joined_valid_rec_trules = '\n'.join(valid_rec_trules)
      logger.debug(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'simple_ntext:\n{simple_ntext}\n'
        f'learned {len(iter_learned_rec_trules)} new translation rules by RECOVERY procedure; '
        f'{len(valid_rec_trules)} passed validation:\n'
        f'{joined_valid_rec_trules}\n'
        f'Prepending validated overfitted translation rules to the current ruleset')
      for rule_str in reversed(valid_rec_trules):
        rule_parsed = p_ruleset.TRuleBase.parse_rule_str(rule_str)
        rule = p_ruleset.StatementOverfittedTRule(rule_parsed, stat_nid, simple_ntext)
        if current_ruleset.get_rule_ref(rule) is not None:
          logger.debug(f'skipping duplicate rule:\n{rule}')
          continue
        current_ruleset.prepend_rule(rule)
    else:
      lstat_node.success = False
      lstat_node.reason = 'should not happen: no learned translation rules'
      lstat_node.etms = p_utils.current_time_msec()
      raise RuntimeError('should not happen: no learned translation rules')

    if iter_counter == _MAX_NUM_ITERS and len(current_ruleset.rules) > ruleset_size_before_update:
      should_run_final_validation = True

  if should_run_final_validation:
    logger.debug(
      f'--stat-main--: statement node (nid={stat_nid}): '
      'max iterations reached right after ruleset update; '
      'running one final validation-only pass')
    lstat_node_val = ptlog.StatNodeVal()
    lstat_node.val_learn_iters.append(lstat_node_val)
    stat_learn_subject = _create_subject_for_stat_learn(
      main_subject, simple_ntext, current_ruleset, simple_nchoices)
    stat_val_subject = _create_subject_for_stat_val(
      main_subject,
      pre_context,
      simple_ntext,
      current_ruleset,
      origin_stat_nid_for_eot=stat_nid,
    )
    try:
      await stat_node_validate_trules(
        simple_nchoices,
        simple_ntext,
        stat_learn_subject,
        stat_val_subject,
        current_ruleset,
        lstat_node_val,
      )
      logger.info(
        f'--stat-main--: statement node (nid={stat_nid}): '
        'SUCCESS Statement node translation rules validated in final validation-only pass')
      lstat_node.success = True
      lstat_node.etms = p_utils.current_time_msec()
      return
    except Exception as err:
      logger.warning(
        f'--stat-main--: statement node (nid={stat_nid}): '
        f'final validation-only pass failed with {type(err).__name__}')
      lstat_node_val.success = False
      lstat_node_val.reason = f'Final validation-only pass failed: {type(err).__name__}'
      lstat_node_val.etms = p_utils.current_time_msec()

  lstat_node.success = False
  lstat_node.reason = f'hit max iterations ({_MAX_NUM_ITERS})'
  lstat_node.etms = p_utils.current_time_msec()
  raise RuntimeError('stat_node_main_learn_validate_trules: hit max iterations')


async def learn_trans_rules_for_subject_execution_order(
  subject: p_subject.PirelSubject,
  starting_ruleset: p_ruleset.Ruleset,
  lrule_learn_phase: Optional[ptlog.RuleLearnPhase] = None,
):
  '''
  Iterate over statement nodes in the source code of the subject,
  learn translation rules for each statement node,
  validate the learned rules, and if necessary recover from errors.
  NOTE writes learned translation rules to starting_ruleset.
  NOTE All errors propagate to the caller.
  '''

  '''
  Iterate over statement nodes (simple statements, compound statements).
  It happens that the statement nodes are also context nodes for any problematic node.
  Using this relation between context nodes and statement nodes,
  we will make a list of such nodes.
  '''
  stat_nodes = await _get_statement_nodes(
    subject.get_src_main_code(), subject.src_lang, subject.is_three_split, subject.name)
  logger.info(
    f'There are {len(stat_nodes)} statement nodes in src_main_code:\n'
    f'{subject.get_src_main_code()}')

  graylist_nids: List[int] = []
  recurring_exec_nids: Set[int] = set()
  first_exec_stack_by_nid: Dict[int, Tuple[str, ...]] = {}
  if not subject.is_three_split:
    _executed_stat_nids = [node.get_id() for node in stat_nodes]
    _all_stat_nids_static = await _get_statement_nodes(
      subject.get_src_main_code(),
      subject.src_lang,
      True,
      subject.name,
      return_node_ids=True,
    )
    _executed_stat_nids_set = set(_executed_stat_nids)
    graylist_nids = [
      nid for nid in _all_stat_nids_static
      if nid not in _executed_stat_nids_set
    ]
    logger.debug(
      f'Computed EOT graylist statements: {len(graylist_nids)} '
      f'(all={len(_all_stat_nids_static)}, executed={len(_executed_stat_nids)})'
    )
    # Root cause:
    # Suffix-only blacklist can prune statements that are re-entered later
    # in runtime (e.g., loop/caller re-entry), even if they have already
    # executed before the current statement in this test trace.
    # Fix rationale:
    # Preserve previously-seen recurring statements by excluding them from
    # blacklist, so runtime-critical assignments are not replaced by `pass`.
    _exec_trace_events = await get_statement_exec_events_eot(
      subject.get_src_main_code(),
      subject.src_lang,
      subject.name,
      deduplicate=False,
    )
    _exec_trace_nids = [node_id for node_id, _ in _exec_trace_events]
    for node_id, call_stack in _exec_trace_events:
      if node_id not in first_exec_stack_by_nid:
        first_exec_stack_by_nid[node_id] = call_stack
    _exec_nid_counts = Counter(_exec_trace_nids)
    recurring_exec_nids = {
      nid for nid, count in _exec_nid_counts.items() if count > 1
    }
    logger.debug(
      f'Computed recurring EOT statement nids: {len(recurring_exec_nids)} '
      f'(trace_len={len(_exec_trace_nids)})'
    )

  lrule_learn_phase = lrule_learn_phase or ptlog.RuleLearnPhase()
  lrule_learn_phase.stms = p_utils.current_time_msec()
  lrule_learn_phase.num_stat_nodes = len(stat_nodes)

  src_main_code = subject.get_src_main_code()
  stat_node_ids = [node.get_id() for node in stat_nodes]

  def _build_nid_blacklist(
    current_idx: int,
    include_current_statement: bool = False,
    preserve_recurring: bool = True,
  ) -> List[int]:
    nonlocal graylist_nids, recurring_exec_nids, stat_nodes
    '''
    NOTE:
    `current_idx` is 1-based, while list slicing is 0-based.
    - include_current_statement=False (default): preserve existing behavior
      for normal statement-learning flow.
    - include_current_statement=True: include the current execution-order
      statement in blacklist, used for deferred-finalization to prevent
      current-step statements from leaking into pre-context.
    '''
    slice_start = max(current_idx - 1, 0) if include_current_statement else max(current_idx, 0)
    nid_blacklist = [node.get_id() for node in stat_nodes[slice_start:]]
    current_statement_nid: Optional[int] = None
    if 1 <= current_idx <= len(stat_nodes):
      current_statement_nid = stat_nodes[current_idx - 1].get_id()
    if recurring_exec_nids and preserve_recurring:
      seen_nids = {node.get_id() for node in stat_nodes[:current_idx]}
      preserve_nids = recurring_exec_nids.intersection(seen_nids)
      if include_current_statement and current_statement_nid is not None:
        preserve_nids.discard(current_statement_nid)
      if preserve_nids:
        nid_blacklist = [nid for nid in nid_blacklist if nid not in preserve_nids]
        logger.debug(
          f'Filtered suffix blacklist by recurring+seen nids: '
          f'preserved={len(preserve_nids)}, blacklist_after={len(nid_blacklist)}')
    if graylist_nids:
      nid_blacklist.extend(graylist_nids)
    return nid_blacklist

  def _append_statement_csv_for_lstat_node(
    statement_idx: int,
    statement_nid: int,
    lstat_node: ptlog.StatNode,
    row_status: str,
    row_error_type: str,
  ) -> None:
    (
      e2e_ms,
      learning_ms,
      translation_ms,
      validation_ms,
      llm_query_ms,
      llm_tokens_total,
    ) = _collect_statement_metrics(lstat_node)
    _append_statement_result_csv(
      subject_name=subject.name,
      statement_idx=statement_idx,
      statement_nid=statement_nid,
      e2e_ms=e2e_ms,
      learning_ms=learning_ms,
      translation_ms=translation_ms,
      validation_ms=validation_ms,
      llm_query_ms=llm_query_ms,
      llm_tokens_total=llm_tokens_total,
      status=row_status,
      error_type=row_error_type,
    )

  deferred_entries: List[dict] = []
  local_fn_names: Set[str] = set()
  local_call_graph: Dict[str, Set[str]] = {}
  nid_to_enclosing_fn_name: Dict[int, Optional[str]] = {}
  if subject.src_lang == 'py' and not subject.is_three_split:
    local_fn_names, local_call_graph = _build_local_function_call_graph(src_main_code)
    nid_to_enclosing_fn_name = _map_statement_nids_to_enclosing_fn_names(
      src_main_code,
      stat_node_ids,
    )

  def _build_active_deferred_overrides(
    exclude_statement_nid: Optional[int] = None
  ) -> Dict[int, str]:
    nonlocal deferred_entries
    overrides: Dict[int, str] = {}
    for entry in deferred_entries:
      statement_nid = int(entry['statement_nid'])
      if exclude_statement_nid is not None and statement_nid == exclude_statement_nid:
        continue
      overrides[statement_nid] = str(entry['call_only_simple_ntext'])
    return overrides

  def _build_deferred_entry_for_statement(
    statement_idx: int,
    statement_node: pds.PirelNode,
    statement_lstat_node: ptlog.StatNode,
  ) -> Optional[dict]:
    nonlocal local_fn_names, local_call_graph, nid_to_enclosing_fn_name
    if not local_call_graph:
      return None

    simple_ntext = _simplify_comp_stat_node_text(statement_node, src_main_code)
    defer_candidate = _extract_defer_candidate_call_only_statement(
      simple_ntext,
      subject.src_lang,
      allowed_callee_names=local_fn_names,
    )
    if defer_candidate is None:
      return None

    call_only_stmt, callee_names = defer_candidate
    local_seed_fns = {name for name in callee_names if name in local_fn_names}
    if not local_seed_fns:
      return None

    callee_closure = _compute_transitive_callee_closure(local_seed_fns, local_call_graph)
    boundary_idx = _compute_deferred_boundary_idx(
      statement_idx,
      stat_nodes,
      nid_to_enclosing_fn_name,
      callee_closure,
    )
    if boundary_idx <= statement_idx:
      return None

    return {
      'statement_idx': statement_idx,
      'statement_nid': statement_node.get_id(),
      'lstat_node': statement_lstat_node,
      'original_simple_ntext': simple_ntext,
      'call_only_simple_ntext': call_only_stmt,
      'boundary_idx': boundary_idx,
      'callee_closure': callee_closure,
      'local_seed_fns': local_seed_fns,
    }

  async def _finalize_deferred_entries(current_idx: int) -> None:
    nonlocal deferred_entries
    has_current_target = 1 <= current_idx <= len(stat_nodes)
    current_statement_nid: Optional[int] = None
    current_statement_dynamic_stack: Tuple[str, ...] = tuple()
    if has_current_target:
      current_statement_nid = stat_nodes[current_idx - 1].get_id()
      current_statement_dynamic_stack = first_exec_stack_by_nid.get(current_statement_nid, tuple())

    ready_entries: List[dict] = []
    for entry in deferred_entries:
      # Original rule: finalize after crossing computed boundary.
      should_finalize = current_idx > entry['boundary_idx']

      # Dynamic finalization:
      # If current target statement is no longer on the deferred call path,
      # finalize immediately even before static boundary.
      if not should_finalize and has_current_target:
        local_seed_fns = set(entry.get('local_seed_fns', set()))
        if len(local_seed_fns) > 0 and len(current_statement_dynamic_stack) > 0:
          in_deferred_path = any(fn_name in current_statement_dynamic_stack for fn_name in local_seed_fns)
          if not in_deferred_path:
            logger.debug(
              f'Dynamic-defer-finalize trigger: '
              f'current_idx={current_idx}, current_nid={current_statement_nid}, '
              f'seed_fns={sorted(local_seed_fns)}, '
              f'current_stack={list(current_statement_dynamic_stack)}')
            should_finalize = True
        elif len(local_seed_fns) > 0 and len(current_statement_dynamic_stack) == 0:
          # Module-level execution cannot be inside a function-call defer path.
          should_finalize = True

      if should_finalize:
        ready_entries.append(entry)

    for entry in ready_entries:
      statement_idx = int(entry['statement_idx'])
      statement_nid = int(entry['statement_nid'])
      statement_lstat_node = entry['lstat_node']
      original_simple_ntext = str(entry['original_simple_ntext'])

      logger.info(
        f'---stat-main---: finalizing deferred statement '
        f'{statement_idx}/{len(stat_nodes)} '
        f'(nid={statement_nid}, boundary={entry["boundary_idx"]}, current={current_idx})')
      row_status = 'success'
      row_error_type = ''
      try:
        active_deferred_overrides = _build_active_deferred_overrides(exclude_statement_nid=statement_nid)
        await stat_node_main_learn_validate_trules(
          subject,
          starting_ruleset,
          statement_nid,
          _build_nid_blacklist(current_idx, include_current_statement=True),
          statement_lstat_node,
          simple_ntext_override=original_simple_ntext,
          nid_text_overrides=active_deferred_overrides or None,
        )
      except Exception as err:
        row_status = 'error'
        row_error_type = type(err).__name__
        raise
      finally:
        _append_statement_csv_for_lstat_node(
          statement_idx=statement_idx,
          statement_nid=statement_nid,
          lstat_node=statement_lstat_node,
          row_status=row_status,
          row_error_type=row_error_type,
        )
        deferred_entries.remove(entry)

  for sn_idx in range(1, len(stat_nodes) + 1):
    await _finalize_deferred_entries(sn_idx)

    stat_node = stat_nodes[sn_idx - 1]
    logger.info(f'---stat-main---: statement node {sn_idx}/{len(stat_nodes)}')
    lstat_node = ptlog.StatNode()
    lstat_node.id = sn_idx
    lrule_learn_phase.stat_nodes.append(lstat_node)

    # writes new rules to starting_ruleset
    nid_blacklist = _build_nid_blacklist(sn_idx)

    deferred_entry = _build_deferred_entry_for_statement(sn_idx, stat_node, lstat_node)
    if deferred_entry is not None:
      logger.info(
        f'--stat-main--: deferred statement {sn_idx}/{len(stat_nodes)} '
        f'(nid={stat_node.get_id()}) with call-only snippet:\n'
        f'{deferred_entry["call_only_simple_ntext"]}\n'
        f'boundary_idx={deferred_entry["boundary_idx"]}, '
        f'callee_closure={sorted(deferred_entry["callee_closure"])}'
      )

    row_status = 'success'
    row_error_type = ''
    should_write_csv = True
    try:
      active_deferred_overrides = _build_active_deferred_overrides()
      if deferred_entry is None:
        await stat_node_main_learn_validate_trules(
          subject,
          starting_ruleset,
          stat_node.get_id(),
          nid_blacklist,
          lstat_node,
          nid_text_overrides=active_deferred_overrides or None,
        )
      else:
        await stat_node_main_learn_validate_trules(
          subject,
          starting_ruleset,
          stat_node.get_id(),
          nid_blacklist,
          lstat_node,
          simple_ntext_override=deferred_entry['call_only_simple_ntext'],
          nid_text_overrides=active_deferred_overrides or None,
        )
        deferred_entries.append(deferred_entry)
        should_write_csv = False
    except Exception as err:
      row_status = 'error'
      row_error_type = type(err).__name__
      raise
    finally:
      if should_write_csv:
        _append_statement_csv_for_lstat_node(
          statement_idx=sn_idx,
          statement_nid=stat_node.get_id(),
          lstat_node=lstat_node,
          row_status=row_status,
          row_error_type=row_error_type,
        )

    # NOTE can be used to resume learning from a specific statement node
    logger.debug(f'Saving intermediate ruleset after statement node {sn_idx}/{len(stat_nodes)}')
    p_utils.log_json_time(f'intermediate_ruleset_after_stat_node_{sn_idx}.json',
                          starting_ruleset.to_dict())
    if sn_idx % _RULESET_CHECKPOINT_INTERVAL == 0 or sn_idx == len(stat_nodes):
      _save_ruleset_checkpoint(subject.name, sn_idx, starting_ruleset)

  await _finalize_deferred_entries(len(stat_nodes) + 1)
  logger.debug(f'Finished learning translation rules for all {len(stat_nodes)} statement nodes')


def _extract_py_assignment_stmt(simple_ntext: str) -> Optional[ast.stmt]:
  if not isinstance(simple_ntext, str):
    return None
  try:
    parsed = ast.parse(simple_ntext)
  except SyntaxError:
    return None
  if len(parsed.body) != 1:
    return None
  only_stmt = parsed.body[0]
  if not isinstance(only_stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
    return None
  return only_stmt


def _collect_assignment_target_names(stmt: ast.stmt) -> Set[str]:
  names: Set[str] = set()

  def _collect_from_target(target: ast.expr) -> None:
    if isinstance(target, ast.Name):
      names.add(target.id)
      return
    if isinstance(target, (ast.Tuple, ast.List)):
      for elt in target.elts:
        _collect_from_target(elt)

  if isinstance(stmt, ast.Assign):
    for target in stmt.targets:
      _collect_from_target(target)
  elif isinstance(stmt, ast.AugAssign):
    _collect_from_target(stmt.target)
  elif isinstance(stmt, ast.AnnAssign):
    _collect_from_target(stmt.target)

  return names


def _get_py_assignment_target_names(simple_ntext: str) -> Set[str]:
  stmt = _extract_py_assignment_stmt(simple_ntext)
  if stmt is None:
    return set()
  return _collect_assignment_target_names(stmt)


def _extract_js_declared_names_from_trule(trule_str: str) -> Set[str]:
  declared_names: Set[str] = set()
  if not isinstance(trule_str, str):
    return declared_names

  # Parse names on the LHS of js.variable_declarator, e.g.
  # - var decltype_j = ...
  # - var [decltype, j] = ...
  for match in re.finditer(
    r'\("js\.variable_declarator"\s*(.*?)\s*\(str "="\)',
    trule_str,
    flags=re.DOTALL,
  ):
    lhs_text = match.group(1)
    lhs_names = re.findall(
      r'\("js\.identifier"\s*\(val\s+"([^"]+)"\)\)',
      lhs_text,
    )
    declared_names.update(lhs_names)
  return declared_names


def _is_self_referential_py_assignment_stmt(simple_ntext: str) -> bool:
  stmt = _extract_py_assignment_stmt(simple_ntext)
  if stmt is None:
    return False

  target_names = _collect_assignment_target_names(stmt)
  if not target_names:
    return False

  # Keep the guard narrow: target only plain/annotated assignments.
  # AugAssign (x += y) is excluded from this declaration-blocking heuristic.
  if isinstance(stmt, ast.AugAssign):
    return False

  rhs: Optional[ast.expr] = None
  if isinstance(stmt, ast.Assign):
    rhs = stmt.value
  elif isinstance(stmt, ast.AnnAssign):
    rhs = stmt.value

  if rhs is None:
    return False

  for node in ast.walk(rhs):
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
      if node.id in target_names:
        return True
  return False


def _is_invalid_recovery_rule_for_statement(simple_ntext: str, trule_str: str) -> bool:
  if not isinstance(trule_str, str):
    return False
  # Guard against a frequent overfit in recovery:
  # self-referential assignment translated to top-level JS declaration.
  # In function scope this can shadow/redeclare state and break runtime behavior.
  if not _is_self_referential_py_assignment_stmt(simple_ntext):
    return False
  if '(fragment ("py.expression_statement" ("py.assignment"' not in trule_str:
    return False
  if '(fragment ("js.variable_declaration"' not in trule_str:
    return False

  source_target_names = _get_py_assignment_target_names(simple_ntext)
  if not source_target_names:
    return False
  declared_names = _extract_js_declared_names_from_trule(trule_str)
  if not declared_names:
    # Keep previous safety posture when declaration names cannot be parsed.
    return True
  return len(source_target_names.intersection(declared_names)) > 0
