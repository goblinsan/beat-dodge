shader_type canvas_item;

// Perspective ground plane. The authored centre path stays aligned with the
// screen centre, then widens below the horizon as it approaches the camera.
uniform sampler2D floor_texture : repeat_enable, filter_linear_mipmap;
uniform float scroll_time : hint_range(0.0, 100000.0) = 0.0;
uniform float horizon_y : hint_range(0.1, 0.9) = 0.4;

void fragment() {
    vec4 forest_shadow = vec4(0.035, 0.085, 0.025, 1.0);
    vec4 distant_forest = vec4(0.055, 0.13, 0.035, 1.0);

    if (UV.y < horizon_y) {
        float sky_t = UV.y / max(horizon_y, 0.001);
        float centre_light = 1.0 - smoothstep(0.0, 0.42, abs(UV.x - 0.5));
        vec4 far_col = mix(forest_shadow, distant_forest, sky_t);
        COLOR = mix(far_col, vec4(0.12, 0.18, 0.055, 1.0), centre_light * sky_t * 0.35);
    } else {
        float ground_y = clamp((UV.y - horizon_y) / max(1.0 - horizon_y, 0.001), 0.0, 1.0);
        float width_scale = mix(1.55, 0.20, pow(ground_y, 0.86));
        float forward_scroll = scroll_time * 0.72;

        vec2 floor_uv = vec2(
            clamp(0.5 + (UV.x - 0.5) * width_scale, 0.0, 1.0),
            fract(ground_y * 2.35 - forward_scroll)
        );

        vec4 floor_col = texture(floor_texture, floor_uv);

        float edge_vignette = smoothstep(0.0, 0.32, UV.x) * (1.0 - smoothstep(0.68, 1.0, UV.x));
        float horizon_fog = 1.0 - smoothstep(0.0, 0.20, ground_y);
        float foreground_contrast = smoothstep(0.35, 1.0, ground_y);

        floor_col = mix(forest_shadow, floor_col, edge_vignette);
        floor_col.rgb *= mix(0.72, 1.12, foreground_contrast);
        COLOR = mix(floor_col, distant_forest, horizon_fog * 0.58);
    }
}
