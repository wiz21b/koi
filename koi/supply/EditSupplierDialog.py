if __name__ == "__main__":
    from Logging import init_logging
    from Configurator import init_i18n,load_configuration, configuration
    init_logging()
    init_i18n()
    load_configuration()
    from db_mapping import metadata
    from datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


from koi.gui.MetaFormDialog import MetaFormDialog
from koi.gui.ProxyModel import TextLinePrototype,TextAreaPrototype
from koi.datalayer.supplier_mapping import Supplier

class EditSupplierDialog(MetaFormDialog):
    def __init__(self,parent):
        table_prototype = [ TextLinePrototype('fullname',_('Name'),editable=False) ]

        form_prototype = [ TextLinePrototype('fullname',_('Name'),nullable=False),
                           TextLinePrototype('phone',_('Phone'),nullable=True),
                           TextLinePrototype('phone2',_('Phone 2'),nullable=True),
                           TextLinePrototype('fax',_('Fax'),nullable=True),
                           TextLinePrototype('email',_('E-Mail'),nullable=True),
                           TextLinePrototype('address1',_('Address 1'),nullable=True),
                           TextLinePrototype('address2','',nullable=True),
                           TextLinePrototype('country',_('Country'),nullable=True),
                           TextAreaPrototype('notes',_('Notes'),nullable=True)]

        super(EditSupplierDialog,self).__init__(parent,_("Edit supplier"),_("Suppliers"),_("Detail"),
                                                Supplier,table_prototype,form_prototype,'fullname',lambda s:s.indexed_fullname)



if __name__ == "__main__":

    import sys
    from PySide.QtGui import QApplication

    app = QApplication(sys.argv)
    # widget = EditCustomerDialog(None)
    widget = EditSupplierDialog(None)
    # widget = EditEmployeeDialog(None,dao)
    # widget = EditUserDialog(None,dao)
    widget.show()

    app.exec_()
