// Shared observation contract for T06.003.003.003. No parser or resolver here.
// Only constructor fields are inspected; reader buffers/compile methods are excluded.
export function explicit(value) {
  if (value === undefined) return { special: 'undefined' };
  if (typeof value === 'number' && !Number.isFinite(value)) {
    return { special: Number.isNaN(value) ? 'NaN' : value > 0 ? '+Infinity' : '-Infinity' };
  }
  if (Array.isArray(value) || ArrayBuffer.isView(value)) {
    return Array.from(value, explicit);
  }
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).map(k => [k, explicit(value[k])]));
  }
  return value;
}

function statistics(fields) {
  const out = { finite: 0, nan: 0, positive_infinity: 0, negative_infinity: 0,
    undefined: 0, null: 0, min: null, max: null, exceptional_locations: [] };
  function visit(v, location) {
    let category;
    if (v === undefined) category = 'undefined';
    else if (v === null) category = 'null';
    else if (typeof v === 'number') {
      if (Number.isFinite(v)) {
        out.finite++;
        out.min = out.min === null ? v : Math.min(out.min, v);
        out.max = out.max === null ? v : Math.max(out.max, v);
        return;
      }
      category = Number.isNaN(v) ? 'nan' : v > 0 ? 'positive_infinity' : 'negative_infinity';
    } else if (Array.isArray(v) || ArrayBuffer.isView(v)) {
      for (let i = 0; i < v.length; i++) visit(v[i], `${location}[${i}]`);
      return;
    } else if (typeof v === 'object') {
      for (const k of Object.keys(v)) visit(v[k], `${location}.${k}`);
      return;
    } else return;
    out[category]++;
    if (out.exceptional_locations.length < 16) out.exceptional_locations.push({ location, category });
  }
  for (const k of Object.keys(fields)) visit(fields[k], k);
  return out;
}

function ends(values) {
  return { first: values.length ? explicit(values[0]) : null,
    last: values.length ? explicit(values[values.length - 1]) : null };
}

function waterFields(water) {
  return { level: water.level, type: water.type, waveHeight: water.waveHeight,
    waveSpeed: water.waveSpeed, wavePitch: water.wavePitch, animSpeed: water.animSpeed };
}

export function summarizeConstructor(kind, value) {
  if (kind === 'rsw') {
    const water = waterFields(value.water);
    return {
      files: explicit(value.files), water: explicit(water), light: explicit(value.light), ground: explicit(value.ground),
      object_counts: { models: value.models.length, lights: value.lights.length,
        sounds: value.sounds.length, effects: value.effects.length },
      model_dependencies: value.models.map((v, i) => ({ object_index: i, filename: v.filename, nodename: v.nodename })),
      sound_dependencies: value.sounds.map((v, i) => ({ object_index: i, file: v.file })),
      samples: { models: ends(value.models), lights: ends(value.lights), sounds: ends(value.sounds), effects: ends(value.effects) },
      numeric_fields: statistics({ water, light: value.light, ground: value.ground,
        models: value.models, lights: value.lights, sounds: value.sounds, effects: value.effects })
    };
  }
  if (kind === 'gnd') {
    // GND water contains only constructor data; do not inspect fp internals.
    return {
      version: explicit(value.version), width: value.width, height: value.height, zoom: explicit(value.zoom),
      textures: explicit(value.textures), texture_indexes: explicit(value.textureIndexes),
      lightmap: { count: value.lightmap.count, per_cell: value.lightmap.per_cell,
        byte_length: value.lightmap.data.length, first_bytes: Array.from(value.lightmap.data.subarray(0, 8)) },
      tile_count: value.tiles.length, surface_count: value.surfaces.length,
      samples: { tiles: ends(value.tiles), surfaces: ends(value.surfaces) }, water: explicit(value.water),
      cursor: { offset: value.fp.tell(), length: value.fp.length, trailing_bytes: value.fp.length - value.fp.tell() },
      numeric_fields: statistics({ version: value.version, width: value.width, height: value.height, zoom: value.zoom,
        texture_indexes: value.textureIndexes, lightmap_count: value.lightmap.count, lightmap_per_cell: value.lightmap.per_cell,
        tiles: value.tiles, surfaces: value.surfaces, water: value.water })
    };
  }
  if (kind === 'gat') {
    const histogram = Object.create(null);
    for (let i = 4; i < value.cells.length; i += 5) {
      const n = value.cells[i];
      const key = Number.isNaN(n) ? 'NaN' : n === Infinity ? '+Infinity' : n === -Infinity ? '-Infinity' : String(n);
      histogram[key] = (histogram[key] || 0) + 1;
    }
    return {
      version: explicit(value.version), width: value.width, height: value.height, cells_length: value.cells.length,
      first_cell: explicit(value.cells.subarray(0, 5)), last_cell: explicit(value.cells.subarray(Math.max(0, value.cells.length - 5))),
      transformed_flag_histogram: histogram, numeric_fields: statistics({ cells: value.cells })
    };
  }
  throw new Error('Unknown constructor kind');
}
