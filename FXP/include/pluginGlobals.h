#pragma once
// pluginGlobals.h — Shared host suite pointers and global state

#include "ofxCore.h"

// Global host suites — populated during OfxActionLoad
extern OfxHost*                 gHost;
extern OfxPropertySuiteV1*      gPropSuite;
extern OfxParameterSuiteV1*     gParamSuite;
extern OfxImageEffectSuiteV1*   gEffectSuite;

// Convenience macro for checking OFX status codes
#define OFX_CHECK(expr)  do { OfxStatus _s = (expr); if (_s != kOfxStatOK) return _s; } while(0)

// Convenience: get suites with a single call
inline OfxStatus fetchSuites()
{
    if (!gHost) return kOfxStatErrBadHandle;
    gPropSuite   = (OfxPropertySuiteV1*)   gHost->fetchSuite(gHost->host, kOfxPropertySuite,    1);
    gParamSuite  = (OfxParameterSuiteV1*)  gHost->fetchSuite(gHost->host, kOfxParameterSuite,   1);
    gEffectSuite = (OfxImageEffectSuiteV1*)gHost->fetchSuite(gHost->host, kOfxImageEffectSuite, 1);
    if (!gPropSuite || !gParamSuite || !gEffectSuite) return kOfxStatErrMissingHostFeature;
    return kOfxStatOK;
}

// Pixel access helpers
inline unsigned char* getPixelByte(void* data, int rowBytes, int x, int y)
{
    return (unsigned char*)data + y * rowBytes + x * 4;
}

inline float* getPixelFloat(void* data, int rowBytes, int x, int y)
{
    return (float*)((unsigned char*)data + y * rowBytes + x * 4 * sizeof(float));
}

// Clamp helpers
inline float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
inline int   clampi(int v, int lo, int hi)        { return v < lo ? lo : (v > hi ? hi : v); }
