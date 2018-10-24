import sys, os
from os import path 
import struct
from socket import *  
import numpy as np
import time
import datetime
import threading
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from Ui_TimeDomainPlot import Ui_MainWindow

gSocketHeaderSize = 16
gSocketBodySize = 32 * 1024
gSocketBufSize = gSocketBodySize + gSocketHeaderSize

class UDPSocketClient:
    def __init__(self):
        self.mHost = '192.168.1.6'
        #self.mHost = '127.0.0.1'
        self.mPort = 6000 
        self.mBufSize = gSocketBodySize + gSocketHeaderSize
        self.mAddress = (self.mHost, self.mPort)
        self.mUDPClient = socket(AF_INET, SOCK_DGRAM)
        self.mData = None
        self.mUDPClient.settimeout(5)

    def setBufSize (self,  bufSize):
        self.mBufSize = bufSize
        
    def sendData(self):
        self.mUDPClient.sendto(self.mData,self.mAddress)
        self.mData = None # Clear data after send out

    def receiveData(self):
       self.mData, self.mAddress = self.mUDPClient.recvfrom(gSocketBufSize)
       return self.mData

class RealTimeThread(threading.Thread):  
    def __init__(self, axes, canvas, cha,  timeout):  
        super(RealTimeThread, self).__init__()  
        self.axes = axes
        self.canvas = canvas
        self.CHA = mainWindow.radioButton_CHA.isChecked()
        self.timeout = timeout 
        self.data = []
        self.data_ChA = []
        self.data_ChB = []
        self.stopped = False
        self.sampleRate = mainWindow.getSampleRate()
        self.recordLength = mainWindow.getRecordLength()
        self.volScale = mainWindow.getVoltageScale()
        self.offset = mainWindow.getOffset()     

    def run(self):  
        def bumatoyuanmaSingle(x):
          if (x > 32767): 
             x = x - 65536 
          return x
   
        def parseData(data, length,  withHead):
            data_ChA =[]
            data_ChB = []
            newdata = data
            if (withHead):
               newdata = data[16:]
               #newdata = data # just for testing
            else:
                newdata = data
                
            for pos in range(0, length*1024, 32):
                line = newdata[pos:pos+32]
                newline = ''
                # One line data
                for i in range(0, 32, 2):
                   #print (line[i:i+2])
                   newline =  newline + ("%04x" % int(struct.unpack('H',line[i:i+2])[0]))

                # Get CHA/CHB VALUE BY ABAB...
                for i in range(0,  64,  8):
                    dataA1= newline[i:i+2]
                    dataA2= newline[i+2:i+4]
                    dataA = dataA2 + dataA1
                    dataA = int (dataA,  16)
                    data_ChA.append(bumatoyuanmaSingle(dataA))
                    dataB1 = newline[i+4:i+6]
                    dataB2 = newline[i+6:i+8]
                    dataB = dataB2  + dataB1
                    dataB = int (dataB,  16)
                    data_ChB.append(bumatoyuanmaSingle(dataB))

            #print ("Channel A: Length:", len(data_ChA))
            #print ("Channel B: Length:", len(data_ChB))
            
            return [data_ChA, data_ChB]

#            if (mainWindow.radioButton_CHA.isChecked()):
#                return self.data_ChA
#            else:
#                return self.data_ChB 

        def receiveData():
#            mainWindow.sendCmdWRREG(0x2, 0x28)
#            mainWindow.sendCmdWRREG(0x2, 0x29)
#            time.sleep(1)
#            mainWindow.sendCmdWRREG(0x2, 0x2b)
            mainWindow.sendCmdRAW_AD_SAMPLE(self.recordLength * 4)
            mainWindow.receiveCmdRAW_AD_SAMPLE(self.recordLength * 4)
            return mainWindow.udpSocketClient.mData
                    
        def realtimecapture():
            print ("Real Time Capture.......")
            receiveTimes = int (self.recordLength / 8)

            mainWindow.sendCmdWRREG(0x2, 0x28)
            mainWindow.sendCmdWRREG(0x2, 0x29)
            time.sleep(1)
            mainWindow.sendCmdWRREG(0x2, 0x2b)

            while not self.stopped:
                self.data_ChA = []
                self.data_ChB = []
                if receiveTimes <= 1:
                    data = receiveData()
                    #print ("Receive Total Length:",  len(data))
                    if data:
                        data = parseData(data, self.recordLength * 4 ,  True )
                        self.data_ChA = data[0]
                        self.data_ChB = data[1]
                else:
                    for loop in range(0, receiveTimes):
                        data = receiveData()
                        if data:
                            data = parseData(data, 32,  True )
                            self.data_ChA = self.data_ChA + data[0]
                            self.data_ChB = self.data_ChB + data[1]
                        
                if (mainWindow.radioButton_CHA.isChecked()): 
                    on_draw(self.axes, self.canvas, self.data_ChA)
                else: 
                    on_draw(self.axes, self.canvas, self.data_ChB)

            if self.stopped:
                mainWindow.lastChAData = self.data_ChA 
                mainWindow.lastChBData = self.data_ChB
                
        def on_draw( axes, canvas, data):
                # clear the axes and redraw the plot anew
                axes.clear() 
                #axes.set_title('Signal')
                axes.set_xlabel('Time(μs)')
                axes.set_ylabel('Voltage')
                
                self.sampleRate = mainWindow.getSampleRate()
                #self.recordLength = mainWindow.getRecordLength()
                self.volScale = mainWindow.getVoltageScale()
                self.offset = mainWindow.getOffset()
                timespan = self.recordLength*1024/self.sampleRate # in us
                x = np.linspace(0, timespan, self.recordLength*1024)  
                #x = np.linspace(-self.sampleRate*1e6/2, self.sampleRate*1e6/2, self.recordLength*1024)  
                normalLimY = self.volScale * 10;
                axes.set_ylim(-normalLimY/2 + self.offset, normalLimY/2 + self.offset )
                ymajorLocator = MultipleLocator(self.volScale) 
                yminorLocator = MultipleLocator(self.volScale/2) 
                axes.yaxis.set_major_locator(ymajorLocator)
                axes.yaxis.set_minor_locator(yminorLocator)
                axes.grid(True)
                
                #print ("Plot X Length: ",  self.recordLength*1024)
                #print ("Plot Data Length: ",  len(data))
                axes.plot(x, data)
                canvas.draw()

        now = datetime.datetime.now()
        startTime = now.strftime('%Y-%m-%d-%H-%M-%S')
        subthread = threading.Thread(target=realtimecapture)
        subthread.setDaemon(True)  
        subthread.start()  
        
    def stop(self): 
        print ("Stop thread...")
        self.stopped = True  

    def isStopped(self):  
        return self.stopped  

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)

        self.dpi = 100
        self.signalframe = self.widget_Signal_TimeDomain
        self.figure = Figure((11.3, 6.3), dpi=self.dpi)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self.signalframe)
        self.axes = self.figure.add_subplot(111)
        #self.axes.set_title('Signal')
        self.axes.set_xlabel('Time(μs)')
        self.axes.set_ylabel('Voltage')
        #plt.subplots_adjust(left=0.2, bottom=0.2, right=0.8, top=0.8, hspace=0.2, wspace=0.3)
        
        timespan = self.getRecordLength()*1024/self.getSampleRate() # in us
        x = np.linspace(0, timespan, self.getRecordLength()*1024)  
        normalLimY = self.getVoltageScale() * 10;
        self.axes.set_ylim(-normalLimY/2 + self.getOffset(), normalLimY/2 + self.getOffset() )
        ymajorLocator = MultipleLocator(self.getVoltageScale()) 
        yminorLocator = MultipleLocator(self.getVoltageScale()/2) 
        self.axes.yaxis.set_major_locator(ymajorLocator)
        self.axes.yaxis.set_minor_locator(yminorLocator)
        self.axes.grid(True)
        
        
        self.figure.tight_layout()# Adjust spaces
        #self.NavToolbar = NavigationToolbar(self.canvas, self.signalframe)
        #self.addToolBar(QtCore.Qt.RightToolBarArea, NavigationToolbar(self.canvas, self.signalframe))
        self.toolbar = NavigationToolbar(self.canvas, self.signalframe)
        self.toolbar.hide()
        
        # Button slots
        self.pushButton_Home.clicked.connect(self.home)
        self.pushButton_Back.clicked.connect(self.back)
        self.pushButton_Forward.clicked.connect(self.forward)
        self.pushButton_Pan.clicked.connect(self.pan)
        self.pushButton_Zoom.clicked.connect(self.zoom)
        self.pushButton_SavePic.clicked.connect(self.savepic)
        
        # Init Socket
        self.udpSocketClient = UDPSocketClient()
        
        # Init Length
        self.sendCmdRecordLength(1)
        
        self.sendCmdWRREG(0x2,  0x20)
        self.sendCmdWRREG(0x2,  0x28)
        
        # Read sampleRate
        value = self.readCmdSampleRate()
        if value > 5:
            value = 0
        self.comboBox_SampleRate.setCurrentIndex(value)
        
        # The last data
        self.lastChAData = []
        self.lastChBData = []

    def home(self):
        self.toolbar.home()
    def back(self):
        self.toolbar.back()
    def forward(self):
        self.toolbar.forward ()
    def zoom(self):
        self.toolbar.zoom()
    def pan(self):
        self.toolbar.pan()
    def savepic(self):
        self.toolbar.save_figure()

    def sendcommand(self, cmdid, status, msgid, len, type, offset, apiversion, pad, CRC16,  cmdData):
          cmdid=struct.pack('H',htons(cmdid))
          status=struct.pack('H',htons(status))
          msgid=struct.pack('H',htons(msgid))
          len=struct.pack('H',htons(len))
          type=struct.pack('H',htons(type))
          offset=struct.pack('H',htons(offset))
          apiversion=struct.pack('B',apiversion) # 1 Byte unsigned char
          pad=struct.pack('B',pad) # 1 Byte unsigned char
          CRC16=struct.pack('H',htons(CRC16)) # 2 Byte unsigned short
          cmdHeader = cmdid + status + msgid + len + type + offset + apiversion + pad + CRC16
          
          if (cmdData != None):
              self.udpSocketClient.mData = cmdHeader + cmdData
          else:
              self.udpSocketClient.mData = cmdHeader
          
          self.udpSocketClient.sendData()
       
    def sendCmdTriggerType(self,  value): 
        type = mainWindow.getTriggerType()
        value = value << 2
        regAddr= 0x2 # 0x2, Bit[2], 0: Auot, 1: External
        regValue=type
        currentValue = self.readCmdTriggerType()
        currentValue = currentValue | value
        self.sendCmdWRREG(regAddr,  currentValue)

#    def receiveCmdTriggerType(self): 
#        global gSocketBodySize
#        gSocketBodySize = 8
#        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
#        mainWindow.udpSocketClient.receiveData() # Do nothing
    
    def readCmdTriggerType(self): 
        self.sendCmdRDREG(0x02,  0x00)
        data = mainWindow.udpSocketClient.receiveData()
        data = data[16:]
        value = int(struct.unpack('L',data[20:])[0])
        return value
    
    def sendCmdSampleRate(self, value): 
        global gSocketBodySize
        gSocketBodySize = 4
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        cmdData  =  struct.pack('L', htonl(value)) 
        self.sendcommand(0x5a09,0x0000,0x5a09,0x0004,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
        mainWindow.udpSocketClient.receiveData() # Do nothing
        
    def readCmdSampleRate(self): 
        global gSocketBodySize
        gSocketBodySize = 4
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        # Len is not cared
        self.sendcommand(0x5a0a,0x0000,0x5a0a,0x0004,0x0000,0x0000,0x00,0x00,0x0000, None )
        data = self.udpSocketClient.receiveData()
        value = int(struct.unpack('L',data[16:20])[0])
        return value
        
    def sendCmdRecordLength(self,  length): 
        #recordLength = self.getRecordLength()
        regAddr= 0x8
        regValue= length
        self.sendCmdWRREG(regAddr,  regValue)

    def receiveCmdRecordLength(self): 
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        self.udpSocketClient.receiveData() # Do nothing
   
    def sendCmdRAW_AD_SAMPLE(self,  length):
        #print (sys._getframe().f_code.co_name)        
        global gSocketBodySize
        gSocketBodySize = length*1024
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        len = 0 #self.getRecordLength()
        self.sendcommand(0x5a04,0x0000,0x5a04,len,0x0000,0x0000,0x00,0x00,0x0000, None)
          
    def receiveCmdRAW_AD_SAMPLE(self,  length):
        global gSocketBodySize
        gSocketBodySize =  length*1024
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        mainWindow.udpSocketClient.receiveData()
    
    def sendCmdWRREG(self,  regAddress,  regValue):
        #print (sys._getframe().f_code.co_name)
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        cmdData  =  struct.pack('L', htonl(regAddress)) +  struct.pack('L', htonl(regValue))
        self.sendcommand(0x5a02,0x0000,0x5a02,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
        self.udpSocketClient.receiveData() # Do nothing
        
    def sendCmdRDREG(self,  regAddress,  regValue):
        #print (sys._getframe().f_code.co_name)
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        cmdData  =  struct.pack('L', htonl(regAddress)) +  struct.pack('L', htonl(regValue))
        self.sendcommand(0x5a01,0x0000,0x5a01,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
    
    def getTriggerType(self):
        index = self.comboBox_TriggerDomain.currentIndex()
        return int(index)
        
    def getSampleRate(self):
        index = self.comboBox_SampleRate.currentText()
        return int(index)
        
    def getRecordLength(self):
        index = self.comboBox_RecordLength.currentIndex()
        return 2**index
        
    def getVoltageScale(self):
        volScale = 200
        volScaleStr = self.lineEdit_VolScale.text()
        volScale = 200
        if (('-' )  == volScaleStr or "" == volScaleStr):
            volScale = 200
        else:
            volScale = int(volScaleStr) 
                
        return volScale
        
    def getOffset(self):
        offset = 0
        offsetStr = self.lineEdit_Offset.text();
        if (('-' )  == offsetStr or "" == offsetStr):
            offset = 0
        else:
            offset = int(offsetStr) 
                
        return offset
    
    @pyqtSlot()
    def on_pushButton_Stop_TimeDomain_clicked(self):
        """
        Slot documentation goes here.
        """
        self.realTimeThread.stop()
        self.pushButton_Start_TimeDomain.setEnabled(True)
        self.pushButton_Stop_TimeDomain.setEnabled(False)
        self.pushButton_Save_TimeDomain.setEnabled(True)
        self.comboBox_RecordLength.setEnabled(True)
        self.comboBox_SampleRate.setEnabled(True)
        self.comboBox_TriggerDomain.setEnabled(True)
    
    @pyqtSlot()
    def on_pushButton_Start_TimeDomain_clicked(self):
        """
        Slot documentation goes here.
        """
        self.pushButton_Start_TimeDomain.setEnabled(False)
        self.pushButton_Stop_TimeDomain.setEnabled(True)
        self.pushButton_Save_TimeDomain.setEnabled(False)
        self.comboBox_RecordLength.setEnabled(False)
        self.comboBox_SampleRate.setEnabled(False)
        self.comboBox_TriggerDomain.setEnabled(False)
        self.realTimeThread = RealTimeThread(self.axes, self.canvas, self.radioButton_CHA.isChecked(), 1.0)
        self.realTimeThread.setDaemon(True)
        self.realTimeThread.start()
    
    @pyqtSlot()
    def on_pushButton_Save_TimeDomain_clicked(self):
        """
        Slot documentation goes here.
        """
        # Write into file
        now = datetime.datetime.now()
        currentTime = now.strftime('%Y-%m-%d-%H-%M-%S') 
        FileName_CHA = "ChA-" + currentTime + ".txt"
        File_CHA=open(FileName_CHA,'w')
        FileName_CHB = "ChB-" + currentTime + ".txt"
        File_CHB=open(FileName_CHB,'w')
        for pos in range(0, len(self.lastChAData)):
            File_CHA.write(str(self.lastChAData[pos]))
            File_CHA.write('\n')
            File_CHB.write(str(self.lastChBData[pos]))
            File_CHB.write('\n')
            
        File_CHA.close()
        File_CHB.close()
        
#        self.lastChAData = []
#        self.lastChBData = []
        
    @pyqtSlot(int)
    def on_comboBox_TriggerDomain_currentIndexChanged(self, index):
        """
        Slot documentation goes here.
        
        @param index DESCRIPTION
        @type int
        """
        self.sendCmdTriggerType(index)
        
        # if it is exteranl trigger, need to monitor
        if value == 1:
            # start to thread to monitor register value
            # To be implemented
            l = 1
        
    @pyqtSlot(int)
    def on_comboBox_SampleRate_currentIndexChanged(self, index):
        """
        Slot documentation goes here.
        
        @param index DESCRIPTION
        @type int
        """
        if index > -1:
            self.sendCmdSampleRate(index)
        
    @pyqtSlot(int)
    def on_comboBox_RecordLength_currentIndexChanged(self, index):
        """
        Slot documentation goes here.
        
        @param index DESCRIPTION
        @type int
        """
        # TODO: not implemented yet
        self.sendCmdRecordLength(2**index)
  
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
