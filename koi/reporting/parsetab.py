
# parsetab.py
# This file is automatically generated. Do not edit.
_tabversion = '3.2'

_lr_method = 'LALR'

_lr_signature = b'\xc5e_\xac}mL\xf8\xa8\xc3y\x9cM\xf5\xff\xbf'
    
_lr_action_items = {'SLIP_ACTIVE':([0,3,18,19,],[1,1,1,1,]),'CURRENT_MONTH':([23,],[40,]),'RIGHT_PAREN':([4,7,8,9,10,11,17,28,29,30,31,32,33,34,35,36,37,38,40,41,42,43,44,45,46,47,51,52,53,],[-24,-26,-18,-25,-2,-1,33,-6,-8,-7,-9,-4,-12,-11,-10,-15,-16,-13,-21,-17,-20,-14,-22,-29,-28,-27,-23,53,-19,]),'CUSTOMER_NAME':([0,3,18,19,],[2,2,2,2,]),'PART_DESCRIPTION':([0,3,18,19,],[12,12,12,12,]),'LEFT_PAREN':([0,3,18,19,23,],[3,3,3,3,39,]),'TILDE':([2,12,13,],[-5,-3,26,]),'TRUE':([14,15,],[28,30,]),'COMMA':([44,45,48,51,],[-22,49,50,-23,]),'MONTH_BEFORE':([23,],[42,]),'BEFORE':([6,8,10,],[20,-18,-2,]),'IN':([2,6,8,10,12,13,],[-5,23,-18,-2,-3,25,]),'$end':([4,5,7,8,9,10,11,28,29,30,31,32,33,34,35,36,37,38,40,41,42,43,44,45,46,47,51,53,],[-24,0,-26,-18,-25,-2,-1,-6,-8,-7,-9,-4,-12,-11,-10,-15,-16,-13,-21,-17,-20,-14,-22,-29,-28,-27,-23,-19,]),'DATE':([0,3,18,19,20,21,22,24,39,50,],[8,8,8,8,8,8,8,8,48,52,]),'AFTER':([6,8,10,],[22,-18,-2,]),'CREATION_DATE':([0,3,18,19,20,21,22,24,],[10,10,10,10,10,10,10,10,]),'IS':([1,],[14,]),'LT':([6,8,10,],[21,-18,-2,]),'STRING':([16,25,26,27,49,],[32,44,46,47,51,]),'AND':([4,5,7,8,9,10,11,17,28,29,30,31,32,33,34,35,36,37,38,40,41,42,43,44,45,46,47,51,53,],[-24,19,-26,-18,-25,-2,-1,19,-6,-8,-7,-9,-4,-12,-11,-10,-15,-16,-13,-21,-17,-20,-14,-22,-29,-28,-27,-23,-19,]),'FALSE':([14,15,],[29,31,]),'OR':([4,5,7,8,9,10,11,17,28,29,30,31,32,33,34,35,36,37,38,40,41,42,43,44,45,46,47,51,53,],[-24,18,-26,-18,-25,-2,-1,18,-6,-8,-7,-9,-4,-12,-11,-10,-15,-16,-13,-21,-17,-20,-14,-22,-29,-28,-27,-23,-19,]),'EQUALS':([1,2,12,13,],[15,16,-3,27,]),'GT':([6,8,10,],[24,-18,-2,]),}

_lr_action = { }
for _k, _v in _lr_action_items.items():
   for _x,_y in zip(_v[0],_v[1]):
      if not _x in _lr_action:  _lr_action[_x] = { }
      _lr_action[_x][_k] = _y
del _lr_action_items

_lr_goto_items = {'date_after_expression':([0,3,18,19,],[4,4,4,4,]),'term':([0,3,18,19,],[11,11,34,35,]),'date_term':([0,3,18,19,20,21,22,24,],[6,6,6,6,36,37,38,43,]),'bool_expression':([0,3,],[5,17,]),'text_term':([0,3,18,19,],[13,13,13,13,]),'date_before_expression':([0,3,18,19,],[9,9,9,9,]),'period_term':([23,],[41,]),'list':([25,],[45,]),'date_in_period_expression':([0,3,18,19,],[7,7,7,7,]),}

_lr_goto = { }
for _k, _v in _lr_goto_items.items():
   for _x,_y in zip(_v[0],_v[1]):
       if not _x in _lr_goto: _lr_goto[_x] = { }
       _lr_goto[_x][_k] = _y
del _lr_goto_items
_lr_productions = [
  ("S' -> bool_expression","S'",1,None,None,None),
  ('bool_expression -> term','bool_expression',1,'p_expression_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\delivery_slip_query_parser.py',101),
  ('date_term -> CREATION_DATE','date_term',1,'p_creation_date_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\delivery_slip_query_parser.py',106),
  ('text_term -> PART_DESCRIPTION','text_term',1,'p_part_description','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\delivery_slip_query_parser.py',110),
  ('term -> CUSTOMER_NAME EQUALS STRING','term',3,'p_customer_name_equals','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\delivery_slip_query_parser.py',114),
  ('text_term -> CUSTOMER_NAME','text_term',1,'p_customer_name','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\delivery_slip_query_parser.py',124),
  ('term -> SLIP_ACTIVE IS TRUE','term',3,'p_order_is_active','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\delivery_slip_query_parser.py',129),
  ('term -> SLIP_ACTIVE EQUALS TRUE','term',3,'p_order_is_active','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\delivery_slip_query_parser.py',130),
  ('term -> SLIP_ACTIVE IS FALSE','term',3,'p_order_is_not_active','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\delivery_slip_query_parser.py',134),
  ('term -> SLIP_ACTIVE EQUALS FALSE','term',3,'p_order_is_not_active','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\delivery_slip_query_parser.py',135),
  ('bool_expression -> bool_expression AND term','bool_expression',3,'p_and_expression','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',155),
  ('bool_expression -> bool_expression OR term','bool_expression',3,'p_or_expression','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',160),
  ('term -> LEFT_PAREN bool_expression RIGHT_PAREN','term',3,'p_term_parenthesis','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',166),
  ('date_after_expression -> date_term AFTER date_term','date_after_expression',3,'p_date_after_expression','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',172),
  ('date_after_expression -> date_term GT date_term','date_after_expression',3,'p_date_after_expression','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',173),
  ('date_before_expression -> date_term BEFORE date_term','date_before_expression',3,'p_date_before_expression','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',178),
  ('date_before_expression -> date_term LT date_term','date_before_expression',3,'p_date_before_expression','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',179),
  ('date_in_period_expression -> date_term IN period_term','date_in_period_expression',3,'p_date_in_period_expression','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',184),
  ('date_term -> DATE','date_term',1,'p_date_term_encoded','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',191),
  ('period_term -> LEFT_PAREN DATE COMMA DATE RIGHT_PAREN','period_term',5,'p_period_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',197),
  ('period_term -> MONTH_BEFORE','period_term',1,'p_period_function_month_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',202),
  ('period_term -> CURRENT_MONTH','period_term',1,'p_period_function_current_month_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',210),
  ('list -> STRING','list',1,'p_string_list','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',220),
  ('list -> list COMMA STRING','list',3,'p_string_list_l','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',226),
  ('term -> date_after_expression','term',1,'p_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',232),
  ('term -> date_before_expression','term',1,'p_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',233),
  ('term -> date_in_period_expression','term',1,'p_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',234),
  ('term -> text_term EQUALS STRING','term',3,'p_string_eql_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',238),
  ('term -> text_term TILDE STRING','term',3,'p_string_tilde_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',242),
  ('term -> text_term IN list','term',3,'p_in_list_term','C:\\PORT-STC\\PRIVATE\\PL\\horse\\koi\\datalayer\\parser_utils.py',246),
]
