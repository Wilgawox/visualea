"""
Author: Thomas Cokelaer

"""
from openalea.visualea.helpwidget import *

rst1 = """<div class="document">
<p>This is a simple docstring</p>
</div>
"""

rst2 = """<div class="document">
<p>This is a simple docstring</p>
<table class="docutils field-list" frame="void" rules="none">
<col class="field-name" />
<col class="field-body" />
<tbody valign="top">
<tr class="field"><th class="field-name">param a:</th><td class="field-body">test</td>
</tr>
</tbody>
</table>
</div>
"""



def test_rst2alea():

    res = rst2alea("This is a simple docstring")
    assert res == rst1, res
    res = rst2alea("This is a simple docstring\n\n:param a: test")
    assert res == rst2, res

from PyQt4.QtCore import *
from PyQt4.QtGui import *
app = QApplication([])

def test_helpwidget():
    help = HelpWidget()
    help.set_rst("This is a simple docstring")
    #assert help.getHtml()==rst1



test_rst2alea()
test_helpwidget()
