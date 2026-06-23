// effectBlur.cpp — Separable Gaussian Blur Filter
// Two-pass (horizontal then vertical) true Gaussian blur.
// Parameters: Radius (pixels), Quality

#include "effectBlur.h"
#include "pluginGlobals.h"
#include <cmath>
#include <cstring>
#include <vector>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// ─────────────────────────────────────────────────────────────────────────────
// Build a 1D Gaussian kernel, normalised so it sums to 1.0
// radius: the max kernel half-width (kernel size = 2*radius+1)
// ─────────────────────────────────────────────────────────────────────────────
static std::vector<float> buildGaussianKernel(int radius)
{
    if (radius < 1) radius = 1;
    int     size   = 2 * radius + 1;
    double  sigma  = radius / 3.0;   // 3-sigma rule: covers 99.7% of distribution
    if (sigma < 0.5) sigma = 0.5;

    std::vector<float> kernel(size);
    double              sum   = 0.0;

    for (int i = 0; i < size; ++i)
    {
        double x = (double)(i - radius);
        double v = std::exp(-(x * x) / (2.0 * sigma * sigma));
        kernel[i] = (float)v;
        sum       += v;
    }
    // Normalise
    for (int i = 0; i < size; ++i)
        kernel[i] = (float)((double)kernel[i] / sum);

    return kernel;
}

// ─────────────────────────────────────────────────────────────────────────────
// Describe
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus blurDescribe(OfxImageEffectHandle effect)
{
    OfxPropertySetHandle effectProps;
    OFX_CHECK(gEffectSuite->getPropertySet(effect, &effectProps));

    gPropSuite->propSetString(effectProps, kOfxPropLabel,      0, "FXPack Gaussian Blur");
    gPropSuite->propSetString(effectProps, kOfxPropShortLabel, 0, "Blur");
    gPropSuite->propSetString(effectProps, kOfxPropLongLabel,  0, "FXPack: Gaussian Blur");
    gPropSuite->propSetString(effectProps, kOfxPluginDescription, 0,
        "Two-pass separable Gaussian blur with independent X/Y radius control.");

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
OfxStatus blurDescribeInContext(OfxImageEffectHandle effect, OfxPropertySetHandle /*inArgs*/)
{
    OfxPropertySetHandle clipProps;
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectSimpleSourceClipName, &clipProps));
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectOutputClipName,       &clipProps));

    OfxParamSetHandle paramSet;
    OFX_CHECK(gEffectSuite->getParamSet(effect, &paramSet));

    OfxPropertySetHandle paramProps;

    // Blur Radius X
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeInteger, "blurRadiusX", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Radius X");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "Gaussian blur radius in pixels (horizontal)");
    gPropSuite->propSetInt(paramProps,    kOfxParamPropDefault,    0, 5);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropMin,        0, 0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropMax,        0, 100);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 1);

    // Blur Radius Y
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeInteger, "blurRadiusY", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Radius Y");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "Gaussian blur radius in pixels (vertical)");
    gPropSuite->propSetInt(paramProps,    kOfxParamPropDefault,    0, 5);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropMin,        0, 0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropMax,        0, 100);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 1);

    return kOfxStatOK;
}

// ─────────────────────────────────────────────────────────────────────────────
// Render — Float implementation (byte path converts then converts back)
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus blurRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs)
{
    double time = 0.0;
    gPropSuite->propGetDouble(inArgs, kOfxPropTime, 0, &time);

    OfxParamSetHandle paramSet;
    OFX_CHECK(gEffectSuite->getParamSet(effect, &paramSet));

    OfxParamHandle hRX, hRY;
    gParamSuite->paramGetHandle(paramSet, "blurRadiusX", &hRX, nullptr);
    gParamSuite->paramGetHandle(paramSet, "blurRadiusY", &hRY, nullptr);

    int radiusX = 5, radiusY = 5;
    gParamSuite->paramGetValueAtTime(hRX, time, &radiusX);
    gParamSuite->paramGetValueAtTime(hRY, time, &radiusY);

    if (radiusX < 0) radiusX = 0;
    if (radiusY < 0) radiusY = 0;

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

    // ── Build kernels ─────────────────────────────────────────────────────
    std::vector<float> kernelX = (radiusX > 0) ? buildGaussianKernel(radiusX) : std::vector<float>{1.0f};
    std::vector<float> kernelY = (radiusY > 0) ? buildGaussianKernel(radiusY) : std::vector<float>{1.0f};

    int kSizeX = (int)kernelX.size();
    int kSizeY = (int)kernelY.size();

    // ── Working float buffer (RGBA, planar scanline order) ────────────────
    // We always work in float internally, even for byte images.
    std::vector<float> floatSrc(nPix * 4);
    std::vector<float> tempBuf (nPix * 4);   // result after horizontal pass
    std::vector<float> floatDst(nPix * 4);   // result after vertical pass

    // Copy source to float buffer
    if (isFloat)
    {
        for (int y = 0; y < height; ++y)
        {
            const float* row = (const float*)((const unsigned char*)srcData + y * srcRowBytes);
            float*       dst = &floatSrc[y * width * 4];
            for (int x = 0; x < width; ++x)
            {
                dst[x*4+0] = row[x*4+0];
                dst[x*4+1] = row[x*4+1];
                dst[x*4+2] = row[x*4+2];
                dst[x*4+3] = row[x*4+3];
            }
        }
    }
    else
    {
        for (int y = 0; y < height; ++y)
        {
            const unsigned char* row = (const unsigned char*)srcData + y * srcRowBytes;
            float*               dst = &floatSrc[y * width * 4];
            for (int x = 0; x < width; ++x)
            {
                dst[x*4+0] = row[x*4+0] / 255.0f;
                dst[x*4+1] = row[x*4+1] / 255.0f;
                dst[x*4+2] = row[x*4+2] / 255.0f;
                dst[x*4+3] = row[x*4+3] / 255.0f;
            }
        }
    }

    // ── Horizontal pass ───────────────────────────────────────────────────
    int kHalfX = kSizeX / 2;
    for (int y = 0; y < height; ++y)
    {
        const float* srcRow = &floatSrc[y * width * 4];
        float*       dstRow = &tempBuf [y * width * 4];

        for (int x = 0; x < width; ++x)
        {
            float r=0, g=0, b=0, a=0;
            for (int k = 0; k < kSizeX; ++k)
            {
                int sx = clampi(x + k - kHalfX, 0, width - 1);
                float w = kernelX[k];
                r += srcRow[sx*4+0] * w;
                g += srcRow[sx*4+1] * w;
                b += srcRow[sx*4+2] * w;
                a += srcRow[sx*4+3] * w;
            }
            dstRow[x*4+0] = r;
            dstRow[x*4+1] = g;
            dstRow[x*4+2] = b;
            dstRow[x*4+3] = a;
        }
    }

    // ── Vertical pass ─────────────────────────────────────────────────────
    int kHalfY = kSizeY / 2;
    for (int y = 0; y < height; ++y)
    {
        float* dstRow = &floatDst[y * width * 4];

        for (int x = 0; x < width; ++x)
        {
            float r=0, g=0, b=0, a=0;
            for (int k = 0; k < kSizeY; ++k)
            {
                int sy = clampi(y + k - kHalfY, 0, height - 1);
                const float* srcRow = &tempBuf[sy * width * 4];
                float w = kernelY[k];
                r += srcRow[x*4+0] * w;
                g += srcRow[x*4+1] * w;
                b += srcRow[x*4+2] * w;
                a += srcRow[x*4+3] * w;
            }
            dstRow[x*4+0] = r;
            dstRow[x*4+1] = g;
            dstRow[x*4+2] = b;
            dstRow[x*4+3] = a;
        }
    }

    // ── Write result to output image ──────────────────────────────────────
    if (isFloat)
    {
        for (int y = 0; y < height; ++y)
        {
            const float* src = &floatDst[y * width * 4];
            float*       dst = (float*)((unsigned char*)dstData + y * dstRowBytes);
            for (int x = 0; x < width; ++x)
            {
                dst[x*4+0] = src[x*4+0];
                dst[x*4+1] = src[x*4+1];
                dst[x*4+2] = src[x*4+2];
                dst[x*4+3] = src[x*4+3];
            }
        }
    }
    else
    {
        for (int y = 0; y < height; ++y)
        {
            const float*   src = &floatDst[y * width * 4];
            unsigned char* dst = (unsigned char*)dstData + y * dstRowBytes;
            for (int x = 0; x < width; ++x)
            {
                dst[x*4+0] = (unsigned char)clampi((int)(src[x*4+0] * 255.0f + 0.5f), 0, 255);
                dst[x*4+1] = (unsigned char)clampi((int)(src[x*4+1] * 255.0f + 0.5f), 0, 255);
                dst[x*4+2] = (unsigned char)clampi((int)(src[x*4+2] * 255.0f + 0.5f), 0, 255);
                dst[x*4+3] = (unsigned char)clampi((int)(src[x*4+3] * 255.0f + 0.5f), 0, 255);
            }
        }
    }

    gEffectSuite->clipReleaseImage(srcImg);
    gEffectSuite->clipReleaseImage(dstImg);
    return kOfxStatOK;
}
