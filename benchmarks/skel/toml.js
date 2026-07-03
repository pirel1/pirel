"use strict";

const TEST_STR1 = `\n[a]\r\nb = 1\r\nc = 2\n`;
const TEST_STR2 = `[[products]]\nname = "Nail"\nsku = 284758393\n# This is a comment\ncolor = "gray" # Hello World\n# name = { first = \'Tom\', last = \'Preston-Werner\' }\n# arr7 = [\n#  1, 2, 3\n# ]\n# lines  = \'\'\'\n# The first newline is\n# trimmed in raw strings.\n#   All other whitespace\n#   is preserved.\n# \'\'\'\n\n[animals]\ncolor = "gray" # col\nfruits = "apple" # a = [1,2,3]\na = 3\nb-comment = "a is 3"\n`;
const TIME_RE = new RegExp("^([0-9]{2}):([0-9]{2}):([0-9]{2})(\\.([0-9]{3,6}))?$");
const TEST_DICT = { "a": { "b": 1, "c": 2 } };
const NUMBER_WITH_UNDERSCORES_RE = new RegExp('([0-9])(_([0-9]))*');
const GROUPNAME_RE = new RegExp('^[A-Za-z0-9_-]+$');
const ESCAPES = ['0', 'b', 'f', 'n', 'r', 't', '"'];
const ESCAPED_CHARS = ['\0', '\b', '\f', '\n', '\r', '\t', '\"'];
const ESCAPE_TO_ESCAPED_CHARS = {};
for (var index = 0; index < ESCAPES.length; index++) {
    ESCAPE_TO_ESCAPED_CHARS[ESCAPES[index]] = ESCAPED_CHARS[index];
}


function user_check_type(obj, _type) {
    if (_type === null || _type === undefined) {
        return false;
    }
    if (Array.isArray(_type)) {
        for (var i = 0; i < _type.length; i++) {
            if (user_check_type(obj, _type[i])) {
                return true;
            }
        }
        return false;
    }
    var type_name = null;
    if (typeof _type === 'function' && _type.name) {
        type_name = _type.name;
    } else if (typeof _type === 'string') {
        var fn_match = _type.match(/<function\s+([^\s>]+)/);
        var cls_match = _type.match(/<class\s+'([^']+)'>/);
        if (fn_match) {
            type_name = fn_match[1];
        } else if (cls_match) {
            type_name = cls_match[1];
        } else {
            type_name = _type;
        }
    }
    if (type_name === 'dict' || type_name === 'object' || type_name === 'func_dict') {
        return obj !== null && typeof obj === 'object' && !Array.isArray(obj);
    }
    if (obj !== null && typeof obj === 'object' && typeof obj._class_name === 'string' && type_name) {
        var names = obj._class_name.split(';');
        for (var j = 0; j < names.length; j++) {
            if (names[j] === type_name) {
                return true;
            }
        }
    }
    if (typeof _type === 'string') {
        if (_type === 'string') return typeof obj === 'string' || obj instanceof String;
        if (_type === 'number') return typeof obj === 'number';
        if (_type === 'boolean') return typeof obj === 'boolean';
        if (_type === 'function') return typeof obj === 'function';
        return false;
    }
    if (_type === Number) return typeof obj === 'number';
    if (_type === String) return typeof obj === 'string' || obj instanceof String;
    if (_type === Boolean) return typeof obj === 'boolean';
    if (_type === Function) return typeof obj === 'function';
    if (_type === Object) return obj !== null && typeof obj === 'object';
    try {
        return obj instanceof _type;
    } catch (_e) {
        return false;
    }
}
function _self_split(s, sep, maxsplit) {
    var i = 0;
    var j = 0;
    var k = 0;
    var split = [];
    while (i < s.length && k < maxsplit) {
        if (s.slice(i, i + sep.length) === sep) {
            split.push(s.substring(j, i));
            j = i + sep.length;
            k += 1;
        }
        i += 1;
    }
    split.push(s.substring(j));
    var _return_value = split;
    return _return_value;
}
function func_dict(...args) {
    var class_var = {};
    return class_var;
}
function get_input(test_case_name) {
    const fs = require('fs');
    let decode_input = fs.readFileSync('toml.d/example.toml', 'utf8');
    decode_input = decode_input.split('################################################################################\n');
    for (let i of decode_input) {
        if (i.includes('## ' + test_case_name)) {
            return i;
        }
    }
}
function SkelClass(class_name) {
    var _class_var = {};
    _class_var._class_name = class_name;
    return _class_var;
}
function _get_encoder(obj) {
    return new TomlEncoder(obj.constructor, false);
}
function _get_base_exception(arg0, arg1, arg2) {
    return new Error(arg0, arg1, arg2);
}






function TomlDecodeError(param_0, param_1, param_2) {
    var class_var = _get_base_exception(param_0, param_1, param_2);
    return class_var;
}
function CommentValue(param_0, param_1, param_2, param_3) {
    function CommentValue_dlm___init__(val, comment, beginline, _dict) {
        class_var.val = val;
        var separator = beginline ? "\n" : " ";
        class_var.comment = separator + comment;
        class_var._dict = _dict;
    }
    function __getitem__(key) {
        return class_var.val[key];
    }
    function __setitem__(key, value) {
        class_var.val[key] = value;
    }
    function dump(dump_value_func) {
        var retstr = dump_value_func(class_var.val);
        return retstr.toString() + class_var.comment;
    }
    var class_var = SkelClass('CommentValue');
    class_var.__init__ = CommentValue_dlm___init__;
    class_var.__getitem__ = __getitem__;
    class_var.__setitem__ = __setitem__;
    class_var.dump = dump;
    CommentValue_dlm___init__(param_0, param_1, param_2, param_3);
    return class_var;
}
function _strictly_valid_num(n) {
    n = n.trim();
    if (!n) {
        return false;
    }
    if (n[0] === '_') {
        return false;
    }
    if (n[n.length - 1] === '_') {
        return false;
    }
    if (n.includes("_.") || n.includes("._")) {
        return false;
    }
    if (n.length === 1) {
        return true;
    }
    if (n[0] === '0' && !['.', 'o', 'b', 'x'].includes(n[1])) {
        return false;
    }
    if (n[0] === '+' || n[0] === '-') {
        n = n.substring(1);
        if (n.length > 1 && n[0] === '0' && n[1] !== '.') {
            return false;
        }
    }
    if (n.includes('__')) {
        return false;
    }
    return true;
}
function loads(s, _dict, decoder) {
    function handle_keyname() {
        key += item;
        if (item === '\n') {
            throw new TomlDecodeError("Key name found without value. Reached end of line.", original, i);
        }
        if (openstring) {
            if (item === openstrchar) {
                var oddbackslash = false;
                var k = 1;
                while (i >= k && sl[i - k] === '\\') {
                    oddbackslash = !oddbackslash;
                    k += 1;
                }
                if (!oddbackslash) {
                    keyname = 2;
                    openstring = false;
                    openstrchar = "";
                }
            }
            return "continue";
        } else if (keyname === 1) {
            if (/\s/.test(item)) {
                keyname = 2;
                return "continue";
            } else if (item === '.') {
                dottedkey = true;
                return "continue";
            } else if (/[\w-]/.test(item)) {
                return "continue";
            } else if (dottedkey && sl[i - 1] === '.' && (item === '"' || item === "'")) {
                openstring = true;
                openstrchar = item;
                return "continue";
            }
        } else if (keyname === 2) {
            if (/\s/.test(item)) {
                if (dottedkey) {
                    var nextitem = sl[i + 1];
                    if (!/\s/.test(nextitem) && nextitem !== '.') {
                        keyname = 1;
                    }
                }
                return "continue";
            }
            if (item === '.') {
                dottedkey = true;
                var nextitem = sl[i + 1];
                if (!/\s/.test(nextitem) && nextitem !== '.') {
                    keyname = 1;
                }
                return "continue";
            }
        }
        if (item === '=') {
            keyname = 0;
            prev_key = key.slice(0, -1).trim();
            key = '';
            dottedkey = false;
        } else {
            throw new TomlDecodeError("Found invalid character in key name: '" + item + "'. Try quoting the key name.", original, i);
        }
    }
    function handle_single_quote_1() {
        var k = 1;
        while (sl[i - k] === "'") {
            k += 1;
            if (k === 3) {
                break;
            }
        }
        if (k === 3) {
            multilinestr = !multilinestr;
            openstring = multilinestr;
        } else {
            openstring = !openstring;
        }
        if (openstring) {
            openstrchar = "'";
        } else {
            openstrchar = "";
        }
    }
    function handle_single_quote_2() {
        var oddbackslash = false;
        var k = 1;
        var tripquote = false;
        while (sl[i - k] === '"') {
            k += 1;
            if (k === 3) {
                tripquote = true;
                break;
            }
        }
        if (k === 1 || (k === 3 && tripquote)) {
            while (sl[i - k] === '\\') {
                oddbackslash = !oddbackslash;
                k += 1;
            }
        }
        if (!oddbackslash) {
            if (tripquote) {
                multilinestr = !multilinestr;
                openstring = multilinestr;
            } else {
                openstring = !openstring;
            }
        }
        if (openstring) {
            openstrchar = '"';
        } else {
            openstrchar = "";
        }
    }
    function handle_comment() {
        var j = i;
        var comment = "";
        while (sl[j] !== '\n') {
            comment += sl[j];
            sl[j] = ' ';
            j++;
        }
        if (!openarr) {
            decoder.preserve_comment(line_no, prev_key, comment, beginline);
        }
    }
    function handle_backslash() {
        if (item === '\n') {
            if (openstring || multilinestr) {
                if (!multilinestr) {
                    throw new TomlDecodeError("Unbalanced quotes", original, i);
                }
                if ((sl[i - 1] === "'" || sl[i - 1] === '"') && (sl[i - 2] === sl[i - 1])) {
                    sl[i] = sl[i - 1];
                    if (sl[i - 3] === sl[i - 1]) {
                        sl[i - 3] = ' ';
                    }
                }
            } else if (openarr) {
                sl[i] = ' ';
            } else {
                beginline = true;
            }
            line_no++;
        } else if (beginline && sl[i] !== ' ' && sl[i] !== '\t') {
            beginline = false;
            if (!keygroup && !arrayoftables) {
                if (sl[i] === '=') {
                    throw new TomlDecodeError("Found empty keyname. ", original, i);
                }
                keyname = 1;
                key += item;
            }
        }
    }
    function handle_bracket() {
        if (item === '[' && (!openstring && !keygroup && !arrayoftables)) {
            if (beginline) {
                if (sl.length > i + 1 && sl[i + 1] === '[') {
                    arrayoftables = true;
                } else {
                    keygroup = true;
                }
            } else {
                openarr += 1;
            }
        }
        if (item === ']' && !openstring) {
            if (keygroup) {
                keygroup = false;
            } else if (arrayoftables) {
                if (sl[i - 1] === ']') {
                    arrayoftables = false;
                }
            } else {
                openarr -= 1;
            }
        }
    }
    function loads_dlm_handle_remaining() {
        function handle_multikey() {
            if (multibackslash) {
                multilinestr += line;
            } else {
                multilinestr += line;
            }
            multibackslash = false;
            var closed = false;
            if (multilinestr[0] === '[') {
                closed = line[line.length - 1] === ']';
            } else if (line.length > 2) {
                closed = line[line.length - 1] === multilinestr[0] && line[line.length - 2] === multilinestr[0] && line[line.length - 3] === multilinestr[0];
            }
            if (closed) {
                try {
                    var [value, vtype] = decoder.load_value(multilinestr, true);
                } catch (err) {
                    throw new TomlDecodeError(err.toString(), original, pos);
                }
                currentlevel[multikey] = value;
                multikey = null;
                multilinestr = "";
            } else {
                var k = multilinestr.length - 1;
                while (k > -1 && multilinestr[k] === '\\') {
                    multibackslash = !multibackslash;
                    k -= 1;
                }
                if (multibackslash) {
                    multilinestr = multilinestr.slice(0, -1);
                } else {
                    multilinestr += "\n";
                }
            }
            return "continue";
        }
        function handle_start_bracket() {
            function handle_groupname() {
                var i = 0;
                while (i < groups.length) {
                    groups[i] = groups[i].trim();
                    if (groups[i].length > 0 && (groups[i][0] === '"' || groups[i][0] === "'")) {
                        var groupstr = groups[i];
                        var j = i + 1;
                        while (groupstr[0] !== groupstr[groupstr.length - 1] || groupstr.length === 1) {
                            j++;
                            if (j > groups.length + 2) {
                                throw new TomlDecodeError("Invalid group name '" + groupstr + "' Something went wrong.", original, pos);
                            }
                            groupstr = groups.slice(i, j).join('.').trim();
                        }
                        groups[i] = groupstr.substring(1, groupstr.length - 1);
                        groups.splice(i + 1, j - (i + 1));
                    } else if (!GROUPNAME_RE.test(groups[i])) {
                        throw new TomlDecodeError("Invalid group name '" + groups[i] + "'. Try quoting it.", original, pos);
                    }
                    i++;
                }
            }
            arrayoftables = false;
            if (line.length === 1) {
                throw new TomlDecodeError("Opening key group bracket on line by itself.", original, pos);
            }
            var splitstr = null;
            if (line[1] === '[') {
                arrayoftables = true;
                line = line.substring(2);
                splitstr = ']]';
            } else {
                line = line.substring(1);
                splitstr = ']';
            }
            var i = 1;
            var quotesplits = decoder._get_split_on_quotes(line);
            var quoted = false;
            for (var quotesplit of quotesplits) {
                if (!quoted && quotesplit.includes(splitstr)) {
                    break;
                }
                i += (quotesplit.match(new RegExp(splitstr, "g")) || []).length;
                quoted = !quoted;
            }
            line = _self_split(line, splitstr, i);
            if (line.length < i + 1 || line[line.length - 1].trim() !== "") {
                throw new TomlDecodeError("Key group not on a line by itself.", original, pos);
            }
            var groups = line.slice(0, -1).join(splitstr).split('.');
            handle_groupname();
            currentlevel = retval;
            for (i = 0; i < groups.length; i++) {
                var group = groups[i];
                if (group === "") {
                    throw new TomlDecodeError("Can't have a keygroup with an empty name", original, pos);
                }
                try {
                    if (currentlevel.constructor.name === 'Array' && isNaN(parseInt(group))) {
                        throw new TypeError("abc");
                    }
                    if (!currentlevel.hasOwnProperty(group)) {
                        throw new RangeError("abc");
                    }
                    if (i === groups.length - 1) {
                        if (implicitgroups.includes(group)) {
                            implicitgroups.splice(implicitgroups.indexOf(group), 1);
                            if (arrayoftables) {
                                throw new TomlDecodeError("An implicitly defined table can't be an array", original, pos);
                            }
                        } else if (arrayoftables) {
                            currentlevel[group].push(decoder['get_empty_table']());
                        } else {
                            throw new TomlDecodeError("What? " + group + " already exists?" + JSON.stringify(currentlevel), original, pos);
                        }
                    }
                } catch (error) {
                    if (error instanceof TypeError) {
                        currentlevel = currentlevel[currentlevel.length - 1];
                        if (!(group in currentlevel)) {
                            currentlevel[group] = decoder['get_empty_table']();
                            if (i === groups.length - 1 && arrayoftables) {
                                currentlevel[group] = [decoder['get_empty_table']()];
                            }
                        }
                    } else if (error instanceof RangeError) {
                        if (i !== groups.length - 1) {
                            implicitgroups.push(group);
                        }
                        currentlevel[group] = decoder['get_empty_table']();
                        if (i === groups.length - 1 && arrayoftables) {
                            currentlevel[group] = [decoder['get_empty_table']()];
                        }
                    }
                }
                currentlevel = currentlevel[group];
                if (arrayoftables) {
                    try {
                        currentlevel = currentlevel[currentlevel.length - 1];
                    } catch (KeyError) {
                    }
                }
            }
        }
        var s = sl.join('');
        s = s.split('\n');
        var multikey = null;
        var multilinestr = "";
        var multibackslash = false;
        var pos = 0;
        for (var idx = 0; idx < s.length; idx++) {
            var line = s[idx];
            if (idx > 0) {
                pos += s[idx - 1].length + 1;
            }
            decoder.embed_comments(idx, currentlevel);
            if (!multilinestr || multibackslash || !multilinestr.includes('\n')) {
                line = line.trim();
            }
            if (line === "" && (!multikey || multibackslash)) {
                continue;
            }
            if (multikey) {
                var act = handle_multikey();
                if (act === "continue") {
                    continue;
                }
            }
            if (line[0] === '[') {
                handle_start_bracket();
            } else if (line[0] === "{") {
                if (line[line.length - 1] !== "}") {
                    throw new TomlDecodeError("Line breaks are not allowed in inline objects", original, pos);
                }
                try {
                    decoder.load_inline_object(line, currentlevel, multikey, multibackslash);
                } catch (err) {
                    throw new TomlDecodeError(err.toString(), original, pos);
                }
            } else if (line.includes("=")) {
                try {
                    var ret = decoder.load_line(line, currentlevel, multikey, multibackslash);
                } catch (err) {
                    throw new TomlDecodeError(err.toString(), original, pos);
                }
                if (ret !== null) {
                    multikey = ret[0];
                    multilinestr = ret[1];
                    multibackslash = ret[2];
                }
            }
        }
        return retval;
    }
    var implicitgroups = [];
    if (decoder === null) {
        decoder = new TomlDecoder(_dict);
    }
    var retval = decoder.get_empty_table();
    var currentlevel = retval;
    if (typeof s !== 'string') {
        throw new TypeError("Expecting something like a string");
    }
    var original = s;
    var sl = s.split('');
    var openarr = 0;
    var openstring = false;
    var openstrchar = "";
    var multilinestr = false;
    var arrayoftables = false;
    var beginline = true;
    var keygroup = false;
    var dottedkey = false;
    var keyname = 0;
    var key = '';
    var prev_key = '';
    var line_no = 1;
    for (var i = 0; i < sl.length; i++) {
        var item = sl[i];
        if (item === '\r' && sl.length > i + 1 && sl[i + 1] === '\n') {
            sl[i] = ' ';
            continue;
        }
        if (keyname) {
            var act = handle_keyname();
            if (act === "continue") {
                continue;
            }
        }
        if (item === "'" && openstrchar !== '"') {
            handle_single_quote_1();
        }
        if (item === '"' && openstrchar !== "'") {
            handle_single_quote_2();
        }
        if (item === '#' && (!openstring && !keygroup && !arrayoftables)) {
            act = handle_comment();
            if (act === "break") {
                break;
            }
        }
        handle_bracket();
        handle_backslash();
    }
    if (keyname) {
        throw new TomlDecodeError("Key name found without value. Reached end of file.", original, s.length);
    }
    if (openstring) {
        throw new TomlDecodeError("Unterminated string found. Reached end of file.", original, s.length);
    }
    return loads_dlm_handle_remaining();
}
function _load_date(val) {
    var microsecond = 0;
    var tz = null;
    try {
        if (val.length > 19) {
            if (val[19] === '.') {
                var subsecondval, tzval;
                if (val[val.length - 1].toUpperCase() === 'Z') {
                    subsecondval = val.substring(20, val.length - 1);
                    tzval = "Z";
                } else {
                    var subsecondvalandtz = val.substring(20);
                    var splitpoint;
                    if (subsecondvalandtz.includes('+')) {
                        splitpoint = subsecondvalandtz.indexOf('+');
                        subsecondval = subsecondvalandtz.substring(0, splitpoint);
                        tzval = subsecondvalandtz.substring(splitpoint);
                    } else if (subsecondvalandtz.includes('-')) {
                        splitpoint = subsecondvalandtz.indexOf('-');
                        subsecondval = subsecondvalandtz.substring(0, splitpoint);
                        tzval = subsecondvalandtz.substring(splitpoint);
                    } else {
                        tzval = null;
                        subsecondval = subsecondvalandtz;
                    }
                }
                if (tzval !== null) {
                    tz = new TomlTz(tzval);
                }
                microsecond = parseInt(parseInt(subsecondval) * Math.pow(10, (6 - subsecondval.length)));
            } else {
                tz = new TomlTz(val.substring(19).toUpperCase());
            }
        }
    } catch (e) {
        tz = null;
    }
    if (!val.substring(1).includes("-")) {
        return null;
    }
    var d = null;
    try {
        if (val.length === 10) {
            d = new Date(Date.UTC(parseInt(val.substring(0, 4)), parseInt(val.substring(5, 7)) - 1, parseInt(val.substring(8, 10))));
        } else {
            d = new Date(Date.UTC(parseInt(val.substring(0, 4)), parseInt(val.substring(5, 7)) - 1, parseInt(val.substring(8, 10)), parseInt(val.substring(11, 13)), parseInt(val.substring(14, 16)), parseInt(val.substring(17, 19)), microsecond));
        }
        d.tz = tz;
        if (isNaN(d)) {
            throw new Error("Invalid date");
        }
    } catch (e) {
        return null;
    }
    return d;
}
function unichr(s) {
    return String.fromCharCode(s);
}
function _load_unicode_escapes(v, hexbytes, prefix) {
    var skip = false;
    var i = v.length - 1;
    while (i > -1 && v[i] === '\\') {
        skip = !skip;
        i -= 1;
    }
    for (var hx of hexbytes) {
        if (skip) {
            skip = false;
            i = hx.length - 1;
            while (i > -1 && hx[i] === '\\') {
                skip = !skip;
                i -= 1;
            }
            v += prefix;
            v += hx;
            continue;
        }
        var hxb = "";
        i = 0;
        var hxblen = 4;
        if (prefix === "\\U") {
            hxblen = 8;
        }
        hxb = hx.substring(i, i + hxblen).toLowerCase();
        if (/[^0123456789abcdef]/.test(hxb)) {
            throw new Error("Invalid escape sequence: " + hxb);
        }
        if (hxb[0] === "d" && /[^01234567]/.test(hxb[1])) {
            throw new Error("Invalid escape sequence: " + hxb + ". Only scalar unicode points are allowed.");
        }
        v += unichr(parseInt(hxb, 16));
        v += hx.substring(hxb.length);
    }
    return v;
}
function _unescape(v) {
    var i = 0;
    var backslash = false;
    while (i < v.length) {
        if (backslash) {
            backslash = false;
            if (ESCAPES.includes(v[i])) {
                v = v.substring(0, i - 1) + ESCAPE_TO_ESCAPED_CHARS[v[i]] + v.substring(i + 1);
            } else if (v[i] === '\\') {
                v = v.substring(0, i - 1) + v.substring(i);
            } else if (v[i] === 'u' || v[i] === 'U') {
                i += 1;
            } else {
                throw new Error("Reserved escape sequence used");
            }
            continue;
        } else if (v[i] === '\\') {
            backslash = true;
        }
        i += 1;
    }
    return v;
}
function InlineTableDict(...args) {
    var class_var = SkelClass('InlineTableDict');
    return class_var;
}
function DynamicInlineTableDict(...args) {
    var class_var = {};
    return class_var;
}
function TomlDecoder(param_0) {
    function TomlDecoder_dlm___init__(_dict) {
        class_var._dict = _dict;
    }
    function TomlDecoder_dlm_get_empty_table() {
        return class_var._dict();
    }
    function get_empty_inline_table() {
        return DynamicInlineTableDict();
    }
    function load_inline_object(line, currentlevel, multikey, multibackslash) {
        var candidate_groups = line.slice(1, -1).split(",");
        var groups = [];
        if (candidate_groups.length === 1 && !candidate_groups[0].trim()) {
            candidate_groups.pop();
        }
        while (candidate_groups.length > 0) {
            var candidate_group = candidate_groups.shift();
            var _chunks = candidate_group.split('=');
            if (_chunks.length < 2) {
                throw new Error("Invalid inline table encountered");
            }
            var value = _chunks[1];
            value = value.trim();
            if (value[0] === value[value.length - 1] && "'\"".includes(value[0]) || ('-0123456789'.includes(value[0]) || ['true', 'false'].includes(value) || (value[0] === "[" && value[value.length - 1] === "]") || (value[0] === '{' && value[value.length - 1] === '}'))) {
                groups.push(candidate_group);
            } else if (candidate_groups.length > 0) {
                candidate_groups[0] = candidate_group + "," + candidate_groups[0];
            } else {
                throw new Error("Invalid inline table value encountered");
            }
        }
        for (var _toml_i1 = 0; _toml_i1 < groups.length; _toml_i1++) {
            var group = groups[_toml_i1];
            var status = class_var.load_line(group, currentlevel, multikey, multibackslash);
            if (status !== null) {
                break;
            }
        }
    }
    function _get_split_on_quotes(line) {
        var doublequotesplits = line.split('"');
        var quoted = false;
        var quotesplits = [];
        if (doublequotesplits.length > 1 && doublequotesplits[0].includes("'")) {
            var singlequotesplits = doublequotesplits[0].split("'");
            doublequotesplits = doublequotesplits.slice(1);
            while (singlequotesplits.length % 2 === 0 && doublequotesplits.length) {
                var _res1 = '"' + doublequotesplits[0];
                singlequotesplits[singlequotesplits.length - 1] = singlequotesplits[singlequotesplits.length - 1] + _res1;
                doublequotesplits = doublequotesplits.slice(1);
                if (singlequotesplits[singlequotesplits.length - 1].includes("'")) {
                    singlequotesplits = singlequotesplits.slice(0, -1).concat(singlequotesplits[singlequotesplits.length - 1].split("'"));
                }
            }
            quotesplits = quotesplits.concat(singlequotesplits);
        }
        for (var doublequotesplit of doublequotesplits) {
            if (quoted) {
                quotesplits.push(doublequotesplit);
            } else {
                quotesplits = quotesplits.concat(doublequotesplit.split("'"));
                quoted = !quoted;
            }
        }
        return quotesplits;
    }
    function load_line(line, currentlevel, multikey, multibackslash) {
        var i = 1;
        var quotesplits = class_var._get_split_on_quotes(line);
        var quoted = false;
        for (var quotesplit of quotesplits) {
            if (!quoted && quotesplit.includes('=')) {
                break;
            }
            i += (quotesplit.match(/=/g) || []).length;
            quoted = !quoted;
        }
        var pair = _self_split(line, '=', i);
        var strictly_valid = _strictly_valid_num(pair[pair.length - 1]);
        if (NUMBER_WITH_UNDERSCORES_RE.test(pair[pair.length - 1]) && pair[pair.length - 1][0] !== " ") {
            pair[pair.length - 1] = pair[pair.length - 1].replace(/_/g, '');
        }
        while (pair[pair.length - 1].length > 0 && (pair[pair.length - 1][0] !== ' ' && pair[pair.length - 1][0] !== '\t' && pair[pair.length - 1][0] !== "'" && pair[pair.length - 1][0] !== '"' && pair[pair.length - 1][0] !== '[' && pair[pair.length - 1][0] !== '{' && pair[pair.length - 1].trim() !== 'true' && pair[pair.length - 1].trim() !== 'false')) {
            if (!isNaN(parseFloat(pair[pair.length - 1])) && !pair[pair.length - 1].includes("1979") && !pair[pair.length - 1].includes("=")) {
                break;
            }
            if (_load_date(pair[pair.length - 1]) !== null) {
                break;
            }
            if (TIME_RE.test(pair[pair.length - 1])) {
                break;
            }
            i++;
            var prev_val = pair[pair.length - 1];
            pair = _self_split(line, '=', i);
            if (prev_val === pair[pair.length - 1]) {
                throw new Error("Invalid date or number");
            }
            if (strictly_valid) {
                strictly_valid = _strictly_valid_num(pair[pair.length - 1]);
            }
        }
        pair = [pair.slice(0, -1).join('=').trim(), pair[pair.length - 1].trim()];
        if (pair[0].includes('.')) {
            if (pair[0].includes('"') || pair[0].includes("'")) {
                quotesplits = class_var._get_split_on_quotes(pair[0]);
                quoted = false;
                var levels = [];
                for (quotesplit of quotesplits) {
                    if (quoted) {
                        levels.push(quotesplit);
                    } else {
                        levels = levels.concat(quotesplit.split('.').map(level => level.trim()));
                    }
                    quoted = !quoted;
                }
            } else {
                levels = pair[0].split('.').map(level => level.trim());
            }
            while (levels[levels.length - 1] === "") {
                levels.pop();
            }
            for (var level of levels.slice(0, -1)) {
                if (level === "") {
                    continue;
                }
                if (!(level in currentlevel)) {
                    currentlevel[level] = class_var.get_empty_table();
                }
                currentlevel = currentlevel[level];
            }
            pair[0] = levels[levels.length - 1];
        } else if ((pair[0][0] === '"' || pair[0][0] === "'") && (pair[0][pair[0].length - 1] === pair[0][0])) {
            pair[0] = _unescape(pair[0].substring(1, pair[0].length - 1));
        }
        var [k, koffset] = class_var._load_line_multiline_str(pair[1]);
        if (k > -1) {
            while (k > -1 && pair[1][k + koffset] === '\\') {
                multibackslash = !multibackslash;
                k--;
            }
            if (multibackslash) {
                var multilinestr = pair[1].slice(0, -1);
            } else {
                var multilinestr = pair[1] + "\n";
            }
            multikey = pair[0];
        } else {
            var [value, vtype] = class_var.load_value(pair[1].replace(), strictly_valid);
        }
        if (currentlevel.hasOwnProperty(pair[0])) {
            throw new Error("Duplicate keys!");
        }
        else {
            if (multikey !== null && multikey !== false) {
                var _return_value = [multikey, multilinestr, multibackslash];
                return _return_value;
            } else {
                currentlevel[pair[0]] = value;
            }
        }
        var _return_value = null;
        return _return_value;
    }
    function _load_line_multiline_str(p) {
        var poffset = 0;
        if (p.length < 3) {
            return [-1, poffset];
        }
        if (p[0] === '[' && (p.trim().slice(-1) !== ']' && class_var._load_array_isstrarray(p))) {
            var newp = p.slice(1).trim().split(',');
            while (newp.length > 1 && newp[newp.length - 1][0] !== '"' && newp[newp.length - 1][0] !== "'") {
                newp = newp.slice(0, -2).concat([newp[newp.length - 2] + ',' + newp[newp.length - 1]]);
            }
            newp = newp[newp.length - 1];
            poffset = p.length - newp.length;
            p = newp;
        }
        if (p[0] !== '"' && p[0] !== "'") {
            return [-1, poffset];
        }
        if (p[1] !== p[0] || p[2] !== p[0]) {
            return [-1, poffset];
        }
        if (p.length > 5 && p[p.length - 1] === p[0] && p[p.length - 2] === p[0] && p[p.length - 3] === p[0]) {
            return [-1, poffset];
        }
        return [p.length - 1, poffset];
    }
    function load_value(v, strictly_valid) {
        function TomlDecoder_dlm_load_value_dlm_handle_remaining() {
            if (parsed_date !== null) {
                return [parsed_date, "date"];
            }
            if (!strictly_valid) {
                throw new Error("Weirdness with leading zeroes or underscores in your number.");
            }
            var itype = "int";
            var neg = false;
            if (v[0] === '-') {
                neg = true;
                v = v.substring(1);
            } else if (v[0] === '+') {
                v = v.substring(1);
            }
            v = v.replace(/_/g, '');
            var lowerv = v.toLowerCase();
            if (v.includes('.') || (!v.includes('x') && (v.includes('e') || v.includes('E')))) {
                if (v.includes('.') && v.split('.', 2)[1] === '') {
                    throw new Error("This float is missing digits after the point");
                }
                if (!'0123456789'.includes(v[0])) {
                    throw new Error("This float doesn't have a leading digit");
                }
                v = parseFloat(v);
                v = v < 1e10 && v % 1 === 0 ? parseInt(v) : v;
                itype = "float";
            } else if (lowerv.length === 3 && (lowerv === 'inf' || lowerv === 'nan')) {
                v = parseFloat(v);
                itype = "float";
            }
            if (itype === "int") {
                v = parseInt(v, 0);
            }
            if (neg) {
                return [0 - v, itype];
            }
            return [v, itype];
        }
        if (!v) {
            throw new Error("Empty value is invalid");
        }
        if (v === 'true') {
            return [true, "bool"];
        } else if (v.toLowerCase() === 'true') {
            throw new Error("Only all lowercase booleans allowed");
        } else if (v === 'false') {
            return [false, "bool"];
        } else if (v.toLowerCase() === 'false') {
            throw new Error("Only all lowercase booleans allowed");
        } else if (v[0] === '"' || v[0] === "'") {
            var quotechar = v[0];
            var testv = v.slice(1).split(quotechar);
            var triplequote = false;
            var triplequotecount = 0;
            if (testv.length > 1 && testv[0] === '' && testv[1] === '') {
                testv = testv.slice(2);
                triplequote = true;
            }
            var closed = false;
            for (var tv of testv) {
                if (tv === '') {
                    if (triplequote) {
                        triplequotecount += 1;
                    } else {
                        closed = true;
                    }
                } else {
                    var oddbackslash = false;
                    var i = -1;
                    i = i >= 0 ? i : tv.length + i;
                    var j = tv[i];
                    while (j === '\\') {
                        oddbackslash = !oddbackslash;
                        i -= 1;
                        i = i >= 0 ? i : tv.length + i;
                        j = tv[i];
                    }
                    if (!oddbackslash) {
                        if (closed) {
                            throw new Error("Found tokens after a closed string. Invalid TOML.");
                        } else if (!triplequote || triplequotecount > 1) {
                            closed = true;
                        } else {
                            triplequotecount = 0;
                        }
                    }
                }
            }
            if (quotechar === '"') {
                var escapeseqs = v.split('\\').slice(1);
                var backslash = false;
                for (var i of escapeseqs) {
                    if (i === '') {
                        backslash = !backslash;
                    } else {
                        if (!ESCAPES.includes(i[0]) && (i[0] !== 'u' && i[0] !== 'U' && !backslash)) {
                            throw new Error("Reserved escape sequence used");
                        }
                        if (backslash) {
                            backslash = false;
                        }
                    }
                }
                for (var prefix of ["\\u", "\\U"]) {
                    if (v.includes(prefix)) {
                        var hexbytes = v.split(prefix);
                        v = _load_unicode_escapes(hexbytes[0], hexbytes.slice(1), prefix);
                    }
                }
                v = _unescape(v);
            }
            if (v.length > 1 && v[1] === quotechar && (v.length < 3 || v[1] === v[2])) {
                v = v.slice(2, -2);
            }
            return [v.slice(1, -1), "str"];
        } else if (v[0] === '[') {
            return [class_var.load_array(v), "array"];
        } else if (v[0] === '{') {
            var inline_object = get_empty_inline_table();
            class_var.load_inline_object(v, inline_object, false, false);
            return [inline_object, "inline_object"];
        } else {
            var parsed_date = _load_date(v);
            return TomlDecoder_dlm_load_value_dlm_handle_remaining();
        }
    }
    function bounded_string(s) {
        if (s.length === 0) {
            return true;
        }
        if (s[s.length - 1] !== s[0]) {
            return false;
        }
        var i = -2;
        var backslash = false;
        while (s.length + i > 0) {
            if (s[i] === "\\") {
                backslash = !backslash;
                i -= 1;
            } else {
                break;
            }
        }
        return !backslash;
    }
    function _load_array_isstrarray(a) {
        a = a.slice(1, -1).trim();
        if (a !== '' && (a[0] === '"' || a[0] === "'")) {
            return true;
        }
        return false;
    }
    function load_array(a) {
        var retval = [];
        a = a.trim();
        if (!a.slice(1, -1).includes('[') || a.slice(1, -1).split('[')[0].trim() !== "") {
            var strarray = class_var._load_array_isstrarray(a);
            if (!a.slice(1, -1).trim().startsWith('{')) {
                a = a.slice(1, -1).split(',');
            } else {
                var new_a = [];
                var start_group_index = 1;
                var end_group_index = 2;
                var open_bracket_count = a[start_group_index] === '{' ? 1 : 0;
                var in_str = false;
                while (end_group_index < a.slice(1).length) {
                    if (a[end_group_index] === '"' || a[end_group_index] === "'") {
                        if (in_str) {
                            var backslash_index = end_group_index - 1;
                            while (backslash_index > -1 && a[backslash_index] === '\\') {
                                in_str = !in_str;
                                backslash_index -= 1;
                            }
                        }
                        in_str = !in_str;
                    }
                    if (!in_str && a[end_group_index] === '{') {
                        open_bracket_count += 1;
                    }
                    if (in_str || a[end_group_index] !== '}') {
                        end_group_index += 1;
                        continue;
                    } else if (a[end_group_index] === '}' && open_bracket_count > 1) {
                        open_bracket_count -= 1;
                        end_group_index += 1;
                        continue;
                    }
                    end_group_index += 1;
                    new_a.push(a.slice(start_group_index, end_group_index));
                    start_group_index = end_group_index + 1;
                    while (start_group_index < a.slice(1).length && a[start_group_index] !== '{') {
                        start_group_index += 1;
                    }
                    end_group_index = start_group_index + 1;
                }
                a = new_a;
            }
            var b = 0;
            if (strarray) {
                while (b < a.length - 1) {
                    var ab = a[b].trim();
                    while (!class_var.bounded_string(ab) || (ab.length > 2 && ab[0] === ab[1] === ab[2] && ab[ab.length - 2] !== ab[0] && ab[ab.length - 3] !== ab[0])) {
                        a[b] = a[b] + ',' + a[b + 1];
                        ab = a[b].trim();
                        if (b < a.length - 2) {
                            a = a.slice(0, b + 1).concat(a.slice(b + 2));
                        } else {
                            a = a.slice(0, b + 1);
                        }
                    }
                    b += 1;
                }
            }
        } else {
            var al = Array.from(a.slice(1, -1));
            a = [];
            var openarr = 0;
            var j = 0;
            for (var i = 0; i < al.length; i++) {
                if (al[i] === '[') {
                    openarr += 1;
                } else if (al[i] === ']') {
                    openarr -= 1;
                } else if (al[i] === ',' && !openarr) {
                    a.push(al.slice(j, i).join(''));
                    j = i + 1;
                }
            }
            a.push(al.slice(j).join(''));
        }
        for (var i = 0; i < a.length; i++) {
            a[i] = a[i].trim();
            if (a[i] !== '') {
                var _packed = class_var.load_value(a[i], true);
                var nval = _packed[0];
                retval.push(nval);
            }
        }
        return retval;
    }
    function TomlDecoder_dlm_preserve_comment(line_no, key, comment, beginline) {
    }
    function TomlDecoder_dlm_embed_comments(idx, currentlevel) {
    }
    var class_var = SkelClass('TomlDecoder');
    class_var.__init__ = TomlDecoder_dlm___init__;
    class_var.get_empty_table = TomlDecoder_dlm_get_empty_table;
    class_var.get_empty_inline_table = get_empty_inline_table;
    class_var.load_inline_object = load_inline_object;
    class_var._get_split_on_quotes = _get_split_on_quotes;
    class_var.load_line = load_line;
    class_var._load_line_multiline_str = _load_line_multiline_str;
    class_var.load_value = load_value;
    class_var.bounded_string = bounded_string;
    class_var._load_array_isstrarray = _load_array_isstrarray;
    class_var.load_array = load_array;
    class_var.preserve_comment = TomlDecoder_dlm_preserve_comment;
    class_var.embed_comments = TomlDecoder_dlm_embed_comments;
    TomlDecoder_dlm___init__(param_0);
    return class_var;
}
function TomlPreserveCommentDecoder(param_0) {
    function TomlPreserveCommentDecoder_dlm___init__(_dict) {
        class_var.saved_comments = {};
    }
    function TomlPreserveCommentDecoder_dlm_preserve_comment(line_no, key, comment, beginline) {
        class_var.saved_comments[line_no] = [key, comment, beginline];
    }
    function TomlPreserveCommentDecoder_dlm_embed_comments(idx, currentlevel) {
        if (!class_var.saved_comments.hasOwnProperty(idx)) {
            return;
        }
        var [key, comment, beginline] = class_var.saved_comments[idx];
        currentlevel[key] = CommentValue(currentlevel[key], comment, beginline, class_var._dict);
    }
    var class_var = TomlDecoder(param_0);
    class_var._class_name = 'TomlPreserveCommentDecoder;' + class_var._class_name;
    class_var.__init__ = TomlPreserveCommentDecoder_dlm___init__;
    class_var.preserve_comment = TomlPreserveCommentDecoder_dlm_preserve_comment;
    class_var.embed_comments = TomlPreserveCommentDecoder_dlm_embed_comments;
    TomlPreserveCommentDecoder_dlm___init__(param_0);
    return class_var;
}
function toml_dumps(o, encoder) {
    var retval = "";
    if (encoder === null) {
        encoder = _get_encoder(o);
    }
    var _result = encoder.dump_sections(o, "");
    var addtoretval = _result[0];
    var sections = _result[1];
    retval += addtoretval;
    while (Object.keys(sections).length > 0) {
        var newsections = encoder.get_empty_table();
        for (var section in sections) {
            var [addtoretval, addtosections] = encoder.dump_sections(sections[section], section);
            if (addtoretval || (!addtoretval && Object.keys(addtosections).length === 0)) {
                if (retval && retval.slice(-2) !== "\n\n") {
                    retval += "\n";
                }
                retval += "[" + section + "]\n";
                if (addtoretval) {
                    retval += addtoretval;
                }
            }
            for (var s in addtosections) {
                newsections[section + "." + s] = addtosections[s];
            }
        }
        sections = newsections;
    }
    return retval;
}
function _dump_str(v) {
    v = JSON.stringify(v);
    if (v[0] === 'u') {
        v = v.substring(1);
    }
    var singlequote = v.startsWith("'");
    if (singlequote || v.startsWith('"')) {
        v = v.substring(1, v.length - 1);
    }
    if (singlequote) {
        v = v.replace("\\'", "'");
        v = v.replace('"', '\\"');
    }
    v = v.split("\\x");
    while (v.length > 1) {
        var i = -1;
        if (!v[0]) {
            v = v.substring(1);
        }
        v[0] = v[0].replace(/\\\\/g, "\\");
        var joinx = v[0][v[0].length + i] !== "\\";
        while (v[0].slice(0, i) && v[0][v[0].length + i] === "\\") {
            joinx = !joinx;
            i -= 1;
        }
        var joiner = joinx ? "x" : "u00";
        v = [v[0] + joiner + v[1]].concat(v.slice(2));
    }
    return '"' + v[0] + '"';
}
function _dump_float(v) {
    if (v === Infinity) {
        return "inf";
    }
    return v.toString().replace("e+0", "e+").replace("e-0", "e-");
}
function _dump_bool(v) {
    return String(v).toLowerCase();
}
function _dump_int(v) {
    return v;
}
function TomlEncoder(param_0, param_1) {
    function TomlEncoder_dlm___init__(_dict, preserve) {
        class_var._dict = _dict;
        class_var.preserve = preserve;
        class_var.dump_funcs = { "str": _dump_str, "list": class_var.dump_list, "bool": _dump_bool, "int": _dump_int, "float": _dump_float, };
    }
    function TomlEncoder_dlm_get_empty_table() {
        return class_var._dict();
    }
    function TomlEncoder_dlm_dump_list(v) {
        var retval = "[";
        for (var u of v) {
            retval += " " + class_var.dump_value(u) + ",";
        }
        retval += "]";
        return retval;
    }
    function dump_inline_table(section) {
        var retval = "";
        if (section instanceof Object) {
            var val_list = [];
            for (var k in section) {
                var v = section[k];
                var val = class_var.dump_inline_table(v);
                val_list.push(k + " = " + val);
            }
            retval += "{ " + val_list.join(", ") + " }\n";
            return retval;
        } else {
            return String(class_var.dump_value(section));
        }
    }
    function dump_value(v) {
        var dump_fn = null;
        if (typeof v === 'string' || v instanceof String) {
            dump_fn = class_var.dump_funcs['str'];
        } else if (Array.isArray(v)) {
            dump_fn = class_var.dump_funcs['list'];
        } else if (typeof v === 'boolean') {
            dump_fn = class_var.dump_funcs['bool'];
        } else if (typeof v === 'number' && Number.isInteger(v) && !String(v).includes("e")) {
            dump_fn = class_var.dump_funcs['int'];
        } else if (typeof v === 'number') {
            dump_fn = class_var.dump_funcs['float'];
        } else if ( v !== null && typeof v === 'object' && typeof v._class_name === 'string' && v._class_name.split(';').includes('CommentValue') ) {
            dump_fn = class_var.dump_funcs['CommentValue'];
        } else if (v !== null && typeof v === 'object' && typeof v[Symbol.iterator] === 'function') {
            dump_fn = class_var.dump_funcs['list'];
        }
        if (dump_fn === null) {
            dump_fn = class_var.dump_funcs['str'];
        }
        return (typeof dump_fn === 'function') ? dump_fn(v) : class_var.dump_funcs['str'](v);
    }
    function dump_sections(o, sup) {
        var retstr = "";
        if (sup !== "") {
            if (sup.slice(-1) !== ".") {
                sup += '.';
            }
        }
        var retdict = class_var._dict();
        var arraystr = "";
        for (var section in o) {
            section = String(section);
            var qsection = section;
            if (!/^[A-Za-z0-9_-]+$/.test(section)) {
                qsection = _dump_str(section);
            }
            var _is_com_val = o[section]._class_name !== undefined && o[section]._class_name === 'CommentValue';
            var _isnt_dict = o[section].constructor.name !== 'Object';
            var _is_list = Array.isArray(o[section]);
            var _cond = _is_com_val || _isnt_dict || _is_list;
            if (_cond) {
                var arrayoftables = false;
                if (Array.isArray(o[section])) {
                    for (var a of o[section]) {
                        if (a.constructor.name === 'Object') {
                            arrayoftables = true;
                        }
                    }
                }
                if (arrayoftables) {
                    for (var a of o[section]) {
                        var arraytabstr = "\n";
                        arraystr += "[[" + sup + qsection + "]]\n";
                        var [s, d] = class_var.dump_sections(a, sup + qsection);
                        if (s) {
                            if (s[0] === "[") {
                                arraytabstr += s;
                            } else {
                                arraystr += s;
                            }
                        }
                        while (Object.keys(d).length > 0) {
                            var newd = class_var._dict();
                            for (var dsec in d) {
                                var [s1, d1] = class_var.dump_sections(d[dsec], sup + qsection + "." + dsec);
                                if (s1) {
                                    arraytabstr += ("[" + sup + qsection + "." + dsec + "]\n");
                                    arraytabstr += s1;
                                }
                                for (var s1 in d1) {
                                    newd[dsec + "." + s1] = d1[s1];
                                }
                            }
                            d = newd;
                        }
                        arraystr += arraytabstr;
                    }
                } else if (o[section] !== null) {
                    retstr += qsection + " = " + String(class_var.dump_value(o[section])) + "\n";
                }
            } else if (class_var.preserve && user_check_type(o[section], InlineTableDict)) {
                retstr += (qsection + " = " + class_var.dump_inline_table(o[section]));
            } else {
                retdict[qsection] = o[section];
            }
        }
        retstr += arraystr;
        return [retstr, retdict];
    }
    var class_var = SkelClass('TomlEncoder');
    class_var.__init__ = TomlEncoder_dlm___init__;
    class_var.get_empty_table = TomlEncoder_dlm_get_empty_table;
    class_var.dump_list = TomlEncoder_dlm_dump_list;
    class_var.dump_inline_table = dump_inline_table;
    class_var.dump_value = dump_value;
    class_var.dump_sections = dump_sections;
    TomlEncoder_dlm___init__(param_0, param_1);
    return class_var;
}
function TomlArraySeparatorEncoder(param_0, param_1, param_2) {
    function TomlArraySeparatorEncoder_dlm___init__(_dict, preserve, separator) {
        if (separator.trim() === "") {
            separator = "," + separator;
        } else if (separator.trim().replace(/[\s,]/g, '')) {
            throw new Error("Invalid separator for arrays");
        }
        class_var.separator = separator;
    }
    function TomlArraySeparatorEncoder_dlm_dump_list(v) {
        var t = [];
        var retval = "[";
        for (var u of v) {
            t.push(class_var.dump_value(u));
        }
        while (t.length !== 0) {
            var s = [];
            for (var u of t) {
                if (Array.isArray(u)) {
                    for (var r of u) {
                        s.push(r);
                    }
                } else {
                    retval += " " + String(u) + class_var.separator;
                }
            }
            t = s;
        }
        retval += "]";
        return retval;
    }
    var class_var = TomlEncoder(param_0, param_1);
    class_var._class_name = 'TomlArraySeparatorEncoder;' + class_var._class_name;
    class_var.__init__ = TomlArraySeparatorEncoder_dlm___init__;
    class_var.dump_list = TomlArraySeparatorEncoder_dlm_dump_list;
    TomlArraySeparatorEncoder_dlm___init__(param_0, param_1, param_2);
    return class_var;
}
function TomlPreserveCommentEncoder(param_0, param_1) {
    function TomlPreserveCommentEncoder_dlm___init__(_dict, preserve) {
        class_var.dump_funcs["CommentValue"] = dump_comment;
    }
    function dump_comment(value) {
        return value.dump(class_var.dump_value);
    }
    var class_var = TomlEncoder(param_0, param_1);
    class_var._class_name = 'TomlPreserveCommentEncoder;' + class_var._class_name;
    class_var.__init__ = TomlPreserveCommentEncoder_dlm___init__;
    TomlPreserveCommentEncoder_dlm___init__(param_0, param_1);
    return class_var;
}
function TomlTz(param_0) {
    function TomlTz_dlm___init__(toml_offset) {
        if (toml_offset === "Z") {
            class_var._raw_offset = "+00:00";
        } else {
            class_var._raw_offset = toml_offset;
        }
        class_var._sign = class_var._raw_offset[0] === '-' ? -1 : 1;
        var _hh = class_var._raw_offset.substring(1, 3);
        _hh = _hh.replace(/_/g, '');
        class_var._hours = parseInt(_hh);
        class_var._minutes = parseInt(class_var._raw_offset.substring(4, 6));
    }
    function __getinitargs__() {
        return [class_var._raw_offset];
    }
    function tzname(dt) {
        return "UTC" + class_var._raw_offset;
    }
    function utcoffset(dt) {
        return class_var._sign * (class_var._hours * 3600000 + class_var._minutes * 60000);
    }
    function dst(dt) {
        return 0;
    }
    var class_var = {};
    class_var.__init__ = TomlTz_dlm___init__;
    class_var.__getinitargs__ = __getinitargs__;
    class_var.tzname = tzname;
    class_var.utcoffset = utcoffset;
    class_var.dst = dst;
    TomlTz_dlm___init__(param_0);
    return class_var;
}
function convert(_toml_val) {
    if (Array.isArray(_toml_val)) {
        return _toml_val.map(vv => convert(vv));
    } else if (!('type' in _toml_val && 'value' in _toml_val)) {
        var _return_value = {};
        for (var k in _toml_val) {
            _return_value[k] = convert(_toml_val[k]);
        }
        return _return_value;
    } else if (_toml_val['type'] === 'string') {
        return _toml_val['value'];
    } else if (_toml_val['type'] === 'integer') {
        return parseInt(_toml_val['value']);
    } else if (_toml_val['type'] === 'float') {
        if (_toml_val['value'] === 'inf') {
            return Infinity;
        }
        return parseFloat(_toml_val['value']);
    } else if (_toml_val['type'] === 'bool') {
        return _toml_val['value'] === 'true';
    } else {
        throw new Error('unknown type: ' + _toml_val['type']);
    }
}
function tag(value) {
    if (value instanceof Object && !(value instanceof Array) && !(value instanceof Date) && !(value instanceof String) && !(value instanceof Boolean) && !(value instanceof Number)) {
        var _return_value_tag = {};
        for (var k in value) {
            if (value.hasOwnProperty(k)) {
                _return_value_tag[k] = tag(value[k]);
            }
        }
        return _return_value_tag;
    } else if (value instanceof Array) {
        var _return_value = value.map(function (v) { return tag(v); });
        return _return_value;
    } else if (typeof value === 'string') {
        var _return_value = { 'type': 'string', 'value': value };
        return _return_value;
    } else if (typeof value === 'boolean') {
        var _return_value = { 'type': 'bool', 'value': value.toString().toLowerCase() };
        return _return_value;
    } else if (typeof value === 'number' && Number.isSafeInteger(value)) {
        var _return_value = { 'type': 'integer', 'value': value.toString() };
        return _return_value;
    } else if (typeof value === 'number' && !Number.isSafeInteger(value)) {
        if (value === Infinity) {
            var _return_value = { 'type': 'float', 'value': "inf" };
        } else {
            var _return_value = { 'type': 'float', 'value': value.toString() };
        }
        return _return_value;
    } else if (value instanceof Date) {
        if (value.getUTCHours() === 0 && value.getUTCMinutes() === 0 && value.getUTCSeconds() === 0 && value.getUTCMilliseconds() === 0) {
            var _return_value = { 'type': 'date-local', 'value': value.toISOString().substring(0, 10) };
        }
        else if (value.getUTCSeconds() === 0 && value.getUTCMilliseconds() === 0) {
            var _tzinfo = value.tz.utcoffset("0")[0];
            if (_tzinfo === 0) {
                var _return_value = { 'type': 'datetime', 'value': value.toISOString().substring(0, 19) + "Z" };
            }
            else {
                var offset = _tzinfo / 3600 / 1000;
                var _return_value = { 'type': 'datetime', 'value': value.toISOString().substring(0, 19) + "-0" + (-offset).toString() + ":00" };
            }
        }
        else {
            var _tzinfo = value.tz.utcoffset("0")[0];
            var offset = _tzinfo / 3600 / 1000;
            var _return_value = { 'type': 'datetime', 'value': value.toISOString().substring(0, 19) + "-0" + (-offset).toString() + ":00" };
        }
        return _return_value;
    } else {
        throw new Error('Unknown type: ' + (typeof value));
    }
}
function tester(name) {
    var decode_input = get_input(name);
    var decode_result = loads(decode_input, func_dict, null);
    decode_result = tag(decode_result);
    var encode_input = {};
    for (var k in decode_result) {
        var v = convert(decode_result[k]);
        encode_input[k] = v;
    }
    var encode_result = toml_dumps(encode_input, null);
}
function test_bug_148() {
    if ('a = "\\u0064"\n' != toml_dumps({ 'a': '\\x64' }, null)) {
        throw new Error("Assertion failed");
    }
    if ('a = "\\\\x64"\n' != toml_dumps({ 'a': '\\\\x64' }, null)) {
        throw new Error("Assertion failed");
    }
    if ('a = "\\\\\\u0064"\n' != toml_dumps({ 'a': '\\\\\\x64' }, null)) {
        throw new Error("Assertion failed");
    }
}
function test__dict() {
    if (!(loads(TEST_STR1, func_dict, null) instanceof Object)) {
        throw new Error("Assertion failed");
    }
}
function test_dict_decoder() {
    var _test_dict_decoder = TomlDecoder(func_dict);
    if (!(loads(TEST_STR1, func_dict, _test_dict_decoder) instanceof Object)) {
        throw new Error("Assertion failed");
    }
}
function test_array_sep() {
    var encoder = TomlArraySeparatorEncoder(func_dict, false, ",\t");
    var d = { "a": [1, 2, 3] };
    var tmp = toml_dumps(d, encoder);
    var o = loads(tmp, func_dict, null);
    var tmp2 = toml_dumps(o, encoder);
    if (JSON.stringify(o) !== JSON.stringify(loads(tmp2, func_dict, null))) {
        throw new Error("Assertion failed");
    }
}
function test_tuple() {
    var d = { "a": [3, 4] };
    var encoder = TomlEncoder(func_dict, false);
    var tmp = toml_dumps(d, encoder);
    var o = loads(tmp, func_dict, null);
    var tmp2 = toml_dumps(o, encoder);
    if (JSON.stringify(o) !== JSON.stringify(loads(tmp2, func_dict, null))) {
        throw new Error("Assertion failed");
    }
}
function test_commutativity() {
    var encoder = TomlEncoder(func_dict, false);
    var tmp = toml_dumps(TEST_DICT, encoder);
    var o = loads(tmp, func_dict, null);
    var tmp2 = toml_dumps(o, encoder);
    if (JSON.stringify(o) !== JSON.stringify(loads(tmp2, func_dict, null))) {
        throw new Error("Assertion failed");
    }
}
function test_comment_preserve_decoder_encoder() {
    var tmp = loads(TEST_STR2, func_dict, TomlPreserveCommentDecoder(func_dict));
    var s = toml_dumps(tmp, TomlPreserveCommentEncoder(func_dict, false));
    if (s.length !== TEST_STR2.length) {
        throw new Error("Assertion failed");
    }
    if ([...TEST_STR2].sort().join('') !== [...s].sort().join('')) {
        throw new Error("Assertion failed");
    }
}
function additional_test() {
    var decoder = new TomlDecoder(func_dict);
    var cur = {};
    var multikey = false;
    var multibackslash = false;
    decoder.load_line("'a.x'=2=3", cur, multikey, multibackslash);
    if (JSON.stringify(cur) !== JSON.stringify({ 'a.x': { '=2': 3 } })) {
        throw new Error("Assertion failed");
    }
}
function additional_test2() {
    var decoder = new TomlDecoder(func_dict);
    var input_str = "[{'x' = 1}]";
    var res = decoder.load_array(input_str);
    if (JSON.stringify(res) !== JSON.stringify([{ 'x': 1 }])) {
        throw new Error("Assertion failed");
    }
    input_str = "[{'x' = 1}, {'y' = 2}]";
    res = decoder.load_array(input_str);
    if (JSON.stringify(res) !== JSON.stringify([{ 'x': 1 }, { 'y': 2 }])) {
        throw new Error("Assertion failed");
    }
}
function additional_test3() {
    var v = "abc\\";
    var hexbytes = ['0064'];
    var prefix = 'u';
    var res = _load_unicode_escapes(v, hexbytes, prefix);
    if (res !== 'abc\\u0064') {
        throw new Error("Assertion failed");
    }
}
function additional_test4() {
    var v = "\\\\";
    var res = _unescape(v);
    if (res !== '\\') {
        throw new Error("Assertion failed");
    }
    v = "\\u";
    res = _unescape(v);
    if (res !== '\\u') {
        throw new Error("Assertion failed");
    }
}
function additional_test5() {
    var s = "['\"test\"']";
    var t = loads(s, func_dict, null);
    if (JSON.stringify(t) !== JSON.stringify({ '"test"': {} })) {
        throw new Error("Assertion failed");
    }
    s = "[\"abc\"]";
    t = loads(s, func_dict, null);
    if (JSON.stringify(t) !== JSON.stringify({ 'abc': {} })) {
        throw new Error("Assertion failed");
    }
}
function test_init() {
    // _dump_float
    var arg = Infinity;
    _dump_float(arg);
    arg = 3.14;
    _dump_float(arg);

    // _dump_bool
    arg = true;
    _dump_bool(arg);

    // _dump_int
    arg = 42;
    _dump_int(arg);

    // CommentValue
    var cv = CommentValue('value', 'comment', 1, func_dict);
    cv.dump(_dump_bool);

    // TomlDecodeError
    var err = TomlDecodeError('a', 'b', 'c');

    // TomlTz_dlm___init__
    arg = '+05:30';
    var tomltz = TomlTz(arg);

    // TomlDecoder
    var tdec = TomlDecoder(func_dict);

    // TomlDecoder.get_empty_inline_table
    tdec.get_empty_inline_table();

    // TomlPreserveCommentDecoder
    var tpcdec = TomlPreserveCommentDecoder(func_dict);
    arg = {};
    tpcdec.embed_comments(1, arg);
    arg = ['key', 'comment', true];
    tpcdec.saved_comments[1] = arg;
    arg = {'key': 'value'};
    tpcdec.embed_comments(1, arg);

    // TomlDecoder._get_split_on_quotes()
    var gsoq1 = 'key = "value"';
    tdec._get_split_on_quotes(gsoq1);
    var gsoq2 = '\'"test"\'';
    tdec._get_split_on_quotes(gsoq2);

    // _unescape
    arg = '"One\\nTwo"';
    _unescape(arg);
    arg = '\\\\';
    _unescape(arg);
    arg = '\\u';
    _unescape(arg);

    // TomlDecoder.bounded_string()
    var bndstr_arg = '"a"';
    tdec.bounded_string(bndstr_arg);

    // TomlDecoder._load_line_multiline_str()
    arg = 'a';
    tdec._load_line_multiline_str(arg);
    arg = 'aaaa';
    tdec._load_line_multiline_str(arg);
    arg = '"abaa"';
    tdec._load_line_multiline_str(arg);
    arg = '"""aaabaaa"""';
    tdec._load_line_multiline_str(arg);
    arg = '"""aaabaaa""';
    tdec._load_line_multiline_str(arg);

    // _strictly_valid_num
    var strictlyvn_arg = ' 0';
    _strictly_valid_num(strictlyvn_arg);
    strictlyvn_arg = ' -17';
    _strictly_valid_num(strictlyvn_arg);

    // _load_unicode_escapes
    var lue_arg1 = 'abc\\';
    var lue_arg2 = ['0064'];
    var lue_arg3 = 'u';
    _load_unicode_escapes(lue_arg1, lue_arg2, lue_arg3);
    lue_arg1 = '"I\'m a string. \\"You can quote me\\". Name\\tJos';
    lue_arg2 = ['00E9\\nLocation\\tSF."'];
    lue_arg3 = '\\u';
    _load_unicode_escapes(lue_arg1, lue_arg2, lue_arg3);

    // TomlDecoder._load_array_isstrarray()
    arg = '["abc"]';
    tdec._load_array_isstrarray(arg);
    arg = '';
    tdec._load_array_isstrarray(arg);

    // _dump_str
    arg = '""';
    _dump_str(arg);
    arg = '"\\x64"';
    _dump_str(arg);

    // TomlEncoder
    var tenc = TomlEncoder(func_dict, false);

    // TomlPreserveCommentEncoder
    var tpcenc = TomlPreserveCommentEncoder(func_dict, false);
    cv = CommentValue('value', 'comment', 1, func_dict);
    tpcenc.dump_value(cv);

    // TomlEncoder_dlm_dump_list
    arg = [1];
    tenc.dump_list(arg);

    // // TomlDecoder.load_array() - not needed since GT is provided
    // var loadarr_arg = '[ 1, 2 ]';
    // tdec.load_array(loadarr_arg);
    // loadarr_arg = '["a", "b"]';
    // tdec.load_array(loadarr_arg);
    // loadarr_arg = "[{'x' = 1}, {'y' = 2}]";
    // tdec.load_array(loadarr_arg);
    // loadarr_arg = '[ [ 1, 2 ], ["a", "b", "c"] ]';
    // tdec.load_array(loadarr_arg);

    // // TomlDecoder.load_value() - non-recursive to load_array() - not needed since GT is provided
    // var lval1 = 'true';
    // var lval2 = true;
    // tdec.load_value(lval1, lval2);
    // lval1 = 'false';
    // lval2 = true;
    // tdec.load_value(lval1, lval2);
    // lval1 = '"I\'m a string. \\"You can quote me\\". Name\\tJos\\u00E9\\nLocation\\tSF."';
    // lval2 = true;
    // tdec.load_value(lval1, lval2);
    // lval1 = '"""a"""';
    // lval2 = true;
    // tdec.load_value(lval1, lval2);
    // lval1 = '-2E-2';
    // lval2 = true;
    // tdec.load_value(lval1, lval2);
    // lval1 = '+1';
    // lval2 = true;
    // tdec.load_value(lval1, lval2);
    // // TomlDecoder.load_value() - recursive to load_array() - not needed since GT is provided;
    // lval1 = '[ 1, 2, 3 ]';
    // lval2 = true;
    // tdec.load_value(lval1, lval2);
    // lval1 = '{ x = 1, y = 2 }';
    // lval2 = true;
    // tdec.load_value(lval1, lval2);

    // load_inline_object
    var arg1 = '{ x = 1, y = 2 }';
    var arg2 = {};
    var arg3 = false;
    var arg4 = false;
    tdec.load_inline_object(arg1, arg2, arg3, arg4);

    // convert
    arg = {'type': 'string', 'value': 'value'};
    convert(arg);
    arg = {'type': 'integer', 'value': '1'};
    convert(arg);
    arg = {'type': 'float', 'value': 'inf'};
    convert(arg);
    arg = {'type': 'float', 'value': '-0.02'};
    convert(arg);
    arg = {'type': 'bool', 'value': 'true'};
    convert(arg);
    arg = [];
    convert(arg);
    arg = {'a': {'type': 'string', 'value': 'value'}};
    convert(arg);

    // dump_sections
    arg1 = {'products': [{'name': 'Nail'}], 'fruit': [{'physical': {'color': 'red'}}]};
    arg2 = '';
    tenc.dump_sections(arg1, arg2);

    // toml_dumps
    arg1 = {'integer': {'key1': 99, 'underscores': {'key1': 1000}}};
    arg2 = null;
    toml_dumps(arg1, arg2);
}
function test() {
    test_init();
    tester('Comment');
    tester('Boolean');
    tester('Integer');
    tester('Float');
    tester('Table');
    tester('Inline Table');
    tester('String');
    tester('Array');
    tester('Array of Tables');
    test_bug_148();
    test__dict();
    test_dict_decoder();
    test_array_sep();
    test_tuple();
    test_commutativity();
    test_comment_preserve_decoder_encoder();
    additional_test();
    additional_test2();
    additional_test3();
    additional_test4();
    additional_test5();
}
test();
