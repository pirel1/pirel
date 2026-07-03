function SkelClass(name) {
    var Clz = function() {
        var _class_var = {};
        _class_var._class_name = name;
        return _class_var;
    };
    return Clz;
}




function assert_iter_equal(iter1, iter2) {
    var iter1 = Array.from(iter1);
    if (iter1.length !== iter2.length) {
        throw new Error('Assertion failed');
    }
    for (var i = 0; i < iter1.length; i++) {
        var a = iter1[i];
        var b = iter2[i];
        if (a !== b) {
            throw new Error('Assertion failed');
        }
    }
}
function RedBlackTree(param_0, param_1, param_2, param_3, param_4) {
    function __init__(label, color, parent, left, right) {
        class_var.label = label;
        class_var.parent = parent;
        class_var.left = left;
        class_var.right = right;
        class_var.color = color;
    }
    function rotate_left() {
        var parent = class_var.parent;
        var right = class_var.right;
        if (right === null) {
            return class_var;
        }
        class_var.right = right.left;
        if (class_var.right) {
            class_var.right.parent = class_var;
        }
        class_var.parent = right;
        right.left = class_var;
        if (parent !== null) {
            if (parent.left.__eq__(class_var)) {
                parent.left = right;
            } else {
                parent.right = right;
            }
        }
        right.parent = parent;
        return right;
    }
    function rotate_right() {
        if (class_var.left === null) {
            return class_var;
        }
        var parent = class_var.parent;
        var left = class_var.left;
        class_var.left = left.right;
        if (class_var.left) {
            class_var.left.parent = class_var;
        }
        class_var.parent = left;
        left.right = class_var;
        if (parent !== null) {
            if (parent.right === class_var) {
                parent.right = left;
            } else {
                parent.left = left;
            }
        }
        left.parent = parent;
        return left;
    }
    function insert(label) {
        if (class_var.label === null) {
            class_var.label = label;
            return class_var;
        }
        if (class_var.label === label) {
            return class_var;
        } else if (class_var.label > label) {
            if (class_var.left) {
                class_var.left.insert(label);
            } else {
                class_var.left = new RedBlackTree(label, 1, class_var, null, null);
                class_var.left._insert_repair();
            }
        } else if (class_var.right) {
            class_var.right.insert(label);
        } else {
            class_var.right = new RedBlackTree(label, 1, class_var, null, null);
            class_var.right._insert_repair();
        }
        return class_var.parent || class_var;
    }
    function _insert_repair() {
        if (class_var.parent === null) {
            class_var.color = 0;
        } else if (get_color(class_var.parent) === 0) {
            class_var.color = 1;
        } else {
            var uncle = class_var.parent.sibling();
            if (get_color(uncle) === 0) {
                var _cv_isleft = class_var.is_left();
                var _cv_isright = class_var.is_right();
                var _cvp_isleft = class_var.parent.is_left();
                var _cvp_isright = class_var.parent.is_right();
                if (_cv_isleft && _cvp_isright) {
                    class_var.parent.rotate_right();
                    if (class_var.right) {
                        class_var.right._insert_repair();
                    }
                } else if (_cv_isright && _cvp_isleft) {
                    class_var.parent.rotate_left();
                    if (class_var.left) {
                        class_var.left._insert_repair();
                    }
                } else if (_cv_isleft) {
                    if (class_var.grandparent()) {
                        class_var.grandparent().rotate_right();
                        class_var.parent.color = 0;
                    }
                    if (class_var.parent.right) {
                        class_var.parent.right.color = 1;
                    }
                } else {
                    if (class_var.grandparent()) {
                        class_var.grandparent().rotate_left();
                        class_var.parent.color = 0;
                    }
                    if (class_var.parent.left) {
                        class_var.parent.left.color = 1;
                    }
                }
            } else {
                class_var.parent.color = 0;
                if (uncle && class_var.grandparent()) {
                    uncle.color = 0;
                    class_var.grandparent().color = 1;
                    class_var.grandparent()._insert_repair();
                }
            }
        }
    }
    function remove(label) {
        if (class_var.label === label) {
            if (class_var.left && class_var.right) {
                var value = class_var.left.get_max();
                if (value !== null) {
                    class_var.label = value;
                    class_var.left.remove(value);
                }
            } else {
                var child = class_var.left || class_var.right;
                if (class_var.color === 1) {
                    if (class_var.parent) {
                        if (class_var.is_left()) {
                            class_var.parent.left = null;
                        } else {
                            class_var.parent.right = null;
                        }
                    }
                } else if (child === null) {
                    if (class_var.parent === null) {
                        return new RedBlackTree(null);
                    } else {
                        class_var._remove_repair();
                        if (class_var.is_left()) {
                            class_var.parent.left = null;
                        } else {
                            class_var.parent.right = null;
                        }
                        class_var.parent = null;
                    }
                } else {
                    class_var.label = child.label;
                    class_var.left = child.left;
                    class_var.right = child.right;
                    if (class_var.left) {
                        class_var.left.parent = class_var;
                    }
                    if (class_var.right) {
                        class_var.right.parent = class_var;
                    }
                }
            }
        } else if (class_var.label !== null && class_var.label > label) {
            if (class_var.left) {
                class_var.left.remove(label);
            }
        } else if (class_var.right) {
            class_var.right.remove(label);
        }
        return class_var.parent || class_var;
    }
    function _remove_repair() {
        if (class_var.parent === null) {
            return;
        }
        if (class_var.sibling() === null) {
            return;
        }
        if (class_var.parent.sibling() === null) {
            return;
        }
        if (class_var.grandparent() === null) {
            return;
        }
        var _cv_sib = class_var.sibling();
        if (get_color(_cv_sib) === 1) {
            _cv_sib.color = 0;
            class_var.parent.color = 1;
            if (class_var.is_left()) {
                class_var.parent.rotate_left();
            } else {
                class_var.parent.rotate_right();
            }
        }
        if (get_color(class_var.parent) === 0) {
            var _cv_sib = class_var.sibling();
            if (get_color(_cv_sib) === 0) {
                if (get_color(_cv_sib.left) === 0) {
                    if (get_color(_cv_sib.right) === 0) {
                        _cv_sib.color = 1;
                        class_var.parent._remove_repair();
                        return;
                    }
                }
            }
        }
        if (get_color(class_var.parent) === 1) {
            var _cv_sib = class_var.sibling();
            if (get_color(_cv_sib) === 0) {
                if (get_color(_cv_sib.left) === 0) {
                    if (get_color(_cv_sib.right) === 0) {
                        _cv_sib.color = 1;
                        class_var.parent.color = 0;
                        return;
                    }
                }
            }
        }
        if (class_var.is_left()) {
            var _cv_sib = class_var.sibling();
            if (get_color(_cv_sib) === 0) {
                if (get_color(_cv_sib.right) === 0) {
                    if (get_color(_cv_sib.left) === 1) {
                        _cv_sib.rotate_right();
                        var _cv_sib2 = class_var.sibling();
                        _cv_sib2.color = 0;
                        if (_cv_sib2.right) {
                            _cv_sib2.right.color = 1;
                        }
                    }
                }
            }
        }
        if (class_var.is_right()) {
            var _cv_sib = class_var.sibling();
            if (get_color(_cv_sib) === 0) {
                if (get_color(_cv_sib.right) === 1) {
                    if (get_color(_cv_sib.left) === 0) {
                        _cv_sib.rotate_left();
                        var _cv_sib2 = class_var.sibling();
                        _cv_sib2.color = 0;
                        if (_cv_sib2.left) {
                            _cv_sib2.left.color = 1;
                        }
                    }
                }
            }
        }
        if (class_var.is_left()) {
            var _cv_sib = class_var.sibling();
            if (get_color(_cv_sib) === 0) {
                if (get_color(_cv_sib.right) === 1) {
                    class_var.parent.rotate_left();
                    class_var.grandparent().color = class_var.parent.color;
                    class_var.parent.color = 0;
                    class_var.parent.sibling().color = 0;
                }
            }
        }
        if (class_var.is_right()) {
            var _cv_sib = class_var.sibling();
            if (get_color(_cv_sib) === 0) {
                if (get_color(_cv_sib.left) === 1) {
                    class_var.parent.rotate_right();
                    class_var.grandparent().color = class_var.parent.color;
                    class_var.parent.color = 0;
                    class_var.parent.sibling().color = 0;
                }
            }
        }
    }
    function check_color_properties() {
        if (class_var.color) {
            console.log("Property 2");
            return false;
        }
        if (!class_var.check_coloring()) {
            console.log("Property 4");
            return false;
        }
        if (class_var.black_height() === null) {
            console.log("Property 5");
            return false;
        }
        return true;
    }
    function check_coloring() {
        var _cv_left_color = get_color(class_var.left);
        var _cv_right_color = get_color(class_var.right);
        if (class_var.color === 1) {
            if ([_cv_left_color, _cv_right_color].includes(1)) {
                return false;
            }
        }
        if (class_var.left) {
            if (!class_var.left.check_coloring()) {
                return false;
            }
        }
        if (class_var.right) {
            if (!class_var.right.check_coloring()) {
                return false;
            }
        }
        return true;
    }
    function black_height() {
        if (class_var === null || class_var.left === null || class_var.right === null) {
            return 1;
        }
        var left = class_var.left.black_height();
        var right = class_var.right.black_height();
        if (left === null || right === null) {
            return null;
        }
        if (left !== right) {
            return null;
        }
        return left + (1 - class_var.color);
    }
    function __contains__(label) {
        return class_var.search(label) !== null;
    }
    function search(label) {
        if (class_var.label === label) {
            return class_var;
        } else if (class_var.label !== null && label > class_var.label) {
            if (class_var.right === null) {
                return null;
            } else {
                return class_var.right.search(label);
            }
        } else if (class_var.left === null) {
            return null;
        } else {
            return class_var.left.search(label);
        }
    }
    function floor(label) {
        if (class_var.label === label) {
            return class_var.label;
        } else if (class_var.label !== null && class_var.label > label) {
            if (class_var.left) {
                return class_var.left.floor(label);
            } else {
                return null;
            }
        } else {
            if (class_var.right) {
                var attempt = null;
                attempt = class_var.right.floor(label);
                if (attempt !== null) {
                    return attempt;
                }
            }
            return class_var.label;
        }
    }
    function ceil(label) {
        if (class_var.label === label) {
            return class_var.label;
        } else if (class_var.label !== null && class_var.label < label) {
            if (class_var.right) {
                return class_var.right.ceil(label);
            } else {
                return null;
            }
        } else {
            if (class_var.left) {
                var attempt = null;
                attempt = class_var.left.ceil(label);
                if (attempt !== null) {
                    return attempt;
                }
            }
            return class_var.label;
        }
    }
    function get_max() {
        if (class_var.right) {
            return class_var.right.get_max();
        } else {
            return class_var.label;
        }
    }
    function get_min() {
        if (class_var.left) {
            return class_var.left.get_min();
        } else {
            return class_var.label;
        }
    }
    function grandparent() {
        if (class_var.parent === null) {
            return null;
        } else {
            return class_var.parent.parent;
        }
    }
    function sibling() {
        if (class_var.parent === null) {
            return null;
        }
        if (class_var.parent.left === class_var) {
            return class_var.parent.right;
        }
        return class_var.parent.left;
    }
    function is_left() {
        if (class_var.parent === null) {
            return false;
        }
        return class_var.parent.left === class_var;
    }
    function is_right() {
        if (class_var.parent === null) {
            return false;
        }
        return class_var.parent.right === class_var;
    }
    function __bool__() {
        return true;
    }
    function __len__() {
        var ln = 1;
        if (class_var.left) {
            ln += class_var.left.length;
        }
        if (class_var.right) {
            ln += class_var.right.length;
        }
        return ln;
    }
    function* preorder_traverse() {
        yield class_var.label;
        if (class_var.left) {
            yield* class_var.left.preorder_traverse();
        }
        if (class_var.right) {
            yield* class_var.right.preorder_traverse();
        }
    }
    function* inorder_traverse() {
        if (class_var.left) {
            yield* class_var.left.inorder_traverse();
        }
        yield class_var.label;
        if (class_var.right) {
            yield* class_var.right.inorder_traverse();
        }
    }
    function* postorder_traverse() {
        if (class_var.left) {
            yield* class_var.left.postorder_traverse();
        }
        if (class_var.right) {
            yield* class_var.right.postorder_traverse();
        }
        yield class_var.label;
    }
    function __eq__(other) {
        if (class_var.label === other.label) {
            var _left_eq = false;
            if (class_var.left === null) {
                _left_eq = true;
            } else {
                _left_eq = class_var.left.__eq__(other.left);
            }
            var _right_eq = false;
            if (class_var.right === null) {
                _right_eq = true;
            } else {
                _right_eq = class_var.right.__eq__(other.right);
            }
            return _left_eq && _right_eq;
        } else {
            return false;
        }
    }
    var Clz = SkelClass('RedBlackTree');
    var class_var = Clz();
    class_var.__init__ = __init__;
    class_var.rotate_left = rotate_left;
    class_var.rotate_right = rotate_right;
    class_var.insert = insert;
    class_var._insert_repair = _insert_repair;
    class_var.remove = remove;
    class_var._remove_repair = _remove_repair;
    class_var.check_color_properties = check_color_properties;
    class_var.check_coloring = check_coloring;
    class_var.black_height = black_height;
    class_var.__contains__ = __contains__;
    class_var.search = search;
    class_var.floor = floor;
    class_var.ceil = ceil;
    class_var.get_max = get_max;
    class_var.get_min = get_min;
    class_var.grandparent = grandparent;
    class_var.sibling = sibling;
    class_var.is_left = is_left;
    class_var.is_right = is_right;
    class_var.__bool__ = __bool__;
    class_var.__len__ = __len__;
    class_var.preorder_traverse = preorder_traverse;
    class_var.inorder_traverse = inorder_traverse;
    class_var.postorder_traverse = postorder_traverse;
    class_var.__eq__ = __eq__;
    __init__(param_0, param_1, param_2, param_3, param_4);
    return class_var;
}
function get_color(node) {
    if (node === null) {
        return 0;
    } else {
        return node.color;
    }
}
function test_rotations() {
    var tree = RedBlackTree(0, 0, null, null, null);
    tree.left = RedBlackTree(-10, 0, tree, null, null);
    tree.right = RedBlackTree(10, 0, tree, null, null);
    tree.left.left = RedBlackTree(-20, 0, tree.left, null, null);
    tree.left.right = RedBlackTree(-5, 0, tree.left, null, null);
    tree.right.left = RedBlackTree(5, 0, tree.right, null, null);
    tree.right.right = RedBlackTree(20, 0, tree.right, null, null);
    var left_rot = RedBlackTree(10, 0, null, null, null);
    left_rot.left = RedBlackTree(0, 0, left_rot, null, null);
    left_rot.left.left = RedBlackTree(-10, 0, left_rot.left, null, null);
    left_rot.left.right = RedBlackTree(5, 0, left_rot.left, null, null);
    left_rot.left.left.left = RedBlackTree(-20, 0, left_rot.left.left, null, null);
    left_rot.left.left.right = RedBlackTree(-5, 0, left_rot.left.left, null, null);
    left_rot.right = RedBlackTree(20, 0, left_rot, null, null);
    tree = tree.rotate_left();
    if (!tree.__eq__(left_rot)) {
        throw new Error('Assertion failed');
    }
    tree = tree.rotate_right();
    tree = tree.rotate_right();
    var right_rot = RedBlackTree(-10, 0, null, null, null);
    right_rot.left = RedBlackTree(-20, 0, right_rot, null, null);
    right_rot.right = RedBlackTree(0, 0, right_rot, null, null);
    right_rot.right.left = RedBlackTree(-5, 0, right_rot.right, null, null);
    right_rot.right.right = RedBlackTree(10, 0, right_rot.right, null, null);
    right_rot.right.right.left = RedBlackTree(5, 0, right_rot.right.right, null, null);
    right_rot.right.right.right = RedBlackTree(20, 0, right_rot.right.right, null, null);
    if (!tree.__eq__(right_rot)) {
        throw new Error('Assertion failed');
    }
    return true;
}
function test_insertion_speed() {
    tree = RedBlackTree(-1, 0, null, null, null);
    for (var i = 0; i < 10; i++) {
        tree = tree.insert(i);
    }
    return true;
}
function test_insert() {
    tree = RedBlackTree(0, 0, null, null, null);
    tree.insert(8);
    tree.insert(-8);
    tree.insert(4);
    tree.insert(12);
    tree.insert(10);
    tree.insert(11);
    ans = RedBlackTree(0, 0, null, null, null);
    ans.left = RedBlackTree(-8, 0, ans, null, null);
    ans.right = RedBlackTree(8, 1, ans, null, null);
    ans.right.left = RedBlackTree(4, 0, ans.right, null, null);
    ans.right.right = RedBlackTree(11, 0, ans.right, null, null);
    ans.right.right.left = RedBlackTree(10, 1, ans.right.right, null, null);
    ans.right.right.right = RedBlackTree(12, 1, ans.right.right, null, null);
    return tree.__eq__(ans);
}
function test_insert_and_search() {
    tree = RedBlackTree(0, 0, null, null, null);
    tree.insert(8);
    tree.insert(-8);
    tree.insert(4);
    tree.insert(12);
    tree.insert(10);
    tree.insert(11);
    if (tree.__contains__(5)) {
        throw new Error('Assertion failed');
    }
    if (tree.__contains__(-6)) {
        throw new Error('Assertion failed');
    }
    if (tree.__contains__(-10)) {
        throw new Error('Assertion failed');
    }
    if (tree.__contains__(13)) {
        throw new Error('Assertion failed');
    }
    if (!tree.__contains__(11)) {
        throw new Error('Assertion failed');
    }
    if (!tree.__contains__(12)) {
        throw new Error('Assertion failed');
    }
    if (!tree.__contains__(-8)) {
        throw new Error('Assertion failed');
    }
    if (!tree.__contains__(0)) {
        throw new Error('Assertion failed');
    }
    return true;
}
function test_insert_delete() {
    tree = RedBlackTree(0, 0, null, null, null);
    tree = tree.insert(-12);
    tree = tree.insert(8);
    tree = tree.insert(-8);
    tree = tree.insert(15);
    tree = tree.insert(4);
    tree = tree.insert(12);
    tree = tree.insert(10);
    tree = tree.insert(9);
    tree = tree.insert(11);
    tree = tree.remove(15);
    tree = tree.remove(-12);
    tree = tree.remove(9);
    if (!tree.check_color_properties()) {
        throw new Error('Assertion failed');
    }
    var result = tree.inorder_traverse();
    assert_iter_equal(result, [-8, 0, 4, 8, 10, 11, 12]);
    return true;
}
function test_floor_ceil() {
    tree = RedBlackTree(0, 0, null, null, null);
    tree.insert(-16);
    tree.insert(16);
    tree.insert(8);
    tree.insert(24);
    tree.insert(20);
    tree.insert(22);
    var tuples = [[-20, null, -16], [-10, -16, 0], [8, 8, 8], [50, 24, null]];
    for (var i = 0; i < tuples.length; i++) {
        var val = tuples[i][0];
        var floor = tuples[i][1];
        var ceil = tuples[i][2];
        if (tree.floor(val) !== floor) {
            throw new Error('Assertion failed');
        }
        if (tree.ceil(val) !== ceil) {
            throw new Error('Assertion failed');
        }
    }
    return true;
}
function test_min_max() {
    tree = RedBlackTree(0, 0, null, null, null);
    tree.insert(-16);
    tree.insert(16);
    tree.insert(8);
    tree.insert(24);
    tree.insert(20);
    tree.insert(22);
    if (tree.get_max() !== 24) {
        throw new Error('Assertion failed');
    }
    if (tree.get_min() !== -16) {
        throw new Error('Assertion failed');
    }
    return true;
}
function test_tree_traversal() {
    tree = RedBlackTree(0, 0, null, null, null);
    tree = tree.insert(-16);
    tree.insert(16);
    tree.insert(8);
    tree.insert(24);
    tree.insert(20);
    tree.insert(22);
    var _result_inorder = tree.inorder_traverse();
    var _result_preorder = tree.preorder_traverse();
    var _result_postorder = tree.postorder_traverse();
    assert_iter_equal(_result_inorder, [-16, 0, 8, 16, 20, 22, 24]);
    assert_iter_equal(_result_preorder, [0, -16, 16, 8, 22, 20, 24]);
    assert_iter_equal(_result_postorder, [-16, 8, 20, 24, 22, 16, 0]);
    return true;
}
function test_tree_chaining() {
    tree = RedBlackTree(0, 0, null, null, null);
    tree = tree.insert(-16).insert(16).insert(8).insert(24).insert(20).insert(22);
    var _result_inorder = tree.inorder_traverse();
    var _result_preorder = tree.preorder_traverse();
    var _result_postorder = tree.postorder_traverse();
    assert_iter_equal(_result_inorder, [-16, 0, 8, 16, 20, 22, 24]);
    assert_iter_equal(_result_preorder, [0, -16, 16, 8, 22, 20, 24]);
    assert_iter_equal(_result_postorder, [-16, 8, 20, 24, 22, 16, 0]);
    return true;
}
function print_results(msg, passes) {
    console.log(msg.toString(), passes ? "works!" : "doesn't work :|");
}
function additional_tests() {
    tree = RedBlackTree(0, 0, null, null, null);
    if (tree.__len__() !== 1) {
        throw new Error('Assertion failed');
    }
    tree = RedBlackTree(0, 0, null, null, null);
    tree.insert(-16);
    tree.insert(16);
    tree.insert(-8);
    tree.insert(12);
    tree.insert(-20);
    tree.insert(8);
    tree.insert(-4);
    tree.insert(4);
    tree.insert(-3);
    tree.insert(24);
    tree.insert(-20);
    tree.insert(20);
    tree.insert(-1);
    tree.insert(2);
    tree.insert(-3);
    tree.insert(3);
    tree.insert(10);
    tree.insert(26);
    tree.right.right.left._remove_repair();
    if (tree.right.right.left.label !== 20) {
        throw new Error('Assertion failed');
    }
}
function test_init() {
    // is_left, is_right
    var tree = RedBlackTree(13, null, null, null, null);
    tree.is_left();
    tree.is_right();
    // sibling
    tree = RedBlackTree(13, null, null, null, null);
    var sib = tree.sibling();
    tree.insert(8);
    sib = tree.left.sibling();
    tree.insert(17);
    sib = tree.right.sibling();
    // ceil
    tree = RedBlackTree(13, null, null, null, null);
    var c = tree.ceil(13);
    tree.insert(8);
    c = tree.ceil(15);
    tree.insert(15);
    c = tree.ceil(15);
    var tree1 = RedBlackTree(13, null, null, null, null);
    tree1.insert(15);
    c = tree1.ceil(12);
    tree1.insert(8);
    c = tree1.ceil(7);
    // floor
    tree = RedBlackTree(13, null, null, null, null);
    c = tree.floor(13);
    tree.insert(15);
    c = tree.floor(8);
    tree.insert(8);
    c = tree.floor(8);
    tree1 = RedBlackTree(13, null, null, null, null);
    tree1.insert(8);
    c = tree1.floor(12);
    tree1.insert(15);
    c = tree1.floor(17);
    // search
    tree = RedBlackTree(13, null, null, null, null);
    t = tree.search(13);
    tree.insert(8);
    t = tree.search(15);
    tree.insert(15);
    t = tree.search(17);
    tree1 = RedBlackTree(13, null, null, null, null);
    t = tree1.search(12);
    tree1.insert(8);
    t = tree1.search(12);
}
function test() {
    test_init();
    print_results('Rotating right and left', test_rotations());
    print_results('Inserting', test_insert());
    print_results('Searching', test_insert_and_search());
    print_results('Deleting', test_insert_delete());
    print_results('Floor and ceil', test_floor_ceil());
    print_results('Min and max', test_min_max());
    print_results('Tree traversal', test_tree_traversal());
    print_results('Tree traversal', test_tree_chaining());
    console.log("Testing tree balancing...");
    console.log("This should only be a few seconds.");
    test_insertion_speed();
    additional_tests();
    console.log("Done!");
}
test();
