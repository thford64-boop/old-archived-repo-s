#pragma once
// effectShake.h — Camera Shake effect declarations

#include "ofxCore.h"

OfxStatus shakeDescribe(OfxImageEffectHandle effect);
OfxStatus shakeDescribeInContext(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs);
OfxStatus shakeRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs);
