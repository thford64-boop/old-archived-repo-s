// effectGlow.cpp — Glow / Bloom Effect (CPU)
// Algorithm: threshold → gaussian blur the bright regions → additive composite.
// Parameters: Threshold, Intensity, Radius, Saturation boost

#include "effectGlow.h"
#include "pluginGlobals.h"
#include <cmath>
#include <cstring>
#include <vector>

// ─────────────────────────────────────────────────────────────────────────────
// Describe
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus glowDescribe(OfxImageEffectHandle effect)
{
    OfxPropertySetHandle effectProps;
    OFX_CHECK(gEffectSuite->getPropertySet(effect, &effectProps));

    gPropSuite->propSetString(effectProps, kOfxPropLabel,      0, "FXPack Glow/Bloom");
    gPropSuite->propSetString(effectProps, kOfxPropShortLabel, 0, "Glow");
    gPropSuite->propSetString(effectProps, kOfxPropLongLabel,  0, "FXPack: Glow/Bloom");
    gPropSuite->propSetString(effectProps, kOfxPluginDescription, 0,
        "Threshold-based bloom: bright areas spread light onto the image additively.");

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
OfxStatus glowDescribeInContext(OfxImageEffectHandle effect, OfxPropertySetHandle /*inArgs*/)
{
    OfxPropertySetHandle clipProps;
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectSimpleSourceClipName, &clipProps));
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectOutputClipName,       &clipProps));

    OfxParamSetHandle paramSet;
    OFX_CHECK(gEffectSuite->getParamSet(effect, &paramSet));
    OfxPropertySetHandle paramProps;

    // Threshold
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble, "glowThreshold", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Threshold");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "Luminance level above which glow is generated");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 0.7);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 1.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 1);

    // Glow Radius
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeInteger, "glowRadius", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,   0, "Glow Radius");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,    0, "Radius of bloom spread in pixels");
    gPropSuite->propSetInt(paramProps,    kOfxParamPropDefault, 0, 15);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropMin,     0, 1);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropMax,     0, 80);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,0, 1);

    // Glow Intensity
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble, "glowIntensity", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Glow Intensity");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "Strength of the bloom composite");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 1.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 5.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDisplayMin, 0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDisplayMax, 0, 3.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 1);

    // Saturation boost for glow
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble, "glowSaturation", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Glow Saturation");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "How colourful the glow is (0=white, 1=matches source colour)");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 0.8);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 2.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 0);

    return kOfxStatOK;
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal: separable box blur (approximate Gaussian via 3 passes)
// Faster than true Gaussian at large radii
// ─────────────────────────────────────────────────────────────────────────────
static void boxBlurHoriz(const float* src, float* dst, int width, int height, int radius)
{
    if (radius < 1) { std::memcpy(dst, src, (size_t)width * height * 4 * sizeof(float)); return; }
    float invLen = 1.0f / (float)(2 * radius + 1);

    for (int y = 0; y < height; ++y)
    {
        const float* s = src + y * width * 4;
        float*       d = dst + y * width * 4;

        // Prefix sum initialisation
        float sumR=0, sumG=0, sumB=0, sumA=0;
        for (int k = -radius; k <= radius; ++k)
        {
            int kx = clampi(k, 0, width - 1);
            sumR += s[kx*4+0]; sumG += s[kx*4+1];
            sumB += s[kx*4+2]; sumA += s[kx*4+3];
        }
        d[0] = sumR * invLen; d[1] = sumG * invLen;
        d[2] = sumB * invLen; d[3] = sumA * invLen;

        for (int x = 1; x < width; ++x)
        {
            int addX  = clampi(x + radius,     0, width - 1);
            int subX  = clampi(x - radius - 1, 0, width - 1);
            sumR += s[addX*4+0] - s[subX*4+0];
            sumG += s[addX*4+1] - s[subX*4+1];
            sumB += s[addX*4+2] - s[subX*4+2];
            sumA += s[addX*4+3] - s[subX*4+3];
            d[x*4+0] = sumR * invLen; d[x*4+1] = sumG * invLen;
            d[x*4+2] = sumB * invLen; d[x*4+3] = sumA * invLen;
        }
    }
}

static void boxBlurVert(const float* src, float* dst, int width, int height, int radius)
{
    if (radius < 1) { std::memcpy(dst, src, (size_t)width * height * 4 * sizeof(float)); return; }
    float invLen = 1.0f / (float)(2 * radius + 1);

    for (int x = 0; x < width; ++x)
    {
        float sumR=0, sumG=0, sumB=0, sumA=0;
        for (int k = -radius; k <= radius; ++k)
        {
            int ky = clampi(k, 0, height - 1);
            sumR += src[ky*width*4 + x*4+0]; sumG += src[ky*width*4 + x*4+1];
            sumB += src[ky*width*4 + x*4+2]; sumA += src[ky*width*4 + x*4+3];
        }
        dst[0*width*4 + x*4+0] = sumR*invLen; dst[0*width*4 + x*4+1] = sumG*invLen;
        dst[0*width*4 + x*4+2] = sumB*invLen; dst[0*width*4 + x*4+3] = sumA*invLen;

        for (int y = 1; y < height; ++y)
        {
            int addY = clampi(y + radius,     0, height - 1);
            int subY = clampi(y - radius - 1, 0, height - 1);
            sumR += src[addY*width*4 + x*4+0] - src[subY*width*4 + x*4+0];
            sumG += src[addY*width*4 + x*4+1] - src[subY*width*4 + x*4+1];
            sumB += src[addY*width*4 + x*4+2] - src[subY*width*4 + x*4+2];
            sumA += src[addY*width*4 + x*4+3] - src[subY*width*4 + x*4+3];
            dst[y*width*4 + x*4+0] = sumR*invLen; dst[y*width*4 + x*4+1] = sumG*invLen;
            dst[y*width*4 + x*4+2] = sumB*invLen; dst[y*width*4 + x*4+3] = sumA*invLen;
        }
    }
}

// 3-pass box blur approximates a Gaussian well
static void approxGaussian(float* buf, float* tmp, int width, int height, int radius)
{
    boxBlurHoriz(buf, tmp, width, height, radius);
    boxBlurVert (tmp, buf, width, height, radius);
    boxBlurHoriz(buf, tmp, width, height, radius);
    boxBlurVert (tmp, buf, width, height, radius);
    boxBlurHoriz(buf, tmp, width, height, radius);
    boxBlurVert (tmp, buf, width, height, radius);
}

// ─────────────────────────────────────────────────────────────────────────────
// Render
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus glowRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs)
{
    double time = 0.0;
    gPropSuite->propGetDouble(inArgs, kOfxPropTime, 0, &time);

    OfxParamSetHandle paramSet;
    OFX_CHECK(gEffectSuite->getParamSet(effect, &paramSet));

    OfxParamHandle hThresh, hRadius, hIntensity, hSat;
    gParamSuite->paramGetHandle(paramSet, "glowThreshold",  &hThresh,    nullptr);
    gParamSuite->paramGetHandle(paramSet, "glowRadius",     &hRadius,    nullptr);
    gParamSuite->paramGetHandle(paramSet, "glowIntensity",  &hIntensity, nullptr);
    gParamSuite->paramGetHandle(paramSet, "glowSaturation", &hSat,       nullptr);

    double threshold  = 0.7;
    int    radius     = 15;
    double intensity  = 1.0;
    double saturation = 0.8;

    gParamSuite->paramGetValueAtTime(hThresh,    time, &threshold);
    gParamSuite->paramGetValueAtTime(hRadius,    time, &radius);
    gParamSuite->paramGetValueAtTime(hIntensity, time, &intensity);
    gParamSuite->paramGetValueAtTime(hSat,       time, &saturation);

    if (radius < 1)  radius = 1;
    if (radius > 80) radius = 80;

    // ── Fetch images ──────────────────────────────────────────────────────
    OfxImageClipHandle srcClip, dstClip;
    gEffectSuite->clipGetHandle(effect, kOfxImageEffectSimpleSourceClipName, &srcClip, nullptr);
    gEffectSuite->clipGetHandle(effect, kOfxImageEffectOutputClipName,       &dstClip, nullptr);

    OfxPropertySetHandle srcImg, dstImg;
    OFX_CHECK(gEffectSuite->clipGetImage(srcClip, time, nullptr, &srcImg));
    OFX_CHECK(gEffectSuite->clipGetImage(dstClip, time, nullptr, &dstImg));

    void* srcData = nullptr; gPropSuite->propGetPointer(srcImg, kOfxImagePropData, 0, &srcData);
    void* dstData = nullptr; gPropSuite->propGetPointer(dstImg, kOfxImagePropData, 0, &dstData);
    int srcRowBytes = 0;     gPropSuite->propGetInt(srcImg, kOfxImagePropRowBytes,  0, &srcRowBytes);
    int dstRowBytes = 0;     gPropSuite->propGetInt(dstImg, kOfxImagePropRowBytes,  0, &dstRowBytes);

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
    int nPix   = width * height;

    // ── Convert source to float ───────────────────────────────────────────
    std::vector<float> srcBuf(nPix * 4);
    for (int y = 0; y < height; ++y)
    {
        float* dst = &srcBuf[y * width * 4];
        if (isFloat)
        {
            const float* s = (const float*)((const unsigned char*)srcData + y * srcRowBytes);
            for (int x = 0; x < width; ++x)
            { dst[x*4+0]=s[x*4+0]; dst[x*4+1]=s[x*4+1]; dst[x*4+2]=s[x*4+2]; dst[x*4+3]=s[x*4+3]; }
        }
        else
        {
            const unsigned char* s = (const unsigned char*)srcData + y * srcRowBytes;
            for (int x = 0; x < width; ++x)
            { dst[x*4+0]=s[x*4+0]/255.f; dst[x*4+1]=s[x*4+1]/255.f; dst[x*4+2]=s[x*4+2]/255.f; dst[x*4+3]=s[x*4+3]/255.f; }
        }
    }

    // ── Build bloom mask: pixels above threshold ──────────────────────────
    std::vector<float> bloomBuf(nPix * 4, 0.0f);
    float thresh = (float)threshold;
    float sat    = (float)saturation;

    for (int i = 0; i < nPix; ++i)
    {
        float r = srcBuf[i*4+0];
        float g = srcBuf[i*4+1];
        float b = srcBuf[i*4+2];

        // Perceptual luminance
        float lum = 0.2126f * r + 0.7152f * g + 0.0722f * b;

        if (lum > thresh)
        {
            float excess = (lum - thresh) / (1.0f - thresh + 1e-6f);  // [0,1]

            // Blend between white glow and coloured glow
            float glowR = r * sat + lum * (1.0f - sat);
            float glowG = g * sat + lum * (1.0f - sat);
            float glowB = b * sat + lum * (1.0f - sat);

            bloomBuf[i*4+0] = glowR * excess;
            bloomBuf[i*4+1] = glowG * excess;
            bloomBuf[i*4+2] = glowB * excess;
            bloomBuf[i*4+3] = srcBuf[i*4+3];
        }
    }

    // ── Blur the bloom mask ───────────────────────────────────────────────
    std::vector<float> tmpBuf(nPix * 4);
    approxGaussian(bloomBuf.data(), tmpBuf.data(), width, height, radius);

    // ── Additive composite ────────────────────────────────────────────────
    float intF = (float)intensity;
    for (int y = 0; y < height; ++y)
    {
        const float* src  = &srcBuf  [y * width * 4];
        const float* bloom= &bloomBuf[y * width * 4];

        if (isFloat)
        {
            float* dst = (float*)((unsigned char*)dstData + y * dstRowBytes);
            for (int x = 0; x < width; ++x)
            {
                dst[x*4+0] = clampf(src[x*4+0] + bloom[x*4+0] * intF, 0.f, 1.f);
                dst[x*4+1] = clampf(src[x*4+1] + bloom[x*4+1] * intF, 0.f, 1.f);
                dst[x*4+2] = clampf(src[x*4+2] + bloom[x*4+2] * intF, 0.f, 1.f);
                dst[x*4+3] = src[x*4+3];
            }
        }
        else
        {
            unsigned char* dst = (unsigned char*)dstData + y * dstRowBytes;
            for (int x = 0; x < width; ++x)
            {
                dst[x*4+0] = (unsigned char)clampi((int)((src[x*4+0] + bloom[x*4+0]*intF)*255.f+.5f),0,255);
                dst[x*4+1] = (unsigned char)clampi((int)((src[x*4+1] + bloom[x*4+1]*intF)*255.f+.5f),0,255);
                dst[x*4+2] = (unsigned char)clampi((int)((src[x*4+2] + bloom[x*4+2]*intF)*255.f+.5f),0,255);
                dst[x*4+3] = (unsigned char)clampi((int)(src[x*4+3]*255.f+.5f),0,255);
            }
        }
    }

    gEffectSuite->clipReleaseImage(srcImg);
    gEffectSuite->clipReleaseImage(dstImg);
    return kOfxStatOK;
}
