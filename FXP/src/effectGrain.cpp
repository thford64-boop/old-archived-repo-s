// effectGrain.cpp — Animated Film Grain Filter
// Parameters: Intensity (0-1), Grain Size (1-8), Color Grain toggle, Speed multiplier

#include "effectGrain.h"
#include "pluginGlobals.h"
#include <cmath>
#include <cstring>

// ─────────────────────────────────────────────────────────────────────────────
// LCG pseudo-random number generator — fast, seedable, no stdlib dependency
// ─────────────────────────────────────────────────────────────────────────────
static inline unsigned int lcgRand(unsigned int& state)
{
    state = state * 1664525u + 1013904223u;
    return state;
}

static inline float lcgRandFloat(unsigned int& state)
{
    return (float)(lcgRand(state) & 0x00FFFFFFu) / (float)0x01000000u; // [0,1)
}

// ─────────────────────────────────────────────────────────────────────────────
// Describe — registers plugin-level properties
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus grainDescribe(OfxImageEffectHandle effect)
{
    OfxPropertySetHandle effectProps;
    OFX_CHECK(gEffectSuite->getPropertySet(effect, &effectProps));

    gPropSuite->propSetString(effectProps, kOfxPropLabel,      0, "FXPack Film Grain");
    gPropSuite->propSetString(effectProps, kOfxPropShortLabel, 0, "Grain");
    gPropSuite->propSetString(effectProps, kOfxPropLongLabel,  0, "FXPack: Animated Film Grain");
    gPropSuite->propSetString(effectProps, kOfxPluginDescription, 0,
        "Adds animated, per-frame pseudo-random film grain with intensity and size controls.");

    gPropSuite->propSetString(effectProps, kOfxImageEffectPropSupportedContexts, 0,
        kOfxImageEffectContextFilter);

    gPropSuite->propSetString(effectProps, kOfxImageEffectPropSupportedPixelDepths, 0,
        kOfxBitDepthByte);
    gPropSuite->propSetString(effectProps, kOfxImageEffectPropSupportedPixelDepths, 1,
        kOfxBitDepthFloat);

    gPropSuite->propSetInt(effectProps, kOfxImageEffectPropSupportsMultiResolution, 0, 1);
    gPropSuite->propSetInt(effectProps, kOfxImageEffectPropSupportsTiles,           0, 0);
    gPropSuite->propSetInt(effectProps, kOfxImageEffectPropTemporalClipAccess,      0, 0);
    gPropSuite->propSetString(effectProps, kOfxImageEffectPropRenderThreadSafety,   0,
        kOfxImageEffectRenderFullySafe);

    return kOfxStatOK;
}

// ─────────────────────────────────────────────────────────────────────────────
// DescribeInContext — defines clips and parameters
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus grainDescribeInContext(OfxImageEffectHandle effect, OfxPropertySetHandle /*inArgs*/)
{
    // ── Clips ──────────────────────────────────────────────────────────────
    OfxPropertySetHandle clipProps;
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectSimpleSourceClipName, &clipProps));
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectOutputClipName, &clipProps));

    // ── Parameters ────────────────────────────────────────────────────────
    OfxParamSetHandle paramSet;
    OFX_CHECK(gEffectSuite->getParamSet(effect, &paramSet));

    OfxPropertySetHandle paramProps;

    // Intensity
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble, "grainIntensity", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Grain Intensity");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "Amount of grain to add (0 = none, 1 = heavy)");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 0.3);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 1.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDisplayMin, 0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDisplayMax, 0, 1.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 1);

    // Grain Size
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeInteger, "grainSize", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,   0, "Grain Size");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,    0, "Size of individual grain particles (1=finest)");
    gPropSuite->propSetInt(paramProps,    kOfxParamPropDefault, 0, 1);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropMin,     0, 1);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropMax,     0, 8);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,0, 0);

    // Color Grain toggle
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeBoolean, "grainColor", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,   0, "Color Grain");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,    0, "Enable colored (RGB) grain instead of luminance-only grain");
    gPropSuite->propSetInt(paramProps,    kOfxParamPropDefault, 0, 0); // off by default
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,0, 0);

    // Speed
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble, "grainSpeed", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Animation Speed");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "How fast the grain pattern changes per frame");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 1.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 0.1);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 10.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDisplayMin, 0, 0.1);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDisplayMax, 0, 5.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 0);

    return kOfxStatOK;
}

// ─────────────────────────────────────────────────────────────────────────────
// Render
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus grainRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs)
{
    // ── Fetch time and render scale ────────────────────────────────────────
    double time = 0.0;
    gPropSuite->propGetDouble(inArgs, kOfxPropTime, 0, &time);

    double renderScaleX = 1.0, renderScaleY = 1.0;
    gPropSuite->propGetDouble(inArgs, kOfxImageEffectPropRenderScale, 0, &renderScaleX);
    gPropSuite->propGetDouble(inArgs, kOfxImageEffectPropRenderScale, 1, &renderScaleY);

    // ── Read parameters ───────────────────────────────────────────────────
    OfxParamSetHandle paramSet;
    OFX_CHECK(gEffectSuite->getParamSet(effect, &paramSet));

    OfxParamHandle hIntensity, hSize, hColor, hSpeed;
    gParamSuite->paramGetHandle(paramSet, "grainIntensity", &hIntensity, nullptr);
    gParamSuite->paramGetHandle(paramSet, "grainSize",      &hSize,      nullptr);
    gParamSuite->paramGetHandle(paramSet, "grainColor",     &hColor,     nullptr);
    gParamSuite->paramGetHandle(paramSet, "grainSpeed",     &hSpeed,     nullptr);

    double intensity = 0.3;
    int    grainSize = 1;
    int    colorGrain = 0;
    double speed = 1.0;

    gParamSuite->paramGetValueAtTime(hIntensity, time, &intensity);
    gParamSuite->paramGetValueAtTime(hSize,      time, &grainSize);
    gParamSuite->paramGetValueAtTime(hColor,     time, &colorGrain);
    gParamSuite->paramGetValueAtTime(hSpeed,     time, &speed);

    // ── Fetch source and output images ────────────────────────────────────
    OfxImageClipHandle srcClip, dstClip;
    gEffectSuite->clipGetHandle(effect, kOfxImageEffectSimpleSourceClipName, &srcClip, nullptr);
    gEffectSuite->clipGetHandle(effect, kOfxImageEffectOutputClipName,       &dstClip, nullptr);

    OfxPropertySetHandle srcImg, dstImg;
    OFX_CHECK(gEffectSuite->clipGetImage(srcClip, time, nullptr, &srcImg));
    OFX_CHECK(gEffectSuite->clipGetImage(dstClip, time, nullptr, &dstImg));

    // ── Get image data ────────────────────────────────────────────────────
    void*  srcData    = nullptr;  gPropSuite->propGetPointer(srcImg, kOfxImagePropData,     0, &srcData);
    void*  dstData    = nullptr;  gPropSuite->propGetPointer(dstImg, kOfxImagePropData,     0, &dstData);
    int    srcRowBytes = 0;       gPropSuite->propGetInt(srcImg, kOfxImagePropRowBytes,     0, &srcRowBytes);
    int    dstRowBytes = 0;       gPropSuite->propGetInt(dstImg, kOfxImagePropRowBytes,     0, &dstRowBytes);

    OfxRectI bounds = {0,0,0,0};
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 0, &bounds.x1);
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 1, &bounds.y1);
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 2, &bounds.x2);
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 3, &bounds.y2);

    char* pixelDepthStr = nullptr;
    gPropSuite->propGetString(srcImg, kOfxImageEffectPropPixelDepth, 0, &pixelDepthStr);
    bool isFloat = (pixelDepthStr && std::strcmp(pixelDepthStr, kOfxBitDepthFloat) == 0);

    // ── Per-frame unique seed derived from time and speed ─────────────────
    // Multiplying time by speed gives faster grain animation at high speeds
    unsigned int frameSeed = (unsigned int)(time * speed * 12345.0 + 9999.0);

    int width  = bounds.x2 - bounds.x1;
    int height = bounds.y2 - bounds.y1;

    if (isFloat)
    {
        // ──── Float path (32-bit) ─────────────────────────────────────────
        for (int y = 0; y < height; ++y)
        {
            // Row-based seed variation
            unsigned int rowSeed = frameSeed + (unsigned int)(y * 65537u);

            float* srcRow = (float*)((unsigned char*)srcData + y * srcRowBytes);
            float* dstRow = (float*)((unsigned char*)dstData + y * dstRowBytes);

            for (int x = 0; x < width; ++x)
            {
                // All pixels in a grain block share the same noise value
                int bx = x / grainSize;
                int by = y / grainSize;
                unsigned int pixSeed = frameSeed ^ ((unsigned int)(bx * 73856093u) ^ (unsigned int)(by * 19349663u));

                float noiseL = lcgRandFloat(pixSeed) * 2.0f - 1.0f;  // [-1, 1]

                float noiseR = noiseL;
                float noiseG = noiseL;
                float noiseB = noiseL;

                if (colorGrain)
                {
                    // Independent channel noise for color grain
                    unsigned int s2 = pixSeed + 0xDEADBEEFu;
                    unsigned int s3 = pixSeed + 0xCAFEBABEu;
                    noiseR = lcgRandFloat(pixSeed) * 2.0f - 1.0f;
                    noiseG = lcgRandFloat(s2)      * 2.0f - 1.0f;
                    noiseB = lcgRandFloat(s3)      * 2.0f - 1.0f;
                }

                int idx = x * 4;
                dstRow[idx + 0] = clampf(srcRow[idx + 0] + (float)intensity * noiseR, 0.0f, 1.0f);
                dstRow[idx + 1] = clampf(srcRow[idx + 1] + (float)intensity * noiseG, 0.0f, 1.0f);
                dstRow[idx + 2] = clampf(srcRow[idx + 2] + (float)intensity * noiseB, 0.0f, 1.0f);
                dstRow[idx + 3] = srcRow[idx + 3]; // preserve alpha
            }
        }
    }
    else
    {
        // ──── Byte path (8-bit) ────────────────────────────────────────────
        for (int y = 0; y < height; ++y)
        {
            unsigned char* srcRow = (unsigned char*)srcData + y * srcRowBytes;
            unsigned char* dstRow = (unsigned char*)dstData + y * dstRowBytes;

            for (int x = 0; x < width; ++x)
            {
                int bx = x / grainSize;
                int by = y / grainSize;
                unsigned int pixSeed = frameSeed ^ ((unsigned int)(bx * 73856093u) ^ (unsigned int)(by * 19349663u));

                // Noise in [-127, 127]
                int noiseL = (int)(lcgRandFloat(pixSeed) * 255.0f) - 127;
                int noiseR = noiseL, noiseG = noiseL, noiseB = noiseL;

                if (colorGrain)
                {
                    unsigned int s2 = pixSeed + 0xDEADBEEFu;
                    unsigned int s3 = pixSeed + 0xCAFEBABEu;
                    noiseR = (int)(lcgRandFloat(pixSeed) * 255.0f) - 127;
                    noiseG = (int)(lcgRandFloat(s2)      * 255.0f) - 127;
                    noiseB = (int)(lcgRandFloat(s3)      * 255.0f) - 127;
                }

                int scale = (int)(intensity * 127.0);
                int idx   = x * 4;

                dstRow[idx + 0] = (unsigned char)clampi(srcRow[idx + 0] + (noiseR * scale) / 127, 0, 255);
                dstRow[idx + 1] = (unsigned char)clampi(srcRow[idx + 1] + (noiseG * scale) / 127, 0, 255);
                dstRow[idx + 2] = (unsigned char)clampi(srcRow[idx + 2] + (noiseB * scale) / 127, 0, 255);
                dstRow[idx + 3] = srcRow[idx + 3];
            }
        }
    }

    gEffectSuite->clipReleaseImage(srcImg);
    gEffectSuite->clipReleaseImage(dstImg);
    return kOfxStatOK;
}
