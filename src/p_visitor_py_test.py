import unittest
from typing import Dict, List, Tuple

import d_ast_parse
import p_consts
import p_utils
import p_visitor as pvis
import p_visitor_py as pvpy


logger = p_utils.setup_logger(__name__)


class TestParametrizableVariablesCollector(unittest.TestCase):
  def setUp(self):
    self.snippets_dir = p_consts.TEST_ARTIFACTS_DIR / 'py' / 'TestParametrizableVariablesCollector'
    self.src_lang = 'py'
    self.parser = p_consts.PARSER_DICT[self.src_lang]
    self.param_collector = pvpy.ParametrizableVariablesCollector()

  def load_tree_from(self, subject_name: str) -> pvpy.Tree:
    for fpath in self.snippets_dir.iterdir():
      if fpath.name.startswith(subject_name):
        snippet_text = p_utils.read_text(fpath)
        ts_tree = self.parser.parse(bytes(snippet_text, 'utf8'))
        tree = pvpy.Tree.from_ts_tree(ts_tree)
        return tree
    raise FileNotFoundError(f"No file starting with '{subject_name}' found in {self.snippets_dir}")

  def test_identifier_in_keyword_argument(self):
    code = '''while i < j:
    print(id_wpyb, id_xafp=id_evw)
    break'''
    ts_tree = self.parser.parse(bytes(code, 'utf8'))
    tree = pvpy.Tree.from_ts_tree(ts_tree)
    self.param_collector.visit(tree.root_node)
    self.assertCountEqual(self.param_collector.get_parametrizable_identifiers(), ['i', 'j', 'id_wpyb', 'id_evw'])


class TestPrettyPrinter(unittest.TestCase):
  def setUp(self):
    self.snippets_dir = p_consts.TEST_ARTIFACTS_DIR / 'py' / 'TestPrettyPrinter'
    self.skel_fixtures_dir = p_consts.TEST_ARTIFACTS_DIR / 'p-visitor-py' / 'pretty-printer'
    self.maxDiff = None

  def test_all_gfg(self):
    for fpath in sorted(self.snippets_dir.glob('G*.py')):
      subject_name = fpath.stem[:5]
      subject_code = fpath.read_text().strip()
      with self.subTest(subject_name=subject_name):
        tree = pvpy.Tree.from_str(subject_code)
        pp_code = pvpy.PrettyPrinter(indent_with='    ').visit(tree.root_node).strip()
        self.assertEqual(subject_code, pp_code)

  def test_all_leetcode(self):
    for fpath in sorted(self.snippets_dir.glob('L*.py')):
      subject_name = fpath.stem[:5]
      # tree-sitter version we are using cannot parse it correctly
      if subject_name == 'L0986':
        continue
      subject_code = fpath.read_text().strip()
      with self.subTest(subject_name=subject_name):
        tree = pvpy.Tree.from_str(subject_code)
        pp_code = pvpy.PrettyPrinter(indent_with='    ').visit(tree.root_node).strip()
        self.assertEqual(subject_code, pp_code)


class TestLogStatementsIndexer(unittest.TestCase):
  def setUp(self):
    self.fixtures_dir_path = p_consts.TEST_ARTIFACTS_DIR / 'p-visitor-py' / 'log-statements-indexer'
    self.maxDiff = None

  def get_fixtures(self, fixture_id: str) -> None:
    prog_in = self.fixtures_dir_path / f'{fixture_id}-in.py'
    prog_out = self.fixtures_dir_path / f'{fixture_id}-out.py'
    return p_utils.read_text(prog_in), p_utils.read_text(prog_out)


class TestLoggableValueExtractor(unittest.TestCase):
  def setUp(self):
    self.src_lang = 'py'
    self.parser = p_consts.PARSER_DICT[self.src_lang]
    self.pp = pvpy.PrettyPrinter(indent_with='    ')
    self.maxDiff = None

  def get_ast(self, snippet) -> pvis.AbstractNode:
    ts_tree = self.parser.parse(bytes(snippet, 'utf-8'))
    tree = pvpy.Tree.from_ts_tree(ts_tree)
    assert tree.root_node is not None
    assert tree.root_node.node_type == 'module'
    assert len(tree.root_node.children) == 1, 'snippet must contain a single statement'
    return tree.root_node.children[0]

  def extract_loggable_values(self, snippet):
    ast = self.get_ast(snippet)
    extractor = pvpy.LoggableValueExtractor()
    extractor.visit(ast)
    loggable_nodes = extractor.get_loggable_nodes()
    loggable_values = [self.pp.visit(node).strip() for node in loggable_nodes]
    return loggable_values

  def test_single_assignment(self):
    # Test a simple assignment
    snippet = 'x = 10'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['x'])

    snippet = 'num = 10'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['num'])

    snippet = 'lo = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['lo'])

  def test_list_01(self):
    snippet = 't[size] = len(t)'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['t[size]'])

  def test_list_02(self):
    snippet = 'a[0] = 10'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['a[0]'])

  def test_list_03(self):
    snippet = 'dp[i + a] = 10'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp[i + a]'])

  def test_list_04(self):
    snippet = 'countA[a[i]] = countA[a[i]] + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['countA[a[i]]'])

  def test_list_05(self):
    snippet = 'hash_0[abs(i)] = hash_0.get(abs(i), 0) + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['hash_0[abs(i)]'])

  def test_list_06(self):
    snippet = 'table[i // 2] = table[i // 2] + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['table[i // 2]'])

  def test_list_07(self):
    snippet = 'visited[arr[i] - Min] = True'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['visited[arr[i] - Min]'])

  def test_list_08(self):
    snippet = 'temp[(j + arr[i]) % m] = temp[(j + arr[i]) % m] + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['temp[(j + arr[i]) % m]'])

  def test_list_09(self):
    snippet = 'frequency[ord(str_0[i]) - 97] = frequency.get(ord(str_0[i]) - 97, 0) + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['frequency[ord(str_0[i]) - 97]'])

  def test_list_10(self):
    snippet = 'count[ord(str_0[i])] = count.get(ord(str_0[i]), 0) + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['count[ord(str_0[i])]'])

  def test_list_11(self):
    snippet = 'mp[arr[i] + arr[j]] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['mp[arr[i] + arr[j]]'])

  def test_list_12(self):
    snippet = 'c[arr[i] % 3] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['c[arr[i] % 3]'])

  def test_list_13(self):
    snippet = 'hash_negative[-difference] = hash_negative.get(-difference, 0) + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['hash_negative[-difference]'])

  def test_list_14(self):
    snippet = 'st[len(st) - 1] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['st[len(st) - 1]'])

  def test_tuple_list_duplicate_01(self):
    snippet = 'a[lo], a[mid] = 0, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['a[lo]', 'a[mid]'])

  def test_tuple_list_duplicate_02(self):
    snippet = 'num[0], num[small] = 0, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['num[0]', 'num[small]'])

  def test_tuple_list_duplicate_03(self):
    snippet = 'num[i], num[rightMin[i]] = 0, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['num[i]', 'num[rightMin[i]]'])

  def test_tuple_list_duplicate_04(self):
    snippet = 'arr[i], arr[i + 1] = 0, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['arr[i]', 'arr[i + 1]'])

  def test_tuple_list_01(self):
    snippet = 'a[i], b[j] = 0, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['a[i]', 'b[j]'])

  def test_matrix_01(self):
    snippet = 'LCSuff[i][j] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['LCSuff[i][j]'])

  def test_matrix_02(self):
    snippet = 'mat[i][0] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['mat[i][0]'])

  def test_matrix_03(self):
    snippet = 'mat[0][j] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['mat[0][j]'])

  def test_matrix_04(self):
    snippet = 'P[i][i + 1] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['P[i][i + 1]'])

  def test_matrix_05(self):
    snippet = 'dp[0][0] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp[0][0]'])

  def test_matrix_06(self):
    snippet = 'dp[i + 1][j + 1] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp[i + 1][j + 1]'])

  def test_matrix_07(self):
    snippet = 'dp[i + 1][j] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp[i + 1][j]'])

  def test_tuple_01(self):
    snippet = 'a, b, c = 1, 2, 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['a', 'b', 'c'])

  def test_tuple_02(self):
    snippet = 'pos, neg = 1, -1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['pos', 'neg'])

  def test_tuple_03(self):
    snippet = 'pPrevPrev, pPrev, pCurr, pNext = 1, 1, 1, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['pPrevPrev', 'pPrev', 'pCurr', 'pNext'])

  def test_tuple_duplicate_01(self):
    snippet = 'a, a = 1, 2'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['a'])

  def test_3d_matrix_01(self):
    snippet = 'dp[1][0][0] = 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp[1][0][0]'])

  def test_3d_matrix_02(self):
    snippet = 'dp[i][j][0] = 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp[i][j][0]'])

  def test_3d_matrix_03(self):
    snippet = 'dp[l][r][k] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp[l][r][k]'])

  def test_method_call(self):
    snippet = 'chars.remove(s[i])'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['chars'])

  def test_method_call_on_subscript(self):
    snippet = 'matrix[i].remove(num)'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['matrix[i]'])

    snippet = 'matrix[i][j].remove(num)'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['matrix[i][j]'])


class TestLoggableIdentifierExtractor(unittest.TestCase):
  def setUp(self):
    self.src_lang = 'py'
    self.parser = p_consts.PARSER_DICT[self.src_lang]
    self.maxDiff = None

  def get_ast(self, snippet) -> pvis.AbstractNode:
    ts_tree = self.parser.parse(bytes(snippet, 'utf-8'))
    tree = pvpy.Tree.from_ts_tree(ts_tree)
    assert tree.root_node is not None
    assert tree.root_node.node_type == 'module'
    assert len(tree.root_node.children) == 1, 'snippet must contain a single statement'
    return tree.root_node.children[0]

  def extract_loggable_values(self, snippet) -> List[str]:
    ast = self.get_ast(snippet)
    extractor = pvpy.LoggableIdentifierExtractor()
    extractor.visit(ast)
    loggable_values = extractor.get_loggable_identifiers()
    return loggable_values

  def test_single_assignment(self):
    # Test a simple assignment
    snippet = 'x = 10'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['x'])

    snippet = 'num = 10'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['num'])

    snippet = 'lo = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['lo'])

  def test_list_01(self):
    snippet = 't[size] = len(t)'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['t'])

  def test_list_02(self):
    snippet = 'a[0] = 10'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['a'])

  def test_list_03(self):
    snippet = 'dp[i + a] = 10'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp'])

  def test_list_04(self):
    snippet = 'countA[a[i]] = countA[a[i]] + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['countA'])

  def test_list_05(self):
    snippet = 'hash_0[abs(i)] = hash_0.get(abs(i), 0) + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['hash_0'])

  def test_list_06(self):
    snippet = 'table[i // 2] = table[i // 2] + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['table'])

  def test_list_07(self):
    snippet = 'visited[arr[i] - Min] = True'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['visited'])

  def test_list_08(self):
    snippet = 'temp[(j + arr[i]) % m] = temp[(j + arr[i]) % m] + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['temp'])

  def test_list_09(self):
    snippet = 'frequency[ord(str_0[i]) - 97] = frequency.get(ord(str_0[i]) - 97, 0) + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['frequency'])

  def test_list_10(self):
    snippet = 'count[ord(str_0[i])] = count.get(ord(str_0[i]), 0) + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['count'])

  def test_list_11(self):
    snippet = 'mp[arr[i] + arr[j]] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['mp'])

  def test_list_12(self):
    snippet = 'c[arr[i] % 3] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['c'])

  def test_list_13(self):
    snippet = 'hash_negative[-difference] = hash_negative.get(-difference, 0) + 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['hash_negative'])

  def test_list_14(self):
    snippet = 'st[len(st) - 1] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['st'])

  def test_tuple_list_duplicate_01(self):
    snippet = 'a[lo], a[mid] = 0, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['a'])

  def test_tuple_list_duplicate_02(self):
    snippet = 'num[0], num[small] = 0, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['num'])

  def test_tuple_list_duplicate_03(self):
    snippet = 'num[i], num[rightMin[i]] = 0, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['num'])

  def test_tuple_list_duplicate_04(self):
    snippet = 'arr[i], arr[i + 1] = 0, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['arr'])

  def test_tuple_list_01(self):
    snippet = 'a[i], b[j] = 0, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['a', 'b'])

  def test_matrix_01(self):
    snippet = 'LCSuff[i][j] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['LCSuff'])

  def test_matrix_02(self):
    snippet = 'mat[i][0] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['mat'])

  def test_matrix_03(self):
    snippet = 'mat[0][j] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['mat'])

  def test_matrix_04(self):
    snippet = 'P[i][i + 1] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['P'])

  def test_matrix_05(self):
    snippet = 'dp[0][0] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp'])

  def test_matrix_06(self):
    snippet = 'dp[i + 1][j + 1] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp'])

  def test_matrix_07(self):
    snippet = 'dp[i + 1][j] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp'])

  def test_tuple_01(self):
    snippet = 'a, b, c = 1, 2, 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['a', 'b', 'c'])

  def test_tuple_02(self):
    snippet = 'pos, neg = 1, -1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['pos', 'neg'])

  def test_tuple_03(self):
    snippet = 'pPrevPrev, pPrev, pCurr, pNext = 1, 1, 1, 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['pPrevPrev', 'pPrev', 'pCurr', 'pNext'])

  def test_tuple_duplicate_01(self):
    snippet = 'a, a = 1, 2'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['a'])

  def test_3d_matrix_01(self):
    snippet = 'dp[1][0][0] = 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp'])

  def test_3d_matrix_02(self):
    snippet = 'dp[i][j][0] = 1'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp'])

  def test_3d_matrix_03(self):
    snippet = 'dp[l][r][k] = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['dp'])

  def test_method_call(self):
    snippet = 'chars.remove(s[i])'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['chars'])

  def test_method_call_on_subscript(self):
    snippet = 'matrix[i].remove(num)'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['matrix'])

    snippet = 'matrix[i][j].remove(num)'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['matrix'])

  def test_assignment_to_attribute_of_call_result(self):
    snippet = 'RedBlackTree_dlm_sibling(class_var).color = 0'
    loggable_values = self.extract_loggable_values(snippet)
    self.assertCountEqual(loggable_values, ['class_var'])


class TestDefinedFunctionNameExtractor(unittest.TestCase):
  def setUp(self):
    self.fixtures_dir_path = p_consts.TEST_ARTIFACTS_DIR / 'p-visitor-py' / 'defined-function-name-extractor'

  def get_snippet(self, fname: str) -> str:
    return p_utils.read_text(self.fixtures_dir_path / fname)

  def test_simple_001(self):
    snippet = 'def my_function():\n    pass'
    def_fn_names = pvpy.DefinedFunctionNameExtractor.get_defined_function_names(snippet)
    self.assertCountEqual(def_fn_names, ['my_function'])

  def test_simple_002(self):
    snippet = self.get_snippet('simple_002.py')
    def_fn_names = pvpy.DefinedFunctionNameExtractor.get_defined_function_names(snippet)
    self.assertCountEqual(def_fn_names, ['f_gold'])

  def test_nested_001(self):
    snippet = 'def outer_function():\n    def inner_function():\n        pass'
    def_fn_names = pvpy.DefinedFunctionNameExtractor.get_defined_function_names(snippet)
    self.assertCountEqual(def_fn_names, ['outer_function', 'inner_function'])

  def test_multiple_001(self):
    snippet = 'def func_one():\n    pass\n\ndef func_two():\n    pass'
    def_fn_names = pvpy.DefinedFunctionNameExtractor.get_defined_function_names(snippet)
    self.assertCountEqual(def_fn_names, ['func_one', 'func_two'])


class TestFunctionInvocationReplacer(unittest.TestCase):
  def setUp(self):
    self.fixtures_dir_path = p_consts.TEST_ARTIFACTS_DIR / 'p-visitor-py' / 'function-invocation-replacer'
    self.maxDiff = None

  def get_snippets(self, snippet_id: str) -> Tuple[str, str]:
    snippet = p_utils.read_text(self.fixtures_dir_path / f'{snippet_id}_in.py')
    gold = p_utils.read_text(self.fixtures_dir_path / f'{snippet_id}_out.py')
    return snippet, gold

  def test_all_int(self):
    NUM_TESTS = 47
    for i in range(1, NUM_TESTS + 1):
      snippet_id = f'int88888888_{i:03d}'
      with self.subTest(snippet_id=snippet_id):
        snippet, gold_snippet = self.get_snippets(snippet_id)
        replaced, replacement_done = pvpy.FunctionInvocationReplacer.replace_function_invocations(snippet, 'f_gold', 'f_gold', 88888888)
        self.assertTrue(replacement_done)
        self.assertEqual(replaced, gold_snippet)

  def test_all_true(self):
    NUM_TESTS = 47
    for i in range(1, NUM_TESTS + 1):
      snippet_id = f'true_{i:03d}'
      with self.subTest(snippet_id=snippet_id):
        snippet, gold_snippet = self.get_snippets(snippet_id)
        replaced, replacement_done = pvpy.FunctionInvocationReplacer.replace_function_invocations(snippet, 'f_gold', 'f_gold', True)
        self.assertTrue(replacement_done)
        self.assertEqual(replaced, gold_snippet)


class TestTreeGetNidNodeMap(unittest.TestCase):
  def setUp(self):
    self.gfg_snippets_dir = p_consts.TEST_ARTIFACTS_DIR / 'py' / 'TestPrettyPrinter'
    self.skel_snippets_dir = p_consts.TEST_ARTIFACTS_DIR / 'p-visitor-py' / 'tree-get-nid-node-map'
    self.skel_subjects = ['bst_clean.py']
    self.maxDiff = None

  def get_duoglot_style_ast(self, code: str, keep_text: bool) -> list:
    ast, _ = d_ast_parse.parse_text_dbg(code, 'py', keep_text=keep_text)
    return ast

  def get_tree(self, code: str) -> pvpy.Tree:
    tree = pvpy.Tree.from_str(code)
    return tree

  def compare_nid_node_maps(
    self,
    duoglot_map: Dict[int, str],
    ours_map: Dict[int, pvis.AbstractNode]
  ) -> None:
    self.assertEqual(set(duoglot_map.keys()), set(ours_map.keys()), 'Node ID sets do not match')
    for nid in duoglot_map.keys():
      self.assertEqual(duoglot_map[nid], ours_map[nid].node_type, f'Node types do not match for node ID {nid}')

  def test_all_gfg(self):
    for fpath in sorted(self.gfg_snippets_dir.glob('G*.py')):
      subject_code = fpath.read_text().strip()
      subject_name = fpath.stem[:5]
      with self.subTest(subject_name=subject_name):
        ast = self.get_duoglot_style_ast(subject_code, keep_text=False)
        ast_text = self.get_duoglot_style_ast(subject_code, keep_text=True)
        tree = self.get_tree(subject_code)
        nid_map = tree.root_node.get_nid_node_map()
        duoglot_nid_map = d_ast_parse.get_nid_ntype_map(ast, with_text=False)
        pirel_nid_map = d_ast_parse.get_nid_ntype_map(ast_text, with_text=True)
        self.compare_nid_node_maps(duoglot_nid_map, nid_map)
        self.compare_nid_node_maps(pirel_nid_map, nid_map)

  def test_all_skel(self):
    for subject_name in self.skel_subjects:
      fpath = self.skel_snippets_dir / subject_name
      subject_code = fpath.read_text().strip()
      with self.subTest(subject_name=subject_name):
        ast = self.get_duoglot_style_ast(subject_code, keep_text=False)
        ast_text = self.get_duoglot_style_ast(subject_code, keep_text=True)
        tree = self.get_tree(subject_code)
        nid_map = tree.root_node.get_nid_node_map()
        duoglot_nid_map = d_ast_parse.get_nid_ntype_map(ast, with_text=False)
        pirel_nid_map = d_ast_parse.get_nid_ntype_map(ast_text, with_text=True)
        self.compare_nid_node_maps(duoglot_nid_map, nid_map)
        self.compare_nid_node_maps(pirel_nid_map, nid_map)


class TestChoicableNodeExtractor(unittest.TestCase):
  def setUp(self):
    self.fixtures_dir = p_consts.TEST_ARTIFACTS_DIR / 'p-visitor-py' / 'choicable-node-extractor'
    self.maxDiff = None
    self.pp = pvpy.PrettyPrinter()

  def load_test(self, test_id: str) -> tuple:
    fpath = self.fixtures_dir / f'{test_id}.json'
    data = p_utils.read_json(fpath)
    return data['code'], data['choicable_nodes'], data['exclude_stat_nids']

  def test_all(self):
    test_ids = sorted([fpath.stem for fpath in self.fixtures_dir.glob('*.json')])
    for test_id in test_ids:
      with self.subTest(test_id=test_id):
        code, golden_choicable_nodes, exclude_stat_nids = self.load_test(test_id)
        choicable_nodes = pvpy.ChoicableNodeExtractor.extract_choicable_nodes(
          code,
          exclude_statement_nodes_ids=exclude_stat_nids
        )
        choicable_nodes_str = [self.pp.visit(node) for node in choicable_nodes]
        self.assertCountEqual(golden_choicable_nodes, choicable_nodes_str)


class TestBlockSecretFunInserter(unittest.TestCase):
  def setUp(self):
    self.fixtures_dir_path = p_consts.TEST_ARTIFACTS_DIR / 'p-visitor-py' / 'secret-function-inserter'
    self.maxDiff = None

  def get_snippets(self, snippet_id: str) -> Tuple[str, str]:
    snippet = p_utils.read_text(self.fixtures_dir_path / f'snippet_{snippet_id}_in.py')
    gold = p_utils.read_text(self.fixtures_dir_path / f'snippet_{snippet_id}_out.py')
    return snippet, gold

  def test_all_positive(self):
    for i in range(1, 10):
      with self.subTest(i=i):
        snippet, gold_snippet = self.get_snippets(f'{i:03d}')
        modified = pvpy.BlockSecretFunInserter.insert_secret_functions(snippet)
        self.assertEqual(modified, gold_snippet)

  def test_all_negative(self):
    for i in range(10, 22):
      with self.subTest(i=i):
        snippet, gold_snippet = self.get_snippets(f'{i:03d}')
        modified = pvpy.BlockSecretFunInserter.insert_secret_functions(snippet)
        self.assertEqual(modified, gold_snippet)
        print('%'*100)


if __name__ == '__main__':
  unittest.main()
