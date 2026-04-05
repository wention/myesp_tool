UI_FILES := $(shell find . -name "*.ui")
PY_FILES := $(patsubst %.ui,%_ui.py,$(UI_FILES))

.PHONY: all clean

all: $(PY_FILES)

%_ui.py: %.ui
	uv run pyuic5 $< -o $@

clean:
	rm -f $(PY_FILES)
