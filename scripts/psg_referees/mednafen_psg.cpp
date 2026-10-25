// Harness: Mednafen's PCE_PSG (compiled from reference/, not copied) driven step by step.
// argv = LOG OUT STEPS REVISION(0 = HuC6280, 1 = HuC6280A) START. LOG: <I step, B register, B value>.
// OUT: per step two int32 (left, right): the sum over the six channels of the output level the
// model holds at the start of that step (blip_prev_samp, refreshed through each channel's own
// output function so a register write shows at once).
#define private public
#include <mednafen/mednafen.h>
#include "pce_psg.h"
#undef private
#include <vector>
using namespace Mednafen;

int main(int argc, char **argv) {
	if (argc < 5) return 2;
	FILE *log = fopen(argv[1], "rb");
	FILE *out = fopen(argv[2], "wb");
	long steps = atol(argv[3]);
	int revision = atoi(argv[4]);
	long start = argc > 5 ? atol(argv[5]) : 0;
	if (!log || !out) return 2;
	std::vector<unsigned char> raw;
	unsigned char buf[6];
	while (fread(buf, 1, 6, log) == 6) raw.insert(raw.end(), buf, buf + 6);
	static int32 hr[2][0x10020];
	PCE_PSG psg(hr[0], hr[1], revision);
	size_t at = 0;
	for (long s = 0; s < steps; s++) {
		int32 ts = (int32)(2 * s);  // CPU clocks: two per PSG step
		while (at + 6 <= raw.size()) {
			uint32_t step = raw[at] | raw[at + 1] << 8 | raw[at + 2] << 16 | (uint32_t)raw[at + 3] << 24;
			if ((long)step > s) break;
			psg.Write(ts, raw[at + 4], raw[at + 5]);
			at += 6;
		}
		psg.Update(ts);
		int32 l = 0, r = 0;
		for (int c = 0; c < 6; c++) {
			psg_channel *ch = &psg.channel[c];
			(psg.*ch->UpdateOutput)(ts, ch);
			l += ch->blip_prev_samp[0];
			r += ch->blip_prev_samp[1];
		}
		int32_t pair[2] = {l, r};
		if (s >= start) fwrite(pair, 4, 2, out);
		// keep the blip buffers from growing: they are not read
		if ((s & 0x3FFF) == 0) { memset(hr, 0, sizeof(hr)); }
		if (ts > 0x3FFFFFF0) break;
	}
	fclose(out);
	return 0;
}
