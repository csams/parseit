"""
parseit is a small library for parsing simple, context free grammars or
grammars requiring knowledge of indentation.

The design is top down recursive decent with backtracking. Fancy optimizations
like packrat are not implemented since the goal is a library under 500 lines
that's still sufficient for describing small, non-standard configuration files.
If some file is yaml, xml, or json, just use the standard parsers.
"""
import string
from bisect import bisect_left
from io import StringIO


class Node:
    """
    Node is a simple tree structure that helps with rendering grammars.
    """
    def __init__(self):
        self.children = []

    def add_child(self, child):
        self.children.append(child)
        return self

    def set_children(self, children):
        self.children.clear()
        for c in children:
            self.add_child(c)
        return self

    def __repr__(self):
        return self.__class__.__name__


def text_format(tree):
    """ Formats a tree with indentation. """
    out = StringIO()
    tab = " " * 2
    seen = set()

    def inner(cur, prefix):
        print(prefix + str(cur), file=out)
        if cur in seen:
            return

        seen.add(cur)

        next_prefix = prefix + tab
        for c in cur.children:
            inner(c, next_prefix)

    inner(tree, "")
    out.seek(0)
    return out.read()


def render(tree):
    """ Helper that prints a tree with indentation. """
    print(text_format(tree))


class Ctx:
    def __init__(self, lines):
        self.error_pos = -1
        self.error_msg = None
        self.indents = []
        self.lines = [i for i, x in enumerate(lines) if x == "\n"]

    def set(self, pos, msg):
        if pos >= self.error_pos:
            self.error_pos = pos
            self.error_msg = msg

    def line(self, pos):
        return bisect_left(self.lines, pos)

    def col(self, pos):
        p = self.line(pos)
        if p == 0:
            return pos
        return (pos - self.lines[p - 1] - 1)


class Parser(Node):
    def __init__(self):
        super().__init__()
        self.name = None

    def map(self, func):
        return Map(self, func)

    @staticmethod
    def accumulate(first, rest):
        results = [first] if first else []
        if rest:
            results.extend(rest)
        return results

    def sep_by(self, sep):
        return Lift(self.accumulate) * Opt(self) * Many(sep >> self)

    def __or__(self, other):
        return Choice(self, other)

    def __and__(self, other):
        return FollowedBy(self, other)

    def __truediv__(self, other):
        return NotFollowedBy(self, other)

    def __add__(self, other):
        return Seq(self, other)

    def __lshift__(self, other):
        return KeepLeft(self, other)

    def __rshift__(self, other):
        return KeepRight(self, other)

    def __mod__(self, name):
        self.name = name
        return self

    def __call__(self, data):
        data = list(data)
        data.append(None)  # add a terminal so we don't overrun
        ctx = Ctx(data)
        try:
            _, ret = self.process(0, data, ctx)
            return ret
        except Exception:
            lineno = ctx.line(ctx.error_pos) + 1
            colno = ctx.col(ctx.error_pos) + 1
            raise Exception(f"At line {lineno} column {colno}: {ctx.error_msg}")

    def __repr__(self):
        return self.name or f"{self.__class__.__name__}"


class Choice(Parser):
    def __init__(self, left, right):
        super().__init__()
        self.set_children([left, right])

    def __or__(self, other):
        return self.add_child(other)

    def process(self, pos, data, ctx):
        ex = None
        for c in self.children:
            try:
                return c.process(pos, data, ctx)
            except Exception as e:
                ex = e
        raise ex


class Seq(Parser):
    def __init__(self, left, right):
        super().__init__()
        self.set_children([left, right])

    def __add__(self, other):
        return self.add_child(other)

    def process(self, pos, data, ctx):
        results = []
        for p in self.children:
            pos, res = p.process(pos, data, ctx)
            results.append(res)
        return pos, results


class Many(Parser):
    def __init__(self, p):
        super().__init__()
        self.add_child(p)

    def process(self, pos, data, ctx):
        results = []
        p = self.children[0]
        while True:
            try:
                pos, res = p.process(pos, data, ctx)
                results.append(res)
            except Exception:
                break
        return pos, results


class FollowedBy(Parser):
    def __init__(self, p, f):
        super().__init__()
        self.set_children([p, f])

    def process(self, pos, data, ctx):
        left, right = self.children
        new, res = left.process(pos, data, ctx)
        try:
            right.process(new, data, ctx)
        except Exception:
            raise
        else:
            return new, res


class NotFollowedBy(Parser):
    def __init__(self, p, f):
        super().__init__()
        self.set_children([p, f])

    def process(self, pos, data, ctx):
        left, right = self.children
        new, res = left.process(pos, data, ctx)
        try:
            right.process(new, data, ctx)
        except Exception:
            return new, res
        else:
            raise Exception(f"{right} can't follow {left}")


class KeepLeft(Parser):
    def __init__(self, left, right):
        super().__init__()
        self.set_children([left, right])

    def process(self, pos, data, ctx):
        left, right = self.children
        pos, res = left.process(pos, data, ctx)
        pos, _ = right.process(pos, data, ctx)
        return pos, res


class KeepRight(Parser):
    def __init__(self, left, right):
        super().__init__()
        self.set_children([left, right])

    def process(self, pos, data, ctx):
        left, right = self.children
        pos, _ = left.process(pos, data, ctx)
        pos, res = right.process(pos, data, ctx)
        return pos, res


class Opt(Parser):
    def __init__(self, p, default=None):
        super().__init__()
        self.set_children([p])
        self.default = default

    def process(self, pos, data, ctx):
        try:
            return self.children[0].process(pos, data, ctx)
        except Exception:
            return pos, self.default


class Map(Parser):
    def __init__(self, p, func):
        super().__init__()
        self.add_child(p)
        self.func = func

    def process(self, pos, data, ctx):
        pos, res = self.children[0].process(pos, data, ctx)
        return pos, self.func(res)

    def __repr__(self):
        return f"Map({self.func})"


class Lift(Parser):
    def __init__(self, func):
        super().__init__()
        self.func = func

    def __mul__(self, other):
        return self.add_child(other)

    def process(self, pos, data, ctx):
        results = []
        for c in self.children:
            pos, res = c.process(pos, data, ctx)
            results.append(res)
        return pos, self.func(*results)


class Forward(Parser):
    def __init__(self):
        super().__init__()
        self.delegate = None

    def __le__(self, delegate):
        self.set_children([delegate])

    def process(self, pos, data, ctx):
        return self.children[0].process(pos, data, ctx)


class WithIndent(Parser):
    def __init__(self, p):
        super().__init__()
        self.parser = p

    def process(self, pos, data, ctx):
        new, _ = WS.process(pos, data, ctx)
        try:
            ctx.indents.append(ctx.col(new))
            return self.parser.process(new, data, ctx)
        finally:
            ctx.indents.pop()


class Nothing(Parser):
    def process(self, pos, data, ctx):
        return pos, None


class EOF(Parser):
    def process(self, pos, data, ctx):
        if data[pos] is None:
            return pos, None
        msg = "Expected end of input."
        ctx.set(pos, msg)
        raise Exception(msg)


class Char(Parser):
    def __init__(self, char):
        super().__init__()
        self.char = char

    def process(self, pos, data, ctx):
        if data[pos] == self.char:
            return (pos + 1, self.char)
        msg = f"Expected {self.char}."
        ctx.set(pos, msg)
        raise Exception(msg)

    def __repr__(self):
        return f"Char('{self.char}')"


class InSet(Parser):
    def __init__(self, s, name=None):
        super().__init__()
        self.values = set(s)
        self.name = name

    def process(self, pos, data, ctx):
        c = data[pos]
        if c in self.values:
            return (pos + 1, c)
        msg = f"Expected {self}."
        ctx.set(pos, msg)
        raise Exception()


class Literal(Parser):
    def __init__(self, chars):
        super().__init__()
        self.chars = chars

    def process(self, pos, data, ctx):
        old = pos
        for c in self.chars:
            if data[pos] == c:
                pos += 1
            else:
                msg = f"Expected {self.chars}."
                ctx.set(old, msg)
                raise Exception(msg)
        return pos, self.chars


class Keyword(Literal):
    def __init__(self, chars, value):
        super().__init__(chars)
        self.value = value

    def process(self, pos, data, ctx):
        pos, _ = super().process(pos, data, ctx)
        return pos, self.value


class String(Parser):
    def __init__(self, chars, echars=None):
        super().__init__()
        self.chars = set(chars)
        self.echars = set(echars) if echars else set()

    def process(self, pos, data, ctx):
        results = []
        p = data[pos]
        old = pos
        while p in self.chars or p == "\\":
            if p == "\\" and data[pos + 1] in self.echars:
                results.append(data[pos + 1])
                pos += 2
            elif p in self.chars:
                results.append(p)
                pos += 1
            else:
                break
            p = data[pos]
        if not results:
            msg = f"Expected one of {self.chars}."
            ctx.set(old, msg)
            raise Exception(msg)
        return pos, "".join(results)


class EnclosedComment(Parser):
    def __init__(self, s, e):
        super().__init__()
        Start = Literal(s)
        End = Literal(e)
        p = (Start + Many(AnyChar / End) + AnyChar + End).map(self.combine)
        self.add_child(p)

    @staticmethod
    def combine(c):
        return c[0] + "".join(c[1]) + "".join(c[2:])

    def process(self, pos, data, ctx):
        return self.children[0].process(pos, data, ctx)


class OneLineComment(Parser):
    def __init__(self, s):
        super().__init__()
        Start = Literal(s)
        End = EOL | EOF
        p = ((Start + Many(AnyChar / End) + Opt(AnyChar) + End) | (Start + End)).map(self.combine)
        self.add_child(p)

    @staticmethod
    def combine(c):
        c = [i for i in c if i]
        if len(c) == 2:
            return "".join(c)
        c[1] = "".join(c[1])
        return "".join(c)

    def process(self, pos, data, ctx):
        return self.children[0].process(pos, data, ctx)


def make_number(sign, int_part, frac_part):
    tmp = sign + int_part + ("".join(frac_part) if frac_part else "")
    return float(tmp) if "." in tmp else int(tmp)


Nothing = Nothing()
EOF = EOF()
EOL = InSet("\n\r") % "EOL"

LeftCurly = Char("{")
RightCurly = Char("}")
LeftBracket = Char("[")
RightBracket = Char("]")
LeftParen = Char("(")
RightParen = Char(")")
Colon = Char(":")
SemiColon = Char(";")
Comma = Char(",")

AnyChar = InSet(string.printable) % "Any Char"
Digit = InSet(string.digits) % "Digit"
Digits = String(string.digits) % "Digits"
WSChar = InSet(set(string.whitespace) - set("\n\r")) % "Whitespace"
WS = Many(InSet(string.whitespace)) % "Whitespace"
Number = (Lift(make_number) * Opt(Char("-"), "") * Digits * Opt(Char(".") + Digits)) % "Number"

SingleQuotedString = Char("'") >> String(set(string.printable) - set("'"), "'") << Char("'")
DoubleQuotedString = Char('"') >> String(set(string.printable) - set('"'), '"') << Char('"')
QuotedString = (DoubleQuotedString | SingleQuotedString) % "Quoted String"
