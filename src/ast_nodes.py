class ASTNode:
    pass


class TypeNode(ASTNode):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"TypeNode({self.name})"


class ArrayTypeNode(ASTNode):
    def __init__(self, element_type):
        self.element_type = element_type

    def __repr__(self):
        return f"ArrayTypeNode({self.element_type})"


class MapTypeNode(ASTNode):
    def __init__(self, key_type, value_type):
        self.key_type = key_type
        self.value_type = value_type

    def __repr__(self):
        return f"MapTypeNode({self.key_type}, {self.value_type})"


class FuncTypeNode(ASTNode):
    def __init__(self, param_types, return_type):
        self.param_types = param_types
        self.return_type = return_type

    def __repr__(self):
        return f"FuncTypeNode({self.param_types} -> {self.return_type})"


class ExternBlock(ASTNode):
    def __init__(self, funcs):
        self.funcs = funcs

    def __repr__(self):
        return f"ExternBlock({len(self.funcs)} funcs)"


class ExternFuncDecl(ASTNode):
    def __init__(self, ret_type, c_name, params, zinc_name=None):
        self.ret_type = ret_type
        self.c_name = c_name
        self.params = params
        self.zinc_name = zinc_name if zinc_name else c_name

    def __repr__(self):
        return f"ExternFuncDecl({self.c_name} as {self.zinc_name})"


class MultiReturnTypeNode(ASTNode):
    def __init__(self, types):
        self.types = types

    def __repr__(self):
        return f"MultiReturnTypeNode({self.types})"


class RefTypeNode(ASTNode):
    def __init__(self, inner_type):
        self.inner_type = inner_type

    def __repr__(self):
        return f"RefTypeNode({self.inner_type})"


class NamedTypeNode(ASTNode):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"NamedTypeNode({self.name})"


class Program(ASTNode):
    def __init__(self):
        self.declarations = []

    def __repr__(self):
        return f"Program({len(self.declarations)} decls)"


class ImportDecl(ASTNode):
    def __init__(self, path, source_file=None):
        self.path = path
        self.source_file = source_file

    def __repr__(self):
        return f"ImportDecl({self.path})"


class ConstDecl(ASTNode):
    def __init__(self, name, type_node, value):
        self.name = name
        self.type_node = type_node
        self.value = value

    def __repr__(self):
        return f"ConstDecl({self.name}, {self.type_node}, {self.value})"


class VarDecl(ASTNode):
    def __init__(self, name, type_node, value, is_ref=False, is_const=False):
        self.name = name
        self.type_node = type_node
        self.value = value
        self.is_ref = is_ref
        self.is_const = is_const

    def __repr__(self):
        return f"VarDecl({self.name}, {self.type_node})"


class FunctionDecl(ASTNode):
    def __init__(self, name, params, return_types, body, is_method=False, struct_name=None):
        self.name = name
        self.params = params
        self.return_types = return_types
        self.body = body
        self.is_method = is_method
        self.struct_name = struct_name

    def __repr__(self):
        return f"FunctionDecl({self.name}, {len(self.params)} params)"


class ParamDecl(ASTNode):
    def __init__(self, name, type_node, is_ref=False):
        self.name = name
        self.type_node = type_node
        self.is_ref = is_ref

    def __repr__(self):
        return f"ParamDecl({self.name}, {self.type_node}, ref={self.is_ref})"


class StructDecl(ASTNode):
    def __init__(self, name, fields, methods=None):
        self.name = name
        self.fields = fields
        self.methods = methods or []

    def __repr__(self):
        return f"StructDecl({self.name}, {len(self.fields)} fields)"


class FieldDecl(ASTNode):
    def __init__(self, name, type_node):
        self.name = name
        self.type_node = type_node

    def __repr__(self):
        return f"FieldDecl({self.name}, {self.type_node})"


class EnumDecl(ASTNode):
    def __init__(self, name, variants):
        self.name = name
        self.variants = variants

    def __repr__(self):
        return f"EnumDecl({self.name}, {self.variants})"


class Block(ASTNode):
    def __init__(self, statements):
        self.statements = statements

    def __repr__(self):
        return f"Block({len(self.statements)} stmts)"


class IfStmt(ASTNode):
    def __init__(self, condition, then_block, elifs=None, else_block=None):
        self.condition = condition
        self.then_block = then_block
        self.elifs = elifs or []
        self.else_block = else_block

    def __repr__(self):
        return f"IfStmt({self.condition})"


class ElifStmt(ASTNode):
    def __init__(self, condition, block):
        self.condition = condition
        self.block = block


class ForStmt(ASTNode):
    def __init__(self, init, condition, increment, body):
        self.init = init
        self.condition = condition
        self.increment = increment
        self.body = body

    def __repr__(self):
        return f"ForStmt(init={self.init}, cond={self.condition})"


class ForInStmt(ASTNode):
    def __init__(self, var_name, iterable, body):
        self.var_name = var_name
        self.iterable = iterable
        self.body = body

    def __repr__(self):
        return f"ForInStmt({self.var_name} in {self.iterable})"


class WhileStmt(ASTNode):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

    def __repr__(self):
        return f"WhileStmt({self.condition})"


class MatchStmt(ASTNode):
    def __init__(self, expr, cases, default_block=None):
        self.expr = expr
        self.cases = cases
        self.default_block = default_block

    def __repr__(self):
        return f"MatchStmt({len(self.cases)} cases)"


class MatchCase(ASTNode):
    def __init__(self, pattern, block):
        self.pattern = pattern
        self.block = block


class DelStmt(ASTNode):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f"DelStmt({self.expr})"


class DeferStmt(ASTNode):
    def __init__(self, statement):
        self.statement = statement

    def __repr__(self):
        return f"DeferStmt({self.statement})"


class ReturnStmt(ASTNode):
    def __init__(self, values=None):
        self.values = values if values is not None else []

    def __repr__(self):
        return f"ReturnStmt({self.values})"


class BreakStmt(ASTNode):
    def __repr__(self):
        return "BreakStmt()"


class ContinueStmt(ASTNode):
    def __repr__(self):
        return "ContinueStmt()"


class RaiseStmt(ASTNode):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f"RaiseStmt({self.expr})"


class ExprStmt(ASTNode):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f"ExprStmt({self.expr})"


class AssignStmt(ASTNode):
    def __init__(self, targets, value):
        self.targets = targets
        self.value = value

    def __repr__(self):
        return f"AssignStmt({self.targets} = {self.value})"


class MultiAssignStmt(ASTNode):
    def __init__(self, targets, value):
        self.targets = targets
        self.value = value

    def __repr__(self):
        return f"MultiAssignStmt({self.targets} = {self.value})"


class BinaryOp(ASTNode):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

    def __repr__(self):
        return f"BinaryOp({self.left} {self.op} {self.right})"


class UnaryOp(ASTNode):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand

    def __repr__(self):
        return f"UnaryOp({self.op} {self.operand})"


class IntLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"IntLiteral({self.value})"


class FloatLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"FloatLiteral({self.value})"


class StringLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"StringLiteral({self.value!r})"


class CharLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"CharLiteral({self.value!r})"


class BoolLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"BoolLiteral({self.value})"


class Identifier(ASTNode):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Identifier({self.name})"


class CallExpr(ASTNode):
    def __init__(self, callee, args):
        self.callee = callee
        self.args = args

    def __repr__(self):
        return f"CallExpr({self.callee}, {len(self.args)} args)"


class MethodCallExpr(ASTNode):
    def __init__(self, obj, method_name, args):
        self.obj = obj
        self.method_name = method_name
        self.args = args

    def __repr__(self):
        return f"MethodCallExpr({self.obj}.{self.method_name})"


class IndexExpr(ASTNode):
    def __init__(self, obj, index):
        self.obj = obj
        self.index = index

    def __repr__(self):
        return f"IndexExpr({self.obj}[{self.index}])"


class SliceExpr(ASTNode):
    def __init__(self, obj, start, end):
        self.obj = obj
        self.start = start
        self.end = end

    def __repr__(self):
        return f"SliceExpr({self.obj}[{self.start}:{self.end}])"


class MemberExpr(ASTNode):
    def __init__(self, obj, member):
        self.obj = obj
        self.member = member

    def __repr__(self):
        return f"MemberExpr({self.obj}.{self.member})"


class StructLiteral(ASTNode):
    def __init__(self, struct_name, fields):
        self.struct_name = struct_name
        self.fields = fields

    def __repr__(self):
        return f"StructLiteral({self.struct_name}, {len(self.fields)} fields)"


class StructFieldInit(ASTNode):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __repr__(self):
        return f"StructFieldInit({self.name} = {self.value})"


class ArrayLiteral(ASTNode):
    def __init__(self, elements):
        self.elements = elements

    def __repr__(self):
        return f"ArrayLiteral({len(self.elements)} elems)"


class MapLiteral(ASTNode):
    def __init__(self, entries=None):
        self.entries = entries or []

    def __repr__(self):
        return f"MapLiteral({len(self.entries)} entries)"


class MapEntry(ASTNode):
    def __init__(self, key, value):
        self.key = key
        self.value = value


class InExpr(ASTNode):
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def __repr__(self):
        return f"InExpr({self.left} in {self.right})"


class ParenExpr(ASTNode):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f"ParenExpr({self.expr})"


class MultiValueExpr(ASTNode):
    def __init__(self, values):
        self.values = values

    def __repr__(self):
        return f"MultiValueExpr({self.values})"


class MultiVarDecl(ASTNode):
    def __init__(self, var_names, types, value):
        self.var_names = var_names
        self.types = types
        self.value = value

    def __repr__(self):
        return f"MultiVarDecl({self.var_names}, {self.types}, {self.value})"


class RangeExpr(ASTNode):
    def __init__(self, args):
        self.args = args

    def __repr__(self):
        return f"RangeExpr({self.args})"
