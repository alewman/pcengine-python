// A just-enough stand-in for Mednafen's <mednafen/mednafen.h> so that pce_psg.cpp (read from
// reference/, not copied) compiles unchanged for scripts/psg_compare.py.
#pragma once
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int8_t int8;
typedef int16_t int16;
typedef int32_t int32;
typedef int64_t int64;
typedef uint8_t uint8;
typedef uint16_t uint16;
typedef uint32_t uint32;
typedef uint64_t uint64;

#define INLINE inline
#define MDFN_COLD
#define MDFN_FASTCALL
#define MDFN_UNLIKELY(x) (x)

namespace Mednafen {
struct StateMem {};
struct SFORMAT { int dummy; };
}
#define SFVARN(a, b) Mednafen::SFORMAT{0}
#define SFVAR(a) Mednafen::SFORMAT{0}
#define SFEND Mednafen::SFORMAT{0}
#define MDFNSS_StateAction(a, b, c, d, e) ((void)0)
