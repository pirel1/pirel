function SkelClass(name) {
    var Clz = function() {
        var _class_var = {};
        _class_var._class_name = name;
        return _class_var;
    };
    return Clz;
}





function assert_iter_equal(iter1, iter2) {
    for (var index = 0; index < iter1.length; index++) {
        var a = iter1[index];
        var b = iter2[index];
        if (a !== b) {
            throw new Error('Assertion failed');
        }
    }
}
function Node(param_0, param_1) {
    function Node_dlm___init__(label, parent) {
        class_var.label = label;
        class_var.parent = parent;
        class_var.left = null;
        class_var.right = null;
    }
    var Clz = SkelClass('Node');
    var class_var = Clz();
    class_var.__init__ = Node_dlm___init__;
    Node_dlm___init__(param_0, param_1);
    return class_var;
}
function BinarySearchTree() {
    function BinarySearchTree_dlm___init__() {
        class_var.root = null;
    }
    function empty() {
        class_var.root = null;
    }
    function is_empty() {
        return class_var.root === null;
    }
    function put(label) {
        class_var.root = class_var._put(class_var.root, label, null);
    }
    function _put(node, label, parent) {
        if (node === null) {
            node = new Node(label, parent);
        } else if (label < node.label) {
            node.left = class_var._put(node.left, label, node);
        } else if (label > node.label) {
            node.right = class_var._put(node.right, label, node);
        } else {
            var msg = "Node with label " + label + " already exists";
            throw new Exception(msg);
        }
        return node;
    }
    function search(label) {
        return class_var._search(class_var.root, label);
    }
    function _search(node, label) {
        if (node === null) {
            var msg = "Node with label " + label + " does not exist";
            throw new Exception(msg);
        } else if (label < node.label) {
            node = class_var._search(node.left, label);
        } else if (label > node.label) {
            node = class_var._search(node.right, label);
        }
        return node;
    }
    function remove(label) {
        var node = class_var.search(label);
        if (node.right && node.left) {
            var lowest_node = class_var._get_lowest_node(node.right);
            lowest_node.left = node.left;
            lowest_node.right = node.right;
            node.left.parent = lowest_node;
            if (node.right) {
                node.right.parent = lowest_node;
            }
            class_var._reassign_nodes(node, lowest_node);
        } else if (!node.right && node.left) {
            class_var._reassign_nodes(node, node.left);
        } else if (node.right && !node.left) {
            class_var._reassign_nodes(node, node.right);
        } else {
            class_var._reassign_nodes(node, null);
        }
    }
    function _reassign_nodes(node, new_children) {
        if (new_children !== null) {
            new_children.parent = node.parent;
        }
        if (node.parent !== null) {
            if (node.parent.right === node) {
                node.parent.right = new_children;
            } else {
                node.parent.left = new_children;
            }
        } else {
            class_var.root = new_children;
        }
    }
    function _get_lowest_node(node) {
        var lowest_node = null;
        if (node.left) {
            lowest_node = class_var._get_lowest_node(node.left);
        } else {
            lowest_node = node;
            class_var._reassign_nodes(node, node.right);
        }
        return lowest_node;
    }
    function exists(label) {
        try {
            class_var.search(label);
            return true;
        } catch {
            return false;
        }
    }
    function get_max_label() {
        if (class_var.root === null) {
            throw new Exception("Binary search tree is empty");
        }
        var node = class_var.root;
        while (node.right !== null) {
            node = node.right;
        }
        return node.label;
    }
    function get_min_label() {
        if (class_var.root === null) {
            throw new Error("Binary search tree is empty");
        }
        var node = class_var.root;
        while (node.left !== null) {
            node = node.left;
        }
        return node.label;
    }
    function inorder_traversal() {
        var nodes = class_var._inorder_traversal(class_var.root);
        return nodes;
    }
    function* _inorder_traversal(node) {
        if (node !== null) {
            yield* class_var._inorder_traversal(node.left);
            yield node;
            yield* class_var._inorder_traversal(node.right);
        }
    }
    function preorder_traversal() {
        var nodes = class_var._preorder_traversal(class_var.root);
        return nodes;
    }
    function* _preorder_traversal(node) {
        if (node !== null) {
            yield node;
            yield* class_var._preorder_traversal(node.left);
            yield* class_var._preorder_traversal(node.right);
        }
    }
    var Clz = SkelClass('BinarySearchTree');
    var class_var = Clz();
    class_var.__init__ = BinarySearchTree_dlm___init__;
    class_var.empty = empty;
    class_var.is_empty = is_empty;
    class_var.put = put;
    class_var._put = _put;
    class_var.search = search;
    class_var._search = _search;
    class_var.remove = remove;
    class_var._reassign_nodes = _reassign_nodes;
    class_var._get_lowest_node = _get_lowest_node;
    class_var.exists = exists;
    class_var.get_max_label = get_max_label;
    class_var.get_min_label = get_min_label;
    class_var.inorder_traversal = inorder_traversal;
    class_var._inorder_traversal = _inorder_traversal;
    class_var.preorder_traversal = preorder_traversal;
    class_var._preorder_traversal = _preorder_traversal;
    BinarySearchTree_dlm___init__();
    return class_var;
}
function _get_binary_search_tree() {
    var t = new BinarySearchTree();
    t.put(8);
    t.put(3);
    t.put(6);
    t.put(1);
    t.put(10);
    t.put(14);
    t.put(13);
    t.put(4);
    t.put(7);
    t.put(5);
    return t;
}
function test_put() {
    t = new BinarySearchTree();
    if (!t.is_empty()) {
        throw new Error('Assertion failed');
    }
    t.put(8);
    if (t.root === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.parent !== null) {
        throw new Error('Assertion failed');
    }
    if (t.root.label !== 8) {
        throw new Error('Assertion failed');
    }
    t.put(10);
    if (t.root.right === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.right.parent !== t.root) {
        throw new Error('Assertion failed');
    }
    if (t.root.right.label !== 10) {
        throw new Error('Assertion failed');
    }
    t.put(3);
    if (t.root.left === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.parent !== t.root) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.label !== 3) {
        throw new Error('Assertion failed');
    }
    t.put(6);
    if (t.root.left.right === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.right.parent !== t.root.left) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.right.label !== 6) {
        throw new Error('Assertion failed');
    }
    t.put(1);
    if (t.root.left.left === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.left.parent !== t.root.left) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.left.label !== 1) {
        throw new Error('Assertion failed');
    }
    var _exception_thrown = false;
    try {
        t.put(1);
    } catch {
        _exception_thrown = true;
    }
    if (!_exception_thrown) {
        throw new Error('Assertion failed');
    }
}
function test_search() {
    var t = _get_binary_search_tree();
    var node = t.search(6);
    if (node.label !== 6) {
        throw new Error('Assertion failed');
    }
    node = t.search(13);
    if (node.label !== 13) {
        throw new Error('Assertion failed');
    }
    var _exception_thrown = false;
    try {
        t.search(2);
    } catch {
        _exception_thrown = true;
    }
    if (!_exception_thrown) {
        throw new Error('Assertion failed');
    }
}
function test_remove() {
    var t = _get_binary_search_tree();
    t.remove(13);
    if (t.root === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.right === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.right.right === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.right.right.right !== null) {
        throw new Error("Assertion failed");
    }
    if (t.root.right.right.left !== null) {
        throw new Error("Assertion failed");
    }
    t.remove(7);
    if (t.root.left === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right.left === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right.right !== null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right.left.label !== 4) {
        throw new Error("Assertion failed");
    }
    t.remove(6);
    if (t.root.left.left === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right.right === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.left.label !== 1) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right.label !== 4) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right.right.label !== 5) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right.left !== null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.left.parent !== t.root.left) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right.parent !== t.root.left) {
        throw new Error("Assertion failed");
    }
    t.remove(3);
    if (t.root === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.label !== 4) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right.label !== 5) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.left.label !== 1) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.parent !== t.root) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.left.parent !== t.root.left) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right.parent !== t.root.left) {
        throw new Error("Assertion failed");
    }
    t.remove(4);
    if (t.root.left === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.left === null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.label !== 5) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.right !== null) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.left.label !== 1) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.parent !== t.root) {
        throw new Error("Assertion failed");
    }
    if (t.root.left.left.parent !== t.root.left) {
        throw new Error("Assertion failed");
    }
}
function test_remove_2() {
    t = _get_binary_search_tree();
    t.remove(3);
    if (t.root === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.left === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.left === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.right === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.right.left === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.right.right === null) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.label !== 4) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.right.label !== 6) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.left.label !== 1) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.right.right.label !== 7) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.right.left.label !== 5) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.parent !== t.root) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.right.parent !== t.root.left) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.left.parent !== t.root.left) {
        throw new Error('Assertion failed');
    }
    if (t.root.left.right.left.parent !== t.root.left.right) {
        throw new Error('Assertion failed');
    }
}
function test_empty() {
    t = _get_binary_search_tree();
    t.empty();
    if (t.root !== null) {
        throw new Error('Assertion failed');
    }
}
function test_is_empty() {
    t = _get_binary_search_tree();
    if (t.is_empty()) {
        throw new Error("Assertion failed");
    }
    t.empty();
    if (!t.is_empty()) {
        throw new Error("Assertion failed");
    }
}
function test_exists() {
    t = _get_binary_search_tree();
    if (!t.exists(6)) {
        throw new Error('Assertion failed');
    }
    if (t.exists(-1)) {
        throw new Error('Assertion failed');
    }
}
function test_get_max_label() {
    t = _get_binary_search_tree();
    if (t.get_max_label() !== 14) {
        throw new Error('Assertion failed');
    }
    t.empty();
    var _exception_thrown = false;
    try {
        t.get_max_label();
    } catch {
        _exception_thrown = true;
    }
    if (!_exception_thrown) {
        throw new Error('Assertion failed');
    }
}
function test_get_min_label() {
    t = _get_binary_search_tree();
    if (t.get_min_label() !== 1) {
        throw new Error('Assertion failed');
    }
    t.empty();
    var _exception_thrown = false;
    try {
        t.get_min_label();
    } catch {
        _exception_thrown = true;
    }
    if (!_exception_thrown) {
        throw new Error('Assertion failed');
    }
}
function test_inorder_traversal() {
    t = _get_binary_search_tree();
    nodes = t.inorder_traversal();
    inorder_traversal_nodes = Array.from(nodes).map(i => i.label);
    assert_iter_equal(inorder_traversal_nodes, [1, 3, 4, 5, 6, 7, 8, 10, 13, 14]);
}
function test_preorder_traversal() {
    t = _get_binary_search_tree();
    nodes = t.preorder_traversal();
    preorder_traversal_nodes = Array.from(nodes).map(i => i.label);
    assert_iter_equal(preorder_traversal_nodes, [8, 3, 1, 6, 4, 5, 7, 10, 14, 13]);
}
function binary_search_tree_example() {
    t = new BinarySearchTree();
    t.put(8);
    t.put(3);
    t.put(6);
    t.put(1);
    t.put(10);
    t.put(14);
    t.put(13);
    t.put(4);
    t.put(7);
    t.put(5);
    console.log("Label 6 exists:", t.exists(6));
    console.log("Label 13 exists:", t.exists(13));
    console.log("Label -1 exists:", t.exists(-1));
    console.log("Label 12 exists:", t.exists(12));
    var nodes = t.inorder_traversal();
    var inorder_traversal_nodes = Array.from(nodes).map(i => i.label);
    console.log("Inorder traversal:", inorder_traversal_nodes);
    nodes = t.preorder_traversal()
    var preorder_traversal_nodes = Array.from(nodes).map(i => i.label);
    console.log("Preorder traversal:", preorder_traversal_nodes);
    console.log("Max. label:", t.get_max_label());
    console.log("Min. label:", t.get_min_label());
    console.log("\nDeleting elements 13, 10, 8, 3, 6, 14");
    t.remove(13);
    t.remove(10);
    t.remove(8);
    t.remove(3);
    t.remove(6);
    t.remove(14);
    nodes = t.inorder_traversal()
    inorder_traversal_nodes = Array.from(nodes).map(i => i.label);
    console.log("Inorder traversal after delete:", inorder_traversal_nodes);
    nodes = t.preorder_traversal()
    preorder_traversal_nodes = Array.from(nodes).map(i => i.label);
    console.log("Preorder traversal after delete:", preorder_traversal_nodes);
    console.log("Max. label:", t.get_max_label());
    console.log("Min. label:", t.get_min_label());
}
function test_init() {
    t = new BinarySearchTree();
    t.put(8);
    t.put(3);
    t.put(6);
    t.put(1);
    t.put(10);
    t.put(14);
    t.put(13);
    t.put(4);
    t.put(7);
    t.put(5);
    node = t._get_lowest_node(t.root);
    console.log(node.label);
}
function test() {
    test_init();
    binary_search_tree_example();
    test_put();
    test_search();
    test_remove();
    test_remove_2();
    test_is_empty();
    test_empty();
    test_exists();
    test_get_max_label();
    test_get_min_label();
    test_inorder_traversal();
    test_preorder_traversal();
}
test();
