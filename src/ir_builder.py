import struct


class IRType:
    def __init__(self, llvm_str):
        self.llvm_str = llvm_str

    def __str__(self):
        return self.llvm_str

    def __eq__(self, other):
        if isinstance(other, IRType):
            return self.llvm_str == other.llvm_str
        if isinstance(other, str):
            return self.llvm_str == other
        return NotImplemented

    def __hash__(self):
        return hash(self.llvm_str)


VOID = IRType("void")
I1 = IRType("i1")
I4 = IRType("i4")
I8 = IRType("i8")
I16 = IRType("i16")
I32 = IRType("i32")
I64 = IRType("i64")
FLOAT = IRType("float")
DOUBLE = IRType("double")
PTR = IRType("ptr")


def named_struct_type(name):
    return IRType(f"%{name}")


def literal_struct_type(members):
    return IRType("{" + ", ".join(str(m) for m in members) + "}")


def array_type(element, size):
    return IRType(f"[{size} x {element}]")


class IRValue:
    _counter = 0

    def __init__(self, ir_type, name=None):
        self.ir_type = ir_type
        if name:
            self.name = name
        else:
            IRValue._counter += 1
            self.name = f"%v{IRValue._counter}"

    def __str__(self):
        return self.name


class Constant(IRValue):
    def __init__(self, ir_type, value):
        super().__init__(ir_type, name="")
        self._value = value

    def __str__(self):
        if isinstance(self._value, str):
            return self._value
        return str(self._value)


def const_int(value, bits=64):
    return Constant(IRType(f"i{bits}"), str(value))


def const_bool(value):
    return Constant(I1, "true" if value else "false")


def const_float(value):
    hex_val = struct.pack('>f', float(value)).hex()
    return Constant(FLOAT, f"0x{hex_val}")


def const_double(value):
    hex_val = struct.pack('>d', float(value)).hex()
    return Constant(DOUBLE, f"0x{hex_val}")


def const_null():
    return Constant(PTR, "null")

def const_zeroinitializer(ir_type):
    return Constant(ir_type, "zeroinitializer")


class GlobalString:
    _counter = 0

    def __init__(self, value):
        GlobalString._counter += 1
        self.name = f".str.{GlobalString._counter}"
        self.value = value
        self.length = len(value)

    def emit(self):
        if '"' in self.value:
            bytes_str = ', '.join(f'i8 {ord(c)}' for c in self.value) + ', i8 0'
            return f'@{self.name} = private unnamed_addr constant [{self.length + 1} x i8] [{bytes_str}]'
        escaped = (self.value
                   .replace('\\', '\\\\')
                   .replace('\n', '\\0A')
                   .replace('\t', '\\09')
                   .replace('\0', '\\00'))
        return f'@{self.name} = private unnamed_addr constant [{self.length + 1} x i8] c"{escaped}\\00"'


class IRInstr:
    def __init__(self, text):
        self.text = text

    def emit(self):
        return self.text


class BasicBlock:
    _counter = 0

    def __init__(self, label=None):
        BasicBlock._counter += 1
        if label:
            self.label = f"{label}.{BasicBlock._counter}"
        else:
            self.label = f"bb{BasicBlock._counter}"
        self.instructions = []
        self.terminator = None

    def add(self, instr):
        self.instructions.append(instr)
        return instr

    def set_terminator(self, term):
        self.terminator = term

    def emit(self):
        lines = [f"{self.label}:"]
        for instr in self.instructions:
            lines.append("  " + instr.emit())
        return "\n".join(lines)


class FunctionIR:
    _fn_counter = 0

    def __init__(self, name, ret_type, param_types, param_names=None):
        self.name = name
        self.ret_type = ret_type
        self.param_types = param_types
        self.param_names = param_names or [f"p{i}" for i in range(len(param_types))]
        self.blocks = []
        self.is_declaration = False

    def new_block(self, label=None):
        bb = BasicBlock(label)
        self.blocks.append(bb)
        return bb

    def emit(self):
        if self.is_declaration:
            params = ", ".join(f"{t} %{n}" for t, n in zip(self.param_types, self.param_names))
            return f"declare {self.ret_type} @{self.name}({params})"
        params = ", ".join(f"{t} %{n}" for t, n in zip(self.param_types, self.param_names))
        lines = [f"define {self.ret_type} @{self.name}({params}) {{"]
        for bb in self.blocks:
            lines.append(bb.emit())
        lines.append("}")
        return "\n".join(lines)


class ModuleIR:
    def __init__(self):
        self.target_triple = "x86_64-pc-linux-gnu"
        self.data_layout = ""
        self.global_strings = []
        self.global_lines = []
        self.declarations = []
        self.type_defs = []
        self.functions = []

    def add_global_string(self, gs):
        self.global_strings.append(gs)
        return gs

    def add_global_line(self, line):
        self.global_lines.append(line)

    def add_declaration(self, decl):
        self.declarations.append(decl)

    def add_type(self, type_def):
        self.type_defs.append(type_def)

    def add_function(self, func):
        self.functions.append(func)

    def emit(self):
        lines = []
        if self.target_triple:
            lines.append(f'target triple = "{self.target_triple}"')
        if self.data_layout:
            lines.append(f'data layout = "{self.data_layout}"')
        lines.append("")
        for td in self.type_defs:
            lines.append(str(td))
        if self.type_defs:
            lines.append("")
        for gs in self.global_strings:
            lines.append(gs.emit())
        if self.global_strings:
            lines.append("")
        for gl in self.global_lines:
            lines.append(gl)
        if self.global_lines:
            lines.append("")
        for decl in self.declarations:
            lines.append(decl.emit())
        if self.declarations:
            lines.append("")
        for func in self.functions:
            lines.append(func.emit())
            lines.append("")
        return "\n".join(lines)


_uid_counter = 0


def _uid():
    global _uid_counter
    _uid_counter += 1
    return _uid_counter


def emit_alloca(block, ir_type, name=None):
    uid = _uid()
    result = f"%{name}" if name else f"%a{uid}"
    instr = IRInstr(f"{result} = alloca {ir_type}, align 8")
    block.add(instr)
    return IRValue(PTR, result)


def emit_load(block, ptr, ir_type):
    uid = _uid()
    result = f"%l{uid}"
    instr = IRInstr(f"{result} = load {ir_type}, ptr {ptr}, align 8")
    block.add(instr)
    return IRValue(ir_type, result)


def emit_store(block, value, ptr):
    instr = IRInstr(f"store {value.ir_type} {value}, ptr {ptr}, align 8")
    block.add(instr)


def emit_binop(block, op, left, right, result_type):
    uid = _uid()
    result = f"%b{uid}"
    s = str(result_type)
    if "double" in s or "float" in s:
        fop_map = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}
        llvm_op = fop_map.get(op, op)
    else:
        iop_map = {"+": "add", "-": "sub", "*": "mul", "/": "sdiv", "%": "srem",
                    "and": "and", "or": "or", "xor": "xor"}
        llvm_op = iop_map.get(op, op)
    instr = IRInstr(f"{result} = {llvm_op} {result_type} {left}, {right}")
    block.add(instr)
    return IRValue(result_type, result)


def emit_icmp(block, cond, left, right, ir_type):
    uid = _uid()
    result = f"%c{uid}"
    cmap = {"==": "eq", "!=": "ne", "<": "slt", ">": "sgt", "<=": "sle", ">=": "sge"}
    cc = cmap.get(cond, cond)
    instr = IRInstr(f"{result} = icmp {cc} {ir_type} {left}, {right}")
    block.add(instr)
    return IRValue(I1, result)


def emit_fcmp(block, cond, left, right, ir_type):
    uid = _uid()
    result = f"%fc{uid}"
    cmap = {"==": "oeq", "!=": "one", "<": "olt", ">": "ogt", "<=": "ole", ">=": "oge"}
    cc = cmap.get(cond, cond)
    instr = IRInstr(f"{result} = fcmp {cc} {ir_type} {left}, {right}")
    block.add(instr)
    return IRValue(I1, result)


def emit_br(block, target_block):
    instr = IRInstr(f"br label %{target_block.label}")
    block.add(instr)
    block.set_terminator(instr)


def emit_cond_br(block, cond, true_block, false_block):
    instr = IRInstr(f"br i1 {cond}, label %{true_block.label}, label %{false_block.label}")
    block.add(instr)
    block.set_terminator(instr)


def emit_unreachable(block):
    instr = IRInstr("unreachable")
    block.add(instr)
    block.set_terminator(instr)

def emit_ret(block, value=None):
    if value:
        instr = IRInstr(f"ret {value.ir_type} {value}")
    else:
        instr = IRInstr("ret void")
    block.add(instr)
    block.set_terminator(instr)


def emit_call(block, callee, args, ret_type=None):
    args_str = ", ".join(f"{a.ir_type} {a}" for a in args)
    if ret_type and str(ret_type) != "void":
        uid = _uid()
        result = f"%call{uid}"
        instr = IRInstr(f"{result} = call {ret_type} @{callee}({args_str})")
        block.add(instr)
        return IRValue(ret_type, result)
    else:
        instr = IRInstr(f"call void @{callee}({args_str})")
        block.add(instr)
        return None


def emit_indirect_call(block, callee_ptr, args, ret_type=I64):
    args_str = ", ".join(f"{a.ir_type} {a}" for a in args)
    if str(ret_type) != "void":
        uid = _uid()
        result = f"%call{uid}"
        instr = IRInstr(f"{result} = call {ret_type} {callee_ptr}({args_str})")
        block.add(instr)
        return IRValue(ret_type, result)
    else:
        instr = IRInstr(f"call void {callee_ptr}({args_str})")
        block.add(instr)
        return None


def emit_gep(block, base_type, ptr, indices):
    uid = _uid()
    result = f"%gep{uid}"
    indices_str = ", ".join(f"{i.ir_type} {i}" for i in indices)
    instr = IRInstr(f"{result} = getelementptr inbounds {base_type}, ptr {ptr}, {indices_str}")
    block.add(instr)
    return IRValue(PTR, result)


def emit_bitcast(block, value, target_type):
    uid = _uid()
    result = f"%bc{uid}"
    instr = IRInstr(f"{result} = bitcast {value.ir_type} {value} to {target_type}")
    block.add(instr)
    return IRValue(target_type, result)


def emit_ptrtoint(block, value, target_type):
    uid = _uid()
    result = f"%pi{uid}"
    instr = IRInstr(f"{result} = ptrtoint {value.ir_type} {value} to {target_type}")
    block.add(instr)
    return IRValue(target_type, result)


def emit_inttoptr(block, value, target_type):
    uid = _uid()
    result = f"%ip{uid}"
    instr = IRInstr(f"{result} = inttoptr {value.ir_type} {value} to {target_type}")
    block.add(instr)
    return IRValue(target_type, result)


def emit_sext(block, value, target_type):
    uid = _uid()
    result = f"%se{uid}"
    instr = IRInstr(f"{result} = sext {value.ir_type} {value} to {target_type}")
    block.add(instr)
    return IRValue(target_type, result)


def emit_zext(block, value, target_type):
    uid = _uid()
    result = f"%ze{uid}"
    instr = IRInstr(f"{result} = zext {value.ir_type} {value} to {target_type}")
    block.add(instr)
    return IRValue(target_type, result)


def emit_extractvalue(block, struct_val, index, result_type):
    uid = _uid()
    result = f"%ev{uid}"
    instr = IRInstr(f"{result} = extractvalue {struct_val.ir_type} {struct_val}, {index}")
    block.add(instr)
    return IRValue(result_type, result)


def emit_trunc(block, value, target_type):
    uid = _uid()
    result = f"%tr{uid}"
    instr = IRInstr(f"{result} = trunc {value.ir_type} {value} to {target_type}")
    block.add(instr)
    return IRValue(target_type, result)


def emit_sitofp(block, value, target_type):
    uid = _uid()
    result = f"%sf{uid}"
    instr = IRInstr(f"{result} = sitofp {value.ir_type} {value} to {target_type}")
    block.add(instr)
    return IRValue(target_type, result)


def emit_fptosi(block, value, target_type):
    uid = _uid()
    result = f"%fs{uid}"
    instr = IRInstr(f"{result} = fptosi {value.ir_type} {value} to {target_type}")
    block.add(instr)
    return IRValue(target_type, result)


def emit_fpext(block, value, target_type):
    uid = _uid()
    result = f"%fe{uid}"
    instr = IRInstr(f"{result} = fpext {value.ir_type} {value} to {target_type}")
    block.add(instr)
    return IRValue(target_type, result)


def emit_fptrunc(block, value, target_type):
    uid = _uid()
    result = f"%ft{uid}"
    instr = IRInstr(f"{result} = fptrunc {value.ir_type} {value} to {target_type}")
    block.add(instr)
    return IRValue(target_type, result)


def emit_select(block, cond, true_val, false_val):
    uid = _uid()
    result = f"%sel{uid}"
    t = true_val.ir_type
    instr = IRInstr(f"{result} = select i1 {cond}, {t} {true_val}, {t} {false_val}")
    block.add(instr)
    return IRValue(t, result)


def declare_function(module, name, ret_type, param_types):
    func = FunctionIR(name, ret_type, param_types)
    func.is_declaration = True
    module.add_declaration(func)
    return func
