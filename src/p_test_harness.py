import argparse
import asyncio
import json
from pathlib import Path

import d_ast_parse
import d_grammar_expand
import p_consts
import p_generator_lw
import p_pirel
import p_rule_applicator as prapp
import p_rule_inferencer
import p_rule_validator
import p_ruleset
import p_subject
import p_utils


def _get_args_dict(test_name: str) -> dict:
  config_fpath = p_consts.TMP_DIR / f'{test_name}.txt'
  if not config_fpath.exists():
    raise FileNotFoundError(f'Config file not found at {config_fpath}')
  contents = p_utils.read_text(config_fpath).strip()
  lines = contents.splitlines()
  assert len(lines) == 1, f'Expected exactly one line in config file, but got {len(lines)} lines'
  line = lines[0]
  chunks = line.split(' ')  # path should be the last chunk as in the log file
  fpath = chunks[-1].strip('"')  # remove quotes around path if present
  fpath = Path(fpath)
  assert fpath.exists(), f'Args dict file path {fpath} does not exist'
  args_dict = p_utils.read_json(fpath)
  return args_dict


def _test_generate_tsps_lightweight():
  '''
  def generate_tsps_lightweight(
    template_dict: dict
  ) -> Tuple[Tuple[str, str], dict]:
  '''
  args_dict = _get_args_dict('_test_generate_tsps_lightweight')
  template_dict = args_dict['template_dict']

  tsp, updated_template_dict = p_generator_lw.generate_tsps_lightweight(template_dict)

  data = {
    'tsps': tsp,
    'template_dict': template_dict,
    'updated_template_dict': updated_template_dict,
  }
  print(f'Updated Template Dict: \n{json.dumps(updated_template_dict, indent=2)}\n')
  print(f'Template Dict: \n{json.dumps(template_dict, indent=2)}\n')
  print(json.dumps(data) + '\n')
  print(f'Generated TSPs: \n{json.dumps(tsp, indent=2)}')


def _test_run_tests():
  '''
  async def _run_tests(
    src_program_instr: str,
    tar_program_instr: str,
    subject: p_subject.PirelSubject
  ) -> Optional[dict]:
  '''
  args_dict = _get_args_dict('_test_run_tests')
  src_program_instr = args_dict['src_program_instr']
  tar_program_instr = args_dict['tar_program_instr']
  subject = p_subject.PirelSubject.from_dict(args_dict['subject'])

  asyncio.run(prapp._run_tests(src_program_instr, tar_program_instr, subject))


def _test_apply_translation_rules():
  '''
  async def apply_translation_rules(
    subject: p_subject.PirelSubject,
    raise_on_missing_vrf_rule: bool = False,
  ) -> str:
  '''
  args_dict = _get_args_dict('_test_apply_translation_rules')
  subject = p_subject.PirelSubject.from_dict(args_dict['subject'])
  raise_on_missing_vrf_rule = args_dict['raise_on_missing_vrf_rule']

  tar_program_plausible, translate_dbg_history = asyncio.run(prapp.apply_translation_rules(
    subject,
    raise_on_missing_vrf_rule,
  ))
  print(f'Plausible target program:\n{tar_program_plausible}')


def _test_duoglot_translate_wrapper():
  '''
  def duoglot_translate_wrapper(
    src_code: str,
    src_lang: str,
    tar_lang: str,
    trans_rules: str,
    auto_backward: bool,
    choices: dict,
    **kwargs
  ) -> dict:
  '''
  args_dict = _get_args_dict('_test_duoglot_translate_wrapper')
  src_code = args_dict['src_code']
  src_lang = args_dict['src_lang']
  tar_lang = args_dict['tar_lang']
  trans_rules = args_dict['trans_rules']
  auto_backward = args_dict['auto_backward']
  choices = args_dict['choices']
  kwargs = args_dict['kwargs']

  # uncomment for debugging when necessary
  # p_utils.write_text(p_consts.SRC_DIR / 'asrc_code.py', src_code)
  # p_utils.write_text(p_consts.SRC_DIR / 'atrans_rules.snart', trans_rules)
  # p_utils.write_json(p_consts.SRC_DIR / 'achoices.json', choices)
  # src_code = p_utils.read_text(p_consts.SRC_DIR / 'asrc_code.py')
  # trans_rules = p_utils.read_text(p_consts.SRC_DIR / 'atrans_rules.snart')
  # choices = p_utils.read_json(p_consts.SRC_DIR / 'achoices.json')

  try:
    result = p_pirel.duoglot_translate_wrapper(
      src_code,
      src_lang,
      tar_lang,
      trans_rules,
      auto_backward,
      choices,
      **kwargs
    )
    # print(json.dumps(result, indent=2))
    tar_code = result['tar_code']
    dbg_history = result['dbg_history']
    map_to_exid = result['map_to_exid']

    # print(tar_code)
    # p_utils.write_text(p_consts.SRC_DIR / 'atar_code.js', tar_code)
    # p_utils.write_text(p_consts.SRC_DIR / 'adbg_history.json', json.dumps(dbg_history, indent=2))

    # highlight translation rules used at particular line number
    # import p_ext_rule_chooser
    # line_idx = 439  # 0-based
    # line_idxs_to_exid = p_ext_rule_chooser._build_line_idx_to_exids(tar_code, map_to_exid)
    # p_utils.write_text(p_consts.SRC_DIR / 'all_line_idxs.json', json.dumps(sorted(line_idxs_to_exid.keys()), indent=2))
    # exids_line = line_idxs_to_exid[line_idx]
    # rel_alt_step_infos = p_ext_rule_chooser._get_rel_alt_step_infos_from_exids(exids_line, dbg_history)
    # ruleset = p_ruleset.Ruleset.from_starting_ruleset(trans_rules)
    # for step_idx, step_info in rel_alt_step_infos.items():
    #   rule_id = step_info['current_rule_id']
    #   rule = ruleset.get_rule_by_idx(rule_id)
    #   print(rule.to_rule_str())

  except d_grammar_expand.TranslationRuleNotFoundException as exc:
    templates_dict = exc.get_templates_dict()
    print(f'Error: {exc}')
    print(f'Templates dict:\n{json.dumps(templates_dict, indent=2)}')

    # highlight the problematic node
    ast, ann = d_ast_parse.parse_text_dbg(src_code, src_lang)
    lines = src_code.splitlines()
    _, _, (strow, stcol), (enrow, encol) = ann[templates_dict['problematic_node_id']]
    if strow == enrow:
      lines.insert(strow + 1, ' ' * stcol + '^' * (encol - stcol))
      highlighted = '\n'.join(lines[strow:enrow+2])
    else:
      highlighted = '\n'.join(lines[strow:enrow+1])
    print(highlighted)
    print(f'On line number {strow + 1}')

    # uncomment for debugging when necessary
    # p_utils.write_text(p_consts.SRC_DIR / 'aast.json', json.dumps(ast, indent=2))

  except Exception as exc:
    p_utils.write_tmp_json('dbg_history.json', exc.dbg_history)
    print(f'{type(exc).__name__}: {exc}')


def _test_stat_node_validate_trules_test_based():
  '''
  async def stat_node_validate_trules_test_based(
    stat_val_subject: p_subject.PirelSubject,
    current_ruleset: p_ruleset.Ruleset,
    simple_ntext: str,
    lstat_node_val: Optional[ptlog.StatNodeVal] = None
  ) -> Tuple[str, List[dict]]:
  '''
  args_dict = _get_args_dict('_test_stat_node_validate_trules_test_based')

  stat_val_subject = p_subject.PirelSubject.from_dict(args_dict['stat_val_subject'])
  current_ruleset = p_ruleset.Ruleset.from_dict(args_dict['current_ruleset'])
  simple_ntext = args_dict['simple_ntext']

  tar_program_plausible, translate_dbg_history = asyncio.run(p_rule_validator.stat_node_validate_trules_test_based(
    stat_val_subject,
    current_ruleset,
    simple_ntext,
    None
  ))


def _test_stat_node_main_learn_validate_trules():
  '''
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
  args_dict = _get_args_dict('_test_stat_node_main_learn_validate_trules')

  main_subject = p_subject.PirelSubject.from_dict(args_dict['main_subject'])
  current_ruleset = p_ruleset.Ruleset.from_dict(args_dict['current_ruleset'])
  stat_nid = args_dict['stat_nid']
  nid_blacklist = args_dict['nid_blacklist']
  lstat_node = None
  simple_ntext_override = args_dict['simple_ntext_override']
  nid_text_overrides = args_dict['nid_text_overrides']

  asyncio.run(p_pirel.stat_node_main_learn_validate_trules(
    main_subject,
    current_ruleset,
    stat_nid,
    nid_blacklist,
    lstat_node,
    simple_ntext_override,
    nid_text_overrides,
  ))


def _test_infer_translation_rule_wrapper():
  '''
  def infer_translation_rule_wrapper(
    translation_pair: dict,
    src_lang: str,
    tar_lang: str,
    context: dict,
    is_insert_secret_fn: bool,
    choose_largest_node: bool,
    is_ignore_semicolon: bool
  ) -> str:
  '''
  args_dict = _get_args_dict('_test_infer_translation_rule_wrapper')

  translation_pair = args_dict['translation_pair']
  src_lang = args_dict['src_lang']
  tar_lang = args_dict['tar_lang']
  context = args_dict['context']
  is_insert_secret_fn = args_dict['is_insert_secret_fn']
  choose_largest_node = args_dict['choose_largest_node']
  is_ignore_semicolon = args_dict['is_ignore_semicolon']

  trule = p_rule_inferencer.infer_translation_rule_wrapper(
    translation_pair,
    src_lang,
    tar_lang,
    context,
    is_insert_secret_fn,
    choose_largest_node,
    is_ignore_semicolon
  )

  print(trule)


if __name__ == '__main__':
  dispatch_table = {
    '_test_generate_tsps_lightweight': _test_generate_tsps_lightweight,
    '_test_run_tests': _test_run_tests,
    '_test_apply_translation_rules': _test_apply_translation_rules,
    '_test_duoglot_translate_wrapper': _test_duoglot_translate_wrapper,
    '_test_stat_node_validate_trules_test_based': _test_stat_node_validate_trules_test_based,
    '_test_stat_node_main_learn_validate_trules': _test_stat_node_main_learn_validate_trules,
    '_test_infer_translation_rule_wrapper': _test_infer_translation_rule_wrapper,
  }
  argparser = argparse.ArgumentParser(description='Test harness for pirel')
  argparser.add_argument('function', type=str, help=f'Function to run. Valid options are: {list(dispatch_table.keys())}')
  args = argparser.parse_args()
  fn_name = args.function
  if fn_name not in dispatch_table:
    raise ValueError(f'Invalid function name {fn_name}. Valid options are: {list(dispatch_table.keys())}')
  dispatch_table[fn_name]()
