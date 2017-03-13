from koi.OperationDefinitionsCache import operation_definition_cache
from koi.gui.MetaFormDialog import MetaFormDialog
from koi.gui.ProxyModel import TextLinePrototype,BooleanPrototype,OperationDefinitionPrototype, MachineZonePrototype
from koi.machine.machine_mapping import Machine
from koi.machine.machine_service import machine_service
from koi.translators import text_search_normalize

class EditMachinesDialog(MetaFormDialog):
    def __init__(self,parent):
        self.key_field = 'machine_id'

        list_prototype = []
        list_prototype.append( TextLinePrototype('fullname',_('Name'),editable=False))

        form_prototype = [ TextLinePrototype('fullname',_('Name'),nullable=False),
                           OperationDefinitionPrototype('operation_definition_id',_('Operation'),operation_definition_cache.all_on_order_part(),nullable=False),
                           BooleanPrototype('is_active',_('Active'),nullable=False),
                           MachineZonePrototype('clock_zone',_('Zone'),nullable = True)]

        super(EditMachinesDialog,self).__init__(parent,_("Machine edit"),_("Machines"),_("Detail"),
                                                Machine,list_prototype,form_prototype,'fullname',index_builder=lambda o:text_search_normalize(o.fullname))

        self.setMinimumWidth(800)


    def save_object(self,form_data):
        res = super(EditMachinesDialog, self).save_object(form_data)
        machine_service._reset_cache()
        return res


    def objects_list(self):
        return machine_service.all_machines()
