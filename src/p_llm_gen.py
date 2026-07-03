'''
This module is an attempt to generate translation rules statefully.

Class diagram
                                        BasePirelTask
                                              │    │
                                              │    │
                                              │    │
                                              │    │
                                              │    │
                                              │    │
                                              ▼    └──────────────────────►
                                       BaseTranslateSP1Task         BaseTranslateSP2Task
                                          │  │                            │     │
                                          │  │                            │     │
                                          │  │                            │     │
                                          │  │                            │     │
                                          │  │                            │     │
                                          │  │                            │     │
               ◄──────────────────────────┘  ▼                            ▼     └──────────────►
      SP1_DirectTransG            SP1_PartialProgramG            SP2_DirectTransG        SP2_PartialProgramG

NOTE on adding a new task class:
1. Create a main task class inheriting from `BasePirelTask`
   - add your own attributes alongside attributes of superclass
   - implement all abstract methods
2. Create prompt templates in `p_llm_templates` module
3. Create a validation result class in `p_llm_val` module.
   - create a subclass of `BaseValidationResult`
4. Create validation functions in `p_llm_val` module.
5. Create a feedback message factory in `p_llm_messages` module.
'''


import asyncio
import copy
import functools
import hashlib
import json
import re
from abc import ABC, abstractmethod
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.base import BaseMessage
from langchain_core.messages.human import HumanMessage
from langchain_core.messages.system import SystemMessage
from langchain_core.prompts.chat import HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_openai import ChatOpenAI
from openai import APIError as OpenAIAPIError
from typing import Any, Dict, List, Optional, Tuple, Union

import d_ast_parse
import d_utils
import p_consts
import p_data_structures as pds
import p_llm_messages
import p_llm_templates
import p_llm_val
import p_subject
import p_tree_log as ptlog
import p_utils
import p_visitor as pvis
import p_visitor_js as pvjs
import p_visitor_py as pvpy
from p_config import Config


logger = p_utils.setup_logger(__name__)


# ERROR CLASSES
class SP1TranslationRetryLimitError(RuntimeError): pass
class SP2TranslationRetryLimitError(RuntimeError): pass
class NoTransPairsFromTSPError(RuntimeError): pass
class OpenAIErrors(ExceptionGroup): pass
class GetRefTransRetryLimitError(RuntimeError): pass


class BasePirelTask(ABC):
  '''
  Base class for PiREL LLM tasks.

  NOTE on `chat_history`:
  Starting messages
  - system message
  - few shot messages
  - starting prompt message
  Starting response
  - starting response
  Iteration 1
  - feedback 1
  - response 1
  ...
  Iteration N
  - feedback N
  - response N

  NOTE subclasses must have a corresponding adapter `BaseValidationResult` class.
  '''

  # error class for internal use
  class _TaskIterationFinishedError(RuntimeError): pass

  def __init__(
    self,
    task_name: str,
    subject: p_subject.PirelSubject,
    template_dict: dict,
    lbase_task: ptlog.BaseTask
  ):
    self.task_name : str = task_name
    self.subject = subject
    self.template_dict = template_dict

    self.chat_history : List[BaseMessage] = []
    self.code_blocks_history : List[List[str]] = []
    self.feedback_iteration_counter = 1
    self.task_iteration_counter = 1
    self.model_params = {}
    self._log(f'creating an in instance of "{task_name}"')

    # creating an attribute in PLLMGenLog
    self.ltask_loop = ptlog.TaskLoop()
    self.ltask_loop.task_name = task_name
    lbase_task.task_loop = self.ltask_loop

    # stats
    self.llm_query_stats: List[Dict[str, Any]] = []

  def __repr__(self) -> str:
    return self.__class__.__name__

  # TASK LOOP
  async def run(self) -> Any:
    '''
    Entry point. Not intended to be overridden.
    '''
    assert self.task_iteration_counter == 1, 'state error: task iteration counter'

    self._log('BasePirelTask.run: initializing the task')
    self.run_init()

    self._log('BasePirelTask.run: starting the task loop')
    while self.does_require_task_iteration():

      ltask_iteration = ptlog.TaskIteration()
      ltask_iteration.id = self.task_iteration_counter
      self.ltask_loop.task_iterations.append(ltask_iteration)

      try:
        self._log(f'BasePirelTask.run: task loop (iteration #{self.task_iteration_counter})')
        data = await self._run_task_once(ltask_iteration)

        self._log(f'BasePirelTask.run: SUCCESS task run successful. Ending.')
        self.ltask_loop.success = True
        return data

      except BasePirelTask._TaskIterationFinishedError:
        self._log('BasePirelTask.run: WARNING task run failed. Trying one more time.')
        ltask_iteration.reason = 'BasePirelTask._TaskIterationFinishedError'
        self.task_iteration_counter += 1

      except p_llm_messages.FeedbackImpossibleError as err:
        self._log(f'BasePirelTask.run: WARNING task run failed due to "{str(err)}"')
        self._log('Trying one more time.')
        ltask_iteration.reason = 'p_llm_messages.FeedbackImpossibleError'
        self.task_iteration_counter += 1

    self._log('BasePirelTask.run: FAIL task failed. Ending.')
    self.ltask_loop.success = False
    self.ltask_loop.reason = 'Failed this task for given number of iterations'
    self.run_failed()

  def run_init(self) -> None:
    '''Invoked before starting the task. Can be overridden by subclasses'''

  # TASK ITERATION
  async def _run_task_once(self, ltask_iteration: ptlog.TaskIteration) -> Any:
    '''
    A single iteration of a task.
    RETURN refer to `BaseValidationResult` and its subclasses.

    NOTE prompts always ask for code blocks, thus we extract code blocks from raw response
    '''

    self._log(f'_run_task_once: initializing task iteration #{self.task_iteration_counter}')
    self.run_task_once_init()

    # reset state
    self._log('_run_task_once: resetting the state')
    self.chat_history.clear()
    self.code_blocks_history.clear()
    self.feedback_iteration_counter = 1

    # starting prompt and response
    self._log(f'_run_task_once: starting prompt and response')
    starting_messages = self._create_starting_messages()
    self.chat_history.extend(starting_messages)
    starting_raw_response = await self._query_llm()
    self.chat_history.append(AIMessage(starting_raw_response))
    starting_code_blocks = self._extract_code_blocks(starting_raw_response)
    ltask_iteration.starting_code_blocks = starting_code_blocks
    self.code_blocks_history.append(starting_code_blocks)

    # validate starting code blocks
    validation_result = self._validate_code_blocks()
    if validation_result.is_successful():
      self._log('_run_task_once: SUCCESS validation is successful. Returning the validation result')
      ltask_iteration.success = True
      return validation_result.get_data()

    # FEEDBACK LOOP
    self._log('_run_task_once: First prompt and response are not valid. Starting the feedback loop')
    while self.does_require_feedback_iteration():

      self._log(f'_run_task_once: feedback loop (run #{self.task_iteration_counter}) (iteration #{self.feedback_iteration_counter})')
      self.run_task_once_feedback_init()

      lfeedback = ptlog.Feedback()
      lfeedback.id = self.feedback_iteration_counter
      ltask_iteration.feedbacks.append(lfeedback)

      # feedback prompt and response
      self._log('_run_task_once: generating a feedback message')
      feedback_message = self.get_feedback_message(validation_result)
      self.chat_history.append(feedback_message)
      feedback_raw_response = await self._query_llm()
      self.chat_history.append(AIMessage(feedback_raw_response))
      feedback_code_blocks = self._extract_code_blocks(feedback_raw_response)
      lfeedback.code_blocks = feedback_code_blocks
      self.code_blocks_history.append(feedback_code_blocks)

      # validate code blocks
      validation_result = self._validate_code_blocks()
      if validation_result.is_successful():
        self._log('_run_task_once: SUCCESS validation is successful. Returning the validation result')
        ltask_iteration.success = True
        lfeedback.success = True
        return validation_result.get_data()

      self._log('_run_task_once: WARNING feedback loop unsuccessful. trying one more time.')
      self.feedback_iteration_counter += 1
      lfeedback.success = False
      lfeedback.reason = 'Code blocks are not valid'
      self.run_task_once_feedback_failed()

    self._log(f'_run_task_once: FAIL task iteration failure #{self.task_iteration_counter}')
    raise BasePirelTask._TaskIterationFinishedError

  def run_task_once_init(self) -> None:
    '''Invoked before starting the task iteration. Can be overridden by subclasses'''

  def run_task_once_feedback_init(self) -> None:
    '''Invoked before starting feedback iteration. Can be overridden by subclasses'''

  def run_task_once_feedback_failed(self) -> None:
    '''Invoked at the end of feedback iteration. Can be overridden by subclasses'''

  # METHODS FOR INTERNAL USE
  def _create_starting_messages(self) -> List[BaseMessage]:
    '''Create a list of starting messages for initial query of a task'''
    self._log('creating starting messages')
    starting_messages = []
    starting_messages.append(self.get_system_message())
    starting_messages.extend(self.get_few_shot_messages())
    starting_messages.append(self.get_starting_prompt_message())
    return starting_messages

  async def _query_llm(self) -> str:
    assert self.chat_history[-1].type == 'human', 'chat history must end with a human prompt'
    self._log_file(langchain_msgs_to_md(self.chat_history), f'llm-messages.md')
    raw_response, query_stats = await query_llm(self.chat_history, **self.model_params)
    self.llm_query_stats.append(query_stats)
    self._log_file(raw_response, f'llm-raw-response.md')
    return raw_response

  def _extract_code_blocks(self, raw_response: str) -> List[str]:
    code_blocks = extract_code_blocks(raw_response)
    self._log_json(code_blocks, f'gen-code-blocks.json')
    logger.debug(f'generated code blocks:\n{json.dumps(code_blocks, indent=2)}')
    return code_blocks

  def _validate_code_blocks(self) -> p_llm_val.BaseValidationResult:
    self._log('validating the generated code blocks by p_llm_val module')
    validation_result = self.validate_code_blocks()
    self._log_json(validation_result.get_val_result(), f'val-result.json')
    return validation_result

  def _log_json(self, data: Union[list, dict], fname: str) -> None:
    p_utils.log_json_time(f'{self.subject.name}_{self.task_name}_{fname}', data)

  def _log_file(self, text: str, fname: str) -> None:
    p_utils.log_file_time(f'{self.subject.name}_{self.task_name}_{fname}', text)

  def _log(self, msg: str) -> None:
    logger.debug(f'{self.task_name}: {msg}')

  # HELPER METHODS
  def get_all_gen_code_blocks(self) -> List[str]:
    '''Return all previously generated code blocks'''
    all_code_blocks = []
    for code_blocks_history_elem in self.code_blocks_history:
      all_code_blocks.extend(code_blocks_history_elem)
    return all_code_blocks

  def log_args_as_json(self, fname: str, **kwargs) -> None:
    self._log_json(kwargs, fname)

  # ABSTRACT METHODS
  @abstractmethod
  def run_failed(self) -> None:
    '''Invoken when the task fails'''

  @abstractmethod
  def get_system_message(self) -> BaseMessage:
    '''Return system message for a task'''

  @abstractmethod
  def get_few_shot_messages(self) -> List[BaseMessage]:
    '''Return few shot messages (golden conversation) for a task'''

  @abstractmethod
  def get_starting_prompt_message(self) -> HumanMessage:
    '''Return the first prompt to start the chat'''

  @abstractmethod
  def get_feedback_message(self, validation_result: p_llm_val.BaseValidationResult) -> HumanMessage:
    '''
    Return a feedback message based on the generated code blocks and validation result.
    This method is generally invoked only when the previous response (or all previous responses) is not valid.
    '''

  @abstractmethod
  def validate_code_blocks(self) -> p_llm_val.BaseValidationResult:
    '''Validation is currently performed with `p_llm_val` module'''

  @abstractmethod
  def does_require_feedback_iteration(self) -> bool:
    '''Return True if need to run one more feedback-response iteration'''

  @abstractmethod
  def does_require_task_iteration(self) -> bool:
    '''Return True if need to run one more task iteration'''


# TRANSLATE SP1
class BaseTranslateSP1Task(BasePirelTask):
  '''
  Simple algorithm for translating SP1.
  `self.run` returns list of program pairs.
  '''

  def __init__(
    self,
    task_name: str,
    subject: p_subject.PirelSubject,
    template_dict: dict,
    sp1: str,
    lbase_task: ptlog.BaseTask
  ):
    super().__init__(task_name, subject, template_dict, lbase_task)
    self.sp1 = sp1

  def get_system_message(self) -> BaseMessage:
    system_message = SystemMessage(p_llm_templates.TemplateManager().render(
      'system.j2',
      src_language = p_consts.LANG_DICT[self.subject.src_lang],
      tar_language = p_consts.LANG_DICT[self.subject.tar_lang],
      use_reduced_prompts = Config.use_reduced_prompts
    ))
    return system_message

  def get_few_shot_messages(self) -> List[BaseMessage]:
    return []

  def get_starting_prompt_message(self) -> HumanMessage:
    raise NotImplementedError('This method should be implemented in subclass')

  def validate_code_blocks(self) -> p_llm_val.TranslateSP1ValidationResult:
    self._log('starting tp1 candidates validation')
    all_tp1_cands = self.get_all_gen_code_blocks()
    val_result_obj = p_llm_val.val_tp1_candidates(all_tp1_cands, self.sp1, self.template_dict)
    return val_result_obj

  def does_require_feedback_iteration(self) -> bool:
    return self.feedback_iteration_counter <= p_consts.TRANSLATION_SP1_MAX_FEEDBACKS

  def does_require_task_iteration(self) -> bool:
    return self.task_iteration_counter <= p_consts.TRANSLATION_SP1_MAX_RETRIES

  def run_failed(self) -> None:
    msg = f'Could not translate SP1. Reached retry limit. Check the logs.'
    self._log(f'ERROR {msg}')
    raise SP1TranslationRetryLimitError(msg)

  @classmethod
  def dispatch(
    self,
    subject: p_subject.PirelSubject,
    template_dict: dict,
    sp1: str,
    lbase_task: ptlog.BaseTask
  ) -> 'BaseTranslateSP1Task':
    '''
    Based on the values of the arguments provided, choose the right translator subclass
    '''
    logger.debug('~~~ BaseTranslateSP1Task.dispatch: starting')
    logger.debug(f'BaseTranslateSP1Task.dispatch: Translating SP1:\n{repr(sp1)}')

    if _is_context_empty(template_dict):
      logger.debug('BaseTranslateSP1Task.dispatch: Context is empty. Will use direct translation of SP1.')
      task_obj = SP1_DirectTransG('tr_sp1_dir_tr', subject, template_dict, sp1, lbase_task)

    else:
      logger.debug('BaseTranslateSP1Task.dispatch: Context is not empty. Will use partial translation of SP1.')
      task_obj = SP1_PartialProgramG('tr_sp1_par_pr', subject, template_dict, sp1, lbase_task)

    logger.debug(f'BaseTranslateSP1Task.dispatch: returning task object "{repr(task_obj)}"')
    return task_obj


class SP1_DirectTransG(BaseTranslateSP1Task):
  '''
  Ask for translation directly.
  '''
  def get_feedback_message(self, validation_result: p_llm_val.TranslateSP1ValidationResult) -> HumanMessage:
    self._log('initiating a feedback message factory')
    factory = p_llm_messages.SP1_DirectTransF(self.template_dict, self.subject, validation_result)
    feedback_message = factory.get_feedback_message()
    return feedback_message

  def get_starting_prompt_message(self) -> HumanMessage:
    use_constraint_trans_assignment_declare_first = False
    use_constraint_trans_assignment_declare_second = False
    if '=' in self.sp1:
      if self.subject.name in p_consts.SUBJECT_NAMES_ASSIGN_DECLARE_FIRST:
        logger.debug('SP1_DirectTransG.get_starting_prompt_message: assignment with declaration first')
        use_constraint_trans_assignment_declare_first = True
        use_constraint_trans_assignment_declare_second = False
      else:
        logger.debug('SP1_DirectTransG.get_starting_prompt_message: assignment without declaration first')
        use_constraint_trans_assignment_declare_first = False
        use_constraint_trans_assignment_declare_second = True

    starting_prompt = HumanMessage(p_llm_templates.TemplateManager().render(
      'trans-sp1-direct.j2',
      src_language = p_consts.LANG_DICT[self.subject.src_lang],
      tar_language = p_consts.LANG_DICT[self.subject.tar_lang],
      program_to_translate = self.sp1,
      use_reduced_prompts = Config.use_reduced_prompts,
      use_constraint_trans_assignment_declare_second = use_constraint_trans_assignment_declare_second,
      use_constraint_trans_assignment_declare_first = use_constraint_trans_assignment_declare_first,
      use_constraint_trans_equals_op = '==' in self.sp1,
      use_constraint_trans_modulus_op = '%' in self.sp1,
      use_constraint_trans_comp_stat = any(tok in self.sp1 for tok in ['if', 'while', 'for', 'try', 'with']),
      use_constraint_trans_array_sort = '.sort(' in self.sp1,
      use_constraint_trans_raise_statement = 'raise ' in self.sp1,
      use_constraint_trans_multiline_strings = '"""' in self.sp1 or "'''" in self.sp1,
      use_constraint_trans_for_enumerate = re.search(r'\bfor\b.*\benumerate\b', self.sp1) is not None,
    ))
    return starting_prompt


class SP1_PartialProgramG(BaseTranslateSP1Task):
  '''
  Translate a portion of a larger program.
  '''
  def get_starting_prompt_message(self) -> HumanMessage:
    src_lang = self.subject.src_lang
    tar_lang = self.subject.tar_lang
    problematic_node_path = self.template_dict['problematic_node_path']
    partial_program = self.template_dict['partial_program']
    src_snippet_to_translate = _extract_snippet(self.sp1, src_lang, problematic_node_path)

    starting_prompt = HumanMessage(p_llm_templates.TemplateManager().render(
      'trans-sp1-partial.j2',
      src_language = p_consts.LANG_DICT[src_lang],
      src_snippet_to_translate = src_snippet_to_translate,
      src_snippet_context = self.sp1,
      tar_language = p_consts.LANG_DICT[tar_lang],
      tar_partial_program = partial_program,
      variable_to_replace = p_consts.PAR_PROG_PROB_NODE_REPLACE,
      use_reduced_prompts = Config.use_reduced_prompts,
      use_constraint_trans_equals_op = '==' in src_snippet_to_translate,
      use_constraint_trans_modulus_op = '%' in src_snippet_to_translate,
      use_constraint_keep_parentheses = '(' in src_snippet_to_translate and ')' in src_snippet_to_translate,
      use_constraint_trans_multiline_strings = '"""' in src_snippet_to_translate or "'''" in src_snippet_to_translate,
      use_constraint_trans_for_enumerate = re.search(r'\bfor\b.*\benumerate\b', src_snippet_to_translate) is not None,
    ))
    return starting_prompt

  def get_feedback_message(self, validation_result: p_llm_val.TranslateSP1ValidationResult) -> HumanMessage:
    self._log('initiating a feedback message factory')
    factory = p_llm_messages.SP1_PartialProgramF(self.template_dict, self.subject, validation_result)
    feedback_message = factory.get_feedback_message()
    return feedback_message


# TRANSLATE SP2
class BaseTranslateSP2Task(BasePirelTask):
  '''
  Simple algorithm for translating SP2.
  `self.run` returns list of program pairs.
  '''

  def __init__(
    self,
    task_name: str,
    subject: p_subject.PirelSubject,
    template_dict: dict,
    sp1_tp1_cand: dict,
    sp2: str,
    lbase_task: ptlog.BaseTask
  ):
    '''
    PARAM sp1_tp1_cand: (sp1_i, tp1_i_j)
    '''
    super().__init__(task_name, subject, template_dict, lbase_task)
    self.sp1 = sp1_tp1_cand['source']
    self.tp1_cand = sp1_tp1_cand['target']
    self.sp2 = sp2

  def get_system_message(self) -> BaseMessage:
    system_message = SystemMessagePromptTemplate.from_template(
      p_llm_templates.TranslateAny.System.REDUCED
      if Config.use_reduced_prompts else
      p_llm_templates.TranslateAny.System.DEFAULT
    ).format(
      src_language = p_consts.LANG_DICT[self.subject.src_lang],
      tar_language = p_consts.LANG_DICT[self.subject.tar_lang],
    )
    return system_message

  def get_few_shot_messages(self) -> List[BaseMessage]:
    return []

  def get_starting_prompt_message(self) -> HumanMessage:
    starting_prompt = HumanMessagePromptTemplate.from_template(
      p_llm_templates.TranslateAny.Prompt.DIRECT_TRANS_REDUCED
      if Config.use_reduced_prompts else
      p_llm_templates.TranslateAny.Prompt.DIRECT_TRANS
    ).format(
      src_language = p_consts.LANG_DICT[self.subject.src_lang],
      tar_language = p_consts.LANG_DICT[self.subject.tar_lang],
      program_to_translate = self.sp2
    )
    return starting_prompt

  def validate_code_blocks(self) -> p_llm_val.TranslateSP2ValidationResult:
    self._log('starting tp2 candidates validation')
    all_tp2_cands = self.get_all_gen_code_blocks()
    val_result_obj = p_llm_val.val_tp2_candidates(all_tp2_cands, self.sp1, self.sp2, self.tp1_cand, self.template_dict)
    return val_result_obj

  def does_require_feedback_iteration(self) -> bool:
    return self.feedback_iteration_counter <= p_consts.TRANSLATION_SP2_MAX_FEEDBACKS

  def does_require_task_iteration(self) -> bool:
    return self.task_iteration_counter <= p_consts.TRANSLATION_SP2_MAX_RETRIES

  def run_failed(self) -> None:
    msg = f'Could not translate SP2. Reached retry limit. Check the logs.'
    self._log(f'ERROR {msg}')
    raise SP2TranslationRetryLimitError(msg)

  @classmethod
  def dispatch(
    self,
    subject: p_subject.PirelSubject,
    template_dict: dict,
    sp1_tp1_cand: dict,
    sp2: str,
    lbase_task: ptlog.BaseTask
  ) -> 'BaseTranslateSP1Task':
    '''
    Based on the values of the arguments provided, choose the right subclass (translator)
    '''
    logger.debug('~~~ BaseTranslateSP2Task.dispatch: starting')
    logger.debug(f'BaseTranslateSP2Task.dispatch: Translating SP2:\n{repr(sp2)}')
    logger.debug(f'BaseTranslateSP2Task.dispatch: SP1-TP1-cand:\n{json.dumps(sp1_tp1_cand, indent=2)}')

    if _is_context_empty(template_dict):
      logger.debug('BaseTranslateSP2Task.dispatch: Context is empty. Will use direct translation of SP2 (similar to SP1).')
      task_obj = SP2_DirectTransG('tr_sp2_dir_tr', subject, template_dict, sp1_tp1_cand, sp2, lbase_task)

    else:
      logger.debug('BaseTranslateSP2Task.dispatch: Context is not empty. Will use partial translation of SP2 (similar to SP1).')
      task_obj = SP2_PartialProgramG('tr_sp2_par_pr', subject, template_dict, sp1_tp1_cand, sp2, lbase_task)

    logger.debug(f'BaseTranslateSP2Task.dispatch: returning task object "{repr(task_obj)}"')
    return task_obj


class SP2_DirectTransG(BaseTranslateSP2Task):
  '''
  Ask for translation directly, but provide a reference translation (sp1 -> tp1_cand)
  '''
  def get_starting_prompt_message(self) -> HumanMessage:
    src_lang = self.subject.src_lang
    tar_lang = self.subject.tar_lang

    starting_prompt = HumanMessagePromptTemplate.from_template(
      p_llm_templates.TranslateSP2.Prompt.DIRECT_TRANS_SIMILAR
    ).format(
      src_language=p_consts.LANG_DICT[src_lang],
      sp1=self.sp1,
      tar_language=p_consts.LANG_DICT[tar_lang],
      tp1_cand=self.tp1_cand,
      sp2=self.sp2
    )
    return starting_prompt

  def get_feedback_message(self, validation_result: p_llm_val.TranslateSP2ValidationResult) -> HumanMessage:
    self._log('initiating a feedback message factory')
    factory = p_llm_messages.SP2_DirectTransF(self.template_dict, self.subject, validation_result)
    feedback_message = factory.get_feedback_message()
    return feedback_message


class SP2_PartialProgramG(BaseTranslateSP2Task):
  '''
  Ask for translation of a portion of a larger program, provide a reference translation (sp1 -> tp1_cand)
  '''
  def get_starting_prompt_message(self) -> HumanMessage:
    src_lang = self.subject.src_lang
    tar_lang = self.subject.tar_lang
    problematic_node_path = self.template_dict['problematic_node_path']
    partial_program = self.template_dict['partial_program']

    src_snippet_to_translate = _extract_snippet(self.sp2, src_lang, problematic_node_path)

    starting_prompt = HumanMessagePromptTemplate.from_template(
      p_llm_templates.TranslateSP2.Prompt.PARTIAL_PROGRAM_SIMILAR
    ).format(
      src_language=p_consts.LANG_DICT[src_lang],
      snippet_to_translate_sp2=src_snippet_to_translate,
      snippet_context_sp2=self.sp2,
      tar_language=p_consts.LANG_DICT[tar_lang],
      partial_program=partial_program,
      variable_to_replace=p_consts.PAR_PROG_PROB_NODE_REPLACE,
      tp1_cand=self.tp1_cand,
      sp1=self.sp1,
    )
    return starting_prompt

  def get_feedback_message(self, validation_result: p_llm_val.TranslateSP2ValidationResult) -> HumanMessage:
    self._log('initiating a feedback message factory')
    factory = p_llm_messages.SP2_PartialProgramF(self.template_dict, self.subject, validation_result)
    feedback_message = factory.get_feedback_message()
    return feedback_message


# GET REFERENCE TRANSLATION
class GetReferenceTranslation(BasePirelTask):
  '''
  Get a reference translation for a statement node
  '''
  def __init__(
    self,
    task_name: str,
    statement_str: str,
    subject: p_subject.PirelSubject,
    template_dict: dict,
    lbase_task: ptlog.BaseTask,
  ):
    super().__init__(task_name, subject, template_dict, lbase_task)
    self.statement_str = statement_str

  def get_system_message(self) -> BaseMessage:
    system_message = SystemMessage(p_llm_templates.TemplateManager().render(
      'system.j2',
      src_language = p_consts.LANG_DICT[self.subject.src_lang],
      tar_language = p_consts.LANG_DICT[self.subject.tar_lang],
      use_reduced_prompts = Config.use_reduced_prompts
    ))
    return system_message

  def get_few_shot_messages(self) -> List[BaseMessage]:
    return []

  def get_starting_prompt_message(self) -> HumanMessage:
    use_constraint_trans_assignment_declare_first = False
    use_constraint_trans_assignment_declare_second = False
    if '=' in self.statement_str:
      if self.subject.name in p_consts.SUBJECT_NAMES_ASSIGN_DECLARE_FIRST:
        logger.debug('GetReferenceTranslation.get_starting_prompt_message: assignment with declaration first')
        use_constraint_trans_assignment_declare_first = True
        use_constraint_trans_assignment_declare_second = False
      else:
        logger.debug('GetReferenceTranslation.get_starting_prompt_message: assignment without declaration first')
        use_constraint_trans_assignment_declare_first = False
        use_constraint_trans_assignment_declare_second = True

    starting_prompt = HumanMessage(p_llm_templates.TemplateManager().render(
      'get-ref-trans.j2',
      src_language = p_consts.LANG_DICT[self.subject.src_lang],
      tar_language = p_consts.LANG_DICT[self.subject.tar_lang],
      statement_to_translate = self.statement_str,
      use_reduced_prompts = Config.use_reduced_prompts,
      use_constraint_trans_assignment_declare_second = use_constraint_trans_assignment_declare_second,
      use_constraint_trans_assignment_declare_first = use_constraint_trans_assignment_declare_first,
      use_constraint_trans_equals_op = '==' in self.statement_str,
      use_constraint_trans_modulus_op = '%' in self.statement_str,
      use_constraint_trans_comp_stat = any(tok in self.statement_str for tok in ['if', 'while', 'for', 'try', 'with']),
      use_constraint_trans_secret_fn = p_consts.GENERIC_SECRET_FN_INVOCATION in self.statement_str,
      use_constraint_trans_array_sort = '.sort(' in self.statement_str,
      use_constraint_trans_type_metaclass = '= type(' in self.statement_str,
      use_constraint_trans_raise_statement = 'raise ' in self.statement_str,
      use_constraint_trans_multiline_strings = '"""' in self.statement_str or "'''" in self.statement_str,
      use_constraint_trans_for_enumerate = re.search(r'\bfor\b.*\benumerate\b', self.statement_str) is not None,
      use_constraint_trans_py__class__ = re.search(r'\w+\.__class__(?!\.)', self.statement_str) is not None,  # does not match `.__class__.`, to avoid matching attribute accesses on the class object itself
      use_constraint_trans_negative_index_subscript = _uses_py_slice_then_index_negative_semantics(self.statement_str),
      use_constraint_trans_regex_match_start = re.search(r'([a-zA-Z0-9_]+)\.start\(\)', self.statement_str) is not None,
      use_constraint_trans_regex_re_match = re.search(r'[A-Z_]+\.match\(', self.statement_str) is not None,
    ))
    return starting_prompt

  def get_feedback_message(self, validation_result: p_llm_val.GetRefTransValidationResult) -> HumanMessage:
    self._log('initiating a feedback message factory')
    factory = p_llm_messages.GetRefTransF(
      self.template_dict,
      self.subject,
      validation_result,
      source_statement=self.statement_str,
    )
    feedback_message = factory.get_feedback_message()
    return feedback_message

  def validate_code_blocks(self) -> p_llm_val.GetRefTransValidationResult:
    self._log('starting reference translations validation')
    all_ref_trans_cands_stats = self.get_all_gen_code_blocks()
    val_result_obj = p_llm_val.val_get_ref_trans_candidates(
      all_ref_trans_cands_stats,
      self.subject.tar_lang,
    )
    return val_result_obj

  def does_require_feedback_iteration(self) -> bool:
    return self.feedback_iteration_counter <= p_consts.GET_REF_TRANS_LLM_FEEDBACKS

  def does_require_task_iteration(self):
    return self.task_iteration_counter <= p_consts.GET_REF_TRANS_LLM_NUM_ATTEMPTS

  def run_failed(self) -> None:
    msg = f'Could not get a reference translation. Reached retry limit. Check the logs.'
    self._log(f'ERROR {msg}')
    raise GetRefTransRetryLimitError(msg)


# HELPER FUNCTIONS
def _uses_py_slice_then_index_negative_semantics(source_stmt: str) -> bool:
  '''
  Detect patterns like `base[:i] ... base[i]` where `i` is likely walking
  backwards (e.g. initialized as -1), requiring JS negative-index restoration.
  '''
  if source_stmt is None:
    return False
  source_nowhitespace = re.sub(r'\s+', '', source_stmt)
  if source_nowhitespace == '':
    return False

  pattern = re.compile(
    r'(?<![A-Za-z0-9_\]\)])'
    r'([A-Za-z_]\w*(?:\s*\[[^\[\]\n]+\])*)'
    r'\s*\[\s*:\s*([A-Za-z_]\w*)\s*\]'
  )
  for match in pattern.finditer(source_stmt):
    base_expr = re.sub(r'\s+', '', match.group(1))
    idx_var = match.group(2)
    if f'{base_expr}[{idx_var}]' in source_nowhitespace:
      return True
  return False


def get_openai_credentials() -> Tuple[str, str]:
  assert p_consts.ENV_FILE.exists(), f'Create a "{p_consts.ENV_FILE.name}" file with necessary environment variables'
  env_dict = p_utils.read_json(p_consts.ENV_FILE)
  try:
    openai_api_key = env_dict['OPENAI_API_KEY']
    openai_organization = env_dict['OPENAI_ORGANIZATION']
    return openai_api_key, openai_organization
  except KeyError as err:
    msg = f'An environment variable "{err}" must be set.'
    logger.critical(msg)
    raise RuntimeError(msg) from err


def decorator_query_llm_cache(is_force_new=False):
  '''
  Decorator for caching LLM queries and responses.
  Written specifically for `query_llm` function.

  1. use exact prompt match
  2. allow multiple responses for a single prompt P
  3. allow multiple correct and incorrect responses for a single prompt P
  4. use index rotation when retrieving responses
  5. index always points to the next response to be retrieved
  6. the most recent written response is always returned

  P - pointer
  F - is_force_new
  q() - query LLM and return response
  inc(P) - increment pointer P
  reset(P) - reset pointer P to 0
  r(P) - read response at pointer P
  noop(P) - do nothing with pointer P
  '''

  def _parse_concatenated_json_objects(raw_line: str) -> List[dict]:
    '''
    Parse one JSONL line that may accidentally contain multiple
    concatenated JSON objects (e.g. `{"a":1}{"b":2}`).
    '''
    payload = raw_line.strip()
    if payload == '':
      return []

    decoder = json.JSONDecoder()
    objs: List[dict] = []
    idx = 0
    n = len(payload)
    while idx < n:
      while idx < n and payload[idx].isspace():
        idx += 1
      if idx >= n:
        break
      obj, end_idx = decoder.raw_decode(payload, idx)
      if not isinstance(obj, dict):
        raise json.JSONDecodeError('Expected JSON object', payload, idx)
      objs.append(obj)
      idx = end_idx
    return objs

  def _cache_read_success(hash_value: str) -> Optional[dict]:
    data_fpath = p_consts.LLM_CACHE_DIR / f'success-{hash_value}-data.jsonl'
    counter_fpath = p_consts.LLM_CACHE_DIR / f'success-{hash_value}-counter.json'

    # cache exists
    if data_fpath.exists():
      with open(data_fpath, 'r') as fin: lines = fin.readlines()
      with open(counter_fpath, 'r') as fin: cur_idx = json.load(fin)

      # pointer is out of bounds (state_1)
      # F=0 -> q(), reset(P) -> state_2
      # F=1 -> q(), noop(P) -> state_2
      if cur_idx == len(lines):
        if is_force_new:
          pass  # noop(P)
        else:
          with open(counter_fpath, 'w') as fout: fout.write('0')  # reset(P)
        return None  # q()

      # pointer is in bounds (state_2)
      # F=1 -> q(), noop(P) -> state_2
      # F=0 -> r(P), inc(P) -> state_2
      # F=0 -> r(P), inc(P) -> state_1
      else:
        if is_force_new:
          return None  # q(), noop(P)
        else:
          try:
            data = json.loads(lines[cur_idx])
          except json.JSONDecodeError as err:
            logger.error(f'Error decoding JSON from cache for hash {hash_value} at index {cur_idx}.')
            logger.error(f'Line content: {repr(lines[cur_idx])}')

            repaired_objs: List[dict] = []
            try:
              repaired_objs = _parse_concatenated_json_objects(lines[cur_idx])
            except Exception:
              repaired_objs = []

            if len(repaired_objs) >= 2:
              logger.warning(
                f'Auto-repairing malformed JSONL cache line for hash {hash_value}: '
                f'splitting one line into {len(repaired_objs)} JSON objects.'
              )
              repaired_lines: List[str] = []
              for i, line in enumerate(lines):
                if i != cur_idx:
                  repaired_lines.append(line if line.endswith('\n') else line + '\n')
                  continue
                for obj in repaired_objs:
                  repaired_lines.append(json.dumps(obj) + '\n')
              with open(data_fpath, 'w') as fout:
                fout.writelines(repaired_lines)
              data = repaired_objs[0]
            else:
              raise err
          with open(counter_fpath, 'w') as fout: fout.write(str(cur_idx + 1))  # inc(P)
          return data  # r(P)

    # cache does not exist (state_0)
    # F=0 -> q(), inc(P) -> state_1
    # F=1 -> q(), inc(P) -> state_1
    else:
      return None  # q()

  def _cache_write_success(hash_value: str, messages_md: str, query_result: str, query_stats: dict):
    data_fpath = p_consts.LLM_CACHE_DIR / f'success-{hash_value}-data.jsonl'
    counter_fpath = p_consts.LLM_CACHE_DIR / f'success-{hash_value}-counter.json'
    data = {
      'messages_md': messages_md,
      'query_result': query_result,
      'query_stats': query_stats
    }

    # cache exists
    if data_fpath.exists():
      with open(data_fpath, 'a') as fout: fout.write(json.dumps(data) + '\n')
    # cache does not exist (state_0)
    # F=0 -> q(), inc(P) -> state_1
    # F=1 -> q(), inc(P) -> state_1
    else:
      with open(data_fpath, 'w') as fout: fout.write(json.dumps(data) + '\n')  # q()
      with open(counter_fpath, 'w') as fout: fout.write('1')  # inc(P)

  def _cache_write_failure(hash_value: str, messages_md: str, error_info: dict):
    data_fpath = p_consts.LLM_CACHE_DIR / f'failure-{hash_value}-data.jsonl'
    data = {
      'messages_md': messages_md,
      'error_info': error_info
    }
    with open(data_fpath, 'a') as fout: fout.write(json.dumps(data) + '\n')

  def decorator(func):

    @functools.wraps(func)
    async def wrapper(messages: List[BaseMessage], **kwargs):

      messages_md = langchain_msgs_to_md(messages)
      key = messages_md + json.dumps(kwargs)
      hash_value = hashlib.sha256(key.encode('utf-8')).hexdigest()

      if Config.is_enable_llm_cache:
        data = _cache_read_success(hash_value)
        if data is not None:
          cached_query_stats = data.get('query_stats', {})
          if not isinstance(cached_query_stats, dict):
            cached_query_stats = {}
          cached_query_stats = copy.deepcopy(cached_query_stats)
          cached_query_stats['is_cache_hit'] = True
          try:
            cached_ms = max(0, int(cached_query_stats.get('etms')) - int(cached_query_stats.get('stms')))
          except Exception:
            cached_ms = 0
          cached_query_stats['cached_query_ms'] = cached_ms
          return data.get('query_result', ''), cached_query_stats

      try:
        raw_response, query_stats = await query_llm_base(messages, **kwargs)
        if not isinstance(query_stats, dict):
          query_stats = {}
        else:
          query_stats = copy.deepcopy(query_stats)
        query_stats['is_cache_hit'] = False
        query_stats['cached_query_ms'] = 0
        if Config.is_enable_llm_cache:
          _cache_write_success(hash_value, messages_md, raw_response, query_stats)
        return raw_response, query_stats

      except Exception as e:
        error_info = {
          'exception': e.__class__.__name__,
          'message': str(e)
        }
        if Config.is_enable_llm_cache:
          _cache_write_failure(hash_value, messages_md, error_info)
        raise e

    return wrapper

  return decorator


@decorator_query_llm_cache(is_force_new=False)
async def query_llm(messages: List[BaseMessage], **kwargs) -> Tuple[str, dict]:
  '''
  Wrapper for `query_llm_base` with caching functionality.
  RETURN a tuple of (raw_response, query_stats)
  '''
  return await query_llm_base(messages, **kwargs)


async def query_llm_base(messages: List[BaseMessage], **kwargs) -> Tuple[str, dict]:
  '''
  Query the LLM with the given messages and parameters.
  RETURN a tuple of (raw_response, query_stats)
  '''
  api_key, org_id = get_openai_credentials()

  model_params = copy.deepcopy(Config.model_params)
  # overwrite the default model params, if `model_params` is provided
  if 'model_params' in kwargs:
    for param, val in kwargs['model_params'].items():
      model_params[param] = val

  logger.debug(
    f'Making a query to LLM with parameters:\n'
    f'{json.dumps(model_params, indent=2)}')

  query_stats = {}
  query_stats['stms'] = p_utils.current_time_msec()

  chatgpt = ChatOpenAI(openai_api_key=api_key, openai_organization=org_id, **model_params)
  excs = []
  for i in range(7):
    try:
      chat_result = await chatgpt.ainvoke(messages)
    except OpenAIAPIError as e:  # probably hitting rate limit
      logger.warning(e)
      excs.append(e)
      await asyncio.sleep(2**i)  # 1 to 64 seconds
    else:
      break
  else:
    raise OpenAIErrors('Repeated API failures', excs)

  query_stats['etms'] = p_utils.current_time_msec()
  # number of input tokens (model takes in)
  query_stats['num_tokens_prompt'] = \
    chat_result.response_metadata['token_usage']['prompt_tokens']
  # number of output tokens (model generates)
  query_stats['num_tokens_completion'] = \
    chat_result.response_metadata['token_usage']['completion_tokens']
  # total number of tokens (input + output)
  query_stats['num_tokens_total'] = \
    chat_result.response_metadata['token_usage']['total_tokens']

  return chat_result.content, query_stats


def extract_code_blocks(raw_response: str) -> List[str]:

  def _pre_process_raw_response(raw_response: str) -> str:
    lines = [line for line in raw_response.split('\n')]
    # 1. strip trailing whitespace characters at each line
    lines = [line.rstrip() for line in lines]
    # 2. strip leading whitespace characters at lines beginning with ```
    lines = [line.lstrip() if line.lstrip().startswith('```') else line for line in lines]
    return '\n'.join(lines)

  raw_response = _pre_process_raw_response(raw_response)

  code_block_re = re.compile(r'^```(\w+)?\n(.*?)```$', re.DOTALL | re.MULTILINE)
  matches = re.finditer(code_block_re, raw_response)
  code_blocks = [m.group(2).strip() for m in matches]

  code_block_single_line_re = re.compile(r'^```(.*?)```$', re.MULTILINE)
  matches_single_line = re.finditer(code_block_single_line_re, raw_response)
  code_blocks_single_line = [m.group(1).strip() for m in matches_single_line]

  all_code_blocks = code_blocks + code_blocks_single_line

  logger.debug(f'Extracted {len(all_code_blocks)} code blocks from raw LLM response')
  return all_code_blocks


def langchain_msgs_to_md(messages: List[BaseMessage]) -> str:
  result_md = ''
  for msg in messages:
    result_md += f'# {msg.type}\n\n{msg.content}\n\n\n'
  return result_md.strip()


def _extract_snippet(program: str, lang: str, node_path: List[int]) -> str:
  '''
  Extract a snippet from `program` under `node_path`
  PARAM node_path: path to node of interest relative to the one and only child (context) under the root node
  '''
  program_ast_text, _ = d_ast_parse.parse_text_dbg(program, lang, keep_text=True)
  program_tree = pds.PirelTree(program_ast_text)

  root_node_children = program_tree.get_root_node().get_children()
  assert len(root_node_children) > 0, 'sanity check'
  if len(root_node_children) > 1:
    logger.warning(f'_extract_snippet: requested program\'s root node has multiple children (should be one)\n:{program}')

  context_node = root_node_children[0]
  problematic_node = context_node.get_child_by_path(node_path)
  snippet = problematic_node.get_text().strip()
  return snippet


def _is_context_empty(template_dict: dict) -> bool:
  ''''''
  # TODO template_dict['contexts'] is a list of contexts. Which one to consider?
  context = template_dict['contexts'][0]

  source_context = context['source_context']
  target_context = context['target_context']

  # source or parent context have a parent -> have context
  if len(source_context) > 1 or len(target_context) > 1:
    assert len(source_context) > 1, 'sanity check'
    assert len(target_context) > 1, 'sanity check'
    return False

  source_node_and_siblings = source_context[0]
  target_node_and_siblings = target_context[0]

  # source or parent context have a sibling -> have context
  if len(source_node_and_siblings) > 1 or len(target_node_and_siblings) > 1:
    assert len(source_node_and_siblings) > 1, 'sanity check'
    assert len(source_node_and_siblings) > 1, 'sanity check'
    return False

  assert source_node_and_siblings[0].split('.')[1] == template_dict['problematic_node_type'], 'sanity check'
  assert target_node_and_siblings[0] == 'unknown', 'sanity check'

  return True


# API
async def get_translation_pairs_from_tsp(
  subject: p_subject.PirelSubject,
  tsp: Tuple[str, str, str],
  template_dict: dict,
  lpllm_gen_log: Optional[ptlog.PLLMGenLog] = None
) -> List[Tuple[dict, dict]]:
  '''
  RETURN non-empty list of all possible translation pairs obtained from a given `tsp`.
  NOTE raised errors propagate to the caller.

  subject must contain the following attributes:
  - name
  - src_lang
  - tar_lang
  '''
  logger.debug(
    f'trans-tsp: ~~~ attempting to translate SP1 and SP2 to generate '
    f'a translation pair:\n{json.dumps(tsp, indent=2)}')

  def _check_sp1_sp2_identical(
    sp1_tp1_cands: List[Dict[str, str]], sp2: str
  ) -> Optional[list[Tuple[dict, dict]]]:
    assert len(sp1_tp1_cands) > 0, 'sanity check'
    sp1 = sp1_tp1_cands[0]['source']
    assert all(map(lambda sp1_tp1_cand: sp1_tp1_cand['source'] == sp1, sp1_tp1_cands)), 'sanity check'
    if sp1 != sp2:
      return None
    logger.debug(f'SP1 and SP2 are identical. Just using the translation of SP1.')
    translation_pairs = []
    for sp1_tp1_cand in sp1_tp1_cands:
      sp1, tp1 = sp1_tp1_cand['source'], sp1_tp1_cand['target']
      translation_pairs.append(({'source': sp1, 'target': tp1}, {'source': sp2, 'target': tp1}))
    return translation_pairs

  def _aux_log_msg_sp1_tp1_cands(sp1_tp1_cands: List[Dict[str, str]]) -> str:
    s = f'trans-tsp: generated {len(sp1_tp1_cands)} candidate translations for SP1:\n'
    for idx, sp1_tp1_cand in enumerate(sp1_tp1_cands, start=1):
      hash = d_utils.string_sha256(sp1_tp1_cand['source'] + sp1_tp1_cand['target'])
      cand = json.dumps(sp1_tp1_cand, indent=2)
      s += f'[{idx}] {hash}:\n{cand}\n'
    return s.rstrip('\n')

  def _aux_log_msg_trans_pair_cands(translation_pair_cands: List[Dict[str, str]]) -> str:
    s = f'trans-tsp: generated {len(translation_pair_cands)} new translation pairs:\n'
    for idx, translation_pair_cand in enumerate(translation_pair_cands, start=1):
      sp1 = translation_pair_cand[0]['source']
      tp1 = translation_pair_cand[0]['target']
      sp2 = translation_pair_cand[1]['source']
      tp2 = translation_pair_cand[1]['target']
      hash = d_utils.string_sha256(f'{sp1}{tp1}{sp2}{tp2}')
      cand = json.dumps(translation_pair_cand, indent=2)
      s += f'[{idx}] {hash}:\n{cand}\n'
    return s.rstrip('\n')

  lpllm_gen_log = lpllm_gen_log or ptlog.PLLMGenLog()
  lpllm_gen_log.stms = p_utils.current_time_msec()
  sp1, sp2 = tsp

  # ~~~ TRANSLATE `SP1` TO PRODUCE SP1_TP1_CANDS (A.K.A. PROGRAM PAIRS)
  ltrans_sp1 = ptlog.TransSP1()
  ltrans_sp1.sp1 = sp1
  ltrans_sp1.stms = p_utils.current_time_msec()
  lpllm_gen_log.trans_sp1 = ltrans_sp1
  trans_sp1 = BaseTranslateSP1Task.dispatch(subject, template_dict, sp1, ltrans_sp1)

  try:
    sp1_tp1_cands = await trans_sp1.run()
    ltrans_sp1.sp1_tp1_cands = [ptlog.Sp1Tp1Cand.from_gen_cands(_c) for _c in sp1_tp1_cands]
    ltrans_sp1.llm_query_stats = [ptlog.LLMQueryStat.from_dict(stats) for stats in trans_sp1.llm_query_stats]
    ltrans_sp1.success = True
    ltrans_sp1.etms = p_utils.current_time_msec()
  except SP1TranslationRetryLimitError as err:
    msg = f'BAD: Reached a retry limit for SP1 translation:\n{str(err)}'
    logger.warning(msg)
    ltrans_sp1.llm_query_stats = [ptlog.LLMQueryStat.from_dict(stats) for stats in trans_sp1.llm_query_stats]
    ltrans_sp1.success = False
    ltrans_sp1.reason = msg
    ltrans_sp1.etms = p_utils.current_time_msec()
    raise NoTransPairsFromTSPError from err

  logger.debug(_aux_log_msg_sp1_tp1_cands(sp1_tp1_cands))

  # ~~~ FOR EACH `SP1_TP1_CAND` GENERATE ALL POSSIBLE `TRANSLATION_PAIR` CANDIDATES
  all_translation_pairs = []
  for cand_idx, sp1_tp1_cand in enumerate(sp1_tp1_cands, start=1):
    logger.debug(
      f'trans-tsp: translating SP2 (SP1-TP1 cand {cand_idx}/{len(sp1_tp1_cands)})\n'
      f'trans_sp2.id = {cand_idx}')

    ltrans_sp2 = ptlog.TransSP2()
    ltrans_sp2.id = cand_idx
    ltrans_sp2.sp1_tp1_cand = ptlog.Sp1Tp1Cand.from_gen_cands(sp1_tp1_cand)
    ltrans_sp2.sp2 = sp2
    ltrans_sp2.sp1_sp2_are_identical = False
    ltrans_sp2.stms = p_utils.current_time_msec()
    lpllm_gen_log.trans_sp2s.append(ltrans_sp2)

    # check if SP1 and SP2 are identical
    translation_pairs = _check_sp1_sp2_identical(sp1_tp1_cands, sp2)
    if translation_pairs is not None:
      all_translation_pairs.extend(translation_pairs)
      ltrans_sp2.sp1_sp2_are_identical = True
      ltrans_sp2.translation_pairs = [ptlog.TransPair.from_tuple(tp) for tp in translation_pairs]
      ltrans_sp2.success = True
      ltrans_sp2.etms = p_utils.current_time_msec()
      continue

    trans_sp2 = BaseTranslateSP2Task.dispatch(subject, template_dict, sp1_tp1_cand, sp2, ltrans_sp2)

    try:
      translation_pair_cands = await trans_sp2.run()
    except SP2TranslationRetryLimitError as err:
      msg = (
        f'BAD: Reached a retry limit for SP2 translation:\n'
        f'{str(err)}\n'
        f'Will try with the next TP1 cands ({len(sp1_tp1_cands)-cand_idx} left)')
      logger.warning(msg)
      ltrans_sp2.llm_query_stats = [ptlog.LLMQueryStat.from_dict(stats) for stats in trans_sp2.llm_query_stats]
      ltrans_sp2.success = False
      ltrans_sp2.reason = msg
      ltrans_sp2.etms = p_utils.current_time_msec()
      continue

    all_translation_pairs.extend(translation_pair_cands)
    ltrans_sp2.translation_pairs = [ptlog.TransPair.from_tuple(tp) for tp in translation_pair_cands]
    ltrans_sp2.llm_query_stats = [ptlog.LLMQueryStat.from_dict(stats) for stats in trans_sp2.llm_query_stats]
    ltrans_sp2.success = True
    ltrans_sp2.etms = p_utils.current_time_msec()
    logger.debug(_aux_log_msg_trans_pair_cands(translation_pair_cands))

  logger.debug(
    f'trans-tsp: ~~~ finishing API call to p_llm_gen.get_translation_pairs_from_tsp\n'
    f'The number of all translation pairs is {len(all_translation_pairs)}:\n'
    f'{json.dumps(all_translation_pairs, indent=2)}')

  if len(all_translation_pairs) == 0:
    msg = f'BAD: Could not gen trans pairs from a program pair:\n{json.dumps(sp1_tp1_cands, indent=2)}'
    logger.warning(msg)
    lpllm_gen_log.success = False
    lpllm_gen_log.reason = msg
    lpllm_gen_log.etms = p_utils.current_time_msec()
    raise NoTransPairsFromTSPError(msg)

  lpllm_gen_log.success = True
  lpllm_gen_log.etms = p_utils.current_time_msec()
  return all_translation_pairs


def _edit_node_text(
  tp1_lit_node: pvis.AbstractNode,
  sp1_lit_value: str,
  sp2_lit_value: str
) -> None:
  ''''''
  _RE_INT = re.compile(r'^\d+$')
  _RE_BIGINT = re.compile(r'^(\d+)n$')
  is_int = lambda s: bool(_RE_INT.match(s))
  is_bigint = lambda s: bool(_RE_BIGINT.match(s))
  tp1_lit_value = tp1_lit_node.children[0].get_type()

  if is_int(sp1_lit_value):
    if is_bigint(tp1_lit_value):
      if tp1_lit_value[:-1] == sp1_lit_value:
        if is_int(sp2_lit_value):
          tp1_lit_node.children[0].node_type = sp2_lit_value + 'n'
        else:
          tp1_lit_node.children[0].node_type = sp2_lit_value
    else:
      if tp1_lit_value == sp1_lit_value:
        tp1_lit_node.children[0].node_type = sp2_lit_value
  else:
    if tp1_lit_value == sp1_lit_value:
      tp1_lit_node.children[0].node_type = sp2_lit_value


def _get_edit_dict(
  sp1_lit_nodes: List[pvis.AbstractNode],
  tp1_lit_nodes: List[pvis.AbstractNode],
  sp1_prob_node: pvis.AbstractNode,
  sp2_prob_node: pvis.AbstractNode
) -> Dict[str, str]:
  ''''''
  edit_dict : Dict[str, str] = {}
  for sp1_lit_node in sp1_lit_nodes:
    sp1_lit_npath = sp1_prob_node.get_path_to_child(sp1_lit_node)
    sp2_lit_node = sp2_prob_node.get_child_by_path(sp1_lit_npath)
    assert sp2_lit_node.is_literal_node(), 'sanity check'
    assert sp1_lit_node.is_literal_node(), 'sanity check'
    sp1_lit_value = sp1_lit_node.children[0].get_type()
    sp2_lit_value = sp2_lit_node.children[0].get_type()
    if sp1_lit_value == sp2_lit_value:
      continue
    if sp1_lit_value in edit_dict:
      assert edit_dict[sp1_lit_value] == sp2_lit_value, 'sanity check'
    else:
      edit_dict[sp1_lit_value] = sp2_lit_value
  for tp1_lit_node in tp1_lit_nodes:
    assert tp1_lit_node.is_literal_node(), 'sanity check'
  return edit_dict


def get_tp2_offline(
  sp1: str,
  sp2: str,
  tp1: str,
  context: dict
) -> str:
  '''
  Given two generated snippets sp1 and sp2, and a candidate translation tp1 of sp1,
  generate a candidate translation tp2 of sp2 by editing tp1 based on the differences
  between sp1 and sp2.
  This function is intended to replace SP2 translation via LLM.
  '''
  p_utils.log_json_time(f'args-get_tp2_offline.json', locals())

  sp1tree = pvpy.Tree.from_str(sp1)
  sp2tree = pvpy.Tree.from_str(sp2)
  tp1tree = pvjs.Tree.from_str(tp1)

  sp1_prob_node = sp1tree.root_node.find_node_under_context(context['source_context'])
  sp2_prob_node = sp2tree.root_node.find_node_under_context(context['source_context'])
  tp1_prob_node = tp1tree.root_node.find_node_under_context(context['target_context'])

  assert sp1_prob_node is not None, 'sanity check'
  assert sp2_prob_node is not None, 'sanity check'
  assert tp1_prob_node is not None, 'sanity check'

  sp1_lit_nodes = sp1_prob_node.collect_literal_nodes()
  tp1_lit_nodes = tp1_prob_node.collect_literal_nodes()

  edit_dict = _get_edit_dict(sp1_lit_nodes, tp1_lit_nodes, sp1_prob_node, sp2_prob_node)
  for src, dst in edit_dict.items():
    for tp1_lit_node in tp1_lit_nodes:
      _edit_node_text(tp1_lit_node, src, dst)

  pp = pvjs.PrettyPrinter()
  tp2 = pp.visit(tp1tree.root_node)
  return tp2


async def get_translation_pairs_from_tsp_less_llm(
  subject: p_subject.PirelSubject,
  tsp: Tuple[str, str, str],
  template_dict: dict,
  lpllm_gen_log: Optional[ptlog.PLLMGenLog] = None
) -> List[Tuple[dict, dict]]:
  '''
  RETURN non-empty list of all possible translation pairs obtained from a given `tsp`.
  NOTE raised errors propagate to the caller.

  NOTE subject must contain the following attributes:
  - name
  - src_lang
  - tar_lang
  '''
  logger.debug(
    f'trans-tsp: ~~~ attempting to translate SP1 (LLM) and SP2 (offline) to generate '
    f'translation pairs:\n{json.dumps(tsp, indent=2)}')

  def _aux_log_msg_sp1_tp1_cands(sp1_tp1_cands: List[Dict[str, str]]) -> str:
    s = f'trans-tsp: generated {len(sp1_tp1_cands)} candidate translations for SP1:\n'
    for idx, sp1_tp1_cand in enumerate(sp1_tp1_cands, start=1):
      hash = d_utils.string_sha256(sp1_tp1_cand['source'] + sp1_tp1_cand['target'])
      cand = json.dumps(sp1_tp1_cand, indent=2)
      s += f'[{idx}] {hash}:\n{cand}\n'
    return s.rstrip('\n')

  lpllm_gen_log = lpllm_gen_log or ptlog.PLLMGenLog()
  lpllm_gen_log.stms = p_utils.current_time_msec()
  sp1, sp2 = tsp

  # ~~~ TRANSLATE `SP1` TO PRODUCE SP1_TP1_CANDS (A.K.A. PROGRAM PAIRS)
  ltrans_sp1 = ptlog.TransSP1()
  ltrans_sp1.sp1 = sp1
  ltrans_sp1.stms = p_utils.current_time_msec()
  lpllm_gen_log.trans_sp1 = ltrans_sp1
  trans_sp1 = BaseTranslateSP1Task.dispatch(subject, template_dict, sp1, ltrans_sp1)

  try:
    sp1_tp1_cands = await trans_sp1.run()
    ltrans_sp1.sp1_tp1_cands = [ptlog.Sp1Tp1Cand.from_gen_cands(_c) for _c in sp1_tp1_cands]
    ltrans_sp1.llm_query_stats = [ptlog.LLMQueryStat.from_dict(stats) for stats in trans_sp1.llm_query_stats]
    ltrans_sp1.success = True
    ltrans_sp1.etms = p_utils.current_time_msec()
  except SP1TranslationRetryLimitError as err:
    msg = f'BAD: Reached a retry limit for SP1 translation:\n{str(err)}'
    logger.warning(msg)
    ltrans_sp1.llm_query_stats = [ptlog.LLMQueryStat.from_dict(stats) for stats in trans_sp1.llm_query_stats]
    ltrans_sp1.success = False
    ltrans_sp1.reason = msg
    ltrans_sp1.etms = p_utils.current_time_msec()
    raise NoTransPairsFromTSPError from err

  logger.debug(_aux_log_msg_sp1_tp1_cands(sp1_tp1_cands))

  # ~~~ FOR EACH `TP1_CAND` GENERATE `TP2` VIA OFFLINE EDITING
  all_translation_pairs = []
  for cand_idx, sp1_tp1_cand in enumerate(sp1_tp1_cands, start=1):
    logger.debug('Obtaining TP2 via offline editing of TP1')
    tp1 = sp1_tp1_cand['target']
    context = template_dict['contexts'][0]
    tp2 = get_tp2_offline(sp1, sp2, tp1, context)
    if p_utils.does_have_parse_error(tp2, subject.tar_lang):
      msg = f'WARNING: TP2 generated via offline editing has a parse error. Skipping it.\nTP2:\n{tp2}'
      logger.warning(msg)
      continue
    translation_pair = ({'source': sp1, 'target': tp1}, {'source': sp2, 'target': tp2})
    all_translation_pairs.append(translation_pair)

  logger.debug(
    f'trans-tsp: ~~~ finishing API call to p_llm_gen.get_translation_pairs_from_tsp_less_llm\n'
    f'The number of all translation pairs is {len(all_translation_pairs)}:\n'
    f'{json.dumps(all_translation_pairs, indent=2)}')

  if len(all_translation_pairs) == 0:
    msg = f'BAD: Could not gen trans pairs from a program pair:\n{json.dumps(sp1_tp1_cands, indent=2)}'
    logger.warning(msg)
    lpllm_gen_log.success = False
    lpllm_gen_log.reason = msg
    lpllm_gen_log.etms = p_utils.current_time_msec()
    raise NoTransPairsFromTSPError(msg)

  lpllm_gen_log.success = True
  lpllm_gen_log.etms = p_utils.current_time_msec()
  return all_translation_pairs


async def get_reference_translations(
  statement_str: str,
  src_lang: str,
  tar_lang: str,
) -> Tuple[List[str], ptlog.GetRefTrans]:
  '''
  Get a reference translation for a statement node code.
  RETURN: reference translations or empty list if failed.

  `subject` must contain the following attributes:
  - name
  - src_lang
  - tar_lang
  `template_dict` must contain the following attributes:
  - src_lang
  - tar_lang
  '''
  logger.info(f'~~~ Starting API call to p_llm_gen.get_reference_translations')

  lget_ref_trans = ptlog.GetRefTrans()
  lget_ref_trans.stms = p_utils.current_time_msec()
  lget_ref_trans.statement_str = statement_str

  fabr_template_dict = {'src_lang': src_lang, 'tar_lang': tar_lang}
  subject_conf = {
    'benchmark_name': 'get_reference_translations',
    'name': 'get_reference_translations',
    'src_program': 'get_reference_translations',
    'src_lang': src_lang,
    'tar_lang': tar_lang,
  }
  fabr_subject = p_subject.PirelSubject.from_dict(subject_conf)

  get_ref_trans_task = GetReferenceTranslation(
    task_name='get_ref_trans',
    statement_str=statement_str,
    subject=fabr_subject,
    template_dict=fabr_template_dict,
    lbase_task=lget_ref_trans,
  )

  try:
    ref_translations = await get_ref_trans_task.run()
  except GetRefTransRetryLimitError as err:
    logger.warning(str(err))
    lget_ref_trans.llm_query_stats = \
      [ptlog.LLMQueryStat.from_dict(stats) for stats in get_ref_trans_task.llm_query_stats]
    lget_ref_trans.success = False
    lget_ref_trans.reason = str(err)
    lget_ref_trans.etms = p_utils.current_time_msec()
    return [], lget_ref_trans

  assert len(ref_translations) > 0, 'sanity check'

  lget_ref_trans.llm_query_stats = \
    [ptlog.LLMQueryStat.from_dict(stats) for stats in get_ref_trans_task.llm_query_stats]
  lget_ref_trans.success = True
  lget_ref_trans.ref_translations = ref_translations
  lget_ref_trans.etms = p_utils.current_time_msec()

  return ref_translations, lget_ref_trans
