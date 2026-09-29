// Odin runtime package for the game publishing page.
//
// A game imports this package as
//
//	import audio "lib:audio"
//
// and plays sounds: audio.play synthesizes a sawtooth oscillator whose
// volume follows an ADSR envelope, and audio.play_samples plays a
// buffer of samples that the game has generated itself.
package audio

foreign import env "env"

foreign env {
	host_play_sound :: proc "c" (frequency, duration_seconds, attack, decay, sustain, release, volume: f32) ---
	host_play_samples :: proc "c" (samples: rawptr, sample_count, sample_rate: i32) ---
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

// play_samples plays one buffer of samples that the game has generated
// itself: samples holds one value per SAMPLE_RATE-th of a second, where
// -1 is the loudest negative value, 0 is silence and 1 is the loudest
// positive value.  The page clamps values outside -1..1 to silence-safe
// levels, so a game can use any scale and divide by its peak loudness
// before playing.
//
// sample_rate is the playback rate in Hz, for example 22050 or 44100;
// it must match the rate the samples were generated with or the sound
// plays at the wrong speed and pitch.
//
// The buffer can be reused: the page copies the samples before playing,
// so the game may keep generating into the same slice.
play_samples :: proc(samples: []f32, sample_rate: i32) {
	if len(samples) == 0 {
		return
	}
	host_play_samples(raw_data(samples), i32(len(samples)), sample_rate)
}
