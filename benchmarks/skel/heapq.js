function _compare(a, b) {
    if (typeof a === 'string' && typeof b === 'string') {
        return a.localeCompare(b);
    } else if (typeof a === 'number' && typeof b === 'number') {
        return a - b;
    } else if (Array.isArray(a) && Array.isArray(b)) {
        if (a.length !== b.length) {
            return a.length - b.length;
        } else {
            for (let i = 0; i < a.length; i++) {
                const comparison = _compare(a[i], b[i]);
                if (comparison !== 0) {
                    return comparison;
                }
            }
            return 0;
        }
    } else {
        throw new Error('Cannot compare different types');
    }
}





function assert_almost_equal(a, b) {
    if (Math.abs(a - b) > 0.0001) {
        throw new Error("Assertion failed: abs(a - b) <= 0.0001");
    }
}
function assert_iter_almost_equal(iter1, iter2) {
    if (iter1.length !== iter2.length) {
        throw new Error("Assertion failed");
    }
    for (var i = 0; i < iter1.length; i++) {
        var elem_a = iter1[i];
        var elem_b = iter2[i];
        assert_almost_equal(elem_a, elem_b);
    }
}
function heappush(heap, item) {
    heap.push(item);
    _siftdown(heap, 0, heap.length - 1);
}
function heappop(heap) {
    var lastelt = heap.pop();
    if (heap.length > 0) {
        var returnitem = heap[0];
        heap[0] = lastelt;
        _siftup(heap, 0);
        return returnitem;
    }
    return lastelt;
}
function heapreplace(heap, item) {
    var returnitem = heap[0];
    heap[0] = item;
    _siftup(heap, 0);
    return returnitem;
}
function heappushpop(heap, item) {
    if (heap.length > 0 && heap[0] < item) {
        var temp = item;
        item = heap[0];
        heap[0] = temp;
        _siftup(heap, 0);
    }
    return item;
}
function heapify(x) {
    var n = x.length;
    for (var i = Math.floor(n / 2) - 1; i > -1; i--) {
        _siftup(x, i);
    }
}
function _heappop_max(heap) {
    var lastelt = heap.pop();
    if (heap.length > 0) {
        var returnitem = heap[0];
        heap[0] = lastelt;
        _siftup_max(heap, 0);
        return returnitem;
    }
    return lastelt;
}
function _heapreplace_max(heap, item) {
    var returnitem = heap[0];
    heap[0] = item;
    _siftup_max(heap, 0);
    return returnitem;
}
function _heapify_max(x) {
    var n = x.length;
    for (var i = Math.floor(n / 2) - 1; i > -1; i--) {
        _siftup_max(x, i);
    }
}
function _siftdown(heap, startpos, pos) {
    var newitem = heap[pos];
    while (pos > startpos) {
        var parentpos = (pos - 1) >> 1;
        var parent = heap[parentpos];
        if (_compare(parent, newitem) > 0) {
            heap[pos] = parent;
            pos = parentpos;
            continue;
        }
        break;
    }
    heap[pos] = newitem;
}
function _siftup(heap, pos) {
    var endpos = heap.length;
    var startpos = pos;
    var newitem = heap[pos];
    var childpos = 2 * pos + 1;
    while (childpos < endpos) {
        var rightpos = childpos + 1;
        if (rightpos < endpos) {
            if (_compare(heap[childpos], heap[rightpos]) >= 0) {
                childpos = rightpos;
            }
        }
        heap[pos] = heap[childpos];
        pos = childpos;
        childpos = 2 * pos + 1;
    }
    heap[pos] = newitem;
    _siftdown(heap, startpos, pos);
}
function _siftdown_max(heap, startpos, pos) {
    var newitem = heap[pos];
    while (pos > startpos && heap[(pos - 1) >> 1] < newitem) {
        var parentpos = (pos - 1) >> 1;
        heap[pos] = heap[parentpos];
        pos = parentpos;
    }
    heap[pos] = newitem;
}
function _siftup_max(heap, pos) {
    var endpos = heap.length;
    var startpos = pos;
    var newitem = heap[pos];
    var childpos = 2 * pos + 1;
    while (childpos < endpos) {
        var rightpos = childpos + 1;
        if (rightpos < endpos) {
            if (heap[rightpos] >= heap[childpos]) {
                childpos = rightpos;
            }
        }
        heap[pos] = heap[childpos];
        pos = childpos;
        childpos = 2 * pos + 1;
    }
    heap[pos] = newitem;
    _siftdown_max(heap, startpos, pos);
}
function* merge(reverse, ...iterables) {
    var h = [];
    var _heapify = null;
    var _heappop = null;
    var _heapreplace = null;
    var direction = null;
    if (reverse) {
        _heapify = _heapify_max;
        _heappop = _heappop_max;
        _heapreplace = _heapreplace_max;
        direction = -1;
    } else {
        _heapify = heapify;
        _heappop = heappop;
        _heapreplace = heapreplace;
        direction = 1;
    }
    for (var order = 0; order < iterables.length; order++) {
        var it = iterables[order][Symbol.iterator]();
        try {
            var next = it.next.bind(it);
            var next_elem = next();
            if (next_elem.done) {
                continue;
            }
            h.push([next_elem.value, order * direction, next]);
        } catch (e) {
            throw e;
        }
    }
    order -= 1;
    _heapify(h);
    while (h.length > 1) {
        try {
            while (true) {
                var s = h[0];
                var [value, order, next] = s;
                yield value;
                var next_elem = next();
                var done = next_elem.done;
                if (done) {
                    _heappop(h);
                    break;
                }
                s[0] = next_elem.value;
                _heapreplace(h, s);
            }
        } catch (e) {
            throw e;
        }
    }
    if (h.length > 0) {
        var [value, order, next] = h[0];
        yield value;
        yield* (function* next_wrap() {
            while (true) {
                var next_elem = next();
                var val = next_elem.value;
                var done = next_elem.done;
                if (done) {
                    break;
                }
                yield val;
            };
        })();
    }
    return;
}
function nsmallest(n, iterable) {
    if (n === 1) {
        if (iterable.length === 0) {
            return [];
        }
        var _return_val = [Math.min(...iterable)];
        return _return_val;
    }
    if (n === 0) {
        return [];
    }
    var _try_success = false;
    try {
        var size = iterable.length;
        _try_success = true;
    } catch {
    }
    if (_try_success) {
        if (n >= size) {
            return iterable.slice().sort().slice(0, n);
        }
    }
    it = iterable[Symbol.iterator]();
    var result = [];
    for (var i = 0; i < n; i++) {
        var elem = it.next().value;
        result.push([elem, i]);
    }
    if (result.length === 0) {
        return result;
    }
    _heapify_max(result);
    var top = result[0][0];
    var order = n;
    var _heapreplace = _heapreplace_max;
    for (elem of it) {
        if (elem < top) {
            _heapreplace(result, [elem, order]);
            top = result[0][0];
            order++;
        }
    }
    result.sort((a, b) => a[0] - b[0]);
    var _return_val = [];
    for (var i = 0; i < result.length; i++) {
        var elem = result[i][0];
        _return_val.push(elem);
    }
    return _return_val;
}
function nlargest(n, iterable) {
    if (n === 1) {
        if (iterable.length === 0) {
            return [];
        }
        var _return_val = [Math.max(...iterable)];
        return _return_val;
    }
    if (n === 0) {
        return [];
    }
    var _try_success = false;
    try {
        var size = iterable.length;
        _try_success = true;
    } catch {
    }
    if (_try_success) {
        if (n >= size) {
            return iterable.slice().sort((a, b) => b - a).slice(0, n);
        }
    }
    it = iterable[Symbol.iterator]();
    result = [];
    for (var i = 0; i < n; i++) {
        var elem = it.next().value;
        result.push([elem, -i]);
    }
    if (result.length === 0) {
        return result;
    }
    heapify(result);
    var top = result[0][0];
    var order = -n;
    var _heapreplace = heapreplace;
    for (var elem of it) {
        if (top < elem) {
            _heapreplace(result, [elem, order]);
            top = result[0][0];
            order = result[0][1];
            order -= 1;
        }
    }
    result.sort((a, b) => b[0] - a[0]);
    var _return_val = [];
    for (var i = 0; i < result.length; i++) {
        var elem = result[i][0];
        _return_val.push(elem);
    }
    return _return_val;
}
function test_heappush_help_function(items) {
    var heap = [];
    for (var item of items) {
        heappush(heap, item);
    }
    var a = heappop(heap);
    var b = heappop(heap);
    return [a, b];
}
function test_heappush() {
    var items1 = [6, 1, -2, 5];
    var gold1 = [-2, 1];
    var res1 = test_heappush_help_function(items1);
    assert_iter_almost_equal(res1, gold1);
    var items2 = [34, -3, -12, 0];
    var gold2 = [-12, -3];
    var res2 = test_heappush_help_function(items2);
    assert_iter_almost_equal(res2, gold2);
    var items3 = [5, 4, 3, 2, 1];
    var gold3 = [1, 2];
    var res3 = test_heappush_help_function(items3);
    assert_iter_almost_equal(res3, gold3);
    var items4 = [4.7, 8, -1.2, 7.2];
    var gold4 = [-1.2, 4.7];
    var res4 = test_heappush_help_function(items4);
    assert_iter_almost_equal(res4, gold4);
}
function test_heapify_help_function(x) {
    heapify(x);
    var a = heappop(x);
    var b = heappop(x);
    return [a, b];
}
function test_heapify() {
    var items1 = [6, 1, -2, 5];
    var gold1 = [-2, 1];
    var res1 = test_heapify_help_function(items1);
    assert_iter_almost_equal(res1, gold1);
    var items2 = [34, -3, -12, 0];
    var gold2 = [-12, -3];
    var res2 = test_heapify_help_function(items2);
    assert_iter_almost_equal(res2, gold2);
    var items3 = [5, 4, 3, 2, 1];
    var gold3 = [1, 2];
    var res3 = test_heapify_help_function(items3);
    assert_iter_almost_equal(res3, gold3);
    var items4 = [4.7, 8, -1.2, 7.2];
    var gold4 = [-1.2, 4.7];
    var res4 = test_heapify_help_function(items4);
    assert_iter_almost_equal(res4, gold4);
}
function test_heappushpop_help_function(x, i) {
    heapify(x);
    var a = heappushpop(x, i);
    return a;
}
function test_heappushpop() {
    var items1 = [6, 1, -2, 5];
    var item1 = -5;
    var gold1 = -5;
    var res1 = test_heappushpop_help_function(items1, item1);
    assert_almost_equal(res1, gold1);
    var items2 = [34, -3, -12, 0];
    var item2 = -13;
    var gold2 = -13;
    var res2 = test_heappushpop_help_function(items2, item2);
    assert_almost_equal(res2, gold2);
    var items3 = [5, 4, 3, 2, 1];
    var item3 = 0;
    var gold3 = 0;
    var res3 = test_heappushpop_help_function(items3, item3);
    assert_almost_equal(res3, gold3);
    var items4 = [4.7, 8, -1.2, 7.2];
    var item4 = 9;
    var gold4 = -1.2;
    var res4 = test_heappushpop_help_function(items4, item4);
    assert_almost_equal(res4, gold4);
}
function test_heapreplace_help_function(x, i) {
    heapify(x);
    var a = heapreplace(x, i);
    var b = heappop(x);
    return [a, b];
}
function test_heapreplace() {
    var items1 = [6, 1, -2, 5];
    var item1 = -5;
    var gold1 = [-2, -5];
    var res1 = test_heapreplace_help_function(items1, item1);
    assert_iter_almost_equal(res1, gold1);
    var items2 = [34, -3, -12, 0];
    var item2 = -13;
    var gold2 = [-12, -13];
    var res2 = test_heapreplace_help_function(items2, item2);
    assert_iter_almost_equal(res2, gold2);
    var items3 = [5, 4, 3, 2, 1];
    var item3 = 0;
    var gold3 = [1, 0];
    var res3 = test_heapreplace_help_function(items3, item3);
    assert_iter_almost_equal(res3, gold3);
    var items4 = [4.7, 8, -1.2, 7.2];
    var item4 = 9;
    var gold4 = [-1.2, 4.7];
    var res4 = test_heapreplace_help_function(items4, item4);
    assert_iter_almost_equal(res4, gold4);
}
function test_merge() {
    var items11 = [1, 3, 5, 7];
    var items12 = [0, 2, 4, 8];
    var items13 = [5, 10, 15, 20];
    var items14 = [];
    var items15 = [25];
    var gold1 = [0, 1, 2, 3, 4, 5, 5, 7, 8, 10, 15, 20, 25];
    var res1 = Array.from(merge(false, items11, items12, items13, items14, items15));
    assert_iter_almost_equal(res1, gold1);
    var items21 = [7, 5, 3, 1];
    var items22 = [8, 4, 2, 0];
    var gold2 = [8, 7, 5, 4, 3, 2, 1, 0];
    var res2 = Array.from(merge(true, items21, items22));
    assert_iter_almost_equal(res2, gold2);
}
function test_nsmallest() {
    var items1 = [];
    var gold1 = [];
    var res1 = nsmallest(1, items1);
    assert_iter_almost_equal(res1, gold1);
    var items6 = [1, 2, 3];
    var gold2 = [1];
    var res2 = nsmallest(1, items6);
    assert_iter_almost_equal(res2, gold2);
    var items7 = [1, 2, 3];
    var gold3 = [];
    var res3 = nsmallest(0, items7);
    assert_iter_almost_equal(res3, gold3);
    var items4 = [1, 2, 3];
    var gold4 = [1, 2, 3];
    var res4 = nsmallest(4, items4);
    assert_iter_almost_equal(res4, gold4);
    var items5 = [6, 1, -2, 5];
    var gold5 = [-2];
    var res5 = nsmallest(1, items5);
    assert_iter_almost_equal(res5, gold5);
    var items6 = [34, -3, -12, 0];
    var gold6 = [-12, -3];
    var res6 = nsmallest(2, items6);
    assert_iter_almost_equal(res6, gold6);
    var items7 = [5, 4, 3, 2, 1];
    var gold7 = [1, 2];
    var res7 = nsmallest(2, items7);
    assert_iter_almost_equal(res7, gold7);
    var items8 = [4.7, 8, -1.2, 7.2];
    var gold8 = [-1.2, 4.7];
    var res8 = nsmallest(2, items8);
    assert_iter_almost_equal(res8, gold8);
}
function test_nlargest() {
    var items1 = [];
    var gold1 = [];
    var res1 = nlargest(1, items1);
    assert_iter_almost_equal(res1, gold1);
    var items2 = [1, 2, 3];
    var gold2 = [3];
    var res2 = nlargest(1, items2);
    assert_iter_almost_equal(res2, gold2);
    var items3 = [1, 2, 3];
    var gold3 = [];
    var res3 = nlargest(0, items3);
    assert_iter_almost_equal(res3, gold3);
    var items4 = [1, 2, 3];
    var gold4 = [3, 2, 1];
    var res4 = nlargest(4, items4);
    assert_iter_almost_equal(res4, gold4);
    var items5 = [6, 1, -2, 5];
    var gold5 = [6];
    var res5 = nlargest(1, items5);
    assert_iter_almost_equal(res5, gold5);
    var items6 = [34, -3, -12, 0];
    var gold6 = [34, 0];
    var res6 = nlargest(2, items6);
    assert_iter_almost_equal(res6, gold6);
    var items7 = [5, 4, 3, 2, 1];
    var gold7 = [5, 4];
    var res7 = nlargest(2, items7);
    assert_iter_almost_equal(res7, gold7);
    var items8 = [4.7, 8, -1.2, 7.2];
    var gold8 = [8, 7.2];
    var res8 = nlargest(2, items8);
    assert_iter_almost_equal(res8, gold8);
}
function additional_tests() {
    var items1 = [1];
    var gold1 = 1;
    var res1 = heappop(items1);
    assert_almost_equal(res1, gold1);
    var items2 = [1];
    var gold2 = 1;
    var res2 = _heappop_max(items2);
    assert_almost_equal(res2, gold2);
    var items3 = [1];
    var gold3 = [];
    var res3 = nsmallest(0, items3);
    assert_iter_almost_equal(res3, gold3);
    var items4 = [];
    var gold4 = [];
    var res4 = nsmallest(2, items4);
    assert_iter_almost_equal(res4, gold4);
    var items5 = [];
    var gold5 = [];
    var res5 = nsmallest(0, items5);
    assert_iter_almost_equal(res5, gold5);
    var items6 = [1];
    var gold6 = [];
    var res6 = nlargest(0, items6);
    assert_iter_almost_equal(res6, gold6);
    var items7 = [];
    var gold7 = [];
    var res7 = nlargest(2, items7);
    assert_iter_almost_equal(res7, gold7);
    var items8 = [];
    var gold8 = [];
    var res8 = nlargest(0, items8);
    assert_iter_almost_equal(res8, gold8);
    var items9 = [1, 2, 3];
    var gold9 = [3, 2, 1];
    _siftup_max(items9, 0);
    assert_iter_almost_equal(items9, gold9);
}
function test_init() {
    var items1 = [6, 1, -2, 5];
    heapify(items1);
    _siftdown_max(items1, 0, 1);
    _siftdown(items1, 0, 1);
    _siftup_max(items1, 0);
    _siftup(items1, 0);
    var items2 = [6, 1, -2, 5];
    heapify(items2);
    var item21 = _heappop_max(items2);
    var item22 = heappop(items2);
}
function test() {
    test_init();
    test_nsmallest();
    test_nlargest();
    additional_tests();
    test_heappush();
    test_heapify();
    test_heappushpop();
    test_heapreplace();
    test_merge();
}
test();
