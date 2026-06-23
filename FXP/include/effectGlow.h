#pragma once
// effectGlow.h — Glow / Bloom effect declarations

#include "ofxCore.h"

OfxStatus glowDescribe(OfxImageEffectHandle effect);
OfxStatus glowDescribeInContext(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs);
OfxStatus glowRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs);
