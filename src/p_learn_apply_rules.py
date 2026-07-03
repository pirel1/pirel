import argparse
import asyncio
import random
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Tuple

import p_code_runner
import p_consts
import p_data_structures as pds
import p_pirel
import p_ruleset
import p_rule_applicator as prapp
import p_subject
import p_tree_log as ptlog
import p_utils
import p_visitor_py as pvpy
from p_config import Config, load_configs


logger = p_utils.setup_logger(__name__)


# TaskGroup would cancel the remaining tasks in case one fails.
# With workaround <https://stackoverflow.com/questions/75250788>,
# SIGINT (Ctrl-C) has to be sent twice to stop the program though.
class ForgivingTaskGroup(asyncio.TaskGroup):
  _abort = lambda self: None


async def _run_benchmark_subject_finish(
  lsubject: ptlog.Subject,
  lbenchmark: ptlog.Benchmark,
  lock: asyncio.Lock,
  shared_cnt_fin: List[int],
) -> None:
  '''
  Called when a task for a subject finishes.
  '''

  lrule_learn_phase = lsubject.rule_learn_phase
  lrule_application_phase = lsubject.rule_application_phase

  async with lock:
    shared_cnt_fin[0] += 1

  # `L0001 1/20 7m11s: `
  subject = f'{lsubject.subject_name} {shared_cnt_fin[0]}/{lbenchmark.num_subjects} '
  message = f'{lsubject.subject_name}:\n\n'

  if lrule_learn_phase.success is True:
    assert lrule_application_phase.success in [True, False], 'sanity check'
    if lrule_application_phase.success is True:
      subject = subject + f'L-YES, A-YES'
      message = message + lrule_application_phase.tar_main_code_plausible
    else:
      subject = subject + f'L-YES, A-NO'
      message = message + lrule_application_phase.reason
  else:
    subject = subject + f'L-NO'
    message = message + lrule_learn_phase.reason

  if Config.is_email_report:
    p_utils.email_safely(subject=subject, message=message)


def _create_src_program_for_apply_phase(
  main_subject: p_subject.PirelSubject
) -> str:
  '''
  RETURN the source program to be used in the application phase.
  '''
  if not main_subject.is_three_split:
    return pvpy.LogIndexerNo3Split.index_log_statements(
      pvpy.LogInserterNo3Split.insert_log_statements(
        main_subject.src_program))
  src_main_code = main_subject.get_src_main_code()
  src_main_code = pvpy.LogStatementInserter.insert_log_statements(src_main_code)
  src_main_code = pvpy.LogStatementsIndexer.index_log_statements(src_main_code)
  src_test_code = main_subject.get_src_test_code()
  src_test_call_code = main_subject.get_src_test_call_code()
  src_program = p_consts.TEST_SCRIPT_TEMPLATE.format(
    test_code=src_test_code, main_code=src_main_code, test_call_code=src_test_call_code)
  return src_program


def _create_subject_for_apply_phase(
  main_subject: p_subject.PirelSubject,
  current_ruleset: p_ruleset.Ruleset,
) -> p_subject.PirelSubject:
  '''
  Create a PirelSubject instance for the application phase.
  '''
  logger.debug('Creating subject for application phase')
  p_utils.log_json_time('args-_create_subject_for_apply_phase.json', locals())

  # all attributes of PirelSubject instance set explicitly
  benchmark_name = main_subject.benchmark_name
  name = main_subject.name
  src_program = _create_src_program_for_apply_phase(main_subject)
  src_lang = main_subject.src_lang
  tar_lang = main_subject.tar_lang
  is_three_split = main_subject.is_three_split
  translation_rules_main_code = \
    p_utils.read_text(p_consts.LOG_STAT_RULE_FPATH) + '\n\n' + \
    current_ruleset.to_str_ruleset()  # code is instrumented
  translation_rules_test_code = main_subject.translation_rules_test_code
  auto_backward = True
  choices = main_subject.choices
  verified_choice_options = []

  # create a subject instance
  apply_phase_subject = p_subject.PirelSubject(
    benchmark_name, name, src_program, src_lang, tar_lang, is_three_split)
  apply_phase_subject.translation_rules_main_code = translation_rules_main_code
  apply_phase_subject.translation_rules_test_code = translation_rules_test_code
  apply_phase_subject.auto_backward = auto_backward
  apply_phase_subject.choices = choices
  apply_phase_subject.verified_choice_options = verified_choice_options

  # override verified_choice_options with verified rules
  apply_phase_subject.verified_choice_options = current_ruleset.get_choice_options_from_verified_rules(
    apply_phase_subject.get_src_main_code())

  return apply_phase_subject


def _post_process_tar_program_plausible(
  tar_program_plausible: str,
  subject: p_subject.PirelSubject,
) -> str:
  lines = tar_program_plausible.splitlines()
  # remove log statements and empty lines
  lines = [line for line in lines if line.strip() and not line.strip().startswith('myexactlog(')]
  tar_program_plausible = '\n'.join(lines)
  # place ground truth translations back
  tar_program_plausible, gt_line_map = p_code_runner._replace_tar_fns_with_gt_translations(
    tar_program_plausible,
    subject,
  )
  return tar_program_plausible


async def learn_and_application_phases_on_subject(
  subject: p_subject.PirelSubject,
  starting_ruleset: p_ruleset.Ruleset,
  semaphore: asyncio.Semaphore,
  lock: asyncio.Lock,
  shared_cnt_fin: List[int],
  lsubject: ptlog.Subject,
  lbenchmark: ptlog.Benchmark,
) -> Optional[p_ruleset.Ruleset]:
  '''
  Wrapper function to run both rule learning and application phases.
  RETURN validated ruleset or None on failure.
  '''
  # Override starting ruleset if exists for the subject
  subject_starting_ruleset_fpath = p_consts.TRANSLATION_RULES_DIR / f'starting-ruleset-{subject.name}.snart'
  if subject_starting_ruleset_fpath.exists():
    logger.info(f'Found overriding starting ruleset for subject "{subject.name}" at {subject_starting_ruleset_fpath}')
    starting_ruleset = p_ruleset.Ruleset.from_starting_ruleset(p_utils.read_text(subject_starting_ruleset_fpath))
  else:
    logger.info(f'No overriding starting ruleset found for subject "{subject.name}". Using default starting ruleset.')

  logger.debug(f'Starting ruleset size: {len(starting_ruleset.rules)}')

  # rule learning phase
  lrule_learn_phase = ptlog.RuleLearnPhase()
  lsubject.rule_learn_phase = lrule_learn_phase

  try:
    async with semaphore:
      logger.info('About to start rule learning phase')
      if Config.translation_order == p_consts.TranslationOrder.EOT:
        logger.debug('Using execution order translation for rule learning')
        await p_pirel.learn_trans_rules_for_subject_execution_order(
          subject,
          starting_ruleset,
          lrule_learn_phase,
        )
      else:
        raise ValueError(f'Unsupported translation order: {Config.translation_order}')

    logger.info(f'SUCCESS Rule learning phase for "{subject.name}" succeeded.')
    lrule_learn_phase.success = True
    lrule_learn_phase.etms = p_utils.current_time_msec()
    p_utils.llog_text(f'{subject.name}_learned_rules.snart', starting_ruleset.to_str_ruleset())
    p_utils.llog_json(f'{subject.name}_learned_rules.json', starting_ruleset.to_dict())
    p_utils.llog_text(f'{subject.name}_src_main_code.py', subject.get_src_main_code())
    p_utils.llog_yaml(f'{subject.name}_tree_log_learn_phase_success.yaml', asdict(lsubject))

  except Exception as exc:
    logger.critical(f'FAIL Rule learning phase for "{subject.name}" failed.')
    logger.critical(p_utils.exception_to_str(exc))
    lrule_learn_phase.success = False
    lrule_learn_phase.reason = p_utils.exception_to_str(exc)
    lrule_learn_phase.etms = p_utils.current_time_msec()
    p_utils.llog_yaml(
      f'{subject.name}_tree_log_learn_phase_fail.yaml',
      asdict(lsubject),
      include_timestamp=True,
      is_inline=True,
    )
    await _run_benchmark_subject_finish(lsubject, lbenchmark, lock, shared_cnt_fin)
    return None

  # TODO temporarily disable rule application phase
  p_utils.email_safely(f'PiREL: {subject.name} finished rule learning phase')
  return None

  # rule application phase
  lrule_application_phase = ptlog.RuleApplicationPhase()
  lsubject.rule_application_phase = lrule_application_phase
  lrule_application_phase.stms = p_utils.current_time_msec()
  try:
    async with semaphore:
      logger.info('About to start rule application phase')
      apply_subject = _create_subject_for_apply_phase(subject, starting_ruleset)
      tar_program_plausible, translate_dbg_history = \
        await prapp.apply_translation_rules(apply_subject)
      if subject.is_three_split:
        _, tar_main_code_plausible, _ = tar_program_plausible.split(p_consts.TEST_MAIN_CALL_DELIMITER)
      elif Config.translation_order == p_consts.TranslationOrder.EOT:
        tar_main_code_plausible = _post_process_tar_program_plausible(tar_program_plausible, apply_subject)
      else:
        tar_main_code_plausible = tar_program_plausible

    logger.info(f'SUCCESS Rule application phase for "{subject.name}" succeeded.')
    lrule_application_phase.tar_main_code_plausible = tar_main_code_plausible
    lrule_application_phase.success = True
    lrule_application_phase.etms = p_utils.current_time_msec()
    p_utils.llog_text(f'{subject.name}_validated_rules.snart', starting_ruleset.to_str_ruleset())
    p_utils.llog_json(f'{subject.name}_validated_rules.json', starting_ruleset.to_dict())
    p_utils.llog_text(f'{subject.name}_tar_main_code_plausible.{subject.tar_lang}', tar_main_code_plausible)
    p_utils.llog_yaml(f'{subject.name}_tree_log_apply_phase_success.yaml', asdict(lsubject))

  except Exception as exc:
    logger.critical(f'FAIL Rule application phase for "{subject.name}" failed.')
    logger.critical(p_utils.exception_to_str(exc))
    lrule_application_phase.success = False
    lrule_application_phase.reason = p_utils.exception_to_str(exc)
    lrule_application_phase.etms = p_utils.current_time_msec()
    p_utils.llog_yaml(
      f'{subject.name}_tree_log_apply_phase_fail.yaml',
      asdict(lsubject),
      include_timestamp=True,
      is_inline=True,
    )
    await _run_benchmark_subject_finish(lsubject, lbenchmark, lock, shared_cnt_fin)
    return None

  logger.info(f'SUCCESS Both learn and apply phases for "{subject.name}" succeeded.')
  await _run_benchmark_subject_finish(lsubject, lbenchmark, lock, shared_cnt_fin)
  return starting_ruleset


def _run_benchmark_init() -> Tuple[p_ruleset.Ruleset, ptlog.Benchmark, List[p_subject.PirelSubject]]:

  def _load_subjects() -> List[Tuple[str, str]]:
    '''
    RETURN a sequence of (subject_name, src_program).
    `subject_name` is a five character prefix of the program
    in the dataset for gfg, or the full name for skel.
    `src_program` is contents of the program in the benchmark
    NOTE removes comments and docstrings from src_main_code.
    '''
    assert Config.benchmark_name in p_consts.BENCHMARK_CONFIGS, \
      f'Unsupported benchmark: {Config.benchmark_name}'
    assert len(Config.subject_names) > 0, 'No subject names specified in the configuration'
    benchmark_conf = p_consts.BENCHMARK_CONFIGS[Config.benchmark_name]
    benchmark_dir = benchmark_conf['benchmark_dir']
    _get_subject_name = (lambda p: p.stem[:5]) if Config.benchmark_name == 'gfg' else (lambda p: p.stem)
    subject_fpaths : List[Path] = list(sorted(benchmark_dir.glob(f"*.{Config.src_lang}")))
    subject_fpaths = [p for p in subject_fpaths if _get_subject_name(p) in Config.subject_names]
    assert len(subject_fpaths) > 0, 'No subject files found for the specified subject names'

    dataset : List[Tuple[str, str]] = []
    for subject_fpath in subject_fpaths:
      src_program = p_utils.read_text(subject_fpath)
      if Config.is_three_split:
        src_test_code, src_main_code, src_test_call_code = src_program.split(p_consts.TEST_MAIN_CALL_DELIMITER)
        src_main_code = p_utils.remove_comments_and_docstrings_py(src_main_code)
        src_program = pvpy.PrettyPrinter.pretty_print(src_program)
        src_program = f'\n{p_consts.TEST_MAIN_CALL_DELIMITER}\n'.join([src_test_code, src_main_code, src_test_call_code])
      else:
        src_program = p_utils.remove_comments_and_docstrings_py(src_program)
        src_program = pvpy.PrettyPrinter.pretty_print(src_program)
      dataset.append((_get_subject_name(subject_fpath), src_program))
    return dataset

  def _load_starting_ruleset() -> p_ruleset.Ruleset:
    '''
    RETURN the starting ruleset for the learning phase from
    the configuration file or the default starting ruleset.
    '''
    if len(Config.overriding_rulesets) > 0:
      starting_ruleset = p_ruleset.Ruleset()
      for fpath in Config.overriding_rulesets:
        assert fpath.exists(), f'Overriding ruleset file does not exist: {fpath}'
        if fpath.suffix == '.snart':
          ruleset = p_ruleset.Ruleset.from_starting_ruleset(p_utils.read_text(fpath))
          starting_ruleset.extend(ruleset)
        elif fpath.suffix == '.json':
          ruleset = p_ruleset.Ruleset.from_dict(p_utils.read_json(fpath))
          starting_ruleset.extend(ruleset)
        else:
          raise ValueError(f'Unsupported overriding ruleset file type: {fpath}')
      return starting_ruleset
    else:
      starting_ruleset_str = p_utils.read_text(p_consts.STARTING_RULESET_FPATH)
      return p_ruleset.Ruleset.from_starting_ruleset(starting_ruleset_str)

  starting_ruleset = _load_starting_ruleset()
  subjects = _load_subjects()
  logger.info(f'Loaded {len(subjects)} subjects.')
  assert len(subjects) > 0, 'No subjects were loaded'

  lbenchmark = ptlog.Benchmark()
  lbenchmark.benchmark_name = Config.benchmark_name
  lbenchmark.num_subjects = len(subjects)

  subject_list = []
  for subject_idx, (subject_name, src_program) in enumerate(subjects, start=1):

    subject = p_subject.PirelSubject(
      benchmark_name=Config.benchmark_name,
      name=subject_name,
      src_program=src_program,
      src_lang=Config.src_lang,
      tar_lang=Config.tar_lang,
      is_three_split=Config.is_three_split,
    )

    lsubject = ptlog.Subject()
    lsubject.id = subject_idx
    lsubject.subject_name = subject.name
    lsubject.src_main_code = subject.get_src_main_code()

    subject_list.append(subject)
    lbenchmark.subjects.append(lsubject)

  return starting_ruleset, lbenchmark, subject_list


async def _run_benchmark_sequential(
  starting_ruleset: p_ruleset.Ruleset,
  subject_list: List[p_subject.PirelSubject],
  semaphore: asyncio.Semaphore,
  lock: asyncio.Lock,
  shared_cnt_fin: List[int],
  lbenchmark: ptlog.Benchmark,
) -> None:
  logger.debug('Running benchmark sequentially')
  current_ruleset = starting_ruleset
  for subject, lsubject in zip(subject_list, lbenchmark.subjects):
    async with ForgivingTaskGroup() as tg:
      coroutine = learn_and_application_phases_on_subject(
        subject, current_ruleset,
        semaphore, lock, shared_cnt_fin,
        lsubject, lbenchmark)
      task = tg.create_task(coroutine, name=subject.name)
    latest_ruleset = task.result()
    if latest_ruleset is not None and Config.reuse_translation_rules:
      logger.info('Reusing learned translation rules for the next subject')
      current_ruleset = latest_ruleset


async def _run_benchmark_concurrent(
  starting_ruleset: p_ruleset.Ruleset,
  subject_list: List[p_subject.PirelSubject],
  semaphore: asyncio.Semaphore,
  lock: asyncio.Lock,
  shared_cnt_fin: List[int],
  lbenchmark: ptlog.Benchmark,
) -> None:
  logger.debug('Running benchmark concurrently')
  async with ForgivingTaskGroup() as tg:
    for subject, lsubject in zip(subject_list, lbenchmark.subjects):
      coroutine = learn_and_application_phases_on_subject(
        subject, starting_ruleset,
        semaphore, lock, shared_cnt_fin,
        lsubject, lbenchmark)
      tg.create_task(coroutine, name=subject.name)


async def run_benchmark() -> None:
  '''
  Run PiREL to learn and apply translation rules for a given benchmark.
  '''
  starting_ruleset, lbenchmark, subject_list = _run_benchmark_init()
  num_concurrent_subjects = min(lbenchmark.num_subjects, Config.max_concurrent_subjects)
  semaphore = asyncio.Semaphore(num_concurrent_subjects)
  lock = asyncio.Lock()
  shared_cnt_fin = [0]

  if Config.max_concurrent_subjects == 1:
    await _run_benchmark_sequential(
      starting_ruleset, subject_list,
      semaphore, lock, shared_cnt_fin, lbenchmark)
  else:
    await _run_benchmark_concurrent(
      starting_ruleset, subject_list,
      semaphore, lock, shared_cnt_fin, lbenchmark)


def get_args() -> argparse.Namespace:
  '''
  NOTE perform sanity checks on the new arguments.
  '''
  def _resolve_overriding_ruleset_path(path_str: str) -> Path:
    raw_path = Path(path_str)
    if raw_path.is_absolute():
      return raw_path
    candidates = [
      p_utils.make_abs(path_str, p_consts.ROOT_DIR),
      p_consts.RULESET_CHECKPOINTS_DIR / path_str,
    ]
    for candidate in candidates:
      if candidate.exists():
        return candidate
    return candidates[0]

  argparser = argparse.ArgumentParser()

  argparser.add_argument('--benchmark-name', '-b',
                         choices={'gfg', 'skel'},
                         default='skel',
                         required=False,
                         help=('Name of the benchmark to run '
                         '(DEFAULT: skel)'))

  argparser.add_argument('--subject-names', '-s',
                         required=True,
                         nargs='+',
                         type=str,
                         dest='arg_subject_names',
                         metavar='SUBJECT_NAME',
                         help=('Subject names to process. For gfg, use '
                              'five character prefixes. '
                              'For skel, use full names.'))

  argparser.add_argument('--src-lang',
                         choices={'py'},
                         default='py',
                         help='Source programming language (DEFAULT: py)')

  argparser.add_argument('--tar-lang',
                         choices={'js'},
                         default='js',
                         help='Target programming language (DEFAULT: js)')

  argparser.add_argument('--is-three-split',
                         action='store_true',
                         help=('Whether the benchmark uses three-split'
                               ' (test, main, test_call) programs'
                               ' (DEFAULT: False). Three-split is supported '
                               'only for gfg benchmark.'))

  argparser.add_argument('--translation-order',
                         type=str,
                         default=p_consts.TranslationOrder.EOT,
                         choices=[p_consts.TranslationOrder.EOT],
                         help=('Order of source code translation. Execution Order Translation (SKEL)'
                               f'(DEFAULT: {p_consts.TranslationOrder.EOT}).'))

  argparser.add_argument('--overriding-rulesets',
                         default=[],
                         nargs='+',
                         metavar='PATH',
                         help=('Relative path(s) to overriding rulesets.'
                               ' Overrides the default starting ruleset'
                               f' Checkpoints are saved under'
                               f' "{p_consts.RULESET_CHECKPOINTS_DIR.relative_to(p_consts.ROOT_DIR)}".'
                               ' (DEFAULT: empty list)'))

  argparser.add_argument('--max-concurrent-subjects',
                         default=p_consts.MAX_CONCURRENT_SUBJECTS,
                         type=int,
                         metavar='N',
                         help=('Maximum number of subjects to run concurrently. '
                               'Set to 1 to run sequentially. '
                               f' (DEFAULT: {p_consts.MAX_CONCURRENT_SUBJECTS})'))

  argparser.add_argument('--reuse-translation-rules',
                         action='store_true',
                         help=('Whether to reuse the learned translation rules'
                               ' from previous subjects. Works only'
                               ' with `--max-concurrent-subjects 1`.'
                               ' (DEFAULT: False)'))

  argparser.add_argument('--is-email-report', '--email', '-e',
                         action='store_true',
                         help=('Whether to email the report after '
                               ' each subject finishes (DEFAULT: False)'))

  argparser.add_argument('--openai-model-name', '--model', '-m',
                         choices=[p_consts.OpenAIModelNames.GPT5_NANO,
                                  p_consts.OpenAIModelNames.GPT5],
                         default=p_consts.OpenAIModelNames.GPT5_NANO,
                         type=str,
                         help=('OpenAI model name to use (DEFAULT: '
                               f'{p_consts.OpenAIModelNames.GPT5_NANO})'))

  argparser.add_argument('--use-reduced-prompts', '-r',
                         action='store_true',
                         help=('Whether to use reduced prompts to be more '
                               'economical with token usage (DEFAULT: False)'))

  argparser.add_argument('--generator',
                         choices=['lightweight', 'default'],
                         default='lightweight',
                         type=str,
                         help=('Snippet generator to use (DEFAULT: lightweight)'))

  args = argparser.parse_args()

  # benchmark_name
  assert args.benchmark_name in ['gfg', 'skel'], f'Unsupported benchmark: {args.benchmark_name}'

  # arg_subject_names
  assert isinstance(args.arg_subject_names, list) and len(args.arg_subject_names) > 0, f'subject_names must be a non-empty list'
  for subject_name in args.arg_subject_names:
    assert isinstance(subject_name, str) and len(subject_name) > 0, f'Each subject_name must be a non-empty string'

  # src_lang, tar_lang
  assert args.src_lang in ['py'], f'Unsupported source language: {args.src_lang}'
  assert args.tar_lang in ['js'], f'Unsupported target language: {args.tar_lang}'

  # is_three_split
  assert isinstance(args.is_three_split, bool), f'is_three_split must be boolean'
  if args.is_three_split:
    assert args.benchmark_name == 'gfg', f'Three-split is supported only for gfg benchmark'

  # translation_order
  assert args.translation_order in [p_consts.TranslationOrder.EOT], \
    f'Unsupported translation_order: {args.translation_order}'

  # overriding_rulesets
  assert isinstance(args.overriding_rulesets, list), f'overriding_rulesets must be a list'
  args.overriding_rulesets = [_resolve_overriding_ruleset_path(p) for p in args.overriding_rulesets]

  # max_concurrent_subjects, reuse_translation_rules
  assert isinstance(args.max_concurrent_subjects, int) and args.max_concurrent_subjects > 0, \
    f'max_concurrent_subjects must be a positive integer'
  assert isinstance(args.reuse_translation_rules, bool), f'reuse_translation_rules must be boolean'
  if args.reuse_translation_rules:
    assert args.max_concurrent_subjects == 1, \
      f'When reuse_translation_rules is set, max_concurrent_subjects must be 1'

  # is_email_report
  assert isinstance(args.is_email_report, bool), f'is_email_report must be boolean'

  # openai_model_name
  assert args.openai_model_name in [
    p_consts.OpenAIModelNames.GPT5_NANO,
    p_consts.OpenAIModelNames.GPT5,
  ], f'Unsupported openai_model_name: {args.openai_model_name}'

  # use_reduced_prompts
  assert isinstance(args.use_reduced_prompts, bool), f'use_reduced_prompts must be boolean'

  # generator
  assert args.generator in ['lightweight', 'default'], f'Unsupported generator: {args.generator}'

  return args


def main():
  args = get_args()
  load_configs(args)

  try:
    asyncio.run(run_benchmark())
  except Exception as exc:
    p_utils.email_safely(subject='SCRIPT ERROR', message=p_utils.exception_to_str(exc))
    raise


if __name__ == '__main__':
  main()
