# v.0.0.1 stable version 

# shot utils 
import os
import sys 
from functools import partial
from tool.utils import entityInfo 
from tool.utils import fileUtils 
from tool.utils import mayaTools 
from tool.utils import pipelineTools 
reload(pipelineTools)
import logging 

logger = logging.getLogger(__name__)
moduleFile = sys.modules[__name__].__file__
moduleDir = os.path.dirname(moduleFile)


try: 
    import maya.cmds as mc 
    import maya.OpenMayaUI as mui
    isMaya = True 
    # If inside Maya open Maya GUI
    def getMayaWindow():
        ptr = mui.MQtUtil.mainWindow()
        return wrapInstance(long(ptr), QtWidgets.QWidget)

except ImportError: 
    isMaya = False 

# import Qt
from Qt import QtGui, QtWidgets, QtCore, QtUiTools, wrapInstance
QtUiTools = QtUiTools()

def loadUI(uiPath, parent): 
    # read .ui directly
    dirname = os.path.dirname(uiPath)
    loader = QtUiTools.QUiLoader()
    loader.setWorkingDirectory(dirname)

    f = QtCore.QFile(uiPath)
    f.open(QtCore.QFile.ReadOnly)

    myWidget = loader.load(f, parent)

    f.close()
    return myWidget

def deleteUI(ui):
    if mc.window(ui, exists=True):
        mc.deleteUI(ui)
        deleteUI(ui)

def show(uiName = 'cleanAssetUI'):
    if isMaya:
        logger.info('Run in Maya\n')
        deleteUI(uiName)
        myApp = CoreUI(getMayaWindow())
        return myApp

    else:
        logger.info('Run in standalone\n')
        app = QtWidgets.QApplication(sys.argv)
        myApp = CoreUI()
        sys.exit(app.exec_())

class CoreUI(QtWidgets.QMainWindow):

    def __init__(self, parent=None):
        self.count = 0
        #Setup Window
        super(CoreUI, self).__init__(parent)

        uiFile = '%s/ui.ui' % moduleDir
        self.ui = loadUI(uiFile, self)
        self.ui.show()
        self.ui.setWindowTitle('Asset Frustum cleaner v.0.0.1')

        # step 
        self.cameraRangeStep = 4

        self.prefixSearch = 'Rig_Grp'
        self.inIcon = '%s/icons/in_icon.png' % moduleDir
        self.outIcon = '%s/icons/out_icon.png' % moduleDir
        self.noIcon = '%s/icons/no_icon.png' % moduleDir

        self.green = [0, 50, 0]
        self.red = [50, 0, 0]


        self.init_functions()
        self.init_signals()


    def init_functions(self): 
        self.set_tool_tip()
        self.set_ui()
        

    def init_signals(self): 
        # get camera asset 
        self.ui.analyse_pushButton.clicked.connect(self.analyse)
        self.ui.clearCache_pushButton.clicked.connect(self.clear_list)

        self.ui.asset_listWidget.itemSelectionChanged.connect(self.select)
        self.ui.assetInCamera_pushButton.clicked.connect(partial(self.selection, 'in'))
        self.ui.assetOutCamera_pushButton.clicked.connect(partial(self.selection, 'out'))

        self.ui.removeAsset_pushButton.clicked.connect(self.remove_reference)

        self.ui.asset_listWidget.customContextMenuRequested.connect(self.set_menu)


    def set_tool_tip(self): 
        pass


    def set_ui(self): 
        self.button_check()
        self.set_info()

        if self.read_cache(): 
            self.list_asset_ui()


    def button_check(self): 
        # button import check 
        dataFile = self.data_file()

        self.ui.clearCache_pushButton.setEnabled(False)
        if os.path.exists(dataFile): 
            self.ui.clearCache_pushButton.setEnabled(True)


    def set_info(self): 
        """ read info from rig and put on ui """
        # option for asset camera 
        startFrame = mc.playbackOptions(q=True, min=True)
        endFrame = mc.playbackOptions(q=True, max=True)
        self.ui.min_lineEdit.setText(str(startFrame))
        self.ui.max_lineEdit.setText(str(endFrame))
        self.ui.step_lineEdit.setText(str(self.cameraRangeStep))


    def selection(self, area): 
        """ select asset from area of circle """
        allItems = [self.ui.asset_listWidget.item(a) for a in range(self.ui.asset_listWidget.count())]
        inItems = [a for a in allItems if a.data(QtCore.Qt.UserRole)]
        outItems = [a for a in allItems if not a.data(QtCore.Qt.UserRole)]
        
        # deselect 
        for item in allItems: 
            item.setSelected(False)

        items = []

        if area == 'in': 
            items = inItems

        if area == 'out': 
            items = outItems 

        if items: 
            for item in items: 
                item.setSelected(True)

    def select(self): 
        items = self.ui.asset_listWidget.selectedItems()

        if items: 
            sels = [str(a.text()) for a in items]
            mc.select(sels)


    def set_menu(self, pos): 
        item = self.ui.asset_listWidget.currentItem()
        state = item.data(QtCore.Qt.UserRole)
        label = 'Set in camera'
        
        if state: 
            label = 'Set behind camera'

        menu = QtWidgets.QMenu(self)
        menu.addAction(label)
        # menu.addSeparator()

        menu.triggered.connect(partial(self.update_ui, item))

        menu.popup(self.ui.asset_listWidget.mapToGlobal(pos))
        result = menu.exec_(self.ui.asset_listWidget.mapToGlobal(pos))


    def remove_reference(self): 
        self.selection('out')
        sels = mc.ls(sl=True)

        if sels: 
            for sel in sels: 
                mayaTools.removeReference(sel)

        self.list_asset_ui()
        

    def update_ui(self, item, *args): 
        state = not item.data(QtCore.Qt.UserRole)
        iconPath = self.outIcon
        color = self.red
        if state: 
            iconPath = self.inIcon
            color = self.green 

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(iconPath),QtGui.QIcon.Normal,QtGui.QIcon.Off)
        item.setIcon(icon)
        item.setBackground(QtGui.QColor(color[0], color[1], color[2]))
        item.setData(QtCore.Qt.UserRole, state)


    def analyse(self): 
        # turn off / on mask 
        mayaTools.selectionMask('Marker', 0)
        mayaTools.selectionMask('Joint', 0)
        mayaTools.selectionMask('Curve', 0)
        mayaTools.selectionMask('Surface', 1)

        # clear cache 
        self.clear_cache()
        self.list_asset_ui()
        
        
    def list_asset_ui(self): 
        # analyse 
        objs = self.get_cameraview_asset()

        # interpret data 
        assets = pipelineTools.objs_to_asset(objs)
        allAssets = self.all_assets()

        # clear ui 
        self.ui.asset_listWidget.clear()

        # list ui 
        if assets and allAssets: 
            assets = [mc.ls(a)[0] for a in assets]
            self.list_asset(assets, allAssets)


    def get_cameraview_asset(self): 
        """ get asset from camera view """
        asRange = self.ui.range_checkBox.isChecked()
        startFrame = 0
        endFrame = 0
        step = 1

        if asRange: 
            startFrame = int(float(self.ui.min_lineEdit.text()))
            endFrame = int(float(self.ui.max_lineEdit.text()))
            step = int(float(self.ui.step_lineEdit.text()))

        data = self.read_cache()

        # run again 
        if not data: 
            logger.info('recalculating ...')
            objs = pipelineTools.get_object_from_viewport(startFrame=startFrame, endFrame=endFrame, increment=step, progressBar=True)
        # use cache 
        else: 
            logger.info('use cache')
            objs = data.get('objects')

        self.save_cache(objs)
        self.button_check()

        return objs


    def list_asset(self, assets, allAssets): 

        for asset in allAssets: 
            icon = self.outIcon
            color = self.red
            data = False
            
            if asset in assets: 
                icon = self.inIcon
                color = self.green
                data = True

            if not mc.objExists(asset): 
                icon = self.noIcon
            
            self.add_item(asset, icon, color, data)
        

    def clear_list(self): 
        self.ui.asset_listWidget.clear()
        self.clear_cache()


    def add_item(self, text, iconPath, color, data): 
        item = QtWidgets.QListWidgetItem(self.ui.asset_listWidget)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(iconPath),QtGui.QIcon.Normal,QtGui.QIcon.Off)
        item.setIcon(icon)
        item.setText(text)
        item.setData(QtCore.Qt.UserRole, data)
        item.setBackground(QtGui.QColor(color[0], color[1], color[2]))
        self.ui.asset_listWidget.setIconSize(QtCore.QSize(16, 16))


    def save_cache(self, objs): 
        dataFile = self.data_file()
        dataPath = os.path.dirname(dataFile)

        if not os.path.exists(dataPath): 
            os.makedirs(dataPath)

        fileUtils.ymlDumper(dataFile, {'objects': objs})

    def read_cache(self): 
        dataFile = self.data_file()
        if os.path.exists(dataFile): 
            data = fileUtils.ymlLoader(dataFile)
            return data


    def data_file(self): 
        shot = entityInfo.info()
        dataPath = shot.getShotData()
        step = shot.department()
        dataFile = '%s/%s' % (dataPath, 'cameraAsset_%s.yml' % step)
        return dataFile

    def clear_cache(self): 
        dataFile = self.data_file()
        if os.path.exists(dataFile): 
            os.remove(dataFile)
            logger.debug('Remove %s' % dataFile)
        else: 
            logger.debug('Cache has already been removed')

        self.button_check()

    def all_assets(self, reference=True): 
        """ get all assets in the scene by search wildcard for Rig_Grp """
        allAssets = [a for a in mc.ls('*:%s*' % self.prefixSearch) if mc.objectType(a) == 'transform']

        if reference: 
            allAssets = [a for a in allAssets if mc.referenceQuery(a, isNodeReferenced=True)]

        return allAssets


    def get_distance(self): 
        """ get distance from center from distanceDimensionShape node """
        return mc.getAttr(self.innerRadius)
