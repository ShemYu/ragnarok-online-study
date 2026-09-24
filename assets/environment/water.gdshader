shader_type spatial;
render_mode specular_disabled;
varying vec3 world;
void vertex() { world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	vec2 p = world.xz;
	float edge = abs(p.x - 9.0) / 1.64;
	float long_wave = sin(p.y * 4.7 + sin(p.x * 3.0) * 1.2 + TIME * 0.6);
	float small_wave = sin(p.x * 18.0 + p.y * 11.0 - TIME * 1.0);
	vec3 deep = vec3(0.25, 0.42, 0.43);
	vec3 shallow = vec3(0.48, 0.57, 0.47);
	vec3 color = mix(deep, shallow, smoothstep(0.5, 1.0, edge));
	color += vec3(0.017, 0.024, 0.019) * long_wave + vec3(0.006) * small_wave;
	float ripple = smoothstep(0.975, 1.0, long_wave) * smoothstep(0.1, 0.6, sin(p.x * 6.0 + p.y));
	ALBEDO = color + vec3(0.06, 0.09, 0.07) * ripple;
	ROUGHNESS = 0.8;
}
