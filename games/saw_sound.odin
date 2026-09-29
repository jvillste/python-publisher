// Title: Saw wave with an ADSR envelope
package main

import audio "lib:audio"
import screen "lib:screen"

// The sound: a sawtooth tone whose volume follows an ADSR envelope.
// The attack rises to full volume, the decay falls to the sustain level,
// the note holds there and the release fades it back to silence.
FREQUENCY     :: 220.0
DURATION      :: 3.4
ATTACK        :: 0.2
DECAY         :: 1.50
SUSTAIN_LEVEL :: 0.8
RELEASE       :: 1.25
VOLUME        :: 0.2

// The number of samples per second that the sound is generated at.
// The page plays the buffer back at exactly this rate.
SAMPLE_RATE :: 22050

// The sustain hold lasts until the release begins.
SUSTAIN_HOLD :: DURATION - ATTACK - DECAY - RELEASE

// The sound starts again this often, in milliseconds.
REPEAT_MS :: 4700

BACKGROUND_COLOR :: 0x0f172a
ENVELOPE_COLOR   :: 0x38bdf8
WAVEFORM_COLOR   :: 0xfbbf24
PLAYHEAD_COLOR   :: 0xf87171
GUIDE_COLOR      :: 0x334155
LABEL_COLOR      :: 0x94a3b8
TITLE_COLOR      :: 0xe2e8f0

// Layout: the envelope plot on top, the waveform plot below.  Both use
// the same amplitude scale, where the top edge is the peak volume.
PLOT_LEFT  :: 56
PLOT_RIGHT :: 584
PLOT_WIDTH :: PLOT_RIGHT - PLOT_LEFT
PLOT_STEP  :: 2

ENVELOPE_TOP    :: 70
ENVELOPE_BOTTOM :: 180
ENVELOPE_HEIGHT :: ENVELOPE_BOTTOM - ENVELOPE_TOP

WAVE_MID  :: 300
WAVE_HALF :: 80

// The moving line that shows where in the sound we currently are.  Only
// the narrow strip around it is redrawn on every frame; the whole picture
// is redrawn when the sound starts again.
PLAYHEAD_MARGIN       :: 2
ENVELOPE_STRIP_TOP    :: ENVELOPE_TOP - 4
ENVELOPE_STRIP_HEIGHT :: ENVELOPE_BOTTOM - ENVELOPE_STRIP_TOP
WAVE_STRIP_TOP        :: WAVE_MID - WAVE_HALF - 4
WAVE_STRIP_HEIGHT     :: WAVE_MID + WAVE_HALF - WAVE_STRIP_TOP

// How many generated samples are inspected per one pixel wide column.
SAMPLES_PER_COLUMN :: 4

// The generated sound.  It is filled once before the game starts, played
// from the start on every repeat and read on every redrawn pixel column.
samples: [i32(f32(SAMPLE_RATE) * DURATION)]f32

last_sound_ms: i32 = -REPEAT_MS
playhead_x: i32 = PLOT_LEFT

// envelope_shape returns the ADSR envelope (0..1) at time seconds.
envelope_shape :: proc(seconds: f32) -> f32 {
	if seconds <= 0 || seconds >= DURATION {
		return 0
	}
	time := seconds
	if time < ATTACK {
		return time / ATTACK
	}
	time -= ATTACK
	if time < DECAY {
		return 1.0 + (SUSTAIN_LEVEL - 1.0) * time / DECAY
	}
	time -= DECAY
	if time < SUSTAIN_HOLD {
		return SUSTAIN_LEVEL
	}
	time -= SUSTAIN_HOLD
	if time < RELEASE {
		return SUSTAIN_LEVEL * (1.0 - time / RELEASE)
	}
	return 0
}

// saw_sample returns one sample of the saw wave shaped by the envelope.
// The phase of the wave is truncated into 0..1 instead of using a modulo,
// so the sample does not need a math library.
saw_sample :: proc(seconds: f32) -> f32 {
	phase := seconds * FREQUENCY
	phase -= f32(i32(phase))
	return (2.0 * phase - 1.0) * envelope_shape(seconds)
}

// generate_samples fills the sample buffer with the whole sound: every
// value is one sample of the saw wave at its point of time, scaled into
// the -1..1 range that audio.play_samples expects.
generate_samples :: proc() {
	for index: i32 = 0; index < i32(len(samples)); index += 1 {
		seconds := f32(index) / f32(SAMPLE_RATE)
		samples[index] = saw_sample(seconds) * VOLUME
	}
}

// samples_between returns the smallest and largest sample that the
// buffer holds between two points of time of the sound.
samples_between :: proc(start_seconds, end_seconds: f32) -> (minimum, maximum: f32) {
	first := clamp(i32(start_seconds * f32(SAMPLE_RATE)), 0, i32(len(samples)) - 1)
	last := clamp(i32(end_seconds * f32(SAMPLE_RATE)), 0, i32(len(samples)) - 1)
	minimum, maximum = samples[first], samples[first]
	for index: i32 = first + 1; index <= last; index += 1 {
		minimum = min(minimum, samples[index])
		maximum = max(maximum, samples[index])
	}
	return
}

x_for_time :: proc(seconds: f32) -> i32 {
	return PLOT_LEFT + i32(seconds / DURATION * f32(PLOT_WIDTH))
}

time_for_x :: proc(x: i32) -> f32 {
	return DURATION * f32(x - PLOT_LEFT) / f32(PLOT_WIDTH)
}

envelope_y :: proc(shape: f32) -> i32 {
	return ENVELOPE_BOTTOM - i32(shape * f32(ENVELOPE_HEIGHT))
}

// wave_y maps a sample value onto the waveform plot.  The samples are
// scaled by the peak volume, so the loudest sample reaches both edges.
wave_y :: proc(amplitude: f32) -> i32 {
	return WAVE_MID - i32(amplitude / VOLUME * f32(WAVE_HALF))
}

// draw_h_line draws a horizontal guide line, but only the part that
// belongs to the x range that is currently being (re)drawn.
draw_h_line :: proc(y: i32, only_from, only_to: i32, color: u32) {
	from := max(PLOT_LEFT, only_from)
	to := min(PLOT_RIGHT, only_to)
	if from <= to do screen.line(from, y, to, y, color, 1)
}

draw_sustain_guide :: proc(only_from, only_to: i32) {
	from := max(x_for_time(ATTACK + DECAY), only_from)
	to := min(x_for_time(ATTACK + DECAY + SUSTAIN_HOLD), only_to)
	if from < to {
		y := envelope_y(SUSTAIN_LEVEL)
		screen.line(from, y, to, y, GUIDE_COLOR, 1)
	}
}

draw_segment_letter :: proc(start_seconds, end_seconds: f32, letter: string, only_from, only_to: i32) {
	if (end_seconds - start_seconds) / DURATION * f32(PLOT_WIDTH) < 14.0 {
		return
	}
	center := x_for_time((start_seconds + end_seconds) * 0.5)
	if center + 5 < only_from || center - 5 > only_to {
		return
	}
	screen.text(center - 4, ENVELOPE_TOP - 10, letter, LABEL_COLOR, 12)
}

// draw_envelope_curve draws the envelope plot between the x positions
// only_from and only_to.  The whole picture uses PLOT_LEFT and PLOT_RIGHT;
// the narrow playhead strip reuses the same procedure to redraw itself.
draw_envelope_curve :: proc(only_from, only_to: i32) {
	draw_h_line(ENVELOPE_BOTTOM, only_from, only_to, GUIDE_COLOR)
	draw_sustain_guide(only_from, only_to)
	for x: i32 = PLOT_LEFT + PLOT_STEP; x <= PLOT_RIGHT; x += PLOT_STEP {
		// The segment spans x - PLOT_STEP .. x; draw it when it
		// intersects the range that is being drawn.
		if x < only_from || x - PLOT_STEP > only_to {
			continue
		}
		from_y := envelope_y(envelope_shape(time_for_x(x - PLOT_STEP)))
		to_y := envelope_y(envelope_shape(time_for_x(x)))
		screen.line(x - PLOT_STEP, from_y, x, to_y, ENVELOPE_COLOR, 2)
	}
	draw_segment_letter(0.0, ATTACK, "A", only_from, only_to)
	draw_segment_letter(ATTACK, ATTACK + DECAY, "D", only_from, only_to)
	draw_segment_letter(ATTACK + DECAY, ATTACK + DECAY + SUSTAIN_HOLD, "S", only_from, only_to)
	draw_segment_letter(ATTACK + DECAY + SUSTAIN_HOLD, DURATION, "R", only_from, only_to)
}

// draw_waveform_bars draws the generated waveform as one vertical bar per
// pixel column, spanning the smallest and largest sample of the column,
// between the x positions only_from and only_to.
draw_waveform_bars :: proc(only_from, only_to: i32) {
	draw_h_line(WAVE_MID, only_from, only_to, GUIDE_COLOR)
	for column: i32 = PLOT_LEFT; column < PLOT_RIGHT; column += 1 {
		if column < only_from || column > only_to {
			continue
		}
		minimum, maximum := samples_between(time_for_x(column), time_for_x(column + 1))
		if minimum == 0 && maximum == 0 {
			continue
		}
		top := wave_y(maximum)
		bottom := wave_y(minimum)
		if bottom <= top do bottom = top + 1
		screen.rect(column, top, 1, bottom - top, WAVEFORM_COLOR)
	}
}

draw_everything :: proc() {
	screen.clear(BACKGROUND_COLOR)
	screen.text(PLOT_LEFT, 14, "Saw wave with an ADSR envelope", TITLE_COLOR, 16)
	screen.text(PLOT_LEFT, ENVELOPE_TOP - 24, "ADSR envelope", LABEL_COLOR, 13)
	screen.text(PLOT_LEFT, WAVE_MID - WAVE_HALF - 24, "Generated waveform", LABEL_COLOR, 13)
	draw_envelope_curve(PLOT_LEFT, PLOT_RIGHT)
	draw_waveform_bars(PLOT_LEFT, PLOT_RIGHT)
	screen.text(PLOT_LEFT, ENVELOPE_BOTTOM + 8, "0", LABEL_COLOR, 11)
	screen.text(PLOT_RIGHT - 48, ENVELOPE_BOTTOM + 8, "400 ms", LABEL_COLOR, 11)
}

// draw_playhead_strip erases the strip around the given playhead position
// and redraws the plots inside it.
draw_playhead_strip :: proc(x: i32) {
	screen.rect(
		x - PLAYHEAD_MARGIN,
		ENVELOPE_STRIP_TOP,
		PLAYHEAD_MARGIN * 2 + 1,
		ENVELOPE_STRIP_HEIGHT,
		BACKGROUND_COLOR,
	)
	screen.rect(
		x - PLAYHEAD_MARGIN,
		WAVE_STRIP_TOP,
		PLAYHEAD_MARGIN * 2 + 1,
		WAVE_STRIP_HEIGHT,
		BACKGROUND_COLOR,
	)
	draw_envelope_curve(x - PLAYHEAD_MARGIN, x + PLAYHEAD_MARGIN)
	draw_waveform_bars(x - PLAYHEAD_MARGIN, x + PLAYHEAD_MARGIN)
}

// update_playhead moves the playhead line to its new position.  A frame
// that just redrew everything only needs the line itself.
update_playhead :: proc(time_ms: i32, just_redrew: bool) {
	elapsed := min(f32(time_ms - last_sound_ms), DURATION * 1000.0)
	x := x_for_time(elapsed / 1000.0)
	if x < PLOT_LEFT do x = PLOT_LEFT
	if !just_redrew {
		if x == playhead_x {
			return
		}
		draw_playhead_strip(playhead_x)
	}
	screen.line(x, ENVELOPE_STRIP_TOP, x, ENVELOPE_BOTTOM, PLAYHEAD_COLOR, 1)
	screen.line(x, WAVE_STRIP_TOP, x, WAVE_MID + WAVE_HALF, PLAYHEAD_COLOR, 1)
	playhead_x = x
}

update :: proc(time_ms: i32) {
	just_redrew := false
	if time_ms - last_sound_ms >= REPEAT_MS {
		last_sound_ms = time_ms
		audio.play_samples(samples[:], SAMPLE_RATE)
		draw_everything()
		playhead_x = PLOT_LEFT
		just_redrew = true
	}
	update_playhead(time_ms, just_redrew)
}

main :: proc() {
	generate_samples()
	draw_everything()
	screen.on_frame(update)
}
