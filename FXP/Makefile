# Makefile — FXPack OFX Plugin (MSYS2 MINGW64)
# Usage from the project root (where this file lives):
#
#   mingw32-make            — Release build
#   mingw32-make DEBUG=1    — Debug build
#   mingw32-make clean      — Remove build artefacts
#   mingw32-make install    — Copy bundle to the system OFX folder
#                             (requires an elevated / Administrator shell)

# ─────────────────────────────────────────────────────────────────────────────
# Toolchain  (MSYS2 MINGW64 provides these on PATH)
# ─────────────────────────────────────────────────────────────────────────────
CXX      := x86_64-w64-mingw32-g++
STRIP    := x86_64-w64-mingw32-strip

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
SRC_DIR     := src
INC_DIR     := include
BUILD_DIR   := build
BUNDLE_DIR  := bundle/FXPack.ofx.bundle/Contents/Win64
OFX_INSTALL := C:/Program Files/Common Files/OFX/Plugins/FXPack.ofx.bundle

# ─────────────────────────────────────────────────────────────────────────────
# Source / object lists
# ─────────────────────────────────────────────────────────────────────────────
SRCS := $(SRC_DIR)/FXPackPlugin.cpp \
        $(SRC_DIR)/effectBlur.cpp   \
        $(SRC_DIR)/effectGlow.cpp   \
        $(SRC_DIR)/effectGrain.cpp  \
        $(SRC_DIR)/effectShake.cpp  \
        $(SRC_DIR)/effectTransition.cpp

OBJS := $(patsubst $(SRC_DIR)/%.cpp, $(BUILD_DIR)/%.o, $(SRCS))

TARGET_NAME := FXPack.ofx

# ─────────────────────────────────────────────────────────────────────────────
# Flags
# ─────────────────────────────────────────────────────────────────────────────
CXXFLAGS_COMMON := -std=c++17 -Wall -I$(INC_DIR) \
                   -DWIN32 -DWIN64 -D_WINDOWS -D_USRDLL

ifdef DEBUG
  CXXFLAGS := $(CXXFLAGS_COMMON) -O0 -g -D_DEBUG
  BUILD_DIR := build/Debug
else
  CXXFLAGS := $(CXXFLAGS_COMMON) -O2 -DNDEBUG -mavx2
  BUILD_DIR := build/Release
endif

OBJS := $(patsubst $(SRC_DIR)/%.cpp, $(BUILD_DIR)/%.o, $(SRCS))

# Shared-library flags for a Windows DLL:
#   -shared          — build a DLL
#   -static-libgcc / -static-libstdc++  — bundle the runtime so Resolve
#                                          doesn't need MINGW DLLs on PATH
LDFLAGS := -shared \
            -static-libgcc -static-libstdc++ \
            -Wl,--subsystem,windows \
            -Wl,--kill-at \
            -Wl,--output-def,$(BUILD_DIR)/FXPack.def

# ─────────────────────────────────────────────────────────────────────────────
# Rules
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: all clean install

all: $(BUNDLE_DIR)/$(TARGET_NAME)

# ── Compile each .cpp → .o ────────────────────────────────────────────────────
$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

# ── Link all objects → FXPack.ofx (really a DLL) ─────────────────────────────
$(BUILD_DIR)/$(TARGET_NAME): $(OBJS)
	$(CXX) $(LDFLAGS) -o $@ $(OBJS)
ifndef DEBUG
	$(STRIP) --strip-unneeded $@
endif

# ── Copy the .ofx into the bundle ─────────────────────────────────────────────
$(BUNDLE_DIR)/$(TARGET_NAME): $(BUILD_DIR)/$(TARGET_NAME) | $(BUNDLE_DIR)
	cp -f $< $@
	@echo "Bundle ready: bundle/FXPack.ofx.bundle"

# ── Create build/obj directories as needed ───────────────────────────────────
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUNDLE_DIR):
	mkdir -p $(BUNDLE_DIR)

# ── Install (needs Administrator shell) ───────────────────────────────────────
install: $(BUNDLE_DIR)/$(TARGET_NAME)
	@echo "Installing to $(OFX_INSTALL) ..."
	mkdir -p "$(OFX_INSTALL)/Contents/Win64"
	cp -rf bundle/FXPack.ofx.bundle/. "$(OFX_INSTALL)/"
	@echo "Done. Restart DaVinci Resolve to load the plugin."

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	rm -rf build
	rm -f $(BUNDLE_DIR)/$(TARGET_NAME)
	@echo "Clean complete."
