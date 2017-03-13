from koi.db_mapping import Employee,Task,OperationDefinition,Operation,Order,TaskOnOperation,TaskActionReportType
from koi.machine.machine_mapping import Machine

# Good explanation of EAN13 : http://www.barcodeisland.com/ean13.phtml

class BarCode(object):
    EAN13 = 1

    FirstGroup =  ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]
    SecondGroup = ["RRRRRR", "RRRRRR", "RRRRRR", "RRRRRR", "RRRRRR", "RRRRRR", "RRRRRR", "RRRRRR", "RRRRRR", "RRRRRR"]
    LCodes = ["0001101","0011001","0010011","0111101","0100011","0110001","0101111","0111011","0110111","0001011"]
    GCodes = ["0100111","0110011","0011011","0100001","0011101","0111001","0000101","0010001","0001001","0010111"]
    RCodes = ["1110010","1100110","1101100","1000010","1011100","1001110","1010000","1000100","1001000", "1110100"]

    def __init__(self,value,type = EAN13):
        self.value = value
        self.src = "{:0>12}".format(value)

    def _checksum(self):
        # The string we convert is aligned on the right of
        # a 17 charcters string. ndx is the index of the
        # first character of our string in the padded string.
        ndx = 17 - len(self.src)

        weight = 3
        if (ndx % 2) == 1:
            weight = 1

        sum = 0
        for digit in self.src:

            prd = int(digit) * weight
            sum = sum + prd
		#	print "{} : {} * {} = {}".format(ndx,digit,weight,prd)

            if weight == 1:
                weight = 3
            elif weight == 3:
                weight = 1

            ndx = ndx + 1

        # 10 complement
        res = 0
        if (sum % 10) > 0:
            res = 10 - (sum % 10)

        return res

    def to_binary(self):

        with_checksum = "{}{}".format(self.src,self._checksum())

        g = self.FirstGroup[int(self.src[0])] + self.SecondGroup[0]
        result = "101"

        for c in range(0,6):
            digit = int( with_checksum[1+c])
            #	print g[c]
            if g[c] == 'L':
                result = result + self.LCodes[ int(digit)]
            elif g[c] == 'R':
                result = result + self.RCodes[ int(digit)]
            elif g[c] == 'G':
                result = result + self.GCodes[ int(digit)]

        result = result + "01010"

        for c in range(6,12):
            digit = int( with_checksum[1+c])
            if g[c] == 'L':
                result = result + self.LCodes[ int(digit)]
            elif g[c] == 'R':
                result = result + self.RCodes[ int(digit)]
            elif g[c] == 'G':
                result = result + self.GCodes[ int(digit)]

        result = result + "101"

        return result



# def draw_barcode(painter,x,y,barcode,height):
#     """ Draws a barcode on a QPainter """

#     barcode = barcode.to_binary()
#     hborder = 50
#     vborder = 20
#     barwidth = 3

#     h = height - 2*vborder # Widget's current height !

#     # Background (white helps the scanners)
#     painter.fillRect(x,y,2*hborder + len(barcode)*barwidth,h+2*vborder,QColor(255,255,255))

#     # left border
#     x = x + hborder

#     # Drawing the barcode bar by bar
#     for c in barcode:
#         if c == '1':
#             painter.fillRect(x,y+vborder,barwidth,h,QColor(0,0,0))
#         x = x + barwidth



class BarCodeIdentifier(object):

    @staticmethod
    def code_for(obj,obj2 = None):
        """ Given a "barcodable" object, this method returns a unique
        code for it. It is guaranteed that no two barcodable objects
        will have the same code unless they are the "same".
        The "same" means, same identifier in database.

        Note that although the barcodes are used to refer to tasks,
        their value is in no way related to the task_id.
        Barcodes denote "real" (operation, order, user) objects in
        the database. In the beginning, barcodes id were directly
        related to tasks id. However this was not practical. Indeed
        the barcode exists most often before the task is created.

        The returned code is not a barcode, it's a simple integer but
        it is suitable for barcode representation.
        """

        if isinstance(obj,Employee):
            return obj.employee_id
        elif isinstance(obj,Machine):
            return  4000000 + obj.resource_id
        elif isinstance(obj,OperationDefinition) and not obj.on_order and not obj.on_operation:
            # Reporting op def is done through TaskOnNonBillable
            return  5000000 + obj.operation_definition_id
        elif isinstance(obj,Operation) or isinstance(obj,TaskOnOperation):
            # Reporting time on operation is done through TaskOnOperation
            return 10000000 + obj.operation_id
        elif isinstance(obj,Order):
            if not isinstance(obj2,OperationDefinition):
                raise Exception("Indirect must be operation definition on order. You provided {} on {}".format(type(obj), type(obj2)))
            if not obj2.on_order:
                raise Exception("The operation definition provided is not imputable on order righ now")
            # TaskOnOrder
            return 900000000 + obj.order_id * 10000 + obj2.operation_definition_id
        elif obj == TaskActionReportType.day_in:
            return 1000
        elif obj == TaskActionReportType.day_out:
            return 1001
        else:
            raise Exception(u"Unrecognized instance : types are :{}/{},   key objects are :{} / {}".format(type(obj), type(obj2), obj,obj2))

    @staticmethod
    def barcode_to_id(code):
        """ Converts a barcode code to an object id in the database.
        Also returns the type of the object.
        """

        code = int(code)

        if          0 <= code < 1000:
            return [Employee, code]

        elif             code == 1000:
            return [TaskActionReportType.day_in]

        elif             code == 1001:
            return [TaskActionReportType.day_out]

        elif  4000000 <= code < 5000000:
            machine_id = code - 4000000
            return [Machine, machine_id]

        elif  5000000 <= code < 10000000:
            operation_definition_id = code - 5000000
            return [OperationDefinition, operation_definition_id]

        elif 10000000 <= code < 900000000:
            operation_id = code - 10000000
            return [Operation, operation_id]

        elif 900000000 <= code < 999999999:
            order_id = (code - 900000000) // 10000
            operation_definition_id = (code - 900000000) % 10000
            return [Order, OperationDefinition, order_id, operation_definition_id]

        else:
            raise Exception("Bar code syntax incorrect : {}".format(code))


if __name__ == "__main__":


    #    BarCode("7351353").to_binary()

    # EAN13

    print(BarCode("871125300120").to_binary())
    # 10101110110110011001100100110110111001011110101010111001011100101100110110110011100101101100101
    print(BarCode("978212345680").to_binary())
    # 10101110110001001001101100110010011011011110101010101110010011101010000100100011100101000010101
    print(BarCode("123456789120").to_binary()) # test checskum = 0
    # 10100100110111101001110101100010000101001000101010100100011101001100110110110011100101110010101
    print(BarCode("140519790000").to_binary())
    # 10101000110001101011100100110010010111001000101010111010011100101110010111001011100101110010101
