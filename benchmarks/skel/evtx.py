import os
import base64
import datetime
import json
import re
import os.path
import struct
from binascii import crc32

NAME_PATTERN = re.compile('[a-zA-Z_][a-zA-Z_\\-]*')
RESTRICTED_CHARS = re.compile('[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]')

EndOfStreamToken = 0
OpenStartElementToken = 1
CloseStartElementToken = 2
CloseEmptyElementToken = 3
CloseElementToken = 4
ValueToken = 5
AttributeToken = 6
CDataSectionToken = 7
EntityReferenceToken = 8
ProcessingInstructionTargetToken = 10
ProcessingInstructionDataToken = 11
TemplateInstanceToken = 12
NormalSubstitutionToken = 13
ConditionalSubstitutionToken = 14
StartOfStreamToken = 15

NULL = 0
WSTRING = 1
STRING = 2
SIGNED_BYTE = 3
UNSIGNED_BYTE = 4
SIGNED_WORD = 5
UNSIGNED_WORD = 6
SIGNED_DWORD = 7
UNSIGNED_DWORD = 8
SIGNED_QWORD = 9
UNSIGNED_QWORD = 10
FLOAT = 11
DOUBLE = 12
BOOLEAN = 13
BINARY = 14
GUID = 15
SIZE = 16
FILETIME = 17
SYSTEMTIME = 18
SID = 19
HEX32 = 20
HEX64 = 21
BXML = 33
WSTRINGARRAY = 129

expected_output1 = {'start_file': 1, 'end_file': 153, 'start_log': 12049, 'end_log': 12201}
expected_output2 = {'start_file': 1, 'end_file': 91, 'start_log': 1, 'end_log': 91}


def user_check_type(obj, _type):
    if 'function' in str(_type):
        for i in obj._class_name.split(';'):
            if i == str(_type).split(' ')[1]:
                return True
        return False
def SkelClass(class_name):
    Clz = type(class_name, (), {'_class_name': class_name})
    return Clz()
def system_path():
    cd = os.path.dirname(__file__)
    datadir = os.path.join(cd, 'evtx.d')
    systempath = os.path.join(datadir, 'system.evtx')
    return systempath
def system():
    p = system_path()
    with open(p, 'rb') as f:
        return f.read()
def security_path():
    cd = os.path.dirname(__file__)
    datadir = os.path.join(cd, 'evtx.d')
    secpath = os.path.join(datadir, 'security.evtx')
    return secpath
def security():
    p = security_path()
    with open(p, 'rb') as f:
        return f.read()
def user_infinite_counter():
    start = 0
    while True:
        yield start
        start += 1
def get_input(_case):
    if _case == 'case1':
        return system()
    else:
        return security()
def _get_expected_output3():
    cd = os.path.dirname(__file__)
    datadir = os.path.join(cd, 'evtx.d')
    systempath = os.path.join(datadir, 'expected_output3.json')
    with open(systempath, 'r') as f:
        return json.load(f)
def _get_expected_output_4():
    cd = os.path.dirname(__file__)
    datadir = os.path.join(cd, 'evtx.d')
    systempath = os.path.join(datadir, 'expected_output4.json')
    with open(systempath, 'r') as f:
        return json.load(f)
def _get_test_init_input(input_name):
    cd = os.path.dirname(__file__)
    datadir = os.path.join(cd, 'evtx.d')
    input_path = os.path.join(datadir, input_name)
    with open(input_path, 'rb') as f:
        return f.read()









def memoize(param_0, decorated_object):
    def __init__1(func):
        class_var.func = func
    def __call__(*args):
        obj = args[0]
        if not hasattr(obj, '__cache'):
            obj.__cache = {}
        cache = obj.__cache
        if class_var not in cache:
            cache[class_var] = class_var.func(*args)
        _mem_retval = cache[class_var]
        return _mem_retval
    def self_func(*args):
        _retval = tmp_f(*args[1:])
        return _retval
    def self_call(*args):
        _retval = __call__(decorated_object, *args)
        return _retval
    class_var = SkelClass('memoize')
    tmp_f = param_0
    param_0 = self_func
    class_var.__init__ = __init__1
    class_var.__call__ = __call__
    __init__1(param_0)
    return self_call
def parse_filetime(qword):
    if qword == 0:
        return datetime.datetime.min
    try:
        return datetime.datetime.fromtimestamp(float(qword) * 1e-07 - 11644473600, datetime.timezone.utc)
    except (ValueError, OSError):
        return datetime.datetime.min
def BinaryParserException(pvalue):
    def __init__2(value):
        class_var._value = value
    class_var = Exception()
    class_var._class_name = 'BinaryParserException;' + class_var._class_name
    class_var.__init__ = __init__2
    __init__2(pvalue)
    return class_var
def ParseException(pvalue):
    def __init__3(value):
        pass
    class_var = BinaryParserException(pvalue)
    class_var._class_name = 'ParseException;' + class_var._class_name
    class_var.__init__ = __init__3
    __init__3(pvalue)
    return class_var
def OverrunBufferException(preadOffs, pbufLen):
    def __init__4(readOffs, bufLen):
        tvalue = 'read: {}, buffer length: {}'.format(hex(readOffs), hex(bufLen))
    class_var = ParseException('Error: Type not support')
    class_var._class_name = 'OverrunBufferException;' + class_var._class_name
    class_var.__init__ = __init__4
    __init__4(preadOffs, pbufLen)
    return class_var
def Block(pbuf, poffset):
    def __init__5(buf, offset):
        class_var._buf = buf
        class_var._offset = offset
        class_var._implicit_offset = 0
    def declare_field(type, name, offset, length):
        def no_length_handler():
            f = getattr(class_var, 'unpack_' + type)
            return f(offset)
        def explicit_length_handler():
            f = getattr(class_var, 'unpack_' + type)
            return f(offset, length)
        if offset is None:
            offset = class_var._implicit_offset
        if length is None:
            setattr(class_var, name, no_length_handler)
        else:
            setattr(class_var, name, explicit_length_handler)
        setattr(class_var, '_off_' + name, offset)
        if type == 'byte' or type == 'int8':
            class_var._implicit_offset = offset + 1
        elif type == 'word' or type == 'word_be' or type == 'int16':
            class_var._implicit_offset = offset + 2
        elif type == 'dword' or type == 'dword_be' or type == 'int32' or type == 'float':
            class_var._implicit_offset = offset + 4
        elif type == 'qword' or type == 'int64' or type == 'double' or type == 'filetime' or type == 'systemtime':
            class_var._implicit_offset = offset + 8
        elif type == 'guid':
            class_var._implicit_offset = offset + 16
        elif type == 'binary':
            class_var._implicit_offset = offset + length
        elif type == 'string' and length is not None:
            class_var._implicit_offset = offset + length
        elif type == 'wstring' and length is not None:
            class_var._implicit_offset = offset + 2 * length
        elif 'string' in type and length is None:
            raise ParseException('Implicit offset not supported for dynamic length strings')
        else:
            raise ParseException('Implicit offset not supported for type: {}'.format(type))
    def current_field_offset():
        return class_var._implicit_offset
    def unpack_byte(offset):
        o = class_var._offset + offset
        try:
            _retval = struct.unpack_from('<B', class_var._buf, o)[0]
            return _retval
        except:
            raise OverrunBufferException(o, len(class_var._buf))
    def unpack_word(offset):
        o = class_var._offset + offset
        try:
            _retval = struct.unpack_from('<H', class_var._buf, o)[0]
            return _retval
        except:
            raise OverrunBufferException(o, len(class_var._buf))
    def unpack_word_be(offset):
        o = class_var._offset + offset
        try:
            _retval = struct.unpack_from('>H', class_var._buf, o)[0]
            return _retval
        except:
            raise OverrunBufferException(o, len(class_var._buf))
    def unpack_dword(offset):
        o = class_var._offset + offset
        try:
            _retval = struct.unpack_from('<I', class_var._buf, o)[0]
            return _retval
        except:
            raise OverrunBufferException(o, len(class_var._buf))
    def unpack_dword_be(offset):
        o = class_var._offset + offset
        try:
            _retval = struct.unpack_from('>I', class_var._buf, o)[0]
            return _retval
        except:
            raise OverrunBufferException(o, len(class_var._buf))
    def unpack_int32(offset):
        o = class_var._offset + offset
        try:
            _retval = struct.unpack_from('<i', class_var._buf, o)[0]
            return _retval
        except:
            raise OverrunBufferException(o, len(class_var._buf))
    def unpack_qword(offset):
        o = class_var._offset + offset
        try:
            _retval = struct.unpack_from('<Q', class_var._buf, o)[0]
            return _retval
        except:
            raise OverrunBufferException(o, len(class_var._buf))
    def unpack_binary(offset, length):
        if not length:
            _retval = ''.encode('ascii')
            return _retval
        o = class_var._offset + offset
        try:
            _retval = struct.unpack_from('<{}s'.format(length), class_var._buf, o)[0]
            return _retval
        except:
            raise OverrunBufferException(o, len(class_var._buf))
    def unpack_string(offset, length):
        _retval = class_var.unpack_binary(offset, length).decode('ascii')
        return _retval
    def unpack_wstring(offset, length):
        start = class_var._offset + offset
        end = class_var._offset + offset + 2 * length
        try:
            _retval = bytes(class_var._buf[start:end]).decode('utf16')
            return _retval
        except AttributeError:
            _retval = bytes(class_var._buf[start:end]).decode('utf16')
            return _retval
    def unpack_filetime(offset):
        return parse_filetime(class_var.unpack_qword(offset))
    def unpack_guid(offset):
        o = class_var._offset + offset
        _bin = None
        try:
            _bin = bytes(class_var._buf[o:o + 16])
        except:
            raise OverrunBufferException(o, len(class_var._buf))
        h = []
        for i in range(len(_bin)):
            h.append(_bin[i])
        _retval = '{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}'.format(h[3], h[2], h[1], h[0], h[5], h[4], h[7], h[6], h[8], h[9], h[10], h[11], h[12], h[13], h[14], h[15])
        return _retval
    def offset():
        return class_var._offset
    class_var = SkelClass('Block')
    class_var.__init__ = __init__5
    class_var.declare_field = declare_field
    class_var.current_field_offset = current_field_offset
    class_var.unpack_byte = unpack_byte
    class_var.unpack_word = unpack_word
    class_var.unpack_word_be = unpack_word_be
    class_var.unpack_dword = unpack_dword
    class_var.unpack_dword_be = unpack_dword_be
    class_var.unpack_int32 = unpack_int32
    class_var.unpack_qword = unpack_qword
    class_var.unpack_binary = unpack_binary
    class_var.unpack_string = unpack_string
    class_var.unpack_wstring = unpack_wstring
    class_var.unpack_filetime = unpack_filetime
    class_var.unpack_guid = unpack_guid
    class_var.offset = offset
    __init__5(pbuf, poffset)
    return class_var
def BXmlNode(pbuf, poffset, pchunk, pparent):
    def __init__6(buf, offset, chunk, parent):
        class_var._chunk = chunk
        class_var._parent = parent
    def _children(max_children, end_tokens):
        ret = []
        ofs = class_var.tag_length()
        gen = user_infinite_counter()
        if max_children:
            gen = list(range(max_children))
        for _ in gen:
            token = class_var.unpack_byte(ofs) & 15
            HandlerNodeClass = NODE_DISPATCH_TABLE[token]
            child = HandlerNodeClass(class_var._buf, class_var.offset() + ofs, class_var._chunk, class_var)
            ret.append(child)
            ofs += child.length()
            if token in end_tokens:
                break
            if child.find_end_of_stream():
                break
        return ret
    def children1():
        _retval = class_var._children(None, [EndOfStreamToken])
        return _retval
    def length1():
        ret = class_var.tag_length()
        for child in class_var.children():
            ret += child.length()
        return ret
    def find_end_of_stream1():
        for child in class_var.children():
            if user_check_type(child, EndOfStreamNode):
                return child
            ret = child.find_end_of_stream()
            if ret:
                return ret
        return None
    class_var = Block(pbuf, poffset)
    class_var._class_name = 'BXmlNode;' + class_var._class_name
    children1 = memoize(children1, class_var)
    length1 = memoize(length1, class_var)
    find_end_of_stream1 = memoize(find_end_of_stream1, class_var)
    class_var.__init__ = __init__6
    class_var._children = _children
    class_var.children = children1
    class_var.length = length1
    class_var.find_end_of_stream = find_end_of_stream1
    __init__6(pbuf, poffset, pchunk, pparent)
    return class_var
def NameStringNode(pbuf, poffset, pchunk, pparent):
    def __init__7(buf, offset, chunk, parent):
        class_var.declare_field('dword', 'next_offset', 0, None)
        class_var.declare_field('word', 'hash', None, None)
        class_var.declare_field('word', 'string_length', None, None)
        class_var.declare_field('wstring', 'string', None, class_var.string_length())
    def tag_length1():
        _retval = class_var.string_length() * 2 + 8
        return _retval
    def length2():
        _retval = class_var.tag_length() + 2
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'NameStringNode;' + class_var._class_name
    class_var.__init__ = __init__7
    class_var.tag_length = tag_length1
    class_var.length = length2
    __init__7(pbuf, poffset, pchunk, pparent)
    return class_var
def TemplateNode(pbuf, poffset, pchunk, pparent):
    def __init__8(buf, offset, chunk, parent):
        class_var.declare_field('dword', 'next_offset', 0, None)
        class_var.declare_field('dword', 'template_id', None, None)
        class_var.declare_field('guid', 'guid', 4, None)
        class_var.declare_field('dword', 'data_length', None, None)
    def tag_length2():
        return 24
    def length3():
        _retval = class_var.tag_length() + class_var.data_length()
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'TemplateNode;' + class_var._class_name
    class_var.__init__ = __init__8
    class_var.tag_length = tag_length2
    class_var.length = length3
    __init__8(pbuf, poffset, pchunk, pparent)
    return class_var
def EndOfStreamNode(pbuf, poffset, pchunk, pparent):
    def __init__9(buf, offset, chunk, parent):
        pass
    def length4():
        return 1
    def children2():
        return []
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'EndOfStreamNode;' + class_var._class_name
    class_var.__init__ = __init__9
    class_var.length = length4
    class_var.children = children2
    __init__9(pbuf, poffset, pchunk, pparent)
    return class_var
def OpenStartElementNode(pbuf, poffset, pchunk, pparent):
    def __init__10(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
        class_var.declare_field('word', 'unknown0', None, None)
        class_var.declare_field('dword', 'size', None, None)
        class_var.declare_field('dword', 'string_offset', None, None)
        class_var._tag_length = 11
        class_var._element_type = 0
        if class_var.flags() & 4:
            class_var._tag_length += 4
        if class_var.string_offset() > class_var.offset() - class_var._chunk._offset:
            new_string = class_var._chunk.add_string(class_var.string_offset(), class_var)
            class_var._tag_length += new_string.length()
    def flags1():
        _retval = class_var.token() >> 4
        return _retval
    def tag_name():
        _retval = class_var._chunk.strings()[class_var.string_offset()].string()
        return _retval
    def tag_length3():
        _retval = class_var._tag_length
        return _retval
    def children3():
        _retval = class_var._children(None, [CloseElementToken, CloseEmptyElementToken])
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'OpenStartElementNode;' + class_var._class_name
    tag_name = memoize(tag_name, class_var)
    children3 = memoize(children3, class_var)
    class_var.__init__ = __init__10
    class_var.flags = flags1
    class_var.tag_name = tag_name
    class_var.tag_length = tag_length3
    class_var.children = children3
    __init__10(pbuf, poffset, pchunk, pparent)
    return class_var
def CloseStartElementNode(pbuf, poffset, pchunk, pparent):
    def __init__11(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
    def length5():
        return 1
    def children4():
        return []
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'CloseStartElementNode;' + class_var._class_name
    class_var.__init__ = __init__11
    class_var.length = length5
    class_var.children = children4
    __init__11(pbuf, poffset, pchunk, pparent)
    return class_var
def CloseEmptyElementNode(pbuf, poffset, pchunk, pparent):
    def __init__12(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
    def length6():
        return 1
    def children5():
        return []
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'CloseEmptyElementNode;' + class_var._class_name
    class_var.__init__ = __init__12
    class_var.length = length6
    class_var.children = children5
    __init__12(pbuf, poffset, pchunk, pparent)
    return class_var
def CloseElementNode(pbuf, poffset, pchunk, pparent):
    def __init__13(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
    def length7():
        return 1
    def children6():
        return []
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'CloseElementNode;' + class_var._class_name
    class_var.__init__ = __init__13
    class_var.length = length7
    class_var.children = children6
    __init__13(pbuf, poffset, pchunk, pparent)
    return class_var
def get_variant_value(buf, offset, chunk, parent, type_, length):
    types = {NULL: NullTypeNode, WSTRING: WstringTypeNode, UNSIGNED_BYTE: UnsignedByteTypeNode, UNSIGNED_WORD: UnsignedWordTypeNode, UNSIGNED_DWORD: UnsignedDwordTypeNode, UNSIGNED_QWORD: UnsignedQwordTypeNode, FLOAT: FloatTypeNode, DOUBLE: DoubleTypeNode, BOOLEAN: BooleanTypeNode, BINARY: BinaryTypeNode, GUID: GuidTypeNode, SIZE: SizeTypeNode, FILETIME: FiletimeTypeNode, SYSTEMTIME: SystemtimeTypeNode, SID: SIDTypeNode, HEX32: Hex32TypeNode, HEX64: Hex64TypeNode, BXML: BXmlTypeNode, WSTRINGARRAY: WstringArrayTypeNode}
    TypeClass = types[type_]
    _retval = TypeClass(buf, offset, chunk, parent, length)
    return _retval
def ValueNode(pbuf, poffset, pchunk, pparent):
    def __init__14(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
        class_var.declare_field('byte', 'type', None, None)
    def tag_length4():
        return 2
    def children7():
        child = get_variant_value(class_var._buf, class_var.offset() + class_var.tag_length(), class_var._chunk, class_var, class_var.type(), None)
        _retval = [child]
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'ValueNode;' + class_var._class_name
    class_var.__init__ = __init__14
    class_var.tag_length = tag_length4
    class_var.children = children7
    __init__14(pbuf, poffset, pchunk, pparent)
    return class_var
def AttributeNode(pbuf, poffset, pchunk, pparent):
    def __init__15(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
        class_var.declare_field('dword', 'string_offset', None, None)
        class_var._name_string_length = 0
        if class_var.string_offset() > class_var.offset() - class_var._chunk._offset:
            new_string = class_var._chunk.add_string(class_var.string_offset(), class_var)
            class_var._name_string_length += new_string.length()
    def attribute_name():
        _retval = class_var._chunk.strings()[class_var.string_offset()]
        return _retval
    def attribute_value():
        _retval = class_var.children()[0]
        return _retval
    def tag_length5():
        _retval = 5 + class_var._name_string_length
        return _retval
    def children8():
        _retval = class_var._children(1, [EndOfStreamToken])
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'AttributeNode;' + class_var._class_name
    children8 = memoize(children8, class_var)
    class_var.__init__ = __init__15
    class_var.attribute_name = attribute_name
    class_var.attribute_value = attribute_value
    class_var.tag_length = tag_length5
    class_var.children = children8
    __init__15(pbuf, poffset, pchunk, pparent)
    return class_var
def CharacterReferenceNode(pbuf, poffset, pchunk, pparent):
    def __init__16(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
        class_var.declare_field('word', 'entity', None, None)
        class_var._tag_length = 3
    def entity_reference1():
        _retval = '&#x%04x;' % class_var.entity()
        return _retval
    def flags2():
        _retval = class_var.token() >> 4
        return _retval
    def tag_length6():
        _retval = class_var._tag_length
        return _retval
    def children9():
        _retval = []
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'CharacterReferenceNode;' + class_var._class_name
    class_var.__init__ = __init__16
    class_var.entity_reference = entity_reference1
    class_var.flags = flags2
    class_var.tag_length = tag_length6
    class_var.children = children9
    __init__16(pbuf, poffset, pchunk, pparent)
    return class_var
def EntityReferenceNode(pbuf, poffset, pchunk, pparent):
    def __init__17(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
        class_var.declare_field('dword', 'string_offset', None, None)
        class_var._tag_length = 5
        if class_var.string_offset() > class_var.offset() - class_var._chunk.offset():
            new_string = class_var._chunk.add_string(class_var.string_offset(), class_var)
            class_var._tag_length += new_string.length()
    def entity_reference2():
        _retval = '&{};'.format(class_var._chunk.strings()[class_var.string_offset()].string())
        return _retval
    def flags3():
        _retval = class_var.token() >> 4
        return _retval
    def tag_length7():
        _retval = class_var._tag_length
        return _retval
    def children10():
        _retval = []
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'EntityReferenceNode;' + class_var._class_name
    class_var.__init__ = __init__17
    class_var.entity_reference = entity_reference2
    class_var.flags = flags3
    class_var.tag_length = tag_length7
    class_var.children = children10
    __init__17(pbuf, poffset, pchunk, pparent)
    return class_var
def TemplateInstanceNode(pbuf, poffset, pchunk, pparent):
    def __init__18(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
        class_var.declare_field('byte', 'unknown0', None, None)
        class_var.declare_field('dword', 'template_id', None, None)
        class_var.declare_field('dword', 'template_offset', None, None)
        class_var._data_length = 0
        if class_var.is_resident_template():
            new_template = class_var._chunk.add_template(class_var.template_offset(), class_var)
            class_var._data_length += new_template.length()
    def is_resident_template():
        _retval = class_var.template_offset() > class_var.offset() - class_var._chunk._offset
        return _retval
    def tag_length8():
        return 10
    def length8():
        _retval = class_var.tag_length() + class_var._data_length
        return _retval
    def template1():
        _retval = class_var._chunk.templates()[class_var.template_offset()]
        return _retval
    def children11():
        _retval = []
        return _retval
    def find_end_of_stream2():
        _retval = class_var.template().find_end_of_stream()
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'TemplateInstanceNode;' + class_var._class_name
    find_end_of_stream2 = memoize(find_end_of_stream2, class_var)
    class_var.__init__ = __init__18
    class_var.is_resident_template = is_resident_template
    class_var.tag_length = tag_length8
    class_var.length = length8
    class_var.template = template1
    class_var.children = children11
    class_var.find_end_of_stream = find_end_of_stream2
    __init__18(pbuf, poffset, pchunk, pparent)
    return class_var
def NormalSubstitutionNode(pbuf, poffset, pchunk, pparent):
    def __init__19(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
        class_var.declare_field('word', 'index', None, None)
        class_var.declare_field('byte', 'type', None, None)
    def tag_length9():
        return 4
    def length9():
        _retval = class_var.tag_length()
        return _retval
    def children12():
        _retval = []
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'NormalSubstitutionNode;' + class_var._class_name
    class_var.__init__ = __init__19
    class_var.tag_length = tag_length9
    class_var.length = length9
    class_var.children = children12
    __init__19(pbuf, poffset, pchunk, pparent)
    return class_var
def ConditionalSubstitutionNode(pbuf, poffset, pchunk, pparent):
    def __init__20(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
        class_var.declare_field('word', 'index', None, None)
        class_var.declare_field('byte', 'type', None, None)
    def tag_length10():
        return 4
    def length10():
        _retval = class_var.tag_length()
        return _retval
    def children13():
        _retval = []
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'ConditionalSubstitutionNode;' + class_var._class_name
    class_var.__init__ = __init__20
    class_var.tag_length = tag_length10
    class_var.length = length10
    class_var.children = children13
    __init__20(pbuf, poffset, pchunk, pparent)
    return class_var
def StreamStartNode(pbuf, poffset, pchunk, pparent):
    def __init__21(buf, offset, chunk, parent):
        class_var.declare_field('byte', 'token', 0, None)
        class_var.declare_field('byte', 'unknown0', None, None)
        class_var.declare_field('word', 'unknown1', None, None)
    def tag_length11():
        return 4
    def length11():
        _retval = class_var.tag_length() + 0
        return _retval
    def children14():
        _retval = []
        return _retval
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'StreamStartNode;' + class_var._class_name
    class_var.__init__ = __init__21
    class_var.tag_length = tag_length11
    class_var.length = length11
    class_var.children = children14
    __init__21(pbuf, poffset, pchunk, pparent)
    return class_var
def RootNode(pbuf, poffset, pchunk, pparent):
    def __init__22(buf, offset, chunk, parent):
        pass
    def tag_length12():
        return 0
    def children15():
        _retval = class_var._children(None, [EndOfStreamToken,])
        return _retval
    def tag_and_children_length():
        children_length = 0
        for child in class_var.children():
            children_length += child.length()
        _retval = class_var.tag_length() + children_length
        return _retval
    def template_instance():
        ofs = class_var.offset()
        if class_var.unpack_byte(0) & 15 == 15:
            ofs += 4
        _retval = TemplateInstanceNode(class_var._buf, ofs, class_var._chunk, class_var)
        return _retval
    def template2():
        instance = class_var.template_instance()
        offset = class_var._chunk.offset() + instance.template_offset()
        node = TemplateNode(class_var._buf, offset, class_var._chunk, instance)
        return node
    def substitutions():
        sub_decl = []
        sub_def = []
        ofs = class_var.tag_and_children_length()
        sub_count = class_var.unpack_dword(ofs)
        ofs += 4
        for i in range(sub_count):
            size = class_var.unpack_word(ofs)
            type_ = class_var.unpack_byte(ofs + 2)
            sub_decl.append((size, type_))
            ofs += 4
        for index in range(len(sub_decl)):
            size = sub_decl[index][0]
            type_ = sub_decl[index][1]
            val = get_variant_value(class_var._buf, class_var.offset() + ofs, class_var._chunk, class_var, type_, size)
            if abs(size - val.length()) > 4:
                raise ParseException('Invalid substitution value size')
            sub_def.append(val)
            ofs += size
        return sub_def
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'RootNode;' + class_var._class_name
    children15 = memoize(children15, class_var)
    substitutions = memoize(substitutions, class_var)
    class_var.__init__ = __init__22
    class_var.tag_length = tag_length12
    class_var.children = children15
    class_var.tag_and_children_length = tag_and_children_length
    class_var.template_instance = template_instance
    class_var.template = template2
    class_var.substitutions = substitutions
    __init__22(pbuf, poffset, pchunk, pparent)
    return class_var
def VariantTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__23(buf, offset, chunk, parent, length):
        class_var._length = length
    def length12():
        _retval = class_var.tag_length()
        return _retval
    def children16():
        return []
    class_var = BXmlNode(pbuf, poffset, pchunk, pparent)
    class_var._class_name = 'VariantTypeNode;' + class_var._class_name
    class_var.__init__ = __init__23
    class_var.length = length12
    class_var.children = children16
    __init__23(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def NullTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__24(buf, offset, chunk, parent, length):
        class_var._offset = offset
        class_var._length = length
    def string1():
        return ''
    def length13():
        _retval = class_var._length or 0
        return _retval
    def children17():
        return []
    class_var = SkelClass('NullTypeNode')
    class_var.__init__ = __init__24
    class_var.string = string1
    class_var.length = length13
    class_var.children = children17
    __init__24(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def WstringTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__25(buf, offset, chunk, parent, length):
        if class_var._length is None:
            class_var.declare_field('word', 'string_length', 0, None)
            class_var.declare_field('wstring', '_string', None, class_var.string_length())
            return
        class_var.declare_field('wstring', '_string', 0, class_var._length // 2)
    def tag_length13():
        if class_var._length is None:
            _retval = 2 + class_var.string_length() * 2
            return _retval
        _retval = class_var._length
        return _retval
    def string2():
        _retval = class_var._string().replace('\x00', '')
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'WstringTypeNode;' + class_var._class_name
    class_var.__init__ = __init__25
    class_var.tag_length = tag_length13
    class_var.string = string2
    __init__25(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def UnsignedByteTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__26(buf, offset, chunk, parent, length):
        class_var.declare_field('byte', 'byte', 0, None)
    def tag_length14():
        return 1
    def string3():
        _retval = str(class_var.byte())
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'UnsignedByteTypeNode;' + class_var._class_name
    class_var.__init__ = __init__26
    class_var.tag_length = tag_length14
    class_var.string = string3
    __init__26(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def UnsignedWordTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__27(buf, offset, chunk, parent, length):
        class_var.declare_field('word', 'word', 0, None)
    def tag_length15():
        return 2
    def string4():
        _retval = str(class_var.word())
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'UnsignedWordTypeNode;' + class_var._class_name
    class_var.__init__ = __init__27
    class_var.tag_length = tag_length15
    class_var.string = string4
    __init__27(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def UnsignedDwordTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__28(buf, offset, chunk, parent, length):
        class_var.declare_field('dword', 'dword', 0, None)
    def tag_length16():
        return 4
    def string5():
        _retval = str(class_var.dword())
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'UnsignedDwordTypeNode;' + class_var._class_name
    class_var.__init__ = __init__28
    class_var.tag_length = tag_length16
    class_var.string = string5
    __init__28(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def UnsignedQwordTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__29(buf, offset, chunk, parent, length):
        class_var.declare_field('qword', 'qword', 0, None)
    def tag_length17():
        return 8
    def string6():
        _retval = str(class_var.qword())
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'UnsignedQwordTypeNode;' + class_var._class_name
    class_var.__init__ = __init__29
    class_var.tag_length = tag_length17
    class_var.string = string6
    __init__29(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def FloatTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__30(buf, offset, chunk, parent, length):
        class_var.declare_field('dword', 'float', 0, None)
    def tag_length18():
        return 4
    def string7():
        _retval = str(class_var.float())
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'FloatTypeNode;' + class_var._class_name
    class_var.__init__ = __init__30
    class_var.tag_length = tag_length18
    class_var.string = string7
    __init__30(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def DoubleTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__31(buf, offset, chunk, parent, length):
        class_var.declare_field('qword', 'double', 0, None)
    def tag_length19():
        return 8
    def string8():
        _retval = str(class_var.double())
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'DoubleTypeNode;' + class_var._class_name
    class_var.__init__ = __init__31
    class_var.tag_length = tag_length19
    class_var.string = string8
    __init__31(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def BooleanTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__32(buf, offset, chunk, parent, length):
        class_var.declare_field('int32', 'int32', 0, None)
    def tag_length20():
        return 4
    def string9():
        if class_var.int32() > 0:
            return 'True'
        return 'False'
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'BooleanTypeNode;' + class_var._class_name
    class_var.__init__ = __init__32
    class_var.tag_length = tag_length20
    class_var.string = string9
    __init__32(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def BinaryTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__33(buf, offset, chunk, parent, length):
        if class_var._length is None:
            class_var.declare_field('dword', 'size', 0, None)
            class_var.declare_field('binary', 'binary', None, class_var.size())
            return
        class_var.declare_field('binary', 'binary', 0, class_var._length)
    def tag_length21():
        if class_var._length is None:
            _retval = 4 + class_var.size()
            return _retval
        _retval = class_var._length
        return _retval
    def string10():
        _retval = base64.b64encode(class_var.binary()).decode('ascii')
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'BinaryTypeNode;' + class_var._class_name
    class_var.__init__ = __init__33
    class_var.tag_length = tag_length21
    class_var.string = string10
    __init__33(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def GuidTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__34(buf, offset, chunk, parent, length):
        class_var.declare_field('guid', 'guid', 0, None)
    def tag_length22():
        return 16
    def string11():
        _retval = '{' + class_var.guid() + '}'
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'GuidTypeNode;' + class_var._class_name
    class_var.__init__ = __init__34
    class_var.tag_length = tag_length22
    class_var.string = string11
    __init__34(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def SizeTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__35(buf, offset, chunk, parent, length):
        if class_var._length == 4:
            class_var.declare_field('dword', 'num', 0, None)
            return
        if class_var._length == 8:
            class_var.declare_field('qword', 'num', 0, None)
            return
        class_var.declare_field('qword', 'num', 0, None)
    def tag_length23():
        if class_var._length is None:
            return 8
        return class_var._length
    def string12():
        _retval = str(class_var.num())
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'SizeTypeNode;' + class_var._class_name
    class_var.__init__ = __init__35
    class_var.tag_length = tag_length23
    class_var.string = string12
    __init__35(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def FiletimeTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__36(buf, offset, chunk, parent, length):
        class_var.declare_field('filetime', 'filetime', 0, None)
    def string13():
        return 'time not supported'
    def tag_length24():
        return 8
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'FiletimeTypeNode;' + class_var._class_name
    class_var.__init__ = __init__36
    class_var.string = string13
    class_var.tag_length = tag_length24
    __init__36(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def SystemtimeTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__37(buf, offset, chunk, parent, length):
        class_var.declare_field('systemtime', 'systemtime', 0, None)
    def tag_length25():
        return 16
    def string14():
        return 'time not supported'
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'SystemtimeTypeNode;' + class_var._class_name
    class_var.__init__ = __init__37
    class_var.tag_length = tag_length25
    class_var.string = string14
    __init__37(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def SIDTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__38(buf, offset, chunk, parent, length):
        class_var.declare_field('byte', 'version', 0, None)
        class_var.declare_field('byte', 'num_elements', None, None)
        class_var.declare_field('dword_be', 'id_high', None, None)
        class_var.declare_field('word_be', 'id_low', None, None)
    def elements():
        ret = []
        _tmp = class_var.num_elements()
        for i in range(_tmp):
            ret.append(class_var.unpack_dword(class_var.current_field_offset() + 4 * i))
        return ret
    def id():
        ret = 'S-{}-{}'.format(class_var.version(), class_var.id_high() << 16 ^ class_var.id_low())
        for elem in class_var.elements():
            ret += '-{}'.format(elem)
        return ret
    def tag_length26():
        _retval = 8 + 4 * class_var.num_elements()
        return _retval
    def string15():
        _retval = class_var.id()
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'SIDTypeNode;' + class_var._class_name
    elements = memoize(elements, class_var)
    id = memoize(id, class_var)
    class_var.__init__ = __init__38
    class_var.elements = elements
    class_var.id = id
    class_var.tag_length = tag_length26
    class_var.string = string15
    __init__38(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def Hex32TypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__39(buf, offset, chunk, parent, length):
        class_var.declare_field('binary', 'hex', 0, 4)
    def tag_length27():
        return 4
    def string16():
        ret = '0x'
        b = class_var.hex()[::-1]
        for i in range(len(b)):
            ret += '{:02x}'.format(b[i])
        return ret
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'Hex32TypeNode;' + class_var._class_name
    class_var.__init__ = __init__39
    class_var.tag_length = tag_length27
    class_var.string = string16
    __init__39(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def Hex64TypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__40(buf, offset, chunk, parent, length):
        class_var.declare_field('binary', 'hex', 0, 8)
    def tag_length28():
        return 8
    def string17():
        ret = '0x'
        b = class_var.hex()[::-1]
        for i in range(len(b)):
            ret += '{:02x}'.format(b[i])
        return ret
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'Hex64TypeNode;' + class_var._class_name
    class_var.__init__ = __init__40
    class_var.tag_length = tag_length28
    class_var.string = string17
    __init__40(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def BXmlTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__41(buf, offset, chunk, parent, length):
        class_var._root = RootNode(buf, offset, chunk, class_var)
    def tag_length29():
        _retval = class_var._length or class_var._root.length()
        return _retval
    def string18():
        return ''
    def root1():
        _retval = class_var._root
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'BXmlTypeNode;' + class_var._class_name
    class_var.__init__ = __init__41
    class_var.tag_length = tag_length29
    class_var.string = string18
    class_var.root = root1
    __init__41(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def WstringArrayTypeNode(pbuf, poffset, pchunk, pparent, plength):
    def __init__42(buf, offset, chunk, parent, length):
        if class_var._length is None:
            class_var.declare_field('word', 'binary_length', 0, None)
            class_var.declare_field('binary', 'binary', None, class_var.binary_length())
            return
        class_var.declare_field('binary', 'binary', 0, class_var._length)
    def tag_length30():
        if class_var._length is None:
            _retval = 2 + class_var.binary_length()
            return _retval
        _retval = class_var._length
        return _retval
    def string19():
        binary = class_var.binary()
        binaryString = binary.decode('utf16')
        acc = []
        while len(binaryString) > 0:
            match = re.search('(?:[^\x00].)+', binaryString)
            if match:
                frag = match.group(0)
                acc.append('<string>')
                acc.append(frag)
                acc.append('</string>\n')
                binaryString = binaryString[len(frag) + 2:]
                if len(binaryString) == 0:
                    break
            frag = re.search('(\x00*)', binaryString).group(0)
            if len(frag) % 2 == 0:
                for i in range(len(frag) // 2):
                    acc.append('<string></string>\n')
            else:
                raise ParseException('Error parsing uneven substring of NULLs')
            binaryString = binaryString[len(frag):]
        _retval = ''.join(acc)
        return _retval
    class_var = VariantTypeNode(pbuf, poffset, pchunk, pparent, plength)
    class_var._class_name = 'WstringArrayTypeNode;' + class_var._class_name
    class_var.__init__ = __init__42
    class_var.tag_length = tag_length30
    class_var.string = string19
    __init__42(pbuf, poffset, pchunk, pparent, plength)
    return class_var
def UnexpectedElementException(param_0):
    def __init__43(msg):
        pass
    class_var = Exception(param_0)
    class_var._class_name = 'UnexpectedElementException;' + class_var._class_name
    class_var.__init__ = __init__43
    __init__43(param_0)
    return class_var
def escape_value(s):
    esc = s.replace('&', '&amp;')
    esc = esc.replace('<', '&lt;')
    esc = esc.replace('>', '&gt;')
    esc = esc.replace('"', '&quot;')
    esc = esc.replace("'", '&#x27;')
    esc = re.sub(r'[\u0080-\uFFFF]', lambda m: f'&#{ord(m.group(0))};', esc)
    esc = RESTRICTED_CHARS.sub('', esc)
    return esc
def validate_name(s):
    if not NAME_PATTERN.match(s):
        raise Exception('invalid xml name: %s' % s)
    return s
def render_root_node_with_subs(root_node, subs):
    def rec(node, acc):
        if user_check_type(node, EndOfStreamNode):
            pass
        elif user_check_type(node, OpenStartElementNode):
            acc.append('<')
            acc.append(node.tag_name())
            for child in node.children():
                if user_check_type(child, AttributeNode):
                    acc.append(' ')
                    acc.append(validate_name(child.attribute_name().string()))
                    acc.append('="')
                    rec(child.attribute_value(), acc)
                    acc.append('"')
            acc.append('>')
            for child in node.children():
                rec(child, acc)
            acc.append('</')
            acc.append(validate_name(node.tag_name()))
            acc.append('>\n')
        elif user_check_type(node, CloseStartElementNode):
            pass
        elif user_check_type(node, CloseEmptyElementNode):
            pass
        elif user_check_type(node, CloseElementNode):
            pass
        elif user_check_type(node, ValueNode):
            acc.append(escape_value(node.children()[0].string()))
        elif user_check_type(node, AttributeNode):
            pass
        elif user_check_type(node, EntityReferenceNode):
            acc.append(escape_value(node.entity_reference()))
        elif user_check_type(node, TemplateInstanceNode):
            raise UnexpectedElementException('TemplateInstanceNode')
        elif user_check_type(node, NormalSubstitutionNode):
            sub = subs[node.index()]
            if user_check_type(sub, BXmlTypeNode):
                sub = render_root_node(sub.root())
            else:
                sub = escape_value(sub.string())
            acc.append(sub)
        elif user_check_type(node, ConditionalSubstitutionNode):
            sub = subs[node.index()]
            if user_check_type(sub, BXmlTypeNode):
                sub = render_root_node(sub.root())
            else:
                sub = escape_value(sub.string())
            acc.append(sub)
        elif user_check_type(node, StreamStartNode):
            pass
    acc = []
    for child in root_node.template().children():
        rec(child, acc)
    _retval = ''.join(acc)
    return _retval
def render_root_node(root_node):
    subs = []
    for sub in root_node.substitutions():
        if user_check_type(sub, "string"):
            raise Exception('string sub?')
        if sub is None:
            raise Exception('null sub?')
        subs.append(sub)
    _retval = render_root_node_with_subs(root_node, subs)
    return _retval
def evtx_record_xml_view(record, cache):
    _retval = render_root_node(record.root())
    return _retval
def InvalidRecordException():
    def __init__44():
        pass
    class_var = ParseException('Invalid record structure')
    class_var._class_name = 'InvalidRecordException;' + class_var._class_name
    class_var.__init__ = __init__44
    __init__44()
    return class_var
def FileHeader(pbuf, poffset):
    def __init__45(buf, offset):
        class_var.declare_field('string', 'magic', 0, 8)
        class_var.declare_field('qword', 'oldest_chunk', None, None)
        class_var.declare_field('qword', 'current_chunk_number', None, None)
        class_var.declare_field('qword', 'next_record_number', None, None)
        class_var.declare_field('dword', 'header_size', None, None)
        class_var.declare_field('word', 'minor_version', None, None)
        class_var.declare_field('word', 'major_version', None, None)
        class_var.declare_field('word', 'header_chunk_size', None, None)
        class_var.declare_field('word', 'chunk_count', None, None)
        class_var.declare_field('binary', 'unused1', None, 76)
        class_var.declare_field('dword', 'flags', None, None)
        class_var.declare_field('dword', 'checksum', None, None)
    def check_magic1():
        _retval = class_var.magic() == 'ElfFile\x00'
        return _retval
    def calculate_checksum():
        buffer = class_var.unpack_binary(0, 120)
        _retval = crc32(buffer) & 4294967295
        return _retval
    def verify1():
        _retval = class_var.check_magic() and class_var.major_version() == 3 and (class_var.minor_version() == 1) and (class_var.header_chunk_size() == 4096) and (class_var.checksum() == class_var.calculate_checksum())
        return _retval
    def is_dirty():
        _retval = class_var.flags() & 1 == 1
        return _retval
    def is_full():
        _retval = class_var.flags() & 2 == 2
        return _retval
    def first_chunk():
        ofs = class_var._offset + class_var.header_chunk_size()
        _retval = ChunkHeader(class_var._buf, ofs)
        return _retval
    def current_chunk():
        ofs = class_var._offset + class_var.header_chunk_size()
        ofs += class_var.current_chunk_number() * 65536
        _retval = ChunkHeader(class_var._buf, ofs)
        return _retval
    def chunks(include_inactive):
        chunk_count = 1000000
        if not include_inactive:
            chunk_count = class_var.chunk_count()
        i = 0
        ofs = class_var._offset + class_var.header_chunk_size()
        _return_chunks = []
        while ofs + 65536 <= len(class_var._buf) and i < chunk_count:
            _yield_value = ChunkHeader(class_var._buf, ofs)
            _return_chunks.append(_yield_value)
            ofs += 65536
            i += 1
        return _return_chunks
    def get_record(record_num):
        for chunk in class_var.chunks():
            first_record = chunk.log_first_record_number()
            last_record = chunk.log_last_record_number()
            if not first_record <= record_num and record_num <= last_record:
                continue
            for record in chunk.records():
                if record.record_num() == record_num:
                    return record
        return None
    class_var = Block(pbuf, poffset)
    class_var._class_name = 'FileHeader;' + class_var._class_name
    class_var.__init__ = __init__45
    class_var.check_magic = check_magic1
    class_var.calculate_checksum = calculate_checksum
    class_var.verify = verify1
    class_var.is_dirty = is_dirty
    class_var.is_full = is_full
    class_var.first_chunk = first_chunk
    class_var.current_chunk = current_chunk
    class_var.chunks = chunks
    class_var.get_record = get_record
    __init__45(pbuf, poffset)
    return class_var
def ChunkHeader(pbuf, poffset):
    def __init__46(buf, offset):
        class_var._strings = None
        class_var._templates = None
        class_var.declare_field('string', 'magic', 0, 8)
        class_var.declare_field('qword', 'file_first_record_number', None, None)
        class_var.declare_field('qword', 'file_last_record_number', None, None)
        class_var.declare_field('qword', 'log_first_record_number', None, None)
        class_var.declare_field('qword', 'log_last_record_number', None, None)
        class_var.declare_field('dword', 'header_size', None, None)
        class_var.declare_field('dword', 'last_record_offset', None, None)
        class_var.declare_field('dword', 'next_record_offset', None, None)
        class_var.declare_field('dword', 'data_checksum', None, None)
        class_var.declare_field('binary', 'unused', None, 68)
        class_var.declare_field('dword', 'header_checksum', None, None)
    def check_magic2():
        _retval = class_var.magic() == 'ElfChnk\x00'
        return _retval
    def calculate_header_checksum():
        data = class_var.unpack_binary(0, 120) + class_var.unpack_binary(128, 384)
        _retval = crc32(data) & 4294967295
        return _retval
    def calculate_data_checksum():
        data = class_var.unpack_binary(512, class_var.next_record_offset() - 512)
        _retval = crc32(data) & 4294967295
        return _retval
    def verify2():
        _retval = class_var.check_magic() and class_var.calculate_header_checksum() == class_var.header_checksum() and (class_var.calculate_data_checksum() == class_var.data_checksum())
        return _retval
    def _load_strings():
        if class_var._strings is None:
            class_var._strings = {}
        for i in range(64):
            ofs = class_var.unpack_dword(128 + i * 4)
            while ofs > 0:
                string_node = class_var.add_string(ofs, None)
                ofs = string_node.next_offset()
    def strings():
        if not class_var._strings:
            class_var._load_strings()
        _retval = class_var._strings
        return _retval
    def add_string(offset, parent):
        if class_var._strings is None:
            class_var._load_strings()
        string_node = NameStringNode(class_var._buf, class_var._offset + offset, class_var, parent or class_var)
        class_var._strings[offset] = string_node
        return string_node
    def _load_templates():
        if class_var._templates is None:
            class_var._templates = {}
        for i in range(32):
            ofs = class_var.unpack_dword(384 + i * 4)
            while ofs > 0:
                token = class_var.unpack_byte(ofs - 10)
                pointer = class_var.unpack_dword(ofs - 4)
                if token != 12 or pointer != ofs:
                    ofs = 0
                    continue
                template = class_var.add_template(ofs, None)
                ofs = template.next_offset()
    def add_template(offset, parent):
        if class_var._templates is None:
            class_var._load_templates()
        node = TemplateNode(class_var._buf, class_var._offset + offset, class_var, parent or class_var)
        class_var._templates[offset] = node
        return node
    def templates():
        if not class_var._templates:
            class_var._load_templates()
        _retval = class_var._templates
        return _retval
    def first_record():
        _retval = Record(class_var._buf, class_var._offset + 512, class_var)
        return _retval
    def records():
        result = []
        try:
            record = class_var.first_record()
        except InvalidRecordException:
            return result
        while record._offset < class_var._offset + class_var.next_record_offset() and record.length() > 0:
            result.append(record)
            try:
                record = Record(class_var._buf, record._offset + record.length(), class_var)
            except InvalidRecordException:
                return result
        return result
    class_var = Block(pbuf, poffset)
    class_var._class_name = 'ChunkHeader;' + class_var._class_name
    class_var.__init__ = __init__46
    class_var.check_magic = check_magic2
    class_var.calculate_header_checksum = calculate_header_checksum
    class_var.calculate_data_checksum = calculate_data_checksum
    class_var.verify = verify2
    class_var._load_strings = _load_strings
    class_var.strings = strings
    class_var.add_string = add_string
    class_var._load_templates = _load_templates
    class_var.add_template = add_template
    class_var.templates = templates
    class_var.first_record = first_record
    class_var.records = records
    __init__46(pbuf, poffset)
    return class_var
def Record(pbuf, poffset, pchunk):
    def __init__47(buf, offset, chunk):
        class_var._chunk = chunk
        class_var.declare_field('dword', 'magic', 0, None)
        class_var.declare_field('dword', 'size', None, None)
        class_var.declare_field('qword', 'record_num', None, None)
        class_var.declare_field('filetime', 'timestamp', None, None)
        if class_var.size() > 65536:
            return None
        class_var.declare_field('dword', 'size2', class_var.size() - 4, None)
    def root2():
        _retval = RootNode(class_var._buf, class_var._offset + 24, class_var._chunk, class_var)
        return _retval
    def length14():
        _retval = class_var.size()
        return _retval
    def verify3():
        _retval = class_var.size() == class_var.size2()
        return _retval
    def data():
        _retval = class_var._buf[class_var.offset():class_var.offset() + class_var.size()]
        return _retval
    def xml():
        _retval = evtx_record_xml_view(class_var, None)
        return _retval
    class_var = Block(pbuf, poffset)
    class_var._class_name = 'Record;' + class_var._class_name
    class_var.__init__ = __init__47
    class_var.root = root2
    class_var.length = length14
    class_var.verify = verify3
    class_var.data = data
    class_var.xml = xml
    __init__47(pbuf, poffset, pchunk)
    return class_var
def test_chunks_sys(input_str):
    fh = FileHeader(input_str, 0)
    chunks = list(fh.chunks(False))
    if len(chunks) != 1:
        raise Exception('Assertion failed')
    chunk = chunks[0]
    if not chunk.check_magic():
        raise Exception('Assertion failed')
    if chunk.magic() != 'ElfChnk\x00':
        raise Exception('Assertion failed')
    if chunk.calculate_header_checksum() != chunk.header_checksum():
        raise Exception('Assertion failed')
    if chunk.calculate_data_checksum() != chunk.data_checksum():
        raise Exception('Assertion failed')
    if chunk.file_first_record_number() != expected_output1['start_file']:
        raise Exception('Assertion failed')
    if chunk.file_last_record_number() != expected_output1['end_file']:
        raise Exception('Assertion failed')
    if chunk.log_first_record_number() != expected_output1['start_log']:
        raise Exception('Assertion failed')
    if chunk.log_last_record_number() != expected_output1['end_log']:
        raise Exception('Assertion failed')
def test_chunks_sec(input_str):
    fh = FileHeader(input_str, 0)
    chunks = list(fh.chunks(False))
    if len(chunks) != 1:
        raise Exception('Assertion failed')
    chunk = chunks[0]
    if not chunk.check_magic():
        raise Exception('Assertion failed')
    if chunk.magic() != 'ElfChnk\x00':
        raise Exception('Assertion failed')
    if chunk.calculate_header_checksum() != chunk.header_checksum():
        raise Exception('Assertion failed')
    if chunk.calculate_data_checksum() != chunk.data_checksum():
        raise Exception('Assertion failed')
    if chunk.file_first_record_number() != expected_output2['start_file']:
        raise Exception('Assertion failed')
    if chunk.file_last_record_number() != expected_output2['end_file']:
        raise Exception('Assertion failed')
    if chunk.log_first_record_number() != expected_output2['start_log']:
        raise Exception('Assertion failed')
    if chunk.log_last_record_number() != expected_output2['end_log']:
        raise Exception('Assertion failed')
def test_file_header_sys(input_str):
    fh = FileHeader(input_str, 0)
    if fh.magic() != 'ElfFile\x00':
        raise Exception('Assertion failed')
    if fh.major_version() != 3:
        raise Exception('Assertion failed')
    if fh.minor_version() != 1:
        raise Exception('Assertion failed')
    if fh.flags() != 1:
        raise Exception('Assertion failed')
    if not fh.is_dirty():
        raise Exception('Assertion failed')
    if fh.is_full():
        raise Exception('Assertion failed')
    if fh.current_chunk_number() != 0:
        raise Exception('Assertion failed')
    if fh.chunk_count() != 1:
        raise Exception('Assertion failed')
    if fh.oldest_chunk() != 0:
        raise Exception('Assertion failed')
    if fh.next_record_number() != 13528:
        raise Exception('Assertion failed')
    if fh.checksum() != 2761825960:
        raise Exception('Assertion failed')
    if fh.calculate_checksum() != fh.checksum():
        raise Exception('Assertion failed')
def test_file_header_sec(input_str):
    fh = FileHeader(input_str, 0)
    if fh.magic() != 'ElfFile\x00':
        raise Exception('Assertion failed')
    if fh.major_version() != 3:
        raise Exception('Assertion failed')
    if fh.minor_version() != 1:
        raise Exception('Assertion failed')
    if fh.flags() != 1:
        raise Exception('Assertion failed')
    if not fh.is_dirty():
        raise Exception('Assertion failed')
    if fh.is_full():
        raise Exception('Assertion failed')
    if fh.current_chunk_number() != 0:
        raise Exception('Assertion failed')
    if fh.chunk_count() != 1:
        raise Exception('Assertion failed')
    if fh.oldest_chunk() != 0:
        raise Exception('Assertion failed')
    if fh.next_record_number() != 2226:
        raise Exception('Assertion failed')
    if fh.checksum() != 441071771:
        raise Exception('Assertion failed')
    if fh.calculate_checksum() != fh.checksum():
        raise Exception('Assertion failed')
def _extract_structure(node):
    name = node._class_name.split(';')[0]
    value = None
    if user_check_type(node, BXmlTypeNode):
        value = None
    elif user_check_type(node, VariantTypeNode):
        value = node.string()
    elif user_check_type(node, OpenStartElementNode):
        value = node.tag_name()
    elif user_check_type(node, AttributeNode):
        value = node.attribute_name().string()
    else:
        value = None
    children = []
    if user_check_type(node, BXmlTypeNode):
        children.append(_extract_structure(node._root))
    elif user_check_type(node, TemplateInstanceNode) and node.is_resident_template():
        children.append(_extract_structure(node.template()))
    children.extend(list(map(_extract_structure, node.children())))
    if user_check_type(node, RootNode):
        substitutions = list(map(_extract_structure, node.substitutions()))
        children.append(['Substitutions', None, substitutions])
    if len(children) > 0:
        _retval = [name, value, children]
        return _retval
    elif value is not None:
        _retval = [name, value]
        return _retval
    else:
        _retval = [name]
        return _retval
def test_parse_record_sys(input_str):
    fh = FileHeader(input_str, 0)
    chunk = fh.chunks(False)[0]
    record = chunk.records()[0]
    expected_output3 = _get_expected_output3()
    if json.dumps(_extract_structure(record.root())) != json.dumps(expected_output3):
        raise Exception('Assertion failed')
def test_parse_records_sys(input_str):
    fh = FileHeader(input_str, 0)
    chunks = list(fh.chunks(False))
    if len(chunks) != 1:
        raise Exception('Assertion failed')
    chunk = chunks[0]
    for record in chunk.records():
        if record.magic() != 10794:
            raise Exception('Assertion failed')
def test_parse_records_sec(input_str):
    fh = FileHeader(input_str, 0)
    chunks = list(fh.chunks(False))
    if len(chunks) != 1:
        raise Exception('Assertion failed')
    chunk = chunks[0]
    for record in chunk.records():
        if record.magic() != 10794:
            raise Exception('Assertion failed')
def test_render_record_sys(input_str):
    fh = FileHeader(input_str, 0)
    chunk = fh.chunks(False)[0]
    record = chunk.records()[0]
    xml = record.xml()
    expected_output4 = _get_expected_output_4()
    if json.dumps(xml) != json.dumps(expected_output4):
        raise Exception('Assertion failed')
def test_render_records_sys(input_str):
    fh = FileHeader(input_str, 0)
    chunks = list(fh.chunks(False))
    if len(chunks) != 1:
        raise Exception('Assertion failed')
    chunk = chunks[0]
    records = chunk.records()
    include_only = [86, 106, 132, 133, 135]
    for idx in range(len(records)):
        if idx not in include_only:
            continue
        record = records[idx]
        if record.xml() is None:
            raise Exception('Assertion failed')
def test_render_records_sec(input_str):
    fh = FileHeader(input_str, 0)
    chunks = list(fh.chunks(False))
    if len(chunks) != 1:
        raise Exception('Assertion failed')
    chunk = chunks[0]
    records = chunk.records()
    include_only = [0]
    for idx in range(len(records)):
        if idx not in include_only:
            continue
        record = records[idx]
        if record.xml() is None:
            raise Exception('Assertion failed')
def test_init():
    escape_value('&&<<>>""\'\'\u0080\uFFFF')
    obj = SkelClass('dummy')
    fn = lambda x: x
    fn = memoize(fn, obj)
    fn(1)
    inp = _get_test_init_input('block.evtx')
    obj = Block(inp, 0)
    obj.current_field_offset()
    obj.offset()
    obj.unpack_byte(0)
    obj.unpack_word(0)
    obj.unpack_word_be(0)
    obj.unpack_dword(0)
    obj.unpack_dword_be(0)
    obj.unpack_int32(0)
    obj.unpack_qword(0)
    obj.unpack_binary(0, None)
    obj.unpack_binary(0, 1)
    obj.unpack_string(0, 1)
    obj.unpack_wstring(0, 1)
    obj.unpack_guid(0)
    obj = NullTypeNode(inp, 0, None, None, None)
    obj.string()
    obj.length()
    obj.children()
    inp = _get_test_init_input('name-string-node.evtx')
    obj = NameStringNode(inp, 0, None, None)
    obj.tag_length()
    obj.length()
    inp = _get_test_init_input('template-node.evtx')
    obj = TemplateNode(inp, 0, None, None)
    obj.tag_length()
    obj.length()
    obj = EndOfStreamNode(inp, 0, None, None)
    obj.length()
    obj.children()
    obj = WstringTypeNode(inp, 0, None, None, None)
    obj.string()
    obj.tag_length()
    obj = WstringTypeNode(inp, 0, None, None, 0)
    obj.tag_length()
    obj.length()
    obj.children()
    obj = UnsignedByteTypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj.string()
    obj = UnsignedWordTypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj.string()
    obj = UnsignedDwordTypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj.string()
    obj = UnsignedQwordTypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj.string()
    inp = _get_test_init_input('boolean-type-node.evtx')
    obj = BooleanTypeNode(inp, 4, None, None, None)
    obj.string()
    obj = BooleanTypeNode(inp, 0, None, None, None)
    obj.string()
    obj.tag_length()
    inp = _get_test_init_input('binary-type-node.evtx')
    obj = BinaryTypeNode(inp, 0, None, None, None)
    obj.string()
    obj.tag_length()
    obj = BinaryTypeNode(inp, 0, None, None, 0)
    obj.tag_length()
    inp = _get_test_init_input('block.evtx')
    obj = GuidTypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj.string()
    obj = FiletimeTypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj.string()
    inp = _get_test_init_input('sid-type-node.evtx')
    obj = SIDTypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj.elements()
    obj.id()
    obj.string()
    inp = _get_test_init_input('block.evtx')
    obj = Hex32TypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj.string()
    obj = Hex64TypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj.string()
    inp = _get_test_init_input('wstring-array-type-node-1.evtx')
    obj = WstringArrayTypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj = WstringArrayTypeNode(inp, 0, None, None, 0)
    obj.tag_length()
    obj = WstringArrayTypeNode(inp, 0, None, None, None)
    obj.string()
    inp = _get_test_init_input('wstring-array-type-node-2.evtx')
    obj = WstringArrayTypeNode(inp, 0, None, None, None)
    obj.string()
    inp = _get_test_init_input('block.evtx')
    obj = CloseStartElementNode(inp, 0, None, None)
    obj.length()
    obj.children()
    obj = CloseEmptyElementNode(inp, 0, None, None)
    obj.length()
    obj.children()
    obj = CloseElementNode(inp, 0, None, None)
    obj.length()
    obj.children()
    get_variant_value(inp, 0, None, None, 0x00, None)
    obj = ValueNode(inp, 0, None, None)
    obj.tag_length()
    obj.children()
    obj = CharacterReferenceNode(inp, 0, None, None)
    obj.entity_reference()
    obj.flags()
    obj.tag_length()
    obj.children()
    obj = NormalSubstitutionNode(inp, 0, None, None)
    obj.tag_length()
    obj.length()
    obj.children()
    obj = ConditionalSubstitutionNode(inp, 0, None, None)
    obj.tag_length()
    obj.length()
    obj.children()
    obj = StreamStartNode(inp, 0, None, None)
    obj.tag_length()
    obj.length()
    obj.children()
    inp = _get_test_init_input('record-1.evtx')
    obj = Record(inp, 0, None)
    inp = _get_test_init_input('record-2.evtx')
    obj = Record(inp, 0, None)
    obj.length()
    obj.data()
    obj.root()
    inp = _get_test_init_input('empty.evtx')
    obj = ChunkHeader(inp, 0)
    obj.check_magic()
    obj.calculate_header_checksum()
    obj.add_string(0, None)
    obj = ChunkHeader(inp, 0)
    obj.strings()
    obj.first_record()
    inp = _get_test_init_input('template-instance-node.evtx')
    obj2 = TemplateInstanceNode(inp, 0, obj, None)
    obj2.tag_length()
    obj2.length()
    obj2.children()
    inp = _get_test_init_input('empty.evtx')
    obj = RootNode(inp, 0, None, None)
    obj.tag_length()
    obj._children(1, [0x00])
    obj.children()
    obj.length()
    obj.find_end_of_stream()
    obj = BXmlTypeNode(inp, 0, None, None, None)
    obj.tag_length()
    obj.string()
    obj.root()
def test():
    test_init()
    sys_bstr = get_input('case1')
    sec_bstr = get_input('case2')
    test_chunks_sys(sys_bstr)
    test_chunks_sec(sec_bstr)
    test_file_header_sys(sys_bstr)
    test_file_header_sec(sec_bstr)
    test_parse_record_sys(sys_bstr)
    test_parse_records_sys(sys_bstr)
    test_parse_records_sec(sec_bstr)
    test_render_record_sys(sys_bstr)
    test_render_records_sys(sys_bstr)
    test_render_records_sec(sec_bstr)

NODE_DISPATCH_TABLE = [EndOfStreamNode, OpenStartElementNode, CloseStartElementNode, CloseEmptyElementNode, CloseElementNode, ValueNode, AttributeNode, None, CharacterReferenceNode, EntityReferenceNode, None, None, TemplateInstanceNode, NormalSubstitutionNode, ConditionalSubstitutionNode, StreamStartNode]

test()
