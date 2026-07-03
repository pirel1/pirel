import json
import re
from typing import Dict, List, Optional, Tuple, Set

import d_ast_parse
import d_grammar_rules
import p_code_runner
import p_consts
import p_pirel
import p_ruleset
import p_rule_applicator as prapp
import p_subject
import p_utils
import p_visitor as pvis
import p_visitor_py as pvpy
from p_config import Config


logger = p_utils.setup_logger(__name__)


class NoRuleToHandleRangeCursorError(Exception): pass
class UnhandledRangeCursorExistsError(Exception): pass
class RuleCombinationsExhaustedError(RuntimeError): pass
class ExprLogStatHasParseError(RuntimeError): pass
class ExprLogStatContextError(RuntimeError): pass
class QueueInfiniteLoopError(RuntimeError): pass

class AllRulesInMatcherGroupImplausibleError(RuntimeError):
  def __init__(self, not_matching_rules_str: str, snippet: str):
    '''
    PARAM snippet: string repr of the node for which
    there are no plausible rules in the matcher group.
    PARAM not_matching_rules_str: ruleset without
    the rules that match the snippet.
    '''
    self.not_matching_rules_str = not_matching_rules_str
    self.snippet = snippet
  def __str__(self):
    return (f'All rules in the matcher group are implausible for the snippet {self.snippet!r}')

class VerifiedRulesExhaustedError(RuntimeError):
  def __init__(self, choice_identifier: Tuple[int, int, int]):
    '''
    PARAM choice_identifier: range info of the node for which
    all existing verified rules have been exhausted.
    FIELD no_choices_snippet: string repr of the node.
    FIELD not_matching_rules_str: ruleset without
    the rules that match the snippet.
    '''
    self.choice_identifier = choice_identifier
    self.no_choices_snippet = None
    self.not_matching_rules_str = None
  def __str__(self):
    return (f'None of the verified rules work for {self.no_choices_snippet!r} at {self.choice_identifier}')


_CACHE_new_expr_choice_info: Dict[str, Tuple[Dict[str, Set[int]], Dict[int, str]]] = {}
_CACHE_log_stat_rule_pretty: Optional[str] = None
_CACHE_log_stat_choice_info: Dict[str, Tuple[Optional[str], Optional[int]]] = {}
_CACHE_src_ast: Dict[str, list] = {}
_CACHE_subject_gt_fn_names: Dict[str, Set[str]] = {}
_CACHE_SRC_FN_ANCESTOR_NAME_BY_NID: Dict[str, Dict[int, Optional[str]]] = {}
_CACHE_base_ruleset: Optional[p_ruleset.Ruleset] = None
_CACHE_base_ruleset_key: Optional[Tuple[str, ...]] = None
_LOG_PREVIEW_MAX_CHARS = 400
_LOG_PREVIEW_MAX_LINES = 8


def _log_preview(text: str) -> str:
  '''
  Return a compact preview for very large debug strings.
  '''
  if text is None:
    return ''
  lines = text.splitlines()
  if len(lines) > _LOG_PREVIEW_MAX_LINES:
    text = '\n'.join(lines[:_LOG_PREVIEW_MAX_LINES]) + \
      f'\n... [truncated {len(lines) - _LOG_PREVIEW_MAX_LINES} lines]'
  if len(text) > _LOG_PREVIEW_MAX_CHARS:
    text = text[:_LOG_PREVIEW_MAX_CHARS] + \
      f' ... [truncated {len(text) - _LOG_PREVIEW_MAX_CHARS} chars]'
  return text


def _get_new_expr_choice_info(
  translation_rules_main_code: str
) -> Tuple[Dict[str, Set[int]], Dict[int, str]]:
  cached = _CACHE_new_expr_choice_info.get(translation_rules_main_code)
  if cached is not None:
    return cached

  try:
    rules_parsed = d_grammar_rules.parse_analyze_rules_optim(translation_rules_main_code)
  except Exception as err:
    logger.warning(f'Failed to parse translation rules for new-expression filtering: {err}')
    result = ({}, {})
    _CACHE_new_expr_choice_info[translation_rules_main_code] = result
    return result

  match_sig_to_new_expr_idxs: Dict[str, Set[int]] = {}
  rule_id_to_match_sig: Dict[int, str] = {}
  match_sig_to_count: Dict[str, int] = {}
  for rule_id, rule_parsed in enumerate(rules_parsed):
    match_sig = str(rule_parsed.get('match'))
    idx_in_group = match_sig_to_count.get(match_sig, 0)
    rule_id_to_match_sig[rule_id] = match_sig
    match_sig_to_count[match_sig] = idx_in_group + 1
    if 'js.new_expression' in d_grammar_rules.pretty_rule(rule_parsed):
      match_sig_to_new_expr_idxs.setdefault(match_sig, set()).add(idx_in_group)

  result = (match_sig_to_new_expr_idxs, rule_id_to_match_sig)
  _CACHE_new_expr_choice_info[translation_rules_main_code] = result
  return result


def _get_log_stat_rule_pretty() -> Optional[str]:
  global _CACHE_log_stat_rule_pretty
  if _CACHE_log_stat_rule_pretty is not None:
    return _CACHE_log_stat_rule_pretty
  try:
    log_rule_parsed = d_grammar_rules.parse_analyze_rules_optim(
      p_utils.read_text(p_consts.LOG_STAT_RULE_FPATH))[0]
  except Exception as err:
    logger.warning(f'Failed to parse log statement rule for filtering: {err}')
    return None
  _CACHE_log_stat_rule_pretty = d_grammar_rules.pretty_rule(log_rule_parsed)
  return _CACHE_log_stat_rule_pretty


def _get_log_stat_choice_info(
  translation_rules_main_code: str
) -> Tuple[Optional[str], Optional[int]]:
  cached = _CACHE_log_stat_choice_info.get(translation_rules_main_code)
  if cached is not None:
    return cached

  log_rule_pretty = _get_log_stat_rule_pretty()
  if log_rule_pretty is None:
    result = (None, None)
    _CACHE_log_stat_choice_info[translation_rules_main_code] = result
    return result

  try:
    log_rule_parsed = d_grammar_rules.parse_analyze_rules_optim(
      p_utils.read_text(p_consts.LOG_STAT_RULE_FPATH))[0]
  except Exception as err:
    logger.warning(f'Failed to parse log statement rule for choice info: {err}')
    result = (None, None)
    _CACHE_log_stat_choice_info[translation_rules_main_code] = result
    return result

  log_match_sig = str(log_rule_parsed['match'])
  try:
    rules_parsed = d_grammar_rules.parse_analyze_rules_optim(translation_rules_main_code)
  except Exception as err:
    logger.warning(f'Failed to parse translation rules for log-stat choices: {err}')
    result = (log_match_sig, None)
    _CACHE_log_stat_choice_info[translation_rules_main_code] = result
    return result

  idx_in_group = 0
  for rule_parsed in rules_parsed:
    if str(rule_parsed.get('match')) != log_match_sig:
      continue
    if d_grammar_rules.pretty_rule(rule_parsed) == log_rule_pretty:
      result = (log_match_sig, idx_in_group)
      _CACHE_log_stat_choice_info[translation_rules_main_code] = result
      return result
    idx_in_group += 1

  result = (log_match_sig, None)
  _CACHE_log_stat_choice_info[translation_rules_main_code] = result
  return result


def _get_src_ast(src_main_code: str) -> Optional[list]:
  cached = _CACHE_src_ast.get(src_main_code)
  if cached is not None:
    return cached
  try:
    src_ast, _ = d_ast_parse.parse_text_dbg(src_main_code, 'py')
  except Exception as err:
    logger.warning(f'Failed to parse src_main_code for new-expression filtering: {err}')
    return None
  _CACHE_src_ast[src_main_code] = src_ast
  return src_ast


def _get_subject_gt_fn_names(subject_name: Optional[str]) -> Set[str]:
  '''
  Return names of functions that have ground truth translations for a subject.
  '''
  if subject_name is None or not isinstance(subject_name, str):
    return set()
  cached = _CACHE_subject_gt_fn_names.get(subject_name)
  if cached is not None:
    return cached

  config_fpath = p_consts.SKEL_BENCHMARK_DIR / f'{subject_name}-config.json'
  if not config_fpath.exists():
    logger.debug(f'Subject config does not exist for GT exclusion: {config_fpath}')
    _CACHE_subject_gt_fn_names[subject_name] = set()
    return set()

  try:
    subject_config = p_utils.read_json(config_fpath)
  except Exception as err:
    logger.warning(f'Failed to read subject config for GT exclusion ({subject_name}): {err}')
    _CACHE_subject_gt_fn_names[subject_name] = set()
    return set()

  ground_truth_translations = subject_config.get('ground_truth_translations', {})
  if not isinstance(ground_truth_translations, dict):
    logger.warning(
      f'Unexpected ground_truth_translations format for subject "{subject_name}": '
      f'{type(ground_truth_translations)}')
    _CACHE_subject_gt_fn_names[subject_name] = set()
    return set()

  gt_fn_names = set(ground_truth_translations.keys())
  _CACHE_subject_gt_fn_names[subject_name] = gt_fn_names
  return gt_fn_names


def _filter_myexactlog_to_log_stat_rule(
  matcher_group: List[p_ruleset.TRuleBase]
) -> List[p_ruleset.TRuleBase]:
  log_rule_pretty = _get_log_stat_rule_pretty()
  if log_rule_pretty is None:
    return []
  filtered = [trule for trule in matcher_group if trule.to_rule_str() == log_rule_pretty]
  if not filtered:
    logger.debug('Log statement rule not found in matcher_group for myexactlog.')
  return filtered


def _range_includes_myexactlog(
  range_info: Tuple[int, int, int],
  src_ast: list,
) -> bool:
  try:
    parent_ast, start_idx, end_idx = d_ast_parse.choice_identifier_to_range_cursor(
      range_info, src_ast)
  except Exception:
    return False
  for idx in range(start_idx, end_idx):
    child = parent_ast[idx]
    if not isinstance(child, list):
      continue
    for node in _iter_duoglot_nt_nodes(child):
      if _is_myexactlog_expr_stmt(node):
        return True
  return False


# GENERATING READONLY CHOICES LIST
def _match_rule_to_range_cursor(
  matcher: list,
  range_cursor: tuple
) -> dict:
  '''
  Match matcher to range_cursor and return a match object.
  This function is copied from d_grammar_expand.TransSession._try_get_expansion_if_match_on_slot()

  PARAM matcher: matcher of a translation rule
  PARAM range_cursor: internal data structure used in TransSession class.

  RETURN a match object {is_matched: bool, slot_cursors: list}
  '''
  def _is_anno_compatible(matcher_anno, intree_anno):
    matcher_anno_dict = {x[0]:x[1] for x in matcher_anno[1:]}
    intree_anno_dict = {x[0]:x[1] for x in intree_anno[1:]}
    for key in matcher_anno_dict:
      if key not in intree_anno_dict: return False
      if matcher_anno_dict[key] != intree_anno_dict[key]: return False
    return True

  def _range_cursor_has_is_not(rc: tuple) -> bool:
    elems, start_idx, end_idx = rc
    def _elem_is_token(elem, token: str) -> bool:
      if isinstance(elem, str) and _strip_quotes(elem) == token:
        return True
      return isinstance(elem, list) and len(elem) == 2 and elem[0] == 'str' and _strip_quotes(elem[1]) == token
    def _node_has_is_not_comp(node) -> bool:
      if not isinstance(node, list):
        return False
      if len(node) > 0 and isinstance(node[0], str) and _node_type_equals(node[0], 'py.comparison_operator'):
        has_is = False
        has_not = False
        for item in node[1:]:
          if isinstance(item, list) and len(item) == 2 and item[0] == 'str':
            if _strip_quotes(item[1]) == 'is':
              has_is = True
            elif _strip_quotes(item[1]) == 'not':
              has_not = True
        if has_is and has_not:
          return True
      for child in node:
        if _node_has_is_not_comp(child):
          return True
      return False
    for idx in range(start_idx, end_idx - 1):
      if _elem_is_token(elems[idx], 'is') and _elem_is_token(elems[idx + 1], 'not'):
        return True
    for idx in range(start_idx, end_idx):
      if _node_has_is_not_comp(elems[idx]):
        return True
    return False

  def _matcher_is_is_without_not(m: list) -> bool:
    def _rec(node) -> bool:
      if not isinstance(node, list):
        return False
      if len(node) > 0 and isinstance(node[0], str) and _node_type_equals(node[0], 'py.comparison_operator'):
        has_is = False
        has_not = False
        for item in node[1:]:
          if isinstance(item, list) and len(item) == 2 and item[0] == 'str':
            if _strip_quotes(item[1]) == 'is':
              has_is = True
            elif _strip_quotes(item[1]) == 'not':
              has_not = True
        if has_is and not has_not:
          return True
      for child in node:
        if _rec(child):
          return True
      return False
    return _rec(m)

  if _matcher_is_is_without_not(matcher) and _range_cursor_has_is_not(range_cursor):
    return {'is_matched': False, 'slot_cursors': []}

  def _range_cursor_has_py_none(rc: tuple) -> bool:
    elems, start_idx, end_idx = rc
    def _node_has_py_none(node) -> bool:
      if not isinstance(node, list):
        return False
      if len(node) > 0 and isinstance(node[0], str) and _node_type_equals(node[0], 'py.none'):
        return True
      for child in node:
        if _node_has_py_none(child):
          return True
      return False
    for idx in range(start_idx, end_idx):
      if _node_has_py_none(elems[idx]):
        return True
    return False

  def _matcher_has_py_none(m: list) -> bool:
    if not isinstance(m, list):
      return False
    if len(m) > 0 and isinstance(m[0], str) and _node_type_equals(m[0], 'py.none'):
      return True
    for child in m:
      if _matcher_has_py_none(child):
        return True
    return False

  if _matcher_is_is_comparison(matcher) and _range_cursor_has_py_none(range_cursor) and not _matcher_has_py_none(matcher):
    return {'is_matched': False, 'slot_cursors': []}

  def _try_match_rec_inner_fun(
    range_cursor,
    range_cursor_idx: int,
    matcher,
    matcher_idx: int
  ) -> bool:
    '''
    PARAMETERS:
    range_cursor:             Slot.range_cursor           Tuple[ List[src_ast] , int , int ]
    range_cursor_idx:         int                         start index in the AST list
    matcher:                  list                        [['"py.argument_list"', '"*"'], '"*"']
    matcher_idx:              int                         index in the matcher

    LOCALS:
    current_matcher_elem:     list                        ['"py.argument_list"', '"*"']
    matcher_operator:         str                         '"py.argument_list"'  # with double quotes as in rules
    current_matcher_type:     str                         'py.argument_list'  # without double quotes

    returns bool
    '''

    nonlocal slot_cursors

    # assert range_cursor[2] <= len(range_cursor[0])
    if range_cursor_idx >= range_cursor[2] and matcher_idx >= len(matcher):
      return True

    # 1 matcher element is empty
    if matcher_idx >= len(matcher):
      # the rest of the cursor must all be terminals
      for visit_cur_idx in range(range_cursor_idx, range_cursor[2]):
        visit_elem = range_cursor[0][visit_cur_idx]
        if isinstance(visit_elem, str): continue
        else: return False  # contains non terminal
      return True  # loop done. All of them are terminals.

    # 2 matcher element is not empty
    assert len(matcher) > 0
    current_matcher_elem = matcher[matcher_idx]

    # case 1 current_matcher_elem
    if current_matcher_elem == '"*"':
      slot_cursors.append((range_cursor[0], range_cursor_idx, range_cursor[2]))
      return True

    # case 2 current_matcher_elem
    elif current_matcher_elem == '"."':
      # everything until the next NT is a cursor
      # everything after the next NT would be the rest to match
      split_idx = None
      for visit_cur_idx in range(range_cursor_idx, range_cursor[2]):
        visit_elem = range_cursor[0][visit_cur_idx]
        if d_ast_parse.is_elem_non_terminal(visit_elem):
          split_idx = visit_cur_idx + 1
          break

      # NT not found
      if split_idx is None:
        return False

      # NT found, cursor endswith NT
      slot_cursors.append((range_cursor[0], range_cursor_idx, split_idx))
      return _try_match_rec_inner_fun(
        range_cursor,  # range_cursor
        split_idx,  # range_cursor_idx
        matcher,  # matcher
        matcher_idx + 1  # matcher_idx
      )

    # case 3 current_matcher_elem
    elif current_matcher_elem == '"_val_"':
      assert len(matcher) == 1
      is_invalid = len(range_cursor[0]) != 3 or (range_cursor[2] - range_cursor[1]) != 1 or range_cursor_idx != 2
      assert not is_invalid, 'UNEXPECTED range_cursor'
      return True

    # case 4 current_matcher_elem
    elif current_matcher_elem == '"_str_"':
      if range_cursor_idx >= range_cursor[2]:
        return False # TOCHECK: out of length is failed to match.
      current_range_elem = range_cursor[0][range_cursor_idx]
      if not isinstance(current_range_elem, str):
        return False
      return _try_match_rec_inner_fun(
        range_cursor,  # range_cursor
        range_cursor_idx + 1,  # range_cursor_idx
        matcher,  # matcher
        matcher_idx + 1  # matcher_idx
      )

    # case 6 current_matcher_elem
    elif current_matcher_elem == '"_anno_"':
      current_range_elem = range_cursor[0][range_cursor_idx]
      assert isinstance(current_range_elem, list), '_anno_ meet none-annotation element: Not a list.'
      assert current_range_elem[0] == "anno", \
        '_anno_ meet none-annotation element: elem head: ' + current_range_elem[0]
      return _try_match_rec_inner_fun(
        range_cursor,  # range_cursor
        range_cursor_idx + 1,  # range_cursor_idx
        matcher,  # matcher
        matcher_idx + 1  # matcher_idx
      )

    # case 7 current_matcher_elem (non-terminal) not direct string, must be a list (all prev if's are False)
    assert isinstance(current_matcher_elem, list)
    matcher_operator = current_matcher_elem[0]

    # case 7.1
    if range_cursor_idx >= range_cursor[2]:
      if matcher_operator == "val" or matcher_operator == "str" or matcher_operator.startswith('"'):
        return False
      elif matcher_operator == "nostr":
        return _try_match_rec_inner_fun(
          range_cursor,  # range_cursor
          range_cursor_idx,  # range_cursor_idx
          matcher,  # matcher
          matcher_idx + 1  # matcher_idx
        )
      raise ValueError("UNEXPECTED range_cursor_idx out of length")

    # case 7.2
    if matcher_operator == "val":
      assert len(current_matcher_elem) == 2
      match_val = current_matcher_elem[1]
      is_invalid = len(range_cursor[0]) != 3 or (range_cursor[2] - range_cursor[1]) != 1 or range_cursor_idx != 2
      if is_invalid:
        print("# UNEXPECTED range_cursor for val match: ", range_cursor, range_cursor_idx)
        assert "UNEXPECTED range_cursor for val match" == 0
      range_val = range_cursor[0][range_cursor_idx]
      if not isinstance(range_val, str) and not isinstance(range_val, int) and not isinstance(range_val, float):
        return False
      if str(range_val) == str(match_val):
        return True
      return False

    # case 7.3
    elif matcher_operator == 'str':
      assert len(current_matcher_elem) == 2
      match_val = current_matcher_elem[1]
      should_be_str_val = range_cursor[0][range_cursor_idx]

      # skip `anno` in range_cursor when it's matched by `str`
      # for reference: L0004 (leetcode), long rule
      if isinstance(should_be_str_val, list) and len(should_be_str_val) > 0 and should_be_str_val[0] == 'anno':
        return _try_match_rec_inner_fun(
          range_cursor,  # range_cursor
          range_cursor_idx + 1,  # range_cursor_idx
          matcher,  # matcher
          matcher_idx  # matcher_idx
        )

      if not isinstance(should_be_str_val, str):
        return False
      if str(should_be_str_val) != str(match_val):
        return False
      return _try_match_rec_inner_fun(
        range_cursor,  # range_cursor
        range_cursor_idx + 1,  # range_cursor_idx
        matcher,  # matcher
        matcher_idx + 1  # matcher_idx
      )

    # case 7.4
    elif matcher_operator == "nostr":
      assert len(current_matcher_elem) == 1
      should_not_be_str_val = range_cursor[0][range_cursor_idx]
      if isinstance(should_not_be_str_val, str):
        return False
      return _try_match_rec_inner_fun(
        range_cursor,  # range_cursor
        range_cursor_idx,  # range_cursor_idx
        matcher,  # matcher
        matcher_idx + 1  # matcher_idx
      )

    # case 7.5
    elif matcher_operator == "anno":
      should_be_anno = range_cursor[0][range_cursor_idx]
      assert isinstance(should_be_anno, list), '(anno ...) meet none-annotation element: Not a list.'
      assert should_be_anno[0] == "anno", '(anno ...) meet none-annotation element: elem head: ' + should_be_anno[0]
      if not _is_anno_compatible(current_matcher_elem, should_be_anno):
        return False
      return _try_match_rec_inner_fun(
        range_cursor,  # range_cursor
        range_cursor_idx + 1,  # range_cursor_idx
        matcher,  # matcher
        matcher_idx + 1  # matcher_idx
      )

    # case 7.6 not special operators, must be grammar NT constructs
    assert matcher_operator.startswith('"'), 'UNEXPECTED matcher_operator: ' + matcher_operator
    current_matcher_type = matcher_operator[1:-1]
    assert current_matcher_type != "fragment" and current_matcher_type != "anno"

    for visit_cur_idx in range(range_cursor_idx, range_cursor[2]):
      visit_elem = range_cursor[0][visit_cur_idx]

      # this is not an NT. It is a T. We are currently matching against an NT.
      if isinstance(visit_elem, str):
        continue
      # we are currently matching against NT. anno if not caputured in earlier cases, in this case it will be skipped.
      if visit_elem[0] == "anno":
        continue

      assert d_ast_parse.is_elem_non_terminal(visit_elem)
      if visit_elem[0] == current_matcher_type:
        # check if the matching element is matched
        children_matcher = current_matcher_elem[1:]
        is_elem_matching = _try_match_rec_inner_fun(
          (visit_elem, 2, len(visit_elem)),  # range_cursor
          2,  # range_cursor_idx
          children_matcher,  # matcher
          0  # matcher_idx
        )

        if not is_elem_matching:
          return False

        return _try_match_rec_inner_fun(
          range_cursor,  # range_cursor
          visit_cur_idx + 1,  # range_cursor_idx
          matcher,  # matcher
          matcher_idx + 1  # matcher_idx
        )

      # mismatch
      return False

    # no match or mismatch
    return False

  assert matcher[0] == 'fragment', 'UNEXPECTED matcher: ' + str(matcher)
  slot_cursors = []

  is_matched = _try_match_rec_inner_fun(
    range_cursor,
    range_cursor[1],
    matcher[1:],
    0
  )

  return {
    'matcher': matcher,
    'range_cursor': range_cursor,
    'is_matched': is_matched,
    'slot_cursors': slot_cursors
  }


def _strip_quotes(val: str) -> str:
  if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
    return val[1:-1]
  return val


def _node_type_equals(a: str, b: str) -> bool:
  return _strip_quotes(a) == _strip_quotes(b)


def _ast_contains_node_type(ast: Optional[list], node_type: str) -> bool:
  if not isinstance(ast, list):
    return False
  if len(ast) > 0 and isinstance(ast[0], str) and _node_type_equals(ast[0], node_type):
    return True
  for child in ast[1:]:
    if _ast_contains_node_type(child, node_type):
      return True
  return False


def _matcher_has_str_token(node: list, token: str) -> bool:
  if not isinstance(node, list):
    return False
  if len(node) == 2 and node[0] == 'str' and _strip_quotes(node[1]) == token:
    return True
  for child in node:
    if _matcher_has_str_token(child, token):
      return True
  return False


def _matcher_is_is_comparison(matcher: list) -> bool:
  if not isinstance(matcher, list):
    return False
  def _rec(node) -> bool:
    if not isinstance(node, list):
      return False
    if len(node) > 0 and isinstance(node[0], str) and _node_type_equals(node[0], 'py.comparison_operator'):
      return _matcher_has_str_token(node, 'is')
    for child in node:
      if _rec(child):
        return True
    return False
  return _rec(matcher)


def _ast_contains_is_comparison(ast: list) -> bool:
  if not isinstance(ast, list):
    return False
  def _rec(node) -> bool:
    if not isinstance(node, list):
      return False
    if len(node) > 0 and isinstance(node[0], str) and _node_type_equals(node[0], 'py.comparison_operator'):
      return _matcher_has_str_token(node, 'is')
    for child in node[1:]:
      if _rec(child):
        return True
    return False
  return _rec(ast)


def _ast_contains_is_not_comparison(ast: list) -> bool:
  if not isinstance(ast, list):
    return False
  def _rec(node) -> bool:
    if not isinstance(node, list):
      return False
    if len(node) > 0 and isinstance(node[0], str) and _node_type_equals(node[0], 'py.comparison_operator'):
      return _matcher_has_str_token(node, 'is') and _matcher_has_str_token(node, 'not')
    for child in node[1:]:
      if _rec(child):
        return True
    return False
  return _rec(ast)


def _rule_uses_strict_eq_or_object_is(rule_ut: p_ruleset.TRuleBase) -> bool:
  rule_str = rule_ut.to_rule_str()
  if '(str "===")' in rule_str or '(str "!==")' in rule_str:
    return True
  if '(val "Object")' in rule_str and '(val "is")' in rule_str:
    return True
  return False


def _rule_uses_null_equality(rule_ut: p_ruleset.TRuleBase) -> bool:
  rule_str = rule_ut.to_rule_str()
  if '(js.null (str "null"))' not in rule_str:
    return False
  return '(str "==")' in rule_str


def _rule_uses_null_inequality(rule_ut: p_ruleset.TRuleBase) -> bool:
  rule_str = rule_ut.to_rule_str()
  if '(js.null (str "null"))' not in rule_str:
    return False
  return '(str "!=")' in rule_str


def _range_cursor_has_py_none(range_cursor: tuple) -> bool:
  elems, start_idx, end_idx = range_cursor
  def _node_has_py_none(node) -> bool:
    if not isinstance(node, list):
      return False
    if len(node) > 0 and isinstance(node[0], str) and _node_type_equals(node[0], 'py.none'):
      return True
    for child in node:
      if _node_has_py_none(child):
        return True
    return False
  for idx in range(start_idx, end_idx):
    if _node_has_py_none(elems[idx]):
      return True
  return False


def _range_cursor_has_is_not(range_cursor: tuple) -> bool:
  elems, start_idx, end_idx = range_cursor
  def _elem_is_token(elem, token: str) -> bool:
    if isinstance(elem, str) and _strip_quotes(elem) == token:
      return True
    return isinstance(elem, list) and len(elem) == 2 and elem[0] == 'str' and _strip_quotes(elem[1]) == token
  def _node_has_is_not_comp(node) -> bool:
    if not isinstance(node, list):
      return False
    if len(node) > 0 and isinstance(node[0], str) and _node_type_equals(node[0], 'py.comparison_operator'):
      has_is = False
      has_not = False
      for item in node[1:]:
        if isinstance(item, list) and len(item) == 2 and item[0] == 'str':
          if _strip_quotes(item[1]) == 'is':
            has_is = True
          elif _strip_quotes(item[1]) == 'not':
            has_not = True
      if has_is and has_not:
        return True
    for child in node:
      if _node_has_is_not_comp(child):
        return True
    return False
  for idx in range(start_idx, end_idx - 1):
    if _elem_is_token(elems[idx], 'is') and _elem_is_token(elems[idx + 1], 'not'):
      return True
  for idx in range(start_idx, end_idx):
    if _node_has_is_not_comp(elems[idx]):
      return True
  return False


def _range_cursor_has_is(range_cursor: tuple) -> bool:
  elems, start_idx, end_idx = range_cursor
  def _node_has_is_comp(node) -> bool:
    if not isinstance(node, list):
      return False
    if len(node) > 0 and isinstance(node[0], str) and _node_type_equals(node[0], 'py.comparison_operator'):
      return _matcher_has_str_token(node, 'is')
    for child in node:
      if _node_has_is_comp(child):
        return True
    return False
  for idx in range(start_idx, end_idx):
    if _node_has_is_comp(elems[idx]):
      return True
  return False


def _filter_none_comparison_rules(
  matcher_group: List[p_ruleset.TRuleBase],
  matched_ast: Optional[list],
  matcher: list,
  range_cursor: Optional[tuple] = None
) -> List[p_ruleset.TRuleBase]:
  has_py_none = False
  has_is = False
  is_not_none = False
  if matched_ast:
    has_py_none = _ast_contains_node_type(matched_ast, 'py.none')
    has_is = _ast_contains_is_comparison(matched_ast)
    is_not_none = _ast_contains_is_not_comparison(matched_ast)
  elif range_cursor:
    has_py_none = _range_cursor_has_py_none(range_cursor)
    has_is = _range_cursor_has_is(range_cursor)
    is_not_none = _range_cursor_has_is_not(range_cursor)
  if not has_py_none or not has_is:
    return matcher_group
  filtered = []
  for trule in matcher_group:
    if _rule_uses_strict_eq_or_object_is(trule):
      continue
    if is_not_none:
      if _rule_uses_null_inequality(trule):
        filtered.append(trule)
    else:
      if _rule_uses_null_equality(trule):
        filtered.append(trule)
  return filtered


def assert_matchers_match(matcher_group: List[p_ruleset.TRuleBase]) -> None:
  '''
  Assert that all rules in the list have the same matcher signature.
  Assert that rule idx are sorted in ascending order.
  PARAM matcher_group: a list of TRuleBase objects.
  '''
  assert len(matcher_group) > 0, 'Expected at least one rule'
  first_rule_signature = matcher_group[0].get_matcher_signature()
  for rule in matcher_group[1:]:
    assert rule.get_matcher_signature() == first_rule_signature, \
      f'Expected all rules to have the same matcher signature, got {rule.get_matcher_signature()}'


def _choicable_node_get_context_node(node: pvis.AbstractNode) -> pvis.AbstractNode:
  '''
  Given a choicable node, return its context node.
  Context node is the nearest ancestor that is either
  a statement node that participates in readonly-choice generation.
  '''

  _CONTEXT_NODE_TYPES = (
    pvpy.ExpressionStatementNode,
    pvpy.ForStatementNode,
    pvpy.IfStatementNode,
    pvpy.RaiseStatementNode,
    pvpy.ReturnStatementNode,
    pvpy.WhileStatementNode,
    pvpy.AssertStatementNode,
    pvpy.DeleteStatementNode,
  )
  is_context_node = lambda node: \
    isinstance(node, _CONTEXT_NODE_TYPES)

  cursor = node.parent
  while cursor is not None:
    if is_context_node(cursor):
      return cursor
    cursor = cursor.parent
  raise ValueError('No context node found')


def _reset_expr_subject(
  expr_subject: p_subject.PirelSubject,
  test_scr_matched_rc_chid: Tuple[int, int, int],
  rule_idx: int
) -> None:
  '''
  Modifies expr_subject in-place to reset its choices and verified choice options.
  '''
  expr_subject.choices['choices_list'] = []

  '''
  Update the verified choice options with the new choice option.
  '''
  vrf_ch_opts_dict = {
    chid: rule_idxs for chid, rule_idxs in expr_subject.verified_choice_options
  }
  vrf_ch_opts_dict[test_scr_matched_rc_chid] = [rule_idx]
  vrf_ch_opts = list(vrf_ch_opts_dict.items())
  vrf_ch_opts.sort(key=lambda x: x[0])  # sort by choice identifier

  expr_subject.verified_choice_options = vrf_ch_opts


def _iter_duoglot_nt_nodes(ast: list):
  if not isinstance(ast, list):
    return
  yield ast
  for child in ast[2:]:
    if isinstance(child, list):
      yield from _iter_duoglot_nt_nodes(child)


def _normalize_identifier_val(val: str) -> str:
  if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
    return val[1:-1]
  return val


def _is_myexactlog_expr_stmt(ast_node: list) -> bool:
  if ast_node[0] != 'py.expression_statement':
    return False
  nt_children = [ch for ch in ast_node[2:] if isinstance(ch, list)]
  if len(nt_children) != 1:
    return False
  call_node = nt_children[0]
  if call_node[0] != 'py.call':
    return False
  call_children = [ch for ch in call_node[2:] if isinstance(ch, list)]
  if not call_children:
    return False
  fn_node = call_children[0]
  if fn_node[0] != 'py.identifier' or len(fn_node) < 3:
    return False
  fn_val = _normalize_identifier_val(fn_node[2])
  return fn_val == p_consts.PIREL_LOG_OBJ_FN_NAME


def _filter_myexactlog_new_expr_rules(
  matcher_group: List[p_ruleset.TRuleBase]
) -> List[p_ruleset.TRuleBase]:
  filtered = []
  for trule in matcher_group:
    rule_str = trule.to_rule_str()
    if 'js.new_expression' in rule_str:
      continue
    filtered.append(trule)
  if len(filtered) != len(matcher_group):
    logger.debug(
      f'Filtered {len(matcher_group) - len(filtered)} js.new_expression rule(s) '
      f'for myexactlog.')
  return filtered


def _get_log_stat_rule_idx_in_matcher_group(
  translation_rules_main_code: Optional[str]
) -> int:
  if not translation_rules_main_code:
    return 0

  try:
    log_rule_parsed = d_grammar_rules.parse_analyze_rules_optim(
      p_utils.read_text(p_consts.LOG_STAT_RULE_FPATH))[0]
  except Exception as err:
    logger.warning(f'Failed to parse log statement rule: {err}')
    return 0

  log_rule_pretty = d_grammar_rules.pretty_rule(log_rule_parsed)
  log_match_sig = str(log_rule_parsed['match'])

  try:
    rules_parsed = d_grammar_rules.parse_analyze_rules_optim(translation_rules_main_code)
  except Exception as err:
    logger.warning(f'Failed to parse translation rules for log-stat choices: {err}')
    return 0

  idx_in_group = 0
  for rule_parsed in rules_parsed:
    if str(rule_parsed.get('match')) != log_match_sig:
      continue
    if d_grammar_rules.pretty_rule(rule_parsed) == log_rule_pretty:
      return idx_in_group
    idx_in_group += 1

  logger.warning('Log statement rule not found in translation rules; defaulting to index 0.')
  return 0


def _get_forced_log_stat_choice_options(
  src_main_code: str,
  log_rule_idx_in_group: int
) -> List[Tuple[Tuple[int, int, int], List[int]]]:
  try:
    dgast, _ = d_ast_parse.parse_text_dbg(src_main_code, 'py')
  except Exception as err:
    logger.warning(f'Failed to parse src_main_code for log-stat choices: {err}')
    return []

  choices = {}
  for node in _iter_duoglot_nt_nodes(dgast):
    if not _is_myexactlog_expr_stmt(node):
      continue
    range_cursor = d_ast_parse.get_range_cursor(dgast, node[1])
    choice_identifier = d_ast_parse.range_cursor_to_choice_identifier(range_cursor)
    choices[choice_identifier] = [log_rule_idx_in_group]

  return sorted(choices.items(), key=lambda x: x[0])


def add_forced_log_stat_choice_options(
  verified_choice_options: List[Tuple[Tuple[int, int, int], List[int]]],
  src_main_code: str,
  translation_rules_main_code: Optional[str] = None
) -> List[Tuple[Tuple[int, int, int], List[int]]]:
  log_rule_idx_in_group = _get_log_stat_rule_idx_in_matcher_group(
    translation_rules_main_code)
  forced_choice_options = _get_forced_log_stat_choice_options(
    src_main_code, log_rule_idx_in_group)
  if not forced_choice_options:
    return verified_choice_options

  if verified_choice_options:
    _sanity_check_choice_options(verified_choice_options)
  _sanity_check_choice_options(forced_choice_options)

  merged = {k: v for k, v in verified_choice_options}
  for choice_identifier, choice_idxs in forced_choice_options:
    if choice_identifier in merged and merged[choice_identifier] != choice_idxs:
      logger.debug(f'Overriding verified choices for log statement: {choice_identifier}')
    merged[choice_identifier] = choice_idxs

  return sorted(merged.items(), key=lambda x: x[0])


def _get_non_log_expr_stmt_snippet_under(
  range_cursor: Tuple[list, int, int],
  ann: dict,
  src_code: str,
) -> Optional[str]:
  try:
    ast = d_ast_parse.range_cursor_to_ast_node(range_cursor)
  except Exception:
    return None

  if ast[0] == 'py.expression_statement':
    if not _is_myexactlog_expr_stmt(ast):
      return d_ast_parse.range_cursor_pretty_print(range_cursor, ann, src_code)
    prev_stmt = _get_prev_non_log_expr_stmt_snippet_in_parent(
      range_cursor, ann, src_code)
    if prev_stmt is not None:
      return prev_stmt

  candidates = []
  try:
    all_range_cursors = d_ast_parse.get_all_range_cursors_under(range_cursor)
  except Exception:
    return None

  for rc in all_range_cursors:
    try:
      rc_ast = d_ast_parse.range_cursor_to_ast_node(rc)
    except Exception:
      continue
    if rc_ast[0] != 'py.expression_statement':
      continue
    if _is_myexactlog_expr_stmt(rc_ast):
      continue
    nid = rc_ast[1]
    if nid not in ann:
      continue
    start_byte, end_byte, _, _ = ann[nid]
    snippet = d_ast_parse.range_cursor_pretty_print(rc, ann, src_code)
    candidates.append((start_byte, end_byte, snippet))

  if not candidates:
    return None
  candidates.sort(key=lambda x: (x[0], x[1]))
  return candidates[-1][2]


def _get_prev_non_log_expr_stmt_snippet_in_parent(
  range_cursor: Tuple[list, int, int],
  ann: dict,
  src_code: str,
) -> Optional[str]:
  parent_ast, start_idx, _ = range_cursor
  if not isinstance(parent_ast, list):
    return None
  for idx in range(start_idx - 1, 1, -1):
    if idx >= len(parent_ast):
      continue
    child = parent_ast[idx]
    if not isinstance(child, list):
      continue
    if child[0] != 'py.expression_statement':
      continue
    if _is_myexactlog_expr_stmt(child):
      continue
    rc = (parent_ast, idx, idx + 1)
    try:
      return d_ast_parse.range_cursor_pretty_print(rc, ann, src_code)
    except Exception:
      continue
  return None


def _get_range_cursor_span(
  range_cursor: Tuple[list, int, int],
  ann: dict,
) -> Optional[Tuple[int, int]]:
  try:
    node = d_ast_parse.range_cursor_to_ast_node(range_cursor)
  except Exception:
    node = None

  for candidate in (node, range_cursor[0]):
    if not isinstance(candidate, list) or len(candidate) < 2:
      continue
    nid = candidate[1]
    if not isinstance(nid, int) or nid not in ann:
      continue
    start_byte, end_byte, _, _ = ann[nid]
    return (start_byte, end_byte)
  return None


def _get_enclosing_non_log_expr_stmt_snippet(
  range_cursor: Tuple[list, int, int],
  ast: list,
  ann: dict,
  src_code: str,
) -> Optional[str]:
  span = _get_range_cursor_span(range_cursor, ann)
  if span is None:
    return None
  target_start, target_end = span

  best = None
  for node in _iter_duoglot_nt_nodes(ast):
    if node[0] != 'py.expression_statement':
      continue
    if _is_myexactlog_expr_stmt(node):
      continue
    nid = node[1]
    if nid not in ann:
      continue
    start_byte, end_byte, _, _ = ann[nid]
    if start_byte <= target_start and end_byte >= target_end:
      span_len = end_byte - start_byte
      if best is None or span_len < best[0]:
        best = (span_len, nid)

  if best is None:
    return None
  try:
    stmt_rc = d_ast_parse.get_range_cursor(ast, best[1])
  except Exception:
    return None
  return d_ast_parse.range_cursor_pretty_print(stmt_rc, ann, src_code)


def choice_identifier_to_snippet(
  choice_identifier: Tuple[int, int, int],
  src_main_code: str
) -> Optional[str]:
  try:
    dgast, dgann = d_ast_parse.parse_text_dbg(src_main_code, 'py')
  except Exception as err:
    logger.debug(f'Failed to resolve snippet for {choice_identifier}: {err}')
    return None
  try:
    range_cursor = d_ast_parse.choice_identifier_to_range_cursor(choice_identifier, dgast)
  except Exception as err:
    logger.debug(f'Failed to resolve range cursor for {choice_identifier}: {err}')
    try:
      range_cursor = d_ast_parse.get_range_cursor(dgast, choice_identifier[0])
    except Exception as err2:
      logger.debug(f'Failed to resolve fallback range cursor for {choice_identifier}: {err2}')
      return None

  debug_ctx = None
  def _get_debug_ctx() -> str:
    nonlocal debug_ctx
    if debug_ctx is not None:
      return debug_ctx
    rc_type = None
    try:
      rc_ast = d_ast_parse.range_cursor_to_ast_node(range_cursor)
      if isinstance(rc_ast, list):
        rc_type = rc_ast[0]
    except Exception:
      rc_type = None
    span = _get_range_cursor_span(range_cursor, dgann)
    text = None
    try:
      text = d_ast_parse.range_cursor_pretty_print(range_cursor, dgann, src_main_code)
    except Exception:
      text = None
    if text is not None and len(text) > 200:
      text = text[:200] + '...'
    debug_ctx = f'type={rc_type} span={span} text={text!r}'
    return debug_ctx

  snippet = _get_non_log_expr_stmt_snippet_under(range_cursor, dgann, src_main_code)
  if snippet is None:
    logger.debug(
      f'No non-log expr stmt snippet under range cursor for {choice_identifier} '
      f'({_get_debug_ctx()})'
    )
    snippet = _get_enclosing_non_log_expr_stmt_snippet(
      range_cursor, dgast, dgann, src_main_code)
  if snippet is None:
    logger.debug(
      f'No enclosing non-log expr stmt snippet for {choice_identifier} '
      f'({_get_debug_ctx()})'
    )
  return snippet


def _find_logged_expr_in_test_script_str(
  test_script_str: str,
  test_script_ast: list,
  test_script_ann: dict,
  expr_str: str,
  log_stat_idx: Optional[int] = None,
) -> tuple:
  '''
  Find all range cursors in the test_script_str that match the expr_str.
  PARAM test_script_str: instrumented script that is passed to the rule applicator
  '''
  def _norm_ws(text: str) -> str:
    return re.sub(r'\s+', '', text)

  def _find_assignment_rhs_by_expr(
    expr_text: str,
    lhs_hint: Optional[str],
  ) -> Optional[tuple]:
    matches: List[tuple] = []
    lhs_hint_matches: List[tuple] = []

    for rc in d_ast_parse.range_cursor_seq_descending_from_ast(test_script_ast):
      ast = d_ast_parse.range_cursor_to_ast_node(rc)
      if ast[0] != 'py.assignment':
        continue
      child_rcs = d_ast_parse.get_nt_children_as_range_cursors(ast)
      if len(child_rcs) < 2:
        continue
      lhs_rc = child_rcs[0]
      rhs_rc = child_rcs[-1]
      rhs_pp = d_ast_parse.range_cursor_pretty_print(rhs_rc, test_script_ann, test_script_str)
      if _norm_ws(rhs_pp) != _norm_ws(expr_text):
        continue
      matches.append(rhs_rc)
      if lhs_hint is None:
        continue
      lhs_pp = d_ast_parse.range_cursor_pretty_print(lhs_rc, test_script_ann, test_script_str)
      if _norm_ws(lhs_pp) == _norm_ws(lhs_hint):
        lhs_hint_matches.append(rhs_rc)

    if len(lhs_hint_matches) == 1:
      return lhs_hint_matches[0]
    if len(matches) == 1:
      return matches[0]
    return None

  if log_stat_idx is not None:
    matches = []
    for rc in d_ast_parse.range_cursor_seq_descending_from_ast(test_script_ast):
      call_ast = d_ast_parse.range_cursor_to_ast_node(rc)
      if call_ast[0] != 'py.call':
        continue

      call_children = d_ast_parse.get_nt_children_as_range_cursors(call_ast)
      if len(call_children) < 2:
        continue
      fn_rc, arglist_rc = call_children[:2]
      fn_pp = d_ast_parse.range_cursor_pretty_print(fn_rc, test_script_ann, test_script_str)
      if fn_pp != 'myexactlog':
        continue

      arglist_ast = d_ast_parse.range_cursor_to_ast_node(arglist_rc)
      arg_rcs = d_ast_parse.get_nt_children_as_range_cursors(arglist_ast)
      if len(arg_rcs) < 2:
        continue

      idx_pp = d_ast_parse.range_cursor_pretty_print(
        arg_rcs[0], test_script_ann, test_script_str)
      if idx_pp != str(log_stat_idx):
        continue
      matches.append(arg_rcs[1])

    assert len(matches) == 1, (
      f'Expected exactly one match for logged expression in test script with '
      f'log_stat_idx={log_stat_idx}'
    )
    logged_expr_rc = matches[0]
    logged_expr_pp = d_ast_parse.range_cursor_pretty_print(
      logged_expr_rc, test_script_ann, test_script_str)
    if _norm_ws(logged_expr_pp) == _norm_ws(expr_str):
      return logged_expr_rc

    # Root cause:
    # Assignment-RHS fallback may intentionally log `lhs` (not `rhs`) to avoid
    # re-evaluating side-effectful RHS expressions such as function calls.
    # Then this resolver can no longer find the original expression directly
    # from myexactlog's second argument.
    # Patch reason:
    # When logged arg != target expr, recover the original assignment RHS
    # cursor by expression text (and prefer same-LHS candidate) so matcher
    # validation still targets the intended node.
    rhs_rc = _find_assignment_rhs_by_expr(expr_str, lhs_hint=logged_expr_pp)
    if rhs_rc is not None:
      logger.debug(
        f'Recovered assignment RHS cursor for expression validation '
        f'(log_stat_idx={log_stat_idx}): '
        f'logged_arg="{logged_expr_pp}", target_expr="{expr_str}"')
      return rhs_rc

    logger.debug(
      f'Could not recover RHS cursor for expression validation '
      f'(log_stat_idx={log_stat_idx}); using logged arg directly. '
      f'logged_arg="{logged_expr_pp}", target_expr="{expr_str}"')
    return logged_expr_rc

  re_expr = re.compile(rf'myexactlog\((\d+), ({re.escape(expr_str)})\)')
  matches = re.finditer(re_expr, test_script_str)
  matches = list(matches)

  '''
  There should be exactly one match for the logged expression.
  '''
  assert len(matches) == 1, 'Expected exactly one match for logged expression in test script'
  expr_st_idx = matches[0].start(2)
  expr_end_idx = matches[0].end(2)

  # get the AST node id that correspond to the expr_str
  for nid, (sidx, eidx, _, _) in test_script_ann.items():
    if sidx == expr_st_idx and eidx == expr_end_idx:
      range_cursor = d_ast_parse.get_range_cursor(test_script_ast, nid)
      return range_cursor

  raise ValueError('Should not happen: no range cursor found for logged expression')


def _find_unique_explicit_log_arglist(
  root_node: pvis.AbstractNode
) -> pvpy.ArgumentListNode:
  '''
  Find the one explicit myexactlog(...) call inserted for expression validation
  before automatic log insertion/indexing adds any extra logging calls.
  '''
  found: List[pvpy.ArgumentListNode] = []

  def _rec(node: pvis.AbstractNode) -> None:
    if isinstance(node, pvpy.CallNode):
      function_name = node.function
      if (
        isinstance(function_name, pvpy.IdentifierNode) and
        function_name.val() == p_consts.PIREL_LOG_OBJ_FN_NAME
      ):
        found.append(node.arguments)
    for child in node.get_nt_children():
      _rec(child)

  _rec(root_node)
  assert len(found) == 1, 'Expected exactly one explicit myexactlog call before indexing'
  return found[0]


class _TargetLogStatementsIndexer(pvpy.LogStatementsIndexer):
  '''
  Index log statements while recording the index assigned to
  the explicit myexactlog(...) inserted for expression validation.
  '''
  def __init__(
    self,
    function_name: str,
    target_arglist: pvpy.ArgumentListNode,
    is_three_split: bool,
  ):
    super().__init__(function_name=function_name)
    self.target_arglist = target_arglist
    self.target_index: Optional[int] = None
    self.is_three_split = is_three_split

  def visit_ModuleNode(self, node: pvpy.ModuleNode) -> None:
    if not self.is_three_split:
      self.default_visit(node)
      return
    super().visit_ModuleNode(node)

  def visit_ArgumentListNode(self, node: pvpy.ArgumentListNode) -> None:
    parent = node.get_parent()
    if (
      node is self.target_arglist and
      isinstance(parent, pvpy.CallNode) and
      isinstance(parent.function, pvpy.IdentifierNode) and
      parent.function.val() == p_consts.PIREL_LOG_OBJ_FN_NAME
    ):
      self.target_index = self.counter
    super().visit_ArgumentListNode(node)


def _create_expr_src_main_code_for_val(
  is_three_split: bool,
  matched_range_cursor: tuple,
  matcher_group: List[p_ruleset.TRuleBase],
  src_main_code: str,
  pre_context: str,
  dgann: dict,
  ruleset: p_ruleset.Ruleset,
) -> Tuple[str, int]:
  '''
  Create the validation source for an expression and return the concrete
  myexactlog index assigned to the inserted expression logger.
  '''
  log_stat_str = _create_log_stat_str_for_expr(
    matched_range_cursor,
    dgann,
    src_main_code,
    matcher_group,
    ruleset
  )

  # Root cause:
  # expression fallback snippets can be multi-line (e.g. assignment replay +
  # myexactlog), and text-based statement lookup for break insertion can fail.
  # Patch reason:
  # mirror statement-validation flow: keep PRE_CTX marker, instrument breaks by
  # marker nid, then replace marker with concrete expression snippet.
  expr_src_main_code = pre_context
  function_name = 'f_gold'

  if is_three_split:  # wrap in f_gold
    function_headers = [line for line in src_main_code.splitlines()
                        if line.startswith('def f_gold(')]
    assert len(function_headers) == 1
    fn_header = function_headers[0].strip()
    assert fn_header.endswith('):')
    expr_src_main_code = f'{fn_header}\n{p_utils.indent(expr_src_main_code, 4)}'

  spec_stmt_nid = p_pirel._find_pre_ctx_spec_statement_nid(expr_src_main_code)
  expr_src_main_code = p_pirel._instrument_with_break_statements(
    # Root cause:
    # During EOT/expression validation, ancestor-only break insertion misses
    # caller-side loops for callee statements, while all-loops may over-trim
    # unrelated loop paths and perturb runtime state.
    # Patch reason:
    # Instrument only execution-relevant loops (ancestors + caller-chain)
    # so validation keeps progressing without distorting unrelated control flow.
    expr_src_main_code,
    p_consts.PRE_CTX_SPEC_IDENT,
    loop_scope='ancestors_and_callers',
    statement_nid=spec_stmt_nid,
  )
  expr_src_main_code = p_pirel._combine_prectx_and_simple_ntext(expr_src_main_code, log_stat_str)

  expr_tree = pvpy.Tree.from_str(expr_src_main_code)
  target_arglist = _find_unique_explicit_log_arglist(expr_tree.root_node)

  if is_three_split:
    inserter = pvpy.LogStatementInserter(function_name=function_name)
  else:
    inserter = pvpy.LogInserterNo3Split(function_name=function_name)
  inserter.visit(expr_tree.root_node)

  indexer = _TargetLogStatementsIndexer(
    function_name,
    target_arglist,
    is_three_split,
  )
  indexer.visit(expr_tree.root_node)
  assert indexer.target_index is not None, 'Expected explicit myexactlog to be indexed'

  pp = pvpy.PrettyPrinter(indent_with='    ')
  code = pp.visit(expr_tree.root_node)
  if code is None:
    code = '\n'.join(pp.lines)
  return code.strip(), indexer.target_index


def _create_subject_for_expr(
  src_test_script: str,
  is_three_split: bool,
  translation_rules_test_code: str,
  ruleset: p_ruleset.Ruleset,
  subject_name: str,
) -> p_subject.PirelSubject:
  '''
  Create a subject for validating a rule for expression.
  '''

  # all attributes of PirelSubject instance set explicitly
  benchmark_name = 'n/a'
  name = subject_name
  src_program = src_test_script
  src_lang = 'py'
  tar_lang = 'js'
  translation_rules_main_code = \
    p_utils.read_text(p_consts.RULE_VAL_PRIORITY_RULES_FPATH) + '\n\n' + \
    p_utils.read_text(p_consts.LOG_STAT_RULE_FPATH) + '\n\n' + \
    ruleset.to_str_ruleset() + '\n\n' + \
    p_utils.read_text(p_consts.RULE_VAL_EXTRA_RULES_FPATH)
  # translation_rules_test_code  # already set
  auto_backward = True
  choices = {'type': 'ASTNODE', 'choices_list': []}
  verified_choice_options = []

  # create a subject instance
  expr_subject = p_subject.PirelSubject(
    benchmark_name, name, src_program, src_lang, tar_lang, is_three_split)
  expr_subject.translation_rules_main_code = translation_rules_main_code
  expr_subject.translation_rules_test_code = translation_rules_test_code
  expr_subject.auto_backward = auto_backward
  expr_subject.choices = choices
  expr_subject.verified_choice_options = verified_choice_options

  # override verified_choice_options with verified rules
  expr_subject.verified_choice_options = ruleset.get_choice_options_from_verified_rules(
    expr_subject.get_src_main_code())
  expr_subject.verified_choice_options = add_forced_log_stat_choice_options(
    expr_subject.verified_choice_options,
    expr_subject.get_src_main_code(),
    expr_subject.translation_rules_main_code
  )

  return expr_subject


def _is_bound_method_alias_rhs_match_assignment(
  matched_range_cursor: tuple
) -> bool:
  '''
  Return True for assignment RHS nodes shaped like:
    <identifier_ending_with__match> = <something>.match

  Why this exists:
  expression-level validation was logging `<something>.match` directly and
  repeatedly producing false semantic mismatches like:
  Expected "['function']", got "['null']" at the same log statement index.
  Such nodes are context-sensitive in JS (method extraction needs binding),
  so validating `<something>.match` as a standalone logged expression is noisy.
  '''
  assert isinstance(matched_range_cursor, tuple) and len(matched_range_cursor) == 3, 'sanity check'
  parent_ast, child_st_idx, child_en_idx = matched_range_cursor
  if child_st_idx + 1 != child_en_idx:
    return False

  if not d_ast_parse.is_elem_non_terminal(parent_ast):
    return False
  if parent_ast[0] != 'py.assignment':
    return False

  rhs_ast = d_ast_parse.range_cursor_to_ast_node(matched_range_cursor)
  if not d_ast_parse.is_elem_non_terminal(rhs_ast):
    return False
  if rhs_ast[0] != 'py.attribute':
    return False

  nt_child_idxs = [
    idx for idx in range(2, len(parent_ast))
    if d_ast_parse.is_elem_non_terminal(parent_ast[idx])
  ]
  if len(nt_child_idxs) < 2:
    return False
  # Assignment RHS is the right-most non-terminal child.
  if child_st_idx != nt_child_idxs[-1]:
    return False

  lhs_ast = parent_ast[nt_child_idxs[0]]
  if not d_ast_parse.is_elem_non_terminal(lhs_ast):
    return False
  if lhs_ast[0] != 'py.identifier':
    return False
  if len(lhs_ast) < 3 or not isinstance(lhs_ast[2], str):
    return False
  lhs_name = _strip_quotes(lhs_ast[2])
  if not lhs_name.endswith('_match'):
    return False

  rhs_nt_children = [
    child for child in rhs_ast[2:]
    if d_ast_parse.is_elem_non_terminal(child)
  ]
  if len(rhs_nt_children) < 2:
    return False
  rhs_attr_name_ast = rhs_nt_children[-1]
  if rhs_attr_name_ast[0] != 'py.identifier':
    return False
  if len(rhs_attr_name_ast) < 3 or not isinstance(rhs_attr_name_ast[2], str):
    return False
  rhs_attr_name = _strip_quotes(rhs_attr_name_ast[2])

  return rhs_attr_name == 'match'


def _get_assignment_lhs_for_rhs_range_cursor(
  matched_range_cursor: tuple,
  dgann: dict,
  src_main_code: str,
) -> Optional[str]:
  '''
  If matched_range_cursor points to RHS of a `py.assignment`, return the
  assignment LHS text. Otherwise return None.
  '''
  assert isinstance(matched_range_cursor, tuple) and len(matched_range_cursor) == 3, 'sanity check'
  parent_ast, child_st_idx, child_en_idx = matched_range_cursor
  if child_st_idx + 1 != child_en_idx:
    return None

  if not d_ast_parse.is_elem_non_terminal(parent_ast):
    return None
  if parent_ast[0] != 'py.assignment':
    return None

  nt_child_idxs = [
    idx for idx in range(2, len(parent_ast))
    if d_ast_parse.is_elem_non_terminal(parent_ast[idx])
  ]
  if len(nt_child_idxs) < 2:
    return None
  # Assignment RHS is the right-most non-terminal child.
  if child_st_idx != nt_child_idxs[-1]:
    return None

  lhs_idx = nt_child_idxs[0]
  lhs_rc = (parent_ast, lhs_idx, lhs_idx + 1)
  lhs_str = d_ast_parse.range_cursor_pretty_print(lhs_rc, dgann, src_main_code)
  if lhs_str.strip() == '':
    return None
  return lhs_str


def _create_log_stat_str_for_expr(
  matched_range_cursor: tuple,
  dgann: dict,
  src_main_code: str,
  matcher_group: List[p_ruleset.TRuleBase],
  ruleset: p_ruleset.Ruleset
) -> str:
  '''
  Return a log statement that logs the AST.
  If we cannot validate the matched_range_cursor with the given matcher_group,
  then we need to mark the matching rules as unverifiable for the matched_range_cursor.
  '''
  matched_ast_str = d_ast_parse.range_cursor_pretty_print(matched_range_cursor, dgann, src_main_code)
  matched_ast = d_ast_parse.range_cursor_to_ast_node(matched_range_cursor)
  matched_ast_encoded = d_ast_parse.range_cursor_encode(matched_range_cursor, dgann, src_main_code)
  log_expr_only_str = f'myexactlog({matched_ast_str})'
  log_stat_str = log_expr_only_str

  lhs_for_rhs = _get_assignment_lhs_for_rhs_range_cursor(
    matched_range_cursor, dgann, src_main_code)
  if lhs_for_rhs is not None:
    # Root cause:
    # Logging assignment RHS as `myexactlog(rhs)` evaluates RHS twice.
    # For call-like RHS (e.g., compare_fractions(10)), the second evaluation can
    # alter branch outcomes and break validation with runtime errors
    # (e.g., UnboundLocalError from different branch-local initialization).
    # Patch reason:
    # Replay assignment once, then log LHS for call RHS; for pure RHS keep
    # logging RHS directly.
    if (
      d_ast_parse.is_elem_non_terminal(matched_ast) and
      matched_ast[0] == 'py.call'
    ):
      log_stat_str = f'{lhs_for_rhs} = {matched_ast_str}\nmyexactlog({lhs_for_rhs})'
    else:
      log_stat_str = f'{lhs_for_rhs} = {matched_ast_str}\n{log_expr_only_str}'

  # Bound-method alias assignments (e.g., `_x_match = _x.match`) are not
  # reliably verifiable as standalone expression logs in JS.
  # Without this guard we hit false semantic errors (function vs null trace
  # mismatch) and rule validation drifts to the wrong matcher fragment.
  # Mark matcher-group rules as unverifiable for this cursor and skip.
  if _is_bound_method_alias_rhs_match_assignment(matched_range_cursor):
    logger.debug(
      f'Expression "{matched_ast_str}" is context-sensitive '
      f'(bound-method alias assignment RHS); skipping standalone validation.')
    for trule in matcher_group:
      ruleset.update_unverifiable_rules(matched_ast_encoded, trule)
    raise ExprLogStatContextError()

  '''
  Make sure that the log statement is parseable.
  Examples where there are parse errors:
  a = m[i:j]
        ^^^
  myexactlog(i:j)
  '''
  if p_utils.does_have_parse_error(log_stat_str, 'py'):
    logger.debug(
      f'Expression "{matched_ast_str}" is unverifiable due to '
      f'parse error in log statement "{log_stat_str}".')
    for trule in matcher_group:
      ruleset.update_unverifiable_rules(matched_ast_encoded, trule)
    raise ExprLogStatHasParseError()

  '''
  Make sure that the logged expression has the same AST
  structure as the original expression.
  ["py.module", 0, ["py.expression_statement", 1, ["py.call", 2,
    ["py.identifier", 3, "\"myexactlog\""],
    ["py.argument_list", 4,
      "\"(\"",
      <sub-AST for logged expression is rooted here>,
      "\")\""
    ]
  ]]]
  '''
  # `log_stat_str` can be multi-statement for assignment-RHS fallback.
  # Use canonical one-line log expression for AST isomorphism check.
  log_stat_ast, _ = d_ast_parse.parse_text_dbg(log_expr_only_str, 'py')
  logged_expr_ast = log_stat_ast[2][2][3][3]

  if not d_ast_parse.are_nodes_equal(matched_ast, logged_expr_ast):
    logger.debug(
      f'Expression "{matched_ast_str}" is unverifiable due to '
      f'tree non-isomorphism in log statement "{log_stat_str}".')
    for trule in matcher_group:
      ruleset.update_unverifiable_rules(matched_ast_encoded, trule)
    raise ExprLogStatContextError()

  return log_stat_str


def _create_test_script_str_for_expr(
  is_three_split: bool,
  matched_range_cursor: tuple,
  matcher_group: List[p_ruleset.TRuleBase],
  src_test_code: Optional[str],
  src_main_code: str,
  pre_context: str,
  dgann: dict,
  ruleset: p_ruleset.Ruleset,
) -> Tuple[str, int]:
  '''
  a = ((15 + (   7 * (math.sqrt(5))   )) / 4) * (math.pow(side, 3))
                 ^^^^^^^^^^^^^^^^^^

  myexactlog(7 * (math.sqrt(5)))

  def test():
    f_gold()
  def f_gold():
    myexactlog(7 * (math.sqrt(5)))
  test()

  NOTE We need to create a test script which combines
  1. the test function - use the test function that we generated previously
  2. the f_gold function
  3. the test function call
  '''
  expr_src_main_code, log_stat_idx = _create_expr_src_main_code_for_val(
    is_three_split,
    matched_range_cursor,
    matcher_group,
    src_main_code,
    pre_context,
    dgann,
    ruleset,
  )

  if is_three_split:
    test_script_str = p_consts.TEST_SCRIPT_TEMPLATE.format(
      test_code=src_test_code,
      main_code=expr_src_main_code,
      test_call_code='test()')
    return test_script_str, log_stat_idx

  return expr_src_main_code, log_stat_idx


def _get_base_ruleset() -> p_ruleset.Ruleset:
  '''
  Load and cache base ruleset used for fast-path rule verification.
  Uses overriding rulesets when provided, mirroring p_learn_apply_rules.
  '''
  global _CACHE_base_ruleset, _CACHE_base_ruleset_key

  overriding_rulesets = Config.overriding_rulesets or []
  if len(overriding_rulesets) == 0:
    cache_key: Tuple[str, ...] = (str(p_consts.STARTING_RULESET_FPATH),)
  else:
    cache_key = tuple(str(fpath) for fpath in overriding_rulesets)

  if _CACHE_base_ruleset is not None and _CACHE_base_ruleset_key == cache_key:
    return _CACHE_base_ruleset

  if len(overriding_rulesets) > 0:
    base_ruleset = p_ruleset.Ruleset()
    for fpath in overriding_rulesets:
      if fpath.suffix == '.snart':
        ruleset = p_ruleset.Ruleset.from_starting_ruleset(p_utils.read_text(fpath))
        base_ruleset.extend(ruleset)
      elif fpath.suffix == '.json':
        ruleset = p_ruleset.Ruleset.from_dict(p_utils.read_json(fpath))
        base_ruleset.extend(ruleset)
      else:
        raise ValueError(f'Unsupported overriding ruleset file type: {fpath}')
    logger.debug(
      f'Loaded base ruleset from overriding rulesets ({len(overriding_rulesets)} file(s)).')
  else:
    starting_ruleset_str = p_utils.read_text(p_consts.STARTING_RULESET_FPATH)
    base_ruleset = p_ruleset.Ruleset.from_starting_ruleset(starting_ruleset_str)
    logger.debug(f'Loaded base ruleset from default path: {p_consts.STARTING_RULESET_FPATH}')

  _CACHE_base_ruleset = base_ruleset
  _CACHE_base_ruleset_key = cache_key
  return _CACHE_base_ruleset


def _check_for_base_rules(
  matcher_group: List[p_ruleset.TRuleBase],
  matched_range_cursor: tuple,
  ruleset: p_ruleset.Ruleset,
  dgann: dict,
  src_main_code: str
) -> bool:
  '''
  When validating matching rules, check if the matched rules are base rules.
  The logic is this: if a rule that matched a range cursor is a rule
  from starting ruleset, then we don't need to run test based validation
  to verify that rule; we just mark that the range cursor can be
  handled by that rule.
  RETURN True if the matched rules are base rules.
  '''
  logger.debug(f'~~~ Checking if rule(s) in the matcher group are base rules')

  base_ruleset = _get_base_ruleset()

  '''
  All rules from matcher_group must be present in base_ruleset
  to be considered base rules.
  '''
  flag_all_rules_in_starting_ruleset = True
  for trule in matcher_group:
    if trule not in base_ruleset.rules:
      flag_all_rules_in_starting_ruleset = False
      break

  if not flag_all_rules_in_starting_ruleset:
    logger.debug('Not all rules in the matcher group are present in the starting ruleset.')
    return False

  '''
  TODO instead of marking all rules as verified, consider checking them one by one.
  '''
  for trule in matcher_group:
    range_cursor_encoded = d_ast_parse.range_cursor_encode(
      matched_range_cursor, dgann, src_main_code)
    ruleset.update_verified_rules(range_cursor_encoded, trule)

  return True


async def _process_match_obj(
  match_obj: dict,
  matcher_group: List[p_ruleset.TRuleBase],
  ruleset: p_ruleset.Ruleset,
  src_main_code: str,
  pre_context: str,
  src_test_code: Optional[str],
  translation_rules_test_code: str,
  dgast: list,
  dgann: dict,
  subject_name: str,
  **kwargs
) -> None:
  '''
  Process the match object and log the information.
  A match object contains a reference to an AST node that matched some rule.

  PARAM match_obj: {
    'matcher': matcher,  # matcher signature
    'range_cursor': range_cursor,  # range cursor that matches the matcher
    'is_matched': is_matched,  # whether the matcher matches the range cursor
    'slot_cursors': slot_cursors  # list of slot cursors that match the range cursor
  }
  PARAM src_main_code: pre_context + simple_ntext
  '''

  logger.debug('~~~ Starting match object processing')

  assert match_obj['is_matched'], 'Expected match_obj to be matched'
  matched_range_cursor = match_obj['range_cursor']

  try:
    matched_ast = d_ast_parse.range_cursor_to_ast_node(matched_range_cursor)
  except Exception:
    matched_ast = None
  if matched_ast and _is_myexactlog_expr_stmt(matched_ast):
    matcher_group = _filter_myexactlog_to_log_stat_rule(matcher_group)
    if not matcher_group:
      logger.warning('Log statement rule not found for myexactlog; skipping match.')
      return

  matcher_group = _filter_none_comparison_rules(
    matcher_group,
    matched_ast,
    match_obj['matcher'],
    matched_range_cursor
  )
  if not matcher_group:
    raise NoRuleToHandleRangeCursorError()

  '''
  Check if the rule(s) in the matcher_group are base rules.
  If so, we do not need to validate them, since they are already verified.
  '''
  flag_check_base_rule = _check_for_base_rules(
    matcher_group,
    matched_range_cursor,
    ruleset,
    dgann,
    src_main_code
  )
  if flag_check_base_rule:
    logger.debug('~~~~~ Validation is complete. Matcher group is a list of one base rule.')
    return

  '''
  Prepare test script and subject for expression.
  '''
  is_three_split = src_test_code is not None

  if Config.translation_order == p_consts.TranslationOrder.EOT:
    logger.debug('Creating test script for EOT translation order')
    test_script_str, test_log_stat_idx = _create_test_script_str_for_expr(
      is_three_split,
      matched_range_cursor,
      matcher_group,
      src_test_code,
      src_main_code,
      pre_context,
      dgann,
      ruleset,
    )
  else:
    raise ValueError(f'Unsupported translation order: {Config.translation_order}')

  expr_subject = _create_subject_for_expr(
    test_script_str,
    is_three_split,
    translation_rules_test_code,
    ruleset,
    subject_name
  )

  '''
  Need to find matched_range_cursor in test_script_str
  '''
  test_scr_ast, test_scr_ann = d_ast_parse.parse_text_dbg(test_script_str, 'py')

  expr_str = d_ast_parse.range_cursor_pretty_print(matched_range_cursor, dgann, src_main_code)
  test_scr_matched_rc = _find_logged_expr_in_test_script_str(
    test_script_str,
    test_scr_ast,
    test_scr_ann,
    expr_str,
    log_stat_idx=test_log_stat_idx
  )

  test_scr_matched_rc_chid = d_ast_parse.range_cursor_to_choice_identifier(test_scr_matched_rc)
  test_scr_matched_rc_enc = d_ast_parse.range_cursor_encode(test_scr_matched_rc, test_scr_ann, test_script_str)
  test_scr_matched_rc_pp = d_ast_parse.range_cursor_pretty_print(test_scr_matched_rc, test_scr_ann, test_script_str)
  matched_subtree_choice_ids = {
    d_ast_parse.range_cursor_to_choice_identifier(rc)
    for rc in d_ast_parse.get_all_range_cursors_under(test_scr_matched_rc)
  }

  def _raise_verified_rules_exhausted_with_context(
    missing_choice_identifier: Tuple[int, int, int]
  ) -> None:
    '''
    Raise VerifiedRulesExhaustedError enriched with snippet/rule context.
    Error cause/fix rationale:
    - Cause: during expression validation, a child node (e.g., py.slice)
      can be the real missing-rule source.
    - Fix strategy: surface that exact child as VerifiedRulesExhaustedError
      so the learner targets the missing dependency first, instead of
      misclassifying the parent matcher-group as implausible.
    NOTE:
    We must use test-script AST/annotation/code here, because verified-rule
    keys for expression validation are encoded from test_script_str.
    '''
    no_choices_rc = d_ast_parse.choice_identifier_to_range_cursor(
      missing_choice_identifier, test_scr_ast)
    no_choices_rc_encoded = d_ast_parse.range_cursor_encode(
      no_choices_rc, test_scr_ann, test_script_str)
    if ruleset.verified_rules_exist(no_choices_rc_encoded):
      ruleset.remove_verified_rules_for(no_choices_rc_encoded)
    else:
      logger.debug(
        f'No verified rules recorded for {no_choices_rc_encoded}; '
        f'skipping removal.')

    no_choices_snippet = d_ast_parse.range_cursor_pretty_print(
      no_choices_rc, test_scr_ann, test_script_str)
    not_matching_rules : List[p_ruleset.TRuleBase] = []
    for ruleset_matcher_group in ruleset.matcher_groups.values():
      matcher = ruleset_matcher_group[0].rule_parsed['match']
      match_obj = _match_rule_to_range_cursor(matcher, no_choices_rc)
      if match_obj['is_matched']:
        continue
      not_matching_rules.extend(ruleset_matcher_group)
    not_matching_rules_str = '\n\n'.join([r.to_rule_str() for r in not_matching_rules])

    err = VerifiedRulesExhaustedError(missing_choice_identifier)
    err.no_choices_snippet = no_choices_snippet
    err.not_matching_rules_str = not_matching_rules_str
    raise err

  flag_vrf_rule_found = False
  for rule_idx, rule_ut in enumerate(matcher_group):
    logger.debug(f'~~~~~ Rule {rule_idx + 1}/{len(matcher_group)} in matcher group:\n{rule_ut}')
    _reset_expr_subject(expr_subject, test_scr_matched_rc_chid, rule_idx)

    '''
    If this translation succeeds, it means that the rule is plausible
    with respect to the matched AST.
    '''
    try:
      if Config.translation_order == p_consts.TranslationOrder.EOT:
        logger.debug('Applying translation rules for EOT translation order')
        tar_program_plausible, translate_dbg_history = \
          await prapp.apply_translation_rules(expr_subject, raise_on_missing_vrf_rule=True)
      else:
        raise ValueError(f'Unsupported translation order: {Config.translation_order}')
      ruleset.update_verified_rules(test_scr_matched_rc_enc, rule_ut)
      flag_vrf_rule_found = True
      logger.debug(
        f'~~~~~ Rule {rule_idx + 1}/{len(matcher_group)} is plausible with respect to the matched AST:\n{rule_ut}\n'
        f'Matched AST: "{test_scr_matched_rc_pp}"')

    except VerifiedRulesExhaustedError as err:
      logger.warning(
        f'While verifying translation rules for a matched AST, stumbled upon '
        f'an AST node that cannot be plausibly translated with any of the '
        f'verified rules.')

      # the node itself is missing a rule
      if err.choice_identifier == test_scr_matched_rc_chid:
        continue

      _raise_verified_rules_exhausted_with_context(err.choice_identifier)

    except prapp.SrcTestScriptProblematicNodeError as err:
      # Root cause:
      # a child/sub-expression with missing translation rule can make the
      # parent rule look "implausible" even though the parent rule may be fine.
      # Symptom in logs:
      # - AllRulesInMatcherGroupImplausibleError for parent node
      # - eventually "stat_node_main_learn_validate_trules: hit max iterations"
      # Fix:
      # when the problematic node is under the currently matched subtree,
      # surface it as VerifiedRulesExhaustedError so the learner targets
      # the actual missing child node first.
      problematic_nid = err.problematic_node_id
      if problematic_nid is not None:
        try:
          problematic_rc = d_ast_parse.get_range_cursor(test_scr_ast, problematic_nid)
          problematic_chid = d_ast_parse.range_cursor_to_choice_identifier(problematic_rc)
          if (
            problematic_chid != test_scr_matched_rc_chid and
            problematic_chid in matched_subtree_choice_ids
          ):
            logger.debug(
              'Detected unresolved dependency inside matched AST; '
              f'promoting problematic node as missing verified rule: {problematic_chid}')
            _raise_verified_rules_exhausted_with_context(problematic_chid)
        except ValueError:
          logger.debug(
            f'Problematic node id {problematic_nid} not found in expression '
            f'test script AST; treating rule as implausible.')
      logger.warning(
        f'~~~~~ Error while applying translation rules:\n{p_utils.exception_to_str(err)}\n'
        f'Rule {rule_idx + 1}/{len(matcher_group)} is not plausible with respect to the matched AST:\n{rule_ut}\n'
        f'Matched AST: "{test_scr_matched_rc_pp}"')
      continue

    except Exception as err:
      logger.warning(
        f'~~~~~ Error while applying translation rules:\n{p_utils.exception_to_str(err)}\n'
        f'Rule {rule_idx + 1}/{len(matcher_group)} is not plausible with respect to the matched AST:\n{rule_ut}\n'
        f'Matched AST: "{test_scr_matched_rc_pp}"')
      continue

  if not flag_vrf_rule_found:
    not_matching_rules : List[p_ruleset.TRuleBase] = []
    for matcher_group in ruleset.matcher_groups.values():
      matcher = matcher_group[0].rule_parsed['match']
      match_obj = _match_rule_to_range_cursor(matcher, test_scr_matched_rc)
      if match_obj['is_matched']:
        continue
      not_matching_rules.extend(matcher_group)
    not_matching_rules_str = '\n\n'.join([r.to_rule_str() for r in not_matching_rules])
    err_obj = AllRulesInMatcherGroupImplausibleError(
      not_matching_rules_str, test_scr_matched_rc_pp)
    raise err_obj


async def _process_choicable_range_cursor(
  matcher_group: List[p_ruleset.TRuleBase],
  all_range_cursors: List[Tuple[list, int, int]],
  ruleset: p_ruleset.Ruleset,
  src_main_code: str,
  pre_context: str,
  src_test_code: Optional[str],
  translation_rules_test_code: str,
  dgast: list,
  dgann: dict,
  processed_match_objs: Dict[str, list],
  subject_name: str,
  **kwargs
):
  '''
  PARAM matcher_group: a list of rules that have the same matcher signature.

  NOTE a range cursor is a different representation of an AST node.
  Duoglot-style AST allows us to identify ASTs using their node ids
  and range cursors. We can get an AST from a range cursor, but
  we cannot get a range cursor from an AST node, because range cursors
  need a reference to the parent AST node.
  '''
  assert_matchers_match(matcher_group)
  matcher = matcher_group[0].rule_parsed['match']
  matcher_signature = matcher_group[0].get_matcher_signature()

  '''
  Keep only those range cursors that have not been processed yet.
  '''
  all_range_cursors = [
    rc for rc in all_range_cursors
    if d_ast_parse.range_cursor_to_choice_identifier(rc) not in processed_match_objs.get(matcher_signature, [])
  ]
  match_objs = [_match_rule_to_range_cursor(matcher, range_cursor) for range_cursor in all_range_cursors]
  match_objs = [match_obj for match_obj in match_objs if match_obj['is_matched']]

  if len(match_objs) == 0:
    return

  logger.debug(f'~~ Matcher: {matcher}')
  logger.debug(f'~~ Number of range cursors that match the matcher: {len(match_objs)}')
  flag_unhandled_exists = False

  '''
  Process each matched AST that matched the rule (matcher).
  '''
  for idx, match_obj in enumerate(match_objs, start=1):

    range_cursor = match_obj['range_cursor']
    logger.debug(
      f'~~ Processing match_obj {idx}/{len(match_objs)}:\n'
      f'-> matcher signature: {matcher_signature}\n'
      f'-> matched AST: "{d_ast_parse.range_cursor_pretty_print(range_cursor, dgann, src_main_code)}"')

    # Process the match object
    try:
      await _process_match_obj(
        match_obj,
        matcher_group,
        ruleset,
        src_main_code,
        pre_context,
        src_test_code,
        translation_rules_test_code,
        dgast,
        dgann,
        subject_name,
        **kwargs
      )
      logger.debug('~~ Successfully processed the match_obj.')
      processed_match_objs.setdefault(matcher_signature, []).append(
        d_ast_parse.range_cursor_to_choice_identifier(range_cursor))

    except NoRuleToHandleRangeCursorError:
      logger.debug('~~ Not enough rules to handle the slot cursor. Continuing with the next match_obj.')
      flag_unhandled_exists = True
      continue

    except ExprLogStatHasParseError:
      logger.debug(
        '~~ Logged expression has parse error. Unlinking the range cursor '
        'from matcher group (rules that match this range cursor):\n'
        f'{d_ast_parse.range_cursor_pretty_print(range_cursor, dgann, src_main_code)}')
      processed_match_objs.setdefault(matcher_signature, []).append(
        d_ast_parse.range_cursor_to_choice_identifier(range_cursor))

    except ExprLogStatContextError:
      logger.debug(
        '~~ Logged expression cannot be used as an argument to a log statement '
        '(context issue).\nUnlinking the range cursor '
        'from matcher group (rules that match this range cursor):\n'
        f'{d_ast_parse.range_cursor_pretty_print(range_cursor, dgann, src_main_code)}')
      processed_match_objs.setdefault(matcher_signature, []).append(
        d_ast_parse.range_cursor_to_choice_identifier(range_cursor))

  if flag_unhandled_exists:
    raise UnhandledRangeCursorExistsError


def _is_excluded_range_cursor(
  root_range_cursor: tuple,
  range_cursor: tuple,
  dgann: dict,
  src_main_code: str
) -> bool:
  '''
  Check if the given range cursor is excluded from consideration.
  PRE: range_cursor[1] + 1 == range_cursor[2]  # range_cursor specifies exactly one AST node
  '''
  def __pattern_1_recursive_call_to_f_gold(ast: list) -> bool:
    '''
    PARAM ast: duoglot-style AST
    '''
    # must be non-terminal
    if not isinstance(ast, list):
      return False
    ntype = ast[0]
    nid = ast[1]
    assert isinstance(nid, int), 'sanity check'
    if ntype != 'py.call':
      return False
    children = ast[2:]
    ch1 = children[0]
    ch1_type = ch1[0]
    if ch1_type != 'py.identifier':
      return False
    assert len(ch1) == 3, 'sanity check'
    ch_literal = ch1[2]
    if ch_literal == '"f_gold"':
      return True
    return False

  def __pattern_2_descendant_of_string(root_ast: list, ast: list, ann: dict) -> bool:
    '''
    Any nodes under string: string_content, interpolation, etc. since
    we learn overfitted rules for f-strings (and alike).
    PARAM ast: duoglot-style AST
    '''
    root_ast_ntype = root_ast[0]
    if root_ast_ntype != 'py.string':
      return False
    root_ast_nid = root_ast[1]
    rsidx, reidx, _, _ = ann[root_ast_nid]
    ast_nid = ast[1]
    asidx, aeidx, _, _ = ann[ast_nid]
    assert rsidx <= asidx, 'start idx of root_ast <= start idx of ast'
    assert reidx >= aeidx, 'end idx of root_ast >= end idx of ast'
    if asidx == rsidx and aeidx == reidx:
      return False
    return True

  def __pattern_3_direct_child_of_list_comprehension(root_ast: list, ast: list, ann: dict) -> bool:
    '''
    Any node that is a direct child of list comprehension. For example:
    [x*f_gold(x) for x in range(n)]
     ^^^^^^^^^^^
    '''
    ast_ntype = ast[0]
    if ast_ntype == 'py.list_comprehension':
      return False  # include itself
    nt_children = [ch for ch in root_ast[2:] if d_ast_parse.is_elem_non_terminal(ch)]
    nt_children_nids = [ch[1] for ch in nt_children]
    ast_nid = ast[1]
    if ast_nid in nt_children_nids:
      return True  # direct child of list comprehension
    return False

  ast = d_ast_parse.range_cursor_to_ast_node(range_cursor)
  if __pattern_1_recursive_call_to_f_gold(ast):
    range_cursor_pretty = d_ast_parse.range_cursor_pretty_print(range_cursor, dgann, src_main_code)
    logger.debug(
      f'Excluding range cursor (recursive call to `f_gold`): '
      f'"{_log_preview(range_cursor_pretty)}"')
    return True

  root_ast = d_ast_parse.range_cursor_to_ast_node(root_range_cursor)
  if __pattern_2_descendant_of_string(root_ast, ast, dgann):
    range_cursor_pretty = d_ast_parse.range_cursor_pretty_print(range_cursor, dgann, src_main_code)
    logger.debug(
      f'Excluding range cursor (descendant of string): '
      f'"{_log_preview(range_cursor_pretty)}"')
    return True

  if __pattern_3_direct_child_of_list_comprehension(root_ast, ast, dgann):
    range_cursor_pretty = d_ast_parse.range_cursor_pretty_print(range_cursor, dgann, src_main_code)
    logger.debug(
      f'Excluding range cursor (direct child of list comprehension): '
      f'"{_log_preview(range_cursor_pretty)}"')
    return True

  return False


def _get_matcher_anchor_ntype(matcher: list) -> Optional[str]:
  '''
  Best-effort extraction of the first concrete non-terminal node type
  from a matcher fragment. Returns None when the matcher is generic.
  '''
  if not isinstance(matcher, list) or len(matcher) == 0:
    return None
  if matcher[0] != 'fragment':
    return None
  for elem in matcher[1:]:
    if not isinstance(elem, list) or len(elem) == 0:
      continue
    op = elem[0]
    if not isinstance(op, str):
      continue
    if not op.startswith('"'):
      # val/str/nostr/anno operators are not a concrete node-type anchor
      continue
    ntype = _strip_quotes(op)
    if ntype in ['fragment', 'anno']:
      continue
    return ntype
  return None


def _get_range_cursor_ntype(range_cursor: tuple) -> Optional[str]:
  ast = d_ast_parse.range_cursor_to_ast_node(range_cursor)
  if d_ast_parse.is_elem_non_terminal(ast):
    return ast[0]
  return None


def _filter_range_cursors(
  range_cursors: list,
  dgann: dict,
  src_main_code: str,
  ruleset: p_ruleset.Ruleset
) -> list:
  '''
  Exclude some nodes from consideration.
  All rules that match the removed range cursors must be
  added to unverifiable rules.
  '''
  result = []
  root_range_cursor = range_cursors[0]
  # Build matcher index once: concrete anchor ntype -> matcher groups.
  # Generic matchers (no concrete anchor) stay in a fallback bucket.
  matcher_groups_by_anchor: Dict[str, List[Tuple[str, List[p_ruleset.TRuleBase], list]]] = {}
  matcher_groups_generic: List[Tuple[str, List[p_ruleset.TRuleBase], list]] = []
  all_matcher_groups: List[Tuple[str, List[p_ruleset.TRuleBase], list]] = []
  for matcher_sig, matcher_group in ruleset.matcher_groups.items():
    assert_matchers_match(matcher_group)
    matcher = matcher_group[0].rule_parsed['match']
    info = (matcher_sig, matcher_group, matcher)
    all_matcher_groups.append(info)
    anchor_ntype = _get_matcher_anchor_ntype(matcher)
    if anchor_ntype is None:
      matcher_groups_generic.append(info)
    else:
      matcher_groups_by_anchor.setdefault(anchor_ntype, []).append(info)

  for range_cursor in range_cursors:
    if not _is_excluded_range_cursor(root_range_cursor, range_cursor, dgann, src_main_code):
      result.append(range_cursor)
      continue
    range_cursor_unparsed = d_ast_parse.range_cursor_pretty_print(range_cursor, dgann, src_main_code)
    range_cursor_unparsed_preview = _log_preview(range_cursor_unparsed)
    range_cursor_encoded = d_ast_parse.range_cursor_encode(range_cursor, dgann, src_main_code)

    # if we reach here, it means the range cursor is excluded
    range_cursor_ntype = _get_range_cursor_ntype(range_cursor)
    if range_cursor_ntype is None:
      candidate_matcher_groups = all_matcher_groups
    else:
      candidate_matcher_groups = matcher_groups_generic + \
        matcher_groups_by_anchor.get(range_cursor_ntype, [])

    # matcher_group is a list of rules that share the same matcher
    for _matcher_sig, matcher_group, matcher in candidate_matcher_groups:
      match_obj = _match_rule_to_range_cursor(matcher, range_cursor)
      if not match_obj['is_matched']:
        continue
      # if we reach here, it means that matcher_group contains rules
      # that match the range_cursor
      logger.debug(
        f'Updating unverifiable rules for range cursor: '
        f'{range_cursor_unparsed_preview}')
      for rule in matcher_group:
        ruleset.update_unverifiable_rules(
          range_cursor_encoded,
          rule
        )

  return result


async def _get_validated_stat_nid_in_instr_code(
  src_main_code: str,
  simple_ntext: str,
  all_stat_nids: List[int],
) -> int:
  '''
  PARAM src_main_code: instrumented source code prepared for rule applicator.
  RETURN the node id of the statement rules of which are
  to be validated.
  '''

  # uncomment for debugging when needed
  # ast, ann = d_ast_parse.parse_text_dbg(src_main_code, 'py')
  # p_utils.write_text(p_consts.SRC_DIR / 'asrc_main_code.py', src_main_code)
  # p_utils.write_text(p_consts.SRC_DIR / 'asimple_ntext.py', simple_ntext)
  # p_utils.write_json(p_consts.SRC_DIR / 'aall_stat_nids.json', all_stat_nids)
  # p_utils.write_json(p_consts.SRC_DIR / 'aast.json', ast)

  _GFG_STAT_NTYPES = [
    pvpy.ImportFromStatementNode,
    pvpy.ImportStatementNode,
    pvpy.BreakStatementNode,
    pvpy.ContinueStatementNode,
    pvpy.ReturnStatementNode,
    pvpy.ExpressionStatementNode,
    pvpy.IfStatementNode,
    pvpy.WhileStatementNode,
    pvpy.ForStatementNode,
    pvpy.TryStatementNode,
    pvpy.PassStatementNode,  # never used in f_gold, but added by instrumentation
  ]

  _SKEL_STAT_NTYPES = _GFG_STAT_NTYPES +[
    pvpy.WithStatementNode,
    pvpy.DeleteStatementNode,
    pvpy.AssertStatementNode,
    pvpy.NonlocalStatementNode,
    pvpy.GlobalStatementNode,
    pvpy.RaiseStatementNode,
  ]

  tree = pvpy.Tree.from_str(src_main_code)
  root_node = tree.root_node
  nid_node_map = root_node.get_nid_node_map()

  simple_ntree = pvpy.Tree.from_str(simple_ntext)
  assert len(simple_ntree.root_node.get_nt_children()) == 1, 'Expected exactly one statement node'
  simple_node = simple_ntree.root_node.get_nt_children()[0]

  '''
  Need to ignore all statements that were added as
  part of instrumentation: break statements, log statements,
  pass statements.
  TODO with break statements, it's a bit tricky; for now, just return
  the latest break statement node id even if it's inserted by instrumentation,
  because it has "no" effect on p_ext_rule_chooser.stat_node_validate_exprs().
  '''
  pp = pvpy.PrettyPrinter(indent_with='    ')
  for stat_nid in reversed(all_stat_nids):
    stat_node = nid_node_map[stat_nid]
    assert isinstance(stat_node, tuple(_SKEL_STAT_NTYPES)), \
      f'unexpected type: {stat_node.__class__.__name__}'

    # skip if statement types do not match
    if type(stat_node) != type(simple_node):
      continue

    # skip myexactlog(...) statements
    if isinstance(stat_node, pvpy.ExpressionStatementNode):
      assert len(stat_node.get_nt_children()) == 1, 'sanity check'
      child = stat_node.get_nt_children()[0]
      if isinstance(child, pvpy.CallNode):
        unparsed_child : str = pp.visit(child)
        if unparsed_child.lstrip().startswith('myexactlog('):
          continue
        if unparsed_child.lstrip().startswith('os._exit('):
          continue

    return stat_nid

  raise ValueError('No statement node found that matches the simple_ntext statement node.')


async def _get_stat_nids_in_pre_context(
  src_main_code: str,
  simple_ntext: str,
  is_three_split: bool,
  subject_name: str,
  eot_probe_src_main_code: Optional[str] = None,
  eot_probe_stat_nid: Optional[int] = None,
) -> Tuple[List[int], List[int]]:
  '''
  RETURN (statement node ids in pre_context, all statement node ids).
  all statement node ids are also needed by overfitted-exclusion logic:
  if an overfitted rule matches a compound statement (e.g., for/if/while),
  we keep only the parent excluded and allow descendant statements to
  remain choosable.
  '''
  origin_pre_context_count: Optional[int] = None

  if is_three_split:
    all_stat_nids = await p_pirel._get_statement_nodes(
      src_main_code, 'py', is_three_split, subject_name, return_node_ids=True)
    assert all_stat_nids == sorted(all_stat_nids)
  else:
    if (
      isinstance(eot_probe_src_main_code, str)
      and eot_probe_src_main_code.strip() != ''
      and isinstance(eot_probe_stat_nid, int)
    ):
      try:
        # Requested pipeline order:
        # 1) resolve execution-order position on original source code first
        # 2) then work on blacklist/pruned validation snippet
        origin_exec_stat_nids = await p_pirel.get_statement_nodes_eot(
          eot_probe_src_main_code, 'py', subject_name, return_node_ids=True)
        if eot_probe_stat_nid in origin_exec_stat_nids:
          origin_pre_context_count = origin_exec_stat_nids.index(eot_probe_stat_nid)
        else:
          logger.debug(
            'EOT probe stat_nid not found in origin execution order; '
            f'stat_nid={eot_probe_stat_nid}, len(origin_exec)={len(origin_exec_stat_nids)}'
          )
      except Exception as err:
        # Do not fail readonly initialization on probe-only path.
        logger.warning(
          f'Failed EOT probe on original source for pre-context boundary; '
          f'falling back to static snippet order: {type(err).__name__}: {err}')
    all_stat_nids = await p_pirel.get_statement_nodes_eot(
      src_main_code, 'py', subject_name, return_node_ids=True)

  val_stat_nid = await _get_validated_stat_nid_in_instr_code(
    src_main_code, simple_ntext, all_stat_nids)

  simple_ntext_idx = all_stat_nids.index(val_stat_nid)
  stat_nids_pre_context = all_stat_nids[:simple_ntext_idx]
  if (
    not is_three_split
    and origin_pre_context_count is not None
    and origin_pre_context_count != len(stat_nids_pre_context)
  ):
    logger.debug(
      'Pre-context boundary mismatch between origin-EOT count and '
      'snippet-static count '
      f'(origin={origin_pre_context_count}, snippet={len(stat_nids_pre_context)}).'
    )
  return stat_nids_pre_context, all_stat_nids


def _get_src_fn_ancestor_name_by_nid(
  src_main_code: str,
  rc_src_main_code: tuple,
) -> Dict[int, Optional[str]]:
  '''
  Build and cache nid -> first enclosing function name map for src_main_code.
  '''
  cached = _CACHE_SRC_FN_ANCESTOR_NAME_BY_NID.get(src_main_code)
  if cached is not None:
    return cached

  nid_to_fn_ancestor: Dict[int, Optional[str]] = {}

  def _walk(node: list, current_fn_name: Optional[str]) -> None:
    if not d_ast_parse.is_elem_non_terminal(node):
      return

    next_fn_name = current_fn_name
    if node[0] == 'py.function_definition':
      try:
        fn_name_node = node[3]
        assert d_ast_parse.is_elem_non_terminal(fn_name_node), \
          'expected non-terminal node for function name'
        assert fn_name_node[0] == 'py.identifier', \
          'expected identifier node for function name'
        fn_name = fn_name_node[2]
        assert isinstance(fn_name, str), 'expected string literal for function name'
        next_fn_name = json.loads(fn_name)
      except Exception as err:
        logger.warning(f'Failed to resolve function name in GT exclusion precompute: {err}')
        next_fn_name = current_fn_name

    node_id = node[1]
    if isinstance(node_id, int):
      nid_to_fn_ancestor[node_id] = next_fn_name

    for child in node[2:]:
      if d_ast_parse.is_elem_non_terminal(child):
        _walk(child, next_fn_name)

  _walk(rc_src_main_code[0], None)
  _CACHE_SRC_FN_ANCESTOR_NAME_BY_NID[src_main_code] = nid_to_fn_ancestor
  return nid_to_fn_ancestor


async def _get_exluded_stat_nids(
  src_main_code: str,
  simple_ntext: str,
  ruleset: p_ruleset.Ruleset,
  is_three_split: bool,
  subject_name: str,
  eot_probe_src_main_code: Optional[str] = None,
  eot_probe_stat_nid: Optional[int] = None,
) -> List[int]:
  '''
  RETURN a list of statement node ids that should be excluded
  from consideration when generating choices for translation.
  These are statement nodes that appear in pre_context
  and statement nodes that match overfitted rules.
  '''
  excluded_stat_nids = set()

  '''
  Nodes in pre context are excluded since they are already processed.
  '''
  if Config.translation_order == p_consts.TranslationOrder.EOT:
    logger.debug('Getting statement node ids in pre-context for EOT translation order.')
    stat_nids_pre_context, all_stat_nids = await _get_stat_nids_in_pre_context(
      src_main_code,
      simple_ntext,
      is_three_split,
      subject_name,
      eot_probe_src_main_code=eot_probe_src_main_code,
      eot_probe_stat_nid=eot_probe_stat_nid,
    )
  else:
    raise ValueError(f'Unsupported translation order: {Config.translation_order}')
  excluded_stat_nids.update(stat_nids_pre_context)

  '''
  Nodes that match overfitted rules are excluded.
  '''
  rc_src_main_code, dgann = d_ast_parse.parse_text_to_range_cursor(src_main_code, 'py')
  if is_three_split:
    assert rc_src_main_code[1] + 1 == rc_src_main_code[2], \
      'range cursor must specify just one node (function f_gold)'
    all_range_cursors = d_ast_parse.get_all_range_cursors_under(
      rc_src_main_code)
  else:
    all_range_cursors = d_ast_parse.range_cursor_seq_descending_from_ast(
      rc_src_main_code[0])

  range_cursors_by_ntype: Dict[str, List[tuple]] = {}
  for range_cursor in all_range_cursors:
    ntype = _get_range_cursor_ntype(range_cursor)
    if ntype is not None:
      range_cursors_by_ntype.setdefault(ntype, []).append(range_cursor)

  overfitted_stat_nids = set()
  overfitted_rules = ruleset.get_stat_overfitted_rules()
  for rule in overfitted_rules:
    matcher = rule.rule_parsed['match']
    matcher_anchor_ntype = _get_matcher_anchor_ntype(matcher)
    if matcher_anchor_ntype is None:
      candidate_range_cursors = all_range_cursors
    else:
      candidate_range_cursors = range_cursors_by_ntype.get(matcher_anchor_ntype, [])
    rule_preview = _log_preview(rule.to_rule_str())
    for range_cursor in candidate_range_cursors:
      match_obj = _match_rule_to_range_cursor(matcher, range_cursor)
      if not match_obj['is_matched']:
        continue
      matched_ast = d_ast_parse.range_cursor_to_ast_node(range_cursor)
      assert d_ast_parse.is_elem_non_terminal(matched_ast), 'sanity check'
      stat_nid = matched_ast[1]
      assert isinstance(stat_nid, int), 'sanity check'
      range_cursor_pretty = d_ast_parse.range_cursor_pretty_print(range_cursor, dgann, src_main_code)
      logger.debug(
        f'Will exclude statement node id {stat_nid}:\n'
        f'"{_log_preview(range_cursor_pretty)}"\n'
        f'since it matches overfitted rule:\n{rule_preview}')
      overfitted_stat_nids.add(stat_nid)

  excluded_stat_nids.update(overfitted_stat_nids)

  '''
  Nodes that are inside bodies of functions that have ground truth translations
  are excluded. We check the first function_definition ancestor for all nodes,
  and exclude nodes that match the function name.
  TODO this is not accurate, since this function must return only statement node ids,
  but we currently exclude all nodes under the matched function, including non-statement nodes.
  '''
  if subject_name is not None and isinstance(subject_name, str):
    gt_fn_names = _get_subject_gt_fn_names(subject_name)
    if len(gt_fn_names) == 0:
      logger.debug('Skipping GT exclusion loop: no ground_truth_translations in subject config.')
    else:
      nid_to_fn_ancestor = _get_src_fn_ancestor_name_by_nid(src_main_code, rc_src_main_code)
      for range_cursor in all_range_cursors:
        matched_ast = d_ast_parse.range_cursor_to_ast_node(range_cursor)
        assert d_ast_parse.is_elem_non_terminal(matched_ast), 'sanity check'
        stat_nid = matched_ast[1]
        assert isinstance(stat_nid, int), 'sanity check'
        fn_def_anc_name = nid_to_fn_ancestor.get(stat_nid)
        if fn_def_anc_name not in gt_fn_names:
          continue
        range_cursor_pretty = d_ast_parse.range_cursor_pretty_print(range_cursor, dgann, src_main_code)
        # logger.debug(
        #   f'Will exclude statement node id {stat_nid}:\n'
        #   f'"{_log_preview(range_cursor_pretty)}"\n'
        #   f'since it is inside function "{fn_def_anc_name}" that has a ground truth translation.')
        excluded_stat_nids.add(stat_nid)

  excluded_stat_nids = sorted(excluded_stat_nids)
  return excluded_stat_nids


async def _stat_node_validate_exprs_init(
  src_main_code: str,
  ruleset: p_ruleset.Ruleset,
  is_three_split: bool,
  simple_ntext: str,
  subject_name: str,
  eot_probe_src_main_code: Optional[str] = None,
  eot_probe_stat_nid: Optional[int] = None,
) -> tuple:
  '''
  Given a duoglot-style AST, collect all nodes under AST,
  for which we should "cleverly" generate choices that
  result in a plausible translation.
  RETURN a list of tuples (range cursor, context statement node id).

  NOTE: pre-context generation is intentionally deferred to
  stat_node_validate_exprs() so we can skip work for nodes that
  are already handled by verified/unverifiable rules.
  '''
  excluded_stat_nids = await _get_exluded_stat_nids(
    src_main_code,
    simple_ntext,
    ruleset,
    is_three_split,
    subject_name,
    eot_probe_src_main_code=eot_probe_src_main_code,
    eot_probe_stat_nid=eot_probe_stat_nid,
  )

  choicable_nodes = pvpy.ChoicableNodeExtractor.extract_choicable_nodes(
    src_main_code, exclude_statement_nodes_ids=excluded_stat_nids)
  logger.debug(f'There are {len(choicable_nodes)} choicable nodes in src_main_code.')
  p_utils.log_file_time('src_main_code.py', src_main_code)

  chable_rc_stat_nids = []  # (choicable range cursor, context statement node id)
  dgast, dgann = d_ast_parse.parse_text_dbg(src_main_code, 'py')

  for i, choicable_node in enumerate(choicable_nodes, start=1):
    choicable_range_cursor = d_ast_parse.get_range_cursor(dgast, choicable_node.get_node_id())
    stat_node = _choicable_node_get_context_node(choicable_node)
    chable_rc_stat_nids.append((choicable_range_cursor, stat_node.get_node_id()))
    logger.debug(
      f'-> Choicable_node {i}/{len(choicable_nodes)}: '
      f'"{d_ast_parse.range_cursor_pretty_print(choicable_range_cursor, dgann, src_main_code)}"')

  return chable_rc_stat_nids, dgast, dgann


async def stat_node_validate_exprs(
  src_main_code: str,
  src_test_code: Optional[str],
  translation_rules_test_code: str,
  ruleset: p_ruleset.Ruleset,
  simple_ntext: str,
  subject_name: str,
  eot_probe_src_main_code: Optional[str] = None,
  eot_probe_stat_nid: Optional[int] = None,
  **kwargs
) -> None:
  '''
  Generate a readonly choices list for the given source code and rules.
  Readonly choices list contains choices to validated rules that result
  in plausible translation. This is much better than blindly iterating
  over all possible rule combinations to get a plausible translation.

  Readonly choices contains choices to right hand side of assignments,
  and conditions of if statements.

  PARAM src_main_code (check p_pirel._create_src_program_for_stat_val()):
  - instrumented with log statements
  - break statements inserted
  PARAM subject_name: to know what subject we are dealing with.

  NOTE This function should not add or remove rules from the ruleset.
  '''

  p_utils.log_json_time('args-stat_node_validate_exprs.json', locals())
  logger.debug('--readonly-main--: Starting generation of read-only choices list')

  if simple_ntext.lstrip().startswith('raise '):
    logger.warning('Skipping stat_node_validate_exprs() for raise statements')
    return
  if simple_ntext.lstrip().startswith('break'):
    logger.warning('Skipping stat_node_validate_exprs() for break statements')
    return
  if simple_ntext.lstrip().startswith('continue'):
    logger.warning('Skipping stat_node_validate_exprs() for continue statements')
    return

  '''
  `choicable_range_cursors` - a list of range cursors
  for which we need to create readonly choices list
  that results in a plausible translation.
  retval_0 = ((15 + (7 * (math.sqrt(5)))) / 4) * (math.pow(side, 3))
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  if h < 0 or m < 0 or h > 12 or m > 60:
     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  '''
  src_main_code = p_code_runner._replace_src_fns_with_pass_with_gt_translations(src_main_code, subject_name)
  is_three_split = src_test_code is not None
  chable_rc_stat_nids, dgast, dgann = await _stat_node_validate_exprs_init(
    src_main_code,
    ruleset,
    is_three_split,
    simple_ntext,
    subject_name,
    eot_probe_src_main_code=eot_probe_src_main_code,
    eot_probe_stat_nid=eot_probe_stat_nid,
  )
  pre_context_is_three_split = is_three_split
  pre_context_cache: Dict[int, str] = {}
  pre_context_cache_hits = 0
  pre_context_cache_misses = 0

  for i, (choicable_range_cursor, context_stat_nid) in enumerate(chable_rc_stat_nids, start=1):

    logger.debug(
      f'readonly-main: processing choicable_range_cursor {i}/{len(chable_rc_stat_nids)}: '
      f'"{d_ast_parse.range_cursor_pretty_print(choicable_range_cursor, dgann, src_main_code)}"')

    '''
    Verified or unverifiable rules may already contain rules that can handle
    the choicable_range_cursor. If so, we skip processing it.
    '''
    choicable_range_cursor_encoded = d_ast_parse.range_cursor_encode(
      choicable_range_cursor, dgann, src_main_code)
    if ruleset.verified_rules_exist(choicable_range_cursor_encoded):
      logger.debug('Skipping processing of choicable_range_cursor, since it is already handled by verified rules.')
      continue
    if ruleset.unverifiable_rules_exist(choicable_range_cursor_encoded):
      logger.debug('Skipping processing of choicable_range_cursor, since it is already handled by unverifiable rules.')
      continue

    if context_stat_nid in pre_context_cache:
      pre_context_cache_hits += 1
      pre_context = pre_context_cache[context_stat_nid]
      logger.debug(f'Reusing cached pre-context for context statement node id: {context_stat_nid}')
    else:
      pre_context_cache_misses += 1
      logger.debug(
        f'Computing pre-context for context statement node id: {context_stat_nid} '
        f'(translation_order={Config.translation_order})')
      # For subject without the three-split format,
      # statements yet to be translated (by the order of execution)
      # are already purged from src_main_code,
      # hence the node blacklist is empty here.
      pre_context = p_pirel.get_pre_context(
        src_main_code, 'py', pre_context_is_three_split, context_stat_nid, [])
      pre_context = pvpy.LogStatementRemover.remove_log_statements(pre_context)
      pre_context_cache[context_stat_nid] = pre_context

    '''
    Matcher groups are groups of rules that have the same matcher signature.
    We make a queue of matcher groups to process them one by one.
    '''
    queue_matcher_groups = list(ruleset.matcher_groups.values())

    '''
    Each matcher matches to a number of ASTs, in order to avoid
    processing the same matched AST multiple times, we keep
    track of processed match objects.
    '''
    processed_match_objs : Dict[str, list] = {}

    '''
    paramable_ids: a list of parameterable identifiers under choicable_range_cursor.
    test_fn_str: a test function string that will be used to validate translation rules.
    all_range_cursors: a list of all range cursors under choicable_range_cursor.
    This includes the choicable_range_cursor itself (as the first elem) and all its subtrees.
    '''
    all_range_cursors = d_ast_parse.get_all_range_cursors_under(choicable_range_cursor)
    all_range_cursors = _filter_range_cursors(
      all_range_cursors, dgann, src_main_code, ruleset)
    logger.debug(f'Number of range cursors under choicable_range_cursor: {len(all_range_cursors)}')

    '''
    Attempt to control the infinite loop that may arise from
    unchanging queue size.
    '''
    unchanged_count = 0
    prev_queue_size = len(queue_matcher_groups)
    _MAX_QUEUE_UNCHANGED_COUNT = len(queue_matcher_groups) * 2

    while queue_matcher_groups:
      logger.debug(f'~ Queue size: {len(queue_matcher_groups)}')
      matcher_group = queue_matcher_groups.pop(0)
      try:
        await _process_choicable_range_cursor(
          matcher_group,
          all_range_cursors,
          ruleset,
          src_main_code,
          pre_context,
          src_test_code,
          translation_rules_test_code,
          dgast,
          dgann,
          processed_match_objs,
          subject_name,
          **kwargs
        )
      except UnhandledRangeCursorExistsError as err:
        logger.debug(f'Moving the matcher group to the end of the queue')
        queue_matcher_groups.append(matcher_group)

      # prevent infinite loop
      if len(queue_matcher_groups) == prev_queue_size:
        unchanged_count += 1
      else:
        unchanged_count = 0
      prev_queue_size = len(queue_matcher_groups)
      if unchanged_count >= _MAX_QUEUE_UNCHANGED_COUNT:
        logger.error(f'Infinite loop detected. Stopping processing for matcher group: {matcher_group}')
        raise QueueInfiniteLoopError('Infinite loop detected')

  logger.debug(
    'readonly-main: pre-context cache stats: '
    f'hits={pre_context_cache_hits}, misses={pre_context_cache_misses}, '
    f'unique_context_nodes={len(pre_context_cache)}')
  logger.debug('readonly-main: Finished generation of read-only choices list')
  verified_choice_options = ruleset.get_choice_options_from_verified_rules(src_main_code)
  translation_rules_main_code = \
    p_utils.read_text(p_consts.RULE_VAL_PRIORITY_RULES_FPATH) + '\n\n' + \
    p_utils.read_text(p_consts.LOG_STAT_RULE_FPATH) + '\n\n' + \
    ruleset.to_str_ruleset() + '\n\n' + \
    p_utils.read_text(p_consts.RULE_VAL_EXTRA_RULES_FPATH)
  verified_choice_options = add_forced_log_stat_choice_options(
    verified_choice_options,
    src_main_code,
    translation_rules_main_code
  )
  return verified_choice_options


# GENERATING NEW CHOICES LIST BASED ON ERRORS
def _sanity_check_choices_list(
  choices_list: List[Tuple[Tuple[int, int, int], int]]
) -> None:
  '''
  Perform sanity checks on the choices list.
  POST: choice identifiers are unique and sorted.
  '''
  seen = set()
  prev_range_info = None
  for range_info, choice_idx in choices_list:
    assert range_info not in seen, f'duplicate choice identifier found in choices_list: {range_info}'
    seen.add(range_info)
    if prev_range_info is not None:
      assert range_info > prev_range_info, f'choices list is not sorted: {choices_list}'
    prev_range_info = range_info


def _sanity_check_choice_options(
  choice_options: List[Tuple[Tuple[int, int, int], List[int]]],
  assert_uniq_choice_ids: bool = True,
  assert_sorted: bool = True,
) -> None:
  '''
  Perform sanity checks on the choice options.
  POST: choice identifiers are unique and sorted.
  '''
  seen = set()
  prev_range_info = None
  for range_info, choice_idxs in choice_options:
    if assert_uniq_choice_ids:
      assert range_info not in seen, f'duplicate choice identifier found in choice_options: {range_info}'
    seen.add(range_info)
    if assert_sorted and prev_range_info is not None:
      assert range_info > prev_range_info, f'choice options list is not sorted: {choice_options}'
    prev_range_info = range_info


def merge_choices_list_and_choice_options(
  choices_list: List[Tuple[Tuple[int, int, int], int]],
  choice_options: List[Tuple[Tuple[int, int, int], List[int]]],
  raise_on_conflict: bool = False
) -> List[Tuple[Tuple[int, int, int], int]]:
  '''
  Create a union of two choices lists.
  If a choice exists in both lists and raise_on_conflict is True,
  raise an error if the choice indices are different.
  RETURN the merged choices list.
  PRE: choice identifiers are unique and sorted.
  '''
  result = []
  idx_li = 0
  idx_op = 0
  len_li = len(choices_list)
  len_op = len(choice_options)

  while idx_li < len_li and idx_op < len_op:
    range_info_li, choice_idx_li = choices_list[idx_li]
    range_info_op, choice_idxs_op = choice_options[idx_op]
    assert len(choice_idxs_op) > 0, 'sanity check: choice options must have at least one choice idx'

    if range_info_li < range_info_op:
      result.append((range_info_li, choice_idx_li))
      idx_li += 1
    elif range_info_li > range_info_op:
      result.append((range_info_op, choice_idxs_op[0]))  # take the first choice idx
      idx_op += 1
    else:
      # range_info_a == range_info_b
      if raise_on_conflict and choice_idx_li != choice_idxs_op[0]:
        raise ValueError(
          f'Conflict in choices lists for range_info {range_info_li}: '
          f'choice_idx_li={choice_idx_li}, choice_idx_op={choice_idxs_op[0]}')
      assert choice_idx_li in choice_idxs_op, 'choice_idx_li must be in choice_idxs_op'
      result.append((range_info_li, choice_idx_li))
      idx_li += 1
      idx_op += 1

  # append remaining choices from choices_list_a
  while idx_li < len_li:
    result.append(choices_list[idx_li])
    idx_li += 1

  # append remaining choices from choices_list_b
  while idx_op < len_op:
    range_info_op, choice_idxs_op = choice_options[idx_op]
    assert len(choice_idxs_op) > 0, 'sanity check: choice options must have at least one choice idx'
    result.append((range_info_op, choice_idxs_op[0]))  # take the first choice idx
    idx_op += 1

  return result


def choices_list_sorted(
  choices_list: List[Tuple[Tuple[int, int, int], int]],
  reverse: bool = False
) -> List[Tuple[Tuple[int, int, int], int]]:
  '''
  Sort the choices list by range_info.
  '''
  return sorted(choices_list, key=lambda x: x[0], reverse=reverse)


def rel_alt_step_info_remove_duplicates(
  rel_alt_step_infos: dict
) -> dict:
  '''
  For some unknown reason, DuoGlot translator includes duplicate
  entries in translate_dbg_history structure. Duplicate entries
  have the same range_info. Having duplicates causes
  duplicate choices in the generated choices list.
  '''
  seen = set()
  result = dict()
  for alt_step, entries in rel_alt_step_infos.items():
    current_range_info = entries['current_range_info']
    if current_range_info in seen:
      logger.debug(f'removing duplicate entry for alt_step for range: {current_range_info}')
      continue
    seen.add(current_range_info)
    result[alt_step] = entries
  return result


def _add_verified_choice_options(
  all_choices_list: List[Tuple[Tuple[int, int, int], int]],
  verified_choice_options: List[Tuple[Tuple[int, int, int], List[int]]]
) -> List[Tuple[Tuple[int, int, int], int]]:
  '''
  Add readonly choices to the all_choices_list.
  '''
  _sanity_check_choices_list(all_choices_list)
  _sanity_check_choice_options(verified_choice_options)
  return merge_choices_list_and_choice_options(
    all_choices_list,
    verified_choice_options,
    raise_on_conflict=False  # choice may have been made from verified choices
  )


def _choices_list_history_to_choices_list(
  choices_list_history: List[List[Tuple[Tuple[int, int, int], int]]]
) -> List[Tuple[Tuple[int, int, int], int]]:
  '''
  Convert a history of choices lists to a single choices list.
  The history is a list of lists, where each inner list is a choices list.
  The function returns a single choices list that contains all the choices
  from the history, preserving the order of choices.
  '''
  merged = {}
  for choices_list in choices_list_history:
    for choice in choices_list:
      range_info, choice_idx = choice
      merged[range_info] = choice_idx  # later ones overwrite earlier ones
  merged_choices_list = [(range_info, choice_idx) for range_info, choice_idx in merged.items()]
  return merged_choices_list


def _choices_lists_ab_failed_contains(
  choices_lists_ab_failed: List[List[Tuple[Tuple[int, int, int], int]]],
  choices_list: List[Tuple[Tuple[int, int, int], int]]
) -> bool:
  '''
  Check if the given choices_list is contained in the choices_list_ab_failed.
  This is used to avoid repeating the same failed choices list.
  '''
  for failed_choices_list in choices_lists_ab_failed:
    if set(failed_choices_list) == set(choices_list):
      return True
  return False


def _choices_lists_error_contains(
  choices_lists_error: List[List[Tuple[Tuple[int, int, int], int]]],
  choices_list: List[Tuple[Tuple[int, int, int], int]]
) -> bool:
  '''
  Check if the given choices_list is contained in the choices_lists_error.
  This is used to avoid repeating the same error choices list.
  '''
  for error_choices_list in choices_lists_error:
    if set(error_choices_list) == set(choices_list):
      return True
  return False


def _get_new_choices_list_rec_gen(
  choice_options: List[Tuple[Tuple[int], List[int]]],
  vrf_range_infos: Set[Tuple[int, int, int]],
  raise_on_missing_vrf_rule: bool = False,
):
  '''
  Generator version: yields all possible choices lists, preserving base case and error handling.
  '''
  if not choice_options:
    yield []
    return

  current_range_info, choice_idxs = choice_options[0]
  rest = choice_options[1:]

  # base case: only one node
  if len(choice_options) == 1:
    if len(choice_idxs) == 0:
      if raise_on_missing_vrf_rule and current_range_info in vrf_range_infos:
        raise VerifiedRulesExhaustedError(current_range_info)
      return
    for idx in choice_idxs:
      yield [(current_range_info, idx)]
    return

  # recursive case
  for idx in choice_idxs:
    node_choice = (current_range_info, idx)
    try:
      for tail_choices in _get_new_choices_list_rec_gen(rest, vrf_range_infos, raise_on_missing_vrf_rule):
        yield [node_choice] + tail_choices
    except VerifiedRulesExhaustedError as err:
      # propagate up
      raise


def _get_new_choices_list_rec(
  choice_options: List[Tuple[Tuple[int], List[int]]],
  vrf_range_infos: Set[Tuple[int, int, int]],
  raise_on_missing_vrf_rule: bool = False,
) -> Tuple[Optional[list], bool]:
  '''
  PARAM choice_options: a list of tuples, each tuple contains:
    - current_range_info: choice_identifier of the current node
    - choice_idxs: list of possible choice indices at the current node

  RETURN a tuple of (new_choices_list, is_new_choice_created)
  '''

  '''
  The idea is to choose the next combination at the lower level.
  If there are no more choices at the lower level, choose the next
  combination one level up.
  '''
  current_range_info, choice_idxs = choice_options[0]

  # base case
  if len(choice_options) == 1:
    # no choices left at this node
    if len(choice_idxs) == 1:
      if raise_on_missing_vrf_rule and current_range_info in vrf_range_infos:
        raise VerifiedRulesExhaustedError(current_range_info)
      return [], False
    node_choice = (current_range_info, choice_idxs[1])
    return [node_choice], True

  # recursive call
  choices_down_the_line, is_new_choice_created = _get_new_choices_list_rec(
    choice_options[1:],
    vrf_range_infos,
    raise_on_missing_vrf_rule,
  )

  # if a new choice was created at the lower level,
  # we need to return it as a new choice at the current level
  if is_new_choice_created:
    assert len(choices_down_the_line) > 0, 'Expected choices_down_the_line to be non-empty'
    # repeat the same choice at the current level
    node_choice = (current_range_info, choice_idxs[0])
    return [node_choice] + choices_down_the_line, True

  # no choices left at this node
  if len(choice_idxs) == 1:
    if raise_on_missing_vrf_rule and current_range_info in vrf_range_infos:
      raise VerifiedRulesExhaustedError(current_range_info)
    return choices_down_the_line, False

  # make the next choice at the current node
  node_choice = (current_range_info, choice_idxs[1])
  return [node_choice] + choices_down_the_line, True


def get_next_unique_choices(
  rel_alt_step_infos: Dict[int, dict],
  choices_list_history: list,
  verified_choice_options: List[Tuple[Tuple[int, int, int], List[int]]],
  raise_on_missing_vrf_rule: bool = False,
  src_main_code: Optional[str] = None,
  translation_rules_main_code: Optional[str] = None,
  excluded_choice_options: Optional[List[Tuple[Tuple[int, int, int], List[int]]]] = None,
  choices_lists_ab_failed: list = [],
  choices_lists_error: list = [],
) -> dict:
  '''
  PARAM rel_alt_step_infos: (rasis) contains information about all the possible
  translation rules that can be applied to obtain a different translation
  at the location of an error.
  NOTE Exhaustively checks all possible choices.
  '''

  '''
  `err_line_choices_list` contains current rule choices at lines with error.
  The fact that we are inside this function tells that these choices
  were invalid and must be replaced.
  '''
  err_line_choices_list = [
    (info['current_range_info'], info['current_choose_idx'])
    for info in list(rel_alt_step_infos.values())
  ]
  err_line_choices_list = choices_list_sorted(err_line_choices_list)

  '''
  Create new choices list at the error lines.
  Sorting order of choice_options defines the order of
  node combinations, i.e., trying different rules at parent nodes vs child nodes.
  Sorting choice_options in descending order means that
  we try different rules at child nodes first.
  '''
  src_ast = None
  match_sig_to_new_expr_idxs: Dict[str, Set[int]] = {}
  rule_id_to_match_sig: Dict[int, str] = {}
  log_match_sig = None
  log_rule_idx_in_group = None
  if src_main_code and translation_rules_main_code:
    src_ast = _get_src_ast(src_main_code)
    match_sig_to_new_expr_idxs, rule_id_to_match_sig = _get_new_expr_choice_info(
      translation_rules_main_code)
    log_match_sig, log_rule_idx_in_group = _get_log_stat_choice_info(
      translation_rules_main_code)

  choice_options = []
  for rasis_value in rel_alt_step_infos.values():
    next_choices_count = rasis_value['next_choices_count']
    current_choose_idx = rasis_value['current_choose_idx']
    current_range_info = rasis_value['current_range_info']
    choice_idxs = list(range(current_choose_idx, next_choices_count))
    current_rule_id = rasis_value.get('current_rule_id')
    if (
      src_ast is not None and
      current_rule_id is not None and
      _range_includes_myexactlog(current_range_info, src_ast)
    ):
      match_sig = rule_id_to_match_sig.get(current_rule_id)
      if log_match_sig and match_sig == log_match_sig and log_rule_idx_in_group is not None:
        if log_rule_idx_in_group in choice_idxs:
          choice_idxs = [log_rule_idx_in_group]
        else:
          logger.debug(
            f'Log statement choice idx not available for myexactlog at {current_range_info}.')
      new_expr_idxs = match_sig_to_new_expr_idxs.get(match_sig, set()) if match_sig else set()
      if new_expr_idxs:
        filtered_choice_idxs = [idx for idx in choice_idxs if idx not in new_expr_idxs]
        if filtered_choice_idxs:
          choice_idxs = filtered_choice_idxs
        else:
          logger.debug(
            f'All choices filtered for myexactlog at {current_range_info}; '
            f'keeping original choices.')
    choice_options.append(
      (current_range_info, choice_idxs)
    )
  choice_options.sort(key=lambda elem: elem[0], reverse=True)
  range_info_to_rel = {info['current_range_info']: info for info in rel_alt_step_infos.values()}

  if excluded_choice_options:
    exclude_map: Dict[Tuple[int, int, int], Set[int]] = {}
    for range_info, choice_idxs in excluded_choice_options:
      exclude_map.setdefault(range_info, set()).update(choice_idxs)
    for i in range(len(choice_options)):
      cur_range_info, cur_choice_idxs = choice_options[i]
      if cur_range_info not in exclude_map:
        continue
      filtered_choice_idxs = [idx for idx in cur_choice_idxs if idx not in exclude_map[cur_range_info]]
      if not filtered_choice_idxs:
        logger.warning(
          f'Runtime error blacklist excluded all choices for {cur_range_info}; '
          f'keeping original choices: {cur_choice_idxs}'
        )
        continue
      choice_options[i] = (cur_range_info, filtered_choice_idxs)

  '''
  Overwrite choice_options to only include the verified choices from
  verified_choice_options
  '''
  _sanity_check_choice_options(choice_options, assert_sorted=False)
  _sanity_check_choice_options(verified_choice_options)
  for vrf_choice_option in verified_choice_options:
    vrf_range_info, vrf_choice_idxs = vrf_choice_option
    for i in range(len(choice_options)):
      cur_range_info, cur_choice_idxs = choice_options[i]
      if cur_range_info == vrf_range_info:
        # update choice options to only include the verified choice
        # however, do not add vrf_choice_idxs that were previously in err_line_choices_list
        intn_choice_idxs = list(set(vrf_choice_idxs) & set(cur_choice_idxs))
        choice_options[i] = (cur_range_info, intn_choice_idxs)
        break

  vrf_range_infos = set(vrf_choice_option[0] for vrf_choice_option in verified_choice_options)

  try:
    for cand_choices_list in _get_new_choices_list_rec_gen(choice_options, vrf_range_infos, raise_on_missing_vrf_rule):
      new_choices_list = choices_list_sorted(cand_choices_list)
      assert len(new_choices_list) > 0, 'Expected new_choices_list to be non-empty'
      choices_list_history.append(new_choices_list)
      all_choices_list = _choices_list_history_to_choices_list(choices_list_history)
      all_choices_list = choices_list_sorted(all_choices_list)
      all_choices_list = _add_verified_choice_options(all_choices_list, verified_choice_options)
      if _choices_lists_ab_failed_contains(choices_lists_ab_failed, all_choices_list):
        logger.debug('Generated choices list has already been tried and failed; skipping.')
        continue
      if _choices_lists_error_contains(choices_lists_error, all_choices_list):
        logger.debug('Generated choices list has already been tried and caused error; skipping.')
        continue
      return {'type': 'ASTNODE', 'choices_list': all_choices_list}

  except VerifiedRulesExhaustedError as err:
    no_choices_rc = None
    if err.no_choices_snippet is None and src_main_code:
      try:
        src_ast, dgann = d_ast_parse.parse_text_dbg(src_main_code, 'py')
        no_choices_rc = d_ast_parse.choice_identifier_to_range_cursor(
          err.choice_identifier, src_ast)
        err.no_choices_snippet = d_ast_parse.range_cursor_pretty_print(
          no_choices_rc, dgann, src_main_code)
      except Exception as ex:
        logger.warning(
          f'Failed to resolve no_choices_snippet for {err.choice_identifier}: {ex}')

    if err.not_matching_rules_str is None and translation_rules_main_code and no_choices_rc is not None:
      try:
        not_matching_rules = []
        rules_parsed = d_grammar_rules.parse_analyze_rules_optim(translation_rules_main_code)
        for rule_parsed in rules_parsed:
          matcher = rule_parsed.get('match')
          if matcher is None:
            continue
          match_obj = _match_rule_to_range_cursor(matcher, no_choices_rc)
          if match_obj.get('is_matched'):
            continue
          not_matching_rules.append(d_grammar_rules.pretty_rule(rule_parsed))
        err.not_matching_rules_str = '\n\n'.join(not_matching_rules)
      except Exception as ex:
        logger.warning(
          f'Failed to resolve not_matching_rules_str for {err.choice_identifier}: {ex}')
    raise

  tight_choices = []
  for range_info, choice_idxs in choice_options:
    if len(choice_idxs) <= 1:
      rel = range_info_to_rel.get(range_info, {})
      snippet = None
      if src_main_code is not None:
        try:
          snippet = choice_identifier_to_snippet(range_info, src_main_code)
        except Exception:
          snippet = None
      tight_choices.append({
        'range_info': range_info,
        'choice_idxs': choice_idxs,
        'current_rule_id': rel.get('current_rule_id'),
        'next_choices_count': rel.get('next_choices_count'),
        'current_choose_idx': rel.get('current_choose_idx'),
        'snippet': snippet,
      })
  if tight_choices:
    logger.warning(
      f'No new choices available; nodes with <=1 choice: '
      f'{json.dumps(tight_choices, indent=2)}'
    )
  raise RuleCombinationsExhaustedError('Exhaustively checked all possible choices')


def get_char_line_col_idxs(main_code_lines: List[str]) -> Tuple[List[int], List[int]]:
  '''
  Given the code split into lines, return the line and column indices of each character.
  The column index is -1 for the newline character.
  '''
  line_idxs = []
  col_idxs = []
  for i, line in enumerate(main_code_lines):
    for j, _ in enumerate(line):
      line_idxs.append(i)
      col_idxs.append(j)
    # the newline char
    line_idxs.append(i)
    col_idxs.append(-1)
  return line_idxs, col_idxs


def _build_line_idx_to_exids(
  tar_main_code: str,
  map_to_exid: Dict[int, List[dict]],
) -> Dict[int, Set[int]]:
  '''
  Build a mapping from line index to expansion ids on that line.
  '''
  main_code_lines = tar_main_code.split('\n')
  line_idxs, _ = get_char_line_col_idxs(main_code_lines)

  line_idx_to_exids : Dict[int, Set[int]] = {}
  for exid, tokens_by_ex in map_to_exid.items():
    for token_by_ex in tokens_by_ex:
      token = token_by_ex['str']
      token_range = token_by_ex['range']
      _si, _ei = token_range
      assert tar_main_code[_si:_ei] == token, 'sanity check: discrepancy in token range'
      line_si : int = line_idxs[_si]
      line_ei : int = line_idxs[_ei]
      assert line_si <= line_ei, 'sanity check: start line should be <= end line'
      if line_si == line_ei:
        assert token in main_code_lines[line_si], \
          'sanity check: single-line token not found in tar_main_code'
      else:
        assert token in '\n'.join(main_code_lines[line_si:line_ei + 1]), \
          'sanity check: multi-line token not found in tar_main_code'
      line_idx_to_exids.setdefault(line_si, set()).add(exid)

  return line_idx_to_exids


def _find_log_statement_line_idx(
  tar_program_instr: str,
  log_stat_idx: int
) -> Optional[int]:
  '''
  Return 0-based line index of a myexactlog statement in tar_program_instr.
  '''
  for i, line in enumerate(tar_program_instr.split('\n')):
    if line.lstrip().startswith(f'myexactlog({log_stat_idx}'):
      return i
  return None


def get_err_line_idx_in_tar_main_code(
  line_content: str,
  err_line_tpi: int,
  tar_program_instr: str,
  tar_main_code: str
) -> int:
  '''
  Get the index of the line in `tar_main_code` that corresponds to the error line.
  PARAM tar_program_instr: instrumented target program (test, main, test call)
  PARAM tar_main_code: main code of the target program (main)
  PARAM err_line_tpi: line number in `tar_program_instr` where the error occurred (1 indexed)
  PARAM line_content: content of the line where the error occurred in `tar_program_instr`
  '''
  tpi_chunks = tar_program_instr.split(tar_main_code)
  assert len(tpi_chunks) == 2, 'sanity check: tar_main_code should appear exactly once in wrapper'

  pre_main_code = tpi_chunks[0]
  pre_main_code_line_count = len(pre_main_code.split('\n'))

  err_line_idx = err_line_tpi - pre_main_code_line_count
  main_code_lines = tar_main_code.split('\n')
  expected_line = ''
  if 0 <= err_line_idx < len(main_code_lines):
    expected_line = main_code_lines[err_line_idx]
    if line_content in expected_line:
      return err_line_idx
    # Whitespace-agnostic match for formatting differences (e.g., pretty-printer spacing).
    norm_expected_line = re.sub(r'\s+', '', expected_line)
    norm_line_content = re.sub(r'\s+', '', line_content)
    if norm_line_content and norm_line_content in norm_expected_line:
      logger.warning(
        'Error line mismatch; falling back to whitespace-agnostic expected-line match. '
        f'expected_idx={err_line_idx}')
      return err_line_idx

  # Fallback: line numbers can drift if the executed program is instrumented.
  # Try to locate the error line directly in tar_main_code.
  candidates = [i for i, line in enumerate(main_code_lines) if line_content in line]
  if len(candidates) == 1:
    logger.warning(
      'Error line mismatch; falling back to content match in tar_main_code. '
      f'expected_idx={err_line_idx}, matched_idx={candidates[0]}')
    return candidates[0]

  stripped = line_content.strip()
  if stripped:
    candidates = [i for i, line in enumerate(main_code_lines) if stripped in line]
    if len(candidates) == 1:
      logger.warning(
        'Error line mismatch; falling back to stripped content match in tar_main_code. '
        f'expected_idx={err_line_idx}, matched_idx={candidates[0]}')
      return candidates[0]

  # Last content-based fallback: ignore all whitespace when matching.
  norm_line_content = re.sub(r'\s+', '', line_content)
  if norm_line_content:
    candidates = [
      i for i, line in enumerate(main_code_lines)
      if norm_line_content in re.sub(r'\s+', '', line)
    ]
    if len(candidates) == 1:
      logger.warning(
        'Error line mismatch; falling back to whitespace-agnostic content match in tar_main_code. '
        f'expected_idx={err_line_idx}, matched_idx={candidates[0]}')
      return candidates[0]
    if len(candidates) > 1:
      # Pick the closest candidate to preserve line-number signal.
      best_idx = min(candidates, key=lambda idx: abs(idx - err_line_idx))
      logger.warning(
        'Error line mismatch; multiple whitespace-agnostic candidates found. '
        f'expected_idx={err_line_idx}, matched_idx={best_idx}, candidates={candidates}')
      return best_idx

  # Do not crash the whole run on line matching failure; keep exploring choices.
  if len(main_code_lines) == 0:
    logger.warning(
      'Error line mismatch and empty tar_main_code. '
      'Falling back to line index 0 to continue search.')
    return 0

  fallback_idx = min(max(err_line_idx, 0), len(main_code_lines) - 1)
  logger.warning(
    'Error line mismatch; using bounded fallback index to continue search. '
    f'expected_idx={err_line_idx}, fallback_idx={fallback_idx}, '
    f'expected_line={expected_line!r}, actual_line={line_content!r}')
  return fallback_idx


def _build_mod_dbg_history_maps(
  translate_dbg_history: List[dict]
) -> Tuple[Dict[int, dict], Dict[int, dict]]:
  '''
  Build:
  - mod_dbg_history: a compact alt-step keyed map
  - exid_to_mod_dbg_history_elem: expansion-id to alt-step map
  '''
  mod_dbg_history : Dict[int, dict] = {}
  exid_to_mod_dbg_history_elem : Dict[int, dict] = {}

  for elem in translate_dbg_history:
    alt_step = elem['alt_step']
    exid = elem['dbg_info']['ex_id']
    # dbg history elems should come in order of alt_step starting from 1.
    assert alt_step - 1 == len(mod_dbg_history), 'sanity check: dbg history elems should come in order'
    mod_dbg_history_elem = {
      'alt_step': alt_step,
      'next_choices_count': elem['next_choices_status']['count'],
      'next_choices_all_known': elem['next_choices_status']['done'],
      'ex_id': exid,
      'current_choose_idx': elem['dbg_info']['notes']['choose_idx'],
      'current_rule_id': elem['dbg_info']['notes']['rule_id'],
      'current_range_info': elem['range_info']
    }
    mod_dbg_history[alt_step] = mod_dbg_history_elem
    exid_to_mod_dbg_history_elem[exid] = mod_dbg_history_elem

  return mod_dbg_history, exid_to_mod_dbg_history_elem


def _get_rel_alt_step_infos_from_exids(
  exids_err_line: List[int],
  translate_dbg_history: List[dict],
) -> Dict[int, dict]:
  '''
  Given expansion ids, return relevant alt-step info entries.
  NOTE alt_step is DuoGlot terminology for a single step in the translation process.
  '''
  mod_dbg_history, exid_to_mod_dbg_history_elem = _build_mod_dbg_history_maps(translate_dbg_history)
  rel_alt_step_infos : Dict[int, dict] = {}
  _RELATED_WINDOW_SIZE = 0

  for exid_err_line in exids_err_line:
    if exid_err_line not in exid_to_mod_dbg_history_elem:
      continue
    mod_dbg_history_elem = exid_to_mod_dbg_history_elem[exid_err_line]
    alt_step : int = mod_dbg_history_elem['alt_step']

    # previous _RELATED_WINDOW_SIZE elements + alt_step itself
    rel_alt_steps = list(range(alt_step - _RELATED_WINDOW_SIZE, alt_step + 1))
    for rel_alt_step in rel_alt_steps:
      # because we use `rel_alt_step - 1` below
      if rel_alt_step - 1 < 1:
        continue
      # keep only if number of rules at that step is greater than 1
      if mod_dbg_history[rel_alt_step - 1]['next_choices_count'] <= 1:
        continue
      rel_alt_step_infos[rel_alt_step] = {
        'next_choices_count': mod_dbg_history[rel_alt_step - 1]['next_choices_count'],
        'current_choose_idx': mod_dbg_history[rel_alt_step]['current_choose_idx'],
        # 'ex_id': mod_dbg_history[rel_alt_step]['ex_id'],  # not used
        'current_rule_id': mod_dbg_history[rel_alt_step]['current_rule_id'],
        'current_range_info': mod_dbg_history[rel_alt_step]['current_range_info']
      }

  if len(rel_alt_step_infos) == 0:
    raise RuleCombinationsExhaustedError('No alternative rules found for the error line')

  return rel_alt_step_infos


def get_proposed_choices_based_on_line_idxs(
  tar_main_code: str,
  err_line_idxs: List[int],
  choices_list_history: list,
  map_to_exid: Dict[int, List[dict]],
  translate_dbg_history: List[dict],
  verified_choice_options: List[Tuple[Tuple[int, int, int], List[int]]],
  raise_on_missing_vrf_rule: bool = False,
  src_main_code: Optional[str] = None,
  translation_rules_main_code: Optional[str] = None,
  excluded_choice_options: Optional[List[Tuple[Tuple[int, int, int], List[int]]]] = None,
  choices_lists_ab_failed: list = [],
  choices_lists_error: list = [],
):
  '''
  PARAM tar_main_code: main code (f_gold) of the target program.
  PARAM err_line_idxs: a list of 0-based indices of the lines in
  `tar_main_code` where the error occurred.
  PARAM verified_choice_options: a list of choices that should not be modified.
  '''

  line_idx_to_exids = _build_line_idx_to_exids(tar_main_code, map_to_exid)
  missing_err_line_idxs = [idx for idx in err_line_idxs if idx not in line_idx_to_exids]
  if len(missing_err_line_idxs) > 0:
    logger.warning(
      'No expansion ids found for some error lines in tar_main_code. '
      f'err_line_idxs={err_line_idxs}, missing={missing_err_line_idxs}')

  # Collect all expansion ids that are related to the error lines.
  exids_err_line : List[int] = list(sorted(set(
    [exid for err_line_idx in err_line_idxs for exid in line_idx_to_exids.get(err_line_idx, set())]
  )))

  rel_alt_step_infos = _get_rel_alt_step_infos_from_exids(exids_err_line, translate_dbg_history)
  rel_alt_step_infos = rel_alt_step_info_remove_duplicates(rel_alt_step_infos)

  new_choices = get_next_unique_choices(
    rel_alt_step_infos,
    choices_list_history,
    verified_choice_options,
    raise_on_missing_vrf_rule,
    src_main_code=src_main_code,
    translation_rules_main_code=translation_rules_main_code,
    excluded_choice_options=excluded_choice_options,
    choices_lists_ab_failed=choices_lists_ab_failed,
    choices_lists_error=choices_lists_error,
  )
  return new_choices


def get_proposed_choices_based_on_exids(
  exids_err_line: List[int],
  choices_list_history: list,
  translate_dbg_history: List[dict],
  verified_choice_options: List[Tuple[Tuple[int, int, int], List[int]]],
  raise_on_missing_vrf_rule: bool = False,
  src_main_code: Optional[str] = None,
  translation_rules_main_code: Optional[str] = None,
  excluded_choice_options: Optional[List[Tuple[Tuple[int, int, int], List[int]]]] = None,
  choices_lists_ab_failed: list = [],
  choices_lists_error: list = [],
):
  '''
  Propose new choices directly from expansion ids.
  '''
  rel_alt_step_infos = _get_rel_alt_step_infos_from_exids(exids_err_line, translate_dbg_history)
  rel_alt_step_infos = rel_alt_step_info_remove_duplicates(rel_alt_step_infos)

  new_choices = get_next_unique_choices(
    rel_alt_step_infos,
    choices_list_history,
    verified_choice_options,
    raise_on_missing_vrf_rule,
    src_main_code=src_main_code,
    translation_rules_main_code=translation_rules_main_code,
    excluded_choice_options=excluded_choice_options,
    choices_lists_ab_failed=choices_lists_ab_failed,
    choices_lists_error=choices_lists_error,
  )

  return new_choices


def get_proposed_choices_compile_error(
  tar_program_instr: str,
  tar_main_code: str,
  tar_error_dict: dict,
  choices_list_history: list,
  map_to_exid: Dict[int, List[dict]],
  translate_dbg_history: List[dict],
  verified_choice_options: List[Tuple[Tuple[int, int, int], List[int]]] = [],
  raise_on_missing_vrf_rule: bool = False,
  src_main_code: Optional[str] = None,
  translation_rules_main_code: Optional[str] = None,
  choices_lists_ab_failed: list = [],
  choices_lists_error: list = [],
) -> dict:
  '''
  NOTE PARAM map_to_exid:
  <map_to_exid> -> Dict[<exid>, List[<token_info>]]
  <map_to_exid>: (id of expansion: list of all tokens that were created by this expansion)
  <token_info> -> {
    'ex_id': (id of expansion this token belongs to),
    'str': (token in tar_main_code),
    'range': (range of token in tar_main_code)
  }
  In informal words, map_to_exid contains expansion ids and all tokens that
  were created by this expansion + ranges of every token.
  map_to_exid is created by `d_ast_pretty.ast_to_code()` function.
  The function `d_ast_pretty.ast_to_code()` is called in `p_pirel.duoglot_translate_wrapper()`.

  NOTE PARAM translate_dbg_history:
  <translate_dbg_history> -> List[<history_elem>]
  <history_elem> -> {
    'alt_step' -> (translation step id),
    'range_info' -> (source AST to which the rule was mapped),
    'next_choices_status' -> <next_choices_status>,
    'dbg_info' -> <dbg_info>
  }
  <next_choices_status> -> {
    'count' -> (number of rules that matched a source AST),
    'done' -> (next_choices_all_known?)
  }
  <dbg_info> -> {
    'ex_id' -> (expansion.ex_id, id of expansion that was created from source AST),
    'corres_slot_id' -> (expansion.corres_slot_id, id of slot in source AST),
    'src_matching_node_ids' -> (expansion.matching_node_ids),
    'slot_src_matching_node_ids' -> ([_get_node_ids_from_range_cursor(x) for x in expansion.src_slot_cursors]),
    'notes' -> <notes>,
    'slot_names' -> (expansion.slot_names),
    'slot_ids' -> ([(x.slot_id if x is not None else None) for x in expansion.slots]),
    'outcome' -> (AC, RE, or ER),
    'elem_list_info_id' -> (self._optional_dbg_info_func((self._tail_stack, len(self._tail_stack)), _tail_stack_length_to_elem_list)),
    'loop_count' -> (DelimitedParser._loop_idx)
  }
  <notes> -> {
    'choose_idx': (index of rule from a list of matched rules),
    'rule_id': (id of the rule in the ruleset)
  }
  <notes>: (expansion.notes)
  This object is created in `d_grammar_expand.TransSession._get_alt_debug_history()`
  and is passed to `p_pirel.duoglot_translate_wrapper()`.
  <dbg_info> is a dictionary that is created by
  `d_grammar_dlmparser.DelimitedParser.add_expansion_parse_until_stuck()`,
  which in turn is called by `d_grammar_expand.TransSession._ensure_parser_result()`.
  '''

  p_utils.log_json_time(f'args-get_proposed_choices_compile_error.json', locals())
  logger.debug('Starting p_ext_rule_chooser.get_proposed_choices_compile_error')

  # Unpack `tar_error_dict`. "tpi" stands for "tar_program_instr"
  error_msg = tar_error_dict['error_msg']  # e.g. 'SyntaxError: invalid syntax'
  error_type = tar_error_dict['error_type']  # e.g. 'SyntaxError'
  line_content = tar_error_dict['line_content']  # code snippet at the line of error in `tar_program_instr`
  file_path = tar_error_dict['file_path']  # absolute path to the file where the error occurred
  err_line_tpi = tar_error_dict['line_num']  # line number in the file where the error occurred (0 indexed)

  '''
  Current implementation of `get_proposed_choices_compile_error()` can propose choices
  only on the basis of errors in "tar_program_run.js". And the following
  are the errors that are supported.
  '''
  assert error_type in p_consts.SUPPORTED_ERROR_TYPES_JS, f'unsupported error type {error_type}'

  '''
  The following function returns the error line number in tar_main_code.
  We need to do this because the `err_line_tpi` points to the line number
  in "tar_program_run.js", which is the wrapper code that runs the main code.
  err_line_idx is 0-based.
  '''
  err_line_idx = get_err_line_idx_in_tar_main_code(line_content, err_line_tpi, tar_program_instr, tar_main_code)

  logger.debug(
    f'there was an error running `tar_program_instr`\n'
    f'{error_type} "{error_msg}" on line {err_line_idx + 1} of "{line_content}"')

  new_choices = get_proposed_choices_based_on_line_idxs(
    tar_main_code,
    [err_line_idx],
    choices_list_history,
    map_to_exid,
    translate_dbg_history,
    verified_choice_options,
    raise_on_missing_vrf_rule,
    src_main_code=src_main_code,
    translation_rules_main_code=translation_rules_main_code,
    choices_lists_ab_failed=choices_lists_ab_failed,
    choices_lists_error=choices_lists_error,
  )
  return new_choices


def get_proposed_choices_semantic_error(
  tar_program_instr: str,
  tar_main_code: str,
  error_lines: dict,
  mismatched_log_stat_idxs: Optional[Tuple[int, int]],
  choices_list_history: list,
  map_to_exid: Dict[int, List[dict]],
  translate_dbg_history: List[dict],
  verified_choice_options: List[Tuple[Tuple[int, int, int], List[int]]] = [],
  raise_on_missing_vrf_rule: bool = False,
  src_main_code: Optional[str] = None,
  translation_rules_main_code: Optional[str] = None,
  choices_lists_ab_failed: list = [],
  choices_lists_error: list = [],
) -> dict:
  '''
  Propose new choices based on a semantic error. A semantic error occurs
  when traces of src and tar test scripts do not match.

  PARAM error_lines: a dictionary where keys are line numbers (0-based) and values
  are the content of the lines that caused the semantic error. Sample:
  {
    12: "    while (x && m) {"
  }
  '''

  p_utils.log_json_time(f'args-get_proposed_choices_semantic_error.json', locals())
  logger.debug('Starting p_ext_rule_chooser.get_proposed_choices_compile_error')

  # Normalize line-number keys because cached semantic errors can arrive with
  # JSON-restored string keys, while this function expects integer line indexes.
  normalized_error_lines = {}
  for line_num, line_content in error_lines.items():
    if isinstance(line_num, int):
      line_idx = line_num
    else:
      try:
        line_idx = int(line_num)
      except (TypeError, ValueError):
        logger.debug(f'Ignoring semantic error line with invalid index key: {line_num!r}')
        continue
    normalized_error_lines[line_idx] = line_content
  error_lines = normalized_error_lines

  logger.debug(
    f'There are {len(error_lines)} error lines in the semantic error\n'
    f'{json.dumps(error_lines, indent=2)}')

  if len(error_lines) == 0:
    if mismatched_log_stat_idxs is None:
      raise RuleCombinationsExhaustedError('No error lines and no log idxs for semantic error')
    log_stat_idx = min(mismatched_log_stat_idxs)
    line_idx = _find_log_statement_line_idx(tar_program_instr, log_stat_idx)
    if line_idx is None:
      raise RuleCombinationsExhaustedError('Log statement not found for semantic error')
    line_content = tar_program_instr.split('\n')[line_idx]
    err_line_idx = get_err_line_idx_in_tar_main_code(line_content, line_idx + 1, tar_program_instr, tar_main_code)
    exids_err_line = list(sorted(
      _build_line_idx_to_exids(tar_main_code, map_to_exid).get(err_line_idx, set())
    ))
    if len(exids_err_line) == 0:
      raise RuleCombinationsExhaustedError('No exids found for semantic error log line')
    return get_proposed_choices_based_on_exids(
      exids_err_line,
      choices_list_history,
      translate_dbg_history,
      verified_choice_options,
      raise_on_missing_vrf_rule,
      src_main_code=src_main_code,
      translation_rules_main_code=translation_rules_main_code,
      excluded_choice_options=[],
      choices_lists_ab_failed=choices_lists_ab_failed,
      choices_lists_error=choices_lists_error,
    )

  '''
  line_num is 0-based line index of a trace mismatch in
  tar_program_instr, we need to get the 0-based line index in tar_main_code.
  '''
  err_line_idxs = [
    get_err_line_idx_in_tar_main_code(
      line_content, line_num + 1, tar_program_instr, tar_main_code)
    for line_num, line_content in error_lines.items()
  ]

  new_choices = get_proposed_choices_based_on_line_idxs(
    tar_main_code,
    err_line_idxs,
    choices_list_history,
    map_to_exid,
    translate_dbg_history,
    verified_choice_options,
    raise_on_missing_vrf_rule,
    src_main_code=src_main_code,
    translation_rules_main_code=translation_rules_main_code,
    choices_lists_ab_failed=choices_lists_ab_failed,
    choices_lists_error=choices_lists_error,
  )
  return new_choices
