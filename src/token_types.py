class TokenType:
    EOF = "EOF"
    NEWLINE = "NEWLINE"
    INDENT = "INDENT"
    DEDENT = "DEDENT"

    IDENTIFIER = "IDENTIFIER"
    NUMBER = "NUMBER"
    FLOAT = "FLOAT"
    STRING = "STRING"
    CHAR = "CHAR"

    KEYWORD_INT = "int"
    KEYWORD_UINT64 = "uint64"
    KEYWORD_FLOAT = "float"
    KEYWORD_FLOAT32 = "float32"
    KEYWORD_FLOAT64 = "float64"
    KEYWORD_STRING = "string"
    KEYWORD_CHAR = "char"
    KEYWORD_BOOL = "bool"
    KEYWORD_VOID = "void"
    KEYWORD_TRUE = "true"
    KEYWORD_FALSE = "false"
    KEYWORD_IF = "if"
    KEYWORD_ELIF = "elif"
    KEYWORD_ELSE = "else"
    KEYWORD_FOR = "for"
    KEYWORD_WHILE = "while"
    KEYWORD_RETURN = "return"
    KEYWORD_STRUCT = "struct"
    KEYWORD_ENUM = "enum"
    KEYWORD_MATCH = "match"
    KEYWORD_IMPORT = "import"
    KEYWORD_CONST = "const"
    KEYWORD_REF = "ref"
    KEYWORD_DEFER = "defer"
    KEYWORD_IN = "in"
    KEYWORD_NOT = "not"
    KEYWORD_AND = "and"
    KEYWORD_OR = "or"
    KEYWORD_BREAK = "break"
    KEYWORD_CONTINUE = "continue"
    KEYWORD_DEL = "del"
    KEYWORD_MAP = "map"
    KEYWORD_FILE = "file"
    KEYWORD_EXTERN = "extern"
    KEYWORD_AS = "as"
    KEYWORD_RAISE = "raise"

    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    LBRACE = "{"
    RBRACE = "}"
    COMMA = ","
    DOT = "."
    COLON = ":"
    SEMI = ";"
    ARROW = "->"
    UNDERSCORE = "_"

    ASSIGN = "="
    EQ = "=="
    NEQ = "!="
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"

    keywords = {
        "int": KEYWORD_INT,
        "uint64": KEYWORD_UINT64,
        "float": KEYWORD_FLOAT,
        "float32": KEYWORD_FLOAT32,
        "float64": KEYWORD_FLOAT64,
        "string": KEYWORD_STRING,
        "char": KEYWORD_CHAR,
        "bool": KEYWORD_BOOL,
        "void": KEYWORD_VOID,
        "true": KEYWORD_TRUE,
        "false": KEYWORD_FALSE,
        "if": KEYWORD_IF,
        "elif": KEYWORD_ELIF,
        "else": KEYWORD_ELSE,
        "for": KEYWORD_FOR,
        "while": KEYWORD_WHILE,
        "return": KEYWORD_RETURN,
        "struct": KEYWORD_STRUCT,
        "enum": KEYWORD_ENUM,
        "match": KEYWORD_MATCH,
        "import": KEYWORD_IMPORT,
        "const": KEYWORD_CONST,
        "ref": KEYWORD_REF,
        "defer": KEYWORD_DEFER,
        "in": KEYWORD_IN,
        "not": KEYWORD_NOT,
        "and": KEYWORD_AND,
        "or": KEYWORD_OR,
        "break": KEYWORD_BREAK,
        "continue": KEYWORD_CONTINUE,
        "del": KEYWORD_DEL,
        "map": KEYWORD_MAP,
        "file": KEYWORD_FILE,
        "extern": KEYWORD_EXTERN,
        "as": KEYWORD_AS,
        "raise": KEYWORD_RAISE,
    }
