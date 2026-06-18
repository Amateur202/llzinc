DEPS_URL := https://github.com/Amateur202/llzinc/releases/download/v1/deps.tar.gz
RUN  ?= .
BUILD?= .

setup:
	@if [ -d deps ]; then \
		echo "deps/ already exists"; \
	else \
		echo "Downloading Zinc dependencies..."; \
		curl -L -o deps.tar.gz "$(DEPS_URL)" && \
		tar -xzf deps.tar.gz && \
		rm deps.tar.gz && \
		echo "Done. Run './zinc run <file>' to start."; \
	fi

run:
	./zinc run "$(RUN)"

build:
	./zinc build "$(BUILD)"

clean:
	find . -name '*.ll' -not -path './runtime/*' -delete
	find . -name '*.bc' -delete
	find . -name '*.o' -not -path './deps/*' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
	rm -f zinc.*.ll
	@echo "Cleaned"

check:
	@python3 -c "from src.toolchain import get_toolchain; tc = get_toolchain(); tc.check() and print('All tools found')"

.PHONY: setup run build clean check
