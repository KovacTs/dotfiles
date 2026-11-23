#version 300 es

precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;

layout(location = 0) out vec4 fragColor;

void main() {
    vec4 pixColor = texture(tex, v_texcoord);
    // Warm ~4000K blue-light filter for night mode
    pixColor.r *= 1.00;
    pixColor.g *= 0.88;
    pixColor.b *= 0.68;
    fragColor = pixColor;
}
