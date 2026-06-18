#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "raylib.h"

typedef struct { char *data; int64_t len; } zn_string;

int8_t _zn_gfx_window(int64_t w, int64_t h, zn_string title) {
    char *buf = strndup(title.data, title.len);
    if (!buf) return 0;
    InitWindow((int)w, (int)h, buf);
    free(buf);
    return 1;
}

void _zn_gfx_close() {
    CloseWindow();
}

int8_t _zn_gfx_running() {
    return !WindowShouldClose();
}

void _zn_gfx_clear(int64_t r, int64_t g, int64_t b, int64_t a) {
    BeginDrawing();
    ClearBackground((Color){(unsigned char)r, (unsigned char)g, (unsigned char)b, (unsigned char)a});
}

void _zn_gfx_update() {
    EndDrawing();
}

void _zn_gfx_title(zn_string title) {
    char *buf = strndup(title.data, title.len);
    if (!buf) return;
    SetWindowTitle(buf);
    free(buf);
}

int64_t _zn_gfx_fps() {
    return GetFPS();
}

void _zn_gfx_set_fps(int64_t fps) {
    SetTargetFPS((int)fps);
}

double _zn_gfx_delta() {
    return GetFrameTime();
}

void _zn_gfx_pixel(int64_t x, int64_t y, int64_t r, int64_t g, int64_t b, int64_t a) {
    DrawPixel((int)x, (int)y, (Color){(unsigned char)r, (unsigned char)g, (unsigned char)b, (unsigned char)a});
}

void _zn_gfx_line(int64_t x1, int64_t y1, int64_t x2, int64_t y2, int64_t r, int64_t g, int64_t b, int64_t a) {
    DrawLine((int)x1, (int)y1, (int)x2, (int)y2, (Color){(unsigned char)r, (unsigned char)g, (unsigned char)b, (unsigned char)a});
}

void _zn_gfx_rect(int64_t x, int64_t y, int64_t w, int64_t h, int64_t r, int64_t g, int64_t b, int64_t a) {
    DrawRectangle((int)x, (int)y, (int)w, (int)h, (Color){(unsigned char)r, (unsigned char)g, (unsigned char)b, (unsigned char)a});
}

void _zn_gfx_rect_outline(int64_t x, int64_t y, int64_t w, int64_t h, int64_t r, int64_t g, int64_t b, int64_t a, int64_t thick) {
    DrawRectangleLinesEx((Rectangle){(float)x, (float)y, (float)w, (float)h}, (float)thick, (Color){(unsigned char)r, (unsigned char)g, (unsigned char)b, (unsigned char)a});
}

void _zn_gfx_circle(int64_t cx, int64_t cy, int64_t rad, int64_t r, int64_t g, int64_t b, int64_t a) {
    DrawCircle((int)cx, (int)cy, (float)rad, (Color){(unsigned char)r, (unsigned char)g, (unsigned char)b, (unsigned char)a});
}

void _zn_gfx_circle_outline(int64_t cx, int64_t cy, int64_t rad, int64_t r, int64_t g, int64_t b, int64_t a) {
    DrawCircleLines((int)cx, (int)cy, (float)rad, (Color){(unsigned char)r, (unsigned char)g, (unsigned char)b, (unsigned char)a});
}

void _zn_gfx_triangle(int64_t x1, int64_t y1, int64_t x2, int64_t y2, int64_t x3, int64_t y3, int64_t r, int64_t g, int64_t b, int64_t a) {
    Vector2 v1 = {(float)x1, (float)y1};
    Vector2 v2 = {(float)x2, (float)y2};
    Vector2 v3 = {(float)x3, (float)y3};
    DrawTriangle(v1, v2, v3, (Color){(unsigned char)r, (unsigned char)g, (unsigned char)b, (unsigned char)a});
}

void _zn_gfx_text(zn_string text, int64_t x, int64_t y, int64_t size, int64_t r, int64_t g, int64_t b, int64_t a) {
    char *buf = strndup(text.data, text.len);
    if (!buf) return;
    DrawText(buf, (int)x, (int)y, (int)size, (Color){(unsigned char)r, (unsigned char)g, (unsigned char)b, (unsigned char)a});
    free(buf);
}

int8_t _zn_gfx_key_down(int64_t key) {
    return IsKeyDown((int)key);
}

int8_t _zn_gfx_key_pressed(int64_t key) {
    return IsKeyPressed((int)key);
}

int8_t _zn_gfx_key_released(int64_t key) {
    return IsKeyReleased((int)key);
}

int64_t _zn_gfx_mouse_x() {
    return GetMouseX();
}

int64_t _zn_gfx_mouse_y() {
    return GetMouseY();
}

int8_t _zn_gfx_mouse_clicked(int64_t btn) {
    return IsMouseButtonDown((int)btn);
}

int64_t _zn_gfx_mouse_scroll() {
    return (int64_t)GetMouseWheelMove();
}
