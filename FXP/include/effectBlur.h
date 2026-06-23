#pragma once
// effectBlur.h — Gaussian Blur effect declarations

#include "ofxCore.h"

OfxStatus blurDescribe(OfxImageEffectHandle effect);
OfxStatus blurDescribeInContext(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs);
OfxStatus blurRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs);
