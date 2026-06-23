// effectShake.cpp — Camera Shake Filter
// Simulates handheld/earthquake camera motion via per-frame pixel offset.
// Parameters: Intensity, Frequency, Randomness

#include "effectShake.h"
#include "pluginGlobals.h"
#include <cmath>
#include <cstring>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// ─────────────────────────────────────────────────────────────────────────────
// Smooth noise via a simple hash-based approach
// Produces values in [-1, 1]
// ─────────────────────────────────────────────────────────────────────────────
static float smoothNoise1D(double t)
{
    int    i  = (int)std::floor(t);
    double f  = t - std::floor(t);
    // Smooth cubic fade
    double u  = f * f * (3.0 - 2.0 * f);

    // Hash two adjacent integer positions
    auto h = [](int n) -> float {
        unsigned int x = (unsigned int)n;
        x = x * 2747636419u + 2654435761u;
        x ^= (x >> 16);
        x *= 2246822519u;
        x ^= (x >> 13);
        x *= 3266489917u;
        x ^= (x >> 16);
        return (float)(x & 0x00FFFFFFu) / (float)0x01000000u * 2.0f - 1.0f;
    };

    return (float)((1.0 - u) * h(i) + u * h(i + 1));
}

// ─────────────────────────────────────────────────────────────────────────────
// Describe
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus shakeDescribe(OfxImageEffectHandle effect)
{
    OfxPropertySetHandle effectProps;
    OFX_CHECK(gEffectSuite->getPropertySet(effect, &effectProps));

    gPropSuite->propSetString(effectProps, kOfxPropLabel,      0, "FXPack Camera Shake");
    gPropSuite->propSetString(effectProps, kOfxPropShortLabel, 0, "Shake");
    gPropSuite->propSetString(effectProps, kOfxPropLongLabel,  0, "FXPack: Camera Shake");
    gPropSuite->propSetString(effectProps, kOfxPluginDescription, 0,
        "Simulates camera shake via animated frame offset with frequency and intensity controls.");

    gPropSuite->propSetString(effectProps, kOfxImageEffectPropSupportedContexts, 0,
        kOfxImageEffectContextFilter);

    gPropSuite->propSetString(effectProps, kOfxImageEffectPropSupportedPixelDepths, 0, kOfxBitDepthByte);
    gPropSuite->propSetString(effectProps, kOfxImageEffectPropSupportedPixelDepths, 1, kOfxBitDepthFloat);

    gPropSuite->propSetInt(effectProps, kOfxImageEffectPropSupportsTiles,         0, 0);
    gPropSuite->propSetInt(effectProps, kOfxImageEffectPropTemporalClipAccess,    0, 0);
    gPropSuite->propSetString(effectProps, kOfxImageEffectPropRenderThreadSafety, 0,
        kOfxImageEffectRenderFullySafe);

    return kOfxStatOK;
}

// ─────────────────────────────────────────────────────────────────────────────
// DescribeInContext
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus shakeDescribeInContext(OfxImageEffectHandle effect, OfxPropertySetHandle /*inArgs*/)
{
    OfxPropertySetHandle clipProps;
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectSimpleSourceClipName, &clipProps));
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectOutputClipName,       &clipProps));

    OfxParamSetHandle  paramSet;
    OFX_CHECK(gEffectSuite->getParamSet(effect, &paramSet));

    OfxPropertySetHandle paramProps;

    // Intensity (pixels at 100% scale)
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble, "shakeIntensity", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Intensity");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "Maximum shake displacement in pixels");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 20.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 200.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDisplayMin, 0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDisplayMax, 0, 100.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 1);

    // Frequency (shakes per second)
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble, "shakeFrequency", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Frequency");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "Shakes per second — higher = faster trembling");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 8.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 0.1);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 60.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDisplayMin, 0, 0.1);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDisplayMax, 0, 30.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 0);

    // Randomness (0 = sinusoidal, 1 = fully random)
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble, "shakeRandomness", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Randomness");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "0 = regular sine wave, 1 = fully random noise");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 0.7);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 1.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 0);

    // Rotation shake (degrees)
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble, "shakeRotation", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Max Rotation");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "Maximum rotation in degrees added by shake");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 1.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 15.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 0);

    return kOfxStatOK;
}

// ─────────────────────────────────────────────────────────────────────────────
// Render
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus shakeRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs)
{
    double time = 0.0;
    gPropSuite->propGetDouble(inArgs, kOfxPropTime, 0, &time);

    // ── Read params ───────────────────────────────────────────────────────
    OfxParamSetHandle paramSet;
    OFX_CHECK(gEffectSuite->getParamSet(effect, &paramSet));

    OfxParamHandle hIntensity, hFreq, hRandom, hRot;
    gParamSuite->paramGetHandle(paramSet, "shakeIntensity",  &hIntensity, nullptr);
    gParamSuite->paramGetHandle(paramSet, "shakeFrequency",  &hFreq,      nullptr);
    gParamSuite->paramGetHandle(paramSet, "shakeRandomness", &hRandom,    nullptr);
    gParamSuite->paramGetHandle(paramSet, "shakeRotation",   &hRot,       nullptr);

    double intensity   = 20.0;
    double frequency   = 8.0;
    double randomness  = 0.7;
    double maxRotation = 1.0;

    gParamSuite->paramGetValueAtTime(hIntensity, time, &intensity);
    gParamSuite->paramGetValueAtTime(hFreq,      time, &frequency);
    gParamSuite->paramGetValueAtTime(hRandom,    time, &randomness);
    gParamSuite->paramGetValueAtTime(hRot,       time, &maxRotation);

    // ── Compute shake offset for this frame ───────────────────────────────
    double t = time * frequency;

    // X and Y offsets: blend sine wave with smooth noise
    double sineX  = std::sin(t * 2.0 * M_PI);
    double sineY  = std::cos(t * 2.0 * M_PI * 1.3f);  // slightly different frequency

    double noiseX = smoothNoise1D(t * 1.0);
    double noiseY = smoothNoise1D(t * 1.0 + 123.456);

    double offsetX = intensity * ((1.0 - randomness) * sineX + randomness * noiseX);
    double offsetY = intensity * ((1.0 - randomness) * sineY + randomness * noiseY);

    // Rotation in radians
    double noiseRot = smoothNoise1D(t * 0.7 + 77.77);
    double rotation = maxRotation * (M_PI / 180.0) *
                      ((1.0 - randomness) * std::sin(t * 2.0 * M_PI * 0.8) +
                        randomness * noiseRot);

    // Round to integer pixel shift (cheap but correct for most uses)
    int dx = (int)std::round(offsetX);
    int dy = (int)std::round(offsetY);

    // ── Fetch images ──────────────────────────────────────────────────────
    OfxImageClipHandle srcClip, dstClip;
    gEffectSuite->clipGetHandle(effect, kOfxImageEffectSimpleSourceClipName, &srcClip, nullptr);
    gEffectSuite->clipGetHandle(effect, kOfxImageEffectOutputClipName,       &dstClip, nullptr);

    OfxPropertySetHandle srcImg, dstImg;
    OFX_CHECK(gEffectSuite->clipGetImage(srcClip, time, nullptr, &srcImg));
    OFX_CHECK(gEffectSuite->clipGetImage(dstClip, time, nullptr, &dstImg));

    void* srcData  = nullptr; gPropSuite->propGetPointer(srcImg, kOfxImagePropData, 0, &srcData);
    void* dstData  = nullptr; gPropSuite->propGetPointer(dstImg, kOfxImagePropData, 0, &dstData);
    int srcRowBytes = 0;      gPropSuite->propGetInt(srcImg, kOfxImagePropRowBytes,  0, &srcRowBytes);
    int dstRowBytes = 0;      gPropSuite->propGetInt(dstImg, kOfxImagePropRowBytes,  0, &dstRowBytes);

    OfxRectI bounds = {0,0,0,0};
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 0, &bounds.x1);
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 1, &bounds.y1);
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 2, &bounds.x2);
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 3, &bounds.y2);

    char* depthStr = nullptr;
    gPropSuite->propGetString(srcImg, kOfxImageEffectPropPixelDepth, 0, &depthStr);
    bool isFloat = (depthStr && std::strcmp(depthStr, kOfxBitDepthFloat) == 0);

    int width  = bounds.x2 - bounds.x1;
    int height = bounds.y2 - bounds.y1;

    // Center for rotation
    double cx = width  * 0.5;
    double cy = height * 0.5;
    double cosA = std::cos(rotation);
    double sinA = std::sin(rotation);

    // ── Per-pixel blit with rotation + translation ─────────────────────────
    // For each dst pixel, compute the source pixel via inverse transform.
    // Transform: Tdst -> (rotate around center) -> (translate by -offset) -> Tsrc

    if (isFloat)
    {
        for (int y = 0; y < height; ++y)
        {
            float* dstRow = (float*)((unsigned char*)dstData + y * dstRowBytes);
            for (int x = 0; x < width; ++x)
            {
                // Inverse rotate
                double rx = x - cx;
                double ry = y - cy;
                double srcXf = cosA * rx + sinA * ry + cx - dx;
                double srcYf = -sinA * rx + cosA * ry + cy - dy;

                int sx = (int)std::round(srcXf);
                int sy = (int)std::round(srcYf);

                // Clamp to edge (gives border fill, no black bars)
                sx = clampi(sx, 0, width  - 1);
                sy = clampi(sy, 0, height - 1);

                float* srcRow = (float*)((unsigned char*)srcData + sy * srcRowBytes);
                int di = x  * 4;
                int si = sx * 4;

                dstRow[di + 0] = srcRow[si + 0];
                dstRow[di + 1] = srcRow[si + 1];
                dstRow[di + 2] = srcRow[si + 2];
                dstRow[di + 3] = srcRow[si + 3];
            }
        }
    }
    else
    {
        for (int y = 0; y < height; ++y)
        {
            unsigned char* dstRow = (unsigned char*)dstData + y * dstRowBytes;
            for (int x = 0; x < width; ++x)
            {
                double rx = x - cx;
                double ry = y - cy;
                double srcXf = cosA * rx + sinA * ry + cx - dx;
                double srcYf = -sinA * rx + cosA * ry + cy - dy;

                int sx = clampi((int)std::round(srcXf), 0, width  - 1);
                int sy = clampi((int)std::round(srcYf), 0, height - 1);

                unsigned char* srcRow = (unsigned char*)srcData + sy * srcRowBytes;
                int di = x  * 4;
                int si = sx * 4;

                dstRow[di + 0] = srcRow[si + 0];
                dstRow[di + 1] = srcRow[si + 1];
                dstRow[di + 2] = srcRow[si + 2];
                dstRow[di + 3] = srcRow[si + 3];
            }
        }
    }

    gEffectSuite->clipReleaseImage(srcImg);
    gEffectSuite->clipReleaseImage(dstImg);
    return kOfxStatOK;
}
