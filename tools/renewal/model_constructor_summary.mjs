// Frozen common observation for T06.003.003.006; no parser, fetch or compile.
// Explicit projections exclude circular node.main and the unavailable reader.
export const SUMMARY_LIMITS = Object.freeze({ nodes: 65536, textures: 65536,
  node_slots: 262144, string_code_units: 1048576, numeric_visits: 4194304 });

export class SummaryLimitError extends Error {
  constructor() { super('model summary limit'); this.name = 'SummaryLimitError'; }
}

export function explicit(value) {
  if (value === undefined) return { special: 'undefined' };
  if (typeof value === 'number' && !Number.isFinite(value)) {
    return { special: Number.isNaN(value) ? 'NaN' : value > 0 ? '+Infinity' : '-Infinity' };
  }
  if (Array.isArray(value) || ArrayBuffer.isView(value)) return Array.from(value, explicit);
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).map(key => [key, explicit(value[key])]));
  }
  return value;
}

function string(value) {
  if (typeof value !== 'string') throw new TypeError('model string expected');
  if (value.length > SUMMARY_LIMITS.string_code_units) throw new SummaryLimitError();
  return value;
}

function array(value, maximum) {
  if (!Array.isArray(value)) throw new TypeError('model array expected');
  if (value.length > maximum) throw new SummaryLimitError();
  return value;
}

function count(value) { return value === undefined ? { special: 'undefined' } : value.length; }

function box(value) {
  return Object.fromEntries(['min', 'max', 'offset', 'range', 'center'].map(key => [key, value[key]]));
}

function statistics(fields, budget) {
  const result = { finite: 0, nan: 0, positive_infinity: 0, negative_infinity: 0,
    undefined: 0, null: 0, min: null, max: null, exceptional_locations: [], exceptional_locations_omitted: 0 };
  function visit(value, location) {
    if (++budget.visits > SUMMARY_LIMITS.numeric_visits) throw new SummaryLimitError();
    let category;
    if (value === undefined) category = 'undefined';
    else if (value === null) category = 'null';
    else if (typeof value === 'number') {
      if (Number.isFinite(value)) {
        result.finite++;
        result.min = result.min === null ? value : Math.min(result.min, value);
        result.max = result.max === null ? value : Math.max(result.max, value);
        return;
      }
      category = Number.isNaN(value) ? 'nan' : value > 0 ? 'positive_infinity' : 'negative_infinity';
    } else if (Array.isArray(value) || ArrayBuffer.isView(value)) {
      for (let i = 0; i < value.length; i++) visit(value[i], `${location}[${i}]`);
      return;
    } else if (typeof value === 'object') {
      for (const key of Object.keys(value)) visit(value[key], `${location}.${key}`);
      return;
    } else return;
    result[category]++;
    if (result.exceptional_locations.length < 16) result.exceptional_locations.push({ location, category });
    else result.exceptional_locations_omitted++;
  }
  for (const key of Object.keys(fields)) visit(fields[key], key);
  return result;
}

export function summarizeModel(value) {
  const nodes = array(value.nodes, SUMMARY_LIMITS.nodes);
  const textures = array(value.textures, SUMMARY_LIMITS.textures).map(string);
  const budget = { visits: 0 };
  const globalFields = { version: value.version, animLen: value.animLen, shadeType: value.shadeType,
    alpha: value.alpha, frameRatePerSecond: value.frameRatePerSecond, posKeyframes: value.posKeyframes,
    volumebox: value.volumebox, box: box(value.box) };
  let slots = 0;
  const nodeSummaries = nodes.map((node, node_index) => {
    const nodeSlots = array(node.textures, SUMMARY_LIMITS.node_slots);
    if ((slots += nodeSlots.length) > SUMMARY_LIMITS.node_slots) throw new SummaryLimitError();
    const transform = { mat3: node.mat3, offset: node.offset, pos: node.pos, rotangle: node.rotangle,
      rotaxis: node.rotaxis, scale: node.scale, flip: node.flip, matrix: node.matrix };
    const nodeBox = box(node.box);
    const numericFields = { transform, box: nodeBox, vertices: node.vertices, tvertices: node.tvertices,
      faces: node.faces, textures: nodeSlots, rotKeyframes: node.rotKeyframes, posKeyframes: node.posKeyframes,
      scaleKeyFrames: node.scaleKeyFrames, textureKeyFrameGroup: node.textureKeyFrameGroup };
    return { node_index, name: string(node.name), parentname: string(node.parentname), is_only: node.is_only,
      textures: explicit(nodeSlots), texture_references: nodeSlots.map((slot, slot_index) => ({ slot_index,
        table_index: Number.isInteger(slot) && slot >= 0 && slot < textures.length ? slot : null,
        state: Number.isInteger(slot) && slot >= 0 && slot < textures.length ? 'resolved' : 'unresolved' })),
      transform: explicit(transform), box: explicit(nodeBox),
      vertex_count: node.vertices.length, tvertex_components: node.tvertices.length, face_count: node.faces.length,
      keyframe_counts: { rotation: count(node.rotKeyframes), position: count(node.posKeyframes),
        scale: count(node.scaleKeyFrames), texture_groups: count(node.textureKeyFrameGroup) },
      numeric_fields: statistics(numericFields, budget) };
  });
  const declarations = textures.map((raw_name, texture_index) => {
    const logical_name = 'data\\texture\\' + raw_name;
    const filemanager_name = logical_name.trim();
    const http_path = filemanager_name.replace(/\\/g, '/').split('/').map(encodeURIComponent).join('/');
    return { texture_index, constructor_pointer: `/textures/${texture_index}`, raw_name, logical_name,
      filemanager_name, http_path };
  });
  return {
    version: explicit(value.version), animLen: explicit(value.animLen), shadeType: explicit(value.shadeType),
    alpha: explicit(value.alpha), frameRatePerSecond: explicit(value.frameRatePerSecond),
    textures, main_node_index: nodes.indexOf(value.main_node), instances: value.instances.length,
    global_position_keys: count(value.posKeyframes), volume_boxes: count(value.volumebox),
    box: explicit(box(value.box)), nodes: nodeSummaries, texture_declarations: declarations,
    animation_by_node_keys: nodes.some(node => node.rotKeyframes.length > 0 ||
      (node.posKeyframes !== undefined && node.posKeyframes.length > 0) ||
      (node.scaleKeyFrames !== undefined && node.scaleKeyFrames.length > 0)),
    numeric_fields: statistics(globalFields, budget),
    cursor: { state: 'not_observable_from_unchanged_constructor', remaining_bytes: null }
  };
}
