shader_type spatial;
render_mode specular_disabled;

uniform vec2 main_path[8];
uniform vec2 branch_path[5];
varying vec3 world;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}
float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
		mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0)), f.x), f.y);
}
float segment_distance(vec2 p, vec2 a, vec2 b) {
	vec2 v = b - a;
	return length(p - a - v * clamp(dot(p - a, v) / dot(v, v), 0.0, 1.0));
}
void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
void fragment() {
	vec2 p = world.xz;
	float broad = noise(p * 0.30);
	float patches = noise(p * 1.4 + broad);
	float grain = noise(p * 34.0);
	float tufts = noise(p * 8.0);
	vec3 grass = mix(vec3(0.27, 0.39, 0.18), vec3(0.48, 0.57, 0.30), broad);
	grass = mix(grass, vec3(0.59, 0.61, 0.34), smoothstep(0.68, 0.90, patches) * 0.42);
	grass *= 0.89 + grain * 0.18 + tufts * 0.10;
	// Tiny clustered strokes keep a hand-painted meadow surface at game zoom.
	float blade = smoothstep(0.60, 0.77, noise(p * vec2(39.0, 17.0)));
	grass += vec3(0.045, 0.054, 0.018) * blade;
	float road = 100.0;
	float branch = 100.0;
	vec2 drift = vec2(noise(p * 1.8), noise(p * 2.1 + 70.0)) * 0.18 - 0.09;
	for (int i = 0; i < 7; i++) {
		road = min(road, segment_distance(p + drift, main_path[i], main_path[i + 1]));
	}
	for (int i = 0; i < 4; i++) {
		branch = min(branch, segment_distance(p + drift, branch_path[i], branch_path[i + 1]));
	}
	float distance_to_edge = min(road - 1.08, branch - 0.64);
	float wear = noise(p * 5.0) * 0.14 + noise(p * 0.9) * 0.20;
	float road_mask = 1.0 - smoothstep(-0.12, 0.30, distance_to_edge + wear);
	float verge = 1.0 - smoothstep(0.16, 0.67, distance_to_edge + wear);
	vec3 dirt = mix(vec3(0.57, 0.47, 0.31), vec3(0.71, 0.62, 0.43), noise(p * 1.7));
	dirt *= 0.89 + grain * 0.17;
	// Faint worn wheel strips and compacted gravel, broken by noise.
	float rut = exp(-pow((road - 0.57) * 9.0, 2.0)) * smoothstep(0.18, 0.70, noise(p * 3.0));
	dirt -= vec3(0.08, 0.07, 0.05) * rut;
	float pebble = step(0.88, hash(floor(p * 29.0))) * smoothstep(0.0, 0.28, 0.5 - length(fract(p * 29.0) - 0.5));
	dirt += vec3(0.12, 0.11, 0.085) * pebble;
	vec3 verge_color = mix(grass, vec3(0.42, 0.42, 0.24), 0.65);
	ALBEDO = mix(mix(grass, verge_color, verge * 0.55), dirt, road_mask);
	ROUGHNESS = 1.0;
}
