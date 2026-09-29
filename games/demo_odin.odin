// Title: Odin-demo (grafiikka)
package main

import screen "lib:screen"

RADIUS :: 10

x: f32 = 300
y: f32 = 200
dx: f32 = 120
dy: f32 = 90
previous_time: i32 = -1

draw :: proc() {
	screen.clear(0x0f172a)
	screen.circle(i32(x), i32(y), RADIUS, 0xfacc15)
}

update :: proc(time_ms: i32) {
	if previous_time < 0 {
		previous_time = time_ms
		return
	}
	seconds := f32(time_ms - previous_time) / 1000.0
	previous_time = time_ms
	x += dx * seconds
	y += dy * seconds
	if x < RADIUS || x > f32(screen.width()) - RADIUS {
		dx = -dx
	}
	if y < RADIUS || y > f32(screen.height()) - RADIUS {
		dy = -dy
	}
	draw()
}

main :: proc() {
	draw()
	screen.on_frame(update)
}
