from __future__ import annotations

import hashlib
import json
from abc import ABC
from typing import Dict, Iterable, List, Optional, Tuple

import d_ast_parse
import d_grammar_rules
import p_visitor_py as pvpy
import p_utils
from p_config import Config


logger = p_utils.setup_logger(__name__)


class TRuleBase(ABC):
  '''
  An abstract base class representing a translation rule.
  '''
  def __init__(self, rule_parsed: dict):
    '''
    PARAM rule_parsed: a dictionary representing a translation rule
    as parsed by d_grammar_rules.parse_analyze_rules().
    '''
    assert isinstance(rule_parsed, dict), f'Expected rule to be a dict, got {type(rule_parsed)}'
    assert 'type' in rule_parsed, 'Rule must have a "type" key'
    assert 'match' in rule_parsed, 'Rule must have a "match" key'
    assert 'expand' in rule_parsed, 'Rule must have a "expand" key'
    self.rule_parsed = rule_parsed
    self._rule_str = None  # lazy initialization
    self._rule_hash = None  # lazy initialization

  def __str__(self):
    return self.to_rule_str()

  def __repr__(self):
    # return repr(self.to_rule_str())  # for debugging
    return f'{self.__class__.__name__} {str(self.rule_parsed)}'

  def __eq__(self, obj) -> bool:
    if not isinstance(obj, TRuleBase):
      raise ValueError(f'Cannot use == with {type(obj)}')
    return self.to_rule_str() == obj.to_rule_str()

  def get_matcher_signature(self) -> str:
    return str(self.rule_parsed['match'])

  @classmethod
  def parse_rule_str(cls, rule_str: str) -> dict:
    '''
    Parse a rule string into a rule_parsed dict.
    '''
    rules_parsed = d_grammar_rules.parse_analyze_rules_optim(rule_str)
    assert len(rules_parsed) == 1, f'Expected exactly one rule, got {len(rules_parsed)}'
    return rules_parsed[0]

  # SERIALIZATION METHODS
  def to_rule_str(self) -> str:
    '''
    Convert the rule to a plain string representation.
    '''
    if self._rule_str is None:
      self._rule_str = d_grammar_rules.pretty_rule(self.rule_parsed)
    return self._rule_str

  def to_rule_hash(self) -> str:
    '''
    Stable hash key for this rule's canonical string form.
    '''
    if self._rule_hash is None:
      self._rule_hash = hashlib.sha256(self.to_rule_str().encode('utf-8')).hexdigest()
    return self._rule_hash

  def to_dict(self) -> dict:
    '''
    Serialize the rule to a dict.
    '''
    res = {
      'type': self.__class__.__name__,
      'rule_str': self.to_rule_str(),
    }
    return res

  @classmethod
  def from_dict(cls, rule_serialized: dict) -> TRuleBase:
    '''
    Create a rule instance from a serialized dict.
    '''
    if rule_serialized['type'] == 'StartingTRule':
      return StartingTRule.from_dict(rule_serialized)
    elif rule_serialized['type'] == 'LogStatTRule':
      return LogStatTRule.from_dict(rule_serialized)
    elif rule_serialized['type'] == 'StandardTRule':
      return StandardTRule.from_dict(rule_serialized)
    elif rule_serialized['type'] == 'StatementOverfittedTRule':
      return StatementOverfittedTRule.from_dict(rule_serialized)
    else:
      raise ValueError(f'Unknown rule type: {rule_serialized["type"]}')


class StartingTRule(TRuleBase):
  '''
  A class that represents a translation rule that appears
  in the starting ruleset. It is assumed to be valid.
  '''
  @classmethod
  def from_dict(cls, rule_serialized: dict) -> StartingTRule:
    '''
    Create a StartingTRule instance from a serialized dict.
    '''
    assert rule_serialized['type'] == 'StartingTRule', f'Expected type to be StartingTRule, got {rule_serialized["type"]}'
    rule_str = rule_serialized['rule_str']
    rule_parsed = cls.parse_rule_str(rule_str)
    return cls(rule_parsed)


class LogStatTRule(TRuleBase):
  '''
  A class that represents a translation rule for log statements
  used during instrumentation.
  '''
  @classmethod
  def from_dict(cls, rule_serialized: dict) -> LogStatTRule:
    '''
    Create a LogStatTRule instance from a serialized dict.
    '''
    assert rule_serialized['type'] == 'LogStatTRule', f'Expected type to be LogStatTRule, got {rule_serialized["type"]}'
    rule_str = rule_serialized['rule_str']
    rule_parsed = cls.parse_rule_str(rule_str)
    return cls(rule_parsed)


class LearnedTRuleBase(TRuleBase, ABC):
  '''
  An abstract class that represents a learned translation rule.
  '''
  def __init__(
    self,
    rule_parsed: dict,
    stat_nid: int,
    simple_ntext: str,
  ):
    super().__init__(rule_parsed)
    self.stat_nid = stat_nid
    self.simple_ntext = simple_ntext

  # SERIALIZATION METHODS
  def to_dict(self) -> dict:
    '''
    Serialize the learned rule to a dict.
    '''
    res = super().to_dict()
    res.update({
      'stat_nid': self.stat_nid,
      'simple_ntext': self.simple_ntext,
    })
    return res


class StandardTRule(LearnedTRuleBase):
  '''
  A class that represents a translation rule that was
  learned using the standard learning method.
  '''
  @classmethod
  def from_dict(cls, rule_serialized: dict) -> StandardTRule:
    '''
    Create a StandardTRule instance from a serialized dict.
    '''
    assert rule_serialized['type'] == 'StandardTRule', f'Expected type to be StandardTRule, got {rule_serialized["type"]}'
    rule_str = rule_serialized['rule_str']
    rule_parsed = cls.parse_rule_str(rule_str)
    stat_nid = rule_serialized['stat_nid']
    simple_ntext = rule_serialized['simple_ntext']
    return cls(rule_parsed, stat_nid, simple_ntext)


class StatementOverfittedTRule(LearnedTRuleBase):
  '''
  A class that represents a translation rule that was
  learned using the recovery learning method to translate
  a specific statement directly.
  '''
  @classmethod
  def from_dict(cls, rule_serialized: dict) -> StatementOverfittedTRule:
    '''
    Create a StatementOverfittedTRule instance from a serialized dict.
    '''
    assert rule_serialized['type'] == 'StatementOverfittedTRule', f'Expected type to be StatementOverfittedTRule, got {rule_serialized["type"]}'
    rule_str = rule_serialized['rule_str']
    rule_parsed = cls.parse_rule_str(rule_str)
    stat_nid = rule_serialized['stat_nid']
    simple_ntext = rule_serialized['simple_ntext']
    return cls(rule_parsed, stat_nid, simple_ntext)


class TaggedTRule(LearnedTRuleBase):
  '''
  A class that represents a translation rule that is tagged with a specific tag.
  The tag can be used to indicate the source or purpose of the rule.
  '''
  @classmethod
  def from_dict(cls, rule_serialized: dict) -> TaggedTRule:
    '''
    Create a TaggedTRule instance from a serialized dict.
    '''
    assert rule_serialized['type'] == 'TaggedTRule', f'Expected type to be TaggedTRule, got {rule_serialized["type"]}'
    rule_str = rule_serialized['rule_str']
    rule_parsed = cls.parse_rule_str(rule_str)
    stat_nid = rule_serialized['stat_nid']
    simple_ntext = rule_serialized['simple_ntext']
    return cls(rule_parsed, stat_nid, simple_ntext)


class TaggedOverfittedTRule(LearnedTRuleBase):
  '''
  A class that represents a translation rule that is tagged with a specific tag.
  The tag can be used to indicate the source or purpose of the rule.
  '''
  @classmethod
  def from_dict(cls, rule_serialized: dict) -> TaggedOverfittedTRule:
    '''
    Create a TaggedOverfittedTRule instance from a serialized dict.
    '''
    assert rule_serialized['type'] == 'TaggedOverfittedTRule', f'Expected type to be TaggedOverfittedTRule, got {rule_serialized["type"]}'
    rule_str = rule_serialized['rule_str']
    rule_parsed = cls.parse_rule_str(rule_str)
    stat_nid = rule_serialized['stat_nid']
    simple_ntext = rule_serialized['simple_ntext']
    return cls(rule_parsed, stat_nid, simple_ntext)


class Ruleset:
  '''
  Represents a set of translation rules.

  PROPERTY matcher_groups: is a dictionary that groups rules
  by their matcher signatures.
  INV: rules in self._verified_rules are also in self.rules
  '''
  def __init__(self):
    self.rules : List[TRuleBase] = []

    '''
    Matcher groups contains groups of rules that share the same matcher signature.
    '''
    self.matcher_groups: Dict[str, List[TRuleBase]] = {}
    '''
    Fast lookup from rule string to in-ruleset rule reference.
    Used to avoid repeated O(n) scans in get_rule_ref().
    '''
    self._rule_ref_index: Dict[str, TRuleBase] = {}
    '''
    Fast lookup from rule hash to in-ruleset rule reference.
    Used by compact cache payloads that store only rule hashes.
    '''
    self._rule_hash_index: Dict[str, TRuleBase] = {}

    '''
    Verified rules are rules that were validated based on tests
    to be able to correctly translate a specific AST node.
    Verified rules are "guaranteed" to work for the matched AST.
    '''
    self._verified_rules: Dict[str, List[TRuleBase]] = {}

    '''
    Unverifiable rules are rules that could not be verified
    based on tests because the AST nodes they match are not
    loggable. Unlike verified rules, a single AST node can
    map to multiple unverifiable rules, because they might share
    the same matcher signature but have different expansions.
    '''
    self._unverifiable_rules: Dict[str, List[TRuleBase]] = {}

  def __str__(self):
    return json.dumps(self.to_dict(), indent=2)

  def _update_matcher_groups(self):
    self.matcher_groups = {}
    self._rule_ref_index = {}
    self._rule_hash_index = {}
    for rule in self.rules:
      sig = rule.get_matcher_signature()
      self.matcher_groups.setdefault(sig, []).append(rule)
      rule_str = rule.to_rule_str()
      # Keep the first occurrence to match legacy linear-scan behavior.
      if rule_str not in self._rule_ref_index:
        self._rule_ref_index[rule_str] = rule
      # Same "first occurrence wins" behavior for hash index.
      rule_hash = rule.to_rule_hash()
      if rule_hash not in self._rule_hash_index:
        self._rule_hash_index[rule_hash] = rule

  def append_rule(self, rule: TRuleBase):
    '''
    Append a rule to the ruleset and update matcher_groups.
    '''
    assert isinstance(rule, TRuleBase), \
      f'Expected rule to be subclass of TRuleBase, got {type(rule)}'
    if rule not in self.rules:
      self.rules.append(rule)
      self._update_matcher_groups()

  def _extend_rules(self, rules: Iterable[TRuleBase]):
    rules = list(rules)
    for idx, rule in enumerate(rules):
      print(f'Extending rules: {idx+1}/{len(rules)}', end='\r')
      assert isinstance(rule, TRuleBase), \
        f'Expected rule to be subclass of TRuleBase, got {type(rule)}'
      if rule not in self.rules:
        self.rules.append(rule)
    self._update_matcher_groups()

  def prepend_rule(self, rule: TRuleBase):
    '''
    Prepend a rule to the ruleset and update matcher_groups.
    '''
    assert isinstance(rule, TRuleBase), \
      f'Expected rule to be subclass of TRuleBase, got {type(rule)}'
    self.rules.insert(0, rule)
    self._update_matcher_groups()

  def get_rule_ref(self, other_rule: TRuleBase) -> Optional[TRuleBase]:
    '''
    Get a reference to a rule in the ruleset that is equal to other_rule.
    '''
    assert isinstance(other_rule, TRuleBase), \
      f'Expected other_rule to be subclass of TRuleBase, got {type(other_rule)}'
    return self._rule_ref_index.get(other_rule.to_rule_str())

  def get_rule_ref_by_hash(self, rule_hash: str) -> Optional[TRuleBase]:
    '''
    Get a reference to a rule in the ruleset by rule hash.
    '''
    assert isinstance(rule_hash, str), f'Expected rule_hash to be str, got {type(rule_hash)}'
    return self._rule_hash_index.get(rule_hash)

  def get_rule_by_idx(self, idx: int) -> TRuleBase:
    '''
    Get a rule by its index in the ruleset.
    '''
    assert 0 <= idx < len(self.rules), f'Index {idx} out of bounds for ruleset of size {len(self.rules)}'
    return self.rules[idx]

  def get_stat_overfitted_rules(self) -> List[StatementOverfittedTRule]:
    '''
    Get all StatementOverfittedTRule rules in the ruleset.
    '''
    return [rule for rule in self.rules if isinstance(rule, StatementOverfittedTRule)]

  # VERIFIED RULES RELATED
  def update_verified_rules(self, encoded_ast: str, rule: TRuleBase) -> None:
    assert isinstance(encoded_ast, str), f'Unexpected type {type(encoded_ast)}'
    assert isinstance(rule, TRuleBase), f'Unexpected type {type(rule)}'
    assert self.get_rule_ref(rule) is not None, \
      'Rule must be in self.rules to be added to verified rules'

    '''
    Store a set of verified rules for the given encoded_ast.
    '''
    if encoded_ast in self._verified_rules:
      existing_vrf_rules = self._verified_rules[encoded_ast]
      # add only if rule is not already present (avoid duplicates)
      if rule not in existing_vrf_rules:
        self._verified_rules[encoded_ast].append(rule)
    else:
      self._verified_rules[encoded_ast] = [rule]

  def remove_verified_rules_for(self, encoded_ast: str) -> None:
    assert isinstance(encoded_ast, str), f'Unexpected type {type(encoded_ast)}'
    assert encoded_ast in self._verified_rules, f'No verified rules for "{encoded_ast}"'
    del self._verified_rules[encoded_ast]

  def get_verified_rules(self, encoded_ast: str) -> TRuleBase:
    assert isinstance(encoded_ast, str), f'Unexpected type {type(encoded_ast)}'
    assert encoded_ast in self._verified_rules, f'No verified rule for "{encoded_ast}"'
    return self._verified_rules[encoded_ast]

  def verified_rules_exist(self, encoded_ast: str) -> bool:
    assert isinstance(encoded_ast, str), f'Unexpected type {type(encoded_ast)}'
    return encoded_ast in self._verified_rules

  def merge_verified_rules_from(self, ruleset_serialized: dict) -> None:
    '''
    NOTE if ruleset_serialized has a verified rule for an AST that
    already exists in self._verified_rules, it will be ignored.
    If ruleset_serialized has a rule that does not exist in self.rules,
    it will be ignored. This makes sure that self.rules are the only
    rules that we have.
    '''
    assert isinstance(ruleset_serialized, dict), f'Unexpected type {type(ruleset_serialized)}'
    kv_pairs = list(ruleset_serialized.get('verified_rules', {}).items())
    for idx, (encoded_ast, serialized_trules) in enumerate(kv_pairs):
      print(f'Merging verified rules: {idx+1}/{len(kv_pairs)}', end='\r')
      for serialized_trule in serialized_trules:
        other_rule = TRuleBase.from_dict(serialized_trule)
        rule = self.get_rule_ref(other_rule)  # None if rule not in self.rules
        if rule:
          self.update_verified_rules(encoded_ast, rule)
        else:
          logger.warning(f'Ignoring verified rule for "{encoded_ast}" because it is not in self.rules.')

  # UNVERIFIABLE RULES RELATED
  def update_unverifiable_rules(self, encoded_ast: str, rule: TRuleBase) -> None:
    assert isinstance(encoded_ast, str), f'Unexpected type {type(encoded_ast)}'
    assert isinstance(rule, TRuleBase), f'Unexpected type {type(rule)}'
    assert self.get_rule_ref(rule) is not None, \
      'Rule must be in self.rules to be added to unverifiable rules'
    existing = self._unverifiable_rules.setdefault(encoded_ast, [])
    if rule not in existing:
      existing.append(rule)

  def get_unverifiable_rules(self, encoded_ast: str) -> List[TRuleBase]:
    assert isinstance(encoded_ast, str), f'Unexpected type {type(encoded_ast)}'
    assert encoded_ast in self._unverifiable_rules, f'No unverifiable rules for "{encoded_ast}"'
    return self._unverifiable_rules[encoded_ast]

  def unverifiable_rules_exist(self, encoded_ast: str) -> bool:
    assert isinstance(encoded_ast, str), f'Unexpected type {type(encoded_ast)}'
    return encoded_ast in self._unverifiable_rules

  def merge_unverifiable_rules_from(self, ruleset_serialized: dict) -> None:
    '''
    Check docs for merge_verified_rules_from().
    '''
    assert isinstance(ruleset_serialized, dict), f'Unexpected type {type(ruleset_serialized)}'
    kv_pairs = list(ruleset_serialized.get('unverifiable_rules', {}).items())
    for idx, (encoded_ast, serialized_trules) in enumerate(kv_pairs):
      print(f'Merging unverifiable rules: {idx+1}/{len(kv_pairs)}', end='\r')
      for serialized_trule in serialized_trules:
        other_rule = TRuleBase.from_dict(serialized_trule)
        rule = self.get_rule_ref(other_rule)  # None if rule not in self.rules
        if rule:
          self.update_unverifiable_rules(encoded_ast, rule)
        else:
          logger.warning(f'Ignoring unverifiable rule for "{encoded_ast}" because it is not in self.rules.')

  def get_verified_rule_hashes(self) -> Dict[str, List[str]]:
    '''
    Return compact hash payload for verified rules.
    '''
    payload: Dict[str, List[str]] = {}
    for encoded_ast, rules in self._verified_rules.items():
      rule_hashes: List[str] = []
      for rule in rules:
        rule_hash = rule.to_rule_hash()
        if rule_hash in rule_hashes:
          continue
        rule_hashes.append(rule_hash)
      if len(rule_hashes) > 0:
        payload[encoded_ast] = rule_hashes
    return payload

  def get_unverifiable_rule_hashes(self) -> Dict[str, List[str]]:
    '''
    Return compact hash payload for unverifiable rules.
    '''
    payload: Dict[str, List[str]] = {}
    for encoded_ast, rules in self._unverifiable_rules.items():
      rule_hashes: List[str] = []
      for rule in rules:
        rule_hash = rule.to_rule_hash()
        if rule_hash in rule_hashes:
          continue
        rule_hashes.append(rule_hash)
      if len(rule_hashes) > 0:
        payload[encoded_ast] = rule_hashes
    return payload

  # OTHER METHODS
  def get_rule_idx_in_matcher_group(self, rule: TRuleBase) -> int:
    '''
    Get the index of a rule in its matcher group.
    '''
    sig = rule.get_matcher_signature()
    if sig not in self.matcher_groups:
      raise ValueError(f'No matcher group with signature {sig}')
    matcher_group = self.matcher_groups[sig]
    for idx, r in enumerate(matcher_group):
      if r == rule:
        return idx
    raise ValueError(f'Rule is not in the ruleset: {rule}')

  def add_all_rules_from_missing_matcher_groups(
    self, matcher_groups: Dict[str, List[TRuleBase]]
  ) -> List[TRuleBase]:
    '''
    Return a list of all rules, for matcher signatures that are in `matcher_groups`,
    use the rules from `matcher_groups` and for the rest use the rules from `self.matcher_groups`.
    Example:
    self.matcher_groups   matcher_groups   result
    {a, b, c}             {a}              {a}
    {d}                                    {d}
    {e, f}                {e}              {e}
    {g, h, i, j}                           {g, h, i, j}
    '''
    trules = []
    for mat_sig, mat_gr_rules in self.matcher_groups.items():
      if mat_sig in matcher_groups:
        trules.extend(matcher_groups[mat_sig])
      else:
        trules.extend(mat_gr_rules)
    return trules

  def get_choice_options_from_verified_rules(
    self,
    code: str
  ) -> List[Tuple[Tuple[int, int, int], List[int]]]:
    '''
    Given a code string, self.rules, and self._verified_rules
    return a list of choices for all choicable nodes in `code`
    according to self._verified_rules.
    '''
    choices = []

    dgast, dgann = d_ast_parse.parse_text_dbg(code, 'py')
    choicable_nodes = pvpy.ChoicableNodeExtractor.extract_choicable_nodes(code)

    for choicable_node in choicable_nodes:
      choicable_range_cursor = d_ast_parse.get_range_cursor(dgast, choicable_node.get_node_id())
      all_range_cursors = d_ast_parse.get_all_range_cursors_under(choicable_range_cursor)
      for range_cursor in all_range_cursors:
        range_cursor_encoded = d_ast_parse.range_cursor_encode(range_cursor, dgann, code)
        if range_cursor_encoded not in self._verified_rules:
          continue
        vrf_rules = self._verified_rules[range_cursor_encoded]
        assert len(vrf_rules) > 0, 'There should be at least one verified rule'
        if Config.prefer_shorter_rules:
          vrf_rules.sort(key=lambda r: len(r.to_rule_str()))
        choice_identifier = d_ast_parse.range_cursor_to_choice_identifier(range_cursor)
        choice_idxs = []
        for vrf_rule in vrf_rules:
          rule_idx_in_matcher_group = self.get_rule_idx_in_matcher_group(vrf_rule)
          choice_idxs.append(rule_idx_in_matcher_group)
        choices.append((choice_identifier, choice_idxs))

    choices = sorted(choices, key=lambda x: x[0])  # sort by choice identifier
    return choices

  # RULESET TO RULESET
  def extend(self, other_ruleset: Ruleset) -> None:
    '''
    Extend self by adding everything from other_ruleset.
    '''
    assert isinstance(other_ruleset, Ruleset), f'Expected other_ruleset to be Ruleset, got {type(other_ruleset)}'
    self._extend_rules(other_ruleset.rules)
    self.merge_verified_rules_from(other_ruleset.to_dict())
    self.merge_unverifiable_rules_from(other_ruleset.to_dict())

  # SERIALIZATION METHODS
  def to_str_ruleset(self) -> str:
    '''
    Convert the ruleset to a plain string representation.
    '''
    return '\n\n'.join([rule.to_rule_str() for rule in self.rules])

  def to_dict(self) -> dict:
    '''
    Serialize the Ruleset to a dict.
    '''
    res = {
      'type': 'Ruleset',
      'rules': [rule.to_dict() for rule in self.rules],
      'verified_rules': {enc: [vrf_rule.to_dict() for vrf_rule in vrf_rules] for enc, vrf_rules in self._verified_rules.items()},
      'unverifiable_rules': {
        k: [r.to_dict() for r in v] for k, v in self._unverifiable_rules.items()
      },
    }
    return res

  @classmethod
  def from_starting_ruleset(cls, starting_ruleset: str) -> Ruleset:
    '''
    Create a Ruleset from a plain string representation of starting rules.
    '''
    ruleset = cls()
    rules_parsed = d_grammar_rules.parse_analyze_rules_optim(starting_ruleset)
    ruleset._extend_rules(map(StartingTRule, rules_parsed))
    return ruleset

  @classmethod
  def from_dict(cls, ruleset_serialized: dict) -> Ruleset:
    '''
    Create a Ruleset from a serialized dict.
    '''
    assert ruleset_serialized['type'] == 'Ruleset', 'Expected type to be Ruleset'
    ruleset = cls()
    # ruleset.rules and ruleset.matcher_groups
    ruleset._extend_rules(map(TRuleBase.from_dict,
                              ruleset_serialized['rules']))
    # ruleset._verified_rules
    ruleset.merge_verified_rules_from(ruleset_serialized)
    # ruleset._unverifiable_rules
    ruleset.merge_unverifiable_rules_from(ruleset_serialized)
    return ruleset

  @classmethod
  def format_str_ruleset(cls, ruleset_str: str) -> str:
    '''
    Format a string representation of a ruleset.
    '''
    rules_parsed, _ = d_grammar_rules.parse_analyze_rules(ruleset_str)
    formatted_rules = [d_grammar_rules.pretty_rule(rule_parsed) for rule_parsed in rules_parsed]
    return '\n\n'.join(formatted_rules)
