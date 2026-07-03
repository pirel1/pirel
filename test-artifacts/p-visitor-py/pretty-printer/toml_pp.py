import datetime
import re
def user_check_type(obj, _type):
    if hasattr(obj, '_class_name'):
        if "function" in str(_type):
            for i in obj._class_name.split(";"):
                if i == str(_type).split(" ")[1]:
                    return True
    else:
        return isinstance(obj, _type)
def SkelClass(class_name, super_class=None):
    Clz = None
    if super_class is None:
        Clz = type(class_name, (), {'_class_name': class_name})
    else:
        Clz = type(class_name, (super_class,), {'_class_name': class_name})
    return Clz()
def func_dict(*args):
    class_var = SkelClass('func_dict', dict)
    return class_var
def CommentValue(param_0, param_1, param_2, param_3):
    def __init__(val, comment, beginline, _dict):
        class_var.val = val
        separator = "\n" if beginline else " "
        class_var.comment = separator + comment
        class_var._dict = _dict
    def dump(dump_value_func):
        retstr = dump_value_func(class_var.val)
        return str(retstr) + class_var.comment
    class_var = SkelClass('CommentValue')
    class_var.__init__ = __init__
    class_var.dump = dump
    __init__(param_0, param_1, param_2, param_3)
    return class_var
def _strictly_valid_num(n):
    n = n.strip()
    if len(n) == 1:
        return True
    if n[0] == '+' or n[0] == '-':
        n = n[1:]
    return True
def loads(s, _dict=func_dict, decoder=None):
    def handle_keyname():
        nonlocal key, openstring, openstrchar, keyname, dottedkey, prev_key
        key += item
        if keyname == 1:
            if item.isspace():
                keyname = 2
                return "continue"
            elif item.isalnum() or item == '_' or item == '-':
                return "continue"
        elif keyname == 2:
            if item.isspace():
                return "continue"
        if item == '=':
            keyname = 0
            prev_key = key[:-1].rstrip()
            key = ''
            dottedkey = False
    def handle_single_quote_1():
        nonlocal multilinestr, openstring, openstrchar
        k = 1
        while sl[i - k] == "'":
            k += 1
            if k == 3:
                break
        if k == 3:
            multilinestr = not multilinestr
            openstring = multilinestr
        else:
            openstring = not openstring
        if openstring:
            openstrchar = "'"
        else:
            openstrchar = ""
    def handle_single_quote_2():
        nonlocal multilinestr, openstring, openstrchar
        oddbackslash = False
        k = 1
        tripquote = False
        while sl[i - k] == '"':
            k += 1
            if k == 3:
                tripquote = True
                break
        if k == 1 or (k == 3 and tripquote):
            while sl[i - k] == '\\':
                oddbackslash = not oddbackslash
                k += 1
        if not oddbackslash:
            if tripquote:
                multilinestr = not multilinestr
                openstring = multilinestr
            else:
                openstring = not openstring
        if openstring:
            openstrchar = '"'
        else:
            openstrchar = ""
    def handle_comment():
        j = i
        comment = ""
        while sl[j] != '\n':
            comment += s[j]
            sl[j] = ' '
            j += 1
        if not openarr:
            decoder.preserve_comment(line_no, prev_key, comment, beginline)
    def handle_backslash():
        nonlocal multilinestr, keyname, openstring, key, beginline, line_no
        if item == '\n':
            if openstring or multilinestr:
                if ((sl[i - 1] == "'" or sl[i - 1] == '"') and (sl[i - 2] == sl[i - 1])):
                    sl[i] = sl[i - 1]
                    if sl[i - 3] == sl[i - 1]:
                        sl[i - 3] = ' '
            elif openarr:
                sl[i] = ' '
            else:
                beginline = True
            line_no += 1
        elif beginline and sl[i] != ' ' and sl[i] != '\t':
            beginline = False
            if not keygroup and not arrayoftables:
                keyname = 1
                key += item
    def handle_bracket():
        nonlocal openarr, keygroup, arrayoftables
        if item == '[' and (not openstring and not keygroup and not arrayoftables):
            if beginline:
                if len(sl) > i + 1 and sl[i + 1] == '[':
                    arrayoftables = True
                else:
                    keygroup = True
            else:
                openarr += 1
        if item == ']' and not openstring:
            if keygroup:
                keygroup = False
            elif arrayoftables:
                if sl[i - 1] == ']':
                    arrayoftables = False
            else:
                openarr -= 1
    def handle_remaining():
        def handle_multikey():
            nonlocal multibackslash, multilinestr, multikey
            if multibackslash:
                multilinestr += line
            else:
                multilinestr += line
            multibackslash = False
            closed = False
            if len(line) > 2:
                closed = (line[-1] == multilinestr[0] and line[-2] == multilinestr[0] and line[-3] == multilinestr[0])
            if closed:
                value, vtype = decoder.load_value(multilinestr, True)
                currentlevel[multikey] = value
                multikey = None
                multilinestr = ""
            else:
                k = len(multilinestr) - 1
                while k > -1 and multilinestr[k] == '\\':
                    multibackslash = not multibackslash
                    k -= 1
                if multibackslash:
                    multilinestr = multilinestr[:-1]
                else:
                    multilinestr += "\n"
            return "continue"
        def handle_start_bracket():
            def handle_groupname():
                i = 0
                while i < len(groups):
                    groups[i] = groups[i].strip()
                    if len(groups[i]) > 0 and (groups[i][0] == '"' or groups[i][0] == "'"):
                        groupstr = groups[i]
                        j = i + 1
                        groups[i] = groupstr[1:-1]
                        groups[i + 1:j] = []
                    i += 1
            nonlocal line, currentlevel, arrayoftables
            arrayoftables = False
            if line[1] == '[':
                arrayoftables = True
                line = line[2:]
                splitstr = ']]'
            else:
                line = line[1:]
                splitstr = ']'
            i = 1
            quotesplits = decoder._get_split_on_quotes(line)
            quoted = False
            for quotesplit in quotesplits:
                if not quoted and splitstr in quotesplit:
                    break
                i += quotesplit.count(splitstr)
                quoted = not quoted
            line = line.split(splitstr, i)
            groups = splitstr.join(line[:-1]).split('.')
            handle_groupname()
            currentlevel = retval
            for i in range(len(groups)):
                group = groups[i]
                try:
                    currentlevel[group]
                    if i == len(groups) - 1:
                        if arrayoftables:
                            currentlevel[group].append(decoder.get_empty_table())
                except TypeError:
                    currentlevel = currentlevel[-1]
                    if group not in currentlevel:
                        currentlevel[group] = decoder.get_empty_table()
                except KeyError:
                    if i != len(groups) - 1:
                        implicitgroups.append(group)
                    currentlevel[group] = decoder.get_empty_table()
                    if i == len(groups) - 1 and arrayoftables:
                        currentlevel[group] = [decoder.get_empty_table()]
                currentlevel = currentlevel[group]
                if arrayoftables:
                    currentlevel = currentlevel[-1]
        nonlocal currentlevel
        s = ''.join(sl)
        s = s.split('\n')
        multikey = None
        multilinestr = ""
        multibackslash = False
        pos = 0
        for idx, line in enumerate(s):
            if idx > 0:
                pos += len(s[idx - 1]) + 1
            decoder.embed_comments(idx, currentlevel)
            if not multilinestr or multibackslash or '\n' not in multilinestr:
                line = line.strip()
            if line == "" and (not multikey or multibackslash):
                continue
            if multikey:
                act = handle_multikey()
                if act == "continue":
                    continue
            if line[0] == '[':
                handle_start_bracket()
            elif "=" in line:
                ret = decoder.load_line(line, currentlevel, multikey, multibackslash)
                if ret is not None:
                    multikey, multilinestr, multibackslash = ret
        return retval
    implicitgroups = []
    if decoder is None:
        decoder = TomlDecoder(_dict)
    retval = decoder.get_empty_table()
    currentlevel = retval
    sl = list(s)
    openarr = 0
    openstring = False
    openstrchar = ""
    multilinestr = False
    arrayoftables = False
    beginline = True
    keygroup = False
    dottedkey = False
    keyname = 0
    key = ''
    prev_key = ''
    line_no = 1
    for i, item in enumerate(sl):
        if item == '\r' and len(sl) > (i + 1) and sl[i + 1] == '\n':
            sl[i] = ' '
            continue
        if keyname:
            act = handle_keyname()
            if act == "continue":
                continue
        if item == "'" and openstrchar != '"':
            handle_single_quote_1()
        if item == '"' and openstrchar != "'":
            handle_single_quote_2()
        if item == '#' and (not openstring and not keygroup and not arrayoftables):
            act = handle_comment()
        handle_bracket()
        handle_backslash()
    return handle_remaining()
def _load_date(val):
    microsecond = 0
    tz = None
    try:
        if len(val) > 19:
            tz = TomlTz(val[19:].upper())
    except ValueError:
        tz = None
    if "-" not in val[1:]:
        return None
    try:
        if len(val) == 10:
            d = datetime.date(int(val[:4]), int(val[5:7]), int(val[8:10]))
        else:
            d = datetime.datetime(int(val[:4]), int(val[5:7]), int(val[8:10]), int(val[11:13]), int(val[14:16]), int(val[17:19]), microsecond, tz)
    except ValueError:
        return None
    return d
def _load_unicode_escapes(v, hexbytes, prefix):
    skip = False
    i = len(v) - 1
    while i > -1 and v[i] == '\\':
        skip = not skip
        i -= 1
    for hx in hexbytes:
        if skip:
            skip = False
            i = len(hx) - 1
            v += prefix
            v += hx
            continue
        hxb = ""
        i = 0
        hxblen = 4
        hxb = ''.join(hx[i:i + hxblen]).lower()
        v += unichr(int(hxb, 16))
        v += str(hx[len(hxb):])
    return v
def _unescape(v):
    i = 0
    backslash = False
    while i < len(v):
        if backslash:
            backslash = False
            if v[i] in _escapes:
                v = v[:i - 1] + _escape_to_escapedchars[v[i]] + v[i + 1:]
            elif v[i] == '\\':
                v = v[:i - 1] + v[i:]
            elif v[i] == 'u' or v[i] == 'U':
                i += 1
            continue
        elif v[i] == '\\':
            backslash = True
        i += 1
    return v
def DynamicInlineTableDict(*args):
    class_var = SkelClass('DynamicInlineTableDict', dict)
    return class_var
def TomlDecoder(param_0):
    def __init__(_dict):
        class_var._dict = _dict
    def get_empty_table():
        return class_var._dict()
    def get_empty_inline_table():
        return DynamicInlineTableDict()
    def load_inline_object(line, currentlevel, multikey, multibackslash):
        candidate_groups = line[1:-1].split(",")
        groups = []
        while len(candidate_groups) > 0:
            candidate_group = candidate_groups.pop(0)
            _, value = candidate_group.split('=', 1)
            value = value.strip()
            if ((value[0] == value[-1] and value[0] in ('"', "'")) or (value[0] in '-0123456789' or value in ('true', 'false') or (value[0] == "[" and value[-1] == "]") or (value[0] == '{' and value[-1] == '}'))):
                groups.append(candidate_group)
        for group in groups:
            status = class_var.load_line(group, currentlevel, multikey, multibackslash)
    def _get_split_on_quotes(line):
        doublequotesplits = line.split('"')
        quoted = False
        quotesplits = []
        if len(doublequotesplits) > 1 and "'" in doublequotesplits[0]:
            singlequotesplits = doublequotesplits[0].split("'")
            doublequotesplits = doublequotesplits[1:]
            while len(singlequotesplits) % 2 == 0 and len(doublequotesplits):
                singlequotesplits[-1] += '"' + doublequotesplits[0]
                doublequotesplits = doublequotesplits[1:]
                if "'" in singlequotesplits[-1]:
                    singlequotesplits = (singlequotesplits[:-1] + singlequotesplits[-1].split("'"))
            quotesplits += singlequotesplits
        for doublequotesplit in doublequotesplits:
            if quoted:
                quotesplits.append(doublequotesplit)
            else:
                quotesplits += doublequotesplit.split("'")
                quoted = not quoted
        return quotesplits
    def load_line(line, currentlevel, multikey, multibackslash):
        i = 1
        quotesplits = class_var._get_split_on_quotes(line)
        quoted = False
        for quotesplit in quotesplits:
            if not quoted and '=' in quotesplit:
                break
            i += quotesplit.count('=')
            quoted = not quoted
        pair = line.split('=', i)
        strictly_valid = _strictly_valid_num(pair[-1])
        if _number_with_underscores.match(pair[-1]):
            pair[-1] = pair[-1].replace('_', '')
        while len(pair[-1]) and (pair[-1][0] != ' ' and pair[-1][0] != '\t' and pair[-1][0] != "'" and pair[-1][0] != '"' and pair[-1][0] != '[' and pair[-1][0] != '{' and pair[-1].strip() != 'true' and pair[-1].strip() != 'false'):
            try:
                float(pair[-1])
                break
            except ValueError:
                pass
            if _load_date(pair[-1]) is not None:
                break
            i += 1
            pair = line.split('=', i)
            if strictly_valid:
                strictly_valid = _strictly_valid_num(pair[-1])
        pair = ['='.join(pair[:-1]).strip(), pair[-1].strip()]
        if '.' in pair[0]:
            if '"' in pair[0] or "'" in pair[0]:
                quotesplits = class_var._get_split_on_quotes(pair[0])
                quoted = False
                levels = []
                for quotesplit in quotesplits:
                    if quoted:
                        levels.append(quotesplit)
                    else:
                        levels += [level.strip() for level in quotesplit.split('.')]
                    quoted = not quoted
            for level in levels[:-1]:
                if level == "":
                    continue
                if level not in currentlevel:
                    currentlevel[level] = class_var.get_empty_table()
                currentlevel = currentlevel[level]
            pair[0] = levels[-1].strip()
        elif (pair[0][0] == '"' or pair[0][0] == "'") and (pair[0][-1] == pair[0][0]):
            pair[0] = _unescape(pair[0][1:-1])
        k, koffset = class_var._load_line_multiline_str(pair[1])
        if k > -1:
            while k > -1 and pair[1][k + koffset] == '\\':
                multibackslash = not multibackslash
                k -= 1
            if multibackslash:
                multilinestr = pair[1][:-1]
            else:
                multilinestr = pair[1] + "\n"
            multikey = pair[0]
        else:
            value, vtype = class_var.load_value(pair[1], strictly_valid)
        try:
            currentlevel[pair[0]]
        except KeyError:
            if multikey:
                return multikey, multilinestr, multibackslash
            else:
                currentlevel[pair[0]] = value
    def _load_line_multiline_str(p):
        poffset = 0
        if len(p) < 3:
            return -1, poffset
        if p[0] != '"' and p[0] != "'":
            return -1, poffset
        if p[1] != p[0] or p[2] != p[0]:
            return -1, poffset
        if len(p) > 5 and p[-1] == p[0] and p[-2] == p[0] and p[-3] == p[0]:
            return -1, poffset
        return len(p) - 1, poffset
    def load_value(v, strictly_valid):
        def handle_remaining():
            nonlocal v
            if parsed_date is not None:
                return (parsed_date, "date")
            itype = "int"
            neg = False
            if v[0] == '-':
                neg = True
                v = v[1:]
            elif v[0] == '+':
                v = v[1:]
            v = v.replace('_', '')
            if '.' in v or ('x' not in v and ('e' in v or 'E' in v)):
                v = float(v)
                itype = "float"
            if itype == "int":
                v = int(v, 0)
            if neg:
                return (0 - v, itype)
            return (v, itype)
        if v == 'true':
            return (True, "bool")
        elif v == 'false':
            return (False, "bool")
        elif v[0] == '"' or v[0] == "'":
            quotechar = v[0]
            testv = v[1:].split(quotechar)
            triplequote = False
            triplequotecount = 0
            if len(testv) > 1 and testv[0] == '' and testv[1] == '':
                testv = testv[2:]
                triplequote = True
            closed = False
            for tv in testv:
                if tv == '':
                    if triplequote:
                        triplequotecount += 1
                    else:
                        closed = True
                else:
                    oddbackslash = False
                    i = -1
                    j = tv[i]
                    while j == '\\':
                        oddbackslash = not oddbackslash
                        i -= 1
                        j = tv[i]
                    if not oddbackslash:
                        if not triplequote or triplequotecount > 1:
                            closed = True
                        else:
                            triplequotecount = 0
            if quotechar == '"':
                for prefix in ["\\u", "\\U"]:
                    if prefix in v:
                        hexbytes = v.split(prefix)
                        v = _load_unicode_escapes(hexbytes[0], hexbytes[1:], prefix)
                v = _unescape(v)
            if len(v) > 1 and v[1] == quotechar and (len(v) < 3 or v[1] == v[2]):
                v = v[2:-2]
            return (v[1:-1], "str")
        elif v[0] == '[':
            return (class_var.load_array(v), "array")
        elif v[0] == '{':
            inline_object = class_var.get_empty_inline_table()
            class_var.load_inline_object(v, inline_object, False, False)
            return (inline_object, "inline_object")
        else:
            parsed_date = _load_date(v)
            return handle_remaining()
    def _load_array_isstrarray(a):
        a = a[1:-1].strip()
        if a != '' and (a[0] == '"' or a[0] == "'"):
            return True
        return False
    def load_array(a):
        retval = []
        a = a.strip()
        if '[' not in a[1:-1] or "" != a[1:-1].split('[')[0].strip():
            strarray = class_var._load_array_isstrarray(a)
            if not a[1:-1].strip().startswith('{'):
                a = a[1:-1].split(',')
            else:
                new_a = []
                start_group_index = 1
                end_group_index = 2
                in_str = False
                while end_group_index < len(a[1:]):
                    if a[end_group_index] == '"' or a[end_group_index] == "'":
                        in_str = not in_str
                    if in_str or a[end_group_index] != '}':
                        end_group_index += 1
                        continue
                    end_group_index += 1
                    new_a.append(a[start_group_index:end_group_index])
                    start_group_index = end_group_index + 1
                    while (start_group_index < len(a[1:]) and a[start_group_index] != '{'):
                        start_group_index += 1
                    end_group_index = start_group_index + 1
                a = new_a
            b = 0
            if strarray:
                while b < len(a) - 1:
                    ab = a[b].strip()
                    b += 1
        else:
            al = list(a[1:-1])
            a = []
            openarr = 0
            j = 0
            for i in range(len(al)):
                if al[i] == '[':
                    openarr += 1
                elif al[i] == ']':
                    openarr -= 1
                elif al[i] == ',' and not openarr:
                    a.append(''.join(al[j:i]))
                    j = i + 1
            a.append(''.join(al[j:]))
        for i in range(len(a)):
            a[i] = a[i].strip()
            if a[i] != '':
                nval, ntype = class_var.load_value(a[i], True)
                retval.append(nval)
        return retval
    def preserve_comment(line_no, key, comment, beginline):
        pass
    def embed_comments(idx, currentlevel):
        pass
    class_var = SkelClass('TomlDecoder')
    class_var.__init__ = __init__
    class_var.get_empty_table = get_empty_table
    class_var.get_empty_inline_table = get_empty_inline_table
    class_var.load_inline_object = load_inline_object
    class_var._get_split_on_quotes = _get_split_on_quotes
    class_var.load_line = load_line
    class_var._load_line_multiline_str = _load_line_multiline_str
    class_var.load_value = load_value
    class_var._load_array_isstrarray = _load_array_isstrarray
    class_var.load_array = load_array
    class_var.preserve_comment = preserve_comment
    class_var.embed_comments = embed_comments
    __init__(param_0)
    return class_var
def TomlPreserveCommentDecoder(param_0):
    def __init__(_dict):
        class_var.saved_comments = {}
    def preserve_comment(line_no, key, comment, beginline):
        class_var.saved_comments[line_no] = (key, comment, beginline)
    def embed_comments(idx, currentlevel):
        if idx not in class_var.saved_comments:
            return
        key, comment, beginline = class_var.saved_comments[idx]
        currentlevel[key] = CommentValue(currentlevel[key], comment, beginline, class_var._dict)
    class_var = TomlDecoder(param_0)
    class_var._class_name = 'TomlPreserveCommentDecoder;' + class_var._class_name
    class_var.__init__ = __init__
    class_var.preserve_comment = preserve_comment
    class_var.embed_comments = embed_comments
    __init__(param_0)
    return class_var
def dumps(o, encoder):
    retval = ""
    if encoder is None:
        encoder = TomlEncoder(o.__class__, False)
    addtoretval, sections = encoder.dump_sections(o, "")
    retval += addtoretval
    while sections:
        newsections = encoder.get_empty_table()
        for section in sections:
            addtoretval, addtosections = encoder.dump_sections(sections[section], section)
            if addtoretval or (not addtoretval and not addtosections):
                if retval and retval[-2:] != "\n\n":
                    retval += "\n"
                retval += "[" + section + "]\n"
                if addtoretval:
                    retval += addtoretval
            for s in addtosections:
                newsections[section + "." + s] = addtosections[s]
        sections = newsections
    return retval
def _dump_str(v):
    v = "%r" % v
    singlequote = v.startswith("'")
    if singlequote or v.startswith('"'):
        v = v[1:-1]
    if singlequote:
        v = v.replace("\\'", "'")
        v = v.replace('"', '\\"')
    v = v.split("\\x")
    while len(v) > 1:
        i = -1
        v[0] = v[0].replace("\\\\", "\\")
        joinx = v[0][i] != "\\"
        while v[0][:i] and v[0][i] == "\\":
            joinx = not joinx
            i -= 1
        if joinx:
            joiner = "x"
        else:
            joiner = "u00"
        v = [v[0] + joiner + v[1]] + v[2:]
    return str('"' + v[0] + '"')
def _dump_float(v):
    return "{}".format(v).replace("e+0", "e+").replace("e-0", "e-")
def _dump_bool(v):
    return str(v).lower()
def _dump_int(v):
    return v
def TomlEncoder(param_0, param_1):
    def __init__(_dict, preserve):
        class_var._dict = _dict
        class_var.preserve = preserve
        class_var.dump_funcs = {"str": _dump_str, "list": class_var.dump_list, "bool": _dump_bool, "int": _dump_int, "float": _dump_float}
    def get_empty_table():
        return class_var._dict()
    def dump_list(v):
        retval = "["
        for u in v:
            retval += " " + str(class_var.dump_value(u)) + ","
        retval += "]"
        return retval
    def dump_value(v):
        dump_fn = None
        for t in class_var.dump_funcs:
            if (t == "str" and isinstance(v, str) or t == "list" and isinstance(v, list) or t == "bool" and isinstance(v, bool) or t == "int" and isinstance(v, int) or t == "float" and isinstance(v, float) or t == "CommentValue" and user_check_type(v, CommentValue)):
                dump_fn = class_var.dump_funcs[t]
                break
        if dump_fn is None and hasattr(v, '__iter__'):
            dump_fn = class_var.dump_funcs["list"]
        return dump_fn(v) if dump_fn is not None else class_var.dump_funcs["str"](v)
    def dump_sections(o, sup):
        retstr = ""
        if sup != "" and sup[-1] != ".":
            sup += '.'
        retdict = class_var._dict()
        arraystr = ""
        for section in o:
            section = str(section)
            qsection = section
            if not isinstance(o[section], dict):
                arrayoftables = False
                if isinstance(o[section], list):
                    for a in o[section]:
                        if isinstance(a, dict):
                            arrayoftables = True
                if arrayoftables:
                    for a in o[section]:
                        arraytabstr = "\n"
                        arraystr += "[[" + sup + qsection + "]]\n"
                        s, d = class_var.dump_sections(a, sup + qsection)
                        if s:
                            arraystr += s
                        while d:
                            newd = class_var._dict()
                            for dsec in d:
                                s1, d1 = class_var.dump_sections(d[dsec], sup + qsection + "." + dsec)
                                if s1:
                                    arraytabstr += ("[" + sup + qsection + "." + dsec + "]\n")
                                    arraytabstr += s1
                            d = newd
                        arraystr += arraytabstr
                else:
                    if o[section] is not None:
                        retstr += (qsection + " = " + str(class_var.dump_value(o[section])) + '\n')
            else:
                retdict[qsection] = o[section]
        retstr += arraystr
        return (retstr, retdict)
    class_var = SkelClass('TomlEncoder')
    class_var.__init__ = __init__
    class_var.get_empty_table = get_empty_table
    class_var.dump_list = dump_list
    class_var.dump_value = dump_value
    class_var.dump_sections = dump_sections
    __init__(param_0, param_1)
    return class_var
def TomlArraySeparatorEncoder(param_0, param_1, param_2):
    def __init__(_dict, preserve, separator):
        class_var.separator = separator
    class_var = TomlEncoder(param_0, param_1)
    class_var._class_name = 'TomlArraySeparatorEncoder;' + class_var._class_name
    class_var.__init__ = __init__
    __init__(param_0, param_1, param_2)
    return class_var
def TomlPreserveCommentEncoder(param_0, param_1):
    def __init__(_dict, preserve):
        class_var.dump_funcs["CommentValue"] = lambda v: v.dump(class_var.dump_value)
    class_var = TomlEncoder(param_0, param_1)
    class_var._class_name = 'TomlPreserveCommentEncoder;' + class_var._class_name
    class_var.__init__ = __init__
    __init__(param_0, param_1)
    return class_var
def TomlTz(param_0):
    def __init__(toml_offset):
        if toml_offset == "Z":
            class_var._raw_offset = "+00:00"
        else:
            class_var._raw_offset = toml_offset
        class_var._sign = -1 if class_var._raw_offset[0] == '-' else 1
        class_var._hours = int(class_var._raw_offset[1:3])
        class_var._minutes = int(class_var._raw_offset[4:6])
    def utcoffset(dt):
        return class_var._sign * datetime.timedelta(hours=class_var._hours, minutes=class_var._minutes)
    class_var = SkelClass('TomlTz', datetime.tzinfo)
    class_var.__init__ = __init__
    class_var.utcoffset = utcoffset
    __init__(param_0)
    return class_var
def convert(v):
    if isinstance(v, list):
        return [convert(vv) for vv in v]
    elif v.get('type', None) is None or v.get('value', None) is None:
        return {k: convert(vv) for (k, vv) in v.items()}
    elif v['type'] == 'string':
        return v['value']
    elif v['type'] == 'integer':
        return int(v['value'])
    elif v['type'] == 'float':
        return float(v['value'])
    elif v['type'] == 'bool':
        return True if v['value'] == 'true' else False
    elif v['type'] in ['datetime', 'datetime-local', 'date-local', 'time-local']:
        return loads('a=' + v['value'])['a']
def tag(value):
    if isinstance(value, dict):
        return {k: tag(v) for (k, v) in value.items()}
    elif isinstance(value, list):
        return [tag(v) for v in value]
    elif isinstance(value, str):
        return {'type': 'string', 'value': value}
    elif isinstance(value, bool):
        return {'type': 'bool', 'value': str(value).lower()}
    elif isinstance(value, int):
        return {'type': 'integer', 'value': str(value)}
    elif isinstance(value, float):
        return {'type': 'float', 'value': repr(value)}
    elif user_check_type(value, datetime.datetime):
        return {'type': 'datetime-local' if value.tzinfo is None else 'datetime', 'value': value.isoformat().replace('+00:00', 'Z')}
    elif user_check_type(value, datetime.date):
        return {'type': 'date-local', 'value': value.isoformat()}
def get_input(test_case_name=None):
    decode_input = ""
    with open("toml.d/example.toml") as f:
        decode_input = f.read()
    decode_input = decode_input.split("################################################################################\n")
    for i in decode_input:
        if "## " + test_case_name in i:
            return i
def tester(name):
    decode_input = get_input(name)
    decode_result = loads(decode_input, func_dict, None)
    decode_result = tag(decode_result)
    encode_input = {k: convert(v) for (k, v) in decode_result.items()}
    encode_result = dumps(encode_input, None)
def test_bug_148():
    assert 'a = "\\u0064"\n' == dumps({'a': '\\x64'}, None)
    assert 'a = "\\\\x64"\n' == dumps({'a': '\\\\x64'}, None)
    assert 'a = "\\\\\\u0064"\n' == dumps({'a': '\\\\\\x64'}, None)
def test__dict():
    assert isinstance(loads(TEST_STR, func_dict, None), dict)
def test_dict_decoder():
    _test_dict_decoder = TomlDecoder(func_dict)
    assert isinstance(loads(TEST_STR, func_dict, _test_dict_decoder), dict)
def test_array_sep():
    encoder = TomlArraySeparatorEncoder(func_dict, False, ",\t")
    d = {"a": [1, 2, 3]}
    tmp = dumps(d, encoder)
    o = loads(tmp, func_dict, None)
    tmp2 = dumps(o, encoder)
    assert o == loads(tmp2, func_dict, None)
def test_tuple():
    d = {"a": (3, 4)}
    encoder = TomlEncoder(func_dict, False)
    tmp = dumps(d, encoder)
    o = loads(tmp, func_dict, None)
    tmp2 = dumps(o, encoder)
    assert o == loads(tmp2, func_dict, None)
def test_commutativity():
    encoder = TomlEncoder(func_dict, False)
    tmp = dumps(TEST_DICT, encoder)
    o = loads(tmp, func_dict, None)
    tmp2 = dumps(o, encoder)
    assert o == loads(tmp2, func_dict, None)
test_str = """[[products]]
name = "Nail"
sku = 284758393
# This is a comment
color = "gray" # Hello World
# name = { first = 'Tom', last = 'Preston-Werner' }
# arr7 = [
#  1, 2, 3
# ]
# lines  = '''
# The first newline is
# trimmed in raw strings.
#   All other whitespace
#   is preserved.
# '''

[animals]
color = "gray" # col
fruits = "apple" # a = [1,2,3]
a = 3
b-comment = "a is 3"
"""
def test_comment_preserve_decoder_encoder():
    tmp = loads(test_str, func_dict, TomlPreserveCommentDecoder(func_dict))
    s = dumps(tmp, TomlPreserveCommentEncoder(func_dict, False))
    assert len(s) == len(test_str) and sorted(test_str) == sorted(s)
def test():
    tester("Comment")
    tester("Boolean")
    tester("Integer")
    tester("Float")
    tester("Table")
    tester("Inline Table")
    tester("String")
    tester("Array")
    tester("Array of Tables")
    tester("Datetime")
    test_bug_148()
    test__dict()
    test_dict_decoder()
    test_array_sep()
    test_tuple()
    test_commutativity()
    test_comment_preserve_decoder_encoder()
    additional_test()
    additional_test2()
    additional_test3()
    additional_test4()
    additional_test5()
def unichr(s):
    return chr(s)
def additional_test():
    decoder = TomlDecoder(func_dict)
    cur = {}
    multikey = False
    multibackslash = False
    decoder.load_line("'a.x'=2=3", cur, multikey, multibackslash)
    assert (cur == {'a.x': {'=2': 3}})
def additional_test2():
    decoder = TomlDecoder(func_dict)
    input_str = "[{'x' = 1}]"
    res = decoder.load_array(input_str)
    assert (res == [{'x': 1}])
    input_str = "[{'x' = 1}, {'y' = 2}]"
    res = decoder.load_array(input_str)
    assert (res == [{'x': 1}, {'y': 2}])
def additional_test3():
    v = "abc\\"
    hexbytes = ['0064']
    prefix = 'u'
    res = _load_unicode_escapes(v, hexbytes, prefix)
    assert (res == 'abc\\u0064')
def additional_test4():
    v = "\\\\"
    res = _unescape(v)
    assert (res == '\\')
    v = "\\u"
    res = _unescape(v)
    assert (res == '\\u')
def additional_test5():
    s = """['"test"']"""
    t = loads(s, func_dict, None)
    assert (t == {'"test"': {}})
    s = """["abc"]"""
    t = loads(s, func_dict, None)
    assert (t == {'abc': {}})
TIME_RE = re.compile(r"([0-9]{2}):([0-9]{2}):([0-9]{2})(\.([0-9]{3,6}))?")
_number_with_underscores = re.compile('([0-9])(_([0-9]))*')
_escapes = ['0', 'b', 'f', 'n', 'r', 't', '"']
_escapedchars = ['\0', '\b', '\f', '\n', '\r', '\t', '\"']
_escape_to_escapedchars = dict(zip(_escapes, _escapedchars))
TEST_STR = """
[a]\r
b = 1\r
c = 2
"""
TEST_DICT = {"a": {"b": 1, "c": 2}}
test()