import copy
import json
import re
import sys

import d_code_beautify
import d_consts

_additional_child_immediate_nts = {
  "js": [
    "js.string",
    "js.template_chars",
    "js.template_string",
    "js.template_substitution"
  ],
  "py": [
    "py.string",
    "py.escape_interpolation",
    "py.escape_sequence",
    "py.string_content",
    "py.interpolation"
  ]
}
# exclude immediate nts    # old js: ['"\\""', '"\'"']
_additional_self_immediates_before = {
  "js": [
    '","',
    '"("',
    '")"',
    '"."'
  ],
  "py": [
    '":"',
    '"("',
    '")"',
    '","',
    '"."',
    '"["',
    '"]"'
  ]
}
_additional_self_immediates_after = {
  "js": [
    '"("',
    '")"',
    '"."'
  ],
  "py": [
    '"("',
    '")"',
    '"."',
    '"["',
    ']"'
  ]
}


_RE_JS_PY_U_ESCAPE = re.compile(r'^\\U([0-9a-fA-F]{8})$')


def normalize_js_escape_sequence_token(token: str) -> str:
  '''
  Normalize Python-only unicode escapes when emitting JavaScript code.

  Python supports `\\UXXXXXXXX` in strings, but JavaScript does not.
  Convert it to JS code-point escape form `\\u{...}`.
  '''
  match = _RE_JS_PY_U_ESCAPE.fullmatch(token)
  if not match:
    return token

  code_point = int(match.group(1), 16)
  if code_point > 0x10FFFF:
    # Keep original token for impossible/invalid code points.
    return token
  return f'\\u{{{code_point:x}}}'


def pretty_mapanno_ast(ast, lang, grammar=None, annotation=None):
  '''
  used in DuoGlot translation
  '''
  py_pretty_indent = 0
  py_indented_spaces = {
    x: ((" " * x) if x >= 0 else "ERROR_INDENT")
      for x in [-4, -2, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48]
  }
  py_indented_newline = {
    x: "\n" + py_indented_spaces[x] for x in py_indented_spaces
  }

  def _py_hack_init_inner_fun():
    nonlocal py_pretty_indent
    py_pretty_indent = 0

  def _py_hack_indent_inner_fun(strs):
    nonlocal py_pretty_indent
    py_pretty_indent += 2
    return True

  def _py_hack_dedent_inner_fun(strs):
    nonlocal py_pretty_indent
    py_pretty_indent -= 2
    return True

  _hack_init_dict = {
    "py": _py_hack_init_inner_fun,
  }
  _hack_replacer_dict = {
    "js": {
      "EXT._automatic_semicolon": (lambda strs: ";\n", lambda strs : len(strs) == 0 or strs[-1] != "}"),
    },
    "py": {
      "EXT._newline": (lambda strs: py_indented_newline[py_pretty_indent], lambda strs: True),
      "EXT._indent": (lambda strs: py_indented_newline[py_pretty_indent], _py_hack_indent_inner_fun),
      "EXT._dedent": (lambda strs:  py_indented_newline[py_pretty_indent], _py_hack_dedent_inner_fun)
    },
  }

  strs = []
  strswithspaces = []

  replacer_dict = _hack_replacer_dict[lang] if lang in _hack_replacer_dict else {}
  addi_immediates_before = _additional_self_immediates_before[lang] if lang in _additional_self_immediates_before else []
  addi_immediates_after = _additional_self_immediates_after[lang] if lang in _additional_self_immediates_after else []
  addi_immediate_nts = _additional_child_immediate_nts[lang] if lang in _additional_child_immediate_nts else []

  if lang in _hack_init_dict:
    _hack_init_dict[lang]()

  immediate_after_flag = False

  # ranges_by_ntid = {}
  def _decode_terminal_token(raw_token):
    try:
      return str(json.loads(raw_token))
    except Exception:
      return raw_token

  def _escape_js_string_fragment(text, quote_char):
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace(quote_char, "\\" + quote_char)
    # JS string literals cannot contain raw newlines or line separators.
    escaped = escaped.replace("\n", "\\n")
    escaped = escaped.replace("\r", "\\r")
    escaped = escaped.replace("\u2028", "\\u2028")
    escaped = escaped.replace("\u2029", "\\u2029")
    return escaped

  def _find_js_string_quote_char(ast_node):
    '''
    Return the quote char for a js.string node if available.
    '''
    if not isinstance(ast_node, list) or len(ast_node) < 3:
      return None
    if ast_node[0] != "js.string":
      return None
    for child in ast_node[2:]:
      if not isinstance(child, list) or len(child) != 3:
        continue
      if child[0] not in ("string", "istring"):
        continue
      tok = _decode_terminal_token(child[2])
      if tok in ("'", '"'):
        return tok
    return None

  def _ast_contains_nt(ast_node, target_nt):
    if not isinstance(ast_node, list) or len(ast_node) < 1:
      return False
    if ast_node[0] == target_nt:
      return True
    for sub_child in ast_node[2:]:
      if isinstance(sub_child, list) and _ast_contains_nt(sub_child, target_nt):
        return True
    return False

  def _next_terminal_token(children, cur_idx):
    for next_child in children[cur_idx + 1:]:
      if not isinstance(next_child, list):
        continue
      if len(next_child) == 3 and (next_child[0] == "string" or next_child[0] == "istring"):
        return _decode_terminal_token(next_child[2])
    return None

  def _should_skip_js_rest_trailing_comma(nt_name, children, child_idx, terminal_raw):
    if lang != "js" or nt_name != "js.formal_parameters":
      return False
    if terminal_raw != '","':
      return False
    if _next_terminal_token(children, child_idx) != ")":
      return False
    for prev_child in children[:child_idx]:
      if isinstance(prev_child, list) and _ast_contains_nt(prev_child, "js.rest_pattern"):
        return True
    return False

  def _pretty_ast_rec_inner_fun(ast, js_string_quote_char=None):
    nonlocal immediate_after_flag
    assert len(ast) >= 2
    nt_name, node_id = ast[0], ast[1]
    # assert node_id not in ranges_by_ntid
    # ranges_by_ntid[node_id] = []
    children = ast[2:]
    is_child_immediate = nt_name in addi_immediate_nts
    anno = None
    mapanno = None
    if lang == "js" and nt_name == "js.string":
      js_string_quote_char = _find_js_string_quote_char(ast) or js_string_quote_char

    # main loop
    for child_idx, child in enumerate(children):

      if isinstance(child, list):

        child_nt_name = child[0]
        if child_nt_name == "anno":
          anno = {x[0]: x[1] for x in child[1:]}
          if lang == "py" and nt_name == "py.string":
            if not immediate_after_flag and len(strs) > 0:
              assert (strs[-1] != "EXT._newline" and strs[-1] != "EXT._indent" and strs[-1] != "EXT._dedent")
              strswithspaces.append((" ", None))
            else:
              immediate_after_flag = False

            stype = json.loads(anno['"stype"'])
            if len(stype) > 0:
              copied_mapanno = copy.copy(mapanno)
              strs.append(json.loads(anno['"stype"']))
              strswithspaces.append((stype, copied_mapanno))
            # ranges_by_ntid[node_id].append(copied_mapanno)

        elif child_nt_name == "mapanno":
          mapanno = {x[0]: x[1] for x in child[1:]}

        elif child_nt_name == "string" or child_nt_name == "istring":
          assert len(child) == 3
          if _should_skip_js_rest_trailing_comma(nt_name, children, child_idx, child[2]):
            continue
          child_mapanno = {x[0]: x[1] for x in child[1][1:]}
          if child_mapanno["ex_id"] is None:
            child_mapanno["ex_id"] = mapanno["ex_id"]
          is_imm = child_nt_name == "istring"
          thestr = child[2]

          if not is_imm and not is_child_immediate and len(strs) > 0:
            if immediate_after_flag:
              pass
            elif thestr not in addi_immediates_before:
              if lang == "py":
                if strs[-1] != "EXT._newline" and strs[-1] != "EXT._indent" and strs[-1] != "EXT._dedent":
                  strswithspaces.append((" ", None))
              else:
                strswithspaces.append((" ", None))

          immediate_after_flag = False
          if thestr in addi_immediates_after and not is_child_immediate:
            immediate_after_flag = True

          toadd = thestr
          if lang == "py" and nt_name == "py.string" and (anno is not None) and thestr == '"\\""':
            toadd = anno['"quote"']
          toadd = _decode_terminal_token(toadd)
          if (
            lang == "js"
            and nt_name == "js.escape_sequence"
          ):
            toadd = normalize_js_escape_sequence_token(toadd)
          if (
            lang == "js"
            and nt_name == "js.string_fragment"
            and js_string_quote_char in ("'", '"')
          ):
            toadd = _escape_js_string_fragment(toadd, js_string_quote_char)
          assert toadd != ""
          strs.append(toadd)
          strswithspaces.append((toadd, child_mapanno))
          # ranges_by_ntid[node_id].append(child_mapanno)
        else:
          _pretty_ast_rec_inner_fun(child, js_string_quote_char)

      else:
        if not isinstance(child, str): print("ERROR! child has type:", type(child))
        assert isinstance(child, str)
        assert child.startswith("EXT.")
        replacer_found = False
        for k in replacer_dict:
          terminalf, cond = replacer_dict[k]
          if child == k:
            replacer_found = True
            if cond(strs):
              terminal = terminalf(strs)
              if lang == "py":
                if len(strs) > 0 and (strs[-1] == "EXT._newline" or strs[-1] == "EXT._dedent" or strs[-1] == "EXT._indent") and child == "EXT._dedent":
                  assert strs[-1] != "EXT._indent"
                  strs.pop()
                  strswithspaces.pop()
                if k in ["EXT._newline", "EXT._dedent", "EXT._indent"]:
                  immediate_after_flag = True
              strs.append(k)
              strswithspaces.append((terminal, None))
        if not replacer_found: print("# ERROR! no replacer for " + child)
        assert replacer_found
    # end of _pretty_ast_rec_inner_fun()

  # return final result
  _pretty_ast_rec_inner_fun(ast)
  ss = []
  offset = 0
  ranges_by_exid = {}
  for s, mapanno in strswithspaces:
    ss.append(s)
    if mapanno is not None:
      mapanno["range"] = (offset, offset + len(s))
      # assert isinstance(s, str)
      mapanno["str"] = s
      eid = mapanno["ex_id"]
      if eid not in ranges_by_exid:
        ranges_by_exid[eid] = []
      ranges_by_exid[eid].append(mapanno)
    offset += len(s)
  return "".join(ss), ranges_by_exid


def elem_list_to_mapanno_ast(all_elem_nodes):

  def _strip_comma(x):
    assert x.startswith('"') and x.endswith('"')
    return x[1:-1]

  def _add_comma(x):
    repx = x.replace("\"", "\\\"")
    return f'"{repx}"'

  def _node_elem_to_empty_ast_node(node_elem):
    # return: parent id, empty ast node, is_immediate
    if not len(node_elem) == 5:
      print("node length ERROR:", node_elem)
      assert "NODE_LENGTH_ERROR" == 0
    nid = node_elem[0]
    parid = node_elem[1]
    node_type = node_elem[2]
    info_or_strval = node_elem[3]
    ex_id = node_elem[4]
    mapanno = ["mapanno", ("ex_id", ex_id)]
    if node_type == "NT":
      name, ann = info_or_strval
      nt_node = [_strip_comma(name), nid, mapanno] if ann is None else [_strip_comma(name), nid, mapanno, ann]
      return parid, nt_node
    elif node_type == "T":
      assert nid is None
      return parid, ["string", mapanno, _add_comma(info_or_strval)]
    elif node_type == "IT":
      assert nid is None
      return parid, ["istring", mapanno, _add_comma(info_or_strval)]
    elif node_type == "V":
      assert nid is None
      return parid, ["string", mapanno, info_or_strval]
    elif node_type == "IV":
      assert nid is None
      return parid, ["istring", mapanno, info_or_strval]
    elif node_type == "EXT":
      return parid, "EXT." + info_or_strval
    else:
      print("# ERROR. Unknown node type:", node_type)
      assert 0 == "_node_elem_to_empty_ast_node: unknown node type"

  if len(all_elem_nodes) == 0:
    return None
  if all_elem_nodes[0][1] is not None:
    print("# ERROR get_translated_ast. all_elem_nodes[0][1] is not None:", all_elem_nodes)
    assert False
  assert all_elem_nodes[0][0] == 0
  ast_root_node = None
  ast_dict = {}
  for elem in all_elem_nodes:
    parid, ast_node = _node_elem_to_empty_ast_node(elem)
    if parid is None:
      ast_root_node = ast_node
      ast_dict[ast_node[1]] = ast_node
      continue
    if not parid in ast_dict:
      print(f"# ERROR: {parid} not in dict.", list(dict.keys(ast_dict)))
      assert False
    par_node = ast_dict[parid]
    par_node.append(ast_node)
    if isinstance(ast_node, list):
      if len(ast_node) < 2:
        print("# ERROR: get_translated_ast ast_node unexpected:", ast_node)
        assert False
      if not (ast_node[0] == "string" or ast_node[0] == "istring"):
        assert not (ast_node[0] == "anno" or ast_node[0] == "mapanno")
        astid = ast_node[1]
        assert astid is not None
        assert astid not in ast_dict
        ast_dict[astid] = ast_node
    else:
      assert isinstance(ast_node, str) or isinstance(ast_node, int)
  # the result is the root elem
  return ast_root_node


def ast_to_code(tar_ast, tarlang):
  if tar_ast is None: return ""
  prettied_code, map_by_exid = pretty_mapanno_ast(tar_ast, tarlang)
  beautified_code, mapping_list = d_code_beautify.beautify(tarlang, prettied_code)
  for exid in map_by_exid:
    for mapanno in map_by_exid[exid]:
      rg = mapanno["range"]
      if not (rg[1] > rg[0] and prettied_code[rg[0]:rg[1]] == mapanno["str"]):
        print("ERROR! invalid range:", mapanno, file=sys.stderr)
        assert "string mismatch or range length 0" == 0
      try:
        newrg = (mapping_list[rg[0]], mapping_list[rg[1]-1]+1)
      except Exception as e:
        print("ERROR! code map calculation failure: " + str(e), file=sys.stderr)
        print("-------- prettied code:", file=sys.stderr)
        print(prettied_code, file=sys.stderr)
        print("-------- problematic beautify and mapping:", file=sys.stderr)
        print(beautified_code, file=sys.stderr)
        print("-------- problematic range and mapping:", file=sys.stderr)
        print("rg:", rg, file=sys.stderr)
        print("mapping_list:", mapping_list, file=sys.stderr)
        assert "beautified code failed to calculate mapping" == 0
      if newrg[0] is None or newrg[1] is None:
        print("ERROR! after beautify mapping lost:", prettied_code[rg[0]:rg[1]], mapanno, file=sys.stderr)
        assert "after beautify mapping lost" == 0
      mapanno["range"] = newrg
  return beautified_code, map_by_exid
