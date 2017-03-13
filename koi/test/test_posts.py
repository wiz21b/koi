from sqlalchemy import and_
from db_mapping import *
from dao import dao,session

# all_ops = dao.operation_definition_dao.all()
all_ops = [dao.operation_definition_dao.find_by_id(19)] # 10 = TO,  22= AJ, 19=AL

post_ops = {}

for opdef in all_ops:

    operations = dao.operation_dao.active_operations(opdef)

    maximum = 16.0 #float !
    small_hours = 0
    op_ndx =0
    current_x = 50
    bar_drawn = False

    # --------------------------------------------------------------
    total_estimated = 0
    oldpart = None
    partsum=0
    sum_done_hours = 0


    done_hours_grand_total = 0

    c = operations[0].production_file.order_part.order.customer.fullname
    for op in operations:

        todo = op.t_devis*op.production_file.order_part.qty

        if op.production_file.order_part.order.order_id != oldpart:
            print(("------------------ {} Total todo:{} / done:{} - {}".format(c, partsum, sum_done_hours, done_hours_grand_total)))
            print()

            partsum = 0
            sum_done_hours = 0
            oldpart = op.production_file.order_part.order.order_id
            c = op.production_file.order_part.order.customer.fullname

        total_estimated += todo
        done_hours_grand_total += op.done_hours

        partsum += todo
        sum_done_hours += op.done_hours


        if todo > 0:
            print(((u"{}: {} = {}h / {}h".format(op.production_file.order_part.human_identifier, op.description, todo, op.done_hours)).encode(sys.getdefaultencoding(),'ignore')))

if __name__ == "__main__":
    print()
    print(("Done : {} / Estimated {}".format(done_hours_grand_total,total_estimated)))
