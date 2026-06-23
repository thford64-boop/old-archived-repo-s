#pragma once
// effectTransition.h — Cross-Dissolve + Zoom Transition declarations

#include "ofxCore.h"

OfxStatus transitionDescribe(OfxImageEffectHandle effect);
OfxStatus transitionDescribeInContext(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs);
OfxStatus transitionRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs);
