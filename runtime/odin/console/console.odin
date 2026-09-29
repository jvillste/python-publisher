// Odin runtime package for the game publishing page.
//
// A game imports this package as
//
//	import console "lib:console"
//
// and prints into the terminal with console.print / console.println
// and asks the player for one line with console.input.
package console

import "core:fmt"

foreign import env "env"

foreign env {
	host_input :: proc "c" (prompt: rawptr, prompt_len: i32, answer: rawptr, answer_cap: i32) -> i32 ---
}

// The page clips answers to the same length as the Python runtime.
INPUT_BUFFER_SIZE :: 4096

print :: proc(args: ..any) {
	fmt.print(..args)
}

println :: proc(args: ..any) {
	fmt.println(..args)
}

// input asks the player for one line of text.
//
// Returns the answer and true.  When the player cancels the input
// (the Stop button), returns ("", false) — a game should exit its
// loop then, exactly like a Python game that gets an EOFError.
input :: proc(prompt: string) -> (string, bool) {
	buffer: [INPUT_BUFFER_SIZE]u8
	length := host_input(raw_data(prompt), i32(len(prompt)), raw_data(buffer[:]), INPUT_BUFFER_SIZE)
	answer := ""
	if length >= 0 {
		answer = string(buffer[:length])
	}
	return answer, length >= 0
}
