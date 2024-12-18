import sys
import re
import yaml

class ParseError(Exception):
    pass

# Токены
TOKEN_TABLE = 'TABLE'
TOKEN_LPAREN = 'LPAREN'
TOKEN_RPAREN = 'RPAREN'
TOKEN_LBRACK = 'LBRACK'
TOKEN_RBRACK = 'RBRACK'
TOKEN_NAME = 'NAME'
TOKEN_NUMBER = 'NUMBER'
TOKEN_STRING = 'STRING'
TOKEN_EQUAL = 'EQUAL'
TOKEN_COMMA = 'COMMA'
TOKEN_SEMI = 'SEMI'
TOKEN_QUESTION = 'QUESTION'  # для ?{
TOKEN_LBRACE = 'LBRACE'
TOKEN_RBRACE = 'RBRACE'
TOKEN_TRUE = 'TRUE'
TOKEN_FALSE = 'FALSE'
TOKEN_EOF = 'EOF'

class Token:
    def __init__(self, ttype, value, pos):
        self.ttype = ttype
        self.value = value
        self.pos = pos
    def __repr__(self):
        return f"Token({self.ttype}, {self.value}, pos={self.pos})"

def remove_multiline_comments(text):
    # Удаляем все многострочные комментарии <# ... #>
    return re.sub(r"<#.*?#>", "", text, flags=re.DOTALL)

def tokenize(text):

    token_specification = [
        ('TABLE',   r'table'),
        ('LBRACK',  r'\['),
        ('RBRACK',  r'\]'),
        ('LPAREN',  r'\('),
        ('RPAREN',  r'\)'),
        ('EQUAL',   r'='),
        ('COMMA',   r','),
        ('SEMI',    r';'),
        ('TRUE',    r'true'),
        ('FALSE',   r'false'),
        ('QMARK',   r'\?\{'),  # начало подстановки ?{
        ('RBRACE',  r'\}'),
        ('STRING',  r'"[^"]*"'),  # строка в кавычках
        ('NUMBER',  r'[0-9]+'),
        ('NAME',    r'[a-z_]+'),
        ('SKIP',    r'[ \t\r\n]+'),  # пробелы и переводы строк
    ]
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    pos = 0
    tokens = []
    mo = re.compile(tok_regex).match
    line = text
    while pos < len(line):
        m = mo(line, pos)
        if m:
            typ = m.lastgroup
            val = m.group(typ)
            if typ == 'SKIP':
                pass
            elif typ == 'QMARK':
                # Это начало подстановки ?{NAME}
                # Нам нужно дочитать до закрывающей '}'
                # Но мы уже нашли ?{ отдельно. Следующий токен должен быть NAME, потом RBRACE
                tokens.append(Token('QUESTION', '?{', pos))
            else:
                tokens.append(Token(typ, val, pos))
            pos = m.end()
        else:
            raise ParseError(f"Unexpected character at pos {pos}: {line[pos:]}")
    tokens.append(Token(TOKEN_EOF, '', pos))
    return tokens

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.constants = {}

    def current_token(self):
        return self.tokens[self.pos]

    def eat(self, ttype=None):
        # Прочитать текущий токен и перейти к следующему
        token = self.current_token()
        if ttype and token.ttype != ttype:
            raise ParseError(f"Expected token {ttype}, got {token.ttype} at pos {token.pos}")
        self.pos += 1
        return token

    def peek(self, ttype):
        return self.current_token().ttype == ttype

    def parse_config(self):
        # config := (constant_decl)* table_expr
        while self.peek(TOKEN_NAME):
            # Может быть объявление константы
            # Смотрим вперед: NAME '=' value ';'?
            # Если нет ';', значит это не константа
            # Попытаемся парсить как константу
            # Если не получится - выходим
            pos_save = self.pos
            try:
                self.parse_constant_decl()
            except ParseError:
                self.pos = pos_save
                break
        # После констант должен идти table_expr
        result = self.parse_table_expr()
        return result

    def parse_constant_decl(self):
        # constant_decl := NAME '=' value ';'
        name_t = self.eat(TOKEN_NAME)
        self.eat(TOKEN_EQUAL)
        val = self.parse_value()
        semi = self.eat(TOKEN_SEMI)
        # Сохраняем константу
        self.constants[name_t.value] = val

    def parse_table_expr(self):
        # table_expr := 'table' '(' '[' pairs ']' ')'
        self.eat('TABLE')
        self.eat('LPAREN')
        self.eat('LBRACK')
        pairs = self.parse_pairs()
        self.eat('RBRACK')
        self.eat('RPAREN')
        return pairs

    def parse_pairs(self):
        # pairs := (pair (',' pair)*)?
        if self.peek(TOKEN_NAME):
            pair = self.parse_pair()
            result = {pair[0]: pair[1]}
            while self.peek('COMMA'):
                self.eat('COMMA')
                p = self.parse_pair()
                if p[0] in result:
                    raise ParseError(f"Duplicate key {p[0]} in table")
                result[p[0]] = p[1]
            return result
        else:
            # пустой словарь
            return {}

    def parse_pair(self):
        # pair := NAME '=' value
        name_t = self.eat(TOKEN_NAME)
        self.eat('EQUAL')
        val = self.parse_value()
        return (name_t.value, val)

    def parse_value(self):
        # value := NUMBER | STRING | 'true' | 'false' | table_expr | substituted_value
        token = self.current_token()
        if token.ttype == TOKEN_NUMBER:
            self.eat(TOKEN_NUMBER)
            return int(token.value)
        elif token.ttype == TOKEN_STRING:
            self.eat(TOKEN_STRING)
            # Уберём кавычки
            return token.value.strip('"')
        elif token.ttype == TOKEN_TRUE:
            self.eat(TOKEN_TRUE)
            return True
        elif token.ttype == TOKEN_FALSE:
            self.eat(TOKEN_FALSE)
            return False
        elif token.ttype == 'TABLE':
            return self.parse_table_expr()
        elif token.ttype == 'QUESTION':
            # substituted_value := '?{' NAME '}'
            self.eat('QUESTION') # съедаем '?{'
            name_t = self.eat(TOKEN_NAME)
            self.eat('RBRACE') # '}'
            # Подставляем значение из constants
            if name_t.value not in self.constants:
                raise ParseError(f"Undefined constant {name_t.value}")
            const_val = self.constants[name_t.value]
            # const_val уже должен быть конечным значением (int, bool, str, dict)
            return const_val
        else:
            raise ParseError(f"Unexpected token {token.ttype} in value at pos {token.pos}")

def main():
    text = sys.stdin.read()
    # Удаляем многострочные комментарии
    text = remove_multiline_comments(text)

    tokens = tokenize(text)
    parser = Parser(tokens)
    result = parser.parse_config()

    # Выводим в YAML
    print(yaml.dump(result, allow_unicode=True, sort_keys=False))

if __name__ == "__main__":
    main()
