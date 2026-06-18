import sys
import os
import tempfile
import subprocess

from .lexer import Lexer
from .parser import Parser
from .compiler import Compiler
from .ast_nodes import Program
from .toolchain import get_toolchain, ToolchainError


VERSION = "1.0.0"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPS_DIR = os.path.join(PROJECT_ROOT, "deps")
DEPS_BIN = os.path.join(DEPS_DIR, "bin")
DEPS_LIB = os.path.join(DEPS_DIR, "lib")
DEPS_CRT = os.path.join(DEPS_DIR, "crt")


def get_runtime_path():
    return os.path.join(PROJECT_ROOT, "runtime", "runtime.ll")


def parse_file(path):
    with open(path, 'r') as f:
        text = f.read()
    filename = os.path.basename(path)
    lexer = Lexer(text, filename)
    parser = Parser(lexer, source_path=path)
    return parser.parse()


def compile_to_ll(source_path, output_path=None):
    program = parse_file(source_path)
    compiler = Compiler()
    module = compiler.compile(program)
    ll_text = module.emit()
    if output_path is None:
        output_path = os.path.splitext(source_path)[0] + ".ll"
    with open(output_path, 'w') as f:
        f.write(ll_text)
    return output_path, compiler.bundled_sos


def compile_directory(dir_path):
    zn_files = sorted([
        os.path.join(dir_path, f)
        for f in os.listdir(dir_path)
        if f.endswith('.zn') and os.path.isfile(os.path.join(dir_path, f))
    ])
    if not zn_files:
        print(f"No .zn files found in {dir_path}")
        sys.exit(1)
    all_decls = []
    for f in zn_files:
        program = parse_file(f)
        all_decls.extend(program.declarations)
    combined = Program()
    combined.declarations = all_decls
    compiler = Compiler()
    module = compiler.compile(combined)
    return module.emit(), compiler.bundled_sos


def check_init(dir_path):
    mod_path = os.path.join(dir_path, "zinc.mod")
    if not os.path.exists(mod_path):
        print(f"Error: not a Zinc project (no zinc.mod found)")
        print(f"Run 'zinc init {dir_path}' to initialize")
        sys.exit(1)
    with open(mod_path) as f:
        line = f.read().strip()
    if line.startswith("zinc "):
        ver = line[5:]
        if ver != VERSION:
            print(f"Warning: project targets Zinc {ver}, using {VERSION}")
    else:
        print("Warning: invalid zinc.mod format")


def do_init(path):
    os.makedirs(path, exist_ok=True)
    mod_path = os.path.join(path, "zinc.mod")
    if os.path.exists(mod_path):
        print(f"zinc.mod already exists at {mod_path}")
        return
    with open(mod_path, 'w') as f:
        f.write(f"zinc {VERSION}\n")
    print(f"Initialized Zinc project at {path}")


def do_run(path):
    tc = get_toolchain()
    ll_path = None
    bc_path = None
    bundled_sos = []
    try:
        if path.endswith('.zn'):
            ll_path, bundled_sos = compile_to_ll(path)
        else:
            check_init(path)
            base = os.path.basename(os.path.normpath(path))
            ll_path = os.path.join(os.path.dirname(path), f".zinc_{base}.ll")
            ll_text, bundled_sos = compile_directory(path)
            with open(ll_path, 'w') as f:
                f.write(ll_text)
        runtime = get_runtime_path()
        bc_path = ll_path.replace('.ll', '.bc')
        tc.system("llvm-link", [runtime, ll_path, "-o", bc_path])
        lib_dirs = [DEPS_LIB]
        for p in bundled_sos:
            d = os.path.dirname(p)
            if d not in lib_dirs:
                lib_dirs.append(d)
        env = os.environ.copy()
        extra = ":".join(lib_dirs)
        existing = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{extra}:{existing}" if existing else extra
        preload_parts = []
        if bundled_sos:
            preload_parts.extend(bundled_sos)
        gc_so = os.path.join(DEPS_LIB, "libgc.so")
        if os.path.exists(gc_so):
            preload_parts.append(gc_so)
        if preload_parts:
            existing = env.get("LD_PRELOAD", "")
            extra = ":".join(preload_parts)
            env["LD_PRELOAD"] = f"{extra}:{existing}" if existing else extra
        subprocess.run([tc.tool("lli"), bc_path], env=env)
    finally:
        for p in [ll_path, bc_path]:
            if p and os.path.exists(p):
                os.unlink(p)


def _find_crt(name):
    p = os.path.join(DEPS_CRT, name)
    if os.path.exists(p):
        return p
    for d in ["/lib/x86_64-linux-gnu", "/usr/lib/x86_64-linux-gnu", "/lib64"]:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return name


def do_build(path):
    tc = get_toolchain()
    ll_path = None
    bc_path = None
    obj_path = None
    bundled_sos = []
    try:
        if path.endswith('.zn'):
            ll_path, bundled_sos = compile_to_ll(path)
            base = os.path.splitext(ll_path)[0]
        else:
            check_init(path)
            base = os.path.basename(os.path.normpath(path))
            ll_path = os.path.join(os.path.dirname(path), f".zinc_{base}.ll")
            ll_text, bundled_sos = compile_directory(path)
            with open(ll_path, 'w') as f:
                f.write(ll_text)
        runtime = get_runtime_path()
        bc_path = ll_path.replace('.ll', '.bc')
        obj_path = ll_path.replace('.ll', '.o')
        tc.system("llvm-link", [runtime, ll_path, "-o", bc_path])
        tc.system("llc", [bc_path, "-o", obj_path, "--filetype=obj"])
        crt1 = _find_crt("crt1.o")
        crti = _find_crt("crti.o")
        crtn = _find_crt("crtn.o")
        ld_so = os.path.join(DEPS_LIB, "ld-linux-x86-64.so.2")
        link_inputs = [crt1, crti, obj_path] + bundled_sos
        ret = tc.system("lld", [
            *link_inputs,
            "-L" + DEPS_LIB, "-lc", "-lgc",
            "-dynamic-linker", ld_so,
            crtn, "-o", base,
        ])
        if ret == 0:
            print(f"Built: {base}")
        else:
            print("Build failed")
    finally:
        for p in [ll_path, bc_path, obj_path]:
            if p and os.path.exists(p):
                os.unlink(p)


def do_ir(path):
    if path.endswith('.zn'):
        ll_path = compile_to_ll(path)
        print(f"Generated: {ll_path}")
    else:
        base = os.path.basename(os.path.normpath(path))
        ll_path = f"{base}.ll"
        ll_text = compile_directory(path)
        with open(ll_path, 'w') as f:
            f.write(ll_text)
        print(f"Generated: {ll_path}")


def print_usage():
    print("Usage:")
    print("  zinc init [path]       Initialize a Zinc project")
    print("  zinc run <path>        Run a .zn file or Zinc project")
    print("  zinc build <path>      Build a .zn file or Zinc project")
    print("  zinc ir <path>         Emit LLVM IR for a .zn file or project")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        path = sys.argv[2] if len(sys.argv) > 2 else "."
        do_init(path)

    elif command == "run":
        path = sys.argv[2] if len(sys.argv) > 2 else "."
        if not os.path.exists(path):
            print(f"File not found: {path}")
            sys.exit(1)
        do_run(path)

    elif command == "build":
        path = sys.argv[2] if len(sys.argv) > 2 else "."
        if not os.path.exists(path):
            print(f"File not found: {path}")
            sys.exit(1)
        do_build(path)

    elif command == "ir":
        path = sys.argv[2] if len(sys.argv) > 2 else "."
        if not os.path.exists(path):
            print(f"File not found: {path}")
            sys.exit(1)
        do_ir(path)

    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
