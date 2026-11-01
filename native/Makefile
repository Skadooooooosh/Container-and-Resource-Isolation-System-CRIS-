CC      ?= cc
CFLAGS  ?= -std=gnu17 -D_GNU_SOURCE -O2 -Wall -Wextra -Wpedantic -Wshadow -Wformat=2 -D_FORTIFY_SOURCE=2 -fstack-protector-strong
BUILD   := build
INC     := -Iinclude

all: $(BUILD)/cris_run $(BUILD)/cris_workload

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/cris_run: src/cris_run.c include/cris_validate.h | $(BUILD)
	$(CC) $(CFLAGS) $(INC) -o $@ $<

$(BUILD)/cris_workload: src/cris_workload.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $<

# Unit test is built with AddressSanitizer + UBSan
$(BUILD)/test_validate: tests/test_validate.c include/cris_validate.h | $(BUILD)
	$(CC) $(CFLAGS) -fsanitize=address,undefined $(INC) -o $@ $<

test: $(BUILD)/test_validate
	./$(BUILD)/test_validate

clean:
	rm -rf $(BUILD)
.PHONY: all test clean
