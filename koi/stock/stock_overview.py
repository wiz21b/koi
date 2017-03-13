__author__ = 'stc'

if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication, QMainWindow
    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration
    init_logging()
    init_i18n()
    load_configuration()
    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)


from PySide.QtGui import QHBoxLayout, QVBoxLayout, QWidget

from koi.gui.ProxyModel import DatePrototype,TextLinePrototype,FloatNumberPrototype
from koi.QueryLineEdit import QueryLineEdit
from koi.gui.horse_panel import HorsePanel
from koi.gui.PrototypedModelView import PrototypedModelView, PrototypedQuickView
from koi.gui.PersistentFilter import PersistentFilter
from koi.gui.dialog_utils import showErrorBox, TitleWidget, SubFrame

app = QApplication(sys.argv)


title = "title"
content = "content"

def hlayout( left, right):
    l = QHBoxLayout()

    if isinstance(left, QWidget):
        l.addWidget(left)
    else:
        l.addLayout(left)

    if isinstance(right, QWidget):
        l.addWidget(right)
    else:
        l.addLayout(right)

    return l

def vlayout( left, right):
    l = QVBoxLayout()

    if isinstance(left, QWidget):
        l.addWidget(left)
    else:
        l.addLayout(left)

    if isinstance(right, QWidget):
        l.addWidget(right)
    else:
        l.addLayout(right)

    return l

#######################################################################################


# On veut un nouveau panel

def load_all_stock_items():
    session().query(StockItem).all()

# Ce que les utilisateurs veulent c'est : "je veux la liste de mes entrées de stock"
# Ils visualisent ça.

list_item = ListView()
list_item.show( load_all_stock_items())

# Ensuite on voudrait, le détail

detail_item = FormView()
list.selectionChanged.connect(detail.showData)


# On veut connaitre en particulier quelles commandes ont amenés un item donné

list_supply_order_parts = ListView()

def load_order_for_item(stock_item):
    parts = session().query(SupplyOrderPart).filter(SupplyOrderPart.stock_item == stock_item).all()
    list_supply_order_parts.show(parts)

list.selectionChanged.connect(load_order_for_item)





layout = hlayout(
    list_item,
    detail_item )
    
# ensuite on voudrait un moyen de filtrer
# L'utilisateur voit sa liste et il veut la filtrer. Il ne pense pas en
# terme de requête DB





prototype = [
    TextLinePrototype('stock_code',_("Item Nr"), editable=False),
    TextLinePrototype('fullname',_('Fullname'), editable=False)
]


filter = PersistentFilter(QueryLineEdit(),'supply_orders_overview')
service = None

def apply_filter(f):
    if f == '12134':
        objects = service.findByCode(f)
        model.loadObjects(objects)
    else:
        objects = service.findByQueryString(f)
        model.loadObjects(objects)



filter.activated.connect(apply_filter)


model = PrototypedModelView(prototype, None)
list_view = PrototypedQuickView(prototype, None)
detail_view = None

layout = hlayout(
    SubFrame(
        "Stock items",
        vlayout(
            filter,
            list_view), None),
    SubFrame(
        "Details",
        detail_view,
        None )
)



w = QWidget()
w.setLayout(l)
w.show()

app.exec_()
