#pragma once
// ofxCore.h - Minimal OFX Core definitions needed for plugin compilation
// In a real build, replace with the official OpenFX SDK headers from:
// https://github.com/ofxa/openfx

#ifndef __cplusplus
#error "OFX requires C++"
#endif

#include <stddef.h>

// Versioning
#define kOfxVersionMajor 1
#define kOfxVersionMinor 4

// Basic types
typedef void* OfxPropertySetHandle;
typedef void* OfxParamSetHandle;
typedef void* OfxImageEffectHandle;
typedef void* OfxImageClipHandle;
typedef void* OfxParamHandle;
// typedef void* OfxHost; -- removed, struct defined below
typedef void* OfxTime;

typedef int OfxStatus;

// Status codes
#define kOfxStatOK              0
#define kOfxStatFailed          1
#define kOfxStatErrFatal        2
#define kOfxStatErrUnknown      3
#define kOfxStatErrMissingHostFeature 4
#define kOfxStatErrUnsupported  5
#define kOfxStatErrExists       6
#define kOfxStatErrFormat       7
#define kOfxStatErrMemory       8
#define kOfxStatErrBadHandle    9
#define kOfxStatErrBadIndex     10
#define kOfxStatErrValue        11
#define kOfxStatReplyYes        12
#define kOfxStatReplyNo         13
#define kOfxStatReplyDefault    14

// String constants - Actions
#define kOfxActionLoad                  "OfxActionLoad"
#define kOfxActionUnload                "OfxActionUnload"
#define kOfxActionDescribe              "OfxActionDescribe"
#define kOfxActionCreateInstance        "OfxActionCreateInstance"
#define kOfxActionDestroyInstance       "OfxActionDestroyInstance"
#define kOfxActionBeginInstanceChanged  "OfxActionBeginInstanceChanged"
#define kOfxActionInstanceChanged       "OfxActionInstanceChanged"
#define kOfxActionEndInstanceChanged    "OfxActionEndInstanceChanged"
#define kOfxActionPurgeCaches           "OfxActionPurgeCaches"
#define kOfxActionSyncPrivateData       "OfxActionSyncPrivateData"
#define kOfxActionBeginInstanceEdit     "OfxActionBeginInstanceEdit"
#define kOfxActionEndInstanceEdit       "OfxActionEndInstanceEdit"

// Image Effect Actions
#define kOfxImageEffectActionDescribeInContext   "OfxImageEffectActionDescribeInContext"
#define kOfxImageEffectActionGetRoD             "OfxImageEffectActionGetRoD"
#define kOfxImageEffectActionGetFramesNeeded    "OfxImageEffectActionGetFramesNeeded"
#define kOfxImageEffectActionIsIdentity         "OfxImageEffectActionIsIdentity"
#define kOfxImageEffectActionRender             "OfxImageEffectActionRender"
#define kOfxImageEffectActionBeginSequenceRender "OfxImageEffectActionBeginSequenceRender"
#define kOfxImageEffectActionEndSequenceRender  "OfxImageEffectActionEndSequenceRender"
#define kOfxImageEffectActionGetClipPreferences "OfxImageEffectActionGetClipPreferences"
#define kOfxImageEffectActionGetTimeDomain      "OfxImageEffectActionGetTimeDomain"

// Property keys - Effect
#define kOfxPropType                    "OfxPropType"
#define kOfxPropName                    "OfxPropName"
#define kOfxPropLabel                   "OfxPropLabel"
#define kOfxPropShortLabel              "OfxPropShortLabel"
#define kOfxPropLongLabel               "OfxPropLongLabel"
#define kOfxPropVersion                 "OfxPropVersion"
#define kOfxPropVersionLabel            "OfxPropVersionLabel"
#define kOfxPropPluginDescription "OfxPropPluginDescription"
#define kOfxPluginDescription kOfxPropPluginDescription
#define kOfxPropTime                    "OfxPropTime"
#define kOfxPropChangeReason            "OfxPropChangeReason"
#define kOfxPropEffectInstance          "OfxPropEffectInstance"
#define kOfxPropInstanceData            "OfxPropInstanceData"

// Image Effect properties
#define kOfxImageEffectPropSupportedContexts    "OfxImageEffectPropSupportedContexts"
#define kOfxImageEffectPropPluginHandle         "OfxImageEffectPropPluginHandle"
#define kOfxImageEffectPropRenderScale          "OfxImageEffectPropRenderScale"
#define kOfxImageEffectPropFrameRange           "OfxImageEffectPropFrameRange"
#define kOfxImageEffectPropFrameStep            "OfxImageEffectPropFrameStep"
#define kOfxImageEffectPropIsInteractive        "OfxImageEffectPropIsInteractive"
#define kOfxImageEffectPropSupportsMultiResolution "OfxImageEffectPropSupportsMultiResolution"
#define kOfxImageEffectPropSupportsTiles        "OfxImageEffectPropSupportsTiles"
#define kOfxImageEffectPropTemporalClipAccess   "OfxImageEffectPropTemporalClipAccess"
#define kOfxImageEffectPropSupportedPixelDepths "OfxImageEffectPropSupportedPixelDepths"
#define kOfxImageEffectPropSingleInstance       "OfxImageEffectPropSingleInstance"
#define kOfxImageEffectPropRenderThreadSafety   "OfxImageEffectPropRenderThreadSafety"
#define kOfxImageEffectPropHostFrameThreading   "OfxImageEffectPropHostFrameThreading"
#define kOfxImageEffectPropContext              "OfxImageEffectPropContext"
#define kOfxImageEffectInstancePropEffectDuration "OfxImageEffectInstancePropEffectDuration"
#define kOfxImageEffectInstancePropSequentialRender "OfxImageEffectInstancePropSequentialRender"

// Clip properties
#define kOfxImageClipPropConnected      "OfxImageClipPropConnected"
#define kOfxImageClipPropOptional       "OfxImageClipPropOptional"
#define kOfxImageClipPropIsMask         "OfxImageClipPropIsMask"
#define kOfxImageClipPropFieldExtraction "OfxImageClipPropFieldExtraction"
#define kOfxImageClipPropUnmappedComponents "OfxImageClipPropUnmappedComponents"

// Image properties
#define kOfxImagePropData               "OfxImagePropData"
#define kOfxImagePropBounds             "OfxImagePropBounds"
#define kOfxImagePropRegionOfDefinition "OfxImagePropRegionOfDefinition"
#define kOfxImagePropRowBytes           "OfxImagePropRowBytes"
#define kOfxImagePropField              "OfxImagePropField"
#define kOfxImagePropUniqueIdentifier   "OfxImagePropUniqueIdentifier"
#define kOfxImageEffectPropPixelDepth   "OfxImageEffectPropPixelDepth"
#define kOfxImageEffectPropComponents   "OfxImageEffectPropComponents"
#define kOfxImageEffectPropPreMultiplication "OfxImageEffectPropPreMultiplication"
#define kOfxImageEffectPropPixelAspectRatio "OfxImageEffectPropPixelAspectRatio"

// Pixel depth strings
#define kOfxBitDepthByte                "OfxBitDepthByte"
#define kOfxBitDepthShort               "OfxBitDepthShort"
#define kOfxBitDepthFloat               "OfxBitDepthFloat"
#define kOfxBitDepthNone                "OfxBitDepthNone"

// Component strings
#define kOfxImageComponentRGBA          "OfxImageComponentRGBA"
#define kOfxImageComponentRGB           "OfxImageComponentRGB"
#define kOfxImageComponentAlpha         "OfxImageComponentAlpha"
#define kOfxImageComponentNone          "OfxImageComponentNone"

// Premultiplication strings
#define kOfxImageOpaque                 "OfxImageOpaque"
#define kOfxImagePreMultiplied          "OfxImagePreMultiplied"
#define kOfxImageUnPreMultiplied        "OfxImageUnPreMultiplied"

// Context strings
#define kOfxImageEffectContextFilter            "OfxImageEffectContextFilter"
#define kOfxImageEffectContextGeneral           "OfxImageEffectContextGeneral"
#define kOfxImageEffectContextTransition        "OfxImageEffectContextTransition"
#define kOfxImageEffectContextGenerator         "OfxImageEffectContextGenerator"
#define kOfxImageEffectContextRetimer           "OfxImageEffectContextRetimer"

// Render thread safety
#define kOfxImageEffectRenderUnsafe             "OfxImageEffectRenderUnsafe"
#define kOfxImageEffectRenderInstanceSafe       "OfxImageEffectRenderInstanceSafe"
#define kOfxImageEffectRenderFullySafe          "OfxImageEffectRenderFullySafe"

// Clip names
#define kOfxImageEffectSimpleSourceClipName     "Source"
#define kOfxImageEffectOutputClipName           "Output"
#define kOfxImageEffectTransitionSourceFromClipName "SourceFrom"
#define kOfxImageEffectTransitionSourceToClipName   "SourceTo"
#define kOfxImageEffectTransitionParamName      "Transition"

// Param types
#define kOfxParamTypeInteger            "OfxParamTypeInteger"
#define kOfxParamTypeDouble             "OfxParamTypeDouble"
#define kOfxParamTypeBoolean            "OfxParamTypeBoolean"
#define kOfxParamTypeChoice             "OfxParamTypeChoice"
#define kOfxParamTypeRGBA               "OfxParamTypeRGBA"
#define kOfxParamTypeRGB                "OfxParamTypeRGB"
#define kOfxParamTypeDouble2D           "OfxParamTypeDouble2D"
#define kOfxParamTypeInteger2D          "OfxParamTypeInteger2D"
#define kOfxParamTypeDouble3D           "OfxParamTypeDouble3D"
#define kOfxParamTypeInteger3D          "OfxParamTypeInteger3D"
#define kOfxParamTypePushButton         "OfxParamTypePushButton"
#define kOfxParamTypeGroup              "OfxParamTypeGroup"
#define kOfxParamTypePage               "OfxParamTypePage"
#define kOfxParamTypeString             "OfxParamTypeString"
#define kOfxParamTypeCustom             "OfxParamTypeCustom"

// Param properties
#define kOfxParamPropDefault            "OfxParamPropDefault"
#define kOfxParamPropMin                "OfxParamPropMin"
#define kOfxParamPropMax                "OfxParamPropMax"
#define kOfxParamPropDisplayMin         "OfxParamPropDisplayMin"
#define kOfxParamPropDisplayMax         "OfxParamPropDisplayMax"
#define kOfxParamPropLabel              "OfxParamPropLabel"  
#define kOfxParamPropHint               "OfxParamPropHint"
#define kOfxParamPropGroupOpen          "OfxParamPropGroupOpen"
#define kOfxParamPropChoiceOption       "OfxParamPropChoiceOption"
#define kOfxParamPropAnimates           "OfxParamPropAnimates"
#define kOfxParamPropIsAutoKeying       "OfxParamPropIsAutoKeying"
#define kOfxParamPropPersistant         "OfxParamPropPersistant"
#define kOfxParamPropEvaluateOnChange   "OfxParamPropEvaluateOnChange"
#define kOfxParamPropScriptName         "OfxParamPropScriptName"
#define kOfxParamPropDoubleType         "OfxParamPropDoubleType"
#define kOfxParamPropEnabled            "OfxParamPropEnabled"

// Double param sub-types
#define kOfxParamDoubleTypePlain        "OfxParamDoubleTypePlain"
#define kOfxParamDoubleTypeAngle        "OfxParamDoubleTypeAngle"
#define kOfxParamDoubleTypeScale        "OfxParamDoubleTypeScale"
#define kOfxParamDoubleTypeTime         "OfxParamDoubleTypeTime"
#define kOfxParamDoubleTypeAbsoluteTime "OfxParamDoubleTypeAbsoluteTime"
#define kOfxParamDoubleTypeX            "OfxParamDoubleTypeX"
#define kOfxParamDoubleTypeY            "OfxParamDoubleTypeY"
#define kOfxParamDoubleTypeXY           "OfxParamDoubleTypeXY"

// Change reasons
#define kOfxChangeUserEdited            "OfxChangeUserEdited"
#define kOfxChangePluginEdited          "OfxChangePluginEdited"
#define kOfxChangeTime                  "OfxChangeTime"

// Rect
struct OfxRectI { int x1, y1, x2, y2; };
struct OfxRectD { double x1, y1, x2, y2; };
struct OfxPointI { int x, y; };
struct OfxPointD { double x, y; };
struct OfxRangeI { int min, max; };
struct OfxRangeD { double min, max; };

// Suite names
#define kOfxPropertySuite               "OfxPropertySuite"
#define kOfxParameterSuite              "OfxParameterSuite"
#define kOfxImageEffectSuite            "OfxImageEffectSuite"
#define kOfxMemorySuite                 "OfxMemorySuite"
#define kOfxMultiThreadSuite            "OfxMultiThreadSuite"
#define kOfxMessageSuite                "OfxMessageSuite"
#define kOfxProgressSuite               "OfxProgressSuite"
#define kOfxTimeLineSuite               "OfxTimeLineSuite"

// Property Suite
struct OfxPropertySuiteV1 {
    OfxStatus (*propSetPointer)  (OfxPropertySetHandle props, const char* property, int index, void* value);
    OfxStatus (*propSetString)   (OfxPropertySetHandle props, const char* property, int index, const char* value);
    OfxStatus (*propSetDouble)   (OfxPropertySetHandle props, const char* property, int index, double value);
    OfxStatus (*propSetInt)      (OfxPropertySetHandle props, const char* property, int index, int value);
    OfxStatus (*propSetIntN)     (OfxPropertySetHandle props, const char* property, int count, const int* value);
    OfxStatus (*propSetStringN)  (OfxPropertySetHandle props, const char* property, int count, const char** value);
    OfxStatus (*propSetDoubleN)  (OfxPropertySetHandle props, const char* property, int count, const double* value);
    OfxStatus (*propSetPointerN) (OfxPropertySetHandle props, const char* property, int count, void** value);
    OfxStatus (*propGetPointer)  (OfxPropertySetHandle props, const char* property, int index, void** value);
    OfxStatus (*propGetString)   (OfxPropertySetHandle props, const char* property, int index, char** value);
    OfxStatus (*propGetDouble)   (OfxPropertySetHandle props, const char* property, int index, double* value);
    OfxStatus (*propGetInt)      (OfxPropertySetHandle props, const char* property, int index, int* value);
    OfxStatus (*propGetIntN)     (OfxPropertySetHandle props, const char* property, int count, int* value);
    OfxStatus (*propGetStringN)  (OfxPropertySetHandle props, const char* property, int count, char** value);
    OfxStatus (*propGetDoubleN)  (OfxPropertySetHandle props, const char* property, int count, double* value);
    OfxStatus (*propGetPointerN) (OfxPropertySetHandle props, const char* property, int count, void** value);
    OfxStatus (*propReset)       (OfxPropertySetHandle props, const char* property);
    OfxStatus (*propGetDimension)(OfxPropertySetHandle props, const char* property, int* count);
};

// Param Suite
struct OfxParameterSuiteV1 {
    OfxStatus (*paramDefine)             (OfxParamSetHandle paramSet, const char* paramType, const char* name, OfxPropertySetHandle* propertySet);
    OfxStatus (*paramGetHandle)          (OfxParamSetHandle paramSet, const char* name, OfxParamHandle* param, OfxPropertySetHandle* propertySet);
    OfxStatus (*paramSetGetPropertySet)  (OfxParamSetHandle paramSet, OfxPropertySetHandle* propHandle);
    OfxStatus (*paramGetPropertySet)     (OfxParamHandle param, OfxPropertySetHandle* propHandle);
    OfxStatus (*paramGetValue)           (OfxParamHandle paramH, ...);
    OfxStatus (*paramGetValueAtTime)     (OfxParamHandle paramH, double time, ...);
    OfxStatus (*paramGetDerivative)      (OfxParamHandle paramH, double time, ...);
    OfxStatus (*paramGetIntegral)        (OfxParamHandle paramH, double time1, double time2, ...);
    OfxStatus (*paramSetValue)           (OfxParamHandle paramH, ...);
    OfxStatus (*paramSetValueAtTime)     (OfxParamHandle paramH, double time, ...);
    OfxStatus (*paramGetNumKeys)         (OfxParamHandle paramH, unsigned int* numberOfKeys);
    OfxStatus (*paramGetKeyTime)         (OfxParamHandle paramH, unsigned int nthKey, double* time);
    OfxStatus (*paramGetKeyIndex)        (OfxParamHandle paramH, double time, int direction, int* index);
    OfxStatus (*paramDeleteKey)          (OfxParamHandle paramH, double time);
    OfxStatus (*paramDeleteAllKeys)      (OfxParamHandle paramH);
    OfxStatus (*paramCopy)               (OfxParamHandle paramTo, OfxParamHandle paramFrom, double dstOffset, const OfxRangeD* frameRange);
    OfxStatus (*paramEditBegin)          (OfxParamSetHandle paramSet, const char* name);
    OfxStatus (*paramEditEnd)            (OfxParamSetHandle paramSet);
};

// Image Effect Suite
struct OfxImageEffectSuiteV1 {
    OfxStatus (*getPropertySet)         (OfxImageEffectHandle imageEffect, OfxPropertySetHandle* propHandle);
    OfxStatus (*getParamSet)            (OfxImageEffectHandle imageEffect, OfxParamSetHandle* paramSet);
    OfxStatus (*clipDefine)             (OfxImageEffectHandle imageEffect, const char* name, OfxPropertySetHandle* propertySet);
    OfxStatus (*clipGetHandle)          (OfxImageEffectHandle imageEffect, const char* name, OfxImageClipHandle* clip, OfxPropertySetHandle* propertySet);
    OfxStatus (*clipGetPropertySet)     (OfxImageClipHandle clip, OfxPropertySetHandle* propHandle);
    OfxStatus (*clipGetImage)           (OfxImageClipHandle clip, double time, const OfxRectD* region, OfxPropertySetHandle* imageHandle);
    OfxStatus (*clipReleaseImage)       (OfxPropertySetHandle imageHandle);
    OfxStatus (*clipGetRegionOfDefinition)(OfxImageClipHandle clip, double time, OfxRectD* bounds);
    int       (*abort)                  (OfxImageEffectHandle imageEffect);
    OfxStatus (*imageMemoryAlloc)       (OfxImageEffectHandle instanceHandle, size_t nBytes, void** ptr);
    OfxStatus (*imageMemoryFree)        (void* ptr);
    OfxStatus (*imageMemoryLock)        (void* ptr);
    OfxStatus (*imageMemoryUnlock)      (void* ptr);
};

// Memory Suite
struct OfxMemorySuiteV1 {
    OfxStatus (*memoryAlloc)    (void* handle, size_t nBytes, void** allocatedData);
    OfxStatus (*memoryFree)     (void* allocatedData);
};

// Host structure
struct OfxHost {
    OfxPropertySetHandle host;
    void* (*fetchSuite)(OfxPropertySetHandle host, const char* suiteName, int suiteVersion);
};

// Plugin structure
struct OfxPlugin {
    const char*     pluginApi;
    int             apiVersion;
    const char*     pluginIdentifier;
    unsigned int    pluginVersionMajor;
    unsigned int    pluginVersionMinor;
    void            (*setHost)(OfxHost* host);
    OfxStatus       (*mainEntry)(const char* action, const void* handle, OfxPropertySetHandle inArgs, OfxPropertySetHandle outArgs);
};

// The plugin API string for image effects
#define kOfxImageEffectPluginApi        "OfxImageEffectPluginAPI"
#define kOfxImageEffectPluginApiVersion  1

// Export macros
#ifdef _WIN32
  #define EXPORT extern "C" __declspec(dllexport)
#else
  #define EXPORT extern "C" __attribute__((visibility("default")))
#endif
