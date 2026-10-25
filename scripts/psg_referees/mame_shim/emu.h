// A just-enough stand-in for MAME's "emu.h" so that MAME 0.285's src/devices/sound/c6280.cpp
// compiles unchanged for scripts/psg_compare.py (the file is read from reference/, never copied).
// Everything private is made public so the harness can drive the device.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int16_t s16;
typedef int32_t s32;
typedef uint32_t offs_t;
typedef int device_type;

#define BIT(x, n) (((x) >> (n)) & 1)
#define ATTR_COLD
#define NAME(x) x
#define STRUCT_MEMBER(array, member) array
#define DECLARE_DEVICE_TYPE(type, cls) extern const device_type type;
#define DEFINE_DEVICE_TYPE(type, cls, shortname, fullname) const device_type type = 1;

struct machine_config {};
namespace feature { enum { SOUND = 1 }; }
typedef int feature_type;

struct sound_stream {
	int count = 1;
	s32 left = 0, right = 0;
	int samples() const { return count; }
	void put_int(int channel, int, s32 value, s32) { (channel ? right : left) = value; }
	void update() {}
	void set_sample_rate(u32) {}
};

struct device_t {
	device_t(const machine_config &, device_type, const char *, device_t *, u32 c) : m_clock(c) {}
	virtual ~device_t() {}
	u32 clock() const { return m_clock; }
	template <class... A> void save_item(A &&...) {}
	virtual void device_start() {}
	virtual void device_reset() {}
	virtual void device_clock_changed() {}
	u32 m_clock;
};

struct device_sound_interface {
	device_sound_interface(const machine_config &, device_t &) {}
	virtual ~device_sound_interface() {}
	sound_stream *stream_alloc(int, int, u32) { static sound_stream s; return &s; }
	virtual void sound_stream_update(sound_stream &) {}
};

#define protected public
#define private public
