#pragma once
// effectGrain.h — Film Grain effect declarations

#include "ofxCore.h"

// Describe the grain effect (registers params and clips in descriptor context)
OfxStatus grainDescribe(OfxImageEffectHandle effect);

// Describe in a specific context
OfxStatus grainDescribeInContext(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs);

// Render one frame
OfxStatus grainRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs);
