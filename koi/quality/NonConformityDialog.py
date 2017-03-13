if __name__ == "__main__":
    import sys
    from PySide.QtGui import QApplication

    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration, configuration
    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session
    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from datetime import datetime

from PySide.QtCore import Signal, Slot, Qt
from PySide.QtGui import QHBoxLayout,QVBoxLayout, QDialogButtonBox,QDialog, QWidget, QLabel, QTextEdit, QPushButton, QFrame, QComboBox

from koi.base_logging import mainlog
from koi.dao import dao
from koi.datalayer.quality import Comment
from koi.datalayer.quality import QualityEvent, QualityEventType
from koi.datalayer.sqla_mapping_base import Base
from koi.doc_manager.docs_collection_widget import DocumentCollectionWidget
from koi.doc_manager.documents_mapping import Document
from koi.gui.ProxyModel import QualityEventTypePrototype
from koi.gui.dialog_utils import TitleWidget, confirmationBox
from koi.junkyard.sqla_dict_bridge import ChangeTracker, InstrumentedRelation, make_change_tracking_dto
from koi.session.UserSession import user_session
from koi.translators import date_to_s


# class QualityEvent:
#
#     def __init__(self):
#         self.quality_event_id = None
#         self.when = date.today()
#         self.kind = QualityEventType.non_conform_customer
#         self.who_id = user_session.user_id
#         self.order_part_id = None




def make_quality_event_dto( kind : QualityEventType, order_part_id : int):
    assert order_part_id
    assert kind

    qe = make_change_tracking_dto(QualityEvent, obj=None, recursive= {Document})
    qe.order_part_id = order_part_id
    qe.when = datetime.now()
    qe.description = ""
    qe.kind = kind
    qe.who_id = user_session.user_id

    return qe



class CommentsWidget(QWidget):

    def _append_comment(self, comment):
        l = QLabel(comment.text)
        l.setWordWrap(True)
        l.setStyleSheet("background-color: #ffffff;")
        # l.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard | Qt.LinksAccessibleByMouse | Qt.LinksAccessibleByKeyboard)

        self._comments_layout.addWidget(l)

        l = QLabel("Chuck Norris, 14/4/2016")
        l.setStyleSheet("color: #808080;")
        self._comments_layout.addWidget(l)
        self._comments_layout.setAlignment( l, Qt.AlignRight)
        self.comments_list_widget.setVisible( True)

    def show_comments(self, comments):

        self._comments = comments or []

        while self._comments_layout.count() > 0:
            self._comments_layout.removeItem(0)

        for comment in comments:
            self._append_comment(comment)

        self.comments_list_widget.setVisible( len(self._comments) > 0 )

    @Slot()
    def submit_comment(self):
        comment = self.text_edit.toPlainText().strip()

        if comment:

            c = self._change_tracker.make_change_tracking_dto(Comment)
            c.text = comment
            self._append_comment(c)
            self.text_edit.setText("")

    def __init__(self, parent, change_tracker : ChangeTracker):
        super(CommentsWidget,self).__init__(parent)

        self._change_tracker = change_tracker
        #self.setObjectName("zwhite")
        layout = QVBoxLayout()



        self.comments_list_widget = QFrame(self) # If you use QWidget, the background won't be set; don't know why :-(
        self.comments_list_widget.setStyleSheet("background: white;")
        self.comments_list_widget.setAutoFillBackground(True)
        #self.comments_list_widget.setObjectName("zwhite")

        self._comments_layout = QVBoxLayout()
        self.comments_list_widget.setLayout(self._comments_layout)

        self.comments_list_widget.hide()

        self.text_edit = QTextEdit(self)
        self.submit_button = QPushButton(("Add"),self)

        layout.addWidget(self.comments_list_widget)
        layout.addWidget(self.text_edit)
        hlayout = QHBoxLayout()

        hlayout.addStretch()
        hlayout.addWidget(self.submit_button)
        layout.addLayout(hlayout)
        self.setLayout(layout)

        self.submit_button.clicked.connect(self.submit_comment)


class Nonconformity2Widget(QWidget):
    """ Non confomity data have changed """
    issue_changed = Signal()

    @Slot()
    def _documents_changed_slot(self):
        self.issue_changed.emit()

    @Slot()
    def comment_changed(self):
        if self._current_qe:
            if self._track_changes:
                self.issue_changed.emit()
            self._current_qe.description = self.comments_widget.toPlainText()

    @Slot()
    def event_type_changed(self, index):
        if self._current_qe:
            if self._track_changes:
                self.issue_changed.emit()
            self._current_qe.kind = self._quality_event_prototype.edit_widget_data()

    @Slot(int)
    def set_quality_issue(self, qe):
        if qe:
            mainlog.debug("set_quality_issue : qe.type = {}".format(qe.kind))
            self._track_changes = False
            self._current_qe = qe # Must be set before callin set text ! Else the past "current_qe" will be changed :-)
            self.comments_widget.setText( qe.description)
            self._quality_event_prototype.set_edit_widget_data( qe.kind)
            self.documents.set_model_data(qe)
            self._track_changes = True
        else:
            self._current_qe = None
        self._enable_editing()

    def _enable_editing(self):

        show = self._current_qe is not None

        # returns None ??? self.layout().setVisible(show)

        self.comments_widget.setVisible(show)
        self.documents.setVisible(show)
        self._quality_event_type_widget.setVisible(show)
        self._type_label.setVisible(show)
        self._description_label.setVisible(show)


    def __init__(self, parent, remote_documents_service):
        super(Nonconformity2Widget,self).__init__(parent)

        self._track_changes = True
        self._current_qe = None

        top_layout = QVBoxLayout()

        self._quality_event_prototype = QualityEventTypePrototype("kind",_("Kind"))
        self._quality_event_type_widget = self._quality_event_prototype.edit_widget(self)
        self._quality_event_type_widget.activated.connect(self.event_type_changed)

        self._type_label = QLabel(_("Type :"))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self._type_label)
        hlayout.addWidget(self._quality_event_prototype.edit_widget(self))
        hlayout.setStretch(0,0)
        hlayout.setStretch(1,1)
        top_layout.addLayout(hlayout)

        # self.comments_widget = CommentsWidget(self, self._change_tracker)

        self.comments_widget = QTextEdit(self)
        self.comments_widget.textChanged.connect(self.comment_changed)
        self._description_label = QLabel(_("Description :"))
        top_layout.addWidget(self._description_label)
        top_layout.addWidget(self.comments_widget)

        self.documents = DocumentCollectionWidget(parent=self, doc_service=remote_documents_service, used_category_short_name='Qual.', no_header=True)
        self.documents.documents_list_changed.connect(self._documents_changed_slot)
        top_layout.addWidget(self.documents)
        top_layout.addStretch()

        self._enable_editing()
        self.setLayout(top_layout)





class NonconformitiesWidget(QWidget):
    # def set_comments(self, comments):
    #     self.comments_widget.show_comments(comments)

    # @Slot()
    # def comment_changed(self):
    #     if self._current_qe:
    #         if self._track_changes:
    #             self.issues_changed.emit()
    #         self._current_qe.description = self.comments_widget.toPlainText()
    #
    # @Slot()
    # def event_type_changed(self, index):
    #     if self._current_qe:
    #         if self._track_changes:
    #             self.issues_changed.emit()
    #         self._current_qe.kind = self._quality_event_prototype.edit_widget_data()

    @Slot(int)
    def set_quality_issue(self, ndx : int):
        if ndx >= 0:
            qe = self.quality_events[ndx]
            self._current_qe = qe # Must be set before callin set text ! Else the past "current_qe" will be changed :-)
            self.nc_edit.set_quality_issue(qe)
        else:
            self._current_qe = None
            self.nc_edit.set_quality_issue(None)

        self._enable_editing()

        # if ndx >= 0:
        #     self._track_changes = False
        #     qe = self.quality_events[ndx]
        #     self._current_qe = qe # Must be set before callin set text ! Else the past "current_qe" will be changed :-)
        #     self.comments_widget.setText( qe.description)
        #     self._quality_event_prototype.set_edit_widget_data( qe.kind)
        #     self.documents.set_model_data(qe)
        #     self._track_changes = True
        # else:
        #     self._current_qe = None
        # self._enable_editing()

    @Slot()
    def remove_quality_issue(self):
        ndx = self.quality_issue_chooser.currentIndex()

        if ndx >= 0: # defensive programming

            qe = self.quality_events[ndx]

            if (not qe.quality_event_id) or \
                confirmationBox(_("Remove non conformity"),
                                _("Please confirm you want to remove the issue {} ({})").format(self._quality_event_title(qe), qe.description)):

                del self.quality_events[ndx]
                self.quality_issue_chooser.removeItem(ndx) # so the dropbox must trigger selection of remaining QE

                if not self.quality_events:
                    self._enable_editing()

                if self._track_changes:
                    self.issues_changed.emit()

    def _quality_event_title(self, qe):
        if qe.quality_event_id:
            id = qe.human_identifier
            # id = str(qe.quality_event_id)
        else:
            id = "-"

        return _("{} ({})").format(id, date_to_s(qe.when))

    @Slot()
    def add_quality_issue(self):
        # qe = self._change_tracker.make_change_tracking_dto(QualityEvent, recursive= {Document})
        qe = make_change_tracking_dto(QualityEvent, obj=None, recursive= {Document})
        qe.order_part_id = self.order_part_id
        qe.when = datetime.now()
        qe.description = ""
        qe.kind = QualityEventType.non_conform_intern
        qe.who_id = user_session.user_id
        self.quality_events.append(qe)

        self.quality_issue_chooser.addItem( self._quality_event_title(qe))
        self.quality_issue_chooser.setCurrentIndex( len( self.quality_events) - 1)
        if self._track_changes:
            self.issues_changed.emit()

        self.nc_edit.set_quality_issue(qe)

    def _enable_editing(self):
        show = self.quality_issue_chooser.count() > 0
        # Only the one who has encoded can delete
        # Editing is authorized to everybody
        can_remove = self._current_qe and (user_session.user_id == self._current_qe.who_id)

        # self.comments_widget.setVisible(show)
        # self.documents.setVisible(show)
        # self._quality_event_type_widget.setVisible(show)
        # self._type_label.setVisible(show)

        self.remove_quality_issue_button.setEnabled(show and can_remove)

    def set_quality_events(self, quality_events):
        assert quality_events is not None

        self.quality_events = quality_events
        #print("Setting {} quality events".format(len(self.quality_events)))
        self.quality_issue_chooser.clear()

        if self.quality_events:
            for qe in self.quality_events:
                self.quality_issue_chooser.addItem( self._quality_event_title(qe))
            self.quality_issue_chooser.setCurrentIndex( 0)


    def __init__(self, parent, remote_documents_service):
        super(NonconformitiesWidget,self).__init__(parent)

        self._track_changes = True
        self._current_qe = None
        self._change_tracker = ChangeTracker(Base)
        self.order_part_id = None
        self.quality_events = InstrumentedRelation()

        top_layout = QVBoxLayout()
        top_layout.addWidget(QLabel(u"<h3>{}</h3>".format(_("Non conformity"))))

        control_layout = QHBoxLayout()
        self.quality_issue_chooser = QComboBox(self)
        # self.quality_issue_chooser.addItems(["a","b"])
        # self.quality_issue_chooser.activated.connect(self.set_quality_issue)
        self.quality_issue_chooser.currentIndexChanged.connect(self.set_quality_issue)
        self.add_quality_issue_button = QPushButton(_("Add"))
        self.remove_quality_issue_button = QPushButton(_("Remove"))

        self.add_quality_issue_button.clicked.connect(self.add_quality_issue)
        self.remove_quality_issue_button.clicked.connect(self.remove_quality_issue)

        control_layout.addWidget(self.quality_issue_chooser)
        control_layout.addWidget(self.add_quality_issue_button)
        control_layout.addWidget(self.remove_quality_issue_button)
        control_layout.setStretch(0,1)
        
        top_layout.addLayout(control_layout)

        horizontalLine 	=  QFrame(self)
        horizontalLine.setFrameStyle(QFrame.HLine)
        # horizontalLine.setMinimumHeight(1) # seems useless
        # horizontalLine.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum) # seems useless
        top_layout.addWidget(horizontalLine)

        self.nc_edit = Nonconformity2Widget(self, remote_documents_service)
        self.nc_edit.issue_changed.connect(self._issue_edited_slot)
        top_layout.addWidget(self.nc_edit)

        self.setLayout(top_layout)

    """ Non confomity data have changed """
    issues_changed = Signal()

    # @Slot()
    # def _documents_changed_slot(self):
    #     self.issues_changed.emit()

    @Slot()
    def _issue_edited_slot(self):
        self.issues_changed.emit()



class NonConformityDialog(QDialog):

    def set_blank_quality_issue(self,kind, order_part_id):
        order_part_dto = dao.order_part_dao.find_by_id_frozen(order_part_id)
        self.current_qe = make_quality_event_dto( kind, order_part_dto.order_part_id)
        self._explanation.setText(_("<p>Please fill in some details about the non conformity. This non conformity is concerns</p> <p> <b>{}</b> : {}</p>").format(
            order_part_dto.human_identifier, order_part_dto.description))
        self._quality_widget.set_quality_issue(self.current_qe)

    def quality_event(self):
        return self.current_qe

    def __init__(self,parent,remote_documents_service):
        super(NonConformityDialog,self).__init__(parent)

        self._quality_widget = Nonconformity2Widget(self, remote_documents_service)

        title = _("Create a non conformity")
        self.setWindowTitle(title)
        top_layout = QVBoxLayout()
        self.title_widget = TitleWidget(title,self)
        top_layout.addWidget(self.title_widget)

        self._explanation = QLabel()
        self._explanation.setWordWrap(True)
        top_layout.addWidget(self._explanation)

        top_layout.addWidget(self._quality_widget)

        self.buttons = QDialogButtonBox()
        self.buttons.addButton( QDialogButtonBox.Ok)
        self.buttons.addButton( QDialogButtonBox.Cancel)
        top_layout.addWidget(self.buttons)

        self.setLayout(top_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    @Slot()
    def accept(self):
        return super(NonConformityDialog,self).accept()

    @Slot()
    def reject(self):
        return super(NonConformityDialog,self).reject()


if __name__ == "__main__":
    # python -m koi.quality.NonConformityDialog

    from koi.service_config import remote_documents_service
    from koi.configuration.business_functions import business_computations_service
    from koi.junkyard.services import services
    employee = services.employees.any()


    user_session.open(employee)

    # from koi.server.json_decorator import JsonCallWrapper
    # from koi.doc_manager.documents_service import documents_service
    # remote_documents_service = JsonCallWrapper(documents_service,JsonCallWrapper.HTTP_MODE)

    app = QApplication(sys.argv)
    dialog = NonConformityDialog(None, remote_documents_service)

    order_part = dao.order_part_dao.find_youngest()
    print(order_part.nb_non_conformities)

    dialog.set_blank_quality_issue(QualityEventType.non_conform_customer, order_part.order_part_id)

    # from koi.datalayer.quality import Comment
    #
    # c = Comment()
    # c.text = "Lorem ipsum etc " * 10
    # dialog.set_comments([c,c,c])
    dialog.exec_()

    if dialog.result() == QDialog.Accepted:
        business_computations_service.mark_as_non_conform( dialog.quality_event())




