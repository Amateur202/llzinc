import os
import sys

from . import ast_nodes as ast
from .ir_builder import *
from .lexer import Lexer
from .parser import Parser


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def resolve_import_path(import_path, source_file=None):
    packages_dir = os.path.join(PROJECT_ROOT, "packages", import_path)
    if os.path.isdir(packages_dir):
        return packages_dir
    if source_file:
        base = os.path.dirname(os.path.abspath(source_file))
        local_dir = os.path.normpath(os.path.join(base, import_path))
        if os.path.isdir(local_dir):
            return local_dir
    return None


class CompilerError(Exception):
    def __init__(self, message):
        super().__init__(f"[ZINC][ERROR] {message}")


STRING_TYPE = literal_struct_type([PTR, I64])
STRING_PTR_TYPE = PTR
VECTOR_TYPE = literal_struct_type([PTR, I64, I64])


class Compiler:
    def __init__(self):
        self.module = ModuleIR()
        self.symbols = {}
        self.globals = {}
        self.const_values = {}
        self.structs = {}
        self.enums = {}
        self.functions = {}
        self.current_func = None
        self.current_block = None
        self.loop_exit_blocks = []
        self.loop_cond_blocks = []
        self.break_blocks = []
        self.continue_blocks = []
        self.defer_stmts = []
        self.var_types = {}
        self.var_type_nodes = {}
        self.struct_types_added = set()
        self._uid_counter = 0
        self.imported_modules = {}
        self.imported_decls = []
        self.extern_funcs = {}
        self.bundled_sos = []

    def compile(self, program):
        self._collect_declarations(program)
        self._emit_declarations()
        self._compile_declarations(program)
        return self.module

    @staticmethod
    def _is_private(name):
        return name.startswith("_")

    def _collect_declarations(self, program):
        for decl in program.declarations:
            if isinstance(decl, ast.StructDecl):
                self.structs[decl.name] = decl
            elif isinstance(decl, ast.EnumDecl):
                self.enums[decl.name] = decl
            elif isinstance(decl, ast.FunctionDecl):
                self.functions[decl.name] = decl
            elif isinstance(decl, ast.ImportDecl):
                self._resolve_import(decl)
            elif isinstance(decl, ast.VarDecl):
                pass
            elif isinstance(decl, ast.MultiVarDecl):
                pass
            elif isinstance(decl, ast.ExternBlock):
                for f in decl.funcs:
                    self.extern_funcs[f.zinc_name] = (f.ret_type, f.c_name, f.params)

    def _resolve_import(self, decl):
        import_path = decl.path
        source_file = decl.source_file
        module_name = os.path.basename(import_path.rstrip("/\\"))
        if not module_name:
            return
        if module_name in self.imported_modules:
            return
        dir_path = resolve_import_path(import_path, source_file)
        if dir_path is None:
            raise CompilerError(f"Import not found: '{import_path}'")
        if not os.path.isdir(dir_path):
            raise CompilerError(f"Import path is not a directory: '{import_path}'")
        zn_files = sorted([
            os.path.join(dir_path, f)
            for f in os.listdir(dir_path)
            if f.endswith('.zn') and os.path.isfile(os.path.join(dir_path, f))
        ])
        module_decls = []
        for f in zn_files:
            text = open(f).read()
            filename = os.path.basename(f)
            lexer = Lexer(text, filename)
            parser = Parser(lexer, source_path=f)
            prog = parser.parse()
            for d in prog.declarations:
                if isinstance(d, ast.ExternBlock):
                    for f in d.funcs:
                        extern_full = f"{module_name}.{f.zinc_name}"
                        self.extern_funcs[extern_full] = (f.ret_type, f.c_name, f.params)
                    continue
                full_name = f"{module_name}.{d.name}"
                if isinstance(d, ast.StructDecl):
                    if not self._is_private(d.name):
                        self.structs[full_name] = d
                elif isinstance(d, ast.EnumDecl):
                    if not self._is_private(d.name):
                        self.enums[full_name] = d
                elif isinstance(d, ast.FunctionDecl):
                    self.functions[full_name] = d
                elif isinstance(d, ast.VarDecl):
                    if not self._is_private(d.name):
                        self.globals[full_name] = (PTR, None, full_name)
                elif isinstance(d, ast.ConstDecl):
                    if not self._is_private(d.name):
                        val = self._eval_const_expr(d.value)
                        if isinstance(val, float):
                            self.const_values[full_name] = val
                        else:
                            self.const_values[full_name] = int(val) if val else 0
                elif isinstance(d, ast.MultiVarDecl):
                    pass
                module_decls.append((module_name, d))
        so_files = sorted([
            os.path.join(dir_path, f)
            for f in os.listdir(dir_path)
            if f.endswith('.so') and os.path.isfile(os.path.join(dir_path, f))
        ])
        self.bundled_sos.extend(so_files)
        self.imported_modules[module_name] = True
        self.imported_decls.extend(module_decls)

    def _emit_declarations(self):
        self._declare_runtime_funcs()
        for zinc_name, (ret_type, c_name, params) in self.extern_funcs.items():
            ret_ir = self._zinc_type_to_ir(ret_type)
            param_irs = [self._zinc_type_to_ir(p) for p in params]
            declare_function(self.module, c_name, ret_ir, param_irs)

    def _declare_runtime_funcs(self):
        str_type = STRING_TYPE
        declare_function(self.module, "__zn_println", VOID, [str_type])
        declare_function(self.module, "__zn_print", VOID, [str_type])
        declare_function(self.module, "__zn_print_int", VOID, [I64])
        declare_function(self.module, "__zn_print_float", VOID, [DOUBLE])
        declare_function(self.module, "__zn_print_bool", VOID, [I8])
        declare_function(self.module, "__zn_print_char", VOID, [I8])
        declare_function(self.module, "__zn_input", str_type, [str_type])
        declare_function(self.module, "__zn_int64_to_string", str_type, [I64])
        declare_function(self.module, "__zn_float64_to_string", str_type, [DOUBLE])
        declare_function(self.module, "__zn_string_to_int64", I64, [str_type])
        declare_function(self.module, "__zn_string_to_float64", DOUBLE, [str_type])
        declare_function(self.module, "__zn_string_concat", str_type, [str_type, str_type])
        declare_function(self.module, "__zn_string_from_char", str_type, [I8])
        declare_function(self.module, "__zn_string_length", I64, [str_type])
        declare_function(self.module, "__zn_string_upper", str_type, [str_type])
        declare_function(self.module, "__zn_string_lower", str_type, [str_type])
        declare_function(self.module, "__zn_string_contains", I8, [str_type, str_type])
        declare_function(self.module, "__zn_string_index", I8, [str_type, I64])
        declare_function(self.module, "__zn_string_split", VECTOR_TYPE, [str_type, str_type])
        declare_function(self.module, "__zn_len", I64, [str_type])
        declare_function(self.module, "__zn_abort", VOID, [str_type])
        declare_function(self.module, "__zn_exists", I8, [str_type])
        declare_function(self.module, "__zn_vector_get", I64, [VECTOR_TYPE, I64])
        declare_function(self.module, "__zn_vector_push", VOID, [PTR, I64])
        declare_function(self.module, "__zn_vector_push_string", VOID, [PTR, STRING_TYPE])
        declare_function(self.module, "__zn_vector_push_value", VOID, [PTR, PTR, I64])
        declare_function(self.module, "__zn_vector_pop", VOID, [PTR])
        declare_function(self.module, "__zn_vector_contains", I8, [VECTOR_TYPE, I64])
        declare_function(self.module, "__zn_vector_set", VOID, [PTR, I64, I64])
        declare_function(self.module, "__zn_range", VECTOR_TYPE, [I64, I64, I64])
        declare_function(self.module, "GC_malloc", PTR, [I64])
        declare_function(self.module, "GC_realloc", PTR, [PTR, I64])
        declare_function(self.module, "GC_init", VOID, [])
        declare_function(self.module, "llvm.memcpy.p0.p0.i64", VOID, [PTR, PTR, I64, I1])
        declare_function(self.module, "__zn_map_new", PTR, [])
        declare_function(self.module, "__zn_map_set_value", VOID, [PTR, PTR, I64, PTR, I64])
        declare_function(self.module, "__zn_map_get_value", I8, [PTR, PTR, I64, PTR])
        declare_function(self.module, "__zn_map_contains", I8, [PTR, PTR, I64])
        declare_function(self.module, "__zn_map_delete", VOID, [PTR, PTR, I64])
        declare_function(self.module, "__zn_file_open", PTR, [str_type, str_type])
        declare_function(self.module, "__zn_file_write", VOID, [PTR, str_type])
        declare_function(self.module, "__zn_file_read", str_type, [PTR])
        declare_function(self.module, "__zn_file_readln", str_type, [PTR])
        declare_function(self.module, "__zn_file_close", VOID, [PTR])
        declare_function(self.module, "__zn_file_is_eof", I8, [PTR])
        declare_function(self.module, "__zn_argv_to_vector", VECTOR_TYPE, [PTR])

    def _compile_declarations(self, program):
        for decl in program.declarations:
            self._compile_decl(decl)
        for module_name, decl in self.imported_decls:
            full_name = f"{module_name}.{decl.name}"
            self._compile_decl(decl, name_override=full_name, module_name=module_name)

    def _compile_decl(self, decl, name_override=None, module_name=None):
        old_module = getattr(self, 'current_module', None)
        if module_name:
            self.current_module = module_name
        if isinstance(decl, ast.FunctionDecl):
            self._compile_function(decl, name_override)
        elif isinstance(decl, ast.StructDecl):
            self._compile_struct_type(decl, name_override)
        elif isinstance(decl, ast.EnumDecl):
            pass
        elif isinstance(decl, ast.ConstDecl):
            name = name_override or decl.name
            self._compile_global_var(name, decl.type_node, decl.value)
        elif isinstance(decl, ast.VarDecl):
            name = name_override or decl.name
            self._compile_global_var(name, decl.type_node, decl.value)
        elif isinstance(decl, ast.ImportDecl):
            pass
        elif isinstance(decl, ast.MultiVarDecl):
            pass
        elif isinstance(decl, ast.ExternBlock):
            pass
        self.current_module = old_module

    def _compile_global_var(self, name, type_node, value):
        ir_type = self._zinc_type_to_ir(type_node) if type_node else I64
        self.var_types[name] = self._zinc_type_to_str(type_node) if type_node else "int"
        if not value:
            self.globals[name] = (PTR, ir_type, name)
            self.module.add_global_line(f"@{name} = global {ir_type} 0")
            return

        if isinstance(value, ast.StringLiteral):
            gs = GlobalString(value.value)
            self.module.add_global_string(gs)
            self.module.add_global_line(f"@{name}_data = global ptr @{gs.name}")
            self.module.add_global_line(f"@{name}_len = global i64 {gs.length}")
            self.globals[name] = ("string", ir_type, name)
            self.const_values[name] = value.value
            return

        init_val = self._eval_const_expr(value)
        s_val = str(init_val)
        if isinstance(init_val, float):
            import struct
            s_val = f"0x{struct.pack('>d', init_val).hex()}"
        self.globals[name] = (PTR, ir_type, name)
        self.const_values[name] = init_val
        self.module.add_global_line(f"@{name} = global {ir_type} {s_val}")

    def _eval_const_expr(self, expr):
        if isinstance(expr, ast.IntLiteral):
            return expr.value
        elif isinstance(expr, ast.FloatLiteral):
            return expr.value
        elif isinstance(expr, ast.StringLiteral):
            return expr.value
        elif isinstance(expr, ast.BoolLiteral):
            return 1 if expr.value else 0
        elif isinstance(expr, ast.CharLiteral):
            return ord(expr.value)
        elif isinstance(expr, ast.BinaryOp):
            left = self._eval_const_expr(expr.left)
            right = self._eval_const_expr(expr.right)
            if isinstance(left, str) or isinstance(right, str):
                return "0"
            if isinstance(left, float) or isinstance(right, float):
                if expr.op == "+":
                    return float(left) + float(right)
                elif expr.op == "-":
                    return float(left) - float(right)
                elif expr.op == "*":
                    return float(left) * float(right)
                elif expr.op == "/":
                    return float(left) / float(right)
                return float(left) + float(right)
            else:
                if expr.op == "+":
                    return int(left) + int(right)
                elif expr.op == "-":
                    return int(left) - int(right)
                elif expr.op == "*":
                    return int(left) * int(right)
                elif expr.op == "/":
                    return int(left) // int(right)
                elif expr.op == "%":
                    return int(left) % int(right)
                return int(left) + int(right)
        elif isinstance(expr, ast.Identifier):
            if expr.name in self.const_values:
                return self.const_values[expr.name]
            return 0
        return 0

    def _zinc_type_to_ir(self, type_node):
        if isinstance(type_node, ast.TypeNode):
            name = type_node.name
            if name == "int":
                return I64
            elif name == "int32":
                return I32
            elif name == "int16":
                return I16
            elif name == "int8":
                return I8
            elif name == "int4":
                return I4
            elif name == "uint":
                return I64
            elif name == "uint32":
                return I32
            elif name == "uint16":
                return I16
            elif name == "uint8":
                return I8
            elif name == "uint4":
                return I4
            elif name == "float":
                return DOUBLE
            elif name == "float32":
                return FLOAT
            elif name == "bool":
                return I8
            elif name == "char":
                return I8
            elif name == "string":
                return STRING_TYPE
            elif name == "void":
                return VOID
            elif name == "file":
                return PTR
            return PTR
        elif isinstance(type_node, ast.ArrayTypeNode):
            return VECTOR_TYPE
        elif isinstance(type_node, ast.MapTypeNode):
            return PTR
        elif isinstance(type_node, ast.NamedTypeNode):
            if type_node.name in self.enums:
                return I32
            if type_node.name in self.structs:
                return self._struct_ir_type(type_node.name)
            known_types = {
                "int": I64, "uint": I64, "int32": I32, "uint32": I32,
                "int16": I16, "uint16": I16, "int8": I8, "uint8": I8,
                "int4": I4, "uint4": I4,
                "float": DOUBLE, "float32": FLOAT,
                "bool": I8, "char": I8, "void": VOID,
                "string": STRING_TYPE, "file": PTR, "ptr": PTR,
            }
            if type_node.name in known_types:
                return known_types[type_node.name]
            return PTR
        elif isinstance(type_node, ast.RefTypeNode):
            return PTR
        elif isinstance(type_node, ast.FuncTypeNode):
            return PTR
        return PTR

    def _zinc_type_to_str(self, type_node):
        if isinstance(type_node, ast.TypeNode):
            return type_node.name
        elif isinstance(type_node, ast.ArrayTypeNode):
            return "array"
        elif isinstance(type_node, ast.MapTypeNode):
            return "map"
        elif isinstance(type_node, ast.NamedTypeNode):
            return type_node.name
        elif isinstance(type_node, ast.RefTypeNode):
            return "ref"
        elif isinstance(type_node, ast.FuncTypeNode):
            return "function"
        return "unknown"

    def _ir_type_to_str(self, ir_t):
        s = str(ir_t)
        if ir_t == STRING_TYPE:
            return "string"
        if ir_t == VECTOR_TYPE:
            return "array"
        mapping = {
            "i64": "int", "i32": "int32", "i16": "int16", "i8": "int8", "i4": "int4",
            "double": "float", "float": "float32",
            "ptr": "ptr", "void": "void",
        }
        return mapping.get(s)

    def _elem_size_from_ir(self, ir_t):
        s = str(ir_t)
        if s.startswith("%"):
            name = s[1:]
            decl = self.structs.get(name)
            if decl:
                return sum(self._elem_size_from_ir(self._zinc_type_to_ir(f.type_node)) for f in decl.fields)
            return 8
        if s.startswith("{"):
            nfields = s.count(",") + 1
            has_small = any(t in s for t in ("i8", "i1", "i4"))
            if has_small:
                return nfields
            return nfields * 8
        bit_widths = {"i64": 8, "i32": 4, "i16": 2, "i8": 1, "i4": 1, "i1": 1, "double": 8, "float": 4, "ptr": 8}
        for k, v in bit_widths.items():
            if k in s:
                return v
        return 8

    def _compile_struct_type(self, decl, name_override=None):
        name = name_override or decl.name
        if name not in self.structs:
            self.structs[name] = decl

    def _struct_ir_type(self, name):
        decl = self.structs.get(name)
        if not decl:
            return PTR
        if name in self.struct_types_added:
            return named_struct_type(name)
        self.struct_types_added.add(name)
        member_types = [self._zinc_type_to_ir(f.type_node) for f in decl.fields]
        struct_def = literal_struct_type(member_types)
        nt = named_struct_type(name)
        self.module.add_type(IRType(f"%{name} = type {struct_def}"))
        return nt

    def _compile_function(self, decl, name_override=None):
        func_name = name_override or decl.name
        is_main = (func_name == "main")

        if is_main:
            ret_ir = I32
        else:
            ret_types = decl.return_types
            if len(ret_types) == 1:
                ret_ir = self._zinc_type_to_ir(ret_types[0])
            elif len(ret_types) > 1:
                member_types = [self._zinc_type_to_ir(t) for t in ret_types]
                ret_ir = literal_struct_type(member_types)
            else:
                ret_ir = VOID

        has_main_args = is_main and len(decl.params) > 0
        param_irs = []
        param_names = []
        for p in decl.params:
            param_names.append(p.name)
        if has_main_args:
            param_irs = [I32, PTR]
        else:
            for p in decl.params:
                param_irs.append(self._zinc_type_to_ir(p.type_node))

        func = FunctionIR(func_name, ret_ir, param_irs, param_names)
        self.module.add_function(func)
        self.current_func = func
        entry = func.new_block("entry")
        self.current_block = entry
        self.defer_stmts = []

        old_sym = self.symbols.copy()
        self.symbols = {}

        if has_main_args:
            p0_alloca = emit_alloca(entry, I64, None)
            p0_val = IRValue(I32, f"%{decl.params[0].name}")
            p0_ext = emit_zext(entry, p0_val, I64)
            emit_store(entry, p0_ext, p0_alloca)
            self.symbols[decl.params[0].name] = (p0_alloca, I64)
            self.var_types[decl.params[0].name] = self._zinc_type_to_str(decl.params[0].type_node)
            self.var_type_nodes[decl.params[0].name] = decl.params[0].type_node

            p1_val = IRValue(PTR, f"%{decl.params[1].name}")
            vec = emit_call(entry, "__zn_argv_to_vector", [p1_val], VECTOR_TYPE)
            p1_alloca = emit_alloca(entry, VECTOR_TYPE, None)
            emit_store(entry, vec, p1_alloca)
            self.symbols[decl.params[1].name] = (p1_alloca, VECTOR_TYPE)
            self.var_types[decl.params[1].name] = self._zinc_type_to_str(decl.params[1].type_node)
            self.var_type_nodes[decl.params[1].name] = decl.params[1].type_node
        else:
            for i, p in enumerate(decl.params):
                p_ir = param_irs[i]
                alloca = emit_alloca(entry, p_ir, None)
                param_val = IRValue(p_ir, f"%{p.name}")
                emit_store(entry, param_val, alloca)
                self.symbols[p.name] = (alloca, p_ir)
                self.var_types[p.name] = self._zinc_type_to_str(p.type_node)
                self.var_type_nodes[p.name] = p.type_node

        if is_main:
            emit_call(entry, "GC_init", [], VOID)

        for stmt in decl.body.statements:
            self._compile_stmt(stmt)

        if self.current_block and self.current_block.terminator is None:
            if is_main:
                emit_ret(self.current_block, const_int(0, 32))
            elif len(ret_types) == 1 and str(ret_ir) != "void":
                default_val = self._default_value(ret_types[0])
                emit_ret(self.current_block, default_val)
            elif len(ret_types) > 1:
                emit_ret(self.current_block, Constant(ret_ir, "zeroinitializer"))
            else:
                emit_ret(self.current_block)

        self.symbols = old_sym
        self.current_func = None
        self.current_block = None

    def _default_value(self, type_node):
        ir_t = self._zinc_type_to_ir(type_node)
        return self._default_value_by_ir(ir_t)

    def _compile_stmt(self, stmt):
        if stmt is None:
            return

        if isinstance(stmt, ast.Block):
            for s in stmt.statements:
                self._compile_stmt(s)

        elif isinstance(stmt, ast.ExprStmt):
            self._compile_expr(stmt.expr)

        elif isinstance(stmt, ast.VarDecl):
            ir_type = self._zinc_type_to_ir(stmt.type_node)
            alloca = emit_alloca(self.current_block, ir_type, None)
            self.symbols[stmt.name] = (alloca, ir_type)
            self.var_types[stmt.name] = self._zinc_type_to_str(stmt.type_node)
            self.var_type_nodes[stmt.name] = stmt.type_node
            if stmt.value:
                val = self._compile_expr(stmt.value)
                val = self._cast_if_needed(val, ir_type)
                emit_store(self.current_block, val, alloca)

        elif isinstance(stmt, ast.MultiVarDecl):
            val = self._compile_expr(stmt.value)
            for i, name in enumerate(stmt.var_names):
                ir_type = self._zinc_type_to_ir(stmt.types[i])
                alloca = emit_alloca(self.current_block, ir_type, name)
                self.symbols[name] = (alloca, ir_type)
                self.var_types[name] = self._zinc_type_to_str(stmt.types[i])
                self.var_type_nodes[name] = stmt.types[i]
                if len(stmt.var_names) > 1:
                    field_val = emit_extractvalue(self.current_block, val, i, ir_type)
                    cast_val = self._cast_if_needed(field_val, ir_type)
                    emit_store(self.current_block, cast_val, alloca)
                else:
                    cast_val = self._cast_if_needed(val, ir_type)
                    emit_store(self.current_block, cast_val, alloca)

        elif isinstance(stmt, ast.AssignStmt):
            val = self._compile_expr(stmt.value)
            for target in stmt.targets:
                self._compile_assign_target(target, val)

        elif isinstance(stmt, ast.MultiAssignStmt):
            val = self._compile_expr(stmt.value)
            for i, target in enumerate(stmt.targets):
                if isinstance(target, ast.Identifier):
                    name = target.name
                    if name in self.symbols:
                        alloca, ir_type = self.symbols[name]
                        if len(stmt.targets) > 1:
                            field_val = emit_extractvalue(self.current_block, val, i, ir_type)
                            cast_val = self._cast_if_needed(field_val, ir_type)
                        else:
                            cast_val = self._cast_if_needed(val, ir_type)
                        emit_store(self.current_block, cast_val, alloca)

        elif isinstance(stmt, ast.IfStmt):
            self._compile_if(stmt)

        elif isinstance(stmt, ast.ForStmt):
            self._compile_for(stmt)

        elif isinstance(stmt, ast.ForInStmt):
            self._compile_for_in(stmt)

        elif isinstance(stmt, ast.WhileStmt):
            self._compile_while(stmt)

        elif isinstance(stmt, ast.ReturnStmt):
            self._compile_return(stmt)

        elif isinstance(stmt, ast.BreakStmt):
            if self.break_blocks:
                br_block = self.break_blocks[-1]
                emit_br(self.current_block, br_block)

        elif isinstance(stmt, ast.ContinueStmt):
            if self.continue_blocks:
                cont_block = self.continue_blocks[-1]
                emit_br(self.current_block, cont_block)

        elif isinstance(stmt, ast.DeferStmt):
            self.defer_stmts.append(stmt.statement)

        elif isinstance(stmt, ast.MatchStmt):
            self._compile_match(stmt)

        elif isinstance(stmt, ast.DelStmt):
            if isinstance(stmt.expr, ast.IndexExpr):
                idx_expr = stmt.expr
                if isinstance(idx_expr.obj, ast.Identifier) and idx_expr.obj.name in self.var_type_nodes:
                    tn = self.var_type_nodes[idx_expr.obj.name]
                    if isinstance(tn, ast.MapTypeNode):
                        alloca_n, _ = self.symbols[idx_expr.obj.name]
                        map_handle = emit_load(self.current_block, alloca_n, PTR)
                        idx = self._compile_expr(idx_expr.index)
                        key_ptr = emit_extractvalue(self.current_block, idx, 0, PTR)
                        key_len = emit_extractvalue(self.current_block, idx, 1, I64)
                        emit_call(self.current_block, "__zn_map_delete", [map_handle, key_ptr, key_len], VOID)
                        return
            pass

        elif isinstance(stmt, ast.RaiseStmt):
            val = self._compile_expr(stmt.expr)
            emit_call(self.current_block, "__zn_abort", [val], VOID)
            emit_unreachable(self.current_block)
            self.current_block = self.current_func.new_block("after.raise")

        elif isinstance(stmt, ast.FunctionDecl):
            self._compile_function(stmt)

        elif isinstance(stmt, ast.StructDecl):
            self._compile_struct_type(stmt)

        elif isinstance(stmt, ast.EnumDecl):
            pass

        elif isinstance(stmt, ast.ConstDecl):
            ir_type = self._zinc_type_to_ir(stmt.type_node) if stmt.type_node else I64
            alloca = emit_alloca(self.current_block, ir_type, stmt.name)
            self.symbols[stmt.name] = (alloca, ir_type)
            if stmt.value:
                val = self._compile_expr(stmt.value)
                val = self._cast_if_needed(val, ir_type)
                emit_store(self.current_block, val, alloca)

        elif isinstance(stmt, ast.ImportDecl):
            pass

        elif isinstance(stmt, ast.ExternBlock):
            pass

    def _compile_if(self, stmt):
        cond_val = self._compile_expr(stmt.condition)
        cond_val = self._ensure_i1(cond_val)

        then_bb = self.current_func.new_block("if.then")
        else_bb = self.current_func.new_block("if.else")
        merge_bb = self.current_func.new_block("if.merge")

        emit_cond_br(self.current_block, cond_val, then_bb, else_bb)

        self.current_block = then_bb
        for s in stmt.then_block.statements:
            self._compile_stmt(s)
        self._br_if_needed(merge_bb)

        self.current_block = else_bb
        if stmt.elifs:
            self._compile_elif_chain(stmt.elifs, merge_bb)
        if stmt.else_block:
            for s in stmt.else_block.statements:
                self._compile_stmt(s)
            self._br_if_needed(merge_bb)
        else:
            self._br_if_needed(merge_bb)

        self.current_block = merge_bb

    def _compile_elif_chain(self, elifs, merge_bb):
        for i, el in enumerate(elifs):
            cond_val = self._compile_expr(el.condition)
            cond_val = self._ensure_i1(cond_val)

            then_bb = self.current_func.new_block(f"elif{i}.then")
            else_bb = self.current_func.new_block(f"elif{i}.else")
            emit_cond_br(self.current_block, cond_val, then_bb, else_bb)

            self.current_block = then_bb
            for s in el.block.statements:
                self._compile_stmt(s)
            self._br_if_needed(merge_bb)

            self.current_block = else_bb

    def _ensure_i1(self, val):
        s = str(val.ir_type)
        if s == "i8":
            return self._i8_to_i1(val)
        elif s != "i1":
            return emit_icmp(self.current_block, "!=", val, self._default_value_by_ir(val.ir_type), val.ir_type)
        return val

    def _br_if_needed(self, target_block):
        if self.current_block and self.current_block.terminator is None:
            emit_br(self.current_block, target_block)

    def _compile_for(self, stmt):
        self.loop_exit_blocks.append(None)
        cond_bb = self.current_func.new_block("for.cond")
        body_bb = self.current_func.new_block("for.body")
        exit_bb = self.current_func.new_block("for.exit")
        inc_bb = self.current_func.new_block("for.inc")

        self.loop_exit_blocks[-1] = exit_bb
        self.break_blocks.append(exit_bb)
        self.continue_blocks.append(inc_bb)

        if stmt.init:
            self._compile_stmt(stmt.init)

        emit_br(self.current_block, cond_bb)

        self.current_block = cond_bb
        if stmt.condition:
            cond_val = self._compile_expr(stmt.condition)
            if str(cond_val.ir_type) == "i8":
                cond_val = self._i8_to_i1(cond_val)
            elif str(cond_val.ir_type) != "i1":
                test = emit_icmp(self.current_block, "!=", cond_val, self._default_value_by_ir(cond_val.ir_type), cond_val.ir_type)
                cond_val = test
            emit_cond_br(self.current_block, cond_val, body_bb, exit_bb)
        else:
            emit_br(self.current_block, body_bb)

        self.current_block = body_bb
        for s in stmt.body.statements:
            self._compile_stmt(s)
        if self.current_block.terminator is None:
            emit_br(self.current_block, inc_bb)

        self.current_block = inc_bb
        if stmt.increment:
            if isinstance(stmt.increment, ast.AssignStmt) or isinstance(stmt.increment, ast.ExprStmt):
                self._compile_stmt(stmt.increment)
            else:
                self._compile_expr(stmt.increment)
        if self.current_block.terminator is None:
            emit_br(self.current_block, cond_bb)

        self.current_block = exit_bb
        self.loop_exit_blocks.pop()
        self.break_blocks.pop()
        self.continue_blocks.pop()

    def _compile_for_in(self, stmt):
        iterable = self._compile_expr(stmt.iterable)
        iter_type = iterable.ir_type

        exit_bb = self.current_func.new_block("forin.exit")
        cond_bb = self.current_func.new_block("forin.cond")
        body_bb = self.current_func.new_block("forin.body")
        inc_bb = self.current_func.new_block("forin.inc")

        self.break_blocks.append(exit_bb)
        self.continue_blocks.append(inc_bb)

        s = str(iter_type)
        suffix = str(self._uid_counter)
        self._uid_counter += 1
        if "i64, i64}" in s:
            # Vector iteration: for (n in nums) { println(n) }
            temp_alloca = emit_alloca(self.current_block, iter_type, None)
            emit_store(self.current_block, iterable, temp_alloca)

            idx_alloca = emit_alloca(self.current_block, I64, f"{stmt.var_name}_idx{suffix}")
            emit_store(self.current_block, const_int(0, 64), idx_alloca)

            data_ptr_gep = emit_gep(self.current_block, iter_type, temp_alloca, [const_int(0, 32), const_int(0, 32)])
            data_ptr = emit_load(self.current_block, data_ptr_gep, PTR)
            len_gep = emit_gep(self.current_block, iter_type, temp_alloca, [const_int(0, 32), const_int(1, 32)])
            length_val = emit_load(self.current_block, len_gep, I64)
            len_alloca = emit_alloca(self.current_block, I64, f"{stmt.var_name}_len{suffix}")
            emit_store(self.current_block, length_val, len_alloca)

            emit_br(self.current_block, cond_bb)

            self.current_block = cond_bb
            idx = emit_load(self.current_block, idx_alloca, I64)
            length = emit_load(self.current_block, len_alloca, I64)
            cmp = emit_icmp(self.current_block, "<", idx, length, I64)
            emit_cond_br(self.current_block, cmp, body_bb, exit_bb)

            self.current_block = body_bb
            idx_v = emit_load(self.current_block, idx_alloca, I64)
            elem_ptr = emit_gep(self.current_block, I64, data_ptr, [idx_v])
            elem_val = emit_load(self.current_block, elem_ptr, I64)

            elem_alloca = emit_alloca(self.current_block, I64, f"{stmt.var_name}{suffix}")
            emit_store(self.current_block, elem_val, elem_alloca)
            self.symbols[stmt.var_name] = (elem_alloca, I64)

            for s2 in stmt.body.statements:
                self._compile_stmt(s2)
            if self.current_block.terminator is None:
                emit_br(self.current_block, inc_bb)

            self.current_block = inc_bb
            idx_v2 = emit_load(self.current_block, idx_alloca, I64)
            new_idx = emit_binop(self.current_block, "+", idx_v2, const_int(1, 64), I64)
            emit_store(self.current_block, new_idx, idx_alloca)
            if self.current_block.terminator is None:
                emit_br(self.current_block, cond_bb)
        elif "i64}" in s:
            # String iteration: for (c in str) { println(c) }
            temp_alloca = emit_alloca(self.current_block, iter_type, None)
            emit_store(self.current_block, iterable, temp_alloca)

            idx_alloca = emit_alloca(self.current_block, I64, f"{stmt.var_name}_idx{suffix}")
            emit_store(self.current_block, const_int(0, 64), idx_alloca)

            data_ptr_gep = emit_gep(self.current_block, iter_type, temp_alloca, [const_int(0, 32), const_int(0, 32)])
            data_ptr = emit_load(self.current_block, data_ptr_gep, PTR)
            len_gep = emit_gep(self.current_block, iter_type, temp_alloca, [const_int(0, 32), const_int(1, 32)])
            length_val = emit_load(self.current_block, len_gep, I64)
            len_alloca = emit_alloca(self.current_block, I64, f"{stmt.var_name}_len{suffix}")
            emit_store(self.current_block, length_val, len_alloca)

            emit_br(self.current_block, cond_bb)

            self.current_block = cond_bb
            idx = emit_load(self.current_block, idx_alloca, I64)
            length = emit_load(self.current_block, len_alloca, I64)
            cmp = emit_icmp(self.current_block, "<", idx, length, I64)
            emit_cond_br(self.current_block, cmp, body_bb, exit_bb)

            self.current_block = body_bb
            idx_v = emit_load(self.current_block, idx_alloca, I64)
            elem_ptr = emit_gep(self.current_block, I8, data_ptr, [idx_v])
            char_val = emit_load(self.current_block, elem_ptr, I8)

            elem_alloca = emit_alloca(self.current_block, I8, f"{stmt.var_name}{suffix}")
            emit_store(self.current_block, char_val, elem_alloca)
            self.symbols[stmt.var_name] = (elem_alloca, I8)

            for s2 in stmt.body.statements:
                self._compile_stmt(s2)
            if self.current_block.terminator is None:
                emit_br(self.current_block, inc_bb)

            self.current_block = inc_bb
            idx_v2 = emit_load(self.current_block, idx_alloca, I64)
            new_idx = emit_binop(self.current_block, "+", idx_v2, const_int(1, 64), I64)
            emit_store(self.current_block, new_idx, idx_alloca)
            if self.current_block.terminator is None:
                emit_br(self.current_block, cond_bb)
        else:
            emit_br(self.current_block, body_bb)
            emit_unreachable(inc_bb)
            self.current_block = body_bb
            for s2 in stmt.body.statements:
                self._compile_stmt(s2)
            if self.current_block.terminator is None:
                emit_br(self.current_block, cond_bb)
            self.current_block = cond_bb
            emit_br(self.current_block, body_bb)
            self.current_block = exit_bb
            emit_unreachable(self.current_block)

        self.current_block = exit_bb
        self.break_blocks.pop()
        self.continue_blocks.pop()

    def _compile_while(self, stmt):
        cond_bb = self.current_func.new_block("while.cond")
        body_bb = self.current_func.new_block("while.body")
        exit_bb = self.current_func.new_block("while.exit")

        self.break_blocks.append(exit_bb)
        self.continue_blocks.append(cond_bb)

        emit_br(self.current_block, cond_bb)

        self.current_block = cond_bb
        cond_val = self._compile_expr(stmt.condition)
        if str(cond_val.ir_type) == "i8":
            cond_val = self._i8_to_i1(cond_val)
        elif str(cond_val.ir_type) != "i1":
            test = emit_icmp(self.current_block, "!=", cond_val, self._default_value_by_ir(cond_val.ir_type), cond_val.ir_type)
            cond_val = test
        emit_cond_br(self.current_block, cond_val, body_bb, exit_bb)

        self.current_block = body_bb
        for s in stmt.body.statements:
            self._compile_stmt(s)
        if self.current_block.terminator is None:
            emit_br(self.current_block, cond_bb)

        self.current_block = exit_bb
        self.break_blocks.pop()
        self.continue_blocks.pop()

    def _compile_match(self, stmt):
        expr_val = self._compile_expr(stmt.expr)
        merge_bb = self.current_func.new_block("match.merge")
        cases = list(stmt.cases)

        switch_val = expr_val
        if str(expr_val.ir_type) == "i8":
            switch_val = emit_zext(self.current_block, expr_val, I32)

        cond_bbs = []
        for i, case in enumerate(cases):
            cond_bbs.append(self.current_func.new_block(f"match.cond{i}"))

        body_bbs = []
        for i, case in enumerate(cases):
            body_bbs.append(self.current_func.new_block(f"match.body{i}"))

        if stmt.default_block:
            default_bb = self.current_func.new_block("match.defaultbody")
        else:
            default_bb = merge_bb

        emit_br(self.current_block, cond_bbs[0])

        for i, (case, cond_bb, body_bb) in enumerate(zip(cases, cond_bbs, body_bbs)):
            self.current_block = cond_bb
            pat_val = self._compile_expr(case.pattern)
            cmp = emit_icmp(self.current_block, "==", switch_val, pat_val, switch_val.ir_type)
            next_bb = cond_bbs[i + 1] if i < len(cases) - 1 else default_bb
            emit_cond_br(self.current_block, cmp, body_bb, next_bb)

        for i, (case, body_bb) in enumerate(zip(cases, body_bbs)):
            self.current_block = body_bb
            for s in case.block.statements:
                self._compile_stmt(s)
            self._br_if_needed(merge_bb)

        if stmt.default_block:
            self.current_block = default_bb
            for s in stmt.default_block.statements:
                self._compile_stmt(s)
            self._br_if_needed(merge_bb)

        self.current_block = merge_bb

    def _compile_return(self, stmt):
        ret_type = self.current_func.ret_type
        is_void = str(ret_type) == "void"
        if is_void and stmt.values:
            raise CompilerError("Cannot return a value from a void function")
        if not stmt.values or is_void:
            emit_ret(self.current_block)
        elif len(stmt.values) == 1:
            v = self._compile_expr(stmt.values[0])
            emit_ret(self.current_block, v)
        else:
            alloca = emit_alloca(self.current_block, ret_type, None)
            for i, val in enumerate(stmt.values):
                v = self._compile_expr(val)
                field_ptr = emit_gep(self.current_block, ret_type, alloca, [const_int(0, 32), const_int(i, 32)])
                emit_store(self.current_block, v, field_ptr)
            struct_val = emit_load(self.current_block, alloca, ret_type)
            emit_ret(self.current_block, struct_val)

    def _compile_assign_target(self, target, value):
        if isinstance(target, ast.Identifier):
            name = target.name
            if name in self.symbols:
                alloca, ir_type = self.symbols[name]
                cast_val = self._cast_if_needed(value, ir_type)
                emit_store(self.current_block, cast_val, alloca)
            else:
                ir_type = value.ir_type
                alloca = emit_alloca(self.current_block, ir_type, name)
                self.symbols[name] = (alloca, ir_type)
                emit_store(self.current_block, value, alloca)
                type_str = self._ir_type_to_str(ir_type)
                if type_str:
                    self.var_types[name] = type_str
                    self.var_type_nodes[name] = ast.TypeNode(type_str)

        elif isinstance(target, ast.IndexExpr):
            idx = self._compile_expr(target.index)
            is_map = False
            if isinstance(target.obj, ast.Identifier) and target.obj.name in self.var_type_nodes:
                tn = self.var_type_nodes[target.obj.name]
                is_map = isinstance(tn, ast.MapTypeNode)
            if is_map:
                alloca, _ = self.symbols[target.obj.name]
                map_handle = emit_load(self.current_block, alloca, PTR)
                key_ptr = emit_extractvalue(self.current_block, idx, 0, PTR)
                key_len = emit_extractvalue(self.current_block, idx, 1, I64)
                val_alloca = self._emit_value_for_map_set(value)
                val_type_str = self._zinc_type_to_str(tn.value_type)
                val_size = 8 if val_type_str in ("int", "uint64", "bool") else 16
                emit_call(self.current_block, "__zn_map_set_value", [map_handle, key_ptr, key_len, val_alloca, const_int(val_size, 64)], VOID)
            else:
                elem_ir = I64
                if isinstance(target.obj, ast.Identifier) and target.obj.name in self.symbols:
                    ptr, _ = self.symbols[target.obj.name]
                    if target.obj.name in self.var_type_nodes:
                        tn = self.var_type_nodes[target.obj.name]
                        if isinstance(tn, ast.ArrayTypeNode):
                            elem_ir = self._zinc_type_to_ir(tn.element_type)
                    self._emit_array_set_by_ptr(ptr, idx, value, elem_ir)
                else:
                    obj = self._compile_expr(target.obj)
                    temp_alloca = emit_alloca(self.current_block, obj.ir_type, None)
                    emit_store(self.current_block, obj, temp_alloca)
                    self._emit_array_set_by_ptr(temp_alloca, idx, value, I64)

        elif isinstance(target, ast.MemberExpr):
            if isinstance(target.obj, ast.Identifier) and target.obj.name in self.symbols:
                alloca, ir_type = self.symbols[target.obj.name]
                self._emit_struct_field_set_by_ptr(alloca, ir_type, target.member, value)
            else:
                obj = self._compile_expr(target.obj)
                self._emit_struct_field_set(obj, target.member, value)

    def _compile_expr(self, expr):
        if isinstance(expr, ast.IntLiteral):
            return const_int(expr.value, 64)

        elif isinstance(expr, ast.FloatLiteral):
            return const_double(expr.value)

        elif isinstance(expr, ast.StringLiteral):
            return self._emit_string_constant(expr.value)

        elif isinstance(expr, ast.CharLiteral):
            return const_int(ord(expr.value), 8)

        elif isinstance(expr, ast.BoolLiteral):
            return const_int(1 if expr.value else 0, 8)

        elif isinstance(expr, ast.Identifier):
            name = expr.name
            if name in self.symbols:
                alloca, ir_type = self.symbols[name]
                return emit_load(self.current_block, alloca, ir_type)
            if name in self.globals:
                gtype, ir_type, gname = self.globals[name]
                if gtype == "string":
                    data_ptr = Constant(PTR, f"@{name}_data")
                    len_ptr = Constant(PTR, f"@{name}_len")
                    data = emit_load(self.current_block, data_ptr, PTR)
                    length = emit_load(self.current_block, len_ptr, I64)
                    str_alloca = emit_alloca(self.current_block, STRING_TYPE)
                    data_gep = emit_gep(self.current_block, STRING_TYPE, str_alloca, [const_int(0, 32), const_int(0, 32)])
                    emit_store(self.current_block, data, data_gep)
                    len_gep = emit_gep(self.current_block, STRING_TYPE, str_alloca, [const_int(0, 32), const_int(1, 32)])
                    emit_store(self.current_block, length, len_gep)
                    return emit_load(self.current_block, str_alloca, STRING_TYPE)
                global_ptr = Constant(PTR, f"@{gname}")
                return emit_load(self.current_block, global_ptr, ir_type)
            for ename, edecl in self.enums.items():
                if name.startswith(f"{ename}."):
                    parts = name.split(".")
                    if len(parts) == 2:
                        for j, v in enumerate(edecl.variants):
                            if v == parts[1]:
                                return const_int(j, 32)
            if name in self.functions:
                return Constant(PTR, f"@{name}")
            if name in self.extern_funcs:
                _, c_name, _ = self.extern_funcs[name]
                return Constant(PTR, f"@{c_name}")
            mod = getattr(self, 'current_module', None)
            if mod:
                mod_name = f"{mod}.{name}"
                if mod_name in self.functions:
                    return Constant(PTR, f"@{mod_name}")
                if mod_name in self.extern_funcs:
                    _, c_name, _ = self.extern_funcs[mod_name]
                    return Constant(PTR, f"@{c_name}")
                if mod_name in self.globals:
                    gtype, ir_type, gname = self.globals[mod_name]
                    global_ptr = Constant(PTR, f"@{mod_name}")
                    if ir_type is None:
                        return global_ptr
                    return emit_load(self.current_block, global_ptr, ir_type)
            return const_int(0, 64)

        elif isinstance(expr, ast.BinaryOp):
            return self._compile_binary(expr)

        elif isinstance(expr, ast.UnaryOp):
            return self._compile_unary(expr)

        elif isinstance(expr, ast.CallExpr):
            return self._compile_call(expr)

        elif isinstance(expr, ast.MethodCallExpr):
            return self._compile_method_call(expr)

        elif isinstance(expr, ast.IndexExpr):
            obj = self._compile_expr(expr.obj)
            idx = self._compile_expr(expr.index)
            if isinstance(expr.obj, ast.Identifier) and expr.obj.name in self.var_type_nodes:
                tn = self.var_type_nodes[expr.obj.name]
                if isinstance(tn, ast.MapTypeNode):
                    alloca_n, _ = self.symbols[expr.obj.name]
                    map_handle = emit_load(self.current_block, alloca_n, PTR)
                    key_ptr = emit_extractvalue(self.current_block, idx, 0, PTR)
                    key_len = emit_extractvalue(self.current_block, idx, 1, I64)
                    val_type = tn.value_type
                    val_ir = self._zinc_type_to_ir(val_type)
                    val_alloca = emit_alloca(self.current_block, val_ir, None)
                    emit_call(self.current_block, "__zn_map_get_value", [map_handle, key_ptr, key_len, val_alloca], I8)
                    return emit_load(self.current_block, val_alloca, val_ir)
            return self._emit_array_get(obj, idx, expr)

        elif isinstance(expr, ast.SliceExpr):
            obj = self._compile_expr(expr.obj)
            start = self._compile_expr(expr.start) if expr.start else const_int(0, 64)
            end = self._compile_expr(expr.end) if expr.end else None
            return self._emit_slice(obj, start, end)

        elif isinstance(expr, ast.MemberExpr):
            if isinstance(expr.obj, ast.Identifier) and expr.obj.name in self.imported_modules:
                module_name = expr.obj.name
                member_name = expr.member
                if self._is_private(member_name):
                    raise CompilerError(f"'{module_name}.{member_name}' is private")
                full_name = f"{module_name}.{member_name}"
                if full_name in self.functions:
                    return Constant(PTR, f"@{full_name}")
                if full_name in self.extern_funcs:
                    _, c_name, _ = self.extern_funcs[full_name]
                    return Constant(PTR, f"@{c_name}")
                if full_name in self.const_values:
                    val = self.const_values[full_name]
                    if isinstance(val, float):
                        return const_double(val)
                    return const_int(val, 64)
                if full_name in self.globals:
                    gtype, ir_type, gname = self.globals[full_name]
                    global_ptr = Constant(PTR, f"@{full_name}")
                    if ir_type is None:
                        return global_ptr
                    return emit_load(self.current_block, global_ptr, ir_type)
                if full_name in self.enums:
                    return const_int(0, 32)
                return const_int(0, 64)
            obj = self._compile_expr(expr.obj)
            return self._emit_struct_field_get(obj, expr.member)

        elif isinstance(expr, ast.StructLiteral):
            return self._compile_struct_literal(expr)

        elif isinstance(expr, ast.ArrayLiteral):
            return self._compile_array_literal(expr)

        elif isinstance(expr, ast.MapLiteral):
            return self._compile_map_literal(expr)

        elif isinstance(expr, ast.ParenExpr):
            return self._compile_expr(expr.expr)

        elif isinstance(expr, ast.InExpr):
            return self._compile_in_expr(expr)

        elif isinstance(expr, ast.MultiValueExpr):
            pass

        return const_int(0, 64)

    def _compile_binary(self, expr):
        left = self._compile_expr(expr.left)
        right = self._compile_expr(expr.right)
        op = expr.op

        left_s = str(left.ir_type)
        right_s = str(right.ir_type)

        if op == "and":
            if str(left.ir_type) == "i8":
                left = self._i8_to_i1(left)
            if str(right.ir_type) == "i8":
                right = self._i8_to_i1(right)
            result = emit_binop(self.current_block, "and", left, right, I1)
            return emit_zext(self.current_block, result, I8)

        if op == "or":
            if str(left.ir_type) == "i8":
                left = self._i8_to_i1(left)
            if str(right.ir_type) == "i8":
                right = self._i8_to_i1(right)
            result = emit_binop(self.current_block, "or", left, right, I1)
            return emit_zext(self.current_block, result, I8)

        if op == "+":
            if "}" in left_s and right_s in ("i8", "i32", "i64"):
                right = emit_call(self.current_block, "__zn_string_from_char", [right], STRING_TYPE)
                return emit_call(self.current_block, "__zn_string_concat", [left, right], STRING_TYPE)
            if left_s in ("i8", "i32", "i64") and "}" in right_s:
                left = emit_call(self.current_block, "__zn_string_from_char", [left], STRING_TYPE)
                return emit_call(self.current_block, "__zn_string_concat", [left, right], STRING_TYPE)
            if "}" in left_s or "}" in right_s:
                return emit_call(self.current_block, "__zn_string_concat", [left, right], STRING_TYPE)

        if op in ("==", "!=", "<", ">", "<=", ">="):
            if "double" in left_s or "float" in left_s:
                cmp = emit_fcmp(self.current_block, op, left, right, left.ir_type)
            else:
                if str(left.ir_type) != str(right.ir_type):
                    right = self._cast_if_needed(right, left.ir_type)
                cmp = emit_icmp(self.current_block, op, left, right, left.ir_type)
            return emit_zext(self.current_block, cmp, I8)

        if "double" in left_s or "float" in left_s:
            return emit_binop(self.current_block, op, left, right, left.ir_type)

        if str(left.ir_type) != str(right.ir_type):
            right = self._cast_if_needed(right, left.ir_type)

        return emit_binop(self.current_block, op, left, right, left.ir_type)

    def _compile_unary(self, expr):
        operand = self._compile_expr(expr.operand)
        if expr.op == "-":
            zero = self._default_value_by_ir(operand.ir_type)
            return emit_binop(self.current_block, "-", zero, operand, operand.ir_type)
        elif expr.op == "not":
            if str(operand.ir_type) == "i8":
                i1_val = self._i8_to_i1(operand)
                not_val = emit_binop(self.current_block, "xor", i1_val, const_bool(True), I1)
                return emit_zext(self.current_block, not_val, I8)
            return emit_binop(self.current_block, "xor", operand, const_bool(True), operand.ir_type)
        return operand

    def _compile_call(self, expr):
        callee_name = None
        module_name = None
        member_name = None
        if isinstance(expr.callee, ast.Identifier):
            callee_name = expr.callee.name
        elif isinstance(expr.callee, ast.MemberExpr) and isinstance(expr.callee.obj, ast.Identifier):
            if expr.callee.obj.name in self.imported_modules:
                module_name = expr.callee.obj.name
                member_name = expr.callee.member
                if self._is_private(member_name):
                    raise CompilerError(f"'{module_name}.{member_name}' is private")
                callee_name = f"{module_name}.{member_name}"

        if callee_name == "println":
            return self._emit_println(expr)
        elif callee_name == "print":
            return self._emit_print(expr)
        elif callee_name == "len":
            return self._emit_len(expr)
        elif callee_name == "sizeof":
            return self._emit_sizeof(expr)
        elif callee_name == "typeof":
            return self._emit_typeof(expr)
        elif callee_name == "convert":
            return self._emit_convert(expr)
        elif callee_name == "input":
            return self._emit_input(expr)
        elif callee_name == "exists":
            return self._emit_exists(expr)
        elif callee_name == "range":
            return self._emit_range(expr)
        elif callee_name == "open":
            return self._emit_open(expr)

        args = []
        for a in expr.args:
            args.append(self._compile_expr(a))

        if callee_name:
            resolved_name = callee_name
            if resolved_name not in self.functions:
                mod = getattr(self, 'current_module', None)
                if mod:
                    mod_name = f"{mod}.{resolved_name}"
                    if mod_name in self.functions:
                        resolved_name = mod_name
            if resolved_name in self.functions:
                decl = self.functions[resolved_name]
                if len(decl.return_types) == 1:
                    ret_type = self._zinc_type_to_ir(decl.return_types[0])
                elif len(decl.return_types) > 1:
                    member_types = [self._zinc_type_to_ir(t) for t in decl.return_types]
                    ret_type = literal_struct_type(member_types)
                else:
                    ret_type = VOID
                for i, param in enumerate(decl.params):
                    if i < len(args):
                        param_ir = self._zinc_type_to_ir(param.type_node)
                        args[i] = self._cast_if_needed(args[i], param_ir)
                return emit_call(self.current_block, resolved_name, args, ret_type)
            if resolved_name in self.extern_funcs:
                ret_type_node, c_name, param_types = self.extern_funcs[resolved_name]
                ret_ir = self._zinc_type_to_ir(ret_type_node)
                extern_args = self._convert_extern_args(args, param_types)
                return emit_call(self.current_block, c_name, extern_args, ret_ir)
            mod = getattr(self, 'current_module', None)
            if mod:
                mod_extern = f"{mod}.{resolved_name}"
                if mod_extern in self.extern_funcs:
                    ret_type_node, c_name, param_types = self.extern_funcs[mod_extern]
                    ret_ir = self._zinc_type_to_ir(ret_type_node)
                    extern_args = self._convert_extern_args(args, param_types)
                    return emit_call(self.current_block, c_name, extern_args, ret_ir)

        callee_ptr = self._compile_expr(expr.callee)
        ret_type = I64
        if callee_name and callee_name in self.var_type_nodes:
            tn = self.var_type_nodes[callee_name]
            if isinstance(tn, ast.FuncTypeNode):
                ret_type = self._zinc_type_to_ir(tn.return_type)
        return emit_indirect_call(self.current_block, callee_ptr, args, ret_type)

    def _convert_extern_args(self, args, param_types):
        converted = []
        for i, arg in enumerate(args):
            if i < len(param_types):
                param_ir = self._zinc_type_to_ir(param_types[i])
                arg_s = str(arg.ir_type)
                param_s = str(param_ir)
                if param_s == "ptr" and "}" in arg_s and "i64" in arg_s:
                    alloca = emit_alloca(self.current_block, arg.ir_type, None)
                    emit_store(self.current_block, arg, alloca)
                    data_gep = emit_gep(self.current_block, arg.ir_type, alloca, [const_int(0, 32), const_int(0, 32)])
                    arg = emit_load(self.current_block, data_gep, PTR)
            converted.append(arg)
        return converted

    def _compile_method_call(self, expr):
        if isinstance(expr.obj, ast.Identifier) and expr.obj.name in self.imported_modules:
            module_name = expr.obj.name
            member_name = expr.method_name
            if self._is_private(member_name):
                raise CompilerError(f"'{module_name}.{member_name}' is private")
            full_name = f"{module_name}.{member_name}"
            args = [self._compile_expr(a) for a in expr.args]
            if full_name in self.functions:
                decl = self.functions[full_name]
                if len(decl.return_types) == 1:
                    ret_type = self._zinc_type_to_ir(decl.return_types[0])
                elif len(decl.return_types) > 1:
                    member_types = [self._zinc_type_to_ir(t) for t in decl.return_types]
                    ret_type = literal_struct_type(member_types)
                else:
                    ret_type = VOID
                for i, param in enumerate(decl.params):
                    if i < len(args):
                        param_ir = self._zinc_type_to_ir(param.type_node)
                        args[i] = self._cast_if_needed(args[i], param_ir)
                return emit_call(self.current_block, full_name, args, ret_type)
            if full_name in self.extern_funcs:
                ret_type_node, c_name, param_types = self.extern_funcs[full_name]
                ret_ir = self._zinc_type_to_ir(ret_type_node)
                extern_args = self._convert_extern_args(args, param_types)
                return emit_call(self.current_block, c_name, extern_args, ret_ir)
            return const_int(0, 64)

        obj = self._compile_expr(expr.obj)
        method = expr.method_name

        if method == "push":
            arg = self._compile_expr(expr.args[0])
            if isinstance(expr.obj, ast.Identifier) and expr.obj.name in self.symbols:
                ptr, _ = self.symbols[expr.obj.name]
            else:
                ptr = emit_alloca(self.current_block, obj.ir_type, None)
                emit_store(self.current_block, obj, ptr)
            elem_ir = I64
            if isinstance(expr.obj, ast.Identifier) and expr.obj.name in self.var_type_nodes:
                tn = self.var_type_nodes[expr.obj.name]
                if isinstance(tn, ast.ArrayTypeNode):
                    elem_ir = self._zinc_type_to_ir(tn.element_type)
            elem_ir_str = str(elem_ir)
            if elem_ir_str == "{ptr, i64}":
                emit_call(self.current_block, "__zn_vector_push_string", [ptr, arg], VOID)
            elif "}" in elem_ir_str or elem_ir_str.startswith("%"):
                val_alloca = emit_alloca(self.current_block, elem_ir, None)
                emit_store(self.current_block, arg, val_alloca)
                elem_size_val = self._elem_size_from_ir(elem_ir)
                emit_call(self.current_block, "__zn_vector_push_value", [ptr, val_alloca, const_int(elem_size_val, 64)], VOID)
            else:
                emit_call(self.current_block, "__zn_vector_push", [ptr, arg], VOID)
            return const_int(0, 64)
        elif method == "pop":
            if isinstance(expr.obj, ast.Identifier) and expr.obj.name in self.symbols:
                ptr, _ = self.symbols[expr.obj.name]
            else:
                ptr = emit_alloca(self.current_block, obj.ir_type, None)
                emit_store(self.current_block, obj, ptr)
            emit_call(self.current_block, "__zn_vector_pop", [ptr], VOID)
            return const_int(0, 64)
        elif method == "length":
            return self._emit_string_length(obj, obj.ir_type)
        elif method == "upper":
            return emit_call(self.current_block, "__zn_string_upper", [obj], STRING_TYPE)
        elif method == "lower":
            return emit_call(self.current_block, "__zn_string_lower", [obj], STRING_TYPE)
        elif method == "contains":
            arg = self._compile_expr(expr.args[0])
            result = emit_call(self.current_block, "__zn_string_contains", [obj, arg], I8)
            return result
        elif method == "split":
            arg = self._compile_expr(expr.args[0])
            return emit_call(self.current_block, "__zn_string_split", [obj, arg], VECTOR_TYPE)
        elif method == "write":
            arg = self._compile_expr(expr.args[0])
            emit_call(self.current_block, "__zn_file_write", [obj, arg], VOID)
            return const_int(0, 64)
        elif method == "read":
            return emit_call(self.current_block, "__zn_file_read", [obj], STRING_TYPE)
        elif method == "readln":
            return emit_call(self.current_block, "__zn_file_readln", [obj], STRING_TYPE)
        elif method == "close":
            emit_call(self.current_block, "__zn_file_close", [obj], VOID)
            return const_int(0, 64)
        elif method == "is_eof":
            result = emit_call(self.current_block, "__zn_file_is_eof", [obj], I8)
            return result

        return const_int(0, 64)

    def _compile_in_expr(self, expr):
        left = self._compile_expr(expr.left)
        right = self._compile_expr(expr.right)
        ir_type = right.ir_type
        s = str(ir_type)

        if "i64, i64}" in s:
            result = emit_call(self.current_block, "__zn_vector_contains", [right, left], I8)
        elif "i64}" in s:
            left_s = str(left.ir_type)
            if "i8" in left_s:
                left = emit_call(self.current_block, "__zn_string_from_char", [left], STRING_TYPE)
            result = emit_call(self.current_block, "__zn_string_contains", [right, left], I8)
        else:
            key_s = str(left.ir_type)
            if "}" in key_s:
                key_ptr = emit_extractvalue(self.current_block, left, 0, PTR)
                key_len = emit_extractvalue(self.current_block, left, 1, I64)
            else:
                key_str = self._value_to_string(left)
                key_ptr = emit_extractvalue(self.current_block, key_str, 0, PTR)
                key_len = emit_extractvalue(self.current_block, key_str, 1, I64)
            result = emit_call(self.current_block, "__zn_map_contains", [right, key_ptr, key_len], I8)

        return result if result else const_int(0, 8)

    def _emit_string_constant(self, value):
        gs = GlobalString(value)
        self.module.add_global_string(gs)

        char_type = array_type(I8, gs.length + 1)
        gep = emit_gep(self.current_block, char_type, Constant(PTR, f"@{gs.name}"), [const_int(0, 32), const_int(0, 32)])

        str_struct_alloca = emit_alloca(self.current_block, STRING_TYPE)
        emit_store(self.current_block, gep, str_struct_alloca)

        len_val = const_int(gs.length, 64)
        len_ptr = emit_gep(self.current_block, STRING_TYPE, str_struct_alloca, [const_int(0, 32), const_int(1, 32)])
        emit_store(self.current_block, len_val, len_ptr)

        return emit_load(self.current_block, str_struct_alloca, STRING_TYPE)

    def _emit_string_length(self, str_val, str_type):
        s = str(str_type)
        if "i64}" in s:
            alloca = emit_alloca(self.current_block, str_type)
            emit_store(self.current_block, str_val, alloca)
            len_ptr = emit_gep(self.current_block, str_type, alloca, [const_int(0, 32), const_int(1, 32)])
            return emit_load(self.current_block, len_ptr, I64)
        elif "i8" in s:
            alloca = emit_alloca(self.current_block, str_type)
            emit_store(self.current_block, str_val, alloca)
            len_ptr = emit_gep(self.current_block, str_type, alloca, [const_int(0, 32), const_int(1, 32)])
            return emit_load(self.current_block, len_ptr, I64)
        return const_int(0, 64)

    def _emit_array_get(self, arr, idx, expr=None):
        s = str(arr.ir_type)
        if "i64, i64}" in s:
            elem_ir = I64
            if expr and isinstance(expr.obj, ast.Identifier) and expr.obj.name in self.var_type_nodes:
                tn = self.var_type_nodes[expr.obj.name]
                if isinstance(tn, ast.ArrayTypeNode):
                    elem_ir = self._zinc_type_to_ir(tn.element_type)
            elem_ir_str = str(elem_ir)
            if "}" in elem_ir_str or elem_ir_str.startswith("%"):
                temp_alloca = emit_alloca(self.current_block, arr.ir_type, None)
                emit_store(self.current_block, arr, temp_alloca)
                data_gep = emit_gep(self.current_block, arr.ir_type, temp_alloca, [const_int(0, 32), const_int(0, 32)])
                data_ptr = emit_load(self.current_block, data_gep, PTR)
                elem_ptr = emit_gep(self.current_block, elem_ir, data_ptr, [idx])
                return emit_load(self.current_block, elem_ptr, elem_ir)
            return emit_call(self.current_block, "__zn_vector_get", [arr, idx], I64)
        elif "i64}" in s:
            return emit_call(self.current_block, "__zn_string_index", [arr, idx], I8)
        else:
            return const_int(0, 64)

    def _emit_array_set_by_ptr(self, ptr, idx, val, elem_ir=I64):
        elem_ir_str = str(elem_ir)
        if "}" in elem_ir_str or elem_ir_str.startswith("%"):
            v = emit_load(self.current_block, ptr, VECTOR_TYPE)
            temp_alloca = emit_alloca(self.current_block, VECTOR_TYPE, None)
            emit_store(self.current_block, v, temp_alloca)
            data_gep = emit_gep(self.current_block, VECTOR_TYPE, temp_alloca, [const_int(0, 32), const_int(0, 32)])
            data_ptr = emit_load(self.current_block, data_gep, PTR)
            elem_ptr = emit_gep(self.current_block, elem_ir, data_ptr, [idx])
            emit_store(self.current_block, val, elem_ptr)
        else:
            emit_call(self.current_block, "__zn_vector_set", [ptr, idx, val], VOID)

    def _emit_slice(self, obj, start, end):
        s = str(obj.ir_type)
        if "i64, i64}" in s:
            # Array slice: share data pointer with offset
            alloca = emit_alloca(self.current_block, obj.ir_type, None)
            emit_store(self.current_block, obj, alloca)
            data_gep = emit_gep(self.current_block, obj.ir_type, alloca, [const_int(0, 32), const_int(0, 32)])
            old_data = emit_load(self.current_block, data_gep, PTR)
            len_gep = emit_gep(self.current_block, obj.ir_type, alloca, [const_int(0, 32), const_int(1, 32)])
            old_len = emit_load(self.current_block, len_gep, I64)
            new_start = start
            if end is None:
                new_end = old_len
            else:
                new_end = end
            new_len = emit_binop(self.current_block, "-", new_end, new_start, I64)
            byte_offset = emit_binop(self.current_block, "*", new_start, const_int(8, 64), I64)
            new_data = emit_gep(self.current_block, I8, old_data, [byte_offset])
            result_alloca = emit_alloca(self.current_block, obj.ir_type, None)
            rd_gep = emit_gep(self.current_block, obj.ir_type, result_alloca, [const_int(0, 32), const_int(0, 32)])
            emit_store(self.current_block, new_data, rd_gep)
            rl_gep = emit_gep(self.current_block, obj.ir_type, result_alloca, [const_int(0, 32), const_int(1, 32)])
            emit_store(self.current_block, new_len, rl_gep)
            rc_gep = emit_gep(self.current_block, obj.ir_type, result_alloca, [const_int(0, 32), const_int(2, 32)])
            emit_store(self.current_block, new_len, rc_gep)
            return emit_load(self.current_block, result_alloca, obj.ir_type)
        if "i64}" in s:
            # String slice: copy substring to new buffer
            alloca = emit_alloca(self.current_block, obj.ir_type, None)
            emit_store(self.current_block, obj, alloca)
            data_gep = emit_gep(self.current_block, obj.ir_type, alloca, [const_int(0, 32), const_int(0, 32)])
            old_data = emit_load(self.current_block, data_gep, PTR)
            len_gep = emit_gep(self.current_block, obj.ir_type, alloca, [const_int(0, 32), const_int(1, 32)])
            old_len = emit_load(self.current_block, len_gep, I64)
            new_start = start
            if end is None:
                new_end = old_len
            else:
                new_end = end
            new_len = emit_binop(self.current_block, "-", new_end, new_start, I64)
            one = const_int(1, 64)
            alloc_size = emit_binop(self.current_block, "+", new_len, one, I64)
            buf = emit_call(self.current_block, "GC_malloc", [alloc_size], PTR)
            src = emit_gep(self.current_block, I8, old_data, [new_start])
            emit_call(self.current_block, "llvm.memcpy.p0i8.p0i8.i64", [buf, src, new_len, const_bool(False)], VOID)
            null_ptr = emit_gep(self.current_block, I8, buf, [new_len])
            emit_store(self.current_block, const_int(0, 8), null_ptr)
            res_alloca = emit_alloca(self.current_block, obj.ir_type, None)
            rd2 = emit_gep(self.current_block, obj.ir_type, res_alloca, [const_int(0, 32), const_int(0, 32)])
            emit_store(self.current_block, buf, rd2)
            rl2 = emit_gep(self.current_block, obj.ir_type, res_alloca, [const_int(0, 32), const_int(1, 32)])
            emit_store(self.current_block, new_len, rl2)
            return emit_load(self.current_block, res_alloca, obj.ir_type)
        return obj

    def _get_struct_name(self, ir_type):
        s = str(ir_type)
        if s.startswith("%"):
            return s[1:]
        if s.startswith("{") or s.endswith("}"):
            for name, decl in self.structs.items():
                if str(self._struct_ir_type(name)) == s:
                    return name
        return None

    def _emit_struct_field_get(self, obj, field_name):
        struct_name = self._get_struct_name(obj.ir_type)
        if not struct_name or struct_name not in self.structs:
            return const_int(0, 64)
        decl = self.structs[struct_name]
        field_idx = None
        for i, f in enumerate(decl.fields):
            if f.name == field_name:
                field_idx = i
                break
        if field_idx is None:
            return const_int(0, 64)
        alloca = emit_alloca(self.current_block, obj.ir_type, None)
        emit_store(self.current_block, obj, alloca)
        gep = emit_gep(self.current_block, obj.ir_type, alloca, [const_int(0, 32), const_int(field_idx, 32)])
        field_type = self._zinc_type_to_ir(decl.fields[field_idx].type_node)
        return emit_load(self.current_block, gep, field_type)

    def _emit_struct_field_set_by_ptr(self, ptr, ir_type, field_name, value):
        struct_name = self._get_struct_name(ir_type)
        if not struct_name or struct_name not in self.structs:
            return
        decl = self.structs[struct_name]
        field_idx = None
        for i, f in enumerate(decl.fields):
            if f.name == field_name:
                field_idx = i
                break
        if field_idx is None:
            return
        gep = emit_gep(self.current_block, ir_type, ptr, [const_int(0, 32), const_int(field_idx, 32)])
        field_type = self._zinc_type_to_ir(decl.fields[field_idx].type_node)
        cast_val = self._cast_if_needed(value, field_type)
        emit_store(self.current_block, cast_val, gep)

    def _emit_struct_field_set(self, obj, field_name, value):
        struct_name = self._get_struct_name(obj.ir_type)
        if not struct_name or struct_name not in self.structs:
            return
        decl = self.structs[struct_name]
        field_idx = None
        for i, f in enumerate(decl.fields):
            if f.name == field_name:
                field_idx = i
                break
        if field_idx is None:
            return
        alloca = emit_alloca(self.current_block, obj.ir_type, None)
        emit_store(self.current_block, obj, alloca)
        gep = emit_gep(self.current_block, obj.ir_type, alloca, [const_int(0, 32), const_int(field_idx, 32)])
        emit_store(self.current_block, value, gep)

    def _compile_struct_literal(self, expr):
        struct_name = expr.struct_name
        if struct_name not in self.structs:
            return const_int(0, 64)
        decl = self.structs[struct_name]
        ir_type = self._struct_ir_type(struct_name)
        alloca = emit_alloca(self.current_block, ir_type, None)
        emit_store(self.current_block, const_zeroinitializer(ir_type), alloca)
        for init in expr.fields:
            field_idx = None
            for i, f in enumerate(decl.fields):
                if f.name == init.name:
                    field_idx = i
                    break
            if field_idx is None:
                continue
            val = self._compile_expr(init.value)
            field_type = self._zinc_type_to_ir(decl.fields[field_idx].type_node)
            cast_val = self._cast_if_needed(val, field_type)
            gep = emit_gep(self.current_block, ir_type, alloca, [const_int(0, 32), const_int(field_idx, 32)])
            emit_store(self.current_block, cast_val, gep)
        return emit_load(self.current_block, alloca, ir_type)

    def _compile_array_literal(self, expr):
        elements = expr.elements
        count = len(elements)
        if count == 0:
            return const_null()

        first = self._compile_expr(elements[0])
        elem_ir_type = first.ir_type

        elem_size_val = 8
        es = str(elem_ir_type)
        if "}" in es or "%" in es:
            elem_size_val = 8 * (es.count("ptr") + es.count("i64") + es.count("double") + es.count("i32") + es.count("i8"))
        elif "i64" in es or "double" in es:
            elem_size_val = 8
        elif "i32" in es or "float" in es:
            elem_size_val = 4
        elif "i8" in es:
            elem_size_val = 1

        elem_size = const_int(elem_size_val, 64)
        total_bytes = emit_binop(self.current_block, "*", const_int(count, 64), elem_size, I64)
        data_ptr = emit_call(self.current_block, "GC_malloc", [total_bytes], PTR)

        dest_type = elem_ir_type
        for i, e in enumerate(elements):
            val = self._compile_expr(e) if i > 0 else first
            dest = emit_gep(self.current_block, dest_type, data_ptr, [const_int(i, 64)])
            emit_store(self.current_block, val, dest)

        vec_alloca = emit_alloca(self.current_block, VECTOR_TYPE, None)
        data_gep = emit_gep(self.current_block, VECTOR_TYPE, vec_alloca, [const_int(0, 32), const_int(0, 32)])
        emit_store(self.current_block, data_ptr, data_gep)
        len_gep = emit_gep(self.current_block, VECTOR_TYPE, vec_alloca, [const_int(0, 32), const_int(1, 32)])
        emit_store(self.current_block, const_int(count, 64), len_gep)
        cap_gep = emit_gep(self.current_block, VECTOR_TYPE, vec_alloca, [const_int(0, 32), const_int(2, 32)])
        emit_store(self.current_block, const_int(count, 64), cap_gep)
        return emit_load(self.current_block, vec_alloca, VECTOR_TYPE)

    def _emit_value_for_map_set(self, value):
        s = str(value.ir_type)
        if "i64" == s:
            vtype = I64
        elif "}" in s:
            vtype = STRING_TYPE
        else:
            vtype = I64
        alloca = emit_alloca(self.current_block, vtype, None)
        emit_store(self.current_block, value, alloca)
        return alloca

    def _compile_map_literal(self, expr):
        return emit_call(self.current_block, "__zn_map_new", [], PTR)

    def _emit_println(self, expr):
        raw = expr.args[0]
        arg = self._compile_expr(raw)
        s = str(arg.ir_type)

        is_bool = False
        if isinstance(raw, ast.Identifier) and raw.name in self.var_types:
            is_bool = self.var_types[raw.name] == "bool"
        if isinstance(raw, ast.CallExpr):
            func_name = None
            if isinstance(raw.callee, ast.Identifier):
                func_name = raw.callee.name
            elif isinstance(raw.callee, ast.MemberExpr) and isinstance(raw.callee.obj, ast.Identifier):
                func_name = f"{raw.callee.obj.name}.{raw.callee.member}"
            if func_name:
                if func_name in self.functions:
                    decl = self.functions[func_name]
                    if decl.return_types and len(decl.return_types) == 1:
                        is_bool = self._zinc_type_to_str(decl.return_types[0]) == "bool"
                elif func_name in self.extern_funcs:
                    ret_type_node, _, _ = self.extern_funcs[func_name]
                    is_bool = self._zinc_type_to_str(ret_type_node) == "bool"
                elif func_name == "exists":
                    is_bool = True
        if isinstance(raw, ast.MethodCallExpr):
            if isinstance(raw.obj, ast.Identifier) and raw.obj.name in self.imported_modules:
                full_name = f"{raw.obj.name}.{raw.method_name}"
                if full_name in self.functions:
                    decl = self.functions[full_name]
                    if decl.return_types and len(decl.return_types) == 1:
                        is_bool = self._zinc_type_to_str(decl.return_types[0]) == "bool"
                elif full_name in self.extern_funcs:
                    ret_type_node, _, _ = self.extern_funcs[full_name]
                    is_bool = self._zinc_type_to_str(ret_type_node) == "bool"
            elif raw.method_name in ("contains", "exists"):
                is_bool = True

        if "}" in s:
            return emit_call(self.current_block, "__zn_println", [arg], VOID)
        elif "double" in s or "float" in s:
            if "float" in s and "double" not in s:
                arg = emit_fpext(self.current_block, arg, DOUBLE)
            return emit_call(self.current_block, "__zn_print_float", [arg], VOID)
        elif "i1" in s:
            return emit_call(self.current_block, "__zn_print_bool", [arg], VOID)
        elif "i8" in s:
            if is_bool:
                return emit_call(self.current_block, "__zn_print_bool", [arg], VOID)
            return emit_call(self.current_block, "__zn_print_char", [arg], VOID)
        elif "i64" in s or "i32" in s:
            return emit_call(self.current_block, "__zn_print_int", [arg], VOID)
        return emit_call(self.current_block, "__zn_print_int", [arg], VOID)

    def _emit_print(self, expr):
        arg = self._compile_expr(expr.args[0])
        return emit_call(self.current_block, "__zn_print", [arg], VOID)

    def _emit_len(self, expr):
        arg = self._compile_expr(expr.args[0])
        s = str(arg.ir_type)
        if "}" in s:
            alloca = emit_alloca(self.current_block, arg.ir_type)
            emit_store(self.current_block, arg, alloca)
            len_ptr = emit_gep(self.current_block, arg.ir_type, alloca, [const_int(0, 32), const_int(1, 32)])
            return emit_load(self.current_block, len_ptr, I64)
        return emit_call(self.current_block, "__zn_len", [arg], I64)

    def _emit_sizeof(self, expr):
        if isinstance(expr.args[0], ast.Identifier):
            name = expr.args[0].name
            if name in self.structs:
                return const_int(16, 64)
            type_size = {
                "int": 8, "uint": 8, "int32": 4, "uint32": 4,
                "int16": 2, "uint16": 2, "int8": 1, "uint8": 1,
                "int4": 1, "uint4": 1,
                "float": 8, "float32": 4,
                "char": 1, "bool": 1, "string": 16,
                "file": 8, "void": 0,
            }
            return const_int(type_size.get(name, 8), 64)
        return const_int(8, 64)

    def _emit_typeof(self, expr):
        val = self._compile_expr(expr.args[0])
        s = str(val.ir_type)
        type_names = {
            "i64": "int", "double": "float", "float": "float32",
            "i32": "int32", "i16": "int16", "i8": "int8", "i4": "int4",
            "i1": "bool",
        }
        tname = type_names.get(s, s)
        return self._emit_string_constant(tname)

    def _emit_convert(self, expr):
        val = self._compile_expr(expr.args[1])
        target_str = ""
        if isinstance(expr.args[0], ast.StringLiteral):
            target_str = expr.args[0].value

        NUMERIC_TYPES = {"int": I64, "uint": I64, "int32": I32, "uint32": I32,
                         "int16": I16, "uint16": I16, "int8": I8, "uint8": I8,
                         "int4": I4, "uint4": I4, "float": DOUBLE, "float32": FLOAT}
        vs = str(val.ir_type)

        if target_str in NUMERIC_TYPES:
            target_ir = NUMERIC_TYPES[target_str]
            ts = str(target_ir)
            if vs == ts:
                return val
            INT_TYPES = ["i64", "i32", "i16", "i8", "i4", "i1"]
            FLOAT_TYPES = ["double", "float"]
            vs_int = next((t for t in INT_TYPES if t in vs), None)
            ts_int = next((t for t in INT_TYPES if t in ts), None)
            vs_float = next((t for t in FLOAT_TYPES if t in vs), None)
            ts_float = next((t for t in FLOAT_TYPES if t in ts), None)
            if vs_int and ts_int:
                vs_bits = int(vs_int[1:])
                ts_bits = int(ts_int[1:])
                if ts_bits > vs_bits:
                    return emit_sext(self.current_block, val, target_ir)
                else:
                    return emit_trunc(self.current_block, val, target_ir)
            if ts_float and vs_int:
                return emit_sitofp(self.current_block, val, target_ir)
            if ts_int and vs_float:
                return emit_fptosi(self.current_block, val, target_ir)
            return val

        if target_str == "string":
            if "double" in vs or "float" in vs:
                return emit_call(self.current_block, "__zn_float64_to_string", [val], STRING_TYPE)
            return emit_call(self.current_block, "__zn_int64_to_string", [val], STRING_TYPE)
        elif target_str == "char":
            str_alloca = emit_alloca(self.current_block, STRING_TYPE)
            emit_store(self.current_block, val, str_alloca)
            data_ptr = emit_gep(self.current_block, STRING_TYPE, str_alloca, [const_int(0, 32), const_int(0, 32)])
            data = emit_load(self.current_block, data_ptr, PTR)
            char_val = emit_load(self.current_block, data, I8)
            return char_val

        return val

    def _emit_input(self, expr):
        prompt = self._compile_expr(expr.args[0]) if expr.args else None
        return emit_call(self.current_block, "__zn_input", [prompt] if prompt else [], STRING_TYPE)

    def _emit_exists(self, expr):
        arg = self._compile_expr(expr.args[0])
        result = emit_call(self.current_block, "__zn_exists", [arg], I8)
        return result

    def _emit_range(self, expr):
        args = [self._compile_expr(a) for a in expr.args]
        if len(args) == 1:
            return emit_call(self.current_block, "__zn_range", [const_int(0, 64), args[0], const_int(1, 64)], VECTOR_TYPE)
        elif len(args) == 2:
            return emit_call(self.current_block, "__zn_range", [args[0], args[1], const_int(1, 64)], VECTOR_TYPE)
        else:
            return emit_call(self.current_block, "__zn_range", [args[0], args[1], args[2]], VECTOR_TYPE)

    def _emit_open(self, expr):
        path = self._compile_expr(expr.args[0])
        mode = self._compile_expr(expr.args[1])
        return emit_call(self.current_block, "__zn_file_open", [path, mode], PTR)

    def _i8_to_i1(self, val):
        zero = const_int(0, 8)
        cmp = emit_icmp(self.current_block, "!=", val, zero, I8)
        return cmp

    def _cast_if_needed(self, val, target_ir):
        vs = str(val.ir_type)
        ts = str(target_ir)
        if vs == ts:
            return val
        if "}" in ts:
            return val
        INT_TYPES = ["i64", "i32", "i16", "i8", "i4", "i1"]
        FLOAT_TYPES = ["double", "float"]
        vs_int = next((t for t in INT_TYPES if t in vs), None)
        ts_int = next((t for t in INT_TYPES if t in ts), None)
        vs_float = next((t for t in FLOAT_TYPES if t in vs), None)
        ts_float = next((t for t in FLOAT_TYPES if t in ts), None)
        if vs_int and ts_int:
            vs_bits = int(vs_int[1:])
            ts_bits = int(ts_int[1:])
            if ts_bits > vs_bits:
                return emit_sext(self.current_block, val, target_ir)
            else:
                return emit_trunc(self.current_block, val, target_ir)
        if ts_float and vs_int:
            return emit_sitofp(self.current_block, val, target_ir)
        if ts_int and vs_float:
            return emit_fptosi(self.current_block, val, target_ir)
        if ts == "ptr":
            if vs_int:
                return emit_inttoptr(self.current_block, val, target_ir)
        return val

    def _default_value_by_ir(self, ir_type):
        s = str(ir_type)
        if "}" in s or "{" in s:
            return const_null()
        if "i64" in s:
            return const_int(0, 64)
        if "i32" in s:
            return const_int(0, 32)
        if "i16" in s:
            return const_int(0, 16)
        if "i8" in s:
            return const_int(0, 8)
        if "i4" in s:
            return const_int(0, 4)
        if "i1" in s:
            return const_bool(False)
        if "double" in s:
            return const_double(0.0)
        if "float" in s:
            return const_float(0.0)
        if "ptr" in s:
            return const_null()
        return const_int(0, 64)

    def _value_to_string(self, val):
        gs = GlobalString(str(val.value) if hasattr(val, 'value') else "?")
        self.module.add_global_string(gs)
        char_type = array_type(I8, gs.length + 1)
        gep = emit_gep(self.current_block, char_type, Constant(PTR, f"@{gs.name}"), [const_int(0, 32), const_int(0, 32)])
        str_struct_alloca = emit_alloca(self.current_block, STRING_TYPE)
        emit_store(self.current_block, gep, str_struct_alloca)
        len_ptr = emit_gep(self.current_block, STRING_TYPE, str_struct_alloca, [const_int(0, 32), const_int(1, 32)])
        emit_store(self.current_block, const_int(gs.length, 64), len_ptr)
        return emit_load(self.current_block, str_struct_alloca, STRING_TYPE)
