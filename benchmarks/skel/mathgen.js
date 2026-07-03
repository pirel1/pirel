const crypto = require('crypto');


var seed = 1;
function user_hash_random() {
    const hash = crypto.createHash('sha256');
    hash.update(seed.toString());
    seed += 1;
    const hex = hash.digest('hex');
    return parseInt(hex, 16) / (2 ** 256 - 1);
}
function user_randint(min, max) {
    return Math.floor(user_hash_random() * (max - min + 1)) + min;
}
function user_choice_func1(x) {
    if (user_hash_random() < 0.5) {
        return x[0];
    } else {
        return x[1];
    }
}
function user_choice_func2(x) {
    return x[Math.floor(user_hash_random() * x.length)];
}
function user_sample_func1(start, stop, n) {
    var x = Array.from({ length: stop - start }, (_, index) => start + index);
    var a = x[0];
    var b = x[x.length - 1] + 1;
    var lst = [];
    for (var i = 0; i < n; i++) {
        lst.push(Math.floor(user_hash_random() * (b - a + 1)) + a);
    }
    return lst;
}
function user_sample_func2(x, n) {
    x = Array.from(x);
    var lst = [];
    for (var i = 0; i < n; i++) {
        var index = Math.floor(user_hash_random() * x.length);
        lst.push(x[index]);
        x.splice(index, 1);
    }
    return lst;
}
function user_uniform(a, b) {
    return user_hash_random() * (b - a) + a;
}
function user_reset_seed() {
    seed = 1;
}





function assert_equal(a, b) {
    if (a !== b) {
        throw new Error('Assertion failed: a does not equal b');
    }
}
function assert_iter_equal(iter1, iter2) {
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
function absolute_difference(max_a = 100, max_b = 100) {
    var a = user_randint(-max_a, max_a);
    var b = user_randint(-max_b, max_b);
    var absDiff = Math.abs(a - b);
    var _retval = [`&|${a}-${b}|=&`, `&${absDiff}&`];
    return _retval;
}
function addition(max_sum = 99, max_addend = 50) {
    if (max_addend > max_sum) {
        max_addend = max_sum;
    }
    var a = user_randint(0, max_addend);
    var b = user_randint(0, Math.min((max_sum - a), max_addend));
    var c = a + b;
    var problem = `&${a}+${b}=&`;
    var solution = `&${c}&`;
    return [problem, solution];
}
function _compare_fractions_get_solution(first, second) {
    if (first > second) {
        return '>';
    }
    if (first < second) {
        return '<';
    }
    return '=';
}
function compare_fractions(max_val = 10) {
    var a = user_randint(1, max_val);
    var b = user_randint(1, max_val);
    var c = user_randint(1, max_val);
    var d = user_randint(1, max_val);
    while (a === b) {
        b = user_randint(1, max_val);
    }
    while (c === d) {
        d = user_randint(1, max_val);
    }
    var first = a / b;
    var second = c / d;
    var solution = _compare_fractions_get_solution(first, second);
    var problem = `Which symbol represents the comparison between &\\frac{${a}}{${b}}& and &\\frac{${c}}{${d}}&?`;
    return [problem, solution];
}
function cube_root(min_no = 1, max_no = 1000) {
    var b = user_randint(min_no, max_no);
    var a = Math.cbrt(b);
    var _retval = ["What is the cube root of: &\\sqrt[3]{" + b + "}=& to 2 decimal places?", "&" + a.toFixed(2) + "&"];
    return _retval;
}
function divide_fractions(max_val = 10) {
    function divide_fractions_dlm_calculate_gcd(x, y) {
        while (y) {
            var temp = x;
            x = y;
            y = temp % y;
        }
        return x;
    }
    var a = user_randint(1, max_val);
    var b = user_randint(1, max_val);
    while (a === b) {
        b = user_randint(1, max_val);
    }
    var c = user_randint(1, max_val);
    var d = user_randint(1, max_val);
    while (c === d) {
        d = user_randint(1, max_val);
    }
    var tmp_n = a * d;
    var tmp_d = b * c;
    var gcd = divide_fractions_dlm_calculate_gcd(tmp_n, tmp_d);
    var sol_numerator = Math.floor(tmp_n / gcd);
    var sol_denominator = Math.floor(tmp_d / gcd);
    return [`&\\frac{${a}}{${b}}\\div\\frac{${c}}{${d}}=&`, `&\\frac{${sol_numerator}}{${sol_denominator}}&`];
}
function division(max_a = 25, max_b = 25) {
    var a = user_randint(1, max_a);
    var b = user_randint(1, max_b);
    var divisor = a * b;
    var dividend = user_choice_func1([a, b]);
    var quotient = Math.floor(divisor / dividend);
    return ['&' + divisor + '\\div' + dividend + '=&', '&' + quotient + '&'];
}
function exponentiation(max_base = 20, max_expo = 10) {
    var base = user_randint(1, max_base);
    var expo = user_randint(1, max_expo);
    var _retval = [`&${base}^{${expo}}=&`, `&${Math.pow(base, expo)}&`];
    return _retval;
}
function factorial(max_input = 6) {
    var a = user_randint(0, max_input);
    var n = a;
    var b = 1;
    while (a != 1 && n > 0) {
        b *= n;
        n -= 1;
    }
    var _retval = [`&${a}! =&`, `&${b}&`];
    return _retval;
}
function fraction_multiplication(max_val = 10) {
    function fraction_multiplication_dlm_calculate_gcd(x, y) {
        while (y) {
            var temp = x;
            x = y;
            y = temp % y;
        }
        return x;
    }
    var a = user_randint(1, max_val);
    var b = user_randint(1, max_val);
    var c = user_randint(1, max_val);
    var d = user_randint(1, max_val);
    while (a == b) {
        b = user_randint(1, max_val);
    }
    while (c == d) {
        d = user_randint(1, max_val);
    }
    var tmp_n = a * c;
    var tmp_d = b * d;
    var gcd = fraction_multiplication_dlm_calculate_gcd(tmp_n, tmp_d);
    var problem = `&\\frac{${a}}{${b}}\\cdot\\frac{${c}}{${d}}=&`;
    var solution = `&\\frac{${Math.floor(tmp_n / gcd)}}{${Math.floor(tmp_d / gcd)}}&`;
    if (tmp_d == 1 || tmp_d == gcd) {
        solution = `&\\frac{${tmp_n}}{${gcd}}&`;
    }
    return [problem, solution];
}
function fraction_to_decimal(max_res = 99, max_divid = 99) {
    var a = user_randint(0, max_divid);
    var b = user_randint(1, Math.min(max_res, max_divid));
    var c = Math.round((a / b) * 100) / 100;
    var _retval = ['&' + a + '\\div' + b + '=&', '&' + c + '&'];
    return _retval;
}
function greatest_common_divisor(numbers_count = 2, max_num = 1000) {
    function greatestCommonDivisorOfTwoNumbers(number1, number2) {
        number1 = Math.abs(number1);
        number2 = Math.abs(number2);
        while (number2 > 0) {
            var temp = number1;
            number1 = number2;
            number2 = temp % number2;
        }
        return number1;
    }
    numbers_count = Math.max(numbers_count, 2);
    var numbers = [];
    for (var _i = 0; _i < numbers_count; _i++) {
        numbers.push(user_randint(0, max_num));
    }
    var greatestCommonDivisor = greatestCommonDivisorOfTwoNumbers(numbers[0], numbers[1]);
    for (var index = 1; index < numbers_count; index++) {
        greatestCommonDivisor = greatestCommonDivisorOfTwoNumbers(numbers[index], greatestCommonDivisor);
    }
    var fix_bug = numbers.map(num => num.toString()).join(",");
    var _retval = ['&GCD(' + fix_bug + ')=&', '&' + greatestCommonDivisor + '&'];
    return _retval;
}
function is_composite(max_num = 250) {
    var a = user_randint(2, max_num);
    var problem = "Is &" + a + "& composite?";
    if (a === 0 || a === 1) {
        return [problem, "No"];
    }
    for (var i = 2; i < a; i++) {
        if (a % i === 0) {
            return [problem, "Yes"];
        }
    }
    var solution = "No";
    return [problem, solution];
}
function is_prime(max_num = 100) {
    var a = user_randint(2, max_num);
    var problem = "Is &" + a + "& prime?";
    if (a === 2) {
        return [problem, "Yes"];
    }
    if (a % 2 === 0) {
        return [problem, "No"];
    }
    for (var i = 3; i <= Math.floor(a / 2) + 1; i += 2) {
        if (a % i === 0) {
            return [problem, "No"];
        }
    }
    var solution = "Yes";
    return [problem, solution];
}
function multiplication(max_multi = 12) {
    var a = user_randint(0, max_multi);
    var b = user_randint(0, max_multi);
    var c = a * b;
    var _retval = ['&' + a + '\\cdot' + b + '=&', '&' + c + '&'];
    return _retval;
}
function percentage(max_value = 99, max_percentage = 99) {
    var a = user_randint(1, max_percentage);
    var b = user_randint(1, max_value);
    var problem = "What is &" + a + "&% of &" + b + "&?";
    var percentage = a / 100 * b;
    var formatted_float = percentage.toFixed(2);
    var solution = "&" + formatted_float + "&";
    return [problem, solution];
}
function percentage_difference(max_value = 200, min_value = 0) {
    var value_a = user_randint(min_value, max_value);
    var value_b = user_randint(min_value, max_value);
    var diff = 2 * (Math.abs(value_a - value_b) / Math.abs(value_a + value_b)) * 100;
    diff = Math.round(diff * 100) / 100;
    var problem = "What is the percentage difference between &" + value_a + "& and &" + value_b + "&?";
    var solution = "&" + diff + "&%";
    return [problem, solution];
}
function percentage_error(max_value = 100, min_value = -100) {
    var observed_value = user_randint(min_value, max_value);
    var exact_value = user_randint(min_value, max_value);
    if (observed_value * exact_value < 0) {
        observed_value *= -1;
    }
    var error = (Math.abs(observed_value - exact_value) / Math.abs(exact_value)) * 100;
    error = Math.round(error * 100) / 100;
    var problem = "Find the percentage error when observed value equals &" + observed_value + "& and exact value equals &" + exact_value + "&.";
    var solution = "&" + error + "&%";
    return [problem, solution];
}
function power_of_powers(max_base = 50, max_power = 10) {
    var base = user_randint(1, max_base);
    var power1 = user_randint(1, max_power);
    var power2 = user_randint(1, max_power);
    var step = power1 * power2;
    var problem = "Simplify &" + base + "^{" + power1 + "^{" + power2 + "}}&";
    var solution = "&" + base + "^{" + step + "}&";
    return [problem, solution];
}
function square(max_square_num = 20) {
    var a = user_randint(1, max_square_num);
    var b = a ** 2;
    var _retval = [`&${a}^2=&`, `&${b}&`];
    return _retval;
}
function square_root(min_no = 1, max_no = 12) {
    var b = user_randint(min_no, max_no);
    var a = b ** 2;
    var _retval = [`&\\sqrt{${a}}=&`, `&${b}&`];
    return _retval;
}
function simplify_square_root(max_variable = 100) {
    var x = user_randint(1, max_variable);
    var y = x;
    var factors = {};
    var f = 2;
    while (x != 1) {
        if (x % f === 0) {
            if (!(f in factors)) {
                factors[f] = 0;
            }
            factors[f] += 1;
            x /= f;
        } else {
            f += 1;
        }
    }
    var a = 1;
    var b = 1;
    for (var i in factors) {
        if (factors[i] % 2 === 0) {
            a *= Math.pow(i, factors[i] / 2);
        } else {
            a *= Math.pow(i, (factors[i] - 1) / 2);
            b *= i;
        }
    }
    if (a === 1 || b === 1) {
        return simplify_square_root(max_variable);
    }
    var _retval = [`&\\sqrt{${y}}&`, `&${a}\\sqrt{${b}}&`];
    return _retval;
}
function subtraction(max_minuend = 99, max_diff = 99) {
    var a = user_randint(0, max_minuend);
    var b = user_randint(Math.max(0, a - max_diff), a);
    var c = a - b;
    var _retval = [`&${a}-${b}=&`, `&${c}&`];
    return _retval;
}
function bcd_to_decimal(max_number = 10000) {
    var n = user_randint(1000, max_number);
    var binstring = '';
    while (true) {
        var q = Math.floor(n / 10);
        var r = n % 10;
        var nibble = r.toString(2);
        while (nibble.length < 4) {
            nibble = '0' + nibble;
        }
        binstring = nibble + binstring;
        if (q === 0) {
            break;
        } else {
            n = q;
        }
    }
    var problem = "Integer of Binary Coded Decimal &" + n + " =& ";
    var solution = "&" + parseInt(binstring, 2) + "&";
    return [problem, solution];
}
function binary_2s_complement(maxDigits = 10) {
    var digits = user_randint(1, maxDigits);
    var question = Array.from({ length: digits }, function () { return String(user_randint(0, 1)); }).join('').replace(/^0+/, '');
    var answer = [];
    for (var i of question) {
        answer.push((1 - parseInt(i, 10)).toString());
    }
    var carry = true;
    var j = answer.length - 1;
    while (j >= 0) {
        if (answer[j] === '0') {
            answer[j] = '1';
            carry = false;
            break;
        }
        answer[j] = '0';
        j--;
    }
    var problem = "2^s complement of &" + question + " = &";
    var solution = answer.join('').replace(/^0+/, '');
    return [problem, "&" + solution + "&"];
}
function binary_complement_1s(maxDigits = 10) {
    var _nums = [];
    var _uri = user_randint(1, maxDigits);
    for (var i = 0; i < _uri; i++) {
        _nums.push(String(user_randint(0, 1)));
    }
    var question = _nums.join('');
    var answer = Array.from(question, function (digit) { return digit === "1" ? "0" : "1"; }).join('');
    var problem = `&${question} = &`;
    return [problem, `&${answer}&`];
}
function binary_to_decimal(max_dig = 10) {
    var _nums = [];
    var _uri = user_randint(1, max_dig);
    for (var i = 0; i < _uri; i++) {
        _nums.push(String(user_randint(0, 1)));
    }
    var problem = _nums.join('');
    var solution = '&' + parseInt(problem, 2) + '&';
    return ['&' + problem + '&', solution];
}
function binary_to_hex(max_dig = 10) {
    var _nums = [];
    var _uri = user_randint(1, max_dig);
    for (var i = 0; i < _uri; i++) {
        _nums.push(String(user_randint(0, 1)));
    }
    var problem = _nums.join('');
    var solution = '&0x' + parseInt(problem, 2).toString(16) + '&';
    return ['&' + problem + '&', solution];
}
function decimal_to_bcd(max_number = 10000) {
    var n = user_randint(1000, max_number);
    var x = n;
    var bcdstring = '';
    while (x > 0) {
        var nibble = x % 16;
        bcdstring = nibble.toString() + bcdstring;
        x >>= 4;
    }
    var problem = "BCD of Decimal Number &" + n + " = &";
    return [problem, '&' + bcdstring + '&'];
}
function decimal_to_binary(max_dec = 99) {
    var a = user_randint(1, max_dec);
    var b = a.toString(2);
    var problem = 'Binary of &' + a + ' = &';
    var solution = '&' + b + '&';
    return [problem, solution];
}
function decimal_to_hexadeci(max_dec = 1000) {
    var a = user_randint(0, max_dec);
    var b = (a < 0 ? "-0x" + (-a).toString(16) : "0x" + a.toString(16));
    var problem = "Hexadecimal of &" + a + " = &";
    var solution = "&" + b + "&";
    return [problem, solution];
}
function decimal_to_octal(max_decimal = 4096) {
    var x = user_randint(0, max_decimal);
    var problem = "The decimal number &" + x + "& in octal is: ";
    var solution = "&0o" + x.toString(8) + "&";
    return [problem, solution];
}
function fibonacci_series(min_no = 1) {
    function createFibList(n) {
        var list = [];
        for (var i = 0; i < n; i++) {
            if (i < 2) {
                list.push(i);
            } else {
                var val = list[i - 1] + list[i - 2];
                list.push(val);
            }
        }
        return list;
    }
    var n = user_randint(min_no, 20);
    var fibList = createFibList(n);
    var problem = "The Fibonacci Series of the first &" + n + "& numbers is ?";
    var solution = fibList.join(', ');
    return [problem, "&" + solution + "&"];
}
function modulo_division(max_res = 99, max_modulo = 99) {
    var a = user_randint(0, max_modulo);
    var b = user_randint(0, Math.min(max_res, max_modulo));
    var c = b !== 0 ? a % b : 0;
    var problem = `&${a}& % &${b}& = &`;
    var solution = `&${c}&`;
    return [problem, solution];
}
function nth_fibonacci_number(max_n = 100) {
    var gratio = (1 + Math.sqrt(5)) / 2;
    var n = user_randint(1, max_n);
    var problem = `What is the ${n}th Fibonacci number?`;
    var solution = Math.floor((Math.pow(gratio, n) - Math.pow(-gratio, -n)) / Math.sqrt(5));
    return [problem, "&" + solution + "&"];
}
function combinations(max_lengthgth = 20) {
    function combinations_dlm_factorial(n) {
        var result = 1;
        for (var i = 2; i < n + 1; i++) {
            result *= i;
        }
        return result;
    }
    var a = user_randint(10, max_lengthgth);
    var b = user_randint(0, 9);
    var _facta = combinations_dlm_factorial(a);
    var _factb = combinations_dlm_factorial(b);
    var _facta_b = combinations_dlm_factorial(a - b);
    var solution = parseInt(_facta / (_factb * _facta_b));
    var problem = "Find the number of combinations from &" + a + "& objects picked &" + b + "& at a time.";
    return [problem, "&" + solution + "&"];
}
function conditional_probability() {
    function BayesFormula(P_disease, true_positive, true_negative) {
        var P_notDisease = 100. - P_disease;
        var false_positive = 100. - true_negative;
        var P_plus = P_disease * true_positive + P_notDisease * false_positive;
        var P_disease_plus = true_positive * (100 * P_disease) / P_plus;
        return P_disease_plus;
    }
    var P_disease = Math.round(2. * user_hash_random() * 100) / 100;
    var _uhr1 = user_hash_random();
    var _uri1 = user_randint(90, 99);
    var true_positive = Math.round((_uhr1 + parseFloat(_uri1)) * 100) / 100;
    var _uhr2 = user_hash_random();
    var _uri2 = user_randint(90, 99);
    var true_negative = Math.round((_uhr2 + parseFloat(_uri2)) * 100) / 100;
    var answer = Math.round(BayesFormula(P_disease, true_positive, true_negative) * 100) / 100;
    var problem = "Someone tested positive for a nasty disease which only &" + P_disease.toFixed(2) + "&% of the population have. Test sensitivity (true positive) is equal to &SN=" + true_positive.toFixed(2) + "&% whereas test specificity (true negative) &SP=" + true_negative.toFixed(2) + "&%. What is the probability that this guy really has that disease?";
    var solution = '&' + answer + '&%';
    return [problem, solution];
}
function confidence_interval() {
    var n = user_randint(20, 40);
    var j = user_randint(0, 3);
    var lst = user_sample_func1(200, 300, n);
    var lst_per = [80, 90, 95, 99];
    var lst_t = [1.282, 1.645, 1.960, 2.576];
    var mean = 0;
    var sd = 0;
    for (var i of lst) {
        var count = i + mean;
        mean = count;
    }
    mean = mean / n;
    for (var i of lst) {
        var x = (i - mean) ** 2 + sd;
        sd = x;
    }
    sd = sd / n;
    var standard_error = lst_t[j] * Math.sqrt(sd / n);
    var upper = Math.round((mean + standard_error) * 100) / 100;
    var lower = Math.round((mean - standard_error) * 100) / 100;
    var problem = 'The confidence interval for sample &' + JSON.stringify(lst).replace(/,/g, ', ') + '& with &' + lst_per[j] + '&% confidence is';
    var solution = '&(' + upper + ', ' + lower + ')&';
    return [problem, solution];
}
function data_summary(number_values = 15, min_val = 5, max_val = 50) {
    var random_list = [];
    for (var i = 0; i < number_values; i++) {
        var n = user_randint(min_val, max_val);
        random_list.push(n);
    }
    var a = random_list.reduce((acc, val) => acc + val, 0);
    var mean = Math.round((a / number_values) * 100) / 100;
    mean = mean % 1 === 0 ? Math.trunc(mean) : mean;
    var _var = 0;
    for (var i = 0; i < number_values; i++) {
        _var += (random_list[i] - mean) ** 2;
    }
    var standardDeviation = Math.round((_var / number_values) * 100) / 100;
    var variance = Math.round((_var / number_values) ** 0.5 * 100) / 100;
    var tmp = random_list.map(elem => elem.toString()).join(', ');
    var problem = "Find the mean,standard deviation and variance for the data &" + tmp + "&";
    var solution = "The Mean is &" + mean + "&, Standard Deviation is &" + standardDeviation + "&, Variance is &" + variance + "&";
    return [problem, solution];
}
function _dice_sum_probability_get_count(a, b) {
    var count = 0;
    for (var i = 1; i < 7; i++) {
        if (a === 1) {
            if (i === b) {
                count = count + 1;
            }
            continue;
        }
        if (a === 2) {
            for (var j = 1; j < 7; j++) {
                if (i + j === b) {
                    count = count + 1;
                }
            }
            continue;
        }
        if (a === 3) {
            for (var j = 1; j < 7; j++) {
                for (var k = 1; k < 7; k++) {
                    if (i + j + k === b) {
                        count = count + 1;
                    }
                }
            }
        }
    }
    return count;
}
function dice_sum_probability(max_dice = 3) {
    var a = user_randint(1, max_dice);
    var b = user_randint(a, 6 * a);
    var count = _dice_sum_probability_get_count(a, b);
    var problem = "If &" + a + "& dice are rolled at the same time, the probability of getting a sum of &" + b + " =&";
    var solution = "\\frac{" + count + "}{" + Math.pow(6, a) + "}";
    return [problem, solution];
}
function mean_median(max_length = 10) {
    var randomlist = user_sample_func1(1, 99, max_length);
    var total = 0;
    for (var n of randomlist) {
        total = total + n;
    }
    var mean = total / 10;
    randomlist.sort((a, b) => a - b);
    var _randomlist_str = "[" + randomlist[0].toString();
    for (var i = 1; i < randomlist.length; i++) {
        _randomlist_str = _randomlist_str + ", " + randomlist[i].toString();
    }
    _randomlist_str = _randomlist_str + "]";
    var median = (randomlist[4] + randomlist[5]) / 2;
    median = median % 1 === 0 ? Math.trunc(median) : median;
    var problem = "Given the series of numbers &" + _randomlist_str + "&. Find the arithmatic mean and median of the series";
    var solution = "Arithmetic mean of the series is &" + mean + "& and arithmetic median of this series is &" + median + "&";
    return [problem, solution];
}
function permutation(max_lengthgth = 20) {
    function permutation_dlm_factorial(n) {
        var result = 1;
        for (var i = 2; i < n + 1; i++) {
            result *= i;
        }
        return result;
    }
    var a = user_randint(10, max_lengthgth);
    var b = user_randint(0, 9);
    var _facta = permutation_dlm_factorial(a);
    var _facta_b = permutation_dlm_factorial(a - b);
    var solution = Math.floor(_facta / _facta_b);
    var problem = "Number of Permutations from &" + a + "& objects picked &" + b + "& at a time is: ";
    return [problem, "&" + solution + "&"];
}
function angle_btw_vectors(max_elt_amt = 20) {
    var s = 0;
    var v1 = [];
    var _uri = user_randint(2, max_elt_amt);
    for (var i = 0; i < _uri; i++) {
        var _angle = Math.round(user_uniform(0, 1000) * 100) / 100;
        _angle = _angle % 1 === 0 ? Math.trunc(_angle) : _angle;
        v1.push(_angle);
    }
    var _v1_str = "[" + v1[0].toString();
    for (var i = 1; i < v1.length; i++) {
        _v1_str = _v1_str + ", " + v1[i].toString();
    }
    _v1_str = _v1_str + "]";
    var v2 = Array.from({ length: v1.length }, () => Math.round(user_uniform(0, 1000) * 100) / 100);
    for (var i = 0; i < v1.length; i++) {
        s += v1[i] * v2[i];
    }
    var _v2_str = "[" + v2[0].toString();
    for (var i = 1; i < v2.length; i++) {
        _v2_str = _v2_str + ", " + v2[i].toString();
    }
    _v2_str = _v2_str + "]";
    var mags = Math.sqrt(v1.reduce((acc, val) => acc + val * val, 0)) * Math.sqrt(v2.reduce((acc, val) => acc + val * val, 0));
    var solution = '';
    var ans = 0;
    try {
        ans = Math.round(Math.acos(s / mags) * 100) / 100;
        solution = ans + " radians";
    } catch (e) {
        console.log('angleBtwVectorsFunc has some issues with math module, line 16');
        solution = 'NaN';
        ans = 'NaN';
    }
    var problem = `angle between the vectors ${_v1_str} and ${_v2_str} is:`;
    return [problem, solution];
}
function angle_regular_polygon(min_val = 3, max_val = 20) {
    var sideNum = user_randint(min_val, max_val);
    var problem = `Find the angle of a regular polygon with ${sideNum} sides`;
    var exteriorAngle = Math.round((360 / sideNum) * 100) / 100;
    var solution = 180 - exteriorAngle;
    return [problem, solution];
}
function arc_length(max_radius = 49, max_angle = 359) {
    var radius = user_randint(1, max_radius);
    var angle = user_randint(1, max_angle);
    var angle_arc_length = parseFloat((angle / 360) * 2 * Math.PI * radius);
    var formatted_float = angle_arc_length.toFixed(5);
    var problem = "Given radius, " + radius + " and angle, " + angle + ". Find the arc length of the angle.";
    var solution = "Arc length of the angle = " + formatted_float;
    return [problem, solution];
}
function area_of_circle(max_radius = 100) {
    var r = user_randint(0, max_radius);
    var area = Math.round(Math.PI * r * r * 100) / 100;
    var problem = 'Area of circle with radius ' + r + '=';
    return [problem, area.toString()];
}
function area_of_circle_given_center_and_point(max_coordinate = 10, max_radius = 10) {
    var r = user_randint(0, max_radius);
    var center_x = user_randint(-max_coordinate, max_coordinate);
    var center_y = user_randint(-max_coordinate, max_coordinate);
    var angle = user_choice_func2([0, Math.floor(Math.PI / 6), Math.floor(Math.PI / 2), Math.PI, Math.PI + Math.floor(Math.PI / 6), 3 * Math.floor(Math.PI / 2)]);
    var point_x = center_x + Math.round(r * Math.cos(angle) * 100) / 100;
    var point_y = center_y + Math.round(r * Math.sin(angle) * 100) / 100;
    var area = Math.round(Math.PI * r * r * 100) / 100;
    var problem = "Area of circle with center (" + center_x + "," + center_y + ") and passing through (" + point_x + ", " + point_y + ") is";
    return [problem, area.toString()];
}
function area_of_triangle(max_a = 20, max_b = 20) {
    var a = user_randint(1, max_a);
    var b = user_randint(1, max_b);
    var c = user_randint(Math.abs(b - a) + 1, Math.abs(a + b) - 1);
    var s = (a + b + c) / 2;
    var area = Math.sqrt(s * (s - a) * (s - b) * (s - c));
    var problem = "Area of triangle with side lengths: " + a + ", " + b + ", " + c + " = ";
    var solution = Math.round(area * 100) / 100;
    return [problem, String(solution)];
}
function circumference(max_radius = 100) {
    var r = user_randint(0, max_radius);
    var circumference = Math.round(2 * Math.PI * r * 100) / 100;
    var problem = "Circumference of circle with radius " + r + " = ";
    return [problem, String(circumference)];
}
function complementary_and_supplementary_angle(max_supp = 180, max_comp = 90) {
    var angleType = user_choice_func2(["supplementary", "complementary"]);
    var angle = angleType === "supplementary" ? user_randint(1, max_supp) : user_randint(1, max_comp);
    var angleAns = angleType === "supplementary" ? 180 - angle : 90 - angle;
    var problem = "The " + angleType + " angle of " + angle + " =";
    return [problem, String(angleAns)];
}
function curved_surface_area_cylinder(max_radius = 49, max_height = 99) {
    var r = user_randint(1, max_radius);
    var h = user_randint(1, max_height);
    var csa = 2 * Math.PI * r * h;
    var formatted_float = Math.round(csa * 100) / 100;
    var problem = "What is the curved surface area of a cylinder of radius, " + r + " and height, " + h + "?";
    return [problem, String(formatted_float)];
}
function degree_to_rad(max_deg = 360) {
    var a = user_randint(0, max_deg);
    var b = (Math.PI * a) / 180;
    b = Math.round(b * 100) / 100;
    var problem = "Angle " + a + " degrees in radians is: ";
    return [problem, String(b)];
}
function _gcdEuclid(a, b) {
    while (b != 0) {
        var t = b;
        b = a % b;
        a = t;
    }
    return a;
}
function equation_of_line_from_two_points(max_coordinate = 20, min_coordinate = -20) {
    var x1 = user_randint(min_coordinate, max_coordinate);
    var x2 = user_randint(min_coordinate, max_coordinate);
    var y1 = user_randint(min_coordinate, max_coordinate);
    var y2 = user_randint(min_coordinate, max_coordinate);
    var coeff_y = (x2 - x1);
    var coeff_x = (y2 - y1);
    var constant = y2 * coeff_y - x2 * coeff_x;
    var gcd = _gcdEuclid(Math.abs(coeff_x), Math.abs(coeff_y));
    if (gcd != 1) {
        if (coeff_y > 0) {
            coeff_y = Math.floor(coeff_y / gcd);
        }
        if (coeff_x > 0) {
            coeff_x = Math.floor(coeff_x / gcd);
        }
        if (constant > 0) {
            constant = Math.floor(constant / gcd);
        }
        if (coeff_y < 0) {
            coeff_y = -Math.floor(-coeff_y / gcd);
        }
        if (coeff_x < 0) {
            coeff_x = -Math.floor(-coeff_x / gcd);
        }
        if (constant < 0) {
            constant = -Math.floor(-constant / gcd);
        }
    }
    if (coeff_y < 0) {
        coeff_y = -coeff_y;
        coeff_x = -coeff_x;
        constant = -constant;
    }
    if ([-1, 1].includes(coeff_x)) {
        if (coeff_x === 1) {
            coeff_x = '';
        } else {
            coeff_x = '-';
        }
    }
    if ([-1, 1].includes(coeff_y)) {
        if (coeff_y === 1) {
            coeff_y = '';
        } else {
            coeff_y = '-';
        }
    }
    var problem = "What is the equation of the line between points (" + x1 + "," + y1 + ") and (" + x2 + "," + y2 + ") in slope-intercept form?";
    var solution = "";
    if (coeff_x === 0) {
        solution = coeff_y + "y = " + constant;
    } else if (coeff_y === 0) {
        solution = coeff_x + "x = " + (-constant);
    } else if (constant > 0) {
        solution = coeff_y + "y = " + coeff_x + "x + " + constant;
    } else {
        solution = coeff_y + "y = " + coeff_x + "x " + constant;
    }
    return [problem, solution];
}
function fourth_angle_of_quadrilateral(max_angle = 180) {
    var angle1 = user_randint(1, max_angle);
    var angle2 = user_randint(1, 240 - angle1);
    var angle3 = user_randint(1, 340 - (angle1 + angle2));
    var sum_ = angle1 + angle2 + angle3;
    var angle4 = 360 - sum_;
    var problem = `Fourth angle of quadrilateral with angles ${angle1} , ${angle2}, ${angle3} =`;
    return [problem, String(angle4)];
}
function pythagorean_theorem(max_length = 20) {
    var a = user_randint(1, max_length);
    var b = user_randint(1, max_length);
    var c = Math.round(Math.sqrt(a ** 2 + b ** 2) * 100) / 100;
    var problem = `What is the hypotenuse of a right triangle given the other two sides have lengths ${a} and ${b}?`;
    return [problem, String(c)];
}
function radian_to_deg(max_rad = 6.28) {
    var a = user_randint(0, parseInt(max_rad * 100)) / 100;
    var b = Math.round((180 * a) / Math.PI * 100) / 100;
    var problem = "Angle " + a + " radians in degrees is: ";
    return [problem, String(b)];
}
function sector_area(max_radius = 49, max_angle = 359) {
    var r = user_randint(1, max_radius);
    var a = user_randint(1, max_angle);
    var secArea = parseFloat((a / 360) * Math.PI * r * r);
    var formatted_float = Math.round(secArea * 100) / 100;
    var problem = `What is the area of a sector with radius ${r} and angle ${a} degrees?`;
    return [problem, String(formatted_float)];
}
function sum_of_polygon_angles(max_sides = 12) {
    var side_count = user_randint(3, max_sides);
    var _sum = (side_count - 2) * 180;
    var problem = "What is the sum of interior angles of a polygon with " + side_count + " sides?";
    return [problem, String(_sum)];
}
function surface_area_cone(max_radius = 20, max_height = 50, unit = 'm') {
    var a = user_randint(1, max_height);
    var b = user_randint(1, max_radius);
    var slopingHeight = Math.sqrt(a * a + b * b);
    var ans = Math.floor(Math.PI * b * slopingHeight + Math.PI * b * b);
    var problem = "Surface area of cone with height = " + a + unit + " and radius = " + b + unit + " is";
    var solution = ans + " " + unit + "^2";
    return [problem, solution];
}
function surface_area_cube(max_side = 20, unit = 'm') {
    var a = user_randint(1, max_side);
    var ans = 6 * (a * a);
    var problem = "Surface area of cube with side = " + a + unit + " is";
    var solution = ans + " " + unit + "^2";
    return [problem, solution];
}
function surface_area_cuboid(max_side = 20, unit = 'm') {
    var a = user_randint(1, max_side);
    var b = user_randint(1, max_side);
    var c = user_randint(1, max_side);
    var ans = 2 * (a * b + b * c + c * a);
    var problem = "Surface area of cuboid with sides of lengths: " + a + unit + ", " + b + unit + ", " + c + unit + " is";
    var solution = ans + " " + unit + "^2";
    return [problem, solution];
}
function surface_area_cylinder(max_radius = 20, max_height = 50, unit = 'm') {
    var a = user_randint(1, max_height);
    var b = user_randint(1, max_radius);
    var ans = parseInt(2 * Math.PI * a * b + 2 * Math.PI * b * b);
    var problem = "Surface area of cylinder with height = " + a + unit + " and radius = " + b + unit + " is";
    var solution = ans + " " + unit + "^2";
    return [problem, solution];
}
function surface_area_pyramid(unit = 'm') {
    var _PyTHAGOREAN = [[3, 4, 5], [6, 8, 10], [9, 12, 15], [12, 16, 20], [15, 20, 25], [5, 12, 13], [10, 24, 26], [7, 24, 25]];
    var tmp = user_choice_func2(_PyTHAGOREAN);
    var tmp2 = user_sample_func2(tmp, 3);
    var height = tmp2[0];
    var half_width = tmp2[1];
    var triangle_height_1 = tmp2[2];
    var triangle_1 = half_width * triangle_height_1;
    var second_triplet = user_choice_func2(_PyTHAGOREAN.filter(i => i.includes(height)));
    tmp2 = user_sample_func2(second_triplet.filter(i => i !== height), 2);
    var half_length = tmp2[0];
    var triangle_height_2 = tmp2[1];
    var triangle_2 = half_length * triangle_height_2;
    var base = 4 * half_width * half_length;
    var ans = base + 2 * triangle_1 + 2 * triangle_2;
    var problem = "Surface area of pyramid with base length = " + (2 * half_length) + unit + ", base width = " + (2 * half_width) + unit + ", and height = " + height + unit + " is";
    var solution = ans + " " + unit + "^2";
    return [problem, solution];
}
function surface_area_sphere(max_side = 20, unit = 'm') {
    var r = user_randint(1, max_side);
    var ans = Math.round(4 * Math.PI * r * r * 100) / 100;
    var problem = "Surface area of a sphere with radius = " + r + unit + " is";
    var solution = ans + " " + unit + "^2";
    return [problem, solution];
}
function third_angle_of_triangle(max_angle = 89) {
    var angle1 = user_randint(1, max_angle);
    var angle2 = user_randint(1, max_angle);
    var angle3 = 180 - (angle1 + angle2);
    var problem = "Third angle of triangle with angles " + angle1 + " and " + angle2 + " = ";
    return [problem, angle3.toString()];
}
function valid_triangle(max_side_length = 50) {
    var sideA = user_randint(1, max_side_length);
    var sideB = user_randint(1, max_side_length);
    var sideC = user_randint(1, max_side_length);
    var sideSums = [sideA + sideB, sideB + sideC, sideC + sideA];
    var sides = [sideC, sideA, sideB];
    var exists = true && (sides[0] < sideSums[0]) && (sides[1] < sideSums[1]) && (sides[2] < sideSums[2]);
    var problem = `Does triangle with sides ${sideA}, ${sideB} and ${sideC} exist?`;
    var solution = exists ? "yes" : "No";
    return [problem, solution];
}
function volume_cone(max_radius = 20, max_height = 50, unit = 'm') {
    var a = user_randint(1, max_height);
    var b = user_randint(1, max_radius);
    var ans = Math.floor(Math.PI * b * b * a * (1 / 3));
    var problem = "Volume of cone with height = " + a + unit + " and radius = " + b + unit + " is";
    var solution = ans + " " + unit + "^3";
    return [problem, solution];
}
function volume_cube(max_side = 20, unit = 'm') {
    var a = user_randint(1, max_side);
    var ans = Math.pow(a, 3);
    var problem = "Volume of cube with a side length of " + a + unit + " is";
    var solution = ans + " " + unit + "^3";
    return [problem, solution];
}
function volume_cuboid(max_side = 20, unit = 'm') {
    var a = user_randint(1, max_side);
    var b = user_randint(1, max_side);
    var c = user_randint(1, max_side);
    var ans = a * b * c;
    var problem = "Volume of cuboid with sides = " + a + unit + ", " + b + unit + ", " + c + unit + " is";
    var solution = ans + " " + unit + "^3";
    return [problem, solution];
}
function volume_cylinder(max_radius = 20, max_height = 50, unit = 'm') {
    var a = user_randint(1, max_height);
    var b = user_randint(1, max_radius);
    var ans = Math.floor(Math.PI * b * b * a);
    var problem = "Volume of cylinder with height = " + a + unit + " and radius = " + b + unit + " is";
    var solution = ans + " " + unit + "^3";
    return [problem, solution];
}
function volume_cone_frustum(max_r1 = 20, max_r2 = 20, max_height = 50, unit = 'm') {
    var h = user_randint(1, max_height);
    var r1 = user_randint(1, max_r1);
    var r2 = user_randint(1, max_r2);
    var ans = Math.round(((Math.PI * h) * (Math.pow(r1, 2) + Math.pow(r2, 2) + r1 * r2)) / 3 * 100) / 100;
    var problem = "Volume of frustum with height = " + h + unit + " and r1 = " + r1 + unit + " is and r2 = " + r2 + unit + " is ";
    var solution = ans + " " + unit + "^3";
    return [problem, solution];
}
function volume_hemisphere(max_radius = 100) {
    var r = user_randint(1, max_radius);
    var ans = Math.round((2 * Math.PI / 3) * Math.pow(r, 3) * 100) / 100;
    var problem = "Volume of hemisphere with radius " + r + " m = ";
    var solution = ans + " m^3";
    return [problem, solution];
}
function volume_pyramid(max_length = 20, max_width = 20, max_height = 50, unit = 'm') {
    var length = user_randint(1, max_length);
    var width = user_randint(1, max_width);
    var height = user_randint(1, max_height);
    var ans = Math.round(((length * width * height) / 3) * 100) / 100;
    ans = ans % 1 === 0 ? Math.trunc(ans) : ans;
    var problem = "Volume of pyramid with base length = " + length + " " + unit + ", base width = " + width + " " + unit + " and height = " + height + " " + unit + " is";
    var solution = ans + " " + unit + "^3";
    return [problem, solution];
}
function volume_sphere(max_radius = 100) {
    var r = user_randint(1, max_radius);
    var ans = Math.round((4 * Math.PI / 3) * Math.pow(r, 3) * 100) / 100;
    var problem = "Volume of sphere with radius " + r + " m = ";
    var solution = ans + " m^3";
    return [problem, solution];
}
function perimeter_of_polygons(max_sides = 12, max_length = 120) {
    var size_of_sides = user_randint(3, max_sides);
    var sides = [];
    for (var i = 0; i < size_of_sides; i++) {
        sides.push(user_randint(1, max_length));
    }
    var tmp = sides.join(', ');
    var problem = "The perimeter of a " + size_of_sides + " sided polygon with lengths of " + tmp + "cm is: ";
    var solution = sides.reduce(function (a, b) { return a + b; }, 0);
    return [problem, solution.toString()];
}
function test_1() {
    var tmp = absolute_difference();
    var a = tmp[0];
    var b = tmp[1];
    assert_equal(a, '&|-16-66|=&');
    assert_equal(b, '&82&');
    tmp = addition();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&15+14=&');
    assert_equal(b, '&29&');
    tmp = compare_fractions();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Which symbol represents the comparison between &\\frac{10}{1}& and &\\frac{5}{2}&?');
    assert_equal(b, '>');
    tmp = cube_root();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'What is the cube root of: &\\sqrt[3]{291}=& to 2 decimal places?');
    assert_equal(b, '&6.63&');
    tmp = divide_fractions();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&\\frac{4}{5}\\div\\frac{3}{6}=&');
    assert_equal(b, '&\\frac{8}{5}&');
    tmp = division();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&414\\div23=&');
    assert_equal(b, '&18&');
    tmp = exponentiation();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&7^{6}=&');
    assert_equal(b, '&117649&');
    tmp = factorial();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&6! =&');
    assert_equal(b, '&720&');
    tmp = fraction_multiplication();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&\\frac{5}{8}\\cdot\\frac{4}{8}=&');
    assert_equal(b, '&\\frac{5}{16}&');
    tmp = fraction_to_decimal();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&37\\div40=&');
    assert_equal(b, '&0.93&');
    tmp = greatest_common_divisor();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&GCD(351,207)=&');
    assert_equal(b, '&9&');
    tmp = is_composite();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Is &97& composite?');
    assert_equal(b, 'No');
    tmp = is_prime();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Is &92& prime?');
    assert_equal(b, 'No');
    tmp = multiplication();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&11\\cdot10=&');
    assert_equal(b, '&110&');
    tmp = percentage();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'What is &53&% of &62&?');
    assert_equal(b, '&32.86&');
    tmp = percentage_difference();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'What is the percentage difference between &93& and &96&?');
    assert_equal(b, '&3.17&%');
    tmp = percentage_error();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Find the percentage error when observed value equals &-37& and exact value equals &-91&.');
    assert_equal(b, '&59.34&%');
    tmp = power_of_powers();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Simplify &42^{3^{5}}&');
    assert_equal(b, '&42^{15}&');
    tmp = square();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&6^2=&');
    assert_equal(b, '&36&');
    tmp = square_root();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&\\sqrt{36}=&');
    assert_equal(b, '&6&');
    tmp = simplify_square_root();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&\\sqrt{20}&');
    assert_equal(b, '&2\\sqrt{5}&');
    tmp = subtraction();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&59-3=&');
    assert_equal(b, '&56&');
}
function test_2() {
    var tmp = bcd_to_decimal();
    var a = tmp[0];
    var b = tmp[1];
    assert_equal(a, 'Integer of Binary Coded Decimal &4 =& ');
    assert_equal(b, '&18304&');
    tmp = binary_2s_complement();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, "2^s complement of &1100000 = &");
    assert_equal(b, '&100000&');
    tmp = binary_complement_1s();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&01110 = &');
    assert_equal(b, '&10001&');
    tmp = binary_to_decimal();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&1100&');
    assert_equal(b, '&12&');
    tmp = binary_to_hex();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&1100&');
    assert_equal(b, '&0xc&');
    tmp = decimal_to_bcd();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'BCD of Decimal Number &4160 = &');
    assert_equal(b, '&1040&');
    tmp = decimal_to_binary();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Binary of &21 = &');
    assert_equal(b, '&10101&');
    tmp = decimal_to_hexadeci();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Hexadecimal of &384 = &');
    assert_equal(b, '&0x180&');
    tmp = decimal_to_octal();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'The decimal number &3762& in octal is: ');
    assert_equal(b, '&0o7262&');
    tmp = fibonacci_series();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'The Fibonacci Series of the first &18& numbers is ?');
    assert_equal(b, '&0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597&');
    tmp = modulo_division();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, '&77& % &52& = &');
    assert_equal(b, '&25&');
    tmp = nth_fibonacci_number();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'What is the 63th Fibonacci number?');
    assert_equal(b, '&6557470319842&');
}
function test_3() {
    var tmp = combinations();
    var a = tmp[0];
    var b = tmp[1];
    assert_equal(a, 'Find the number of combinations from &14& objects picked &8& at a time.');
    assert_equal(b, '&3003&');
    tmp = conditional_probability();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Someone tested positive for a nasty disease which only &0.61&% of the population have. Test sensitivity (true positive) is equal to &SN=99.29&% whereas test specificity (true negative) &SP=94.91&%. What is the probability that this guy really has that disease?');
    assert_equal(b, '&10.69&%');
    tmp = confidence_interval();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'The confidence interval for sample &[229, 231, 242, 225, 252, 290, 270, 227, 231, 258, 296, 243, 247, 232, 276, 272, 237, 240, 235, 220, 238, 292, 289]& with &80&% confidence is');
    assert_equal(b, '&(257.29, 244.62)&');
    tmp = data_summary();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Find the mean,standard deviation and variance for the data &40, 29, 33, 26, 26, 36, 7, 43, 16, 25, 17, 25, 28, 11, 13&');
    assert_equal(b, 'The Mean is &25&, Standard Deviation is &104.67&, Variance is &10.23&');
    tmp = dice_sum_probability();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'If &2& dice are rolled at the same time, the probability of getting a sum of &2 =&');
    assert_equal(b, '\\frac{1}{36}');
    tmp = mean_median();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Given the series of numbers &[2, 2, 11, 16, 19, 25, 26, 38, 46, 78]&. Find the arithmatic mean and median of the series');
    assert_equal(b, 'Arithmetic mean of the series is &26.3& and arithmetic median of this series is &22&');
    tmp = permutation();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Number of Permutations from &12& objects picked &8& at a time is: ');
    assert_equal(b, '&19958400&');
}
function test_4() {
    var tmp = angle_btw_vectors();
    var a = tmp[0];
    var b = tmp[1];
    assert_equal(a, 'angle between the vectors [829.89, 304.8, 293.49, 934.28, 906.11, 472.69, 173.37, 99, 290.11] and [311.65, 419.22, 249.45, 520.14, 899.08, 693.34, 270.07, 307.76, 578.14] is:');
    assert_equal(b, '0.49 radians');
    tmp = angle_regular_polygon();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Find the angle of a regular polygon with 20 sides');
    assert_equal(b, 162);
    tmp = arc_length();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Given radius, 22 and angle, 169. Find the arc length of the angle.');
    assert_equal(b, 'Arc length of the angle = 64.89134');
    tmp = area_of_circle();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Area of circle with radius 32=');
    assert_equal(b, '3216.99');
    tmp = area_of_circle_given_center_and_point();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Area of circle with center (5,-3) and passing through (9.32, 3.7300000000000004) is');
    assert_equal(b, '201.06');
    tmp = area_of_triangle();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Area of triangle with side lengths: 8, 5, 7 = ');
    assert_equal(b, '17.32');
    tmp = circumference();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Circumference of circle with radius 92 = ');
    assert_equal(b, '578.05');
    tmp = complementary_and_supplementary_angle();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'The complementary angle of 70 =');
    assert_equal(b, '20');
    tmp = curved_surface_area_cylinder();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'What is the curved surface area of a cylinder of radius, 26 and height, 62?');
    assert_equal(b, '10128.49');
    tmp = degree_to_rad();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Angle 167 degrees in radians is: ');
    assert_equal(b, '2.91');
    tmp = equation_of_line_from_two_points();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'What is the equation of the line between points (-1,-19) and (7,14) in slope-intercept form?');
    assert_equal(b, '8y = 33x -119');
    tmp = fourth_angle_of_quadrilateral();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Fourth angle of quadrilateral with angles 44 , 89, 56 =');
    assert_equal(b, '171');
    tmp = pythagorean_theorem();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'What is the hypotenuse of a right triangle given the other two sides have lengths 9 and 11?');
    assert_equal(b, '14.21');
    tmp = radian_to_deg();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Angle 0.93 radians in degrees is: ');
    assert_equal(b, '53.29');
    tmp = sector_area();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'What is the area of a sector with radius 10 and angle 214 degrees?');
    assert_equal(b, '186.75');
    tmp = sum_of_polygon_angles();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'What is the sum of interior angles of a polygon with 3 sides?');
    assert_equal(b, '180');
    tmp = surface_area_cone();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Surface area of cone with height = 6m and radius = 1m is');
    assert_equal(b, '22 m^2');
    tmp = surface_area_cube();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Surface area of cube with side = 6m is');
    assert_equal(b, '216 m^2');
    tmp = surface_area_cuboid();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Surface area of cuboid with sides of lengths: 4m, 4m, 1m is');
    assert_equal(b, '48 m^2');
    tmp = surface_area_cylinder();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Surface area of cylinder with height = 24m and radius = 16m is');
    assert_equal(b, '4021 m^2');
    tmp = surface_area_pyramid();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Surface area of pyramid with base length = 40m, base width = 32m, and height = 12m is');
    assert_equal(b, '2560 m^2');
    tmp = surface_area_sphere();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Surface area of a sphere with radius = 2m is');
    assert_equal(b, '50.27 m^2');
    tmp = third_angle_of_triangle();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Third angle of triangle with angles 21 and 26 = ');
    assert_equal(b, '133');
    tmp = valid_triangle();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Does triangle with sides 32, 39 and 50 exist?');
    assert_equal(b, 'yes');
    tmp = volume_cone();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Volume of cone with height = 25m and radius = 11m is');
    assert_equal(b, '3167 m^3');
    tmp = volume_cube();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Volume of cube with a side length of 12m is');
    assert_equal(b, '1728 m^3');
    tmp = volume_cuboid();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Volume of cuboid with sides = 19m, 20m, 20m is');
    assert_equal(b, '7600 m^3');
    tmp = volume_cylinder();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Volume of cylinder with height = 33m and radius = 5m is');
    assert_equal(b, '2591 m^3');
    tmp = volume_cone_frustum();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Volume of frustum with height = 30m and r1 = 6m is and r2 = 7m is ');
    assert_equal(b, '3989.82 m^3');
    tmp = volume_hemisphere();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Volume of hemisphere with radius 65 m = ');
    assert_equal(b, '575173.25 m^3');
    tmp = volume_pyramid();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Volume of pyramid with base length = 15 m, base width = 6 m and height = 36 m is');
    assert_equal(b, '1080 m^3');
    tmp = volume_sphere();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'Volume of sphere with radius 27 m = ');
    assert_equal(b, '82447.96 m^3');
    tmp = perimeter_of_polygons();
    a = tmp[0];
    b = tmp[1];
    assert_equal(a, 'The perimeter of a 10 sided polygon with lengths of 66, 97, 50, 14, 62, 52, 107, 82, 58, 101cm is: ');
    assert_equal(b, '689');
}
function additional_tests() {
    var tmp = addition(10, 20);
    assert_iter_equal(tmp, ['&4+5=&', '&9&']);
    for (var i = 0; i < 4; i++) {
        tmp = compare_fractions(2);
    }
    assert_iter_equal(tmp, ['Which symbol represents the comparison between &\\frac{1}{2}& and &\\frac{1}{2}&?', '=']);
    for (var i = 0; i < 3; i++) {
        tmp = divide_fractions(2);
    }
    assert_iter_equal(tmp, ['&\\frac{2}{1}\\div\\frac{1}{2}=&', '&\\frac{4}{1}&']);
    for (var i = 0; i < 5; i++) {
        tmp = fraction_multiplication(2);
    }
    assert_iter_equal(tmp, ['&\\frac{2}{1}\\cdot\\frac{2}{1}=&', '&\\frac{4}{1}&']);
    tmp = is_composite(4);
    assert_iter_equal(tmp, ['Is &4& composite?', 'Yes']);
    tmp = is_prime(2);
    assert_iter_equal(tmp, ['Is &2& prime?', 'Yes']);
    tmp = is_prime(3);
    assert_iter_equal(tmp, ['Is &3& prime?', 'Yes']);
    for (var i = 0; i < 4; i++) {
        tmp = is_prime(36);
    }
    assert_iter_equal(tmp, ['Is &11& prime?', 'Yes']);
    tmp = dice_sum_probability(1);
    assert_iter_equal(tmp, ['If &1& dice are rolled at the same time, the probability of getting a sum of &1 =&', '\\frac{1}{6}']);
    for (var i = 0; i < 4; i++) {
        tmp = dice_sum_probability(3);
    }
    assert_iter_equal(tmp, ['If &3& dice are rolled at the same time, the probability of getting a sum of &9 =&', '\\frac{25}{216}']);
    tmp = complementary_and_supplementary_angle(2, 3);
    tmp = complementary_and_supplementary_angle(2, 4);
    tmp = complementary_and_supplementary_angle(2, 5);
    tmp = complementary_and_supplementary_angle(2, 6);
    assert_iter_equal(tmp, ['The supplementary angle of 2 =', '178']);
    tmp = equation_of_line_from_two_points(3, 2);
    tmp = equation_of_line_from_two_points(4, 2);
    tmp = equation_of_line_from_two_points(6, 6);
    tmp = equation_of_line_from_two_points(8, 2);
    tmp = equation_of_line_from_two_points(10, 2);
    tmp = equation_of_line_from_two_points(16, 4);
    tmp = equation_of_line_from_two_points(36, 4);
    assert_iter_equal(tmp, ['What is the equation of the line between points (5,34) and (7,4) in slope-intercept form?', 'y = -15x + 109']);
    for (var i = 0; i < 15; i++) {
        tmp = equation_of_line_from_two_points(1, 0)
    }
    assert_iter_equal(tmp, ['What is the equation of the line between points (0,1) and (1,1) in slope-intercept form?', 'y = 1']);
    tmp = is_composite(0);
    assert_iter_equal(tmp, ['Is &1& composite?', 'No']);
}
function test_init() {
    // gcdEuclid()
    _gcdEuclid(2, 1);

    // compare_fractions()
    _compare_fractions_get_solution(1, 0);
    _compare_fractions_get_solution(0, 1);
    _compare_fractions_get_solution(1, 1);
    user_randint(1, 2);
    user_randint(1, 2);
    compare_fractions(2);
    user_reset_seed();

    // divide_fractions()
    user_randint(1, 2);
    user_randint(1, 2);
    user_randint(1, 2);
    user_randint(1, 2);
    divide_fractions(2);
    user_reset_seed();

    // fraction_multiplication()
    user_randint(1, 2);
    user_randint(1, 2);
    fraction_multiplication(2);
    user_reset_seed();

    // is_composite()
    is_composite(0);
    is_composite(10);
    is_composite(13);
    user_reset_seed();

    // is_prime()
    is_prime(2);
    user_randint(1, 100);
    is_prime(10);
    for (var i = 0; i < 17; i++) {
        user_randint(1, 2);
    }
    is_prime(100);
    for (var i = 0; i < 4; i++) {
        user_randint(1, 2);
    }
    is_prime(10);
    user_reset_seed();

    // dice_sum_probability()
    _dice_sum_probability_get_count(1, 1);
    _dice_sum_probability_get_count(2, 2);
    _dice_sum_probability_get_count(3, 3);
}
function test() {
    test_init();
    test_1();
    user_reset_seed();
    test_2();
    user_reset_seed();
    test_3();
    user_reset_seed();
    test_4();
    user_reset_seed();
    additional_tests();
}
test();
