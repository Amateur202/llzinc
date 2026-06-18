from .token_types import TokenType


class Token:
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.col})"


class LexerError(Exception):
    def __init__(self, message, line, col):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(f"[ZINC][ERROR][{line}, {col}] {message}")


class Lexer:
    def __init__(self, text, filename="<unknown>"):
        self.text = text
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []

    def error(self, msg):
        raise LexerError(msg, self.line, self.col)

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx >= len(self.text):
            return '\0'
        return self.text[idx]

    def advance(self):
        ch = self.text[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def skip_whitespace(self):
        while self.pos < len(self.text) and self.peek() in (' ', '\t', '\r'):
            self.advance()

    def skip_comment(self):
        if self.peek() == '/' and self.peek(1) == '/':
            while self.pos < len(self.text) and self.peek() != '\n':
                self.advance()
        elif self.peek() == '/' and self.peek(1) == '*':
            self.advance()
            self.advance()
            depth = 1
            while self.pos < len(self.text) and depth > 0:
                if self.peek() == '/' and self.peek(1) == '*':
                    self.advance()
                    self.advance()
                    depth += 1
                elif self.peek() == '*' and self.peek(1) == '/':
                    self.advance()
                    self.advance()
                    depth -= 1
                else:
                    self.advance()
            if depth > 0:
                self.error("Unterminated block comment")

    def read_string(self):
        line, col = self.line, self.col
        self.advance()
        result = []
        while self.pos < len(self.text):
            ch = self.peek()
            if ch == '"':
                self.advance()
                return Token(TokenType.STRING, ''.join(result), line, col)
            if ch == '\n':
                self.error("Unterminated string")
            if ch == '\\':
                self.advance()
                esc = self.advance()
                if esc == 'n':
                    result.append('\n')
                elif esc == 't':
                    result.append('\t')
                elif esc == '\\':
                    result.append('\\')
                elif esc == '"':
                    result.append('"')
                elif esc == '0':
                    result.append('\0')
                else:
                    result.append(esc)
            else:
                result.append(self.advance())
        self.error("Unterminated string")

    def read_char(self):
        line, col = self.line, self.col
        self.advance()
        if self.peek() == '\\':
            self.advance()
            esc = self.advance()
            mapping = {'n': '\n', 't': '\t', '\\': '\\', '\'': '\'', '0': '\0'}
            val = mapping.get(esc, esc)
        else:
            val = self.advance()
        if self.peek() != '\'':
            self.error("Expected closing single quote for char")
        self.advance()
        return Token(TokenType.CHAR, val, line, col)

    def read_number(self):
        line, col = self.line, self.col
        result = []
        is_float = False
        while self.pos < len(self.text):
            ch = self.peek()
            if ch.isdigit():
                result.append(self.advance())
            elif ch == '.' and not is_float:
                if self.peek(1) and self.peek(1).isdigit():
                    is_float = True
                    result.append(self.advance())
                else:
                    break
            else:
                break
        val = ''.join(result)
        if is_float:
            if self.peek() == 'f':
                self.advance()
            return Token(TokenType.FLOAT, val, line, col)
        return Token(TokenType.NUMBER, val, line, col)

    def read_identifier(self):
        line, col = self.line, self.col
        result = []
        while self.pos < len(self.text) and (self.peek().isalnum() or self.peek() == '_'):
            result.append(self.advance())
        val = ''.join(result)
        token_type = TokenType.keywords.get(val, TokenType.IDENTIFIER)
        if token_type in (TokenType.KEYWORD_TRUE, TokenType.KEYWORD_FALSE):
            return Token(TokenType.IDENTIFIER, val, line, col)
        return Token(token_type, val, line, col)

    def tokenize(self):
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []

        while self.pos < len(self.text):
            ch = self.peek()

            if ch == '\0':
                break

            if ch in (' ', '\t', '\r'):
                self.skip_whitespace()
                continue

            if ch == '\n':
                self.advance()
                self.tokens.append(Token(TokenType.NEWLINE, '\n', self.line - 1, 1))
                continue

            if ch == '/' and self.peek(1) in ('/', '*'):
                self.skip_comment()
                continue

            if ch == '#':
                while self.pos < len(self.text) and self.peek() != '\n':
                    self.advance()
                continue

            if ch == '"':
                self.tokens.append(self.read_string())
                continue

            if ch == '\'':
                self.tokens.append(self.read_char())
                continue

            if ch.isdigit():
                self.tokens.append(self.read_number())
                continue

            if ch == '_' and not (self.peek(1) and (self.peek(1).isalnum() or self.peek(1) == '_')):
                self.advance()
                self.tokens.append(Token(TokenType.UNDERSCORE, '_', self.line, self.col - 1))
                continue

            if ch.isalpha() or ch == '_':
                token = self.read_identifier()
                if token.type == TokenType.KEYWORD_TRUE:
                    self.tokens.append(Token(TokenType.IDENTIFIER, "true", token.line, token.col))
                elif token.type == TokenType.KEYWORD_FALSE:
                    self.tokens.append(Token(TokenType.IDENTIFIER, "false", token.line, token.col))
                else:
                    self.tokens.append(token)
                continue

            if ch == '=':
                if self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.EQ, '==', self.line, self.col - 1))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.ASSIGN, '=', self.line, self.col - 1))
                continue

            if ch == '!':
                if self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.NEQ, '!=', self.line, self.col - 1))
                else:
                    self.error("Expected '=' after '!'")
                continue

            if ch == '<':
                if self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.LE, '<=', self.line, self.col - 1))
                elif self.peek(1) == '<':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.LT, '<<', self.line, self.col - 1))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.LT, '<', self.line, self.col - 1))
                continue

            if ch == '>':
                if self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.GE, '>=', self.line, self.col - 1))
                elif self.peek(1) == '>':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.GT, '>>', self.line, self.col - 1))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.GT, '>', self.line, self.col - 1))
                continue

            if ch == '-':
                if self.peek(1) == '>':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.ARROW, '->', self.line, self.col - 1))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.MINUS, '-', self.line, self.col - 1))
                continue

            single_char_map = {
                '(': TokenType.LPAREN, ')': TokenType.RPAREN,
                '[': TokenType.LBRACKET, ']': TokenType.RBRACKET,
                '{': TokenType.LBRACE, '}': TokenType.RBRACE,
                ',': TokenType.COMMA, '.': TokenType.DOT,
                ':': TokenType.COLON, ';': TokenType.SEMI,
                '+': TokenType.PLUS, '*': TokenType.STAR,
                '/': TokenType.SLASH, '%': TokenType.PERCENT,
                '_': TokenType.UNDERSCORE,
            }

            if ch in single_char_map:
                self.advance()
                self.tokens.append(Token(single_char_map[ch], ch, self.line, self.col - 1))
                continue

            self.error(f"Unexpected character: {ch!r}")

        self.tokens.append(Token(TokenType.EOF, '', self.line, 1))
        return self.tokens
