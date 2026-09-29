// Odin runtime package for the game publishing page.
//
// A game imports this package as
//
//	import audio "lib:audio"
//
// and plays short synthesized sounds with audio.play.  Every sound is a
// sawtooth oscillator whose volume follows an ADSR envelope: the volume
// rises from silence during the attack, falls to the sustain level during
// the decay, holds there and finally fades to silence during the release.
// The page shows the envelope and the generated waveform on its Sound tab.
package audio

foreign import env "env"

foreign env {
	host_play_sound :: proc "c" (frequency, duration_seconds, attack, decay, sustain, release, volume: f32) ---
}

// play sounds one note: a sawtooth oscillator at frequency Hz that lasts
// duration_seconds.
//
// The ADSR envelope shapes the volume: attack and decay are durations in
// seconds, sustain is the level (0..1) that the decay lands on and release
// is how long the fade-out takes.  Volume is the peak loudness (0..1).
// Every parameter except frequency and duration_seconds has a default, so
// audio.play(220, 0.4) plays a plain short note.
play :: proc(
	frequency: f32,
	duration_seconds: f32,
	attack: f32 = 0.01,
	decay: f32 = 0.1,
	sustain: f32 = 0.6,
	release: f32 = 0.2,
	volume: f32 = 0.5,
) {
	host_play_sound(frequency, duration_seconds, attack, decay, sustain, release, volume)
}
