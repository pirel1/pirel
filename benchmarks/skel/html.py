import os
import re

EXAMPLE_HTML = '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">\n    <!-- Comment -->\n    <![CDATA[ CDATA ]]>\n    <a href="http://www.python.org%20">&nbsp;Python&#123;&#x213;&#x00;&#xd800;&&#x1;&accute;&nbspf;</a>\n    <H1>Python</H1>\n    <script src="script.js">function f(){console.log("sds")}</script>\n    <![IF [condition]>\n             This is an invalid marked section declaration\n     <![ENDIF]-->\n     <img src="image.jpg" alt="Example Image" />\n     <>This is an invalid tag</>\n     &lt;%30%&gt;&##&&#x30;{}()-=]:>}}L><<;<;>;@?;>!;>;;\n     <div>&lt;&#x65;</div>\n     <!fff></!fff>\n     <?we><?we?>\n    '
INVALID_CHARREFS = { 0x00: '\ufffd'}
INVALID_CODEPOINTS = {0x1: ""}

CHARREF_REGULAR_EXP = re.compile('&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\\t\\n\\f <&#;]{1,32};?)')
DECLNAME = re.compile('[a-zA-Z][-_.a-zA-Z0-9]*\\s*')
DECLSTRINGLIT = re.compile('(\\\'[^\\\']*\\\'|"[^"]*")\\s*')
MARKEDSECTIONCLOSE = re.compile(']\\s*]\\s*>')
MSMARKEDSECTIONCLOSE = re.compile(']\\s*>')
INTERESTING_NORMAL = re.compile('[&<]')
INCOMPLETE = re.compile('&[a-zA-Z#]')
ENTITYREF = re.compile('&([a-zA-Z][-.a-zA-Z0-9]*)[^a-zA-Z0-9]')
CHARREF = re.compile('&#(?:[0-9]+|[xX][0-9a-fA-F]+)[^0-9a-fA-F]')
STARTTAGOPEN = re.compile('^<[a-zA-Z]')
PICLOSE = re.compile('>')
COMMENTCLOSE = re.compile('--\\s*>')
TAGFIND_TOLERANT = re.compile('^([a-zA-Z][^\\t\\n\\r\\f />\\x00]*)(?:\\s|/(?!>))*')
ATTRFIND_TOLERANT = re.compile('((?<=[\\\'"\\s/])[^\\s/>][^\\s/=>]*)(\\s*=+\\s*(\\\'[^\\\']*\\\'|"[^"]*"|(?![\\\'"])[^>\\s]*))?(?:\\s|/(?!>))*')
LOCATESTARTTAGEND_TOLERANT = re.compile('<[a-zA-Z][^\\t\\n\\r\\f />\\x00]*(?:[\\s/]*(?:(?<=[\'\\"\\s/])[^\\s/>][^\\s/=>]*(?:\\s*=+\\s*(?:\'[^\']*\'|\\"[^\\"]*\\"|(?![\'\\"])[^>\\s]*))?\\s*(?:\\s|/(?!>))*)*)?\\s*')
ENDENDTAG = re.compile('>')
ENDTAGFIND = re.compile('^</\\s*([a-zA-Z][-.a-zA-Z0-9:_]*)\\s*>')
HTML5 = {'amp;': '&', 'gt;': '>', 'lt;': '<', 'nbsp': '\xa0', 'nbsp;': '\xa0'}

CDATA_CONTENT_ELEMENTS = ['script', 'style']
SCAN_NAME_DEFAULT = [None, -1]
LISTENER_EVENT_LIST = []


def SkelClass(name):
    Clz = type(name, (), {'_class_name': name})
    return Clz




def escape(s, quote):
    s = s.replace('&', '&amp;')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    if quote:
        s = s.replace('"', '&quot;')
        s = s.replace("'", '&#x27;')
    return s
def _replace_charref(s):
    if s[0] == '#':
        num = int(s[2:].replace(';', ''), 16) if s[1] in 'xX' else int(s[1:].replace(';', ''))
        if num in INVALID_CHARREFS:
            return INVALID_CHARREFS[num]
        if 0xD800 <= num and num <= 0xDFFF or num > 0x10FFFF:
            return '\uFFFD'
        if num in INVALID_CODEPOINTS:
            return ''
        return chr(num)
    if s in HTML5:
        return HTML5[s]
    for x in range(len(s) - 1, 1, -1):
        if s[:x] in HTML5:
            return HTML5[s[:x]] + s[x:]
    return '&' + s
def unescape(s):
    if '&' not in s:
        return s
    start = 0
    while True:
        match = CHARREF_REGULAR_EXP.search(s[start:])
        if not match:
            break
        replacement = _replace_charref(match.group(1))
        _start_idx = start + match.start()
        _end_idx = _start_idx + len(match.group(0))
        s = s[:_start_idx] + replacement + s[_end_idx:]
        start = _start_idx + len(replacement)
    return s
def ParserBase():
    def ParserBase_dlm___init__():
        pass
    def getpos():
        return (class_var.lineno, class_var.offset)
    def updatepos(i, j):
        if i >= j:
            return j
        rawdata = class_var.rawdata
        nlines = rawdata.count('\n', i, j)
        if nlines:
            class_var.lineno = class_var.lineno + nlines
            pos = rawdata.rindex('\n', i, j)
            class_var.offset = j - (pos + 1)
        else:
            class_var.offset = class_var.offset + j - i
        return j
    def parse_declaration(i):
        rawdata = class_var.rawdata
        j = i + 2
        if rawdata[i:i + 2] != '<!':
            raise Exception('unexpected call to parse_declaration()')
        if rawdata[j:j + 1] == '>':
            return j + 1
        if rawdata[j:j + 1] in ('-', ''):
            return -1
        n = len(rawdata)
        if rawdata[j:j + 2] == '--':
            return class_var.parse_comment(i, 1)
        elif rawdata[j] == '[':
            return class_var.parse_marked_section(i, 1)
        else:
            decltype, j = class_var._scan_name(j, i)
        if j < 0:
            return j
        if decltype == 'doctype':
            class_var._decl_otherchars = ''
        while j < n:
            c = rawdata[j]
            if c == '>':
                data = rawdata[i + 2:j]
                if decltype == 'doctype':
                    class_var.handle_decl(data)
                else:
                    class_var.unknown_decl(data)
                return j + 1
            if c in '"\'':
                match = DECLSTRINGLIT.match(rawdata[j:])
                if not match:
                    return -1
                j = match.start() + len(match.group(0)) + j
            elif c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ':
                name, j = class_var._scan_name(j, i)
            elif c in class_var._decl_otherchars:
                j = j + 1
            elif c == '[':
                if decltype == 'doctype':
                    j = class_var._parse_doctype_subset(j + 1, i)
                elif decltype in {'attlist', 'linktype', 'link', 'element'}:
                    raise Exception("unsupported '[' char in %s declaration" % decltype)
                else:
                    raise Exception("unexpected '[' char in declaration")
            else:
                raise Exception('unexpected %r char in declaration' % rawdata[j])
            if j < 0:
                return j
        return -1
    def parse_marked_section(i, report):
        rawdata = class_var.rawdata
        if rawdata[i:i + 3] != '<![':
            raise Exception('unexpected call to parse_marked_section()')
        sectName, j = class_var._scan_name(i + 3, i)
        if j < 0:
            return j
        standard_sections = ['temp', 'cdata', 'ignore', 'include', 'rcdata']
        ms_office_sections = ['if', 'else', 'endif']
        match = None
        if sectName in standard_sections:
            match = MARKEDSECTIONCLOSE.search(rawdata[i + 3:])
        elif sectName in ms_office_sections:
            match = MSMARKEDSECTIONCLOSE.search(rawdata[i + 3:])
        else:
            raise Exception('unknown status keyword %r in marked section' % rawdata[i + 3:j])
        if not match:
            return -1
        if report:
            j = match.start(0) + i + 3
            class_var.unknown_decl(rawdata[i + 3:j])
        return match.start(0) + len(match.group(0)) + i + 3
    def parse_comment(i, report):
        rawdata = class_var.rawdata
        if rawdata[i:i + 4] != '<!--':
            raise Exception('unexpected call to parse_comment()')
        match = COMMENTCLOSE.search(rawdata[i + 4:])
        if not match:
            return -1
        if report:
            j = match.start(0) + i + 4
            class_var.handle_comment(rawdata[i + 4:j])
        return match.start(0) + len(match.group(0)) + i + 4
    def _parse_doctype_subset(i, declstartpos):
        rawdata = class_var.rawdata
        n = len(rawdata)
        j = i
        while j < n:
            c = rawdata[j]
            if c == '<':
                s = rawdata[j:j + 2]
                if s == '<':
                    return -1
                if s != '<!':
                    class_var.updatepos(declstartpos, j + 1)
                    raise Exception('unexpected char in internal subset (in %r)' % s)
                if j + 2 == n:
                    return -1
                if j + 4 > n:
                    return -1
                if rawdata[j:j + 4] == '<!--':
                    j = class_var.parse_comment(j, 0)
                    if j < 0:
                        return j
                    continue
                name, j = class_var._scan_name(j + 2, declstartpos)
                if j == -1:
                    return -1
                if name not in ['attlist', 'element', 'entity', 'notation']:
                    class_var.updatepos(declstartpos, j + 2)
                    raise Exception('unknown declaration %r in internal subset' % name)
                meth = getattr(class_var, '_parse_doctype_' + name)
                j = meth(j, declstartpos)
                if j < 0:
                    return j
            elif c == '%':
                if j + 1 == n:
                    return -1
                s, j = class_var._scan_name(j + 1, declstartpos)
                if j < 0:
                    return j
                if rawdata[j] == ';':
                    j = j + 1
            elif c == ']':
                j = j + 1
                while j < n and rawdata[j].isspace():
                    j = j + 1
                if j < n:
                    if rawdata[j] == '>':
                        return j
                    class_var.updatepos(declstartpos, j)
                    raise Exception('unexpected char after internal subset')
                else:
                    return -1
            elif c.isspace():
                j = j + 1
            else:
                class_var.updatepos(declstartpos, j)
                raise Exception('unexpected char %r in internal subset' % c)
        return -1
    def _parse_doctype_element(i, declstartpos):
        name, j = class_var._scan_name(i, declstartpos)
        if j == -1:
            return -1
        rawdata = class_var.rawdata
        if '>' in rawdata[j:]:
            return rawdata.find('>', j) + 1
        return -1
    def _parse_doctype_attlist(i, declstartpos):
        pass
    def _parse_doctype_notation(i, declstartpos):
        name, j = class_var._scan_name(i, declstartpos)
        if j < 0:
            return j
        rawdata = class_var.rawdata
        while True:
            c = rawdata[j:j + 1]
            if not c:
                return -1
            if c == '>':
                return j + 1
            if c in '\'"':
                match = DECLSTRINGLIT.match(rawdata[j:])
                if not match:
                    return -1
                j = j + match.start() + len(match.group(0))
            else:
                name, j = class_var._scan_name(j, declstartpos)
                if j < 0:
                    return j
    def _parse_doctype_entity(i, declstartpos):
        rawdata = class_var.rawdata
        if rawdata[i:i + 1] == '%':
            j = i + 1
            while True:
                c = rawdata[j:j + 1]
                if not c:
                    return -1
                if c.isspace():
                    j = j + 1
                else:
                    break
        else:
            j = i
        name, j = class_var._scan_name(j, declstartpos)
        if j < 0:
            return j
        while True:
            c = class_var.rawdata[j:j + 1]
            if not c:
                return -1
            if c in '\'"':
                match = DECLSTRINGLIT.match(rawdata[j:])
                if match:
                    j = j + match.start() + len(match.group(0))
                else:
                    return -1
            elif c == '>':
                return j + 1
            else:
                name, j = class_var._scan_name(j, declstartpos)
                if j < 0:
                    return j
    def _scan_name(i, declstartpos):
        rawdata = class_var.rawdata
        n = len(rawdata)
        if i == n:
            return SCAN_NAME_DEFAULT
        match = DECLNAME.match(rawdata[i:])
        if match:
            s = match.group(0)
            name = s.strip()
            if i + len(s) == n:
                return SCAN_NAME_DEFAULT
            return (name.lower(), i + match.start() + len(s))
        else:
            class_var.updatepos(declstartpos, i)
            raise Exception('expected name token at %r' % rawdata[declstartpos:declstartpos + 20])
    Clz = SkelClass('ParserBase')
    class_var = Clz()
    class_var.__init__ = ParserBase_dlm___init__
    class_var.getpos = getpos
    class_var.updatepos = updatepos
    class_var.parse_declaration = parse_declaration
    class_var.parse_marked_section = parse_marked_section
    class_var.parse_comment = parse_comment
    class_var._parse_doctype_subset = _parse_doctype_subset
    class_var._parse_doctype_element = _parse_doctype_element
    class_var._parse_doctype_attlist = _parse_doctype_attlist
    class_var._parse_doctype_notation = _parse_doctype_notation
    class_var._parse_doctype_entity = _parse_doctype_entity
    class_var._scan_name = _scan_name
    ParserBase_dlm___init__()
    return class_var
def HTMLParser(param_0):
    def HTMLParser_dlm___init__(convert_charrefs):
        class_var.CDATA_CONTENT_ELEMENTS = CDATA_CONTENT_ELEMENTS
        class_var.convert_charrefs = convert_charrefs
        class_var.reset()
    def reset():
        class_var.rawdata = ''
        class_var.lasttag = '???'
        class_var.interesting = INTERESTING_NORMAL
        class_var.cdata_elem = None
        class_var.lineno = 1
        class_var.offset = 0
    def feed(data):
        class_var.rawdata = class_var.rawdata + data
        class_var.goahead(0)
    def close():
        class_var.goahead(1)
    def get_starttag_text():
        return class_var.__starttag_text
    def set_cdata_mode(elem):
        class_var.cdata_elem = elem.lower()
        class_var.interesting = re.compile('</\\s*%s\\s*>' % class_var.cdata_elem, re.I)
    def clear_cdata_mode():
        class_var.interesting = INTERESTING_NORMAL
        class_var.cdata_elem = None
    def goahead(end):
        def handle_leftangle():
            nonlocal i
            k = None
            if STARTTAGOPEN.match(rawdata[i:]):
                k = class_var.parse_starttag(i)
            elif rawdata.startswith('</', i):
                k = class_var.parse_endtag(i)
            elif rawdata.startswith('<!--', i):
                k = class_var.parse_comment(i, 1)
            elif rawdata.startswith('<?', i):
                k = class_var.parse_pi(i)
            elif rawdata.startswith('<!', i):
                k = class_var.parse_html_declaration(i)
            elif i + 1 < n:
                class_var.handle_data('<')
                k = i + 1
            else:
                return 'break'
            if k < 0:
                if not end:
                    return 'break'
                k = rawdata.find('>', i + 1)
                if k < 0:
                    k = rawdata.find('<', i + 1)
                    if k < 0:
                        k = i + 1
                else:
                    k += 1
                if class_var.convert_charrefs and (not class_var.cdata_elem):
                    class_var.handle_data(unescape(rawdata[i:k]))
                else:
                    class_var.handle_data(rawdata[i:k])
            i = class_var.updatepos(i, k)
        def HTMLParser_dlm_goahead_dlm_handle_charref():
            nonlocal i
            match = CHARREF.match(rawdata[i:])
            if match:
                name = match.group(0)[2:-1]
                class_var.handle_charref(name)
                k = match.start() + i + len(match.group(0))
                if not rawdata.startswith(';', k - 1):
                    k = k - 1
                i = class_var.updatepos(i, k)
                return 'continue'
            else:
                if ';' in rawdata[i:]:
                    class_var.handle_data(rawdata[i:i + 2])
                    i = class_var.updatepos(i, i + 2)
                return 'break'
        def HTMLParser_dlm_goahead_dlm_handle_entityref():
            nonlocal i
            match = ENTITYREF.match(rawdata[i:])
            if match:
                name = match.group(1)
                class_var.handle_entityref(name)
                k = match.start() + i + len(match.group(0))
                if not rawdata.startswith(';', k - 1):
                    k = k - 1
                i = class_var.updatepos(i, k)
                return 'continue'
            match = INCOMPLETE.match(rawdata[i:])
            if match:
                if end and match.group(0) == rawdata[i:]:
                    k = i + len(match.group(0))
                    if k <= i:
                        k = n
                    i = class_var.updatepos(i, i + 1)
                return 'break'
            elif i + 1 < n:
                class_var.handle_data('&')
                i = class_var.updatepos(i, i + 1)
            else:
                return 'break'
        rawdata = class_var.rawdata
        i = 0
        n = len(rawdata)
        while i < n:
            if class_var.convert_charrefs and (not class_var.cdata_elem):
                j = rawdata.find('<', i)
                if j < 0:
                    amppos = rawdata.rfind('&', max(i, n - 34))
                    if amppos >= 0 and (not re.compile('[\\s;]').search(rawdata[amppos:])):
                        break
                    j = n
            else:
                match = class_var.interesting.search(rawdata[i:])
                if match:
                    j = match.start() + i
                else:
                    if class_var.cdata_elem:
                        break
                    j = n
            if i < j:
                if class_var.convert_charrefs and (not class_var.cdata_elem):
                    class_var.handle_data(unescape(rawdata[i:j]))
                else:
                    class_var.handle_data(rawdata[i:j])
            i = class_var.updatepos(i, j)
            if i == n:
                break
            if rawdata.startswith('<', i):
                act = handle_leftangle()
                if act == 'break':
                    break
                elif act == 'continue':
                    continue
                else:
                    pass
            elif rawdata.startswith('&#', i):
                _act = HTMLParser_dlm_goahead_dlm_handle_charref()
                if _act == 'break':
                    break
                elif _act == 'continue':
                    continue
                else:
                    pass
            elif rawdata.startswith('&', i):
                _act = HTMLParser_dlm_goahead_dlm_handle_entityref()
                if _act == 'break':
                    break
                elif _act == 'continue':
                    continue
                else:
                    pass
            else:
                raise Exception('interesting.search() lied')
        if end and i < n and (not class_var.cdata_elem):
            if class_var.convert_charrefs and (not class_var.cdata_elem):
                class_var.handle_data(unescape(rawdata[i:n]))
            else:
                class_var.handle_data(rawdata[i:n])
            i = class_var.updatepos(i, n)
        class_var.rawdata = rawdata[i:]
    def parse_html_declaration(i):
        rawdata = class_var.rawdata
        if rawdata[i:i + 2] != '<!':
            raise Exception('unexpected call to parse_html_declaration()')
        if rawdata[i:i + 4] == '<!--':
            return class_var.parse_comment(i, 1)
        elif rawdata[i:i + 3] == '<![':
            return class_var.parse_marked_section(i, 1)
        elif rawdata[i:i + 9].lower() == '<!doctype':
            gtpos = rawdata.find('>', i + 9)
            if gtpos == -1:
                return -1
            class_var.handle_decl(rawdata[i + 2:gtpos])
            return gtpos + 1
        else:
            return class_var.parse_bogus_comment(i, 1)
    def parse_bogus_comment(i, report):
        rawdata = class_var.rawdata
        if rawdata[i:i + 2] not in ('<!', '</'):
            raise Exception('unexpected call to parse_comment()')
        pos = rawdata.find('>', i + 2)
        if pos == -1:
            return -1
        if report:
            class_var.handle_comment(rawdata[i + 2:pos])
        return pos + 1
    def parse_pi(i):
        rawdata = class_var.rawdata
        if rawdata[i:i + 2] != '<?':
            raise Exception('unexpected call to parse_pi()')
        match = PICLOSE.search(rawdata[i + 2:])
        if not match:
            return -1
        j = match.start() + i + 2
        class_var.handle_pi(rawdata[i + 2:j])
        j = match.start() + len(match.group(0)) + i + 2
        return j
    def parse_starttag(i):
        class_var.__starttag_text = None
        endpos = class_var.check_for_whole_start_tag(i)
        if endpos < 0:
            return endpos
        rawdata = class_var.rawdata
        class_var.__starttag_text = rawdata[i:endpos]
        attrs = []
        match = TAGFIND_TOLERANT.match(rawdata[i + 1:])
        if not match:
            raise Exception('unexpected call to parse_starttag()')
        k = match.start() + len(match.group(0)) + i + 1
        tag = match.group(1).lower()
        class_var.lasttag = tag
        while k < endpos:
            match2 = ATTRFIND_TOLERANT.search(rawdata[k - 1:])
            if not match2:
                break
            attrname = match2.group(1)
            rest = match2.group(2)
            attrvalue = match2.group(3)
            if not rest:
                attrvalue = None
            elif attrvalue[:1] == "'" == attrvalue[-1:] or attrvalue[:1] == '"' == attrvalue[-1:]:
                attrvalue = attrvalue[1:-1]
            if attrvalue:
                attrvalue = unescape(attrvalue)
            attrs.append((attrname.lower(), attrvalue))
            k = k + match2.start() + len(match2.group(0)) - 1
        end = rawdata[k:endpos].strip()
        if end not in ('>', '/>'):
            class_var.handle_data(rawdata[i:endpos])
            return endpos
        if end.endswith('/>'):
            class_var.handle_startendtag(tag, attrs)
        else:
            class_var.handle_starttag(tag, attrs)
            if tag in class_var.CDATA_CONTENT_ELEMENTS:
                class_var.set_cdata_mode(tag)
        return endpos
    def check_for_whole_start_tag(i):
        rawdata = class_var.rawdata
        match = LOCATESTARTTAGEND_TOLERANT.match(rawdata[i:])
        if match:
            j = i + match.start() + len(match.group(0))
            next = rawdata[j:j + 1]
            if next == '>':
                return j + 1
            if next == '/':
                if rawdata.startswith('/>', j):
                    return j + 2
                if rawdata.startswith('/', j):
                    return -1
                if j > i:
                    return j
                else:
                    return i + 1
            if next == '':
                return -1
            if next in 'abcdefghijklmnopqrstuvwxyz=/ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                return -1
            if j > i:
                return j
            else:
                return i + 1
        raise Exception('we should not get here!')
    def parse_endtag(i):
        rawdata = class_var.rawdata
        if rawdata[i:i + 2] != '</':
            raise Exception('unexpected call to parse_endtag()')
        match = ENDENDTAG.search(rawdata[i + 1:])
        if not match:
            return -1
        gtpos = match.start() + len(match.group(0)) + i + 1
        match = ENDTAGFIND.match(rawdata[i:])
        if not match:
            if class_var.cdata_elem is not None:
                class_var.handle_data(rawdata[i:gtpos])
                return gtpos
            namematch = TAGFIND_TOLERANT.match(rawdata[i + 2:])
            if not namematch:
                if rawdata[i:i + 3] == '</>':
                    return i + 3
                else:
                    return class_var.parse_bogus_comment(i, 1)
            tagname = namematch.group(1).lower()
            gtpos = rawdata.find('>', namematch.start() + len(namematch.group(0)) + i + 2)
            class_var.handle_endtag(tagname)
            return gtpos + 1
        elem = match.group(1).lower()
        if class_var.cdata_elem is not None:
            if elem != class_var.cdata_elem:
                class_var.handle_data(rawdata[i:gtpos])
                return gtpos
        class_var.handle_endtag(elem)
        class_var.clear_cdata_mode()
        return gtpos
    def handle_startendtag(tag, attrs):
        class_var.handle_starttag(tag, attrs)
        class_var.handle_endtag(tag)
    def HTMLParser_dlm_handle_starttag(tag, attrs):
        pass
    def HTMLParser_dlm_handle_endtag(tag):
        pass
    def HTMLParser_dlm_handle_charref(name):
        pass
    def HTMLParser_dlm_handle_entityref(name):
        pass
    def HTMLParser_dlm_handle_data(data):
        pass
    def HTMLParser_dlm_handle_comment(data):
        pass
    def HTMLParser_dlm_handle_decl(decl):
        pass
    def HTMLParser_dlm_handle_pi(data):
        pass
    def HTMLParser_dlm_unknown_decl(data):
        pass
    class_var = ParserBase()
    class_var._class_name = 'HTMLParser;' + class_var._class_name
    class_var.__init__ = HTMLParser_dlm___init__
    class_var.reset = reset
    class_var.feed = feed
    class_var.close = close
    class_var.get_starttag_text = get_starttag_text
    class_var.set_cdata_mode = set_cdata_mode
    class_var.clear_cdata_mode = clear_cdata_mode
    class_var.goahead = goahead
    class_var.parse_html_declaration = parse_html_declaration
    class_var.parse_bogus_comment = parse_bogus_comment
    class_var.parse_pi = parse_pi
    class_var.parse_starttag = parse_starttag
    class_var.check_for_whole_start_tag = check_for_whole_start_tag
    class_var.parse_endtag = parse_endtag
    class_var.handle_startendtag = handle_startendtag
    class_var.handle_starttag = HTMLParser_dlm_handle_starttag
    class_var.handle_endtag = HTMLParser_dlm_handle_endtag
    class_var.handle_charref = HTMLParser_dlm_handle_charref
    class_var.handle_entityref = HTMLParser_dlm_handle_entityref
    class_var.handle_data = HTMLParser_dlm_handle_data
    class_var.handle_comment = HTMLParser_dlm_handle_comment
    class_var.handle_decl = HTMLParser_dlm_handle_decl
    class_var.handle_pi = HTMLParser_dlm_handle_pi
    class_var.unknown_decl = HTMLParser_dlm_unknown_decl
    HTMLParser_dlm___init__(param_0)
    return class_var
def MyHTMLParserTester(*args):
    def MyHTMLParserTester_dlm_handle_starttag(tag, attrs):
        LISTENER_EVENT_LIST.append(('starttag', tag, attrs))
    def MyHTMLParserTester_dlm_handle_endtag(tag):
        LISTENER_EVENT_LIST.append(('endtag', tag))
    def MyHTMLParserTester_dlm_handle_data(data):
        LISTENER_EVENT_LIST.append(('data', data))
    def MyHTMLParserTester_dlm_handle_commenthandle_comment(data):
        LISTENER_EVENT_LIST.append(('comment', data))
    def MyHTMLParserTester_dlm_handle_entityref(name):
        LISTENER_EVENT_LIST.append(('entityref', name))
    def MyHTMLParserTester_dlm_handle_charref(name):
        LISTENER_EVENT_LIST.append(('charref', name))
    def MyHTMLParserTester_dlm_handle_decl(data):
        LISTENER_EVENT_LIST.append(('decl', data))
    def MyHTMLParserTester_dlm_handle_pi(data):
        LISTENER_EVENT_LIST.append(('pi', data))
    def MyHTMLParserTester_dlm_unknown_decl(data):
        LISTENER_EVENT_LIST.append(('unknown', data))
    class_var = HTMLParser(*args)
    class_var._class_name = 'MyHTMLParserTester;' + class_var._class_name
    class_var.handle_starttag = MyHTMLParserTester_dlm_handle_starttag
    class_var.handle_endtag = MyHTMLParserTester_dlm_handle_endtag
    class_var.handle_data = MyHTMLParserTester_dlm_handle_data
    class_var.handle_comment = MyHTMLParserTester_dlm_handle_commenthandle_comment
    class_var.handle_entityref = MyHTMLParserTester_dlm_handle_entityref
    class_var.handle_charref = MyHTMLParserTester_dlm_handle_charref
    class_var.handle_decl = MyHTMLParserTester_dlm_handle_decl
    class_var.handle_pi = MyHTMLParserTester_dlm_handle_pi
    class_var.unknown_decl = MyHTMLParserTester_dlm_unknown_decl
    return class_var
def main_test():
    p = MyHTMLParserTester(True)
    p.feed(EXAMPLE_HTML)
    LISTENER_EVENT_LIST.append(('PRINT', p.getpos()))
    LISTENER_EVENT_LIST.append(('PRINT', p.get_starttag_text()))
    LISTENER_EVENT_LIST.append(('PRINT', p.parse_declaration(0)))
    p.close()
def additional_test():
    p = MyHTMLParserTester(True)
    p.rawdata = '<!DOCTYPE html>'
    parse_res = p.parse_declaration(0)
    if parse_res != 15:
        raise Exception('Assertion failed')
    p.reset()
    p.rawdata = "<!DOCTYPE '2'>"
    parse_res = p.parse_declaration(0)
    if parse_res != 14:
        raise Exception('Assertion failed')
    p.reset()
    p.rawdata = '<!DOCTYPE [<!-->]> '
    parse_res = p.parse_declaration(0)
    if parse_res != -1:
        raise Exception('Assertion failed')
    p.reset()
    p.rawdata = '<!DOCTYPE [%hello]> '
    parse_res = p.parse_declaration(0)
    if parse_res != 19:
        raise Exception('Assertion failed')
    p.reset()
    p.rawdata = '<!DOCTYPE [ ]> '
    parse_res = p.parse_declaration(0)
    if parse_res != 14:
        raise Exception('Assertion failed')
    p.reset()
    p.close()
def additional_test2():
    p = MyHTMLParserTester(True)
    p.convert_charrefs = False
    p.feed('&abc<')
    p.reset()
    p.convert_charrefs = False
    p.feed('&#abc<')
    p.reset()
    p.convert_charrefs = False
    p.feed('&<')
    p.reset()
    p.convert_charrefs = False
    p.feed('&#<')
    p.reset()
    p.close()
def additional_test3():
    p = MyHTMLParserTester(True)
    p.handle_startendtag('tag', [])
    p.reset()
    p.handle_charref('name')
    p.reset()
    p.handle_entityref('name')
    p.reset()
    p.handle_data('data')
    p.reset()
    p.handle_comment('data')
    p.reset()
    p.handle_decl('data')
    p.reset()
    p.handle_pi('data')
    p.reset()
    p.unknown_decl('data')
    p.reset()
    p = HTMLParser(True)
    p.handle_startendtag('tag', [])
    p.reset()
    p.handle_charref('name')
    p.reset()
    p.handle_entityref('name')
    p.reset()
    p.handle_data('data')
    p.reset()
    p.handle_comment('data')
    p.reset()
    p.handle_decl('data')
    p.reset()
    p.handle_pi('data')
    p.reset()
    p.unknown_decl('data')
    p.reset()
    p.close()
def additional_test4():
    p = HTMLParser(True)
    p.rawdata = '<abc/'
    parse_res = p.check_for_whole_start_tag(0)
    if parse_res != -1:
        raise Exception('Assertion failed')
    p.reset()
    p.rawdata = '<tagname attr="value'
    parse_res = p.check_for_whole_start_tag(0)
    if parse_res != -1:
        raise Exception('Assertion failed')
    p.reset()
    p.rawdata = '<tagname attr'
    parse_res = p.check_for_whole_start_tag(0)
    if parse_res != -1:
        raise Exception('Assertion failed')
    p.reset()
    p.rawdata = '<tagname /'
    parse_res = p.check_for_whole_start_tag(0)
    if parse_res != -1:
        raise Exception('Assertion failed')
    p.reset()
    p.rawdata = '<tagname attr = "value" /'
    parse_res = p.check_for_whole_start_tag(0)
    if parse_res != -1:
        raise Exception('Assertion failed')
    p.reset()
    p.rawdata = '<tagname "value" /'
    parse_res = p.check_for_whole_start_tag(0)
    if parse_res != -1:
        raise Exception('Assertion failed')
    p.reset()
    p.close()
def additional_test5():
    res = escape("abc<>/'", True)
    if res != 'abc&lt;&gt;/&#x27;':
        raise Exception('Assertion failed')
    res = escape('<>', True)
    if res != '&lt;&gt;':
        raise Exception('Assertion failed')
    res = escape('abc', True)
    if res != 'abc':
        raise Exception('Assertion failed')
    res = escape('abc&', True)
    if res != 'abc&amp;':
        raise Exception('Assertion failed')
    res = unescape('abc&lt;&gt;/&#x27;')
    if res != "abc<>/'":
        raise Exception('Assertion failed')
    res = unescape('&lt;&gt;')
    if res != '<>':
        raise Exception('Assertion failed')
    res = unescape('abc')
    if res != 'abc':
        raise Exception('Assertion failed')
    res = unescape('abc&amp;')
    if res != 'abc&':
        raise Exception('Assertion failed')
def additional_test6():
    p = HTMLParser(True)
    p.rawdata = 'element>'
    p._parse_doctype_element(0, 0)
    p.reset()
    p.rawdata = 'attlist element'
    p._parse_doctype_attlist(0, 0)
    p.reset()
    p.rawdata = 'notation element'
    p._parse_doctype_notation(0, 0)
    p.reset()
    p.rawdata = "notation'"
    p._parse_doctype_notation(0, 0)
    p.reset()
    p.rawdata = '%element element'
    p._parse_doctype_entity(0, 0)
    p.reset()
    p.close()
def additional_tests():
    additional_test()
    additional_test2()
    additional_test3()
    additional_test4()
    additional_test5()
    additional_test6()
def test_init():
    _replace_charref('#xa')
    _replace_charref('#1')
    _replace_charref('#0')
    _replace_charref('#55297')
    _replace_charref('amp;')
    _replace_charref('amp;&')
    _replace_charref('am')
    unescape('')
    unescape('&abc;')
    hp = HTMLParser(True)
    pb = ParserBase()
    pb.rawdata = ''
    pb.lineno = 0
    pb.offset = 0
    pb.updatepos(0, 0)
    pb.rawdata = ''
    pb.lineno = 0
    pb.offset = 0
    pb.updatepos(0, 1)
    pb.rawdata = '\n'
    pb.lineno = 0
    pb.offset = 0
    pb.updatepos(0, 10)
    hp.rawdata = '<a href="value">'
    hp.check_for_whole_start_tag(0)
    hp.rawdata = '<a href="value"/>'
    hp.check_for_whole_start_tag(0)
    hp.rawdata = '<a'
    hp.check_for_whole_start_tag(0)
    hp.rawdata = '<a a="v'
    hp.check_for_whole_start_tag(0)
    hp.rawdata = '<?a>'
    hp.parse_pi(0)
    hp.rawdata = '<!--comment'
    hp.parse_comment(0, True)
    hp.rawdata = '<!--comment-->'
    hp.parse_comment(0, True)
    hp.rawdata = '<!bogus>'
    hp.parse_bogus_comment(0, True)
    hp.rawdata = '</>'
    hp.parse_endtag(0)
    hp.rawdata = '</!fff>'
    hp.parse_endtag(0)
    hp.rawdata = '</a>'
    hp.parse_endtag(0)
    hp.rawdata = '<a attr="v">value</a>'
    hp.parse_starttag(0)
    pb.rawdata = 'abc'
    pb._scan_name(0, 0)
    pb.rawdata = 'CDATA[ CDATA ]]>'
    pb._scan_name(0, 0)
    hp.rawdata = '<!DOCTYPE [<!-->]> '
    hp._parse_doctype_subset(11, 0)
    hp.rawdata = '<!DOCTYPE [%hello]> '
    hp._parse_doctype_subset(11, 0)
    hp.rawdata = '<!DOCTYPE [ ]> '
    hp._parse_doctype_subset(11, 0)
    hp.rawdata = "notation'"
    hp._parse_doctype_notation(0, 0)
    hp.rawdata = "notation element"
    hp._parse_doctype_notation(0, 0)
    hp.rawdata = 'element>'
    hp._parse_doctype_element(0, 0)
    hp.rawdata = '<![ENDIF]-->'
    hp.parse_marked_section(0, True)
    hp.rawdata = '<![CDATA[ CDATA ]]>'
    hp.parse_marked_section(0, True)
    hp.rawdata = '<![CDATA[ CDATA ]]>'
    hp.parse_html_declaration(0)
    hp.rawdata = '<!DOCTYPE html>'
    hp.parse_html_declaration(0)
    hp.rawdata = '<!fff>'
    hp.parse_html_declaration(0)
    hp.rawdata = '<!DOCTYPE html>'
    hp.parse_declaration(0)
    hp.rawdata = '<![ENDIF]-->'
    hp.parse_declaration(0)
    hp.rawdata = "<!DOCTYPE '2'>"
    hp.parse_declaration(0)
    hp.rawdata = '<!DOCTYPE [<!-->]> '
    hp.parse_declaration(0)
    hp.rawdata = '%element element'
    hp._parse_doctype_entity(0, 0)
    hp.feed('<s')
    hp.feed('<s></s>')
    hp.feed('<!--c-->')
    hp.feed('<?pi?>')
    hp.feed('<!t>')
    hp.feed('<>')
    hp.feed('&abc<')
def test():
    test_init()
    main_test()
    additional_tests()
test()
