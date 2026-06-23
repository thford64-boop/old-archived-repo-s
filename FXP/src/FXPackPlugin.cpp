// FXPackPlugin.cpp — OFX Plugin Entry Point
// Defines the two symbols DaVinci Resolve (and any OFX host) looks for:
//   OfxGetNumberOfPlugins()  — returns how many plugins live in this bundle
//   OfxGetPlugin(int nth)    — returns a pointer to plugin descriptor #nth
//
// Each effect gets its own mainEntry thunk so the host can hold a distinct
// function pointer per plugin.  All thunks forward to pluginMain() which
// dispatches by index.

#include "ofxCore.h"
#include "pluginGlobals.h"
#include "effectBlur.h"
#include "effectGlow.h"
#include "effectGrain.h"
#include "effectShake.h"
#include "effectTransition.h"

#include <cstring>

// ─────────────────────────────────────────────────────────────────────────────
// Global suite pointers — declared extern in pluginGlobals.h, defined here
// ─────────────────────────────────────────────────────────────────────────────
OfxHost*                gHost        = nullptr;
OfxPropertySuiteV1*     gPropSuite   = nullptr;
OfxParameterSuiteV1*    gParamSuite  = nullptr;
OfxImageEffectSuiteV1*  gEffectSuite = nullptr;

// ─────────────────────────────────────────────────────────────────────────────
// setHost — called once by the host before any action is dispatched.
// Stored globally so every effect can access the suites via fetchSuites().
// ─────────────────────────────────────────────────────────────────────────────
static void setHost(OfxHost* host)
{
    gHost = host;
}

// ─────────────────────────────────────────────────────────────────────────────
// Central dispatcher — routes every OFX action to the correct effect module.
// pluginIndex maps 1:1 to the gPlugins[] array below.
// ─────────────────────────────────────────────────────────────────────────────
static OfxStatus pluginMain(int                  pluginIndex,
                             const char*          action,
                             const void*          handle,
                             OfxPropertySetHandle inArgs,
                             OfxPropertySetHandle /*outArgs*/)
{
    OfxImageEffectHandle effect = (OfxImageEffectHandle)handle;

    // ── Load: fetch host suites once (shared by all plugins) ─────────────
    if (std::strcmp(action, kOfxActionLoad) == 0)
        return fetchSuites();

    // ── Unload: nothing heap-allocated to free ────────────────────────────
    if (std::strcmp(action, kOfxActionUnload) == 0)
        return kOfxStatOK;

    // ── CreateInstance / DestroyInstance: no per-instance data needed ─────
    if (std::strcmp(action, kOfxActionCreateInstance)  == 0) return kOfxStatOK;
    if (std::strcmp(action, kOfxActionDestroyInstance) == 0) return kOfxStatOK;

    // ── Describe ──────────────────────────────────────────────────────────
    if (std::strcmp(action, kOfxActionDescribe) == 0)
    {
        switch (pluginIndex)
        {
            case 0: return blurDescribe(effect);
            case 1: return glowDescribe(effect);
            case 2: return grainDescribe(effect);
            case 3: return shakeDescribe(effect);
            case 4: return transitionDescribe(effect);
        }
    }

    // ── DescribeInContext ─────────────────────────────────────────────────
    if (std::strcmp(action, kOfxImageEffectActionDescribeInContext) == 0)
    {
        switch (pluginIndex)
        {
            case 0: return blurDescribeInContext(effect, inArgs);
            case 1: return glowDescribeInContext(effect, inArgs);
            case 2: return grainDescribeInContext(effect, inArgs);
            case 3: return shakeDescribeInContext(effect, inArgs);
            case 4: return transitionDescribeInContext(effect, inArgs);
        }
    }

    // ── Render ────────────────────────────────────────────────────────────
    if (std::strcmp(action, kOfxImageEffectActionRender) == 0)
    {
        switch (pluginIndex)
        {
            case 0: return blurRender(effect, inArgs);
            case 1: return glowRender(effect, inArgs);
            case 2: return grainRender(effect, inArgs);
            case 3: return shakeRender(effect, inArgs);
            case 4: return transitionRender(effect, inArgs);
        }
    }

    // ── IsIdentity: tell the host we always modify the image ─────────────
    // Returning kOfxStatReplyDefault means "no, I am not a pass-through".
    return kOfxStatReplyDefault;
}

// ─────────────────────────────────────────────────────────────────────────────
// Per-plugin thunks — each OfxPlugin entry needs its own function pointer.
// The OFX spec does not allow two plugins to share a mainEntry address.
// ─────────────────────────────────────────────────────────────────────────────
static OfxStatus blurMain(const char* a, const void* h,
                           OfxPropertySetHandle i, OfxPropertySetHandle o)
{ return pluginMain(0, a, h, i, o); }

static OfxStatus glowMain(const char* a, const void* h,
                           OfxPropertySetHandle i, OfxPropertySetHandle o)
{ return pluginMain(1, a, h, i, o); }

static OfxStatus grainMain(const char* a, const void* h,
                            OfxPropertySetHandle i, OfxPropertySetHandle o)
{ return pluginMain(2, a, h, i, o); }

static OfxStatus shakeMain(const char* a, const void* h,
                            OfxPropertySetHandle i, OfxPropertySetHandle o)
{ return pluginMain(3, a, h, i, o); }

static OfxStatus transitionMain(const char* a, const void* h,
                                 OfxPropertySetHandle i, OfxPropertySetHandle o)
{ return pluginMain(4, a, h, i, o); }

// ─────────────────────────────────────────────────────────────────────────────
// Plugin descriptor table
// pluginIdentifier strings must be unique; by convention: reverse-DNS + name.
// ─────────────────────────────────────────────────────────────────────────────
static OfxPlugin gPlugins[] =
{
    {
        kOfxImageEffectPluginApi,
        kOfxImageEffectPluginApiVersion,
        "com.fxpack.GaussianBlur",
        1, 0,
        setHost, blurMain
    },
    {
        kOfxImageEffectPluginApi,
        kOfxImageEffectPluginApiVersion,
        "com.fxpack.Glow",
        1, 0,
        setHost, glowMain
    },
    {
        kOfxImageEffectPluginApi,
        kOfxImageEffectPluginApiVersion,
        "com.fxpack.FilmGrain",
        1, 0,
        setHost, grainMain
    },
    {
        kOfxImageEffectPluginApi,
        kOfxImageEffectPluginApiVersion,
        "com.fxpack.CameraShake",
        1, 0,
        setHost, shakeMain
    },
    {
        kOfxImageEffectPluginApi,
        kOfxImageEffectPluginApiVersion,
        "com.fxpack.Transition",
        1, 0,
        setHost, transitionMain
    },
};

static const int kNumPlugins = sizeof(gPlugins) / sizeof(gPlugins[0]);

// ─────────────────────────────────────────────────────────────────────────────
// The two exported entry points the OFX host calls.
// EXPORT expands to  extern "C" __declspec(dllexport)  on Windows (see ofxCore.h).
// They are also listed in FXPack.def to guarantee correct export names.
// ─────────────────────────────────────────────────────────────────────────────
EXPORT int OfxGetNumberOfPlugins(void)
{
    return kNumPlugins;
}

EXPORT OfxPlugin* OfxGetPlugin(int nth)
{
    if (nth >= 0 && nth < kNumPlugins)
        return &gPlugins[nth];
    return nullptr;
}
