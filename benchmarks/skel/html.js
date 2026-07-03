const EXAMPLE_HTML = `<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">\n    <!-- Comment -->\n    <![CDATA[ CDATA ]]>\n    <a href="http://www.python.org%20">&nbsp;Python&#123;&#x213;&#x00;&#xd800;&&#x1;&accute;&nbspf;</a>\n    <H1>Python</H1>\n    <script src="script.js">function f(){console.log("sds")}</script>\n    <![IF [condition]>\n             This is an invalid marked section declaration\n     <![ENDIF]-->\n     <img src="image.jpg" alt="Example Image" />\n     <>This is an invalid tag</>\n     &lt;%30%&gt;&##&&#x30;{}()-=]:>}}L><<;<;>;@?;>!;>;;\n     <div>&lt;&#x65;</div>\n     <!fff></!fff>\n     <?we><?we?>\n    `;
const INVALID_CHARREFS = {0x00: '\ufffd'};
const INVALID_CODEPOINTS = {0x1: ""};

const CHARREF_REGULAR_EXP = /&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\t\n\f <&#;]{1,32};?)/;
const DECLNAME = /[a-zA-Z][-_.a-zA-Z0-9]*\s*/;
const DECLSTRINGLIT = /('[^']*'|"[^"]*")\s*/;
const MARKEDSECTIONCLOSE = /\]\s*\]\s*>/;
const MSMARKEDSECTIONCLOSE = /\]\s*>/;
const INTERESTING_NORMAL = /[&<]/;
const INCOMPLETE = /&[a-zA-Z#]/g;
const ENTITYREF = /&([a-zA-Z][-.a-zA-Z0-9]*)[^a-zA-Z0-9]/g;
const CHARREF = /&#(?:[0-9]+|[xX][0-9a-fA-F]+)[^0-9a-fA-F]/g;
const STARTTAGOPEN = /^<[a-zA-Z]/;
const PICLOSE = />/g;
const COMMENTCLOSE = /--\s*>/g;
const TAGFIND_TOLERANT = /^([a-zA-Z][^\t\n\r\f />\x00]*)(?:\s|\/(?!>))*/;
const ATTRFIND_TOLERANT = /((?<=[\'"\s\/])[^\s\/>][^\s\/=>]*)(\s*=+\s*('[^']*'|"[^"]*"|(?!['"])[^>\s]*))?(?:\s|\/(?!>))*/;
const LOCATESTARTTAGEND_TOLERANT = /<[a-zA-Z][^\t\n\r\f />\x00]*(?:[\s/]*(?:(?<=['"\s/])[^\s/>][^\s/=>]*(?:\s*=+\s*(?:'[^']*'|"[^"]*"|(?!['"])[^>\s]*)\s*)?(?:\s|\/(?!>))*)*)?\s*/;
const ENDENDTAG = />/;
const ENDTAGFIND = /^<\/\s*([a-zA-Z][-.a-zA-Z0-9:_]*)\s*>/;
const HTML5 = {'amp;': '&', 'gt;': '>', 'lt;': '<', 'nbsp': '\xa0', 'nbsp;': '\xa0'};

const CDATA_CONTENT_ELEMENTS = ["script", "style"];
const SCAN_NAME_DEFAULT = [null, -1];
const LISTENER_EVENT_LIST = [];


function SkelClass(name) {
    var Clz = function() {
        var _class_var = {};
        _class_var._class_name = name;
        return _class_var;
    }
    return Clz;
}





function escape(s, quote) {
    s = s.replace('&', '&amp;');
    s = s.replace('<', '&lt;');
    s = s.replace('>', '&gt;');
    if (quote) {
        s = s.replace('"', '&quot;');
        s = s.replace("'", '&#x27;');
    }
    return s;
}
function _replace_charref(s) {
    if (s[0] === '#') {
        var num = "xX".includes(s[1]) ? parseInt(s.substring(2).replace(';', ''), 16) : parseInt(s.substring(1).replace(';', ''));
        if (num in INVALID_CHARREFS) {
            return INVALID_CHARREFS[num];
        }
        if (0xD800 <= num && num <= 0xDFFF || num > 0x10FFFF) {
            return '\uFFFD';
        }
        if (num in INVALID_CODEPOINTS) {
            return '';
        }
        return String.fromCharCode(num);
    }
    if (s in HTML5) {
        return HTML5[s];
    }
    for (var x = s.length - 1; x > 1; x--) {
        if (s.substring(0, x) in HTML5) {
            return HTML5[s.substring(0, x)] + s.substring(x);
        }
    }
    return '&' + s;
}
function unescape(s) {
    if (!s.includes('&')) {
        return s;
    }
    var start = 0;
    while (true) {
        var match = CHARREF_REGULAR_EXP.exec(s.substring(start));
        if (!match) {
            break;
        }
        var replacement = _replace_charref(match[1]);
        var _start_idx = start + match.index;
        var _end_idx = _start_idx + match[0].length;
        s = s.substring(0, _start_idx) + replacement + s.substring(_end_idx);
        start = _start_idx + replacement.length;
    }
    return s;
}
function ParserBase() {
    function ParserBase_dlm___init__() {
    }
    function getpos() {
        return [class_var.lineno, class_var.offset];
    }
    function updatepos(i, j) {
        if (i >= j) {
            return j;
        }
        var rawdata = class_var.rawdata;
        var nlines = (rawdata.substring(i, j).match(/\n/g) || []).length;
        if (nlines) {
            class_var.lineno = class_var.lineno + nlines;
            var pos = rawdata.lastIndexOf("\n", j);
            class_var.offset = j - (pos + 1);
        } else {
            class_var.offset = class_var.offset  + j - i;
        }
        return j;
    }
    function parse_declaration(i) {
        var rawdata = class_var.rawdata;
        var j = i + 2;
        if (rawdata.substring(i, j) !== "<!") {
            throw new Error("unexpected call to parse_declaration");
        }
        if (rawdata.substring(j, j + 1) === ">") {
            return j + 1;
        }
        if (["-", ""].includes(rawdata.substring(j, j + 1))) {
            return -1;
        }
        var n = rawdata.length;
        if (rawdata.substring(j, j + 2) === '--') {
            return class_var.parse_comment(i, 1);
        } else if (rawdata[j] === '[') {
            return class_var.parse_marked_section(i, 1);
        } else {
            var [decltype, j] = class_var._scan_name(j, i);
        }
        if (j < 0) {
            return j;
        }
        if (decltype === "doctype") {
            class_var._decl_otherchars = '';
        }
        while (j < n) {
            var c = rawdata[j];
            if (c === ">") {
                var data = rawdata.substring(i + 2, j);
                if (decltype === "doctype") {
                    class_var.handle_decl(data);
                } else {
                    class_var.unknown_decl(data);
                }
                return j + 1;
            }
            if ("'\"".includes(c)) {
                var match = DECLSTRINGLIT.exec(rawdata.substring(j));
                if (!match) {
                    return -1;
                }
                j = match.index + match[0].length + j;
            } else if ("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ".includes(c)) {
                var [name, j] = class_var._scan_name(j, i);
            } else if (class_var._decl_otherchars.includes(c)) {
                j = j + 1;
            } else if (c === "[") {
                if (decltype === "doctype") {
                    j = class_var._parse_doctype_subset(j + 1, i);
                } else if (["attlist", "linktype", "link", "element"].includes(decltype)) {
                    throw new Error("unsupported '[' char in " + decltype + " declaration");
                } else {
                    throw new Error("unexpected '[' char in declaration");
                }
            } else {
                throw new Error("unexpected " + rawdata[j] + " char in declaration");
            }
            if (j < 0) {
                return j;
            }
        }
        return -1;
    }
    function parse_marked_section(i, report) {
        var rawdata = class_var.rawdata;
        if (rawdata.substring(i, i + 3) !== '<![') {
            throw new Error("unexpected call to parse_marked_section()");
        }
        var [sectName, j] = class_var._scan_name(i + 3, i);
        if (j < 0) {
            return j;
        }
        var standard_sections = ['temp', 'cdata', 'ignore', 'include', 'rcdata'];
        var ms_office_sections = ['if', 'else', 'endif'];
        var match = null;
        if (standard_sections.includes(sectName)) {
            match = MARKEDSECTIONCLOSE.exec(rawdata.substring(i + 3));
        } else if (ms_office_sections.includes(sectName)) {
            match = MSMARKEDSECTIONCLOSE.exec(rawdata.substring(i + 3));
        } else {
            throw new Error('unknown status keyword ' + rawdata.substring(i + 3, j) + ' in marked section');
        }
        if (!match) {
            return -1;
        }
        if (report) {
            j = match.index + i + 3;
            class_var.unknown_decl(rawdata.substring(i + 3, j));
        }
        return match.index + match[0].length + i + 3;
    }
    function parse_comment(i, report) {
        var rawdata = class_var.rawdata;
        if (rawdata.substring(i, i + 4) !== '<!--') {
            throw new Error('unexpected call to parse_comment()');
        }
        var match = COMMENTCLOSE.exec(rawdata.substring(i + 4));
        if (!match) {
            return -1;
        }
        if (report) {
            var j = match.index + i + 4;
            class_var.handle_comment(rawdata.substring(i + 4, j));
        }
        return match.index + match[0].length + i + 4;
    }
    function _parse_doctype_subset(i, declstartpos) {
        var rawdata = class_var.rawdata;
        var n = rawdata.length;
        var j = i;
        while (j < n) {
            var c = rawdata[j];
            if (c === "<") {
                var s = rawdata.substring(j, j + 2);
                if (s === "<") {
                    return -1;
                }
                if (s !== "<!") {
                    class_var.updatepos(declstartpos, j + 1);
                    throw new Error("unexpected char in internal subset (in " + s + ")");
                }
                if (j + 2 === n) {
                    return -1;
                }
                if (j + 4 > n) {
                    return -1;
                }
                if (rawdata.substring(j, j + 4) === "<!--") {
                    j = class_var.parse_comment(j, 0);
                    if (j < 0) {
                        return j;
                    }
                    continue;
                }
                var [name, j] = class_var._scan_name(j + 2, declstartpos);
                if (j === -1) {
                    return -1;
                }
                if (!["attlist", "element", "entity", "notation"].includes(name)) {
                    class_var.updatepos(declstartpos, j + 2);
                    throw new Error("unknown declaration " + name + " in internal subset");
                }
                var meth = class_var["_parse_doctype_" + name];
                j = meth(j, declstartpos);
                if (j < 0) {
                    return j;
                }
            } else if (c === "%") {
                if (j + 1 === n) {
                    return -1;
                }
                var [s, j] = class_var._scan_name(j + 1, declstartpos);
                if (j < 0) {
                    return j;
                }
                if (rawdata[j] === ";") {
                    j = j + 1;
                }
            } else if (c === "]") {
                j = j + 1;
                while (j < n && /\s/.test(rawdata[j])) {
                    j = j + 1;
                }
                if (j < n) {
                    if (rawdata[j] === ">") {
                        return j;
                    }
                    class_var.updatepos(declstartpos, j);
                    throw new Error("unexpected char after internal subset");
                } else {
                    return -1;
                }
            } else if (/\s/.test(c)) {
                j = j + 1;
            } else {
                class_var.updatepos(declstartpos, j);
                throw new Error("unexpected char " + c + " in internal subset");
            }
        }
        return -1;
    }
    function _parse_doctype_element(i, declstartpos) {
        var [name, j] = class_var._scan_name(i, declstartpos);
        if (j === -1) {
            return -1;
        }
        var rawdata = class_var.rawdata;
        if (rawdata.substring(j).includes('>')) {
            return rawdata.indexOf(">", j) + 1;
        }
        return -1;
    }
    function _parse_doctype_attlist(i, declstartpos) {
    }
    function _parse_doctype_notation(i, declstartpos) {
        var [name, j] = class_var._scan_name(i, declstartpos);
        if (j < 0) {
            return j;
        }
        var rawdata = class_var.rawdata;
        while (true) {
            var c = rawdata.substring(j, j + 1);
            if (!c) {
                return -1;
            }
            if (c === '>') {
                return j + 1;
            }
            if ("'\"".includes(c)) {
                var match = DECLSTRINGLIT.exec(rawdata.substring(j));
                if (!match) {
                    return -1;
                }
                j = j + match.index + match[0].length;
            } else {
                [name, j] = class_var._scan_name(j, declstartpos);
                if (j < 0) {
                    return j;
                }
            }
        }
    }
    function _parse_doctype_entity(i, declstartpos) {
        var rawdata = class_var.rawdata;
        if (rawdata.substring(i, i + 1) === "%") {
            var j = i + 1;
            while (true) {
                var c = rawdata.substring(j, j + 1);
                if (!c) {
                    return -1;
                }
                if (/\s/.test(c)) {
                    j++;
                } else {
                    break;
                }
            }
        } else {
            j = i;
        }
        var [name, j] = class_var._scan_name(j, declstartpos);
        if (j < 0) {
            return j;
        }
        while (true) {
            c = rawdata.substring(j, j + 1);
            if (!c) {
                return -1;
            }
            if ("'\"".includes(c)) {
                var match = DECLSTRINGLIT.exec(rawdata.substring(j));
                if (match) {
                    j = j + match.index + match[0].length;
                } else {
                    return -1;
                }
            } else if (c === ">") {
                return j + 1;
            } else {
                [name, j] = class_var._scan_name(j, declstartpos);
                if (j < 0) {
                    return j;
                }
            }
        }
    }
    function _scan_name(i, declstartpos) {
        var rawdata = class_var.rawdata;
        var n = rawdata.length;
        if (i === n) {
            return SCAN_NAME_DEFAULT;
        }
        var match = DECLNAME.exec(rawdata.substring(i));
        if (match) {
            var s = match[0];
            var name = s.trim();
            if ((i + s.length) === n) {
                return SCAN_NAME_DEFAULT;
            }
            return [name.toLowerCase(), i + match.index + s.length];
        } else {
            class_var.updatepos(declstartpos, i);
            throw new Error("expected name token at " + rawdata.substring(declstartpos, declstartpos + 20));
        }
    }
    var Clz = SkelClass('ParserBase');
    var class_var = Clz();
    class_var.__init__ = ParserBase_dlm___init__;
    class_var.getpos = getpos;
    class_var.updatepos = updatepos;
    class_var.parse_declaration = parse_declaration;
    class_var.parse_marked_section = parse_marked_section;
    class_var.parse_comment = parse_comment;
    class_var._parse_doctype_subset = _parse_doctype_subset;
    class_var._parse_doctype_element = _parse_doctype_element;
    class_var._parse_doctype_attlist = _parse_doctype_attlist;
    class_var._parse_doctype_notation = _parse_doctype_notation;
    class_var._parse_doctype_entity = _parse_doctype_entity;
    class_var._scan_name = _scan_name;
    ParserBase_dlm___init__();
    return class_var;
}
function HTMLParser(param_0) {
    function HTMLParser_dlm___init__(convert_charrefs) {
        class_var.CDATA_CONTENT_ELEMENTS = CDATA_CONTENT_ELEMENTS;
        class_var.convert_charrefs = convert_charrefs;
        class_var.reset();
    }
    function reset() {
        class_var.rawdata = '';
        class_var.lasttag = '???';
        class_var.interesting = INTERESTING_NORMAL;
        class_var.cdata_elem = null;
        class_var.lineno = 1;
        class_var.offset = 0;
    }
    function feed(data) {
        class_var.rawdata = class_var.rawdata + data;
        class_var.goahead(0);
    }
    function close() {
        class_var.goahead(1);
    }
    function get_starttag_text() {
        return class_var.__starttag_text;
    }
    function set_cdata_mode(elem) {
        class_var.cdata_elem = elem.toLowerCase();
        class_var.interesting = new RegExp('</\\s*' + class_var.cdata_elem + '\\s*>', 'i');
    }
    function clear_cdata_mode() {
        class_var.interesting = INTERESTING_NORMAL;
        class_var.cdata_elem = null;
    }
    function goahead(end) {
        function handle_leftangle() {
            var k = null;
            if (STARTTAGOPEN.test(rawdata.substring(i))) {
                k = class_var.parse_starttag(i);
            } else if (rawdata.startsWith("</", i)) {
                k = class_var.parse_endtag(i);
            } else if (rawdata.startsWith("<!--", i)) {
                k = class_var.parse_comment(i, 1);
            } else if (rawdata.startsWith("<?", i)) {
                k = class_var.parse_pi(i);
            } else if (rawdata.startsWith("<!", i)) {
                k = class_var.parse_html_declaration(i);
            } else if (i + 1 < n) {
                class_var.handle_data("<");
                k = i + 1;
            } else {
                return "break";
            }
            if (k < 0) {
                if (!end) {
                    return "break";
                }
                k = rawdata.indexOf('>', i + 1);
                if (k < 0) {
                    k = rawdata.indexOf('<', i + 1);
                    if (k < 0) {
                        k = i + 1;
                    }
                } else {
                    k += 1;
                }
                if (class_var.convert_charrefs && !class_var.cdata_elem) {
                    class_var.handle_data(unescape(rawdata.substring(i, k)));
                } else {
                    class_var.handle_data(rawdata.substring(i, k));
                }
            }
            i = class_var.updatepos(i, k);
        }
        function HTMLParser_dlm_goahead_dlm_handle_charref() {
            var match = CHARREF.exec(rawdata.substring(i));
            if (match) {
                var name = match[0].slice(2, -1);
                class_var.handle_charref(name);
                var k = match.index + i + match[0].length;
                if (!rawdata.startsWith(';', k - 1)) {
                    k = k - 1;
                }
                i = class_var.updatepos(i, k);
                return "continue";
            } else {
                if (rawdata.substring(i).includes(";")) {
                    class_var.handle_data(rawdata.substring(i, i + 2));
                    i = class_var.updatepos(i, i + 2);
                }
                return "break";
            }
        }
        function HTMLParser_dlm_goahead_dlm_handle_entityref() {
            var match = ENTITYREF.exec(rawdata.substring(i));
            if (match) {
                var name = match[1];
                class_var.handle_entityref(name);
                var k = i + match[0].length;
                if (!rawdata.startsWith(';', k - 1)) {
                    k = k - 1;
                }
                i = class_var.updatepos(i, k);
                return "continue";
            }
            match = INCOMPLETE.exec(rawdata.substring(i));
            if (match) {
                if (end && match[0] === rawdata.substring(i)) {
                    k = i + match[0].length;
                    if (k <= i) {
                        k = n;
                    }
                    i = class_var.updatepos(i, i + 1);
                }
                return "break";
            } else if (i + 1 < n) {
                class_var.handle_data("&");
                i = class_var.updatepos(i, i + 1);
            } else {
                return "break";
            }
        }
        var rawdata = class_var.rawdata;
        var i = 0;
        var n = rawdata.length;
        while (i < n) {
            if (class_var.convert_charrefs && !class_var.cdata_elem) {
                var j = rawdata.indexOf('<', i);
                if (j < 0) {
                    var amppos = rawdata.lastIndexOf('&', Math.max(i, n - 34));
                    if (amppos >= 0 && !/[\s;]/.test(rawdata.substring(amppos))) {
                        break;
                    }
                    j = n;
                }
            } else {
                var match = class_var.interesting.exec(rawdata.substring(i));
                if (match) {
                    j = match.index + i;
                } else {
                    if (class_var.cdata_elem) {
                        break;
                    }
                    j = n;
                }
            }
            if (i < j) {
                if (class_var.convert_charrefs && !class_var.cdata_elem) {
                    class_var.handle_data(unescape(rawdata.substring(i, j)));
                } else {
                    class_var.handle_data(rawdata.substring(i, j));
                }
            }
            i = class_var.updatepos(i, j);
            if (i == n) {
                break;
            }
            if (rawdata.startsWith('<', i)) {
                var act = handle_leftangle();
                if (act === "break") {
                    break;
                } else if (act === "continue") {
                    continue;
                } else {
                }
            } else if (rawdata.startsWith("&#", i)) {
                var _act = HTMLParser_dlm_goahead_dlm_handle_charref();
                if (_act === "break") {
                    break;
                } else if (_act === "continue") {
                    continue;
                } else {
                }
            } else if (rawdata.startsWith('&', i)) {
                var _act = HTMLParser_dlm_goahead_dlm_handle_entityref();
                if (_act === "break") {
                    break;
                } else if (_act === "continue") {
                    continue;
                } else {
                }
            } else {
                throw new Error("interesting.search() lied");
            }
        }
        if (end && i < n && !class_var.cdata_elem) {
            if (class_var.convert_charrefs && !class_var.cdata_elem) {
                class_var.handle_data(unescape(rawdata.substring(i, n)));
            } else {
                class_var.handle_data(rawdata.substring(i, n));
            }
            i = class_var.updatepos(i, n);
        }
        class_var.rawdata = rawdata.substring(i);
    }
    function parse_html_declaration(i) {
        var rawdata = class_var.rawdata;
        if (rawdata.substring(i, i + 2) !== '<!') {
            throw new Error('unexpected call to parse_html_declaration()');
        }
        if (rawdata.substring(i, i + 4) === '<!--') {
            return class_var.parse_comment(i, 1);
        } else if (rawdata.substring(i, i + 3) === '<![') {
            return class_var.parse_marked_section(i, 1);
        } else if (rawdata.substring(i, i + 9).toLowerCase() === '<!doctype') {
            var gtpos = rawdata.indexOf('>', i + 9);
            if (gtpos === -1) {
                return -1;
            }
            class_var.handle_decl(rawdata.substring(i + 2, gtpos));
            return gtpos + 1;
        } else {
            return class_var.parse_bogus_comment(i, 1);
        }
    }
    function parse_bogus_comment(i, report) {
        var rawdata = class_var.rawdata;
        if (!['<!', '</'].includes(rawdata.substring(i, i + 2))) {
            throw new Error('unexpected call to parse_comment()');
        }
        var pos = rawdata.indexOf('>', i + 2);
        if (pos === -1) {
            return -1;
        }
        if (report) {
            class_var.handle_comment(rawdata.substring(i + 2, pos));
        }
        return pos + 1;
    }
    function parse_pi(i) {
        var rawdata = class_var.rawdata;
        if (rawdata.substring(i, i + 2) !== '<?') {
            throw new Error('unexpected call to parse_pi()');
        }
        var match = PICLOSE.exec(rawdata.substring(i + 2));
        if (!match) {
            return -1;
        }
        var j = match.index + i + 2;
        class_var.handle_pi(rawdata.substring(i + 2, j));
        j = match.index + match[0].length + i + 2;
        return j;
    }
    function parse_starttag(i) {
        class_var.__starttag_text = null;
        var endpos = class_var.check_for_whole_start_tag(i);
        if (endpos < 0) {
            return endpos;
        }
        var rawdata = class_var.rawdata;
        class_var.__starttag_text = rawdata.substring(i, endpos);
        var attrs = [];
        var match = TAGFIND_TOLERANT.exec(rawdata.substring(i + 1));
        if (!match) {
            throw new Error('unexpected call to parse_starttag()');
        }
        var k = match.index + match[0].length + i + 1;
        var tag = match[1].toLowerCase();
        class_var.lasttag = tag;
        while (k < endpos) {
            var match2 = ATTRFIND_TOLERANT.exec(rawdata.substring(k - 1));
            if (match2[2] == undefined) {
                break;
            }
            var attrname = match2[1];
            var rest = match2[2];
            var attrvalue = match2[3];
            if (!rest) {
                attrvalue = null;
            } else if ((attrvalue[0] == "'" && attrvalue[attrvalue.length-1] == "'") || (attrvalue[0] == '"' && attrvalue[attrvalue.length-1] == '"')) {
                attrvalue = attrvalue.slice(1, -1);
            }
            if (attrvalue) {
                attrvalue = unescape(attrvalue);
            }
            attrs.push([attrname.toLowerCase(), attrvalue]);
            k = k + match2.index + match2[0].length - 1;
        }
        var end = rawdata.slice(k, endpos).trim();
        if (![">", "/>"].includes(end)) {
            class_var.handle_data(rawdata.substring(i, endpos));
            return endpos;
        }
        if (end.endsWith('/>')) {
            class_var.handle_startendtag(tag, attrs);
        } else {
            class_var.handle_starttag(tag, attrs);
            if (class_var.CDATA_CONTENT_ELEMENTS.includes(tag)) {
                class_var.set_cdata_mode(tag);
            }
        }
        return endpos;
    }
    function check_for_whole_start_tag(i) {
        var rawdata = class_var.rawdata;
        var match = LOCATESTARTTAGEND_TOLERANT.exec(rawdata.substring(i));
        if (match) {
            var j = i + match.index + match[0].length;
            var next = rawdata.substring(j, j + 1);
            if (next === ">") {
                return j + 1;
            }
            if (next === "/") {
                if (rawdata.startsWith("/>", j)) {
                    return j + 2;
                }
                if (rawdata.startsWith("/", j)) {
                    return -1;
                }
                if (j > i) {
                    return j;
                } else {
                    return i + 1;
                }
            }
            if (next === "") {
                return -1;
            }
            if ("abcdefghijklmnopqrstuvwxyz=/ABCDEFGHIJKLMNOPQRSTUVWXYZ".includes(next)) {
                return -1;
            }
            if (j > i) {
                return j;
            } else {
                return i + 1;
            }
        }
        throw new Error("we should not get here!");
    }
    function parse_endtag(i) {
        var rawdata = class_var.rawdata;
        if (rawdata.substring(i, i+2) !== "</") {
            throw new Error("unexpected call to parse_endtag");
        }
        var match = ENDENDTAG.exec(rawdata.substring(i + 1));
        if (!match) {
            return -1;
        }
        var gtpos = match.index + match[0].length + i + 1;
        match = ENDTAGFIND.exec(rawdata.substring(i));
        if (!match) {
            if (class_var.cdata_elem !== null) {
                class_var.handle_data(rawdata.substring(i, gtpos));
                return gtpos;
            }
            var namematch = TAGFIND_TOLERANT.exec(rawdata.substring(i + 2));
            if (!namematch) {
                if (rawdata.substring(i, i + 3) === '</>') {
                    return i + 3;
                } else {
                    return class_var.parse_bogus_comment(i, 1);
                }
            }
            var tagname = namematch[1].toLowerCase();
            gtpos = rawdata.indexOf('>', namematch.index + namematch[0].length + i + 2);
            class_var.handle_endtag(tagname);
            return gtpos + 1;
        }
        var elem = match[1].toLowerCase();
        if (class_var.cdata_elem !== null) {
            if (elem !== class_var.cdata_elem) {
                class_var.handle_data(rawdata.substring(i, gtpos));
                return gtpos;
            }
        }
        class_var.handle_endtag(elem);
        class_var.clear_cdata_mode();
        return gtpos;
    }
    function handle_startendtag(tag, attrs) {
        class_var.handle_starttag(tag, attrs);
        class_var.handle_endtag(tag);
    }
    function HTMLParser_dlm_handle_starttag(tag, attrs) {
    }
    function HTMLParser_dlm_handle_endtag(tag) {
    }
    function HTMLParser_dlm_handle_charref(name) {
    }
    function HTMLParser_dlm_handle_entityref(name) {
    }
    function HTMLParser_dlm_handle_data(data) {
    }
    function HTMLParser_dlm_handle_comment(data) {
    }
    function HTMLParser_dlm_handle_decl(decl) {
    }
    function HTMLParser_dlm_handle_pi(data) {
    }
    function HTMLParser_dlm_unknown_decl(data) {
    }
    var class_var = ParserBase();
    class_var._class_name = 'HTMLParser;' + class_var._class_name;
    class_var.__init__ = HTMLParser_dlm___init__;
    class_var.reset = reset;
    class_var.feed = feed;
    class_var.close = close;
    class_var.get_starttag_text = get_starttag_text;
    class_var.set_cdata_mode = set_cdata_mode;
    class_var.clear_cdata_mode = clear_cdata_mode;
    class_var.goahead = goahead;
    class_var.parse_html_declaration = parse_html_declaration;
    class_var.parse_bogus_comment = parse_bogus_comment;
    class_var.parse_pi = parse_pi;
    class_var.parse_starttag = parse_starttag;
    class_var.check_for_whole_start_tag = check_for_whole_start_tag;
    class_var.parse_endtag = parse_endtag;
    class_var.handle_startendtag = handle_startendtag;
    class_var.handle_starttag = HTMLParser_dlm_handle_starttag;
    class_var.handle_endtag = HTMLParser_dlm_handle_endtag;
    class_var.handle_charref = HTMLParser_dlm_handle_charref;
    class_var.handle_entityref = HTMLParser_dlm_handle_entityref;
    class_var.handle_data = HTMLParser_dlm_handle_data;
    class_var.handle_comment = HTMLParser_dlm_handle_comment;
    class_var.handle_decl = HTMLParser_dlm_handle_decl;
    class_var.handle_pi = HTMLParser_dlm_handle_pi;
    class_var.unknown_decl = HTMLParser_dlm_unknown_decl;
    HTMLParser_dlm___init__(param_0);
    return class_var;
}
function MyHTMLParserTester(...args) {
    function MyHTMLParserTester_dlm_handle_starttag(tag, attrs) {
        LISTENER_EVENT_LIST.push(["starttag", tag, attrs]);
    }
    function MyHTMLParserTester_dlm_handle_endtag(tag) {
        LISTENER_EVENT_LIST.push(["endtag", tag]);
    }
    function MyHTMLParserTester_dlm_handle_data(data) {
        LISTENER_EVENT_LIST.push(["data", data]);
    }
    function MyHTMLParserTester_dlm_handle_comment(data) {
        LISTENER_EVENT_LIST.push(["comment", data]);
    }
    function MyHTMLParserTester_dlm_handle_entityref(name) {
        LISTENER_EVENT_LIST.push(["entityref", name]);
    }
    function MyHTMLParserTester_dlm_handle_charref(name) {
        LISTENER_EVENT_LIST.push(["charref", name]);
    }
    function MyHTMLParserTester_dlm_handle_decl(data) {
        LISTENER_EVENT_LIST.push(["decl", data]);
    }
    function MyHTMLParserTester_dlm_handle_pi(data) {
        LISTENER_EVENT_LIST.push(["pi", data]);
    }
    function MyHTMLParserTester_dlm_unknown_decl(data) {
        LISTENER_EVENT_LIST.push(["unknown", data]);
    }
    var class_var = HTMLParser(...args);
    class_var._class_name = 'MyHTMLParserTester;' + class_var._class_name;
    class_var.handle_starttag = MyHTMLParserTester_dlm_handle_starttag;
    class_var.handle_endtag = MyHTMLParserTester_dlm_handle_endtag;
    class_var.handle_data = MyHTMLParserTester_dlm_handle_data;
    class_var.handle_comment = MyHTMLParserTester_dlm_handle_comment;
    class_var.handle_entityref = MyHTMLParserTester_dlm_handle_entityref;
    class_var.handle_charref = MyHTMLParserTester_dlm_handle_charref;
    class_var.handle_decl = MyHTMLParserTester_dlm_handle_decl;
    class_var.handle_pi = MyHTMLParserTester_dlm_handle_pi;
    class_var.unknown_decl = MyHTMLParserTester_dlm_unknown_decl;
    return class_var;
}
function main_test() {
    var p = MyHTMLParserTester(true);
    p.feed(EXAMPLE_HTML);
    LISTENER_EVENT_LIST.push(["PRINT", p.getpos()]);
    LISTENER_EVENT_LIST.push(["PRINT", p.get_starttag_text()]);
    LISTENER_EVENT_LIST.push(["PRINT", p.parse_declaration(0)]);
    p.close();
}
function additional_test() {
    var p = MyHTMLParserTester(true);
    p.rawdata = "<!DOCTYPE html>";
    var parse_res = p.parse_declaration(0);
    if (parse_res !== 15) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.rawdata = "<!DOCTYPE '2'>";
    parse_res = p.parse_declaration(0);
    if (parse_res !== 14) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.rawdata = "<!DOCTYPE [<!-->]> ";
    parse_res = p.parse_declaration(0);
    if (parse_res !== -1) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.rawdata = "<!DOCTYPE [%hello]> ";
    parse_res = p.parse_declaration(0);
    if (parse_res !== 19) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.rawdata = "<!DOCTYPE [ ]> ";
    parse_res = p.parse_declaration(0);
    if (parse_res !== 14) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.close();
}
function additional_test2() {
    var p = MyHTMLParserTester(true);
    p.convert_charrefs = false;
    p.feed("&abc<");
    p.reset();
    p.convert_charrefs = false;
    p.feed("&#abc<");
    p.reset();
    p.convert_charrefs = false;
    p.feed("&<");
    p.reset();
    p.convert_charrefs = false;
    p.feed("&#<");
    p.reset();
    p.close();
}
function additional_test3() {
    var p = MyHTMLParserTester(true);
    p.handle_startendtag("tag", []);
    p.reset();
    p.handle_charref("name");
    p.reset();
    p.handle_entityref("name");
    p.reset();
    p.handle_data("data");
    p.reset();
    p.handle_comment("data");
    p.reset();
    p.handle_decl("data");
    p.reset();
    p.handle_pi("data");
    p.reset();
    p.unknown_decl("data");
    p.reset();
    p = HTMLParser(true);
    p.handle_startendtag("tag", []);
    p.reset();
    p.handle_charref("name");
    p.reset();
    p.handle_entityref("name");
    p.reset();
    p.handle_data("data");
    p.reset();
    p.handle_comment("data");
    p.reset();
    p.handle_decl("data");
    p.reset();
    p.handle_pi("data");
    p.reset();
    p.unknown_decl("data");
    p.reset();
    p.close();
}
function additional_test4() {
    var p = HTMLParser(true);
    p.rawdata = "<abc/";
    var parse_res = p.check_for_whole_start_tag(0);
    if (parse_res !== -1) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.rawdata = '<tagname attr="value';
    parse_res = p.check_for_whole_start_tag(0);
    if (parse_res !== -1) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.rawdata = '<tagname attr';
    parse_res = p.check_for_whole_start_tag(0);
    if (parse_res !== -1) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.rawdata = '<tagname /';
    parse_res = p.check_for_whole_start_tag(0);
    if (parse_res !== -1) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.rawdata = '<tagname attr = "value" /';
    parse_res = p.check_for_whole_start_tag(0);
    if (parse_res !== -1) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.rawdata = '<tagname "value" /';
    parse_res = p.check_for_whole_start_tag(0);
    if (parse_res !== -1) {
        throw new Error("Assertion failed");
    }
    p.reset();
    p.close();
}
function additional_test5() {
    var res = escape("abc<>/'", true);
    if (res !== "abc&lt;&gt;/&#x27;") {
        throw new Error("Assertion failed");
    }
    res = escape("<>", true);
    if (res !== "&lt;&gt;") {
        throw new Error("Assertion failed");
    }
    res = escape("abc", true);
    if (res !== "abc") {
        throw new Error("Assertion failed");
    }
    res = escape("abc&", true);
    if (res !== "abc&amp;") {
        throw new Error("Assertion failed");
    }
    res = unescape("abc&lt;&gt;/&#x27;");
    if (res !== "abc<>/'") {
        throw new Error("Assertion failed");
    }
    res = unescape("&lt;&gt;");
    if (res !== "<>") {
        throw new Error("Assertion failed");
    }
    res = unescape("abc");
    if (res !== "abc") {
        throw new Error("Assertion failed");
    }
    res = unescape("abc&amp;");
    if (res !== "abc&") {
        throw new Error("Assertion failed");
    }
}
function additional_test6() {
    var p = HTMLParser(true);
    p.rawdata = "element>";
    p._parse_doctype_element(0, 0);
    p.reset();
    p.rawdata = "attlist element";
    p._parse_doctype_attlist(0, 0);
    p.reset();
    p.rawdata = "notation element";
    p._parse_doctype_notation(0, 0);
    p.reset();
    p.rawdata = "notation'";
    p._parse_doctype_notation(0, 0);
    p.reset();
    p.rawdata = "%element element";
    p._parse_doctype_entity(0, 0);
    p.reset();
    p.close();
}
function additional_tests() {
    additional_test();
    additional_test2();
    additional_test3();
    additional_test4();
    additional_test5();
    additional_test6();
}
function test_init() {
    // _replace_charref() LEAF
    _replace_charref('#xa');
    _replace_charref('#1');
    _replace_charref('#0');
    _replace_charref('#55297');
    _replace_charref('amp;');
    _replace_charref('amp;&');
    _replace_charref('am');

    // unescape() [_replace_charref]
    unescape('');
    unescape('&abc;');

    // HTMLParser constructor
    var hp = HTMLParser(true);

    // ParserBase() constructor
    var pb = ParserBase();

    // ParserBase.updatepos()
    pb.rawdata = '';
    pb.lineno = 0;
    pb.offset = 0;
    pb.updatepos(0, 0);
    pb.rawdata = '';
    pb.lineno = 0;
    pb.offset = 0;
    pb.updatepos(0, 1);
    pb.rawdata = '\n';
    pb.lineno = 0;
    pb.offset = 0;
    pb.updatepos(0, 10);

    // HTMLParser.check_for_whole_start_tag()
    hp.rawdata = '<a href="value">';
    hp.check_for_whole_start_tag(0);
    hp.rawdata = '<a href="value"/>';
    hp.check_for_whole_start_tag(0);
    hp.rawdata = '<a';
    hp.check_for_whole_start_tag(0);
    hp.rawdata = '<a a="v';
    hp.check_for_whole_start_tag(0);

    // HTMLParser.parse_pi()
    hp.rawdata = '<?a>';
    hp.parse_pi(0);

    // ParserBase.parse_comment()
    hp.rawdata = '<!--comment';
    hp.parse_comment(0, true);
    hp.rawdata = '<!--comment-->';
    hp.parse_comment(0, true);

    // HTMLParser.parse_bogus_comment()
    hp.rawdata = '<!bogus>';
    hp.parse_bogus_comment(0, true);

    // HTMLParser.parse_endtag()
    hp.rawdata = '</>';
    hp.parse_endtag(0);
    hp.rawdata = '</!fff>';
    hp.parse_endtag(0);
    hp.rawdata = '</a>';
    hp.parse_endtag(0);

    // HTMLParser.parse_starttag()
    hp.rawdata = '<a attr="v">value</a>';
    hp.parse_starttag(0);

    // ParserBase._scan_name()
    pb.rawdata = 'abc';
    pb._scan_name(0, 0);
    pb.rawdata = 'CDATA[ CDATA ]]>';
    pb._scan_name(0, 0);

    // ParserBase._parse_doctype_subset()
    hp.rawdata = '<!DOCTYPE [<!-->]> ';
    hp._parse_doctype_subset(11, 0);
    hp.rawdata = '<!DOCTYPE [%hello]> ';
    hp._parse_doctype_subset(11, 0);
    hp.rawdata = '<!DOCTYPE [ ]> ';
    hp._parse_doctype_subset(11, 0);

    // ParserBase._parse_doctype_notation()
    hp.rawdata = "notation'";
    hp._parse_doctype_notation(0, 0);
    hp.rawdata = "notation element";
    hp._parse_doctype_notation(0, 0);

    // ParserBase._parse_doctype_element()
    hp.rawdata = 'element>';
    hp._parse_doctype_element(0, 0);

    // ParserBase.parse_marked_section()
    hp.rawdata = '<![ENDIF]-->';
    hp.parse_marked_section(0, true);
    hp.rawdata = '<![CDATA[ CDATA ]]>';
    hp.parse_marked_section(0, true);

    // HTMLPaser.parse_html_declaration()
    hp.rawdata = '<![CDATA[ CDATA ]]>';
    hp.parse_html_declaration(0);
    hp.rawdata = '<!DOCTYPE html>';
    hp.parse_html_declaration(0);
    hp.rawdata = '<!fff>';
    hp.parse_html_declaration(0);

    // ParserBase.parse_declaration()
    hp.rawdata = '<!DOCTYPE html>';
    hp.parse_declaration(0);
    hp.rawdata = '<![ENDIF]-->';
    hp.parse_declaration(0);
    hp.rawdata = "<!DOCTYPE '2'>";
    hp.parse_declaration(0);
    hp.rawdata = '<!DOCTYPE [<!-->]> ';
    hp.parse_declaration(0);

    // ParserBase._parse_doctype_entity()
    hp.rawdata = '%element element';
    hp._parse_doctype_entity(0, 0);

    // goahead::handle_leftangle() first if-elif-else block
    hp.feed('<s');
    hp.feed('<s></s>');
    hp.feed('<!--c-->');
    hp.feed('<?pi?>');
    hp.feed('<!t>');
    hp.feed('<>');
    hp.feed('&abc<');
}
function test() {
    test_init();
    main_test();
    additional_tests();
}
test();
