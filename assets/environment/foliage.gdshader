shader_type spatial;
render_mode specular_disabled;
varying vec3 world;
varying vec3 local_normal;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0)), f.x), f.y);
}
void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	local_normal = NORMAL;
}
void fragment() {
	vec2 p = world.xz + world.y * vec2(0.32, 0.20);
	float patches = noise(p * 4.1);
	float leaf = noise(p * vec2(22.0, 27.0));
	float crown = clamp(local_normal.y * 0.55 + 0.45, 0.0, 1.0);
	vec3 dark = vec3(0.19, 0.29, 0.16);
	vec3 middle = vec3(0.35, 0.44, 0.21);
	vec3 light = vec3(0.51, 0.55, 0.27);
	vec3 color = mix(dark, middle, crown);
	color = mix(color, light, smoothstep(0.40, 0.85, patches) * crown * 0.70);
	color *= 0.79 + smoothstep(0.23, 0.77, leaf) * 0.31;
	// Sparse light leaf tips over several irregular broad crown planes.
	color += vec3(0.085, 0.082, 0.027) * step(0.76, leaf) * crown;
	ALBEDO = color;
	ROUGHNESS = 1.0;
}
