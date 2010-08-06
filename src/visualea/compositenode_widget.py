# -*- python -*-
#
#       OpenAlea.Visualea: OpenAlea graphical user interface
#
#       Copyright 2006-2009 INRIA - CIRAD - INRA
#
#       File author(s): Samuel Dufour-Kowalski <samuel.dufour@sophia.inria.fr>
#                       Christophe Pradal <christophe.prada@cirad.fr>
#
#       Distributed under the CeCILL v2 License.
#       See accompanying file LICENSE.txt or copy at
#           http://www.cecill.info/licences/Licence_CeCILL_V2-en.html
#
#       OpenAlea WebSite : http://openalea.gforge.inria.fr
#
################################################################################
"""Composite Node Widgets"""

__license__ = "CeCILL v2"
__revision__ = " $Id: compositenode_widget.py 2329 2010-02-25 15:24:25Z dbarbeau $ "



import sys

from PyQt4 import QtCore, QtGui
from graph_operator import GraphOperator
from openalea.visualea.dataflowview import GraphicalGraph
from openalea.visualea.node_widget import NodeWidget
from openalea.visualea.util import busy_cursor, exception_display
from openalea.visualea.node_widget import DefaultNodeWidget
from tooltip import VertexTooltip

def rst2alea(text):
    """Convert docstring into HTML (assuming docstring is in reST format)

    This function uses docutils. Ideally it should use Sphinx

    :param text: the docstring

    :returns: text in HTML format

    .. todo:: implement conversion with Sphinx to have all SPhinx's directives interpreted.
    """
    try:
        from docutils import core
        from docutils.writers.html4css1 import Writer
        newdoc = text
        w = Writer()
        res = core.publish_parts(text, writer=w)['html_body']
        return res
    except:
        res = '<i>For a better rendering, install docutils or sphinx !</i><br/>'
        res  += text
        for name in [':Parameters:', ':Returns:', ':Keywords:', ':Author:', ':Authors:']:
            res = res.replace(name, '<b>'+name.replace(':','') + '</b>')
        res = res.replace('\n','<br />')

        return res

class DisplayGraphWidget(QtGui.QWidget, NodeWidget):
    """ Display widgets contained in the graph """

    def __init__(self, node, parent=None, autonomous=False):

        QtGui.QWidget.__init__(self, parent)
        NodeWidget.__init__(self, node)

        vboxlayout = QtGui.QVBoxLayout(self)
        self.vboxlayout = vboxlayout

        self.node = node

        # Container
        self.container = QtGui.QTabWidget(self)
        vboxlayout.addWidget(self.container)


        if(autonomous):
            self.set_autonomous()
            return

        # empty_io is a flag to define if the composite widget add only io widgets

        # Trey to create a standard node widget for inputs
        default_widget = DefaultNodeWidget(node, parent)

        if(default_widget.is_empty()):
            default_widget.close()
            default_widget.destroy()
            del default_widget
            empty_io = True

        else:
            empty_io = False
            self.container.addTab(default_widget, "Inputs")


        # Add subwidgets (Need to sort widget)
        for id in node.vertices():

            subnode = node.node(id)

            # Do not display widget if hidden
            hide = subnode.internal_data.get('hide', False)
            user_app = subnode.internal_data.get('user_application', False)
            if(hide and not empty_io): continue

            if(not user_app):
                # ignore node with all input connected
                states = [ bool(subnode.get_input_state(p)=="connected")
                           for p in xrange(subnode.get_nb_input())]

                if(all(states)): continue

            # Add tab
            try:
                factory = subnode.get_factory()
                widget = factory.instantiate_widget(subnode, self)
                assert widget
            except:
                continue

            if(widget.is_empty()) :
                widget.close()
                del widget
            else :
                # Add as tab
                caption = "%s"%(subnode.caption)
                self.container.addTab(widget, caption)




    def set_autonomous(self):
        """ Create autonomous widget with user applications buttons and dataflow """

        # User App panel
        userapp_widget = QtGui.QWidget(self)
        userapp_layout = QtGui.QVBoxLayout(userapp_widget)


        for id in self.node.vertices():

            subnode = self.node.node(id)
            user_app = subnode.internal_data.get('user_application', False)

            # add to user app panel
            if(user_app):

                label = QtGui.QLabel(subnode.caption, userapp_widget)
                runbutton = QtGui.QPushButton("Run", userapp_widget)
                runbutton.id = id

                widgetbutton = QtGui.QPushButton("Widget", userapp_widget)
                widgetbutton.id = id

                self.connect(runbutton, QtCore.SIGNAL("clicked()"), self.run_node)
                self.connect(widgetbutton, QtCore.SIGNAL("clicked()"), self.open_widget)

                buttons = QtGui.QHBoxLayout()
                buttons.addWidget(label)
                buttons.addWidget(runbutton)
                buttons.addWidget(widgetbutton)
                userapp_layout.addLayout(buttons)


        dataflow_widget = GraphicalGraph.create_view(self.node, parent=self.container)
        #dataflow_widget = qtgraphview.View(self.container, self.node)
        self.container.addTab(dataflow_widget, "Dataflow")
        self.dataflow_widget = dataflow_widget

        self.container.addTab(userapp_widget, "User Applications")

        exitbutton = QtGui.QPushButton("Exit", self)
        self.connect(exitbutton, QtCore.SIGNAL("clicked()"), self.exit)

        buttons = QtGui.QHBoxLayout()
        buttons.addWidget(exitbutton)
        self.vboxlayout.addLayout(buttons)


    @exception_display
    @busy_cursor
    def run_node(self):
        self.node.eval_as_expression(self.sender().id)

    def open_widget(self):
        operator = GraphOperator(graph=self.node)
        operator.vertex_open(self.sender().id)

    def exit(self):
        self.parent().close()

