const crc32 = require('crc-32');

const NAME_PATTERN = /^[a-zA-Z_][a-zA-Z0-9_\-:]*$/;
const RESTRICTED_CHARS = /[\x01-\x08\x0B\x0C\x0E-\x1F\x7F-\x84\x86-\x9F]/g;

const EndOfStreamToken = 0;
const OpenStartElementToken = 1;
const CloseStartElementToken = 2;
const CloseEmptyElementToken = 3;
const CloseElementToken = 4;
const ValueToken = 5;
const AttributeToken = 6;
const CDataSectionToken = 7;
const EntityReferenceToken = 8;
const ProcessingInstructionTargetToken = 10;
const ProcessingInstructionDataToken = 11;
const TemplateInstanceToken = 12;
const NormalSubstitutionToken = 13;
const ConditionalSubstitutionToken = 14;
const StartOfStreamToken = 15;

const NULL = 0;
const WSTRING = 1;
const STRING = 2;
const SIGNED_BYTE = 3;
const UNSIGNED_BYTE = 4;
const SIGNED_WORD = 5;
const UNSIGNED_WORD = 6;
const SIGNED_DWORD = 7;
const UNSIGNED_DWORD = 8;
const SIGNED_QWORD = 9;
const UNSIGNED_QWORD = 10;
const FLOAT = 11;
const DOUBLE = 12;
const BOOLEAN = 13;
const BINARY = 14;
const GUID = 15;
const SIZE = 16;
const FILETIME = 17;
const SYSTEMTIME = 18;
const SID = 19;
const HEX32 = 20;
const HEX64 = 21;
const BXML = 33;
const WSTRINGARRAY = 129;

const expected_output1 = { "start_file": 1, "end_file": 153, "start_log": 12049, "end_log": 12201 };
const expected_output2 = { "start_file": 1, "end_file": 91, "start_log": 1, "end_log": 91 };


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
function SkelClass(class_name) {
    var _class_var = {};
    _class_var._class_name = class_name;
    return _class_var;
}
function system_path() {
    const path = require('path');
    const cd = path.dirname(__filename);
    const datadir = path.join(cd, "evtx.d");
    return path.join(datadir, "system.evtx");
}
function system() {
    const fs = require('fs');
    const p = system_path();
    return fs.readFileSync(p);
}
function security_path() {
    const path = require('path');
    const cd = path.dirname(__filename);
    const datadir = path.join(cd, "evtx.d");
    return path.join(datadir, "security.evtx");
}
function security() {
    const fs = require('fs');
    const p = security_path();
    return fs.readFileSync(p);
}
function* user_infinite_counter() {
    var start = 0;
    while (true) {
        yield start;
        start += 1;
    }
}
function get_input(_case) {
    if (_case === "case1") {
        return system();
    } else {
        return security();
    }
}
function _get_expected_output3() {
    const fs = require('fs');
    const path = require('path');
    const cd = path.dirname(__filename);
    const datadir = path.join(cd, "evtx.d");
    const systempath = path.join(datadir, "expected_output3.json");
    const data = fs.readFileSync(systempath, "utf-8");
    return JSON.parse(data);
}
function _get_expected_output4() {
    const fs = require('fs');
    const path = require('path');
    const cd = path.dirname(__filename);
    const datadir = path.join(cd, "evtx.d");
    const systempath = path.join(datadir, "expected_output4.json");
    const data = fs.readFileSync(systempath, "utf-8");
    return JSON.parse(data);
}
function _get_test_init_input(input_name) {
    const fs = require('fs');
    const path = require('path');
    const cd = path.dirname(__filename);
    const datadir = path.join(cd, "evtx.d");
    const input_path = path.join(datadir, input_name);
    const data = fs.readFileSync(input_path);
    return data;
}








function memoize(param_0, decorated_object) {
    function __init__1(func) {
        class_var.func = func;
    }
    function __call__(...args) {
        var obj = args[0];
        if (!('__cache' in obj)) {
            obj.__cache = new Map();
        }
        var cache = obj.__cache;
        if (!cache.has(class_var)) {
            cache.set(class_var, class_var.func(...args));
        }
        var _mem_retval = cache.get(class_var);
        return _mem_retval;
    }
    function self_func(...args) {
        var _retval = tmp_f(...args.slice(1));
        return _retval;
    }
    function self_call(...args) {
        var _retval = __call__(decorated_object, ...args);
        return _retval;
    }
    var class_var = SkelClass('memoize');
    var tmp_f = param_0;
    param_0 = self_func;
    class_var.__init__ = __init__1;
    class_var.__call__ = __call__;
    __init__1(param_0);
    return self_call;
}
function parse_filetime(qword) {
    if (qword === 0) {
        return new Date(-8640000000000000);
    }
    try {
        return new Date((qword * 1e-7 - 11644473600) * 1000);
    } catch (e) {
        return new Date(-8640000000000000);
    }
}
function BinaryParserException(pvalue) {
    function __init__2(value) {
        class_var._value = value;
    }
    var class_var = new Error();
    class_var._class_name = 'BinaryParserException;' + class_var._class_name;
    class_var.__init__ = __init__2;
    __init__2(pvalue);
    return class_var;
}
function ParseException(pvalue) {
    function __init__3(value) {
    }
    var class_var = BinaryParserException(pvalue);
    class_var._class_name = 'ParseException;' + class_var._class_name;
    class_var.__init__ = __init__3;
    __init__3(pvalue);
    return class_var;
}
function OverrunBufferException(preadOffs, pbufLen) {
    function __init__4(readOffs, bufLen) {
        var tvalue = `read: ${readOffs.toString(16)}, buffer length: ${bufLen.toString(16)}`;
    }
    var class_var = ParseException('Error: Type not support');
    class_var._class_name = 'OverrunBufferException;' + class_var._class_name;
    class_var.__init__ = __init__4;
    __init__4(preadOffs, pbufLen);
    return class_var;
}
function Block(pbuf, poffset) {
    function __init__5(buf, offset) {
        class_var._buf = buf;
        class_var._offset = offset;
        class_var._implicit_offset = 0;
    }
    function declare_field(type, name, offset, length) {
        function no_length_handler() {
            var f = class_var["unpack_" + type];
            return f(offset);
        }
        function explicit_length_handler() {
            var f = class_var["unpack_" + type];
            return f(offset, length);
        }
        if (offset === null) {
            offset = class_var._implicit_offset;
        }
        if (length === null) {
            class_var[name] = no_length_handler;
        } else {
            class_var[name] = explicit_length_handler;
        }
        class_var["_off_" + name] = offset;
        if (type === "byte" || type === "int8") {
            class_var._implicit_offset = offset + 1;
        } else if (type === "word" || type === "word_be" || type === "int16") {
            class_var._implicit_offset = offset + 2;
        } else if (type === "dword" || type === "dword_be" || type === "int32" || type === "float") {
            class_var._implicit_offset = offset + 4;
        } else if (type === "qword" || type === "int64" || type === "double" || type === "filetime" || type === "systemtime") {
            class_var._implicit_offset = offset + 8;
        } else if (type === "guid") {
            class_var._implicit_offset = offset + 16;
        } else if (type === "binary") {
            class_var._implicit_offset = offset + length;
        } else if (type === "string" && length !== null) {
            class_var._implicit_offset = offset + length;
        } else if (type === "wstring" && length !== null) {
            class_var._implicit_offset = offset + (2 * length);
        } else if (type.includes("string") && length === null) {
            throw new ParseException("Implicit offset not supported for dynamic length strings");
        } else {
            throw new ParseException("Implicit offset not supported for type: " + type);
        }
    }
    function current_field_offset() {
        return class_var._implicit_offset;
    }
    function unpack_byte(offset) {
        var o = class_var._offset + offset;
        try {
            var _retval = class_var._buf[o];
            return _retval;
        } catch {
            throw new OverrunBufferException(o, class_var._buf.length);
        }
    }
    function unpack_word(offset) {
        var o = class_var._offset + offset;
        try {
            var _retval = class_var._buf.readUInt16LE(o);
            return _retval;
        } catch {
            throw new OverrunBufferException(o, class_var._buf.length);
        }
    }
    function unpack_word_be(offset) {
        var o = class_var._offset + offset;
        try {
            var _retval = class_var._buf.readUInt16BE(o);
            return _retval;
        } catch {
            throw new OverrunBufferException(o, class_var._buf.length);
        }
    }
    function unpack_dword(offset) {
        var o = class_var._offset + offset;
        try {
            var _retval = class_var._buf.readUInt32LE(o);
            return _retval;
        } catch {
            throw new OverrunBufferException(o, class_var._buf.length);
        }
    }
    function unpack_dword_be(offset) {
        var o = class_var._offset + offset;
        try {
            var _retval = class_var._buf.readUInt32BE(o);
            return _retval;
        } catch {
            throw new OverrunBufferException(o, class_var._buf.length);
        }
    }
    function unpack_int32(offset) {
        var o = class_var._offset + offset;
        try {
            var _retval = new DataView(class_var._buf.buffer, class_var._buf.byteOffset, class_var._buf.byteLength).getInt32(o, true);
            return _retval;
        } catch {
            throw new OverrunBufferException(o, class_var._buf.length);
        }
    }
    function unpack_qword(offset) {
        var o = class_var._offset + offset;
        try {
            var _retval = new DataView(class_var._buf.buffer, class_var._buf.byteOffset, class_var._buf.byteLength).getBigUint64(o, true);
            if (_retval <= Number.MAX_SAFE_INTEGER) {
                _retval = Number(_retval);
            }
            return _retval;
        } catch {
            throw new OverrunBufferException(o, class_var._buf.length);
        }
    }
    function unpack_binary(offset, length) {
        if (!length) {
            var _retval = new Uint8Array(0);
            return _retval;
        }
        var o = class_var._offset + offset;
        try {
            var _retval = new Uint8Array(class_var._buf.slice(o, o + length));
            return _retval;
        } catch {
            throw new OverrunBufferException(o, class_var._buf.length);
        }
    }
    function unpack_string(offset, length) {
        var _retval = String.fromCharCode.apply(null, class_var.unpack_binary(offset, length));
        return _retval;
    }
    function unpack_wstring(offset, length) {
        var start = class_var._offset + offset;
        var end = class_var._offset + offset + 2 * length;
        try {
            var _retval = new TextDecoder("utf-16").decode(class_var._buf.slice(start, end));
            return _retval;
        } catch (e) {
            var _retval = new TextDecoder("utf-16").decode(class_var._buf.slice(start, end));
            return _retval;
        }
    }
    function unpack_filetime(offset) {
        return parse_filetime(class_var.unpack_qword(offset));
    }
    function unpack_guid(offset) {
        var o = class_var._offset + offset;
        var _bin = null;
        try {
            _bin = class_var._buf.slice(o, o + 16);
        } catch (e) {
            throw new OverrunBufferException(o, class_var._buf.length);
        }
        var h = [];
        for (var i = 0; i < _bin.length; i++) {
            h.push(_bin[i]);
        }
        var _retval = `${h[3].toString(16).padStart(2, '0')}${h[2].toString(16).padStart(2, '0')}${h[1].toString(16).padStart(2, '0')}${h[0].toString(16).padStart(2, '0')}-${h[5].toString(16).padStart(2, '0')}${h[4].toString(16).padStart(2, '0')}-${h[7].toString(16).padStart(2, '0')}${h[6].toString(16).padStart(2, '0')}-${h[8].toString(16).padStart(2, '0')}${h[9].toString(16).padStart(2, '0')}-${h[10].toString(16).padStart(2, '0')}${h[11].toString(16).padStart(2, '0')}${h[12].toString(16).padStart(2, '0')}${h[13].toString(16).padStart(2, '0')}${h[14].toString(16).padStart(2, '0')}${h[15].toString(16).padStart(2, '0')}`;
        return _retval;
    }
    function offset() {
        return class_var._offset;
    }
    var class_var = SkelClass('Block');
    class_var.__init__ = __init__5;
    class_var.declare_field = declare_field;
    class_var.current_field_offset = current_field_offset;
    class_var.unpack_byte = unpack_byte;
    class_var.unpack_word = unpack_word;
    class_var.unpack_word_be = unpack_word_be;
    class_var.unpack_dword = unpack_dword;
    class_var.unpack_dword_be = unpack_dword_be;
    class_var.unpack_int32 = unpack_int32;
    class_var.unpack_qword = unpack_qword;
    class_var.unpack_binary = unpack_binary;
    class_var.unpack_string = unpack_string;
    class_var.unpack_wstring = unpack_wstring;
    class_var.unpack_filetime = unpack_filetime;
    class_var.unpack_guid = unpack_guid;
    class_var.offset = offset;
    __init__5(pbuf, poffset);
    return class_var;
}
function BXmlNode(pbuf, poffset, pchunk, pparent) {
    function __init__6(buf, offset, chunk, parent) {
        class_var._chunk = chunk;
        class_var._parent = parent;
    }
    function _children(max_children, end_tokens) {
        var ret = [];
        var ofs = class_var.tag_length();
        var gen = user_infinite_counter();
        if (max_children !== null) {
            gen = Array.from({ length: max_children }, (_, i) => i);
        }
        for (var _ of gen) {
            var token = class_var.unpack_byte(ofs) & 15;
            var HandlerNodeClass = NODE_DISPATCH_TABLE[token];
            var child = new HandlerNodeClass(class_var._buf, class_var.offset() + ofs, class_var._chunk, class_var);
            ret.push(child);
            ofs += child.length();
            if (end_tokens.includes(token)) {
                break;
            }
            if (child.find_end_of_stream()) {
                break;
            }
        }
        return ret;
    }
    function children1() {
        var _retval = class_var._children(null, [EndOfStreamToken]);
        return _retval;
    }
    function length1() {
        var ret = class_var.tag_length();
        for (var child of class_var.children()) {
            ret += child.length();
        }
        return ret;
    }
    function find_end_of_stream1() {
        for (var child of class_var.children()) {
            if (user_check_type(child, EndOfStreamNode)) {
                return child;
            }
            var ret = child.find_end_of_stream();
            if (ret) {
                return ret;
            }
        }
        return null;
    }
    var class_var = Block(pbuf, poffset);
    class_var._class_name = 'BXmlNode;' + class_var._class_name;
    children1 = memoize(children1, class_var);
    length1 = memoize(length1, class_var);
    find_end_of_stream1 = memoize(find_end_of_stream1, class_var);
    class_var.__init__ = __init__6;
    class_var._children = _children;
    class_var.children = children1;
    class_var.length = length1;
    class_var.find_end_of_stream = find_end_of_stream1;
    __init__6(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function NameStringNode(pbuf, poffset, pchunk, pparent) {
    function __init__7(buf, offset, chunk, parent) {
        class_var.declare_field("dword", "next_offset", 0, null);
        class_var.declare_field("word", "hash", null, null);
        class_var.declare_field("word", "string_length", null, null);
        class_var.declare_field("wstring", "string", null, class_var.string_length());
    }
    function tag_length1() {
        var _retval = class_var.string_length() * 2 + 8;
        return _retval;
    }
    function length2() {
        var _retval = class_var.tag_length() + 2;
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'NameStringNode;' + class_var._class_name;
    class_var.__init__ = __init__7;
    class_var.tag_length = tag_length1;
    class_var.length = length2;
    __init__7(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function TemplateNode(pbuf, poffset, pchunk, pparent) {
    function __init__8(buf, offset, chunk, parent) {
        class_var.declare_field("dword", "next_offset", 0, null);
        class_var.declare_field("dword", "template_id", null, null);
        class_var.declare_field("guid", "guid", 4, null);
        class_var.declare_field("dword", "data_length", null, null);
    }
    function tag_length2() {
        return 24;
    }
    function length3() {
        var _retval = class_var.tag_length() + class_var.data_length();
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'TemplateNode;' + class_var._class_name;
    class_var.__init__ = __init__8;
    class_var.tag_length = tag_length2;
    class_var.length = length3;
    __init__8(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function EndOfStreamNode(pbuf, poffset, pchunk, pparent) {
    function __init__9(buf, offset, chunk, parent) {
    }
    function length4() {
        return 1;
    }
    function children2() {
        return [];
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'EndOfStreamNode;' + class_var._class_name;
    class_var.__init__ = __init__9;
    class_var.length = length4;
    class_var.children = children2;
    __init__9(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function OpenStartElementNode(pbuf, poffset, pchunk, pparent) {
    function __init__10(buf, offset, chunk, parent) {
        class_var.declare_field("byte", "token", 0, null);
        class_var.declare_field("word", "unknown0", null, null);
        class_var.declare_field("dword", "size", null, null);
        class_var.declare_field("dword", "string_offset", null, null);
        class_var._tag_length = 11;
        class_var._element_type = 0;
        if (class_var.flags() & 4) {
            class_var._tag_length += 4;
        }
        if (class_var.string_offset() > class_var.offset() - class_var._chunk._offset) {
            var new_string = class_var._chunk.add_string(class_var.string_offset(), class_var);
            class_var._tag_length += new_string.length();
        }
    }
    function flags1() {
        var _retval = class_var.token() >> 4;
        return _retval;
    }
    function tag_name() {
        var _retval = class_var._chunk.strings()[class_var.string_offset()].string();
        return _retval;
    }
    function tag_length3() {
        var _retval = class_var._tag_length;
        return _retval;
    }
    function children3() {
        var _retval = class_var._children(null, [CloseElementToken, CloseEmptyElementToken]);
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'OpenStartElementNode;' + class_var._class_name;
    tag_name = memoize(tag_name, class_var);
    children3 = memoize(children3, class_var);
    class_var.__init__ = __init__10;
    class_var.flags = flags1;
    class_var.tag_name = tag_name;
    class_var.tag_length = tag_length3;
    class_var.children = children3;
    __init__10(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function CloseStartElementNode(pbuf, poffset, pchunk, pparent) {
    function __init__11(buf, offset, chunk, parent) {
        class_var.declare_field("byte", "token", 0, null);
    }
    function length5() {
        return 1;
    }
    function children4() {
        return [];
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'CloseStartElementNode;' + class_var._class_name;
    class_var.__init__ = __init__11;
    class_var.length = length5;
    class_var.children = children4;
    __init__11(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function CloseEmptyElementNode(pbuf, poffset, pchunk, pparent) {
    function __init__12(buf, offset, chunk, parent) {
        class_var.declare_field("byte", "token", 0, null);
    }
    function length6() {
        return 1;
    }
    function children5() {
        return [];
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'CloseEmptyElementNode;' + class_var._class_name;
    class_var.__init__ = __init__12;
    class_var.length = length6;
    class_var.children = children5;
    __init__12(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function CloseElementNode(pbuf, poffset, pchunk, pparent) {
    function __init__13(buf, offset, chunk, parent) {
        class_var.declare_field("byte", "token", 0, null);
    }
    function length7() {
        return 1;
    }
    function children6() {
        return [];
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'CloseElementNode;' + class_var._class_name;
    class_var.__init__ = __init__13;
    class_var.length = length7;
    class_var.children = children6;
    __init__13(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function get_variant_value(buf, offset, chunk, parent, type_, length) {
    var types = { [NULL]: NullTypeNode, [WSTRING]: WstringTypeNode, [UNSIGNED_BYTE]: UnsignedByteTypeNode, [UNSIGNED_WORD]: UnsignedWordTypeNode, [UNSIGNED_DWORD]: UnsignedDwordTypeNode, [UNSIGNED_QWORD]: UnsignedQwordTypeNode, [FLOAT]: FloatTypeNode, [DOUBLE]: DoubleTypeNode, [BOOLEAN]: BooleanTypeNode, [BINARY]: BinaryTypeNode, [GUID]: GuidTypeNode, [SIZE]: SizeTypeNode, [FILETIME]: FiletimeTypeNode, [SYSTEMTIME]: SystemtimeTypeNode, [SID]: SIDTypeNode, [HEX32]: Hex32TypeNode, [HEX64]: Hex64TypeNode, [BXML]: BXmlTypeNode, [WSTRINGARRAY]: WstringArrayTypeNode, };
    var TypeClass = types[type_];
    var _retval = new TypeClass(buf, offset, chunk, parent, length);
    return _retval;
}
function ValueNode(pbuf, poffset, pchunk, pparent) {
    function __init__14(buf, offset, chunk, parent) {
        class_var.declare_field("byte", "token", 0, null);
        class_var.declare_field("byte", "type", null, null);
    }
    function tag_length4() {
        return 2;
    }
    function children7() {
        var child = get_variant_value(class_var._buf, class_var.offset() + class_var.tag_length(), class_var._chunk, class_var, class_var.type(), null);
        var _retval = [child];
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'ValueNode;' + class_var._class_name;
    class_var.__init__ = __init__14;
    class_var.tag_length = tag_length4;
    class_var.children = children7;
    __init__14(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function AttributeNode(pbuf, poffset, pchunk, pparent) {
    function __init__15(buf, offset, chunk, parent) {
        class_var.declare_field("byte", "token", 0, null);
        class_var.declare_field("dword", "string_offset", null, null);
        class_var._name_string_length = 0;
        if (class_var.string_offset() > class_var.offset() - class_var._chunk._offset) {
            var new_string = class_var._chunk.add_string(class_var.string_offset(), class_var);
            class_var._name_string_length += new_string.length();
        }
    }
    function attribute_name() {
        var _retval = class_var._chunk.strings()[class_var.string_offset()];
        return _retval;
    }
    function attribute_value() {
        var _retval = class_var.children()[0];
        return _retval;
    }
    function tag_length5() {
        var _retval = 5 + class_var._name_string_length;
        return _retval;
    }
    function children8() {
        var _retval = class_var._children(1, [EndOfStreamToken]);
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'AttributeNode;' + class_var._class_name;
    children8 = memoize(children8, class_var);
    class_var.__init__ = __init__15;
    class_var.attribute_name = attribute_name;
    class_var.attribute_value = attribute_value;
    class_var.tag_length = tag_length5;
    class_var.children = children8;
    __init__15(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function CharacterReferenceNode(pbuf, poffset, pchunk, pparent) {
    function __init__16(buf, offset, chunk, parent) {
        class_var.declare_field('byte', 'token', 0, null);
        class_var.declare_field('word', 'entity', null, null);
        class_var._tag_length = 3;
    }
    function entity_reference1() {
        var _retval = '&#x' + class_var.entity().toString(16).padStart(4, '0') + ';';
        return _retval;
    }
    function flags2() {
        var _retval = class_var.token() >> 4;
        return _retval;
    }
    function tag_length6() {
        var _retval = class_var._tag_length;
        return _retval;
    }
    function children9() {
        var _retval = [];
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'CharacterReferenceNode;' + class_var._class_name;
    class_var.__init__ = __init__16;
    class_var.entity_reference = entity_reference1;
    class_var.flags = flags2;
    class_var.tag_length = tag_length6;
    class_var.children = children9;
    __init__16(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function EntityReferenceNode(pbuf, poffset, pchunk, pparent) {
    function __init__17(buf, offset, chunk, parent) {
        class_var.declare_field('byte', 'token', 0, null);
        class_var.declare_field('dword', 'string_offset', null, null);
        class_var._tag_length = 5;
        if (class_var.string_offset() > class_var.offset() - class_var._chunk.offset()) {
            var new_string = class_var._chunk.add_string(class_var.string_offset(), class_var);
            class_var._tag_length += new_string.length();
        }
    }
    function entity_reference2() {
        var _retval = '&' + class_var._chunk.strings()[class_var.string_offset()].string() + ';';
        return _retval;
    }
    function flags3() {
        var _retval = class_var.token() >> 4;
        return _retval;
    }
    function tag_length7() {
        var _retval = class_var._tag_length;
        return _retval;
    }
    function children10() {
        var _retval = [];
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'EntityReferenceNode;' + class_var._class_name;
    class_var.__init__ = __init__17;
    class_var.entity_reference = entity_reference2;
    class_var.flags = flags3;
    class_var.tag_length = tag_length7;
    class_var.children = children10;
    __init__17(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function TemplateInstanceNode(pbuf, poffset, pchunk, pparent) {
    function __init__18(buf, offset, chunk, parent) {
        class_var.declare_field("byte", "token", 0, null);
        class_var.declare_field("byte", "unknown0", null, null);
        class_var.declare_field("dword", "template_id", null, null);
        class_var.declare_field("dword", "template_offset", null, null);
        class_var._data_length = 0;
        if (class_var.is_resident_template()) {
            var new_template = class_var._chunk.add_template(class_var.template_offset(), class_var);
            class_var._data_length += new_template.length();
        }
    }
    function is_resident_template() {
        var _retval = class_var.template_offset() > class_var.offset() - class_var._chunk._offset;
        return _retval;
    }
    function tag_length8() {
        return 10;
    }
    function length8() {
        var _retval = class_var.tag_length() + class_var._data_length;
        return _retval;
    }
    function template1() {
        var _retval = class_var._chunk.templates()[class_var.template_offset()];
        return _retval;
    }
    function children11() {
        var _retval = [];
        return _retval;
    }
    function find_end_of_stream2() {
        var _retval = class_var.template().find_end_of_stream();
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'TemplateInstanceNode;' + class_var._class_name;
    find_end_of_stream2 = memoize(find_end_of_stream2, class_var);
    class_var.__init__ = __init__18;
    class_var.is_resident_template = is_resident_template;
    class_var.tag_length = tag_length8;
    class_var.length = length8;
    class_var.template = template1;
    class_var.children = children11;
    class_var.find_end_of_stream = find_end_of_stream2;
    __init__18(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function NormalSubstitutionNode(pbuf, poffset, pchunk, pparent) {
    function __init__19(buf, offset, chunk, parent) {
        class_var.declare_field("byte", "token", 0, null);
        class_var.declare_field("word", "index", null, null);
        class_var.declare_field("byte", "type", null, null);
    }
    function tag_length9() {
        return 4;
    }
    function length9() {
        var _retval = class_var.tag_length();
        return _retval;
    }
    function children12() {
        var _retval = [];
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'NormalSubstitutionNode;' + class_var._class_name;
    class_var.__init__ = __init__19;
    class_var.tag_length = tag_length9;
    class_var.length = length9;
    class_var.children = children12;
    __init__19(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function ConditionalSubstitutionNode(pbuf, poffset, pchunk, pparent) {
    function __init__20(buf, offset, chunk, parent) {
        class_var.declare_field("byte", "token", 0, null);
        class_var.declare_field("word", "index", null, null);
        class_var.declare_field("byte", "type", null, null);
    }
    function tag_length10() {
        return 4;
    }
    function length10() {
        var _retval = class_var.tag_length();
        return _retval;
    }
    function children13() {
        var _retval = [];
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'ConditionalSubstitutionNode;' + class_var._class_name;
    class_var.__init__ = __init__20;
    class_var.tag_length = tag_length10;
    class_var.length = length10;
    class_var.children = children13;
    __init__20(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function StreamStartNode(pbuf, poffset, pchunk, pparent) {
    function __init__21(buf, offset, chunk, parent) {
        class_var.declare_field("byte", "token", 0, null);
        class_var.declare_field("byte", "unknown0", null, null);
        class_var.declare_field("word", "unknown1", null, null);
    }
    function tag_length11() {
        return 4;
    }
    function length11() {
        var _retval = class_var.tag_length() + 0;
        return _retval;
    }
    function children14() {
        var _retval = [];
        return _retval;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'StreamStartNode;' + class_var._class_name;
    class_var.__init__ = __init__21;
    class_var.tag_length = tag_length11;
    class_var.length = length11;
    class_var.children = children14;
    __init__21(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function RootNode(pbuf, poffset, pchunk, pparent) {
    function __init__22(buf, offset, chunk, parent) {
    }
    function tag_length12() {
        return 0;
    }
    function children15() {
        var _retval = class_var._children(null, [EndOfStreamToken]);
        return _retval;
    }
    function tag_and_children_length() {
        var children_length = 0;
        for (var child of class_var.children()) {
            children_length += child.length();
        }
        var _retval = class_var.tag_length() + children_length;
        return _retval;
    }
    function template_instance() {
        var ofs = class_var.offset();
        if ((class_var.unpack_byte(0) & 15) === 15) {
            ofs += 4;
        }
        var _retval = new TemplateInstanceNode(class_var._buf, ofs, class_var._chunk, class_var);
        return _retval;
    }
    function template2() {
        var instance = class_var.template_instance();
        var offset = class_var._chunk.offset() + instance.template_offset();
        var node = new TemplateNode(class_var._buf, offset, class_var._chunk, instance);
        return node;
    }
    function substitutions() {
        var sub_decl = [];
        var sub_def = [];
        var ofs = class_var.tag_and_children_length();
        var sub_count = class_var.unpack_dword(ofs);
        ofs += 4;
        for (var i = 0; i < sub_count; i++) {
            var size = class_var.unpack_word(ofs);
            var type_ = class_var.unpack_byte(ofs + 2);
            sub_decl.push([size, type_]);
            ofs += 4;
        }
        for (var index = 0; index < sub_decl.length; index++) {
            var size = sub_decl[index][0];
            var type_ = sub_decl[index][1];
            var val = get_variant_value(class_var._buf, class_var.offset() + ofs, class_var._chunk, class_var, type_, size);
            if (Math.abs(size - val.length()) > 4) {
                throw new ParseException("Invalid substitution value size");
            }
            sub_def.push(val);
            ofs += size;
        }
        return sub_def;
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'RootNode;' + class_var._class_name;
    children15 = memoize(children15, class_var);
    substitutions = memoize(substitutions, class_var);
    class_var.__init__ = __init__22;
    class_var.tag_length = tag_length12;
    class_var.children = children15;
    class_var.tag_and_children_length = tag_and_children_length;
    class_var.template_instance = template_instance;
    class_var.template = template2;
    class_var.substitutions = substitutions;
    __init__22(pbuf, poffset, pchunk, pparent);
    return class_var;
}
function VariantTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__23(buf, offset, chunk, parent, length) {
        class_var._length = length;
    }
    function length12() {
        var _retval = class_var.tag_length();
        return _retval;
    }
    function children16() {
        return [];
    }
    var class_var = BXmlNode(pbuf, poffset, pchunk, pparent);
    class_var._class_name = 'VariantTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__23;
    class_var.length = length12;
    class_var.children = children16;
    __init__23(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function NullTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__24(buf, offset, chunk, parent, length) {
        class_var._offset = offset;
        class_var._length = length;
    }
    function string1() {
        return "";
    }
    function length13() {
        var _retval = class_var._length || 0;
        return _retval;
    }
    function children17() {
        return [];
    }
    var class_var = SkelClass('NullTypeNode');
    class_var.__init__ = __init__24;
    class_var.string = string1;
    class_var.length = length13;
    class_var.children = children17;
    __init__24(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function WstringTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__25(buf, offset, chunk, parent, length) {
        if (class_var._length === null) {
            class_var.declare_field("word", "string_length", 0, null);
            class_var.declare_field("wstring", "_string", null, class_var.string_length());
            return;
        }
        class_var.declare_field("wstring", "_string", 0, Math.floor(class_var._length / 2));
    }
    function tag_length13() {
        if (class_var._length === null) {
            var _retval = 2 + (class_var.string_length() * 2);
            return _retval;
        }
        var _retval = class_var._length;
        return _retval;
    }
    function string2() {
        var _retval = class_var._string().replace('\x00', '');
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'WstringTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__25;
    class_var.tag_length = tag_length13;
    class_var.string = string2;
    __init__25(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function UnsignedByteTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__26(buf, offset, chunk, parent, length) {
        class_var.declare_field("byte", "byte", 0, null);
    }
    function tag_length14() {
        return 1;
    }
    function string3() {
        var _retval = String(class_var.byte());
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'UnsignedByteTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__26;
    class_var.tag_length = tag_length14;
    class_var.string = string3;
    __init__26(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function UnsignedWordTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__27(buf, offset, chunk, parent, length) {
        class_var.declare_field("word", "word", 0, null);
    }
    function tag_length15() {
        return 2;
    }
    function string4() {
        var _retval = String(class_var.word());
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'UnsignedWordTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__27;
    class_var.tag_length = tag_length15;
    class_var.string = string4;
    __init__27(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function UnsignedDwordTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__28(buf, offset, chunk, parent, length) {
        class_var.declare_field("dword", "dword", 0, null);
    }
    function tag_length16() {
        return 4;
    }
    function string5() {
        var _retval = String(class_var.dword());
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'UnsignedDwordTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__28;
    class_var.tag_length = tag_length16;
    class_var.string = string5;
    __init__28(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function UnsignedQwordTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__29(buf, offset, chunk, parent, length) {
        class_var.declare_field("qword", "qword", 0, null);
    }
    function tag_length17() {
        return 8;
    }
    function string6() {
        var _retval = String(class_var.qword());
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'UnsignedQwordTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__29;
    class_var.tag_length = tag_length17;
    class_var.string = string6;
    __init__29(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function FloatTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__30(buf, offset, chunk, parent, length) {
        class_var.declare_field("dword", "float", 0, null);
    }
    function tag_length18() {
        return 4;
    }
    function string7() {
        var _retval = String(class_var.float());
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'FloatTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__30;
    class_var.tag_length = tag_length18;
    class_var.string = string7;
    __init__30(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function DoubleTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__31(buf, offset, chunk, parent, length) {
        class_var.declare_field('qword', 'double', 0, null);
    }
    function tag_length19() {
        return 8;
    }
    function string8() {
        var _retval = String(class_var.double());
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'DoubleTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__31;
    class_var.tag_length = tag_length19;
    class_var.string = string8;
    __init__31(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function BooleanTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__32(buf, offset, chunk, parent, length) {
        class_var.declare_field("int32", "int32", 0, null);
    }
    function tag_length20() {
        return 4;
    }
    function string9() {
        if (class_var.int32() > 0) {
            return "True";
        }
        return "False";
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'BooleanTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__32;
    class_var.tag_length = tag_length20;
    class_var.string = string9;
    __init__32(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function BinaryTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__33(buf, offset, chunk, parent, length) {
        if (class_var._length === null) {
            class_var.declare_field("dword", "size", 0, null);
            class_var.declare_field("binary", "binary", null, class_var.size());
            return;
        }
        class_var.declare_field("binary", "binary", 0, class_var._length);
    }
    function tag_length21() {
        if (class_var._length === null) {
            var _retval = 4 + class_var.size();
            return _retval;
        }
        var _retval = class_var._length;
        return _retval;
    }
    function string10() {
        var _retval = Buffer.from(class_var.binary()).toString('base64');
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'BinaryTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__33;
    class_var.tag_length = tag_length21;
    class_var.string = string10;
    __init__33(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function GuidTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__34(buf, offset, chunk, parent, length) {
        class_var.declare_field("guid", "guid", 0, null);
    }
    function tag_length22() {
        return 16;
    }
    function string11() {
        var _retval = "{" + class_var.guid() + "}";
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'GuidTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__34;
    class_var.tag_length = tag_length22;
    class_var.string = string11;
    __init__34(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function SizeTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__35(buf, offset, chunk, parent, length) {
        if (class_var._length === 4) {
            class_var.declare_field('dword', 'num', 0, null);
            return;
        }
        if (class_var._length === 8) {
            class_var.declare_field('qword', 'num', 0, null);
            return;
        }
        class_var.declare_field('qword', 'num', 0, null);
    }
    function tag_length23() {
        if (class_var._length === null) {
            return 8;
        }
        return class_var._length;
    }
    function string12() {
        var _retval = String(class_var.num());
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'SizeTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__35;
    class_var.tag_length = tag_length23;
    class_var.string = string12;
    __init__35(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function FiletimeTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__36(buf, offset, chunk, parent, length) {
        class_var.declare_field("filetime", "filetime", 0, null);
    }
    function string13() {
        return "time not supported";
    }
    function tag_length24() {
        return 8;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'FiletimeTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__36;
    class_var.string = string13;
    class_var.tag_length = tag_length24;
    __init__36(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function SystemtimeTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__37(buf, offset, chunk, parent, length) {
        class_var.declare_field('systemtime', 'systemtime', 0, null);
    }
    function tag_length25() {
        return 16;
    }
    function string14() {
        return "time not supported";
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'SystemtimeTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__37;
    class_var.tag_length = tag_length25;
    class_var.string = string14;
    __init__37(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function SIDTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__38(buf, offset, chunk, parent, length) {
        class_var.declare_field("byte", "version", 0, null);
        class_var.declare_field("byte", "num_elements", null, null);
        class_var.declare_field("dword_be", "id_high", null, null);
        class_var.declare_field("word_be", "id_low", null, null);
    }
    function elements() {
        var ret = [];
        var _tmp = class_var.num_elements();
        for (var i = 0; i < _tmp; i++) {
            ret.push(class_var.unpack_dword(class_var.current_field_offset() + 4 * i));
        }
        return ret;
    }
    function id() {
        var ret = "S-" + class_var.version() + "-" + ((class_var.id_high() << 16) ^ class_var.id_low());
        for (var elem of class_var.elements()) {
            ret += "-" + elem;
        }
        return ret;
    }
    function tag_length26() {
        var _retval = 8 + 4 * class_var.num_elements();
        return _retval;
    }
    function string15() {
        var _retval = class_var.id();
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'SIDTypeNode;' + class_var._class_name;
    elements = memoize(elements, class_var);
    id = memoize(id, class_var);
    class_var.__init__ = __init__38;
    class_var.elements = elements;
    class_var.id = id;
    class_var.tag_length = tag_length26;
    class_var.string = string15;
    __init__38(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function Hex32TypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__39(buf, offset, chunk, parent, length) {
        class_var.declare_field("binary", "hex", 0, 4);
    }
    function tag_length27() {
        return 4;
    }
    function string16() {
        var ret = "0x";
        var b = Array.from(class_var.hex()).reverse();
        for (var i = 0; i < b.length; i++) {
            ret += b[i].toString(16).padStart(2, '0');
        }
        return ret;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'Hex32TypeNode;' + class_var._class_name;
    class_var.__init__ = __init__39;
    class_var.tag_length = tag_length27;
    class_var.string = string16;
    __init__39(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function Hex64TypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__40(buf, offset, chunk, parent, length) {
        class_var.declare_field("binary", "hex", 0, 8);
    }
    function tag_length28() {
        return 8;
    }
    function string17() {
        var ret = "0x";
        var b = Array.from(class_var.hex()).reverse();
        for (var i = 0; i < b.length; i++) {
            ret += b[i].toString(16).padStart(2, '0');
        }
        return ret;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'Hex64TypeNode;' + class_var._class_name;
    class_var.__init__ = __init__40;
    class_var.tag_length = tag_length28;
    class_var.string = string17;
    __init__40(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function BXmlTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__41(buf, offset, chunk, parent, length) {
        class_var._root = new RootNode(buf, offset, chunk, class_var);
    }
    function tag_length29() {
        var _retval = class_var._length || class_var._root.length();
        return _retval;
    }
    function string18() {
        return "";
    }
    function root1() {
        var _retval = class_var._root;
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'BXmlTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__41;
    class_var.tag_length = tag_length29;
    class_var.string = string18;
    class_var.root = root1;
    __init__41(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function WstringArrayTypeNode(pbuf, poffset, pchunk, pparent, plength) {
    function __init__42(buf, offset, chunk, parent, length) {
        if (class_var._length === null) {
            class_var.declare_field("word", "binary_length", 0, null);
            class_var.declare_field("binary", "binary", null, class_var.binary_length());
            return;
        }
        class_var.declare_field("binary", "binary", 0, class_var._length);
    }
    function tag_length30() {
        if (class_var._length === null) {
            var _retval = 2 + class_var.binary_length();
            return _retval;
        }
        var _retval = class_var._length;
        return _retval;
    }
    function string19() {
        var binary = class_var.binary();
        var binaryString = (new TextDecoder("utf-16")).decode(binary);
        var acc = [];
        while (binaryString.length > 0) {
            var match = binaryString.match(/(?:[^\x00].)+/);
            if (match) {
                var frag = match[0];
                acc.push("<string>");
                acc.push(frag);
                acc.push("</string>\n");
                binaryString = binaryString.substring(frag.length + 2);
                if (binaryString.length === 0) {
                    break;
                }
            }
            frag = binaryString.match(/(\x00*)/)[0];
            if (frag.length % 2 === 0) {
                for (var i = 0; i < frag.length / 2; i++) {
                    acc.push("<string></string>\n");
                }
            } else {
                throw new ParseException("Error parsing uneven substring of NULLs");
            }
            binaryString = binaryString.slice(frag.length);
        }
        var _retval = acc.join("");
        return _retval;
    }
    var class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength);
    class_var._class_name = 'WstringArrayTypeNode;' + class_var._class_name;
    class_var.__init__ = __init__42;
    class_var.tag_length = tag_length30;
    class_var.string = string19;
    __init__42(pbuf, poffset, pchunk, pparent, plength);
    return class_var;
}
function UnexpectedElementException(param_0) {
    function __init__43(msg) {
    }
    var class_var = new Error(param_0);
    class_var._class_name = 'UnexpectedElementException;' + class_var._class_name;
    class_var.__init__ = __init__43;
    __init__43(param_0);
    return class_var;
}
function escape_value(s) {
    var esc = s.replace('&', '&amp;');
    esc = esc.replace('<', '&lt;');
    esc = esc.replace('>', '&gt;');
    esc = esc.replace('"', '&quot;');
    esc = esc.replace("'", '&#x27;');
    esc = esc.replace(/[\u0080-\uFFFF]/g, m => `&#${m.charCodeAt(0)};`);
    esc = esc.replace(RESTRICTED_CHARS, '');
    return esc;
}
function validate_name(s) {
    if (!NAME_PATTERN.test(s)) {
        throw new Error("invalid xml name: " + s);
    }
    return s;
}
function render_root_node_with_subs(root_node, subs) {
    function rec(node, acc) {
        if (user_check_type(node, EndOfStreamNode)) {
        } else if (user_check_type(node, OpenStartElementNode)) {
            acc.push("<");
            acc.push(node.tag_name());
            for (var child of node.children()) {
                if (user_check_type(child, AttributeNode)) {
                    acc.push(" ");
                    acc.push(validate_name(child.attribute_name().string()));
                    acc.push('="');
                    rec(child.attribute_value(), acc);
                    acc.push('"');
                }
            }
            acc.push(">");
            for (var child of node.children()) {
                rec(child, acc);
            }
            acc.push("</");
            acc.push(validate_name(node.tag_name()));
            acc.push(">\n");
        } else if (user_check_type(node, CloseStartElementNode)) {
        } else if (user_check_type(node, CloseEmptyElementNode)) {
        } else if (user_check_type(node, CloseElementNode)) {
        } else if (user_check_type(node, ValueNode)) {
            acc.push(escape_value(node.children()[0].string()));
        } else if (user_check_type(node, AttributeNode)) {
        } else if (user_check_type(node, EntityReferenceNode)) {
            acc.push(escape_value(node.entity_reference()));
        } else if (user_check_type(node, TemplateInstanceNode)) {
            throw new UnexpectedElementException("TemplateInstanceNode");
        } else if (user_check_type(node, NormalSubstitutionNode)) {
            var sub = subs[node.index()];
            if (user_check_type(sub, BXmlTypeNode)) {
                sub = render_root_node(sub.root());
            } else {
                sub = escape_value(sub.string());
            }
            acc.push(sub);
        } else if (user_check_type(node, ConditionalSubstitutionNode)) {
            var sub = subs[node.index()];
            if (user_check_type(sub, BXmlTypeNode)) {
                sub = render_root_node(sub.root());
            } else {
                sub = escape_value(sub.string());
            }
            acc.push(sub);
        } else if (user_check_type(node, StreamStartNode)) {
        }
    }
    var acc = [];
    for (var child of root_node.template().children()) {
        rec(child, acc);
    }
    var _retval = acc.join("");
    return _retval;
}
function render_root_node(root_node) {
    var subs = [];
    for (var sub of root_node.substitutions()) {
        if (user_check_type(sub, "string")) {
            throw new Error("string sub?");
        }
        if (sub === null) {
            throw new Error("null sub?");
        }
        subs.push(sub);
    }
    var _retval = render_root_node_with_subs(root_node, subs);
    return _retval;
}
function evtx_record_xml_view(record, cache) {
    var _retval = render_root_node(record.root());
    return _retval;
}
function InvalidRecordException() {
    function __init__44() {
    }
    var class_var = ParseException("Invalid record structure");
    class_var._class_name = 'InvalidRecordException;' + class_var._class_name;
    class_var.__init__ = __init__44;
    __init__44();
    return class_var;
}
function FileHeader(pbuf, poffset) {
    function __init__45(buf, offset) {
        class_var.declare_field("string", "magic", 0, 8);
        class_var.declare_field("qword", "oldest_chunk", null, null);
        class_var.declare_field("qword", "current_chunk_number", null, null);
        class_var.declare_field("qword", "next_record_number", null, null);
        class_var.declare_field("dword", "header_size", null, null);
        class_var.declare_field("word", "minor_version", null, null);
        class_var.declare_field("word", "major_version", null, null);
        class_var.declare_field("word", "header_chunk_size", null, null);
        class_var.declare_field("word", "chunk_count", null, null);
        class_var.declare_field("binary", "unused1", null, 76);
        class_var.declare_field("dword", "flags", null, null);
        class_var.declare_field("dword", "checksum", null, null);
    }
    function check_magic1() {
        var _retval = class_var.magic() === 'ElfFile\x00';
        return _retval;
    }
    function calculate_checksum() {
        var buffer = class_var.unpack_binary(0, 120);
        var _retval = crc32.buf(buffer) >>> 0;
        return _retval;
    }
    function verify1() {
        var _retval = class_var.check_magic() && class_var.major_version() === 3 && (class_var.minor_version() === 1) && (class_var.header_chunk_size() === 4096) && (class_var.checksum() === class_var.calculate_checksum());
        return _retval;
    }
    function is_dirty() {
        var _retval = (class_var.flags() & 1) === 1;
        return _retval;
    }
    function is_full() {
        var _retval = (class_var.flags() & 2) === 2;
        return _retval;
    }
    function first_chunk() {
        var ofs = class_var._offset + class_var.header_chunk_size();
        var _retval = ChunkHeader(class_var._buf, ofs);
        return _retval;
    }
    function current_chunk() {
        var ofs = class_var._offset + class_var.header_chunk_size();
        ofs += class_var.current_chunk_number() * 65536;
        var _retval = ChunkHeader(class_var._buf, ofs);
        return _retval;
    }
    function chunks(include_inactive) {
        var chunk_count = 1000000;
        if (!include_inactive) {
            chunk_count = class_var.chunk_count();
        }
        var i = 0;
        var ofs = class_var._offset + class_var.header_chunk_size();
        var _return_chunks = [];
        while (ofs + 65536 <= class_var._buf.length && i < chunk_count) {
            var _yield_value = new ChunkHeader(class_var._buf, ofs);
            _return_chunks.push(_yield_value);
            ofs += 65536;
            i += 1;
        }
        return _return_chunks;
    }
    function get_record(record_num) {
        for (var chunk of class_var.chunks()) {
            var first_record = chunk.log_first_record_number();
            var last_record = chunk.log_last_record_number();
            if (!(first_record <= record_num && record_num <= last_record)) {
                continue;
            }
            for (var record of chunk.records()) {
                if (record.record_num() === record_num) {
                    return record;
                }
            }
        }
        return null;
    }
    var class_var = Block(pbuf, poffset);
    class_var._class_name = 'FileHeader;' + class_var._class_name;
    class_var.__init__ = __init__45;
    class_var.check_magic = check_magic1;
    class_var.calculate_checksum = calculate_checksum;
    class_var.verify = verify1;
    class_var.is_dirty = is_dirty;
    class_var.is_full = is_full;
    class_var.first_chunk = first_chunk;
    class_var.current_chunk = current_chunk;
    class_var.chunks = chunks;
    class_var.get_record = get_record;
    __init__45(pbuf, poffset);
    return class_var;
}
function ChunkHeader(pbuf, poffset) {
    function __init__46(buf, offset) {
        class_var._strings = null;
        class_var._templates = null;
        class_var.declare_field("string", "magic", 0, 8);
        class_var.declare_field("qword", "file_first_record_number", null, null);
        class_var.declare_field("qword", "file_last_record_number", null, null);
        class_var.declare_field("qword", "log_first_record_number", null, null);
        class_var.declare_field("qword", "log_last_record_number", null, null);
        class_var.declare_field("dword", "header_size", null, null);
        class_var.declare_field("dword", "last_record_offset", null, null);
        class_var.declare_field("dword", "next_record_offset", null, null);
        class_var.declare_field("dword", "data_checksum", null, null);
        class_var.declare_field("binary", "unused", null, 68);
        class_var.declare_field("dword", "header_checksum", null, null);
    }
    function check_magic2() {
        var _retval = class_var.magic() === "ElfChnk\x00";
        return _retval;
    }
    function calculate_header_checksum() {
        var data = new Uint8Array([...class_var.unpack_binary(0, 120), ...class_var.unpack_binary(128, 384)]);
        var _retval = crc32.buf(data) >>> 0;
        return _retval;
    }
    function calculate_data_checksum() {
        var data = class_var.unpack_binary(512, class_var.next_record_offset() - 512);
        var _retval = crc32.buf(data) >>> 0;
        return _retval;
    }
    function verify2() {
        var _retval = class_var.check_magic() && class_var.calculate_header_checksum() === class_var.header_checksum() && (class_var.calculate_data_checksum() === class_var.data_checksum());
        return _retval;
    }
    function _load_strings() {
        if (class_var._strings === null) {
            class_var._strings = {};
        }
        for (var i = 0; i < 64; i++) {
            var ofs = class_var.unpack_dword(128 + (i * 4));
            while (ofs > 0) {
                var string_node = class_var.add_string(ofs, null);
                ofs = string_node.next_offset();
            }
        }
    }
    function strings() {
        if (!class_var._strings) {
            class_var._load_strings();
        }
        var _retval = class_var._strings;
        return _retval;
    }
    function add_string(offset, parent) {
        if (class_var._strings === null) {
            class_var._load_strings();
        }
        var string_node = new NameStringNode(class_var._buf, class_var._offset + offset, class_var, parent || class_var);
        class_var._strings[offset] = string_node;
        return string_node;
    }
    function _load_templates() {
        if (class_var._templates === null) {
            class_var._templates = {};
        }
        for (var i = 0; i < 32; i++) {
            var ofs = class_var.unpack_dword(384 + (i * 4));
            while (ofs > 0) {
                var token = class_var.unpack_byte(ofs - 10);
                var pointer = class_var.unpack_dword(ofs - 4);
                if (token !== 12 || pointer !== ofs) {
                    ofs = 0;
                    continue;
                }
                var template = class_var.add_template(ofs, null);
                ofs = template.next_offset();
            }
        }
    }
    function add_template(offset, parent) {
        if (class_var._templates === null) {
            class_var._load_templates();
        }
        var node = new TemplateNode(class_var._buf, class_var._offset + offset, class_var, parent || class_var);
        class_var._templates[offset] = node;
        return node;
    }
    function templates() {
        if (!class_var._templates) {
            class_var._load_templates();
        }
        var _retval = class_var._templates;
        return _retval;
    }
    function first_record() {
        var _retval = new Record(class_var._buf, class_var._offset + 512, class_var);
        return _retval;
    }
    function records() {
        var result = [];
        try {
            var record = class_var.first_record();
        } catch (e) {
            if (e instanceof InvalidRecordException) {
                return result;
            }
        }
        while (record._offset < class_var._offset + class_var.next_record_offset() && record.length() > 0) {
            result.push(record);
            try {
                record = new Record(class_var._buf, record._offset + record.length(), class_var);
            } catch (e) {
                if (e instanceof InvalidRecordException) {
                    return result;
                }
            }
        }
        return result;
    }
    var class_var = Block(pbuf, poffset);
    class_var._class_name = 'ChunkHeader;' + class_var._class_name;
    class_var.__init__ = __init__46;
    class_var.check_magic = check_magic2;
    class_var.calculate_header_checksum = calculate_header_checksum;
    class_var.calculate_data_checksum = calculate_data_checksum;
    class_var.verify = verify2;
    class_var._load_strings = _load_strings;
    class_var.strings = strings;
    class_var.add_string = add_string;
    class_var._load_templates = _load_templates;
    class_var.add_template = add_template;
    class_var.templates = templates;
    class_var.first_record = first_record;
    class_var.records = records;
    __init__46(pbuf, poffset);
    return class_var;
}
function Record(pbuf, poffset, pchunk) {
    function __init__47(buf, offset, chunk) {
        class_var._chunk = chunk;
        class_var.declare_field("dword", "magic", 0, null);
        class_var.declare_field("dword", "size", null, null);
        class_var.declare_field("qword", "record_num", null, null);
        class_var.declare_field("filetime", "timestamp", null, null);
        if (class_var.size() > 65536) {
            return null;
        }
        class_var.declare_field("dword", "size2", class_var.size() - 4, null);
    }
    function root2() {
        var _retval = new RootNode(class_var._buf, class_var._offset + 24, class_var._chunk, class_var);
        return _retval;
    }
    function length14() {
        var _retval = class_var.size();
        return _retval;
    }
    function verify3() {
        var _retval = class_var.size() === class_var.size2();
        return _retval;
    }
    function data() {
        var _retval = class_var._buf.slice(class_var.offset(), class_var.offset() + class_var.size());
        return _retval;
    }
    function xml() {
        var _retval = evtx_record_xml_view(class_var, null);
        return _retval;
    }
    var class_var = Block(pbuf, poffset);
    class_var._class_name = 'Record;' + class_var._class_name;
    class_var.__init__ = __init__47;
    class_var.root = root2;
    class_var.length = length14;
    class_var.verify = verify3;
    class_var.data = data;
    class_var.xml = xml;
    __init__47(pbuf, poffset, pchunk);
    return class_var;
}
function test_chunks_sys(input_str) {
    var fh = new FileHeader(input_str, 0);
    var chunks = Array.from(fh["chunks"](false));
    if (chunks.length !== 1) {
        throw new Error('Assertion failed');
    }
    var chunk = chunks[0];
    if (!chunk.check_magic()) {
        throw new Error('Assertion failed');
    }
    if (chunk.magic() !== "ElfChnk\x00") {
        throw new Error('Assertion failed');
    }
    if (chunk.calculate_header_checksum() !== chunk.header_checksum()) {
        throw new Error('Assertion failed');
    }
    if (chunk.calculate_data_checksum() !== chunk.data_checksum()) {
        throw new Error('Assertion failed');
    }
    if (chunk.file_first_record_number() !== expected_output1["start_file"]) {
        throw new Error('Assertion failed');
    }
    if (chunk.file_last_record_number() !== expected_output1["end_file"]) {
        throw new Error('Assertion failed');
    }
    if (chunk.log_first_record_number() !== expected_output1["start_log"]) {
        throw new Error('Assertion failed');
    }
    if (chunk.log_last_record_number() !== expected_output1["end_log"]) {
        throw new Error('Assertion failed');
    }
}
function test_chunks_sec(input_str) {
    var fh = new FileHeader(input_str, 0);
    var chunks = Array.from(fh["chunks"](false));
    if (chunks.length !== 1) {
        throw new Error('Assertion failed');
    }
    var chunk = chunks[0];
    if (!chunk.check_magic()) {
        throw new Error('Assertion failed');
    }
    if (chunk.magic() !== "ElfChnk\x00") {
        throw new Error('Assertion failed');
    }
    if (chunk.calculate_header_checksum() !== chunk.header_checksum()) {
        throw new Error('Assertion failed');
    }
    if (chunk.calculate_data_checksum() !== chunk.data_checksum()) {
        throw new Error('Assertion failed');
    }
    if (chunk.file_first_record_number() !== expected_output2["start_file"]) {
        throw new Error('Assertion failed');
    }
    if (chunk.file_last_record_number() !== expected_output2["end_file"]) {
        throw new Error('Assertion failed');
    }
    if (chunk.log_first_record_number() !== expected_output2["start_log"]) {
        throw new Error('Assertion failed');
    }
    if (chunk.log_last_record_number() !== expected_output2["end_log"]) {
        throw new Error('Assertion failed');
    }
}
function test_file_header_sys(input_str) {
    var fh = new FileHeader(input_str, 0);
    if(fh.magic() !== "ElfFile\x00") {
        throw new Error('Assertion failed');
    }
    if(fh.major_version() !== 3) {
        throw new Error('Assertion failed');
    }
    if(fh.minor_version() !== 1) {
        throw new Error('Assertion failed');
    }
    if(fh.flags() !== 1) {
        throw new Error('Assertion failed');
    }
    if(!fh.is_dirty()) {
        throw new Error('Assertion failed');
    }
    if(fh.is_full()) {
        throw new Error('Assertion failed');
    }
    if(fh.current_chunk_number() !== 0) {
        throw new Error('Assertion failed');
    }
    if(fh.chunk_count() !== 1) {
        throw new Error('Assertion failed');
    }
    if(fh.oldest_chunk() !== 0) {
        throw new Error('Assertion failed');
    }
    if(fh.next_record_number() !== 13528) {
        throw new Error('Assertion failed');
    }
    if(fh.checksum() !== 2761825960) {
        throw new Error('Assertion failed');
    }
    if(fh.calculate_checksum() !== fh.checksum()) {
        throw new Error('Assertion failed');
    }
}
function test_file_header_sec(input_str) {
    var fh = new FileHeader(input_str, 0);
    if(fh.magic() !== "ElfFile\x00") {
        throw new Error('Assertion failed');
    }
    if(fh.major_version() !== 3) {
        throw new Error('Assertion failed');
    }
    if(fh.minor_version() !== 1) {
        throw new Error('Assertion failed');
    }
    if(fh.flags() !== 1) {
        throw new Error('Assertion failed');
    }
    if(!fh.is_dirty()) {
        throw new Error('Assertion failed');
    }
    if(fh.is_full()) {
        throw new Error('Assertion failed');
    }
    if(fh.current_chunk_number() !== 0) {
        throw new Error('Assertion failed');
    }
    if(fh.chunk_count() !== 1) {
        throw new Error('Assertion failed');
    }
    if(fh.oldest_chunk() !== 0) {
        throw new Error('Assertion failed');
    }
    if(fh.next_record_number() !== 2226) {
        throw new Error('Assertion failed');
    }
    if(fh.checksum() !== 441071771) {
        throw new Error('Assertion failed');
    }
    if(fh.calculate_checksum() !== fh.checksum()) {
        throw new Error('Assertion failed');
    }
}
function _extract_structure(node) {
    var name = node._class_name.split(";")[0];
    var value = null;
    if (user_check_type(node, BXmlTypeNode)) {
        value = null;
    } else if (user_check_type(node, VariantTypeNode)) {
        value = node.string();
    } else if (user_check_type(node, OpenStartElementNode)) {
        value = node.tag_name();
    } else if (user_check_type(node, AttributeNode)) {
        value = node.attribute_name().string();
    } else {
        value = null;
    }
    var children = [];
    if (user_check_type(node, BXmlTypeNode)) {
        children.push(_extract_structure(node._root));
    } else if (user_check_type(node, TemplateInstanceNode) && node.is_resident_template()) {
        children.push(_extract_structure(node.template()));
    }
    children = children.concat(Array.from(node.children()).map(child => _extract_structure(child)));
    if (user_check_type(node, RootNode)) {
        var substitutions = Array.from(node.substitutions()).map(substitution => _extract_structure(substitution));
        children.push(["Substitutions", null, substitutions]);
    }
    if (children.length > 0) {
        var _retval = [name, value, children];
        return _retval;
    } else if (value !== null) {
        var _retval = [name, value];
        return _retval;
    } else {
        var _retval = [name];
        return _retval;
    }
}
function test_parse_record_sys(input_str) {
    var fh = new FileHeader(input_str, 0);
    var chunk = fh.chunks(false)[0];
    var record = chunk.records()[0];
    var expected_output3 = _get_expected_output3();
    if (JSON.stringify(_extract_structure(record.root())) !== JSON.stringify(expected_output3)) {
        throw new Error("Assertion failed");
    }
}
function test_parse_records_sys(input_str) {
    var fh = new FileHeader(input_str, 0);
    var chunks = Array.from(fh["chunks"](false));
    if (chunks.length !== 1) {
        throw new Error('Assertion failed');
    }
    var chunk = chunks[0];
    for (var record of chunk.records()) {
        if (record.magic() !== 10794) {
            throw new Error("Assertion failed");
        }
    }
}
function test_parse_records_sec(input_str) {
    var fh = new FileHeader(input_str, 0);
    var chunks = Array.from(fh["chunks"](false));
    if (chunks.length !== 1) {
        throw new Error('Assertion failed');
    }
    var chunk = chunks[0];
    for (var record of chunk.records()) {
        if (record.magic() !== 10794) {
            throw new Error("Assertion failed");
        }
    }
}
function test_render_record_sys(input_str) {
    var fh = new FileHeader(input_str, 0);
    var chunk = fh.chunks(false)[0];
    var record = chunk.records()[0];
    var expected_output4 = _get_expected_output4();
    var xml = record.xml();
    if (JSON.stringify(xml) !== JSON.stringify(expected_output4)) {
        throw new Error("Assertion failed");
    }
}
function test_render_records_sys(input_str) {
    var fh = new FileHeader(input_str, 0);
    var chunks = Array.from(fh["chunks"](false));
    if (chunks.length !== 1) {
        throw new Error('Assertion failed');
    }
    var chunk = chunks[0];
    var records = chunk.records();
    var include_only = [86, 106, 132, 133, 135];
    for (var idx = 0; idx < records.length; idx++) {
        if (!include_only.includes(idx)) {
            continue;
        }
        var record = records[idx];
        if (record.xml() === null) {
            throw new Error("Assertion failed");
        }
    }
}
function test_render_records_sec(input_str) {
    var fh = new FileHeader(input_str, 0);
    var chunks = Array.from(fh["chunks"](false));
    if (chunks.length !== 1) {
        throw new Error('Assertion failed');
    }
    var chunk = chunks[0];
    var records = chunk.records();
    var include_only = [0];
    for (var idx = 0; idx < records.length; idx++) {
        if (!include_only.includes(idx)) {
            continue;
        }
        var record = records[idx];
        if (record.xml() === null) {
            throw new Error("Assertion failed");
        }
    }
}
function test_init() {
    // escape_value
    escape_value('&&<<>>""\'\'\u0080\uFFFF');

    // memoize
    var obj = SkelClass('dummy');
    var fn = function (x) { return x; };
    fn = memoize(fn, obj);
    fn(1);

    // Block
    var inp = _get_test_init_input('block.evtx');
    obj = Block(inp, 0);
    obj.current_field_offset();
    obj.offset();
    obj.unpack_byte(0);
    obj.unpack_word(0);
    obj.unpack_word_be(0);
    obj.unpack_dword(0);
    obj.unpack_dword_be(0);
    obj.unpack_int32(0);
    obj.unpack_qword(0);
    obj.unpack_binary(0, null);
    obj.unpack_binary(0, 1);
    obj.unpack_string(0, 1);
    obj.unpack_wstring(0, 1);
    obj.unpack_guid(0);

    // NullTypeNode
    obj = NullTypeNode(inp, 0, null, null, null);
    obj.string();
    obj.length();
    obj.children();

    // NameStringNode
    inp = _get_test_init_input('name-string-node.evtx');
    obj = NameStringNode(inp, 0, null, null);
    obj.tag_length();
    obj.length();

    // TemplateNode
    inp = _get_test_init_input('template-node.evtx');
    obj = TemplateNode(inp, 0, null, null);
    obj.tag_length();
    obj.length();

    // EndOfStreamNode
    obj = EndOfStreamNode(inp, 0, null, null);
    obj.length();
    obj.children();

    // WstringTypeNode
    obj = WstringTypeNode(inp, 0, null, null, null);
    obj.string();
    obj.tag_length();
    obj = WstringTypeNode(inp, 0, null, null, 0);
    obj.tag_length();

    // VariantTypeNode
    obj.length();
    obj.children();

    // UnsignedByteTypeNode
    obj = UnsignedByteTypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj.string();

    // UnsignedWordTypeNode
    obj = UnsignedWordTypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj.string();

    // UnsignedDwordTypeNode
    obj = UnsignedDwordTypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj.string();

    // UnsignedQwordTypeNode
    obj = UnsignedQwordTypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj.string();

    // // FloatTypeNode - uncovered
    // obj = FloatTypeNode(inp, 0, null, null, null);
    // obj.tag_length();
    // obj.string();

    // // DoubleTypeNode - uncovered
    // obj = DoubleTypeNode(inp, 0, null, null, null);
    // obj.tag_length();
    // obj.string();

    // BooleanTypeNode
    inp = _get_test_init_input('boolean-type-node.evtx');
    obj = BooleanTypeNode(inp, 4, null, null, null);
    obj.string();
    obj = BooleanTypeNode(inp, 0, null, null, null);
    obj.string();
    obj.tag_length();

    // BinaryTypeNode
    inp = _get_test_init_input('binary-type-node.evtx');
    obj = BinaryTypeNode(inp, 0, null, null, null);
    obj.string();
    obj.tag_length();
    obj = BinaryTypeNode(inp, 0, null, null, 0);
    obj.tag_length();

    // GuidTypeNode
    inp = _get_test_init_input('block.evtx');
    obj = GuidTypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj.string();

    // // SizeTypeNode - uncovered
    // obj = SizeTypeNode(inp, 0, null, null, null);
    // obj.tag_length();
    // obj.string();
    // obj = SizeTypeNode(inp, 0, null, null, 4);
    // obj = SizeTypeNode(inp, 0, null, null, 8);
    // obj.tag_length();

    // FiletimeTypeNode
    obj = FiletimeTypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj.string();

    // // SystemtimeTypeNode - uncovered
    // obj = SystemtimeTypeNode(inp, 0, null, null, null);
    // obj.tag_length();
    // obj.string();

    // SIDTypeNode
    inp = _get_test_init_input('sid-type-node.evtx');
    obj = SIDTypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj.elements();
    obj.id();
    obj.string();

    // Hex32TypeNode
    inp = _get_test_init_input('block.evtx');
    obj = Hex32TypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj.string();

    // Hex64TypeNode
    obj = Hex64TypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj.string();

    // WstringArrayTypeNode
    inp = _get_test_init_input('wstring-array-type-node-1.evtx');
    obj = WstringArrayTypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj = WstringArrayTypeNode(inp, 0, null, null, 0);
    obj.tag_length();
    obj = WstringArrayTypeNode(inp, 0, null, null, null);
    obj.string();
    inp = _get_test_init_input('wstring-array-type-node-2.evtx');
    obj = WstringArrayTypeNode(inp, 0, null, null, null);
    obj.string();

    // CloseStartElementNode
    inp = _get_test_init_input('block.evtx');
    obj = CloseStartElementNode(inp, 0, null, null);
    obj.length();
    obj.children();

    // CloseEmptyElementNode
    obj = CloseEmptyElementNode(inp, 0, null, null);
    obj.length();
    obj.children();

    // CloseElementNode
    obj = CloseElementNode(inp, 0, null, null);
    obj.length();
    obj.children();

    // get_variant_value
    get_variant_value(inp, 0, null, null, 0x00, null);

    // ValueNode
    obj = ValueNode(inp, 0, null, null);
    obj.tag_length();
    obj.children();

    // CharacterReferenceNode
    obj = CharacterReferenceNode(inp, 0, null, null);
    obj.entity_reference();
    obj.flags();
    obj.tag_length();
    obj.children();

    // EntityReferenceNode - uncovered
    // obj = EntityReferenceNode(inp, 0, null, null);

    // NormalSubstitutionNode
    obj = NormalSubstitutionNode(inp, 0, null, null);
    obj.tag_length();
    obj.length();
    obj.children();

    // ConditionalSubstitutionNode
    obj = ConditionalSubstitutionNode(inp, 0, null, null);
    obj.tag_length();
    obj.length();
    obj.children();

    // StreamStartNode
    obj = StreamStartNode(inp, 0, null, null);
    obj.tag_length();
    obj.length();
    obj.children();

    // Record (partial)
    inp = _get_test_init_input('record-1.evtx');
    obj = Record(inp, 0, null);
    inp = _get_test_init_input('record-2.evtx');
    obj = Record(inp, 0, null);
    obj.length();
    obj.data();
    obj.root();

    // ChunkHeader (partial)
    inp = _get_test_init_input('empty.evtx');
    obj = ChunkHeader(inp, 0);
    obj.check_magic();
    obj.calculate_header_checksum();
    obj.add_string(0, null);
    obj = ChunkHeader(inp, 0);
    obj.strings();
    obj.first_record();

    // TemplateInstanceNode (partial)
    inp = _get_test_init_input('template-instance-node.evtx');
    var obj2 = TemplateInstanceNode(inp, 0, obj, null);
    obj2.tag_length();
    obj2.length();
    obj2.children();

    // RootNode, BXmlNode (partial)
    inp = _get_test_init_input('empty.evtx');
    obj = RootNode(inp, 0, null, null);
    obj.tag_length();
    obj._children(1, [0x00]);
    obj.children();
    obj.length();
    obj.find_end_of_stream();

    // BXmlTypeNode
    obj = BXmlTypeNode(inp, 0, null, null, null);
    obj.tag_length();
    obj.string();
    obj.root();
}
function test() {
    test_init();
    var sys_bstr = get_input('case1');
    var sec_bstr = get_input('case2');
    test_chunks_sys(sys_bstr);
    test_chunks_sec(sec_bstr);
    test_file_header_sys(sys_bstr);
    test_file_header_sec(sec_bstr);
    test_parse_record_sys(sys_bstr);
    test_parse_records_sys(sys_bstr);
    test_parse_records_sec(sec_bstr);
    test_render_record_sys(sys_bstr);
    test_render_records_sys(sys_bstr);
    test_render_records_sec(sec_bstr);
}

const NODE_DISPATCH_TABLE = [EndOfStreamNode, OpenStartElementNode, CloseStartElementNode, CloseEmptyElementNode, CloseElementNode, ValueNode, AttributeNode, null, CharacterReferenceNode, EntityReferenceNode, null, null, TemplateInstanceNode, NormalSubstitutionNode, ConditionalSubstitutionNode, StreamStartNode];

test();
