from koi.translators import text_search_normalize
from sqlalchemy import and_,or_,not_
from datetime import date
from koi.date_utils import _last_moment_of_previous_month,_last_moment_of_month,_first_moment_of_month,month_before
from koi.date_parser import SimpleDateParser
from koi.base_logging import mainlog


date_parser = SimpleDateParser()

# Common key words. Upper case when it makes sense.
# The following keywords are simple enough that they don't require any
# interpretation logic.

basic_reserved = {
    'AFTER' : 'AFTER',
    'BEFORE' : 'BEFORE',
    'MONTHBEFORE' : 'MONTH_BEFORE',
    'CURRENTMONTH' : 'CURRENT_MONTH',
    'TRUE' : 'TRUE',
    'FALSE' : 'FALSE',
    'OR' : 'OR',
    'IN' : 'IN',
    'AND' : 'AND',
    'IS' : 'IS',
    'STRING' :'STRING' }

basic_tokens = [ 'SPACER',  'COMMA', 'EQUALS','LEFT_PAREN','RIGHT_PAREN', 'GT', 'LT',
                 'FLOAT', 'DATE', 'TILDE' ]

t_COMMA = ','
t_LEFT_PAREN = '\('
t_RIGHT_PAREN = '\)'


# def t_TRUE(t):
#     'TRUE'
#     return t

# def t_FALSE(t):
#     'FALSE'
#     return t

# def t_MONTH_BEFORE(t):
#     'MONTHBEFORE'
#     return t

# def t_CURRENT_MONTH(t):
#     'CURRENTMONTH'
#     return t


# def t_AFTER(t):
#     'AFTER'
#     return t

# def t_BEFORE(t):
#     'BEFORE'
#     return t

# def t_IN(t):
#     'IN'
#     return t

# def t_IS(t):
#     'IS'
#     return t


# def t_AND(t):
#     'AND'
#     return t

# def t_OR(t):
#     'OR'
#     return t

def t_TILDE(t):
    '~'
    return t

def t_SPACER(t):
    '[ ]+'
    t.lexer.skip(0)

def t_DATE(t):
    r'[0-9]+/[0-9]+/[0-9]{4}'

    p = date_parser.parse(t.value)
    if p:
        t.value = p
        return t
    else:
        raise ParserException(_("the date you provided ({}) is not valid".format(t.value)), t.lexpos)

def t_FLOAT(t):
    r'[0-9]+((\.|,)[0-9]+)?'
    t.value = float(t.value)
    return t

def t_GT(t):
    r'>'
    t.value = lambda a,b: a > b
    return t

def t_LT(t):
    r'<'
    t.value = lambda a,b: a < b
    return t

def t_EQUALS(t):
    r'='
    t.value = lambda a,b: a == b
    t.length = 1
    return t


def t_STRING(x):
    r'\w+|"[^"]+"'

    #MAtch T.A.C. ? FIXME !
    # !!! THIS WILL MATCH NUMBERS TOO !!! FIXME I need to add a number token
    # \D == [^0-9]

    if x.value[0] == '"' and x.value[-1] == '"':
        x.length = len(x.value)
        x.value = x.value[1:-1]

    return x

def t_error(t):
    raise ParserException(_("syntax error"), t.lexpos)
    # t.lexer.skip(1)


def p_error(p):
    mainlog.debug("Parsing Error : {}".format(p))
    if p:
        mainlog.debug("Parsing Error : lexpos: {}".format(p.lexer.lexpos))
        mainlog.debug("Parsing Error : yacc.token: {}".format(p.lexer.token()))

    if not p:
        raise ParserException(_("parsing error"))
    else:
        raise ParserException(_("parsing error"),p.lexer.lexpos)








def p_and_expression(p):
    ''' bool_expression : bool_expression AND term '''

    p[0] = and_(p[1],p[3])

def p_or_expression(p):
    ''' bool_expression : bool_expression OR term '''
    # p[0] = p[1] + " || " + p[3]

    p[0] = or_(p[1],p[3])

def p_term_parenthesis(p):
    ''' term : LEFT_PAREN bool_expression RIGHT_PAREN'''
    # p[0] = "(" + str(p[2]) + ")"
    p[0] = p[2]


def p_date_after_expression(p):
    ''' date_after_expression : date_term AFTER date_term
                          | date_term GT date_term '''
    p[0] = p[1] > p[3]


def p_date_before_expression(p):
    ''' date_before_expression : date_term BEFORE date_term
                           | date_term LT date_term'''
    p[0] = p[1] < p[3]


def p_date_in_period_expression(p):
   ''' date_in_period_expression : date_term IN period_term '''

   p[0] = and_(p[1] != None, p[1].between(p[3][0], p[3][1]))



def p_date_term_encoded(p):
    ''' date_term : DATE '''

    p[0] =  p[1]


def p_period_term(p):
   ''' period_term : LEFT_PAREN DATE COMMA DATE RIGHT_PAREN '''

   p[0] = ( p[2], p[4] )

def p_period_function_month_term(p):
   ''' period_term : MONTH_BEFORE '''

   d = month_before(date.today())

   p[0] = ( _first_moment_of_month(d), _last_moment_of_month(d) )
   mainlog.debug(p[0])

def p_period_function_current_month_term(p):
   ''' period_term : CURRENT_MONTH '''

   d = date.today()
   p[0] = ( _first_moment_of_month(d), _last_moment_of_month(d) )
   mainlog.debug("CurrentMonth")
   mainlog.debug(p[0])



def p_string_list(p):
    ''' list : STRING'''

    p[0] = [ p[1] ]


def p_string_list_l(p):
    ''' list : list COMMA STRING'''

    p[0] = [ p[3] ] + p[1]


def p_term(p):
    ''' term : date_after_expression
               | date_before_expression
               | date_in_period_expression '''
    p[0] = p[1]

def p_string_eql_term(p):
    ''' term : text_term EQUALS STRING'''
    p[0] = p[1] == text_search_normalize(p[3])

def p_string_tilde_term(p):
    ''' term : text_term TILDE STRING'''
    p[0] = p[1].like(u"%{}%".format(text_search_normalize(p[3])))

def p_in_list_term(p):
    ''' term : text_term IN list'''
    p[0] = apply_ilikes( [text_search_normalize(term) for term in p[3]],
                         p[1])




class ParserException(Exception):
    def __init__(self, nature_error, lexpos=0, completions = []):
        super(ParserException,self).__init__()

        self.text = nature_error
        self.lexpos = lexpos
        self.suggestions = completions
        self.string = ""

    def __str__(self):

        if self.suggestions:
            return _("Parsing failed for text : {} {}, possible completions are : {}".format(self.text,self.lexpos,self.suggestions))
        else:
            return _("Parsing failed for text : {} {}".format(self.text, self.lexpos))


def tokens_ends_with(tokens, end):
    if len(tokens) < len(end):
        return False
    else:
        if tokens[-1].type == '$end':
            tokens = tokens[0:-1]

        for i in range(1,1+len(end)):
            if tokens[-i].type != end[-i]:
                return False
        return True


def token_length(t):
    if hasattr(t,"length"):
        return t.length
    else:
        return len(t.value)

def word_at_point(t,pos):
    if not t or pos < 0 or pos >= len(t):
        return None,None,None

    end = start = pos

    # while t[pos] == ' ' and pos > 0:
    #     pos = pos -1

    if t[pos] == ' ':
        return None,None,None

    if end == len(t) and len(t) > 0:
        end = len(t) - 1

    while start > 0 and t[start - 1] != ' ':
        start = start - 1

    while end < len(t) - 1 and t[end + 1] != ' ':
        end = end + 1

    return t[start:end+1],start,end+1


def apply_ilikes(names,column):
    # bvb : apply_ilikes( ['alpha','omega'] , OrderPart.indexed_description)

    if len(names) == 1:
        return column.like(u"%{}%".format(names[0]))
    elif len(names) > 1:
        return or_(column.like(u"%{}%".format(names[0])), apply_ilikes(names[0:-1], column) )
    else:
        raise Exception("This will work only on non empty names lists.")

def find_suggestions(s,cursor_position,lexer,parser,suggestions_generator):
    """ returns :
    * replacement_area : a (action, start index,stop index) tuple representing where
    the suggestion might fit in the original s string. action is always "rep"
    for the moment.
    * s : an array with all possible suggestions
    """

    mainlog.debug(u"Finding suggestions for :'{}'".format(s))
    mainlog.debug(u"Finding suggestions for :'{}^".format(" "*cursor_position))

    # But we keep the spaces
    s = s.upper()

    lexer.input(s)

    tokens = []
    while True:
        try:
            tok = lexer.token()
        except Exception as e:
            mainlog.exception(e)
            break

        if tok and tok.lexpos <= cursor_position:
            tokens.append(tok)
        else:
            break

    last_pos = 0

    if tokens:
        last_pos = tokens[-1].lexpos + token_length(tokens[-1]) - 1

    if len(tokens) > 0:
        mainlog.debug("Last pos is pos:{} + len:{} = {}".format(tokens[-1].lexpos,token_length(tokens[-1]),last_pos))

    # while tokens and tokens[-1].lexpos > cursor_position:
    #     # tokens[-1] starts completely after the cursor position
    #     # So it doesn't interest us
    #     mainlog.debug("Popping token {}".format(tokens[-1].value))
    #     t = tokens.pop()
    #     last_pos = t.lexpos - 1

    # At this point the last token either :
    # - ends before the cursor_position
    # - starts before/on and ends after the cursor_position
    # We don't know for sure because we don't know
    # its actual end (there may be spaces after which the
    # lexer hides from us...).

    # last_pos is either at the end of the string
    # or 1 character before the first token that doesn't interest us

    # Figure out the actual end of the last token
    # while last_pos > 0 and last_pos < len(s) and s[last_pos] == ' ':
    #     last_pos = last_pos - 1

    mainlog.debug("Last token's last character is at index {}".format(last_pos))
    replacement_area = None
    inside_token = None

    if tokens and (last_pos >= cursor_position or (cursor_position >= len(s) and s[cursor_position-1] != ' ')):

        # cursor is "inside" the last token.
        mainlog.debug(u"Cursor is inside last token : {} lexpos:{} cursor:{}".format(tokens[-1].value, tokens[-1].lexpos,cursor_position))

        t = inside_token = tokens.pop()

        # Eats useless spaces
        start = t.lexpos
        # while start > 0 and s[start] == ' ':
        #     start = start - 1

        replacement_area = ( 'rep', start, max(0,last_pos) )

        last_pos = t.lexpos - 1

    else:
        # Cursor is after the last token
        if tokens:
            mainlog.debug("Cursor is after the last token : {} lexpos:{}".format(tokens[-1].value, tokens[-1].lexpos))
        else:
            mainlog.debug("Cursor is after NO token")

        replacement_area = ( 'rep', last_pos+1, cursor_position )

    mainlog.debug("Tokens are {}".format(tokens))
    mainlog.debug("Will parse from 0 to {}".format(last_pos+1))


    try:
        parser.parse(s[0:last_pos+1],lexer=lexer)
    except Exception as ex:
        mainlog.exception(ex)
        pass

    suggestions = []
    indexed_s = []
    needs_quoting = False

    if tokens:

        # mainlog.debug(str(parser.symstack))
        # mainlog.debug("Lookahead = {}".format(parser.lookahead_token))
        # if parser.lookahead_token.type != '$end':
        #     return []

        suggestions, needs_quoting = suggestions_generator(parser.symstack) # tokens[0:-1])
    else:
        suggestions, needs_quoting = suggestions_generator([]) # tokens)

    if inside_token:
        # If inside a token, then we use the part of the token
        # we have to filter out some suggestions

        key = text_search_normalize(str(inside_token.value))
        indexed_s =  [text_search_normalize(s) for s in suggestions]

        # suggestions are tuples : (text, normalized text)
        filtered_s = [label[1] for label in
                      filter( lambda label: key in label[0],
                              zip(indexed_s,suggestions) )]

        if filtered_s and len(filtered_s) > 0:
            suggestions = filtered_s


    # mainlog.debug("Found these suggestions : {}".format(s))
    return replacement_area, suggestions, needs_quoting




def check_parse(s):
    try:
        parser.parse(s.upper(),lexer=lexer)
        mainlog.debug("Parse success")
        return True

    except ParserException as ex:

        mainlog.debug(u"Original string {}".format(s))
        lexer.input(s.upper())
        while True:
            t = lexer.token()
            if t:
                mainlog.debug(t)
            else:
                break


        wrong_part = s[max(0,ex.lexpos - 10) : min(len(s),ex.lexpos + 10)]
        if wrong_part:
            return _("There was an error ({}) while parsing the request around '{}'").format(ex.text, wrong_part)
        else:
            return _("There was an error ({}) while parsing the request.").format(ex.text)
