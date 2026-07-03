const INPUT_SHANGHAI = "SH";
const INPUT_SHANGHAI_CITY = "SHC";


function SkelClass(class_name) {
    var _class_var = {};
    _class_var._class_name = class_name;
    return _class_var;
}







function assert_equal(a, b) {
    if (a !== b) {
        throw new Error("Assertion failed");
    }
}
function StringDistance(...args) {
    function StringDistance_dlm_distance(s0, s1) {
        return null;
    }
    var class_var = SkelClass('StringDistance');
    class_var.distance = StringDistance_dlm_distance;
    return class_var;
}
function NormalizedStringDistance(...args) {
    function NormalizedStringDistance_dlm_distance(s0, s1) {
        return null;
    }
    var class_var = StringDistance(...args);
    class_var._class_name = 'NormalizedStringDistance;' + class_var._class_name;
    class_var.distance = NormalizedStringDistance_dlm_distance;
    return class_var;
}
function MetricStringDistance(...args) {
    function MetricStringDistance_dlm_distance(s0, s1) {
        return null;
    }
    var class_var = StringDistance(...args);
    class_var._class_name = 'MetricStringDistance;' + class_var._class_name;
    class_var.distance = MetricStringDistance_dlm_distance;
    return class_var;
}
function Levenshtein(...args) {
    function Levenshtein_dlm_distance(s0, s1) {
        if (s0 === s1) {
            return 0.0;
        }
        if (s0.length === 0) {
            var _retval = s1.length;
            return _retval;
        }
        var v0 = new Array(s1.length + 1).fill(0);
        var v1 = new Array(s1.length + 1).fill(0);
        for (var i = 0; i < v0.length; i++) {
            v0[i] = i;
        }
        for (var i = 0; i < s0.length; i++) {
            v1[0] = i + 1;
            for (var j = 0; j < s1.length; j++) {
                var cost = 1;
                if (s0[i] === s1[j]) {
                    cost = 0;
                }
                v1[j + 1] = Math.min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost);
            }
            var temp = v0;
            v0 = v1;
            v1 = temp;
        }
        var _retval = v0[s1.length];
        return _retval;
    }
    var class_var = MetricStringDistance(...args);
    class_var._class_name = 'Levenshtein;' + class_var._class_name;
    class_var.distance = Levenshtein_dlm_distance;
    return class_var;
}
function LongestCommonSubsequence(...args) {
    function LongestCommonSubsequence_dlm_distance(s0, s1) {
        if (s0 === s1) {
            return 0.0;
        }
        var _retval = s0.length + s1.length - 2 * class_var.length(s0, s1);
        return _retval;
    }
    function length(s0, s1) {
        var s0_len = s0.length;
        var s1_len = s1.length;
        var x = s0.slice();
        var y = s1.slice();
        var matrix = Array.from({ length: s0_len + 1 }, () => Array(s1_len + 1).fill(0));
        for (var i = 1; i < s0_len + 1; i++) {
            for (var j = 1; j < s1_len + 1; j++) {
                if (x[i - 1] === y[j - 1]) {
                    matrix[i][j] = matrix[i - 1][j - 1] + 1;
                } else {
                    matrix[i][j] = Math.max(matrix[i][j - 1], matrix[i - 1][j]);
                }
            }
        }
        var _retval = matrix[s0_len][s1_len];
        return _retval;
    }
    var class_var = StringDistance(...args);
    class_var._class_name = 'LongestCommonSubsequence;' + class_var._class_name;
    class_var.distance = LongestCommonSubsequence_dlm_distance;
    class_var.length = length;
    return class_var;
}
function MetricLCS() {
    function MetricLCS_dlm___init__() {
        class_var.lcs = new LongestCommonSubsequence();
    }
    function MetricLCS_dlm_distance(s0, s1) {
        if (s0 === s1) {
            return 0.0;
        }
        var max_len = Math.max(s0.length, s1.length);
        var _retval = 1.0 - (1.0 * class_var.lcs.length(s0, s1)) / max_len;
        return _retval;
    }
    var class_var = MetricStringDistance();
    class_var._class_name = 'MetricLCS;' + class_var._class_name;
    class_var.__init__ = MetricLCS_dlm___init__;
    class_var.distance = MetricLCS_dlm_distance;
    MetricLCS_dlm___init__();
    return class_var;
}
function NGram(param_0) {
    function NGram_dlm___init__(n) {
        class_var.n = n;
    }
    function NGram_dlm_distance(s0, s1) {
        if (s0 === s1) {
            return 0.0;
        }
        var special = '\n';
        var sl = s0.length;
        var tl = s1.length;
        if (sl === 0 || tl === 0) {
            return 1.0;
        }
        var cost = 0;
        var sa = Array(sl + class_var.n - 1).fill('');
        for (var i = 0; i < sa.length; i++) {
            if (i < class_var.n - 1) {
                sa[i] = special;
            } else {
                sa[i] = s0[i - class_var.n + 1];
            }
        }
        var p = Array(sl + 1).fill(0.0);
        var d = Array(sl + 1).fill(0.0);
        var t_j = Array(class_var.n).fill('');
        for (var i = 0; i < sl + 1; i++) {
            p[i] = 1.0 * i;
        }
        for (var j = 1; j < tl + 1; j++) {
            if (j < class_var.n) {
                for (var ti = 0; ti < class_var.n - j; ti++) {
                    t_j[ti] = special;
                }
                for (var ti = class_var.n - j; ti < class_var.n; ti++) {
                    t_j[ti] = s1[ti - (class_var.n - j)];
                }
            } else {
                t_j = s1.slice(j - class_var.n, j);
            }
            d[0] = 1.0 * j;
            for (var i = 1; i < sl + 1; i++) {
                cost = 0;
                var tn = class_var.n;
                for (var ni = 0; ni < class_var.n; ni++) {
                    var _idxsa = i - 1 + ni;
                    _idxsa = (_idxsa + sa.length) % sa.length;
                    if (sa[_idxsa] !== t_j[ni]) {
                        cost += 1;
                    } else if (sa[_idxsa] === special) {
                        tn -= 1;
                    }
                }
                var ec = cost / tn;
                var _idxd = i - 1;
                _idxd = (_idxd + d.length) % d.length;
                var _idxp = i - 1;
                _idxp = (_idxp + p.length) % p.length;
                d[i] = Math.min(d[_idxd] + 1, p[i] + 1, p[_idxp] + ec);
            }
            var temp = p;
            p = d;
            d = temp;
        }
        var _retval = p[sl] / Math.max(tl, sl);
        return _retval;
    }
    var class_var = NormalizedStringDistance();
    class_var._class_name = 'NGram;' + class_var._class_name;
    class_var.__init__ = NGram_dlm___init__;
    class_var.distance = NGram_dlm_distance;
    NGram_dlm___init__(param_0);
    return class_var;
}
function Damerau(...args) {
    function Damerau_dlm_distance(s0, s1) {
        if (s0 === s1) {
            return 0.0;
        }
        var inf = s0.length + s1.length;
        var da = {};
        for (var i = 0; i < s0.length; i++) {
            da[s0[i]] = '0';
        }
        for (var i = 0; i < s1.length; i++) {
            da[s1[i]] = '0';
        }
        var h = [];
        for (var _ = 0; _ < s0.length + 2; _++) {
            h.push(new Array(s1.length + 2).fill(0));
        }
        for (var i = 0; i < s0.length + 1; i++) {
            h[i + 1][0] = inf;
            h[i + 1][1] = i;
        }
        for (var j = 0; j < s1.length + 1; j++) {
            h[0][j + 1] = inf;
            h[1][j + 1] = j;
        }
        for (var i = 1; i < s0.length + 1; i++) {
            var db = 0;
            for (var j = 1; j < s1.length + 1; j++) {
                var i1 = parseInt(da[s1[j - 1]]);
                var j1 = db;
                var cost = 1;
                if (s0[i - 1] === s1[j - 1]) {
                    cost = 0;
                    db = j;
                }
                h[i + 1][j + 1] = Math.min(h[i][j] + cost, h[i + 1][j] + 1, h[i][j + 1] + 1, h[i1][j1] + (i - i1 - 1) + 1 + (j - j1 - 1));
            }
            da[s0[i - 1]] = i.toString();
        }
        var _retval = h[s0.length + 1][s1.length + 1];
        return _retval;
    }
    var class_var = MetricStringDistance(...args);
    class_var._class_name = 'Damerau;' + class_var._class_name;
    class_var.distance = Damerau_dlm_distance;
    return class_var;
}
function ShingleBased(param_0) {
    function ShingleBased_dlm___init__(k) {
        class_var.k = k;
    }
    function get_k() {
        return class_var.k;
    }
    function get_profile(string) {
        var shingles = {};
        var no_space_str = string.replace(/\s+/g, " ");
        for (var i = 0; i < no_space_str.length - class_var.k + 1; i++) {
            var shingle = no_space_str.substring(i, i + class_var.k);
            var old = shingles[shingle];
            if (old) {
                shingles[shingle] = old + 1;
            } else {
                shingles[shingle] = 1;
            }
        }
        return shingles;
    }
    var class_var = SkelClass('ShingleBased');
    class_var.__init__ = ShingleBased_dlm___init__;
    class_var.get_k = get_k;
    class_var.get_profile = get_profile;
    ShingleBased_dlm___init__(param_0);
    return class_var;
}
function StringSimilarity(...args) {
    function StringSimilarity_dlm_similarity(s0, s1) {
        return null;
    }
    var class_var = SkelClass('StringSimilarity');
    class_var.similarity = StringSimilarity_dlm_similarity;
    return class_var;
}
function NormalizedStringSimilarity(...args) {
    function NormalizedStringSimilarity_dlm_similarity(s0, s1) {
        return null;
    }
    var class_var = StringSimilarity(...args);
    class_var._class_name = 'NormalizedStringSimilarity;' + class_var._class_name;
    class_var.similarity = NormalizedStringSimilarity_dlm_similarity;
    return class_var;
}
function Cosine(param_0) {
    function Cosine_dlm___init__(k) {
    }
    function Cosine_dlm_distance(s0, s1) {
        var _retval = 1.0 - class_var.similarity(s0, s1);
        return _retval;
    }
    function Cosine_dlm_similarity(s0, s1) {
        if (s0 === s1) {
            return 1.0;
        }
        var _cvk = class_var.get_k();
        if (s0.length < _cvk || s1.length < _cvk) {
            return 0.0;
        }
        var profile0 = class_var.get_profile(s0);
        var profile1 = class_var.get_profile(s1);
        var _cvn0 = class_var._norm(profile0);
        var _cvn1 = class_var._norm(profile1);
        var _retval = class_var._dot_product(profile0, profile1) / (_cvn0 * _cvn1);
        return _retval;
    }
    function _dot_product(profile0, profile1) {
        var small = profile1;
        var large = profile0;
        if (Object.keys(profile0).length < Object.keys(profile1).length) {
            small = profile0;
            large = profile1;
        }
        var agg = 0.0;
        for (var k in small) {
            var v = small[k];
            var i = large[k];
            if (!i) {
                continue;
            }
            agg += 1.0 * v * i;
        }
        return agg;
    }
    function _norm(profile) {
        var agg = 0.0;
        for (var k in profile) {
            var v = profile[k];
            agg += 1.0 * v * v;
        }
        var _retval = Math.sqrt(agg);
        return _retval;
    }
    var class_var = ShingleBased(param_0);
    class_var._class_name = 'Cosine;' + class_var._class_name;
    class_var.__init__ = Cosine_dlm___init__;
    class_var.distance = Cosine_dlm_distance;
    class_var.similarity = Cosine_dlm_similarity;
    class_var._dot_product = _dot_product;
    class_var._norm = _norm;
    Cosine_dlm___init__(param_0);
    return class_var;
}
function Jaccard(param_0) {
    function Jaccard_dlm___init__(k) {
    }
    function Jaccard_dlm_distance(s0, s1) {
        var _retval = 1.0 - class_var.similarity(s0, s1);
        return _retval;
    }
    function Jaccard_dlm_similarity(s0, s1) {
        if (s0 === s1) {
            return 1.0;
        }
        var _cvk = class_var.get_k();
        if (s0.length < _cvk || s1.length < _cvk) {
            return 0.0;
        }
        var profile0 = class_var.get_profile(s0);
        var profile1 = class_var.get_profile(s1);
        var union = new Set();
        for (var ite in profile0) {
            union.add(ite);
        }
        for (var ite in profile1) {
            union.add(ite);
        }
        var inter = Object.keys(profile0).length + Object.keys(profile1).length - union.size;
        var _retval = 1.0 * inter / union.size;
        return _retval;
    }
    var class_var = ShingleBased(param_0);
    class_var._class_name = 'Jaccard;' + class_var._class_name;
    class_var.__init__ = Jaccard_dlm___init__;
    class_var.distance = Jaccard_dlm_distance;
    class_var.similarity = Jaccard_dlm_similarity;
    Jaccard_dlm___init__(param_0);
    return class_var;
}
function JaroWinkler(param_0) {
    function JaroWinkler_dlm___init__(threshold) {
        class_var.threshold = threshold;
        class_var.three = 3;
        class_var.jw_coef = 0.1;
    }
    function get_threshold() {
        return class_var.threshold;
    }
    function JaroWinkler_dlm_similarity(s0, s1) {
        if (s0 === s1) {
            return 1.0;
        }
        var mtp = class_var.matches(s0, s1);
        var m = mtp[0];
        if (m === 0) {
            return 0.0;
        }
        var j = (m / s0.length + m / s1.length + (m - mtp[1]) / m) / class_var.three;
        var jw = j;
        if (j > class_var.get_threshold()) {
            jw = j + Math.min(class_var.jw_coef, 1.0 / mtp[class_var.three]) * mtp[2] * (1 - j);
        }
        return jw;
    }
    function JaroWinkler_dlm_distance(s0, s1) {
        var _retval = 1.0 - class_var.similarity(s0, s1);
        return _retval;
    }
    function matches(s0, s1) {
        var max_str = s1;
        var min_str = s0;
        var ran = Math.floor(Math.max(max_str.length / 2 - 1, 0));
        var match_indexes = Array(min_str.length).fill(-1);
        var match_flags = Array(max_str.length).fill(false);
        var matches = 0;
        for (var mi = 0; mi < min_str.length; mi++) {
            var c1 = min_str[mi];
            for (var xi = Math.max(mi - ran, 0); xi < Math.min(mi + ran + 1, max_str.length); xi++) {
                if (!match_flags[xi] && c1 === max_str[xi]) {
                    match_indexes[mi] = xi;
                    match_flags[xi] = true;
                    matches++;
                    break;
                }
            }
        }
        var ms0 = Array(matches).fill(0);
        var ms1 = Array(matches).fill(0);
        var si = 0;
        for (var i = 0; i < min_str.length; i++) {
            if (match_indexes[i] !== -1) {
                ms0[si] = min_str[i];
                si++;
            }
        }
        si = 0;
        for (var j = 0; j < max_str.length; j++) {
            if (match_flags[j]) {
                ms1[si] = max_str[j];
                si++;
            }
        }
        var transpositions = 0;
        var prefix = 0;
        for (var mi = 0; mi < min_str.length; mi++) {
            if (s0[mi] === s1[mi]) {
                prefix++;
            }
        }
        var _retval = [matches, Math.floor(transpositions / 2), prefix, max_str.length];
        return _retval;
    }
    var class_var = NormalizedStringSimilarity();
    class_var._class_name = 'JaroWinkler;' + class_var._class_name;
    class_var.__init__ = JaroWinkler_dlm___init__;
    class_var.get_threshold = get_threshold;
    class_var.similarity = JaroWinkler_dlm_similarity;
    class_var.distance = JaroWinkler_dlm_distance;
    class_var.matches = matches;
    JaroWinkler_dlm___init__(param_0);
    return class_var;
}
function NormalizedLevenshtein() {
    function NormalizedLevenshtein_dlm___init__() {
        class_var.levenshtein = new Levenshtein();
    }
    function NormalizedLevenshtein_dlm_distance(s0, s1) {
        if (s0 === s1) {
            return 0.0;
        }
        var m_len = Math.max(s0.length, s1.length);
        var _retval = class_var.levenshtein.distance(s0, s1) / m_len;
        return _retval;
    }
    function NormalizedLevenshtein_dlm_similarity(s0, s1) {
        var _retval = 1.0 - class_var.distance(s0, s1);
        return _retval;
    }
    var class_var = NormalizedStringDistance();
    class_var._class_name = 'NormalizedLevenshtein;' + class_var._class_name;
    class_var.__init__ = NormalizedLevenshtein_dlm___init__;
    class_var.distance = NormalizedLevenshtein_dlm_distance;
    class_var.similarity = NormalizedLevenshtein_dlm_similarity;
    NormalizedLevenshtein_dlm___init__();
    return class_var;
}
function OptimalStringAlignment(...args) {
    function OptimalStringAlignment_dlm_distance(s0, s1) {
        if (s0 === s1) {
            return 0.0;
        }
        var n = s0.length;
        var m = s1.length;
        if (n === 0) {
            var _retval = 1.0 * n;
            return _retval;
        }
        var d = Array.from({ length: n + 2 }, () => Array(m + 2).fill(0));
        for (var i = 0; i < n + 1; i++) {
            d[i][0] = i;
        }
        for (var j = 0; j < m + 1; j++) {
            d[0][j] = j;
        }
        for (var i = 1; i < n + 1; i++) {
            for (var j = 1; j < m + 1; j++) {
                var cost = 1;
                if (s0[i - 1] === s1[j - 1]) {
                    cost = 0;
                }
                d[i][j] = Math.min(d[i - 1][j - 1] + cost, d[i][j - 1] + 1, d[i - 1][j] + 1);
            }
        }
        var _retval = d[n][m];
        return _retval;
    }
    var class_var = StringDistance(...args);
    class_var._class_name = 'OptimalStringAlignment;' + class_var._class_name;
    class_var.distance = OptimalStringAlignment_dlm_distance;
    return class_var;
}
function OverlapCoefficient(param_0) {
    function OverlapCoefficient_dlm___init__(k) {
    }
    function OverlapCoefficient_dlm_distance(s0, s1) {
        var _retval = 1.0 - class_var.similarity(s0, s1);
        return _retval;
    }
    function OverlapCoefficient_dlm_similarity(s0, s1) {
        var union = new Set();
        var profile0 = class_var.get_profile(s0);
        var profile1 = class_var.get_profile(s1);
        for (var k in profile0) {
            union.add(k);
        }
        for (var k in profile1) {
            union.add(k);
        }
        var inter = Object.keys(profile0).length + Object.keys(profile1).length - union.size;
        var _retval = inter / Math.min(Object.keys(profile0).length, Object.keys(profile1).length);
        return _retval;
    }
    var class_var = ShingleBased(param_0);
    class_var._class_name = 'OverlapCoefficient;' + class_var._class_name;
    class_var.__init__ = OverlapCoefficient_dlm___init__;
    class_var.distance = OverlapCoefficient_dlm_distance;
    class_var.similarity = OverlapCoefficient_dlm_similarity;
    OverlapCoefficient_dlm___init__(param_0);
    return class_var;
}
function QGram(param_0) {
    function QGram_dlm___init__(k) {
    }
    function QGram_dlm_distance(s0, s1) {
        if (s0 === s1) {
            return 0.0;
        }
        var profile0 = class_var.get_profile(s0);
        var profile1 = class_var.get_profile(s1);
        var _retval = class_var.distance_profile(profile0, profile1);
        return _retval;
    }
    function distance_profile(profile0, profile1) {
        var union = new Set();
        for (var k in profile0) {
            union.add(k);
        }
        for (var k in profile1) {
            union.add(k);
        }
        var agg = 0;
        var _sorted_union = Array.from(union).sort();
        for (var k of _sorted_union) {
            var v0 = 0;
            var v1 = 0;
            if (profile0[k] !== undefined) {
                v0 = parseInt(profile0[k]);
            }
            if (profile1[k] !== undefined) {
                v1 = parseInt(profile1[k]);
            }
            agg += Math.abs(v0 - v1);
        }
        return agg;
    }
    var class_var = ShingleBased(param_0);
    class_var._class_name = 'QGram;' + class_var._class_name;
    class_var.__init__ = QGram_dlm___init__;
    class_var.distance = QGram_dlm_distance;
    class_var.distance_profile = distance_profile;
    QGram_dlm___init__(param_0);
    return class_var;
}
function SIFT4Options(param_0) {
    function SIFT4Options_dlm___init__(options) {
        function _code0(x) {
            var _retval = Array.from(x);
            return _retval;
        }
        function _code1(t1, t2) {
            var _retval = t1 === t2;
            return _retval;
        }
        function _code2(t1, t2) {
            return 1;
        }
        function _code3(x) {
            return x;
        }
        function _code4(c1, c2) {
            return 1;
        }
        function _code5(lcss, trans) {
            var _retval = lcss - trans;
            return _retval;
        }
        class_var.options = {'maxdistance': 0, 'tokenizer': _code0, 'tokenmatcher': _code1, 'matchingevaluator': _code2, 'locallengthevaluator': _code3, 'transpositioncostevaluator': _code4, 'transpositionsevaluator': _code5};
        if (typeof options === 'object' && options !== null && Object.keys(options).length === 1 && Object.prototype.hasOwnProperty.call(options, 'maxdistance')) {
            if (typeof options['maxdistance'] !== 'number') {
                throw new Error("Assertion failed");
            }
            class_var.options['maxdistance'] = options['maxdistance'];
        }
        class_var.maxdistance = class_var.options['maxdistance'];
        class_var.tokenizer = class_var.options['tokenizer'];
        class_var.tokenmatcher = class_var.options['tokenmatcher'];
        class_var.matchingevaluator = class_var.options['matchingevaluator'];
        class_var.locallengthevaluator = class_var.options['locallengthevaluator'];
        class_var.transpositioncostevaluator = class_var.options['transpositioncostevaluator'];
        class_var.transpositionsevaluator = class_var.options['transpositionsevaluator'];
    }
    var class_var = MetricStringDistance();
    class_var._class_name = 'SIFT4Options;' + class_var._class_name;
    class_var.__init__ = SIFT4Options_dlm___init__;
    SIFT4Options_dlm___init__(param_0);
    return class_var;
}
function SIFT4(...args) {
    function SIFT4_dlm_distance(s1, s2, maxoffset, options) {
        options = new SIFT4Options(options);
        var t1 = options.tokenizer(s1);
        var t2 = options.tokenizer(s2);
        var l1 = t1.length;
        var l2 = t2.length;
        var c1 = 0, c2 = 0, lcss = 0, local_cs = 0, trans = 0, offset_arr = [];
        while (c1 < l1 && c2 < l2) {
            if (options.tokenmatcher(t1[c1], t2[c2])) {
                local_cs += options.matchingevaluator(t1[c1], t2[c2]);
                var isTrans = false;
                var i = 0;
                while (i < offset_arr.length) {
                    var ofs = offset_arr[i];
                    if (c1 <= ofs['c1'] || c2 <= ofs['c2']) {
                        isTrans = Math.abs(c2 - c1) >= Math.abs(ofs['c2'] - ofs['c1']);
                        if (isTrans) {
                            trans += options.transpositioncostevaluator(c1, c2);
                        } else if (!ofs['trans']) {
                            ofs['trans'] = true;
                            trans += options.transpositioncostevaluator(ofs.c1, ofs.c2);
                        }
                        break;
                    } else if (c1 > ofs['c2'] && c2 > ofs['c1']) {
                        offset_arr.splice(i, 1);
                    } else {
                        i++;
                    }
                }
                offset_arr.push({ c1: c1, c2: c2, trans: isTrans });
            } else {
                lcss += options.locallengthevaluator(local_cs);
                local_cs = 0;
                if (c1 !== c2) {
                    c1 = c2 = Math.min(c1, c2);
                }
                for (i = 0; i < maxoffset; i++) {
                    if (c1 + i < l1 || c2 + i < l2) {
                        if (c1 + i < l1 && options.tokenmatcher(t1[c1 + i], t2[c2])) {
                            c1 += i - 1;
                            c2 -= 1;
                            break;
                        }
                    }
                    if (c2 + i < l2 && options.tokenmatcher(t1[c1], t2[c2 + i])) {
                        c1 -= 1;
                        c2 += i - 1;
                        break;
                    }
                }
            }
            c1++;
            c2++;
            if (c1 >= l1 || c2 >= l2) {
                lcss += options.locallengthevaluator(local_cs);
                local_cs = 0;
                c1 = c2 = Math.min(c1, c2);
            }
        }
        lcss += options.locallengthevaluator(local_cs);
        var _olle = options.locallengthevaluator(Math.max(l1, l2));
        var _ote = options.transpositionsevaluator(lcss, trans);
        var _retval = Math.round(_olle - _ote);
        return _retval;
    }
    var class_var = SkelClass('SIFT4');
    class_var.distance = SIFT4_dlm_distance;
    return class_var;
}
function SorensenDice(param_0) {
    function SorensenDice_dlm___init__(k) {
    }
    function SorensenDice_dlm_distance(s0, s1) {
        var _retval = 1.0 - class_var.similarity(s0, s1);
        return _retval;
    }
    function SorensenDice_dlm_similarity(s0, s1) {
        var union = new Set();
        var profile0 = class_var.get_profile(s0);
        var profile1 = class_var.get_profile(s1);
        for (var k in profile0) {
            union.add(k);
        }
        for (var k in profile1) {
            union.add(k);
        }
        var inter = Object.keys(profile0).length + Object.keys(profile1).length - union.size;
        var _retval = 2.0 * inter / (Object.keys(profile0).length + Object.keys(profile1).length);
        return _retval;
    }
    var class_var = ShingleBased(param_0);
    class_var._class_name = 'SorensenDice;' + class_var._class_name;
    class_var.__init__ = SorensenDice_dlm___init__;
    class_var.distance = SorensenDice_dlm_distance;
    class_var.similarity = SorensenDice_dlm_similarity;
    SorensenDice_dlm___init__(param_0);
    return class_var;
}
function default_insertion_cost(char) {
    return 1.0;
}
function default_deletion_cost(char) {
    return 1.0;
}
function default_substitution_cost(char_a, char_b) {
    return 1.0;
}
function WeightedLevenshtein(param_0, param_1, param_2) {
    function WeightedLevenshtein_dlm___init__(substitution_cost_fn, insertion_cost_fn, deletion_cost_fn) {
        class_var.substitution_cost_fn = substitution_cost_fn;
        class_var.insertion_cost_fn = insertion_cost_fn;
        class_var.deletion_cost_fn = deletion_cost_fn;
    }
    function WeightedLevenshtein_dlm_distance(s0, s1) {
        if (s0 === s1) {
            return 0.0;
        }
        if (s0.length === 0) {
            var _retval = s1.split('').reduce(function (cost, char) { return cost + class_var.insertion_cost_fn(char); }, 0);
            return _retval;
        }
        var v0 = new Array(s1.length + 1).fill(0.0);
        var v1 = new Array(s1.length + 1).fill(0.0);
        v0[0] = 0;
        for (var i = 1; i < v0.length; i++) {
            v0[i] = v0[i - 1] + class_var.insertion_cost_fn(s1[i - 1]);
        }
        for (var i = 0; i < s0.length; i++) {
            var s0i = s0[i];
            var deletion_cost = class_var.deletion_cost_fn(s0i);
            v1[0] = v0[0] + deletion_cost;
            for (var j = 0; j < s1.length; j++) {
                var s1j = s1[j];
                var cost = 0;
                if (s0i !== s1j) {
                    cost = class_var.substitution_cost_fn(s0i, s1j);
                }
                var insertion_cost = class_var.insertion_cost_fn(s1j);
                v1[j + 1] = Math.min(v1[j] + insertion_cost, v0[j + 1] + deletion_cost, v0[j] + cost);
            }
            var temp = v0;
            v0 = v1;
            v1 = temp;
        }
        var _retval = v0[s1.length];
        return _retval;
    }
    var class_var = StringDistance();
    class_var._class_name = 'WeightedLevenshtein;' + class_var._class_name;
    class_var.__init__ = WeightedLevenshtein_dlm___init__;
    class_var.distance = WeightedLevenshtein_dlm_distance;
    WeightedLevenshtein_dlm___init__(param_0, param_1, param_2);
    return class_var;
}
function test_levenshtein() {
    var a = Levenshtein();
    var s0 = "";
    var s1 = "";
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s0, s1);
    assert_equal(res, 0.0);
    res = a.distance(s0, s2);
    assert_equal(res, 2);
    res = a.distance(s0, s3);
    assert_equal(res, 3);
    res = a.distance(s1, s2);
    assert_equal(res, 2);
    res = a.distance(s1, s3);
    assert_equal(res, 3);
    res = a.distance(s2, s3);
    assert_equal(res, 1);
}
function test_longest_common_subsequence() {
    var a = LongestCommonSubsequence();
    var s0 = "";
    var s1 = "";
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s0, s1);
    assert_equal(res, 0);
    res = a.distance(s0, s2);
    assert_equal(res, 2);
    res = a.distance(s0, s3);
    assert_equal(res, 3);
    res = a.distance(s2, s3);
    assert_equal(res, 1);
    res = a.length(s2, s3);
    assert_equal(res, 2);
    res = a.distance('AGCAT', 'GAC');
    assert_equal(res, 4);
    res = a.length('AGCAT', 'GAC');
    assert_equal(res, 2);
}
function test_metric_lcs() {
    var a = MetricLCS();
    var s0 = "";
    var s1 = "";
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s0, s1);
    assert_equal(res, 0.0);
    res = a.distance(s0, s2);
    assert_equal(res, 1.0);
    res = a.distance(s0, s3);
    assert_equal(res, 1.0);
    res = a.distance(s1, s2);
    assert_equal(res, 1.0);
    res = a.distance(s1, s3);
    assert_equal(res, 1.0);
    res = a.distance(s2, s3);
    assert_equal(Math.round(res * 100) / 100, 0.33);
}
function test_ngram() {
    var a = NGram(2);
    var s0 = "";
    var s1 = "";
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s0, s1);
    assert_equal(res, 0.0);
    res = a.distance(s0, s2);
    assert_equal(res, 1.0);
    res = a.distance(s0, s3);
    assert_equal(res, 1.0);
    res = a.distance(s1, s2);
    assert_equal(res, 1.0);
    res = a.distance(s1, s3);
    assert_equal(res, 1.0);
    res = a.distance(s2, s3);
    assert_equal(Math.round(res * 100) / 100, 0.33);
}
function test_damerau() {
    var a = Damerau();
    var s0 = "";
    var s1 = "";
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s0, s1);
    assert_equal(res, 0.0);
    res = a.distance(s0, s2);
    assert_equal(res, 2);
    res = a.distance(s0, s3);
    assert_equal(res, 3);
    res = a.distance(s1, s2);
    assert_equal(res, 2);
    res = a.distance(s1, s3);
    assert_equal(res, 3);
    res = a.distance(s2, s3);
    assert_equal(res, 1);
}
function test_cosine() {
    var cos = Cosine(1);
    var s = ['', ' ', 'Shanghai', 'ShangHai', 'Shang Hai'];
    var res = cos.distance(s[0], s[0]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[0], s[0]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = cos.distance(s[0], s[1]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[0], s[1]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.distance(s[0], s[2]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[0], s[2]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.distance(s[0], s[3]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[0], s[3]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.distance(s[0], s[4]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[0], s[4]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.distance(s[1], s[1]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[1], s[1]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = cos.distance(s[1], s[2]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[1], s[2]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.distance(s[1], s[3]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[1], s[3]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.distance(s[1], s[4]);
    assert_equal(0.6985, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[1], s[4]);
    assert_equal(0.3015, parseFloat(res.toFixed(4)));
    res = cos.distance(s[2], s[2]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[2], s[2]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = cos.distance(s[2], s[3]);
    assert_equal(0.0871, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[2], s[3]);
    assert_equal(0.9129, parseFloat(res.toFixed(4)));
    res = cos.distance(s[2], s[4]);
    assert_equal(0.1296, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[2], s[4]);
    assert_equal(0.8704, parseFloat(res.toFixed(4)));
    res = cos.distance(s[3], s[3]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[3], s[3]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = cos.distance(s[3], s[4]);
    assert_equal(0.0465, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[3], s[4]);
    assert_equal(0.9535, parseFloat(res.toFixed(4)));
    res = cos.distance(s[4], s[4]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = cos.similarity(s[4], s[4]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
}
function test_jaccard() {
    var jaccard = Jaccard(1);
    var s = ['', ' ', 'Shanghai', 'ShangHai', 'Shang Hai'];
    var res = jaccard.distance(s[0], s[0]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[0], s[0]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[0], s[1]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[0], s[1]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[0], s[2]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[0], s[2]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[0], s[3]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[0], s[3]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[0], s[4]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[0], s[4]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[1], s[1]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[1], s[1]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[1], s[2]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[1], s[2]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[1], s[3]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[1], s[3]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[1], s[4]);
    assert_equal(0.8750, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[1], s[4]);
    assert_equal(0.1250, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[2], s[2]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[2], s[2]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[2], s[3]);
    assert_equal(0.1429, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[2], s[3]);
    assert_equal(0.8571, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[2], s[4]);
    assert_equal(0.2500, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[2], s[4]);
    assert_equal(0.7500, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[3], s[3]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[3], s[3]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[3], s[4]);
    assert_equal(0.1250, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[3], s[4]);
    assert_equal(0.8750, parseFloat(res.toFixed(4)));
    res = jaccard.distance(s[4], s[4]);
    assert_equal(0.0000, parseFloat(res.toFixed(4)));
    res = jaccard.similarity(s[4], s[4]);
    assert_equal(1.0000, parseFloat(res.toFixed(4)));
}
function test_jarowinkler() {
    var a = new JaroWinkler(0.7);
    var s0 = "";
    var s1 = "";
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s0, s1);
    assert_equal(res, 0.0);
    res = a.distance(s0, s2);
    assert_equal(res, 1.0);
    res = a.distance(s0, s3);
    assert_equal(res, 1.0);
    res = a.distance(s1, s2);
    assert_equal(res, 1.0);
    res = a.distance(s1, s3);
    assert_equal(res, 1.0);
    res = a.distance(s2, s3);
    assert_equal(Math.round(res * 10000) / 10000, 0.0889);
    res = a.similarity(s0, s1);
    assert_equal(res, 1.0);
    res = a.similarity(s0, s2);
    assert_equal(res, 0.0);
    res = a.similarity(s0, s3);
    assert_equal(res, 0.0);
    res = a.similarity(s1, s2);
    assert_equal(res, 0.0);
    res = a.similarity(s1, s3);
    assert_equal(res, 0.0);
    res = a.similarity(s2, s3);
    assert_equal(Math.round(res * 10000) / 10000, 0.9111);
}
function test_normalized_levenshtein() {
    var a = new NormalizedLevenshtein();
    var s0 = "";
    var s1 = "";
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s0, s1);
    assert_equal(res, 0.0);
    res = a.distance(s0, s2);
    assert_equal(res, 1.0);
    res = a.distance(s0, s3);
    assert_equal(res, 1.0);
    res = a.distance(s1, s2);
    assert_equal(res, 1.0);
    res = a.distance(s1, s3);
    assert_equal(res, 1.0);
    res = a.distance(s2, s3);
    assert_equal(Math.round(res * 100) / 100, 0.33);
    res = a.similarity(s0, s1);
    assert_equal(res, 1.0);
    res = a.similarity(s0, s2);
    assert_equal(res, 0.0);
    res = a.similarity(s0, s3);
    assert_equal(res, 0.0);
    res = a.similarity(s1, s2);
    assert_equal(res, 0.0);
    res = a.similarity(s1, s3);
    assert_equal(res, 0.0);
    res = a.similarity(s2, s3);
    assert_equal(Math.round(res * 100) / 100, 0.67);
}
function test_optimal_string_alignment() {
    var a = OptimalStringAlignment();
    var s0 = "";
    var s1 = "";
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s0, s1);
    assert_equal(res, 0.0);
    res = a.distance(s0, s2);
    assert_equal(res, 0.0);
    res = a.distance(s0, s3);
    assert_equal(res, 0.0);
    res = a.distance(s1, s2);
    assert_equal(res, 0.0);
    res = a.distance(s1, s3);
    assert_equal(res, 0.0);
    res = a.distance(s2, s3);
    assert_equal(Math.round(res * 100) / 100, 1);
}
function test_overlap_coefficient_0() {
    var sim = OverlapCoefficient(3);
    var s1 = "eat";
    var s2 = "eating";
    var actual = sim.distance(s1, s2);
    assert_equal(0, actual);
}
function test_overlap_coefficient_1() {
    var sim = OverlapCoefficient(3);
    var s1 = "eat";
    var s2 = "eating";
    var actual = sim.similarity(s1, s2);
    assert_equal(1, actual);
}
function test_overlap_coefficient_2() {
    var sim = OverlapCoefficient(3);
    var s1 = "eat";
    var s2 = "eating";
    var actual = sim.similarity(s1, s2);
    assert_equal(1, actual);
}
function test_overlap_coefficient_3() {
    var sim = OverlapCoefficient(2);
    var s1 = "car";
    var s2 = "bar";
    var res = sim.similarity(s1, s2);
    assert_equal(1 / 2, res);
    res = sim.distance(s1, s2);
    assert_equal(1 / 2, res);
}
function test_qgram() {
    var a = QGram(1);
    var s0 = "";
    var s1 = "";
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s0, s1);
    assert_equal(res, 0.0);
    res = a.distance(s0, s2);
    assert_equal(res, 2);
    res = a.distance(s0, s3);
    assert_equal(res, 3);
    res = a.distance(s1, s2);
    assert_equal(res, 2);
    res = a.distance(s1, s3);
    assert_equal(res, 3);
    res = a.distance(s2, s3);
    assert_equal(res, 1);
}
function test_sift4() {
    var s = SIFT4();
    var results = [['This is the first string', 'And this is another string', 5, 11.0], ['Lorem ipsum dolor sit amet, consectetur adipiscing elit.', 'Amet Lorm ispum dolor sit amet, consetetur adixxxpiscing elit.', 10, 12.0]];
    for (var [a, b, offset, res] of results) {
        var comp = s.distance(a, b, offset, null);
        assert_equal(res, comp);
    }
}
function test_sorensen_dice() {
    var a = SorensenDice(2);
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s2, s3);
    assert_equal(Math.round(res * 100) / 100, 0.33);
    res = a.similarity(s2, s3);
    assert_equal(Math.round(res * 100) / 100, 0.67);
}
function test_weighted_levenshtein() {
    var a = WeightedLevenshtein(default_substitution_cost, default_insertion_cost, default_deletion_cost);
    var s0 = "";
    var s1 = "";
    var s2 = INPUT_SHANGHAI;
    var s3 = INPUT_SHANGHAI_CITY;
    var res = a.distance(s0, s1);
    assert_equal(res, 0.0);
    res = a.distance(s0, s2);
    assert_equal(res, 2);
    res = a.distance(s0, s3);
    assert_equal(res, 3);
    res = a.distance(s1, s2);
    assert_equal(res, 2);
    res = a.distance(s1, s3);
    assert_equal(res, 3);
    res = a.distance(s2, s3);
    assert_equal(res, 1);
}
function additional_tests() {
    var s = StringDistance();
    var tmp = s.distance("a", "b");
    assert_equal(tmp, null);
    s = NormalizedLevenshtein();
    tmp = s.distance("a", "b");
    assert_equal(tmp, 1.0);
    s = OptimalStringAlignment();
    tmp = s.distance("a", "b");
    assert_equal(tmp, 1);
    s = NormalizedStringDistance();
    tmp = s.distance("a", "b");
    assert_equal(tmp, null);
    s = SIFT4();
    var results = [['This is the first string', 'And this is another string', 5, 11.0], ['Lorem ipsum dolor sit amet, consectetur adipiscing elit.', 'Amet Lorm ispum dolor sit amet, consetetur adixxxpiscing elit.', 10, 12.0]];
    var options = { "maxdistance": 0 };
    for (var [a, b, offset, res] of results) {
        var comp = s.distance(a, b, offset, options);
        assert_equal(res, comp);
    }
    s = MetricStringDistance();
    tmp = s.distance("a", "b");
    assert_equal(tmp, null);
    s = Cosine(1);
    tmp = s.distance("a", "b");
    assert_equal(tmp, 1.0);
    s = NormalizedStringSimilarity();
    tmp = s.similarity("a", "b");
    assert_equal(tmp, null);
    s = StringSimilarity();
    tmp = s.similarity("a", "b");
    assert_equal(tmp, null);
}
function test_init() {
    // default_*_cost
    default_deletion_cost('a');
    default_insertion_cost('a');
    default_substitution_cost('a', 'b');

    // Levenshtein
    var lev = Levenshtein();
    var d = lev.distance('a', 'a');
    d = lev.distance('', 'a');
    d = lev.distance('ab', 'bb');

    // LongestCommonSubsequence
    var lcs = LongestCommonSubsequence();
    var le = lcs.length('ab', 'ab');
    d = lcs.distance('a', 'a');
    d = lcs.distance('ab', 'bb');

    // MetricLCS
    var mlcs = MetricLCS();
    d = mlcs.distance('a', 'a');
    d = mlcs.distance('a', '');

    // NGram
    var ngram = NGram(2);
    d = ngram.distance('a', 'a');
    d = ngram.distance('', 'a');
    d = ngram.distance('ab', 'bb');

    // Damerau
    var damerau = Damerau();
    d = damerau.distance('a', 'a');
    d = damerau.distance('aa', 'ab');

    // ShingleBased
    var s = ShingleBased(1);
    var k = s.get_k();
    var p = s.get_profile('abcc');

    // Cosine(ShingleBased)
    var cos1 = Cosine(1);
    var p1 = cos1.get_profile('abc');
    var n1 = cos1._norm(p1);
    var p2 = cos1.get_profile('abde');
    var d1 = cos1._dot_product(p1, p2);
    var cos2 = Cosine(2);
    var s2 = cos2.similarity('a', 'a');
    s2 = cos2.similarity('a', 'b');
    s2 = cos2.similarity('aaa', 'bbb');
    var d2 = cos2.distance('aaa', 'bbb');

    // Jaccard(ShingleBased)
    var jaccard1 = Jaccard(2);
    var s1 = jaccard1.similarity('a', 'a');
    s1 = jaccard1.similarity('a', 'b');
    s1 = jaccard1.similarity('aaa', 'bbb');
    d1 = jaccard1.distance('a', 'b');

    // JaroWinkler
    var jw = JaroWinkler(0.7);
    var t = jw.get_threshold();
    var m = jw.matches('abc', 'abc');
    s = jw.similarity('a', 'a');
    s = jw.similarity('a', 'b');
    s = jw.similarity('abc', 'abd');
    d = jw.distance('a', 'a');

    // NormalizedLevenshtein
    var nlev = NormalizedLevenshtein();
    d = nlev.distance('a', 'a');
    d = nlev.distance('', 'a');
    s = nlev.similarity('a', '');

    // OptimalStringAlignment
    var osa = OptimalStringAlignment();
    d = osa.distance('a', 'a');
    d = osa.distance('', 'a');
    d = osa.distance('ab', 'bb');

    // OverlapCoefficient(ShingleBased)
    var oc = OverlapCoefficient(1);
    s = oc.similarity('a', 'b');
    d = oc.distance('a', 'b');

    // QGram(ShingleBased)
    var qgram = QGram(1);
    p1 = qgram.get_profile('a');
    p2 = qgram.get_profile('b');
    var dp = qgram.distance_profile(p1, p2);
    d = qgram.distance('a', 'a');
    d = qgram.distance('a', 'b');

    // SIFT4Options
    var options = SIFT4Options({'maxdistance': 5});
    var tokens = options.tokenizer('a');
    var is_match = options.tokenmatcher('a', 'a');
    var match_score = options.matchingevaluator('a', 'a');
    var local_length = options.locallengthevaluator(5);
    var transposition_cost = options.transpositioncostevaluator(1, 2);
    var transposition_score = options.transpositionsevaluator(5, 2);

    // SIFT4
    s = SIFT4();
    d = s.distance('This is the first string', 'And this is another string', 5, options);
    d = s.distance('abc', 'abc', 5, options);
    d = s.distance('abc', 'abd', 5, options);

    // SorensenDice(ShingleBased)
    var sd = SorensenDice(1);
    s = sd.similarity('a', 'a');
    d = sd.distance('a', 'a');

    // WeightedLevenshtein
    var wl = WeightedLevenshtein(default_substitution_cost, default_insertion_cost, default_deletion_cost);
    d = wl.distance('a', 'a');
    d = wl.distance('', 'a');
    d = wl.distance('ab', 'bb');
}
function test() {
    test_init();
    test_levenshtein();
    test_longest_common_subsequence();
    test_metric_lcs();
    test_ngram();
    test_damerau();
    test_cosine();
    test_jaccard();
    test_jarowinkler();
    test_normalized_levenshtein();
    test_optimal_string_alignment();
    test_overlap_coefficient_0();
    test_overlap_coefficient_1();
    test_overlap_coefficient_2();
    test_overlap_coefficient_3();
    test_qgram();
    test_sift4();
    test_sorensen_dice();
    test_weighted_levenshtein();
    additional_tests();
}
test();
