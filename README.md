# parseit
parseit is a small library for parsing simple, context free grammars or
grammars requiring knowledge of indentation.

The design is top down recursive decent with backtracking. Fancy optimizations
like packrat are not implemented since the goal is a library under 500 lines
that's still sufficient for describing small, non-standard configuration files.
Just use standard parsers for things like xml or yaml.

## Primitives
The building blocks for matching individual characters, sets of characters, and
a few convenient objects like numbers. All matching is case sensitive.

### Char
Match a single character.
```python
a = Char("a")     # parses a single "a"
val = a("a")      # produces an "a" from the data.
val = a("b")      # raises an exception
```

### InSet
Match any single character in a set.
```python
vowel = InSet("aeiou")  # or InSet(set("aeiou"))
val = vowel("a")  # okay
val = vowel("e")  # okay
val = vowel("i")  # okay
val = vowel("o")  # okay
val = vowel("u")  # okay
val = vowel("y")  # raises an exception
```

### String
Match zero or more characters in a set. Matching is greedy.
```python
vowels = String("aeiou")
val = vowels("a")
val = vowels("u")
val = vowels("aaeiouuoui")
val = vowels("uoiea")
val = vowels("oouieaaea")
val = vowels("ga") # raises an exception
```

### Literal
Match a literal string.
```python
lit = Literal("true")
val = lit("true")
val = lit("True")  # raises an exception
val = lit("anything else") # raises an exception
```

### Keyword
Match a literal string but return a python value for it instead of the string
itself.
```python
t = Keyword("true", True)
f = Keyword("true", True)
val = t("true")  # returns the boolean True
val = f("false") # returns the boolean False
```

### Number
Match a possibly negative integer or simple floating point number. Returns the
python int or float for it.
```python
val = Number("123")  # returns 123
val = Number("-12")  # returns -12
val = Number("12.4")  # returns 12.4
val = Number("-12.4")  # returns -12.4
```

parseit also provides SingleQuotedString, DoubleQuotedString, QuotedString, EOL,
EOF, WS, AnyChar, Nothing, and several other primitives. See parseit/__init__.py

## Combinators
parseit provides several ways of combining primitives and their combinations.

### Sequencing
Require expressions to be in an order.
```python
a = Char("a")     # parses a single "a"
b = Char("b")     # parses a single "b"
c = Char("c")     # parses a single "c"

ab = a + b        # parses a single "a" followed by a single "b"
abc = a + b + c   # parses "abc"

val = ab("ab")    # produces a list ["a", "b"]
val = ab("a")     # raises an exception
val = ab("b")     # raises an exception
val = ab("ac")    # raises an exception
val = ab("cb")    # raises an exception

val = abc("abc")  # produces ["a", "b", "c"]
```

### Choice
Accept one of a list of alternatives.
```python
abc = a | b | c   # alternation or choice.
val = abc("a")    # parses a single "a"
val = abc("b")    # parses a single "b"
val = abc("c")    # parses a single "c"
val = abc("d")    # raises an exception
```

### Many
Match zero or more occurences of an expression. Matching is greedy.
```python
x = Char("x")
xs = Many(x)      # parses many (or no) x's in a row
val = xs("")      # returns []
val = xs("a")     # returns []
val = xs("x")     # returns ["x"]
vxl = xs("xxxxx") # returns ["x", "x", "x", "x", "x"]
val = xs("xxxxb") # returns ["x", "x", "x", "x"]

ab = Many(a + b)  # parses "abab..."
val = ab("")      # produces []
val = ab("ab")    # produces ["a", b"]
val = ab("ba")    # produces []
val = ab("abab")  # produces ["a", b", "a", "b"]

ab = Many(a | b)  # parses any combination of "a" and "b" like "aababbaba..."
val = ab("aababb")# produces ["a", "a", "b", "a", "b", "b"]
```

### Followed by
Require an expression to be followed by another, but don't consume the input
that matches the latter expression.
```python
ab = Char("a") & Char("b") # matches an "a" followed by a "b", but the "b"
                           # isn't consumed from the input.
val = ab("ab")             # returns "a" and leaves "b" to be consumed.
val = ab("ac")             # raises an exception and doesn't consume "a".
```

### Not followed by
Require an expression to *not* be followed by another.
```python
anb = Char("a") / Char("b") # matches an "a" not followed by a "b".
val = anb("ac")             # returns "a" and leaves "c" to be consumed
val = anb("ab")             # raises an exception and doesn't consume "a".
```

### Keep Left / Keep Right
`KeepLeft` (`<<`) and `KeepRight` (`>>`) match adjacent expressions but ignore
one of their results.
```python
a = Char("a")
q = Char('"')

qa = a << q      # like a + q except only the result of a is returned
val = qa('a"')   # returns "a". Keeps the thing on the left of the << 

qa = q >> a      # like q + a except only the result of a is returned
val = qa('"a')   # returns "a". Keeps the thing on the right of the >> 

qa = q >> a << q # like q + a + q except only the result of the a is returned
val = qa('"a"')  # returns "a".
```

### Opt
`Opt` always succeeds. A default value can be provided for when the parser it
wraps doesnt match anything. The default is `None` if one isn't provided.
```python
a = Char("a")
o = Opt(a)      # matches an "a" if its available. Still succeeds otherwise but
                # doesn't advance the read pointer.
val = o("a")    # returns "a"
val = o("b")    # returns None
```

### map
All parsers have a `.map` function that allows you to pass a function to
evaluate the input they've matched.
```python
def to_number(val):
    # val is like [non_zero_digit, [other_digits]]
    first, rest = val
    s = first + "".join(rest)
    return int(s)

m = NonZeroDigit + Many(Digit)  # returns [nzd, [other digits]]
n = m.map(to_number)  # converts the match to an actual integer
val = n("15")  # returns the int 15
```

### Lift
Allows a multiple parameter function to work on parsers.
```python
def comb(a, b, c):
    """ a, b, and c should be strings. Returns their concatenation."""
    return "".join([a, b, c])

# You'd normally invoke comb like comb("x", "y", "z"), but you can "lift" it for
# use with parsers like this:

x = Char("x")
y = Char("y")
z = Char("z")
p = Lift(comb) * x * y * z

# The * operator separates parsers whose results will go into the arguments of
# the lifted function. I've used Char above, but x, y, and z can be arbitrarily
# complex.

val = p("xyz")  # would return "xyz"
val = p("xyx")  # raises an exception. nothing would be consumed
```

### Forward
`Forward` allows recursive grammars where a nonterminal's definition includes
itself directly or indirectly. Here's an arithmetic parser that ties several
concepts together.
```python
def op(args):
   ans, rest = args
   for op, arg in rest:
       if op == "+":
           ans += arg
       elif op == "-":
           ans -= arg
       elif op == "*":
           ans *= arg
       elif op == "/":
           ans /= arg
   return ans

expr = Forward()
factor = (Number | (LeftParen >> expr << RightParen))
term = (factor + Many((Char("*") | Char("/")) + factor)).map(op)
expr <= (term + Many((Char("+") | Char("-")) + term)).map(op)

# Notice that expr is initially declared as "Forward" and the "<=" operator is
# then used to assign the actual definition.

val = expr("2*(3+4)/3+4")  # returns 8.666666666666668
```

### WithIndent
This is the "context sensitive" part of the library. The `WithIndent` class
wraps a parser and provides it and all of its subparsers with context about
indentation of the first encountered line. If the WithIndent instance is used in
a recursive definition, the stack of indents is maintained and made available to
all active parsers participating in the recursion. Refer to
parseit/iniparser.py for an example.
