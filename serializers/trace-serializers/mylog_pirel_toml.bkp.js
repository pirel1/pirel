"use strict";
const crypto = require("crypto");
const fs = require("fs");
let _default_console_log = console.log;


// js alternatives for datetime.datetime, datetime.date, datetime.time
var datetime = {
    date: class date {
        constructor(y, m, d) {
            this.y = y;
            this.m = m;
            this.d = d;
        }
        isoformat() {
            return `${this.y.toString().padStart(4, "0")}-${this.m.toString().padStart(2, "0")}-${this.d.toString().padStart(2, "0")}`;
        }
    },
    datetime: class datetime {
        constructor(year, month, day, hour, minute, second, microsecond, tz) {
            this.year = year;
            this.month = month;
            this.day = day;
            this.hour = hour;
            this.minute = minute;
            this.second = second;
            this.microsecond = microsecond;
            this.tz = tz;
        }
        isoformat() {
            let datePart = `${this.year.toString().padStart(4, "0")}-${this.month.toString().padStart(2, "0")}-${this.day.toString().padStart(2, "0")}`;
            let timePart = `${this.hour.toString().padStart(2, "0")}:${this.minute.toString().padStart(2, "0")}:${this.second.toString().padStart(2, "0")}`;
            let tzPart = this.tz.utcoffset();
            return `${datePart}T${timePart}${tzPart}`;
        }
    },
    tzinfo: class tzinfo {
        constructor(tz) {
            if (tz === "Z") {
                this.tz = "+00:00";
            } else {
                this.tz = tz;
            }
        }
    }
};


function isUserDefinedClass(obj) {
    if (typeof obj !== 'object' || obj === null)
        return false;
    // Exclude plain objects
    return obj.constructor && obj.constructor !== Object;
}

function hasattr(obj, attr) {
    if (obj === null || typeof obj === "undefined") {
        return false;
    }
    return attr in Object(obj);
}


function serializeNull() {
    return ["null"];
}

function serializeBool(arg) {
    return ["bool", arg];
}

function codePointLength(arg) {
    return Array.from(arg).length;
}

function serializeString(arg) {
    return ["string", codePointLength(arg), arg];
}

function serializeNum(arg) {
    if (arg === Infinity)
        return serializeString("inf");
    if (arg === -Infinity)
        return serializeString("-inf");
    if (Number.isNaN(arg))
        return serializeString("nan");
    if (arg >= Number.MIN_SAFE_INTEGER && arg <= Number.MAX_SAFE_INTEGER) {
        if (Math.abs(arg) <= 1e-9) {
            return ["number", 0];
        }
        // force whole numbers to be int type
        if (arg % 1 === 0) {
            return ["number", Math.round(arg)];
        }
        const srlzd = String(arg.toExponential(6));
        return serializeString(srlzd);
    }
    return serializeString(String(arg.toExponential(6)));
}

function canonicalAnyOf() {
    return ["any_of", ["opaque_object"], ["dict", 0, []]];
}

function normalizeForHash(val) {
    if (!Array.isArray(val)) {
        return val;
    }
    if (val.length >= 1 && val[0] === "any_of") {
        return canonicalAnyOf();
    }
    if (val.length === 1 && val[0] === "opaque_object") {
        return canonicalAnyOf();
    }
    if (val.length === 3 && val[0] === "dict" && val[1] === 0 && Array.isArray(val[2]) && val[2].length === 0) {
        return canonicalAnyOf();
    }
    return val.map(child => normalizeForHash(child));
}

function jsonStringifyEnsureAscii(value) {
    // Match Python's default json.dumps(..., ensure_ascii=True) behavior.
    const raw = JSON.stringify(value);
    let ascii = "";
    for (const ch of raw) {
        const codepoint = ch.codePointAt(0);
        if (codepoint <= 0x7f) {
            ascii += ch;
        } else if (codepoint <= 0xffff) {
            ascii += "\\u" + codepoint.toString(16).padStart(4, "0");
        } else {
            const cp = codepoint - 0x10000;
            const hi = 0xd800 + (cp >> 10);
            const lo = 0xdc00 + (cp & 0x3ff);
            ascii += "\\u" + hi.toString(16).padStart(4, "0");
            ascii += "\\u" + lo.toString(16).padStart(4, "0");
        }
    }
    return ascii;
}

function serializeArray(arg) {
    const serializedVals = arg.map(val => serialize(val));
    const normalizedVals = serializedVals.map(val => normalizeForHash(val));
    const serializedValsStr = jsonStringifyEnsureAscii(normalizedVals);
    const hashed = crypto.createHash("sha256").update(serializedValsStr).digest("hex");
    return ["hash", hashed.length, hashed];
}

function serializeSet(arg) {
    const arrVals = Array.from(arg);
    let sortedVals;
    if (arrVals.length === 0) {
        sortedVals = arrVals;
    } else {
        const firstType = typeof arrVals[0];
        if (firstType === "string") {
            sortedVals = arrVals.slice().sort();
        } else if (firstType === "number") {
            sortedVals = arrVals.slice().sort((a, b) => a - b);
        } else {
            throw new Error("serializeSet only supports sets of strings or numbers");
        }
    }
    const serializedVals = sortedVals.map(val => serialize(val));
    return ["set", sortedVals.length, serializedVals];
}

function serializeObject(arg) {
    if (Object.getPrototypeOf(arg) === null) {
        return ["opaque_object"];
    }
    if (isUserDefinedClass(arg)) {
        return serializeDefinedInMain(arg);
    }
    const sortedKeys = Object.keys(arg).sort();
    if (sortedKeys.length === 0) {
        return ["any_of", ["opaque_object"], ["dict", 0, []]];
    }
    let serializedKeyValuePairs = [];
    for (const key of sortedKeys) {
        serializedKeyValuePairs.push(serialize([key, arg[key]]));
    }
    return ["dict", sortedKeys.length, serializedKeyValuePairs];
}

function serializeMap(arg) {
    // Python serializer converts int/float keys to strings, then sorts string keys.
    const keyValuePairs = [];
    for (const [key, value] of arg.entries()) {
        if (typeof key === "string") {
            keyValuePairs.push([key, value]);
            continue;
        }
        if (typeof key === "number") {
            keyValuePairs.push([String(key), value]);
            continue;
        }
        throw new Error("cannot serialize map with non string/number keys");
    }
    keyValuePairs.sort((a, b) => {
        if (a[0] < b[0]) return -1;
        if (a[0] > b[0]) return 1;
        return 0;
    });

    let serializedKeyValuePairs = [];
    for (const [key, value] of keyValuePairs) {
        serializedKeyValuePairs.push(serialize([key, value]));
    }
    return ["dict", keyValuePairs.length, serializedKeyValuePairs];
}

function serializeGenerator(arg) {
    // intentionally avoid consuming the generator
    return serializeIterator(arg);
}

function serializeIterator(arg) {
    // intentionally avoid consuming the iterator
    return ["iterator"];
}

function serializeCallable(arg) {
    return ["function"];
}

function serializeDefinedInMain(arg) {
    // Prioritize user-defined classes with _class_name attribute
    // since JavaScript does not allow dynamic class names.
    // Follow the same logic in Python trc serializer.
    if (arg.hasOwnProperty("_class_name")) {
        return ["defined_in_main", arg._class_name];
    }
    return ["defined_in_main", arg.constructor.name];
}

function serializeRegex(arg) {
    const pattern = arg.source;
    return ["regex", codePointLength(pattern), pattern];
}

function serialize(arg) {
    if (arg === null || typeof arg === "undefined")
        return serializeNull();
    if (arg === true || arg === false)
        return serializeBool(arg);
    if (typeof arg === "string")
        return serializeString(arg);
    if (typeof arg === "number")
        return serializeNum(arg);
    if (Array.isArray(arg))
        return serializeArray(arg);
    if (Object.prototype.toString.call(arg) === "[object Generator]")
        return serializeGenerator(arg);
    if (Object.prototype.toString.call(arg) === "[object Set]")
        return serializeSet(arg);
    if (Object.prototype.toString.call(arg) === "[object Object]")
        return serializeObject(arg);
    if (Object.prototype.toString.call(arg) === "[object Map]")
        return serializeMap(arg);
    if (arg && typeof arg.next === "function")
        return serializeIterator(arg);
    if (arg && typeof arg[Symbol.iterator] === "function")
        return serializeArray(Array.from(arg));
    if (arg instanceof RegExp)
        return serializeRegex(arg);
    if (typeof arg === "bigint")
        return serializeNum(Number(arg));
    if (arg instanceof Function)
        return serializeCallable(arg);
    let str_result = String(arg);
    return ["unknown", codePointLength(str_result), str_result];
}

let _trace_idx = 0;  // for debugging
function myexactlog(...args) {
    let info_list = ["MYLOGEX:"];
    for (let i = 0; i < args.length; i++) {
        info_list.push(serialize(args[i]));
    }
    // Use synchronous write to avoid partial line loss when the process
    // crashes right after logging (console.log may buffer asynchronously).
    fs.writeSync(1, JSON.stringify(info_list) + "\n");
    _trace_idx += 1
}

function mylog(...args) {
    myexactlog(...args);
}

console.log = function () {
    // myexactlog([...arguments]);
    // _default_console_log(...arguments);
};

// this function is inserted into body node types' `block`
function secret_fun_4071() {
    return 0;
}

class Exception extends Error {
    constructor(message) {
        super(message);
        this.name = "Exception";
    }
}
