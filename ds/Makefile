WONDERFUL_TOOLCHAIN ?= $(HOME)/.local/share/wonderful
BLOCKSDS := $(WONDERFUL_TOOLCHAIN)/thirdparty/blocksds/core
BLOCKSDSEXT := $(WONDERFUL_TOOLCHAIN)/thirdparty/blocksds/external
NAME := kinder_fresh
# Keep SDK targets space-free; publish the human-readable ROM atomically.
override ROM := build/kinder_fresh.nds
GAME_TITLE := Kinder Fresh Adventures
GAME_SUBTITLE := Nintendo DS port
GAME_AUTHOR := v$(shell cat ../VERSION)
GAME_ICON := icon.png
BINDIRS := assets
NITROFSDIR := nitrofs
LIBS := -lnds9 -lmm9
LIBDIRS := $(BLOCKSDS)/libs/maxmod
LDFLAGS += -Wl,--wrap=fread,--wrap=fseek
KF_DEBUG ?= 0
KF_PYTHON ?= python3
ifneq ($(filter $(KF_DEBUG),0 1),$(KF_DEBUG))
$(error KF_DEBUG must be 0 or 1)
endif
CFLAGS := -Wall -Wextra -Werror -DKF_DEBUG=$(KF_DEBUG)
include $(BLOCKSDS)/sys/default_makefiles/rom_arm9/Makefile

# Repack the ROM when the banner changes, even if ARM9 code is unchanged.
$(ROM): $(GAME_ICON) Makefile ../VERSION

# ARM9 graphics and transfer hot paths.
$(BUILDDIR)/source/scene.c.o $(BUILDDIR)/source/player_graphics.c.o $(BUILDDIR)/source/frame_transfer.c.o: CFLAGS += -marm
$(BUILDDIR)/source/scene.c.o $(BUILDDIR)/source/player_graphics.c.o $(BUILDDIR)/source/frame_transfer.c.o: Makefile

# ARM also improves the callback-heavy gameplay path on ARM946E-S.
$(BUILDDIR)/source/world.c.o $(BUILDDIR)/source/body.c.o $(BUILDDIR)/source/geometry.c.o $(BUILDDIR)/source/entities.c.o $(BUILDDIR)/source/enemies.c.o $(BUILDDIR)/source/platforms.c.o: CFLAGS += -marm
$(BUILDDIR)/source/world.c.o $(BUILDDIR)/source/body.c.o $(BUILDDIR)/source/geometry.c.o $(BUILDDIR)/source/entities.c.o $(BUILDDIR)/source/enemies.c.o $(BUILDDIR)/source/platforms.c.o: Makefile

# The streaming mixer is a bounded audio interrupt hot path.
$(BUILDDIR)/source/sound_events.c.o $(BUILDDIR)/source/audio.c.o: CFLAGS += -marm
$(BUILDDIR)/source/sound_events.c.o $(BUILDDIR)/source/audio.c.o: Makefile
$(BUILDDIR)/source/blocks.c.o: CFLAGS += -marm
$(BUILDDIR)/source/blocks.c.o: Makefile

# Recovered ordinary-enemy callbacks and the shared projectile pool run every tick.
$(BUILDDIR)/source/world_enemies.c.o $(BUILDDIR)/source/enemy_shots.c.o: CFLAGS += -marm
$(BUILDDIR)/source/world_enemies.c.o $(BUILDDIR)/source/enemy_shots.c.o: Makefile

$(BUILDDIR)/source/boss_factory.c.o $(BUILDDIR)/source/boss_valley.c.o $(BUILDDIR)/source/boss_mountain_jungle.c.o: CFLAGS += -marm
$(BUILDDIR)/source/boss_factory.c.o $(BUILDDIR)/source/boss_valley.c.o $(BUILDDIR)/source/boss_mountain_jungle.c.o: Makefile

$(BUILDDIR)/source/projectiles.c.o: CFLAGS += -marm
$(BUILDDIR)/source/projectiles.c.o: Makefile

# Texture-window uploads also traverse thousands of RGB555 pixels per scroll.
$(BUILDDIR)/source/gpu_prefix.c.o: CFLAGS += -marm
$(BUILDDIR)/source/gpu_prefix.c.o: Makefile

# SDK's ROM rule tracks the executable but not every file embedded by ndstool.
# Repack after any NitroFS asset edit, including nested files, without recompiling.
nitrofs_files = $(foreach path,$(wildcard $(1)*),$(if $(wildcard $(path)/.),$(path) $(call nitrofs_files,$(path)/),$(path)))
$(ROM): $(NITROFSDIR) $(call nitrofs_files,$(NITROFSDIR)/)

# Opt-in build + repeatable emulator playtest. The runner writes JSON/CSV logs
# and always closes its own emulator; ordinary builds remain build-only.
.PHONY: playtest playtest-all
playtest: $(ROM)
	"$(KF_PYTHON)" "$(abspath ..)/tools/playtest.py" --no-build
playtest-all: $(ROM)
	"$(KF_PYTHON)" "$(abspath ..)/tools/playtest.py" --no-build --world all

# Share exact NitroFS payload duplicates without changing file names or decoding.
# The SDK still constructs the executable/banner and DS/DSi support sections.
.PHONY: optimize-rom
all: publish-rom
optimize-rom: $(ROM) ../tools/deduplicate_nds.py
	python3 ../tools/deduplicate_nds.py "$(ROM)"
playtest playtest-all: publish-rom


$(BUILDDIR)/source/native_actors.c.o: CFLAGS += -marm

# Native tile/palette sampling is an ARM9 raster hot path.
$(BUILDDIR)/source/native_scene.c.o: CFLAGS += -marm

# Recompile source when changing debug mode without requiring a manual clean.
KF_CONFIG_STAMP := $(BUILDDIR)/.kf-debug-$(KF_DEBUG)
$(KF_CONFIG_STAMP):
	@mkdir -p "$(BUILDDIR)"
	@rm -f "$(BUILDDIR)/.kf-debug-0" "$(BUILDDIR)/.kf-debug-1"
	@touch "$@"
$(OBJS_SOURCES): $(KF_CONFIG_STAMP)

.PHONY: publish-rom clean-published
publish-rom: optimize-rom ../tools/publish_rom.py ../VERSION
	python3 ../tools/publish_rom.py "$(ROM)" "Kinder Fresh Adventures.nds"
clean: clean-published
clean-published:
	rm -f "Kinder Fresh Adventures.nds" "Kinder Fresh Adventures.nds.sha256"
