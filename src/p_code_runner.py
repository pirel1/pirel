import asyncio
import copy
import json
import re
import sys
from pathlib import Path
from typing import Optional, Set, Tuple

import d_ast_parse
import d_utils
import p_consts
import p_subject
import p_utils
import p_visitor_js as pvjs
import p_visitor_py as pvpy
from p_config import Config


logger = p_utils.setup_logger(__name__)


CODE_RUN_COMMANDS = {'py': sys.executable, 'js': 'node'}
assert all(map(CODE_RUN_COMMANDS.__contains__, p_consts.LANG_DICT))

TMP_DIR = Path('/tmp/pirel_code_runner')
TMP_DIR.mkdir(exist_ok=True)


def get_mylog_impl(lang: str, subject_name: Optional[str] = None) -> str:
  '''
  Get the mylog implementation for the given language.
  If `subject_name` is provided, prefer a subject-specific serializer
  named `mylog_pirel_<subject_name>.<lang>` when it exists.
  '''
  assert lang in p_consts.LANG_DICT, f'Unsupported language: {lang}'
  serializers_dir = p_consts.SERIALIZERS_DIR / 'trace-serializers'
  mylog_fpath = serializers_dir / f'mylog_pirel.{lang}'
  if subject_name:
    subject_mylog_fpath = serializers_dir / f'mylog_pirel_{subject_name}.{lang}'
    if subject_mylog_fpath.exists():
      mylog_fpath = subject_mylog_fpath
  assert mylog_fpath.exists(), f'Mylog implementation not found for {lang}'
  return p_utils.read_text(mylog_fpath)


def _get_temp_filename(text: str, lang: str) -> str:
  hexhash = d_utils.string_sha256(text)[:8]
  return TMP_DIR / f'{hexhash}.{lang}'


def _extract_trace_from_stdout(
  stdout: str,
  ignore_json_errors: bool = False,
) -> list:
  '''
  Parses whatever was produced by the `mylog` function

  sample stdout:
  ["MYLOGEX:", ["number", 0]]
  ["MYLOGEX:", ["number", 42]]
  89 ["MYLOGEX:",["number",1],["hash",64,"31258e253c85ed2fcf5c0c1df7817d48be55a95e1b90d9b4f201183cf6bf9afb"]]
  '''
  lines_str = stdout.split('\n')
  trace = []
  for line_idx, line_str in enumerate(lines_str, start=1):
    if line_str.startswith('["MYLOGEX:"'):
      json_payload_str = line_str

    # Cases where myexactlog output is not at the beginning of the line
    # e.g. '89 ["MYLOGEX:",["number",1],["hash",4,"8e25"]]'.
    # Happens in JS when process.stdout.write is used instead of console.log
    # as in G0004 in GFG benchmark.
    elif '["MYLOGEX:"' in line_str:
      begin_idx = line_str.index('["MYLOGEX:"')
      json_payload_str = line_str[begin_idx:]
    else:
      continue

    try:
      line_obj = json.loads(json_payload_str)
    except json.JSONDecodeError as err:
      if not ignore_json_errors:
        raise
      preview = json_payload_str[:200]
      logger.warning(
        'Skipping malformed MYLOGEX JSON line while parsing stdout '
        f'(line={line_idx}, len={len(json_payload_str)}): {err}. '
        f'preview={preview!r}')
      continue

    trace.append(['list', len(line_obj) - 1, line_obj[1:]])

  return ['list', len(trace), trace]


def extract_err_from_stderr_JS(
  stderr: str,
  lang: str,
) -> dict:
  '''
  Parse the error message from the stderr of the JS code.
  Refer to tests for sample inputs and expected outputs.

  SAMPLE:
  ```
  /tmp/pirel_code_runner/ef41e541.js:512
  TEST_DICT = {
            ^

  ReferenceError: TEST_DICT is not defined
      at Object.<anonymous> (/tmp/pirel_code_runner/ef41e541.js:512:11)
      at Module._compile (node:internal/modules/cjs/loader:1529:14)
      at Module._extensions..js (node:internal/modules/cjs/loader:1613:10)
      at Module.load (node:internal/modules/cjs/loader:1275:32)
      at Module._load (node:internal/modules/cjs/loader:1096:12)
      at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:164:12)
      at node:internal/main/run_main_module:28:49
  13:40:58,295 toml DEBUG p_rule_applicator._run_tests:1546

  Node.js v20.19.3
  ```
  '''

  logger.debug('Starting p_code_runner._extract_err_from_stderr')
  assert lang == 'js', f'Unsupported language: {lang}'
  assert str(TMP_DIR) in stderr, f'Expected "{TMP_DIR}" in stderr: {stderr}'

  RE_FIRST_LINE = r'^(.+):(\d+)$'
  RE_AT_LINE = r'^at(.*) \(?(.+):(\d+):(\d+)\)?$'

  lines = [line.strip() for line in stderr.split('\n')]
  at_lines = [line for line in lines[5:]
              if line.startswith('at ') and str(TMP_DIR) in line]

  if len(at_lines) == 0:
    first_line = lines[0]
    match = re.match(RE_FIRST_LINE, first_line)
    assert match is not None, f'Expected match for first_line: {first_line}'
    file_path = match.group(1)
    line_num = int(match.group(2))
  else:
    at_line = at_lines[0]
    match = re.match(RE_AT_LINE, at_line)
    assert match is not None, f'Expected match for at_line: {at_line}'
    file_path = match.group(2)
    line_num = int(match.group(3))

  line_content = lines[1]
  assert lines[2].strip('^') == '', f'Expected one or more hats "^" on line #3: {lines[2]}'
  assert lines[3] == '', f'Expected nothing on line #4: {lines[3]}'

  # Error messages can contain additional ":" (e.g. "{:.2f}"), so split only
  # on the first ":" to preserve the full message payload.
  error_type, sep, error_msg_raw = lines[4].partition(':')
  error_type = error_type.strip()
  assert error_type in p_consts.SUPPORTED_ERROR_TYPES_JS, f'Unsupported error type: {error_type}'
  error_msg = error_msg_raw.strip() if sep else ''

  return {
    'error_type': error_type,
    'error_msg': error_msg,
    'file_path': file_path,
    'line_num': line_num,  # 1-indexed line number
    'line_content': line_content
  }


def _get_global_non_fn_def_stats(root_ast: list) -> list:
  '''
  PARAM root_ast: the root AST node of the program in JS.
  RETURN a list of global statements that are not function definitions.
  '''
  ntype, nid, children = root_ast[0], root_ast[1], root_ast[2:]
  assert ntype == 'js.program', f'Expected root AST node type to be js.program, got {ntype}'
  global_non_fn_def_stats = [
    child for child in children
    if child[0] not in ['js.function_declaration', 'js.generator_function_declaration']
  ]
  return global_non_fn_def_stats



def _get_fn_decl_name(fn_decl_node: list) -> str:
  '''
  PARAM fn_decl_node: AST node of type js.function_declaration.
  RETURN declared function name.
  '''
  ntype, _, children = fn_decl_node[0], fn_decl_node[1], fn_decl_node[2:]
  assert ntype == 'js.function_declaration', f'Expected function declaration node, got {ntype}'
  fn_name_node = None
  fn_name_idx = None
  for idx, child in enumerate(children):
    if isinstance(child, list) and child[0] == 'js.identifier':
      fn_name_node = child
      fn_name_idx = idx
      break
  assert fn_name_node is not None, \
    f'Expected to find js.identifier child for function name in function_declaration node: {fn_decl_node}'
  assert fn_name_idx is not None, \
    f'Expected to find index of js.identifier child for function name in function_declaration node: {fn_decl_node}'
  assert fn_name_idx in [1, 2], \
    f'Expected function name identifier to be at index 1 or 2 in function_declaration children, got index {fn_name_idx} in node: {fn_decl_node}'
  idntype, _, idchildren = fn_name_node[0], fn_name_node[1], fn_name_node[2:]
  assert idntype == 'js.identifier', f'Expected function name node to be an identifier, got {idntype}'
  assert len(idchildren) == 1, \
    f'Expected identifier node to have exactly one child (the function name), got {len(idchildren)}: {fn_name_node}'
  assert isinstance(idchildren[0], str), \
    f'Expected function name child of identifier node to be a string, got {idchildren[0]}'
  return json.loads(idchildren[0])


def _collect_fn_decl_nodes(node: list, out_nodes: list) -> None:
  ntype, _, children = node[0], node[1], node[2:]
  if ntype == 'js.function_declaration':
    out_nodes.append(node)
  for child in children:
    if isinstance(child, list):
      _collect_fn_decl_nodes(child, out_nodes)


def _get_fn_def_stats(root_ast: list, fn_name: str) -> list:
  '''
  PARAM root_ast: the root AST node of the program in JS.
  PARAM fn_name: the name of the function to extract.
  RETURN a list of statements that are part of the specified function such that
         the statements exclude inner function definitions.
  '''
  def __find_fn(node: list, fn_name: str) -> Optional[list]:
    ntype, nid, children = node[0], node[1], node[2:]
    if ntype == 'js.function_declaration':
      # first nt child that is of type js.identifier should be the function name
      # it is not fixed, because the function can be a generator or async which introduces terminals
      fn_name_node = None
      fn_name_idx = None
      for idx, child in enumerate(children):
        if isinstance(child, list) and child[0] == 'js.identifier':
          fn_name_node = child
          fn_name_idx = idx
          break
      assert fn_name_node is not None, f'Expected to find js.identifier child for function name in function_declaration node: {node}'
      assert fn_name_idx is not None, f'Expected to find index of js.identifier child for function name in function_declaration node: {node}'
      assert fn_name_idx in [1, 2], f'Expected function name identifier to be at index 1 or 2 in function_declaration children, got index {fn_name_idx} in node: {node}'
      idntype, idnid, idchildren = fn_name_node[0], fn_name_node[1], fn_name_node[2:]
      assert idntype == 'js.identifier', f'Expected function name node to be an identifier, got {idntype}'
      assert len(idchildren) == 1, f'Expected identifier node to have exactly one child (the function name), got {len(idchildren)}: {fn_name_node}'
      assert isinstance(idchildren[0], str), f'Expected function name child of identifier node to be a string, got {idchildren[0]}'
      identifier_name = json.loads(idchildren[0])
      if identifier_name == fn_name:
        return node
    for child in children:
      # skip terminal children
      if not isinstance(child, list):
        continue
      result = __find_fn(child, fn_name)
      if result is not None:
        return result
    return None
  fn_node = __find_fn(root_ast, fn_name)
  assert fn_node is not None, f'Expected to find function definition for {fn_name}'
  # statements are located inside statement block which is a child of the function_declaration node
  statement_block_node = fn_node[-1]
  sbntype, sbnid, sbchildren = statement_block_node[0], statement_block_node[1], statement_block_node[2:]
  assert sbntype == 'js.statement_block', f'Expected function body to be a statement block, got {sbntype}'
  result_stats = []
  for child in sbchildren:
    # skip terminal children (e.g. "{" and "}")
    if not isinstance(child, list):
      continue
    # skip inner function definitions
    if child[0] == 'js.function_declaration':
      continue
    # skip inner generator function definitions
    if child[0] == 'js.generator_function_declaration':
      continue
    result_stats.append(child)
  return result_stats


def _are_ast_nodes_equivalent(node1: list, node2: list) -> bool:
  '''
  Check if two AST nodes are identical.
  '''
  if isinstance(node1, str) and isinstance(node2, str):
    return node1 == node2
  assert isinstance(node1, list) and isinstance(node2, list), f'Expected both nodes to be lists or strings: {node1} vs {node2}'
  assert len(node1) >= 3 and len(node2) >= 3, f'Expected AST nodes to have at least 3 elements (type, id, and children): {node1} vs {node2}'
  if node1[0] != node2[0]:
    return False
  # node ids can be different
  if len(node1) != len(node2):
    return False
  for child1, child2 in zip(node1[2:], node2[2:]):
    if not _are_ast_nodes_equivalent(child1, child2):
      return False
  return True


def _build_stat_2_stat_line_map(
  orig_stat: list,
  orig_ann: dict,
  mod_stat: list,
  mod_ann: dict,
) -> dict:
  '''
  RETURN a 1-based line map from the original statement to the modified statement.
  '''
  assert _are_ast_nodes_equivalent(orig_stat, mod_stat), f'Expected equivalent AST nodes for statements: {orig_stat} vs {mod_stat}'
  orig_ntype, orig_nid, orig_children = orig_stat[0], orig_stat[1], orig_stat[2:]
  mod_ntype, mod_nid, mod_children = mod_stat[0], mod_stat[1], mod_stat[2:]

  orig_boundary = orig_ann[orig_nid]
  mod_boundary = mod_ann[mod_nid]

  orig_start_byte, orig_end_byte, orig_start_char, orig_end_char = orig_boundary
  mod_start_byte, mod_end_byte, mod_start_char, mod_end_char = mod_boundary

  orig_start_char_line, orig_start_char_col = orig_start_char
  orig_end_char_line, orig_end_char_col = orig_end_char
  mod_start_char_line, mod_start_char_col = mod_start_char
  mod_end_char_line, mod_end_char_col = mod_end_char

  orig_lines = list(range(orig_start_char_line, orig_end_char_line + 1))
  mod_lines = list(range(mod_start_char_line, mod_end_char_line + 1))

  '''
  The assumption is that both original and modified code are formatted in the same way,
  so that equivalent statements should occupy the same number of lines.
  '''
  assert len(orig_lines) == len(mod_lines), f'Expected same number of lines for equivalent statements: {orig_lines} vs {mod_lines}'

  line_map = {}
  for o_line, m_line in zip(orig_lines, mod_lines):
    line_map[m_line + 1] = o_line + 1
  return line_map


def _build_tar_line_map_from_modified_to_original(
  orig_code: str,
  modified_code: str,
  gt_fn_names: Set[str],
) -> dict:
  '''
  Build a line map from modified code to original code.
  The line map is a dictionary mapping line numbers (1-based) in modified_code
  to line numbers (1-based) in orig_code.
  ASSUMPTIONS
  1. Map only lines that are in functions that don't have gt translations and global statements.
     The idea is that errors MUST NOT happen at other lines such as
     a. function headers
     b. lines in functions that have gt translations
     c. closing braces of functions

  EXAMPLE INPUT
/////////// ORIGINAL
// global 1
function foo() {
    function bar() {
        function qux() {
            // quux statement 1
            // quux statement 2
        }
    }
    function baz() {
        // baz statement 1
        // baz statement 2
        // baz statement 3
    }
}
// global 2
// global 3
function quux() {}
// global 4
/////////// MODIFIED
// global 1
function foo() {
    function bar() {
        function qux() {
            // quux statement 1
            // quux statement 2
        }
        // added bar statement 1
        // added bar statement 2
    }
    function baz() {
        // baz statement 1
        // baz statement 2
        // baz statement 3
    }
    // added foo statement 1
    // added foo statement 2
    // added foo statement 3
}
// global 2
// global 3
function quux() {
    // added quux statement 1
    // added quux statement 2
    // added quux statement 3
}
// global 4
  '''

  orig_all_fn_names = pvjs.DefinedFunctionNameExtractor.get_defined_function_names(orig_code)
  mod_all_fn_names = pvjs.DefinedFunctionNameExtractor.get_defined_function_names(modified_code)
  assert len(set(mod_all_fn_names)) == len(mod_all_fn_names), f'Expected no duplicate function names in modified code'
  assert len(set(orig_all_fn_names)) == len(orig_all_fn_names), f'Expected no duplicate function names in original code'
  assert set(mod_all_fn_names) == set(orig_all_fn_names), f'Expected same function names in modified and original code'
  assert p_utils.are_same_lists(mod_all_fn_names, orig_all_fn_names), f'Expected same function names in modified and original code'

  untouched_fn_names = [fn_name for fn_name in mod_all_fn_names if fn_name not in gt_fn_names]
  orig_ast, orig_ann = d_ast_parse.parse_text_dbg(orig_code, 'js', keep_text=False)
  mod_ast, mod_ann = d_ast_parse.parse_text_dbg(modified_code, 'js', keep_text=False)
  line_map = {}

  '''
  map the globals first
  '''
  orig_global_stats = _get_global_non_fn_def_stats(orig_ast)
  mod_global_stats = _get_global_non_fn_def_stats(mod_ast)
  assert len(orig_global_stats) == len(mod_global_stats), f'Expected same number of global non-function-definition statements in original and modified code'
  for orig_stat, mod_stat in zip(orig_global_stats, mod_global_stats):
    assert _are_ast_nodes_equivalent(orig_stat, mod_stat), f'Expected equivalent AST nodes for global statement: {orig_stat} vs {mod_stat}'
    global_line_map = _build_stat_2_stat_line_map(orig_stat, orig_ann, mod_stat, mod_ann)
    line_map.update(global_line_map)

  '''
  map the statements in untouched functions next
  '''
  for fn_name in untouched_fn_names:
    orig_fn_stats = _get_fn_def_stats(orig_ast, fn_name)
    mod_fn_stats = _get_fn_def_stats(mod_ast, fn_name)
    assert len(orig_fn_stats) == len(mod_fn_stats), f'Expected same number of statements in function {fn_name} in original and modified code'
    for orig_stat, mod_stat in zip(orig_fn_stats, mod_fn_stats):
      assert _are_ast_nodes_equivalent(orig_stat, mod_stat), f'Expected equivalent AST nodes for statement in function {fn_name}: {orig_stat} vs {mod_stat}'
      stat_line_map = _build_stat_2_stat_line_map(orig_stat, orig_ann, mod_stat, mod_ann)
      line_map.update(stat_line_map)

  return line_map


def _replace_src_fns_with_pass_with_gt_translations(
  src_main_code: str,
  subject_name: str
) -> str:
  '''
  Revert action of `_replace_src_fns_with_gt_translations_with_pass`.
  Return a modified src_main_code where the bodies of functions that
  have ground-truth translations are replaced with their original bodies (instead of `pass`).
  '''
  logger.debug('Replacing bodies of src functions with ground-truth translations with their original bodies.')
  config_fpath = p_consts.SKEL_BENCHMARK_DIR / f'{subject_name}-config.json'
  if not config_fpath.exists():
    logger.warning(f'Config file {config_fpath} does not exist. Skipping restoring function bodies.')
    return src_main_code
  subject_config = p_utils.read_json(config_fpath)
  assert 'ground_truth_translations' in subject_config, 'expecting ground_truth_translations in subject config'
  gt_translations = subject_config['ground_truth_translations']
  fn_names = pvpy.DefinedFunctionNameExtractor.get_defined_function_names(src_main_code)
  modified_code = src_main_code
  for fn_name, gt_map in gt_translations.items():
    assert fn_name in fn_names, f'sanity check: function {fn_name} should be defined in src_main_code'
    assert fn_names.count(fn_name) == 1, f'sanity check: function {fn_name} should be defined only once in src_main_code'
    gt_fn_body = gt_map['src']
    modified_code = pvpy.FunctionBodyReplacer.replace_function_body(
      modified_code,
      fn_name,
      gt_fn_body,
      dont_touch_inner_fn_defs=True,
      dont_insert_pass_if_inner_fns_exist=True,
    )
  return modified_code


def _replace_tar_fns_with_gt_translations(
  tar_main_code: str,
  subject: p_subject.PirelSubject,
) -> Tuple[str, dict]:
  '''
  RETURN a modified tar_main_code where the bodies of functions that
  have ground-truth translations are replaced with their original bodies.
  RETURN a tuple of (modified_tar_main_code, line_map) where
  - modified_tar_main_code is the modified tar_main_code after replacing
    function bodies with ground-truth translations
  - line_map is a dictionary mapping line numbers (1-based) in modified_tar_main_code
    to line numbers (1-based) in original tar_main_code for lines that are part of ground-truth translations
  '''
  logger.debug('Replacing bodies of tar functions with ground-truth translations with their original bodies.')

  config_fpath = p_consts.SKEL_BENCHMARK_DIR / f'{subject.name}-config.json'
  if not config_fpath.exists():
    logger.warning(f'Config file {config_fpath} does not exist. Skipping restoring function bodies.')
    return tar_main_code, {}

  subject_config = p_utils.read_json(config_fpath)
  assert 'ground_truth_translations' in subject_config, 'expecting ground_truth_translations in subject config'
  gt_translations = subject_config['ground_truth_translations']

  fn_names = pvjs.DefinedFunctionNameExtractor.get_defined_function_names(tar_main_code)
  modified_code = tar_main_code
  for fn_name, gt_map in gt_translations.items():
    assert fn_name in fn_names, f'sanity check: function {fn_name} should be defined in tar_main_code'
    assert fn_names.count(fn_name) == 1, f'sanity check: function {fn_name} should be defined only once in tar_main_code'
    gt_fn_body = gt_map['tar']
    is_generator_fn = gt_map.get('is_generator', False)
    modified_code = pvjs.FunctionBodyReplacer.replace_function_body(
      modified_code,
      fn_name,
      gt_fn_body,
      dont_touch_inner_fn_defs=True,
      is_generator_fn=is_generator_fn,
    )

  line_map = _build_tar_line_map_from_modified_to_original(tar_main_code, modified_code, set(gt_translations.keys()))
  return modified_code, line_map


async def _run_code(
  code: str,
  lang: str,
  timeout_sec: None | int | float = 100,
  cwd: Optional[str] = None,
) -> tuple[str, str]:
  '''
  Run the code and return stdout and stderr
  '''
  assert lang in p_consts.LANG_DICT, f'Unsupported language: {lang}'
  command = CODE_RUN_COMMANDS[lang]
  temp_filename = _get_temp_filename(code, lang)
  p_utils.write_text(temp_filename, code)

  logger.debug(f'Executing command: {command} {temp_filename}')
  proc = await asyncio.create_subprocess_exec(
    command,
    temp_filename,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=cwd
  )
  try:
    async with asyncio.timeout(timeout_sec):
      # await proc.communicate() sometimes create a zombie process,
      # which probably has something to do with improper pipe cleanup
      # at in asyncio.gather.  See also
      # https://github.com/python/cpython/issues/103847
      # and relevant issues mentioned in that thread.
      stdout = (await proc._read_stream(1)).decode()
      stderr = (await proc._read_stream(2)).decode()
  except Exception as exc:
    logger.debug(f'Error executing "{command} {temp_filename}": {exc}')
    proc.kill()
    raise
  else:
    return stdout, stderr


_CACHE_RUN_SRC_TS = {}
_CACHE_RUN_SRC_TS_SIZE = 1000
_RUN_SRC_TS_CACHE_FPATH = p_consts.VALIDATION_CACHE_DIR / 'src-tests-cache.json'
_RUN_TAR_TS_CACHE_FPATH = p_consts.VALIDATION_CACHE_DIR / 'tar-tests-cache.json'
_CACHE_RUN_TAR_TS = {}
_CACHE_RUN_TAR_TS_SIZE = 1000
_CACHE_RUN_SRC_TS_LOADED = False
_CACHE_RUN_TAR_TS_LOADED = False


def _load_run_src_cache() -> None:
  global _CACHE_RUN_SRC_TS_LOADED, _CACHE_RUN_SRC_TS
  if _CACHE_RUN_SRC_TS_LOADED:
    return
  _CACHE_RUN_SRC_TS_LOADED = True
  if not _RUN_SRC_TS_CACHE_FPATH.exists():
    _CACHE_RUN_SRC_TS = {}
    return
  try:
    payload = p_utils.read_json(_RUN_SRC_TS_CACHE_FPATH)
    entries = payload.get('entries', {})
    if not isinstance(entries, dict):
      logger.warning('Unexpected run_src cache payload format; starting with empty cache.')
      _CACHE_RUN_SRC_TS = {}
      return
    _CACHE_RUN_SRC_TS = {}
    for cache_key, cached in entries.items():
      if not isinstance(cached, dict):
        continue
      timing = cached.get('timing', {})
      if not isinstance(timing, dict):
        timing = {}
      _CACHE_RUN_SRC_TS[cache_key] = {
        'src_trace': cached.get('src_trace'),
        'stderr': cached.get('stderr', ''),
        'timing': timing,
      }
    while len(_CACHE_RUN_SRC_TS) > _CACHE_RUN_SRC_TS_SIZE:
      _CACHE_RUN_SRC_TS.pop(next(iter(_CACHE_RUN_SRC_TS)))
  except Exception as err:
    logger.warning(f'Failed to load persistent run_src cache: {err}')
    _CACHE_RUN_SRC_TS = {}


def _persist_run_src_cache() -> None:
  payload_entries = {}
  for cache_key, cached in _CACHE_RUN_SRC_TS.items():
    payload_entries[cache_key] = {
      'src_trace': copy.deepcopy(cached['src_trace']),
      'stderr': cached['stderr'],
      'timing': copy.deepcopy(cached.get('timing', {})),
    }
  payload = {
    'version': 1,
    'entries': payload_entries,
  }
  try:
    _RUN_SRC_TS_CACHE_FPATH.parent.mkdir(parents=True, exist_ok=True)
    p_utils.write_json(_RUN_SRC_TS_CACHE_FPATH, payload)
  except Exception as err:
    logger.warning(f'Failed to persist run_src cache: {err}')


def _run_src_cache_make_key(
  src_lang: str,
  src_program_run: str,
) -> str:
  key_payload = {
    'src_lang': src_lang,
    'src_program_run': src_program_run,
  }
  key_json = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
  return d_utils.string_sha256(key_json)


def _run_src_cache_store(
  cache_key: str,
  src_trace: list,
  stderr: str,
  timing: dict,
) -> None:
  _load_run_src_cache()
  if cache_key in _CACHE_RUN_SRC_TS:
    _CACHE_RUN_SRC_TS.pop(cache_key)
  _CACHE_RUN_SRC_TS[cache_key] = {
    'src_trace': copy.deepcopy(src_trace),
    'stderr': stderr,
    'timing': copy.deepcopy(timing),
  }
  while len(_CACHE_RUN_SRC_TS) > _CACHE_RUN_SRC_TS_SIZE:
    _CACHE_RUN_SRC_TS.pop(next(iter(_CACHE_RUN_SRC_TS)))
  _persist_run_src_cache()


def _load_run_tar_cache() -> None:
  global _CACHE_RUN_TAR_TS_LOADED, _CACHE_RUN_TAR_TS
  if _CACHE_RUN_TAR_TS_LOADED:
    return
  _CACHE_RUN_TAR_TS_LOADED = True
  if not _RUN_TAR_TS_CACHE_FPATH.exists():
    _CACHE_RUN_TAR_TS = {}
    return
  try:
    payload = p_utils.read_json(_RUN_TAR_TS_CACHE_FPATH)
    entries = payload.get('entries', {})
    if not isinstance(entries, dict):
      logger.warning('Unexpected run_tar cache payload format; starting with empty cache.')
      _CACHE_RUN_TAR_TS = {}
      return
    _CACHE_RUN_TAR_TS = {}
    for cache_key, cached in entries.items():
      if not isinstance(cached, dict):
        continue
      tar_trace = cached.get('tar_trace')
      stderr = cached.get('stderr')
      gt_line_map_raw = cached.get('gt_line_map', {})
      mod_gt_lines_raw = cached.get('mod_gt_lines', [])
      timing = cached.get('timing', {})
      if not isinstance(gt_line_map_raw, dict):
        continue
      if not isinstance(timing, dict):
        timing = {}
      gt_line_map = {}
      for k, v in gt_line_map_raw.items():
        gt_line_map[int(k)] = int(v)
      mod_gt_lines = set(int(x) for x in mod_gt_lines_raw)
      _CACHE_RUN_TAR_TS[cache_key] = {
        'tar_trace': tar_trace,
        'stderr': stderr,
        'gt_line_map': gt_line_map,
        'mod_gt_lines': mod_gt_lines,
        'timing': timing,
      }
    while len(_CACHE_RUN_TAR_TS) > _CACHE_RUN_TAR_TS_SIZE:
      _CACHE_RUN_TAR_TS.pop(next(iter(_CACHE_RUN_TAR_TS)))
  except Exception as err:
    logger.warning(f'Failed to load persistent run_tar cache: {err}')
    _CACHE_RUN_TAR_TS = {}


def _persist_run_tar_cache() -> None:
  payload_entries = {}
  for cache_key, cached in _CACHE_RUN_TAR_TS.items():
    payload_entries[cache_key] = {
      'tar_trace': copy.deepcopy(cached['tar_trace']),
      'stderr': cached['stderr'],
      'timing': copy.deepcopy(cached.get('timing', {})),
    }
  payload = {
    'version': 1,
    'entries': payload_entries,
  }
  try:
    _RUN_TAR_TS_CACHE_FPATH.parent.mkdir(parents=True, exist_ok=True)
    p_utils.write_json(_RUN_TAR_TS_CACHE_FPATH, payload)
  except Exception as err:
    logger.warning(f'Failed to persist run_tar cache: {err}')


def _run_tar_cache_make_key(
  tar_lang: str,
  tar_program_run: str,
) -> str:
  key_payload = {
    'tar_lang': tar_lang,
    'tar_program_run': tar_program_run,
  }
  key_json = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
  return d_utils.string_sha256(key_json)


def _run_tar_cache_store(
  cache_key: str,
  tar_trace: list,
  stderr: str,
  timing: dict,
) -> None:
  _load_run_tar_cache()
  if cache_key in _CACHE_RUN_TAR_TS:
    _CACHE_RUN_TAR_TS.pop(cache_key)
  _CACHE_RUN_TAR_TS[cache_key] = {
    'tar_trace': copy.deepcopy(tar_trace),
    'stderr': stderr,
    'timing': copy.deepcopy(timing),
  }
  while len(_CACHE_RUN_TAR_TS) > _CACHE_RUN_TAR_TS_SIZE:
    _CACHE_RUN_TAR_TS.pop(next(iter(_CACHE_RUN_TAR_TS)))
  _persist_run_tar_cache()

async def run_src_test_script(
  src_program_run: str,
  subject: p_subject.PirelSubject
) -> Tuple[list, str]:
  '''
  This function runs the source program with mylog and returns the log list and error.
  PARAM src_program_run: actual code that is run to collect src trace.
  '''
  logger.debug('Running source test script')

  _load_run_src_cache()
  cache_key = _run_src_cache_make_key(subject.src_lang, src_program_run)
  if cache_key in _CACHE_RUN_SRC_TS:
    logger.debug('Cache hit: source test script found in cache')
    p_utils.log_file_time(f'{subject.name}_src_program_run.{subject.src_lang}', src_program_run)
    cached = _CACHE_RUN_SRC_TS[cache_key]
    return copy.deepcopy(cached['src_trace']), cached['stderr']

  p_utils.log_file_time(f'{subject.name}_src_program_run.{subject.src_lang}', src_program_run)
  run_stms = p_utils.current_time_msec()
  stdout, stderr = await _run_code(src_program_run, subject.src_lang)
  run_etms = p_utils.current_time_msec()
  src_trace = _extract_trace_from_stdout(stdout)
  _run_src_cache_store(cache_key, src_trace, stderr, {
    'run_stms': run_stms,
    'run_etms': run_etms,
    'run_ms': run_etms - run_stms,
    'cached_at_ms': run_etms,
  })
  return src_trace, stderr


async def run_tar_test_script(
  tar_program_run: str,
  subject: p_subject.PirelSubject,
) -> Tuple[list, str]:
  '''
  This function runs the target program until the log list mismatch
  and returns the concatenated code, log list, and error if any.
  PARAM tar_program_run: actual code that is run to collect tar trace.
  '''
  logger.debug('Running target test script')

  _load_run_tar_cache()
  cache_key = _run_tar_cache_make_key(subject.tar_lang, tar_program_run)
  if cache_key in _CACHE_RUN_TAR_TS:
    logger.debug('Cache hit: target test script found in cache')
    p_utils.log_file_time(f'{subject.name}_tar_program_run.{subject.tar_lang}', tar_program_run)
    cached = _CACHE_RUN_TAR_TS[cache_key]
    return (
      copy.deepcopy(cached['tar_trace']),
      cached['stderr'],
    )

  p_utils.log_file_time(f'{subject.name}_tar_program_run.{subject.tar_lang}', tar_program_run)
  run_stms = p_utils.current_time_msec()
  stdout, stderr = await _run_code(tar_program_run, subject.tar_lang)
  run_etms = p_utils.current_time_msec()
  tar_trace = _extract_trace_from_stdout(stdout, ignore_json_errors=(stderr != ''))
  _run_tar_cache_store(cache_key, tar_trace, stderr, {
    'run_stms': run_stms,
    'run_etms': run_etms,
    'run_ms': run_etms - run_stms,
    'cached_at_ms': run_etms,
  })

  return tar_trace, stderr
