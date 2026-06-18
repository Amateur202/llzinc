from .token_types import TokenType
from .lexer import Lexer
from .ast_nodes import *


class ParserError(Exception):
    def __init__(self, message, token):
        self.message = message
        self.line = token.line if hasattr(token, 'line') else 0
        self.col = token.col if hasattr(token, 'col') else 0
        super().__init__(f"[ZINC][ERROR][{self.line}, {self.col}] {message}")


class Parser:
    def __init__(self, lexer, source_path=None):
        self.lexer = lexer
        self.tokens = lexer.tokenize()
        self.pos = 0
        self.source_path = source_path

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, *expected_types):
        tok = self.peek()
        if tok.type not in expected_types:
            msg = f"Expected {' or '.join(expected_types)}, got {tok.type} ({tok.value})"
            raise ParserError(msg, tok)
        return self.advance()

    def skip_newlines(self):
        while self.peek().type == TokenType.NEWLINE:
            self.advance()

    def parse(self):
        program = Program()
        self.skip_newlines()
        while self.peek().type != TokenType.EOF:
            decl = self.parse_top_level_decl()
            if decl:
                if isinstance(decl, list):
                    program.declarations.extend(decl)
                else:
                    program.declarations.append(decl)
            self.skip_newlines()
        return program

    def parse_top_level_decl(self):
        tok = self.peek()

        if tok.type == TokenType.KEYWORD_EXTERN:
            return self.parse_extern_block()
        if tok.type == TokenType.KEYWORD_IMPORT:
            return self.parse_import()
        if tok.type == TokenType.KEYWORD_CONST:
            return self.parse_const_decl()
        if tok.type == TokenType.KEYWORD_STRUCT:
            return self.parse_struct_decl()
        if tok.type == TokenType.KEYWORD_ENUM:
            return self.parse_enum_decl()

        if tok.type == TokenType.KEYWORD_VOID:
            self.advance()
            name = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.LPAREN)
            params = self.parse_params()
            self.expect(TokenType.RPAREN)
            body = self.parse_brace_block()
            return FunctionDecl(name, params, [TypeNode("void")], body)

        return_types = self.parse_return_types()
        name = self.expect(TokenType.IDENTIFIER).value
        tok2 = self.peek()

        if tok2.type == TokenType.LPAREN:
            self.advance()
            params = self.parse_params()
            self.expect(TokenType.RPAREN)
            body = self.parse_brace_block()
            return FunctionDecl(name, params, return_types, body)
        else:
            if len(return_types) == 1:
                var_type = return_types[0]
                if self.peek().type == TokenType.ASSIGN:
                    self.advance()
                    value = self.parse_expression()
                    return VarDecl(name, var_type, value)
                return VarDecl(name, var_type, None)
            else:
                value = None
                if self.peek().type == TokenType.ASSIGN:
                    self.advance()
                    value = self.parse_expression()
                return MultiVarDecl([name], return_types, value)

    def parse_import(self):
        self.advance()
        path_tok = self.expect(TokenType.STRING)
        return ImportDecl(path_tok.value, source_file=self.source_path)

    def parse_const_decl(self):
        self.advance()
        tok = self.peek()
        if tok.type == TokenType.IDENTIFIER:
            name = self.advance().value
            type_node = None
            if self.peek().type != TokenType.ASSIGN:
                type_node = self.parse_type()
            self.expect(TokenType.ASSIGN)
            value = self.parse_expression()
            return ConstDecl(name, type_node, value)
        else:
            type_node = self.parse_type()
            name = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.ASSIGN)
            value = self.parse_expression()
            return ConstDecl(name, type_node, value)

    def parse_struct_decl(self):
        self.advance()
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        fields = []
        methods = []
        while self.peek().type != TokenType.RBRACE:
            return_types = self.parse_return_types()
            tok = self.peek()
            field_name = self.expect(TokenType.IDENTIFIER).value
            if self.peek().type == TokenType.LPAREN:
                self.advance()
                params = self.parse_params()
                self.expect(TokenType.RPAREN)
                body = self.parse_brace_block()
                methods.append(FunctionDecl(field_name, params, return_types, body, is_method=True, struct_name=name))
            else:
                if return_types:
                    fields.append(FieldDecl(field_name, return_types[0] if isinstance(return_types, list) and len(return_types) == 1 else return_types))
            self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return StructDecl(name, fields, methods)

    def parse_enum_decl(self):
        self.advance()
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        variants = []
        while self.peek().type != TokenType.RBRACE:
            variant = self.expect(TokenType.IDENTIFIER).value
            variants.append(variant)
            self.skip_newlines()
            if self.peek().type == TokenType.COMMA:
                self.advance()
                self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return EnumDecl(name, variants)

    def parse_extern_block(self):
        self.advance()
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        funcs = []
        while self.peek().type != TokenType.RBRACE and self.peek().type != TokenType.EOF:
            ret_type = self.parse_type()
            c_name = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.LPAREN)
            params = []
            self.skip_newlines()
            if self.peek().type != TokenType.RPAREN:
                while True:
                    ptype = self.parse_type()
                    if self.peek().type == TokenType.IDENTIFIER:
                        self.advance()
                    params.append(ptype)
                    self.skip_newlines()
                    if self.peek().type == TokenType.COMMA:
                        self.advance()
                        self.skip_newlines()
                    else:
                        break
            self.expect(TokenType.RPAREN)
            zinc_name = None
            if self.peek().type == TokenType.KEYWORD_AS:
                self.advance()
                zinc_name = self.expect(TokenType.IDENTIFIER).value
            funcs.append(ExternFuncDecl(ret_type, c_name, params, zinc_name))
            self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return ExternBlock(funcs)

    def parse_return_types(self):
        types = [self.parse_type()]
        while self.peek().type == TokenType.COMMA:
            self.advance()
            types.append(self.parse_type())
        return types

    def parse_type(self):
        tok = self.peek()
        if tok.type == TokenType.KEYWORD_MAP:
            self.advance()
            self.expect(TokenType.LT)
            key_type = self.parse_type()
            self.expect(TokenType.COMMA)
            value_type = self.parse_type()
            self.expect(TokenType.GT)
            base_type = MapTypeNode(key_type, value_type)
            while self.peek().type == TokenType.LBRACKET:
                self.advance()
                self.expect(TokenType.RBRACKET)
                base_type = ArrayTypeNode(base_type)
            return base_type
        if tok.type == TokenType.LBRACKET:
            self.advance()
            self.expect(TokenType.RBRACKET)
            elem_type = self.parse_type()
            return ArrayTypeNode(elem_type)
        if tok.type in {
            TokenType.KEYWORD_INT, TokenType.KEYWORD_UINT64,
            TokenType.KEYWORD_FLOAT, TokenType.KEYWORD_FLOAT32,
            TokenType.KEYWORD_FLOAT64,
            TokenType.KEYWORD_STRING, TokenType.KEYWORD_CHAR,
            TokenType.KEYWORD_BOOL, TokenType.KEYWORD_VOID,
            TokenType.KEYWORD_FILE,
        }:
            base_type = TypeNode(self.advance().value)
            while self.peek().type == TokenType.LBRACKET:
                self.advance()
                self.expect(TokenType.RBRACKET)
                base_type = ArrayTypeNode(base_type)
            return base_type
        if tok.type == TokenType.IDENTIFIER:
            name = self.advance().value
            base_type = NamedTypeNode(name)
            while self.peek().type == TokenType.LBRACKET:
                self.advance()
                self.expect(TokenType.RBRACKET)
                base_type = ArrayTypeNode(base_type)
            return base_type
        raise ParserError(f"Expected type, got {tok} ({tok.value})", tok)

    def parse_params(self):
        params = []
        self.skip_newlines()
        if self.peek().type == TokenType.RPAREN:
            return params
        while True:
            is_ref = False
            if self.peek().type == TokenType.KEYWORD_REF:
                is_ref = True
                self.advance()
            ptype = self.parse_type()
            pname = self.expect(TokenType.IDENTIFIER).value
            if self.peek().type == TokenType.LPAREN:
                self.advance()
                func_params = []
                self.skip_newlines()
                if self.peek().type != TokenType.RPAREN:
                    while True:
                        func_params.append(self.parse_type())
                        self.skip_newlines()
                        if self.peek().type == TokenType.COMMA:
                            self.advance()
                            self.skip_newlines()
                        else:
                            break
                self.expect(TokenType.RPAREN)
                ptype = FuncTypeNode(ptype, func_params)
            params.append(ParamDecl(pname, ptype, is_ref))
            if self.peek().type == TokenType.COMMA:
                self.advance()
                self.skip_newlines()
            else:
                break
        return params

    def parse_brace_block(self):
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        stmts = []
        while self.peek().type != TokenType.RBRACE and self.peek().type != TokenType.EOF:
            stmt = self.parse_statement()
            if stmt:
                stmts.append(stmt)
            self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return Block(stmts)

    def parse_statement(self):
        tok = self.peek()

        if tok.type == TokenType.KEYWORD_IF:
            return self.parse_if_stmt()
        if tok.type == TokenType.KEYWORD_FOR:
            return self.parse_for_stmt()
        if tok.type == TokenType.KEYWORD_WHILE:
            return self.parse_while_stmt()
        if tok.type == TokenType.KEYWORD_MATCH:
            return self.parse_match_stmt()
        if tok.type == TokenType.KEYWORD_RETURN:
            return self.parse_return_stmt()
        if tok.type == TokenType.KEYWORD_BREAK:
            self.advance()
            return BreakStmt()
        if tok.type == TokenType.KEYWORD_CONTINUE:
            self.advance()
            return ContinueStmt()
        if tok.type == TokenType.KEYWORD_DEFER:
            self.advance()
            stmt = self.parse_statement()
            return DeferStmt(stmt)
        if tok.type == TokenType.KEYWORD_DEL:
            self.advance()
            expr = self.parse_expression()
            return DelStmt(expr)
        if tok.type == TokenType.KEYWORD_RAISE:
            self.advance()
            expr = self.parse_expression()
            return RaiseStmt(expr)
        if tok.type == TokenType.KEYWORD_CONST:
            return self.parse_const_decl()
        if tok.type == TokenType.KEYWORD_STRUCT:
            return self.parse_struct_decl()
        if tok.type == TokenType.KEYWORD_ENUM:
            return self.parse_enum_decl()
        if tok.type == TokenType.KEYWORD_IMPORT:
            return self.parse_import()
        if tok.type == TokenType.LBRACE:
            return self.parse_brace_block()

        if tok.type in {
            TokenType.KEYWORD_INT, TokenType.KEYWORD_UINT64,
            TokenType.KEYWORD_FLOAT, TokenType.KEYWORD_FLOAT32,
            TokenType.KEYWORD_FLOAT64,
            TokenType.KEYWORD_STRING, TokenType.KEYWORD_CHAR,
            TokenType.KEYWORD_BOOL, TokenType.KEYWORD_VOID,
            TokenType.KEYWORD_FILE, TokenType.KEYWORD_MAP,
            TokenType.LBRACKET,
        }:
            return self.parse_var_decl_or_assign()

        if tok.type == TokenType.IDENTIFIER:
            if self.peek_next(1).type in (TokenType.IDENTIFIER, TokenType.LBRACKET):
                return self.parse_var_decl_or_assign()

        return self.parse_expr_or_assign()

    def parse_multi_var_decl(self, first_type, firstName):
        names = [firstName]
        types = [first_type]
        while self.peek().type == TokenType.COMMA:
            self.advance()
            types.append(self.parse_type())
            names.append(self.expect(TokenType.IDENTIFIER).value)
        self.expect(TokenType.ASSIGN)
        value = self.parse_expression()
        return MultiVarDecl(names, types, value)

    def parse_var_decl_or_assign(self):
        saved = self.pos
        try:
            if self.peek().type == TokenType.LBRACKET:
                self.advance()
                self.expect(TokenType.RBRACKET)
                elem_type = self.parse_type()
                var_type = ArrayTypeNode(elem_type)
                name = self.expect(TokenType.IDENTIFIER).value
            else:
                var_type = self.parse_type()
                name = self.expect(TokenType.IDENTIFIER).value

            if self.peek().type == TokenType.COMMA:
                return self.parse_multi_var_decl(var_type, name)

            if self.peek().type == TokenType.LPAREN:
                self.advance()
                func_params = []
                self.skip_newlines()
                if self.peek().type != TokenType.RPAREN:
                    while True:
                        func_params.append(self.parse_type())
                        self.skip_newlines()
                        if self.peek().type == TokenType.COMMA:
                            self.advance()
                            self.skip_newlines()
                        else:
                            break
                self.expect(TokenType.RPAREN)
                var_type = FuncTypeNode(var_type, func_params)

            if self.peek().type == TokenType.ASSIGN:
                self.advance()
                value = self.parse_expression()
                return VarDecl(name, var_type, value)
            return VarDecl(name, var_type, None)
        except ParserError:
            self.pos = saved
            return self.parse_expr_or_assign()

    def parse_expr_or_assign(self):
        expr = self.parse_expression()
        if self.peek().type == TokenType.ASSIGN:
            self.advance()
            value = self.parse_expression()
            if isinstance(expr, Identifier):
                return AssignStmt([expr], value)
            return AssignStmt([expr], value)
        if self.peek().type == TokenType.COMMA:
            targets = [expr]
            while self.peek().type == TokenType.COMMA:
                self.advance()
                targets.append(self.parse_expression())
            if self.peek().type == TokenType.ASSIGN:
                self.advance()
                value = self.parse_expression()
                return MultiAssignStmt(targets, value)
            raise ParserError("Expected = after multi-target", self.peek())
        return ExprStmt(expr)

    def parse_if_stmt(self):
        self.advance()
        condition = self.parse_expression()
        self.skip_newlines()
        then_block = self.parse_brace_block()
        elifs = []
        else_block = None
        self.skip_newlines()
        while self.peek().type == TokenType.KEYWORD_ELIF:
            self.advance()
            cond = self.parse_expression()
            self.skip_newlines()
            blk = self.parse_brace_block()
            elifs.append(ElifStmt(cond, blk))
            self.skip_newlines()
        if self.peek().type == TokenType.KEYWORD_ELSE:
            self.advance()
            self.skip_newlines()
            else_block = self.parse_brace_block()
        return IfStmt(condition, then_block, elifs, else_block)

    def parse_for_stmt(self):
        self.advance()

        has_paren = False
        if self.peek().type == TokenType.LPAREN:
            self.advance()
            has_paren = True

        if not has_paren and self.peek().type == TokenType.LBRACE:
            body = self.parse_brace_block()
            return ForStmt(None, None, None, body)

        if self.peek().type == TokenType.IDENTIFIER and self.peek_next(1).type == TokenType.KEYWORD_IN:
            name = self.advance().value
            self.advance()
            iterable = self.parse_expression()
            if has_paren:
                if self.peek().type == TokenType.RPAREN:
                    self.advance()
            body = self.parse_brace_block()
            return ForInStmt(name, iterable, body)

        init = None
        cond = None
        incr = None

        if self.peek().type != TokenType.RPAREN and self.peek().type != TokenType.SEMI:
            if self.peek().type in {
                TokenType.KEYWORD_INT, TokenType.KEYWORD_UINT64,
                TokenType.KEYWORD_FLOAT, TokenType.KEYWORD_FLOAT32,
                TokenType.KEYWORD_FLOAT64,
                TokenType.KEYWORD_STRING, TokenType.KEYWORD_CHAR,
                TokenType.KEYWORD_BOOL,
            }:
                init = self.parse_var_decl_or_assign()
            else:
                expr = self.parse_expression()
                if self.peek().type == TokenType.ASSIGN:
                    self.advance()
                    val = self.parse_expression()
                    init = AssignStmt([expr], val)
                else:
                    cond = expr

        if self.peek().type == TokenType.SEMI:
            self.advance()
            if self.peek().type != TokenType.SEMI and self.peek().type != TokenType.RPAREN:
                cond = self.parse_expression()
            if self.peek().type == TokenType.SEMI:
                self.advance()
                if self.peek().type != TokenType.RPAREN:
                    saved = self.pos
                    try:
                        incr = self.parse_expr_or_assign()
                    except ParserError:
                        self.pos = saved
                        incr = self.parse_expression()

        if self.peek().type == TokenType.RPAREN:
            self.advance()

        body = self.parse_brace_block()
        return ForStmt(init, cond, incr, body)
    def parse_while_stmt(self):
        self.advance()
        cond = self.parse_expression()
        body = self.parse_brace_block()
        return WhileStmt(cond, body)

    def parse_match_stmt(self):
        self.advance()
        expr = self.parse_expression()
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        cases = []
        default_block = None
        while self.peek().type != TokenType.RBRACE and self.peek().type != TokenType.EOF:
            if self.peek().type == TokenType.UNDERSCORE:
                self.advance()
                self.skip_newlines()
                default_block = self.parse_brace_block()
            else:
                pattern = self.parse_expression()
                self.skip_newlines()
                if self.peek().type == TokenType.DOT:
                    enum_name = pattern
                    self.advance()
                    variant = self.expect(TokenType.IDENTIFIER).value
                    if isinstance(enum_name, Identifier):
                        pattern = Identifier(f"{enum_name.name}.{variant}")
                    self.skip_newlines()
                block = self.parse_brace_block()
                cases.append(MatchCase(pattern, block))
            self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return MatchStmt(expr, cases, default_block)

    def parse_return_stmt(self):
        self.advance()
        if self.peek().type in (TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
            return ReturnStmt([])
        values = [self.parse_expression()]
        while self.peek().type == TokenType.COMMA:
            self.advance()
            if self.peek().type in (TokenType.NEWLINE, TokenType.RBRACE):
                break
            values.append(self.parse_expression())
        return ReturnStmt(values)

    def parse_expression(self):
        self.skip_newlines()
        return self.parse_logical_or()

    def parse_logical_or(self):
        left = self.parse_logical_and()
        while self.peek().type == TokenType.KEYWORD_OR:
            self.advance()
            right = self.parse_logical_and()
            left = BinaryOp(left, "or", right)
        return left

    def parse_logical_and(self):
        left = self.parse_equality()
        while self.peek().type == TokenType.KEYWORD_AND:
            self.advance()
            right = self.parse_equality()
            left = BinaryOp(left, "and", right)
        return left

    def parse_equality(self):
        left = self.parse_comparison()
        while self.peek().type in (TokenType.EQ, TokenType.NEQ):
            op = self.advance().value
            right = self.parse_comparison()
            left = BinaryOp(left, op, right)
        return left

    def parse_comparison(self):
        left = self.parse_term()
        while self.peek().type in (TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE):
            op = self.advance().value
            right = self.parse_term()
            left = BinaryOp(left, op, right)
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.peek().type in (TokenType.PLUS, TokenType.MINUS):
            op = self.advance().value
            right = self.parse_factor()
            left = BinaryOp(left, op, right)
        return left

    def parse_factor(self):
        left = self.parse_unary()
        while self.peek().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self.advance().value
            right = self.parse_unary()
            left = BinaryOp(left, op, right)
        return left

    def parse_unary(self):
        if self.peek().type == TokenType.MINUS:
            self.advance()
            operand = self.parse_unary()
            return UnaryOp("-", operand)
        if self.peek().type == TokenType.KEYWORD_NOT:
            self.advance()
            operand = self.parse_unary()
            return UnaryOp("not", operand)
        return self.parse_primary()

    def parse_primary(self):
        tok = self.peek()

        if tok.type == TokenType.NUMBER:
            self.advance()
            return self.parse_postfix(IntLiteral(int(tok.value)))

        if tok.type == TokenType.FLOAT:
            self.advance()
            return self.parse_postfix(FloatLiteral(float(tok.value)))

        if tok.type == TokenType.STRING:
            self.advance()
            return self.parse_postfix(StringLiteral(tok.value))

        if tok.type == TokenType.CHAR:
            self.advance()
            return self.parse_postfix(CharLiteral(tok.value))

        if tok.type == TokenType.IDENTIFIER:
            name = self.advance().value
            if name == "true":
                return self.parse_postfix(BoolLiteral(True))
            if name == "false":
                return self.parse_postfix(BoolLiteral(False))
            if self.peek().type == TokenType.LBRACE and name[0].isupper():
                return self.parse_struct_literal(name)
            return self.parse_postfix(Identifier(name))

        if tok.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expression()
            if self.peek().type == TokenType.COMMA:
                exprs = [expr]
                while self.peek().type == TokenType.COMMA:
                    self.advance()
                    if self.peek().type == TokenType.RPAREN:
                        break
                    exprs.append(self.parse_expression())
                self.expect(TokenType.RPAREN)
                return MultiValueExpr(exprs)
            self.expect(TokenType.RPAREN)
            return self.parse_postfix(ParenExpr(expr))

        if tok.type == TokenType.LBRACKET:
            self.advance()
            self.skip_newlines()
            if self.peek().type == TokenType.RBRACKET:
                self.advance()
                return self.parse_postfix(ArrayLiteral([]))
            elements = [self.parse_expression()]
            self.skip_newlines()
            while self.peek().type == TokenType.COMMA:
                self.advance()
                elements.append(self.parse_expression())
                self.skip_newlines()
            self.skip_newlines()
            self.expect(TokenType.RBRACKET)
            return self.parse_postfix(ArrayLiteral(elements))

        if tok.type == TokenType.LBRACE:
            self.advance()
            if self.peek().type == TokenType.RBRACE:
                self.advance()
                return self.parse_postfix(MapLiteral([]))
            entries = []
            while self.peek().type != TokenType.RBRACE and self.peek().type != TokenType.EOF:
                key = self.parse_expression()
                self.expect(TokenType.COLON)
                value = self.parse_expression()
                entries.append(MapEntry(key, value))
                if self.peek().type == TokenType.COMMA:
                    self.advance()
            self.expect(TokenType.RBRACE)
            return self.parse_postfix(MapLiteral(entries))

        if tok.type in {
            TokenType.KEYWORD_INT, TokenType.KEYWORD_UINT64,
            TokenType.KEYWORD_FLOAT, TokenType.KEYWORD_FLOAT32,
            TokenType.KEYWORD_FLOAT64,
            TokenType.KEYWORD_STRING, TokenType.KEYWORD_CHAR,
            TokenType.KEYWORD_BOOL, TokenType.KEYWORD_VOID,
            TokenType.KEYWORD_FILE,
        }:
            type_name = self.advance().value
            if self.peek().type == TokenType.LBRACE:
                return self.parse_struct_literal(type_name)
            return self.parse_postfix(Identifier(type_name))

        if tok.type == TokenType.KEYWORD_MAP:
            self.advance()
            self.expect(TokenType.LT)
            key_t = self.parse_type()
            self.expect(TokenType.COMMA)
            val_t = self.parse_type()
            self.expect(TokenType.GT)
            if self.peek().type == TokenType.LBRACE:
                self.advance()
                entries = []
                while self.peek().type != TokenType.RBRACE and self.peek().type != TokenType.EOF:
                    key = self.parse_expression()
                    self.expect(TokenType.COLON)
                    value = self.parse_expression()
                    entries.append(MapEntry(key, value))
                    if self.peek().type == TokenType.COMMA:
                        self.advance()
                self.expect(TokenType.RBRACE)
                return self.parse_postfix(MapLiteral(entries))
            return self.parse_postfix(MapLiteral([]))

        raise ParserError(f"Unexpected token: {tok.type} ({tok.value})", tok)

    def parse_struct_literal(self, type_name):
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        fields = []
        while self.peek().type != TokenType.RBRACE and self.peek().type != TokenType.EOF:
            name = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.COLON)
            value = self.parse_expression()
            fields.append(StructFieldInit(name, value))
            if self.peek().type == TokenType.COMMA:
                self.advance()
            self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return StructLiteral(type_name, fields)

    def parse_postfix(self, expr):
        while True:
            tok = self.peek()
            if tok.type == TokenType.LPAREN:
                self.advance()
                args = self.parse_call_args()
                self.skip_newlines()
                self.expect(TokenType.RPAREN)
                expr = CallExpr(expr, args)
            elif tok.type == TokenType.DOT:
                self.advance()
                member = self.expect(TokenType.IDENTIFIER).value
                if self.peek().type == TokenType.LPAREN:
                    self.advance()
                    args = self.parse_call_args()
                    self.expect(TokenType.RPAREN)
                    expr = MethodCallExpr(expr, member, args)
                else:
                    expr = MemberExpr(expr, member)
            elif tok.type == TokenType.LBRACKET:
                self.advance()
                if self.peek().type == TokenType.COLON:
                    self.advance()
                    end = None
                    if self.peek().type != TokenType.RBRACKET:
                        end = self.parse_expression()
                    self.expect(TokenType.RBRACKET)
                    expr = SliceExpr(expr, None, end)
                else:
                    idx = self.parse_expression()
                    if self.peek().type == TokenType.COLON:
                        self.advance()
                        end = None
                        if self.peek().type != TokenType.RBRACKET:
                            end = self.parse_expression()
                        self.expect(TokenType.RBRACKET)
                        expr = SliceExpr(expr, idx, end)
                    else:
                        self.expect(TokenType.RBRACKET)
                        expr = IndexExpr(expr, idx)
            elif tok.type == TokenType.KEYWORD_IN:
                self.advance()
                right = self.parse_expression()
                expr = InExpr(expr, right)
            else:
                break
        return expr

    def parse_call_args(self):
        args = []
        self.skip_newlines()
        if self.peek().type == TokenType.RPAREN:
            return args
        while True:
            args.append(self.parse_expression())
            self.skip_newlines()
            if self.peek().type == TokenType.COMMA:
                self.advance()
                self.skip_newlines()
            else:
                break
        return args

    def peek_next(self, offset=1):
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]
