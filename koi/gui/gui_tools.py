from koi.translators import EURO_SIGN
from PySide.QtGui import QLabel

class EuroLabel(QLabel):
    def __init__(self,parent=None,flags=0):
        super(EuroLabel,self).__init__("--",parent,flags)

    def _amount_to_str(self, amount):
        if amount is None:
            return u"/ " + EURO_SIGN
        else:
            # Display an amount in the french/belgian way
            t = u"<b>{:,.2f}</b>".format(amount).replace(u",",u" ").replace(u".",u",")
            return t + EURO_SIGN

    def set_amount(self,f):
        if f is None:
            self.setText("--")
        else:
            self.setText(self._amount_to_str(f))
