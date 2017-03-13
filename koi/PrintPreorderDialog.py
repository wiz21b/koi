if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication
    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()
    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from PySide.QtCore import Slot
from PySide.QtGui import QDialogButtonBox,QDialog,QTextEdit,QVBoxLayout,QLabel

from koi.dao import dao
from koi.gui.dialog_utils import TitleWidget

class PrintPreorderDialog (QDialog):
    def __init__(self,parent):
        super(PrintPreorderDialog,self).__init__(parent)

        title = _("Print preorder")
        self.setWindowTitle(title)

        top_layout = QVBoxLayout()

        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)

        info = QLabel(_("Here you can give a small message that will be printed togetehr with the preorder."),self)
        info.setWordWrap(True)
        top_layout.addWidget(info)

        top_layout.addWidget(QLabel(_("Header text")))

        self.message_text_area = QTextEdit()
        top_layout.addWidget(self.message_text_area)

        top_layout.addWidget(QLabel(_("Footer text")))

        self.message_text_area_footer = QTextEdit()
        top_layout.addWidget(self.message_text_area_footer)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.StandardButton.Cancel)
        self.buttons.addButton( QDialogButtonBox.Ok)

        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)


    def set_preorder(self,preorder_id):
        preorder = dao.order_dao.find_by_id_frozen(preorder_id)

        if preorder.preorder_print_note:
            self.message_text_area.setText(preorder.preorder_print_note)
        else:
            self.message_text_area.setText(_("Sir,\nPlease find your preorder below as discussed earlier. Please send us a signed copy to complete the order.\nBest regards"))

        if preorder.preorder_print_note_footer:
            self.message_text_area_footer.setText(preorder.preorder_print_note_footer)
        else:
            self.message_text_area_footer.setText(_("Best regards,\n\nthe company team."))

    def get_print_notes(self):
        return self.message_text_area.toPlainText().strip(),self.message_text_area_footer.toPlainText().strip()

    @Slot()
    def accept(self):
        super(PrintPreorderDialog,self).accept()

    @Slot()
    def reject(self):
        super(PrintPreorderDialog,self).reject()


if __name__ == "__main__":

    app = QApplication(sys.argv)
    d = PrintPreorderDialog(None)
    d.set_preorder( dao.order_dao.find_by_id(4000))
    d.exec_()
