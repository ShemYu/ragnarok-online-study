shader_type spatial;
render_mode specular_disabled;
uniform vec4 base_color : source_color = vec4(0.5, 0.5, 0.5, 1.0);
uniform float grain_scale = 12.0;
uniform float grain_amount = 0.18;
uniform bool wood = false;
varying vec3 world;
varying vec3 world_normal;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0)), f.x), f.y);
}
void vertex() { world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; world_normal = MODEL_NORMAL_MATRIX * NORMAL; }
void fragment() {
	vec3 n = abs(normalize(world_normal));
	vec2 uv = world.xz * n.y + world.xy * n.z + world.zy * n.x;
	float g = noise(uv * grain_scale);
	if (wood) { g = noise(uv * vec2(18.0, 2.0) + noise(uv * 4.0)); }
	float grain = (g - 0.5) * grain_amount;
	float patch = (noise(uv * 2.5) - 0.5) * grain_amount;
	ALBEDO = base_color.rgb * (1.0 + grain + patch);
	ROUGHNESS = 1.0;
}
