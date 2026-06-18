import os
import shutil
import subprocess
import sys


class ToolchainError(Exception):
    pass


def _deps_bin():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "deps", "bin")


class ZincToolchain:
    def __init__(self):
        self._tools = {}
        self._search()

    def _search(self):
        llvm_dir = os.environ.get("LLVM_DIR", "")

        candidates = []
        deps_bin = _deps_bin()
        if os.path.isdir(deps_bin):
            candidates.append(deps_bin)
        if llvm_dir:
            candidates.append(llvm_dir)

        for ver in range(20, 10, -1):
            candidates.append(f"/usr/lib/llvm-{ver}/bin")

        candidates.append("/usr/bin")
        candidates.append("/usr/local/bin")

        self._search_dirs = candidates

        self._find_tool("llc", ["llc"])
        self._find_tool("lli", ["lli"])
        self._find_tool("llvm-link", ["llvm-link"])
        self._find_tool("lld", ["ld.lld", "ld.lld-18", "ld.lld-20", "ld.lld-19", "lld-18", "lld-20", "lld-19", "lld"])

    def _find_tool(self, name, candidates):
        for d in self._search_dirs:
            for c in candidates:
                path = os.path.join(d, c)
                if os.path.exists(path):
                    self._tools[name] = path
                    return
                which = shutil.which(c)
                if which:
                    self._tools[name] = which
                    return
        self._tools[name] = None

    def tool(self, name):
        path = self._tools.get(name)
        if not path:
            raise ToolchainError(
                f"LLVM tool '{name}' not found. "
                f"Set LLVM_DIR to your LLVM installation or install the package."
            )
        return path

    def run(self, name, args, **kwargs):
        cmd = [self.tool(name)] + args
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

    def system(self, name, args):
        cmd = [self.tool(name)] + args
        cmd_str = " ".join(cmd)
        return os.system(cmd_str)

    def check(self):
        missing = []
        for name in ["llc", "lli", "llvm-link", "lld"]:
            if not self._tools.get(name):
                missing.append(name)
        if missing:
            print(f"Missing LLVM tools: {', '.join(missing)}", file=sys.stderr)
            print("Install them or set LLVM_DIR environment variable.", file=sys.stderr)
            return False
        return True


_default_toolchain = None


def get_toolchain():
    global _default_toolchain
    if _default_toolchain is None:
        _default_toolchain = ZincToolchain()
    return _default_toolchain
