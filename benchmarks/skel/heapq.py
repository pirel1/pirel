import os


def _compare(a, b):
    return (a > b) - (a < b)




def assert_almost_equal(a, b):
    if abs(a - b) > 0.0001:
        raise Exception('Assertion failed: abs(a - b) <= 0.0001')
def assert_iter_almost_equal(iter1, iter2):
    if len(iter1) != len(iter2):
        raise Exception('Assertion failed')
    for i in range(len(iter1)):
        elem_a = iter1[i]
        elem_b = iter2[i]
        assert_almost_equal(elem_a, elem_b)
def heappush(heap, item):
    heap.append(item)
    _siftdown(heap, 0, len(heap) - 1)
def heappop(heap):
    lastelt = heap.pop()
    if len(heap) > 0:
        returnitem = heap[0]
        heap[0] = lastelt
        _siftup(heap, 0)
        return returnitem
    return lastelt
def heapreplace(heap, item):
    returnitem = heap[0]
    heap[0] = item
    _siftup(heap, 0)
    return returnitem
def heappushpop(heap, item):
    if len(heap) > 0 and heap[0] < item:
        temp = item
        item = heap[0]
        heap[0] = temp
        _siftup(heap, 0)
    return item
def heapify(x):
    n = len(x)
    for i in range((n // 2) - 1, -1, -1):
        _siftup(x, i)
def _heappop_max(heap):
    lastelt = heap.pop()
    if len(heap) > 0:
        returnitem = heap[0]
        heap[0] = lastelt
        _siftup_max(heap, 0)
        return returnitem
    return lastelt
def _heapreplace_max(heap, item):
    returnitem = heap[0]
    heap[0] = item
    _siftup_max(heap, 0)
    return returnitem
def _heapify_max(x):
    n = len(x)
    for i in range((n // 2) - 1, -1, -1):
        _siftup_max(x, i)
def _siftdown(heap, startpos, pos):
    newitem = heap[pos]
    while pos > startpos:
        parentpos = (pos - 1) >> 1
        parent = heap[parentpos]
        if _compare(parent, newitem) > 0:
            heap[pos] = parent
            pos = parentpos
            continue
        break
    heap[pos] = newitem
def _siftup(heap, pos):
    endpos = len(heap)
    startpos = pos
    newitem = heap[pos]
    childpos = 2 * pos + 1
    while childpos < endpos:
        rightpos = childpos + 1
        if rightpos < endpos:
            if _compare(heap[childpos], heap[rightpos]) >= 0:
              childpos = rightpos
        heap[pos] = heap[childpos]
        pos = childpos
        childpos = 2 * pos + 1
    heap[pos] = newitem
    _siftdown(heap, startpos, pos)
def _siftdown_max(heap, startpos, pos):
    newitem = heap[pos]
    while pos > startpos and heap[(pos - 1) >> 1] < newitem:
        parentpos = (pos - 1) >> 1
        heap[pos] = heap[parentpos]
        pos = parentpos
    heap[pos] = newitem
def _siftup_max(heap, pos):
    endpos = len(heap)
    startpos = pos
    newitem = heap[pos]
    childpos = 2 * pos + 1
    while childpos < endpos:
        rightpos = childpos + 1
        if rightpos < endpos:
            if heap[rightpos] >= heap[childpos]:
                childpos = rightpos
        heap[pos] = heap[childpos]
        pos = childpos
        childpos = 2 * pos + 1
    heap[pos] = newitem
    _siftdown_max(heap, startpos, pos)
def merge(reverse, *iterables):
    h = []
    _heapify = None
    _heappop = None
    _heapreplace = None
    direction = None
    if reverse:
        _heapify = _heapify_max
        _heappop = _heappop_max
        _heapreplace = _heapreplace_max
        direction = -1
    else:
        _heapify = heapify
        _heappop = heappop
        _heapreplace = heapreplace
        direction = 1
    for (order, it) in enumerate(map(iter, iterables)):
        try:
            next = it.__next__
            h.append([next(), order * direction, next])
        except StopIteration:
            pass
    _heapify(h)
    while len(h) > 1:
        try:
            while True:
                (value, order, next) = s = h[0]
                yield value
                s[0] = next()
                _heapreplace(h, s)
        except StopIteration:
            _heappop(h)
    if h:
        (value, order, next) = h[0]
        yield value
        yield from next.__self__
    return
def nsmallest(n, iterable):
    if n == 1:
        if len(iterable) == 0:
            return []
        _return_val = [min(iterable)]
        return _return_val
    if n == 0:
        return []
    _try_success = False
    try:
        size = len(iterable)
        _try_success = True
    except:
        pass
    if _try_success:
        if n >= size:
            return sorted(iterable)[:n]
    it = iter(iterable)
    result = []
    for i in range(n):
        elem = next(it)
        result.append((elem, i))
    if len(result) == 0:
        return result
    _heapify_max(result)
    top = result[0][0]
    order = n
    _heapreplace = _heapreplace_max
    for elem in it:
        if elem < top:
            _heapreplace(result, (elem, order))
            top = result[0][0]
            order += 1
    result.sort()
    _return_val = []
    for i in range(len(result)):
        elem = result[i][0]
        _return_val.append(elem)
    return _return_val
def nlargest(n, iterable):
    if n == 1:
        if len(iterable) == 0:
            return []
        _return_val = [max(iterable)]
        return _return_val
    if n == 0:
        return []
    _try_success = False
    try:
        size = len(iterable)
        _try_success = True
    except:
        pass
    if _try_success:
        if n >= size:
            return sorted(iterable, reverse=True)[:n]
    it = iter(iterable)
    result = []
    for i in range(n):
        elem = next(it)
        result.append((elem, -i))
    if len(result) == 0:
        return result
    heapify(result)
    top = result[0][0]
    order = -n
    _heapreplace = heapreplace
    for elem in it:
        if top < elem:
            _heapreplace(result, (elem, order))
            top = result[0][0]
            order = result[0][1]
            order -= 1
    result.sort(reverse=True)
    _return_val = []
    for i in range(len(result)):
        elem = result[i][0]
        _return_val.append(elem)
    return _return_val
def test_heappush_help_function(items):
    heap = []
    for item in items:
        heappush(heap, item)
    a = heappop(heap)
    b = heappop(heap)
    return [a, b]
def test_heappush():
    items1 = [6, 1, -2, 5]
    gold1 = [-2, 1]
    res1 = test_heappush_help_function(items1)
    assert_iter_almost_equal(res1, gold1)
    items2 = [34, -3, -12, 0]
    gold2 = [-12, -3]
    res2 = test_heappush_help_function(items2)
    assert_iter_almost_equal(res2, gold2)
    items3 = [5, 4, 3, 2, 1]
    gold3 = [1, 2]
    res3 = test_heappush_help_function(items3)
    assert_iter_almost_equal(res3, gold3)
    items4 = [4.7, 8, -1.2, 7.2]
    gold4 = [-1.2, 4.7]
    res4 = test_heappush_help_function(items4)
    assert_iter_almost_equal(res4, gold4)
def test_heapify_help_function(x):
    heapify(x)
    a = heappop(x)
    b = heappop(x)
    return [a, b]
def test_heapify():
    items1 = [6, 1, -2, 5]
    gold1 = [-2, 1]
    res1 = test_heapify_help_function(items1)
    assert_iter_almost_equal(res1, gold1)
    items2 = [34, -3, -12, 0]
    gold2 = [-12, -3]
    res2 = test_heapify_help_function(items2)
    assert_iter_almost_equal(res2, gold2)
    items3 = [5, 4, 3, 2, 1]
    gold3 = [1, 2]
    res3 = test_heapify_help_function(items3)
    assert_iter_almost_equal(res3, gold3)
    items4 = [4.7, 8, -1.2, 7.2]
    gold4 = [-1.2, 4.7]
    res4 = test_heapify_help_function(items4)
    assert_iter_almost_equal(res4, gold4)
def test_heappushpop_help_function(x, i):
    heapify(x)
    a = heappushpop(x, i)
    return a
def test_heappushpop():
    items1 = [6, 1, -2, 5]
    item1 = -5
    gold1 = -5
    res1 = test_heappushpop_help_function(items1, item1)
    assert_almost_equal(res1, gold1)
    items2 = [34, -3, -12, 0]
    item2 = -13
    gold2 = -13
    res2 = test_heappushpop_help_function(items2, item2)
    assert_almost_equal(res2, gold2)
    items3 = [5, 4, 3, 2, 1]
    item3 = 0
    gold3 = 0
    res3 = test_heappushpop_help_function(items3, item3)
    assert_almost_equal(res3, gold3)
    items4 = [4.7, 8, -1.2, 7.2]
    item4 = 9
    gold4 = -1.2
    res4 = test_heappushpop_help_function(items4, item4)
    assert_almost_equal(res4, gold4)
def test_heapreplace_help_function(x, i):
    heapify(x)
    a = heapreplace(x, i)
    b = heappop(x)
    return [a, b]
def test_heapreplace():
    items1 = [6, 1, -2, 5]
    item1 = -5
    gold1 = [-2, -5]
    res1 = test_heapreplace_help_function(items1, item1)
    assert_iter_almost_equal(res1, gold1)
    items2 = [34, -3, -12, 0]
    item2 = -13
    gold2 = [-12, -13]
    res2 = test_heapreplace_help_function(items2, item2)
    assert_iter_almost_equal(res2, gold2)
    items3 = [5, 4, 3, 2, 1]
    item3 = 0
    gold3 = [1, 0]
    res3 = test_heapreplace_help_function(items3, item3)
    assert_iter_almost_equal(res3, gold3)
    items4 = [4.7, 8, -1.2, 7.2]
    item4 = 9
    gold4 = [-1.2, 4.7]
    res4 = test_heapreplace_help_function(items4, item4)
    assert_iter_almost_equal(res4, gold4)
def test_merge():
    items11 = [1, 3, 5, 7]
    items12 = [0, 2, 4, 8]
    items13 = [5, 10, 15, 20]
    items14 = []
    items15 = [25]
    gold1 = [0, 1, 2, 3, 4, 5, 5, 7, 8, 10, 15, 20, 25]
    res1 = list(merge(False, items11, items12, items13, items14, items15))
    assert_iter_almost_equal(res1, gold1)
    items21 = [7, 5, 3, 1]
    items22 = [8, 4, 2, 0]
    gold2 = [8, 7, 5, 4, 3, 2, 1, 0]
    res2 = list(merge(True, items21, items22))
    assert_iter_almost_equal(res2, gold2)
def test_nsmallest():
    items1 = []
    gold1 = []
    res1 = nsmallest(1, items1)
    assert_iter_almost_equal(res1, gold1)
    items6 = [1, 2, 3]
    gold2 = [1]
    res2 = nsmallest(1, items6)
    assert_iter_almost_equal(res2, gold2)
    items7 = [1, 2, 3]
    gold3 = []
    res3 = nsmallest(0, items7)
    assert_iter_almost_equal(res3, gold3)
    items4 = [1, 2, 3]
    gold4 = [1, 2, 3]
    res4 = nsmallest(4, items4)
    assert_iter_almost_equal(res4, gold4)
    items5 = [6, 1, -2, 5]
    gold5 = [-2]
    res5 = nsmallest(1, items5)
    assert_iter_almost_equal(res5, gold5)
    items6 = [34, -3, -12, 0]
    gold6 = [-12, -3]
    res6 = nsmallest(2, items6)
    assert_iter_almost_equal(res6, gold6)
    items7 = [5, 4, 3, 2, 1]
    gold7 = [1, 2]
    res7 = nsmallest(2, items7)
    assert_iter_almost_equal(res7, gold7)
    items8 = [4.7, 8, -1.2, 7.2]
    gold8 = [-1.2, 4.7]
    res8 = nsmallest(2, items8)
    assert_iter_almost_equal(res8, gold8)
def test_nlargest():
    items5 = []
    gold1 = []
    res1 = nlargest(1, items5)
    assert_iter_almost_equal(res1, gold1)
    items2 = [1, 2, 3]
    gold2 = [3]
    res2 = nlargest(1, items2)
    assert_iter_almost_equal(res2, gold2)
    items3 = [1, 2, 3]
    gold3 = []
    res3 = nlargest(0, items3)
    assert_iter_almost_equal(res3, gold3)
    items4 = [1, 2, 3]
    gold4 = [3, 2, 1]
    res4 = nlargest(4, items4)
    assert_iter_almost_equal(res4, gold4)
    items5 = [6, 1, -2, 5]
    gold5 = [6]
    res5 = nlargest(1, items5)
    assert_iter_almost_equal(res5, gold5)
    items6 = [34, -3, -12, 0]
    gold6 = [34, 0]
    res6 = nlargest(2, items6)
    assert_iter_almost_equal(res6, gold6)
    items7 = [5, 4, 3, 2, 1]
    gold7 = [5, 4]
    res7 = nlargest(2, items7)
    assert_iter_almost_equal(res7, gold7)
    items8 = [4.7, 8, -1.2, 7.2]
    gold8 = [8, 7.2]
    res8 = nlargest(2, items8)
    assert_iter_almost_equal(res8, gold8)
def additional_tests():
    items1 = [1]
    gold1 = 1
    res1 = heappop(items1)
    assert_almost_equal(res1, gold1)
    items2 = [1]
    gold2 = 1
    res2 = _heappop_max(items2)
    assert_almost_equal(res2, gold2)
    items3 = [1]
    gold3 = []
    res3 = nsmallest(0, items3)
    assert_iter_almost_equal(res3, gold3)
    items4 = []
    gold4 = []
    res4 = nsmallest(2, items4)
    assert_iter_almost_equal(res4, gold4)
    items5 = []
    gold5 = []
    res5 = nsmallest(0, items5)
    assert_iter_almost_equal(res5, gold5)
    items6 = [1]
    gold6 = []
    res6 = nlargest(0, items6)
    assert_iter_almost_equal(res6, gold6)
    items7 = []
    gold7 = []
    res7 = nlargest(2, items7)
    assert_iter_almost_equal(res7, gold7)
    items8 = []
    gold8 = []
    res8 = nlargest(0, items8)
    assert_iter_almost_equal(res8, gold8)
    items9 = [1, 2, 3]
    gold9 = [3, 2, 1]
    _siftup_max(items9, 0)
    assert_iter_almost_equal(items9, gold9)
def test_init():
    items1 = [6, 1, -2, 5]
    heapify(items1)
    _siftdown_max(items1, 0, 1)
    _siftdown(items1, 0, 1)
    _siftup_max(items1, 0)
    _siftup(items1, 0)
    items2 = [6, 1, -2, 5]
    heapify(items2)
    item21 = _heappop_max(items2)
    item22 = heappop(items2)
def test():
    test_init()
    test_nsmallest()
    test_nlargest()
    additional_tests()
    test_heappush()
    test_heapify()
    test_heappushpop()
    test_heapreplace()
    test_merge()
test()
