import re
from datetime import date
import koi.ply.lex as lex
import koi.ply.yacc as yacc
from sqlalchemy import and_,or_,not_

if __name__ == "__main__":

    print("hello")
    from koi.Configurator import init_i18n,load_configuration,configuration,resource_dir
    from koi.base_logging import init_logging
    from koi.base_logging import mainlog

    print("hello")
    import logging
    print("hello-log")
    init_logging()
    print("hello-log2")
    mainlog.setLevel(logging.DEBUG)
    print("hello-i18")
    init_i18n()
    print("hello-conf")
    load_configuration()

from koi.datalayer.database_session import session
from koi.base_logging import mainlog
from koi.db_mapping import metadata,OrderPart,Customer,Order,OrderPartStateType
from koi.date_parser import SimpleDateParser
from koi.translators import text_search_normalize


if __name__ == "__main__":
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from koi.date_utils import _last_moment_of_previous_month,_last_moment_of_month,_first_moment_of_month,month_before


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




customers = { 'customers' : [] }

def initialize_customer_cache():
    customers['customers'] = [p.fullname for p in
                              session().query(Customer.fullname).order_by(Customer.fullname).all()]


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


date_parser = SimpleDateParser()


# Used for suggestions
order_part_fields = {
    "Price" : "PART_PRICE",
    "Total_Price" : "PART_VALUE",
    "DoneHours" : "DONE_HOURS",
    "PlannedHours" : "PLANNED_HOURS",
    "Status" : "PART_STATUS",
    "Client" : "CLIENT_NAME",
    "Deadline" : "DEADLINE",
    "CompletionDate" : "COMPLETION_DATE",
    "CreationDate" : "CREATION_DATE",
    "Description" : "PART_DESCRIPTION",
    "Priority" : "PRIORITY",
    "NbNonConformities" : "NB_NON_CONFORMITIES"
}


reserved = {
    # Textual representation -> Token
    "DONEHOURS" : "DONE_HOURS",
    "PLANNEDHOURS" : "PLANNED_HOURS",
    "DEADLINE" : "DEADLINE",
    "PRICE" : "PART_PRICE",
    "TOTAL_PRICE" : "PART_VALUE",

    "STATUS" : "PART_STATUS",
    "CLIENT" : "CLIENT_NAME",
    "Client" : "CLIENT_NAME",
    "CompletionDate" : "COMPLETION_DATE",
    "COMPLETIONDATE" : "COMPLETION_DATE",
    "CreationDate" : "CREATION_DATE",
    "CREATIONDATE" : "CREATION_DATE",
    "PRIORITY" : "PRIORITY",
    "AND" : "AND",
    "OR" : "OR",
    "AFTER" : "AFTER",
    "BEFORE" : "BEFORE",
    "In" : "IN",
    "IN" : "IN",
    "MonthBefore" : "MONTH_BEFORE",
    "MONTHBEFORE" : "MONTH_BEFORE",
    "CURRENTMONTH" : "CURRENT_MONTH",
    "DESCRIPTION" : "PART_DESCRIPTION",
    "NbNonConformities" : "NB_NON_CONFORMITIES",
    "NBNONCONFORMITIES" : "NB_NON_CONFORMITIES"
}


tokens = [ 'SPACER',  'COMMA', 'EQUALS','LEFT_PAREN','RIGHT_PAREN', 'GT_EQUALS', 'GT', 'LT_EQUALS', 'LT',
           'PLUS','TIMES','MINUS','DIVIDES',
           'FLOAT', 'DATE', 'STATUS_ENUM'] + list(set(reserved.values())) + [ 'ID', 'STRING' ]

def token_length(t):
    if hasattr(t,"length"):
        return t.length
    else:
        return len(t.value)

#t_SPACER = '[ ]+'
# t_CLIENT_NAME = 'CLIENT'
# t_STATUS = r'STATUS'
#t_STRING = '[A-Za-z]+|"[A-Za-z ^"]+"'
# t_QUOTED_STRING = '"[A-Za-z ^"]+"'


t_COMMA = r','
t_LEFT_PAREN = '\('
t_RIGHT_PAREN = '\)'

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
    l = len(t.value)
    t.value = float(t.value)
    t.length = l

    return t

def t_GT_EQUALS(t):
    r'>='
    t.value = lambda a,b: a >= b
    t.length = len('>=')

    return t

def t_LT_EQUALS(t):
    r'<='
    t.value = lambda a,b: a <= b
    t.length = len('<=')

    return t

def t_GT(t):
    r'>'
    t.value = lambda a,b: a > b
    t.length = len('>')

    return t

def t_PLUS(t):
    r'\+'
    t.value = lambda a,b: a + b
    t.length = len('+')

    return t

def t_MINUS(t):
    r'\-'
    t.value = lambda a,b: a - b
    t.length = len('-')

    return t

def t_TIMES(t):
    r'\*'
    t.value = lambda a,b: a * b
    t.length = len('*')

    return t

def t_DIVIDES(t):
    r'\/'
    t.value = lambda a,b: a / b
    t.length = len('/')

    return t

def t_LT(t):
    r'<'
    t.value = lambda a,b: a < b
    t.length = len('<')
    return t

def t_EQUALS(t):
    r'='
    t.value = lambda a,b: a == b
    t.length = len('=')
    return t



@lex.TOKEN('|'.join(["({})".format(n.upper()) for n in OrderPartStateType.names()]))
def t_STATUS_ENUM(t):
    t.value = OrderPartStateType.from_str(t.value.lower())
    return t

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'

    t.type = reserved.get(t.value,'STRING')    # Check for reserved words
    t.length = len(t.value)
    return t

def t_STRING(x):
    r'\D][\D0-9\.^\-]|"[\D0-9\. ^\-"]+"'

    if x.value[0] == '"' and x.value[-1] == '"':
        x.length = len(x.value)
        x.value = x.value[1:-1]
    mainlog.debug(x.value)

    return x

def t_error(t):
    raise ParserException(_("syntax error"), t.lexpos)
    # t.lexer.skip(1)



# yacc.yaccdebug = True

def p_expression_term(p):
    ''' expression : term '''
    p[0] = p[1]

def p_and_expression(p):
    ''' expression : expression AND term '''

    p[0] = and_(p[1],p[3])

def p_or_expression(p):
    ''' expression : expression OR term '''
    # p[0] = p[1] + " || " + p[3]

    p[0] = or_(p[1],p[3])

def p_term2(p):
    ''' term : LEFT_PAREN expression RIGHT_PAREN'''
    # p[0] = "(" + str(p[2]) + ")"
    p[0] = p[2]

def p_term(p):
    ''' term : client_term
               | description_term
               | status_term
               | float_comparison_term
               | date_after_term
               | number_comparison_term
               | date_before_term
               | date_in_period_expression '''
    p[0] = p[1]



def p_float_comparison(p):
    ''' float_comparison_term : PART_PRICE GT FLOAT
                              | PART_PRICE LT FLOAT
                              | PART_PRICE GT_EQUALS FLOAT
                              | PART_PRICE LT_EQUALS FLOAT
                              | PART_PRICE EQUALS FLOAT'''

    lambda_op = p[2]
    p[0] = lambda_op(OrderPart.sell_price, p[3])


def p_float_comparison_value(p):
    ''' float_comparison_term : PART_VALUE GT FLOAT
                              | PART_VALUE LT FLOAT
                              | PART_VALUE GT_EQUALS FLOAT
                              | PART_VALUE LT_EQUALS FLOAT
                              | PART_VALUE EQUALS FLOAT'''

    lambda_op = p[2]
    p[0] = lambda_op(OrderPart.total_sell_price, p[3])

def p_number_comparison(p):
    ''' number_comparison_term : number_expression LT number_expression
                               | number_expression GT number_expression
                               | number_expression GT_EQUALS number_expression
                               | number_expression LT_EQUALS number_expression
                               | number_expression EQUALS number_expression
    '''

    lambda_op = p[2]
    p[0] = lambda_op(p[1], p[3])



def p_number_expression_float(p):
    ''' number_expression : FLOAT
    '''
    p[0] = float(p[1])


def p_number_expression_done_hours(p):
    ''' number_expression : DONE_HOURS
    '''
    p[0] = OrderPart.total_hours


def p_number_expression_estimated_hours(p):
    ''' number_expression : PLANNED_HOURS
    '''
    p[0] = OrderPart.total_estimated_time


def p_number_expression_priority(p):
    ''' number_expression : PRIORITY
    '''
    p[0] = OrderPart.priority


def p_number_expression_nb_non_conformities(p):
    ''' number_expression : NB_NON_CONFORMITIES
    '''
    p[0] = OrderPart.nb_non_conformities


def p_number_expression_paren(p):
    ''' number_expression : LEFT_PAREN number_expression RIGHT_PAREN'''
    # p[0] = "(" + str(p[2]) + ")"
    p[0] = p[2]

def p_number_computation(p):
    ''' number_expression : number_expression PLUS number_expression
                          | number_expression MINUS number_expression
                          | number_expression TIMES number_expression
                          | number_expression DIVIDES number_expression
    '''

    lambda_op = p[2]
    p[0] = lambda_op(p[1], p[3])





# --------------------------------------------------------------------

def p_date_after_term(p):
    ''' date_after_term : date_term AFTER date_term
                          | date_term GT date_term '''
    p[0] = p[1] > p[3]


def p_date_before_term(p):
    ''' date_before_term : date_term BEFORE date_term
                           | date_term LT date_term'''
    p[0] = p[1] < p[3]


def p_date_in_period_expression(p):
   ''' date_in_period_expression : date_term IN period_term '''

   mainlog.debug(p[3][0])
   mainlog.debug(p[3][1])

   p[0] = and_(p[1] != None, p[1].between(p[3][0], p[3][1]))


def p_date_term(p):
    ''' date_term : CREATION_DATE '''

    p[0] =  Order.creation_date

def p_date_term_deadline(p):
    ''' date_term : DEADLINE '''

    p[0] =  OrderPart.deadline

def p_date_term_encoded(p):
    ''' date_term : DATE '''

    p[0] =  p[1]

def p_date_term_completion(p):
    ''' date_term : COMPLETION_DATE '''

    p[0] =  OrderPart.completed_date


def p_period_function_month_term(p):
   ''' period_term : MONTH_BEFORE '''

   d = month_before(date.today())

   p[0] = ( _first_moment_of_month(d), _last_moment_of_month(d) )

def p_period_function_current_month_term(p):
   ''' period_term : CURRENT_MONTH '''

   d = date.today()

   p[0] = ( _first_moment_of_month(d), _last_moment_of_month(d) )



def p_period_term(p):
   ''' period_term : LEFT_PAREN DATE COMMA DATE RIGHT_PAREN '''

   p[0] = ( p[2], p[4] )

# --------------------------------------------------------------------

def p_status_term(p):
    ''' status_term : PART_STATUS EQUALS STATUS_ENUM'''
    p[0] = OrderPart.state == p[3]

# --------------------------------------------------------------------


def apply_ilikes(names,column):
    # bvb : apply_ilikes( ['alpha','omega'] , OrderPart.indexed_description)

    if len(names) == 1:
        return column.like(u"%{}%".format(names[0]))
    elif len(names) > 1:
        return or_(column.like(u"%{}%".format(names[0])), apply_ilikes(names[0:-1], column) )
    else:
        raise Exception("This will work only on non empty names lists.")



def p_description_term(p):
    ''' description_term : PART_DESCRIPTION EQUALS STRING'''
    # p[0] = 'client_name = ' + str(p[3])

    p[0] = OrderPart.indexed_description.like(u"%{}%".format(text_search_normalize(p[3])))


def p_client_term(p):
    ''' client_term : CLIENT_NAME EQUALS list'''
    # p[0] = 'client_name = ' + str(p[3])

    p[0] = apply_ilikes( [text_search_normalize(term) for term in p[3]],
                         Customer.indexed_fullname)


def p_list(p):
    ''' list : STRING'''

    p[0] = [ p[1] ]


def p_list_l(p):
    ''' list : list COMMA STRING'''

    p[0] = [ p[3] ] + p[1]


# def p_string(p):
#     'string : STRING'

#     p[0] = p[1]
#     print "string  {}".format(p[0])

# def p_client_name(p):
#     'client_name : CLIENT_NAME'
#     p[0] = p[1]
#     print "client_name"

# def p_equals(p):
#     'equals : EQUALS'
#     p[0] = p[1]
#     print "equals"




def p_error(p):
    mainlog.debug("Error : p={}".format(p))
    if p:
        mainlog.debug("Error : lexpos = {}".format(p.lexpos))

    mainlog.debug("Error : token : {}".format(yacc.token()))

    if not p:
        raise ParserException(_("parsing error"))
    else:
        raise ParserException(_("parsing error"),p.lexpos)


mainlog.debug("Initializing lexer qp")
# Build the parser
lexer = lex.lex(reflags=re.UNICODE, lextab='ply_order')
# debuglog, errorlog are set to avoid using the console output (this usually
# leads to trouble with a frozen horse)
mainlog.debug("Initializing parser qp")

# if __name__ == "__main__":
#     parser = yacc.yacc(debug=1)
# else:
# Production use
parser = yacc.yacc(write_tables=False, debug=0,debuglog=yacc.NullLogger(),errorlog=mainlog)

mainlog.debug("Initializing parser - done")


def parse_order_parts_query(q):
    sqla = parser.parse(q.upper(),lexer=lexer)
    mainlog.debug( sqla)
    return sqla


def tokens_ends_with(tokens, end):
    if len(tokens) < len(end):
        return False
    else:
        if tokens[-1].type == '$end':
            tokens = tokens[0:-1]

        for i in range(1,1+len(end)):

            if isinstance(end[-i], set):
                if tokens[-i].type not in end[-i]:
                    return False
            else:
                if tokens[-i].type != end[-i]:
                    return False
        return True


def figure_suggestions(tokens):
    suggestions = []

    mainlog.debug("figure_suggestions : Len tokens = {}".format(len(tokens)))
    for t in tokens:
        mainlog.debug("> {} -> type: {}".format(t,t.type))

    td = date.today()
    date_today = u'1/{}/{}'.format(td.month,td.year)

    if len(tokens) == 0: # or tokens[-1].type == '$end' :
        suggestions = list(sorted(order_part_fields.keys()))
    elif tokens_ends_with(tokens, ['CLIENT_NAME','EQUALS']):
        suggestions =  customers['customers']
    elif tokens_ends_with(tokens, ['PART_STATUS','EQUALS']):
        suggestions = [str(s) for s in OrderPartStateType.symbols()]
    elif tokens_ends_with(tokens, ['IN','LEFT_PAREN']):
        suggestions = [date_today]
    elif tokens_ends_with(tokens, [ { 'PART_PRICE', 'PART_VALUE' }, { '<','>','>=','<=','=' }]):
        suggestions = []
    elif tokens[-1].type in ('LEFT_PAREN','AND','OR'):
        suggestions = list(sorted(order_part_fields.keys()))
    elif tokens[-1].type in ('CLIENT_NAME','PART_STATUS',"PART_DESCRIPTION"):
        suggestions = ['=']
    elif tokens[-1].type in ('PART_PRICE', 'PART_VALUE'):
        suggestions = ['<','>']
    elif tokens[-1].type in ('date_term'):
        suggestions = [u'AFTER',u'BEFORE',u'In']
    elif tokens[-1].type in ('AFTER','BEFORE'):
        td = date.today()
        suggestions = [date_today]
    elif tokens[-1].type == 'IN':
        suggestions = [u'MonthBefore',u'CurrentMonth']
    elif tokens[-1].type == 'expression':
        suggestions = [u'AND',u'OR']
    else:
        suggestions = []

    mainlog.debug("Suggestions are : {}".format(suggestions))
    return suggestions, [text_search_normalize(s) for s in suggestions]


def find_suggestions(s,cursor_position):
    """ returns :
    * replacement_area : a (action, start index,stop index) tuple representing where
    the suggestion might fit in the original s string. action is always "rep"
    for the moment.
    * s : an array with all possible suggestions
    * needs_quoting : tells if the suggestion needs to be quoted in the
    query string (so that it will correctly be parsed later on). For
    example, the suggestion "aaa bbb" needs quoting because there is
    a space in it.
    """

    mainlog.debug(u"Finding suggestions for :'{}'".format(s))
    mainlog.debug(u"looking there :          '{}^".format(" "*cursor_position))

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

    s = []
    indexed_s = []

    if tokens:

        # mainlog.debug(str(parser.symstack))
        # mainlog.debug("Lookahead = {}".format(parser.lookahead_token))
        # if parser.lookahead_token.type != '$end':
        #     return []

        s,indexed_s = figure_suggestions(parser.symstack) # tokens[0:-1])
    else:
        s,indexed_s = figure_suggestions([]) # tokens)

    needs_quoting = s == customers['customers']

    if inside_token:
        key = text_search_normalize(str(inside_token.value))

        # suggestions are tuples : (text, normalized text)
        filtered_s = [label[1] for label in
                      filter( lambda label: key in label[0],
                              zip(indexed_s,s) )]

        if filtered_s and len(filtered_s) > 0:
            s = filtered_s


    # mainlog.debug("Found these suggestions : {}".format(s))
    return replacement_area, s, needs_quoting




def check_parse(s):
    try:
        parser.parse(s.upper(),lexer=lexer)
        mainlog.debug("Parse success")
        return True

    except ParserException as ex:
        wrong_part = s[max(0,ex.lexpos - 10) : min(len(s),ex.lexpos + 10)]
        if wrong_part:
            return _("There was an error ({}) while parsing the request around '{}'").format(ex.text, wrong_part)
        else:
            return _("There was an error ({}) while parsing the request.").format(ex.text)


if __name__ == "__main__":


    s = "CLIENT   = ARGKO,Mancini,\"Tessier Ashpool\",Freud AND STATUS = Closed"
    s = " (CompletionDate BEFORE 14/3/2014 AND CompletionDate AFTER ) AND ((CLIENT = TAC) OR STATUS=Closed)" # Closed"
    s = "CLIENT   = ARGKO,Mancini AND (CLIENT = ZUZU)"
    s = "CompletionDate AFTER 14/3/2014"
    s = "PART_PRICE > 12.23"
    s = "PART_STATUS = ready_for_production"
    s = "" # suggestion
    s = "CLIENT ="
    s = "CLIENT AND "
    s = "PART_STATUS =  "


    # mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT ",5)))

    # mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = A",8)))
    # mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = A",7)))
    # mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = TAC ",12)))
    # mainlog.debug("TEST --------------------" + str(find_suggestions("CL",1)))
    # mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = TAC AND ",16)))

    # mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = A",10)))
    # mainlog.debug("TEST --------------------" + str(find_suggestions("CLIENT = A )))",16)))
    # mainlog.debug("TEST --------------------" + str(find_suggestions("CL",2)))

    # mainlog.debug("TEST --------------------" + str(find_suggestions("CreationDate In MonthBefore",28)))

    #mainlog.debug("TEST --------------------" + str(find_suggestions("status",6)))
    # mainlog.debug("TEST --------------------" + str(find_suggestions("sta",3)))
    # mainlog.debug("TEST --------------------" + str(find_suggestions("client = ze",11)))

    # mainlog.debug("TEST --------------------" + str(find_suggestions("client = ",9)))
    # mainlog.debug("TEST --------------------" + str(find_suggestions("client = \"ABM",11)))
    # mainlog.debug("TEST --------------------" + str(find_suggestions("Client=\"ABMI sprl \"  ",21)))



    s = "CreationDate In MonthBefore AND CLIENT = \"TAC\" AND PART_STATUS = ABORTED"
    s = "CreationDate In (1/1/2013,1/1/2014)"
    s = "CreationDate AFTER DEADLINE"
    s = "CreationDate IN CURRENTMONTH"
    s = "(Deadline AFTER 1/1/2014) AND (CompletionDate  AFTER Deadline)"
    s = "delivery_slips = betrand"
    s = "DESCRIPTION = \"4000\""

    mainlog.debug("Parsing...")
    result = parser.parse(s.upper(),lexer=lexer)
    # print result
    # print session().query(OrderPart).join(Order).filter(result)

    # mainlog.debug(check_parse("(Deadline AFTER 1/1/2014) xAND (CompletionDate  AFTER Deadline)"))
    # mainlog.debug(check_parse("(Deadline AFTER 99/1/2014) AND (CompletionDate  AFTER Deadline)"))
    # mainlog.debug(check_parse("(Deadline AFTER 1/1/2014) AND %%%"))
    # mainlog.debug(check_parse(""))
    # mainlog.debug(check_parse("DESCRIPTION = \"4000\""))

    print(parser.parse("10 < 3"))
    print(parser.parse("10 + 3 < 2"))
    print(parser.parse("10 - 3 < 2"))
    print(parser.parse("10 * 3 < 2"))
    print(parser.parse("10 / 3 < 2"))

    s = "10 + 3 < DONEHOURS"
    s = "10 + 3 < PLANNEDHOURS"
    s = "(DONEHOURS < 0.6 * PLANNEDHOURS) AND ( DONEHOURS > 0)"
    s = "Status = ready_for_production  AND DoneHours > 0.6*PlannedHours"
    s = "TOTAL_PRICE >"
    try:
        result = parser.parse(s,lexer=lexer)
    except Exception as ex:
        print("Can't parse the string : {}, because {}".format(s, ex))


        lexer.input(s)
        print("go")
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break      # No more input
            print(tok)
            tokens.append(tok)

        print("Toeksn are : {}".format(tokens))
        suggestions = figure_suggestions(tokens)

        print("suggestions : {}".format( suggestions[1] or 'no suggestion'))



    # print s
