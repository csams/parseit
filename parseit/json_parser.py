"""
This module handles primitive json parsing. It only vaguely conforms to the
spec.
"""
from parseit import Input
from parseit.optimizer import optimize
from parseit.grammar import (AllWhitespace,
                             Colon,
                             Comma,
                             Forward,
                             Keyword,
                             LeftBracket,
                             LeftCurly,
                             Many,
                             Number,
                             RightBracket,
                             RightCurly,
                             QuotedString)


WS = Many(AllWhitespace)
JsonArray = Forward()
JsonObject = Forward()
TRUE = Keyword("true", True) % "TRUE"
FALSE = Keyword("false", False) % "FALSE"
NULL = Keyword("null", None) % "NULL"
SimpleValue = (QuotedString | Number | JsonObject | JsonArray | TRUE | FALSE | NULL) % "SimpleValue"
JsonValue = (WS >> SimpleValue << WS) % "Json Value"
Key = (QuotedString << Colon) % "Key"
KVPairs = (((WS >> Key) & JsonValue).sep_by(Comma)) % "KVPairs"
JsonObject <= (LeftCurly >> KVPairs.map(lambda res: {k: v for (k, v) in res}) << RightCurly) % "Json Object"
JsonArray <= (LeftBracket >> JsonValue.sep_by(Comma) << RightBracket) % "Json Array"
JsonValue = optimize(JsonValue)


def loads(data):
    return JsonValue(Input(data)).value


def load(f):
    return loads(f.read())


if __name__ == "__main__":
    import sys
    from pprint import pprint

    if len(sys.argv) == 2:
        arg = sys.argv[1]
        if arg == "-":
            data = sys.stdin.read()
        else:
            with open(sys.argv[1]) as f:
                data = f.read()
        pprint(loads(data))
    else:
        print("Pass a file.")
