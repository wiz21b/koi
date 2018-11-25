import re
from datetime import date
import koi.ply.lex as lex
import koi.ply.yacc as yacc
from sqlalchemy import and_,or_,not_

if __name__ == "__main__":

    import koi.python3
    from koi.Configurator import init_i18n,load_configuration,configuration,resource_dir
    from koi.base_logging import init_logging

    init_logging()
    init_i18n()
    load_configuration()

from koi.datalayer.database_session import session
from koi.base_logging import mainlog
from koi.db_mapping import metadata,Customer,DeliverySlipPart,DeliverySlip,OrderPart
from koi.datalayer.supplier_mapping import Supplier
from koi.date_parser import SimpleDateParser
from koi.translators import text_search_normalize

if __name__ == "__main__":
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from koi.date_utils import month_before,ts_to_date



from koi.datalayer.supplier_service import supplier_service

suppliers = { 'suppliers' : [] }
def initialize_supplier_cache():
    suppliers['suppliers'] = [p.fullname for p in supplier_service.find_all()]

customers = { 'customers' : [] }
def initialize_customer_cache():
    customers['customers'] = [p.fullname for p in
                              session().query(Customer.fullname).order_by(Customer.fullname).all()]




date_parser = SimpleDateParser()


# Used for suggestions
order_part_fields = {
    "Customer" : "CUSTOMER_NAME",
    "CreationDate" : "CREATION_DATE",
    "Description" : "PART_DESCRIPTION",
    "SlipActive" : "SLIP_ACTIVE"
}


# Reserverd word (as typed by the user), all upper case => token
reserved = {
    "DEADLINE" : "DEADLINE",
    "STATUS" : "PART_STATUS",
    "CUSTOMER" : "CUSTOMER_NAME",
    "CREATIONDATE" : "CREATION_DATE",
    "DESCRIPTION" : "PART_DESCRIPTION",
    "SLIPACTIVE" : "SLIP_ACTIVE"
}


# Import here so that the token above have precedence
# For example, "ORDER" gets precedence over "OR", which is needed !

from koi.datalayer.parser_utils import *
tokens = list(set(reserved.values())) + list(set(basic_reserved.values())) + basic_tokens

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'

    # This construction is explained in ply's documentation.

    # Note that the reserved words have precedence over basic_reserved words...
    # That's because basic_reserved words are usually shorter (so they shouldn' match
    # first, for example : OR and ORDER)

    # It's not very clean to put this code here but that's the only
    # way I've found to group basic reserved words and specific reserved words...

    if t.value in reserved:
        t.type = reserved[t.value]
    elif t.value in basic_reserved:
        t.type = basic_reserved[t.value]
    else:
        t.type = 'STRING'

    t.length = len(t.value)
    return t

# The p_expression_term is the root of the grammar.
# I must put it here else ply won't see it...

def p_expression_term(p):
    ''' bool_expression : term '''
    p[0] = p[1]


def p_creation_date_term(p):
    ''' date_term : CREATION_DATE '''
    p[0] =  DeliverySlip.creation

def p_part_description(p):
    ''' text_term : PART_DESCRIPTION '''
    p[0] = OrderPart.indexed_description

def p_customer_name_equals(p):
    ''' term : CUSTOMER_NAME EQUALS STRING'''
    # I make this rule stand out because I can then track its tokens during the
    # suggestion algorithm. Normally the "text_term equals string" rule should
    # apply.
    # p[0] = Customer.indexed_fullname == text_search_normalize(p[3])

    p[0] = apply_ilikes( [text_search_normalize(p[3])],
                         Customer.indexed_fullname)

def p_customer_name(p):
    ''' text_term : CUSTOMER_NAME '''
    p[0] = Customer.indexed_fullname


def p_order_is_active(p):
    ''' term : SLIP_ACTIVE IS TRUE
             | SLIP_ACTIVE EQUALS TRUE '''
    p[0] = DeliverySlip.active == True

def p_order_is_not_active(p):
    ''' term : SLIP_ACTIVE IS FALSE
             | SLIP_ACTIVE EQUALS FALSE'''
    p[0] = DeliverySlip.active == False






# Build the parser
lexer = lex.lex(reflags=re.UNICODE, lextab='ply_supply_order')

import koi.datalayer.parser_utils
from koi.datalayer.parser_utils import *

mainlog.debug("Initializing lexer ds")

# parser = yacc.yacc(debug=0,module=koi.datalayer.parser_utils)
parser = yacc.yacc(write_tables=False, debug=0, debuglog=yacc.NullLogger(), errorlog=mainlog)


def parse_delivery_slip_parts_query(q):
    sqla = parser.parse(q.upper(),lexer=lexer)
    mainlog.debug( sqla)
    return sqla



def suggestion_finder(text, cursor_pos):
    # To be used in the filter entry widget
    # This is basically a memoizer for some parameters...
    global lexer, parser, figure_suggestions
    return find_suggestions(text, cursor_pos, lexer, parser, figure_suggestions)



def figure_suggestions(tokens):
    suggestions = []

    mainlog.debug("figure_suggestions : Len tokens = {}".format(len(tokens)))
    for t in tokens:
        mainlog.debug("* {} -> {}".format(t,t.type))

    td = date.today()
    date_today = u'1/{}/{}'.format(td.month,td.year)

    if len(tokens) == 0: # or tokens[-1].type == '$end' :
        suggestions = list(sorted(order_part_fields.keys())), False
    elif tokens_ends_with(tokens, ['CUSTOMER_NAME','EQUALS']):
        suggestions = customers['customers'], True
    elif tokens_ends_with(tokens, ['PART_STATUS','EQUALS']):
        suggestions = [str(s) for s in OrderPartStateType.symbols()], False
    elif tokens_ends_with(tokens, ['IN','LEFT_PAREN']):
        suggestions = [date_today], False
    elif tokens_ends_with(tokens, ['PART_PRICE','<']):
        suggestions = [], False
    elif tokens_ends_with(tokens, ['PART_PRICE','>']):
        suggestions = [], False
    elif tokens[-1].type in ('LEFT_PAREN','AND','OR'):
        suggestions = list(sorted(order_part_fields.keys())), False
    elif tokens[-1].type in ('CUSTOMER_NAME','PART_STATUS',"PART_DESCRIPTION"):
        suggestions = ['='], False
    elif tokens[-1].type in ('PART_PRICE'):
        suggestions = ['<','>'], False
    elif tokens[-1].type in ('date_term'):
        suggestions = [u'AFTER',u'BEFORE',u'In'], False
    elif tokens[-1].type in ('AFTER','BEFORE'):
        td = date.today()
        suggestions = [date_today], False
    elif tokens[-1].type == 'IN':
        suggestions = [u'MonthBefore',u'CurrentMonth'], False
    elif tokens[-1].type == 'expression':
        suggestions = [u'AND',u'OR'], False
    else:
        suggestions = [], False

    return suggestions




if __name__ == "__main__":
    # s = "CLIENT   = ARGKO,Mancini,\"Tessier Ashpool\",Freud AND STATUS = Closed"
    # s = " (CompletionDate BEFORE 14/3/2014 AND CompletionDate AFTER ) AND ((CLIENT = TAC) OR STATUS=Closed)" # Closed"
    # s = "CLIENT   = ARGKO,Mancini AND (CLIENT = ZUZU)"
    # s = "CompletionDate AFTER 14/3/2014"
    # s = "PART_PRICE > 12.23"
    # s = "PART_STATUS = ready_for_production"
    # s = "" # suggestion
    # s = "CLIENT ="
    # s = "CLIENT AND "
    # s = "PART_STATUS =  "


    mainlog.debug(u"TEST --------------------" + str(find_suggestions("CLIENT ",5, lexer, figure_suggestions)))

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



    tests = [ "CreationDate In MonthBefore AND customer = \"TAC\"",
              "CreationDate In (1/1/2013,1/1/2014)",
              "CreationDate IN CURRENTMONTH",
              "(CreationDate AFTER 1/1/2014) AND (CreationDate  AFTER 1/2/2014)",
              "CreationDate AFTER 23/11/2014",
              "customer = betrand",
              "customer in betrand, kondor",
              "DESCRIPTION = \"4000\"",
              "DESCRIPTION ~ \"4000\"",
              "SlipActive = false",
              "SlipActive is true",
              "SlipActive = false and SlipActive is true" ]

    for s in tests:
        mainlog.debug("Lexing... -------------------------------------------- {}".format(s))
        lexer.input(s.upper())

        while True:
            t = lexer.token()
            if t:
                print(t)
            else:
                break

        print()

        mainlog.debug("Parsing...")
        result = parser.parse(s.upper(),lexer=lexer)
        print( result)

    # print session().query(OrderPart).join(Order).filter(result)

    # mainlog.debug(check_parse("(Deadline AFTER 1/1/2014) xAND (CompletionDate  AFTER Deadline)"))
    # mainlog.debug(check_parse("(Deadline AFTER 99/1/2014) AND (CompletionDate  AFTER Deadline)"))
    # mainlog.debug(check_parse("(Deadline AFTER 1/1/2014) AND %%%"))
    # mainlog.debug(check_parse(""))
    # mainlog.debug(check_parse("DESCRIPTION = \"4000\""))

    # try:
    #     result = parser.parse(s)
    # except Exception, ex:

    #     lexer.input(s)

    #     tokens = []
    #     while True:
    #         tok = lexer.token()
    #         if not tok:
    #             break      # No more input
    #         tokens.append(tok.type)

    #     suggestions = figure_suggestions(tokens)
    #     raise ParserException(s,suggestions)



    # print s
