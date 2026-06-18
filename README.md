# Zinc

A systems programming language that compiles to LLVM IR.

## Requirements

- **Linux x86_64** only (for now)
- **Python 3** (any modern version)
- Everything else is bundled in `deps/`

No need to install LLVM, Boehm GC, or any C runtime — it's all in `deps/`.

## Quick start

```sh
# Run a single file
./zinc run examples/basics/hello.zn

# Run a project directory
./zinc run .

# Build a binary
./zinc build examples/basics/hello.zn

# Emit LLVM IR
./zinc ir examples/basics/hello.zn
```

Or via make:
```sh
make run RUN=examples/basics/hello.zn
make build BUILD=examples/basics/hello.zn
make clean
```

## Structure

```
zinc              — entry point script
src/              — compiler (Python)
runtime/          — runtime library (runtime.ll)
deps/             — bundled LLVM tools, Boehm GC, CRT files
packages/         — standard library (math, os, time, graphics)
examples/         — example programs
```

## Packages

```zn
import "math"
import "os"
import "time"

math.sqrt(16.0)          // 4.0
os.list("/home")         // directory listing
time.now()               // unix timestamp
```

Graphics requires raylib system deps (OpenGL, X11) but they're usually preinstalled.

## Notes

- Linux x86_64 only. No Windows/macOS support yet.
- Uses Boehm GC — no manual memory management needed.
- All dependencies are bundled. No apt install required.
