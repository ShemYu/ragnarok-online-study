// The unchanged pinned module imports lodash, using only these two methods.
// This fixture passes no JS tables/objects into Lua; canonical strings cross
// the bridge as ASCII bytes. This is a local adapter, not the lodash package.
export default {
  isArray: Array.isArray,
  isPlainObject(value) {
    if (Object.prototype.toString.call(value) !== '[object Object]') return false;
    const proto = Object.getPrototypeOf(value);
    return proto === null || proto === Object.prototype;
  }
};
