// effectTransition.cpp — Cross-Dissolve & Zoom Transition
// Uses two input clips (SourceFrom + SourceTo) and the OFX transition parameter.
// Parameters: Transition (0..1 driven by host), Type (Dissolve / Zoom)

#include "effectTransition.h"
#include "pluginGlobals.h"
#include <cmath>
#include <cstring>
#include <vector>
#include <vector>

// ─────────────────────────────────────────────────────────────────────────────
// Describe
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus transitionDescribe(OfxImageEffectHandle effect)
{
    OfxPropertySetHandle effectProps;
    OFX_CHECK(gEffectSuite->getPropertySet(effect, &effectProps));

    gPropSuite->propSetString(effectProps, kOfxPropLabel,      0, "FXPack Transitions");
    gPropSuite->propSetString(effectProps, kOfxPropShortLabel, 0, "Transition");
    gPropSuite->propSetString(effectProps, kOfxPropLongLabel,  0, "FXPack: Cross-Dissolve & Zoom Transitions");
    gPropSuite->propSetString(effectProps, kOfxPluginDescription, 0,
        "Transitions between two clips via cross-dissolve or zoom.");

    // Transition context uses two source clips + the host-driven Transition param
    gPropSuite->propSetString(effectProps, kOfxImageEffectPropSupportedContexts, 0,
        kOfxImageEffectContextTransition);

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
OfxStatus transitionDescribeInContext(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs)
{
    // In transition context, OFX spec requires these clip names
    OfxPropertySetHandle clipProps;
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectTransitionSourceFromClipName, &clipProps));
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectTransitionSourceToClipName,   &clipProps));
    OFX_CHECK(gEffectSuite->clipDefine(effect, kOfxImageEffectOutputClipName,               &clipProps));

    OfxParamSetHandle paramSet;
    OFX_CHECK(gEffectSuite->getParamSet(effect, &paramSet));

    OfxPropertySetHandle paramProps;

    // The OFX standard "Transition" param — driven by the host (0=from, 1=to)
    // The host usually creates this automatically, but we register it to add hints
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble,
        kOfxImageEffectTransitionParamName, &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Transition");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "Progress from source (0) to destination (1)");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 0.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 1.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 1);

    // Transition type
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeChoice, "transitionType", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,        0, "Transition Type");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,         0, "Style of transition");
    gPropSuite->propSetString(paramProps, kOfxParamPropChoiceOption, 0, "Cross Dissolve");
    gPropSuite->propSetString(paramProps, kOfxParamPropChoiceOption, 1, "Zoom");
    gPropSuite->propSetString(paramProps, kOfxParamPropChoiceOption, 2, "Dissolve + Zoom");
    gPropSuite->propSetInt(paramProps,    kOfxParamPropDefault,      0, 0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,     0, 0);

    // Zoom scale max (for zoom transition)
    OFX_CHECK(gParamSuite->paramDefine(paramSet, kOfxParamTypeDouble, "transitionZoomScale", &paramProps));
    gPropSuite->propSetString(paramProps, kOfxParamPropLabel,      0, "Zoom Scale");
    gPropSuite->propSetString(paramProps, kOfxParamPropHint,       0, "Maximum zoom amount during zoom transition");
    gPropSuite->propSetDouble(paramProps, kOfxParamPropDefault,    0, 1.5);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMin,        0, 1.0);
    gPropSuite->propSetDouble(paramProps, kOfxParamPropMax,        0, 4.0);
    gPropSuite->propSetInt(paramProps,    kOfxParamPropAnimates,   0, 0);

    return kOfxStatOK;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: sample a float RGBA buffer with nearest-neighbour + scale
// scale: >1 = zoom in (sample from inner region)
// Returns {r,g,b,a}
// ─────────────────────────────────────────────────────────────────────────────
static void sampleScaled(const float* buf, int width, int height,
                          int dstX, int dstY, double scale,
                          float& r, float& g, float& b, float& a)
{
    double cx = width  * 0.5;
    double cy = height * 0.5;

    // Inverse map: where in the source does this dst pixel come from?
    double srcX = (dstX - cx) / scale + cx;
    double srcY = (dstY - cy) / scale + cy;

    int sx = clampi((int)std::round(srcX), 0, width  - 1);
    int sy = clampi((int)std::round(srcY), 0, height - 1);

    const float* p = buf + (sy * width + sx) * 4;
    r = p[0]; g = p[1]; b = p[2]; a = p[3];
}

// ─────────────────────────────────────────────────────────────────────────────
// Render
// ─────────────────────────────────────────────────────────────────────────────
OfxStatus transitionRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs)
{
    double time = 0.0;
    gPropSuite->propGetDouble(inArgs, kOfxPropTime, 0, &time);

    // ── Read parameters ───────────────────────────────────────────────────
    OfxParamSetHandle paramSet;
    OFX_CHECK(gEffectSuite->getParamSet(effect, &paramSet));

    OfxParamHandle hTransition, hType, hZoom;
    gParamSuite->paramGetHandle(paramSet, kOfxImageEffectTransitionParamName, &hTransition, nullptr);
    gParamSuite->paramGetHandle(paramSet, "transitionType",       &hType,      nullptr);
    gParamSuite->paramGetHandle(paramSet, "transitionZoomScale",  &hZoom,      nullptr);

    double transitionT  = 0.0;
    int    transType    = 0;
    double zoomScale    = 1.5;

    gParamSuite->paramGetValueAtTime(hTransition, time, &transitionT);
    gParamSuite->paramGetValueAtTime(hType,       time, &transType);
    gParamSuite->paramGetValueAtTime(hZoom,       time, &zoomScale);

    // Clamp transition [0,1]
    transitionT = transitionT < 0.0 ? 0.0 : (transitionT > 1.0 ? 1.0 : transitionT);

    // ── Fetch clips ───────────────────────────────────────────────────────
    OfxImageClipHandle fromClip, toClip, dstClip;
    gEffectSuite->clipGetHandle(effect, kOfxImageEffectTransitionSourceFromClipName, &fromClip, nullptr);
    gEffectSuite->clipGetHandle(effect, kOfxImageEffectTransitionSourceToClipName,   &toClip,   nullptr);
    gEffectSuite->clipGetHandle(effect, kOfxImageEffectOutputClipName,               &dstClip,  nullptr);

    OfxPropertySetHandle fromImg, toImg, dstImg;
    OFX_CHECK(gEffectSuite->clipGetImage(fromClip, time, nullptr, &fromImg));
    OFX_CHECK(gEffectSuite->clipGetImage(toClip,   time, nullptr, &toImg));
    OFX_CHECK(gEffectSuite->clipGetImage(dstClip,  time, nullptr, &dstImg));

    void* fromData = nullptr; gPropSuite->propGetPointer(fromImg, kOfxImagePropData, 0, &fromData);
    void* toData   = nullptr; gPropSuite->propGetPointer(toImg,   kOfxImagePropData, 0, &toData);
    void* dstData  = nullptr; gPropSuite->propGetPointer(dstImg,  kOfxImagePropData, 0, &dstData);

    int fromRowBytes = 0; gPropSuite->propGetInt(fromImg, kOfxImagePropRowBytes, 0, &fromRowBytes);
    int toRowBytes   = 0; gPropSuite->propGetInt(toImg,   kOfxImagePropRowBytes, 0, &toRowBytes);
    int dstRowBytes  = 0; gPropSuite->propGetInt(dstImg,  kOfxImagePropRowBytes, 0, &dstRowBytes);

    OfxRectI bounds = {0,0,0,0};
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 0, &bounds.x1);
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 1, &bounds.y1);
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 2, &bounds.x2);
    gPropSuite->propGetInt(dstImg, kOfxImagePropBounds, 3, &bounds.y2);

    char* depthStr = nullptr;
    gPropSuite->propGetString(fromImg, kOfxImageEffectPropPixelDepth, 0, &depthStr);
    bool isFloat = (depthStr && std::strcmp(depthStr, kOfxBitDepthFloat) == 0);

    int width  = bounds.x2 - bounds.x1;
    int height = bounds.y2 - bounds.y1;
    int nPix   = width * height;

    // ── Convert both inputs to float working buffers ──────────────────────
    std::vector<float> fromBuf(nPix * 4);
    std::vector<float> toBuf  (nPix * 4);

    auto toFloat = [&](void* data, int rowBytes, std::vector<float>& buf)
    {
        for (int y = 0; y < height; ++y)
        {
            float* dst = &buf[y * width * 4];
            if (isFloat)
            {
                const float* src = (const float*)((const unsigned char*)data + y * rowBytes);
                for (int x = 0; x < width; ++x)
                {
                    dst[x*4+0] = src[x*4+0]; dst[x*4+1] = src[x*4+1];
                    dst[x*4+2] = src[x*4+2]; dst[x*4+3] = src[x*4+3];
                }
            }
            else
            {
                const unsigned char* src = (const unsigned char*)data + y * rowBytes;
                for (int x = 0; x < width; ++x)
                {
                    dst[x*4+0] = src[x*4+0] / 255.0f; dst[x*4+1] = src[x*4+1] / 255.0f;
                    dst[x*4+2] = src[x*4+2] / 255.0f; dst[x*4+3] = src[x*4+3] / 255.0f;
                }
            }
        }
    };

    toFloat(fromData, fromRowBytes, fromBuf);
    toFloat(toData,   toRowBytes,   toBuf);

    // ── Transition weights ────────────────────────────────────────────────
    float alpha = (float)transitionT;           // weight of "to" clip
    float beta  = 1.0f - alpha;                 // weight of "from" clip

    // Smooth easing (smoothstep)
    float easedT = alpha * alpha * (3.0f - 2.0f * alpha);
    float easedF = 1.0f - easedT;

    // Zoom scale: from shrinks, to grows from center
    // fromScale: 1.0 at t=0, zoomScale at t=1 (zoom out)
    double fromZoom = 1.0 + (zoomScale - 1.0) * transitionT;
    // toScale: zoomScale at t=0 (tiny), 1.0 at t=1 (full size)
    double toZoom   = zoomScale - (zoomScale - 1.0) * transitionT;
    if (toZoom < 1e-4) toZoom = 1e-4;
    if (fromZoom < 1e-4) fromZoom = 1e-4;

    // ── Composite each pixel ──────────────────────────────────────────────
    std::vector<float> outBuf(nPix * 4);

    for (int y = 0; y < height; ++y)
    {
        float* dst = &outBuf[y * width * 4];
        for (int x = 0; x < width; ++x)
        {
            float fr=0, fg=0, fb=0, fa=0;
            float tr=0, tg=0, tb=0, ta=0;

            if (transType == 0)
            {
                // ── Cross Dissolve ───────────────────────────────────────
                const float* fp = &fromBuf[(y * width + x) * 4];
                const float* tp = &toBuf  [(y * width + x) * 4];
                fr=fp[0]; fg=fp[1]; fb=fp[2]; fa=fp[3];
                tr=tp[0]; tg=tp[1]; tb=tp[2]; ta=tp[3];

                dst[x*4+0] = fr * easedF + tr * easedT;
                dst[x*4+1] = fg * easedF + tg * easedT;
                dst[x*4+2] = fb * easedF + tb * easedT;
                dst[x*4+3] = fa * easedF + ta * easedT;
            }
            else if (transType == 1)
            {
                // ── Zoom Transition ───────────────────────────────────────
                sampleScaled(fromBuf.data(), width, height, x, y, fromZoom, fr, fg, fb, fa);
                sampleScaled(toBuf.data(),   width, height, x, y, toZoom,   tr, tg, tb, ta);

                dst[x*4+0] = fr * easedF + tr * easedT;
                dst[x*4+1] = fg * easedF + tg * easedT;
                dst[x*4+2] = fb * easedF + tb * easedT;
                dst[x*4+3] = fa * easedF + ta * easedT;
            }
            else
            {
                // ── Dissolve + Zoom (combined) ────────────────────────────
                sampleScaled(fromBuf.data(), width, height, x, y, fromZoom, fr, fg, fb, fa);
                sampleScaled(toBuf.data(),   width, height, x, y, toZoom,   tr, tg, tb, ta);

                // Also apply dissolve on top of zoom
                dst[x*4+0] = fr * beta * easedF + tr * alpha * easedT;
                dst[x*4+1] = fg * beta * easedF + tg * alpha * easedT;
                dst[x*4+2] = fb * beta * easedF + tb * alpha * easedT;
                dst[x*4+3] = fa * easedF + ta * easedT;
            }
        }
    }

    // ── Write output ──────────────────────────────────────────────────────
    for (int y = 0; y < height; ++y)
    {
        const float* src = &outBuf[y * width * 4];
        if (isFloat)
        {
            float* dst = (float*)((unsigned char*)dstData + y * dstRowBytes);
            for (int x = 0; x < width; ++x)
            {
                dst[x*4+0] = src[x*4+0]; dst[x*4+1] = src[x*4+1];
                dst[x*4+2] = src[x*4+2]; dst[x*4+3] = src[x*4+3];
            }
        }
        else
        {
            unsigned char* dst = (unsigned char*)dstData + y * dstRowBytes;
            for (int x = 0; x < width; ++x)
            {
                dst[x*4+0] = (unsigned char)clampi((int)(src[x*4+0]*255.0f+0.5f),0,255);
                dst[x*4+1] = (unsigned char)clampi((int)(src[x*4+1]*255.0f+0.5f),0,255);
                dst[x*4+2] = (unsigned char)clampi((int)(src[x*4+2]*255.0f+0.5f),0,255);
                dst[x*4+3] = (unsigned char)clampi((int)(src[x*4+3]*255.0f+0.5f),0,255);
            }
        }
    }

    gEffectSuite->clipReleaseImage(fromImg);
    gEffectSuite->clipReleaseImage(toImg);
    gEffectSuite->clipReleaseImage(dstImg);
    return kOfxStatOK;
}
