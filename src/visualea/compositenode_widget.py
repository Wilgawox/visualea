# -*- python -*-
#
#       OpenAlea.Visualea: OpenAlea graphical user interface
#
#       Copyright 2006 - 2007 INRIA - CIRAD - INRA  
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


__doc__="""
Composite Node Widgets
"""

__license__= "CeCILL v2"
__revision__=" $Id$ "



import sys
import math
import weakref

from PyQt4 import QtCore, QtGui
from openalea.core.node import NodeWidget, RecursionError
from openalea.core.pkgmanager import PackageManager
from openalea.core.observer import lock_notify
from openalea.core.settings import Settings
from openalea.core.observer import AbstractListener
import annotation

from dialogs import DictEditor, ShowPortDialog
from util import busy_cursor, exception_display, open_dialog
from node_widget import DefaultNodeWidget


class DisplayGraphWidget(NodeWidget, QtGui.QWidget):
    """ Display widgets contained in the graph """
    
    def __init__(self, node, parent=None):

        NodeWidget.__init__(self, node)
        QtGui.QWidget.__init__(self, parent)

        vboxlayout = QtGui.QVBoxLayout(self)
        self.vboxlayout = vboxlayout
        # flag to define if the composite widget add only io widgets 
        empty_io = False 

        # Add inputs port
        default_widget = DefaultNodeWidget(node, parent)
        if(default_widget.is_empty()):
            default_widget.close()
            default_widget.destroy()
            del default_widget
            empty_io = True
        else:
            vboxlayout.addWidget(default_widget)

        # Add subwidgets
        for id in node.vertices():

            subnode = node.node(id)
            if(subnode.internal_data.get('hide', False) and not empty_io): continue

            try:
                factory = subnode.get_factory()
                widget = factory.instantiate_widget(subnode, self)
            except:
                continue
            
            if(widget.is_empty()) :
                widget.close()
                del widget
                continue
            
            else : #vboxlayout.addWidget(widget)
            
                caption = "%s"%(subnode.caption)
                groupbox = QtGui.QGroupBox(caption, self)
                layout = QtGui.QVBoxLayout(groupbox)
                layout.setMargin(3)
                layout.setSpacing(2)
                layout.addWidget(widget)
            
                vboxlayout.addWidget(groupbox)
           

    def set_autonomous(self):
        """ Add Run bouton and close button """
        
        runbutton = QtGui.QPushButton("Run", self)
        exitbutton = QtGui.QPushButton("Exit", self)
        self.connect(runbutton, QtCore.SIGNAL("clicked()"), self.run)
        self.connect(exitbutton, QtCore.SIGNAL("clicked()"), self.exit)

        buttons = QtGui.QHBoxLayout()
        buttons.addWidget(runbutton)
        buttons.addWidget(exitbutton)
        self.vboxlayout.addLayout(buttons)
        

    @exception_display
    @busy_cursor    
    def run(self):
        self.node.eval()

    def exit(self):
        self.parent().close()
        

        

class EditGraphWidget(NodeWidget, QtGui.QGraphicsView):
    """ Graph widget allowing to edit the network """
    
    def __init__(self, node, parent=None):

        NodeWidget.__init__(self, node)
        QtGui.QGraphicsView.__init__(self, parent)

        self.setCacheMode(QtGui.QGraphicsView.CacheBackground)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setTransformationAnchor(QtGui.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtGui.QGraphicsView.AnchorViewCenter)
        self.setAlignment(QtCore.Qt.AlignLeft|QtCore.Qt.AlignTop)
        self.setDragMode(QtGui.QGraphicsView.RubberBandDrag)
            
        self.scale(0.8, 0.8)

        self.newedge = None

        # dictionnary mapping elt_id and graphical items
        self.graph_item = {}
        
        # dictionnary mapping elt_id with tupel (dialog, widget)
        self.node_dialog = {}

        self.rebuild_scene()

        


    # Node property 
    def set_node(self, node):
        """ Define the associated node (overloaded) """
        NodeWidget.set_node(self, node)
        self.rebuild_scene()

    node = property(NodeWidget.get_node, set_node)


    def clear_scene(self):
        """ Remove all items from the scene """

        # close dialog
        #for (dialog, widget) in self.node_dialog.items():
            #dialog.close()
            #dialog.destroy()
            
        self.node_dialog = {}

        # Close items
        self.graph_item = {}
        # Scene
        scene = QtGui.QGraphicsScene(self)
        scene.setItemIndexMethod(QtGui.QGraphicsScene.NoIndex)
        self.setScene(scene)
        

    @lock_notify      
    def rebuild_scene(self):
        """ Build the scene with graphic node and edge"""

        self.clear_scene()
        # create items
        ids = self.node.vertices()
        for eltid in ids:
            self.add_graphical_node(eltid)

        # create connections
        dataflow = self.node
        for eid in dataflow.edges():
            (src_id, dst_id) = dataflow.source(eid), dataflow.target(eid)
            
            src_item = self.graph_item[src_id]
            dst_item = self.graph_item[dst_id]

            src_port = dataflow.local_id(dataflow.source_port(eid))
            tgt_port = dataflow.local_id(dataflow.target_port(eid))
            
            src_connector = src_item.get_output_connector(src_port)
            dst_connector = dst_item.get_input_connector(tgt_port)

            self.add_graphical_connection(src_connector, dst_connector)


    # Mouse events

    def mouseMoveEvent(self, event):
        
        # update new edge position
        if(self.newedge) :
            self.newedge.setMousePoint(self.mapToScene(event.pos()))
            event.ignore()
        else:
            QtGui.QGraphicsView.mouseMoveEvent(self, event)


    def mousePressEvent(self, event):

        if (event.buttons() & QtCore.Qt.LeftButton):
            QtGui.QGraphicsView.mousePressEvent(self, event)
            

    @lock_notify
    def mouseReleaseEvent(self, event):
        
        if(self.newedge):
            try:
                item = self.itemAt(event.pos())
                if(item and isinstance(item, ConnectorIn)
                   and isinstance(self.newedge.connector(), ConnectorOut)):

                    self.connect_node(self.newedge.connector(), item)
                    self.add_graphical_connection( self.newedge.connector(), item)


                elif(item and isinstance(item, ConnectorOut) and
                     isinstance(self.newedge.connector(), ConnectorIn) ):

                    self.connect_node(item, self.newedge.connector())
                    self.add_graphical_connection( item, self.newedge.connector())
                    
            finally:
                self.scene().removeItem(self.newedge)
                self.newedge = None

        QtGui.QGraphicsView.mouseReleaseEvent(self, event)


#     def itemMoved(self, item, newvalue):
#         """ function called when a node item has moved """


    def wheelEvent(self, event):
        #self.centerOn(self.mapToScene(event.globalPos()))
        self.scaleView(-event.delta() / 1200.0)
        QtGui.QGraphicsView.wheelEvent(self, event)
        
    def scaleView(self, scaleFactor):

        scaleFactor += 1
        self.scale(scaleFactor, scaleFactor)

    
    def notify(self, sender, event):
        """ Function called by observed objects """

        if(not event): return

        if(event[0] == "connection_modified"):
            self.rebuild_scene()
            
        elif(event[0] == "graph_modified"):
            self.rebuild_scene()


    def start_edge(self, connector):
        """ Start to create an edge """

        self.newedge= SemiEdge(self, connector, None, self.scene())

  
    # graph edition

    def add_graphical_node(self, eltid):
        """
        Add the node graphical representation in the widget
        @param eltid : element id 
        """

        subnode = self.node.node(eltid)

        # Annotation
        if(subnode.__class__.__dict__.has_key("__graphitem__")):

            # Test if Annotation is available
            if("Annotation" in subnode.__graphitem__ and
               not annotation.is_available()):
                mess = QtGui.QMessageBox.warning(None, "Error",
                                                 "This function need PyQT >= 4.2")
                return None
            else:                
                classobj = eval(subnode.__graphitem__)
                gnode = classobj(self, eltid)

        # Standard Node
        else:
            nin = subnode.get_nb_input()
            nout = subnode.get_nb_output()
            gnode = GraphicalNode(self, eltid)

            # do not display in and out nodes if not necessary
            if(nin == 0 and nout == 0 and
               (eltid == self.node.id_in or eltid == self.node.id_out)):
                gnode.setVisible(False)
 
        self.graph_item[eltid] = gnode
        
        return gnode


    def add_graphical_connection(self, connector_src, connector_dst):
        """ Return the new edge """
        
        edge = Edge(self, connector_src.parentItem(), connector_src.index(),
                    connector_dst.parentItem(), connector_dst.index(),
                    None, self.scene())

        return edge
        
    
    def connect_node(self, connector_src, connector_dst):
        """
        Convenience function
        Connect the node in the graph
        """
        
        self.node.connect(connector_src.parentItem().get_id(), 
                          connector_src.index(),
                          connector_dst.parentItem().get_id(), 
                          connector_dst.index())


    def open_item(self, elt_id):
        """ Open the widget of the item elt_id """

        # Test if the node is already opened
        if(self.node_dialog.has_key(elt_id)):
            (d,w) = self.node_dialog[elt_id]

            if(d.isVisible()):
                d.raise_ ()
                d.activateWindow ()
            else:
                d.show()

            return

        node = self.node.node(elt_id)

        # Click on IO node
        # TO refactore 
        from openalea.core.compositenode import CompositeNodeInput, CompositeNodeOutput
        from dialogs import IOConfigDialog
        if(isinstance(node, CompositeNodeInput) or
           isinstance(node, CompositeNodeOutput)):
            
            dialog = IOConfigDialog(self.node.input_desc,
                                    self.node.output_desc,
                                    parent=self)
            ret = dialog.exec_()

            if(ret):
                self.node.set_io(dialog.inputs, dialog.outputs)
                self.rebuild_scene()
            return
        ########### End refactor
            
        factory = node.get_factory()
        if(not factory) : return
        # We Create a new Dialog
        widget = factory.instantiate_widget(node, self)
        
        if (widget.is_empty()):
            widget.close()
            del widget
            return

        container = open_dialog(self, widget, factory.get_id(), False)
        self.node_dialog[elt_id] = (container, widget)


    def get_selected_item(self):
        """ Return the list id of the selected item """

        # get the selected id
        return [ id for id, item in self.graph_item.items() if item.isSelected()]


    def remove_selection(self):
        """ Remove selected nodes """

        # Ensure to not remove in and out node
        self.graph_item[self.node.id_in].setSelected(False)
        self.graph_item[self.node.id_out].setSelected(False)

        # remove the nodes
        nodes = self.get_selected_item()
        for i in nodes : self.remove_node(i)

        # Remove other item
        items = self.scene().selectedItems()
        for i in items : i.remove()


    def group_selection(self, factory):
        """
        Export selected node in factory
        """

        s = self.get_selected_item()
        if(not s): return None

        self.node.to_factory(factory, s, auto_io=True)
        
        pos = self.get_center_pos(s)

        # Instantiate the new node
        if(self.add_new_node(factory, pos)):
            self.remove_selection()


    def copy(self, session):
        """ Copy Selection """
        
        s = self.get_selected_item()
        if(not s): return 

        session.clipboard.clear()
        self.node.to_factory(session.clipboard, s, auto_io=False)


    @lock_notify
    def paste(self, session):
        """ Paste from clipboard """

        l = lambda x :  x + 30
        modifiers = [('posx', l), ('posy', l)]
        new_ids = session.clipboard.paste(self.node, modifiers)

        self.rebuild_scene()
        # select new nodes
        for i in new_ids:
            item = self.graph_item[i]
            item.setSelected(True)


    def get_center_pos(self, items):
        """ Return the center of items (items is the list of id) """

        l = len(items)
        if(l == 0) : return QtCore.QPointF(30,30)
        
        sx = sum((self.graph_item[i].pos().x() for i in items))
        sy = sum((self.graph_item[i].pos().y() for i in items))
        return QtCore.QPointF( float(sx)/l, float(sy)/l )
    

    def close_node_dialog(self, elt_id):
        """ Close a node dialog """

        # close dialog
        try:
            (dialog, widget) = self.node_dialog[elt_id]
            dialog.close()
            dialog.destroy()
            
            del(self.node_dialog[elt_id])
        except KeyError:
            pass


    @lock_notify      
    def remove_node(self, elt_id):
        """ Remove node identified by elt_id """

        if(elt_id == self.node.id_in) : return
        if(elt_id == self.node.id_out) : return

        self.close_node_dialog(elt_id)
        
        item = self.graph_item[elt_id]
        try:
            item.remove_connections()
        except:
            pass
        
        self.scene().removeItem(item)
        del(self.graph_item[elt_id])

        self.node.remove_node(elt_id)



    @lock_notify
    def remove_connection(self, edge_item):
        """ Remove a connection """

        connector_src = edge_item.source
        connector_dst = edge_item.dest
        
        connector_src.edge_list.remove(edge_item)
        connector_dst.edge_list.remove(edge_item)

        edge_item.dest = None
        edge_item.source= None
        
        self.scene().removeItem(edge_item)

        self.node.disconnect(connector_src.parentItem().get_id(), connector_src.index(),
                               connector_dst.parentItem().get_id(), connector_dst.index()) 
    

    # Drag and Drop from TreeView support
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("openalea/nodefactory"):
            event.accept()
        else:
            QtGui.QGraphicsView.dragEnterEvent(self, event)


    def dragMoveEvent(self, event):
        if ( event.mimeData().hasFormat("openalea/nodefactory") ):
            event.setDropAction(QtCore.Qt.MoveAction)
            event.accept()
        else:
            QtGui.QGraphicsView.dragMoveEvent(self, event)


    @lock_notify
    def add_new_node(self, factory, position):
        """ Convenience function : Return True if success"""
        
        try:
            newnode = factory.instantiate([self.node.factory.get_id()])
            newnode.set_data('posx', position.x(), False)
            newnode.set_data('posy', position.y(), False)
        
            newid = self.node.add_node(newnode)
            self.add_graphical_node(newid)
            return True

        except RecursionError:
            mess = QtGui.QMessageBox.warning(self, "Error",
                                                 "A graph cannot be contained in itself.")
            return False


    @lock_notify
    def add_graphical_annotation(self, position=None):
        """ Add text annotation """

        if(not annotation.is_available()):
            mess = QtGui.QMessageBox.warning(None, "Error",
                                             "This function need PyQT >= 4.2")
            return

        # Get Position from cursor
        if(not position) :
            position = self.mapToScene(
            self.mapFromGlobal(self.cursor().pos()))

        # Add new node
        pkgmanager = PackageManager()
        pkg = pkgmanager["System"]
        factory = pkg.get_factory("annotation")

        self.add_new_node(factory, position)
        
         
    def dropEvent(self, event):

        if (event.mimeData().hasFormat("openalea/nodefactory")):
            pieceData = event.mimeData().data("openalea/nodefactory")
            dataStream = QtCore.QDataStream(pieceData, QtCore.QIODevice.ReadOnly)
            
            package_id = QtCore.QString()
            factory_id = QtCore.QString()
            
            dataStream >> package_id >> factory_id

            # Add new node
            pkgmanager = PackageManager()
            pkg = pkgmanager[str(package_id)]
            factory = pkg.get_factory(str(factory_id))

            position = self.mapToScene(event.pos())
                    
            self.add_new_node(factory, position)

            event.setDropAction(QtCore.Qt.MoveAction)
            event.accept()

        else:
            QtGui.QGraphicsView.dropEvent(self, event)

    # Keybord Event
    def keyPressEvent(self, e):

        QtGui.QGraphicsView.keyPressEvent(self, e)
        
        key   = e.key()
        if( key == QtCore.Qt.Key_Delete):
            self.remove_selection()

        elif(key == QtCore.Qt.Key_Space):
            self.setDragMode(QtGui.QGraphicsView.ScrollHandDrag)


    def keyReleaseEvent(self, e):
        """ Key """
        QtGui.QGraphicsView.keyReleaseEvent(self, e)
        key   = e.key()
        if(key == QtCore.Qt.Key_Space):
            self.setDragMode(QtGui.QGraphicsView.RubberBandDrag)


    def event(self, event):
        """ Main event handler """
        
        if (event.type() == QtCore.QEvent.ToolTip):
            item = self.itemAt(event.pos())
            if(item and isinstance(item, Connector)):
                txt = item.update_tooltip()

        return QtGui.QGraphicsView.event(self, event)
 

    def contextMenuEvent(self, event):
        """ Context menu event : Display the menu"""

        if(self.itemAt(event.pos())):
           QtGui.QGraphicsView.contextMenuEvent(self, event)
           return

        menu = QtGui.QMenu(self)
        action = menu.addAction("Add Annotation")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.add_graphical_annotation)
        
        menu.move(event.globalPos())
        menu.show()
        event.accept()

      

# Utility function

def port_name( name, interface ):
    """ Return the port name str """
    iname = 'Any'
    if(interface):
        try:
            iname = interface.__name__
        except AttributeError:
            try:
                iname = interface.__class__.__name__
            except AttributeError:
                iname = str(interface)
    return '%s(%s)'%(name,iname)



    

class GraphicalNode(QtGui.QGraphicsItem, AbstractListener):
    """ Represent a node in the graphwidget """

    def __init__(self, graphview, elt_id):
        """
        @param graphview : EditGraphWidget container
        @param elt_id : id in the graph
        """

        scene = graphview.scene()
        QtGui.QGraphicsItem.__init__(self)

        # members
        self.elt_id = elt_id
        self.graphview = graphview
        self.subnode = self.graphview.node.node(elt_id)
        
        self.nb_cin = 0
        self.connector_in = [None] * self.subnode.get_nb_input()
        self.connector_out = [None] * self.subnode.get_nb_output()

        self.sizey = 32
        self.sizex = 20


        # Record item as a listener for the subnode
        self.ismodified = self.subnode.modified
        self.initialise(self.subnode)

        self.setFlag(QtGui.QGraphicsItem.GraphicsItemFlag(
            QtGui.QGraphicsItem.ItemIsMovable +
            QtGui.QGraphicsItem.ItemIsSelectable))
        self.setZValue(1)

        
        # Set ToolTip
        doc= self.subnode.__doc__
        if doc:
            doc = doc.split('\n')
            doc = [x.strip() for x in doc] 
            doc = '\n'.join(doc)
            self.setToolTip( "Class : %s\n"%(self.subnode.__class__.__name__) +
                             "Documentation : \n%s"%(doc,))
        else:
            if(self.subnode.factory):
                desc = self.subnode.factory.description
            else : desc = ""
            self.setToolTip( "Class : %s\n"%(self.subnode.__class__.__name__)+
                             "Description :%s\n" %(desc)
                             )
                              

        # Font and box size
        self.font = self.graphview.font()
        self.font.setBold(True)
        self.font.setPointSize(10)

        # Add to scene
        scene.addItem(self)

        self.set_connectors()

        # Set Position
        try:
            x = self.subnode.internal_data['posx']
            y = self.subnode.internal_data['posy']
        except:
            (x,y) = (10,10)
        self.setPos(QtCore.QPointF(x,y))

        self.adjust_size()


    def set_connectors(self):
        """ Add connectors """

        scene = self.graphview.scene()
        
        self.nb_cin = 0
        for i,desc in enumerate(self.subnode.input_desc):

            hide = self.subnode.is_port_hidden(i)
            # hidden connector
            if(hide and self.subnode.input_states[i] is not "connected"):
                c = self.connector_in[i]
                if(c):
                    self.scene().removeItem(c)
                    del c
                    self.connector_in[i] = None
                continue

            # show connector (update if necessary)
            elif(not self.connector_in[i]):
                name = desc['name']
                interface = desc.get('interface', None)
                tip = port_name(name,interface)
                self.connector_in[i] = ConnectorIn(self.graphview, self,
                                                   scene, i, tip)
            # nb connector
            self.nb_cin += 1 
                
            
        for i,desc in enumerate(self.subnode.output_desc):
            if(not self.connector_out[i]): # update if necessary
                name = desc['name']
                interface = desc.get('interface', None)
                tip = port_name(name,interface)

                self.connector_out[i] = ConnectorOut(self.graphview, self,
                                                     scene, i, tip)


    def adjust_size(self, force=False):
        """ Compute the box size """

        fm = QtGui.QFontMetrics(self.font);
        newsizex = fm.width(self.get_caption()) + 20;
        # when the text is small but there are lots of ports, 
        # add more space.
        nb_ports = max(self.nb_cin, len(self.connector_out))
        newsizex = max( nb_ports * Connector.WIDTH * 2, newsizex)
        
        if(newsizex != self.sizex or force):
            self.sizex = newsizex

            i = 0
            # i index can differ from real index since port can hidden
            for c in self.connector_in:
                if(not c) : continue
                c.adjust_position(self, i, self.nb_cin)
                c.adjust()
                i += 1

            nb_cout = len(self.connector_out)
            for i,c in enumerate(self.connector_out):
                c.adjust_position(self, i, nb_cout)
                c.adjust()


    def get_caption(self):
        """ Return the node caption (convenience)"""
        
        return self.subnode.caption


    def notify(self, sender, event):
        """ Notification sended by the node associated to the item """

        if(event and
           event[0] == "caption_modified" or
           event[0] == "data_modified"):

            self.adjust_size()
            self.update()
            QtGui.QApplication.processEvents()

        elif(event and
             event[0] == "port_modified"):
            self.set_connectors()
            self.adjust_size(force=True)
            self.update()

            # del widget
            self.graphview.close_node_dialog(self.elt_id)
             
           
        elif(self.ismodified != sender.modified):
            self.ismodified = sender.modified or not sender.lazy
            self.update()
            QtGui.QApplication.processEvents()


    def get_id(self):
        return self.elt_id
    

    def get_input_connector(self, index):

        return self.connector_in[index]
        

    def get_output_connector(self, index):

        return self.connector_out[index]


    def remove_connections(self):
        """ Remove edge connected to this item """ 

        for cin in self.connector_in:
            for e in list(cin.edge_list):
                e.remove()
            #cout.edge_list = []
                
        for cout in self.connector_out:
            for e in list(cout.edge_list):
                e.remove()
            #cout.edge_list = []
                

    def boundingRect(self):
        adjust = 4.0
        return QtCore.QRectF(0 , 0,
                             self.sizex + adjust, self.sizey + adjust)


    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(0, 0, self.sizex, self.sizey)
        return path


    def paint(self, painter, option, widget):
        
        # Shadow
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(100, 100, 100, 50))
        painter.drawRoundRect(3, 3, self.sizex, self.sizey)

        # Draw Box
        if hasattr(self.subnode,'raise_exception'):
            color = QtGui.QColor(255, 0, 0, 255)            
            if(self.isSelected()):
                secondcolor = QtGui.QColor(0, 0, 0, 255)
            else:
                secondcolor = QtGui.QColor(100, 0, 0, 255)
        else:
            if(self.isSelected()):
                color = QtGui.QColor(180, 180, 180, 180)
            else:
                color = QtGui.QColor(255, 255, 255, 100)

            if(self.ismodified):
                secondcolor = QtGui.QColor(255, 0, 0, 200)        
            else:
                secondcolor = QtGui.QColor(0, 0, 255, 200)
            
        
        gradient = QtGui.QLinearGradient(0, 0, 0, 100)
        gradient.setColorAt(0.0, color)
        gradient.setColorAt(1.0, secondcolor)
        painter.setBrush(QtGui.QBrush(gradient))
        
        painter.setPen(QtGui.QPen(QtCore.Qt.black, 1))
        painter.drawRoundRect(0, 0, self.sizex, self.sizey)
        
        # Draw Text
        textRect = QtCore.QRectF(0, 0, self.sizex, self.sizey)
        painter.setFont(self.font)
        painter.setPen(QtCore.Qt.black)
        painter.drawText(textRect, QtCore.Qt.AlignCenter,
                         self.get_caption())

#         # Draw Lazy symbol
#         if(self.subnode.lazy):
#             painter.setPen(QtGui.QPen(QtCore.Qt.darkMagenta, 1))
#             painter.drawRoundRect(0, 0, self.sizex, self.sizey)

        


    def itemChange(self, change, value):
        """ Callback when item has been modified (move...) """

        ret = QtGui.QGraphicsItem.itemChange(self, change, value)
        
        if (change == QtGui.QGraphicsItem.ItemPositionChange):
            
            for c in self.connector_in :
                if(c): c.adjust()
            for c in self.connector_out :
                if(c): c.adjust()

            point = value.toPointF()
        
            self.subnode.set_data('posx', point.x(), False)
            self.subnode.set_data('posy', point.y(), False)
         
            #self.graphview.itemMoved(self, value)
            
#         elif (change == QtGui.QGraphicsItem.ItemSelectedChange):
#             v = value.toBool()
#             for c in self.connector_in :
#                 for e in c.edge_list : e.setSelected(v)
#             for c in self.connector_out :
#                 for e in c.edge_list : e.setSelected(v)
                
        return ret


    def mousePressEvent(self, event):
        self.update()
        QtGui.QGraphicsItem.mousePressEvent(self, event)


    def mouseReleaseEvent(self, event):
        self.update()
        QtGui.QGraphicsItem.mouseReleaseEvent(self, event)


    def mouseDoubleClickEvent(self, event):

        # Read settings
        try:
            localsettings = Settings()
            str = localsettings.get("UI", "DoubleClick")
        except:
            str = "['open']"

        if('open' in str):
            self.graphview.open_item(self.elt_id)
            
        if('run' in str):
            self.run_node()
            

    @lock_notify
    def mouseMoveEvent(self, event):
        QtGui.QGraphicsItem.mouseMoveEvent(self, event)


    def contextMenuEvent(self, event):
        """ Context menu event : Display the menu"""

        menu = QtGui.QMenu(self.graphview)

        action = menu.addAction("Run")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.run_node)
        
        action = menu.addAction("Open Widget")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.open_widget)

        action = menu.addAction("Delete")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.remove)
        
        action = menu.addAction("Caption")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.set_caption)

        action = menu.addAction("Reset")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.subnode.reset)

        action = menu.addAction("Show/Hide ports")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.show_ports)

        action = menu.addAction("Internals")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.set_internals)
        
        
#         action = menu.addAction("Edit")
#         self.scene().connect(action, QtCore.SIGNAL("activated()"), self.edit_code)

        menu.move(event.screenPos())
        menu.show()

        event.accept()


    def show_ports(self):
        """ Open port show/hide dialog """

        editor = ShowPortDialog(self.subnode, self.graphview)
        editor.exec_()
        


    def set_internals(self):
        """ Edit node internal data """
        editor = DictEditor(self.subnode.internal_data, self.graphview)
        ret = editor.exec_()

        if(ret):
            for k in editor.modified_key:
                self.subnode.set_data(k, editor.pdict[k])
            
    @exception_display
    @busy_cursor
    def run_node(self):
        """ Run the current node """
        self.graphview.node.eval_as_expression(self.elt_id)


    def open_widget(self):
        """ Open widget in dialog """
        self.graphview.open_item(self.elt_id)


    def remove(self):
        """ Remove current node """
        self.graphview.remove_node(self.elt_id)
        

    def enable_in_widget(self):
        pass


    def set_caption(self):
        """ Open a input dialog to set node caption """

        n = self.subnode
        (result, ok) = QtGui.QInputDialog.getText(self.graphview, "Node caption", "",
                                   QtGui.QLineEdit.Normal, n.caption)
        if(ok):
            n.caption = str(result)


#     def edit_code(self):
#         """ Edit node code """

#         factory = self.subnode.factory
#         if(not factory) : return
#         widget = factory.instantiate_widget(node=self.subnode, edit=True)
        
#          # Open Code editor dialog
#         dialog = QtGui.QDialog(self.graphview)
#         dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose)
#         widget.setParent(dialog)
                
#         vboxlayout = QtGui.QVBoxLayout(dialog)
#         vboxlayout.setMargin(3)
#         vboxlayout.setSpacing(5)
#         vboxlayout.addWidget(widget)

#         dialog.setWindowTitle(self.subnode.get_caption())
#         dialog.show()
       


################################################################################

class Connector(QtGui.QGraphicsEllipseItem):
    """ A node connector """
    WIDTH = 12
    HEIGHT = 8

    def __init__(self, graphview, parent, scene, index, tooltip=""):
        """
        @param graphview : EditGraphWidget container
        @param parent : QGraphicsItem parent
        @param scene : QGraphicsScene container
        @param index : connector index
        """
        
        QtGui.QGraphicsItem.__init__(self, parent, scene)

        self.mindex = index
        self.graphview = weakref.ref(graphview)

        self.base_tooltip = tooltip
        self.update_tooltip()
        self.setRect(0, 0, self.WIDTH, self.HEIGHT)

        gradient = QtGui.QRadialGradient(-3, -3, 10)
        gradient.setCenter(3, 3)
        gradient.setFocalPoint(3, 3)
        gradient.setColorAt(1, QtGui.QColor(QtCore.Qt.yellow).light(120))
        gradient.setColorAt(0, QtGui.QColor(QtCore.Qt.darkYellow).light(120))
        
        self.setBrush(QtGui.QBrush(gradient))
        self.setPen(QtGui.QPen(QtCore.Qt.black, 0))

        self.edge_list = []


    def index(self):
        return self.mindex


    def add_edge(self, edge):
        self.edge_list.append(edge)
        

    def adjust(self):
        for e in self.edge_list:
            e.adjust()


    def update_tooltip(self):
        self.setToolTip(self.base_tooltip)


#     def mouseMoveEvent(self, event):
#         QtGui.QGraphicsItem.mouseMoveEvent(self, event)


    def mousePressEvent(self, event):
        if (event.buttons() & QtCore.Qt.LeftButton):
            self.graphview().start_edge(self)
        
        QtGui.QGraphicsItem.mousePressEvent(self, event)




class ConnectorIn(Connector):
    """ Input node connector """

    def __init__(self, graphview, parent, scene, index, tooltip):

        Connector.__init__(self, graphview, parent, scene, index, tooltip)

        #self.adjust_position(parent, index, ntotal)
        self.setAcceptDrops(True)


    def update_tooltip(self):
        node = self.parentItem().subnode
        data = node.get_input(self.mindex)
        self.setToolTip("%s %s"%(self.base_tooltip, str(data)))

    
    def adjust_position(self, parentitem, index, ntotal):
        width = parentitem.sizex / float(ntotal+1)
        self.setPos((index+1) * width - self.WIDTH/2., - self.HEIGHT/2)


    # Drag and Drop from TreeView support
    def dragEnterEvent(self, event):
        event.setAccepted(event.mimeData().hasFormat("openalea/data_instance"))


    def dragMoveEvent(self, event):
        if ( event.mimeData().hasFormat("openalea/data_instance") ):
            event.setDropAction(QtCore.Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

            
    def dropEvent(self, event):

        if (event.mimeData().hasFormat("openalea/data_instance")):
            pieceData = event.mimeData().data("openalea/data_instance")
            dataStream = QtCore.QDataStream(pieceData, QtCore.QIODevice.ReadOnly)
            
            data_key = QtCore.QString()
            
            dataStream >> data_key
            data_key = str(data_key)

            from openalea.core.session import DataPool
            datapool = DataPool()  # Singleton

            node = self.parentItem().subnode
            data = node.set_input(self.mindex, datapool[data_key])

            event.setDropAction(QtCore.Qt.MoveAction)
            event.accept()

        else:
            event.ignore()

            


class ConnectorOut(Connector):
    """ Output node connector """

    def __init__(self, graphview, parent, scene, index, tooltip):
        Connector.__init__(self, graphview, parent, scene, index, tooltip)
        
        #self.adjust_position(parent, index, ntotal)

        
    def update_tooltip(self):
        node = self.parentItem().subnode
        data = node.get_output(self.mindex)
        self.setToolTip("%s %s"%(self.base_tooltip, str(data)))


    def adjust_position(self, parentitem, index, ntotal):
            
        width= parentitem.sizex / float(ntotal+1)
        self.setPos((index+1) * width - self.WIDTH/2., parentitem.sizey - self.HEIGHT/2)


    def contextMenuEvent(self, event):
        """ Context menu event : Display the menu"""

        menu = QtGui.QMenu(self.graphview())

        action = menu.addAction("Send to Pool")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.send_to_pool)

        action = menu.addAction("Print")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.print_value )

        menu.move(event.screenPos())
        menu.show()

        event.accept()


    def print_value(self):
        """ Print the value of the connector """

        node = self.parentItem().subnode
        data = node.get_output(self.mindex)
        print data
        

    def send_to_pool(self):

        (result, ok) = QtGui.QInputDialog.getText(self.graphview(), "Data Pool", "Instance name",
                                                      QtGui.QLineEdit.Normal, )
        if(ok):
            from openalea.core.session import DataPool
            datapool = DataPool()  # Singleton

            #self.parentItem().run_node()
            node = self.parentItem().subnode
            data = node.get_output(self.mindex)
            datapool[str(result)] = data




################################################################################

def edge_factory():
    try:
        settings = Settings()
        style = settings.get('UI', 'EdgeStyle')
    except:
        style = 'Line'

    if style == 'Line':
        return LinearEdgePath()
    elif style == 'Polyline':
        return PolylineEdgePath()
    else:
        return SplineEdgePath()


class LinearEdgePath(object):
    """ Draw edges as line. """
    def __init__(self): 
        self.p1 = QtCore.QPointF()
        self.p2 = QtCore.QPointF()

    def shape(self):
        path = QtGui.QPainterPath()

        # Enlarge selection zone
        diff = self.p2 - self.p1

        if( abs(diff.x()) > abs(diff.y())):
            dp = QtCore.QPointF(0, 10)
        else:
            dp = QtCore.QPointF(10, 0)
        
        p1 = self.p1 - dp
        p2 = self.p1 + dp
        p3 = self.p2 + dp
        p4 = self.p2 - dp
        poly = QtGui.QPolygonF([p1, p2, p3, p4])
        path.addPolygon(poly)
        
        return path

    def getPath( self, p1, p2 ):
        self.p1 = p1
        self.p2 = p2
        path = QtGui.QPainterPath(self.p1)
        path.lineTo(self.p2)
        return path

        
class PolylineEdgePath(LinearEdgePath):
    """ Edge as Polyline """
    
    WIDTH = 30
    def __init__(self): 
        LinearEdgePath.__init__(self)

    def shape(self):
        return None

    def getPath( self, p1, p2 ):
        self.p1 = p1
        self.p2 = p2
        path = QtGui.QPainterPath(self.p1)

        points = []

        sd= self.p2 - self.p1
        if abs(sd.x()) <= self.WIDTH: # draw a line
            pass
        elif sd.y() < 2 * self.WIDTH:
            s1 = self.p1 + QtCore.QPointF(0,self.WIDTH)
            d1 = self.p2 - QtCore.QPointF(0,self.WIDTH)

            s1d1= d1 -s1
            s2 = s1 + QtCore.QPointF(s1d1.x() / 2., 0)
            d2 = s2 + QtCore.QPointF(0, s1d1.y())
            points.extend([s1, s2, d2, d1])
        else:
            s1 = self.p1 + QtCore.QPointF(0, sd.y() / 2.)
            d1= self.p2 - QtCore.QPointF(0, sd.y() / 2.)
            points.extend([s1, d1])
        
        points.append(self.p2)
        for pt in points:
            path.lineTo(pt)

        return path


class SplineEdgePath(PolylineEdgePath):
    """ Edge as Spline """
    
    def __init__(self): 
        PolylineEdgePath.__init__(self)

    def getPath( self, p1, p2 ):
        self.p1 = p1
        self.p2 = p2
        path = QtGui.QPainterPath(self.p1)

        sd= self.p2- self.p1
        if abs(sd.x()) <= self.WIDTH: # draw a line
            path.lineTo(self.p2)
        elif sd.y() < self.WIDTH: 
            py = QtCore.QPointF(0, max(self.WIDTH, - sd.y()))
            path.cubicTo(self.p1 + py, self.p2 - py, self.p2)

        else:
            py = QtCore.QPointF(0, sd.y() / 2.)
            pm = (self.p1 + self.p2) / 2.
            path.quadTo(self.p1 + py, pm)
            path.quadTo(self.p2 - py, self.p2)

        return path
    

class AbstractEdge(QtGui.QGraphicsPathItem):
    """
    Base classe for edges 
    """

    def __init__(self, graphview, parent=None, scene=None):
        QtGui.QGraphicsPathItem.__init__(self, parent, scene)

        self.graph = graphview
        self.sourcePoint = QtCore.QPointF()
        self.destPoint = QtCore.QPointF()

        self.edge_path = edge_factory()
        path = self.edge_path.getPath(self.sourcePoint, self.destPoint)
        self.setPath(path)

        self.setPen(QtGui.QPen(QtCore.Qt.black, 3,
                               QtCore.Qt.SolidLine,
                               QtCore.Qt.RoundCap,
                               QtCore.Qt.RoundJoin))

        
    def shape(self):
        path = self.edge_path.shape()
        if not path:
            return QtGui.QGraphicsPathItem.shape(self)
        else:
            return path
        
    def update_line(self):
        path = self.edge_path.getPath(self.sourcePoint, self.destPoint)
        self.setPath(path)


class SemiEdge(AbstractEdge):
    """
    Represents an edge during its creation
    It is connected to one connector only
    """

    def __init__(self, graphview, connector, parent=None, scene=None):
        AbstractEdge.__init__(self, graphview, parent, scene)

        self.connect = connector
        self.sourcePoint = self.mapFromItem(connector, connector.rect().center())


    def connector(self):
        return self.connect


    def setMousePoint(self, scene_point):
        self.destPoint = scene_point
        self.update_line()
        self.update()
    


class Edge(AbstractEdge):
    """ An edge between two graphical nodes """
        
    def __init__(self, graphview, sourceNode, out_index, destNode, in_index,
                 parent=None, scene=None):
        """
        @param sourceNode : source GraphicalNode
        @param out_index : output connector index
        @param destNode : destination GraphicalNode
        @param in_index : input connector index
        """
        AbstractEdge.__init__(self, graphview, parent, scene)

        #self.setAcceptedMouseButtons(QtCore.Qt.NoButton)

        self.setFlag(QtGui.QGraphicsItem.GraphicsItemFlag(
            QtGui.QGraphicsItem.ItemIsSelectable))

        src = sourceNode.get_output_connector(out_index)
        if(src) : src.add_edge(self)

        dst = destNode.get_input_connector(in_index)
        if(dst) : dst.add_edge(self)

        self.source = src
        self.dest = dst
        self.adjust()


    def adjust(self):
        if not self.source or not self.dest:
            return

        source = self.source
        dest = self.dest
        line = QtCore.QLineF(self.mapFromItem(source, source.rect().center() ),
                              self.mapFromItem(dest, dest.rect().center() ))
       
        length = line.length()
        if length == 0.0:
            return
        self.prepareGeometryChange()
        self.sourcePoint = line.p1() 
        self.destPoint = line.p2()
        self.update_line()


    def itemChange(self, change, value):
        """ Callback when item has been modified (move...) """

        if (change == QtGui.QGraphicsItem.ItemSelectedChange):
            if(value.toBool()):
                color = QtCore.Qt.blue
            else:
                color = QtCore.Qt.black

            self.setPen(QtGui.QPen(color, 3,
                                   QtCore.Qt.SolidLine,
                                   QtCore.Qt.RoundCap,
                                   QtCore.Qt.RoundJoin))
        
                
        return QtGui.QGraphicsItem.itemChange(self, change, value)


    def contextMenuEvent(self, event):
        """ Context menu event : Display the menu"""

        menu = QtGui.QMenu(self.graph)

        action = menu.addAction("Delete connection")
        self.scene().connect(action, QtCore.SIGNAL("activated()"), self.remove)
        
        menu.move(event.screenPos())
        menu.show()

        event.accept()


    def remove(self):
        """ Remove the Edge """
        self.graph.remove_connection(self)


    
