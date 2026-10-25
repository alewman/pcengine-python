// Harness: MAME 0.285's c6280 (compiled from reference/, not copied) driven step by step.
// stdin-free: argv = LOG OUT STEPS START (output only from step START on). LOG: records of <I step, B register, B value> (little endian).
// OUT: per step two int32 (left, right): the sums MAME's sound_stream_update puts into the stream.
#include "emu.h"
#include "c6280.h"
#include <cstdio>
#include <cstdlib>
#include <vector>

int main(int argc, char **argv) {
	if (argc < 4) return 2;
	FILE *log = fopen(argv[1], "rb");
	FILE *out = fopen(argv[2], "wb");
	long steps = atol(argv[3]);
	long start = argc > 4 ? atol(argv[4]) : 0;
	if (!log || !out) return 2;
	std::vector<unsigned char> raw;
	unsigned char buf[6];
	while (fread(buf, 1, 6, log) == 6) raw.insert(raw.end(), buf, buf + 6);
	machine_config cfg;
	c6280_device dev(cfg, "psg", nullptr, 3579545);
	dev.device_start();
	dev.device_reset();
	size_t at = 0;
	sound_stream stream;
	for (long s = 0; s < steps; s++) {
		while (at + 6 <= raw.size()) {
			uint32_t step = raw[at] | raw[at + 1] << 8 | raw[at + 2] << 16 | (uint32_t)raw[at + 3] << 24;
			if ((long)step > s) break;
			dev.c6280_w(raw[at + 4], raw[at + 5]);
			at += 6;
		}
		stream.left = stream.right = 0;
		dev.sound_stream_update(stream);
		int32_t pair[2] = {stream.left, stream.right};
		if (s >= start) fwrite(pair, 4, 2, out);
	}
	fclose(out);
	return 0;
}
