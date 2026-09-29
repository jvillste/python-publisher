// Odin runtime package for the game publishing page.
//
// A game imports this package as
//
//	import screen "lib:screen"
//
// and draws on the canvas with screen.clear, screen.circle, screen.rect,
// screen.line and screen.text, exactly like the Python `screen` object.
// Colors are packed integers: 0xRRGGBB, for example 0xfacc15.
//
// Instead of passing event handlers around, the game registers plain
// procedures with screen.on_frame, screen.on_mouse_click,
// screen.on_mouse_move and screen.on_key_press.  The page calls them
// through the exported bridge procedures at the bottom of this file.
//
// Key press handlers receive the Unicode code point of the key for
// single-character keys and the constants below for special keys.
package screen

// Special key codes for on_key_press handlers.  Single-character keys
// (letters, digits, " ") arrive as their Unicode code point.
Key_Backspace :: 8
Key_Tab       :: 9
Key_Enter     :: 13
Key_Escape    :: 27
Key_Delete    :: 46

Key_Arrow_Left  :: 1000
Key_Arrow_Up    :: 1001
Key_Arrow_Right :: 1002
Key_Arrow_Down  :: 1003

Key_Home     :: 1036
Key_End      :: 1035
Key_Page_Up  :: 1033
Key_Page_Down :: 1034
Key_Insert   :: 1045

Frame_Handler :: proc(time_ms: i32)
Mouse_Handler :: proc(x, y: i32)
Key_Handler   :: proc(key_code: i32)

foreign import env "env"

foreign env {
	host_clear :: proc "c" (color: i32) ---
	host_circle :: proc "c" (x, y, radius, color: i32) ---
	host_rect :: proc "c" (x, y, width, height, color: i32) ---
	host_line :: proc "c" (x1, y1, x2, y2, color, width: i32) ---
	host_text :: proc "c" (x, y: i32, content: rawptr, content_len: i32, color, size: i32) ---

	host_width :: proc "c" () -> i32 ---
	host_height :: proc "c" () -> i32 ---

	host_set_frames :: proc "c" (active: i32) ---
	host_set_key_events :: proc "c" (active: i32) ---
	host_set_mouse_click :: proc "c" (active: i32) ---
	host_set_mouse_move :: proc "c" (active: i32) ---
}

frame_handler: Frame_Handler
mouse_click_handler: Mouse_Handler
mouse_move_handler: Mouse_Handler
key_press_handler: Key_Handler

width :: proc() -> i32 {
	return host_width()
}

height :: proc() -> i32 {
	return host_height()
}

clear :: proc(color: u32) {
	host_clear(i32(color))
}

circle :: proc(x, y, radius: i32, color: u32) {
	host_circle(x, y, radius, i32(color))
}

rect :: proc(x, y, width, height: i32, color: u32) {
	host_rect(x, y, width, height, i32(color))
}

line :: proc(x1, y1, x2, y2: i32, color: u32, line_width: i32 = 2) {
	host_line(x1, y1, x2, y2, i32(color), line_width)
}

text :: proc(x, y: i32, content: string, color: u32, size: i32 = 16) {
	host_text(x, y, raw_data(content), i32(len(content)), i32(color), size)
}

on_frame :: proc(handler: Frame_Handler) {
	frame_handler = handler
	if handler != nil {
		host_set_frames(1)
	} else {
		host_set_frames(0)
	}
}

on_mouse_click :: proc(handler: Mouse_Handler) {
	mouse_click_handler = handler
	if handler != nil {
		host_set_mouse_click(1)
	} else {
		host_set_mouse_click(0)
	}
}

on_mouse_move :: proc(handler: Mouse_Handler) {
	mouse_move_handler = handler
	if handler != nil {
		host_set_mouse_move(1)
	} else {
		host_set_mouse_move(0)
	}
}

on_key_press :: proc(handler: Key_Handler) {
	key_press_handler = handler
	if handler != nil {
		host_set_key_events(1)
	} else {
		host_set_key_events(0)
	}
}

// Exported bridge procedures: the page calls these to deliver events.

@(export)
screen_frame :: proc(time_ms: i32) {
	if frame_handler != nil do frame_handler(time_ms)
}

@(export)
screen_mouse_click :: proc(x, y: i32) {
	if mouse_click_handler != nil do mouse_click_handler(x, y)
}

@(export)
screen_mouse_move :: proc(x, y: i32) {
	if mouse_move_handler != nil do mouse_move_handler(x, y)
}

@(export)
screen_key_press :: proc(key_code: i32) {
	if key_press_handler != nil do key_press_handler(key_code)
}
